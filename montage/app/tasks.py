import asyncio
import os
import json
import redis
import shutil
import traceback
import aiohttp
from datetime import datetime
from celery_worker import celery_app
from video_processor import VideoProcessor
from storage import StorageManager
from models import VideoStatus

# Redis connection for status/result storage (separate from Celery broker)
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

STATUS_EXPIRE_TIME = 86400  # 24 hours

def update_status(video_id: str, data: dict):
    key = f"task:{video_id}"
    # Get existing data if any
    current = redis_client.get(key)
    if current:
        current_data = json.loads(current)
        current_data.update(data)
        redis_client.set(key, json.dumps(current_data), ex=STATUS_EXPIRE_TIME)
    else:
        redis_client.set(key, json.dumps(data), ex=STATUS_EXPIRE_TIME)

async def _process_video_async(video_id: str, video_merge_request_data: dict, music_url: str = None):
    task_dir = os.path.join(tempfile.gettempdir(), f"video_processing_{video_id}")
    os.makedirs(task_dir, exist_ok=True)
    
    storage = StorageManager()
    processor = VideoProcessor(task_dir)
    
    try:
        update_status(video_id, {"status": VideoStatus.PROCESSING, "progress": 0.0})

        # Download music if provided
        music_path = None
        if music_url:
            music_path = os.path.join(task_dir, "music_downloaded.mp3") # Simplified ext
            async with aiohttp.ClientSession() as session:
                async with session.get(music_url) as response:
                    if response.status == 200:
                         with open(music_path, "wb") as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)

        async def update_progress(progress: float):
            update_status(video_id, {"progress": progress})

        # Process
        output_file = await processor.merge_videos(
            video_urls=video_merge_request_data.get("video_urls", []),
            music_path=music_path,
            subtitles_data=video_merge_request_data.get("subtitles_data"),
            karaoke_mode=video_merge_request_data.get("karaoke_mode", False),
            subtitle_style=video_merge_request_data.get("subtitle_style"),
            output_filename=video_merge_request_data.get("output_filename", "output.mp4"),
            progress_callback=update_progress
        )
        
        # Upload to MinIO
        object_name = f"{video_id}/{os.path.basename(output_file)}"
        storage.upload_file(output_file, object_name, content_type="video/mp4")
        
        update_status(video_id, {
            "status": VideoStatus.COMPLETED,
            "progress": 100.0,
            "completed_at": datetime.now().isoformat(),
            "object_name": object_name,
            "download_url": f"/download/{video_id}" # API endpoint handling redirect/proxy
        })
        
    except Exception as e:
        print(f"Error processing video {video_id}: {e}")
        traceback.print_exc()
        update_status(video_id, {
            "status": VideoStatus.FAILED,
            "error_message": str(e),
            "completed_at": datetime.now().isoformat()
        })
        raise e
    finally:
        processor.cleanup()
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)

import tempfile

@celery_app.task
def process_video_task(video_id: str, video_merge_request_data: dict, music_url: str = None):
    asyncio.run(_process_video_async(video_id, video_merge_request_data, music_url))


async def _process_circle_video_async(video_id: str, request_data: dict):
    task_dir = os.path.join(tempfile.gettempdir(), f"video_processing_{video_id}")
    os.makedirs(task_dir, exist_ok=True)
    
    storage = StorageManager()
    processor = VideoProcessor(task_dir)
    
    try:
        update_status(video_id, {"status": VideoStatus.PROCESSING, "progress": 0.0})
        
        async def update_progress(progress: float):
            update_status(video_id, {"progress": progress})

        output_file = await processor.process_circle_video(
            background_video_url=request_data.get("video_background_url"),
            circle_video_url=request_data.get("video_circle_url"),
            background_volume=request_data.get("background_volume", 1.0),
            circle_volume=request_data.get("circle_volume", 1.0),
            circle_position=request_data.get("circle_position", "bottom_right"),
            output_filename="circle_video.mp4",
            progress_callback=update_progress
        )

        object_name = f"{video_id}/circle_video.mp4"
        storage.upload_file(output_file, object_name, content_type="video/mp4")
        
        update_status(video_id, {
            "status": VideoStatus.COMPLETED,
            "progress": 100.0,
            "completed_at": datetime.now().isoformat(),
            "object_name": object_name,
            "download_url": f"/download/{video_id}"
        })

    except Exception as e:
        print(f"Error processing circle video {video_id}: {e}")
        traceback.print_exc()
        update_status(video_id, {
            "status": VideoStatus.FAILED,
            "error_message": str(e),
            "completed_at": datetime.now().isoformat()
        })
        raise e
    finally:
        processor.cleanup()
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)

@celery_app.task
def process_circle_video_task(video_id: str, request_data: dict):
    asyncio.run(_process_circle_video_async(video_id, request_data))

async def _process_overlay_video_async(video_id: str, request_data: dict):
    task_dir = os.path.join(tempfile.gettempdir(), f"video_processing_{video_id}")
    os.makedirs(task_dir, exist_ok=True)
    
    storage = StorageManager()
    processor = VideoProcessor(task_dir)
    
    try:
        update_status(video_id, {"status": VideoStatus.PROCESSING, "progress": 0.0})
        
        async def update_progress(progress: float):
            update_status(video_id, {"progress": progress})

        output_file = await processor.process_overlay_video(
            background_video_url=request_data.get("video_background_url"),
            overlay_video_url=request_data.get("video_overlay_url"),
            background_volume=request_data.get("background_volume", 1.0),
            overlay_volume=request_data.get("overlay_volume", 1.0),
            position=request_data.get("position", "bottom"),
            output_filename="overlay_video.mp4",
            progress_callback=update_progress
        )

        object_name = f"{video_id}/overlay_video.mp4"
        storage.upload_file(output_file, object_name, content_type="video/mp4")
        
        update_status(video_id, {
            "status": VideoStatus.COMPLETED,
            "progress": 100.0,
            "completed_at": datetime.now().isoformat(),
            "object_name": object_name,
            "download_url": f"/download/{video_id}"
        })

    except Exception as e:
        print(f"Error processing overlay video {video_id}: {e}")
        traceback.print_exc()
        update_status(video_id, {
            "status": VideoStatus.FAILED,
            "error_message": str(e),
            "completed_at": datetime.now().isoformat()
        })
        raise e
    finally:
        processor.cleanup()
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)

@celery_app.task
def process_overlay_video_task(video_id: str, request_data: dict):
    asyncio.run(_process_overlay_video_async(video_id, request_data))
