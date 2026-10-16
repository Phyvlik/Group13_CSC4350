"""initial schema from ERD

Revision ID: 0001
Revises:
Create Date: 2026-10-14

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AMOUNT = sa.Numeric(18, 6)
UUID_DEFAULT = sa.text("gen_random_uuid()")

user_role = sa.Enum("TRADER", "ADMIN", name="user_role")
account_status = sa.Enum("ACTIVE", "SUSPENDED", "DEACTIVATED", name="account_status")
session_status = sa.Enum("ACTIVE", "PAUSED", "COMPLETED", "ABANDONED", name="session_status")
trade_side = sa.Enum("BUY", "SELL", name="trade_side")
metric_code = sa.Enum("PNL", "WIN_RATE", "EXPOSURE", "LOSS_CHASING", name="metric_code")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", user_role, server_default="TRADER", nullable=False),
        sa.Column("account_status", account_status, server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "instruments",
        sa.Column("instrument_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quote_currency", sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint("instrument_id", name="pk_instruments"),
        sa.UniqueConstraint("symbol", "exchange", name="uq_instruments_symbol_exchange"),
    )

    op.create_table(
        "metrics",
        sa.Column("metric_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("code", metric_code, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("calculation_rule", sa.Text(), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("metric_id", name="pk_metrics"),
    )

    op.create_table(
        "market_datasets",
        sa.Column("dataset_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("imported_by", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("interval", sa.String(20), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("dataset_id", name="pk_market_datasets"),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.instrument_id"],
            name="fk_market_datasets_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by"],
            ["users.user_id"],
            name="fk_market_datasets_imported_by_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_market_datasets_instrument_id", "market_datasets", ["instrument_id"])

    op.create_table(
        "price_bars",
        sa.Column("bar_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("bar_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", AMOUNT, nullable=False),
        sa.Column("high_price", AMOUNT, nullable=False),
        sa.Column("low_price", AMOUNT, nullable=False),
        sa.Column("close_price", AMOUNT, nullable=False),
        sa.Column("volume", AMOUNT, nullable=False),
        sa.PrimaryKeyConstraint("bar_id", name="pk_price_bars"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["market_datasets.dataset_id"],
            name="fk_price_bars_dataset_id_market_datasets",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("dataset_id", "bar_at", name="uq_price_bars_dataset_id_bar_at"),
    )

    op.create_table(
        "practice_sessions",
        sa.Column("session_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replay_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replay_speed", sa.Numeric(6, 2), server_default="1.00", nullable=False),
        sa.Column("initial_cash", AMOUNT, nullable=False),
        sa.Column("cash_balance", AMOUNT, nullable=False),
        sa.Column("position_quantity", AMOUNT, server_default="0", nullable=False),
        sa.Column("average_cost", AMOUNT, server_default="0", nullable=False),
        sa.Column("status", session_status, server_default="ACTIVE", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id", name="pk_practice_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_practice_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["market_datasets.dataset_id"],
            name="fk_practice_sessions_dataset_id_market_datasets",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_practice_sessions_user_id", "practice_sessions", ["user_id"])
    op.create_index("ix_practice_sessions_dataset_id", "practice_sessions", ["dataset_id"])

    op.create_table(
        "trades",
        sa.Column("trade_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("side", trade_side, nullable=False),
        sa.Column("quantity", AMOUNT, nullable=False),
        sa.Column("execution_price", AMOUNT, nullable=False),
        sa.Column("fee", AMOUNT, server_default="0", nullable=False),
        sa.Column("realized_pnl", AMOUNT, nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_revealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("trade_id", name="pk_trades"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.session_id"],
            name="fk_trades_session_id_practice_sessions",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_trades_session_id", "trades", ["session_id"])

    op.create_table(
        "journal_entries",
        sa.Column("journal_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("trade_id", sa.Uuid(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("journal_id", name="pk_journal_entries"),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            ["trades.trade_id"],
            name="fk_journal_entries_trade_id_trades",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("trade_id", name="uq_journal_entries_trade_id"),
    )

    op.create_table(
        "session_metrics",
        sa.Column("session_metric_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("metric_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("value", AMOUNT, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_metric_id", name="pk_session_metrics"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.session_id"],
            name="fk_session_metrics_session_id_practice_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["metric_id"],
            ["metrics.metric_id"],
            name="fk_session_metrics_metric_id_metrics",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "session_id", "metric_id", "revision", name="uq_session_metrics_session_id_metric_id_revision"
        ),
    )
    op.create_index("ix_session_metrics_metric_id", "session_metrics", ["metric_id"])

    op.create_table(
        "tracked_habits",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("metric_id", sa.Uuid(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "metric_id", name="pk_tracked_habits"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_tracked_habits_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["metric_id"],
            ["metrics.metric_id"],
            name="fk_tracked_habits_metric_id_metrics",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "feedback",
        sa.Column("feedback_id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("pattern_code", sa.String(50), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("analysis_version", sa.String(20), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id", name="pk_feedback"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.session_id"],
            name="fk_feedback_session_id_practice_sessions",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_feedback_session_id", "feedback", ["session_id"])

    op.create_table(
        "feedback_evidence",
        sa.Column("feedback_id", sa.Uuid(), nullable=False),
        sa.Column("session_metric_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id", "session_metric_id", name="pk_feedback_evidence"),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["feedback.feedback_id"],
            name="fk_feedback_evidence_feedback_id_feedback",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_metric_id"],
            ["session_metrics.session_metric_id"],
            name="fk_feedback_evidence_session_metric_id_session_metrics",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("feedback_evidence")
    op.drop_index("ix_feedback_session_id", table_name="feedback")
    op.drop_table("feedback")
    op.drop_table("tracked_habits")
    op.drop_index("ix_session_metrics_metric_id", table_name="session_metrics")
    op.drop_table("session_metrics")
    op.drop_table("journal_entries")
    op.drop_index("ix_trades_session_id", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_practice_sessions_dataset_id", table_name="practice_sessions")
    op.drop_index("ix_practice_sessions_user_id", table_name="practice_sessions")
    op.drop_table("practice_sessions")
    op.drop_table("price_bars")
    op.drop_index("ix_market_datasets_instrument_id", table_name="market_datasets")
    op.drop_table("market_datasets")
    op.drop_table("metrics")
    op.drop_table("instruments")
    op.drop_table("users")

    for enum_type in (metric_code, trade_side, session_status, account_status, user_role):
        op.execute(f"DROP TYPE IF EXISTS {enum_type.name}")
