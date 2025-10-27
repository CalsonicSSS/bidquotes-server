from fastapi import APIRouter, Depends
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.payment_credits_services import PaymentService
from app.models.payment_models import DraftBidPaymentRequest, CheckoutSessionResponse, CreditBalanceResponse

payments_credits_router = APIRouter(prefix="/payments", tags=["Payments"])


async def get_payment_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> PaymentService:
    """Dependency to get PaymentService instance"""
    return PaymentService(supabase_client)


async def get_contractor_user_id(clerk_user_id: str, payment_service: PaymentService) -> str:
    """Get contractor user_id from clerk_user_id"""
    result = (
        await payment_service.supabase_client.table("users")
        .select("id")
        .eq("clerk_user_id", clerk_user_id)
        .eq("user_type", "contractor")
        .single()
        .execute()
    )

    if not result.data:
        raise ValueError("Contractor not found")

    return result.data["id"]


#########################################################################################################################


@payments_credits_router.post("/create-draft-bid-payment", response_model=CheckoutSessionResponse)
async def create_draft_bid_payment(
    request: DraftBidPaymentRequest,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Create Stripe checkout session for draft bid payment"""

    contractor_id = await get_contractor_user_id(clerk_user_id, payment_service)

    result = await payment_service.create_checkout_session_for_draft_bid_payment(contractor_id=contractor_id, draft_bid_id=request.draft_bid_id)

    return CheckoutSessionResponse(**result)


# ---------------------------------------------------------------------------------------------------------------------


@payments_credits_router.get("/credits", response_model=CreditBalanceResponse)
async def get_contractor_credits(
    clerk_user_id: str = Depends(get_current_clerk_user_id), payment_service: PaymentService = Depends(get_payment_service)
):
    """Get contractor's current credit balance"""

    contractor_id = await get_contractor_user_id(clerk_user_id, payment_service)
    credits = await payment_service.get_contractor_credits(contractor_id)

    return CreditBalanceResponse(credits=credits)


# ---------------------------------------------------------------------------------------------------------------------


@payments_credits_router.post("/create-credit-purchase", response_model=CheckoutSessionResponse)
async def create_credit_purchase(
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Create Stripe checkout session for credit purchase ($700 for 20 credits)"""

    contractor_id = await get_contractor_user_id(clerk_user_id, payment_service)

    result = await payment_service.create_checkout_session_for_credits_purchase(contractor_id=contractor_id)

    return CheckoutSessionResponse(**result)
