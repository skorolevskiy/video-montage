import os
import time
import json
import redis
from celery_worker import celery_app
from models import VideoStatus

redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
STATUS_EXPIRE_TIME = 86400

def update_status(task_id: str, data: dict):
    key = f"avatar_task:{task_id}"
    current = redis_client.get(key)
    if current:
        current_data = json.loads(current)
        current_data.update(data)
        redis_client.set(key, json.dumps(current_data), ex=STATUS_EXPIRE_TIME)

@celery_app.task(name="tasks.generate_avatar_task", queue="avatar_queue")
def generate_avatar_task(task_id: str, request_data: dict):
    try:
        update_status(task_id, {"status": VideoStatus.PROCESSING, "progress": 10.0})
        
        # Simulate processing - REPLACE WITH ACTUAL AI GENERATION
        time.sleep(5)
        update_status(task_id, {"status": VideoStatus.PROCESSING, "progress": 50.0})
        time.sleep(5)
        
        # Mock result
        result_url = "http://minio/bucket/avatar_result.mp4"
        
        update_status(task_id, {
            "status": VideoStatus.COMPLETED, 
            "progress": 100.0, 
            "result_url": result_url,
            "completed_at": datetime.now().isoformat()
        })
        
        return {"status": "completed", "url": result_url}
        
    except Exception as e:
        update_status(task_id, {
            "status": VideoStatus.FAILED, 
            "error_message": str(e)
        })
        raise e
