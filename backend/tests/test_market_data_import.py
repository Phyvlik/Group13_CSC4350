import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.enums import AccountStatus, UserRole
from app.models.instrument import Instrument
from app.models.market_data import MarketDataset, PriceBar
from app.models.user import User
from app.services import twelve_data

IMPORT_BODY = {
    "symbol": "aapl",
    "exchange": "NASDAQ",
    "interval": "1min",
    "start": "2024-01-02T14:30:00Z",
    "end": "2024-01-02T14:32:00Z",
}

TIME_SERIES = {
    "meta": {"symbol": "AAPL", "interval": "1min", "currency": "USD", "exchange": "NASDAQ"},
    "values": [
        # Twelve Data returns newest first by default; the client sorts them.
        {"datetime": "2024-01-02 14:32:00", "open": "186.10", "high": "186.40", "low": "186.00", "close": "186.30", "volume": "1200"},
        {"datetime": "2024-01-02 14:31:00", "open": "185.90", "high": "186.20", "low": "185.80", "close": "186.10", "volume": "900"},
        {"datetime": "2024-01-02 14:30:00", "open": "185.50", "high": "186.00", "low": "185.40", "close": "185.90", "volume": "1500"},
    ],
    "status": "ok",
}


@pytest.fixture
def twelve_data_api(monkeypatch):
    """Replace the Twelve Data HTTP client with a mock transport and record requests."""
    state = {"payload": TIME_SERIES, "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return httpx.Response(200, json=state["payload"])

    monkeypatch.setattr(get_settings(), "twelve_data_api_key", "test-key")
    monkeypatch.setattr(
        twelve_data,
        "_client",
        lambda: httpx.Client(base_url="https://api.twelvedata.com", transport=httpx.MockTransport(handler)),
    )
    return state


@pytest.fixture
def admin_user(db):
    user = User(
        user_id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="secret_hash",
        display_name="Admin",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_client(db, admin_user):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers={"Authorization": f"Bearer {create_access_token(admin_user.user_id)}"})
    app.dependency_overrides.clear()


def test_non_admin_gets_403(client, db, twelve_data_api):
    # `client` is authenticated as user_1, a TRADER.
    response = client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert response.status_code == 403
    assert twelve_data_api["requests"] == []
    assert db.query(MarketDataset).count() == 0


def test_unauthenticated_gets_401(db, twelve_data_api):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post("/admin/market-data/import", json=IMPORT_BODY)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_import_creates_instrument_dataset_and_bars(admin_client, admin_user, db, twelve_data_api):
    response = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["bars_inserted"] == 3
    assert body["bars_skipped"] == 0
    assert body["symbol"] == "AAPL"

    request = twelve_data_api["requests"][0]
    assert request.url.path == "/time_series"
    assert request.url.params["symbol"] == "AAPL"
    assert request.url.params["exchange"] == "NASDAQ"
    assert request.url.params["interval"] == "1min"
    assert request.url.params["start_date"] == "2024-01-02 14:30:00"
    assert request.url.params["end_date"] == "2024-01-02 14:32:00"
    assert request.url.params["timezone"] == "UTC"
    assert request.url.params["apikey"] == "test-key"

    instrument = db.query(Instrument).one()
    assert (instrument.symbol, instrument.exchange, instrument.quote_currency) == ("AAPL", "NASDAQ", "USD")

    dataset = db.query(MarketDataset).one()
    assert str(dataset.dataset_id) == body["dataset_id"]
    assert dataset.instrument_id == instrument.instrument_id
    assert dataset.imported_by == admin_user.user_id
    assert dataset.provider == "twelvedata"
    assert dataset.interval == "1min"

    bars = db.query(PriceBar).order_by(PriceBar.bar_at).all()
    assert [bar.bar_at.replace(tzinfo=timezone.utc) for bar in bars] == [
        datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
        datetime(2024, 1, 2, 14, 31, tzinfo=timezone.utc),
        datetime(2024, 1, 2, 14, 32, tzinfo=timezone.utc),
    ]
    assert str(bars[0].open_price) == "185.500000"
    assert str(bars[0].volume) == "1500.000000"


def test_reimport_same_range_does_not_duplicate_bars(admin_client, db, twelve_data_api):
    first = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)
    second = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["dataset_id"] == first.json()["dataset_id"]
    assert second.json()["created"] is False
    assert second.json()["bars_inserted"] == 0
    assert second.json()["bars_skipped"] == 3
    assert db.query(Instrument).count() == 1
    assert db.query(MarketDataset).count() == 1
    assert db.query(PriceBar).count() == 3


def test_reimport_adds_only_missing_bars(admin_client, db, twelve_data_api):
    twelve_data_api["payload"] = {**TIME_SERIES, "values": TIME_SERIES["values"][1:]}
    admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    twelve_data_api["payload"] = TIME_SERIES
    response = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert response.json()["bars_inserted"] == 1
    assert response.json()["bars_skipped"] == 2
    assert db.query(PriceBar).count() == 3


def test_provider_error_returns_502(admin_client, db, twelve_data_api):
    twelve_data_api["payload"] = {"code": 404, "message": "symbol not found", "status": "error"}

    response = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert response.status_code == 502
    assert "symbol not found" in response.json()["detail"]
    assert db.query(Instrument).count() == 0


def test_missing_api_key_returns_503(admin_client, twelve_data_api, monkeypatch):
    monkeypatch.setattr(get_settings(), "twelve_data_api_key", "")

    response = admin_client.post("/admin/market-data/import", json=IMPORT_BODY)

    assert response.status_code == 503
    assert twelve_data_api["requests"] == []


def test_start_after_end_returns_422(admin_client, twelve_data_api):
    response = admin_client.post(
        "/admin/market-data/import",
        json={**IMPORT_BODY, "start": IMPORT_BODY["end"], "end": IMPORT_BODY["start"]},
    )

    assert response.status_code == 422
