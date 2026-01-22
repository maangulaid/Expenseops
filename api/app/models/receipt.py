from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, DateTime, Enum as SQLEnum, Text, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import enum


class ReceiptStatus(str, enum.Enum):
    """Receipt processing status enum."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FLAGGED = "FLAGGED"
    FAILED = "FAILED"


class Receipt(Base, TimestampMixin):
    """
    Receipt model with state machine tracking.

    Critical features:
    - Unique constraint on (user_id, source_sha256) for idempotency
    - Status enum for state machine
    - processing_version increments on reprocess
    """

    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Idempotency: SHA256 hash of original file content
    source_sha256 = Column(String(64), nullable=False, index=True)

    # Storage info
    minio_key = Column(String(255), nullable=False)  # Safe object key in MinIO
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)

    # State machine
    status = Column(
        SQLEnum(ReceiptStatus),
        nullable=False,
        default=ReceiptStatus.QUEUED,
        index=True
    )
    processing_version = Column(Integer, nullable=False, default=1, index=True)

    # Extracted data (populated by worker)
    merchant_name = Column(String(255))
    total_amount = Column(Numeric(10, 2))
    transaction_date = Column(Date)
    currency = Column(String(3), default="USD")
    raw_ocr_text = Column(Text)

    # Processing metadata
    uploaded_at = Column(DateTime, nullable=False, server_default="now()")
    processed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="receipts")
    events = relationship("ReceiptEvent", back_populates="receipt", cascade="all, delete-orphan")
    policy_evaluations = relationship("PolicyEvaluation", back_populates="receipt", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="receipt")

    __table_args__ = (
        # CRITICAL: Idempotency constraint
        UniqueConstraint("user_id", "source_sha256", name="uq_user_receipt_hash"),
        # Performance indexes
        Index("idx_receipts_user_status", "user_id", "status"),
        Index("idx_receipts_uploaded_at_desc", uploaded_at.desc()),
    )

    def __repr__(self):
        return f"<Receipt(id={self.id}, user_id={self.user_id}, status='{self.status.value}')>"
