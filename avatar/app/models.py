from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class VideoStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Enums from DB
class SourceType(str, Enum):
    UPLOAD = "upload"
    PRESET = "preset"
    AI_GENERATED = "ai_generated"

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class MontageStatus(str, Enum):
    RENDERING = "rendering"
    READY = "ready"
    ERROR = "error"

# Models for Request/Response
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

# DB Models

# 2. Avatars
class AvatarBase(BaseModel):
    image_url: str
    source_type: SourceType = SourceType.UPLOAD
    generation_prompt: Optional[str] = None

class AvatarCreate(AvatarBase):
    pass

class Avatar(AvatarBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 3. Reference Motions
class ReferenceMotionBase(BaseModel):
    video_url: str
    thumbnail_url: Optional[str] = None
    label: Optional[str] = None
    duration_seconds: float

class ReferenceMotionCreate(ReferenceMotionBase):
    pass

class ReferenceMotion(ReferenceMotionBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 4. Motion Cache
class MotionCacheBase(BaseModel):
    avatar_id: uuid.UUID
    reference_id: uuid.UUID
    motion_video_url: Optional[str] = None
    motion_thumbnail_url: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    external_job_id: Optional[str] = None
    error_log: Optional[str] = None

class MotionCacheCreate(BaseModel):
    avatar_id: uuid.UUID
    reference_id: uuid.UUID

class MotionCacheUpdate(BaseModel):
    motion_video_url: Optional[str] = None
    motion_thumbnail_url: Optional[str] = None
    status: Optional[JobStatus] = None
    external_job_id: Optional[str] = None
    error_log: Optional[str] = None

class MotionCache(MotionCacheBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 5. Background Library
class BackgroundVideoBase(BaseModel):
    video_url: str
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    duration_seconds: float

class BackgroundVideoCreate(BackgroundVideoBase):
    pass

class BackgroundVideo(BackgroundVideoBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# 6. Final Montages
class FinalMontageBase(BaseModel):
    motion_id: uuid.UUID
    bg_video_id: uuid.UUID
    final_video_url: Optional[str] = None
    final_thumbnail_url: Optional[str] = None
    status: MontageStatus = MontageStatus.RENDERING
    settings: Dict[str, Any] = {}

class FinalMontageCreate(BaseModel):
    motion_id: uuid.UUID
    bg_video_id: uuid.UUID
    settings: Optional[Dict[str, Any]] = {}

class FinalMontageUpdate(BaseModel):
    final_video_url: Optional[str] = None
    status: Optional[MontageStatus] = None
    settings: Optional[Dict[str, Any]] = None

class FinalMontage(FinalMontageBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

