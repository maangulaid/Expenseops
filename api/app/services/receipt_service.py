from sqlalchemy.orm import Session
from app.models.receipt import Receipt, ReceiptStatus
from app.services.state_machine import ReceiptStateMachine
from app.services.storage_service import StorageService
from app.core.logging import get_logger
from datetime import datetime
from typing import Optional
import hashlib

logger = get_logger(__name__)


class ReceiptService:
    """
    Service for receipt operations with idempotency and state management.

    Handles:
    - Idempotent upload (checks user_id + source_sha256)
    - File storage via MinIO
    - State transitions via state machine
    - Task enqueuing for worker processing
    """

    def __init__(self, db: Session, correlation_id: str):
        """
        Initialize receipt service.

        Args:
            db: SQLAlchemy session
            correlation_id: Correlation ID for tracing
        """
        self.db = db
        self.correlation_id = correlation_id
        self.state_machine = ReceiptStateMachine(db, correlation_id)
        self.storage = StorageService()
        self.logger = logger

    def process_upload(
        self,
        user_id: int,
        file_content: bytes,
        filename: str,
        content_type: str,
        source_sha256: str
    ) -> Receipt:
        """
        Process receipt upload with full idempotency.

        Flow:
        1. Upload to MinIO
        2. Create receipt record (QUEUED status)
        3. Create initial receipt_event
        4. Enqueue Celery task
        5. Return receipt

        Args:
            user_id: User ID
            file_content: File bytes
            filename: Original filename
            content_type: MIME type
            source_sha256: SHA256 hash of file content (for idempotency)

        Returns:
            Receipt instance

        Raises:
            Exception: On upload or database error
        """
        try:
            # Generate safe MinIO key
            minio_key = self.storage.generate_safe_key(user_id, filename)

            # Upload to MinIO
            self.storage.upload(
                key=minio_key,
                data=file_content,
                content_type=content_type
            )

            # Create receipt record
            receipt = Receipt(
                user_id=user_id,
                source_sha256=source_sha256,
                minio_key=minio_key,
                original_filename=filename,
                mime_type=content_type,
                file_size_bytes=len(file_content),
                status=ReceiptStatus.QUEUED,
                processing_version=1,
                uploaded_at=datetime.utcnow()
            )

            self.db.add(receipt)
            self.db.flush()  # Get receipt.id

            # Create initial event (upload complete)
            # Don't use state_machine.transition() here since receipt is already QUEUED
            # and QUEUED → QUEUED is not a valid transition
            from app.models.receipt_event import ReceiptEvent
            import uuid as uuid_lib

            event = ReceiptEvent(
                receipt_id=receipt.id,
                from_status=None,  # Initial event, no previous status
                to_status=ReceiptStatus.QUEUED,
                correlation_id=uuid_lib.UUID(self.correlation_id) if isinstance(self.correlation_id, str) else self.correlation_id,
                event_type="upload_complete",
                message=f"Receipt uploaded: {filename} ({len(file_content)} bytes)",
                event_metadata={
                    "filename": filename,
                    "mime_type": content_type,
                    "file_size_bytes": len(file_content)
                },
                triggered_by_user_id=user_id,
                triggered_by_system=None
            )

            self.db.add(event)
            self.db.commit()

            # Enqueue Celery task for processing
            self._enqueue_processing_task(receipt.id)

            self.logger.info(
                f"Receipt uploaded successfully: receipt_id={receipt.id}, user_id={user_id}",
                extra={"receipt_id": receipt.id, "correlation_id": self.correlation_id}
            )

            return receipt

        except Exception as e:
            self.db.rollback()
            self.logger.error(
                f"Error processing upload: {e}",
                extra={"user_id": user_id, "correlation_id": self.correlation_id},
                exc_info=True
            )
            raise

    def _enqueue_processing_task(self, receipt_id: int) -> None:
        """
        Enqueue Celery task for receipt processing.

        Args:
            receipt_id: Receipt ID to process
        """
        try:
            # Import here to avoid circular dependency
            from app.tasks.celery_app import celery_app

            celery_app.send_task(
                'app.tasks.process_receipt.process_receipt_task',
                args=[receipt_id, self.correlation_id],
                queue='receipts'
            )

            self.logger.info(
                f"Enqueued processing task for receipt_id={receipt_id}",
                extra={"receipt_id": receipt_id, "correlation_id": self.correlation_id}
            )

        except Exception as e:
            self.logger.error(
                f"Error enqueuing task: {e}",
                extra={"receipt_id": receipt_id, "correlation_id": self.correlation_id},
                exc_info=True
            )
            # Don't raise - receipt is already stored, worker can be triggered manually

    def get_receipt(self, receipt_id: int, user_id: Optional[int] = None) -> Optional[Receipt]:
        """
        Get receipt by ID with optional user filtering.

        Args:
            receipt_id: Receipt ID
            user_id: If provided, filter by user_id (for non-admin users)

        Returns:
            Receipt instance or None if not found
        """
        query = self.db.query(Receipt).filter(Receipt.id == receipt_id)

        if user_id is not None:
            query = query.filter(Receipt.user_id == user_id)

        return query.first()

    def list_receipts(
        self,
        user_id: Optional[int] = None,
        status: Optional[ReceiptStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Receipt]:
        """
        List receipts with filtering and pagination.

        Args:
            user_id: Filter by user_id (None = all users, for admin)
            status: Filter by status
            limit: Max results
            offset: Results offset

        Returns:
            List of Receipt instances
        """
        query = self.db.query(Receipt)

        if user_id is not None:
            query = query.filter(Receipt.user_id == user_id)

        if status is not None:
            query = query.filter(Receipt.status == status)

        query = query.order_by(Receipt.uploaded_at.desc())
        query = query.limit(limit).offset(offset)

        return query.all()

    def reprocess_receipt(
        self,
        receipt_id: int,
        user_id: int,
        clear_extracted_data: bool = False
    ) -> Receipt:
        """
        Reprocess a receipt (support/admin only - enforce in route).

        Args:
            receipt_id: Receipt ID
            user_id: User requesting reprocess (for audit)
            clear_extracted_data: Whether to clear extracted fields

        Returns:
            Updated receipt

        Raises:
            ValueError: If receipt cannot be reprocessed
        """
        receipt = self.db.query(Receipt).filter(Receipt.id == receipt_id).first()

        if not receipt:
            raise ValueError(f"Receipt {receipt_id} not found")

        # Clear extracted data if requested
        if clear_extracted_data:
            receipt.merchant_name = None
            receipt.total_amount = None
            receipt.transaction_date = None
            receipt.raw_ocr_text = None

        # Transition to QUEUED (state machine will increment processing_version)
        self.state_machine.transition(
            receipt=receipt,
            to_status=ReceiptStatus.QUEUED,
            event_type="reprocess_requested",
            message="Receipt reprocess requested by user",
            triggered_by_user_id=user_id,
            metadata={"clear_extracted_data": clear_extracted_data}
        )

        self.db.commit()

        # Enqueue new processing task
        self._enqueue_processing_task(receipt_id)

        self.logger.info(
            f"Receipt reprocess initiated: receipt_id={receipt_id}, version={receipt.processing_version}",
            extra={"receipt_id": receipt_id, "correlation_id": self.correlation_id}
        )

        return receipt
