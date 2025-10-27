from fastapi import APIRouter, Depends, Query
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.services.admin_job_services import AdminJobService
from app.models.admin_job_models import PaginatedJobsResponse, AdminJobDetailResponse

admin_job_router = APIRouter(prefix="/admin/jobs", tags=["Admin"])


async def get_admin_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> AdminJobService:
    """Dependency to get AdminJobService instance"""
    return AdminJobService(supabase_client)


# =====================================
# JOB VALIDATION ENDPOINTS
# =====================================


@admin_job_router.get("", response_model=PaginatedJobsResponse)
async def get_all_jobs_paginated(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(30, ge=1, le=100, description="Items per page"),
    admin_service: AdminJobService = Depends(get_admin_service),
):
    """Get all job cards with pagination for admin dashboard"""
    return await admin_service.get_all_job_cards_paginated(page, page_size)


# --------------------------------------------------------------


@admin_job_router.get("/{job_id}", response_model=AdminJobDetailResponse)
async def get_job_detail_for_validation(
    job_id: str,
    admin_service: AdminJobService = Depends(get_admin_service),
):
    """Get full job detail with buyer contact info for validation"""
    return await admin_service.get_job_detail_with_buyer_contact(job_id)


# --------------------------------------------------------------


@admin_job_router.put("/{job_id}/validate", response_model=bool)
async def validate_job(
    job_id: str,
    admin_service: AdminJobService = Depends(get_admin_service),
):
    """Mark a job as validated"""
    return await admin_service.validate_job(job_id)


# --------------------------------------------------------------


@admin_job_router.delete("/{job_id}", response_model=bool)
async def delete_job(
    job_id: str,
    admin_service: AdminJobService = Depends(get_admin_service),
):
    """Delete a job (for fake/noise jobs)"""
    return await admin_service.delete_job(job_id)
