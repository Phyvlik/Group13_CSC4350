"""Draft calculation helpers for FR-12/FR-13 and issue #12.

Decimal arithmetic uses the caller's current decimal context. Monetary
precision and rounding for storage/display require a shared team policy.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class TradeInput:
    side: Literal["BUY", "SELL"]
    realized_pnl: Decimal | None
    fee: Decimal = Decimal("0")


@dataclass(frozen=True)
class TradeStats:
    pnl: Decimal
    win_rate: Decimal | None
    closed_trades: int
    winning_trades: int


def _validate_decimal(value: Decimal, field: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be a Decimal.")
    if not value.is_finite():
        raise ValueError(f"{field} must be finite.")


def calculate_stats(trades: Iterable[TradeInput]) -> TradeStats:
    """Return P/L after fees and a win-rate ratio from 0 to 1.

    Provisional rules for team review:
    - realized_pnl excludes fees; every fill's fee is deducted once.
    - Each SELL counts as one closed trade, including partial sells.
    - Positive realized_pnl counts as a win before fees.
    - With no SELLs, win_rate is None (N/A), not a measured 0%.

    The caller supplies records belonging to the intended session/user.
    This helper does not query, save, round for storage, or verify metrics.
    """
    pnl = Decimal("0")
    closed_trades = 0
    winning_trades = 0

    for trade in trades:
        if trade.side not in ("BUY", "SELL"):
            raise ValueError("Trade side must be BUY or SELL.")

        _validate_decimal(trade.fee, "fee")
        if trade.fee < 0:
            raise ValueError("fee cannot be negative.")

        realized = trade.realized_pnl
        if realized is not None:
            _validate_decimal(realized, "realized_pnl")

        pnl -= trade.fee
        if trade.side == "BUY":
            if realized is not None and realized != 0:
                raise ValueError("A BUY cannot have realized P/L.")
            continue

        if realized is None:
            raise ValueError("A SELL must have recorded realized P/L.")

        pnl += realized
        closed_trades += 1
        if realized > 0:
            winning_trades += 1

    win_rate = (
        Decimal(winning_trades) / Decimal(closed_trades)
        if closed_trades
        else None
    )
    return TradeStats(pnl, win_rate, closed_trades, winning_trades)


def calculate_overall_stats(sessions: Iterable[TradeStats]) -> TradeStats:
    """Combine session results using total trade counts for the win rate.

    Session P/L already includes fees, so it is summed without deducting fees
    again. The counts determine the overall win rate; individual session win
    rates are not averaged. With no closed trades, win_rate is None.

    The caller must supply each session once, scoped to the intended user,
    using the same currency and calculation rules for every session.
    Input records are not modified; the iterable is consumed in one pass.
    This helper does not query, save, round for storage, or verify metrics.
    """
    pnl = Decimal("0")
    closed_trades = 0
    winning_trades = 0

    for session in sessions:
        _validate_decimal(session.pnl, "session pnl")
        # Exact int checks also reject bool, which is an int subclass.
        if (
            type(session.closed_trades) is not int
            or type(session.winning_trades) is not int
        ):
            raise TypeError("Session trade counts must be integers.")
        if not 0 <= session.winning_trades <= session.closed_trades:
            raise ValueError("Session trade counts are invalid.")

        pnl += session.pnl
        closed_trades += session.closed_trades
        winning_trades += session.winning_trades

    win_rate = (
        Decimal(winning_trades) / Decimal(closed_trades)
        if closed_trades
        else None
    )
    return TradeStats(pnl, win_rate, closed_trades, winning_trades)


@dataclass(frozen=True)
class ExposureStats:
    position_value: Decimal | None
    equity: Decimal | None
    exposure_ratio: Decimal | None


@dataclass(frozen=True)
class SessionStats:
    trades: TradeStats
    exposure: ExposureStats


class SessionSource(Protocol):
    session_id: UUID
    cash_balance: Decimal
    position_quantity: Decimal
    price: Decimal | None
    quote_currency: str
    trades: tuple[TradeInput, ...]


@dataclass(frozen=True)
class CurrencyStats:
    quote_currency: str
    session_count: int
    pnl: Decimal
    win_rate: Decimal | None
    closed_trades: int
    winning_trades: int
    position_value: Decimal | None
    equity: Decimal | None
    exposure_ratio: Decimal | None


def calculate_exposure(
    cash_balance: Decimal, position_quantity: Decimal, price: Decimal | None
) -> ExposureStats:
    """Proposed current exposure for long-only, unleveraged practice accounts.

    Position value = quantity * latest visible close; equity = cash + value.
    Exposure is position value / equity (a ratio, not a loss forecast).
    Missing price for an open position or zero equity gives an undefined
    ratio. A flat position needs no price. Team approval is still required.
    Arithmetic uses a local 38-digit context without modifying the caller's.
    """
    for name, value in (("cash_balance", cash_balance), ("position_quantity", position_quantity)):
        _validate_decimal(value, name)
        if value < 0:
            raise ValueError(f"{name} cannot be negative for a long-only account.")
    if price is not None:
        _validate_decimal(price, "price")
        if price <= 0:
            raise ValueError("price must be positive.")
    if position_quantity and price is None:
        return ExposureStats(None, None, None)
    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        value = position_quantity * price if position_quantity else Decimal("0")
        equity = cash_balance + value
        return ExposureStats(value, equity, value / equity if equity else None)


def calculate_snapshot_stats(snapshot: SessionSource) -> SessionStats:
    """Calculate one bounded session snapshot using deterministic precision."""
    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        return SessionStats(
            calculate_stats(snapshot.trades),
            calculate_exposure(snapshot.cash_balance, snapshot.position_quantity, snapshot.price),
        )


def calculate_summary(snapshots: Iterable[SessionSource]) -> list[CurrencyStats]:
    """Group current snapshots by currency; weight win rate and exposure.

    Never add different currencies or average individual ratios. If any open
    position lacks a visible price, the currency's exposure stays undefined.
    Each session must appear once. Memory is proportional to session count.
    """
    groups: dict[str, list[SessionStats]] = {}
    seen: set[UUID] = set()
    for snapshot in snapshots:
        if snapshot.session_id in seen:
            raise ValueError("A session cannot occur twice in a summary.")
        seen.add(snapshot.session_id)
        groups.setdefault(snapshot.quote_currency, []).append(calculate_snapshot_stats(snapshot))

    result = []
    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        for currency, sessions in sorted(groups.items()):
            trades = calculate_overall_stats(session.trades for session in sessions)
            complete = all(session.exposure.position_value is not None for session in sessions)
            value = sum((session.exposure.position_value for session in sessions), Decimal("0")) if complete else None
            equity = sum((session.exposure.equity for session in sessions), Decimal("0")) if complete else None
            result.append(CurrencyStats(
                currency, len(sessions), trades.pnl, trades.win_rate,
                trades.closed_trades, trades.winning_trades, value, equity,
                value / equity if equity else None,
            ))
    return result
