import uuid

from app.core.security import hash_password
from app.models.enums import AccountStatus, UserRole
from app.models.user import User

PASSWORD = "correct-horse-1"


def make_trader(db, email="trader@example.com"):
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        display_name="Trader",
        role=UserRole.TRADER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_non_admin_gets_403_on_list_and_update(client, user_2):
    # `client` is authenticated as user_1, a TRADER.
    assert client.get("/admin/users").status_code == 403
    response = client.patch(f"/admin/users/{user_2.user_id}", json={"status": "Disabled"})
    assert response.status_code == 403


def test_unauthenticated_gets_401(anon_client):
    assert anon_client.get("/admin/users").status_code == 401


def test_admin_can_list_users(admin_client, admin_user, db):
    trader = make_trader(db)

    response = admin_client.get("/admin/users")

    assert response.status_code == 200
    by_id = {u["id"]: u for u in response.json()}
    assert by_id[str(admin_user.user_id)]["role"] == "Admin"
    assert by_id[str(trader.user_id)] == {
        "id": str(trader.user_id),
        "name": "Trader",
        "email": "trader@example.com",
        "role": "Trader",
        "status": "Active",
    }
    assert all("password_hash" not in u for u in response.json())


def test_admin_can_disable_a_user(admin_client, db):
    trader = make_trader(db)

    response = admin_client.patch(f"/admin/users/{trader.user_id}", json={"status": "Disabled"})

    assert response.status_code == 200
    assert response.json()["status"] == "Disabled"
    db.refresh(trader)
    assert trader.account_status == AccountStatus.SUSPENDED


def test_disabled_user_cannot_log_in(admin_client, anon_client, db):
    trader = make_trader(db)
    login = {"email": "trader@example.com", "password": PASSWORD}
    assert anon_client.post("/auth/login", json=login).status_code == 200

    admin_client.patch(f"/admin/users/{trader.user_id}", json={"status": "Disabled"})

    response = anon_client.post("/auth/login", json=login)
    assert response.status_code == 401


def test_disabled_user_token_stops_working(admin_client, anon_client, db):
    trader = make_trader(db)
    token = anon_client.post("/auth/login", json={"email": "trader@example.com", "password": PASSWORD}).json()[
        "access_token"
    ]

    admin_client.patch(f"/admin/users/{trader.user_id}", json={"status": "Disabled"})

    response = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_admin_can_reactivate_and_promote_a_user(admin_client, db):
    trader = make_trader(db)
    trader.account_status = AccountStatus.SUSPENDED
    db.commit()

    response = admin_client.patch(f"/admin/users/{trader.user_id}", json={"role": "Admin", "status": "Active"})

    assert response.status_code == 200
    assert response.json()["role"] == "Admin"
    assert response.json()["status"] == "Active"


def test_admin_cannot_demote_or_disable_self(admin_client, admin_user):
    for body in ({"role": "Trader"}, {"status": "Disabled"}):
        response = admin_client.patch(f"/admin/users/{admin_user.user_id}", json=body)
        assert response.status_code == 400


def test_update_unknown_user_returns_404(admin_client):
    response = admin_client.patch(f"/admin/users/{uuid.uuid4()}", json={"status": "Disabled"})
    assert response.status_code == 404


def test_update_with_empty_body_returns_422(admin_client, db):
    trader = make_trader(db)
    response = admin_client.patch(f"/admin/users/{trader.user_id}", json={})
    assert response.status_code == 422
