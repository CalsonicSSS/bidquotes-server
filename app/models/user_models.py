from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class BuyerContactInfoCreate(BaseModel):
    contact_email: EmailStr
    phone_number: str


class BuyerContactInfoUpdate(BaseModel):
    contact_email: Optional[EmailStr] = None
    phone_number: Optional[str] = None


class BuyerContactInfoResponse(BaseModel):
    id: str
    user_id: str
    contact_email: str
    phone_number: str
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------------------------------------------------


class UserCreate(BaseModel):
    clerk_user_id: str
    email: EmailStr
    user_type: str


class UserResponse(BaseModel):
    id: str
    clerk_user_id: str
    email: str
    user_type: str
    created_at: datetime
    updated_at: datetime
