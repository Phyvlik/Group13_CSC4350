"""Versioned feedback snapshots; explicit writes share the trading session lock."""

import json
from collections import deque
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
from itertools import groupby
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import Row, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.enums import SessionStatus, TradeSide
from app.models.feedback import Feedback, FeedbackAnalysis, FeedbackEvidence
from app.models.instrument import Instrument
from app.models.journal import JournalEntry
from app.models.market_data import MarketDataset
from app.models.metric import Metric, SessionMetric, TrackedHabit
from app.models.practice import PracticeSession, Trade
from app.models.user import User
from app.services.loss_chasing_v2 import (
    ANALYSIS_VERSION,
    BASELINE_WINDOW,
    LOSS_CHASING_ID,
    LOSS_DEFINITION,
    MIN_BASELINE,
    MIN_RECURRING_EVENTS,
    SIZE_MULTIPLIER,
)
from app.services.stats_storage import (
    METRIC_IDS,
    StatsConflict,
    metric_definitions,
    seed_metric_definitions,
)

SUPPORTED_IDS = frozenset([LOSS_CHASING_ID, *METRIC_IDS.values()])


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@contextmanager
def errors(db):
    try:
        yield
    except (IntegrityError, ValueError, StatsConflict) as exc:
        db.rollback()
        raise HTTPException(
            409, "Feedback data changed or is invalid; recompute and retry."
        ) from exc
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        raise HTTPException(503, "The feedback database is unavailable.") from exc


def _insert(db, model):
    dialect = db.get_bind().dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError("Only PostgreSQL and SQLite are supported.")
    return (pg_insert if dialect == "postgresql" else sqlite_insert)(model)


def seed_loss_metric(db: Session) -> Metric:
    db.execute(
        _insert(db, Metric)
        .values(**LOSS_DEFINITION)
        .on_conflict_do_nothing(index_elements=[Metric.metric_id])
    )
    metric = db.get(Metric, LOSS_CHASING_ID, populate_existing=True)
    if any(getattr(metric, key) != value for key, value in LOSS_DEFINITION.items()):
        raise ValueError("Metric definition changed without a version change.")
    return metric


def _session(db, user_id, session_id, lock=False):
    stmt = select(PracticeSession).where(
        PracticeSession.session_id == session_id, PracticeSession.user_id == user_id
    )
    if lock:
        stmt = stmt.with_for_update()
    session = db.scalar(stmt.execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(404, "Session not found.")
    return session


def _input(db, session):
    instrument = db.scalar(
        select(MarketDataset.instrument_id).where(
            MarketDataset.dataset_id == session.dataset_id
        )
    )
    # Reconstruct prior holdings before selecting the latest baseline samples.
    groups = (
        select(
            Trade.session_id,
            Trade.placed_at,
            func.count().label("fill_count"),
            func.sum(
                case(
                    (Trade.side == TradeSide.BUY, Trade.quantity), else_=-Trade.quantity
                )
            ).label("delta"),
        )
        .join(PracticeSession)
        .join(MarketDataset, PracticeSession.dataset_id == MarketDataset.dataset_id)
        .where(
            PracticeSession.user_id == session.user_id,
            PracticeSession.session_id != session.session_id,
            PracticeSession.status == SessionStatus.COMPLETED,
            PracticeSession.ended_at <= session.started_at,
            PracticeSession.started_at < session.started_at,
            MarketDataset.instrument_id == instrument,
            Trade.placed_at >= PracticeSession.period_start,
            Trade.placed_at <= PracticeSession.period_end,
            Trade.placed_at <= PracticeSession.replay_at,
        )
        .group_by(Trade.session_id, Trade.placed_at)
        .subquery()
    )
    positions = select(
        groups,
        func.sum(groups.c.delta)
        .over(
            partition_by=groups.c.session_id,
            order_by=groups.c.placed_at,
            rows=(None, 0),
        )
        .label("position_quantity"),
    ).subquery()
    invalid_position = db.scalar(
        select(positions.c.session_id).where(positions.c.position_quantity < 0).limit(1)
    )
    if invalid_position is not None:
        raise ValueError("Prior trades produce negative holdings.")
    previous = db.execute(
        select(
            Trade.trade_id,
            Trade.session_id,
            Trade.placed_at,
            positions.c.position_quantity,
        )
        .join(
            positions,
            (Trade.session_id == positions.c.session_id)
            & (Trade.placed_at == positions.c.placed_at),
        )
        .join(PracticeSession, Trade.session_id == PracticeSession.session_id)
        .where(positions.c.fill_count == 1, Trade.side == TradeSide.BUY)
        .order_by(
            PracticeSession.ended_at.desc(),
            PracticeSession.session_id.desc(),
            Trade.placed_at.desc(),
            Trade.trade_id.desc(),
        )
        .limit(BASELINE_WINDOW)
    ).all()
    cutoffs = {}
    for row in previous:
        cutoffs[row.session_id] = max(
            cutoffs.get(row.session_id, row.placed_at), row.placed_at
        )
    prior_support = []
    if cutoffs:
        prior_support = db.execute(
            select(
                Trade.trade_id,
                Trade.session_id,
                Trade.side,
                Trade.quantity,
                Trade.placed_at,
            )
            .join(PracticeSession)
            .where(
                or_(
                    *[
                        (Trade.session_id == sid) & (Trade.placed_at <= cutoff)
                        for sid, cutoff in cutoffs.items()
                    ]
                ),
                Trade.placed_at >= PracticeSession.period_start,
                Trade.placed_at <= PracticeSession.period_end,
                Trade.placed_at <= PracticeSession.replay_at,
            )
            .order_by(Trade.session_id, Trade.placed_at, Trade.trade_id)
        ).all()
        if any(
            not row.quantity.is_finite() or row.quantity <= 0 for row in prior_support
        ):
            raise ValueError("Invalid prior trade quantity.")
    rows = db.execute(
        select(
            Trade.trade_id,
            Trade.side,
            Trade.quantity,
            Trade.realized_pnl,
            Trade.placed_at,
            JournalEntry.reasoning,
        )
        .outerjoin(JournalEntry, Trade.trade_id == JournalEntry.trade_id)
        .where(
            Trade.session_id == session.session_id,
            Trade.placed_at >= session.period_start,
            Trade.placed_at <= session.period_end,
            Trade.placed_at <= session.replay_at,
        )
        .order_by(Trade.placed_at, Trade.trade_id)
    ).all()
    payload = {
        "version": ANALYSIS_VERSION,
        "baseline": [list(row) for row in reversed(previous)],
        "prior_support": [list(row) for row in prior_support],
        "trades": [list(row) for row in rows],
        "replay_at": _utc(session.replay_at),
        "period_start": _utc(session.period_start),
        "period_end": _utc(session.period_end),
    }
    digest = sha256(
        json.dumps(payload, default=str, sort_keys=True).encode()
    ).hexdigest()
    return previous, rows, digest, prior_support


def detect(previous: Sequence[Row], rows: Sequence[Row]) -> list[dict]:
    """Compare post-BUY holdings in one pass; timestamp ties cannot imply order."""
    baseline = deque(
        ((str(r.trade_id), r.position_quantity) for r in reversed(previous)),
        maxlen=BASELINE_WINDOW,
    )
    if any(not value.is_finite() or value <= 0 for _, value in baseline):
        raise ValueError("Invalid baseline position.")
    events = []
    pending_loss = None
    position = Decimal(0)
    with localcontext() as context:
        context.prec = 38
        for _, group in groupby(rows, key=lambda row: row.placed_at):
            group = list(group)
            if any(not r.quantity.is_finite() or r.quantity <= 0 for r in group):
                raise ValueError("Invalid trade quantity.")
            if any(r.side not in (TradeSide.BUY, TradeSide.SELL) for r in group):
                raise ValueError("Invalid trade side.")
            sells = [r for r in group if r.side == TradeSide.SELL]
            if any(
                r.realized_pnl is None or not r.realized_pnl.is_finite() for r in sells
            ):
                raise ValueError("SELL must have a finite realized result.")
            before = position
            position += sum(
                (r.quantity if r.side == TradeSide.BUY else -r.quantity for r in group),
                Decimal(0),
            )
            if position < 0:
                raise ValueError("Trades produce negative holdings.")
            if len(group) != 1:
                pending_loss = None
                continue
            trade = group[0]
            if trade.side == TradeSide.SELL:
                pending_loss = trade if trade.realized_pnl < 0 else None
                continue
            if pending_loss is not None and len(baseline) >= MIN_BASELINE:
                total = sum((value for _, value in baseline), Decimal(0))
                # Compare products to avoid rounding the threshold.
                if position * len(baseline) >= SIZE_MULTIPLIER * total:
                    loss = pending_loss
                    journals = [
                        {"trade_id": str(r.trade_id), "reasoning": r.reasoning}
                        for r in (loss, trade)
                        if r.reasoning
                    ]
                    events.append(
                        {
                            "loss_trade_id": str(loss.trade_id),
                            "buy_trade_id": str(trade.trade_id),
                            "loss_pnl": str(loss.realized_pnl),
                            "buy_quantity": str(trade.quantity),
                            "position_before": str(before),
                            "position_after": str(position),
                            "baseline_total": str(total),
                            "baseline_count": len(baseline),
                            "baseline_mean": str(total / len(baseline)),
                            "baseline_trade_ids": [key for key, _ in baseline],
                            "journal_entries": journals,
                        }
                    )
            pending_loss = None
            baseline.append((str(trade.trade_id), position))
    return events


def _latest(db, session_id):
    return db.execute(
        select(FeedbackAnalysis, SessionMetric)
        .join(
            SessionMetric,
            FeedbackAnalysis.session_metric_id == SessionMetric.session_metric_id,
        )
        .where(
            FeedbackAnalysis.session_id == session_id,
            FeedbackAnalysis.analysis_version == ANALYSIS_VERSION,
        )
        .order_by(SessionMetric.revision.desc())
        .limit(1)
    ).first()


def _require_verified(db, analysis, observation):
    latest_revision = db.scalar(
        select(func.max(SessionMetric.revision)).where(
            SessionMetric.session_id == analysis.session_id,
            SessionMetric.metric_id == LOSS_CHASING_ID,
        )
    )
    if observation.verified_at is None or observation.revision != latest_revision:
        raise HTTPException(
            409, "Latest feedback observation is not verified; recompute first."
        )


def _read(db, session_id):
    result = {
        "session_id": session_id,
        "analysis_version": ANALYSIS_VERSION,
        "status": "not_computed",
        "computed_at": None,
        "metric": None,
        "feedback": [],
    }
    pair = _latest(db, session_id)
    if pair is None:
        return result
    analysis, observation = pair
    _require_verified(db, analysis, observation)
    items = db.execute(
        select(Feedback, FeedbackEvidence)
        .join(FeedbackEvidence, Feedback.feedback_id == FeedbackEvidence.feedback_id)
        .where(
            FeedbackEvidence.session_metric_id == observation.session_metric_id,
            Feedback.session_id == session_id,
            Feedback.analysis_version == ANALYSIS_VERSION,
        )
    ).all()
    snapshot = json.loads(analysis.evidence_json)
    events = snapshot["events"]
    trade_ids = snapshot["support_trade_ids"]
    journals = list(
        {j["trade_id"]: j for e in events for j in e["journal_entries"]}.values()
    )
    result.update(
        status="ready",
        computed_at=observation.computed_at,
        metric=observation,
        feedback=[
            {
                "feedback_id": f.feedback_id,
                "pattern_code": f.pattern_code,
                "explanation": f.explanation,
                "analysis_version": f.analysis_version,
                "generated_at": f.generated_at,
                "trade_ids": trade_ids,
                "evidence": [
                    {
                        "session_metric_id": observation.session_metric_id,
                        "metric_code": "LOSS_CHASING",
                        "value": observation.value,
                        "verified_at": observation.verified_at,
                        "evidence_reason": e.evidence_reason,
                        "trade_ids": trade_ids,
                        "journal_entries": journals,
                    }
                ],
            }
            for f, e in items
        ],
    )
    return result


def read_feedback(db: Session, user_id: UUID, session_id: UUID) -> dict:
    _session(db, user_id, session_id)
    return _read(db, session_id)


def recompute_feedback(db: Session, user_id: UUID, session_id: UUID) -> dict:
    session = _session(db, user_id, session_id, lock=True)
    seed_loss_metric(db)
    previous, rows, digest, prior_support = _input(db, session)
    latest = _latest(db, session_id)
    latest_revision = db.scalar(
        select(func.max(SessionMetric.revision)).where(
            SessionMetric.session_id == session_id,
            SessionMetric.metric_id == LOSS_CHASING_ID,
        )
    )
    if (
        latest
        and latest[0].source_hash == digest
        and latest[1].verified_at is not None
        and latest[1].revision == latest_revision
    ):
        return _read(db, session_id)
    events = detect(previous, rows)
    revision = (latest_revision or 0) + 1
    now = datetime.now(UTC)
    observation = SessionMetric(
        session_metric_id=uuid4(),
        session_id=session_id,
        metric_id=LOSS_CHASING_ID,
        revision=revision,
        value=Decimal(len(events)),
        computed_at=now,
        verified_at=None,
    )
    db.add(observation)
    db.flush()
    # Verify the saved value and reloaded inputs.
    db.refresh(observation)
    fresh_previous, fresh_rows, fresh_digest, _ = _input(db, session)
    if fresh_digest != digest or observation.value != Decimal(
        len(detect(fresh_previous, fresh_rows))
    ):
        raise ValueError("Analysis verification failed.")
    observation.verified_at = now
    support_ids = []
    if events:
        baseline_ids = {key for event in events for key in event["baseline_trade_ids"]}
        prior_cutoffs = {}
        for row in previous:
            if str(row.trade_id) in baseline_ids:
                prior_cutoffs[row.session_id] = max(
                    prior_cutoffs.get(row.session_id, row.placed_at), row.placed_at
                )
        support_ids.extend(
            str(row.trade_id)
            for row in prior_support
            if row.session_id in prior_cutoffs
            and row.placed_at <= prior_cutoffs[row.session_id]
        )
        buy_ids = {event["buy_trade_id"] for event in events}
        last_buy = max(row.placed_at for row in rows if str(row.trade_id) in buy_ids)
        support_ids.extend(
            str(row.trade_id) for row in rows if row.placed_at <= last_buy
        )
    saved_evidence = {
        "events": events,
        "support_trade_ids": list(dict.fromkeys(support_ids)),
    }
    analysis = FeedbackAnalysis(
        analysis_id=uuid4(),
        session_id=session_id,
        session_metric_id=observation.session_metric_id,
        analysis_version=ANALYSIS_VERSION,
        source_hash=digest,
        evidence_json=json.dumps(saved_evidence, sort_keys=True),
    )
    db.add(analysis)
    db.flush()
    if len(events) >= MIN_RECURRING_EVENTS:
        # Explain the verified count using saved evidence.
        persisted_snapshot = json.loads(analysis.evidence_json)
        persisted_events = persisted_snapshot["events"]
        reasons = []
        for event in persisted_events:
            reasons.append(
                f"Loss trade {event['loss_trade_id']} recorded P/L {event['loss_pnl']}; "
                f"subsequent BUY {event['buy_trade_id']} added {event['buy_quantity']} shares to "
                f"{event['position_before']}, producing holdings of {event['position_after']}, at least "
                f"1.5 times the prior {event['baseline_count']}-position mean {event['baseline_mean']}."
            )
        reasons.append(
            "Calculation trades: "
            + ", ".join(persisted_snapshot["support_trade_ids"])
            + "."
        )
        feedback = Feedback(
            feedback_id=uuid4(),
            session_id=session_id,
            pattern_code="LOSS_CHASING",
            explanation=f"In this session, {int(observation.value)} larger post-BUY positions followed losing sells "
            "and met the documented size rule. This describes recorded behavior, not your intent.",
            analysis_version=ANALYSIS_VERSION,
            generated_at=now,
        )
        db.add(feedback)
        db.flush()
        db.add(
            FeedbackEvidence(
                feedback_id=feedback.feedback_id,
                session_metric_id=observation.session_metric_id,
                evidence_reason=" ".join(reasons),
            )
        )
        db.flush()
    return _read(db, session_id)


def _catalog():
    return [*metric_definitions(), LOSS_DEFINITION.copy()]


def read_habits(db: Session, user_id: UUID) -> dict:
    tracked = db.scalars(
        select(TrackedHabit)
        .where(
            TrackedHabit.user_id == user_id,
            TrackedHabit.metric_id.in_(SUPPORTED_IDS),
            TrackedHabit.active.is_(True),
        )
        .order_by(TrackedHabit.selected_at.desc())
    ).all()
    return {"metrics": _catalog(), "tracked": tracked}


def select_habit(
    db: Session, user_id: UUID, metric_id: UUID, active: bool = True
) -> dict:
    if metric_id not in SUPPORTED_IDS:
        raise HTTPException(404, "Metric not found.")
    # Lock the user to serialize metric selections.
    db.scalar(select(User.user_id).where(User.user_id == user_id).with_for_update())
    if metric_id == LOSS_CHASING_ID:
        seed_loss_metric(db)
    else:
        seed_metric_definitions(db)
    if active:
        db.execute(
            update(TrackedHabit)
            .where(TrackedHabit.user_id == user_id, TrackedHabit.metric_id != metric_id)
            .values(active=False)
        )
    stmt = _insert(db, TrackedHabit).values(
        user_id=user_id,
        metric_id=metric_id,
        active=active,
        selected_at=datetime.now(UTC),
    )
    # Repeated saves keep the selection time.
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[TrackedHabit.user_id, TrackedHabit.metric_id],
            set_={"active": active, "selected_at": datetime.now(UTC)},
            where=TrackedHabit.active != active,
        )
    )
    db.expire_all()
    return read_habits(db, user_id)


def habit_history(
    db: Session, user_id: UUID, metric_id: UUID, limit: int = 50, offset: int = 0
) -> dict:
    if metric_id not in SUPPORTED_IDS:
        raise HTTPException(404, "Metric not found.")
    habit = db.get(TrackedHabit, (user_id, metric_id))
    if habit is None or not habit.active:
        raise HTTPException(404, "Tracked habit not found.")
    metric = db.get(Metric, metric_id)
    # Stats share batch revisions; loss chasing has its own.
    # Omitted metrics must not fall back to older values.
    batch_ids = (
        [metric_id] if metric_id == LOSS_CHASING_ID else list(METRIC_IDS.values())
    )
    latest = (
        select(
            SessionMetric.session_id, func.max(SessionMetric.revision).label("revision")
        )
        .join(PracticeSession, PracticeSession.session_id == SessionMetric.session_id)
        .where(
            PracticeSession.user_id == user_id, SessionMetric.metric_id.in_(batch_ids)
        )
        .group_by(SessionMetric.session_id)
        .subquery()
    )
    latest_join = (SessionMetric.session_id == latest.c.session_id) & (
        SessionMetric.revision == latest.c.revision
    )
    unverified = db.scalar(
        select(SessionMetric.session_metric_id)
        .join(latest, latest_join)
        .where(
            SessionMetric.metric_id.in_(batch_ids), SessionMetric.verified_at.is_(None)
        )
        .limit(1)
    )
    if unverified is not None:
        raise HTTPException(
            409, "Latest habit observation is not verified; recompute first."
        )
    rows = db.execute(
        select(SessionMetric, PracticeSession.started_at, Instrument.quote_currency)
        .join(latest, latest_join)
        .join(PracticeSession, PracticeSession.session_id == SessionMetric.session_id)
        .join(MarketDataset, MarketDataset.dataset_id == PracticeSession.dataset_id)
        .join(Instrument, Instrument.instrument_id == MarketDataset.instrument_id)
        .where(
            SessionMetric.metric_id == metric_id,
            SessionMetric.verified_at.is_not(None),
            PracticeSession.user_id == user_id,
        )
        .order_by(PracticeSession.started_at.desc(), PracticeSession.session_id.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "metric_id": metric_id,
        "code": metric.code,
        "unit": metric.unit,
        "calculation_version": metric.calculation_version,
        "limit": limit,
        "offset": offset,
        "has_more": len(rows) > limit,
        "points": [
            {
                "session_id": m.session_id,
                "started_at": start,
                "quote_currency": currency,
                "value": m.value,
                "revision": m.revision,
                "computed_at": m.computed_at,
                "verified_at": m.verified_at,
            }
            for m, start, currency in rows[:limit]
        ],
    }
