from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_database_url = get_settings().database_url
# Keep PostgreSQL sessions in UTC so the API always returns UTC timestamps, whatever the server's zone is.
_connect_args = {"options": "-c timezone=utc"} if _database_url.startswith("postgresql") else {}

engine = create_engine(_database_url, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
