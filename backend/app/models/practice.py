import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SessionStatus, TradeSide
from app.models.types import Amount, UuidPk


class PracticeSession(Base):
    """A user's replay of one dataset. Cash and position fields change only inside a trade transaction."""

    __tablename__ = "practice_sessions"

    session_id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_datasets.dataset_id", ondelete="RESTRICT"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replay_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replay_speed: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("1.00"), server_default="1.00"
    )
    initial_cash: Mapped[Amount]
    cash_balance: Mapped[Amount]
    position_quantity: Mapped[Amount] = mapped_column(default=Decimal("0"), server_default="0")
    average_cost: Mapped[Amount] = mapped_column(default=Decimal("0"), server_default="0")
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        default=SessionStatus.ACTIVE,
        server_default=SessionStatus.ACTIVE.value,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", backref="practice_sessions")
    dataset = relationship("MarketDataset")


class Trade(Base):
    """A simulated fill. outcome_revealed_at stays null until the journal reasoning is recorded."""

    __tablename__ = "trades"

    trade_id: Mapped[UuidPk]
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"), index=True
    )
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide, name="trade_side"))
    quantity: Mapped[Amount]
    execution_price: Mapped[Amount]
    fee: Mapped[Amount] = mapped_column(default=Decimal("0"), server_default="0")
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session = relationship("PracticeSession", backref="trades")
