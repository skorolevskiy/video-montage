import os
import aiohttp
import tempfile
import uuid
import logging
from ..db.supabase import get_supabase
from ..services.storage import get_minio_client, upload_file_to_minio
from ..services.video import generate_thumbnail
from ..core.config import settings

logger = logging.getLogger(__name__)

async def process_table(sb, minio_client, table_name, video_col, thumb_col):
    try:
        # Fetch rows where thumb_col is null
        res = sb.table(table_name).select(f"id, {video_col}").is_(thumb_col, "null").execute()
        rows = res.data
        if not rows:
            return

        logger.info(f"Found {len(rows)} items in {table_name} without thumbnails.")
        
        for row in rows:
            item_id = row['id']
            video_url = row.get(video_col)
            
            if not video_url:
                continue
                
            temp_video = tempfile.mktemp(suffix=".mp4")
            try:
                # Check if it's a minio file or external
                if "/avatar/files/" in video_url or video_url.startswith("files/"):
                    filename = video_url.split("/files/")[-1]
                    try:
                        minio_client.fget_object(settings.MINIO_BUCKET_NAME, filename, temp_video)
                    except Exception as e:
                        logger.error(f"Failed to download from Minio {filename}: {e}")
                        continue
                else:
                    # External URL
                    try:
                         async with aiohttp.ClientSession() as session:
                            async with session.get(video_url) as resp:
                                if resp.status == 200:
                                    with open(temp_video, "wb") as f:
                                        while True:
                                            chunk = await resp.content.read(1024*1024)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                else:
                                    logger.error(f"Failed to download {video_url}: status {resp.status}")
                                    continue
                    except Exception as e:
                        logger.error(f"Failed to download {video_url}: {e}")
                        continue
            
                # Generate Thumbnail
                thumb_path = generate_thumbnail(temp_video)
                if thumb_path:
                    thumb_filename = f"thumb_{uuid.uuid4()}.jpg"
                    try:
                       thumb_url = upload_file_to_minio(thumb_path, thumb_filename, "image/jpeg")
                       
                       # Update DB
                       sb.table(table_name).update({thumb_col: thumb_url}).eq("id", item_id).execute()
                       logger.info(f"Updated thumbnail for {table_name} {item_id}")
                    except Exception as e:
                        logger.error(f"Failed to upload/update thumbnail for {item_id}: {e}")
                    
                    try:
                        os.remove(thumb_path)
                    except: pass
                else:
                    logger.warning(f"Could not generate thumbnail for {table_name} {item_id}")

            finally:
                if os.path.exists(temp_video):
                    try: os.remove(temp_video)
                    except: pass
                    
    except Exception as e:
        logger.error(f"Error processing table {table_name}: {e}")

async def process_missing_thumbnails_task():
    logger.info("Starting missing thumbnail generation task...")
    sb = get_supabase()
    minio_client = get_minio_client()

    # 1. Reference Motions
    await process_table(sb, minio_client, "reference_motions", "video_url", "thumbnail_url")
    
    # 2. Motion Cache
    await process_table(sb, minio_client, "motion_cache", "motion_video_url", "motion_thumbnail_url")
    
    # 3. Background Library
    await process_table(sb, minio_client, "background_library", "video_url", "thumbnail_url")
    
    # 4. Final Montages
    await process_table(sb, minio_client, "final_montages", "final_video_url", "final_thumbnail_url")

    logger.info("Completed thumbnail generation task.")
