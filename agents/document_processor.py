# agents/document_processor.py
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pypdf # <-- NEW IMPORT
from typing import IO

def process_and_store_document(user_id: str, file_obj: IO, filename: str) -> bool:
    """
    Extracts text from an uploaded file (.txt, .md, or .pdf), chunks it,
    and stores it in a user-specific Chroma collection.
    """
    try:
        print(f"Processing document '{filename}' for user: {user_id}")
        file_content = ""

        # --- NEW LOGIC TO HANDLE DIFFERENT FILE TYPES ---
        if filename.endswith('.pdf'):
            reader = pypdf.PdfReader(file_obj)
            for page in reader.pages:
                file_content += page.extract_text() + "\n"
        else: # .txt and .md files
            file_content = file_obj.read().decode('utf-8')
        # ---------------------------------------------------

        if not file_content.strip():
            print("Warning: Extracted content is empty.")
            return False

        # 1. Split document into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_text(file_content)
        
        # 2. Define the embedding model
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        
        # 3. Create a user-specific collection and add the documents
        Chroma.from_texts(
            texts=texts,
            embedding=embeddings,
            persist_directory="./chroma_db",
            collection_name=user_id
        )
        print(f"Successfully stored document '{filename}' for user: {user_id}")
        return True
    except Exception as e:
        print(f"Error processing document for user {user_id}: {e}")
        return False