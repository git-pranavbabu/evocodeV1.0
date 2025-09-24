# build_vectorstore.py
import time
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

print("Starting the vector store creation process...")

# 1. Load all documents from our scraped content directory
loader = DirectoryLoader("etl/scraped_content/", glob="**/*.txt", show_progress=True)
documents = loader.load()
print(f"Loaded {len(documents)} document(s) from scraped content.")

# 2. Split documents into smaller chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
texts = text_splitter.split_documents(documents)
print(f"Split documents into {len(texts)} chunks.")

# 3. Define the embedding model
print("Loading the embedding model...")
model_name = "sentence-transformers/all-MiniLM-L6-v2"
embeddings = HuggingFaceEmbeddings(model_name=model_name)
print("Embedding model loaded.")

# 4. Create the Chroma vector store and persist it in a named collection
print("Creating and persisting the vector store...")
start_time = time.time()
vectorstore = Chroma.from_documents(
    documents=texts, 
    embedding=embeddings, 
    persist_directory="./chroma_db",
    collection_name="w3schools_python"  # <-- This is the important change
)
end_time = time.time()
print(f"Vector store created in {end_time - start_time:.2f} seconds.")

print("\n✅ Global vector store 'w3schools_python' created successfully.")
