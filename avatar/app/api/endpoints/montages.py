from fastapi import APIRouter, HTTPException
from typing import List
from models import FinalMontage, FinalMontageCreate
from db.supabase import get_supabase
from services.montage_service import request_montage_creation

router = APIRouter()

@router.post("", response_model=FinalMontage)
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

    # 4. Service Call
    await request_montage_creation(sb, str(montage_id), bg_url, motion_url)

    return final_montage_record

@router.get("", response_model=List[FinalMontage])
async def list_montage():
    sb = get_supabase()
    result = sb.table("final_montages").select("*").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return result.data

@router.get("/{montage_id}", response_model=FinalMontage)
async def get_montage(montage_id: str):
    sb = get_supabase()
    result = sb.table("final_montages").select("*").eq("id", montage_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return result.data[0]

@router.delete("/{montage_id}", status_code=204)
async def delete_montage(montage_id: str):
    sb = get_supabase()
    result = sb.table("final_montages").delete().eq("id", montage_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Montage not found")
    return None
