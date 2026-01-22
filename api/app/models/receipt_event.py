from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.receipt import ReceiptStatus
import uuid


class ReceiptEvent(Base):
    """
    Audit trail for receipt state transitions.

    Every status change creates an event with:
    - from_status → to_status
    - correlation_id for tracing across services
    - metadata JSONB for additional context
    """

    __tablename__ = "receipt_events"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)

    # State transition
    from_status = Column(SQLEnum(ReceiptStatus))  # NULL for initial QUEUED
    to_status = Column(SQLEnum(ReceiptStatus), nullable=False)

    # Correlation tracking for distributed tracing
    correlation_id = Column(UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # 'upload', 'worker_start', 'policy_flag', etc.
    message = Column(Text)
    event_metadata = Column(JSONB)  # Additional context (error details, policy violations, etc.)

    # Actor (who/what triggered this event)
    triggered_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    triggered_by_system = Column(String(50))  # 'celery_worker', 'api', 'admin_action', etc.

    # Timestamp
    created_at = Column(DateTime, nullable=False, server_default="now()")

    # Relationships
    receipt = relationship("Receipt", back_populates="events")
    triggered_by_user = relationship("User", back_populates="triggered_events", foreign_keys=[triggered_by_user_id])

    __table_args__ = (
        Index("idx_receipt_events_correlation", "correlation_id"),
        Index("idx_receipt_events_created_at_desc", created_at.desc()),
        Index("idx_receipt_events_event_type", "event_type"),
    )

    def __repr__(self):
        return f"<ReceiptEvent(id={self.id}, receipt_id={self.receipt_id}, {self.from_status}→{self.to_status})>"
