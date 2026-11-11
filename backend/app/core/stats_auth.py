"""JWT authentication for statistics until the shared auth API is integrated.

Only a server-signed subject identifies the user. This dependency intentionally
does not accept development identity headers or a user ID supplied in a query.
"""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.stats import users


_bearer = HTTPBearer(auto_error=False)
_DEFAULT_SECRET = "change_me_to_a_long_random_string"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid access token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_stats_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UUID:
    """Validate the token and require an existing, active database user."""
    if credentials is None:
        raise _unauthorized()

    secret = settings.jwt_secret_key
    if (
        settings.jwt_algorithm != "HS256"
        or secret == _DEFAULT_SECRET
        or len(secret.encode("utf-8")) < 32
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Access-token verification is not configured.",
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise _unauthorized() from None

    try:
        account_status = db.execute(
            select(users.c.account_status).where(users.c.user_id == user_id)
        ).scalar_one_or_none()
    except (OperationalError, ProgrammingError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The statistics database is unavailable.",
        ) from None

    if account_status != "ACTIVE":
        raise _unauthorized()
    return user_id
