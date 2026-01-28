from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.responses import JSONResponse
import logging
import traceback
import uuid
from datetime import datetime
import os
import json
import redis
from models import AvatarRequest, AvatarStatusResponse, VideoStatus
from tasks import generate_avatar_task

app = FastAPI(
    title="Avatar Generation API",
    description="API for generating avatars",
    version="1.0.0",
    root_path="/avatar"
)

# Redis for status
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
STATUS_EXPIRE_TIME = 86400

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_initial_status(task_id: str):
    key = f"avatar_task:{task_id}"
    data = {
        "task_id": task_id,
        "status": VideoStatus.PROCESSING,
        "created_at": datetime.now().isoformat(),
        "progress": 0.0
    }
    redis_client.set(key, json.dumps(data), ex=STATUS_EXPIRE_TIME)
    return data

@app.get("/health")
async def health():
    return {"status": "ok", "service": "avatar-service"}

@app.post("/generate", response_model=AvatarStatusResponse)
async def generate_avatar(request: AvatarRequest = Body(...)):
    task_id = str(uuid.uuid4())
    data = set_initial_status(task_id)
    
    # Send to Celery
    generate_avatar_task.delay(task_id, request.dict())
    
    return AvatarStatusResponse(**data)

@app.get("/status/{task_id}", response_model=AvatarStatusResponse)
async def get_status(task_id: str):
    key = f"avatar_task:{task_id}"
    data = redis_client.get(key)
    if not data:
        raise HTTPException(status_code=404, detail="Task not found")
    return json.loads(data)
