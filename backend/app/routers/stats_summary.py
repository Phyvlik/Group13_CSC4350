"""Current statistics grouped by the authenticated user's quote currencies."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.stats_auth import get_stats_user_id
from app.db.session import get_db
from app.repositories.stats import load_user_sessions
from app.routers.stats import DecimalResponse, translate_errors
from app.services.stats import calculate_summary


router = APIRouter(tags=["statistics"])


class CurrencyStatsResponse(DecimalResponse):
    quote_currency: str
    session_count: int = Field(ge=0)
    pnl: Decimal
    win_rate: Decimal | None
    closed_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    position_value: Decimal | None
    equity: Decimal | None
    exposure_ratio: Decimal | None


class SummaryStatsResponse(BaseModel):
    currencies: list[CurrencyStatsResponse]


@router.get("/stats/summary", response_model=SummaryStatsResponse)
def get_summary_stats(
    user_id: UUID = Depends(get_stats_user_id),
    db: Session = Depends(get_db),
):
    """Calculate current totals without combining different currencies."""
    with translate_errors(db):
        return {"currencies": calculate_summary(load_user_sessions(db, user_id))}
