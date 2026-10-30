from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import uuid
import pytest

# Ensure backend directory is importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.core.auth import get_current_user, create_access_token
from app.main import app
from app.models.enums import AccountStatus, UserRole
from app.models.instrument import Instrument
from app.models.market_data import MarketDataset, PriceBar
from app.models.user import User


@pytest.fixture(scope="session")
def test_engine():
    """Create an in-memory SQLite database engine shared across tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(test_engine):
    """Provide a transactional database session with tables cleaned between tests."""
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture
def user_1(db):
    """Primary test user."""
    user = User(
        user_id=uuid.uuid4(),
        email=f"trader1_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="secret_hash",
        display_name="Trader One",
        role=UserRole.TRADER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_2(db):
    """Secondary test user for isolation / permission scoping tests."""
    user = User(
        user_id=uuid.uuid4(),
        email=f"trader2_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="secret_hash",
        display_name="Trader Two",
        role=UserRole.TRADER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(db, user_1):
    """TestClient authenticated as user_1."""
    token = create_access_token(user_1.user_id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_user_2(db, user_2):
    """TestClient authenticated as user_2."""
    token = create_access_token(user_2.user_id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_dataset(db, user_1):
    """Sample dataset with an instrument and 6 chronological price bars."""
    instrument = Instrument(
        instrument_id=uuid.uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        name="Apple Inc.",
        quote_currency="USD",
    )
    db.add(instrument)
    db.commit()

    range_start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    range_end = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)

    dataset = MarketDataset(
        dataset_id=uuid.uuid4(),
        instrument_id=instrument.instrument_id,
        imported_by=user_1.user_id,
        provider="polygon",
        interval="1m",
        version="v1.0",
        range_start=range_start,
        range_end=range_end,
    )
    db.add(dataset)
    db.commit()

    bars = []
    prices = [
        Decimal("150.00"),
        Decimal("151.00"),
        Decimal("152.00"),
        Decimal("153.00"),
        Decimal("154.00"),
        Decimal("155.00"),
    ]
    for minute, price in enumerate(prices):
        bar_at = datetime(2024, 1, 1, 10, minute, 0, tzinfo=timezone.utc)
        bar = PriceBar(
            bar_id=uuid.uuid4(),
            dataset_id=dataset.dataset_id,
            bar_at=bar_at,
            open_price=price,
            high_price=price + Decimal("0.50"),
            low_price=price - Decimal("0.50"),
            close_price=price + Decimal("0.25"),
            volume=Decimal("1000"),
        )
        bars.append(bar)
        db.add(bar)

    db.commit()
    db.refresh(dataset)
    return dataset
