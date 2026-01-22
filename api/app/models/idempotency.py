from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base


class IdempotencyKey(Base):
    """
    Idempotency keys for API requests.

    Stores client-provided or hash-based keys to prevent duplicate processing.
    """

    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)  # Client key or hash
    request_hash = Column(String(64))  # SHA256 of request body for extra validation
    response_status = Column(Integer)  # HTTP status code of response
    response_body = Column(JSONB)  # Cached response

    # TTL for cleanup
    created_at = Column(DateTime, nullable=False, server_default="now()")
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_idempotency_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<IdempotencyKey(id={self.id}, key='{self.key}')>"
