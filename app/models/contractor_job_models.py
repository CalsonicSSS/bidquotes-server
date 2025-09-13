from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.models.job_models import JobImageResponse, JobType


class ContractorJobCardResponse(BaseModel):
    id: str
    title: str
    job_type: JobType
    city: str
    bid_count: int
    created_at: datetime
    thumbnail_image: Optional[str] = None  # Include first image if available


class PreBidJobDetailResponse(BaseModel):
    id: str
    buyer_id: str
    title: str
    job_type: JobType
    job_budget: str
    city: str
    created_at: datetime
    images: List[JobImageResponse] = []
    bid_count: int = 0
