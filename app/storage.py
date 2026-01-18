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
        self.external_url = os.environ.get("MINIO_EXTERNAL_URL")

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Ensure bucket exists
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

        self.uploads_bucket = os.environ.get("MINIO_UPLOADS_BUCKET", "uploads")
        if not self.client.bucket_exists(self.uploads_bucket):
            self.client.make_bucket(self.uploads_bucket)

    def upload_file(self, file_path: str, object_name: str, content_type: str = "application/octet-stream", bucket_name: str = None):
        target_bucket = bucket_name or self.bucket_name
        try:
            self.client.fput_object(
                target_bucket,
                object_name,
                file_path,
                content_type=content_type
            )
            return True
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise e

    def upload_stream(self, file_data, length, object_name, content_type="application/octet-stream", bucket_name: str = None):
        target_bucket = bucket_name or self.bucket_name
        try:
            self.client.put_object(
                target_bucket,
                object_name,
                file_data,
                length,
                content_type=content_type
            )
            return True
        except Exception as e:
            print(f"Error uploading stream: {e}")
            raise e

    def get_presigned_url(self, object_name: str, bucket_name: str = None, expires=timedelta(hours=1)):
        target_bucket = bucket_name or self.bucket_name
        try:
            url = self.client.get_presigned_url(
                "GET",
                target_bucket,
                object_name,
                expires=expires
            )
            
            if self.external_url and url:
                # Replace internal endpoint with external URL
                # Handle both http and https for the internal part just in case
                internal_base = f"http://{self.endpoint}"
                if self.secure:
                    internal_base = f"https://{self.endpoint}"
                
                return url.replace(internal_base, self.external_url)
            
            return url
        except Exception as e:
            print(f"Error getting presigned url: {e}")
            return None

    def list_files(self, bucket_name: str = None):
        target_bucket = bucket_name or self.bucket_name
        try:
            objects = self.client.list_objects(target_bucket)
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified
                } for obj in objects
            ]
        except Exception as e:
            print(f"Error listing files: {e}")
            return []

    def download_file(self, object_name: str, file_path: str, bucket_name: str = None):
        target_bucket = bucket_name or self.bucket_name
        try:
            self.client.fget_object(
                target_bucket,
                object_name,
                file_path
            )
        except Exception as e:
            print(f"Error downloading file: {e}")
            raise e
