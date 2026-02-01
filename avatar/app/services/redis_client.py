import redis
import json
from datetime import datetime
from ..core.config import settings
from ..models import VideoStatus

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def set_initial_status(task_id: str):
    key = f"avatar_task:{task_id}"
    data = {
        "task_id": task_id,
        "status": VideoStatus.PROCESSING,
        "created_at": datetime.now().isoformat(),
        "progress": 0.0
    }
    redis_client.set(key, json.dumps(data), ex=settings.STATUS_EXPIRE_TIME)
    return data
