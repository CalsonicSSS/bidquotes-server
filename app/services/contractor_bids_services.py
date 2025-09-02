from supabase import AsyncClient
from app.models.bid_models import BidCardResponse, BidCreate, BidUpdate, BidDraftCreate, BidResponse, BidDetailResponse, BidStatus
from app.custom_error import UserNotFoundError, DatabaseError, ServerError, ValidationError
from typing import List, Optional
import logging

from app.models.job_models import JobStatus

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
            raise ValidationError("You have already submitted a bid or saved a draft for this job")

    # --------------------------------------------------------------------------------------------------------------------------------------------

    def _clean_price_string(self, price_str: str) -> float:
        """Convert formatted price string to float"""
        if not price_str:
            return 0.0
        # Remove currency symbols, commas, and spaces, then convert to float
        cleaned = price_str.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            raise ValidationError(f"Invalid price format: {price_str}")

    def _validate_bid_data(self, price_min: str, price_max: str) -> None:
        """Validate bid data with formatted currency handling"""
        try:
            min_price = self._clean_price_string(price_min)
            max_price = self._clean_price_string(price_max)

            if min_price < 0 or max_price < 0:
                raise ValidationError("Prices must be positive")

            if min_price > max_price:
                raise ValidationError("Minimum price cannot be greater than maximum price")

        except ValueError as e:
            raise ValidationError("Invalid price format provided")

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

            # Perform Stripe payment flow (we will do this later)

            # Once this bid is fully submitted + payment processed, we need to check if it this is the full bid as this is the 5th one for this job
            # if it is, we will need to update the job status to CLOSED (VERY IMPORTANT)
            job_bids = (
                await self.supabase_client.table("bids").select("id").eq("job_id", bid_data.job_id).eq("status", BidStatus.PENDING.value).execute()
            )
            if len(job_bids.data) == 5:
                await self.supabase_client.table("jobs").update({"status": JobStatus.CLOSED.value}).eq("id", bid_data.job_id).execute()

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

            # Prepare update data
            update_data = bid_data.model_dump(exclude_none=True)

            # Validate price data if being updated
            price_min = update_data.get("price_min", current_bid["price_min"])
            price_max = update_data.get("price_max", current_bid["price_max"])
            if price_min is not None and price_max is not None:
                self._validate_bid_data(price_min, price_max)

            # Handle draft submission
            if is_draft_submit and current_bid["status"] == BidStatus.DRAFT.value:
                # Basic validation - job should exist and be open
                await self._validate_job_available_for_bidding(current_bid["job_id"], contractor_id)

                # Validate no existing bid from this contractor
                # await self._validate_no_existing_bid(current_bid["job_id"], contractor_id)

                update_data["status"] = BidStatus.PENDING.value

                # Perform Stripe payment flow (we will do this later)

                # Once this bid is fully submitted + payment processed, we need to check if it this is the full bid as this is the 5th one for this job
                # if it is, we will need to update the job status to CLOSED (VERY IMPORTANT)
                job_bids = (
                    await self.supabase_client.table("bids")
                    .select("*")
                    .eq("job_id", current_bid["job_id"])
                    .eq("status", BidStatus.PENDING.value)
                    .execute()
                )
                if len(job_bids.data) >= 5:
                    await self.supabase_client.table("jobs").update({"status": JobStatus.CLOSED.value}).eq("id", current_bid["job_id"]).execute()

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

    async def get_contractor_bid_cards(self, clerk_user_id: str, status_filter: Optional[str] = None) -> List[BidCardResponse]:
        """Get bid cards for contractor dashboard"""
        try:
            contractor_id = await self._get_user_id(clerk_user_id)

            # Build query to get bids with job information
            query = (
                self.supabase_client.table("bids")
                .select(
                    """
                    id, job_id, title, status, created_at, updated_at,
                    jobs(title, job_type, city)
                    """
                )
                .eq("contractor_id", contractor_id)
            )

            if status_filter:
                query = query.eq("status", status_filter)

            # Order by latest first
            query = query.order("created_at", desc=True)
            result = await query.execute()

            bid_cards = []
            for bid_data in result.data:
                job_info = bid_data.pop("jobs")  # Extract job info

                # Create bid card with job context
                bid_card = BidCardResponse(
                    id=bid_data["id"],
                    job_id=bid_data["job_id"],
                    title=bid_data["title"] or "Untitled Bid",
                    status=bid_data["status"],
                    created_at=bid_data["created_at"],
                    updated_at=bid_data["updated_at"],
                    job_title=job_info["title"],
                    job_type=job_info["job_type"],
                    job_city=job_info["city"],
                )
                bid_cards.append(bid_card)

            logger.info(f"✅ Retrieved {len(bid_cards)} bid cards for contractor")
            return bid_cards

        except Exception as e:
            logger.error(f"Error getting contractor bid cards - {str(e)}")
            if isinstance(e, UserNotFoundError):
                raise e
            raise ServerError(f"Failed to fetch bids")

    # ----------------------------------------------------------------------------------------------------------------------------------------------------------

    async def get_bid_detail(self, clerk_user_id: str, bid_id: str) -> BidDetailResponse:
        """Get complete bid details with job context and buyer contact info (if confirmed)"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Get bid details with job context
            bid_result = (
                await self.supabase_client.table("bids")
                .select(
                    """
                *,
                jobs!inner(
                    buyer_id,
                    title,
                    job_type,
                    job_budget,
                    city
                )
            """
                )
                .eq("id", bid_id)
                .eq("contractor_id", user_id)
                .execute()
            )

            if not bid_result.data:
                raise ValidationError("Bid not found or permission denied")

            bid_data = bid_result.data[0]
            job_data = bid_data["jobs"]

            # Initialize buyer contact info as None
            buyer_contact_email = None
            buyer_contact_phone = None

            # Only reveal buyer contact info if bid is confirmed
            if bid_data["status"] == "confirmed":
                contact_result = (
                    await self.supabase_client.table("buyer_profiles")
                    .select("contact_email, phone_number")
                    .eq("user_id", job_data["buyer_id"])
                    .execute()
                )
                if contact_result.data:
                    contact_data = contact_result.data[0]
                    buyer_contact_email = contact_data["contact_email"]
                    buyer_contact_phone = contact_data["phone_number"]

            # Create bid detail response
            bid_detail = BidDetailResponse(
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
                # Buyer contact (only if confirmed)
                buyer_contact_email=buyer_contact_email,
                buyer_contact_phone=buyer_contact_phone,
            )

            logger.info(f"✅ Bid detail retrieved for contractor - bid: {bid_id}")
            return bid_detail

        except Exception as e:
            logger.error(f"Error getting bid detail - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to get bid details")

    # =====================================================================================================
    # BID DECLINE AND CONFIRM OPERATIONS
    # =====================================================================================================

    async def decline_selected_bid(self, clerk_user_id: str, bid_id: str) -> bool:
        """Decline a selected bid and update job status accordingly"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify contractor owns this bid and it's selected
            bid_result = await self.supabase_client.table("bids").select("*").eq("id", bid_id).eq("contractor_id", user_id).execute()
            if not bid_result.data:
                raise ValidationError("Bid not found or permission denied")

            bid_data = bid_result.data[0]

            # Check if bid is in selected status
            if bid_data["status"] != "selected" or not bid_data["is_selected"]:
                raise ValidationError("This bid is not currently selected")

            job_id = bid_data["job_id"]

            # Start transaction-like operations
            # 1. Update bid status to declined and unselect it
            await self.supabase_client.table("bids").update({"status": "declined", "is_selected": False}).eq("id", bid_id).execute()

            # 2. Count remaining active bids for the job (excluding declined and draft)
            remaining_bids_result = (
                await self.supabase_client.table("bids").select("id").eq("job_id", job_id).neq("status", "draft").neq("status", "declined").execute()
            )
            remaining_bid_count = len(remaining_bids_result.data) if remaining_bids_result.data else 0

            # 3. Update job status back to open (declined bids don't count toward bid limit)
            new_job_status = "open"  # Always goes back to open since declined bid is removed from count

            await self.supabase_client.table("jobs").update({"status": new_job_status}).eq("id", job_id).execute()

            logger.info(f"✅ Bid declined successfully - bid: {bid_id}, job: {job_id}, remaining bids: {remaining_bid_count}")

            # TODO: Send email notification to buyer (placeholder for now)
            # await self._send_bid_decline_notification(job_id, bid_id)

            return True

        except Exception as e:
            logger.error(f"Error declining selected bid - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to decline bid selection")

    # ---------------------------------------------------------------------------------------------------------------------------------------

    async def confirm_selected_bid(self, clerk_user_id: str, bid_id: str) -> bool:
        """Confirm a selected bid (skip payment for now) and complete the job"""
        try:
            user_id = await self._get_user_id(clerk_user_id)

            # Verify contractor owns this bid and it's selected
            bid_result = await self.supabase_client.table("bids").select("*").eq("id", bid_id).eq("contractor_id", user_id).execute()
            if not bid_result.data:
                raise ValidationError("Bid not found or permission denied")

            bid_data = bid_result.data[0]

            # Check if bid is in selected status
            if bid_data["status"] != "selected" or not bid_data["is_selected"]:
                raise ValidationError("This bid is not currently selected")

            job_id = bid_data["job_id"]

            # Start transaction-like operations
            # 1. Update this bid to confirmed status
            await self.supabase_client.table("bids").update(
                {
                    "status": "confirmed"
                    # Keep is_selected as True since this is the confirmed bid
                }
            ).eq("id", bid_id).execute()

            # 2. Update job status to confirmed
            await self.supabase_client.table("jobs").update({"status": "confirmed"}).eq("id", job_id).execute()

            # 3. Decline all other bids for this job
            await self.supabase_client.table("bids").update({"status": "declined", "is_selected": False}).eq("job_id", job_id).neq(
                "id", bid_id
            ).execute()

            logger.info(f"✅ Bid confirmed successfully - bid: {bid_id}, job: {job_id}")

            # TODO: Send email notifications (placeholder for now)
            # await self._send_bid_confirmation_notification(job_id, bid_id)
            # await self._send_declined_bid_notifications(job_id, bid_id)

            return True

        except Exception as e:
            logger.error(f"Error confirming selected bid - {str(e)}")
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise ServerError(f"Failed to confirm bid selection")
