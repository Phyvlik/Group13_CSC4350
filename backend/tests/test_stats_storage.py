from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg

from app.repositories.stats import SessionNotFound
from app.services import stats_storage as storage
from stats_fixtures import StatsDatabaseTestCase

D = Decimal


class StatsStorageTests(StatsDatabaseTestCase):
    def recompute(self):
        return storage.recompute_session_stats(self.db, self.user, self.session_id)

    def read(self):
        return storage.read_verified_stats(self.db, self.user, self.session_id)

    def test_seeds_three_immutable_definitions_idempotently(self):
        storage.seed_metric_definitions(self.db)
        storage.seed_metric_definitions(self.db)
        rows = self.db.execute(select(storage.metrics)).mappings().all()
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["code"] for row in rows}, {"PNL", "WIN_RATE", "EXPOSURE"})
        self.assertTrue(all(row["calculation_version"] == "1-proposed" for row in rows))
        self.assertTrue(all("ROUND_HALF_EVEN" in row["calculation_rule"] for row in rows))

    def test_metric_code_uses_the_postgresql_enum_without_varchar_cast(self):
        statement = storage.pg_insert(storage.metrics).values(
            metric_id=storage.METRIC_IDS["PNL"], code="PNL",
        )
        sql = str(statement.compile(dialect=PGDialect_psycopg()))
        self.assertEqual(storage.metrics.c.code.type.name, "metric_code")
        self.assertNotIn("%(code)s::VARCHAR", sql)

    def test_existing_rule_is_not_overwritten(self):
        storage.seed_metric_definitions(self.db)
        self.db.execute(update(storage.metrics).where(storage.metrics.c.metric_id == storage.METRIC_IDS["PNL"]).values(calculation_rule="old rule"))
        with self.assertRaises(storage.StatsConflict):
            storage.seed_metric_definitions(self.db)
        self.assertEqual(self.db.scalar(select(storage.metrics.c.calculation_rule).where(storage.metrics.c.metric_id == storage.METRIC_IDS["PNL"])), "old rule")

    def test_empty_session_saves_zero_pnl_and_undefined_win_rate(self):
        result = self.recompute()
        self.assertEqual(result["pnl"], D("0"))
        self.assertIsNone(result["win_rate"])
        self.assertEqual(result["exposure_ratio"], D("0"))
        self.assertIsNotNone(result["verified_at"])
        rows = self.db.execute(select(storage.session_metrics)).mappings().all()
        self.assertEqual(len(rows), 2)
        self.assertNotIn(storage.METRIC_IDS["WIN_RATE"], {row["metric_id"] for row in rows})

    def test_hand_calculated_values_are_saved_and_read(self):
        self.add_trade("BUY", fee=D("1"))
        self.add_trade("SELL", D("10"), D("0.5"))
        self.add_trade("SELL", D("-4"), D("0.5"))
        self.recompute()
        result = self.read()
        self.assertEqual((result["pnl"], result["win_rate"], result["revision"]), (D("4"), D("0.5"), 1))

    def test_recompute_appends_revision_without_changing_history(self):
        self.add_trade("SELL", D("10"))
        self.recompute()
        self.add_trade("SELL", D("-4"))
        result = self.recompute()
        self.assertEqual((result["revision"], result["pnl"]), (2, D("6")))
        old = self.db.scalar(select(storage.session_metrics.c.value).where(
            storage.session_metrics.c.revision == 1,
            storage.session_metrics.c.metric_id == storage.METRIC_IDS["PNL"],
        ))
        self.assertEqual(old, D("10"))
        self.assertEqual(self.read()["revision"], 2)

    def test_undefined_metric_does_not_reuse_an_older_revision(self):
        self.add_trade("SELL", D("10"))
        self.recompute()
        self.db.execute(self.tables["trades"].delete())
        self.recompute()
        self.assertIsNone(self.read()["win_rate"])

    def test_unverified_newer_batch_is_excluded(self):
        first = self.recompute()
        self.db.execute(storage.session_metrics.insert().values(
            session_metric_id=uuid4(), session_id=self.session_id,
            metric_id=storage.METRIC_IDS["PNL"], revision=2, value=D("999"),
            computed_at=self.now, verified_at=None,
        ))
        self.assertEqual(self.read()["revision"], first["revision"])
        self.assertEqual(self.read()["pnl"], D("0"))

    def test_no_verified_results_raises(self):
        with self.assertRaises(storage.StatsNotComputed):
            self.read()

    def test_partially_verified_batch_does_not_replace_complete_batch(self):
        self.recompute()
        self.add_trade("SELL", D("10"))
        self.recompute()
        self.db.execute(update(storage.session_metrics).where(
            storage.session_metrics.c.revision == 2,
            storage.session_metrics.c.metric_id == storage.METRIC_IDS["WIN_RATE"],
        ).values(verified_at=None))
        self.assertEqual(self.read()["revision"], 1)
        self.assertEqual(self.read()["pnl"], D("0"))

    def test_foreign_and_absent_sessions_are_not_visible_or_recomputed(self):
        for session_id in (self.session_id, uuid4()):
            for function in (storage.read_verified_stats, storage.recompute_session_stats):
                with self.subTest(function=function.__name__, session_id=session_id), self.assertRaises(SessionNotFound):
                    function(self.db, self.other_user, session_id)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(storage.session_metrics)), 0)

    def test_verification_mismatch_rolls_back_new_batch(self):
        self.recompute()
        original = storage._values
        calls = 0

        def changed(snapshot):
            nonlocal calls
            calls += 1
            values = original(snapshot)
            if calls == 2:
                values["PNL"] = D("999")
            return values

        with patch.object(storage, "_values", side_effect=changed), self.assertRaises(storage.StatsConflict):
            self.recompute()
        self.assertEqual(self.read()["revision"], 1)
        self.assertEqual(self.db.scalar(select(func.max(storage.session_metrics.c.revision))), 1)

    def test_rounding_of_one_winning_sell_out_of_three(self):
        for pnl in ("1", "-1", "-1"):
            self.add_trade("SELL", D(pnl))
        result = self.recompute()
        self.assertEqual(result["win_rate"], D("0.333333"))
        self.assertEqual(self.read()["win_rate"], D("0.333333"))

    def test_overflow_is_rejected_before_saving_a_revision(self):
        for _ in range(2):
            self.add_trade("SELL", D("900000000000"))
        with self.assertRaises(ValueError):
            self.recompute()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(storage.session_metrics)), 0)
