"""Acceptance tests for evidence-backed feedback using the integrated ORM/API."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.enums import MetricCode, SessionStatus, TradeSide
from app.models.feedback import Feedback, FeedbackAnalysis, FeedbackEvidence
from app.models.journal import JournalEntry
from app.models.metric import Metric, SessionMetric
from app.models.practice import PracticeSession, Trade

START = datetime(2024, 1, 1, 10, tzinfo=UTC)


def make_session(db, user, dataset, *, started_at=None):
    session = PracticeSession(
        session_id=uuid4(),
        user_id=user.user_id,
        dataset_id=dataset.dataset_id,
        period_start=START,
        period_end=START + timedelta(days=1),
        replay_at=START + timedelta(hours=1),
        replay_speed=Decimal(1),
        initial_cash=Decimal(10000),
        cash_balance=Decimal(9000),
        position_quantity=Decimal(0),
        average_cost=Decimal(100),
        status=SessionStatus.ACTIVE,
        started_at=started_at or datetime(2026, 11, 1, tzinfo=UTC),
    )
    db.add(session)
    db.commit()
    return session


def add_trade(db, session, minute, side="BUY", quantity="10", pnl=None):
    trade = Trade(
        trade_id=uuid4(),
        session_id=session.session_id,
        side=TradeSide(side),
        quantity=Decimal(quantity),
        execution_price=Decimal(100),
        fee=Decimal(0),
        realized_pnl=None if pnl is None else Decimal(pnl),
        placed_at=START + timedelta(minutes=minute),
    )
    db.add(trade)
    db.commit()
    return trade


def add_pattern(db, session, *, quantity="15", baseline_count=3, loss="-2"):
    baseline = [add_trade(db, session, n, quantity="10") for n in range(baseline_count)]
    losing = add_trade(db, session, 10, side="SELL", quantity="10", pnl=loss)
    following = add_trade(db, session, 11, quantity=quantity)
    return baseline, losing, following


def analyze(client, session):
    response = client.post(f"/sessions/{session.session_id}/feedback/recompute")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/sessions/{sid}/feedback"),
        ("post", "/sessions/{sid}/feedback/recompute"),
    ],
)
def test_feedback_requires_authentication(anon_client, method, path):
    response = getattr(anon_client, method)(path.format(sid=uuid4()))
    assert response.status_code == 401


@pytest.mark.parametrize("method", ["get", "post"])
def test_feedback_cannot_access_another_users_session(
    db, client_user_2, user_1, sample_dataset, method
):
    session = make_session(db, user_1, sample_dataset)
    suffix = "/recompute" if method == "post" else ""
    response = getattr(client_user_2, method)(
        f"/sessions/{session.session_id}/feedback{suffix}"
    )
    assert response.status_code == 404
    assert db.scalar(select(func.count()).select_from(Feedback)) == 0
    assert db.scalar(select(func.count()).select_from(SessionMetric)) == 0


@pytest.mark.parametrize("method", ["get", "post"])
def test_feedback_missing_session_is_404(client, method):
    suffix = "/recompute" if method == "post" else ""
    assert (
        getattr(client, method)(f"/sessions/{uuid4()}/feedback{suffix}").status_code
        == 404
    )


def test_feedback_get_is_read_only(db, client, user_1, sample_dataset):
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session)
    metric_count = db.scalar(select(func.count()).select_from(Metric))
    response = client.get(f"/sessions/{session.session_id}/feedback")
    assert response.status_code == 200
    assert response.json()["status"] == "not_computed"
    assert db.scalar(select(func.count()).select_from(Metric)) == metric_count
    for model in (Feedback, FeedbackEvidence, SessionMetric):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def add_recurring_pattern(db, session):
    baseline, loss, buy = add_pattern(db, session)
    loss2 = add_trade(db, session, 12, side="SELL", quantity="10", pnl="-3")
    buy2 = add_trade(db, session, 13, quantity="20")
    return baseline, [loss, buy, loss2, buy2]


def test_recurring_pattern_cites_exact_verified_numbers_and_trades(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    _baseline, evidence_trades = add_recurring_pattern(db, session)
    db.add(
        JournalEntry(
            journal_id=uuid4(),
            trade_id=evidence_trades[1].trade_id,
            reasoning="I bought more after my loss.",
        )
    )
    db.commit()
    result = analyze(client, session)
    assert result["status"] == "ready"
    assert Decimal(result["metric"]["value"]) == 2
    assert result["metric"]["verified_at"]
    assert len(result["feedback"]) == 1
    feedback = result["feedback"][0]
    assert feedback["pattern_code"] == "LOSS_CHASING"
    assert set(map(str, [t.trade_id for t in evidence_trades])).issubset(
        feedback["trade_ids"]
    )
    assert feedback["analysis_version"] == result["analysis_version"]
    stored = db.get(Feedback, UUID(feedback["feedback_id"]))
    assert stored.explanation == feedback["explanation"]
    assert stored.explanation.strip()
    for evidence in feedback["evidence"]:
        metric = db.get(SessionMetric, UUID(evidence["session_metric_id"]))
        assert metric.verified_at is not None
        assert metric.value == Decimal(evidence["value"])
        assert metric.session_id == session.session_id
        assert evidence["evidence_reason"]
        for trade_id in evidence["trade_ids"]:
            assert trade_id in evidence["evidence_reason"]
        assert any(
            j["reasoning"] == "I bought more after my loss."
            for j in evidence["journal_entries"]
        )
    metric_definition = db.get(Metric, UUID(result["metric"]["metric_id"]))
    assert metric_definition.code == MetricCode.LOSS_CHASING
    assert "1.5" in metric_definition.calculation_rule
    assert client.get(f"/sessions/{session.session_id}/feedback").json() == result


@pytest.mark.parametrize(
    "quantity,baseline_count,loss,expected",
    [
        ("9.999999", 3, "-2", 0),
        ("10", 3, "-2", 1),
        ("100", 2, "-2", 0),
        ("100", 3, "0", 0),
        ("100", 3, "2", 0),
    ],
)
def test_threshold_minimum_history_and_loss_boundary(
    db, client, user_1, sample_dataset, quantity, baseline_count, loss, expected
):
    session = make_session(db, user_1, sample_dataset)
    add_pattern(
        db, session, quantity=quantity, baseline_count=baseline_count, loss=loss
    )
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == expected
    assert result["feedback"] == []  # One event is not labeled recurring behavior.


def test_no_trades_is_verified_zero_not_fabricated_feedback(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == 0
    assert result["feedback"] == []


def test_recompute_unchanged_inputs_is_idempotent(db, client, user_1, sample_dataset):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    first = analyze(client, session)
    second = analyze(client, session)
    assert first == second
    assert db.scalar(select(func.count()).select_from(Feedback)) == 1
    assert db.scalar(select(func.count()).select_from(SessionMetric)) == 1


def test_unverified_snapshot_is_never_returned_as_evidence(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    result = analyze(client, session)
    metric = db.get(SessionMetric, UUID(result["metric"]["session_metric_id"]))
    metric.verified_at = None
    db.commit()
    response = client.get(f"/sessions/{session.session_id}/feedback")
    assert response.status_code == 409
    assert "feedback_id" not in response.text


def test_latest_unverified_revision_cannot_fall_back_to_old_feedback(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    result = analyze(client, session)
    db.add(
        SessionMetric(
            session_metric_id=uuid4(),
            session_id=session.session_id,
            metric_id=UUID(result["metric"]["metric_id"]),
            revision=2,
            value=Decimal(99),
            verified_at=None,
        )
    )
    db.commit()
    assert client.get(f"/sessions/{session.session_id}/feedback").status_code == 409


def test_future_buy_cannot_change_baseline_or_become_evidence(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session)
    future = add_trade(db, session, 120, quantity="1000")
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == 1
    assert str(future.trade_id) not in str(result)


def test_later_current_session_buys_do_not_change_earlier_baseline(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session)
    add_trade(db, session, 20, quantity="1000")
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == 1


def test_same_timestamp_sell_buy_does_not_invent_order(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    for minute in range(3):
        add_trade(db, session, minute)
    add_trade(db, session, 10, side="SELL", pnl="-2")
    add_trade(db, session, 10, quantity="100")
    assert Decimal(analyze(client, session)["metric"]["value"]) == 0


def test_only_first_buy_after_loss_counts(db, client, user_1, sample_dataset):
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session, quantity="1")
    add_trade(db, session, 12, quantity="100")
    assert Decimal(analyze(client, session)["metric"]["value"]) == 0


@pytest.mark.parametrize(
    "prior_kind,expected",
    [
        ("eligible", 1),
        ("other_user", 0),
        ("other_instrument", 0),
        ("active", 0),
        ("later_session", 0),
    ],
)
def test_prior_baseline_uses_only_owned_completed_earlier_same_instrument_sessions(
    db, client, user_1, user_2, sample_dataset, prior_kind, expected
):
    from app.models.instrument import Instrument
    from app.models.market_data import MarketDataset

    dataset = sample_dataset
    if prior_kind == "other_instrument":
        instrument = Instrument(
            instrument_id=uuid4(),
            symbol="OTHER",
            exchange="TEST",
            name="Other instrument",
            quote_currency="USD",
        )
        db.add(instrument)
        db.flush()
        dataset = MarketDataset(
            dataset_id=uuid4(),
            instrument_id=instrument.instrument_id,
            imported_by=user_1.user_id,
            provider="test",
            interval="1m",
            version="1",
            range_start=START,
            range_end=START + timedelta(days=1),
        )
        db.add(dataset)
        db.commit()
    prior = make_session(
        db,
        user_2 if prior_kind == "other_user" else user_1,
        dataset,
        started_at=datetime(2026, 10, 30, tzinfo=UTC),
    )
    prior.status = (
        SessionStatus.ACTIVE if prior_kind == "active" else SessionStatus.COMPLETED
    )
    prior.ended_at = datetime(2026, 10, 31, tzinfo=UTC)
    if prior_kind == "later_session":
        prior.started_at = datetime(2026, 11, 2, tzinfo=UTC)
        prior.ended_at = datetime(2026, 11, 3, tzinfo=UTC)
    db.commit()
    add_trade(db, prior, 0)
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session, baseline_count=2)
    assert Decimal(analyze(client, session)["metric"]["value"]) == expected


def test_full_trade_api_flow_creates_verified_feedback_and_habit_history(
    db, client, sample_dataset
):
    """Exercise actual trading writes, then analysis, selection, and history APIs."""
    from app.models.market_data import PriceBar

    bars = db.scalars(
        select(PriceBar)
        .where(PriceBar.dataset_id == sample_dataset.dataset_id)
        .order_by(PriceBar.bar_at)
    ).all()
    for minute, bar in enumerate(bars):
        price = Decimal(150 - minute)
        bar.open_price = bar.close_price = price
        bar.high_price = price + 1
        bar.low_price = price - 1
    last_time = START + timedelta(minutes=6)
    db.add(
        PriceBar(
            bar_id=uuid4(),
            dataset_id=sample_dataset.dataset_id,
            bar_at=last_time,
            open_price=Decimal(144),
            close_price=Decimal(144),
            high_price=Decimal(145),
            low_price=Decimal(143),
            volume=Decimal(1000),
        )
    )
    sample_dataset.range_end = last_time
    db.commit()
    response = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": START.isoformat(),
            "period_end": last_time.isoformat(),
            "initial_cash": "10000",
        },
    )
    assert response.status_code == 201, response.text
    sid = response.json()["session_id"]
    orders = [
        ("BUY", 10),
        ("BUY", 10),
        ("BUY", 10),
        ("SELL", 10),
        ("BUY", 15),
        ("SELL", 10),
        ("BUY", 20),
    ]
    for index, (side, quantity) in enumerate(orders):
        if index:
            assert (
                client.post(f"/sessions/{sid}/step", json={"count": 1}).status_code
                == 200
            )
        trade = client.post(
            f"/sessions/{sid}/trades",
            json={"side": side, "quantity": str(quantity), "fee": "0"},
        )
        assert trade.status_code == 201, trade.text
    result = client.post(f"/sessions/{sid}/feedback/recompute")
    assert result.status_code == 200, result.text
    data = result.json()
    assert Decimal(data["metric"]["value"]) == 2
    assert len(data["feedback"]) == 1
    mid = data["metric"]["metric_id"]
    assert client.post("/habits", json={"metric_id": mid}).status_code == 200
    history = client.get(f"/habits/{mid}/history")
    assert history.status_code == 200, history.text
    assert history.json()["points"][0]["session_id"] == sid
    assert Decimal(history.json()["points"][0]["value"]) == 2
    stats = client.post(f"/sessions/{sid}/stats/recompute")
    assert stats.status_code == 200, stats.text
    assert stats.json()["revision"] == 1
    reread = client.get(f"/sessions/{sid}/feedback")
    assert reread.status_code == 200, reread.text
    assert reread.json()["metric"] == data["metric"]


def test_recompute_repairs_unverified_snapshot_without_citing_it(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    first = analyze(client, session)
    unverified_id = UUID(first["metric"]["session_metric_id"])
    old = db.get(SessionMetric, unverified_id)
    old.verified_at = None
    db.commit()
    repaired = analyze(client, session)
    assert repaired["metric"]["session_metric_id"] != str(unverified_id)
    assert repaired["metric"]["revision"] > first["metric"]["revision"]
    for feedback in repaired["feedback"]:
        assert all(
            e["session_metric_id"] != str(unverified_id) for e in feedback["evidence"]
        )
        assert all(e["verified_at"] for e in feedback["evidence"])


def test_journal_edits_refresh_snapshot_instead_of_changing_saved_evidence(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    _, trades = add_recurring_pattern(db, session)
    journal = JournalEntry(
        journal_id=uuid4(), trade_id=trades[1].trade_id, reasoning="Original reasoning."
    )
    db.add(journal)
    db.commit()
    first = analyze(client, session)
    old_feedback = db.get(Feedback, UUID(first["feedback"][0]["feedback_id"]))
    old_evidence = db.scalar(
        select(FeedbackEvidence).where(
            FeedbackEvidence.feedback_id == old_feedback.feedback_id
        )
    )
    saved_reason = old_evidence.evidence_reason
    journal.reasoning = "Updated reasoning."
    db.commit()
    second = analyze(client, session)
    assert second["metric"]["revision"] > first["metric"]["revision"]
    db.refresh(old_evidence)
    assert old_evidence.evidence_reason == saved_reason
    assert any(
        j["reasoning"] == "Updated reasoning."
        for e in second["feedback"][0]["evidence"]
        for j in e["journal_entries"]
    )


def test_failed_source_verification_rolls_back_entire_analysis(
    db, client, user_1, sample_dataset, monkeypatch
):
    from app.services import feedback as service

    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    original = service._input
    calls = 0

    def changed_source(db_arg, session_arg):
        nonlocal calls
        values = list(original(db_arg, session_arg))
        calls += 1
        if calls > 1:
            values[2] = "changed-source-during-verification"
        return tuple(values)

    monkeypatch.setattr(service, "_input", changed_source)
    response = client.post(f"/sessions/{session.session_id}/feedback/recompute")
    assert response.status_code == 409
    for model in (Feedback, FeedbackEvidence, SessionMetric):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_baseline_excludes_hidden_trades_from_prior_session(
    db, client, user_1, sample_dataset
):
    prior = make_session(
        db,
        user_1,
        sample_dataset,
        started_at=datetime(2026, 10, 30, tzinfo=UTC),
    )
    prior.status = SessionStatus.COMPLETED
    prior.ended_at = datetime(2026, 10, 31, tzinfo=UTC)
    prior.replay_at = START
    db.commit()
    add_trade(db, prior, 120, quantity="10")
    session = make_session(db, user_1, sample_dataset)
    add_pattern(db, session, baseline_count=2)
    assert Decimal(analyze(client, session)["metric"]["value"]) == 0


@pytest.mark.parametrize("method", ["get", "post"])
def test_admin_role_does_not_bypass_private_feedback_ownership(
    db, admin_client, user_1, sample_dataset, method
):
    session = make_session(db, user_1, sample_dataset)
    suffix = "/recompute" if method == "post" else ""
    response = getattr(admin_client, method)(
        f"/sessions/{session.session_id}/feedback{suffix}"
    )
    assert response.status_code == 404


def test_recompute_replaces_newer_unverified_revision_instead_of_reusing_old_snapshot(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    first = analyze(client, session)
    mid = UUID(first["metric"]["metric_id"])
    unverified = SessionMetric(
        session_metric_id=uuid4(),
        session_id=session.session_id,
        metric_id=mid,
        revision=2,
        value=Decimal(100),
        verified_at=None,
    )
    db.add(unverified)
    db.commit()
    repaired = analyze(client, session)
    assert repaired["metric"]["revision"] == 3
    assert Decimal(repaired["metric"]["value"]) == 2
    assert repaired["metric"]["session_metric_id"] not in [
        first["metric"]["session_metric_id"],
        str(unverified.session_metric_id),
    ]
    assert all(
        e["session_metric_id"] == repaired["metric"]["session_metric_id"]
        for f in repaired["feedback"]
        for e in f["evidence"]
    )


def saved_events(db, result):
    snapshot = db.scalar(
        select(FeedbackAnalysis).where(
            FeedbackAnalysis.session_metric_id
            == UUID(result["metric"]["session_metric_id"])
        )
    )
    return json.loads(snapshot.evidence_json)["events"]


def test_small_order_can_increase_total_holdings_to_loss_chasing_threshold(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    baselines = [add_trade(db, session, n, quantity="10") for n in range(3)]
    loss = add_trade(db, session, 10, side="SELL", quantity="0.1", pnl="-1")
    buy = add_trade(db, session, 11, quantity="0.1")
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == 1
    event = saved_events(db, result)[0]
    assert Decimal(event["buy_quantity"]) == Decimal("0.1")
    assert Decimal(event["position_before"]) == Decimal("29.9")
    assert Decimal(event["position_after"]) == 30
    assert Decimal(event["baseline_total"]) == 60
    assert Decimal(event["baseline_mean"]) == 20
    assert event["baseline_count"] == 3
    assert event["baseline_trade_ids"] == [str(t.trade_id) for t in baselines]
    assert event["loss_trade_id"] == str(loss.trade_id)
    assert event["buy_trade_id"] == str(buy.trade_id)


def test_large_order_reopening_smaller_total_position_is_not_flagged(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    for minute in range(3):
        add_trade(db, session, minute, quantity="10")
    add_trade(db, session, 10, side="SELL", quantity="30", pnl="-2")
    add_trade(db, session, 11, quantity="15")
    result = analyze(client, session)
    # 15 is 1.5x the prior ORDER size (10), but below 1.5x prior HOLDINGS (20).
    assert Decimal(result["metric"]["value"]) == 0
    assert saved_events(db, result) == []


def test_recurring_feedback_persists_actual_positions_not_order_sizes(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_recurring_pattern(db, session)
    result = analyze(client, session)
    events = saved_events(db, result)
    assert len(events) == 2
    assert [
        (Decimal(e["position_before"]), Decimal(e["position_after"])) for e in events
    ] == [(Decimal(20), Decimal(35)), (Decimal(25), Decimal(45))]
    assert [Decimal(e["baseline_mean"]) for e in events] == [
        Decimal(20),
        Decimal("23.75"),
    ]
    assert result["analysis_version"] == "loss-chasing-v2"


@pytest.mark.parametrize("candidate,expected", [("15", 0), ("25", 1)])
def test_prior_baseline_reconstructs_sells_and_resets_holdings_each_session(
    db, client, user_1, sample_dataset, candidate, expected
):
    prior = make_session(
        db, user_1, sample_dataset, started_at=datetime(2026, 10, 30, tzinfo=UTC)
    )
    prior.status = SessionStatus.COMPLETED
    prior.ended_at = datetime(2026, 10, 31, tzinfo=UTC)
    db.commit()
    p1 = add_trade(db, prior, 0, quantity="10")
    p2 = add_trade(db, prior, 1, quantity="10")
    prior_sell = add_trade(db, prior, 2, side="SELL", quantity="15", pnl="1")
    p3 = add_trade(db, prior, 3, quantity="10")
    current = make_session(db, user_1, sample_dataset)
    first = add_trade(db, current, 0, quantity="10")
    add_trade(db, current, 1, side="SELL", quantity="10", pnl="-1")
    add_trade(db, current, 2, quantity=candidate)
    result = analyze(client, current)
    assert Decimal(result["metric"]["value"]) == expected
    if expected:
        event = saved_events(db, result)[0]
        assert Decimal(event["position_before"]) == 0
        assert Decimal(event["position_after"]) == 25
        assert Decimal(event["baseline_total"]) == 55
        assert event["baseline_count"] == 4
        assert Decimal(event["baseline_mean"]) == Decimal("13.75")
        assert event["baseline_trade_ids"] == [
            str(t.trade_id) for t in (p1, p2, p3, first)
        ]
        snapshot = db.scalar(
            select(FeedbackAnalysis).where(
                FeedbackAnalysis.session_metric_id
                == UUID(result["metric"]["session_metric_id"])
            )
        )
        support = json.loads(snapshot.evidence_json)["support_trade_ids"]
        assert str(prior_sell.trade_id) in support


@pytest.mark.parametrize("initial_buy,sold", [("0", "1"), ("10", "11")])
def test_unreconstructable_or_negative_position_is_rejected_without_feedback(
    db, client, user_1, sample_dataset, initial_buy, sold
):
    session = make_session(db, user_1, sample_dataset)
    if Decimal(initial_buy):
        add_trade(db, session, 0, quantity=initial_buy)
    add_trade(db, session, 1, side="SELL", quantity=sold, pnl="-1")
    response = client.post(f"/sessions/{session.session_id}/feedback/recompute")
    assert response.status_code == 409
    for model in (SessionMetric, Feedback, FeedbackEvidence, FeedbackAnalysis):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_simultaneous_fills_update_holdings_without_creating_ordered_baseline_samples(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_trade(db, session, 0, quantity="10")
    add_trade(db, session, 0, quantity="20")
    # The ambiguous pair nets 30, but neither postBUY position can be known.
    add_trade(db, session, 1, quantity="10")  # first known baseline:40
    add_trade(db, session, 2, quantity="10")  # second known baseline:50
    add_trade(db, session, 3, side="SELL", quantity="1", pnl="-1")
    add_trade(db, session, 4, quantity="100")
    assert Decimal(analyze(client, session)["metric"]["value"]) == 0


def test_known_positions_after_ambiguous_group_use_its_net_holdings(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    add_trade(db, session, 0, quantity="10")
    add_trade(db, session, 0, quantity="20")
    known = [add_trade(db, session, minute, quantity="10") for minute in (1, 2, 3)]
    add_trade(db, session, 4, side="SELL", quantity="10", pnl="-1")
    add_trade(db, session, 5, quantity="25")
    result = analyze(client, session)
    assert Decimal(result["metric"]["value"]) == 1
    event = saved_events(db, result)[0]
    assert Decimal(event["position_before"]) == 50
    assert Decimal(event["position_after"]) == 75
    assert Decimal(event["baseline_mean"]) == 50
    assert event["baseline_trade_ids"] == [str(t.trade_id) for t in known]


def test_baseline_limits_to_last_twenty_known_post_buy_positions(
    db, client, user_1, sample_dataset
):
    session = make_session(db, user_1, sample_dataset)
    buys = [add_trade(db, session, minute, quantity="1") for minute in range(21)]
    add_trade(db, session, 22, side="SELL", quantity="1", pnl="-1")
    add_trade(db, session, 23, quantity="1")
    result = analyze(client, session)
    event = saved_events(db, result)[0]
    assert event["baseline_count"] == 20
    assert Decimal(event["baseline_total"]) == sum(map(Decimal, range(2, 22)))
    assert Decimal(event["baseline_mean"]) == Decimal("11.5")
    assert event["baseline_trade_ids"] == [str(t.trade_id) for t in buys[1:]]
