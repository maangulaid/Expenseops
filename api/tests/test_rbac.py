"""
Tests for role-based access control (RBAC).
"""
import pytest
from fastapi import status


def test_user_can_only_access_own_receipts(client, auth_headers, admin_headers, sample_receipt_bytes, db_session):
    """Test that users can only see their own receipts."""
    from io import BytesIO

    # Admin uploads a receipt
    response = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=admin_headers
    )
    admin_receipt_id = response.json()["receipt_id"]

    # Regular user tries to access admin's receipt
    response = client.get(
        f"/api/v1/receipts/{admin_receipt_id}",
        headers=auth_headers
    )

    # Should return 404 (not found) for security
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_user_cannot_access_admin_endpoints(client, auth_headers):
    """Test that regular users cannot access admin-only endpoints."""

    # Try to access policies endpoint (admin only)
    response = client.get(
        "/api/v1/policies",
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "admin" in response.json()["detail"].lower()


def test_user_cannot_access_support_endpoints(client, auth_headers):
    """Test that regular users cannot access support endpoints."""

    # Try to access tickets endpoint (support+ only)
    response = client.get(
        "/api/v1/tickets",
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_access_all_endpoints(client, admin_headers):
    """Test that admin can access all endpoints."""

    # Policies (admin only)
    response = client.get("/api/v1/policies", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK

    # Tickets (support+)
    response = client.get("/api/v1/tickets", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK


def test_user_cannot_reprocess(client, auth_headers, sample_receipt_bytes):
    """Test that regular users cannot reprocess receipts."""
    from io import BytesIO

    # Upload receipt as user
    response = client.post(
        "/api/v1/receipts",
        files={"file": ("receipt.png", BytesIO(sample_receipt_bytes), "image/png")},
        headers=auth_headers
    )
    receipt_id = response.json()["receipt_id"]

    # Try to reprocess (support+ only)
    response = client.post(
        f"/api/v1/receipts/{receipt_id}/reprocess",
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
