import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class UpdateUserRequest(BaseModel):
    """Admin change to another account. Uses the same labels as UserOut."""

    role: Literal["Trader", "Admin"] | None = None
    status: Literal["Active", "Disabled"] | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "UpdateUserRequest":
        if self.role is None and self.status is None:
            raise ValueError("Provide role and/or status")
        return self


class AdminDatasetOut(BaseModel):
    """A stored dataset with how many bars it holds and how many sessions replay it."""

    dataset_id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: str
    exchange: str
    provider: str
    interval: str
    version: str
    range_start: datetime
    range_end: datetime
    imported_at: datetime
    bar_count: int
    session_count: int

    @field_validator("range_start", "range_end", "imported_at")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        # SQLite drops tzinfo on read; stored values are always UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
