from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import SessionStatus
from app.models.journal import JournalEntry
from app.models.market_data import MarketDataset, PriceBar
from app.models.practice import PracticeSession, Trade
from app.schemas.replay import (
    CreateSessionRequest,
    PriceBarOut,
    TradeOutcomeOut,
    UpdateSessionRequest,
)


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReplayService:
    """Business logic for historical market replay sessions."""

    @staticmethod
    def list_datasets(db: Session) -> Sequence[MarketDataset]:
        """List all datasets with their instrument details (FR-1)."""
        stmt = (
            select(MarketDataset)
            .options(joinedload(MarketDataset.instrument))
            .order_by(MarketDataset.imported_at.desc())
        )
        return db.scalars(stmt).unique().all()

    @staticmethod
    def create_session(
        db: Session,
        user_id: uuid.UUID,
        payload: CreateSessionRequest,
    ) -> PracticeSession:
        """Start a new practice replay session (FR-1, FR-2)."""
        dataset = db.get(MarketDataset, payload.dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )

        start = _to_utc(payload.period_start)
        end = _to_utc(payload.period_end)

        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="period_start must be earlier than period_end",
            )

        if payload.initial_cash <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="initial_cash must be greater than zero",
            )

        session = PracticeSession(
            session_id=uuid.uuid4(),
            user_id=user_id,
            dataset_id=payload.dataset_id,
            period_start=start,
            period_end=end,
            replay_at=start,  # replay_at starts at period_start
            replay_speed=Decimal("1.00"),
            initial_cash=payload.initial_cash,
            cash_balance=payload.initial_cash,
            position_quantity=Decimal("0"),
            average_cost=Decimal("0"),
            status=SessionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
        )

        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def list_sessions(
        db: Session,
        user_id: uuid.UUID,
        status: SessionStatus | None = None,
        limit: int | None = None,
    ) -> Sequence[PracticeSession]:
        """List all replay sessions for a user, ordered newest first."""
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id)
            .order_by(PracticeSession.started_at.desc())
        )
        if status is not None:
            stmt = stmt.where(PracticeSession.status == status)
        if limit is not None:
            stmt = stmt.limit(limit)

        return db.scalars(stmt).all()

    @staticmethod
    def get_session(
        db: Session,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PracticeSession:
        """Fetch session scoped to the logged-in user.

        Another user's session returns 404.
        """
        stmt = select(PracticeSession).where(
            PracticeSession.session_id == session_id,
            PracticeSession.user_id == user_id,
        )
        session = db.scalar(stmt)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        return session

    @staticmethod
    def get_session_bars(
        db: Session,
        session: PracticeSession,
        start_at: datetime | None = None,
        limit: int | None = None,
    ) -> Sequence[PriceBar]:
        """Fetch price bars where bar_at <= replay_at executed at the SQL level (NFR-7)."""
        replay_at = _to_utc(session.replay_at)
        stmt = (
            select(PriceBar)
            .where(
                PriceBar.dataset_id == session.dataset_id,
                PriceBar.bar_at <= replay_at,
            )
            .order_by(PriceBar.bar_at.asc())
        )
        if start_at is not None:
            stmt = stmt.where(PriceBar.bar_at >= _to_utc(start_at))
        if limit is not None:
            stmt = stmt.limit(limit)

        return db.scalars(stmt).all()

    @staticmethod
    def step_session(
        db: Session,
        session: PracticeSession,
        count: int = 1,
    ) -> PracticeSession:
        """Advance replay_at forward by N bars, never past period_end (FR-3)."""
        if session.status in (SessionStatus.COMPLETED, SessionStatus.ABANDONED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot step an ended session",
            )

        if count < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Step count must be at least 1",
            )

        replay_at = _to_utc(session.replay_at)
        period_end = _to_utc(session.period_end)

        stmt = (
            select(PriceBar)
            .where(
                PriceBar.dataset_id == session.dataset_id,
                PriceBar.bar_at > replay_at,
                PriceBar.bar_at <= period_end,
            )
            .order_by(PriceBar.bar_at.asc())
            .limit(count)
        )
        next_bars = db.scalars(stmt).all()

        if next_bars:
            session.replay_at = _to_utc(next_bars[-1].bar_at)
            db.commit()
            db.refresh(session)

        return session

    @staticmethod
    def update_session(
        db: Session,
        session: PracticeSession,
        payload: UpdateSessionRequest,
    ) -> PracticeSession:
        """Update session replay_speed, pause, or end (status, ended_at)."""
        if payload.replay_speed is not None:
            if payload.replay_speed <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="replay_speed must be greater than zero",
                )
            session.replay_speed = payload.replay_speed

        if payload.status is not None:
            session.status = payload.status
            if payload.status in (SessionStatus.COMPLETED, SessionStatus.ABANDONED):
                if payload.ended_at is not None:
                    session.ended_at = _to_utc(payload.ended_at)
                elif session.ended_at is None:
                    session.ended_at = datetime.now(timezone.utc)
            elif payload.status in (SessionStatus.ACTIVE, SessionStatus.PAUSED):
                if session.ended_at is not None and payload.status == SessionStatus.ACTIVE:
                    session.ended_at = None

        if payload.ended_at is not None:
            session.ended_at = _to_utc(payload.ended_at)
            if payload.status is None and session.status == SessionStatus.ACTIVE:
                session.status = SessionStatus.COMPLETED

        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_trade_outcome(
        db: Session,
        trade_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TradeOutcomeOut:
        """Return next price movement only if trade has reasoning journaled (FR-4)."""
        stmt = (
            select(Trade)
            .join(PracticeSession, Trade.session_id == PracticeSession.session_id)
            .where(Trade.trade_id == trade_id)
        )
        trade = db.scalar(stmt)
        if not trade or trade.session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade not found",
            )

        journal_entry = db.scalar(
            select(JournalEntry).where(JournalEntry.trade_id == trade.trade_id)
        )
        if not journal_entry:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Journal entry required before trade outcome can be revealed",
            )

        placed_at = _to_utc(trade.placed_at)
        bar_stmt = (
            select(PriceBar)
            .where(
                PriceBar.dataset_id == trade.session.dataset_id,
                PriceBar.bar_at > placed_at,
            )
            .order_by(PriceBar.bar_at.asc())
            .limit(1)
        )
        next_bar = db.scalar(bar_stmt)

        if trade.outcome_revealed_at is None:
            trade.outcome_revealed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(trade)

        next_price = next_bar.close_price if next_bar else None
        price_change = (next_bar.close_price - trade.execution_price) if next_bar else None
        price_change_pct = None
        if next_bar and trade.execution_price and trade.execution_price != Decimal("0"):
            price_change_pct = (
                (next_bar.close_price - trade.execution_price) / trade.execution_price
            ) * Decimal("100")

        return TradeOutcomeOut(
            trade_id=trade.trade_id,
            session_id=trade.session_id,
            placed_at=_to_utc(trade.placed_at),
            side=trade.side,
            execution_price=trade.execution_price,
            quantity=trade.quantity,
            outcome_revealed_at=_to_utc(trade.outcome_revealed_at),
            next_bar=PriceBarOut.model_validate(next_bar) if next_bar else None,
            next_price=next_price,
            price_change=price_change,
            price_change_pct=price_change_pct,
        )
