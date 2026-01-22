from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.policy import PolicySeverity


class PolicyRuleCreate(BaseModel):
    """Schema for creating a policy rule."""
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    severity: PolicySeverity
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PolicyRuleUpdate(BaseModel):
    """Schema for updating a policy rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[PolicySeverity] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PolicyRuleResponse(BaseModel):
    """Schema for policy rule response."""
    id: int
    code: str
    name: str
    description: Optional[str]
    severity: PolicySeverity
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PolicyEvaluationResponse(BaseModel):
    """Schema for policy evaluation response."""
    id: int
    receipt_id: int
    policy_rule_id: int
    passed: bool
    evaluated_at: datetime
    details: Optional[Dict[str, Any]]
    correlation_id: str

    class Config:
        from_attributes = True
