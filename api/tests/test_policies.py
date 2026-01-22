"""
Tests for policy management endpoints.
"""
import pytest
from fastapi import status


def test_create_policy(client, admin_headers):
    """Test creating a new policy rule."""

    response = client.post(
        "/api/v1/policies",
        json={
            "code": "TEST_POLICY",
            "name": "Test Policy",
            "description": "A test policy",
            "severity": "MEDIUM",
            "config": {"test_value": 100},
            "is_active": True
        },
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["code"] == "TEST_POLICY"
    assert data["config"]["test_value"] == 100


def test_list_policies(client, admin_headers):
    """Test listing policy rules."""

    response = client.get("/api/v1/policies", headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    # Should have seeded policies (MAX_AMOUNT, DUPLICATE_RECEIPT, MISSING_MERCHANT)
    assert len(data) >= 3


def test_update_policy_config(client, admin_headers, db_session):
    """Test updating policy configuration (runtime config change)."""
    from app.models.policy import PolicyRule

    # Get existing policy
    policy = db_session.query(PolicyRule).filter(
        PolicyRule.code == "MAX_AMOUNT"
    ).first()

    # Update config
    response = client.patch(
        f"/api/v1/policies/{policy.id}",
        json={
            "config": {"max_amount": 500.00}  # Change threshold
        },
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["config"]["max_amount"] == 500.00


def test_deactivate_policy(client, admin_headers, db_session):
    """Test deactivating a policy."""
    from app.models.policy import PolicyRule

    policy = db_session.query(PolicyRule).first()

    response = client.delete(
        f"/api/v1/policies/{policy.id}",
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's deactivated
    db_session.refresh(policy)
    assert policy.is_active == False


def test_non_admin_cannot_manage_policies(client, auth_headers):
    """Test that non-admin users cannot manage policies."""

    # Try to create policy
    response = client.post(
        "/api/v1/policies",
        json={
            "code": "TEST",
            "name": "Test",
            "severity": "LOW",
            "config": {}
        },
        headers=auth_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
