from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import enum
import uuid


class TicketStatus(str, enum.Enum):
    """Ticket lifecycle status."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, enum.Enum):
    """Ticket priority levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Ticket(Base, TimestampMixin):
    """
    Support tickets for failures and policy violations.

    Created automatically by:
    - Worker retry exhaustion → processing_failure ticket
    - HIGH/CRITICAL policy violations → policy_violation ticket
    """

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="SET NULL"), index=True)

    # Ticket classification
    ticket_type = Column(String(50), nullable=False, index=True)  # 'processing_failure', 'policy_violation', 'manual_review'
    priority = Column(SQLEnum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(SQLEnum(TicketStatus), nullable=False, default=TicketStatus.OPEN, index=True)

    # Ticket content
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Assignment
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)

    # Metadata (error stack traces, policy details, etc.)
    ticket_metadata = Column(JSONB)

    # Correlation for tracing
    correlation_id = Column(UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4)

    # Resolution
    resolved_at = Column(DateTime)

    # Relationships
    receipt = relationship("Receipt", back_populates="tickets")
    assigned_to = relationship("User", back_populates="assigned_tickets", foreign_keys=[assigned_to_user_id])
    policy_evaluations = relationship("PolicyEvaluation", back_populates="ticket")

    __table_args__ = (
        Index("idx_tickets_status", "status"),
        Index("idx_tickets_correlation", "correlation_id"),
    )

    def __repr__(self):
        return f"<Ticket(id={self.id}, type='{self.ticket_type}', status='{self.status.value}')>"
