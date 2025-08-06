from supabase import AsyncClient
from app.models.buyer_models import BuyerContactInfoCreate, BuyerContactInfoResponse, BuyerContactInfoUpdate
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

    async def _get_user_id(self, clerk_user_id: str) -> str:
        """Helper method to get user_id from clerk_user_id"""
        try:
            result = await self.supabase_client.table("users").select("id").eq("clerk_user_id", clerk_user_id).execute()

            if not result.data:
                raise UserNotFoundError()

            return result.data[0]["id"]

        except Exception as e:
            logger.error(f"Error getting user_id - {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Failed to get user id")

    # -----------------------------------------------------------------------------------------------------------------------

    async def save_buyer_contact_info(
        self, clerk_user_id: str, buyer_contact_info: BuyerContactInfoCreate | BuyerContactInfoUpdate
    ) -> BuyerContactInfoResponse:
        """Save or update buyer contact information"""
        try:
            # First, get the user id
            user_id = await self._get_user_id(clerk_user_id)

            # Check if contact info already exists
            existing_result = await self.supabase_client.table("buyer_profiles").select("*").eq("user_id", user_id).execute()

            buyer_contact_info_prepared = buyer_contact_info.model_dump(exclude_unset=True)

            # Update existing contact info
            if existing_result.data:

                result = await self.supabase_client.table("buyer_profiles").update(buyer_contact_info_prepared).eq("user_id", user_id).execute()
            # Create new contact info
            else:
                buyer_contact_info_prepared["user_id"] = user_id
                result = await self.supabase_client.table("buyer_profiles").insert(buyer_contact_info_prepared).execute()

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
            # First, get the user id
            user_id = await self._get_user_id(clerk_user_id)

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
