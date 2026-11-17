from sqlalchemy import func, select

from app.models.enums import UserRole
from app.models.market_data import MarketDataset, PriceBar
from app.models.user import User
from scripts.seed_demo import DEMO_ADMIN, DEMO_TRADER, TRADING_DAYS, generate_bars, seed_demo


def test_generated_bars_are_valid_weekday_ohlc():
    bars = generate_bars()

    assert len(bars) == TRADING_DAYS
    assert all(bar["bar_at"].weekday() < 5 for bar in bars)
    assert [b["bar_at"] for b in bars] == sorted({b["bar_at"] for b in bars})
    for bar in bars:
        assert bar["low_price"] <= min(bar["open_price"], bar["close_price"])
        assert bar["high_price"] >= max(bar["open_price"], bar["close_price"])
        assert bar["low_price"] > 0


def test_generated_bars_are_reproducible():
    assert generate_bars() == generate_bars()


def test_seed_creates_accounts_and_dataset_once(db):
    first = seed_demo(db)
    second = seed_demo(db)

    assert first.dataset_id == second.dataset_id
    assert db.scalar(select(func.count()).select_from(MarketDataset)) == 1
    assert db.scalar(select(func.count()).select_from(PriceBar)) == TRADING_DAYS
    roles = {u.email: u.role for u in db.scalars(select(User))}
    assert roles == {DEMO_TRADER[0]: UserRole.TRADER, DEMO_ADMIN[0]: UserRole.ADMIN}


def test_demo_trader_can_log_in_and_start_a_session(db, anon_client):
    dataset = seed_demo(db)
    login = anon_client.post("/auth/login", json={"email": DEMO_TRADER[0], "password": DEMO_TRADER[2]})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = anon_client.post(
        "/sessions",
        headers=headers,
        json={
            "dataset_id": str(dataset.dataset_id),
            "period_start": "2023-03-01T00:00:00Z",
            "period_end": "2023-06-30T00:00:00Z",
        },
    )

    assert response.status_code == 201, response.text
