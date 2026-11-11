"""Session HTTP contracts and access controls against a test SQLite schema."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.services.stats_storage import StatsConflict, read_verified_stats
from stats_route_fixtures import StatsRouteTestCase


class StatsRouteTests(StatsRouteTestCase):
    def test_recompute_and_read_preserve_decimal_values_and_verification(self):
        self.add_trade("BUY", fee=Decimal("1.25"))
        self.add_trade("SELL", Decimal("20.125"), Decimal("0.375"))
        self.db.commit()

        created = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertEqual(body["session_id"], str(self.session_id))
        self.assertEqual(body["quote_currency"], "USD")
        self.assertEqual(Decimal(body["pnl"]), Decimal("18.5"))
        self.assertIsInstance(body["pnl"], str)
        self.assertIsInstance(body["win_rate"], str)
        self.assertEqual(Decimal(body["win_rate"]), Decimal("1"))
        self.assertEqual(body["revision"], 1)
        self.assertTrue(body["verified_at"])
        self.assertTrue(body["calculation_version"])

        # A separate Session confirms the HTTP mutation ended its transaction.
        self.assertFalse(self.db.in_transaction())
        with Session(self.engine) as independent_db:
            saved = read_verified_stats(independent_db, self.user, self.session_id)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(saved["pnl"], Decimal("18.5"))

        stored = self.client.get(self.path(), headers=self.headers())
        self.assertEqual(stored.status_code, 200, stored.text)
        self.assertEqual(stored.json(), body)

    def test_read_before_computation_returns_conflict_without_writing(self):
        response = self.client.get(self.path(), headers=self.headers())
        self.assertEqual(response.status_code, 409, response.text)
        count = self.db.scalar(select(func.count()).select_from(self.tables["session_metrics"]))
        self.assertEqual(count, 0)

    def test_empty_session_returns_null_win_rate(self):
        response = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["win_rate"])
        self.assertEqual(Decimal(response.json()["exposure_ratio"]), Decimal("0"))

    def test_saved_snapshot_remains_historical_until_explicit_recomputation(self):
        first = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(first.status_code, 200, first.text)
        self.add_trade("SELL", Decimal("12"))
        self.db.commit()

        stale = self.client.get(self.path(), headers=self.headers())
        self.assertEqual(stale.status_code, 200, stale.text)
        self.assertEqual(Decimal(stale.json()["pnl"]), Decimal("0"))
        refreshed = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["revision"], 2)
        self.assertEqual(Decimal(refreshed.json()["pnl"]), Decimal("12"))

    def test_owned_session_is_hidden_from_another_user_for_read_and_recompute(self):
        created = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(created.status_code, 200, created.text)
        for method, path in (("get", self.path()), ("post", self.path(recompute=True))):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    path, headers=self.headers(subject=self.other_user)
                )
                self.assertEqual(response.status_code, 404, response.text)

    def test_missing_session_is_indistinguishable_from_unowned_session(self):
        for method, recompute in (("get", False), ("post", True)):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.path(uuid4(), recompute=recompute), headers=self.headers()
                )
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json(), {"detail": "Session not found."})

    def test_missing_bearer_token_and_identity_header_are_rejected(self):
        for headers in ({}, {"X-User-Id": str(self.user)}, {"Authorization": "Basic abc"}):
            with self.subTest(headers=headers):
                response = self.client.get(self.path(), headers=headers)
                self.assertEqual(response.status_code, 401, response.text)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_expired_incomplete_and_malformed_subject_tokens_are_rejected(self):
        now = datetime.now(timezone.utc)
        invalid_claims = (
            {"sub": str(self.user), "exp": now - timedelta(seconds=1)},
            {"sub": str(self.user)},
            {"exp": now + timedelta(hours=1)},
            {"sub": "not-a-uuid", "exp": now + timedelta(hours=1)},
            {"sub": 123, "exp": now + timedelta(hours=1)},
        )
        for claims in invalid_claims:
            with self.subTest(claims=claims):
                response = self.client.get(self.path(), headers=self.headers(claims=claims))
                self.assertEqual(response.status_code, 401, response.text)

    def test_wrong_signature_and_wrong_algorithm_are_rejected(self):
        for kwargs in (
            {"secret": "different-test-secret-of-at-least-32-bytes"},
            {"algorithm": "HS384"},
        ):
            with self.subTest(kwargs=kwargs):
                response = self.client.get(self.path(), headers=self.headers(**kwargs))
                self.assertEqual(response.status_code, 401, response.text)

    def test_unknown_and_inactive_users_are_rejected(self):
        missing = self.client.get(self.path(), headers=self.headers(subject=uuid4()))
        self.assertEqual(missing.status_code, 401, missing.text)
        for account_status in ("SUSPENDED", "DEACTIVATED"):
            with self.subTest(account_status=account_status):
                self.db.execute(
                    self.tables["users"].update()
                    .where(self.tables["users"].c.user_id == self.user)
                    .values(account_status=account_status)
                )
                self.db.commit()
                response = self.client.get(self.path(), headers=self.headers())
                self.assertEqual(response.status_code, 401, response.text)

    def test_unsafe_auth_configuration_fails_closed(self):
        valid_headers = self.headers()
        for secret, algorithm in (
            ("change_me_to_a_long_random_string", "HS256"),
            ("too-short", "HS256"),
            (self.settings.jwt_secret_key, "HS384"),
        ):
            with self.subTest(secret=secret, algorithm=algorithm):
                self.settings.jwt_secret_key = secret
                self.settings.jwt_algorithm = algorithm
                response = self.client.get(self.path(), headers=valid_headers)
                self.assertEqual(response.status_code, 503, response.text)

    def test_storage_conflicts_rollback_and_do_not_expose_database_details(self):
        errors = (
            StatsConflict("internal conflict details"),
            IntegrityError("private SQL", {}, Exception("private driver message")),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__), patch(
                "app.routers.stats.recompute_session_stats", side_effect=error
            ), patch.object(self.db, "rollback", wraps=self.db.rollback) as rollback:
                response = self.client.post(self.path(recompute=True), headers=self.headers())
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json(), {"detail": "Statistics changed; retry the request."})
                rollback.assert_called_once()

    def test_unavailable_database_returns_a_safe_service_error(self):
        error = OperationalError("private SQL", {}, Exception("private connection details"))
        with patch("app.routers.stats.read_verified_stats", side_effect=error):
            response = self.client.get(self.path(), headers=self.headers())
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {"detail": "The statistics database is unavailable."})

    def test_invalid_source_data_returns_conflict(self):
        self.db.execute(
            self.tables["practice_sessions"].update()
            .where(self.tables["practice_sessions"].c.session_id == self.session_id)
            .values(cash_balance=Decimal("-1"))
        )
        self.db.commit()
        response = self.client.post(self.path(recompute=True), headers=self.headers())
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json(), {"detail": "Session data cannot produce valid statistics."})
