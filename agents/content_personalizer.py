# agents/content_personalizer.py
import os
from google.cloud import secretmanager
import google.auth

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from langchain_core.pydantic_v1 import BaseModel, Field
from . import llm_provider

from models import LearningProfile

validation_chain = None

# (The rest of the file is exactly the same and is correct)

class ValidationResult(BaseModel):
    is_approved: bool = Field(description="Whether the lesson is approved based on the criteria.")
    feedback: str = Field(description="Constructive feedback for the generator on how to improve the lesson. Be specific.")

def get_validation_chain():
    global validation_chain
    if validation_chain is not None:
        return validation_chain

    print("Initializing validation chain for the first time...")
    
    try:
        _, project_id = google.auth.default()
        secret_id = "groq-api-key"
        version_id = "latest"
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(name=name)
        
        os.environ["GROQ_API_KEY"] = response.payload.data.decode("UTF-8").strip()
        print("Successfully loaded Groq API key from Secret Manager.")
    except Exception as e:
        print(f"FATAL: Could not load Groq API key from Secret Manager: {e}")
        raise e
    
    llm = llm_provider.get_llm(temperature=0.7)
    parser = JsonOutputParser(pydantic_object=ValidationResult)
    
    template = """
    You are a Content Personalization Specialist. Your task is to review a draft lesson and ensure it matches the user's learning preferences.

    **User's Learning Preferences (Tags):**
    {learning_tags}

    **Draft Lesson:**
    ---
    {draft_lesson}
    ---

    **Your Task:**
    Review the draft lesson based *only* on the user's learning preferences.
    - Does it contain the elements requested by the tags? For example, if the user wants 'use_analogy', is there an analogy? If they want 'provide_code_first', does it start with code?
    - Provide your assessment in the requested JSON format.

    {format_instructions}
    """
    prompt = PromptTemplate(
        template=template,
        input_variables=["learning_tags", "draft_lesson"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    validation_chain = prompt | llm | parser
    print("Validation chain initialized successfully.")
    return validation_chain

def personalize_and_validate(draft_content: str, learning_profile: LearningProfile) -> tuple[bool, str]:
    print("Personalizer is validating the draft...")
    chain = get_validation_chain()
    tags = ", ".join(learning_profile.tags) if learning_profile.tags else "No specific preferences."
    if not learning_profile.tags:
        print("No specific tags. Approving by default.")
        return (True, "No specific preferences provided.")
    try:
        result = chain.invoke({ "learning_tags": tags, "draft_lesson": draft_content })
        print(f"Validation result: Approved={result['is_approved']}.")
        return (result['is_approved'], result['feedback'])
    except Exception as e:
        print(f"Error during validation: {e}")
        return (False, "There was an error parsing the validation response.")