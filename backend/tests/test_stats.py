import unittest
from decimal import Decimal
from itertools import chain

from app.services.stats import TradeInput, TradeStats, calculate_stats


D = Decimal


class StatsTests(unittest.TestCase):
    def test_no_trades(self):
        self.assertEqual(calculate_stats([]), TradeStats(D("0"), None, 0, 0))

    def test_buys_only_deduct_fees_without_counting_closed_trades(self):
        trades = [
            TradeInput("BUY", None, D("1.25")),
            TradeInput("BUY", D("0"), D("0.75")),
        ]
        self.assertEqual(calculate_stats(trades), TradeStats(D("-2"), None, 0, 0))

    def test_mixed_results_deduct_all_fees_once(self):
        trades = [
            TradeInput("BUY", None, D("1")),
            TradeInput("SELL", D("10"), D("0.50")),
            TradeInput("SELL", D("-4"), D("0.50")),
        ]
        self.assertEqual(calculate_stats(trades), TradeStats(D("4"), D("0.5"), 2, 1))

    def test_only_losing_trades(self):
        trades = [
            TradeInput("SELL", D("-10"), D("1")),
            TradeInput("SELL", D("-5"), D("1")),
        ]
        self.assertEqual(calculate_stats(trades), TradeStats(D("-17"), D("0"), 2, 0))

    def test_only_winning_trades(self):
        trades = [TradeInput("SELL", D("10")), TradeInput("SELL", D("20"))]
        self.assertEqual(calculate_stats(trades), TradeStats(D("30"), D("1"), 2, 2))

    def test_break_even_is_closed_but_not_a_win(self):
        trades = [TradeInput("SELL", D("0"))]
        self.assertEqual(calculate_stats(trades), TradeStats(D("0"), D("0"), 1, 0))

    def test_provisional_win_rule_uses_profit_before_fees(self):
        trades = [TradeInput("SELL", D("0.50"), D("1"))]
        self.assertEqual(calculate_stats(trades), TradeStats(D("-0.50"), D("1"), 1, 1))

    def test_provisional_rule_counts_each_partial_sell(self):
        # Two fills closing parts of the same position count separately.
        trades = [TradeInput("SELL", D("6")), TradeInput("SELL", D("4"))]
        self.assertEqual(calculate_stats(trades), TradeStats(D("10"), D("1"), 2, 2))

    def test_decimal_amounts_do_not_have_binary_float_error(self):
        trades = [
            TradeInput("BUY", None, D("0.30")),
            TradeInput("SELL", D("0.10")),
            TradeInput("SELL", D("0.20")),
        ]
        self.assertEqual(calculate_stats(trades), TradeStats(D("0"), D("1"), 2, 2))

    def test_accepts_a_single_pass_iterator(self):
        trades = iter([TradeInput("SELL", D("10")), TradeInput("SELL", D("-4"))])
        self.assertEqual(calculate_stats(trades), TradeStats(D("6"), D("0.5"), 2, 1))

    def test_overall_win_rate_uses_counts_not_average_session_rates(self):
        session_a = [TradeInput("SELL", D("10"))]  # 1 win out of 1
        session_b = [TradeInput("SELL", D("-1")) for _ in range(3)]  # 0 out of 3
        result = calculate_stats(chain(session_a, session_b))
        self.assertEqual(result, TradeStats(D("7"), D("0.25"), 4, 1))

    def test_rejects_invalid_trade_records(self):
        invalid = [
            TradeInput("HOLD", None),
            TradeInput("BUY", D("10")),
            TradeInput("SELL", None),
            TradeInput("BUY", None, D("-1")),
        ]
        for trade in invalid:
            with self.subTest(trade=trade):
                with self.assertRaises(ValueError):
                    calculate_stats([trade])

    def test_rejects_nonfinite_decimal_values(self):
        for value in ("NaN", "sNaN", "Infinity", "-Infinity"):
            for trade in (
                TradeInput("BUY", None, D(value)),
                TradeInput("SELL", D(value)),
            ):
                with self.subTest(trade=trade):
                    with self.assertRaises(ValueError):
                        calculate_stats([trade])

    def test_rejects_non_decimal_amounts(self):
        # Type hints alone do not reject these at runtime.
        for value in (0.1, 1, "1", True):
            for trade in (
                TradeInput("BUY", None, value),
                TradeInput("SELL", value),
            ):
                with self.subTest(trade=trade):
                    with self.assertRaises(TypeError):
                        calculate_stats([trade])
        with self.assertRaises(TypeError):
            calculate_stats([TradeInput("BUY", None, None)])


if __name__ == "__main__":
    unittest.main()
