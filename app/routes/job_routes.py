from fastapi import APIRouter, Depends, Query
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from app.services.job_services import JobService
from app.models.job_models import JobCreate, JobUpdate, JobDraftCreate, JobResponse, JobDetailViewResponse, JobCardResponse
from typing import List, Optional

job_router = APIRouter(prefix="/jobs", tags=["Jobs"])


async def get_job_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> JobService:
    """Dependency to get JobService instance"""
    return JobService(supabase_client)


@job_router.post("", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Create a new job posting"""
    return await job_service.create_job(clerk_user_id, job_data)


@job_router.post("/drafts", response_model=JobResponse)
async def save_job_draft(
    draft_data: JobDraftCreate,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Save job as draft"""
    return await job_service.save_job_draft(clerk_user_id, draft_data)


@job_router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Update existing job"""
    return await job_service.update_job(clerk_user_id, job_id, job_data)


@job_router.get("", response_model=List[JobCardResponse])
async def get_buyer_jobs(
    status: Optional[str] = Query(None, description="Filter jobs by status"),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Get all jobs for the authenticated buyer"""
    return await job_service.get_buyer_jobs(clerk_user_id, status)


@job_router.get("/{job_id}", response_model=JobDetailViewResponse)
async def get_job_detail(
    job_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Get detailed job information"""
    return await job_service.get_job_detail(clerk_user_id, job_id)


@job_router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Delete job"""
    success = await job_service.delete_job(clerk_user_id, job_id)
    return {"message": "Job deleted successfully" if success else "Failed to delete job"}


@job_router.get("/drafts/list", response_model=List[JobCardResponse])
async def get_job_drafts(
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    job_service: JobService = Depends(get_job_service),
):
    """Get all job drafts for the authenticated buyer"""
    return await job_service.get_buyer_jobs(clerk_user_id, "draft")
