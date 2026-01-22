from pydantic import BaseModel, Field, UUID4
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from app.models.receipt import ReceiptStatus


class ReceiptUploadResponse(BaseModel):
    """Schema for receipt upload response (202 Accepted)."""
    receipt_id: int
    status: ReceiptStatus
    message: str
    correlation_id: str


class ReceiptResponse(BaseModel):
    """Schema for receipt detail response."""
    id: int
    user_id: int
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: ReceiptStatus
    processing_version: int

    # Extracted data
    merchant_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    transaction_date: Optional[date] = None
    currency: Optional[str] = "USD"

    # Timestamps
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    """Schema for receipt list item."""
    id: int
    user_id: int
    original_filename: str
    status: ReceiptStatus
    merchant_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ReprocessRequest(BaseModel):
    """Schema for reprocess request."""
    clear_extracted_data: bool = False
