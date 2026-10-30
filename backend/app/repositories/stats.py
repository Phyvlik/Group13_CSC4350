"""Owned statistics inputs using the team's existing database contract.

These lightweight Core descriptors only describe columns used by this adapter.
They do not create tables or replace the team's ORM models or migrations. The
caller owns transaction boundaries. PostgreSQL reads share-lock owned session
rows; recomputation can instead request an exclusive row lock. Atomic trade and
replay writers must lock or update the same session rows. Versioned market-data
rows must remain immutable. SQLite does not establish these locking guarantees.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, Select, String, Uuid, column, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.services.stats import TradeInput


_amount = Numeric(18, 6)
sessions = table(
    "practice_sessions",
    column("session_id", Uuid),
    column("user_id", Uuid),
    column("dataset_id", Uuid),
    column("period_start", DateTime(timezone=True)),
    column("period_end", DateTime(timezone=True)),
    column("replay_at", DateTime(timezone=True)),
    column("cash_balance", _amount),
    column("position_quantity", _amount),
)
trades = table(
    "trades",
    column("trade_id", Uuid),
    column("session_id", Uuid),
    column("side", String),
    column("realized_pnl", _amount),
    column("fee", _amount),
    column("placed_at", DateTime(timezone=True)),
)
datasets = table(
    "market_datasets",
    column("dataset_id", Uuid),
    column("instrument_id", Uuid),
)
instruments = table(
    "instruments",
    column("instrument_id", Uuid),
    column("quote_currency", String),
)
price_bars = table(
    "price_bars",
    column("bar_id", Uuid),
    column("dataset_id", Uuid),
    column("bar_at", DateTime(timezone=True)),
    column("close_price", _amount),
)
users = table(
    "users",
    column("user_id", Uuid),
    column("account_status", String),
)


class SessionNotFound(LookupError):
    """A session is absent or does not belong to the requesting user."""


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: UUID
    user_id: UUID
    cash_balance: Decimal
    position_quantity: Decimal
    price: Decimal | None
    quote_currency: str
    trades: tuple[TradeInput, ...]


def _session_query(user_id: UUID) -> Select:
    visible_price = (
        select(price_bars.c.close_price)
        .where(
            price_bars.c.dataset_id == sessions.c.dataset_id,
            price_bars.c.bar_at >= sessions.c.period_start,
            price_bars.c.bar_at <= sessions.c.period_end,
            price_bars.c.bar_at <= sessions.c.replay_at,
        )
        .order_by(price_bars.c.bar_at.desc())
        .limit(1)
        .correlate(sessions)
        .scalar_subquery()
    )
    return (
        select(
            sessions.c.session_id,
            sessions.c.user_id,
            sessions.c.cash_balance,
            sessions.c.position_quantity,
            visible_price.label("price"),
            instruments.c.quote_currency,
        )
        .select_from(
            sessions.join(datasets, sessions.c.dataset_id == datasets.c.dataset_id)
            .join(instruments, datasets.c.instrument_id == instruments.c.instrument_id)
        )
        .where(sessions.c.user_id == user_id)
        .order_by(sessions.c.session_id)
    )


def _load_trades(
    db: Session, user_id: UUID, session_ids: tuple[UUID, ...],
) -> dict[UUID, list[TradeInput]]:
    statement = (
        select(
            trades.c.session_id,
            trades.c.side,
            trades.c.realized_pnl,
            trades.c.fee,
        )
        .select_from(trades.join(sessions, trades.c.session_id == sessions.c.session_id))
        .where(
            sessions.c.user_id == user_id,
            sessions.c.session_id.in_(session_ids),
            trades.c.placed_at >= sessions.c.period_start,
            trades.c.placed_at <= sessions.c.period_end,
            trades.c.placed_at <= sessions.c.replay_at,
        )
        .order_by(trades.c.session_id, trades.c.placed_at, trades.c.trade_id)
    )
    by_session: dict[UUID, list[TradeInput]] = {}
    for row in db.execute(statement).mappings():
        by_session.setdefault(row["session_id"], []).append(
            TradeInput(row["side"], row["realized_pnl"], row["fee"])
        )
    return by_session


def _snapshot(
    row: RowMapping, by_session: dict[UUID, list[TradeInput]],
) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=row["session_id"],
        user_id=row["user_id"],
        cash_balance=row["cash_balance"],
        position_quantity=row["position_quantity"],
        price=row["price"],
        quote_currency=row["quote_currency"],
        trades=tuple(by_session.get(row["session_id"], ())),
    )


def load_session(
    db: Session,
    user_id: UUID,
    session_id: UUID,
    *,
    lock: bool = False,
) -> SessionSnapshot:
    """Load one owned session and its revealed inputs without future prices.

    PostgreSQL holds a shared row lock, or an exclusive lock if ``lock=True``,
    until the caller's transaction ends. Trade and replay writers must lock or
    update the same session row so its fields and trades cannot change between
    the two reads. SQLite ignores row locks and provides no such guarantee.
    """
    statement = (
        _session_query(user_id)
        .where(sessions.c.session_id == session_id)
        .with_for_update(of=sessions, read=not lock)
    )
    row = db.execute(statement).mappings().one_or_none()
    if row is None:
        raise SessionNotFound("Session not found.")
    return _snapshot(row, _load_trades(db, user_id, (session_id,)))


def load_user_sessions(db: Session, user_id: UUID) -> list[SessionSnapshot]:
    """Load owned sessions and trades in two queries, independent of their count.

    Shared session locks are acquired in UUID order to match recomputation's
    lock ordering. New sessions created after the first query are excluded from
    this snapshot; their trades cannot enter the second query.
    """
    statement = _session_query(user_id).with_for_update(of=sessions, read=True)
    rows = db.execute(statement).mappings().all()
    if not rows:
        return []
    session_ids = tuple(row["session_id"] for row in rows)
    by_session = _load_trades(db, user_id, session_ids)
    return [_snapshot(row, by_session) for row in rows]
