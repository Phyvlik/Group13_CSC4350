from typing import Literal

from pydantic import BaseModel, model_validator


class UpdateUserRequest(BaseModel):
    """Admin change to another account. Uses the same labels as UserOut."""

    role: Literal["Trader", "Admin"] | None = None
    status: Literal["Active", "Disabled"] | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "UpdateUserRequest":
        if self.role is None and self.status is None:
            raise ValueError("Provide role and/or status")
        return self
