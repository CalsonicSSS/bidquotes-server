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
    price_min: float
    price_max: float
    timeline_estimate: str
    work_description: str
    additional_notes: Optional[str] = None


class BidUpdate(BaseModel):
    title: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    timeline_estimate: Optional[str] = None
    work_description: Optional[str] = None
    additional_notes: Optional[str] = None


class BidDraftCreate(BaseModel):
    job_id: str
    title: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    timeline_estimate: Optional[str] = None
    work_description: Optional[str] = None
    additional_notes: Optional[str] = None


class BidResponse(BaseModel):
    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: float
    price_max: float
    timeline_estimate: str
    work_description: str
    additional_notes: Optional[str]
    status: BidStatus
    is_selected: bool
    created_at: datetime
    updated_at: datetime


class BidDetailResponse(BaseModel):
    id: str
    job_id: str
    contractor_id: str
    title: str
    price_min: float
    price_max: float
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
