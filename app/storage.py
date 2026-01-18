import os
from minio import Minio
from datetime import timedelta

class StorageManager:
    def __init__(self):
        self.endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        self.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = os.environ.get("MINIO_BUCKET_NAME", "videos")
        self.secure = os.environ.get("MINIO_SECURE", "False").lower() == "true"

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Ensure bucket exists
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file(self, file_path: str, object_name: str, content_type: str = "application/octet-stream"):
        try:
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path,
                content_type=content_type
            )
            return True
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise e

    def get_presigned_url(self, object_name: str, expires=timedelta(hours=1)):
        try:
            return self.client.get_presigned_url(
                "GET",
                self.bucket_name,
                object_name,
                expires=expires
            )
        except Exception as e:
            print(f"Error getting presigned url: {e}")
            return None

    def download_file(self, object_name: str, file_path: str):
        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path
            )
        except Exception as e:
            print(f"Error downloading file: {e}")
            raise e
