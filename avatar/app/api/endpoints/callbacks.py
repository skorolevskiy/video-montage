from fastapi import APIRouter, Body, Response
from fastapi.responses import JSONResponse
import logging
import json
from db.supabase import get_supabase

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
