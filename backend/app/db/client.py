from supabase import create_client, Client
from app.core.config import settings

def get_supabase() -> Client:
    url: str = settings.SUPABASE_URL
    key: str = settings.SUPABASE_KEY
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")

    return create_client(url, key)

supabase: Client = get_supabase()
