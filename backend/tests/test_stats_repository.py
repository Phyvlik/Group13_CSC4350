from dataclasses import FrozenInstanceError
from datetime import timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.repositories import stats as repository
from app.repositories.stats import SessionNotFound, load_session, load_user_sessions
from stats_fixtures import StatsDatabaseTestCase


class StatsRepositoryTests(StatsDatabaseTestCase):
    def test_session_inputs_preserve_decimal_values_and_currency(self):
        self.add_trade("BUY", fee=Decimal("0.25"))
        self.add_trade("SELL", Decimal("12.345678"), Decimal("0.10"))

        result = load_session(self.db, self.user, self.session_id)

        self.assertEqual(result.session_id, self.session_id)
        self.assertEqual(result.user_id, self.user)
        self.assertEqual(result.cash_balance, Decimal("10000"))
        self.assertEqual(result.position_quantity, Decimal("0"))
        self.assertEqual(result.price, Decimal("100"))
        self.assertEqual(result.quote_currency, "USD")
        self.assertEqual(len(result.trades), 2)
        sell = next(trade for trade in result.trades if trade.side == "SELL")
        self.assertEqual(sell.realized_pnl, Decimal("12.345678"))
        self.assertIsInstance(sell.realized_pnl, Decimal)

    def test_absent_and_other_users_session_have_same_error(self):
        for session_id, user_id in (
            (uuid4(), self.user), (self.session_id, self.other_user),
        ):
            with self.subTest(session_id=session_id):
                with self.assertRaisesRegex(SessionNotFound, "^Session not found\\.$"):
                    load_session(self.db, user_id, session_id)

    def test_future_price_and_future_trade_are_excluded(self):
        self.add_price(Decimal("999"), at=self.now + timedelta(minutes=1))
        self.add_trade("SELL", Decimal("800"), at=self.now + timedelta(minutes=1))
        self.add_trade("SELL", Decimal("4"), at=self.now)

        result = load_session(self.db, self.user, self.session_id)

        self.assertEqual(result.price, Decimal("100"))
        self.assertEqual(tuple(t.realized_pnl for t in result.trades), (Decimal("4"),))

    def test_price_is_bounded_by_start_and_end_even_if_replay_is_later(self):
        self.add_price(Decimal("110"), at=self.end)
        self.add_price(Decimal("999"), at=self.end + timedelta(minutes=1))
        session_id = self.create_session(replay_at=self.end + timedelta(minutes=2))
        result = load_session(self.db, self.user, session_id)
        self.assertEqual(result.price, Decimal("110"))

        new_dataset = self.create_dataset()
        self.add_price(Decimal("90"), at=self.start - timedelta(minutes=1), dataset_id=new_dataset)
        session_id = self.create_session(dataset_id=new_dataset)
        self.assertIsNone(load_session(self.db, self.user, session_id).price)

    def test_trade_range_includes_boundaries_but_excludes_outside_range(self):
        session_id = self.create_session(replay_at=self.end + timedelta(minutes=2))
        for at, pnl in (
            (self.start - timedelta(seconds=1), Decimal("999")),
            (self.start, Decimal("1")),
            (self.end, Decimal("2")),
            (self.end + timedelta(seconds=1), Decimal("888")),
        ):
            self.add_trade("SELL", pnl, session_id=session_id, at=at)

        result = load_session(self.db, self.user, session_id)

        self.assertEqual(
            tuple(trade.realized_pnl for trade in result.trades),
            (Decimal("1"), Decimal("2")),
        )

    def test_missing_visible_price_is_none_and_no_trades_is_empty(self):
        session_id = self.create_session(replay_at=self.start)
        result = load_session(self.db, self.user, session_id)
        self.assertIsNone(result.price)
        self.assertEqual(result.trades, ())

    def test_batch_is_scoped_and_keeps_currency_and_trade_groups_separate(self):
        eur_dataset = self.create_dataset("EUR")
        eur_session = self.create_session(dataset_id=eur_dataset)
        other_session = self.create_session(user_id=self.other_user)
        self.add_price(Decimal("50"), dataset_id=eur_dataset)
        self.add_trade("SELL", Decimal("7"))
        self.add_trade("SELL", Decimal("3"), session_id=eur_session)
        self.add_trade("SELL", Decimal("999"), session_id=other_session)

        result = {item.session_id: item for item in load_user_sessions(self.db, self.user)}

        self.assertEqual(set(result), {self.session_id, eur_session})
        self.assertEqual(result[self.session_id].quote_currency, "USD")
        self.assertEqual(result[eur_session].quote_currency, "EUR")
        self.assertEqual(result[eur_session].price, Decimal("50"))
        self.assertEqual(result[self.session_id].trades[0].realized_pnl, Decimal("7"))
        self.assertEqual(result[eur_session].trades[0].realized_pnl, Decimal("3"))

    def test_batch_queries_do_not_grow_with_the_number_of_sessions(self):
        for _ in range(20):
            self.create_session()
        statements = []

        def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", record_statement)
        try:
            results = load_user_sessions(self.db, self.user)
        finally:
            event.remove(self.engine, "before_cursor_execute", record_statement)

        self.assertEqual(len(results), 21)
        self.assertEqual(len(statements), 2)

    def test_user_without_sessions_returns_empty(self):
        self.assertEqual(load_user_sessions(self.db, self.other_user), [])

    def test_postgresql_queries_lock_only_the_owned_session_rows(self):
        # Compilation checks the intended dialect, not runtime lock behavior.
        for exclusive in (False, True):
            statements = []
            original_execute = self.db.execute

            def record(statement, *args, **kwargs):
                statements.append(str(statement.compile(dialect=postgresql.dialect())))
                return original_execute(statement, *args, **kwargs)

            with patch.object(self.db, "execute", side_effect=record):
                load_session(self.db, self.user, self.session_id, lock=exclusive)
            self.assertIn(
                "FOR UPDATE OF practice_sessions" if exclusive
                else "FOR SHARE OF practice_sessions",
                statements[0],
            )

    def test_summary_trade_load_is_limited_to_captured_owned_sessions(self):
        original_loader = repository._load_trades
        captured = []

        def add_new_session_before_trade_read(db, user_id, session_ids):
            new_session = self.create_session()
            self.add_trade("SELL", Decimal("999"), session_id=new_session)
            loaded = original_loader(db, user_id, session_ids)
            captured.extend(loaded)
            return loaded

        with patch.object(repository, "_load_trades", side_effect=add_new_session_before_trade_read):
            results = load_user_sessions(self.db, self.user)

        self.assertEqual([row.session_id for row in results], [self.session_id])
        self.assertEqual(captured, [])

    def test_snapshot_and_its_trade_collection_are_immutable(self):
        result = load_session(self.db, self.user, self.session_id)
        self.assertIsInstance(result.trades, tuple)
        with self.assertRaises(FrozenInstanceError):
            result.cash_balance = Decimal("1")


if __name__ == "__main__":
    unittest.main()
