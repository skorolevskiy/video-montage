from fastapi import APIRouter, Response
from urllib.parse import urlparse
from datetime import timedelta
from services.storage import get_minio_client
from core.config import settings

router = APIRouter()

@router.get("/{filename}")
async def get_file(filename: str):
    # Use X-Accel-Redirect to let Nginx serve the file from MinIO directly
    
    client = get_minio_client()
    
    # Generate presigned URL to allow Nginx to access private bucket
    presigned_url = client.get_presigned_url(
        "GET", 
        settings.MINIO_BUCKET_NAME, 
        filename, 
        expires=timedelta(hours=1)
    )
    
    # Extract path and query from the presigned URL
    # URL is like http://minio:9000/vectors/filename.mp4?Algorithm=...
    parsed = urlparse(presigned_url)
    
    # Map to internal Nginx location
    # parsed.path -> /videos/filename.mp4
    # Result -> /files_internal/videos/filename.mp4?query_params
    redirect_url = f"/files_internal{parsed.path}?{parsed.query}"
    
    return Response(
        headers={
            "X-Accel-Redirect": redirect_url,
            "Content-Type": "video/mp4",
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )
