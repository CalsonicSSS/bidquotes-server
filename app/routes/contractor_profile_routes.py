from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.contractor_profile_services import ContractorProfileService
from app.models.contractor_profile_models import ContractorProfileCreate, ContractorProfileResponse, ContractorType
from typing import Optional, List, Tuple

contractor_profile_router = APIRouter(prefix="/contractors/profile", tags=["Contractors"])


async def get_contractor_profile_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> ContractorProfileService:
    """Dependency to get ContractorProfileService instance"""
    return ContractorProfileService(supabase_client=supabase_client)


async def process_uploaded_profile_images(uploaded_images: List[UploadFile]) -> List[Tuple[bytes, str]]:
    """Helper to convert UploadFile objects to (bytes, filename) tuples"""
    processed_image_files = []
    if uploaded_images:
        for uploaded_image in uploaded_images:
            if uploaded_image.filename and uploaded_image.size:
                file_content = await uploaded_image.read()
                filename = uploaded_image.filename
                processed_image_files.append((file_content, filename))

    return processed_image_files


#############################################################################################################################################


# checked
@contractor_profile_router.get("", response_model=ContractorProfileResponse)
async def get_contractor_profile(
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_profile_service: ContractorProfileService = Depends(get_contractor_profile_service),
):
    """Get contractor profile information with images"""
    return await contractor_profile_service.get_contractor_profile(clerk_user_id)


# ------------------------------------------------------------------------------------------------------------------------------------------------------


@contractor_profile_router.get("/contractor-id/{contractor_id}", response_model=ContractorProfileResponse)
async def get_contractor_profile_by_contractor_id(
    contractor_id: str,
    contractor_profile_service: ContractorProfileService = Depends(get_contractor_profile_service),
):
    """Get contractor profile information by contractor ID"""
    return await contractor_profile_service.get_contractor_profile_by_contractor_id(contractor_id)


# ------------------------------------------------------------------------------------------------------------------------------------------------------


# checked
@contractor_profile_router.get("/completion-status", response_model=bool)
async def check_contractor_profile_completion(
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_profile_service: ContractorProfileService = Depends(get_contractor_profile_service),
):
    """Check if contractor profile is complete"""
    return await contractor_profile_service.check_contractor_profile_completion(clerk_user_id)


# -------------------------------------------------------------------------------------------------------------------------------------------------------


# checked
@contractor_profile_router.post("", response_model=ContractorProfileResponse)
async def save_contractor_profile(
    contractor_name: str = Form(...),
    main_service_areas: str = Form(...),
    years_of_experience: str = Form(...),
    contractor_type: str = Form(...),
    team_size: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    company_website: Optional[str] = Form(None),
    additional_information: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_profile_service: ContractorProfileService = Depends(get_contractor_profile_service),
):
    """Save contractor profile information with optional work sample images"""

    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed per profile")

    # Create profile data
    profile_data = ContractorProfileCreate(
        contractor_name=contractor_name,
        main_service_areas=main_service_areas,
        years_of_experience=years_of_experience,
        contractor_type=ContractorType(contractor_type),
        team_size=team_size,
        phone=phone,
        email=email,
        company_website=company_website,
        additional_information=additional_information,
    )

    # Process images
    processed_image_files = await process_uploaded_profile_images(images)

    return await contractor_profile_service.save_contractor_profile(clerk_user_id, profile_data, processed_image_files)


# -------------------------------------------------------------------------------------------------------------------------------------------------------


# checked
@contractor_profile_router.put("", response_model=ContractorProfileResponse)
async def update_contractor_profile(
    contractor_name: Optional[str] = Form(None),
    main_service_areas: Optional[str] = Form(None),  # Simple text field
    years_of_experience: Optional[str] = Form(None),
    contractor_type: Optional[str] = Form(None),
    team_size: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    company_website: Optional[str] = Form(None),
    additional_information: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_profile_service: ContractorProfileService = Depends(get_contractor_profile_service),
):
    """Update contractor profile information with optional work sample images"""

    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed per profile")

    # Create update data (only include provided fields, no JSON parsing)
    update_data = ContractorProfileCreate(
        contractor_name=contractor_name,
        main_service_areas=main_service_areas,
        years_of_experience=years_of_experience,
        contractor_type=ContractorType(contractor_type) if contractor_type else None,
        team_size=team_size,
        phone=phone,
        email=email,
        company_website=company_website,
        additional_information=additional_information,
    )

    # Process images
    processed_image_files = await process_uploaded_profile_images(images)

    return await contractor_profile_service.save_contractor_profile(clerk_user_id, update_data, processed_image_files)
