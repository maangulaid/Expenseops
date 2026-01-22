from functools import wraps
from fastapi import HTTPException, status
from app.core.dependencies import get_user_roles
from app.models.user import User
from typing import Callable, List


def require_roles(*allowed_roles: str) -> Callable:
    """
    Decorator to enforce RBAC on route handlers.

    Args:
        *allowed_roles: Variable number of role names that are allowed

    Usage:
        from app.core.rbac import require_roles
        from app.core.dependencies import get_current_user

        @router.get("/admin-only")
        async def admin_endpoint(current_user: User = Depends(get_current_user)):
            require_roles("admin")(lambda: None)(current_user)
            return {"message": "Admin access granted"}

        # Or use as a dependency:
        def require_admin(current_user: User = Depends(get_current_user)):
            _check_roles(current_user, ["admin"])
            return current_user
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(current_user: User, *args, **kwargs):
            user_roles = get_user_roles(current_user)

            if not any(role in user_roles for role in allowed_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Requires one of: {', '.join(allowed_roles)}"
                )

            return await func(current_user, *args, **kwargs)
        return wrapper
    return decorator


def _check_roles(user: User, required_roles: List[str]) -> None:
    """
    Check if user has any of the required roles.

    Args:
        user: User instance
        required_roles: List of acceptable role names

    Raises:
        HTTPException: 403 if user doesn't have required role
    """
    user_roles = get_user_roles(user)

    if not any(role in user_roles for role in required_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires one of: {', '.join(required_roles)}"
        )


def check_user_role(user: User, *allowed_roles: str) -> None:
    """
    Utility function to check user roles inline.

    Args:
        user: User instance
        *allowed_roles: Variable number of allowed role names

    Raises:
        HTTPException: 403 if user doesn't have any of the allowed roles

    Usage:
        from app.core.rbac import check_user_role

        @router.post("/receipts/{id}/reprocess")
        async def reprocess_receipt(
            id: int,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            check_user_role(current_user, "support", "admin")
            # ... rest of logic
    """
    _check_roles(user, list(allowed_roles))
