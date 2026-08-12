from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SessionCreateResponse(BaseModel):
    id: int
    session_name: Optional[str] = None
    created_at: datetime
