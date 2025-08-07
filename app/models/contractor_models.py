from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ContractorType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class ContractorProfileCreate(BaseModel):
    contractor_name: str
    main_service_areas: str  # Simple text field: "Plumbing, Electrical, HVAC"
    years_of_experience: int
    contractor_type: ContractorType
    team_size: int
    company_website: Optional[str] = None
    additional_information: Optional[str] = None


class ContractorProfileUpdate(BaseModel):
    contractor_name: Optional[str] = None
    main_service_areas: Optional[str] = None
    years_of_experience: Optional[int] = None
    contractor_type: Optional[ContractorType] = None
    team_size: Optional[int] = None
    company_website: Optional[str] = None
    additional_information: Optional[str] = None


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
    years_of_experience: int
    contractor_type: ContractorType
    team_size: int
    company_website: Optional[str] = None
    additional_information: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    images: List[ContractorProfileImageResponse] = []  # Always include images
