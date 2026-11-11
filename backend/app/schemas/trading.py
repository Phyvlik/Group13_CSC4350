from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TradeSide


def ensure_utc(v: Any) -> Any:
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class CreateTradeRequest(BaseModel):
    side: TradeSide
    quantity: Decimal = Field(gt=0, description="Order quantity, must be greater than zero")
    fee: Decimal = Field(default=Decimal("0"), ge=0, description="Trading fee, cannot be negative")


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_id: uuid.UUID
    session_id: uuid.UUID
    side: TradeSide
    quantity: Decimal
    execution_price: Decimal
    fee: Decimal
    realized_pnl: Decimal | None = None
    placed_at: datetime
    outcome_revealed_at: datetime | None = None

    @field_validator("placed_at", "outcome_revealed_at", mode="before")
    @classmethod
    def ensure_trade_dt_utc(cls, v: Any) -> Any:
        return ensure_utc(v)
