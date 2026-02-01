from fastapi import APIRouter, Body, Response
from fastapi.responses import JSONResponse
import logging
import json
import aiohttp
import os
import tempfile
import uuid
from db.supabase import get_supabase
from services.storage import upload_file_to_minio
from services.video import generate_thumbnail

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("")
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
            motion_thumbnail_url = None
            try:
                # Generate thumbnail
                temp_video = tempfile.mktemp(suffix=".mp4")
                # Download video to temp
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url) as resp:
                        if resp.status == 200:
                            with open(temp_video, "wb") as f:
                                while True:
                                    chunk = await resp.content.read(1024*1024)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            
                            thumb_path = generate_thumbnail(temp_video)
                            if thumb_path:
                                thumb_filename = f"thumb_motion_{task_id}_{uuid.uuid4()}.jpg"
                                motion_thumbnail_url = upload_file_to_minio(thumb_path, thumb_filename, "image/jpeg")
                                try: os.remove(thumb_path)
                                except: pass
                
                if os.path.exists(temp_video):
                    try: os.remove(temp_video)
                    except: pass
            except Exception as e:
                logger.error(f"Failed to generate thumbnail for callback {task_id}: {e}")

            update_data = {
                "status": "success",
                "motion_video_url": video_url,
                "motion_thumbnail_url": motion_thumbnail_url
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
