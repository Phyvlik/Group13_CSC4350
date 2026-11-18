"""Persist reproducible feedback snapshots, including zero-event analyses.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alembic import op
from app.services.loss_chasing_v2 import LOSS_DEFINITION

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_analyses",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("session_metric_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version", sa.String(20), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["practice_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_metric_id"],
            ["session_metrics.session_metric_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_id"),
        sa.UniqueConstraint("session_metric_id"),
    )
    op.create_index(
        "ix_feedback_analyses_session_id", "feedback_analyses", ["session_id"]
    )

    metrics = sa.table(
        "metrics",
        sa.column("metric_id", sa.Uuid()),
        sa.column("code", sa.Enum("LOSS_CHASING", name="metric_code")),
        sa.column("name", sa.String()),
        sa.column("unit", sa.String()),
        sa.column("calculation_version", sa.String()),
        sa.column("calculation_rule", sa.Text()),
    )
    insert = (
        pg_insert if op.get_context().dialect.name == "postgresql" else sqlite_insert
    )
    op.execute(
        insert(metrics)
        .values(**LOSS_DEFINITION)
        .on_conflict_do_nothing(index_elements=[metrics.c.metric_id])
    )


def downgrade():
    # Preserve the metric used by existing observations and habit selections.
    op.drop_index("ix_feedback_analyses_session_id", table_name="feedback_analyses")
    op.drop_table("feedback_analyses")
