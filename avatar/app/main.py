from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.responses import JSONResponse
import logging
import traceback
import uuid
from datetime import datetime
import os
import json
import redis
from models import (
    AvatarRequest, AvatarStatusResponse, VideoStatus,
    Avatar, AvatarCreate,
    ReferenceMotion, ReferenceMotionCreate,
    MotionCache, MotionCacheCreate, MotionCacheUpdate,
    BackgroundVideo, BackgroundVideoCreate,
    FinalMontage, FinalMontageCreate, FinalMontageUpdate
)
from tasks import generate_avatar_task
from supabase import create_client, Client
from typing import List

app = FastAPI(
    title="Avatar Generation API",
    description="API for generating avatars",
    version="1.0.0",
    root_path="/avatar"
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

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("Supabase credentials not found. DB operations will fail.")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

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

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "avatar-service"}

# --- Avatars Endpoints ---
@app.post("/avatars", response_model=Avatar, tags=["Avatars"])
async def create_avatar(avatar: AvatarCreate):
    sb = get_supabase()
    # Pydantic v2 use model_dump(mode='json') for serialization
    data = avatar.model_dump(mode='json')
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
async def create_reference(ref: ReferenceMotionCreate):
    sb = get_supabase()
    data = ref.model_dump(mode='json')
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

    data = motion.model_dump(mode='json')
    result = sb.table("motion_cache").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create motion cache entry")
    return result.data[0]

@app.get("/motions/{motion_id}", response_model=MotionCache, tags=["Motion Cache"])
async def get_motion(motion_id: str):
    sb = get_supabase()
    result = sb.table("motion_cache").select("*").eq("id", motion_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motion not found")
    return result.data[0]

@app.patch("/motions/{motion_id}", response_model=MotionCache, tags=["Motion Cache"])
async def update_motion(motion_id: str, update: MotionCacheUpdate):
    sb = get_supabase()
    data = update.model_dump(exclude_unset=True, mode='json')
    result = sb.table("motion_cache").update(data).eq("id", motion_id).execute()
    if not result.data:
         raise HTTPException(status_code=404, detail="Motion not found or update failed")
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
async def create_background(bg: BackgroundVideoCreate):
    sb = get_supabase()
    data = bg.model_dump(mode='json')
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
    data = montage.model_dump(mode='json')
    result = sb.table("final_montages").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create montage")
    return result.data[0]

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

@app.patch("/montages/{montage_id}", response_model=FinalMontage, tags=["Final Montages"])
async def update_montage(montage_id: str, update: FinalMontageUpdate):
    sb = get_supabase()
    data = update.model_dump(exclude_unset=True, mode='json')
    result = sb.table("final_montages").update(data).eq("id", montage_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found or update failed")
    return result.data[0]
