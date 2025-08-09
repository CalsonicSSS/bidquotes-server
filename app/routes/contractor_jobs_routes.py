from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, Query
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.utils.user_auth import get_current_clerk_user_id
from typing import Optional, List, Tuple
from app.services.contractor_jobs_services import ContractorJobService
from app.models.job_models import ContractorJobCardResponse, JobDetailViewResponse
from typing import List, Optional


contractor_jobs_router = APIRouter(prefix="/contractors", tags=["Contractors"])


async def get_contractor_job_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> ContractorJobService:
    """Dependency to get ContractorJobService instance"""
    return ContractorJobService(supabase_client)


@contractor_jobs_router.get("/available-jobs", response_model=List[ContractorJobCardResponse])
async def get_available_jobs_for_contractor(
    city: Optional[str] = Query(None, description="Filter jobs by city"),
    job_type: Optional[str] = Query(None, description="Filter jobs by job type"),
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_job_service: ContractorJobService = Depends(get_contractor_job_service),
):
    """Get all available jobs that contractors can bid on"""
    return await contractor_job_service.get_available_jobs(clerk_user_id, city, job_type)


@contractor_jobs_router.get("/job-cities", response_model=List[str])
async def get_job_cities(
    contractor_job_service: ContractorJobService = Depends(get_contractor_job_service),
):
    """Get unique cities from open jobs for filtering"""
    return await contractor_job_service.get_job_cities()


@contractor_jobs_router.get("/jobs/{job_id}", response_model=JobDetailViewResponse)
async def get_contractor_job_detail(
    job_id: str,
    clerk_user_id: str = Depends(get_current_clerk_user_id),
    contractor_job_service: ContractorJobService = Depends(get_contractor_job_service),
):
    """Get complete job details for contractor review"""
    return await contractor_job_service.get_job_detail_for_contractor(clerk_user_id, job_id)
