from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import List, Optional
import tempfile
import shutil
import os
import uuid
from models import BackgroundVideo
from db.supabase import get_supabase
from services.storage import upload_file_to_minio
from services.video import get_video_duration, generate_thumbnail

router = APIRouter()

@router.post("", response_model=List[BackgroundVideo])
async def create_backgrounds(
    files: List[UploadFile] = File(...),
    title: Optional[str] = Form(None)
):
    results = []
    sb = get_supabase()

    for file in files:
        temp_file = tempfile.mktemp(suffix=os.path.splitext(file.filename)[1])
        try:
            with open(temp_file, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            if os.path.getsize(temp_file) > 200 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"File {file.filename} too large (max 200MB)")
                
            filename = f"bg_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            video_url = upload_file_to_minio(temp_file, filename, file.content_type)
            
            # Get duration
            duration_seconds = get_video_duration(temp_file)
            
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

        data = {
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "title": title,
            "duration_seconds": duration_seconds
        }
        result = sb.table("background_library").insert(data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create background")
        results.append(result.data[0])

    return results

@router.get("", response_model=List[BackgroundVideo])
async def list_backgrounds():
    sb = get_supabase()
    result = sb.table("background_library").select("*").order("created_at", desc=True).execute()
    return result.data

@router.delete("/{bg_id}", status_code=204)
async def delete_background(bg_id: str):
    sb = get_supabase()
    result = sb.table("background_library").delete().eq("id", bg_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Background video not found")
    return None
