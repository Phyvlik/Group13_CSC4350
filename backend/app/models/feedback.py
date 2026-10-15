import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import UuidPk


class Feedback(Base):
    """Habit feedback for a session. Text is generated only from verified session metrics."""

    __tablename__ = "feedback"

    feedback_id: Mapped[UuidPk]
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"), index=True
    )
    pattern_code: Mapped[str] = mapped_column(String(50))
    explanation: Mapped[str] = mapped_column(Text)
    analysis_version: Mapped[str] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("PracticeSession", backref="feedback")


class FeedbackEvidence(Base):
    """Links a feedback item to a verified session metric that supports it."""

    __tablename__ = "feedback_evidence"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"), primary_key=True
    )
    session_metric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_metrics.session_metric_id", ondelete="CASCADE"), primary_key=True
    )
    evidence_reason: Mapped[str] = mapped_column(Text)

    feedback = relationship("Feedback", backref="evidence")
    session_metric = relationship("SessionMetric")
