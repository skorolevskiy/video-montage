import os
import time
import json
import redis
import requests
import io
import tempfile
import uuid
from datetime import datetime, timedelta
from celery_worker import celery_app
from models import VideoStatus
from supabase import create_client
from minio import Minio
from services.video import generate_thumbnail

redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
STATUS_EXPIRE_TIME = 86400

# Supabase init
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
MONTAGE_SERVICE_URL = os.environ.get("MONTAGE_SERVICE_URL", "http://montage-api:8000")
APP_BASE_URL = os.environ.get("APP_BASE_URL")

# Minio init
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_NAME = os.environ.get("MINIO_BUCKET_NAME", "videos")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "False").lower() == "true"
MINIO_EXTERNAL_URL = os.environ.get("MINIO_EXTERNAL_URL")

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_minio(file_content, object_name, content_type="video/mp4"):
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    if not client.bucket_exists(MINIO_BUCKET_NAME):
        client.make_bucket(MINIO_BUCKET_NAME)
    
    # Put object
    data_stream = io.BytesIO(file_content)
    length = len(file_content)
    client.put_object(MINIO_BUCKET_NAME, object_name, data_stream, length, content_type=content_type)
    
    # If we have APP_BASE_URL, return the proxy URL
    if APP_BASE_URL:
        # e.g. https://uniq.powercodeai.space/avatar/files/myvideo.mp4
        # Remove trailing slash from base if present
        base = APP_BASE_URL.rstrip('/')
        return f"{base}/avatar/files/{object_name}"

    # Generate URL
    # Always initiate with a presigned URL (handles private buckets)
    # Expiry 7 days
    url = client.get_presigned_url("GET", MINIO_BUCKET_NAME, object_name, expires=timedelta(days=7))
    
    if MINIO_EXTERNAL_URL and url:
        # Replace internal endpoint with external URL
        internal_base = f"http://{MINIO_ENDPOINT}"
        # We might need to handle https if internal minio was https, but here it's http://minio:9000
        if MINIO_SECURE:
             internal_base = f"https://{MINIO_ENDPOINT}"
             
        return url.replace(internal_base, MINIO_EXTERNAL_URL)
        
    return url

def update_status(task_id: str, data: dict):
    key = f"avatar_task:{task_id}"
    current = redis_client.get(key)
    if current:
        current_data = json.loads(current)
        current_data.update(data)
        redis_client.set(key, json.dumps(current_data), ex=STATUS_EXPIRE_TIME)

@celery_app.task(name="tasks.monitor_montage_task", queue="avatar_queue")
def monitor_montage_task(montage_id: str, video_id: str):
    sb = get_supabase()
    if not sb:
        print("Supabase Config Missing in Worker")
        return

    url = f"{MONTAGE_SERVICE_URL}/video-status/{video_id}"
    
    # Loop for polling
    # 240 * 15s = 60 minutes max wait time
    max_retries = 240
    
    for _ in range(max_retries):
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                
                if status == "completed":
                    # Download
                    download_url = f"{MONTAGE_SERVICE_URL}/download/{video_id}"
                    vid_resp = requests.get(download_url)
                    if vid_resp.status_code == 200:
                        file_content = vid_resp.content
                        
                        # Save to Minio
                        filename = f"final_montage_{montage_id}.mp4"
                        final_url = upload_to_minio(file_content, filename)
                        
                        # Generate Thumbnail
                        final_thumbnail_url = None
                        try:
                            temp_video = tempfile.mktemp(suffix=".mp4")
                            with open(temp_video, "wb") as f:
                                f.write(file_content)
                                
                            thumb_path = generate_thumbnail(temp_video)
                            if thumb_path:
                                thumb_filename = f"thumb_montage_{montage_id}.jpg"
                                with open(thumb_path, "rb") as tf:
                                    thumb_content = tf.read()
                                    final_thumbnail_url = upload_to_minio(thumb_content, thumb_filename, content_type="image/jpeg")
                                try: os.remove(thumb_path)
                                except: pass
                                
                            if os.path.exists(temp_video):
                                try: os.remove(temp_video)
                                except: pass
                        except Exception as e:
                            print(f"Failed to generate thumbnail for montage {montage_id}: {e}")
                        
                        # Update DB
                        sb.table("final_montages").update({
                            "status": "ready",
                            "final_video_url": final_url,
                            "final_thumbnail_url": final_thumbnail_url
                        }).eq("id", montage_id).execute()
                        
                        return "success"
                    else:
                        print(f"Failed to download video: {vid_resp.status_code}")
                        sb.table("final_montages").update({
                            "status": "error",
                            "settings": {"error": f"Failed to download: {vid_resp.status_code}"}
                        }).eq("id", montage_id).execute()
                        return "download_failed"
                
                elif status == "failed":
                    error_msg = data.get("error_message", "Unknown error")
                    sb.table("final_montages").update({
                        "status": "error",
                        "settings": {"error": error_msg}
                    }).eq("id", montage_id).execute()
                    return "failed"
            
        except Exception as e:
            print(f"Error checking status: {e}")
        
        time.sleep(15)
    
    # Timeout
    sb.table("final_montages").update({
        "status": "error",
        "settings": {"error": "Timeout waiting for montage"}
    }).eq("id", montage_id).execute()
    return "timeout"
    
@celery_app.task(name="tasks.generate_avatar_task", queue="avatar_queue")
def generate_avatar_task(task_id: str, request_data: dict):
    try:
        update_status(task_id, {"status": VideoStatus.PROCESSING, "progress": 10.0})
        
        # Simulate processing - REPLACE WITH ACTUAL AI GENERATION
        time.sleep(5)
        update_status(task_id, {"status": VideoStatus.PROCESSING, "progress": 50.0})
        time.sleep(5)
        
        # Mock result
        result_url = "http://minio/bucket/avatar_result.mp4"
        
        update_status(task_id, {
            "status": VideoStatus.COMPLETED, 
            "progress": 100.0, 
            "result_url": result_url,
            "completed_at": datetime.now().isoformat()
        })
        
        return {"status": "completed", "url": result_url}
        
    except Exception as e:
        update_status(task_id, {
            "status": VideoStatus.FAILED, 
            "error_message": str(e)
        })
        raise e
