from pydantic import BaseModel
from typing import Dict, Any, Optional


class ClerkWebhookEvent(BaseModel):
    data: Dict[str, Any]
    object: str
    type: str


class ClerkUser(BaseModel):
    id: str
    email_addresses: list
    unsafe_metadata: Optional[Dict[str, Any]] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
