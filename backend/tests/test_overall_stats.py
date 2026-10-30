import unittest
from decimal import Decimal

from app.services.stats import (
    TradeInput,
    TradeStats,
    calculate_overall_stats,
    calculate_stats,
)


D = Decimal


class OverallStatsTests(unittest.TestCase):
    def test_weights_win_rate_by_closed_trades_and_sums_pnl(self):
        one_win = TradeStats(D("10"), D("1"), 1, 1)
        three_losses = TradeStats(D("-3"), D("0"), 3, 0)

        result = calculate_overall_stats(iter([one_win, three_losses]))

        self.assertEqual(result, TradeStats(D("7"), D("0.25"), 4, 1))

    def test_no_closed_trades_retains_fees_and_has_no_win_rate(self):
        first = calculate_stats([TradeInput("BUY", None, D("1.25"))])
        second = calculate_stats([TradeInput("BUY", None, D("0.75"))])

        self.assertEqual(
            calculate_overall_stats([first, second]), TradeStats(D("-2"), None, 0, 0)
        )

    def test_no_sessions_returns_empty_stats(self):
        self.assertEqual(
            calculate_overall_stats([]), TradeStats(D("0"), None, 0, 0)
        )

    def test_single_session_preserves_values(self):
        session = TradeStats(D("-1.50"), D("0.5"), 2, 1)

        self.assertEqual(calculate_overall_stats([session]), session)

    def test_mixed_sessions_include_fees_and_break_even_trades(self):
        winning_session = calculate_stats(
            [
                TradeInput("BUY", None, D("1")),
                TradeInput("SELL", D("10"), D("0.50")),
            ]
        )
        other_closed_session = calculate_stats(
            [
                TradeInput("SELL", D("-2"), D("0.25")),
                TradeInput("SELL", D("0")),
                TradeInput("SELL", D("0")),
            ]
        )
        buy_only_session = calculate_stats(
            [TradeInput("BUY", None, D("0.75"))]
        )

        result = calculate_overall_stats(
            [winning_session, other_closed_session, buy_only_session]
        )

        # Gross P/L is 8; all fees total 2.50; only one of four SELLs wins.
        self.assertEqual(result, TradeStats(D("5.50"), D("0.25"), 4, 1))

    def test_empty_sessions_do_not_change_totals(self):
        empty = TradeStats(D("0"), None, 0, 0)
        closed = TradeStats(D("-3"), D("0"), 2, 0)

        self.assertEqual(calculate_overall_stats([empty, closed, empty]), closed)

    def test_decimal_amounts_sum_without_binary_float_error(self):
        sessions = [
            TradeStats(D("0.10"), D("1"), 1, 1),
            TradeStats(D("0.20"), D("1"), 1, 1),
            TradeStats(D("-0.30"), D("0"), 2, 0),
        ]

        self.assertEqual(
            calculate_overall_stats(sessions), TradeStats(D("0"), D("0.5"), 4, 2)
        )

    def test_rejects_invalid_session_counts(self):
        for closed, winning in ((-1, 0), (0, -1), (1, 2)):
            with self.subTest(closed=closed, winning=winning):
                with self.assertRaises(ValueError):
                    calculate_overall_stats(
                        [TradeStats(D("0"), None, closed, winning)]
                    )

    def test_rejects_non_integer_session_counts(self):
        for value in (True, False, 1.0, D("1"), "1", None):
            for closed, winning in ((value, 0), (1, value)):
                with self.subTest(closed=closed, winning=winning):
                    with self.assertRaises(TypeError):
                        calculate_overall_stats(
                            [TradeStats(D("0"), None, closed, winning)]
                        )

    def test_rejects_nonfinite_session_pnl(self):
        for value in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_overall_stats([TradeStats(D(value), None, 0, 0)])

    def test_rejects_non_decimal_session_pnl(self):
        for value in (0.1, 1, "1", True, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                calculate_overall_stats([TradeStats(value, None, 0, 0)])


if __name__ == "__main__":
    unittest.main()
