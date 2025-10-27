from fastapi import APIRouter, Depends
from supabase import AsyncClient
from app.utils.supabase_client_handlers import get_supabase_client
from app.services.admin.admin_financial_services import AdminFinancialService
from app.models.admin.admin_financial_models import FinancialMetricsResponse

admin_financial_router = APIRouter(prefix="/admin/financial", tags=["Admin"])


async def get_admin_financial_service(supabase_client: AsyncClient = Depends(get_supabase_client)) -> AdminFinancialService:
    """Dependency to get AdminFinancialService instance"""
    return AdminFinancialService(supabase_client)


# =====================================
# FINANCIAL METRICS ENDPOINT
# =====================================


@admin_financial_router.get("/metrics", response_model=FinancialMetricsResponse)
async def get_financial_metrics(
    admin_service: AdminFinancialService = Depends(get_admin_financial_service),
):
    """Get complete financial metrics including revenue, transactions, credits, and 30-day breakdown"""
    return await admin_service.get_all_financial_metrics()
