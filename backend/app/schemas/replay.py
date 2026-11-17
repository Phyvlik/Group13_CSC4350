from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import SessionStatus, TradeSide


def ensure_utc(v: Any) -> Any:
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    symbol: str
    exchange: str
    name: str
    quote_currency: str


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: uuid.UUID
    instrument_id: uuid.UUID
    provider: str
    interval: str
    version: str
    range_start: datetime
    range_end: datetime
    imported_at: datetime
    instrument: InstrumentOut | None = None

    @field_validator("range_start", "range_end", "imported_at", mode="before")
    @classmethod
    def ensure_datetimes_utc(cls, v: Any) -> Any:
        return ensure_utc(v)


class PriceBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bar_id: uuid.UUID
    dataset_id: uuid.UUID
    bar_at: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

    @field_validator("bar_at", mode="before")
    @classmethod
    def ensure_bar_at_utc(cls, v: Any) -> Any:
        return ensure_utc(v)


class CreateSessionRequest(BaseModel):
    dataset_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    initial_cash: Decimal = Field(default=Decimal("10000.00"), gt=0)

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def ensure_request_dt_utc(cls, v: Any) -> Any:
        return ensure_utc(v)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    user_id: uuid.UUID
    dataset_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    replay_at: datetime
    replay_speed: Decimal
    initial_cash: Decimal
    cash_balance: Decimal
    position_quantity: Decimal
    average_cost: Decimal
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None = None

    @field_validator("period_start", "period_end", "replay_at", "started_at", "ended_at", mode="before")
    @classmethod
    def ensure_session_dt_utc(cls, v: Any) -> Any:
        return ensure_utc(v)


class StepSessionRequest(BaseModel):
    count: int = Field(default=1, ge=1)

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Accept bars or steps as aliases for count
            if "count" not in data:
                if "bars" in data:
                    data["count"] = data["bars"]
                elif "steps" in data:
                    data["count"] = data["steps"]
        return data


class UpdateSessionRequest(BaseModel):
    replay_speed: Decimal | None = Field(default=None, gt=0)
    status: SessionStatus | None = None
    ended_at: datetime | None = None

    @field_validator("ended_at", mode="before")
    @classmethod
    def ensure_ended_at_utc(cls, v: Any) -> Any:
        return ensure_utc(v)


class TradeOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_id: uuid.UUID
    session_id: uuid.UUID
    placed_at: datetime
    side: TradeSide
    execution_price: Decimal
    quantity: Decimal
    outcome_revealed_at: datetime
    next_bar: PriceBarOut | None = None
    next_price: Decimal | None = None
    price_change: Decimal | None = None
    price_change_pct: Decimal | None = None

    @field_validator("placed_at", "outcome_revealed_at", mode="before")
    @classmethod
    def ensure_trade_dt_utc(cls, v: Any) -> Any:
        return ensure_utc(v)
