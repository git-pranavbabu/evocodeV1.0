# agents/content_generator.py
import os
from operator import itemgetter
from google.cloud import secretmanager
import google.auth

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from models import UserProfile, Lesson

rag_chain = None

def get_rag_chain():
    global rag_chain
    if rag_chain is not None:
        return rag_chain

    print("Initializing RAG chain for the first time...")
    
    try:
        _, project_id = google.auth.default()
        secret_id = "groq-api-key"
        version_id = "latest"
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(name=name)
        
        key = response.payload.data.decode("UTF-8").strip()
        os.environ["GROQ_API_KEY"] = key
        
        # --- THIS IS THE DEBUGGING LINE ---
        print(f"DEBUG: Key retrieved. Length: {len(key)}. Starts with: {key[:8]}")
        
        print("Successfully loaded Groq API key from Secret Manager.")
    except Exception as e:
        print(f"FATAL: Could not load Groq API key from Secret Manager: {e}")
        raise e
    
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.7)
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )
    
    print("Loading documents and building in-memory vector store...")
    loader = TextLoader("python_docs.txt")
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    vectorstore = Chroma.from_documents(documents=texts, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    print("In-memory vector store built successfully.")

    template = """
    You are an expert AI programming tutor for a system called Evocode. Your goal is to generate a personalized, clear, and engaging lesson.

    **User's Learning Style:** {learning_style_tags}
    **Topic to Teach:** {topic}
    **Relevant Information from a Textbook:**
    {context}

    **Your Task:**
    Based on all the information above, generate a lesson to teach the user the specified topic.
    The lesson should be directly tailored to the user's learning style. For example, if they prefer 'provide_code_first', start with a complete code example. If they like 'use_analogy', include a relatable analogy.
    The lesson should be in Markdown format.
    """
    prompt = PromptTemplate.from_template(template)
    
    rag_chain = (
        {
            "context": itemgetter("topic") | retriever,
            "topic": itemgetter("topic"),
            "learning_style_tags": itemgetter("learning_style_tags"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    print("RAG chain initialized successfully.")
    return rag_chain

def generate_content(topic: str, user_profile: UserProfile) -> str:
    print(f"Generating content for topic: '{topic}' for user: '{user_profile.userName}'...")
    chain = get_rag_chain()
    learning_tags = ", ".join(user_profile.learningProfile.tags) if user_profile.learningProfile.tags else "No specific style preference."
    input_data = { "topic": topic, "learning_style_tags": learning_tags }
    lesson = chain.invoke(input_data)
    print("Content generation complete.")
    return lesson