from pydantic import BaseModel
from typing import Optional, Dict, Any


class StripeWebhookEventResponse(BaseModel):
    """Response model for webhook processing"""

    status: str  # "success" or "error"
    message: str
    event_type: Optional[str] = None
    processed: bool = False


class StripeWebhookPayload(BaseModel):
    """Basic structure for incoming Stripe webhook data"""

    # We'll parse the raw webhook payload in the route handler
    # This is just for documentation/validation if needed later
    pass
