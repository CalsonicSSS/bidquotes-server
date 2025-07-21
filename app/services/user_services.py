from supabase import AsyncClient
from app.models.user_models import BuyerContactInfoCreate, BuyerContactInfoResponse, BuyerContactInfoUpdate, UserCreate, UserResponse
from app.custom_error import UserNotFoundError, ContactInfoNotFoundError, DatabaseError, ServerError
from typing import Optional
import logging

# recall __name__ is a special variable in Python that represents the name of the current module.
logger = logging.getLogger(
    __name__
)  # creates a module-specific logger. Use logger will give much more info and professional output than print statements.


class UserService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    async def create_or_get_user(self, clerk_user_id: str, email: str, user_type: str) -> UserResponse:
        """Create a new user or get existing user by clerk_user_id"""
        try:
            # First, try to get existing user
            result = await self.supabase_client.table("users").select("*").eq("clerk_user_id", clerk_user_id).execute()

            if result.data:
                # User exists, return it
                user_data = result.data[0]
                return UserResponse(**user_data)

            # User doesn't exist, create new one
            user_data = {"clerk_user_id": clerk_user_id, "email": email, "user_type": user_type}

            result = await self.supabase_client.table("users").insert(user_data).execute()

            if not result.data:
                raise DatabaseError("Failed to create user")

            return UserResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error in create_or_get_user: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # -----------------------------------------------------------------------------------------------------------------------

    async def save_buyer_contact_info(
        self, clerk_user_id: str, buyer_contact_info: BuyerContactInfoCreate | BuyerContactInfoUpdate
    ) -> BuyerContactInfoResponse:
        """Save or update buyer contact information"""
        try:
            # First, get the user
            user_result = await self.supabase_client.table("users").select("id").eq("clerk_user_id", clerk_user_id).execute()

            if not user_result.data:
                raise UserNotFoundError()

            user_id = user_result.data[0]["id"]

            # Check if contact info already exists
            existing_result = await self.supabase_client.table("buyer_profiles").select("*").eq("user_id", user_id).execute()

            contact_data = buyer_contact_info.model_dump(exclude_unset=True)

            # Update existing contact info
            if existing_result.data:

                result = await self.supabase_client.table("buyer_profiles").update(contact_data).eq("user_id", user_id).execute()
            # Create new contact info
            else:
                contact_data["user_id"] = user_id
                result = await self.supabase_client.table("buyer_profiles").insert(contact_data).execute()

            if not result.data:
                raise DatabaseError("Failed to save contact information")

            return BuyerContactInfoResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error in save_buyer_contact_info: {str(e)}")
            if isinstance(e, (UserNotFoundError, ContactInfoNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # -----------------------------------------------------------------------------------------------------------------------

    async def get_buyer_contact_info(self, clerk_user_id: str) -> Optional[BuyerContactInfoResponse]:
        """Get buyer contact information by clerk_user_id"""
        try:
            # Get user first
            user_result = await self.supabase_client.table("users").select("id").eq("clerk_user_id", clerk_user_id).execute()

            if not user_result.data:
                raise UserNotFoundError()

            user_id = user_result.data[0]["id"]

            # Get contact info
            result = await self.supabase_client.table("buyer_profiles").select("*").eq("user_id", user_id).execute()

            if not result.data:
                return None

            return BuyerContactInfoResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error in get_buyer_contact_info: {str(e)}")
            if isinstance(e, (UserNotFoundError, ContactInfoNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")
