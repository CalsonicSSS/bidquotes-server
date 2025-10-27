from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# =====================================
# Job Validation Models
# =====================================


class AdminJobImageResponse(BaseModel):
    """Job image detail"""

    id: str
    image_url: str
    image_order: int


class BuyerContactResponse(BaseModel):
    """Buyer contact information"""

    contact_email: str
    phone_number: str


class AdminJobCardResponse(BaseModel):
    """Job card for admin dashboard view"""

    id: str
    title: str
    job_type: str
    job_budget: str
    city: str
    status: str
    is_validated: bool
    thumbnail_url: Optional[str] = None
    created_at: datetime


class AdminJobDetailResponse(BaseModel):
    """Full job detail for admin validation view"""

    # Job fields
    id: str
    buyer_id: str
    title: str
    job_type: str
    job_budget: str
    description: str
    location_address: str
    city: str
    other_requirements: Optional[str] = None
    status: str
    is_validated: bool
    created_at: datetime
    updated_at: datetime

    # Job images
    images: List[AdminJobImageResponse]

    # Buyer contact info
    buyer_contact: BuyerContactResponse


class PaginatedJobsResponse(BaseModel):
    """Paginated response for job cards"""

    jobs: List[AdminJobCardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
