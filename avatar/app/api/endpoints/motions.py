from fastapi import APIRouter, HTTPException
from typing import List
from models import MotionCache, MotionCacheCreate
from db.supabase import get_supabase
from services.motion_service import request_motion_generation

router = APIRouter()

@router.post("", response_model=MotionCache)
async def create_motion_cache(motion: MotionCacheCreate):
    sb = get_supabase()
    
    # Check if exists (idempotency for same avatar+reference+success)
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

    # Call External API via Service
    task_id = await request_motion_generation(avatar_url, ref_url)

    data = motion.model_dump(mode='json')
    data["external_job_id"] = task_id
    data["status"] = "processing"

    result = sb.table("motion_cache").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create motion cache entry")
    return result.data[0]

@router.get("", response_model=List[MotionCache])
async def list_motion():
    sb = get_supabase()
    result = sb.table("motion_cache").select("*").order("created_at", desc=True).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motions not found")
    return result.data

@router.get("/{motion_id}", response_model=MotionCache)
async def get_motion(motion_id: str):
    sb = get_supabase()
    result = sb.table("motion_cache").select("*").eq("id", motion_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motion not found")
    return result.data[0]

@router.delete("/{motion_id}", status_code=204)
async def delete_motion(motion_id: str):
    sb = get_supabase()
    result = sb.table("motion_cache").delete().eq("id", motion_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Motion entry not found")
    return None
