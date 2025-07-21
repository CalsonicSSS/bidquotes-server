from fastapi import APIRouter, Request, Depends
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.services.clerk_webhook_services import ClerkWebhookService
from app.models.clerk_webhook_models import ClerkWebhookEvent
from app.configs.app_settings import settings
from app.custom_error import WebhookError
from svix.webhooks import Webhook, WebhookVerificationError
import logging

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/clerk", tags=["Webhooks"])


async def get_clerk_webhook_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> ClerkWebhookService:
    """Dependency to get ClerkWebhookService instance"""
    return ClerkWebhookService(supabase_client)


@webhook_router.post("/webhooks")
async def clerk_webhook(request: Request, webhook_service: ClerkWebhookService = Depends(get_clerk_webhook_service)):
    """Handle Clerk webhook events"""
    print("Received Clerk webhook event")

    try:
        # Get the raw body and headers
        body = await request.body()
        headers = request.headers

        # Verify the webhook signature
        webhook = Webhook(settings.CLERK_WEBHOOK_SECRET)

        try:
            # This will raise an exception if verification fails
            payload = webhook.verify(body, headers)

        except WebhookVerificationError as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            raise WebhookError("Invalid webhook signature")

        # Parse the event
        event = ClerkWebhookEvent(**payload)

        # Handle different event types
        if event.type == "user.created":
            await webhook_service.handle_user_created(event)
        elif event.type == "user.updated":
            await webhook_service.handle_user_updated(event)
        elif event.type == "user.deleted":
            await webhook_service.handle_user_deleted(event)
        else:
            logger.info(f"Unhandled webhook event type: {event.type}")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise WebhookError("Webhook processing failed")
