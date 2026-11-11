import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.schemas.admin import UpdateUserRequest
from app.schemas.auth import UserOut
from app.schemas.market_data import MarketDataImportRequest, MarketDataImportResponse
from app.services.market_data_import import NoBarsReturned, import_market_data
from app.services.twelve_data import TwelveDataError, TwelveDataNotConfigured

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/market-data/import",
    response_model=MarketDataImportResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Dataset already existed; only missing bars were added"}},
)
def import_market_data_route(
    body: MarketDataImportRequest,
    response: Response,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MarketDataImportResponse:
    """Import OHLC bars from Twelve Data into a market dataset (admin only)."""
    try:
        result = import_market_data(db, admin, body)
    except TwelveDataNotConfigured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Market data import is not configured")
    except TwelveDataError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Twelve Data error: {exc}")
    except NoBarsReturned as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except IntegrityError:
        # A concurrent import of the same range inserted rows first.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Import conflicted with another import, retry")

    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/users", response_model=list[UserOut])
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    """List every account, oldest first (admin only, FR-21)."""
    users = db.scalars(select(User).order_by(User.created_at, User.email))
    return [UserOut.from_user(user) for user in users]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    """Change another account's role or status (admin only, FR-21)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # Stops the last admin from locking everyone out by accident.
    if user.user_id == admin.user_id and (body.role == "Trader" or body.status == "Disabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote or disable your own account",
        )

    if body.role is not None:
        user.role = UserRole.ADMIN if body.role == "Admin" else UserRole.TRADER
    if body.status is not None:
        user.account_status = AccountStatus.ACTIVE if body.status == "Active" else AccountStatus.SUSPENDED

    db.commit()
    db.refresh(user)
    return UserOut.from_user(user)
