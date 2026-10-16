from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from dateutil import parser
from sqlalchemy import select

from app.models.enums import SessionStatus, TradeSide
from app.models.journal import JournalEntry
from app.models.market_data import PriceBar
from app.models.practice import PracticeSession, Trade
from app.services.replay import ReplayService


def test_get_datasets_lists_instruments(client, sample_dataset):
    """GET /datasets lists datasets and their instruments (FR-1)."""
    response = client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    ds = next(d for d in data if d["dataset_id"] == str(sample_dataset.dataset_id))
    assert ds["provider"] == "polygon"
    assert ds["interval"] == "1m"
    assert ds["instrument"] is not None
    assert ds["instrument"]["symbol"] == "AAPL"
    assert ds["instrument"]["exchange"] == "NASDAQ"


def test_post_sessions_starts_at_period_start(client, sample_dataset):
    """POST /sessions starts session with replay_at at period_start (FR-1, FR-2)."""
    period_start = "2024-01-01T10:01:00Z"
    period_end = "2024-01-01T10:04:00Z"
    initial_cash = 25000.00

    payload = {
        "dataset_id": str(sample_dataset.dataset_id),
        "period_start": period_start,
        "period_end": period_end,
        "initial_cash": initial_cash,
    }

    response = client.post("/sessions", json=payload)
    assert response.status_code == 201
    session_data = response.json()

    assert session_data["session_id"] is not None
    assert session_data["dataset_id"] == str(sample_dataset.dataset_id)
    # Crucial requirement: replay_at starts at period_start
    assert parser.isoparse(session_data["replay_at"]) == parser.isoparse(period_start)
    assert Decimal(str(session_data["initial_cash"])) == Decimal("25000.00")
    assert Decimal(str(session_data["cash_balance"])) == Decimal("25000.00")
    assert session_data["status"] == SessionStatus.ACTIVE.value
    assert session_data["ended_at"] is None


def test_post_sessions_validations(client, sample_dataset):
    """POST /sessions validates date ordering and initial cash."""
    # period_start >= period_end
    bad_dates = {
        "dataset_id": str(sample_dataset.dataset_id),
        "period_start": "2024-01-01T10:05:00Z",
        "period_end": "2024-01-01T10:01:00Z",
        "initial_cash": 10000.0,
    }
    res = client.post("/sessions", json=bad_dates)
    assert res.status_code == 400

    # Non-existent dataset
    bad_ds = {
        "dataset_id": str(uuid.uuid4()),
        "period_start": "2024-01-01T10:00:00Z",
        "period_end": "2024-01-01T10:05:00Z",
        "initial_cash": 10000.0,
    }
    res = client.post("/sessions", json=bad_ds)
    assert res.status_code == 404

    # Non-positive cash
    bad_cash = {
        "dataset_id": str(sample_dataset.dataset_id),
        "period_start": "2024-01-01T10:00:00Z",
        "period_end": "2024-01-01T10:05:00Z",
        "initial_cash": 0,
    }
    res = client.post("/sessions", json=bad_cash)
    assert res.status_code in (400, 422)


def test_get_session_bars_only_returns_bars_up_to_replay_at(client, sample_dataset):
    """GET /sessions/{id}/bars returns only bars where bar_at <= replay_at (NFR-7)."""
    # Create a session starting at 10:02:00
    period_start = "2024-01-01T10:02:00Z"
    period_end = "2024-01-01T10:05:00Z"

    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": period_start,
            "period_end": period_end,
            "initial_cash": 10000,
        },
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]
    replay_at = parser.isoparse(session_res.json()["replay_at"])

    # Query bars for this session
    bars_res = client.get(f"/sessions/{session_id}/bars")
    assert bars_res.status_code == 200
    bars = bars_res.json()

    # Verify that every bar returned has bar_at <= replay_at
    assert len(bars) > 0
    for bar in bars:
        bar_at = parser.isoparse(bar["bar_at"])
        assert bar_at <= replay_at, f"Leaked future bar {bar_at} > {replay_at}"

    # Verify that future bars (10:03, 10:04, 10:05) are NOT returned
    returned_times = [parser.isoparse(b["bar_at"]) for b in bars]
    future_time = datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
    assert future_time not in returned_times


def test_sql_filter_integrity_nfr7(db, user_1, sample_dataset):
    """Verify that bar_at <= replay_at runs directly in the SQL statement (NFR-7)."""
    session = PracticeSession(
        session_id=uuid.uuid4(),
        user_id=user_1.user_id,
        dataset_id=sample_dataset.dataset_id,
        period_start=datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),
        period_end=datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc),
        replay_at=datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc),
        initial_cash=Decimal("10000"),
        cash_balance=Decimal("10000"),
    )
    db.add(session)
    db.commit()

    # Inspect the SQL statement generated by ReplayService
    stmt = (
        select(PriceBar)
        .where(
            PriceBar.dataset_id == session.dataset_id,
            PriceBar.bar_at <= session.replay_at,
        )
    )
    sql_text = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "price_bars.bar_at <=" in sql_text

    bars = ReplayService.get_session_bars(db, session)
    # Check that in SQL, only bars <= replay_at were fetched
    for b in bars:
        bar_at = b.bar_at if b.bar_at.tzinfo else b.bar_at.replace(tzinfo=timezone.utc)
        assert bar_at <= session.replay_at


def test_post_step_advances_replay_at_and_never_past_period_end(client, sample_dataset):
    """POST /sessions/{id}/step moves replay_at forward by N bars and never past period_end (FR-3)."""
    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:01:00Z",
            "period_end": "2024-01-01T10:03:00Z",
            "initial_cash": 10000,
        },
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]
    period_end = parser.isoparse("2024-01-01T10:03:00Z")

    # Step 1: from 10:01 -> 10:02
    step_res = client.post(f"/sessions/{session_id}/step", json={"count": 1})
    assert step_res.status_code == 200
    new_replay_at = parser.isoparse(step_res.json()["replay_at"])
    assert new_replay_at == datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc)

    # Step 2: from 10:02 -> 10:03 (which is period_end)
    step_res2 = client.post(f"/sessions/{session_id}/step", json={"count": 1})
    assert step_res2.status_code == 200
    new_replay_at2 = parser.isoparse(step_res2.json()["replay_at"])
    assert new_replay_at2 == datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)

    # Step 3: Attempt to step past period_end with count=100
    step_res3 = client.post(f"/sessions/{session_id}/step", json={"count": 100})
    assert step_res3.status_code == 200
    capped_replay_at = parser.isoparse(step_res3.json()["replay_at"])
    assert capped_replay_at <= period_end
    assert capped_replay_at == period_end


def test_patch_session_speed_pausing_and_ending(client, sample_dataset):
    """PATCH /sessions/{id} updates replay_speed, pauses, and ends."""
    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:05:00Z",
            "initial_cash": 10000,
        },
    )
    session_id = session_res.json()["session_id"]

    # 1. Update replay speed
    patch_speed = client.patch(f"/sessions/{session_id}", json={"replay_speed": 2.5})
    assert patch_speed.status_code == 200
    assert Decimal(str(patch_speed.json()["replay_speed"])) == Decimal("2.50")

    # 2. Pause session
    patch_pause = client.patch(f"/sessions/{session_id}", json={"status": "PAUSED"})
    assert patch_pause.status_code == 200
    assert patch_pause.json()["status"] == "PAUSED"

    # 3. Resume session
    patch_resume = client.patch(f"/sessions/{session_id}", json={"status": "ACTIVE"})
    assert patch_resume.status_code == 200
    assert patch_resume.json()["status"] == "ACTIVE"

    # 4. End session (COMPLETED)
    patch_end = client.patch(f"/sessions/{session_id}", json={"status": "COMPLETED"})
    assert patch_end.status_code == 200
    assert patch_end.json()["status"] == "COMPLETED"
    assert patch_end.json()["ended_at"] is not None

    # Stepping an ended session returns 400
    step_res = client.post(f"/sessions/{session_id}/step", json={"count": 1})
    assert step_res.status_code == 400


def test_trade_outcome_requires_journal_entry(db, client, user_1, sample_dataset):
    """GET /trades/{id}/outcome returns next movement only if journaled, otherwise 409 (FR-4)."""
    # Create a practice session
    session = PracticeSession(
        session_id=uuid.uuid4(),
        user_id=user_1.user_id,
        dataset_id=sample_dataset.dataset_id,
        period_start=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        period_end=datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc),
        replay_at=datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),
        initial_cash=Decimal("10000"),
        cash_balance=Decimal("10000"),
    )
    db.add(session)
    db.commit()

    # Place a trade placed at 10:01
    trade = Trade(
        trade_id=uuid.uuid4(),
        session_id=session.session_id,
        side=TradeSide.BUY,
        quantity=Decimal("10"),
        execution_price=Decimal("151.00"),
        placed_at=datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc),
        outcome_revealed_at=None,
    )
    db.add(trade)
    db.commit()

    # 1. Query outcome without journal entry -> MUST return 409 Conflict
    res_no_journal = client.get(f"/trades/{trade.trade_id}/outcome")
    assert res_no_journal.status_code == 409
    assert "journal" in res_no_journal.json()["detail"].lower()

    # Ensure outcome_revealed_at is still null
    db.refresh(trade)
    assert trade.outcome_revealed_at is None

    # 2. Add journal entry
    journal = JournalEntry(
        journal_id=uuid.uuid4(),
        trade_id=trade.trade_id,
        reasoning="Support bounce off 200 EMA with increasing volume",
    )
    db.add(journal)
    db.commit()

    # 3. Query outcome again -> MUST return 200 with next price movement
    res_journaled = client.get(f"/trades/{trade.trade_id}/outcome")
    assert res_journaled.status_code == 200
    outcome = res_journaled.json()

    assert outcome["trade_id"] == str(trade.trade_id)
    assert outcome["outcome_revealed_at"] is not None
    # Next bar is at 10:02 with close price 152.25
    assert outcome["next_bar"] is not None
    assert parser.isoparse(outcome["next_bar"]["bar_at"]) == datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
    assert Decimal(str(outcome["next_price"])) == Decimal("152.25")
    # Price change: 152.25 - 151.00 = 1.25
    assert Decimal(str(outcome["price_change"])) == Decimal("1.25")

    # Ensure database updated outcome_revealed_at
    db.refresh(trade)
    assert trade.outcome_revealed_at is not None


def test_session_endpoints_scoped_to_logged_in_user(db, client, client_user_2, sample_dataset):
    """Every session endpoint is scoped to logged-in user; other user's session returns 404."""
    # User 1 creates a session
    res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:05:00Z",
            "initial_cash": 10000,
        },
    )
    assert res.status_code == 201
    user1_session_id = res.json()["session_id"]

    # User 1 creates a trade
    session1 = db.get(PracticeSession, uuid.UUID(user1_session_id))
    trade1 = Trade(
        trade_id=uuid.uuid4(),
        session_id=session1.session_id,
        side=TradeSide.BUY,
        quantity=Decimal("10"),
        execution_price=Decimal("150.00"),
        placed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    db.add(trade1)
    db.commit()

    # User 2 attempts to access User 1's session and trade -> all must return 404
    assert client_user_2.get(f"/sessions/{user1_session_id}").status_code == 404
    assert client_user_2.get(f"/sessions/{user1_session_id}/bars").status_code == 404
    assert client_user_2.post(f"/sessions/{user1_session_id}/step", json={"count": 1}).status_code == 404
    assert client_user_2.patch(f"/sessions/{user1_session_id}", json={"replay_speed": 2.0}).status_code == 404
    assert client_user_2.get(f"/trades/{trade1.trade_id}/outcome").status_code == 404


def test_no_response_including_errors_ever_contains_future_bars(db, client, user_1, sample_dataset):
    """Tests confirm that no response, including error responses, ever contains a bar after replay_at."""
    future_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    secret_future_price = Decimal("999888.77")

    secret_future_bar = PriceBar(
        bar_id=uuid.uuid4(),
        dataset_id=sample_dataset.dataset_id,
        bar_at=future_time,
        open_price=secret_future_price,
        high_price=secret_future_price + Decimal("1.00"),
        low_price=secret_future_price - Decimal("1.00"),
        close_price=secret_future_price,
        volume=Decimal("500"),
    )
    db.add(secret_future_bar)
    db.commit()

    # Session where replay_at is 10:02 (well before future bar at 11:00)
    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:02:00Z",
            "initial_cash": 10000,
        },
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]

    secret_str = str(secret_future_price)
    secret_bar_id = str(secret_future_bar.bar_id)

    # 1. Normal bar response
    bars_res = client.get(f"/sessions/{session_id}/bars")
    assert bars_res.status_code == 200
    assert secret_str not in bars_res.text
    assert secret_bar_id not in bars_res.text

    # 2. Step response
    step_res = client.post(f"/sessions/{session_id}/step", json={"count": 1})
    assert step_res.status_code == 200
    assert secret_str not in step_res.text
    assert secret_bar_id not in step_res.text

    # 3. Patch response
    patch_res = client.patch(f"/sessions/{session_id}", json={"replay_speed": 3.0})
    assert patch_res.status_code == 200
    assert secret_str not in patch_res.text
    assert secret_bar_id not in patch_res.text

    # 4. Error responses: 422 Unprocessable Entity
    error_422 = client.get(f"/sessions/{session_id}/bars?start_at=not-a-valid-date")
    assert error_422.status_code == 422
    assert secret_str not in error_422.text
    assert secret_bar_id not in error_422.text

    # 5. Error responses: 400 Bad Request
    error_400 = client.post(f"/sessions/{session_id}/step", json={"count": 0})
    assert error_400.status_code in (400, 422)
    assert secret_str not in error_400.text
    assert secret_bar_id not in error_400.text

    # 6. Error responses: 404 Not Found
    error_404 = client.get(f"/sessions/{uuid.uuid4()}/bars")
    assert error_404.status_code == 404
    assert secret_str not in error_404.text
    assert secret_bar_id not in error_404.text


def test_unauthenticated_requests_rejected(sample_dataset):
    """Endpoints require authentication and reject unauthenticated requests (NFR-12)."""
    from app.main import app
    from fastapi.testclient import TestClient

    raw_client = TestClient(app)
    assert raw_client.get("/datasets").status_code == 401
    assert raw_client.post("/sessions", json={}).status_code == 401
    assert raw_client.get(f"/sessions/{uuid.uuid4()}/bars").status_code == 401
    assert raw_client.post(f"/sessions/{uuid.uuid4()}/step", json={}).status_code == 401
    assert raw_client.patch(f"/sessions/{uuid.uuid4()}", json={}).status_code == 401
    assert raw_client.get(f"/trades/{uuid.uuid4()}/outcome").status_code == 401


def test_step_empty_body_and_aliases(client, sample_dataset):
    """POST /sessions/{id}/step supports empty body and alias 'bars'."""
    res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:04:00Z",
            "initial_cash": 10000,
        },
    )
    session_id = res.json()["session_id"]

    # Empty body defaults to count=1 (advance from 10:00 to 10:01)
    step1 = client.post(f"/sessions/{session_id}/step", json={})
    assert step1.status_code == 200
    assert parser.isoparse(step1.json()["replay_at"]) == datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc)

    # Alias "bars" moves 2 bars forward (from 10:01 to 10:03)
    step2 = client.post(f"/sessions/{session_id}/step", json={"bars": 2})
    assert step2.status_code == 200
    assert parser.isoparse(step2.json()["replay_at"]) == datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)


def test_trade_outcome_not_found(client):
    """GET /trades/{id}/outcome returns 404 for non-existent trade."""
    res = client.get(f"/trades/{uuid.uuid4()}/outcome")
    assert res.status_code == 404

