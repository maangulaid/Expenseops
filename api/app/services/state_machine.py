from sqlalchemy.orm import Session
from app.models.receipt import Receipt, ReceiptStatus
from app.models.receipt_event import ReceiptEvent
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class ReceiptStateMachine:
    """
    State machine for receipt status transitions with automatic audit trail.

    Valid transitions:
    - QUEUED → PROCESSING (worker starts)
    - PROCESSING → COMPLETED (success, no violations)
    - PROCESSING → FLAGGED (success with policy violations)
    - PROCESSING → FAILED (retries exhausted)
    - COMPLETED → QUEUED (reprocess)
    - FLAGGED → QUEUED (reprocess)
    - FAILED → QUEUED (reprocess)
    """

    VALID_TRANSITIONS = {
        ReceiptStatus.QUEUED: [ReceiptStatus.PROCESSING],
        ReceiptStatus.PROCESSING: [
            ReceiptStatus.COMPLETED,
            ReceiptStatus.FLAGGED,
            ReceiptStatus.FAILED
        ],
        ReceiptStatus.COMPLETED: [ReceiptStatus.QUEUED],
        ReceiptStatus.FLAGGED: [ReceiptStatus.QUEUED],
        ReceiptStatus.FAILED: [ReceiptStatus.QUEUED],
    }

    def __init__(self, db: Session, correlation_id: str):
        """
        Initialize state machine.

        Args:
            db: SQLAlchemy database session
            correlation_id: Correlation ID for tracing
        """
        self.db = db
        self.correlation_id = correlation_id

    def transition(
        self,
        receipt: Receipt,
        to_status: ReceiptStatus,
        event_type: str,
        message: Optional[str] = None,
        triggered_by_user_id: Optional[int] = None,
        triggered_by_system: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition receipt to new status with audit event.

        Args:
            receipt: Receipt instance to transition
            to_status: Target status
            event_type: Event type identifier
            message: Human-readable message
            triggered_by_user_id: User ID if triggered by user action
            triggered_by_system: System name if triggered by system
            metadata: Additional context data

        Returns:
            True if transition successful

        Raises:
            ValueError: If transition is invalid
        """
        from_status = receipt.status

        # Validate transition
        if to_status not in self.VALID_TRANSITIONS.get(from_status, []):
            raise ValueError(
                f"Invalid state transition: {from_status.value} → {to_status.value}"
            )

        # Update receipt status
        receipt.status = to_status
        receipt.updated_at = datetime.utcnow()

        # Handle reprocessing (increment version when returning to QUEUED)
        if to_status == ReceiptStatus.QUEUED and from_status != ReceiptStatus.QUEUED:
            receipt.processing_version += 1

        # Mark as processed when reaching terminal states
        if to_status in [ReceiptStatus.COMPLETED, ReceiptStatus.FLAGGED, ReceiptStatus.FAILED]:
            if not receipt.processed_at:
                receipt.processed_at = datetime.utcnow()

        # Create audit event
        event = ReceiptEvent(
            receipt_id=receipt.id,
            from_status=from_status if from_status != to_status else None,
            to_status=to_status,
            correlation_id=uuid.UUID(self.correlation_id) if isinstance(self.correlation_id, str) else self.correlation_id,
            event_type=event_type,
            message=message,
            event_metadata=metadata,
            triggered_by_user_id=triggered_by_user_id,
            triggered_by_system=triggered_by_system
        )

        self.db.add(event)
        self.db.flush()

        return True

    def can_transition(self, receipt: Receipt, to_status: ReceiptStatus) -> bool:
        """
        Check if transition is valid without executing it.

        Args:
            receipt: Receipt instance
            to_status: Target status

        Returns:
            True if transition is allowed, False otherwise
        """
        from_status = receipt.status
        return to_status in self.VALID_TRANSITIONS.get(from_status, [])
