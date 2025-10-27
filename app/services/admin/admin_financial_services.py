from supabase import AsyncClient
from app.models.admin.admin_financial_models import (
    FinancialMetricsResponse,
    RevenueMetrics,
    TransactionMetrics,
    CreditMetrics,
    DailyRevenueBreakdown,
)
from app.custom_error import ServerError
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class AdminFinancialService:
    def __init__(self, supabase_client: AsyncClient):
        self.supabase_client = supabase_client

    # =====================================
    # MAIN METRICS ENDPOINT
    # =====================================

    async def get_all_financial_metrics(self) -> FinancialMetricsResponse:
        """Get complete financial metrics for admin dashboard"""
        try:
            # Fetch all metrics in parallel for efficiency
            revenue_metrics = await self._get_revenue_metrics()
            transaction_metrics = await self._get_transaction_metrics()
            credit_metrics = await self._get_credit_metrics()
            daily_breakdown = await self._get_daily_revenue_breakdown()

            return FinancialMetricsResponse(
                revenue=revenue_metrics,
                transactions=transaction_metrics,
                credits=credit_metrics,
                daily_revenue_breakdown=daily_breakdown,
            )

        except Exception as e:
            logger.error(f"Error fetching financial metrics: {str(e)}")
            raise ServerError(f"Failed to fetch financial metrics: {str(e)}")

    # =====================================
    # Individual financial metrics HELPER METHODS
    # =====================================

    async def _get_revenue_metrics(self) -> RevenueMetrics:
        """Calculate total revenue from successful payments"""
        try:
            # Get all successful payments
            result = await self.supabase_client.table("payment_transactions").select("item_type, amount_cad").eq("status", "succeeded").execute()

            total_revenue = 0.0
            bid_payment_revenue = 0.0
            credit_purchase_revenue = 0.0

            if result.data:
                for transaction in result.data:
                    amount = float(transaction["amount_cad"])
                    total_revenue += amount

                    if transaction["item_type"] == "bid_payment":
                        bid_payment_revenue += amount
                    elif transaction["item_type"] == "credit_purchase":
                        credit_purchase_revenue += amount

            return RevenueMetrics(
                total_revenue_cad=round(total_revenue, 2),
                bid_payment_revenue_cad=round(bid_payment_revenue, 2),
                credit_purchase_revenue_cad=round(credit_purchase_revenue, 2),
            )

        except Exception as e:
            logger.error(f"Error calculating revenue metrics: {str(e)}")
            raise

    async def _get_transaction_metrics(self) -> TransactionMetrics:
        """Get transaction statistics by status"""
        try:
            # Get all transactions
            result = await self.supabase_client.table("payment_transactions").select("status").execute()

            total = 0
            successful = 0
            failed = 0
            pending = 0

            if result.data:
                total = len(result.data)
                for transaction in result.data:
                    status = transaction["status"]
                    if status == "succeeded":
                        successful += 1
                    elif status == "failed":
                        failed += 1
                    elif status == "pending":
                        pending += 1

            return TransactionMetrics(
                total_transactions=total,
                successful_transactions=successful,
                failed_transactions=failed,
                pending_transactions=pending,
            )

        except Exception as e:
            logger.error(f"Error calculating transaction metrics: {str(e)}")
            raise

    async def _get_credit_metrics(self) -> CreditMetrics:
        """Get credit usage statistics"""
        try:
            # Get all credit transactions
            result = await self.supabase_client.table("credit_transactions").select("transaction_type, credits_change").execute()

            total_purchased = 0
            total_used = 0
            total_refunded = 0

            if result.data:
                for transaction in result.data:
                    credits_change = transaction["credits_change"]
                    transaction_type = transaction["transaction_type"]

                    if transaction_type == "purchase":
                        total_purchased += credits_change
                    elif transaction_type == "usage":
                        total_used += abs(credits_change)  # Usage is negative, so take absolute value
                    elif transaction_type == "refund":
                        total_refunded += credits_change

            # Calculate active balance: purchased + refunded - used
            active_balance = total_purchased + total_refunded - total_used

            return CreditMetrics(
                total_credits_purchased=total_purchased,
                total_credits_used=total_used,
                total_credits_refunded=total_refunded,
                active_credit_balance=active_balance,
            )

        except Exception as e:
            logger.error(f"Error calculating credit metrics: {str(e)}")
            raise

    async def _get_daily_revenue_breakdown(self) -> List[DailyRevenueBreakdown]:
        """Get daily revenue breakdown for the past 30 days"""
        try:
            # Calculate date range (last 30 days)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=29)  # 29 days ago + today = 30 days

            # Fetch successful payments from the last 30 days
            result = (
                await self.supabase_client.table("payment_transactions")
                .select("created_at, item_type, amount_cad")
                .eq("status", "succeeded")
                .gte("created_at", start_date.isoformat())
                .lte("created_at", (end_date + timedelta(days=1)).isoformat())  # Include all of today
                .execute()
            )

            # Initialize daily data structure
            daily_data: Dict[str, Dict[str, float]] = {}
            current_date = start_date

            # Create entries for all 30 days (even if no transactions)
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_data[date_str] = {
                    "total_revenue": 0.0,
                    "bid_payment_revenue": 0.0,
                    "credit_purchase_revenue": 0.0,
                    "transaction_count": 0,
                }
                current_date += timedelta(days=1)

            # Aggregate transactions by date
            if result.data:
                for transaction in result.data:
                    # Extract date from timestamp (YYYY-MM-DD)
                    transaction_date = transaction["created_at"][:10]

                    # Skip if outside our range (shouldn't happen, but safety check)
                    if transaction_date not in daily_data:
                        continue

                    amount = float(transaction["amount_cad"])
                    item_type = transaction["item_type"]

                    daily_data[transaction_date]["total_revenue"] += amount
                    daily_data[transaction_date]["transaction_count"] += 1

                    if item_type == "bid_payment":
                        daily_data[transaction_date]["bid_payment_revenue"] += amount
                    elif item_type == "credit_purchase":
                        daily_data[transaction_date]["credit_purchase_revenue"] += amount

            # Convert to list of DailyRevenueBreakdown objects, sorted by date
            breakdown = []
            for date_str in sorted(daily_data.keys()):
                data = daily_data[date_str]
                breakdown.append(
                    DailyRevenueBreakdown(
                        date=date_str,
                        total_revenue=round(data["total_revenue"], 2),
                        bid_payment_revenue=round(data["bid_payment_revenue"], 2),
                        credit_purchase_revenue=round(data["credit_purchase_revenue"], 2),
                        transaction_count=data["transaction_count"],
                    )
                )

            return breakdown

        except Exception as e:
            logger.error(f"Error calculating daily revenue breakdown: {str(e)}")
            raise
