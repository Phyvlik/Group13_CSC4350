from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.enums import SessionStatus
from app.models.user import User
from app.schemas.replay import (
    CreateSessionRequest,
    DatasetOut,
    PriceBarOut,
    SessionOut,
    StepSessionRequest,
    TradeOutcomeOut,
    UpdateSessionRequest,
)
from app.services.replay import ReplayService

router = APIRouter()


@router.get(
    "/datasets",
    response_model=list[DatasetOut],
    tags=["datasets"],
    summary="List available datasets and instruments (FR-1)",
)
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List datasets and associated instruments available for replay sessions."""
    return ReplayService.list_datasets(db)


@router.post(
    "/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    tags=["sessions"],
    summary="Start a replay session (FR-1, FR-2)",
)
def create_session(
    payload: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a session with dataset, period_start, period_end, and initial cash.

    replay_at begins at period_start.
    """
    return ReplayService.create_session(
        db=db,
        user_id=current_user.user_id,
        payload=payload,
    )


@router.get(
    "/sessions",
    response_model=list[SessionOut],
    tags=["sessions"],
    summary="List practice replay sessions for the current user",
)
def list_sessions(
    status: SessionStatus | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all sessions belonging to the logged-in user, newest first."""
    return ReplayService.list_sessions(
        db=db,
        user_id=current_user.user_id,
        status=status,
        limit=limit,
    )


@router.get(
    "/sessions/{id}",
    response_model=SessionOut,
    tags=["sessions"],
    summary="Get replay session status and details",
)
def get_session(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch session details. Scoped to the logged-in user."""
    return ReplayService.get_session(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
    )


@router.get(
    "/sessions/{id}/bars",
    response_model=list[PriceBarOut],
    tags=["sessions"],
    summary="Get price bars up to current replay position (FR-2, NFR-7)",
)
def get_session_bars(
    id: uuid.UUID,
    start_at: datetime | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return only bars where bar_at <= replay_at, filtered in SQL."""
    session = ReplayService.get_session(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
    )
    return ReplayService.get_session_bars(
        db=db,
        session=session,
        start_at=start_at,
        limit=limit,
    )


@router.post(
    "/sessions/{id}/step",
    response_model=SessionOut,
    tags=["sessions"],
    summary="Step replay forward by N bars (FR-3)",
)
def step_session(
    id: uuid.UUID,
    body: StepSessionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advance replay_at forward by N bars, never past period_end."""
    session = ReplayService.get_session(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
    )
    count = body.count if body else 1
    return ReplayService.step_session(
        db=db,
        session=session,
        count=count,
    )


@router.patch(
    "/sessions/{id}",
    response_model=SessionOut,
    tags=["sessions"],
    summary="Update session speed, pause, or end (status, ended_at)",
)
def update_session(
    id: uuid.UUID,
    payload: UpdateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update replay_speed, pause, resume, or end a session."""
    session = ReplayService.get_session(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
    )
    return ReplayService.update_session(
        db=db,
        session=session,
        payload=payload,
    )


@router.get(
    "/trades/{id}/outcome",
    response_model=TradeOutcomeOut,
    tags=["trades"],
    summary="Reveal next price movement for a journaled trade (FR-4)",
)
def get_trade_outcome(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return next price movement only if trade reasoning is journaled. Otherwise 409."""
    return ReplayService.get_trade_outcome(
        db=db,
        trade_id=id,
        user_id=current_user.user_id,
    )
