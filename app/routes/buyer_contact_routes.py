from fastapi import APIRouter, Depends
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.buyer_contact_services import UserService
from app.models.buyer_models import BuyerContactInfoCreate, BuyerContactInfoUpdate, BuyerContactInfoResponse
from typing import Optional

user_router = APIRouter(prefix="/users", tags=["Users"])


async def get_user_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> UserService:
    """Dependency to get UserService instance"""
    return UserService(supabase_client)


#############################################################################################################################################


@user_router.post("/buyer-contact-info", response_model=BuyerContactInfoResponse)
async def save_buyer_contact_info(
    buyer_contact_info: BuyerContactInfoCreate | BuyerContactInfoUpdate,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    user_service: UserService = Depends(get_user_service),
):
    """Save buyer contact information"""
    return await user_service.save_buyer_contact_info(clerk_user_id, buyer_contact_info)


# --------------------------------------------------------------------------------------------------------


@user_router.get("/buyer-contact-info", response_model=Optional[BuyerContactInfoResponse])
async def get_buyer_contact_info(clerk_user_id: str = Depends(get_current_clerk_user_id), user_service: UserService = Depends(get_user_service)):
    """Get buyer contact information"""
    return await user_service.get_buyer_contact_info(clerk_user_id)


# --------------------------------------------------------------------------------------------------------


# checked
# get buyer contact information by buyer ID
@user_router.get("/buyer-contact-info/{buyer_id}", response_model=Optional[BuyerContactInfoResponse])
async def get_buyer_contact_info_by_id(
    buyer_id: str,
    user_service: UserService = Depends(get_user_service),
):
    """Get buyer contact information by buyer ID"""
    return await user_service.get_buyer_contact_info_by_id(buyer_id)
