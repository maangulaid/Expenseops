from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import check_user_role
from app.models.user import User
from app.models.policy import PolicyRule
from app.schemas.policy import PolicyRuleCreate, PolicyRuleUpdate, PolicyRuleResponse
from typing import List
from datetime import datetime

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=List[PolicyRuleResponse])
async def list_policies(
    is_active: bool = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all policy rules (admin only).

    Can filter by is_active status.
    """
    check_user_role(current_user, "admin")

    query = db.query(PolicyRule)

    if is_active is not None:
        query = query.filter(PolicyRule.is_active == is_active)

    policies = query.order_by(PolicyRule.code).all()

    return policies


@router.post("/", response_model=PolicyRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new policy rule (admin only).
    """
    check_user_role(current_user, "admin")

    # Check if code already exists
    existing = db.query(PolicyRule).filter(PolicyRule.code == policy_data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Policy with code '{policy_data.code}' already exists"
        )

    policy = PolicyRule(
        code=policy_data.code,
        name=policy_data.name,
        description=policy_data.description,
        severity=policy_data.severity,
        config=policy_data.config,
        is_active=policy_data.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(policy)
    db.commit()
    db.refresh(policy)

    return policy


@router.get("/{policy_id}", response_model=PolicyRuleResponse)
async def get_policy(
    policy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get policy rule by ID (admin only).
    """
    check_user_role(current_user, "admin")

    policy = db.query(PolicyRule).filter(PolicyRule.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    return policy


@router.patch("/{policy_id}", response_model=PolicyRuleResponse)
async def update_policy(
    policy_id: int,
    policy_data: PolicyRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update policy rule (admin only).

    Allows changing:
    - name
    - description
    - severity
    - config (runtime policy changes!)
    - is_active (enable/disable)
    """
    check_user_role(current_user, "admin")

    policy = db.query(PolicyRule).filter(PolicyRule.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    # Update fields
    if policy_data.name is not None:
        policy.name = policy_data.name

    if policy_data.description is not None:
        policy.description = policy_data.description

    if policy_data.severity is not None:
        policy.severity = policy_data.severity

    if policy_data.config is not None:
        policy.config = policy_data.config

    if policy_data.is_active is not None:
        policy.is_active = policy_data.is_active

    policy.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(policy)

    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete (deactivate) policy rule (admin only).

    Sets is_active = False instead of deleting.
    """
    check_user_role(current_user, "admin")

    policy = db.query(PolicyRule).filter(PolicyRule.id == policy_id).first()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    policy.is_active = False
    policy.updated_at = datetime.utcnow()

    db.commit()

    return None
