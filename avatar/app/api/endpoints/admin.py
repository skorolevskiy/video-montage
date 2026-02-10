from fastapi import APIRouter, BackgroundTasks, HTTPException
from core.config import settings
from services.maintenance import process_missing_thumbnails_task
import aiohttp
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/balance")
async def check_balance():
    """
    Check the remaining credit balance from KIE API.
    1 second = 6 credits.
    """
    if not settings.KIE_API_KEY:
        raise HTTPException(status_code=500, detail="KIE_API_KEY is not configured")

    url = "https://api.kie.ai/api/v1/chat/credit"
    headers = {
        "Authorization": f"Bearer {settings.KIE_API_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"KIE API Error: {resp.status} - {error_text}")
                    raise HTTPException(status_code=resp.status, detail="Failed to fetch credit balance")
                
                data = await resp.json()
                # Assuming the response contains "credit" or similar field. 
                # If structure is unknown, we try to interpret 'credit' key.
                # Adjust key access based on actual API response if known, otherwise default to 'credit'.
                credits = data.get("credit")
                
                if credits is None:
                     # Try finding it if nested or named differently
                     credits = data.get("balance") or data.get("credits")

                if credits is None:
                     return {"error": "Could not find credit field in response", "raw": data}
                
                # 1 sec = 6 credits
                seconds_left = float(credits) / 6.0
                minutes = int(seconds_left // 60)
                seconds = int(seconds_left % 60)

                return {
                    "credits": credits,
                    "remaining_time_formatted": f"{minutes}m {seconds}s",
                    "minutes": minutes,
                    "seconds": seconds
                }

        except Exception as e:
            logger.error(f"Error checking balance: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-thumbnails")
async def generate_missing_thumbnails(background_tasks: BackgroundTasks):
    """
    Checks all tables (reference_motions, motion_cache, background_library, final_montages)
    for missing thumbnails. If missing, generates them from the video URL.
    """
    background_tasks.add_task(process_missing_thumbnails_task)
    return {"message": "Thumbnail generation task started in background."}
