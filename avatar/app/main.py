from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Response, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse
import os
import json
import redis
import aiohttp
import shutil
import subprocess
import tempfile
from minio import Minio
from models import (
    AvatarRequest, AvatarStatusResponse, VideoStatus,
    Avatar, AvatarCreate,
    ReferenceMotion, ReferenceMotionCreate,
    MotionCache, MotionCacheCreate, MotionCacheUpdate,
    BackgroundVideo, BackgroundVideoCreate,
    FinalMontage, FinalMontageCreate, FinalMontageUpdate,
    SourceType
)
from tasks import generate_avatar_task, monitor_montage_task
from supabase import create_client, Client
from typing import Final, List, Optional

app = FastAPI(
    title="Avatar Generation API",
    description="API for generating avatars",
    version="1.0.0",
    root_path="/avatar"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis for status
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
STATUS_EXPIRE_TIME = 86400

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Minio Client
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_NAME = os.environ.get("MINIO_BUCKET_NAME", "videos")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "False").lower() == "true"

KIE_API_KEY = os.environ.get("KIE_API_KEY")
CALLBACK_BASE_URL = os.environ.get("CALLBACK_BASE_URL")
MONTAGE_SERVICE_URL = os.environ.get("MONTAGE_SERVICE_URL", "http://montage-api:8000")
APP_BASE_URL = os.environ.get("APP_BASE_URL")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("Supabase credentials not found. DB operations will fail.")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_file_to_minio(file_path: str, object_name: str, content_type: str) -> str:
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    if not client.bucket_exists(MINIO_BUCKET_NAME):
        client.make_bucket(MINIO_BUCKET_NAME)
    
    client.fput_object(MINIO_BUCKET_NAME, object_name, file_path, content_type=content_type)
    
    if APP_BASE_URL:
        base = APP_BASE_URL.rstrip('/')
        return f"{base}/avatar/files/{object_name}"
        
    return f"/avatar/files/{object_name}"

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

def set_initial_status(task_id: str):
    key = f"avatar_task:{task_id}"
    data = {
        "task_id": task_id,
        "status": VideoStatus.PROCESSING,
        "created_at": datetime.now().isoformat(),
        "progress": 0.0
    }
    redis_client.set(key, json.dumps(data), ex=STATUS_EXPIRE_TIME)
    return data

# --- Avatars Endpoints ---
@app.post("/avatars", response_model=Avatar, tags=["Avatars"])
async def create_avatar(
    file: UploadFile = File(...),
    source_type: SourceType = Form(SourceType.UPLOAD),
    generation_prompt: Optional[str] = Form(None)
):
    temp_file = tempfile.mktemp(suffix=os.path.splitext(file.filename)[1])
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Check size (200MB)
        if os.path.getsize(temp_file) > 200 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 200MB)")
            
        filename = f"avatar_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        image_url = upload_file_to_minio(temp_file, filename, file.content_type)
        
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except: pass

    sb = get_supabase()
    data = {
        "image_url": image_url,
        "source_type": source_type,
        "generation_prompt": generation_prompt
    }
    result = sb.table("avatars").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create avatar")
    return result.data[0]

@app.get("/avatars/{avatar_id}", response_model=Avatar, tags=["Avatars"])
async def get_avatar(avatar_id: str):
    sb = get_supabase()
    result = sb.table("avatars").select("*").eq("id", avatar_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return result.data[0]

@app.get("/avatars", response_model=List[Avatar], tags=["Avatars"])
async def list_avatars():
    sb = get_supabase()
    result = sb.table("avatars").select("*").execute()
    return result.data

@app.delete("/avatars/{avatar_id}", status_code=204, tags=["Avatars"])
async def delete_avatar(avatar_id: str):
    sb = get_supabase()
    result = sb.table("avatars").delete().eq("id", avatar_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return None

# --- Reference Motions Endpoints ---
@app.post("/references", response_model=ReferenceMotion, tags=["Reference Motions"])
async def create_reference(
    file: UploadFile = File(...),
    label: Optional[str] = Form(None),
    duration_seconds: float = Form(...)
):
    temp_file = tempfile.mktemp(suffix=os.path.splitext(file.filename)[1])
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if os.path.getsize(temp_file) > 200 * 1024 * 1024:
             raise HTTPException(status_code=413, detail="File too large (max 200MB)")
             
        filename = f"ref_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        video_url = upload_file_to_minio(temp_file, filename, file.content_type)
        
        # Thumbnail
        thumb_path = generate_thumbnail(temp_file)
        thumbnail_url = None
        if thumb_path:
            thumb_name = f"thumb_{filename}.jpg"
            thumbnail_url = upload_file_to_minio(thumb_path, thumb_name, "image/jpeg")
            try:
                os.remove(thumb_path)
            except: pass
            
    finally:
         if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except: pass

    sb = get_supabase()
    data = {
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "label": label,
        "duration_seconds": duration_seconds
    }
    result = sb.table("reference_motions").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create reference")
    return result.data[0]

@app.get("/references", response_model=List[ReferenceMotion], tags=["Reference Motions"])
async def list_references():
    sb = get_supabase()
    result = sb.table("reference_motions").select("*").execute()
    return result.data

@app.delete("/references/{reference_id}", status_code=204, tags=["Reference Motions"])
async def delete_reference(reference_id: str):
    sb = get_supabase()
    result = sb.table("reference_motions").delete().eq("id", reference_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Reference not found")
    return None

# --- Motion Cache Endpoints ---
@app.post("/motions", response_model=MotionCache, tags=["Motion Cache"])
async def create_motion_cache(motion: MotionCacheCreate):
    sb = get_supabase()
    
    # Check if exists (idempotency for same avatar+reference+success)
    # Note: 'eq' chaining works for AND
    existing = sb.table("motion_cache").select("*") \
        .eq("avatar_id", str(motion.avatar_id)) \
        .eq("reference_id", str(motion.reference_id)) \
        .eq("status", "success") \
        .execute()
        
    if existing.data:
        return existing.data[0]

    # Fetch URLs
    av_res = sb.table("avatars").select("image_url").eq("id", str(motion.avatar_id)).execute()
    if not av_res.data:
        raise HTTPException(status_code=404, detail="Avatar not found")
    avatar_url = av_res.data[0]["image_url"]

    ref_res = sb.table("reference_motions").select("video_url").eq("id", str(motion.reference_id)).execute()
    if not ref_res.data:
        raise HTTPException(status_code=404, detail="Reference motion not found")
    ref_url = ref_res.data[0]["video_url"]

    # Call External API
    if not KIE_API_KEY:
        # For development/safety, maybe just log warning or fail.
        logger.warning("KIE_API_KEY is missing")
        # raise HTTPException(status_code=500, detail="KIE_API_KEY not configured")

    # Use config for callback base, default to something if testing
    cb_base = CALLBACK_BASE_URL or "https://your-domain.com"
    payload = {
        "model": "kling-2.6/motion-control",
        "callBackUrl": f"{cb_base}/avatar/callback",
        "input": {
            "prompt": "Change man on video.",
            "input_urls": [avatar_url],
            "video_urls": [ref_url],
            "character_orientation": "video",
            "mode": "720p"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIE_API_KEY}"
    }

    task_id = None
    if KIE_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.kie.ai/api/v1/jobs/createTask", json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"KIE API Error: {resp.status} {text}")
                        raise HTTPException(status_code=502, detail=f"External API failed: {text}")
                    
                    result_json = await resp.json()
                    if result_json.get("code") != 200:
                        logger.error(f"KIE API Logic Error: {result_json}")
                        raise HTTPException(status_code=502, detail=f"External API returned error: {result_json.get('msg')}")
                    
                    task_id = result_json["data"]["taskId"]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to request motion generation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to request motion generation: {str(e)}")
    else:
         # Mocking or Failure
         logger.warning("Skipping KIE API call due to missing key. Creating pending logic without ID.")
         # raise HTTPException(status_code=500, detail="KIE API Key missing")
         task_id = f"mock_{uuid.uuid4()}"

    data = motion.model_dump(mode='json')
    data["external_job_id"] = task_id
    data["status"] = "processing"

    result = sb.table("motion_cache").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create motion cache entry")
    return result.data[0]

@app.get("/motions", response_model=List[MotionCache], tags=["Motion Cache"])
async def list_motion():
    sb = get_supabase()
    result = sb.table("motion_cache").select("*").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motions not found")
    return result.data

@app.get("/motions/{motion_id}", response_model=MotionCache, tags=["Motion Cache"])
async def get_motion(motion_id: str):
    sb = get_supabase()
    result = sb.table("motion_cache").select("*").eq("id", motion_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motion not found")
    return result.data[0]

@app.delete("/motions/{motion_id}", status_code=204, tags=["Motion Cache"])
async def delete_motion(motion_id: str):
    sb = get_supabase()
    result = sb.table("motion_cache").delete().eq("id", motion_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motion entry not found")
    return None

# --- Background Library Endpoints ---
@app.post("/backgrounds", response_model=BackgroundVideo, tags=["Background Library"])
async def create_background(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    duration_seconds: float = Form(...)
):
    temp_file = tempfile.mktemp(suffix=os.path.splitext(file.filename)[1])
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if os.path.getsize(temp_file) > 200 * 1024 * 1024:
             raise HTTPException(status_code=413, detail="File too large (max 200MB)")
             
        filename = f"bg_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        video_url = upload_file_to_minio(temp_file, filename, file.content_type)
        
        # Thumbnail
        thumb_path = generate_thumbnail(temp_file)
        thumbnail_url = None
        if thumb_path:
            thumb_name = f"thumb_{filename}.jpg"
            thumbnail_url = upload_file_to_minio(thumb_path, thumb_name, "image/jpeg")
            try:
                os.remove(thumb_path)
            except: pass
            
    finally:
         if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except: pass

    sb = get_supabase()
    data = {
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "title": title,
        "duration_seconds": duration_seconds
    }
    result = sb.table("background_library").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create background")
    return result.data[0]

@app.get("/backgrounds", response_model=List[BackgroundVideo], tags=["Background Library"])
async def list_backgrounds():
    sb = get_supabase()
    result = sb.table("background_library").select("*").execute()
    return result.data

@app.delete("/backgrounds/{bg_id}", status_code=204, tags=["Background Library"])
async def delete_background(bg_id: str):
    sb = get_supabase()
    result = sb.table("background_library").delete().eq("id", bg_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Background video not found")
    return None

# --- Final Montages Endpoints ---
@app.post("/montages", response_model=FinalMontage, tags=["Final Montages"])
async def create_montage(montage: FinalMontageCreate):
    sb = get_supabase()

    # 1. Fetch Background URL
    bg_res = sb.table("background_library").select("video_url").eq("id", str(montage.bg_video_id)).execute()
    if not bg_res.data:
        raise HTTPException(status_code=404, detail="Background video not found")
    bg_url = bg_res.data[0]["video_url"]

    # 2. Fetch Motion URL
    motion_res = sb.table("motion_cache").select("motion_video_url").eq("id", str(montage.motion_id)).execute()
    if not motion_res.data:
        raise HTTPException(status_code=404, detail="Motion entry not found")
    
    motion_url = motion_res.data[0]["motion_video_url"]
    if not motion_url:
        raise HTTPException(status_code=400, detail="Motion video is not ready yet (url is empty)")

    # 3. Save to DB
    data = montage.model_dump(mode='json')
    result = sb.table("final_montages").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create montage")
    
    final_montage_record = result.data[0]
    montage_id = final_montage_record["id"]

    # 4. Send to video-montage service
    payload = {
        "video_background_url": bg_url,
        "video_circle_url": motion_url,
        "background_volume": 1,
        "circle_volume": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{MONTAGE_SERVICE_URL}/video-circle", json=payload) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error(f"Montage Service Error: {resp.status} - {err_text}")
                    # Update status to error if dispatch failed
                    sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()
                else:
                    try:
                        resp_data = await resp.json()
                        external_video_id = resp_data.get("video_id")
                        if external_video_id:
                            # Schedule monitoring task (wait 1 minute initially)
                            monitor_montage_task.apply_async(args=[str(montage_id), external_video_id], countdown=60)
                            logger.info(f"Successfully sent montage request for {montage_id}, monitoring scheduled.")
                        else:
                            logger.error(f"No video_id in montage response: {resp_data}")
                            sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()
                    except Exception as json_err:
                        logger.error(f"Failed to parse montage response: {json_err}")
                        sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()

    except Exception as e:
        logger.error(f"Failed to communicate with Montage Service: {e}")
        sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()

    return final_montage_record

@app.get("/montages", response_model=List[FinalMontage], tags=["Final Montages"])
async def list_montage():
    sb = get_supabase()
    result = sb.table("final_montages").select("*").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return result.data

@app.get("/montages/{montage_id}", response_model=FinalMontage, tags=["Final Montages"])
async def get_montage(montage_id: str):
    sb = get_supabase()
    result = sb.table("final_montages").select("*").eq("id", montage_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return result.data[0]

@app.delete("/montages/{montage_id}", status_code=204, tags=["Final Montages"])
async def delete_montage(montage_id: str):
    sb = get_supabase()
    result = sb.table("final_montages").delete().eq("id", montage_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return None

@app.post("/callback", tags=["Callbacks"])
async def handle_callback(payload: dict = Body(...)):
    # Validate basics
    if payload.get("code") != 200:
        logger.warning(f"Callback received with non-200 code: {payload}")
        return JSONResponse({"status": "ignored"})
    
    data = payload.get("data", {})
    task_id = data.get("taskId")
    state = data.get("state")
    
    if not task_id:
        return JSONResponse({"status": "no_task_id"}, status_code=400)

    sb = get_supabase()
    
    # We update based on external_job_id
    if state == "success":
        result_json_str = data.get("resultJson")
        video_url = None
        try:
            if result_json_str:
                res_data = json.loads(result_json_str)
                urls = res_data.get("resultUrls", [])
                if urls:
                    video_url = urls[0]
        except Exception as e:
            logger.error(f"Failed to parse resultJson: {e}")
        
        if video_url:
            update_data = {
                "status": "success",
                "motion_video_url": video_url
            }
            sb.table("motion_cache").update(update_data).eq("external_job_id", task_id).execute()
    else:
        # handle fail
        fail_msg = data.get("failMsg")
        update_data = {
            "status": "failed",
            "error_log": fail_msg
        }
        sb.table("motion_cache").update(update_data).eq("external_job_id", task_id).execute()

    return JSONResponse({"status": "ok"})

@app.get("/files/{filename}", tags=["Files"])
async def get_file(filename: str):
    # Use X-Accel-Redirect to let Nginx serve the file from MinIO directly
    
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    
    # Generate presigned URL to allow Nginx to access private bucket
    presigned_url = client.get_presigned_url(
        "GET", 
        MINIO_BUCKET_NAME, 
        filename, 
        expires=timedelta(hours=1)
    )
    
    # Extract path and query from the presigned URL
    # URL is like http://minio:9000/vectors/filename.mp4?Algorithm=...
    parsed = urlparse(presigned_url)
    
    # Map to internal Nginx location
    # parsed.path -> /videos/filename.mp4
    # Result -> /files_internal/videos/filename.mp4?query_params
    redirect_url = f"/files_internal{parsed.path}?{parsed.query}"
    
    return Response(
        headers={
            "X-Accel-Redirect": redirect_url,
            "Content-Type": "video/mp4",
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )
