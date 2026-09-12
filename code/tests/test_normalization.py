from __future__ import annotations

import io
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from buy_or_wait.loaders import load_dataset
from buy_or_wait.normalization import (
    CurrencyConversionError,
    convert_to_home_currency,
    format_normalized_timeline,
    normalize_user_events,
    print_normalized_timeline,
)


DATASET = Path(__file__).resolve().parents[2] / "dataset"


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = load_dataset(DATASET)

    def test_uses_exact_dated_exchange_rate_with_decimal_money(self) -> None:
        result = convert_to_home_currency(
            Decimal("1800"), "USD", "IDR", date(2023, 10, 15), self.index
        )
        self.assertEqual(Decimal("28499994.00"), result)
        event = next(item for item in normalize_user_events(self.index, "user_25") if item.event_id == "event_2167")
        self.assertEqual(Decimal("1800"), event.amount)
        self.assertEqual(Decimal("28499994.00"), event.amount_in_home_currency)
        self.assertEqual("converted", event.conversion_status)

    def test_missing_rate_is_explicit_error_not_an_invented_conversion(self) -> None:
        with self.assertRaises(CurrencyConversionError):
            convert_to_home_currency(Decimal("1"), "USD", "INR", date(1900, 1, 1), self.index)

    def test_normalizes_missing_amount_and_status_without_zero(self) -> None:
        event = next(item for item in normalize_user_events(self.index, "user_03") if item.event_id == "event_253")
        self.assertIsNone(event.amount)
        self.assertIsNone(event.amount_in_home_currency)
        self.assertEqual("missing_amount", event.conversion_status)
        self.assertEqual("settled_cash", event.cash_treatment)

    def test_lifecycle_and_recurring_classification(self) -> None:
        duplicate_raw = self.index.events_by_id["event_12709"]
        duplicate = next(
            item for item in normalize_user_events(self.index, duplicate_raw.user_id)
            if item.event_id == "event_12709"
        )
        self.assertEqual("duplicate", duplicate.lifecycle_role)
        self.assertEqual("excluded_duplicate", duplicate.cash_treatment)
        recurring = next(item for item in normalize_user_events(self.index, "user_01") if item.event_id == "event_01")
        self.assertTrue(recurring.is_recurring)
        self.assertEqual("expense", recurring.event_kind)
        self.assertFalse(recurring.is_flexible)

    def test_pending_and_unrealized_events_are_distinguished(self) -> None:
        pending = next(item for item in normalize_user_events(self.index, "user_01") if item.event_id == "event_102")
        self.assertEqual("reserve_pending_debit", pending.cash_treatment)
        valuation_raw = self.index.events_by_id["event_1856"]
        valuation = next(
            item for item in normalize_user_events(self.index, valuation_raw.user_id)
            if item.event_id == "event_1856"
        )
        self.assertEqual("investment_valuation", valuation.event_kind)
        self.assertEqual("excluded_non_cash_or_unrealized", valuation.cash_treatment)

    def test_debug_timeline_is_human_readable(self) -> None:
        timeline = normalize_user_events(self.index, "user_01")[:3]
        rendered = format_normalized_timeline(timeline)
        stream = io.StringIO()
        print_normalized_timeline(timeline, file=stream)
        self.assertIn("event_id", rendered)
        self.assertIn(timeline[0].event_id, rendered)
        self.assertEqual(rendered + "\n", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
