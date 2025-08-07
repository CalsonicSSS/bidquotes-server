from supabase import AsyncClient
from app.models.job_models import ContractorJobCardResponse
from app.custom_error import UserNotFoundError, ServerError
from typing import Optional, List
import logging

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

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def get_available_jobs(
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
                    id, title, job_type, status, created_at, city,
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
            for job_data in result.data:
                # Get bid count for this job (non-draft bids only)
                bid_result = await self.supabase_client.table("bids").select("id").eq("job_id", job_data["id"]).neq("status", "draft").execute()
                bid_count = len(bid_result.data) if bid_result.data else 0

                # Only include jobs with less than 5 bids (not full)
                if bid_count < 5:
                    # Get thumbnail (first image)
                    thumbnail_image = None
                    if job_data.get("job_images"):
                        for img in job_data["job_images"]:
                            if img.get("image_order") == 1:
                                thumbnail_image = img.get("image_url")
                                break

                    # Create contractor job card with city information
                    job_card = ContractorJobCardResponse(
                        id=job_data["id"],
                        title=job_data["title"],
                        job_type=job_data["job_type"],
                        status=job_data["status"],
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
