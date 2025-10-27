from fastapi import APIRouter, Request, Depends, HTTPException
from supabase import AsyncClient
import stripe
import json
import logging
from app.utils.supabase_client_handlers import get_supabase_client
from app.services.payment_credits_services import PaymentService
from app.models.stripe_webhook_models import StripeWebhookEventResponse
from app.configs.app_settings import settings
from app.custom_error import WebhookError

stripe_webhook_router = APIRouter(prefix="/stripe", tags=["Webhooks"])
logger = logging.getLogger(__name__)


async def get_payment_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> PaymentService:
    """Dependency to get PaymentService instance"""
    return PaymentService(supabase_client)


# ################################################################################################################################


@stripe_webhook_router.post("/webhooks", response_model=StripeWebhookEventResponse)
async def stripe_webhook_handler(request: Request, payment_service: PaymentService = Depends(get_payment_service)):
    """Handle Stripe webhook events"""
    try:
        # Get the raw body and signature
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise WebhookError("Missing stripe-signature header")

        # Verify webhook signature (we'll add the webhook secret to settings)
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except ValueError:
            raise WebhookError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise WebhookError("Invalid signature")

        # Log the event for debugging
        logger.info(f"🔔 Received Stripe webhook: {event['type']}")

        # Handle different event types
        event_type = event["type"]

        if event_type == "checkout.session.completed":
            result = await _handle_payment_success(event["data"]["object"], payment_service)
            return StripeWebhookEventResponse(
                status="success", message=f"Payment processed successfully: {result}", event_type=event_type, processed=True
            )

        elif event_type == "payment_intent.payment_failed":
            result = await _handle_payment_failure(event["data"]["object"], payment_service)
            return StripeWebhookEventResponse(status="success", message=f"Payment failure recorded: {result}", event_type=event_type, processed=True)

        else:
            # Log unhandled events but don't error
            logger.info(f"⚠️ Unhandled webhook event type: {event_type}")
            return StripeWebhookEventResponse(
                status="success", message=f"Event type {event_type} not handled", event_type=event_type, processed=False
            )

    except WebhookError as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


#################################################################################################################################
# helper functions for handling specific event types


async def _handle_payment_success(checkout_session, payment_service: PaymentService):
    """Handle successful payment from checkout.session.completed"""
    try:
        # Extract metadata from the checkout session
        metadata = checkout_session.get("metadata", {})
        session_id = checkout_session["id"]
        payment_intent_id = checkout_session.get("payment_intent")

        # Validate required metadata
        required_fields = ["item_type", "contractor_id", "amount_cad"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required metadata field: {field}")

        # Create payment transaction record
        payment_data = {
            "contractor_id": metadata["contractor_id"],
            "stripe_session_id": session_id,
            "stripe_payment_intent_id": payment_intent_id,
            "item_type": metadata["item_type"],
            "amount_cad": float(metadata["amount_cad"]),
            "currency": "CAD",
            "status": "succeeded",
            "credits_purchased": int(metadata.get("credits_purchased", 0)),
        }

        # Add job/bid info if this is a bid payment
        if metadata["item_type"] == "bid_payment":
            payment_data["job_id"] = metadata.get("job_id")
            payment_data["bid_id"] = metadata.get("bid_id")

        # Insert payment record
        payment_result = await payment_service.supabase_client.table("payment_transactions").insert(payment_data).execute()

        if not payment_result.data:
            raise ValueError("Failed to create payment record")

        payment_record = payment_result.data[0]

        # Handle credit purchase - add credits to contractor
        if metadata["item_type"] == "credit_purchase":
            await _process_credit_purchase(payment_service, metadata["contractor_id"], payment_record["id"], int(metadata["credits_purchased"]))

        logger.info(f"✅ Payment success processed: {session_id}")
        return f"Payment {session_id} recorded successfully"

    except Exception as e:
        logger.error(f"❌ Error processing payment success: {str(e)}")
        raise


async def _process_credit_purchase(payment_service: PaymentService, contractor_id: str, payment_transaction_id: str, credits_purchased: int):
    """Add purchased credits to contractor account"""
    try:
        # Get current credit balance
        current_credits = await payment_service.get_contractor_credits(contractor_id)
        new_balance = current_credits + credits_purchased

        # Create credit transaction record
        credit_data = {
            "contractor_id": contractor_id,
            "transaction_type": "purchase",
            "credits_change": credits_purchased,
            "credits_balance_after": new_balance,
            "payment_transaction_id": payment_transaction_id,
            "description": f"Credit purchase - {credits_purchased} credits added",
        }

        await payment_service.supabase_client.table("credit_transactions").insert(credit_data).execute()

        logger.info(f"💰 Added {credits_purchased} credits to contractor {contractor_id}, new balance: {new_balance}")

    except Exception as e:
        logger.error(f"❌ Error processing credit purchase: {str(e)}")
        raise


async def _handle_payment_failure(payment_intent, payment_service: PaymentService):
    """Handle failed payment from payment_intent.payment_failed"""
    try:
        # Get the checkout session that created this payment intent
        sessions = stripe.checkout.Session.list(payment_intent=payment_intent["id"])

        if not sessions.data:
            logger.warning(f"No checkout session found for failed payment intent: {payment_intent['id']}")
            return "No associated checkout session found"

        checkout_session = sessions.data[0]
        metadata = checkout_session.get("metadata", {})

        # Record the failed payment
        if metadata:
            payment_data = {
                "contractor_id": metadata.get("contractor_id"),
                "stripe_session_id": checkout_session["id"],
                "stripe_payment_intent_id": payment_intent["id"],
                "item_type": metadata.get("item_type", "unknown"),
                "amount_cad": float(metadata.get("amount_cad", 0)),
                "currency": "CAD",
                "status": "failed",
                "credits_purchased": int(metadata.get("credits_purchased", 0)),
            }

            if metadata.get("job_id"):
                payment_data["job_id"] = metadata["job_id"]
            if metadata.get("bid_id"):
                payment_data["bid_id"] = metadata["bid_id"]

            await payment_service.supabase_client.table("payment_transactions").insert(payment_data).execute()

        logger.info(f"💥 Payment failure recorded: {payment_intent['id']}")
        return f"Failed payment {payment_intent['id']} recorded"

    except Exception as e:
        logger.error(f"❌ Error processing payment failure: {str(e)}")
        raise
