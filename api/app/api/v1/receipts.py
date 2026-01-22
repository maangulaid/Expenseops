from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_user_roles
from app.core.rbac import check_user_role
from app.middleware.correlation_id import get_correlation_id
from app.models.user import User
from app.models.receipt import Receipt, ReceiptStatus
from app.services.receipt_service import ReceiptService
from app.schemas.receipt import (
    ReceiptUploadResponse,
    ReceiptResponse,
    ReceiptListResponse,
    ReprocessRequest
)
from app.config import settings
from app.core.logging import get_logger
from typing import List, Optional
import hashlib

router = APIRouter(prefix="/receipts", tags=["receipts"])
logger = get_logger(__name__)


@router.post("/", response_model=ReceiptUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Upload a receipt with idempotency.

    Flow:
    1. Validate file type and size
    2. Compute SHA256 hash
    3. Check for duplicate (user_id + hash)
    4. If duplicate: return existing receipt
    5. If new: upload to MinIO, create DB record, enqueue task

    Returns:
    - 202 Accepted with receipt_id and status
    """
    correlation_id = get_correlation_id(request)

    # Validate file type
    if file.content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_FILE_TYPES)}"
        )

    # Read file content
    file_content = await file.read()

    # Validate file size
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert to bytes
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Compute SHA256 hash for idempotency
    source_sha256 = hashlib.sha256(file_content).hexdigest()

    # Check for existing receipt (idempotency)
    existing = db.query(Receipt).filter(
        Receipt.user_id == current_user.id,
        Receipt.source_sha256 == source_sha256
    ).first()

    if existing:
        logger.info(
            f"Duplicate receipt detected: receipt_id={existing.id}",
            extra={"receipt_id": existing.id, "correlation_id": correlation_id}
        )
        return ReceiptUploadResponse(
            receipt_id=existing.id,
            status=existing.status,
            message="Receipt already exists (idempotent)",
            correlation_id=correlation_id
        )

    # Process new upload
    receipt_service = ReceiptService(db, correlation_id)

    try:
        receipt = receipt_service.process_upload(
            user_id=current_user.id,
            file_content=file_content,
            filename=file.filename or "unknown",
            content_type=file.content_type,
            source_sha256=source_sha256
        )

        return ReceiptUploadResponse(
            receipt_id=receipt.id,
            status=receipt.status,
            message="Receipt uploaded and queued for processing",
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload receipt"
        )


@router.get("/", response_model=List[ReceiptListResponse])
async def list_receipts(
    status_filter: Optional[ReceiptStatus] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    List receipts.

    - Regular users: see only their own receipts
    - Support/Admin: see all receipts
    """
    correlation_id = get_correlation_id(request)
    receipt_service = ReceiptService(db, correlation_id)

    user_roles = get_user_roles(current_user)
    is_support_or_admin = any(role in user_roles for role in ['support', 'admin'])

    # Regular users can only see their own receipts
    user_id_filter = None if is_support_or_admin else current_user.id

    receipts = receipt_service.list_receipts(
        user_id=user_id_filter,
        status=status_filter,
        limit=limit,
        offset=offset
    )

    return [
        ReceiptListResponse(
            id=r.id,
            user_id=r.user_id,
            original_filename=r.original_filename,
            status=r.status,
            merchant_name=r.merchant_name,
            total_amount=r.total_amount,
            uploaded_at=r.uploaded_at
        )
        for r in receipts
    ]


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Get receipt details by ID.

    - Regular users: can only access their own receipts
    - Support/Admin: can access any receipt
    """
    correlation_id = get_correlation_id(request)
    receipt_service = ReceiptService(db, correlation_id)

    user_roles = get_user_roles(current_user)
    is_support_or_admin = any(role in user_roles for role in ['support', 'admin'])

    # Regular users can only see their own receipts
    user_id_filter = None if is_support_or_admin else current_user.id

    receipt = receipt_service.get_receipt(receipt_id, user_id=user_id_filter)

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found"
        )

    return receipt


@router.post("/{receipt_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_receipt(
    receipt_id: int,
    request_data: ReprocessRequest = ReprocessRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Reprocess a receipt (support/admin only).

    Transitions receipt back to QUEUED and increments processing_version.
    """
    # Check role (support or admin only)
    check_user_role(current_user, "support", "admin")

    correlation_id = get_correlation_id(request)
    receipt_service = ReceiptService(db, correlation_id)

    try:
        receipt = receipt_service.reprocess_receipt(
            receipt_id=receipt_id,
            user_id=current_user.id,
            clear_extracted_data=request_data.clear_extracted_data
        )

        return {
            "receipt_id": receipt.id,
            "status": receipt.status,
            "processing_version": receipt.processing_version,
            "message": "Receipt requeued for processing",
            "correlation_id": correlation_id
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Reprocess failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess receipt"
        )


@router.get("/{receipt_id}/events")
async def get_receipt_events(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit trail for a receipt.

    Returns all receipt_events ordered by created_at.
    """
    from app.models.receipt_event import ReceiptEvent

    # Check access (same as get_receipt)
    user_roles = get_user_roles(current_user)
    is_support_or_admin = any(role in user_roles for role in ['support', 'admin'])

    if not is_support_or_admin:
        # Verify receipt belongs to user
        receipt = db.query(Receipt).filter(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id
        ).first()
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receipt not found"
            )

    # Fetch events
    events = db.query(ReceiptEvent).filter(
        ReceiptEvent.receipt_id == receipt_id
    ).order_by(ReceiptEvent.created_at).all()

    return [
        {
            "id": e.id,
            "from_status": e.from_status.value if e.from_status else None,
            "to_status": e.to_status.value,
            "event_type": e.event_type,
            "message": e.message,
            "metadata": e.event_metadata,
            "correlation_id": str(e.correlation_id),
            "triggered_by_system": e.triggered_by_system,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]
