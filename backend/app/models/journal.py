import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.db.base import Base
from app.models.types import UuidPk


class JournalEntry(Base):
    """The trader's reasoning for a trade, written before the outcome is revealed. One per trade."""

    __tablename__ = "journal_entries"

    journal_id: Mapped[UuidPk]
    trade_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trades.trade_id", ondelete="CASCADE"), unique=True
    )
    reasoning: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trade = relationship("Trade", backref=backref("journal_entry", uselist=False))
