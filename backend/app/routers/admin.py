import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.instrument import Instrument
from app.models.market_data import MarketDataset, PriceBar
from app.models.practice import PracticeSession
from app.models.user import User
from app.schemas.admin import AdminDatasetOut, UpdateUserRequest
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


@router.get("/datasets", response_model=list[AdminDatasetOut])
def list_datasets(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminDatasetOut]:
    """List stored datasets with bar and session counts, newest import first (admin only, FR-20)."""
    bar_counts = (
        select(PriceBar.dataset_id, func.count().label("bar_count")).group_by(PriceBar.dataset_id).subquery()
    )
    session_counts = (
        select(PracticeSession.dataset_id, func.count().label("session_count"))
        .group_by(PracticeSession.dataset_id)
        .subquery()
    )
    rows = db.execute(
        select(
            MarketDataset,
            Instrument,
            func.coalesce(bar_counts.c.bar_count, 0),
            func.coalesce(session_counts.c.session_count, 0),
        )
        .join(Instrument, Instrument.instrument_id == MarketDataset.instrument_id)
        .outerjoin(bar_counts, bar_counts.c.dataset_id == MarketDataset.dataset_id)
        .outerjoin(session_counts, session_counts.c.dataset_id == MarketDataset.dataset_id)
        .order_by(MarketDataset.imported_at.desc(), Instrument.symbol)
    ).all()
    return [
        AdminDatasetOut(
            dataset_id=dataset.dataset_id,
            instrument_id=instrument.instrument_id,
            symbol=instrument.symbol,
            exchange=instrument.exchange,
            provider=dataset.provider,
            interval=dataset.interval,
            version=dataset.version,
            range_start=dataset.range_start,
            range_end=dataset.range_end,
            imported_at=dataset.imported_at,
            bar_count=bar_count,
            session_count=session_count,
        )
        for dataset, instrument, bar_count, session_count in rows
    ]


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a dataset and its bars. Blocked with 409 while any practice session uses it (admin only, FR-20)."""
    dataset = db.get(MarketDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    in_use = db.scalar(select(func.count()).where(PracticeSession.dataset_id == dataset_id))
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset is used by {in_use} practice session(s) and cannot be deleted",
        )

    # The database cascades bars too, but deleting them here keeps SQLite (no FK enforcement) consistent.
    db.execute(delete(PriceBar).where(PriceBar.dataset_id == dataset_id))
    db.delete(dataset)
    try:
        db.commit()
    except IntegrityError:
        # A session started on this dataset between the check and the delete.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dataset is in use and cannot be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
