from supabase import AsyncClient
from app.models.bid_models import BidCreate, BidUpdate, BidDraftCreate, BidResponse, BidDetailResponse, BidStatus
from app.custom_error import UserNotFoundError, DatabaseError, ServerError, ValidationError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BidService:
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
    # VALIDATION HELPERS
    # =====================================================================================================

    async def _validate_job_available_for_bidding(self, job_id: str, contractor_id: str) -> None:
        """Validate that job is available for bidding"""
        # Check job exists and is open
        job_result = await self.supabase_client.table("jobs").select("status, buyer_id").eq("id", job_id).execute()

        if not job_result.data:
            raise ValidationError("Job not found")

        job = job_result.data[0]

        if job["status"] != "open":
            raise ValidationError("This job is no longer accepting bids")

        if job["buyer_id"] == contractor_id:
            raise ValidationError("Cannot bid on your own job")

        # Check bid count (max 5 bids per job)
        bid_count_result = (
            await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").neq("status", "declined").execute()
        )
        bid_count = len(bid_count_result.data) if bid_count_result.data else 0

        if bid_count >= 5:
            raise ValidationError("This job already has the maximum number of bids")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def _validate_no_existing_bid(self, job_id: str, contractor_id: str, exclude_bid_id: Optional[str] = None) -> None:
        """Validate contractor hasn't already bid on this job"""
        query = self.supabase_client.table("bids").select("id").eq("job_id", job_id).eq("contractor_id", contractor_id)

        if exclude_bid_id:
            query = query.neq("id", exclude_bid_id)

        result = await query.execute()

        if result.data:
            raise ValidationError("You have already submitted a bid for this job")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    def _validate_bid_data(self, price_min: str, price_max: str) -> None:
        """Validate bid data"""
        if float(price_min) < 0 or float(price_max) < 0:
            raise ValidationError("Prices must be positive")

        if float(price_min) > float(price_max):
            raise ValidationError("Minimum price cannot be greater than maximum price")

    # =====================================================================================================
    # CORE BID OPERATIONS
    # =====================================================================================================

    async def create_bid(self, clerk_user_id: str, bid_data: BidCreate) -> BidResponse:
        """Create a new bid submission"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Validate job is available for bidding
            await self._validate_job_available_for_bidding(bid_data.job_id, contractor_id)

            # Validate no existing bid from this contractor
            await self._validate_no_existing_bid(bid_data.job_id, contractor_id)

            # Validate bid data
            self._validate_bid_data(bid_data.price_min, bid_data.price_max)

            # Prepare bid record
            bid_record = bid_data.model_dump()
            bid_record["contractor_id"] = contractor_id
            bid_record["status"] = BidStatus.PENDING.value

            # Create bid
            result = await self.supabase_client.table("bids").insert(bid_record).execute()
            if not result.data:
                raise DatabaseError("Failed to create your bid")

            bid = BidResponse(**result.data[0])

            logger.info(f"✅ Bid created successfully: {bid.id}")
            return bid

        except Exception as e:
            logger.error(f"Error creating bid - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to create your bid")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def save_bid_draft(self, clerk_user_id: str, draft_data: BidDraftCreate) -> BidResponse:
        """Save bid as draft"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Basic validation - job should exist and be open
            await self._validate_job_available_for_bidding(draft_data.job_id, contractor_id)

            # Validate no existing bid from this contractor
            await self._validate_no_existing_bid(draft_data.job_id, contractor_id)

            # Validate price data if provided
            if draft_data.price_min is not None and draft_data.price_max is not None:
                self._validate_bid_data(draft_data.price_min, draft_data.price_max)

            # Prepare draft record
            draft_record = draft_data.model_dump(exclude_none=True)
            draft_record["contractor_id"] = contractor_id
            draft_record["status"] = BidStatus.DRAFT.value

            # Create draft
            result = await self.supabase_client.table("bids").insert(draft_record).execute()
            if not result.data:
                raise DatabaseError("Failed to save your bid draft")

            draft = BidResponse(**result.data[0])

            logger.info(f"✅ Bid draft saved: {draft.id}")
            return draft

        except Exception as e:
            logger.error(f"Error saving bid draft - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to save your bid draft")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def update_bid(self, clerk_user_id: str, bid_id: str, bid_data: BidUpdate, is_draft_submit: bool = False) -> BidResponse:
        """Update existing bid"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Verify bid ownership and get current bid
            bid_result = await self.supabase_client.table("bids").select("*").eq("id", bid_id).eq("contractor_id", contractor_id).execute()
            if not bid_result.data:
                raise ValidationError("Bid not found or permission denied")

            current_bid = bid_result.data[0]

            # Validate bid can be updated
            if current_bid["status"] not in [BidStatus.DRAFT.value, BidStatus.PENDING.value]:
                raise ValidationError("Cannot edit bid in current status")

            # Validate job is still available if submitting draft
            if is_draft_submit:
                await self._validate_job_available_for_bidding(current_bid["job_id"], contractor_id)

            # Prepare update data
            update_data = bid_data.model_dump(exclude_none=True)

            # Validate price data if being updated
            price_min = update_data.get("price_min", current_bid["price_min"])
            price_max = update_data.get("price_max", current_bid["price_max"])
            if price_min is not None and price_max is not None:
                self._validate_bid_data(price_min, price_max)

            # Handle draft submission
            if is_draft_submit and current_bid["status"] == BidStatus.DRAFT.value:
                update_data["status"] = BidStatus.PENDING.value

            # Update bid
            result = await self.supabase_client.table("bids").update(update_data).eq("id", bid_id).execute()
            if not result.data:
                raise DatabaseError("Failed to update your bid")

            updated_bid = BidResponse(**result.data[0])

            logger.info(f"✅ Bid updated: {bid_id}")
            return updated_bid

        except Exception as e:
            logger.error(f"Error updating bid - {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to update your bid")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    async def delete_bid(self, clerk_user_id: str, bid_id: str) -> bool:
        """Delete bid"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Verify bid ownership and status
            bid_result = await self.supabase_client.table("bids").select("status").eq("id", bid_id).eq("contractor_id", contractor_id).execute()
            if not bid_result.data:
                raise ValidationError("Bid not found or permission denied")

            current_status = bid_result.data[0]["status"]
            if current_status not in [BidStatus.DRAFT.value, BidStatus.PENDING.value, BidStatus.DECLINED.value]:
                raise ValidationError("Cannot delete bid in current status")

            # Delete bid
            result = await self.supabase_client.table("bids").delete().eq("id", bid_id).execute()

            if result.data:
                logger.info(f"✅ Bid deleted: {bid_id}")
                return True
            else:
                raise DatabaseError("Failed to delete your bid")

        except Exception as e:
            logger.error(f"Error deleting bid: {str(e)}")
            if isinstance(e, (UserNotFoundError, DatabaseError, ValidationError)):
                raise e
            raise ServerError(f"Failed to delete your bid")

    # =====================================================================================================
    # BID READING OPERATIONS
    # =====================================================================================================

    async def get_bid_detail(self, clerk_user_id: str, bid_id: str) -> BidDetailResponse:
        """Get complete bid details with job context"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Get bid with job information
            result = (
                await self.supabase_client.table("bids")
                .select(
                    """
                    *, 
                    jobs(title, job_type, job_budget, city)
                """
                )
                .eq("id", bid_id)
                .eq("contractor_id", contractor_id)
                .execute()
            )

            if not result.data:
                raise ValidationError("Bid not found or permission denied")

            bid_data = result.data[0]
            job_info = bid_data.pop("jobs")

            # Prepare response with job context
            response_data = {
                **bid_data,
                "job_title": job_info["title"],
                "job_type": job_info["job_type"],
                "job_budget": job_info["job_budget"],
                "job_city": job_info["city"],
            }

            logger.info(f"✅ Retrieved bid detail: {bid_id}")
            return BidDetailResponse(**response_data)

        except Exception as e:
            logger.error(f"Error getting bid detail - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to fetch bid detail")
