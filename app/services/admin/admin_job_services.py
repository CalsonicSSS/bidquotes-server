from supabase import AsyncClient
from app.models.admin.admin_job_models import (
    AdminJobCardResponse,
    AdminJobDetailResponse,
    PaginatedJobsResponse,
    AdminJobImageResponse,
    BuyerContactResponse,
)
from app.custom_error import ValidationError, ServerError
import logging
from typing import List
import math

logger = logging.getLogger(__name__)


class AdminJobService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    # =====================================
    # JOB VALIDATION OPERATIONS
    # =====================================

    async def get_all_job_cards_paginated(self, page: int = 1, page_size: int = 30) -> PaginatedJobsResponse:
        """Get all job cards for admin view with pagination"""
        try:
            # Calculate offset
            offset = (page - 1) * page_size

            # Get total count first
            count_result = await self.supabase_client.table("jobs").select("id", count="exact").execute()
            total = count_result.count if count_result.count else 0

            # Fetch jobs with left join to get thumbnail
            job_result = (
                await self.supabase_client.table("jobs")
                .select("id, title, job_type, job_budget, city, status, is_validated, created_at, job_images(image_url)")
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )

            # Format job cards
            job_cards = []
            for job in job_result.data:
                # Get thumbnail (first image)
                thumbnail_url = None
                if job.get("job_images") and len(job["job_images"]) > 0:
                    thumbnail_url = job["job_images"][0]["image_url"]

                job_card = AdminJobCardResponse(
                    id=job["id"],
                    title=job["title"],
                    job_type=job["job_type"],
                    job_budget=job["job_budget"],
                    city=job["city"],
                    status=job["status"],
                    is_validated=job["is_validated"],
                    thumbnail_url=thumbnail_url,
                    created_at=job["created_at"],
                )
                job_cards.append(job_card)

            # Calculate total pages
            total_pages = math.ceil(total / page_size) if total > 0 else 1

            return PaginatedJobsResponse(
                jobs=job_cards,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )

        except Exception as e:
            logger.error(f"Error fetching admin job cards: {str(e)}")
            raise ServerError(f"Failed to fetch job cards: {str(e)}")

    # --------------------------------------------------------------

    async def get_job_detail_with_buyer_contact(self, job_id: str) -> AdminJobDetailResponse:
        """Get full job detail with buyer contact info for admin validation"""
        try:
            # Fetch job with images
            job_result = await self.supabase_client.table("jobs").select("*, job_images(*)").eq("id", job_id).single().execute()

            if not job_result.data:
                raise ValidationError("Job not found")

            job_data = job_result.data

            # Format images
            images = []
            if job_data.get("job_images"):
                for img in job_data["job_images"]:
                    images.append(
                        AdminJobImageResponse(
                            id=img["id"],
                            image_url=img["image_url"],
                            image_order=img["image_order"],
                        )
                    )
                images.sort(key=lambda x: x.image_order)

            # Fetch buyer contact info using buyer_id
            buyer_id = job_data["buyer_id"]
            buyer_result = (
                await self.supabase_client.table("buyer_profiles").select("contact_email, phone_number").eq("user_id", buyer_id).single().execute()
            )

            if not buyer_result.data:
                raise ValidationError("Buyer contact info not found")

            buyer_contact = BuyerContactResponse(
                contact_email=buyer_result.data["contact_email"],
                phone_number=buyer_result.data["phone_number"],
            )

            # Build response
            return AdminJobDetailResponse(
                id=job_data["id"],
                buyer_id=job_data["buyer_id"],
                title=job_data["title"],
                job_type=job_data["job_type"],
                job_budget=job_data["job_budget"],
                description=job_data.get("description"),
                location_address=job_data.get("location_address"),
                city=job_data.get("city"),
                other_requirements=job_data.get("other_requirements"),
                status=job_data["status"],
                is_validated=job_data["is_validated"],
                created_at=job_data["created_at"],
                updated_at=job_data["updated_at"],
                images=images,
                buyer_contact=buyer_contact,
            )

        except Exception as e:
            logger.error(f"Error fetching job detail for admin: {str(e)}")
            if isinstance(e, ValidationError):
                raise e
            raise ServerError(f"Failed to fetch job detail: {str(e)}")

    # --------------------------------------------------------------

    async def validate_job(self, job_id: str) -> bool:
        """Mark a job as validated"""
        try:
            result = await self.supabase_client.table("jobs").update({"is_validated": True}).eq("id", job_id).execute()

            if not result.data:
                raise ValidationError("Job not found")

            logger.info(f"✅ Job {job_id} marked as validated")
            return True

        except Exception as e:
            logger.error(f"Error validating job: {str(e)}")
            if isinstance(e, ValidationError):
                raise e
            raise ServerError(f"Failed to validate job: {str(e)}")

    # --------------------------------------------------------------

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job (for fake/noise jobs)"""
        try:
            # select this job to confirm it exists
            job_result = await self.supabase_client.table("jobs").select("id").eq("id", job_id).single().execute()

            if not job_result.data:
                raise ValidationError("Job not found")

            # Get all image records for this job with their storage path
            image_result = await self.supabase_client.table("job_images").select("storage_path").eq("job_id", job_id).execute()

            if image_result.data:
                # Delete image file from storage
                storage_paths = [img["storage_path"] for img in image_result.data if img.get("storage_path")]
                await self.supabase_client.storage.from_("job-images").remove(storage_paths)

                # Delete all image records from job_images table
                await self.supabase_client.table("job_images").delete().eq("job_id", job_id).execute()

                logger.info(f"✅ Deleted {len(storage_paths)} images for job {job_id}")

            result = await self.supabase_client.table("jobs").delete().eq("id", job_id).execute()

            if not result.data:
                raise ValidationError("Job not found")

            logger.info(f"🗑️ Job {job_id} deleted")
            return True

        except Exception as e:
            logger.error(f"Error deleting job: {str(e)}")
            if isinstance(e, ValidationError):
                raise e
            raise ServerError(f"Failed to delete job: {str(e)}")
