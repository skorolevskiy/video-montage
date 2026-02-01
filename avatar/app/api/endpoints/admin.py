from fastapi import APIRouter, BackgroundTasks
from services.maintenance import process_missing_thumbnails_task

router = APIRouter()

@router.post("/generate-thumbnails")
async def generate_missing_thumbnails(background_tasks: BackgroundTasks):
    """
    Checks all tables (reference_motions, motion_cache, background_library, final_montages)
    for missing thumbnails. If missing, generates them from the video URL.
    """
    background_tasks.add_task(process_missing_thumbnails_task)
    return {"message": "Thumbnail generation task started in background."}
