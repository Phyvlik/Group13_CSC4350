"""Public feedback contracts. Decimal values serialize as strings."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)

    @field_validator("*", mode="after")
    @classmethod
    def utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class JournalContext(Output):
    trade_id: UUID
    reasoning: str


class EvidenceOut(Output):
    session_metric_id: UUID
    metric_code: str
    value: Decimal
    verified_at: datetime
    evidence_reason: str
    trade_ids: list[UUID]
    journal_entries: list[JournalContext]


class FeedbackItem(Output):
    feedback_id: UUID
    pattern_code: str
    explanation: str
    analysis_version: str
    generated_at: datetime
    trade_ids: list[UUID]
    evidence: list[EvidenceOut]


class ObservationOut(Output):
    session_metric_id: UUID
    metric_id: UUID
    revision: int
    value: Decimal
    verified_at: datetime


class FeedbackOut(Output):
    session_id: UUID
    analysis_version: str
    status: Literal["not_computed", "ready"]
    computed_at: datetime | None
    metric: ObservationOut | None
    feedback: list[FeedbackItem]


class MetricOut(Output):
    metric_id: UUID
    code: str
    name: str
    unit: str
    calculation_version: str
    calculation_rule: str


class TrackedOut(Output):
    metric_id: UUID
    selected_at: datetime
    active: bool


class HabitsOut(Output):
    metrics: list[MetricOut]
    tracked: list[TrackedOut]


class HabitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: UUID
    active: bool = True


class HistoryPoint(Output):
    session_id: UUID
    started_at: datetime
    quote_currency: str
    value: Decimal
    revision: int
    computed_at: datetime
    verified_at: datetime


class HistoryOut(Output):
    metric_id: UUID
    code: str
    unit: str
    calculation_version: str
    points: list[HistoryPoint]
    limit: int
    offset: int
    has_more: bool
