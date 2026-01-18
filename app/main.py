from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import tempfile
import aiohttp
import urllib.parse
import logging
import traceback
from typing import List, Optional, Dict
import shutil
import uuid
import json
import redis
from datetime import datetime
import asyncio
from collections import OrderedDict

from models import (
    VideoMergeRequest, VideoInfoResponse, HealthResponse, 
    SubtitleStyle, SubtitleItem, VideoStatus, 
    VideoStatusResponse, VideoMergeResponse, VideoCircleRequest
)
from video_processor import VideoProcessor
from storage import StorageManager
from tasks import process_video_task, process_circle_video_task

app = FastAPI(
    title="Video Processing API",
    description="API for merging videos with music and subtitles",
    version="1.0.0"
)

# Redis for status storage
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
STATUS_EXPIRE_TIME = 86400  # 24 hours

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Error processing request {request.method} {request.url}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error", 
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

# Configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VIDEOS = 20
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.aac'}
TEMP_DIR = tempfile.mkdtemp(prefix='video_processing_')

def get_task_status(video_id: str) -> Optional[dict]:
    key = f"task:{video_id}"
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None

def set_initial_status(video_id: str):
    key = f"task:{video_id}"
    data = {
        "video_id": video_id,
        "status": VideoStatus.PROCESSING,
        "created_at": datetime.now().isoformat(),
        "progress": 0.0
    }
    redis_client.set(key, json.dumps(data), ex=STATUS_EXPIRE_TIME)
    return data

@app.post("/video-circle", response_model=VideoStatusResponse)
async def create_connected_video(
    request: VideoCircleRequest = Body(...)
):
    """
    Creates a new video request with circle overlay (video-in-circle)
    """
    video_id = str(uuid.uuid4())
    
    # Store initial status
    data = set_initial_status(video_id)
    
    # Start processing via Celery
    process_circle_video_task.delay(video_id, request.model_dump())
    
    return VideoStatusResponse(**data)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and FFmpeg availability"""
    processor = VideoProcessor()
    ffmpeg_version = processor.check_ffmpeg()
    
    # Check Redis
    try:
        redis_client.ping()
        redis_status = "connected"
    except:
        redis_status = "disconnected"

    if not ffmpeg_version:
        return HealthResponse(status="error", ffmpeg_version=None)
    return HealthResponse(status="ok", ffmpeg_version=ffmpeg_version)

@app.get("/video-status/{video_id}", response_model=VideoStatusResponse)
async def get_video_status(video_id: str):
    """Get status of video processing"""
    status_data = get_task_status(video_id)
    
    if not status_data:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Ensure all required fields are present
    if "status" not in status_data:
        status_data["status"] = VideoStatus.PROCESSING
    
    return VideoStatusResponse(**status_data)


class VideoMergeSimpleRequest(BaseModel):
    video_files: List[str]
    music_url: Optional[str] = None
    karaoke_mode: bool = False
    subtitles_data: List[SubtitleItem] = []
    output_filename: str = "output.mp4"

@app.post("/merge-videos", response_model=VideoMergeResponse)
async def merge_videos(
    request: VideoMergeSimpleRequest
):
    """Start video merge process"""
    logger.info(f"Received merge-videos request: {request}")
    try:
        # Validate request
        if len(request.video_files) > MAX_VIDEOS:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_VIDEOS} videos allowed")

        if request.music_url:
            parsed_url = urllib.parse.urlparse(request.music_url)
            file_ext = os.path.splitext(parsed_url.path)[1].lower()
            if not file_ext:
                file_ext = '.mp3'
            
            if file_ext not in SUPPORTED_AUDIO_FORMATS:
                raise HTTPException(status_code=400, detail="Unsupported audio format")

        # Generate unique ID for this task
        video_id = str(uuid.uuid4())

        # Create VideoMergeRequest for processing (internal model)
        video_merge_request_data = {
            "video_urls": request.video_files,
            "karaoke_mode": request.karaoke_mode,
            "subtitles_data": [s.model_dump() for s in request.subtitles_data] if request.subtitles_data else [],
            "output_filename": request.output_filename,
            "subtitle_style": None # Can be extended
        }

        # Initialize task status
        set_initial_status(video_id)

        # Start processing in background task queue
        process_video_task.delay(video_id, video_merge_request_data, request.music_url)

        return VideoMergeResponse(
            video_id=video_id,
            status=VideoStatus.PROCESSING,
            message="Video processing started"
        )

    except Exception as e:
        logger.error(f"Unexpected error in merge_videos: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/download/{video_id}")
async def download_video(video_id: str):
    """Download processed video (Redirect to MinIO)"""
    status_data = get_task_status(video_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Video not found")
        
    if status_data.get("status") != VideoStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video is not ready yet")
        
    object_name = status_data.get("object_name")
    if not object_name:
        raise HTTPException(status_code=500, detail="File path missing in task status")

    storage = StorageManager()
    url = storage.get_presigned_url(object_name)
    
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate download URL")
        
    return RedirectResponse(url=url)

@app.post("/create-subtitles")
async def create_subtitles(
    subtitles_data: List[SubtitleItem],
    style: Optional[SubtitleStyle] = None,
    output_format: str = "srt"
):
    """Create subtitle file without video"""
    if output_format not in ["srt", "ass"]:
        raise HTTPException(status_code=400, detail="Unsupported subtitle format")

    processor = VideoProcessor()
    try:
        output_file = os.path.join(TEMP_DIR, f"subtitles.srt") # Simplified
        if output_format == "srt":
            processor.create_srt_subtitles(subtitles_data, output_file)
        else:
            raise HTTPException(status_code=400, detail="ASS format not implemented yet")

        return FileResponse(
            output_file,
            media_type="text/plain",
            filename=f"subtitles.{output_format}"
        )
    finally:
        processor.cleanup()

@app.delete("/video/{video_id}")
async def delete_video_task(video_id: str):
    """Delete video task"""
    key = f"task:{video_id}"
    if not redis_client.exists(key):
        raise HTTPException(status_code=404, detail="Video task not found")
    
    redis_client.delete(key)
    # Note: We probably should delete from MinIO too, but keeping it simple for now
    return {"message": "Video task deleted"}

@app.on_event("shutdown")
def cleanup():
    """Clean up temporary directory on shutdown"""
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
            logger.info("Cleaned up main temporary directory")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
