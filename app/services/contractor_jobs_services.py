from supabase import AsyncClient
from app.models.job_models import JobDetailViewResponse, JobImageResponse
from app.custom_error import UserNotFoundError, ServerError, ValidationError
from typing import Optional, List
import logging
from app.models.contractor_job_models import ContractorJobCardResponse, PreBidJobDetailResponse

logger = logging.getLogger(__name__)


class ContractorJobService:
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

    ############################################################################################
    # Core Contractor Job Methods
    ############################################################################################

    # checked
    async def get_available_job_cards(
        self, clerk_user_id: str, city_filter: Optional[str] = None, job_type_filter: Optional[str] = None
    ) -> List[ContractorJobCardResponse]:
        """Get all available jobs for contractors to bid on"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Build query to get open jobs (not from this contractor if they're also a buyer)
            query = (
                self.supabase_client.table("jobs")
                .select(
                    """
                    id, title, job_type, created_at, city,
                    job_images!left(image_url, image_order)
                """
                )
                .eq("status", "open")  # Only show open jobs
                .neq("buyer_id", user_id)  # Don't show contractor's own jobs if they're also a buyer
            )

            # Apply filters if provided
            if city_filter:
                query = query.eq("city", city_filter)
            if job_type_filter:
                query = query.eq("job_type", job_type_filter)

            # Order by latest first
            query = query.order("created_at", desc=True)
            result = await query.execute()

            available_jobs = []

            # get bid count for each job
            for job_data in result.data:
                bid_result = (
                    await self.supabase_client.table("bids")
                    .select("id")
                    .eq("job_id", job_data["id"])
                    .eq("status", "submitted")
                    .neq("status", "draft")
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

                # Create contractor job card
                job_card = ContractorJobCardResponse(
                    id=job_data["id"],
                    title=job_data["title"],
                    job_type=job_data["job_type"],
                    city=job_data["city"],  # Include city for contractors
                    bid_count=bid_count,
                    created_at=job_data["created_at"],
                    thumbnail_image=thumbnail_image,
                )
                available_jobs.append(job_card)

            logger.info(f"✅ Retrieved {len(available_jobs)} available jobs for contractor")
            return available_jobs

        except Exception as e:
            logger.error(f"Error getting available jobs - {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Failed to fetch available jobs")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    # checked
    async def get_job_cities(self) -> List[str]:
        """Get unique cities from all open jobs for filter dropdown"""
        try:
            result = await self.supabase_client.table("jobs").select("city").eq("status", "open").execute()

            # Extract unique cities and filter out empty ones
            cities = list(set([job["city"] for job in result.data if job.get("city") and job["city"].strip()]))
            cities.sort()  # Alphabetical order

            logger.info(f"✅ Retrieved {len(cities)} unique cities")
            return cities

        except Exception as e:
            logger.error(f"Error getting job cities - {str(e)}")
            raise ServerError(f"Failed to fetch job cities")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    # checked
    async def get_pre_bid_job_detail(self, clerk_user_id: str, job_id: str) -> PreBidJobDetailResponse:
        """Get complete job details for contractor review (without buyer contact info)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Get job with images - ensure it's an open job and not from this contractor
            job_result = (
                await self.supabase_client.table("jobs")
                .select(
                    """
                    id, buyer_id, title, created_at, job_type, job_budget, city, job_images(*)
                """
                )
                .eq("id", job_id)
                .neq("buyer_id", user_id)  # Don't allow viewing own jobs if contractor is also buyer
                .execute()
            )

            if not job_result.data:
                raise ValidationError("Job is not available")

            target_job_data = job_result.data[0]

            # Get bid count for this job (non-draft bids only)
            bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_id).eq("status", "submitted").execute()
            bid_count = len(bid_result.data) if bid_result.data else 0

            # Check if job is still available for bidding (less than 5 bids)
            if bid_count >= 5:
                raise ValidationError("This job is no longer accepting bids (full)")

            # Format images
            images = []
            if target_job_data.get("job_images"):
                for img in target_job_data["job_images"]:
                    images.append(JobImageResponse(**img))
                images.sort(key=lambda x: x.image_order)

            # Prepare response data (exclude buyer-specific sensitive info)
            response_data = {**target_job_data, "images": images, "bid_count": bid_count}
            response_data.pop("job_images", None)  # Remove raw job_images field

            logger.info(f"✅ Retrieved job detail for contractor: {job_id}")
            return PreBidJobDetailResponse(**response_data)

        except Exception as e:
            logger.error(f"Error getting contractor job detail - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to fetch job detail")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def get_contractor_full_job_detail(self, clerk_user_id: str, job_id: str) -> JobDetailViewResponse:
        """Get complete job details for contractor review (without buyer contact info)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Get job with images - ensure it's an open job and not from this contractor
            job_result = (
                await self.supabase_client.table("jobs")
                .select(
                    """
                    *, job_images(*)
                """
                )
                .eq("id", job_id)
                # .eq("status", "open")
                .neq("buyer_id", user_id)  # Don't allow viewing own jobs if contractor is also buyer
                .execute()
            )

            if not job_result.data:
                raise ValidationError("Job is not available")

            target_job_data = job_result.data[0]

            # Get bid count for this job (non-draft bids only)
            bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").execute()
            bid_count = len(bid_result.data) if bid_result.data else 0

            # Check if job is still available for bidding (less than 5 bids)
            if bid_count >= 5:
                raise ValidationError("This job is no longer accepting bids (full)")

            # Format images
            images = []
            if target_job_data.get("job_images"):
                for img in target_job_data["job_images"]:
                    images.append(JobImageResponse(**img))
                images.sort(key=lambda x: x.image_order)

            # Prepare response data (exclude buyer-specific sensitive info)
            response_data = {**target_job_data, "images": images, "bid_count": bid_count}
            response_data.pop("job_images", None)  # Remove raw job_images field

            logger.info(f"✅ Retrieved job detail for contractor: {job_id}")
            return JobDetailViewResponse(**response_data)

        except Exception as e:
            logger.error(f"Error getting contractor job detail - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to fetch job detail")
