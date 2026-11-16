from decimal import Decimal
from typing import Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TradeSide
from app.models.market_data import PriceBar
from app.models.practice import Trade
from app.schemas.trading import CreateTradeRequest
from app.services.replay import ENDED_STATUSES, ReplayService, dataset_bars


class TradingService:
    """Business logic for simulated paper trading execution."""

    @staticmethod
    def place_trade(
        db: Session,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: CreateTradeRequest,
    ) -> Trade:
        """Place simulated BUY or SELL order with atomic cash/position update (FR-6, FR-7, NFR-8)."""
        # Session row locked using SELECT ... FOR UPDATE (FR-7, NFR-8)
        session = ReplayService.get_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            for_update=True,
        )

        if session.status in ENDED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot trade on an ended session",
            )

        # Execution price is the close of the bar at replay_at (client cannot set price)
        current_bar = db.scalar(
            dataset_bars(session.dataset_id)
            .where(PriceBar.bar_at <= session.replay_at)
            .order_by(PriceBar.bar_at.desc())
            .limit(1)
        )
        if not current_bar:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No price bar available at current replay position",
            )

        execution_price = current_bar.close_price

        if payload.side == TradeSide.BUY:
            total_cost = (payload.quantity * execution_price) + payload.fee
            if total_cost > session.cash_balance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient cash: order requires {total_cost}, available cash is {session.cash_balance}",
                )

            # Update cash, position quantity, and weighted average cost
            old_position_value = session.position_quantity * session.average_cost
            new_position_quantity = session.position_quantity + payload.quantity
            new_position_cost = old_position_value + (payload.quantity * execution_price)

            session.cash_balance -= total_cost
            session.position_quantity = new_position_quantity
            session.average_cost = new_position_cost / new_position_quantity
            realized_pnl = None

        elif payload.side == TradeSide.SELL:
            if payload.quantity > session.position_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient position: sell quantity {payload.quantity} exceeds current position {session.position_quantity}",
                )

            gross_proceeds = payload.quantity * execution_price
            net_proceeds = gross_proceeds - payload.fee

            # realized_pnl is computed on closing sells using average_cost
            cost_basis = payload.quantity * session.average_cost
            realized_pnl = (gross_proceeds - cost_basis) - payload.fee

            session.cash_balance += net_proceeds
            session.position_quantity -= payload.quantity

            if session.position_quantity == Decimal("0"):
                session.average_cost = Decimal("0")
            # If partial sell, average_cost remains unchanged for remaining shares

        trade = Trade(
            trade_id=uuid.uuid4(),
            session_id=session.session_id,
            side=payload.side,
            quantity=payload.quantity,
            execution_price=execution_price,
            fee=payload.fee,
            realized_pnl=realized_pnl,
            placed_at=session.replay_at,
            outcome_revealed_at=None,
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def list_trades(
        db: Session,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Sequence[Trade]:
        """List trades for a session, owner only."""
        ReplayService.get_session(db=db, session_id=session_id, user_id=user_id)

        stmt = (
            select(Trade)
            .where(Trade.session_id == session_id)
            .order_by(Trade.placed_at.asc())
        )
        return db.scalars(stmt).all()
