import aiohttp
import logging
from core.config import settings
from tasks import monitor_montage_task
from supabase import Client

logger = logging.getLogger(__name__)

async def request_montage_creation(sb: Client, montage_id: str, bg_url: str, motion_url: str):
    payload = {
        "video_background_url": bg_url,
        "video_circle_url": motion_url,
        "background_volume": 1,
        "circle_volume": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{settings.MONTAGE_SERVICE_URL}/video-circle", json=payload) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error(f"Montage Service Error: {resp.status} - {err_text}")
                    sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()
                else:
                    try:
                        resp_data = await resp.json()
                        external_video_id = resp_data.get("video_id")
                        if external_video_id:
                            # Schedule monitoring task (wait 1 minute initially)
                            monitor_montage_task.apply_async(args=[str(montage_id), external_video_id], countdown=60)
                            logger.info(f"Successfully sent montage request for {montage_id}, monitoring scheduled.")
                        else:
                            logger.error(f"No video_id in montage response: {resp_data}")
                            sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()
                    except Exception as json_err:
                        logger.error(f"Failed to parse montage response: {json_err}")
                        sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()

    except Exception as e:
        logger.error(f"Failed to communicate with Montage Service: {e}")
        sb.table("final_montages").update({"status": "error"}).eq("id", montage_id).execute()
