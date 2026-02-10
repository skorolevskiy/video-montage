from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import List, Optional
import tempfile
import shutil
import os
import uuid
from models import Avatar, SourceType
from db.supabase import get_supabase
from services.storage import upload_file_to_minio

router = APIRouter()

@router.post("", response_model=Avatar)
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

@router.get("/{avatar_id}", response_model=Avatar)
async def get_avatar(avatar_id: str):
    sb = get_supabase()
    result = sb.table("avatars").select("*").eq("id", avatar_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return result.data[0]

@router.get("", response_model=List[Avatar])
async def list_avatars():
    sb = get_supabase()
    result = sb.table("avatars").select("*").order("created_at", desc=True).execute()
    return result.data

@router.delete("/{avatar_id}", status_code=204)
async def delete_avatar(avatar_id: str):
    sb = get_supabase()
    result = sb.table("avatars").delete().eq("id", avatar_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return None
