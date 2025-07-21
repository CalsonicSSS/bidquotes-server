from fastapi import Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from app.configs.app_settings import settings
from app.custom_error import ValidationError
from typing import Optional

# Initialize Clerk config and auth guard
clerk_config = ClerkConfig(jwks_url=settings.CLERK_JWKS_URL)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)


async def get_current_clerk_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(clerk_auth_guard)) -> str:
    """Extract clerk user ID from JWT token"""

    if not credentials:
        raise ValidationError("Authentication required")

    # The decoded JWT payload is available in credentials.decoded
    # Clerk puts the user ID in the 'sub' claim
    clerk_user_id = credentials.decoded.get("sub")

    if not clerk_user_id:
        raise ValidationError("Invalid token: user ID not found")

    return clerk_user_id
