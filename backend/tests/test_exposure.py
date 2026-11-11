import unittest
from decimal import Decimal, localcontext
from types import SimpleNamespace
from uuid import uuid4

from app.services.stats import (
    ExposureStats, TradeInput, calculate_exposure, calculate_summary,
)

D = Decimal


def snapshot(currency="USD", cash="800", quantity="2", price="100", trades=()):
    return SimpleNamespace(
        session_id=uuid4(), quote_currency=currency, cash_balance=D(cash),
        position_quantity=D(quantity), price=D(price) if price else None, trades=trades,
    )


class ExposureTests(unittest.TestCase):
    def test_current_position_value_over_equity(self):
        self.assertEqual(calculate_exposure(D("800"), D("2"), D("100")),
                         ExposureStats(D("200"), D("1000"), D("0.2")))

    def test_flat_account_needs_no_price(self):
        self.assertEqual(calculate_exposure(D("500"), D("0"), None),
                         ExposureStats(D("0"), D("500"), D("0")))

    def test_zero_equity_is_undefined(self):
        self.assertEqual(calculate_exposure(D("0"), D("0"), None),
                         ExposureStats(D("0"), D("0"), None))

    def test_fully_invested_is_one(self):
        self.assertEqual(calculate_exposure(D("0"), D("2.5"), D("20")).exposure_ratio, D("1"))

    def test_open_position_without_price_is_unknown(self):
        self.assertEqual(calculate_exposure(D("100"), D("2"), None), ExposureStats(None, None, None))

    def test_invalid_amounts_are_rejected(self):
        for values in ((D("-1"), D("0"), None), (D("1"), D("-1"), D("1")),
                       (D("1"), D("1"), D("0")), (D("NaN"), D("0"), None),
                       (D("1"), D("1"), D("Infinity"))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                calculate_exposure(*values)
        with self.assertRaises(TypeError):
            calculate_exposure(100, D("1"), D("1"))

    def test_independent_precision_does_not_change_caller(self):
        with localcontext() as context:
            context.prec = 3
            result = calculate_exposure(D("9999"), D("1"), D("1"))
            self.assertEqual(result.exposure_ratio, D("0.0001"))
            self.assertEqual(context.prec, 3)

    def test_summary_weights_ratios_using_totals(self):
        a = snapshot(trades=(TradeInput("SELL", D("10"), D("1")),))
        b = snapshot(cash="100", quantity="9", trades=tuple(TradeInput("SELL", D("-1")) for _ in range(3)))
        result = calculate_summary([a, b])[0]
        self.assertEqual((result.pnl, result.closed_trades, result.win_rate), (D("6"), 4, D("0.25")))
        self.assertEqual((result.position_value, result.equity, result.exposure_ratio), (D("1100"), D("2000"), D("0.55")))

    def test_currencies_are_not_combined(self):
        result = calculate_summary([snapshot(), snapshot(currency="EUR")])
        self.assertEqual([row.quote_currency for row in result], ["EUR", "USD"])
        self.assertTrue(all(row.session_count == 1 for row in result))

    def test_summary_missing_price_does_not_understate_exposure(self):
        result = calculate_summary([snapshot(), snapshot(price=None)])[0]
        self.assertIsNone(result.exposure_ratio)
        self.assertIsNone(result.position_value)
        self.assertIsNone(result.equity)

    def test_empty_summary(self):
        self.assertEqual(calculate_summary([]), [])

    def test_duplicate_session_rejected(self):
        item = snapshot()
        with self.assertRaises(ValueError):
            calculate_summary([item, item])


if __name__ == "__main__":
    unittest.main()
