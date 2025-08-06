from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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
