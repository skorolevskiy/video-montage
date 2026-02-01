import os
from typing import Optional

class Settings:
    # Project Info
    TITLE: str = "Avatar Generation API"
    VERSION: str = "1.0.0"
    ROOT_PATH: str = "/avatar"

    # Redis
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    STATUS_EXPIRE_TIME: int = 86400

    # Supabase
    SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = os.environ.get("SUPABASE_KEY")

    # Minio
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET_NAME: str = os.environ.get("MINIO_BUCKET_NAME", "videos")
    MINIO_SECURE: bool = os.environ.get("MINIO_SECURE", "False").lower() == "true"
    MINIO_EXTERNAL_URL: Optional[str] = os.environ.get("MINIO_EXTERNAL_URL")

    # External Services
    KIE_API_KEY: Optional[str] = os.environ.get("KIE_API_KEY")
    CALLBACK_BASE_URL: Optional[str] = os.environ.get("CALLBACK_BASE_URL")
    MONTAGE_SERVICE_URL: str = os.environ.get("MONTAGE_SERVICE_URL", "http://montage-api:8000")
    APP_BASE_URL: Optional[str] = os.environ.get("APP_BASE_URL")

settings = Settings()
