from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from app.models.market_data import MarketDataset, PriceBar
from app.models.user import User
from app.schemas.market_data import MarketDataImportRequest, MarketDataImportResponse
from app.services import twelve_data

PROVIDER = "twelvedata"
DATASET_VERSION = "1"
DEFAULT_QUOTE_CURRENCY = "USD"


class NoBarsReturned(Exception):
    """The provider had no bars for the requested range."""


def _to_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo on read; stored values are always UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _upsert_instrument(db: Session, symbol: str, exchange: str, currency: str | None) -> Instrument:
    instrument = db.scalar(select(Instrument).where(Instrument.symbol == symbol, Instrument.exchange == exchange))
    if instrument is None:
        instrument = Instrument(
            symbol=symbol,
            exchange=exchange,
            name=symbol,
            quote_currency=currency or DEFAULT_QUOTE_CURRENCY,
        )
        db.add(instrument)
        db.flush()
    elif currency and instrument.quote_currency != currency:
        instrument.quote_currency = currency
    return instrument


def import_market_data(db: Session, admin: User, request: MarketDataImportRequest) -> MarketDataImportResponse:
    """Fetch bars from Twelve Data and store them. Re-importing the same range only adds missing bars."""
    series = twelve_data.fetch_time_series(
        symbol=request.symbol,
        exchange=request.exchange,
        interval=request.interval,
        start=request.start,
        end=request.end,
    )
    bars = [bar for bar in series.bars if request.start <= bar.bar_at <= request.end]
    if not bars:
        raise NoBarsReturned(f"No bars returned for {request.symbol} on {request.exchange} in that range")

    instrument = _upsert_instrument(db, request.symbol, request.exchange, series.currency)

    dataset = db.scalar(
        select(MarketDataset).where(
            MarketDataset.instrument_id == instrument.instrument_id,
            MarketDataset.provider == PROVIDER,
            MarketDataset.interval == request.interval,
            MarketDataset.range_start == request.start,
            MarketDataset.range_end == request.end,
        )
    )
    created = dataset is None
    if created:
        dataset = MarketDataset(
            instrument_id=instrument.instrument_id,
            imported_by=admin.user_id,
            provider=PROVIDER,
            interval=request.interval,
            version=DATASET_VERSION,
            range_start=request.start,
            range_end=request.end,
        )
        db.add(dataset)
        db.flush()

    existing = {
        _to_utc(bar_at)
        for bar_at in db.scalars(select(PriceBar.bar_at).where(PriceBar.dataset_id == dataset.dataset_id))
    }
    new_bars = [bar for bar in bars if bar.bar_at not in existing]
    db.add_all(
        PriceBar(
            dataset_id=dataset.dataset_id,
            bar_at=bar.bar_at,
            open_price=bar.open_price,
            high_price=bar.high_price,
            low_price=bar.low_price,
            close_price=bar.close_price,
            volume=bar.volume,
        )
        for bar in new_bars
    )
    db.commit()

    return MarketDataImportResponse(
        dataset_id=dataset.dataset_id,
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        exchange=instrument.exchange,
        provider=dataset.provider,
        interval=dataset.interval,
        version=dataset.version,
        range_start=_to_utc(dataset.range_start),
        range_end=_to_utc(dataset.range_end),
        created=created,
        bars_inserted=len(new_bars),
        bars_skipped=len(bars) - len(new_bars),
    )
