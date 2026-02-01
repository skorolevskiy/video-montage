from minio import Minio
from ..core.config import settings
from typing import Optional

def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

def upload_file_to_minio(file_path: str, object_name: str, content_type: str) -> str:
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        client.make_bucket(settings.MINIO_BUCKET_NAME)
    
    client.fput_object(settings.MINIO_BUCKET_NAME, object_name, file_path, content_type=content_type)
    
    if settings.APP_BASE_URL:
        base = settings.APP_BASE_URL.rstrip('/')
        return f"{base}/avatar/files/{object_name}"
        
    return f"/avatar/files/{object_name}"
