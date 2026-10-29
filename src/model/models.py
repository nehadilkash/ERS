from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    query: str
    service_name: Optional[str] = None
    severity: Optional[str] = None