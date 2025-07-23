from supabase import AsyncClient
from app.models.job_models import (
    JobCreate,
    JobUpdate,
    JobDraftCreate,
    JobResponse,
    JobDetailViewResponse,
    JobCardResponse,
    JobImageResponse,
    JobStatus,
)
from app.custom_error import UserNotFoundError, DatabaseError, ServerError, ValidationError
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class JobService:
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
            logger.error(f"Error getting user_id: {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def create_job(self, clerk_user_id: str, job_data: JobCreate) -> JobResponse:
        """Create a new job posting"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            job_data_prepared = job_data.model_dump(exclude_none=True)
            job_data_prepared["buyer_id"] = user_id
            job_data_prepared["status"] = JobStatus.OPEN.value  # New jobs are immediately open for bidding

            result = await self.supabase_client.table("jobs").insert(job_data_prepared).execute()

            if not result.data:
                raise DatabaseError("Failed to create job")

            logger.info(f"✅ Job created successfully: {result.data[0]['id']}")
            return JobResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def save_job_draft(self, clerk_user_id: str, draft_data: JobDraftCreate) -> JobResponse:
        """Save job as draft"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Prepare draft data (only include non-None values)
            # Add only provided fields
            draft_data_prepared = draft_data.model_dump(exclude_none=True)
            draft_data_prepared["buyer_id"] = user_id
            draft_data_prepared["status"] = JobStatus.DRAFT.value

            result = await self.supabase_client.table("jobs").insert(draft_data_prepared).execute()

            if not result.data:
                raise DatabaseError("Failed to save draft")

            logger.info(f"✅ Job draft saved: {result.data[0]['id']}")
            return JobResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error saving job draft: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def update_job(self, clerk_user_id: str, job_id: str, job_data: JobUpdate) -> JobResponse:
        """Update existing job (only if status allows)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # First, check if job exists and belongs to user
            job_result = await self.supabase_client.table("jobs").select("status").eq("id", job_id).eq("buyer_id", user_id).execute()

            if not job_result.data:
                raise ValidationError("Job not found or you don't have permission to edit it")

            current_status = job_result.data[0]["status"]

            # Only allow updates for draft, open, or full_bid status
            if current_status not in [JobStatus.DRAFT.value, JobStatus.OPEN.value, JobStatus.FULL_BID.value]:
                raise ValidationError("Cannot edit job in current status")

            # Prepare update data (only include non-None values)
            job_data_prepared = job_data.model_dump(exclude_none=True)

            if not job_data_prepared:
                raise ValidationError("No valid fields to update")

            result = await self.supabase_client.table("jobs").update(job_data_prepared).eq("id", job_id).eq("buyer_id", user_id).execute()

            if not result.data:
                raise DatabaseError("Failed to update job")

            logger.info(f"✅ Job updated: {job_id}")
            return JobResponse(**result.data[0])

        except Exception as e:
            logger.error(f"Error updating job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def get_buyer_jobs(self, clerk_user_id: str, status_filter: Optional[str] = None) -> List[JobCardResponse]:
        """Get all jobs for a buyer with optional status filter"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Build query
            # this is a powerful query which will does a left join between "jobs" table and "job_images". and auto agg all the matching image to a single job with "job_images" field
            query = (
                self.supabase_client.table("jobs")
                .select(
                    """
                id, title, job_type, status, created_at,
                job_images!left(image_url, image_order)
            """
                )
                .eq("buyer_id", user_id)
            )

            if status_filter:
                query = query.eq("status", status_filter)

            # Order by creation date (newest first)
            query = query.order("created_at", desc=True)

            result = await query.execute()

            jobs = []
            for job_data in result.data:
                # Get bid count for this job
                bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_data["id"]).neq("status", "draft").execute()
                bid_count = len(bid_result.data) if bid_result.data else 0

                # Get first image as thumbnail
                thumbnail_image = None
                if job_data.get("job_images") and len(job_data["job_images"]) > 0:
                    # Sort by image_order and get first one
                    sorted_images = sorted(job_data["job_images"], key=lambda x: x.get("image_order", 1))
                    thumbnail_image = sorted_images[0].get("image_url")

                jobs.append(
                    JobCardResponse(
                        id=job_data["id"],
                        title=job_data["title"],
                        job_type=job_data["job_type"],
                        status=job_data["status"],
                        bid_count=bid_count,
                        created_at=job_data["created_at"],
                        thumbnail_image=thumbnail_image,
                    )
                )

            logger.info(f"✅ Retrieved {len(jobs)} jobs for buyer")
            return jobs

        except Exception as e:
            logger.error(f"Error getting buyer jobs: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def get_job_detail(self, clerk_user_id: str, job_id: str) -> JobDetailViewResponse:
        """Get detailed job information"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Get job with images
            # Selects all columns from the jobs table
            # Selects all columns from the job_images table that are related to the jobs table.
            # This utilizes Supabase's automatic foreign key relationship detection to perform a LEFT JOIN between jobs and job_images based on the foreign key constraint.
            # The job_images field in output will also auto group up all the multiple images for this job already
            job_result = (
                await self.supabase_client.table("jobs")
                .select(
                    """
                *, job_images(*)
            """
                )
                .eq("id", job_id)
                .eq("buyer_id", user_id)
                .execute()
            )

            if not job_result.data:
                raise ValidationError("Job not found or you don't have permission to view it")

            job_data = job_result.data[0]

            # Get bid count
            bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").execute()
            bid_count = len(bid_result.data) if bid_result.data else 0

            # Format images
            images = []
            if job_data.get("job_images"):
                for img in job_data["job_images"]:
                    images.append(JobImageResponse(**img))
                # Sort by image_order
                images.sort(key=lambda x: x.image_order)

            response_data = {**job_data, "images": images, "bid_count": bid_count}
            # Remove job_images from response_data since we're using images field
            response_data.pop("job_images", None)

            logger.info(f"✅ Retrieved job detail: {job_id}")
            return JobDetailViewResponse(**response_data)

        except Exception as e:
            logger.error(f"Error getting job detail: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # ----------------------------------------------------------------------------------------------------------------------------------

    async def delete_job(self, clerk_user_id: str, job_id: str) -> bool:
        """Delete job (only if status allows)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Check if job exists and get status
            job_result = await self.supabase_client.table("jobs").select("status").eq("id", job_id).eq("buyer_id", user_id).execute()

            if not job_result.data:
                raise ValidationError("Job not found")

            current_status = job_result.data[0]["status"]

            # Only allow deletion for draft, open, or full_bid status
            if current_status not in [JobStatus.DRAFT.value, JobStatus.OPEN.value, JobStatus.FULL_BID.value]:
                raise ValidationError("Cannot delete job in current status")

            # Delete job (CASCADE will handle related records like images and bids)
            result = await self.supabase_client.table("jobs").delete().eq("id", job_id).eq("buyer_id", user_id).execute()

            if result.data:
                logger.info(f"✅ Job deleted: {job_id}")
                return True
            else:
                raise DatabaseError("Failed to delete job")

        except Exception as e:
            logger.error(f"Error deleting job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")
