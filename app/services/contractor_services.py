# Create app/services/contractor_services.py

from supabase import AsyncClient
from app.models.contractor_models import (  # Assuming you add the contractor models to user_models.py
    ContractorProfileCreate,
    ContractorProfileUpdate,
    ContractorProfileResponse,
    ContractorProfileImageResponse,
)
from app.custom_error import UserNotFoundError, DatabaseError, ServerError
from typing import Optional, List, Tuple
import logging
import uuid
import mimetypes

logger = logging.getLogger(__name__)


class ContractorProfileService:
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

    # =====================================================================================================
    # Internal IMAGE PROCESSING METHODS
    # =====================================================================================================

    async def _upload_single_profile_image(self, file_content: bytes, file_name: str, profile_id: str) -> tuple[str, str]:
        """Internal: Upload single profile image and return (image_url, storage_path)"""
        try:
            # Generate storage path
            storage_path = f"contractor-profiles/{profile_id}/{uuid.uuid4()}"

            # Upload to Supabase Storage
            await self.supabase_client.storage.from_("contractor-profile-images").upload(
                path=storage_path, file=file_content, file_options={"content-type": mimetypes.guess_type(file_name)[0] or "image/jpeg"}
            )

            # Get public URL
            image_url = await self.supabase_client.storage.from_("contractor-profile-images").get_public_url(storage_path)

            logger.info(f"✅ Profile image uploaded: {storage_path}")
            return image_url, storage_path

        except Exception as e:
            logger.error(f"Error uploading profile image - {str(e)}")
            raise ServerError(f"Failed to upload profile image")

    # ------------------------------------------------------------------------------------------------------------------------------

    async def _upload_profile_images_create_records(self, profile_id: str, image_files: list[tuple[bytes, str]]) -> None:
        """Internal: Upload profile images and create database records"""
        if not image_files:
            return

        try:
            for index, (file_content, file_name) in enumerate(image_files, 1):
                if not file_content or not file_name:
                    continue

                # Upload to storage
                image_url, storage_path = await self._upload_single_profile_image(file_content, file_name, profile_id)

                # Create database record
                image_data = {"contractor_profile_id": profile_id, "image_url": image_url, "storage_path": storage_path, "image_order": index}
                await self.supabase_client.table("contractor_profile_images").insert(image_data).execute()

            logger.info(f"✅ Uploaded {len(image_files)} profile images for profile: {profile_id}")

        except Exception as e:
            logger.error(f"Error creating profile image records - {str(e)}")
            raise ServerError(f"Failed to process profile images")

    # ------------------------------------------------------------------------------------------------------------------------------

    async def _delete_profile_images(self, profile_id: str) -> None:
        """Internal: Delete all images for a profile (both storage and database)"""
        try:
            # Get all image records for this profile
            result = (
                await self.supabase_client.table("contractor_profile_images").select("storage_path").eq("contractor_profile_id", profile_id).execute()
            )

            if result.data:
                # Delete ALL images from storage
                storage_paths = [img["storage_path"] for img in result.data if img.get("storage_path")]
                if storage_paths:
                    await self.supabase_client.storage.from_("contractor-profile-images").remove(storage_paths)

                # Delete database ALL records
                await self.supabase_client.table("contractor_profile_images").delete().eq("contractor_profile_id", profile_id).execute()

                logger.info(f"✅ Deleted {len(storage_paths)} profile images for profile {profile_id}")

        except Exception as e:
            logger.error(f"Error deleting profile images - {str(e)}")
            raise ServerError(f"Failed to delete profile images")

    # =====================================================================================================
    # CORE OPERATIONS
    # =====================================================================================================

    async def get_contractor_profile(self, clerk_user_id: str) -> Optional[ContractorProfileResponse]:
        """Get contractor profile information with images"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Always get profile with images
            result = (
                await self.supabase_client.table("contractor_profiles").select("*, contractor_profile_images(*)").eq("user_id", user_id).execute()
            )

            if not result.data:
                return None

            profile_data = result.data[0].copy()

            # Format images
            images = []
            if profile_data.get("contractor_profile_images"):
                for img in profile_data["contractor_profile_images"]:
                    images.append(ContractorProfileImageResponse(**img))
                images.sort(key=lambda x: x.image_order)

            profile_data["images"] = images
            profile_data.pop("contractor_profile_images", None)

            return ContractorProfileResponse(**profile_data)

        except Exception as e:
            logger.error(f"Error in get_contractor_profile: {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # -------------------------------------------------------------------------------------------------------------------------------

    async def save_contractor_profile(
        self, clerk_user_id: str, profile_data: ContractorProfileCreate | ContractorProfileUpdate, image_files: List[Tuple[bytes, str]] = None
    ) -> ContractorProfileResponse:
        """Save or update contractor profile information with optional images"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Check if profile already exists
            existing_result = await self.supabase_client.table("contractor_profiles").select("*").eq("user_id", user_id).execute()

            # Prepare profile data (no JSON conversion needed now)
            profile_record = profile_data.model_dump(exclude_unset=True)

            if existing_result.data:
                # Update existing profile
                profile_id = existing_result.data[0]["id"]
                result = await self.supabase_client.table("contractor_profiles").update(profile_record).eq("user_id", user_id).execute()
            else:
                # Create new profile
                profile_record["user_id"] = user_id
                result = await self.supabase_client.table("contractor_profiles").insert(profile_record).execute()
                profile_id = result.data[0]["id"]

            if not result.data:
                raise DatabaseError("Failed to save contractor profile")

            # Handle images if provided
            if image_files:
                # Delete existing images and upload new ones
                await self._delete_profile_images(profile_id)
                await self._upload_profile_images_create_records(profile_id, image_files)

            # Get the complete profile with images for response
            return await self.get_contractor_profile(clerk_user_id)

        except Exception as e:
            logger.error(f"Error in save_contractor_profile: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # -------------------------------------------------------------------------------------------------------------------------------

    async def is_contractor_profile_complete(self, clerk_user_id: str) -> bool:
        """Check if contractor profile is complete"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Use the database function we created
            result = await self.supabase_client.rpc("is_contractor_profile_complete", {"user_uuid": user_id}).execute()

            return result.data if result.data is not None else False

        except Exception as e:
            logger.error(f"Error checking profile completion: {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")
