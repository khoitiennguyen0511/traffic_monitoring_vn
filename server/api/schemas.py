from pydantic import BaseModel
from typing import Optional

class ViolationResponse(BaseModel):
    status: str
    plate_text: Optional[str] = None
    confidence: Optional[float] = None
    message: Optional[str] = None
