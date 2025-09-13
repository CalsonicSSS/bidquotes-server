from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ContractorType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class ContractorProfileCreate(BaseModel):
    contractor_name: str
    main_service_areas: str
    years_of_experience: str
    team_size: str
    contractor_type: ContractorType
    company_website: Optional[str] = None
    additional_information: Optional[str] = None
    phone: str
    email: str


class ContractorProfileImageResponse(BaseModel):
    id: str
    contractor_profile_id: str
    image_url: str
    storage_path: str
    image_order: int
    created_at: datetime


class ContractorProfileResponse(BaseModel):
    id: str
    user_id: str
    contractor_name: str
    main_service_areas: str
    years_of_experience: str
    contractor_type: ContractorType
    team_size: str
    phone: str
    email: str
    company_website: Optional[str] = None
    additional_information: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    credit_count: int
    images: List[ContractorProfileImageResponse] = []
