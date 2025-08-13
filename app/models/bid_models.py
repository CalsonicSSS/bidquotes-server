from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class BidStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SELECTED = "selected"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class BidCreate(BaseModel):
    job_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    work_description: str
    additional_notes: Optional[str] = None


class BidUpdate(BaseModel):
    title: Optional[str] = None
    price_min: Optional[str] = None
    price_max: Optional[str] = None
    timeline_estimate: Optional[str] = None
    work_description: Optional[str] = None
    additional_notes: Optional[str] = None


class BidDraftCreate(BaseModel):
    job_id: str
    title: Optional[str] = None
    price_min: Optional[str] = None
    price_max: Optional[str] = None
    timeline_estimate: Optional[str] = None
    work_description: Optional[str] = None
    additional_notes: Optional[str] = None


class BidResponse(BaseModel):
    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: str
    price_max: str
    timeline_estimate: str
    work_description: str
    additional_notes: Optional[str]
    status: BidStatus
    is_selected: bool
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
    work_description: str
    additional_notes: Optional[str]
    status: BidStatus
    is_selected: bool
    created_at: datetime
    updated_at: datetime
    # Include job info for context
    job_title: str
    job_type: str
    job_budget: str
    job_city: str
    # Buyer contact info (only revealed when bid is confirmed)
    buyer_contact_email: Optional[str] = None
    buyer_contact_phone: Optional[str] = None


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
    is_selected: bool
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
    work_description: str
    additional_notes: Optional[str]
    status: BidStatus
    is_selected: bool
    created_at: datetime
    updated_at: datetime
    # Job context info for reference
    job_title: str
    job_type: str
    job_budget: str
    job_city: str
