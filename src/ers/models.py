from pydantic import BaseModel
from typing import Optional

class LogEntry(BaseModel):
    timestamp: str  
    severity: str   
    service_name: str 
    message: str