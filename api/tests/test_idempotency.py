"""
Tests for idempotent receipt upload.
"""
import pytest
from fastapi import status
from io import BytesIO


def test_idempotent_upload_same_file(client, auth_headers, sample_receipt_bytes, db_session):
    """Test that uploading the same file twice returns the same receipt_id."""

    # First upload
    response1 = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=auth_headers
    )

    assert response1.status_code == status.HTTP_202_ACCEPTED
    data1 = response1.json()
    receipt_id_1 = data1["receipt_id"]
    assert data1["status"] == "QUEUED"

    # Second upload (same file content)
    response2 = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=auth_headers
    )

    assert response2.status_code == status.HTTP_202_ACCEPTED
    data2 = response2.json()
    receipt_id_2 = data2["receipt_id"]

    # Should return same receipt ID
    assert receipt_id_1 == receipt_id_2
    assert "already exists" in data2["message"].lower() or "idempotent" in data2["message"].lower()


def test_different_users_same_file(client, auth_headers, admin_headers, sample_receipt_bytes):
    """Test that different users can upload the same file."""

    # User 1 upload
    response1 = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=auth_headers
    )

    receipt_id_1 = response1.json()["receipt_id"]

    # User 2 (admin) upload same file
    response2 = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=admin_headers
    )

    receipt_id_2 = response2.json()["receipt_id"]

    # Should be different receipts (different users)
    assert receipt_id_1 != receipt_id_2


def test_invalid_file_type(client, auth_headers):
    """Test that invalid file types are rejected."""

    response = client.post(
        "/api/v1/receipts",
        files={"file": ("test.txt", BytesIO(b"text content"), "text/plain")},
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid file type" in response.json()["detail"].lower()
