import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import Amount, UuidPk


class MarketDataset(Base):
    """A versioned import of historical bars for one instrument, uploaded by an admin."""

    __tablename__ = "market_datasets"

    dataset_id: Mapped[UuidPk]
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.instrument_id", ondelete="RESTRICT"), index=True
    )
    imported_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(100))
    interval: Mapped[str] = mapped_column(String(20))
    version: Mapped[str] = mapped_column(String(50))
    range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instrument = relationship("Instrument", backref="datasets")
    importer = relationship("User")


class PriceBar(Base):
    """One OHLCV bar. The replay API must never return bars after a session's replay_at."""

    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("dataset_id", "bar_at"),)

    bar_id: Mapped[UuidPk]
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_datasets.dataset_id", ondelete="CASCADE")
    )
    bar_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open_price: Mapped[Amount]
    high_price: Mapped[Amount]
    low_price: Mapped[Amount]
    close_price: Mapped[Amount]
    volume: Mapped[Amount]

    dataset = relationship("MarketDataset", backref="bars")
