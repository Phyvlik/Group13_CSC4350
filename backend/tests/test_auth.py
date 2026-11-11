import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.main import app
from app.models.enums import AccountStatus
from app.models.user import User

PASSWORD = "correct-horse-1"


@pytest.fixture
def anon_client(db):
    """TestClient with no Authorization header, backed by the test database."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="ada@example.com", password=PASSWORD, display_name="Ada"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_hash_password_round_trip():
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert verify_password(PASSWORD, hashed)
    assert not verify_password("wrong-password", hashed)


def test_register_success(anon_client, db):
    response = register(anon_client, email="Ada@Example.com")

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["name"] == "Ada"
    assert body["user"]["role"] == "Trader"
    assert body["user"]["status"] == "Active"
    assert "password_hash" not in body["user"]

    stored = db.query(User).filter_by(email="ada@example.com").one()
    assert stored.password_hash != PASSWORD
    assert verify_password(PASSWORD, stored.password_hash)


def test_register_duplicate_email_returns_409(anon_client):
    assert register(anon_client).status_code == 201

    response = register(anon_client, email="ADA@example.com", display_name="Other")

    assert response.status_code == 409


def test_register_short_password_returns_422(anon_client):
    response = register(anon_client, password="short")

    assert response.status_code == 422


def test_login_success_returns_token(anon_client):
    register(anon_client)

    response = anon_client.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"

    me = anon_client.get("/auth/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200


def test_login_wrong_password_returns_401(anon_client):
    register(anon_client)

    response = anon_client.post("/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})

    assert response.status_code == 401


def test_login_unknown_email_returns_401(anon_client):
    response = anon_client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})

    assert response.status_code == 401


def test_login_inactive_account_returns_401(anon_client, db):
    register(anon_client)
    user = db.query(User).filter_by(email="ada@example.com").one()
    user.account_status = AccountStatus.SUSPENDED
    db.commit()

    response = anon_client.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 401


def test_me_without_token_returns_401(anon_client):
    response = anon_client.get("/auth/me")

    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(anon_client):
    response = anon_client.get("/auth/me", headers=auth_header("not-a-real-token"))

    assert response.status_code == 401


def test_me_with_token_returns_user_without_password_hash(anon_client):
    registered = register(anon_client).json()

    response = anon_client.get("/auth/me", headers=auth_header(registered["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body == registered["user"]
    assert set(body) == {"id", "name", "email", "role", "status"}
    assert "password_hash" not in response.text


def test_patch_me_updates_name(anon_client):
    token = register(anon_client).json()["access_token"]

    response = anon_client.patch("/auth/me", json={"display_name": "Ada Lovelace"}, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["name"] == "Ada Lovelace"
    assert anon_client.get("/auth/me", headers=auth_header(token)).json()["name"] == "Ada Lovelace"


def test_patch_me_changes_password_with_current_password(anon_client):
    token = register(anon_client).json()["access_token"]

    response = anon_client.patch(
        "/auth/me",
        json={"password": "brand-new-pass", "current_password": PASSWORD},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    old_login = anon_client.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    new_login = anon_client.post("/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_patch_me_password_requires_current_password(anon_client):
    token = register(anon_client).json()["access_token"]

    missing = anon_client.patch("/auth/me", json={"password": "brand-new-pass"}, headers=auth_header(token))
    wrong = anon_client.patch(
        "/auth/me",
        json={"password": "brand-new-pass", "current_password": "wrong-password"},
        headers=auth_header(token),
    )

    assert missing.status_code == 422
    assert wrong.status_code == 400
