from fastapi import APIRouter, Depends, Header
from supabase import AsyncClient
from app.utils.supabase_client import get_supabase_client
from app.services.user_service import UserService
from app.models.user_models import BuyerContactInfoCreate, BuyerContactInfoResponse, BuyerContactInfoUpdate
from typing import Optional
from app.configs.app_settings import settings

user_router = APIRouter(prefix="/users", tags=["Users"])


async def get_user_service(supabase: AsyncClient = Depends(get_supabase_client)) -> UserService:
    """Dependency to get UserService instance"""
    return UserService(supabase)


@user_router.post("/buyer-contact-info", response_model=BuyerContactInfoResponse)
async def save_buyer_contact_info(
    buyer_contact_info: BuyerContactInfoCreate | BuyerContactInfoUpdate,
    clerk_user_id: str = Header(..., alias="x-clerk-user-id"),
    user_service: UserService = Depends(get_user_service),
):
    """Save buyer contact information"""
    return await user_service.save_buyer_contact_info(clerk_user_id, buyer_contact_info)


@user_router.get("/buyer-contact-info", response_model=Optional[BuyerContactInfoResponse])
async def get_buyer_contact_info(clerk_user_id: str = Header(..., alias="x-clerk-user-id"), user_service: UserService = Depends(get_user_service)):
    """Get buyer contact information"""
    return await user_service.get_buyer_contact_info(clerk_user_id)
