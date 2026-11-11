"""Ownership-scoped statistics API. GET requests never create metric records."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.stats_auth import get_stats_user_id
from app.db.session import get_db
from app.repositories.stats import SessionNotFound
from app.services.stats_storage import (
    StatsConflict,
    StatsNotComputed,
    read_verified_stats,
    recompute_session_stats,
)


router = APIRouter(tags=["statistics"])


class DecimalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)

    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_decimal(self, value):
        # Monetary values and ratios retain Decimal precision in JSON clients.
        return str(value) if isinstance(value, Decimal) else value


class SessionStatsResponse(DecimalResponse):
    session_id: UUID
    quote_currency: str
    revision: int = Field(ge=1)
    computed_at: datetime
    verified_at: datetime
    calculation_version: str
    pnl: Decimal
    win_rate: Decimal | None
    exposure_ratio: Decimal | None

    @field_validator("computed_at", "verified_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        # SQLite drops timezone information; these persisted values are UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


@contextmanager
def translate_errors(db: Session) -> Iterator[None]:
    try:
        yield
    except SessionNotFound:
        raise HTTPException(404, "Session not found.") from None
    except StatsNotComputed:
        raise HTTPException(409, "Statistics must be recomputed before reading.") from None
    except (StatsConflict, IntegrityError):
        db.rollback()
        raise HTTPException(409, "Statistics changed; retry the request.") from None
    except ValueError:
        db.rollback()
        raise HTTPException(409, "Session data cannot produce valid statistics.") from None
    except (OperationalError, ProgrammingError):
        db.rollback()
        raise HTTPException(503, "The statistics database is unavailable.") from None


@router.get("/sessions/{session_id}/stats", response_model=SessionStatsResponse)
def get_session_stats(
    session_id: UUID,
    user_id: UUID = Depends(get_stats_user_id),
    db: Session = Depends(get_db),
):
    """Read the latest saved, verified snapshot as of its computation time."""
    with translate_errors(db):
        return read_verified_stats(db, user_id, session_id)


@router.post(
    "/sessions/{session_id}/stats/recompute", response_model=SessionStatsResponse
)
def post_session_stats(
    session_id: UUID,
    user_id: UUID = Depends(get_stats_user_id),
    db: Session = Depends(get_db),
):
    """Explicitly calculate, verify and persist a new statistics revision."""
    with translate_errors(db):
        result = recompute_session_stats(db, user_id, session_id)
        db.commit()
        return result
