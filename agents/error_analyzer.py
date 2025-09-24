# agents/error_analyzer.py
import os
import json
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from . import llm_provider

# Load the knowledge graph to get the list of concepts
with open('KnowledgeGraph.json', 'r') as f:
    knowledge_graph = json.load(f)

def find_concepts_for_topic(topic_id: str) -> list[str]:
    """Finds the sub-concepts for a given topic ID in the knowledge graph."""
    for category in knowledge_graph.values():
        for topic_details in category.values():
            if topic_details["id"] == topic_id:
                return topic_details.get("concepts", [])
    return []

def analyze_error(topic_id: str, source_code: str, error_message: str) -> str:
    """Uses a shared LLM to analyze a code error."""
    print("Error Analyzer: Diagnosing user's mistake...")
    
    llm = llm_provider.get_llm(temperature=0)
    
    concepts = find_concepts_for_topic(topic_id)
    if not concepts:
        return "general_error"

    template = """
    You are an expert Python tutor. A student submitted the following code for a quiz on the topic of '{topic_id}' and it failed with an error.
    Your task is to identify which specific concept the student is misunderstanding.

    USER'S CODE:
    ```python
    {source_code}
    ```

    ERROR MESSAGE:
    ```
    {error_message}
    ```

    Based on the code and the error, which of the following concepts is the most likely source of the student's confusion?
    POSSIBLE CONCEPTS: {concepts}

    Respond with ONLY the single most relevant concept from the list.
    """
    
    prompt = PromptTemplate.from_template(template)
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = chain.invoke({
            "topic_id": topic_id,
            "source_code": source_code,
            "error_message": error_message,
            "concepts": ", ".join(concepts)
        })
        # Clean the result to ensure it matches a concept
        cleaned_result = result.strip().replace("'", "").replace('"', '')
        if cleaned_result in concepts:
            print(f"Error Analyzer identified weakness: {cleaned_result}")
            return cleaned_result
        else:
            print("Error Analyzer could not map LLM output to a known concept.")
            return "general_error"
    except Exception as e:
        print(f"Error during error analysis: {e}")
        return "general_error"