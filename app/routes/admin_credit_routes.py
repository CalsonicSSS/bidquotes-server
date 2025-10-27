from fastapi import APIRouter, Depends, Query
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.services.admin_credit_services import AdminCreditService
from app.models.admin_credit_models import JobBidInquiryResponse, AddCreditRequest, AddCreditResponse

admin_credit_router = APIRouter(prefix="/admin/credits", tags=["Admin"])


async def get_admin_credit_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> AdminCreditService:
    """Dependency to get AdminCreditService instance"""
    return AdminCreditService(supabase_client)


# =====================================
# CREDIT MANAGEMENT ENDPOINTS
# =====================================


@admin_credit_router.get("/inquiry", response_model=JobBidInquiryResponse)
async def get_job_bid_inquiry(
    job_id: str = Query(..., description="Job ID from contractor"),
    bid_id: str = Query(..., description="Bid ID from contractor"),
    admin_service: AdminCreditService = Depends(get_admin_credit_service),
):
    """Get complete job and bid details with contacts for verification"""
    return await admin_service.get_job_bid_inquiry_details(job_id, bid_id)


# --------------------------------------------------------------


@admin_credit_router.post("/add", response_model=AddCreditResponse)
async def add_credit_to_contractor(
    request: AddCreditRequest,
    admin_service: AdminCreditService = Depends(get_admin_credit_service),
):
    """Add 1 credit to contractor as refund/compensation"""
    return await admin_service.add_credit_to_contractor(
        contractor_id=request.contractor_id,
    )
