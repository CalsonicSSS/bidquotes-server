# Create app/routes/bid_routes.py

from fastapi import APIRouter, Depends, Form, Query, HTTPException
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.bid_services import BidService
from app.models.bid_models import BidCreate, BidUpdate, BidDraftCreate, BidResponse, BidDetailResponse
from typing import Optional

bid_router = APIRouter(prefix="/bids", tags=["Bids"])


async def get_bid_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> BidService:
    """Dependency to get BidService instance"""
    return BidService(supabase_client)


########################################################################################################################


@bid_router.post("", response_model=BidResponse)
async def create_bid(
    job_id: str = Form(...),
    title: str = Form(...),
    price_min: float = Form(...),
    price_max: float = Form(...),
    timeline_estimate: str = Form(...),
    work_description: str = Form(...),
    additional_notes: str = Form(None),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    bid_service: BidService = Depends(get_bid_service),
):
    """Create new bid submission"""

    # Create bid data
    bid_data = BidCreate(
        job_id=job_id,
        title=title,
        price_min=price_min,
        price_max=price_max,
        timeline_estimate=timeline_estimate,
        work_description=work_description,
        additional_notes=additional_notes,
    )

    return await bid_service.create_bid(clerk_user_id, bid_data)


# ------------------------------------------------------------------------------------------------------------------------


@bid_router.post("/drafts", response_model=BidResponse)
async def save_bid_draft(
    job_id: str = Form(...),
    title: str = Form(None),
    price_min: Optional[float] = Form(None),
    price_max: Optional[float] = Form(None),
    timeline_estimate: str = Form(None),
    work_description: str = Form(None),
    additional_notes: str = Form(None),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    bid_service: BidService = Depends(get_bid_service),
):
    """Save bid as draft"""

    # Create draft data
    draft_data = BidDraftCreate(
        job_id=job_id,
        title=title,
        price_min=price_min,
        price_max=price_max,
        timeline_estimate=timeline_estimate,
        work_description=work_description,
        additional_notes=additional_notes,
    )

    return await bid_service.save_bid_draft(clerk_user_id, draft_data)


# ------------------------------------------------------------------------------------------------------------------------


@bid_router.put("/{bid_id}", response_model=BidResponse)
async def update_bid(
    bid_id: str,
    is_draft_submit: bool = Query(False, alias="is-draft-submit"),
    title: str = Form(None),
    price_min: Optional[float] = Form(None),
    price_max: Optional[float] = Form(None),
    timeline_estimate: str = Form(None),
    work_description: str = Form(None),
    additional_notes: str = Form(None),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    bid_service: BidService = Depends(get_bid_service),
):
    """Update existing bid"""

    # Create update data
    bid_data = BidUpdate(
        title=title,
        price_min=price_min,
        price_max=price_max,
        timeline_estimate=timeline_estimate,
        work_description=work_description,
        additional_notes=additional_notes,
    )

    return await bid_service.update_bid(clerk_user_id, bid_id, bid_data, is_draft_submit)


# ------------------------------------------------------------------------------------------------------------------------


@bid_router.delete("/{bid_id}", response_model=bool)
async def delete_bid(
    bid_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    bid_service: BidService = Depends(get_bid_service),
):
    """Delete bid"""
    return await bid_service.delete_bid(clerk_user_id, bid_id)


# ------------------------------------------------------------------------------------------------------------------------


@bid_router.get("/{bid_id}", response_model=BidDetailResponse)
async def get_bid_detail(
    bid_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    bid_service: BidService = Depends(get_bid_service),
):
    """Get complete bid details with job context"""
    return await bid_service.get_bid_detail(clerk_user_id, bid_id)
