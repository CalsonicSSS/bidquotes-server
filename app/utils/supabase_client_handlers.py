from supabase import acreate_client, AsyncClient
from app.configs.app_settings import settings
from typing import Optional

# logics explain:
# 1. During app startup, the lifespan block runs await create_supabase_client()
# 2. Inside create_supabase_client(), _supabase_client is initially None, so the function creates the async client and assigns it to the global _supabase_client
# 3. After that, _supabase_client holds your initialized AsyncClient by "variable reassignment" (and this refers to the _supabase_client at the module level)
# 4. Later when you call get_supabase_client(), from this module, it will refer to this initialized client already


_supabase_client: Optional[AsyncClient] = None


async def create_supabase_client() -> AsyncClient:
    """Create async supabase client - only called once during startup"""

    # This global tells Python that I’m referring to the "_supabase_client" defined at the module level, not a new local variable.
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase_client


async def get_supabase_client() -> AsyncClient:
    """Dependency function to get the supabase client"""
    if _supabase_client is None:
        raise RuntimeError("Supabase client not initialized. Call create_supabase_client() during startup.")
    return _supabase_client


async def close_supabase_client():
    """Clean up supabase client during shutdown"""
    global _supabase_client
    if _supabase_client:
        # Supabase client doesn't have explicit close method, but we reset the reference
        _supabase_client = None
