from supabase import AsyncClient
from app.models.bid_models import BuyerBidCardInfo, BuyerBidDetailResponse
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
            logger.error(f"Error getting user_id - {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Failed to get user id")

    # =====================================================================================================
    # INTERNAL IMAGE PROCESSING METHODS
    # =====================================================================================================

    async def _upload_single_image(self, file_content: bytes, file_name: str, job_id: str) -> tuple[str, str]:
        """Internal: Upload single image and return (image_url, storage_path)"""
        try:
            # Generate storage path
            storage_path = f"{job_id}/{uuid.uuid4()}"

            # Upload to Supabase Storage
            await self.supabase_client.storage.from_("job-images").upload(
                path=storage_path, file=file_content, file_options={"content-type": mimetypes.guess_type(file_name)[0] or "image/jpeg"}
            )

            # Get this image public URL from supabase storage
            image_url = await self.supabase_client.storage.from_("job-images").get_public_url(storage_path)

            logger.info(f"✅ Image uploaded: {storage_path}")
            return image_url, storage_path

        except Exception as e:
            logger.error(f"Error uploading this image - {str(e)}")
            raise ServerError(f"Failed to upload a image")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _upload_to_storage_create_image_records(self, job_id: str, image_files: list[tuple[bytes, str]]) -> None:
        """Internal: loop multiple image files to upload for storage and create image record"""
        # if not image_files:
        #     return

        try:

            for index, (file_content, file_name) in enumerate(image_files, 1):
                if not file_content or not file_name:
                    continue

                # Upload to storage
                image_url, storage_path = await self._upload_single_image(file_content, file_name, job_id)

                # Create database record with storage path
                image_data = {"job_id": job_id, "image_url": image_url, "storage_path": storage_path, "image_order": index}  # Store for easy deletion
                await self.supabase_client.table("job_images").insert(image_data).execute()

            logger.info(f"✅ Finished upload and create all image records for job: {job_id}")
            return

        except Exception as e:
            logger.error(f"Error creating image records - {str(e)}")
            raise ServerError(f"Failed to process images")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _delete_job_images(self, job_id: str) -> None:
        """Internal: Delete all images for a job (both storage and database)"""
        try:
            # Get all image records for this job with their storage path
            result = await self.supabase_client.table("job_images").select("storage_path").eq("job_id", job_id).execute()

            if result.data:
                # Delete image file from storage
                storage_paths = [img["storage_path"] for img in result.data if img.get("storage_path")]
                await self.supabase_client.storage.from_("job-images").remove(storage_paths)

                # Delete all image records from job_images table
                await self.supabase_client.table("job_images").delete().eq("job_id", job_id).execute()

                logger.info(f"✅ Deleted {len(storage_paths)} images for job {job_id}")

        except Exception as e:
            logger.error(f"Error deleting job images - {str(e)}")
            raise ServerError(f"Failed to delete job images")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _update_job_images(self, job_id: str, new_image_files: List[Tuple[bytes, str]]) -> None:
        """Internal: Handle image updates by replacing existing images"""
        try:
            # For simplicity in MVP: delete all existing images and add new ones
            # In production, you could implement smart diff logic here
            await self._delete_job_images(job_id)

            # always handle image even if its empty
            await self._upload_to_storage_create_image_records(job_id, new_image_files)

        except Exception as e:
            logger.error(f"Error updating job images - {str(e)}")
            raise ServerError(f"Failed to update images")

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
                raise DatabaseError("Failed to create your job")

            job = JobResponse(**result.data[0])

            # Process images if provided
            if image_files:
                await self._upload_to_storage_create_image_records(job.id, image_files)

            logger.info(f"✅ Job created with {len(image_files) if image_files else 0} images, at job id: {job.id}")
            return job

        except Exception as e:
            logger.error(f"Error creating job - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Failed to create your job")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def save_job_draft(self, clerk_user_id: str, draft_data: JobDraftCreate, image_files: List[Tuple[bytes, str]] = None) -> JobResponse:
        """Save job as draft with optional images"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Prepare draft data
            draft_record = draft_data.model_dump()
            draft_record["buyer_id"] = user_id
            draft_record["status"] = JobStatus.DRAFT.value

            # Create draft
            result = await self.supabase_client.table("jobs").insert(draft_record).execute()
            if not result.data:
                raise DatabaseError("Failed to save your draft")

            draft = JobResponse(**result.data[0])

            # Process images if provided
            if image_files:
                await self._upload_to_storage_create_image_records(draft.id, image_files)

            logger.info(f"✅ Draft saved with {len(image_files) if image_files else 0} images, at job id: {draft.id}")
            return draft

        except Exception as e:
            logger.error(f"Error saving draft - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError)):
                raise e
            raise ServerError(f"Failed to save your draft")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def update_job(
        self, clerk_user_id: str, job_id: str, job_data: JobUpdate, is_draft_post: bool, image_files: List[Tuple[bytes, str]] = None
    ) -> JobResponse:
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

            # Update job record (handle for both draft and regular update cases)
            if is_draft_post:
                job_record_updates["status"] = JobStatus.OPEN.value
                result = await self.supabase_client.table("jobs").update(job_record_updates).eq("id", job_id).execute()
                if not result.data:
                    raise DatabaseError("Failed to update your job info")
                updated_job = JobResponse(**result.data[0])

            else:
                result = await self.supabase_client.table("jobs").update(job_record_updates).eq("id", job_id).execute()
                if not result.data:
                    raise DatabaseError("Failed to update your job info")
                updated_job = JobResponse(**result.data[0])

            # Handle image (always)
            await self._update_job_images(job_id, image_files)

            logger.info(f"✅ Job updated with {len(image_files) if image_files else 0} image changes, at job id: {job_id}")
            return updated_job

        except Exception as e:
            logger.error(f"Error updating job - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to update your job info")

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

            # Delete associated images from storage and records
            await self._delete_job_images(job_id)

            # Delete job record (CASCADE will handle bids deletion as well)
            result = await self.supabase_client.table("jobs").delete().eq("id", job_id).execute()

            if result.data:
                logger.info(f"✅ Job and all associated data deleted: {job_id}")
                return True
            else:
                raise DatabaseError("Failed to delete your job")

        except Exception as e:
            logger.error(f"Error deleting job: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to delete your job")

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

            fetched_jobs = []
            for job_data in result.data:
                # Get bid count
                bid_result = (
                    await self.supabase_client.table("bids")
                    .select("id")
                    .eq("job_id", job_data["id"])
                    .neq("status", "draft")
                    .neq("status", "declined")
                    .execute()
                )
                bid_count = len(bid_result.data) if bid_result.data else 0

                # Get thumbnail (first image)
                thumbnail_image = None
                if job_data.get("job_images"):
                    for img in job_data["job_images"]:
                        if img.get("image_order") == 1:
                            thumbnail_image = img.get("image_url")
                            break

                fetched_jobs.append(
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

            logger.info(f"✅ Retrieved {len(fetched_jobs)} job cards for buyer")
            return fetched_jobs

        except Exception as e:
            logger.error(f"Error getting job cards - {str(e)}")
            if isinstance(e, (UserNotFoundError)):
                raise e
            raise ServerError(f"Failed to fetch jobs")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def get_job_detail(self, clerk_user_id: str, job_id: str) -> JobDetailViewResponse:
        """Get detailed job information including bid details for buyer"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Fetch job with permission check
            job_result = await self.supabase_client.table("jobs").select("*").eq("id", job_id).eq("buyer_id", user_id).execute()
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            job_data = job_result.data[0]

            # Fetch job images
            images_result = await self.supabase_client.table("job_images").select("*").eq("job_id", job_id).order("image_order").execute()
            job_images = [JobImageResponse(**img) for img in images_result.data] if images_result.data else []

            # Fetch bids (no contractor info exposed)
            job_bids_result = (
                await self.supabase_client.table("bids")
                .select("*")
                .eq("job_id", job_id)
                .neq("status", "draft")
                .neq("status", "declined")
                .order("created_at")
                .execute()
            )

            # Process bid data
            bid_cards = []
            if job_bids_result.data:
                for bid_data in job_bids_result.data:
                    bid_card = BuyerBidCardInfo(
                        id=bid_data["id"],
                        contractor_id=bid_data["contractor_id"],
                        title=bid_data["title"],
                        price_min=bid_data["price_min"],
                        price_max=bid_data["price_max"],
                        timeline_estimate=bid_data["timeline_estimate"],
                        status=bid_data["status"],
                        is_selected=bid_data["is_selected"],
                        created_at=bid_data["created_at"],
                    )
                    bid_cards.append(bid_card)

            # Count current non-draft bids
            bid_count = len(bid_cards)

            # Create complete job response
            job_detail_response = JobDetailViewResponse(**job_data, bid_count=bid_count, images=job_images, bids=bid_cards)

            logger.info(f"✅ Job detail fetched with {bid_count} bids for job {job_id}")
            return job_detail_response

        except Exception as e:
            logger.error(f"Error fetching job detail - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to fetch job details")

    # ------------------------------------------------------------------------------------------------------------------------------------------------------

    # =====================================================================================================
    # CORE JOB BID OPERATIONS
    # =====================================================================================================

    async def get_bid_detail_for_buyer(self, clerk_user_id: str, job_id: str, bid_id: str) -> BuyerBidDetailResponse:
        """Get bid details for buyer review (no contractor contact info exposed)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # First verify buyer owns the job
            job_result = (
                await self.supabase_client.table("jobs")
                .select("id, title, job_type, job_budget, city")
                .eq("id", job_id)
                .eq("buyer_id", user_id)
                .execute()
            )
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            job_data = job_result.data[0]

            # Get bid details with verification that bid belongs to this job
            bid_result = await self.supabase_client.table("bids").select("*").eq("id", bid_id).eq("job_id", job_id).execute()
            if not bid_result.data:
                raise ValidationError("Bid not found for this job")

            bid_data = bid_result.data[0]

            # Create complete bid detail response
            bid_detail = BuyerBidDetailResponse(
                id=bid_data["id"],
                job_id=bid_data["job_id"],
                contractor_id=bid_data["contractor_id"],
                title=bid_data["title"],
                price_min=bid_data["price_min"],
                price_max=bid_data["price_max"],
                timeline_estimate=bid_data["timeline_estimate"],
                work_description=bid_data["work_description"],
                additional_notes=bid_data["additional_notes"],
                status=bid_data["status"],
                is_selected=bid_data["is_selected"],
                created_at=bid_data["created_at"],
                updated_at=bid_data["updated_at"],
                # Job context
                job_title=job_data["title"],
                job_type=job_data["job_type"],
                job_budget=job_data["job_budget"],
                job_city=job_data["city"],
            )

            logger.info(f"✅ Bid detail fetched for buyer - bid: {bid_id}, job: {job_id}")
            return bid_detail

        except Exception as e:
            logger.error(f"Error fetching bid detail for buyer - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to fetch bid details")

    # ------------------------------------------------------------------------------------------------------------------------------------------------------

    async def select_bid(self, clerk_user_id: str, job_id: str, bid_id: str) -> bool:
        """Select a bid for a job (max 3 selections allowed per job)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify buyer owns the job and get job details
            job_result = await self.supabase_client.table("jobs").select("*").eq("id", job_id).eq("buyer_id", user_id).execute()
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            job_data = job_result.data[0]

            # Check if job is in valid status for selection
            if job_data["status"] not in ["open", "full_bid"]:
                raise ValidationError("Cannot select bid for job in current status")

            # Check selection limit (max 3 selections per job)
            if job_data["selection_count"] > job_data["max_selections"]:
                raise ValidationError("Maximum number of bid selections reached for this job")

            # Verify bid exists and belongs to this job
            bid_result = (
                await self.supabase_client.table("bids")
                .select("*")
                .eq("id", bid_id)
                .eq("job_id", job_id)
                .neq("status", "draft")
                .neq("status", "declined")
                .execute()
            )
            if not bid_result.data:
                raise ValidationError("Bid not found for this job")

            bid_data = bid_result.data[0]

            # Check if bid is already selected
            if bid_data["is_selected"]:
                raise ValidationError("This bid is already selected")

            # Start transaction-like operations
            # 1. Unselect any currently selected bid for this job
            await self.supabase_client.table("bids").update({"is_selected": False}).eq("job_id", job_id).eq("is_selected", True).execute()

            # 2. Select the new bid
            await self.supabase_client.table("bids").update({"is_selected": True, "status": "selected"}).eq("id", bid_id).execute()

            # 3. Update job status and increment selection count
            new_selection_count = job_data["selection_count"] + 1
            await self.supabase_client.table("jobs").update({"status": "waiting_confirmation", "selection_count": new_selection_count}).eq(
                "id", job_id
            ).execute()

            logger.info(f"✅ Bid selected successfully - job: {job_id}, bid: {bid_id}, selection count: {new_selection_count}")

            # TODO: Send email notification to contractor (placeholder for now)
            # await self._send_bid_selection_notification(bid_data["contractor_id"], job_id, bid_id)

            return True

        except Exception as e:
            logger.error(f"Error selecting bid - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to select bid")

    # -----------------------------------------------------------------------------------------------------------------------

    async def cancel_bid_selection(self, clerk_user_id: str, job_id: str) -> bool:
        """Cancel current bid selection for a job"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify buyer owns the job and get job details
            job_result = await self.supabase_client.table("jobs").select("*").eq("id", job_id).eq("buyer_id", user_id).execute()
            if not job_result.data:
                raise ValidationError("Job not found or permission denied")

            job_data = job_result.data[0]

            # Check if job is in valid status for cancellation
            if job_data["status"] != "waiting_confirmation":
                raise ValidationError("No bid selection to cancel for this job")

            # Find the currently selected bid
            selected_bid_result = await self.supabase_client.table("bids").select("*").eq("job_id", job_id).eq("is_selected", True).execute()
            if not selected_bid_result.data:
                raise ValidationError("No selected bid found for this job")

            selected_bid = selected_bid_result.data[0]

            # Start transaction-like operations
            # 1. Unselect the bid and reset its status to pending
            await self.supabase_client.table("bids").update({"is_selected": False, "status": "pending"}).eq("id", selected_bid["id"]).execute()

            # 2. Determine new job status based on bid count
            bid_count_result = (
                await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").neq("status", "declined").execute()
            )
            current_bid_count = len(bid_count_result.data) if bid_count_result.data else 0

            new_job_status = "full_bid" if current_bid_count >= 5 else "open"

            # 3. Update job status (selection_count stays the same as it tracks total selections made)
            await self.supabase_client.table("jobs").update({"status": new_job_status}).eq("id", job_id).execute()

            logger.info(f"✅ Bid selection cancelled - job: {job_id}, bid: {selected_bid['id']}, new job status: {new_job_status}")

            # TODO: Send email notification to contractor (placeholder for now)
            # await self._send_bid_cancellation_notification(selected_bid["contractor_id"], job_id, selected_bid["id"])

            return True

        except Exception as e:
            logger.error(f"Error cancelling bid selection - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to cancel bid selection")
