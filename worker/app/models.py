"""
Shared SQLAlchemy models for worker.

Note: These are duplicated from API to avoid complex shared package setup.
In production, consider a shared package or single codebase.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, DateTime, Boolean, Text, Enum as SQLEnum, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


# Enums
class ReceiptStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FLAGGED = "FLAGGED"
    FAILED = "FAILED"


class PolicySeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


# Models (simplified, only what worker needs)
class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    minio_key = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(SQLEnum(ReceiptStatus), nullable=False, default=ReceiptStatus.QUEUED)
    processing_version = Column(Integer, nullable=False, default=1)
    merchant_name = Column(String(255))
    total_amount = Column(Numeric(10, 2))
    transaction_date = Column(Date)
    currency = Column(String(3), default="USD")
    raw_ocr_text = Column(Text)
    uploaded_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ReceiptEvent(Base):
    __tablename__ = "receipt_events"

    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)
    from_status = Column(SQLEnum(ReceiptStatus))
    to_status = Column(SQLEnum(ReceiptStatus), nullable=False)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(50), nullable=False)
    message = Column(Text)
    event_metadata = Column(JSONB)
    triggered_by_user_id = Column(Integer)
    triggered_by_system = Column(String(50))
    created_at = Column(DateTime, nullable=False)


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    severity = Column(SQLEnum(PolicySeverity), nullable=False, default=PolicySeverity.MEDIUM)
    config = Column(JSONB, nullable=False, default={})
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluations"

    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)
    policy_rule_id = Column(Integer, ForeignKey("policy_rules.id"), nullable=False)
    passed = Column(Boolean, nullable=False)
    evaluated_at = Column(DateTime, nullable=False)
    details = Column(JSONB)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    correlation_id = Column(UUID(as_uuid=True), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    ticket_type = Column(String(50), nullable=False)
    priority = Column(SQLEnum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(SQLEnum(TicketStatus), nullable=False, default=TicketStatus.OPEN)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    assigned_to_user_id = Column(Integer)
    ticket_metadata = Column(JSONB)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
