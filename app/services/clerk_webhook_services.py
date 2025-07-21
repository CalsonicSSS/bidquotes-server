from supabase import AsyncClient
from app.models.clerk_webhook_models import ClerkWebhookEvent, ClerkUser
from app.custom_error import ServerError
import logging

logger = logging.getLogger(__name__)


class ClerkWebhookService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    def _get_primary_email(self, user_data: dict) -> str:
        """Extract primary email using primary_email_address_id"""

        primary_email_id = user_data.get("primary_email_address_id")
        email_addresses = user_data.get("email_addresses", [])

        # Find the email with matching ID
        for email in email_addresses:
            if email.get("id") == primary_email_id:
                return email.get("email_address")

        # Fallback: return first email if primary not found
        if email_addresses:
            return email_addresses[0].get("email_address")

        return None

    # --------------------------------------------------------------------------------------------------------------------

    async def handle_user_created(self, event: ClerkWebhookEvent):
        """Handle user.created webhook event"""

        try:
            user_data = event.data

            # Extract user info from Clerk webhook
            clerk_user_id = user_data.get("id")
            unsafe_metadata = user_data.get("unsafe_metadata", {})
            primary_email = self._get_primary_email(user_data)

            if not primary_email:
                logger.error(f"No email found for user {clerk_user_id}")
                return

            # Get user type from metadata
            user_type = unsafe_metadata.get("userType", "buyer")  # default to buyer

            # Create user in Supabase
            user_record = {"clerk_user_id": clerk_user_id, "email": primary_email, "user_type": user_type}

            result = await self.supabase_client.table("users").insert(user_record).execute()

            if result.data:
                logger.info(f"✅ User created in Supabase: {clerk_user_id}")
            else:
                logger.error(f"❌ Failed to create user in Supabase: {clerk_user_id}")

        except Exception as e:
            logger.error(f"Error handling user.created webhook: {str(e)}")
            raise ServerError(f"Webhook processing failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------

    async def handle_user_updated(self, event: ClerkWebhookEvent):
        """Handle user.updated webhook event"""

        try:
            user_data = event.data
            clerk_user_id = user_data.get("id")

            # Extract updated info
            primary_email = self._get_primary_email(user_data)
            unsafe_metadata = user_data.get("unsafe_metadata", {})

            # Update user in Supabase
            update_data = {}
            if primary_email:
                update_data["email"] = primary_email
            if unsafe_metadata.get("userType"):
                update_data["user_type"] = unsafe_metadata.get("userType")

            if update_data:
                result = await self.supabase_client.table("users").update(update_data).eq("clerk_user_id", clerk_user_id).execute()

            if result.data:
                logger.info(f"✅ User updated in Supabase: {clerk_user_id}")
            else:
                logger.error(f"❌ Failed to update user in Supabase: {clerk_user_id}")

        except Exception as e:
            logger.error(f"Error handling user.updated webhook: {str(e)}")
            raise ServerError(f"Webhook processing failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------

    async def handle_user_deleted(self, event: ClerkWebhookEvent):
        """Handle user.deleted webhook event"""

        try:
            user_data = event.data
            clerk_user_id = user_data.get("id")

            # Delete user from Supabase (CASCADE will handle related records)
            # Delete will also have targeted row records in related tables
            result = await self.supabase_client.table("users").delete().eq("clerk_user_id", clerk_user_id).execute()

            if result.data:
                logger.info(f"✅ User deleted from Supabase: {clerk_user_id}")
            else:
                logger.error(f"❌ Failed to delete user from Supabase: {clerk_user_id}")

        except Exception as e:
            logger.error(f"Error handling user.deleted webhook: {str(e)}")
            raise ServerError(f"Webhook processing failed: {str(e)}")
