import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MetricCode
from app.models.types import Amount, UuidPk


class Metric(Base):
    """Definition of a stat the backend can compute, with a versioned calculation rule."""

    __tablename__ = "metrics"

    metric_id: Mapped[UuidPk]
    code: Mapped[MetricCode] = mapped_column(Enum(MetricCode, name="metric_code"))
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20))
    calculation_rule: Mapped[str] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(String(20))


class SessionMetric(Base):
    """A computed metric value for a session. verified_at must be set before it can back feedback."""

    __tablename__ = "session_metrics"
    __table_args__ = (UniqueConstraint("session_id", "metric_id", "revision"),)

    session_metric_id: Mapped[UuidPk]
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE")
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metrics.metric_id", ondelete="RESTRICT"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    value: Mapped[Amount]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session = relationship("PracticeSession", backref="session_metrics")
    metric = relationship("Metric")


class TrackedHabit(Base):
    """A metric a user has chosen to track over time."""

    __tablename__ = "tracked_habits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    metric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metrics.metric_id", ondelete="CASCADE"), primary_key=True
    )
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    user = relationship("User", backref="tracked_habits")
    metric = relationship("Metric")
