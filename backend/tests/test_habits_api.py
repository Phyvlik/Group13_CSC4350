"""Habit selection and verified history acceptance tests."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_feedback_api import make_session

from app.models.metric import Metric, SessionMetric, TrackedHabit


def catalog(client):
    response = client.get("/habits")
    assert response.status_code == 200, response.text
    return response.json()


def choose(client, code="LOSS_CHASING", active=True):
    metric = next(m for m in catalog(client)["metrics"] if m["code"] == code)
    response = client.post(
        "/habits", json={"metric_id": metric["metric_id"], "active": active}
    )
    assert response.status_code == 200, response.text
    return metric, response.json()


def test_catalog_lists_real_supported_versioned_metrics_without_writes(db, client):
    metric_count = db.scalar(select(func.count()).select_from(Metric))
    result = catalog(client)
    assert {m["code"] for m in result["metrics"]} == {
        "LOSS_CHASING",
        "PNL",
        "WIN_RATE",
        "EXPOSURE",
    }
    assert result["tracked"] == []
    for metric in result["metrics"]:
        assert (
            metric["calculation_rule"]
            and metric["calculation_version"]
            and metric["unit"]
        )
    assert db.scalar(select(func.count()).select_from(TrackedHabit)) == 0
    assert db.scalar(select(func.count()).select_from(Metric)) == metric_count


def test_selection_is_persisted_idempotent_and_can_be_disabled_and_restored(
    db, client, user_1
):
    metric, first = choose(client)
    _, second = choose(client)
    assert first == second
    record = db.get(TrackedHabit, (user_1.user_id, UUID(metric["metric_id"])))
    assert record.active
    assert db.scalar(select(func.count()).select_from(TrackedHabit)) == 1
    choose(client, active=False)
    db.refresh(record)
    assert not record.active
    choose(client)
    db.refresh(record)
    assert record.active
    assert db.scalar(select(func.count()).select_from(TrackedHabit)) == 1


def test_selecting_new_metric_replaces_active_selection(db, client, user_1):
    first, _ = choose(client, "LOSS_CHASING")
    second, result = choose(client, "WIN_RATE")
    assert [h["metric_id"] for h in result["tracked"] if h["active"]] == [
        second["metric_id"]
    ]
    assert not db.get(TrackedHabit, (user_1.user_id, UUID(first["metric_id"]))).active


def test_habit_selection_is_scoped_to_user(db, client, client_user_2):
    choose(client)
    assert catalog(client_user_2)["tracked"] == []


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/habits", None),
        ("post", "/habits", {"metric_id": str(uuid4())}),
        ("get", "/habits/" + str(uuid4()) + "/history", None),
    ],
)
def test_habits_require_authentication(anon_client, method, path, body):
    response = getattr(anon_client, method)(
        path, **({"json": body} if body is not None else {})
    )
    assert response.status_code == 401


def test_unknown_metric_and_untracked_history_are_rejected(client):
    assert client.post("/habits", json={"metric_id": str(uuid4())}).status_code == 404
    metric = catalog(client)["metrics"][0]
    assert client.get(f"/habits/{metric['metric_id']}/history").status_code == 404


@pytest.mark.parametrize(
    "body",
    [{}, {"metric_id": "not-a-uuid"}, {"metric_id": str(uuid4()), "active": "wrong"}],
)
def test_invalid_habit_inputs_are_rejected(client, body):
    assert client.post("/habits", json=body).status_code == 422


def test_history_empty_is_not_a_fabricated_zero(client):
    metric, _ = choose(client)
    result = client.get(f"/habits/{metric['metric_id']}/history").json()
    assert result["points"] == []
    assert result["has_more"] is False


def test_history_latest_revision_order_pagination_and_ownership(
    db, client, user_1, user_2, sample_dataset
):
    metric, _ = choose(client)
    mid = UUID(metric["metric_id"])
    sessions = [
        make_session(
            db,
            user_1,
            sample_dataset,
            started_at=datetime(2026, 11, n, tzinfo=UTC),
        )
        for n in (1, 2, 3)
    ]
    other = make_session(db, user_2, sample_dataset)
    now = datetime(2026, 11, 17, tzinfo=UTC)
    for n, session in enumerate(sessions + [other]):
        for revision in (1, 2):
            db.add(
                SessionMetric(
                    session_metric_id=uuid4(),
                    session_id=session.session_id,
                    metric_id=mid,
                    revision=revision,
                    value=Decimal(n * 10 + revision),
                    computed_at=now,
                    verified_at=now,
                )
            )
    db.commit()
    response = client.get(f"/habits/{mid}/history?limit=2&offset=0")
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["has_more"]
    assert [p["session_id"] for p in first["points"]] == [
        str(sessions[2].session_id),
        str(sessions[1].session_id),
    ]
    assert [Decimal(p["value"]) for p in first["points"]] == [22, 12]
    assert all(
        p["revision"] == 2 and p["verified_at"] and p["quote_currency"] == "USD"
        for p in first["points"]
    )
    last = client.get(f"/habits/{mid}/history?limit=2&offset=2").json()
    assert [p["session_id"] for p in last["points"]] == [str(sessions[0].session_id)]
    assert last["has_more"] is False


def test_latest_unverified_history_does_not_expose_older_verified_value(
    db, client, user_1, sample_dataset
):
    metric, _ = choose(client)
    session = make_session(db, user_1, sample_dataset)
    mid = UUID(metric["metric_id"])
    for revision, verified in ((1, datetime.now(UTC)), (2, None)):
        db.add(
            SessionMetric(
                session_metric_id=uuid4(),
                session_id=session.session_id,
                metric_id=mid,
                revision=revision,
                value=Decimal(revision),
                verified_at=verified,
            )
        )
    db.commit()
    response = client.get(f"/habits/{mid}/history")
    assert response.status_code == 409


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_history_rejects_invalid_pagination(client, query):
    metric, _ = choose(client)
    assert (
        client.get(f"/habits/{metric['metric_id']}/history?{query}").status_code == 422
    )


@pytest.mark.parametrize("code", ["WIN_RATE", "EXPOSURE"])
def test_history_does_not_reuse_metric_omitted_from_latest_statistics_batch(
    db, client, user_1, sample_dataset, code
):
    metric, _ = choose(client, code)
    pnl = next(m for m in catalog(client)["metrics"] if m["code"] == "PNL")
    session = make_session(db, user_1, sample_dataset)
    now = datetime.now(UTC)
    for metric_id, revision, value in [
        (metric["metric_id"], 1, "0.5"),
        (pnl["metric_id"], 1, "0"),
        (pnl["metric_id"], 2, "0"),
    ]:
        db.add(
            SessionMetric(
                session_metric_id=uuid4(),
                session_id=session.session_id,
                metric_id=UUID(metric_id),
                revision=revision,
                value=Decimal(value),
                computed_at=now,
                verified_at=now,
            )
        )
    db.commit()
    response = client.get(f"/habits/{metric['metric_id']}/history")
    assert response.status_code == 200, response.text
    assert response.json()["points"] == []
