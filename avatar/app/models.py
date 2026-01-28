from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class VideoStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AvatarRequest(BaseModel):
    prompt: str
    style: Optional[str] = "realistic"
    duration: int = 5

class AvatarStatusResponse(BaseModel):
    task_id: str
    status: VideoStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result_url: Optional[str] = None
    error_message: Optional[str] = None
