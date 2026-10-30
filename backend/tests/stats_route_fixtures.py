"""Shared HTTP test fixtures; no production tables or credentials are created."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from stats_fixtures import StatsDatabaseTestCase


class StatsRouteTestCase(StatsDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.db.commit()
        self.settings = Settings(
            _env_file=None,
            jwt_secret_key="test-only-secret-that-is-at-least-sixty-four-bytes-long-for-security-tests",
            jwt_algorithm="HS256",
        )
        previous_overrides = app.dependency_overrides.copy()

        def restore_overrides():
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        self.addCleanup(restore_overrides)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def token(self, *, subject=None, claims=None, algorithm="HS256", secret=None):
        payload = {
            "sub": str(self.user if subject is None else subject),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        if claims is not None:
            payload = claims
        return jwt.encode(
            payload, secret or self.settings.jwt_secret_key, algorithm=algorithm
        )

    def headers(self, **kwargs):
        return {"Authorization": "Bearer " + self.token(**kwargs)}

    def path(self, session_id=None, *, recompute=False):
        path = f"/sessions/{session_id or self.session_id}/stats"
        return path + "/recompute" if recompute else path
