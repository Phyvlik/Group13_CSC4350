import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.enums import AccountStatus, UserRole
from app.models.user import User

EMAIL_PATTERN = re.compile(r"^\S+@\S+\.\S+$")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email address")
    return email


def _check_new_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str
    display_name: str = Field(min_length=1, max_length=100)

    _email = field_validator("email")(_normalize_email)
    _password = field_validator("password")(_check_new_password)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = None
    current_password: str | None = None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str | None) -> str | None:
        return value if value is None else _check_new_password(value)

    @model_validator(mode="after")
    def check_fields(self) -> "UpdateMeRequest":
        if self.display_name is None and self.password is None:
            raise ValueError("Provide display_name and/or password")
        if self.password is not None and not self.current_password:
            raise ValueError("current_password is required to change the password")
        return self


class UserOut(BaseModel):
    """Public user shape. Matches the User type in frontend/src/auth.tsx and never exposes password_hash."""

    id: str
    name: str
    email: str
    role: Literal["Trader", "Admin"]
    status: Literal["Active", "Disabled"]

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.user_id),
            name=user.display_name,
            email=user.email,
            role="Admin" if user.role == UserRole.ADMIN else "Trader",
            status="Active" if user.account_status == AccountStatus.ACTIVE else "Disabled",
        )


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: Literal["bearer"] = "bearer"
