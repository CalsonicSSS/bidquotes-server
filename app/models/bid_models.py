from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class BidStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class BidCreate(BaseModel):
    job_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str


class BidDraftCreate(BaseModel):
    job_id: str
    title: Optional[str] = None
    price_min: Optional[str] = None
    price_max: Optional[str] = None
    timeline_estimate: Optional[str] = None


class BidResponse(BaseModel):
    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    status: BidStatus
    created_at: datetime
    updated_at: datetime


class BidCardResponse(BaseModel):
    id: str
    job_id: str
    title: str
    status: BidStatus
    created_at: datetime
    updated_at: datetime
    # Job context info
    job_title: str
    job_type: str
    job_city: str


class BidDetailResponse(BaseModel):
    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    status: BidStatus
    created_at: datetime
    updated_at: datetime
    # Include job info for context
    job_title: str
    job_type: str
    job_budget: str
    job_city: str


# for payment logic handling
class BidCreationStatus(str, Enum):
    SUBMITTED = "submitted"  # Bid successfully submitted (had credits)
    DRAFT_PAYMENT_REQUIRED = "draft_payment_required"  # Saved as draft, payment needed


class BidCreationResponse(BaseModel):
    status: BidCreationStatus
    bid: BidResponse  # The created bid (either submitted or draft)
    payment_required: bool
    message: str


# ------------------------------------------------------
# buyer side


class BuyerBidCardInfo(BaseModel):
    """Bid information for buyer's job detail view"""

    id: str
    contractor_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    status: str
    created_at: datetime


class BuyerBidDetailResponse(BaseModel):
    """Bid detail response for buyer perspective (no contractor contact info)"""

    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    status: BidStatus
    created_at: datetime
    updated_at: datetime
    # Job context info for reference
    job_title: str
    job_type: str
    job_budget: str
    job_city: str
