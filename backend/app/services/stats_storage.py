"""Append and verify statistics against the team's existing schema.

No tables are created here. The caller commits or rolls back the transaction.
Recomputation locks the parent session row, which trade writers must also
update/lock atomically. PostgreSQL is the deployment target; SQLite is used
only for contract tests, not as evidence of concurrent row-lock behavior.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from uuid import UUID, uuid4, uuid5

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Uuid, case, column, func, select, table, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.repositories.stats import load_session
from app.services.stats import calculate_snapshot_stats


CALCULATION_VERSION = "1-proposed"
_NAMESPACE = UUID("d654ef62-5706-45f1-a027-412547122d32")
_SCALE = Decimal("0.000001")
_MAX_VALUE = Decimal("999999999999.999999")

metrics = table(
    "metrics", column("metric_id", Uuid),
    column("code", Enum("PNL", "WIN_RATE", "EXPOSURE", "LOSS_CHASING", name="metric_code")),
    column("name", String), column("unit", String),
    column("calculation_rule", String), column("calculation_version", String),
)
session_metrics = table(
    "session_metrics", column("session_metric_id", Uuid), column("session_id", Uuid),
    column("metric_id", Uuid), column("revision", Integer), column("value", Numeric(18, 6)),
    column("computed_at", DateTime(timezone=True)), column("verified_at", DateTime(timezone=True)),
)

_RULES = {
    "PNL": ("Realized profit and loss", "quote currency",
            "Sum SELL realized_pnl minus every BUY/SELL fee exactly once; "
            "BUY realized_pnl must be null or zero. Excludes unrealized P/L."),
    "WIN_RATE": ("Win rate", "ratio",
                 "Positive gross realized_pnl SELL fills / all SELL fills, including partial sells. "
                 "Break-even is not a win; no SELL fills means undefined and no observation is saved."),
    "EXPOSURE": ("Current exposure", "ratio",
                 "PROPOSED pending team approval: long-only position_quantity * latest visible close "
                 "/ (cash_balance + position value). Price is bounded by session range and replay_at. "
                 "Missing price for an open position or zero equity means undefined; no observation is saved."),
}
METRIC_IDS = {code: uuid5(_NAMESPACE, f"{code}:{CALCULATION_VERSION}") for code in _RULES}


class StatsNotComputed(Exception):
    """No complete verified batch exists for the current calculation version."""


class StatsConflict(Exception):
    """Stored rules or values do not match the proposed calculation contract."""


def _rounded(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("A metric must be finite.")
    if abs(value) > _MAX_VALUE:
        raise ValueError("A metric exceeds the database's Numeric(18,6) range.")
    with localcontext() as context:
        context.prec = 38
        rounded = value.quantize(_SCALE, rounding=ROUND_HALF_EVEN)
    if abs(rounded) > _MAX_VALUE:
        raise ValueError("A metric exceeds the database's Numeric(18,6) range.")
    return rounded


def seed_metric_definitions(db: Session) -> None:
    """Idempotent definitions keyed by deterministic code/version UUIDs.

    Never overwrite an existing rule: historical observations refer to it.
    Different proposed rules must receive a new version and UUID.
    """
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": pg_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise RuntimeError("Statistics storage supports PostgreSQL and SQLite only.")
    for code, (name, unit, rule) in _RULES.items():
        values = {
            "metric_id": METRIC_IDS[code], "code": code, "name": name, "unit": unit,
            "calculation_rule": rule + " Values rounded to six decimals using ROUND_HALF_EVEN.",
            "calculation_version": CALCULATION_VERSION,
        }
        db.execute(insert(metrics).values(**values).on_conflict_do_nothing(index_elements=[metrics.c.metric_id]))
        existing = db.execute(select(metrics).where(metrics.c.metric_id == values["metric_id"])).mappings().one()
        if any(existing[key] != value for key, value in values.items()):
            raise StatsConflict("An existing metric definition differs; create a new calculation version.")


def _values(snapshot) -> dict[str, Decimal]:
    stats = calculate_snapshot_stats(snapshot)
    values = {
        "PNL": _rounded(stats.trades.pnl),
        "WIN_RATE": _rounded(stats.trades.win_rate),
        "EXPOSURE": _rounded(stats.exposure.exposure_ratio),
    }
    return {code: value for code, value in values.items() if value is not None}


def recompute_session_stats(db: Session, user_id: UUID, session_id: UUID) -> dict:
    """Append one atomic revision, compare persisted values, then verify it.

    Undefined metrics are omitted, not stored as zero. All observations in a
    batch share a revision; readers never fill missing values from old batches.
    A savepoint removes the entire new batch if verification fails.
    """
    with db.begin_nested():
        snapshot = load_session(db, user_id, session_id, lock=True)
        seed_metric_definitions(db)
        revision = (db.scalar(select(func.max(session_metrics.c.revision)).where(
            session_metrics.c.session_id == session_id,
        )) or 0) + 1
        computed_at = datetime.now(timezone.utc)
        values = _values(snapshot)
        db.execute(session_metrics.insert(), [
            {"session_metric_id": uuid4(), "session_id": session_id, "metric_id": METRIC_IDS[code],
             "revision": revision, "value": value, "computed_at": computed_at, "verified_at": None}
            for code, value in values.items()
        ])
        batch = (
            (session_metrics.c.session_id == session_id)
            & (session_metrics.c.revision == revision)
            & session_metrics.c.metric_id.in_(list(METRIC_IDS.values()))
        )
        stored = dict(db.execute(select(session_metrics.c.metric_id, session_metrics.c.value).where(batch)).all())
        expected = _values(load_session(db, user_id, session_id, lock=True))
        if stored != {METRIC_IDS[code]: value for code, value in expected.items()}:
            raise StatsConflict("Metric verification failed; no new verified revision was saved.")
        verified_at = datetime.now(timezone.utc)
        db.execute(update(session_metrics).where(batch).values(verified_at=verified_at))
        return _response(snapshot, revision, computed_at, verified_at, expected)


def _response(snapshot, revision, computed_at, verified_at, values) -> dict:
    return {
        "session_id": snapshot.session_id, "quote_currency": snapshot.quote_currency,
        "revision": revision, "computed_at": computed_at, "verified_at": verified_at,
        "calculation_version": CALCULATION_VERSION, "pnl": values["PNL"],
        "win_rate": values.get("WIN_RATE"), "exposure_ratio": values.get("EXPOSURE"),
    }


def read_verified_stats(db: Session, user_id: UUID, session_id: UUID) -> dict:
    """Return the latest verified batch, with its computation timestamp.

    This is a saved historical snapshot, not a claim that current inputs are
    unchanged. Recompute explicitly after trades or replay movement.
    """
    snapshot = load_session(db, user_id, session_id)
    base = (
        (session_metrics.c.session_id == session_id)
        & session_metrics.c.metric_id.in_(list(METRIC_IDS.values()))
    )
    revision = db.scalar(
        select(session_metrics.c.revision).where(base)
        .group_by(session_metrics.c.revision)
        .having(
            func.count() == func.count(session_metrics.c.verified_at),
            func.sum(case((session_metrics.c.metric_id == METRIC_IDS["PNL"], 1), else_=0)) == 1,
        )
        .order_by(session_metrics.c.revision.desc()).limit(1)
    )
    if revision is None:
        raise StatsNotComputed("No verified statistics are available. Recompute this session first.")
    rows = db.execute(select(session_metrics).where(base, session_metrics.c.revision == revision)).mappings().all()
    codes = {metric_id: code for code, metric_id in METRIC_IDS.items()}
    values = {codes[row["metric_id"]]: row["value"] for row in rows}
    if "PNL" not in values:
        raise StatsNotComputed("The latest verified batch is incomplete.")
    return _response(snapshot, revision, rows[0]["computed_at"], rows[0]["verified_at"], values)
