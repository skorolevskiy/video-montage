from fastapi import HTTPException
from supabase import create_client, Client
from core.config import settings

def get_supabase() -> Client:
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
