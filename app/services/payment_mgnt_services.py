from supabase import AsyncClient
from app.configs.stripe_config import StripeConfig, PaymentConstants
from app.configs.app_settings import settings
from app.custom_error import DatabaseError, ValidationError
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    # ######################################################################################################################
    # Helper methods:
    # ######################################################################################################################

    async def _get_contractor_email(self, contractor_id: str) -> Optional[str]:
        """Get contractor email for receipt delivery"""
        try:
            # Get contractor always from contractor_profiles table
            profile_result = await self.supabase_client.table("contractor_profiles").select("email").eq("user_id", contractor_id).single().execute()

            if profile_result.data and profile_result.data.get("email"):
                return profile_result.data["email"]

            logger.warning(f"No email found for contractor {contractor_id}")
            return None

        except Exception as e:
            logger.warning(f"Error getting contractor email: {str(e)}")
            return None

    # ---------------------------------------------------------------------------------------------------------------------

    async def get_contractor_credits(self, contractor_id: str) -> int:
        """Get current credit balance for contractor"""
        try:
            # Get the latest credit balance from credit_transactions
            result = (
                await self.supabase_client.table("credit_transactions")
                .select("credits_balance_after")
                .eq("contractor_id", contractor_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["credits_balance_after"]
            return 0  # No credit history = 0 credits

        except Exception as e:
            logger.error(f"Error getting contractor credits: {str(e)}")
            raise DatabaseError("Failed to fetch credit balance")

    # ---------------------------------------------------------------------------------------------------------------------

    async def can_use_credit_for_bid(self, contractor_id: str) -> bool:
        """Check if contractor has credits available for bid"""
        # print("can_use_credit_for_bid called")
        credits = await self.get_contractor_credits(contractor_id)
        # print(f"Contractor {contractor_id} has {credits} credits")
        return credits > 0

    # ---------------------------------------------------------------------------------------------------------------------

    # the bid id here is always in draft status for per bid payments
    # so we just name it as draft_bid_id to avoid confusion

    async def create_checkout_session_for_draft_bid_payment(self, contractor_id: str, draft_bid_id: str) -> Dict[str, str]:
        """Create Stripe checkout session for draft bid payment with receipt email"""
        try:
            # GET CONTRACTOR EMAIL FOR RECEIPT
            contractor_email = await self._get_contractor_email(contractor_id)

            # Verify the draft bid exists and belongs to this contractor
            bid_result = (
                await self.supabase_client.table("bids")
                .select("*")
                .eq("id", draft_bid_id)
                .eq("contractor_id", contractor_id)
                .eq("status", "draft")
                .single()
                .execute()
            )

            if not bid_result.data:
                raise ValidationError("Draft bid not found or not owned by contractor")

            draft_bid = bid_result.data

            # Create success/cancel URLs that return to draft submission page
            base_url = settings.CLIENT_DOMAIN
            success_url = f"{base_url}/contractor-dashboard/payment-success?draft={draft_bid_id}"
            cancel_url = f"{base_url}/contractor-dashboard/post-bid?draft={draft_bid_id}&payment=cancelled"

            # Store ALL payment information in metadata for webhook processing
            metadata = {
                "product_name": "Bid Submission Fee",
                "item_type": "bid_payment",
                "contractor_id": contractor_id,
                "job_id": draft_bid["job_id"],  # Get job_id from the draft bid
                "bid_id": draft_bid_id,
                "amount_cad": str(PaymentConstants.BID_PAYMENT_AMOUNT_CAD / 100),  # Store as dollar amount
                "credits_purchased": "0",  # This is not a credit purchase
            }

            # 🎯 PASS EMAIL TO CREATE CHECKOUT SESSION
            session = StripeConfig.create_checkout_session(
                amount_cents=PaymentConstants.BID_PAYMENT_AMOUNT_CAD,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                customer_email=contractor_email,
            )

            print(f"Created Stripe session with receipt email: {session.id}")
            return {"session_id": session.id, "session_url": session.url}

        except Exception as e:
            logger.error(f"Error creating draft bid checkout session: {str(e)}")
            raise ValidationError(f"Failed to create payment session: {str(e)}")

    # ---------------------------------------------------------------------------------------------------------------------

    async def has_completed_payment_for_bid(self, contractor_id: str, bid_id: str) -> bool:
        """Check if contractor has completed payment for specific bid"""
        # print("has_completed_payment_for_bid called")
        try:
            # Look for successful payment transaction for this specific bid
            result = (
                await self.supabase_client.table("payment_transactions")
                .select("id")
                .eq("contractor_id", contractor_id)
                .eq("bid_id", bid_id)
                .eq("status", "succeeded")  # only count successful resulted payments
                .execute()
            )

            print(f"has bid Payment check result: {len(result.data) > 0}")

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error checking payment for bid: {str(e)}")
            return False

    # ---------------------------------------------------------------------------------------------------------------------

    async def create_checkout_session_for_credits_purchase(self, contractor_id: str) -> Dict[str, str]:
        """Create Stripe checkout session for credit purchase with receipt email"""
        try:
            # 🎯 GET CONTRACTOR EMAIL FOR RECEIPT
            contractor_email = await self._get_contractor_email(contractor_id)

            # Create success/cancel URLs that return to credits page
            base_url = settings.CLIENT_DOMAIN
            success_url = f"{base_url}/contractor-dashboard?section=your-credits&payment=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url}/contractor-dashboard?section=your-credits&payment=cancelled"

            # Store ALL payment information in metadata for webhook processing
            metadata = {
                "product_name": f"Credits Package ({PaymentConstants.CREDIT_PURCHASE_QUANTITY} credits)",
                "item_type": "credit_purchase",
                "contractor_id": contractor_id,
                "amount_cad": str(PaymentConstants.CREDIT_PURCHASE_AMOUNT_CAD / 100),  # Store as dollar amount
                "credits_purchased": str(PaymentConstants.CREDIT_PURCHASE_QUANTITY),
                # No job_id or bid_id for credit purchases
            }

            # 🎯 PASS EMAIL TO CREATE CHECKOUT SESSION
            session = StripeConfig.create_checkout_session(
                amount_cents=PaymentConstants.CREDIT_PURCHASE_AMOUNT_CAD,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                customer_email=contractor_email,
            )

            return {"session_id": session.id, "session_url": session.url}

        except Exception as e:
            logger.error(f"Error creating credit purchase checkout session: {str(e)}")
            raise ValidationError(f"Failed to create payment session: {str(e)}")

    # ---------------------------------------------------------------------------------------------------------------------

    async def use_credit_for_bid(self, contractor_id: str, job_id: str, bid_id: str):
        """Consume 1 credit for bid submission (free bid)"""
        try:
            # Get current balance
            current_credits = await self.get_contractor_credits(contractor_id)

            if current_credits <= 0:
                raise ValidationError("Insufficient credits")

            # Create credit usage transaction
            new_balance = current_credits - 1

            await self.supabase_client.table("credit_transactions").insert(
                {
                    "contractor_id": contractor_id,
                    "transaction_type": "usage",
                    "credits_change": -1,
                    "credits_balance_after": new_balance,
                    "bid_id": bid_id,
                    "description": f"Credit consumed for bid submission for job id: {job_id}",
                }
            ).execute()

            logger.info(f"✅ Credit consumed for bid {bid_id}, new balance: {new_balance}")

        except Exception as e:
            logger.error(f"Error using credit for bid: {str(e)}")
            raise DatabaseError(f"Failed to process credit usage: {str(e)}")
