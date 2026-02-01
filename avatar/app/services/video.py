import subprocess
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

def generate_thumbnail(video_path: str) -> str:
    temp_thumb = tempfile.mktemp(suffix=".jpg")
    try:
        subprocess.check_call([
            "ffmpeg", "-i", video_path, "-ss", "00:00:01", "-vframes", "1", 
            "-q:v", "2", "-y", temp_thumb
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(temp_thumb):
            return temp_thumb
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
    return None

def get_video_duration(video_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Failed to get video duration: {e}")
        return 0.0
