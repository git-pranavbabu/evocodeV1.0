# agents/content_generator.py
import os
from operator import itemgetter
from google.cloud import secretmanager
import google.auth
import re

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.retrievers import EnsembleRetriever
from . import llm_provider

from models import UserProfile, Lesson

# The RAG chain is now built on-demand for each user, so we remove the global variable.

def get_rag_chain(user_profile: UserProfile):
    """
    Initializes a user-specific RAG chain by combining a global and a personal retriever.
    """
    print("Initializing RAG chain...")
    
    # Secret manager and LLM initialization
    try:
        _, project_id = google.auth.default()
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/groq-api-key/versions/latest"
        response = client.access_secret_version(name=name)
        key = response.payload.data.decode("UTF-8").strip()
        os.environ["GROQ_API_KEY"] = key
        print("Successfully loaded Groq API key from Secret Manager.")
    except Exception as e:
        print(f"FATAL: Could not load Groq API key from Secret Manager: {e}")
        raise
        
    llm = llm_provider.get_llm(temperature=0.7)
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )
    
    # --- CREATE TWO RETRIEVERS ---
    # 1. The global retriever for W3Schools content
    global_store = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings,
        collection_name="w3schools_python"
    )
    global_retriever = global_store.as_retriever(search_kwargs={"k": 2})

    # 2. The user-specific retriever
    retriever_list = [global_retriever]
    try:
        # Attempt to load the user's personal collection
        user_store = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings,
            collection_name=user_profile.userId
        )
        user_retriever = user_store.as_retriever(search_kwargs={"k": 2})
        retriever_list.append(user_retriever)
        print(f"Loaded personal knowledge base for user {user_profile.userId}.")
    except Exception:
        # This is expected if the user has no documents yet
        print(f"No personal knowledge base found for user {user_profile.userId}. Using global knowledge base only.")

    # --- COMBINE THEM WITH ENSEMBLE RETRIEVER ---
    ensemble_retriever = EnsembleRetriever(
        retrievers=retriever_list, weights=[0.5, 0.5] # Give equal weight to both sources
    )

    template = """
    You are an expert AI programming tutor. You have access to a global knowledge base and the user's personal notes.
    When generating a lesson, prioritize information from the user's personal notes if it is relevant.

    **User's Learning Style:** {learning_style_tags}
    **Topic to Teach:** {topic}
    **Relevant Information (from global knowledge base and user's notes):**
    {context}

    **Your Task:**
    1.  Generate a lesson to teach the user the specified topic, tailored to their learning style.
    2.  Generate a simple coding challenge as a quiz.
    3.  You MUST format your entire response by wrapping the lesson in <lesson> tags and the quiz in <quiz> tags.
    """
    prompt = PromptTemplate.from_template(template)
    
    rag_chain = (
        {
            "context": itemgetter("topic") | ensemble_retriever, # <-- Use the ensemble
            "topic": itemgetter("topic"),
            "learning_style_tags": itemgetter("learning_style_tags"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    print("RAG chain initialized successfully.")
    return rag_chain

def generate_content(topic: str, user_profile: UserProfile) -> tuple[str, str]:
    """Generates a personalized lesson using the ensemble RAG chain."""
    print(f"Generating content for topic: '{topic}' for user: '{user_profile.userName}'...")
    
    # The chain is now created on-demand for each user
    chain = get_rag_chain(user_profile)
    
    learning_tags = ", ".join(user_profile.learningProfile.tags) if user_profile.learningProfile.tags else "No specific style preference."
    input_data = { "topic": topic, "learning_style_tags": learning_tags }
    
    raw_output = chain.invoke(input_data)
    
    try:
        lesson_match = re.search(r'<lesson>(.*?)</lesson>', raw_output, re.DOTALL)
        quiz_match = re.search(r'<quiz>(.*?)</quiz>', raw_output, re.DOTALL)
        lesson_content = lesson_match.group(1).strip() if lesson_match else raw_output
        quiz_challenge = quiz_match.group(1).strip() if quiz_match else "No quiz could be generated for this topic."
    except Exception:
        lesson_content = raw_output
        quiz_challenge = "Error parsing the generated quiz."
        
    print("Content generation complete.")
    return (lesson_content, quiz_challenge)