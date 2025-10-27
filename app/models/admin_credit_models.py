from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# =====================================
# Credit Management Models
# =====================================


class ContractorContactResponse(BaseModel):
    """Contractor contact information"""

    contractor_name: str
    email: str
    phone: str


class BuyerContactResponse(BaseModel):
    """Buyer contact information"""

    contact_email: str
    phone_number: str


class JobBidInquiryResponse(BaseModel):
    """Complete job and bid details for credit inquiry verification"""

    # Job details
    job_id: str
    job_title: str
    job_type: str
    job_budget: str
    job_status: str
    job_location_address: str
    job_city: str
    job_description: str
    job_other_requirements: Optional[str] = None
    job_created_at: datetime

    # Bid details
    bid_id: str
    bid_title: str
    bid_price_min: str
    bid_price_max: str
    bid_timeline_estimate: str
    bid_status: str
    bid_created_at: datetime

    # Contractor info
    contractor_id: str
    contractor_contact: ContractorContactResponse

    # Buyer info
    buyer_id: str
    buyer_contact: BuyerContactResponse

    # Current credit balance
    contractor_current_credits: int


class AddCreditRequest(BaseModel):
    """Request to add credit to contractor"""

    contractor_id: str


class AddCreditResponse(BaseModel):
    """Response after adding credit"""

    success: bool
    contractor_id: str
    credits_added: int
    new_balance: int
    message: str
