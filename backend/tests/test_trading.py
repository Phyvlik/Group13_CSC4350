from decimal import Decimal
import uuid

from app.models.enums import SessionStatus, TradeSide
from app.models.practice import PracticeSession


def test_buy_orders_atomic_updates_and_rejections(db, client, client_user_2, sample_dataset):
    """Test BUY trade execution, atomic balance/position updates, and rejections (FR-5, FR-6, FR-7, FR-8, NFR-8)."""
    # 1. Setup session with 10,000 initial cash (FR-5: cash_balance starts at initial_cash)
    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:05:00Z",
            "initial_cash": 10000.00,
        },
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]
    assert Decimal(str(session_res.json()["cash_balance"])) == Decimal("10000.00")
    assert Decimal(str(session_res.json()["position_quantity"])) == Decimal("0")

    # 2. Place first BUY order at 10:00 (bar close price is 150.25)
    # Order: buy 10 shares with fee 2.50 -> cost = 10 * 150.25 + 2.50 = 1505.00
    buy_res1 = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 10, "fee": 2.50},
    )
    assert buy_res1.status_code == 201
    trade1 = buy_res1.json()
    assert trade1["side"] == TradeSide.BUY.value
    assert Decimal(str(trade1["quantity"])) == Decimal("10")
    assert Decimal(str(trade1["execution_price"])) == Decimal("150.25")
    assert Decimal(str(trade1["fee"])) == Decimal("2.50")
    assert trade1["realized_pnl"] is None
    assert trade1["outcome_revealed_at"] is None

    # Verify session updated: cash 10000 - 1505 = 8495.00, pos 10, avg cost 150.25
    s1 = client.get(f"/sessions/{session_id}").json()
    assert Decimal(str(s1["cash_balance"])) == Decimal("8495.00")
    assert Decimal(str(s1["position_quantity"])) == Decimal("10")
    assert Decimal(str(s1["average_cost"])) == Decimal("150.25")

    # 3. Advance replay by 1 step to 10:01 (bar close price is 151.25)
    client.post(f"/sessions/{session_id}/step", json={"count": 1})

    # Place second BUY order: buy 10 more shares with 0 fee -> cost = 10 * 151.25 = 1512.50
    buy_res2 = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 10, "fee": 0},
    )
    assert buy_res2.status_code == 201
    assert Decimal(str(buy_res2.json()["execution_price"])) == Decimal("151.25")

    # Verify weighted average cost: (10 * 150.25 + 10 * 151.25) / 20 = 150.75
    # Cash: 8495.00 - 1512.50 = 6982.50
    s2 = client.get(f"/sessions/{session_id}").json()
    assert Decimal(str(s2["cash_balance"])) == Decimal("6982.50")
    assert Decimal(str(s2["position_quantity"])) == Decimal("20")
    assert Decimal(str(s2["average_cost"])) == Decimal("150.75")

    # 4. Over-balance rejection (FR-8): Attempt to buy 100 shares (costs ~15,125 > 6,982.50)
    over_cash = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 100, "fee": 0},
    )
    assert over_cash.status_code == 400
    assert "insufficient cash" in over_cash.json()["detail"].lower()

    # NFR-8: Verify cash and position unchanged after failed trade
    db_session = db.get(PracticeSession, uuid.UUID(session_id))
    db.refresh(db_session)
    assert db_session.cash_balance == Decimal("6982.50")
    assert db_session.position_quantity == Decimal("20")

    # 5. Invalid quantity & fee rejections
    bad_qty = client.post(f"/sessions/{session_id}/trades", json={"side": "BUY", "quantity": 0})
    assert bad_qty.status_code in (400, 422)

    neg_qty = client.post(f"/sessions/{session_id}/trades", json={"side": "BUY", "quantity": -5})
    assert neg_qty.status_code in (400, 422)

    neg_fee = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 1, "fee": -2},
    )
    assert neg_fee.status_code in (400, 422)

    # 6. Rejection on ended session
    client.patch(f"/sessions/{session_id}", json={"status": SessionStatus.COMPLETED.value})
    ended_trade = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 1},
    )
    assert ended_trade.status_code == 400
    assert "ended session" in ended_trade.json()["detail"].lower()

    # 7. User scoping: User 2 cannot trade on User 1's session
    unauthorized = client_user_2.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 1},
    )
    assert unauthorized.status_code == 404


def test_sell_orders_realized_pnl_and_rejections(db, client, client_user_2, sample_dataset):
    """Test SELL trade execution, realized P/L computation, and trade listing (FR-6, FR-7, FR-8, NFR-8)."""
    # 1. Setup session and establish initial position of 20 shares @ 150.25 (cash = 6995.00)
    session_res = client.post(
        "/sessions",
        json={
            "dataset_id": str(sample_dataset.dataset_id),
            "period_start": "2024-01-01T10:00:00Z",
            "period_end": "2024-01-01T10:05:00Z",
            "initial_cash": 10000.00,
        },
    )
    session_id = session_res.json()["session_id"]
    buy_res = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "BUY", "quantity": 20, "fee": 0},
    )
    assert buy_res.status_code == 201

    # 2. Over-position rejection (FR-8): holding 20 shares, attempt to sell 25
    over_pos = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "SELL", "quantity": 25, "fee": 0},
    )
    assert over_pos.status_code == 400
    assert "insufficient position" in over_pos.json()["detail"].lower()

    # Verify atomic state untouched (NFR-8)
    s_mid = client.get(f"/sessions/{session_id}").json()
    assert Decimal(str(s_mid["position_quantity"])) == Decimal("20")
    assert Decimal(str(s_mid["cash_balance"])) == Decimal("6995.00")

    # 3. Step to 10:02 (bar close price is 152.25)
    client.post(f"/sessions/{session_id}/step", json={"count": 2})

    # Partial SELL: sell 5 shares @ 152.25 with fee 1.25
    # Gross proceeds: 5 * 152.25 = 761.25. Net proceeds: 761.25 - 1.25 = 760.00
    # Realized PnL: 5 * (152.25 - 150.25) - 1.25 = 10.00 - 1.25 = 8.75
    partial_sell = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "SELL", "quantity": 5, "fee": 1.25},
    )
    assert partial_sell.status_code == 201
    trade_sell1 = partial_sell.json()
    assert trade_sell1["side"] == TradeSide.SELL.value
    assert Decimal(str(trade_sell1["quantity"])) == Decimal("5")
    assert Decimal(str(trade_sell1["execution_price"])) == Decimal("152.25")
    assert Decimal(str(trade_sell1["realized_pnl"])) == Decimal("8.75")

    # Verify session after partial sell:
    # Cash: 6995.00 + 760.00 = 7755.00
    # Position: 20 - 5 = 15
    # Average cost remains 150.25
    s_partial = client.get(f"/sessions/{session_id}").json()
    assert Decimal(str(s_partial["cash_balance"])) == Decimal("7755.00")
    assert Decimal(str(s_partial["position_quantity"])) == Decimal("15")
    assert Decimal(str(s_partial["average_cost"])) == Decimal("150.25")

    # 4. Step to 10:03 (bar close price is 153.25)
    client.post(f"/sessions/{session_id}/step", json={"count": 1})

    # Full closing SELL: sell remaining 15 shares @ 153.25 with fee 0
    # Gross proceeds: 15 * 153.25 = 2298.75
    # Realized PnL: 15 * (153.25 - 150.25) = 15 * 3.00 = 45.00
    closing_sell = client.post(
        f"/sessions/{session_id}/trades",
        json={"side": "SELL", "quantity": 15, "fee": 0},
    )
    assert closing_sell.status_code == 201
    trade_sell2 = closing_sell.json()
    assert Decimal(str(trade_sell2["realized_pnl"])) == Decimal("45.00")

    # Verify session fully closed:
    # Cash: 7755.00 + 2298.75 = 10053.75
    # Position: 0, Average cost: 0
    s_closed = client.get(f"/sessions/{session_id}").json()
    assert Decimal(str(s_closed["cash_balance"])) == Decimal("10053.75")
    assert Decimal(str(s_closed["position_quantity"])) == Decimal("0")
    assert Decimal(str(s_closed["average_cost"])) == Decimal("0")

    # 5. List trades via GET /sessions/{id}/trades
    trades_res = client.get(f"/sessions/{session_id}/trades")
    assert trades_res.status_code == 200
    trades_list = trades_res.json()
    assert len(trades_list) == 3
    assert trades_list[0]["side"] == TradeSide.BUY.value
    assert trades_list[1]["side"] == TradeSide.SELL.value
    assert trades_list[2]["side"] == TradeSide.SELL.value

    # 6. Scoping: User 2 cannot list User 1's trades
    assert client_user_2.get(f"/sessions/{session_id}/trades").status_code == 404
