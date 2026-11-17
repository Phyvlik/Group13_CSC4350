import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.trading import CreateTradeRequest, TradeOut
from app.services.trading import TradingService

router = APIRouter()


@router.post(
    "/sessions/{id}/trades",
    response_model=TradeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["trades"],
    summary="Place a simulated trade in a practice session (FR-6, FR-7, NFR-8)",
)
def place_trade(
    id: uuid.UUID,
    payload: CreateTradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place a simulated BUY or SELL order. Fills at current bar's close price."""
    return TradingService.place_trade(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
        payload=payload,
    )


@router.get(
    "/sessions/{id}/trades",
    response_model=list[TradeOut],
    tags=["trades"],
    summary="List trades in a practice session (owner only)",
)
def list_session_trades(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all trades placed in this practice session."""
    return TradingService.list_trades(
        db=db,
        session_id=id,
        user_id=current_user.user_id,
    )
