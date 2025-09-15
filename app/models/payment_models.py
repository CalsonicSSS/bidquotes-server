from pydantic import BaseModel
from typing import Optional


class DraftBidPaymentRequest(BaseModel):
    draft_bid_id: str


class CheckoutSessionResponse(BaseModel):
    session_id: str
    session_url: str


class CreditBalanceResponse(BaseModel):
    credits: int
