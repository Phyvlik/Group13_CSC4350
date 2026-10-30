"""Draft calculation helpers for FR-12/FR-13 and issue #12.

Decimal arithmetic uses the caller's current decimal context. Monetary
precision and rounding for storage/display require a shared team policy.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


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
