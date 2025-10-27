from supabase import AsyncClient
from app.models.admin_credit_models import (
    JobBidInquiryResponse,
    ContractorContactResponse,
    BuyerContactResponse,
    AddCreditResponse,
)
from app.custom_error import ValidationError, ServerError
import logging

logger = logging.getLogger(__name__)


class AdminCreditService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    # =====================================
    # CREDIT INQUIRY OPERATIONS
    # =====================================

    async def get_job_bid_inquiry_details(self, job_id: str, bid_id: str) -> JobBidInquiryResponse:
        """Get complete job and bid details with all contact info for verification"""
        try:
            # Fetch job details
            job_result = await self.supabase_client.table("jobs").select("*").eq("id", job_id).single().execute()

            if not job_result.data:
                raise ValidationError("Job not found")

            job = job_result.data

            # Fetch bid details and verify it belongs to this job
            bid_result = await self.supabase_client.table("bids").select("*").eq("id", bid_id).eq("job_id", job_id).single().execute()

            if not bid_result.data:
                raise ValidationError("Bid not found or does not belong to this job")

            bid = bid_result.data

            # ----------------------------------------------------------------------

            contractor_id = bid["contractor_id"]
            buyer_id = job["buyer_id"]

            # Fetch buyer contact info
            buyer_contact_result = (
                await self.supabase_client.table("buyer_profiles").select("contact_email, phone_number").eq("user_id", buyer_id).single().execute()
            )

            if not buyer_contact_result.data:
                raise ValidationError("Buyer contact information not found")

            buyer_contact = BuyerContactResponse(**buyer_contact_result.data)

            # Fetch contractor contact info
            contractor_contact_result = (
                await self.supabase_client.table("contractor_profiles")
                .select("contractor_name, email, phone")
                .eq("user_id", contractor_id)
                .single()
                .execute()
            )

            if not contractor_contact_result.data:
                raise ValidationError("Contractor contact information not found")

            contractor_contact = ContractorContactResponse(**contractor_contact_result.data)

            # Get contractor's current credit balance
            credit_result = (
                await self.supabase_client.table("credit_transactions")
                .select("credits_balance_after")
                .eq("contractor_id", contractor_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            current_credits = credit_result.data[0]["credits_balance_after"] if credit_result.data else 0

            # Build complete inquiry response
            return JobBidInquiryResponse(
                job_id=job["id"],
                job_title=job["title"],
                job_type=job["job_type"],
                job_budget=job["job_budget"],
                job_status=job["status"],
                job_city=job["city"],
                job_location_address=job["location_address"],
                job_description=job["description"],
                job_other_requirements=job.get("other_requirements"),
                job_created_at=job["created_at"],
                bid_id=bid["id"],
                bid_title=bid["title"],
                bid_price_min=bid["price_min"],
                bid_price_max=bid["price_max"],
                bid_timeline_estimate=bid["timeline_estimate"],
                bid_status=bid["status"],
                bid_created_at=bid["created_at"],
                contractor_id=contractor_id,
                contractor_contact=contractor_contact,
                buyer_id=buyer_id,
                buyer_contact=buyer_contact,
                contractor_current_credits=current_credits,
            )

        except Exception as e:
            logger.error(f"Error fetching job/bid inquiry details: {str(e)}")
            if isinstance(e, ValidationError):
                raise e
            raise ServerError(f"Failed to fetch inquiry details: {str(e)}")

    # =====================================
    # CREDIT OPERATIONS
    # =====================================

    async def add_credit_to_contractor(self, contractor_id: str) -> AddCreditResponse:
        """Add 1 credit to contractor as compensation"""
        try:
            # Verify contractor exists
            contractor_result = (
                await self.supabase_client.table("users").select("id").eq("id", contractor_id).eq("user_type", "contractor").single().execute()
            )

            if not contractor_result.data:
                raise ValidationError("Contractor not found")

            # Get current credit balance
            credit_result = (
                await self.supabase_client.table("credit_transactions")
                .select("credits_balance_after")
                .eq("contractor_id", contractor_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            current_credits = credit_result.data[0]["credits_balance_after"] if credit_result.data else 0
            new_balance = current_credits + 1

            # Create credit refund transaction
            await self.supabase_client.table("credit_transactions").insert(
                {
                    "contractor_id": contractor_id,
                    "transaction_type": "refund",
                    "credits_change": 1,
                    "credits_balance_after": new_balance,
                    "description": f"Admin refund - 1 credit added by admin",
                }
            ).execute()

            logger.info(f"✅ Added 1 credit to contractor {contractor_id}. New balance: {new_balance}")

            return AddCreditResponse(
                success=True,
                contractor_id=contractor_id,
                credits_added=1,
                new_balance=new_balance,
                message=f"Successfully added 1 credit. New balance: {new_balance}",
            )

        except Exception as e:
            logger.error(f"Error adding credit to contractor: {str(e)}")
            if isinstance(e, ValidationError):
                raise e
            raise ServerError(f"Failed to add credit: {str(e)}")
