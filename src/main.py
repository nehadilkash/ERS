from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.vector.vectorstore import SecurityLogVectorStore
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import json
from langchain_ollama import ChatOllama

# 1. Initialize FastAPI app
app = FastAPI(title="ERS - Event/Error RAG System (Free/Local)")

# 2. Initialize local LLM using Ollama
llm = ChatOllama(model="llama3.2", temperature=0)

# Pydantic models
class IngestRequest(BaseModel):
    logs: List[dict]

class QueryRequest(BaseModel):
    query: str
    service_name: Optional[str] = None
    severity: Optional[str] = None
    top_k: Optional[int] = 3

vector_store = SecurityLogVectorStore()

@app.post("/ingest")
def ingest_logs(payload: IngestRequest):
    try:
        count = 0
        for log in payload.logs:
            vector_store.add_log(log)
            count += 1
        return {"status": "success", "processed_logs": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Query Route
@app.post("/query")
def query_logs(payload: QueryRequest):
    try:
        # If service_name or severity are missing, use the Smart Extractor!
        service_name = payload.service_name
        severity = payload.severity
        search_query = payload.query

        if not service_name or not severity:
            # Assumes extract_filters_from_text is imported or defined in your module
            extracted = extract_filters_from_text(payload.query)
            service_name = service_name or extracted.get("service_name")
            severity = severity or extracted.get("severity")
            search_query = extracted.get("cleaned_query", payload.query)
            
        # Call your updated vector store query method
        results = vector_store.query_logs(
            query_text=search_query,
            n_results=3,
            service_name=service_name,
            severity=severity
        )

        # ChromaDB query returns dictionaries of documents and metadatas
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return {
                "query": payload.query,
                "cleaned_query": search_query,
                "response": "No matching logs were found in the database for your query criteria."
            }

        # Format retrieved documents for the prompt using the metadata headers & chunks
        context_str = "\n\n".join([
            f"[{meta.get('timestamp', 'N/A')}] [{meta.get('severity', 'N/A')}] [{meta.get('service_name', 'N/A')}]: {doc}"
            for doc, meta in zip(documents, metadatas)
        ])

        # Anti-Hallucination Guardrail Prompt
        template = """You are a cybersecurity log assistant. Answer the query strictly based on the provided log context. 
If the logs do not contain enough information to answer or verify a security vulnerability, state clearly: "I cannot verify this vulnerability based on the provided logs." 
Never invent or extrapolate security vulnerabilities that are not explicitly documented in the logs.

Context:
{context}

Query: {question}
Answer:"""

        prompt = ChatPromptTemplate.from_template(template)
        
        # Build and invoke chain
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"context": context_str, "question": payload.query})

        return {"query": payload.query, "cleaned_query": search_query, "response": response}

    except Exception as e:
        print(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 1. Health check to confirm FastAPI is running
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ERS"}

# 2. Inspect ChromaDB to see total log count
@app.get("/db/stats")
def db_stats():
    try:
        count = vector_store._collection.count()
        return {
            "status": "connected",
            "total_logs_stored": count,
            "collection_name": vector_store._collection.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def extract_filters_from_text(user_query: str) -> dict:
    """Uses local Ollama to parse natural language and extract metadata filters."""
    llm = ChatOllama(model="llama3.2", temperature=0)
    
    prompt = f"""
    You are an intelligent log router for a cybersecurity RAG system.
    Analyze the user's query and extract metadata filters.
    
    Valid service names: auth-service, payment-service, order-service, inventory-service
    Valid severities: CRITICAL, ERROR, WARNING, INFO
    
    Return ONLY a valid JSON object with these exact keys:
    - "service_name": string matching one of the valid service names above, or null if not specified.
    - "severity": string matching one of the valid severities above, or null if not specified.
    - "cleaned_query": the semantic search text with filter keywords removed.

    User Query: "{user_query}"
    """
    
    try:
        response = llm.invoke(prompt)
        # Clean up response text in case the model adds markdown code blocks
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        return data
    except Exception as e:
        # Fallback if parsing fails: return original query with no filters
        print(f"Filter extraction fallback triggered: {e}")
        return {
            "service_name": None,
            "severity": None,
            "cleaned_query": user_query
        }