import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Intervals supported by the Twelve Data time_series endpoint.
Interval = Literal["1min", "5min", "15min", "30min", "45min", "1h", "2h", "4h", "1day", "1week", "1month"]


class MarketDataImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=50)
    interval: Interval
    start: datetime
    end: datetime

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Cannot be blank")
        return value

    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_range(self) -> "MarketDataImportRequest":
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")
        return self


class MarketDataImportResponse(BaseModel):
    dataset_id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: str
    exchange: str
    provider: str
    interval: str
    version: str
    range_start: datetime
    range_end: datetime
    created: bool
    bars_inserted: int
    bars_skipped: int
