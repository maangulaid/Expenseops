"""
Ticket creation service for worker.

Creates tickets for:
- Processing failures
- Policy violations (HIGH/CRITICAL severity)
"""
from sqlalchemy.orm import Session
from app.models import Receipt, Ticket, PolicyEvaluation, PolicySeverity, TicketPriority, TicketStatus
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class TicketService:
    """Create and manage support tickets."""

    def __init__(self, db: Session, correlation_id: str):
        self.db = db
        self.correlation_id = correlation_id

    def create_processing_failure_ticket(
        self,
        receipt: Receipt,
        error_message: str,
        task_id: str = None
    ) -> Ticket:
        """
        Create ticket for processing failure.

        Args:
            receipt: Receipt that failed
            error_message: Error description
            task_id: Celery task ID

        Returns:
            Created Ticket instance
        """
        ticket = Ticket(
            receipt_id=receipt.id,
            ticket_type="processing_failure",
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            title=f"Receipt processing failed: {receipt.original_filename}",
            description=f"Receipt processing failed after retries.\n\nError: {error_message}",
            ticket_metadata={
                "error": error_message,
                "task_id": task_id,
                "receipt_id": receipt.id,
                "user_id": receipt.user_id,
                "processing_version": receipt.processing_version
            },
            correlation_id=uuid.UUID(self.correlation_id),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(ticket)
        self.db.flush()

        logger.info(f"Created processing failure ticket: ticket_id={ticket.id}")

        return ticket

    def create_policy_violation_ticket(
        self,
        receipt: Receipt,
        policy_evaluation: PolicyEvaluation
    ) -> Ticket:
        """
        Create ticket for HIGH/CRITICAL policy violation.

        Args:
            receipt: Receipt with violation
            policy_evaluation: PolicyEvaluation with violation details

        Returns:
            Created Ticket instance
        """
        # Fetch policy rule to get severity
        from app.models import PolicyRule
        policy_rule = self.db.query(PolicyRule).filter(
            PolicyRule.id == policy_evaluation.policy_rule_id
        ).first()

        if not policy_rule:
            logger.warning(f"Policy rule not found: {policy_evaluation.policy_rule_id}")
            return None

        # Only create ticket for HIGH/CRITICAL severity
        if policy_rule.severity not in [PolicySeverity.HIGH, PolicySeverity.CRITICAL]:
            return None

        # Map severity to priority
        priority_map = {
            PolicySeverity.HIGH: TicketPriority.HIGH,
            PolicySeverity.CRITICAL: TicketPriority.URGENT
        }

        ticket = Ticket(
            receipt_id=receipt.id,
            ticket_type="policy_violation",
            priority=priority_map.get(policy_rule.severity, TicketPriority.MEDIUM),
            status=TicketStatus.OPEN,
            title=f"Policy violation: {policy_rule.name}",
            description=f"Receipt flagged for policy violation: {policy_rule.name}\n\n"
                       f"Details: {policy_evaluation.details}",
            ticket_metadata={
                "policy_code": policy_rule.code,
                "policy_name": policy_rule.name,
                "severity": policy_rule.severity.value,
                "violation_details": policy_evaluation.details,
                "receipt_id": receipt.id,
                "user_id": receipt.user_id
            },
            correlation_id=uuid.UUID(self.correlation_id),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(ticket)
        self.db.flush()

        # Link ticket to policy evaluation
        policy_evaluation.ticket_id = ticket.id

        logger.info(f"Created policy violation ticket: ticket_id={ticket.id}, policy={policy_rule.code}")

        return ticket
