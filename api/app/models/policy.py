from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import enum
import uuid


class PolicySeverity(str, enum.Enum):
    """Policy violation severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyRule(Base, TimestampMixin):
    """
    DB-driven policy rules with JSONB configuration.

    Examples:
    - MAX_AMOUNT: config = {"max_amount": 1000.00}
    - DUPLICATE_RECEIPT: config = {"look_back_days": 90}
    - MISSING_MERCHANT: config = {"required": true}
    """

    __tablename__ = "policy_rules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # 'MAX_AMOUNT', 'DUPLICATE_RECEIPT', etc.
    name = Column(String(255), nullable=False)
    description = Column(String(500))

    # Severity determines if ticket is created on violation
    severity = Column(SQLEnum(PolicySeverity), nullable=False, default=PolicySeverity.MEDIUM)

    # JSONB config allows runtime policy changes without redeployment
    config = Column(JSONB, nullable=False, default={})

    # Enable/disable policies without deletion
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    evaluations = relationship("PolicyEvaluation", back_populates="policy_rule")

    def __repr__(self):
        return f"<PolicyRule(id={self.id}, code='{self.code}', severity='{self.severity.value}')>"


class PolicyEvaluation(Base):
    """
    Record of policy evaluation against a receipt.

    Links to ticket if HIGH/CRITICAL severity and failed.
    """

    __tablename__ = "policy_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_rule_id = Column(Integer, ForeignKey("policy_rules.id", ondelete="CASCADE"), nullable=False)

    # Evaluation result
    passed = Column(Boolean, nullable=False, index=True)
    evaluated_at = Column(DateTime, nullable=False, server_default="now()")

    # Details about why it passed/failed
    details = Column(JSONB)  # e.g., {"detected_amount": 1500.00, "threshold": 1000.00}

    # Link to ticket if created
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="SET NULL"))

    # Correlation for tracing
    correlation_id = Column(UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4)

    # Relationships
    receipt = relationship("Receipt", back_populates="policy_evaluations")
    policy_rule = relationship("PolicyRule", back_populates="evaluations")
    ticket = relationship("Ticket", back_populates="policy_evaluations")

    __table_args__ = (
        Index("idx_policy_evals_passed", "passed"),
        Index("idx_policy_evals_correlation", "correlation_id"),
    )

    def __repr__(self):
        return f"<PolicyEvaluation(id={self.id}, receipt_id={self.receipt_id}, passed={self.passed})>"
