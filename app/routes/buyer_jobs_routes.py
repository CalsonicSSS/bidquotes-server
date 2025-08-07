from fastapi import APIRouter, Depends, Query, File, UploadFile, Form, HTTPException
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.buyer_jobs_services import JobService
from app.models.job_models import JobCreate, JobUpdate, JobDraftCreate, JobResponse, JobDetailViewResponse, JobCardResponse
from typing import List, Optional, Tuple

buyer_job_router = APIRouter(prefix="/jobs", tags=["Jobs"])


async def get_job_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> JobService:
    """Dependency to get JobService instance"""
    return JobService(supabase_client)


async def process_uploaded_files(uploaded_images: List[UploadFile]) -> List[Tuple[bytes, str]]:
    """Helper to convert UploadFile objects to its (bytes, filename) tuples in list"""
    processed_image_files = []
    if uploaded_images and uploaded_images[0].filename:
        for upload_image in uploaded_images:
            if upload_image.filename and upload_image.size:
                content = await upload_image.read()
                filename = upload_image.filename
                processed_image_files.append((content, filename))

    return processed_image_files


########################################################################################################################


# ... means this field is required
# any other value will make this field optional with default value (so even if client side does not have field, fastapi will always have this field with default value)
@buyer_job_router.post("", response_model=JobResponse)
async def create_job(
    title: str = Form(...),
    job_type: str = Form(...),
    job_budget: str = Form(...),
    description: str = Form(...),
    location_address: str = Form(...),
    city: str = Form(...),
    other_requirements: str = Form(None),
    images: List[UploadFile] = File(default=[]),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Create new job posting with optional images"""
    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed per job")

    # Create job data
    job_data = JobCreate(
        title=title,
        job_type=job_type,
        job_budget=job_budget,
        description=description,
        location_address=location_address,
        city=city,
        other_requirements=other_requirements,
    )

    # prepared images
    processed_image_files = await process_uploaded_files(images)

    return await job_service.create_job(clerk_user_id, job_data, processed_image_files)


# ------------------------------------------------------------------------------------------------------------------------


@buyer_job_router.post("/drafts", response_model=JobResponse)
async def save_job_draft(
    title: str = Form(None),
    job_type: str = Form(None),
    job_budget: str = Form(None),
    description: str = Form(None),
    location_address: str = Form(None),
    city: str = Form(None),
    other_requirements: str = Form(None),
    images: List[UploadFile] = File(default=[]),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Save job as draft with optional images"""
    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed per job")

    # Create draft data (all fields optional)
    draft_data = JobDraftCreate(
        title=title,
        job_type=job_type,
        job_budget=job_budget,
        description=description,
        location_address=location_address,
        city=city,
        other_requirements=other_requirements,
    )

    # Process images
    processed_image_files = await process_uploaded_files(images)

    return await job_service.save_job_draft(clerk_user_id, draft_data, processed_image_files)


# ------------------------------------------------------------------------------------------------------------------------


@buyer_job_router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    is_draft_post: bool = Query(False, alias="is-draft-post"),
    title: str = Form(None),
    job_type: str = Form(None),
    job_budget: str = Form(None),
    description: str = Form(None),
    location_address: str = Form(None),
    city: str = Form(None),
    other_requirements: str = Form(None),
    images: List[UploadFile] = File(default=[]),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Update existing job with optional field and image changes"""
    if len(images) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed per job")

    # Create update data (only include provided fields)
    job_data = JobUpdate(
        title=title,
        job_type=job_type,
        job_budget=job_budget,
        description=description,
        location_address=location_address,
        city=city,
        other_requirements=other_requirements,
    )

    # Process images
    processed_image_files = await process_uploaded_files(images)

    return await job_service.update_job(clerk_user_id, job_id, job_data, is_draft_post, processed_image_files)


# ------------------------------------------------------------------------------------------------------------------------


@buyer_job_router.delete("/{job_id}", response_model=bool)
async def delete_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Delete job and all associated data (images, bids, etc.)"""
    return await job_service.delete_job(clerk_user_id, job_id)


# ------------------------------------------------------------------------------------------------------------------------


@buyer_job_router.get("", response_model=List[JobCardResponse])
async def get_buyer_jobs(
    status: Optional[str] = Query(None, description="Filter jobs by status (draft, open, full_bid, etc.)"),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Get job cards for buyer dashboard with optional status filter"""
    return await job_service.get_buyer_job_cards(clerk_user_id, status)


# ------------------------------------------------------------------------------------------------------------------------


@buyer_job_router.get("/{job_id}", response_model=JobDetailViewResponse)
async def get_job_detail(
    job_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Get complete job details with images and bid information"""
    return await job_service.get_job_detail(clerk_user_id, job_id)
