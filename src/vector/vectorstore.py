import json
import os
from typing import Dict, List, Any, Optional
import chromadb

class SecurityLogVectorStore:
    def __init__(self, persist_directory: str = "./chroma_data"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="security_logs")

    def _chunk_and_format_log(self, raw_log: Dict[str, Any], max_chunk_chars: int = 500) -> List[Dict[str, Any]]:
        metadata = {
            "timestamp": raw_log.get("timestamp", "unknown"),
            "service_name": raw_log.get("service_name", "unknown"),
            "severity": raw_log.get("severity", raw_log.get("level", "INFO")),
            "trace_id": raw_log.get("trace_id", "none")
        }
        
        message = raw_log.get("message", "")
        lines = message.splitlines()
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Respect newline boundaries so multi-line stack traces aren't broken awkwardly
        for line in lines:
            line_len = len(line) + 1
            if current_length + line_len > max_chunk_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_len
            else:
                current_chunk.append(line)
                current_length += line_len
                
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        if not chunks:
            chunks = [""]

        formatted_documents = []
        for idx, chunk in enumerate(chunks):
            # Prepend strict JSON metadata header so the embedding model indexes structural context
            header_str = json.dumps(metadata)
            formatted_text = f"METADATA_HEADER: {header_str}\nLOG_CHUNK_{idx}: {chunk}"
            
            formatted_documents.append({
                "id": f"{metadata['trace_id']}_{idx}",
                "document": formatted_text,
                "metadata": {**metadata, "chunk_index": idx}
            })
            
        return formatted_documents

    def add_log(self, raw_log: Dict[str, Any]):
        processed_chunks = self._chunk_and_format_log(raw_log)
        for item in processed_chunks:
            self.collection.upsert(
                ids=[item["id"]],
                documents=[item["document"]],
                metadatas=[item["metadata"]]
            )

    def query_logs(self, query_text: str, n_results: int = 3, service_name: Optional[str] = None, severity: Optional[str] = None):
        # Build ChromaDB dynamic where filter
        where_conditions = []
        if service_name:
            where_conditions.append({"service_name": service_name})
        if severity:
            where_conditions.append({"severity": severity})
            
        where_clause = None
        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            where_clause = {"$and": where_conditions}

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_clause
        )
        return results