from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from vectorstore import vector_store, add_logs_to_store
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

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

# Ingestion Route
@app.post("/ingest")
def ingest_logs(payload: IngestRequest):
    try:
        add_logs_to_store(payload.logs)
        return {"status": "success", "count": len(payload.logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Query Route
@app.post("/query")
def query_logs(payload: QueryRequest):
    try:
        # Build list of active filter conditions for ChromaDB
        conditions = []
        if payload.service_name:
            conditions.append({"service_name": payload.service_name.lower()})
        if payload.severity:
            conditions.append({"severity": payload.severity.upper()})

        # Format filter dictionary properly for ChromaDB
        chroma_filter = None
        if len(conditions) == 1:
            chroma_filter = conditions[0]
        elif len(conditions) > 1:
            chroma_filter = {"$and": conditions}

        # Search documents in ChromaDB with the correct filter syntax
        search_kwargs = {"k": 3}
        if chroma_filter:
            search_kwargs["filter"] = chroma_filter

        docs = vector_store.similarity_search(payload.query, **search_kwargs)

        if not docs:
            return {
                "query": payload.query,
                "response": "No matching logs were found in the database for your query criteria."
            }

        # Format retrieved documents for the prompt
        context_str = "\n\n".join([
            f"[{d.metadata.get('timestamp', 'N/A')}] [{d.metadata.get('severity', 'N/A')}] [{d.metadata.get('service_name', 'N/A')}]: {d.page_content}"
            for d in docs
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

        return {"query": payload.query, "response": response}

    except Exception as e:
        print(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))