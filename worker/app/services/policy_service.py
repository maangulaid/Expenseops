"""
Policy evaluation service for worker.

Evaluates receipts against active policy rules and creates violations.
"""
from sqlalchemy.orm import Session
from app.models import Receipt, PolicyRule, PolicyEvaluation, PolicySeverity
from datetime import datetime, timedelta
from typing import List
import logging
import uuid

logger = logging.getLogger(__name__)


class PolicyService:
    """
    Evaluate receipts against policy rules.

    Policies:
    - MAX_AMOUNT: Check if total_amount exceeds threshold
    - DUPLICATE_RECEIPT: Check for similar receipts in time window
    - MISSING_MERCHANT: Check if merchant_name was extracted
    """

    def __init__(self, db: Session, correlation_id: str):
        self.db = db
        self.correlation_id = correlation_id

    def evaluate_receipt(self, receipt: Receipt) -> List[PolicyEvaluation]:
        """
        Evaluate all active policies against receipt.

        Returns:
            List of failed PolicyEvaluation objects
        """
        violations = []

        # Fetch active policies
        policies = self.db.query(PolicyRule).filter(
            PolicyRule.is_active == True
        ).all()

        for policy in policies:
            evaluation = self._evaluate_policy(receipt, policy)
            self.db.add(evaluation)

            if not evaluation.passed:
                violations.append(evaluation)
                logger.warning(
                    f"Policy violation: {policy.code} for receipt_id={receipt.id}"
                )

        self.db.flush()
        return violations

    def _evaluate_policy(self, receipt: Receipt, policy: PolicyRule) -> PolicyEvaluation:
        """Evaluate single policy rule."""

        if policy.code == "MAX_AMOUNT":
            return self._check_max_amount(receipt, policy)
        elif policy.code == "DUPLICATE_RECEIPT":
            return self._check_duplicate(receipt, policy)
        elif policy.code == "MISSING_MERCHANT":
            return self._check_missing_merchant(receipt, policy)
        else:
            # Unknown policy - log and pass
            logger.warning(f"Unknown policy code: {policy.code}")
            return PolicyEvaluation(
                receipt_id=receipt.id,
                policy_rule_id=policy.id,
                passed=True,
                correlation_id=uuid.UUID(self.correlation_id),
                details={"note": "Unknown policy, skipped"}
            )

    def _check_max_amount(self, receipt: Receipt, policy: PolicyRule) -> PolicyEvaluation:
        """Check if receipt amount exceeds threshold."""
        max_amount = policy.config.get("max_amount", 1000.00)

        if receipt.total_amount and float(receipt.total_amount) > max_amount:
            return PolicyEvaluation(
                receipt_id=receipt.id,
                policy_rule_id=policy.id,
                passed=False,
                correlation_id=uuid.UUID(self.correlation_id),
                details={
                    "detected_amount": float(receipt.total_amount),
                    "threshold": max_amount,
                    "violation": "Amount exceeds policy limit"
                }
            )

        return PolicyEvaluation(
            receipt_id=receipt.id,
            policy_rule_id=policy.id,
            passed=True,
            correlation_id=uuid.UUID(self.correlation_id),
            details={"amount": float(receipt.total_amount) if receipt.total_amount else None}
        )

    def _check_duplicate(self, receipt: Receipt, policy: PolicyRule) -> PolicyEvaluation:
        """Check for duplicate receipts within time window."""
        look_back_days = policy.config.get("look_back_days", 90)
        cutoff_date = datetime.utcnow() - timedelta(days=look_back_days)

        # Find similar receipts (same merchant, similar amount, recent)
        similar = self.db.query(Receipt).filter(
            Receipt.user_id == receipt.user_id,
            Receipt.id != receipt.id,
            Receipt.merchant_name == receipt.merchant_name,
            Receipt.uploaded_at >= cutoff_date
        ).all()

        # Check for amount similarity (within 5%)
        duplicates = []
        if receipt.total_amount:
            for r in similar:
                if r.total_amount:
                    diff_percent = abs(float(r.total_amount - receipt.total_amount)) / float(receipt.total_amount) * 100
                    if diff_percent < 5.0:
                        duplicates.append(r.id)

        if duplicates:
            return PolicyEvaluation(
                receipt_id=receipt.id,
                policy_rule_id=policy.id,
                passed=False,
                correlation_id=uuid.UUID(self.correlation_id),
                details={
                    "duplicate_receipt_ids": duplicates,
                    "look_back_days": look_back_days,
                    "violation": "Potential duplicate receipt detected"
                }
            )

        return PolicyEvaluation(
            receipt_id=receipt.id,
            policy_rule_id=policy.id,
            passed=True,
            correlation_id=uuid.UUID(self.correlation_id)
        )

    def _check_missing_merchant(self, receipt: Receipt, policy: PolicyRule) -> PolicyEvaluation:
        """Check if merchant name was extracted."""
        required = policy.config.get("required", True)

        if required and not receipt.merchant_name:
            return PolicyEvaluation(
                receipt_id=receipt.id,
                policy_rule_id=policy.id,
                passed=False,
                correlation_id=uuid.UUID(self.correlation_id),
                details={"violation": "Merchant name not extracted"}
            )

        return PolicyEvaluation(
            receipt_id=receipt.id,
            policy_rule_id=policy.id,
            passed=True,
            correlation_id=uuid.UUID(self.correlation_id)
        )
