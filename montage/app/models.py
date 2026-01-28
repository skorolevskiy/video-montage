from typing import List, Optional
from pydantic import BaseModel, HttpUrl, constr
from enum import Enum
from datetime import datetime

class VideoStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubtitleItem(BaseModel):
    start: float
    end: float
    text: str

class SubtitleStyle(BaseModel):
    font_name: str = "Arial"
    font_size: int = 12
    font_color: str = "&Hffffff"
    background_color: str = "&H80000000"
    bold: bool = True
    alignment: int = 2
    margin_v: int = 30

class VideoMergeRequest(BaseModel):
    video_urls: List[str]
    output_filename: str = "merged_video.mp4"
    karaoke_mode: bool = False
    subtitles_data: Optional[List[SubtitleItem]] = None
    subtitle_style: Optional[SubtitleStyle] = None

class VideoCircleRequest(BaseModel):
    video_background_url: str
    video_circle_url: str
    background_volume: float = 1.0
    circle_volume: float = 1.0

class VideoInfoResponse(BaseModel):
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    file_size: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    ffmpeg_version: Optional[str] = None

class VideoStatusResponse(BaseModel):
    video_id: str
    status: VideoStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    download_url: Optional[str] = None
    error_message: Optional[str] = None

class VideoMergeResponse(BaseModel):
    video_id: str
    status: VideoStatus
    message: str
