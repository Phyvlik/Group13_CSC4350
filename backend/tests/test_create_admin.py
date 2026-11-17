import pytest
from pydantic import ValidationError

from app.core.security import verify_password
from app.models.enums import AccountStatus, UserRole
from scripts.create_admin import create_admin

PASSWORD = "correct-horse-1"


def test_creates_new_admin(db):
    user, created = create_admin(db, "Boss@Example.com", "Boss", PASSWORD)

    assert created
    assert user.email == "boss@example.com"
    assert user.role == UserRole.ADMIN
    assert user.account_status == AccountStatus.ACTIVE
    assert verify_password(PASSWORD, user.password_hash)


def test_promotes_existing_user_and_keeps_password(db, user_1):
    user_1.account_status = AccountStatus.SUSPENDED
    db.commit()

    user, created = create_admin(db, user_1.email, "Ignored", "another-password")

    assert not created
    assert user.user_id == user_1.user_id
    assert user.role == UserRole.ADMIN
    assert user.account_status == AccountStatus.ACTIVE
    assert user.password_hash == "secret_hash"


def test_rejects_short_password(db):
    with pytest.raises(ValidationError):
        create_admin(db, "boss@example.com", "Boss", "short")


def test_admin_created_by_script_can_log_in_and_list_users(db, anon_client):
    create_admin(db, "boss@example.com", "Boss", PASSWORD)

    token = anon_client.post("/auth/login", json={"email": "boss@example.com", "password": PASSWORD}).json()[
        "access_token"
    ]
    response = anon_client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
