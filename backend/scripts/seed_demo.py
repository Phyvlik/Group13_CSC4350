"""Seed demo accounts and a generated daily price dataset so the app can be demoed without a Twelve Data key.

Usage (from the backend directory, or inside the backend container):
    python scripts/seed_demo.py

Safe to run more than once: existing demo rows are reused, never duplicated.
"""

import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Make the app package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import AccountStatus, UserRole  # noqa: E402
from app.models.instrument import Instrument  # noqa: E402
from app.models.market_data import MarketDataset, PriceBar  # noqa: E402
from app.models.user import User  # noqa: E402

DEMO_TRADER = ("demo@epoch.test", "Demo Trader", "demo-password")
DEMO_ADMIN = ("admin@epoch.test", "Demo Admin", "admin-password")
SYMBOL, EXCHANGE = "DEMO", "SIM"
PROVIDER, VERSION, INTERVAL = "generated", "1", "1day"
FIRST_DAY = date(2023, 1, 2)
TRADING_DAYS = 500
SEED = 4350  # fixed so every run produces the same bars


def _cents(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def generate_bars(first_day: date = FIRST_DAY, days: int = TRADING_DAYS, seed: int = SEED) -> list[dict]:
    """Weekday OHLCV bars from a random walk with mild drift and changing volatility."""
    rng = random.Random(seed)
    bars = []
    close = 100.0
    volatility = 0.015
    day = first_day
    while len(bars) < days:
        if day.weekday() < 5:
            # Volatility drifts between calm and choppy stretches so the chart has some character.
            volatility = min(0.04, max(0.006, volatility * rng.uniform(0.9, 1.1)))
            open_ = close * (1 + rng.gauss(0, volatility / 3))
            close = max(1.0, open_ * (1 + rng.gauss(0.0004, volatility)))
            high = max(open_, close) * (1 + abs(rng.gauss(0, volatility / 2)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, volatility / 2)))
            bars.append(
                {
                    "bar_at": datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                    "open_price": _cents(open_),
                    "high_price": _cents(high),
                    "low_price": _cents(low),
                    "close_price": _cents(close),
                    "volume": Decimal(rng.randint(800_000, 5_000_000)),
                }
            )
        day += timedelta(days=1)
    return bars


def _ensure_user(db: Session, email: str, name: str, password: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            role=role,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
    return user


def seed_demo(db: Session) -> MarketDataset:
    """Create the demo trader, demo admin, DEMO instrument and its dataset. Returns the dataset."""
    _ensure_user(db, *DEMO_TRADER, UserRole.TRADER)
    admin = _ensure_user(db, *DEMO_ADMIN, UserRole.ADMIN)

    instrument = db.scalar(select(Instrument).where(Instrument.symbol == SYMBOL, Instrument.exchange == EXCHANGE))
    if instrument is None:
        instrument = Instrument(
            symbol=SYMBOL, exchange=EXCHANGE, name="Demo Corp (generated prices)", quote_currency="USD"
        )
        db.add(instrument)
        db.flush()

    dataset = db.scalar(
        select(MarketDataset).where(
            MarketDataset.instrument_id == instrument.instrument_id,
            MarketDataset.provider == PROVIDER,
            MarketDataset.version == VERSION,
        )
    )
    if dataset is None:
        bars = generate_bars()
        dataset = MarketDataset(
            instrument_id=instrument.instrument_id,
            imported_by=admin.user_id,
            provider=PROVIDER,
            interval=INTERVAL,
            version=VERSION,
            range_start=bars[0]["bar_at"],
            range_end=bars[-1]["bar_at"],
        )
        db.add(dataset)
        db.flush()
        db.add_all(PriceBar(dataset_id=dataset.dataset_id, **bar) for bar in bars)

    db.commit()
    return dataset


def main() -> int:
    with SessionLocal() as db:
        dataset = seed_demo(db)
        print(f"Demo dataset {SYMBOL} on {EXCHANGE}: {dataset.dataset_id}")
    print(f"Trader login: {DEMO_TRADER[0]} / {DEMO_TRADER[2]}")
    print(f"Admin login:  {DEMO_ADMIN[0]} / {DEMO_ADMIN[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
