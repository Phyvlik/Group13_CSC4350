from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.market_data import PriceBar
from app.services import twelve_data

START = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
TOTAL_BARS = 10_500  # needs three requests at 5000 bars each


def generated_rows(count):
    rows = []
    for i in range(count):
        price = f"{100 + (i % 50) / 10:.2f}"
        rows.append(
            {
                "datetime": (START + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": "100",
            }
        )
    return rows


@pytest.fixture
def paged_api(monkeypatch):
    """Mock Twelve Data that honors start_date, end_date, and outputsize like the real API."""
    state = {"rows": generated_rows(TOTAL_BARS), "requests": [], "ignore_start": False}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        params = request.url.params
        start, end = params["start_date"], params["end_date"]
        size = int(params["outputsize"])
        rows = [r for r in state["rows"] if (state["ignore_start"] or r["datetime"] >= start) and r["datetime"] <= end]
        return httpx.Response(200, json={"meta": {"currency": "USD"}, "values": rows[:size], "status": "ok"})

    monkeypatch.setattr(get_settings(), "twelve_data_api_key", "test-key")
    monkeypatch.setattr(
        twelve_data,
        "_client",
        lambda: httpx.Client(base_url="https://api.twelvedata.com", transport=httpx.MockTransport(handler)),
    )
    return state


def import_body(minutes):
    return {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "interval": "1min",
        "start": START.isoformat(),
        "end": (START + timedelta(minutes=minutes)).isoformat(),
    }


def test_large_range_is_fetched_in_chunks_and_stitched_without_duplicates(admin_client, db, paged_api):
    response = admin_client.post("/admin/market-data/import", json=import_body(TOTAL_BARS - 1))

    assert response.status_code == 201, response.text
    assert response.json()["bars_inserted"] == TOTAL_BARS
    assert response.json()["bars_skipped"] == 0
    assert len(paged_api["requests"]) == 3
    # Each later request starts where the previous full chunk ended.
    starts = [r.url.params["start_date"] for r in paged_api["requests"]]
    assert starts == ["2024-01-02 00:00:00", "2024-01-05 11:19:00", "2024-01-08 22:38:00"]

    stored = db.scalar(select(func.count()).select_from(PriceBar))
    distinct = db.scalar(select(func.count(func.distinct(PriceBar.bar_at))))
    assert stored == distinct == TOTAL_BARS


def test_range_under_the_cap_uses_one_request(admin_client, paged_api):
    response = admin_client.post("/admin/market-data/import", json=import_body(99))

    assert response.status_code == 201
    assert response.json()["bars_inserted"] == 100
    assert len(paged_api["requests"]) == 1


def test_provider_that_ignores_start_date_does_not_loop_forever(admin_client, paged_api):
    paged_api["ignore_start"] = True

    response = admin_client.post("/admin/market-data/import", json=import_body(TOTAL_BARS - 1))

    assert response.status_code == 201
    assert response.json()["bars_inserted"] == twelve_data.MAX_OUTPUT_SIZE
    assert len(paged_api["requests"]) == 2
