from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user
from app.models.enums import UserRole
from app.models.user import User


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that allows only admin users through, otherwise HTTP 403."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
