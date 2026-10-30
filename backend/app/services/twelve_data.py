"""Minimal Twelve Data client for fetching historical OHLC bars.

Docs: https://twelvedata.com/docs#time-series
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings

# Twelve Data returns at most 5000 bars per request.
MAX_OUTPUT_SIZE = 5000
_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class TwelveDataNotConfigured(Exception):
    """TWELVE_DATA_API_KEY is not set."""


class TwelveDataError(Exception):
    """The provider could not be reached or returned an error payload."""


@dataclass(frozen=True)
class Bar:
    bar_at: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


@dataclass(frozen=True)
class TimeSeries:
    currency: str | None
    bars: list[Bar]


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().twelve_data_base_url, timeout=30.0)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_bar(row: dict) -> Bar:
    try:
        return Bar(
            # Bars are requested in UTC; daily intervals come back as a bare date.
            bar_at=datetime.fromisoformat(row["datetime"]).replace(tzinfo=timezone.utc),
            open_price=Decimal(row["open"]),
            high_price=Decimal(row["high"]),
            low_price=Decimal(row["low"]),
            close_price=Decimal(row["close"]),
            volume=Decimal(row.get("volume") or "0"),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise TwelveDataError(f"Unexpected bar format from Twelve Data: {row!r}") from exc


def fetch_time_series(symbol: str, exchange: str, interval: str, start: datetime, end: datetime) -> TimeSeries:
    """Fetch bars for [start, end] in UTC, oldest first."""
    api_key = get_settings().twelve_data_api_key
    if not api_key:
        raise TwelveDataNotConfigured("TWELVE_DATA_API_KEY is not set")

    params = {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "start_date": _to_utc(start).strftime(_DATETIME_FORMAT),
        "end_date": _to_utc(end).strftime(_DATETIME_FORMAT),
        "timezone": "UTC",
        "order": "ASC",
        "outputsize": MAX_OUTPUT_SIZE,
        "apikey": api_key,
    }
    try:
        with _client() as client:
            response = client.get("/time_series", params=params)
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TwelveDataError("Could not reach Twelve Data") from exc

    # Twelve Data reports most errors with HTTP 200 and status "error" in the body.
    if response.status_code != 200 or payload.get("status") == "error":
        raise TwelveDataError(payload.get("message") or f"Twelve Data returned HTTP {response.status_code}")

    meta = payload.get("meta") or {}
    bars = sorted((_parse_bar(row) for row in payload.get("values") or []), key=lambda bar: bar.bar_at)
    return TimeSeries(currency=meta.get("currency"), bars=bars)
