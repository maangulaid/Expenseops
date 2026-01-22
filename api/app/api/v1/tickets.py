from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import check_user_role
from app.models.user import User
from app.models.ticket import Ticket, TicketStatus
from app.schemas.ticket import TicketResponse, TicketUpdate
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    status_filter: Optional[TicketStatus] = None,
    ticket_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List support tickets (support+ only).

    Filters:
    - status: OPEN, IN_PROGRESS, RESOLVED, CLOSED
    - ticket_type: processing_failure, policy_violation, manual_review
    """
    check_user_role(current_user, "support", "admin")

    query = db.query(Ticket)

    if status_filter:
        query = query.filter(Ticket.status == status_filter)

    if ticket_type:
        query = query.filter(Ticket.ticket_type == ticket_type)

    query = query.order_by(Ticket.created_at.desc())
    query = query.limit(limit).offset(offset)

    tickets = query.all()

    return tickets


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ticket details (support+ only).
    """
    check_user_role(current_user, "support", "admin")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update ticket status or assignment (support+ only).

    Allows changing:
    - status (OPEN, IN_PROGRESS, RESOLVED, CLOSED)
    - assigned_to_user_id (assign to support staff)
    """
    check_user_role(current_user, "support", "admin")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    # Update fields
    if ticket_data.status is not None:
        old_status = ticket.status
        ticket.status = ticket_data.status

        # Set resolved_at when moving to RESOLVED
        if ticket_data.status == TicketStatus.RESOLVED and old_status != TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()

    if ticket_data.assigned_to_user_id is not None:
        ticket.assigned_to_user_id = ticket_data.assigned_to_user_id

    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return ticket


@router.post("/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark ticket as resolved (support+ only).
    """
    check_user_role(current_user, "support", "admin")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    if ticket.status == TicketStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket already resolved"
        )

    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return ticket
