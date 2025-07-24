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
from typing import List, Optional, Tuple
import logging
import uuid
import mimetypes

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

    # =====================================================================================================
    # INTERNAL IMAGE PROCESSING METHODS
    # =====================================================================================================

    async def _upload_single_image(self, file_content: bytes, file_name: str, job_id: str) -> Tuple[str, str]:
        """Internal: Upload single image and return (image_url, storage_path)"""
        try:
            # Generate unique filename
            file_extension = file_name.split(".")[-1] if "." in file_name else "jpg"
            storage_path = f"{job_id}/{uuid.uuid4()}.{file_extension}"

            # Upload to Supabase Storage
            result = await self.supabase_client.storage.from_("job-images").upload(
                path=storage_path, file=file_content, file_options={"content-type": mimetypes.guess_type(file_name)[0] or "image/jpeg"}
            )

            if result.get("error"):
                raise DatabaseError(f"Failed to upload image: {result['error']}")

            # Get public URL
            image_url = self.supabase_client.storage.from_("job-images").get_public_url(storage_path)

            logger.info(f"✅ Image uploaded: {storage_path}")
            return image_url, storage_path

        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            if isinstance(e, DatabaseError):
                raise e
            raise ServerError(f"Image upload failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _create_image_records(self, job_id: str, image_files: List[Tuple[bytes, str]]) -> List[JobImageResponse]:
        """Internal: Process and create multiple image records"""
        if not image_files:
            return []

        try:
            uploaded_images = []

            for index, (file_content, file_name) in enumerate(image_files, 1):
                if not file_content or not file_name:
                    continue

                # Upload to storage
                image_url, storage_path = await self._upload_single_image(file_content, file_name, job_id)

                # Create database record with storage path
                image_data = {"job_id": job_id, "image_url": image_url, "storage_path": storage_path, "image_order": index}  # Store for easy deletion

                result = await self.supabase_client.table("job_images").insert(image_data).execute()
                if result.data:
                    uploaded_images.append(JobImageResponse(**result.data[0]))

            logger.info(f"✅ Created {len(uploaded_images)} image records for job {job_id}")
            return uploaded_images

        except Exception as e:
            logger.error(f"Error creating image records: {str(e)}")
            raise ServerError(f"Failed to process images: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _delete_job_images(self, job_id: str) -> bool:
        """Internal: Delete all images for a job (both storage and database)"""
        try:
            # Get all image records for this job
            result = await self.supabase_client.table("job_images").select("storage_path").eq("job_id", job_id).execute()

            if result.data:
                # Delete from storage
                storage_paths = [img["storage_path"] for img in result.data if img.get("storage_path")]
                storage_result = await self.supabase_client.storage.from_("job-images").remove(storage_paths)
                if storage_result.get("error"):
                    logger.warning(f"⚠️ Storage deletion warning: {storage_result['error']}")

                await self.supabase_client.table("job_images").delete().eq("job_id", job_id).execute()

                logger.info(f"✅ Deleted {len(storage_paths)} images for job {job_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting job images: {str(e)}")
            # Don't fail the whole operation if image cleanup fails
            logger.warning(f"⚠️ Image cleanup failed but continuing: {str(e)}")
            return False

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _update_job_images(self, job_id: str, new_image_files: List[Tuple[bytes, str]]) -> List[JobImageResponse]:
        """Internal: Handle image updates by replacing existing images"""
        try:
            # For simplicity in MVP: delete all existing images and add new ones
            # In production, you could implement smart diff logic here
            await self._delete_job_images(job_id)

            # Add new images
            if new_image_files:
                return await self._create_image_records(job_id, new_image_files)

            return []

        except Exception as e:
            logger.error(f"Error updating job images: {str(e)}")
            raise ServerError(f"Failed to update images: {str(e)}")

    # =====================================================================================================
    # CORE JOB CRUD OPERATIONS
    # =====================================================================================================

    async def create_job(self, clerk_user_id: str, job_data: JobCreate, image_files: List[Tuple[bytes, str]] = None) -> JobResponse:
        """Create a new job posting with optional images"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Prepare job data
            job_record = job_data.model_dump(exclude_none=True)
            job_record["buyer_id"] = user_id
            job_record["status"] = JobStatus.OPEN.value

            # Create job
            result = await self.supabase_client.table("jobs").insert(job_record).execute()
            if not result.data:
                raise DatabaseError("Failed to create job")

            job = JobResponse(**result.data[0])

            # Process images if provided
            if image_files:
                await self._create_image_records(job.id, image_files)

            logger.info(f"✅ Job created with {len(image_files) if image_files else 0} images, at job id: {job.id}")
            return job

        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def save_job_draft(self, clerk_user_id: str, draft_data: JobDraftCreate, image_files: List[Tuple[bytes, str]] = None) -> JobResponse:
        """Save job as draft with optional images"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Prepare draft data
            draft_record = draft_data.model_dump(exclude_none=True)
            draft_record["buyer_id"] = user_id
            draft_record["status"] = JobStatus.DRAFT.value

            # Create draft
            result = await self.supabase_client.table("jobs").insert(draft_record).execute()
            if not result.data:
                raise DatabaseError("Failed to save draft")

            draft = JobResponse(**result.data[0])

            # Process images if provided
            if image_files:
                await self._create_image_records(draft.id, image_files)

            logger.info(f"✅ Draft saved with {len(image_files) if image_files else 0} images, at job id: {draft.id}")
            return draft

        except Exception as e:
            logger.error(f"Error saving draft: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def update_job(self, clerk_user_id: str, job_id: str, job_data: JobUpdate, image_files: List[Tuple[bytes, str]] = None) -> JobResponse:
        """Update existing job with optional image changes"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify permissions and status
            job_result = await self.supabase_client.table("jobs").select("status").eq("id", job_id).eq("buyer_id", user_id).execute()
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            current_status = job_result.data[0]["status"]
            if current_status not in [JobStatus.DRAFT.value, JobStatus.OPEN.value, JobStatus.FULL_BID.value]:
                raise ValidationError("Cannot edit job in current status")

            # Update job data if provided
            job_record_updates = job_data.model_dump(exclude_none=True)

            if not job_record_updates and not image_files:
                raise ValidationError("No changes to update")

            # Update job record if there are field changes
            if job_record_updates:
                result = await self.supabase_client.table("jobs").update(job_record_updates).eq("id", job_id).execute()
                if not result.data:
                    raise DatabaseError("Failed to update job")
                updated_job = JobResponse(**result.data[0])
            else:
                # Get current job data if only updating images
                result = await self.supabase_client.table("jobs").select("*").eq("id", job_id).execute()
                updated_job = JobResponse(**result.data[0])

            # Handle image updates if provided
            if image_files:
                await self._update_job_images(job_id, image_files)

            logger.info(f"✅ Job updated with {len(image_files) if image_files else 0} image changes, at job id: {job_id}")
            return updated_job

        except Exception as e:
            logger.error(f"Error updating job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def delete_job(self, clerk_user_id: str, job_id: str) -> bool:
        """Delete job with complete cleanup (images, bids, etc.)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify permissions and status
            job_result = await self.supabase_client.table("jobs").select("status").eq("id", job_id).eq("buyer_id", user_id).execute()
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            current_status = job_result.data[0]["status"]
            if current_status not in [JobStatus.DRAFT.value, JobStatus.OPEN.value, JobStatus.FULL_BID.value]:
                raise ValidationError("Cannot delete job in current status")

            # Delete associated images from storage first
            await self._delete_job_images(job_id)

            # Delete job record (CASCADE will handle bids and other related records)
            result = await self.supabase_client.table("jobs").delete().eq("id", job_id).execute()

            if result.data:
                logger.info(f"✅ Job and all associated data deleted: {job_id}")
                return True
            else:
                raise DatabaseError("Failed to delete job")

        except Exception as e:
            logger.error(f"Error deleting job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # =====================================================================================================
    # JOB READING OPERATIONS
    # =====================================================================================================

    async def get_buyer_job_cards(self, clerk_user_id: str, status_filter: Optional[str] = None) -> List[JobCardResponse]:
        """Get job cards for buyer dashboard"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Build query with left join for images
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

            query = query.order("created_at", desc=True)
            result = await query.execute()

            jobs = []
            for job_data in result.data:
                # Get bid count
                bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_data["id"]).neq("status", "draft").execute()
                bid_count = len(bid_result.data) if bid_result.data else 0

                # Get thumbnail (first image)
                thumbnail_image = None
                if job_data.get("job_images") and job_data["job_images"]:
                    for img in job_data["job_images"]:
                        if img.get("image_order") == 1:
                            thumbnail_image = img.get("image_url")
                            break

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

            logger.info(f"✅ Retrieved {len(jobs)} job cards for buyer")
            return jobs

        except Exception as e:
            logger.error(f"Error getting job cards: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def get_job_detail(self, clerk_user_id: str, job_id: str) -> JobDetailViewResponse:
        """Get complete job details with images and bids for buyer review"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Get job with images
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
                raise ValidationError("Job not found or permission denied")

            job_data = job_result.data[0]

            # Get bid count
            bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").execute()
            bid_count = len(bid_result.data) if bid_result.data else 0

            # TODO: Get detailed bid information for buyer review
            # This will be implemented when we create the bid system
            # For now, just include bid_count

            # Format images
            images = []
            if job_data.get("job_images"):
                for img in job_data["job_images"]:
                    images.append(JobImageResponse(**img))
                images.sort(key=lambda x: x.image_order)

            # Prepare response data
            response_data = {**job_data, "images": images, "bid_count": bid_count}
            response_data.pop("job_images", None)  # Remove raw job_images field

            logger.info(f"✅ Retrieved job detail: {job_id}")
            return JobDetailViewResponse(**response_data)

        except Exception as e:
            logger.error(f"Error getting job detail: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Server operation failed: {str(e)}")
