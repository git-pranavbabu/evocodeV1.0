# build_vectorstore.py
import time
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

print("Starting the vector store creation process...")

# 1. Load the documents from our text file
loader = TextLoader("python_docs.txt")
documents = loader.load()
print(f"Loaded {len(documents)} document(s).")

# 2. Split the document into smaller chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
texts = text_splitter.split_documents(documents)
print(f"Split the document into {len(texts)} chunks.")

# 3. Define the embedding model
# This will download the model from Hugging Face on the first run
print("Loading the embedding model (this may take a moment on first run)...")
start_time = time.time()
model_name = "sentence-transformers/all-MiniLM-L6-v2"
model_kwargs = {'device': 'cpu'}
encode_kwargs = {'normalize_embeddings': False}
embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs=model_kwargs,
    encode_kwargs=encode_kwargs
)
end_time = time.time()
print(f"Embedding model loaded in {end_time - start_time:.2f} seconds.")

# 4. Create the Chroma vector store and persist it
print("Creating and persisting the vector store...")
start_time = time.time()
vectorstore = Chroma.from_documents(
    documents=texts, 
    embedding=embeddings, 
    persist_directory="./chroma_db"
)
end_time = time.time()
print(f"Vector store created in {end_time - start_time:.2f} seconds.")

print("\n✅ Vector store 'chroma_db' created successfully.")