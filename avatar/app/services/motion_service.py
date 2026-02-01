import aiohttp
import logging
from core.config import settings
from fastapi import HTTPException
import uuid

logger = logging.getLogger(__name__)

async def request_motion_generation(avatar_url: str, ref_url: str) -> str:
    if not settings.KIE_API_KEY:
        logger.warning("KIE_API_KEY is missing")
        # raise HTTPException(status_code=500, detail="KIE_API_KEY not configured")

    cb_base = settings.CALLBACK_BASE_URL or "https://your-domain.com"
    payload = {
        "model": "kling-2.6/motion-control",
        "callBackUrl": f"{cb_base}/avatar/callback",
        "input": {
            "prompt": "Change man on video.",
            "input_urls": [avatar_url],
            "video_urls": [ref_url],
            "character_orientation": "video",
            "mode": "720p"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.KIE_API_KEY}"
    }

    if settings.KIE_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.kie.ai/api/v1/jobs/createTask", json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"KIE API Error: {resp.status} {text}")
                        raise HTTPException(status_code=502, detail=f"External API failed: {text}")
                    
                    result_json = await resp.json()
                    if result_json.get("code") != 200:
                        logger.error(f"KIE API Logic Error: {result_json}")
                        raise HTTPException(status_code=502, detail=f"External API returned error: {result_json.get('msg')}")
                    
                    return result_json["data"]["taskId"]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to request motion generation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to request motion generation: {str(e)}")
    else:
         logger.warning("Skipping KIE API call due to missing key. Creating mock ID.")
         return f"mock_{uuid.uuid4()}"
