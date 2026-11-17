"""Current aggregate HTTP statistics remain scoped to the signed-in user."""

from decimal import Decimal

from stats_route_fixtures import StatsRouteTestCase


class StatsSummaryRouteTests(StatsRouteTestCase):
    def test_summary_separates_currencies_and_excludes_other_users(self):
        self.add_trade("SELL", Decimal("25"))
        second = self.create_session()
        self.add_trade("SELL", Decimal("-10"), session_id=second)
        eur = self.create_dataset("EUR")
        eur_session = self.create_session(dataset_id=eur)
        self.add_trade("SELL", Decimal("5"), session_id=eur_session)
        foreign = self.create_session(user_id=self.other_user)
        self.add_trade("SELL", Decimal("99999"), session_id=foreign)
        self.db.commit()

        response = self.client.get(
            "/stats/summary", headers=self.headers(), params={"user_id": str(self.other_user)}
        )
        self.assertEqual(response.status_code, 200, response.text)
        rows = {row["quote_currency"]: row for row in response.json()["currencies"]}
        self.assertEqual(set(rows), {"USD", "EUR"})
        self.assertEqual(rows["USD"]["session_count"], 2)
        self.assertEqual(Decimal(rows["USD"]["pnl"]), Decimal("15"))
        self.assertEqual(Decimal(rows["USD"]["win_rate"]), Decimal("0.5"))
        self.assertEqual(Decimal(rows["EUR"]["pnl"]), Decimal("5"))

    def test_summary_without_sessions_is_an_empty_list(self):
        response = self.client.get("/stats/summary", headers=self.headers(subject=self.other_user))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"currencies": []})

    def test_summary_does_not_invent_exposure_when_a_position_has_no_visible_price(self):
        self.db.execute(self.tables["price_bars"].delete())
        self.db.execute(
            self.tables["practice_sessions"].update()
            .where(self.tables["practice_sessions"].c.session_id == self.session_id)
            .values(position_quantity=Decimal("2"))
        )
        self.db.commit()
        response = self.client.get("/stats/summary", headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()["currencies"][0]
        self.assertIsNone(row["position_value"])
        self.assertIsNone(row["equity"])
        self.assertIsNone(row["exposure_ratio"])
