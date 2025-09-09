from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
from typing import List, Optional
import shutil

from models import VideoMergeRequest, VideoInfoResponse, HealthResponse, SubtitleStyle, SubtitleItem
from video_processor import VideoProcessor

app = FastAPI(
    title="Video Processing API",
    description="API for merging videos with music and subtitles",
    version="1.0.0"
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

@app.post("/video-info", response_model=VideoInfoResponse)
async def get_video_info(video_file: UploadFile = File(...)):
    """Get information about a video file"""
    if video_file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    try:
        shutil.copyfileobj(video_file.file, temp_file)
        temp_file.close()

        processor = VideoProcessor()
        info = processor.get_video_info(temp_file.name)
        return VideoInfoResponse(**info)
    finally:
        os.unlink(temp_file.name)

@app.post("/merge-videos")
async def merge_videos(
    background_tasks: BackgroundTasks,
    video_merge_request: VideoMergeRequest,
    music_file: UploadFile = File(...)
):
    """Merge videos with music and optional subtitles"""
    # Validate request
    if len(video_merge_request.video_urls) > MAX_VIDEOS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_VIDEOS} videos allowed")

    if music_file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Music file too large")

    file_ext = os.path.splitext(music_file.filename)[1].lower()
    if file_ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    # Create processor instance
    processor = VideoProcessor(TEMP_DIR)

    try:
        # Save music file
        music_path = os.path.join(TEMP_DIR, "music" + file_ext)
        with open(music_path, "wb") as f:
            shutil.copyfileobj(music_file.file, f)

        # Process videos
        output_file = await processor.merge_videos(
            video_urls=[str(url) for url in video_merge_request.video_urls],
            music_path=music_path,
            subtitles_data=video_merge_request.subtitles_data,
            karaoke_mode=video_merge_request.karaoke_mode,
            subtitle_style=video_merge_request.subtitle_style,
            output_filename=video_merge_request.output_filename
        )

        # Schedule cleanup
        background_tasks.add_task(processor.cleanup)

        return FileResponse(
            output_file,
            media_type="video/mp4",
            filename=video_merge_request.output_filename
        )

    except Exception as e:
        processor.cleanup()
        raise HTTPException(status_code=500, detail=str(e))

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
