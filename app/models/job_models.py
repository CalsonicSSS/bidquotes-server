from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobType(str, Enum):
    PLUMBING = "Plumbing"
    PAINTING = "Painting"
    LANDSCAPING = "Landscaping"
    ROOFING = "Roofing"
    INDOOR = "Indoor"
    BACKYARD = "Backyard"
    FENCING_DECKING = "Fencing & Decking"
    DESIGN = "Design"
    DEFAULT = ""


class JobStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    FULL_BID = "full_bid"
    WAITING_CONFIRMATION = "waiting_confirmation"
    CONFIRMED = "confirmed"


class JobCreate(BaseModel):
    title: str
    job_type: JobType
    job_budget: str
    description: str
    location_address: str
    city: str
    other_requirements: Optional[str] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    job_type: Optional[JobType] = None
    job_budget: Optional[str] = None
    description: Optional[str] = None
    location_address: Optional[str] = None
    city: Optional[str] = None
    other_requirements: Optional[str] = None


class JobDraftCreate(BaseModel):
    title: Optional[str] = None
    job_type: Optional[JobType] = None
    job_budget: Optional[str] = None
    description: Optional[str] = None
    location_address: Optional[str] = None
    city: Optional[str] = None
    other_requirements: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    buyer_id: str
    title: str
    job_type: JobType
    job_budget: str
    description: str
    location_address: str
    city: str
    other_requirements: Optional[str]
    status: JobStatus
    selection_count: int
    max_selections: int
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------------------------------------


class JobImageCreate(BaseModel):
    image_url: str
    image_order: int = 1
    storage_path: str
    image_order: int


class JobImageResponse(BaseModel):
    id: str
    job_id: str
    image_url: str
    storage_path: str
    image_order: int
    created_at: datetime


# -------------------------------------------------------------------------------------------


class JobDetailViewResponse(BaseModel):
    id: str
    buyer_id: str
    title: str
    job_type: JobType
    job_budget: str
    description: str
    location_address: str
    city: str
    other_requirements: Optional[str]
    status: JobStatus
    selection_count: int
    max_selections: int
    created_at: datetime
    updated_at: datetime
    images: List[JobImageResponse] = []
    bid_count: int = 0


class JobCardResponse(BaseModel):
    id: str
    title: str
    job_type: JobType
    status: JobStatus
    bid_count: int
    created_at: datetime
    # Include first image if available
    thumbnail_image: Optional[str] = None
