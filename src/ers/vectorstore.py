from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

# 1. Initialize FREE local embedding model via Ollama
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# 2. Initialize ChromaDB
vector_store = Chroma(
    collection_name="security_logs",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

# 3. Add logs to vector database
def add_logs_to_store(logs: list[dict]):
    documents = []
    for log in logs:
        doc = Document(
            page_content=log["message"],
            metadata={
                "timestamp": log["timestamp"],
                "severity": log["severity"].upper(),
                "service_name": log["service_name"].lower()
            }
        )
        documents.append(doc)
    
    vector_store.add_documents(documents)