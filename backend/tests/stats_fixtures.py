"""Independent SQLite fixtures for the statistics database contract.

Only tests create these tables. Production remains dependent on the team's
schema migration; this fixture is not a migration or a substitute for testing
PostgreSQL transaction and row-lock behavior.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, Numeric, String, Table,
    Text, UniqueConstraint, Uuid, create_engine, event,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _contract_tables():
    metadata = MetaData()
    amount = Numeric(18, 6)
    Table(
        "users", metadata,
        Column("user_id", Uuid, primary_key=True),
        Column("account_status", String, nullable=False, default="ACTIVE"),
    )
    Table(
        "instruments", metadata,
        Column("instrument_id", Uuid, primary_key=True),
        Column("quote_currency", String(10), nullable=False),
    )
    Table(
        "market_datasets", metadata,
        Column("dataset_id", Uuid, primary_key=True),
        Column("instrument_id", Uuid, ForeignKey("instruments.instrument_id"), nullable=False),
    )
    Table(
        "practice_sessions", metadata,
        Column("session_id", Uuid, primary_key=True),
        Column("user_id", Uuid, ForeignKey("users.user_id"), nullable=False),
        Column("dataset_id", Uuid, ForeignKey("market_datasets.dataset_id"), nullable=False),
        Column("period_start", DateTime(timezone=True), nullable=False),
        Column("period_end", DateTime(timezone=True), nullable=False),
        Column("replay_at", DateTime(timezone=True), nullable=False),
        Column("cash_balance", amount, nullable=False),
        Column("position_quantity", amount, nullable=False),
    )
    Table(
        "trades", metadata,
        Column("trade_id", Uuid, primary_key=True),
        Column("session_id", Uuid, ForeignKey("practice_sessions.session_id"), nullable=False),
        Column("side", String, nullable=False),
        Column("realized_pnl", amount, nullable=True),
        Column("fee", amount, nullable=False, default=Decimal("0")),
        Column("placed_at", DateTime(timezone=True), nullable=False),
    )
    Table(
        "price_bars", metadata,
        Column("bar_id", Uuid, primary_key=True),
        Column("dataset_id", Uuid, ForeignKey("market_datasets.dataset_id"), nullable=False),
        Column("bar_at", DateTime(timezone=True), nullable=False),
        Column("close_price", amount, nullable=False),
        UniqueConstraint("dataset_id", "bar_at"),
    )
    Table(
        "metrics", metadata,
        Column("metric_id", Uuid, primary_key=True),
        Column("code", String, nullable=False),
        Column("name", String(100), nullable=False),
        Column("unit", String(20), nullable=False),
        Column("calculation_rule", Text, nullable=False),
        Column("calculation_version", String(20), nullable=False),
    )
    Table(
        "session_metrics", metadata,
        Column("session_metric_id", Uuid, primary_key=True),
        Column("session_id", Uuid, ForeignKey("practice_sessions.session_id"), nullable=False),
        Column("metric_id", Uuid, ForeignKey("metrics.metric_id"), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("value", amount, nullable=False),
        Column("computed_at", DateTime(timezone=True), nullable=False),
        Column("verified_at", DateTime(timezone=True), nullable=True),
        UniqueConstraint("session_id", "metric_id", "revision"),
    )
    return metadata


class StatsDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        self.addCleanup(self.engine.dispose)
        self.metadata = _contract_tables()
        self.tables = self.metadata.tables
        self.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.now = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
        self.start = self.now - timedelta(hours=1)
        self.end = self.now + timedelta(hours=1)
        self.user = uuid4()
        self.other_user = uuid4()
        self.db.execute(self.tables["users"].insert(), [
            {"user_id": self.user, "account_status": "ACTIVE"},
            {"user_id": self.other_user, "account_status": "ACTIVE"},
        ])
        self.dataset_id = self.create_dataset()
        self.instrument_id = self.db.execute(
            self.tables["market_datasets"].select().where(
                self.tables["market_datasets"].c.dataset_id == self.dataset_id
            )
        ).mappings().one()["instrument_id"]
        self.session_id = self.create_session()
        self.add_price(Decimal("100"))

    def create_dataset(self, currency: str = "USD") -> UUID:
        instrument_id, dataset_id = uuid4(), uuid4()
        self.db.execute(self.tables["instruments"].insert().values(
            instrument_id=instrument_id, quote_currency=currency,
        ))
        self.db.execute(self.tables["market_datasets"].insert().values(
            dataset_id=dataset_id, instrument_id=instrument_id,
        ))
        return dataset_id

    def create_session(
        self, *, session_id=None, user_id=None, dataset_id=None,
        cash_balance=Decimal("10000"), position_quantity=Decimal("0"),
        period_start=None, period_end=None, replay_at=None,
    ) -> UUID:
        session_id = session_id if session_id is not None else uuid4()
        self.db.execute(self.tables["practice_sessions"].insert().values(
            session_id=session_id,
            user_id=self.user if user_id is None else user_id,
            dataset_id=self.dataset_id if dataset_id is None else dataset_id,
            cash_balance=cash_balance,
            position_quantity=position_quantity,
            period_start=self.start if period_start is None else period_start,
            period_end=self.end if period_end is None else period_end,
            replay_at=self.now if replay_at is None else replay_at,
        ))
        return session_id

    def add_price(self, price: Decimal, *, at=None, dataset_id=None) -> UUID:
        bar_id = uuid4()
        self.db.execute(self.tables["price_bars"].insert().values(
            bar_id=bar_id,
            dataset_id=self.dataset_id if dataset_id is None else dataset_id,
            bar_at=self.now if at is None else at,
            close_price=price,
        ))
        return bar_id

    def add_trade(
        self, side: str, realized_pnl: Decimal | None = None,
        fee: Decimal = Decimal("0"), *, session_id=None, at=None,
    ) -> UUID:
        trade_id = uuid4()
        self.db.execute(self.tables["trades"].insert().values(
            trade_id=trade_id,
            session_id=self.session_id if session_id is None else session_id,
            side=side, realized_pnl=realized_pnl, fee=fee,
            placed_at=self.now if at is None else at,
        ))
        return trade_id
