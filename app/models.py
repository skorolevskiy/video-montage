from typing import List, Optional
from pydantic import BaseModel, HttpUrl, constr

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
    video_urls: List[HttpUrl]
    output_filename: str = "merged_video.mp4"
    karaoke_mode: bool = False
    subtitles_data: Optional[List[SubtitleItem]] = None
    subtitle_style: Optional[SubtitleStyle] = None

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
