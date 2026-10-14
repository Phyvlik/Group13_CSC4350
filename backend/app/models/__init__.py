"""SQLAlchemy ORM models. Import every model here so Alembic can discover them."""

from app.models.user import User

__all__ = ["User"]
