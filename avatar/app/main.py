from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from core.config import settings
from api.endpoints import avatars, references, motions, backgrounds, montages, files, callbacks, admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.TITLE,
    description="API for generating avatars",
    version=settings.VERSION,
    root_path=settings.ROOT_PATH
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(avatars.router, prefix="/avatars", tags=["Avatars"])
app.include_router(references.router, prefix="/references", tags=["Reference Motions"])
app.include_router(motions.router, prefix="/motions", tags=["Motion Cache"])
app.include_router(backgrounds.router, prefix="/backgrounds", tags=["Background Library"])
app.include_router(montages.router, prefix="/montages", tags=["Final Montages"])
app.include_router(files.router, prefix="/files", tags=["Files"])
app.include_router(callbacks.router, prefix="/callback", tags=["Callbacks"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "avatar-service"}
