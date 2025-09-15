import stripe
from supabase import AsyncClient
from app.configs.stripe_config import StripeConfig, PaymentConstants
from app.configs.app_settings import settings
from app.custom_error import DatabaseError, ValidationError
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

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
        credits = await self.get_contractor_credits(contractor_id)
        return credits > 0

    # ---------------------------------------------------------------------------------------------------------------------

    async def _create_payment_transaction_record(
        self,
        contractor_id: str,
        stripe_session_id: str,
        item_type: str,
        amount_cad: float,
        job_id: Optional[str] = None,
        bid_id: Optional[str] = None,
        credits_purchased: int = 0,
    ):
        """Create payment transaction record in database"""
        payment_data = {
            "contractor_id": contractor_id,
            "stripe_session_id": stripe_session_id,
            "item_type": item_type,
            "amount_cad": amount_cad,
            "currency": PaymentConstants.CURRENCY,
            "status": "pending",
            "credits_purchased": credits_purchased,
        }

        if job_id:
            payment_data["job_id"] = job_id
        if bid_id:
            payment_data["bid_id"] = bid_id

        result = await self.supabase_client.table("payment_transactions").insert(payment_data).execute()

        if not result.data:
            raise DatabaseError("Failed to create payment transaction record")

        return result.data[0]

    # ---------------------------------------------------------------------------------------------------------------------

    # the bid id here is always in draft status for per bid payments
    # so we just name it as draft_bid_id to avoid confusion
    async def create_checkout_session_for_draft_bid_payment(self, contractor_id: str, draft_bid_id: str) -> Dict[str, str]:
        """Create Stripe checkout session for draft bid payment"""
        try:
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
            # These will be used inside the StripeConfig.create_checkout_session later
            base_url = settings.CLIENT_DOMAIN
            success_url = f"{base_url}/contractor-dashboard/payment-success?draft={draft_bid_id}"
            cancel_url = f"{base_url}/contractor-dashboard/post-bid?draft={draft_bid_id}&payment=cancelled"

            # Metadata to track this payment
            # This will be used inside the StripeConfig.create_checkout_session later
            metadata = {
                "product_name": "Bid Submission Fee",  # this will display in Stripe session checkout redirect page
                "item_type": "bid_payment",
                "contractor_id": contractor_id,
                "job_id": draft_bid["job_id"],
                "bid_id": draft_bid_id,
                "bid_title": draft_bid["title"],
            }

            # Create Stripe checkout session (THIS IS THE CORE FUNCTIONALITY AND IS FULLY HANDLED BY STRIPE)
            # it will return a session id and url to redirect to the checkout page (which is fully hosted by Stripe)
            session = StripeConfig.create_checkout_session(
                amount_cents=PaymentConstants.BID_PAYMENT_AMOUNT_CAD, success_url=success_url, cancel_url=cancel_url, metadata=metadata
            )

            # Save pending payment record
            await self._create_payment_transaction_record(
                contractor_id=contractor_id,
                stripe_session_id=session.id,
                item_type="bid_payment",
                amount_cad=PaymentConstants.BID_PAYMENT_AMOUNT_CAD / 100,  # Convert cents to dollars
                job_id=draft_bid["job_id"],
                bid_id=draft_bid_id,
                credits_purchased=0,
            )

            return {"session_id": session.id, "session_url": session.url}

        except Exception as e:
            logger.error(f"Error creating draft bid checkout session: {str(e)}")
            raise ValidationError(f"Failed to create payment session: {str(e)}")

    # ---------------------------------------------------------------------------------------------------------------------

    async def has_completed_payment_for_bid(self, contractor_id: str, bid_id: str) -> bool:
        """Check if contractor has completed payment for specific bid"""
        print("has_completed_payment_for_bid called")
        try:
            # Look for successful payment transaction for this specific bid
            result = (
                await self.supabase_client.table("payment_transactions")
                .select("id")
                .eq("contractor_id", contractor_id)
                .eq("bid_id", bid_id)
                .eq("status", "succeeded")
                .execute()
            )

            print(f"Payment check result: {len(result.data) > 0}")

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error checking payment for bid: {str(e)}")
            return False

    # ---------------------------------------------------------------------------------------------------------------------

    async def create_checkout_session_for_credits_purchase(self, contractor_id: str) -> Dict[str, str]:
        """Create Stripe checkout session for credit purchase"""
        try:
            # Create success/cancel URLs that return to credits page
            base_url = settings.CLIENT_DOMAIN
            success_url = f"{base_url}/contractor-dashboard?section=your-credits&payment=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url}/contractor-dashboard?section=your-credits&payment=cancelled"

            # Metadata to track this payment
            metadata = {
                "product_name": f"Credits Package ({PaymentConstants.CREDIT_PURCHASE_QUANTITY} credits)",
                "item_type": "credit_purchase",
                "contractor_id": contractor_id,
                "credits_quantity": str(PaymentConstants.CREDIT_PURCHASE_QUANTITY),
            }

            # Create Stripe checkout session
            session = StripeConfig.create_checkout_session(
                amount_cents=PaymentConstants.CREDIT_PURCHASE_AMOUNT_CAD, success_url=success_url, cancel_url=cancel_url, metadata=metadata
            )

            # Save pending payment record
            await self._create_payment_transaction_record(
                contractor_id=contractor_id,
                stripe_session_id=session.id,
                item_type="credit_purchase",
                amount_cad=PaymentConstants.CREDIT_PURCHASE_AMOUNT_CAD / 100,  # Convert cents to dollars
                credits_purchased=PaymentConstants.CREDIT_PURCHASE_QUANTITY,
            )

            return {"session_id": session.id, "session_url": session.url}

        except Exception as e:
            logger.error(f"Error creating credit checkout session: {str(e)}")
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
                    "description": f"Bid submission for job id: {job_id}",
                }
            ).execute()

            logger.info(f"✅ Credit consumed for bid {bid_id}, new balance: {new_balance}")

        except Exception as e:
            logger.error(f"Error using credit for bid: {str(e)}")
            raise DatabaseError(f"Failed to process credit usage: {str(e)}")

    # ######################################################################################################################
    # Post-payment processing (to be called by webhook handler)
    # ######################################################################################################################

    async def process_successful_payment(self, session_id: str):
        """Process successful payment (called by webhook) - we'll implement this next"""
        # Implementation coming in next step when we build webhooks
        pass
