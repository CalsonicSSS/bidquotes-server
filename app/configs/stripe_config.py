import stripe
import os
from typing import Optional
from app.configs.app_settings import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


# Payment constants for your business model
class PaymentConstants:
    BID_PAYMENT_AMOUNT_CAD = 7000  # for testing now (7000) $70.00 CAD in cents
    CREDIT_PURCHASE_AMOUNT_CAD = 70000  # for testing now (70000) $700.00 CAD in cents
    CREDIT_PURCHASE_QUANTITY = 20  # Credits received per purchase
    CAD_CURRENCY = "cad"

    # Success/Cancel URLs (we'll use these later)
    DOMAIN = os.getenv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:3000")


class StripeConfig:
    """Simple wrapper for common Stripe operations"""

    @staticmethod
    def create_checkout_session(
        amount_cents: int,
        currency: str = PaymentConstants.CAD_CURRENCY,
        success_url: str = "",
        cancel_url: str = "",
        metadata: Optional[dict] = None,
        customer_email: Optional[str] = None,  # Add customer email parameter
    ) -> stripe.checkout.Session:
        """Create a Stripe checkout session with receipt emails enabled"""

        session_config = {
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {
                            "name": metadata.get("product_name", "Bidquotes Payment"),
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
            "payment_intent_data": {"receipt_email": customer_email} if customer_email else {},  # This enables automatic receipt emails!
            # Optional: Pre-fill email in checkout form
            "customer_email": customer_email if customer_email else None,
        }

        # Only add payment_intent_data if customer_email is provided
        if not customer_email:
            session_config.pop("payment_intent_data", None)

        return stripe.checkout.Session.create(**session_config)

    @staticmethod
    def retrieve_session(session_id: str) -> stripe.checkout.Session:
        """Retrieve a checkout session by ID"""
        return stripe.checkout.Session.retrieve(session_id)

    @staticmethod
    def retrieve_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
        """Retrieve a payment intent by ID"""
        return stripe.PaymentIntent.retrieve(payment_intent_id)
