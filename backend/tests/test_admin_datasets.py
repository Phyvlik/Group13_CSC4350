import uuid

from sqlalchemy import func, select

from app.models.market_data import MarketDataset, PriceBar


def start_session(client, dataset):
    response = client.post(
        "/sessions",
        json={
            "dataset_id": str(dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:05:00Z",
        },
    )
    assert response.status_code == 201, response.text


def test_non_admin_gets_403(client, sample_dataset):
    # `client` is authenticated as user_1, a TRADER.
    assert client.get("/admin/datasets").status_code == 403
    assert client.delete(f"/admin/datasets/{sample_dataset.dataset_id}").status_code == 403


def test_admin_lists_datasets_with_bar_and_session_counts(admin_client, client, sample_dataset):
    start_session(client, sample_dataset)

    response = admin_client.get("/admin/datasets")

    assert response.status_code == 200
    [row] = response.json()
    assert row["dataset_id"] == str(sample_dataset.dataset_id)
    assert row["symbol"] == "AAPL"
    assert row["exchange"] == "NASDAQ"
    assert row["interval"] == "1m"
    assert row["bar_count"] == 6
    assert row["session_count"] == 1


def test_admin_can_delete_unused_dataset_and_its_bars(admin_client, db, sample_dataset):
    response = admin_client.delete(f"/admin/datasets/{sample_dataset.dataset_id}")

    assert response.status_code == 204
    assert db.get(MarketDataset, sample_dataset.dataset_id) is None
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 0
    assert admin_client.get("/admin/datasets").json() == []


def test_delete_dataset_used_by_a_session_returns_409(admin_client, client, db, sample_dataset):
    start_session(client, sample_dataset)

    response = admin_client.delete(f"/admin/datasets/{sample_dataset.dataset_id}")

    assert response.status_code == 409
    assert "practice session" in response.json()["detail"]
    assert db.get(MarketDataset, sample_dataset.dataset_id) is not None
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 6


def test_delete_unknown_dataset_returns_404(admin_client):
    assert admin_client.delete(f"/admin/datasets/{uuid.uuid4()}").status_code == 404
