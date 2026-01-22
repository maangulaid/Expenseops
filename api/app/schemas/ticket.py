from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.ticket import TicketStatus, TicketPriority


class TicketUpdate(BaseModel):
    """Schema for updating a ticket."""
    status: Optional[TicketStatus] = None
    assigned_to_user_id: Optional[int] = None


class TicketResponse(BaseModel):
    """Schema for ticket response."""
    id: int
    receipt_id: Optional[int]
    ticket_type: str
    priority: TicketPriority
    status: TicketStatus
    title: str
    description: str
    assigned_to_user_id: Optional[int]
    metadata: Optional[Dict[str, Any]]
    correlation_id: str
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
