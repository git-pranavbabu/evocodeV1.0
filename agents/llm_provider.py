# agents/llm_provider.py
import os
from google.cloud import secretmanager
import google.auth
from langchain_groq import ChatGroq

groq_api_key = None

def load_groq_api_key():
    """
    Loads the Groq API key from Secret Manager and sets it as an environment variable.
    Ensures this is only done once.
    """
    global groq_api_key
    if groq_api_key:
        return

    print("Loading Groq API key for the first time...")
    try:
        _, project_id = google.auth.default()
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/groq-api-key/versions/latest"
        response = client.access_secret_version(name=name)
        key = response.payload.data.decode("UTF-8").strip()
        os.environ["GROQ_API_KEY"] = key
        groq_api_key = key
        print("Successfully loaded Groq API key from Secret Manager.")
    except Exception as e:
        print(f"FATAL: Could not load Groq API key from Secret Manager: {e}")
        raise

def get_llm(temperature: float = 0.7):
    """Initializes and returns a ChatGroq LLM instance."""
    load_groq_api_key()
    return ChatGroq(model_name="llama-3.1-8b-instant", temperature=temperature)