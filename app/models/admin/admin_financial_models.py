from pydantic import BaseModel
from typing import List
from datetime import date

# =====================================
# FINANCIAL METRICS RESPONSE MODELS
# =====================================


from pydantic import BaseModel
from typing import List
from datetime import date

# =====================================
# FINANCIAL METRICS RESPONSE MODELS
# =====================================


class RevenueMetrics(BaseModel):
    """Overall revenue summary"""

    total_revenue_cad: float
    bid_payment_revenue_cad: float
    credit_purchase_revenue_cad: float


class TransactionMetrics(BaseModel):
    """Transaction statistics"""

    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    pending_transactions: int


class CreditMetrics(BaseModel):
    """Credit usage statistics"""

    total_credits_purchased: int
    total_credits_used: int
    total_credits_refunded: int
    active_credit_balance: int  # Current unused credits across all contractors


class DailyRevenueBreakdown(BaseModel):
    """Daily revenue broken down by source for chart visualization"""

    date: str  # Format: "YYYY-MM-DD" for easy charting
    total_revenue: float
    bid_payment_revenue: float
    credit_purchase_revenue: float
    transaction_count: int


class FinancialMetricsResponse(BaseModel):
    """Complete financial metrics dashboard data"""

    revenue: RevenueMetrics
    transactions: TransactionMetrics
    credits: CreditMetrics
    daily_revenue_breakdown: List[DailyRevenueBreakdown]  # Last 30 days for interactive chart
