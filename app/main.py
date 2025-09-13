from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Request
from fastapi.responses import FileResponse, JSONResponse
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
from datetime import datetime
import asyncio
from collections import OrderedDict

from models import (
    VideoMergeRequest, VideoInfoResponse, HealthResponse, 
    SubtitleStyle, SubtitleItem, VideoStatus, 
    VideoStatusResponse, VideoMergeResponse
)
from video_processor import VideoProcessor

# In-memory storage for video processing status
# Using OrderedDict to maintain insertion order and limit size
MAX_STORAGE_ITEMS = 1000
video_tasks: OrderedDict[str, Dict] = OrderedDict()

app = FastAPI(
    title="Video Processing API",
    description="API for merging videos with music and subtitles",
    version="1.0.0"
)

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

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and FFmpeg availability"""
    processor = VideoProcessor()
    ffmpeg_version = processor.check_ffmpeg()
    if not ffmpeg_version:
        return HealthResponse(status="error", ffmpeg_version=None)
    return HealthResponse(status="ok", ffmpeg_version=ffmpeg_version)

@app.get("/video-status/{video_id}", response_model=VideoStatusResponse)
async def get_video_status(video_id: str):
    """Get status of video processing"""
    if video_id not in video_tasks:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return VideoStatusResponse(**video_tasks[video_id])

async def process_video(
    video_id: str,
    video_merge_request: VideoMergeRequest,
    music_path: str
):
    """Background task for video processing"""
    processor = VideoProcessor(TEMP_DIR)
    try:
        # Update status to processing
        video_tasks[video_id].update({
            "status": VideoStatus.PROCESSING,
            "progress": 0.0
        })

        # Process videos
        output_file = await processor.merge_videos(
            video_urls=[str(url) for url in video_merge_request.video_urls],
            music_path=music_path,
            subtitles_data=video_merge_request.subtitles_data,
            karaoke_mode=video_merge_request.karaoke_mode,
            subtitle_style=video_merge_request.subtitle_style,
            output_filename=video_merge_request.output_filename
        )

        # Update status to completed
        video_tasks[video_id].update({
            "status": VideoStatus.COMPLETED,
            "completed_at": datetime.now(),
            "progress": 100.0,
            "download_url": f"/download/{video_id}"
        })

        # Store output file path
        video_tasks[video_id]["output_file"] = output_file

    except Exception as e:
        # Update status to failed
        logger.error(f"Error in process_video for {video_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        video_tasks[video_id].update({
            "status": VideoStatus.FAILED,
            "error_message": str(e),
            "completed_at": datetime.now()
        })
        processor.cleanup()

class VideoMergeSimpleRequest(BaseModel):
    video_files: List[str]
    music_url: str
    karaoke_mode: bool = False
    subtitles_data: List[SubtitleItem] = []
    output_filename: str = "output.mp4"

@app.post("/merge-videos", response_model=VideoMergeResponse)
async def merge_videos(
    background_tasks: BackgroundTasks,
    request: VideoMergeSimpleRequest
):
    """Start video merge process"""
    logger.info(f"Received merge-videos request: {request}")
    try:
        # Validate request
        if len(request.video_files) > MAX_VIDEOS:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_VIDEOS} videos allowed")

        # Get file extension from URL
        parsed_url = urllib.parse.urlparse(request.music_url)
        file_ext = os.path.splitext(parsed_url.path)[1].lower()
        if not file_ext:
            file_ext = '.mp3'  # Default to mp3 if no extension in URL
        
        if file_ext not in SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(status_code=400, detail="Unsupported audio format")

        # Generate unique ID for this task
        video_id = str(uuid.uuid4())
        music_path = os.path.join(TEMP_DIR, f"music_{video_id}{file_ext}")

        # Download music file
        async with aiohttp.ClientSession() as session:
            async with session.get(request.music_url) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Could not download music file")
                
                content_length = response.content_length
                if content_length and content_length > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="Music file too large")

                # Save music file
                with open(music_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

        # Create VideoMergeRequest for processing
        video_merge_request = VideoMergeRequest(
            video_urls=request.video_files,
            karaoke_mode=request.karaoke_mode,
            subtitles_data=request.subtitles_data,
            output_filename=request.output_filename
        )

        # Initialize task status
        video_tasks[video_id] = {
            "video_id": video_id,
            "status": VideoStatus.PROCESSING,
            "created_at": datetime.now(),
            "progress": 0.0
        }

        # Limit storage size
        while len(video_tasks) > MAX_STORAGE_ITEMS:
            _, oldest_task = video_tasks.popitem(last=False)
            if "output_file" in oldest_task:
                try:
                    os.remove(oldest_task["output_file"])
                except:
                    pass

        # Start processing in background
        background_tasks.add_task(
            process_video,
            video_id,
            video_merge_request,
            music_path
        )

        return VideoMergeResponse(
            video_id=video_id,
            status=VideoStatus.PROCESSING,
            message="Video processing started"
        )

    except aiohttp.ClientError as e:
        logger.error(f"HTTP client error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Failed to download music file: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in merge_videos: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/download/{video_id}")
async def download_video(video_id: str):
    """Download processed video"""
    if video_id not in video_tasks:
        raise HTTPException(status_code=404, detail="Video not found")

    task = video_tasks[video_id]
    if task["status"] != VideoStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video is not ready yet")

    if "output_file" not in task:
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        task["output_file"],
        media_type="video/mp4",
        filename=os.path.basename(task["output_file"])
    )

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
        output_file = os.path.join(TEMP_DIR, f"subtitles.{output_format}")
        if output_format == "srt":
            processor.create_srt_subtitles(subtitles_data, output_file)
        else:
            # For ASS format (if implemented)
            raise HTTPException(status_code=400, detail="ASS format not implemented yet")

        return FileResponse(
            output_file,
            media_type="text/plain",
            filename=f"subtitles.{output_format}"
        )
    finally:
        processor.cleanup()

@app.on_event("shutdown")
def cleanup():
    """Clean up temporary directory on shutdown"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
