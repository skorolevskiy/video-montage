from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import List, Optional
import tempfile
import shutil
import os
import uuid
from ...models import ReferenceMotion
from ...db.supabase import get_supabase
from ...services.storage import upload_file_to_minio
from ...services.video import get_video_duration, generate_thumbnail

router = APIRouter()

@router.post("", response_model=ReferenceMotion)
async def create_reference(
    file: UploadFile = File(...),
    label: Optional[str] = Form(None)
):
    temp_file = tempfile.mktemp(suffix=os.path.splitext(file.filename)[1])
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if os.path.getsize(temp_file) > 200 * 1024 * 1024:
             raise HTTPException(status_code=413, detail="File too large (max 200MB)")
             
        filename = f"ref_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
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

@router.get("", response_model=List[ReferenceMotion])
async def list_references():
    sb = get_supabase()
    result = sb.table("reference_motions").select("*").execute()
    return result.data

@router.delete("/{reference_id}", status_code=204)
async def delete_reference(reference_id: str):
    sb = get_supabase()
    result = sb.table("reference_motions").delete().eq("id", reference_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Reference not found")
    return None
