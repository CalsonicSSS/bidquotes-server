from fastapi import Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from app.configs.app_settings import settings
from app.custom_error import ValidationError
from typing import Optional


# "clerk_auth_guard" will run first (as an instance of ClerkHTTPBearer) to:
# - Read the Authorization: Bearer <JWT> header from the incoming request.
# - validate the JWT (using your JWKS URL you config in the "clerk_config").
# - return a validated and decoded HTTPAuthorizationCredentials object if successful as credentials in this function.
# we will then use the decoded credentials to extract the clerk user ID from the JWT token.

# essentially, this whole setup here does two main things in one go:
# 1. Validates the JWT token.
# 2. Extracts the clerk user ID from the token.
# This is a common pattern in FastAPI for handling authentication and authorization.

# its a common practice to for any user specific endpoint request to always validate and extract the JWT token first before the main business logic.
# the purpose is:
# - to ensure the jwt is not tampered with from the client side (very important).
# - to extract which user is which (very important).

clerk_config = ClerkConfig(jwks_url=settings.CLERK_JWKS_URL)
clerk_auth_guard = ClerkHTTPBearer(config=clerk_config)


async def get_current_clerk_user_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(clerk_auth_guard)) -> str:
    """Extract clerk user ID from JWT token"""

    print("get_current_clerk_user_id called")

    if not credentials:
        raise ValidationError("Authentication required")

    # The decoded JWT payload is available in credentials.decoded
    # Clerk puts the user ID in the 'sub' claim
    clerk_user_id = credentials.decoded.get("sub")
    print(f"Extracted clerk user ID: {clerk_user_id}")

    if not clerk_user_id:
        raise ValidationError("Invalid token: user ID not found")

    return clerk_user_id
