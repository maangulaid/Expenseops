"""
Main receipt processing task with OCR, extraction, and policy evaluation.

Includes:
- Retry logic with exponential backoff
- Failure handling → FAILED status + ticket creation
- State machine transitions with audit trail
- Policy evaluation
"""
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from app.celery_app import celery_app
from app.core.database import get_db
from app.models import Receipt, ReceiptEvent, ReceiptStatus
from app.services.ocr_service import OCRService
from app.services.extraction_service import ExtractionService
from app.services.storage_service import StorageService
from app.services.policy_service import PolicyService
from app.services.ticket_service import TicketService
from app.config import settings
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class ReceiptProcessingTask(Task):
    """
    Custom task class with retry configuration.

    Retry policy:
    - Max retries: 3 (configurable)
    - Backoff: Exponential (60s, 120s, 240s...)
    - Jitter: Enabled for distributed load
    """

    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': settings.CELERY_MAX_RETRIES}
    retry_backoff = True  # Exponential backoff
    retry_backoff_max = 600  # Max 10 minutes
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=ReceiptProcessingTask,
    name="app.tasks.process_receipt.process_receipt_task"
)
def process_receipt_task(self, receipt_id: int, correlation_id: str):
    """
    Process receipt with OCR and data extraction.

    Flow:
    1. QUEUED → PROCESSING
    2. Download from MinIO
    3. OCR extraction
    4. Parse structured data
    5. Evaluate policies
    6. PROCESSING → COMPLETED/FLAGGED/FAILED

    Args:
        receipt_id: Receipt ID to process
        correlation_id: Correlation ID for tracing

    Raises:
        Exception: On processing failure (triggers retry)
    """
    db = get_db()

    try:
        # Fetch receipt
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            logger.error(f"Receipt {receipt_id} not found")
            return {"status": "error", "message": "Receipt not found"}

        # Check if already processed (idempotent - avoid reprocessing)
        if receipt.status in [ReceiptStatus.COMPLETED, ReceiptStatus.FLAGGED]:
            logger.info(f"Receipt {receipt_id} already processed, skipping")
            return {"status": "skipped", "message": "Already processed"}

        # Transition to PROCESSING
        _create_event(
            db,
            receipt_id=receipt.id,
            from_status=ReceiptStatus.QUEUED,
            to_status=ReceiptStatus.PROCESSING,
            event_type="worker_start",
            correlation_id=correlation_id,
            message=f"Worker task {self.request.id} started processing"
        )
        receipt.status = ReceiptStatus.PROCESSING
        db.commit()

        logger.info(f"Processing receipt {receipt_id}", extra={"correlation_id": correlation_id})

        # Download file from MinIO
        storage = StorageService()
        file_content = storage.download(receipt.minio_key)

        # OCR extraction
        logger.info(f"Starting OCR for receipt {receipt_id}")
        ocr = OCRService(languages=['en'], gpu=False)
        raw_text = ocr.extract_text(file_content)
        receipt.raw_ocr_text = raw_text

        _create_event(
            db,
            receipt_id=receipt.id,
            from_status=ReceiptStatus.PROCESSING,
            to_status=ReceiptStatus.PROCESSING,
            event_type="ocr_complete",
            correlation_id=correlation_id,
            message=f"OCR extracted {len(raw_text)} characters",
            metadata={"text_length": len(raw_text)}
        )

        logger.info(f"OCR complete for receipt {receipt_id}, extracted {len(raw_text)} chars")

        # Extract structured data
        logger.info(f"Starting extraction for receipt {receipt_id}")
        extractor = ExtractionService()
        extracted = extractor.parse(raw_text)

        receipt.merchant_name = extracted.get("merchant_name")
        receipt.total_amount = extracted.get("total_amount")
        receipt.transaction_date = extracted.get("transaction_date")
        receipt.currency = extracted.get("currency", "USD")

        _create_event(
            db,
            receipt_id=receipt.id,
            from_status=ReceiptStatus.PROCESSING,
            to_status=ReceiptStatus.PROCESSING,
            event_type="extraction_complete",
            correlation_id=correlation_id,
            message="Data extraction complete",
            metadata={
                "merchant_name": receipt.merchant_name,
                "total_amount": float(receipt.total_amount) if receipt.total_amount else None,
                "transaction_date": str(receipt.transaction_date) if receipt.transaction_date else None,
                "confidence_score": extracted.get("confidence_score")
            }
        )

        logger.info(
            f"Extraction complete for receipt {receipt_id}: "
            f"merchant={receipt.merchant_name}, amount={receipt.total_amount}"
        )

        # Policy evaluation
        logger.info(f"Evaluating policies for receipt {receipt_id}")
        policy_service = PolicyService(db, correlation_id)
        violations = policy_service.evaluate_receipt(receipt)

        # Determine final status
        if violations:
            final_status = ReceiptStatus.FLAGGED
            logger.warning(f"Receipt {receipt_id} flagged with {len(violations)} policy violations")

            # Create tickets for HIGH/CRITICAL violations
            ticket_service = TicketService(db, correlation_id)
            tickets_created = 0

            for violation in violations:
                ticket = ticket_service.create_policy_violation_ticket(receipt, violation)
                if ticket:
                    tickets_created += 1

            _create_event(
                db,
                receipt_id=receipt.id,
                from_status=ReceiptStatus.PROCESSING,
                to_status=final_status,
                event_type="policy_flagged",
                correlation_id=correlation_id,
                message=f"Receipt flagged: {len(violations)} violations, {tickets_created} tickets created",
                metadata={
                    "violations_count": len(violations),
                    "tickets_created": tickets_created
                }
            )
        else:
            final_status = ReceiptStatus.COMPLETED
            logger.info(f"Receipt {receipt_id} completed successfully")

            _create_event(
                db,
                receipt_id=receipt.id,
                from_status=ReceiptStatus.PROCESSING,
                to_status=final_status,
                event_type="worker_complete",
                correlation_id=correlation_id,
                message="Processing completed successfully"
            )

        # Update receipt status
        receipt.status = final_status
        receipt.processed_at = datetime.utcnow()

        db.commit()

        logger.info(
            f"Receipt {receipt_id} processing complete: status={final_status.value}",
            extra={"correlation_id": correlation_id}
        )

        return {
            "status": "success",
            "receipt_id": receipt_id,
            "final_status": final_status.value,
            "violations": len(violations) if violations else 0
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            f"Error processing receipt {receipt_id}: {exc}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )

        # Retry logic
        try:
            # Calculate backoff
            countdown = settings.CELERY_RETRY_BACKOFF_BASE * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

        except MaxRetriesExceededError:
            # All retries exhausted - mark as FAILED and create ticket
            logger.error(
                f"Max retries exceeded for receipt {receipt_id}",
                extra={"correlation_id": correlation_id}
            )

            receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
            if receipt:
                # Mark as FAILED
                receipt.status = ReceiptStatus.FAILED
                receipt.processed_at = datetime.utcnow()

                # Create failure event
                _create_event(
                    db,
                    receipt_id=receipt.id,
                    from_status=ReceiptStatus.PROCESSING,
                    to_status=ReceiptStatus.FAILED,
                    event_type="failure",
                    correlation_id=correlation_id,
                    message=f"Processing failed after {self.max_retries} retries: {str(exc)}",
                    metadata={
                        "error": str(exc),
                        "task_id": self.request.id,
                        "retries": self.request.retries
                    }
                )

                # Create failure ticket
                ticket_service = TicketService(db, correlation_id)
                ticket_service.create_processing_failure_ticket(
                    receipt=receipt,
                    error_message=str(exc),
                    task_id=self.request.id
                )

                db.commit()

                logger.info(
                    f"Receipt {receipt_id} marked as FAILED, ticket created",
                    extra={"correlation_id": correlation_id}
                )

            return {
                "status": "failed",
                "receipt_id": receipt_id,
                "error": str(exc)
            }

    finally:
        db.close()


def _create_event(
    db,
    receipt_id: int,
    from_status: ReceiptStatus,
    to_status: ReceiptStatus,
    event_type: str,
    correlation_id: str,
    message: str = None,
    metadata: dict = None
):
    """Helper to create receipt event."""
    event = ReceiptEvent(
        receipt_id=receipt_id,
        from_status=from_status,
        to_status=to_status,
        event_type=event_type,
        correlation_id=uuid.UUID(correlation_id),
        message=message,
        event_metadata=metadata,
        triggered_by_system="celery_worker",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.flush()
