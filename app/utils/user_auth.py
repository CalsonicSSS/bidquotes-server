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
# the purpose is to:
# - ensure the jwt is not tampered with from the client side (very important).
# - extract which user is which for each request (very important).

# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# Structure of a JWT:
# composed of three distinct parts, separated by dots (.)
# 1. Header: Contains metadata about the token, including the signing algorithm.
# 2. Payload: Originally a JSON object contains the claims (statements about an entity, typically the user) and any additional data.
# 3. Signature: A cryptographic signature, created by signing the Base64URL-encoded header and payload using a secret or private key.

# Each of the first two parts (header and payload) data is Base64URL-encoded in JWT, and combined with the signature to form the compact JWT string you see (very important)
# When you decode the JWT (mainly on the payload), you'll revert it back to that original JSON structure and can read all its claims.
# the signature is used to verify the authenticity of the JWT and ensure it hasn't been tampered with during request transmission.

# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# Clerk’s Context JWT
# In Clerk-generated JWTs: The payload claims are derived entirely from Clerk's context
# even without defining your own JWT template, Clerk ensures essential claims are always present. Your templates only add on top of these core claims.

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
