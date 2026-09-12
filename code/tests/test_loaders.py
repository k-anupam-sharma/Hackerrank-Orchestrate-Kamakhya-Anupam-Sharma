from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from buy_or_wait.loaders import DatasetValidationError, load_dataset


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATASET = REPO_ROOT / "dataset"


HEADERS = {
    "financial_profiles.csv": ["user_id", "home_currency", "current_available_balance", "minimum_balance_to_keep", "financial_priorities", "expense_categories_to_protect", "expense_categories_user_is_willing_to_reduce", "expense_categories_user_is_willing_to_stop", "payment_methods_user_will_consider", "max_installment_months"],
    "financial_events.csv": ["event_id", "user_id", "event_type", "description", "category", "direction", "amount", "currency", "event_date", "settlement_date", "status", "linked_event_id", "flexibility", "minimum_allowed_amount"],
    "requests.csv": ["request_id", "user_id", "request_date", "request_type", "requested_amount", "desired_completion_date", "allows_partial_payment", "request_text"],
    "sample_requests.csv": ["request_id", "user_id", "request_date", "request_type", "requested_amount", "desired_completion_date", "allows_partial_payment", "request_text"],
    "request_payment_options.csv": ["payment_option_id", "request_id", "payment_method", "payment_amount", "number_of_payments", "first_payment_date", "payment_frequency_days", "financing_fee", "total_payable_amount"],
    "messages.csv": ["message_id", "user_id", "request_id", "related_event_id", "sent_at", "source_type", "message_text"],
    "images.csv": ["image_id", "user_id", "request_id", "related_event_id"],
    "exchange_rates.csv": ["rate_date", "from_currency", "to_currency", "rate"],
    "output.csv": ["request_id", "amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed", "decision_explanation"],
}


def write_csv(root: Path, name: str, rows: list[list[str]]) -> None:
    with (root / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS[name])
        writer.writerows(rows)


def make_minimal_dataset(root: Path) -> None:
    (root / "media" / "images").mkdir(parents=True)
    write_csv(root, "financial_profiles.csv", [["u1", "INR", "100.10", "25.00", "emergency_savings", "rent", "", "", "full_payment", ""]])
    write_csv(root, "financial_events.csv", [["e1", "u1", "expense", "Rent", "rent", "debit", "", "USD", "2026-01-01", "2026-01-15", "pending", "", "fixed", ""]])
    request = ["r1", "u1", "2026-01-02", "purchase", "50.20", "2026-01-20", "true", "Test request"]
    write_csv(root, "requests.csv", [request])
    write_csv(root, "sample_requests.csv", [["sample1", "u1", "2026-01-01", "purchase", "5", "2026-01-02", "false", "Sample"]])
    write_csv(root, "request_payment_options.csv", [["p1", "r1", "full_payment", "50.20", "1", "2026-01-02", "", "0", "50.20"]])
    write_csv(root, "messages.csv", [["m1", "u1", "r1", "e1", "2026-01-01T00:00:00Z", "bank", "Event note"]])
    write_csv(root, "images.csv", [["i1", "u1", "r1", "e1"]])
    (root / "media" / "images" / "i1.png").write_bytes(b"png")
    write_csv(root, "exchange_rates.csv", [["2026-01-15", "USD", "INR", "83.33"]])
    write_csv(root, "output.csv", [["r1", "", "", "", "", "", "", ""]])


class DatasetLoaderTests(unittest.TestCase):
    def test_loads_every_real_dataset_and_builds_indexes(self) -> None:
        index = load_dataset(REAL_DATASET)
        self.assertEqual(275, len(index.profiles_by_user_id))
        self.assertEqual(250, len(index.evaluation_requests_by_id))
        self.assertEqual(25, len(index.sample_requests_by_id))
        self.assertEqual(25342, len(index.events_by_id))
        self.assertEqual(790, len(index.payment_options_by_id))
        self.assertEqual(215, len(index.messages_by_id))
        self.assertEqual(16, len(index.images_by_id))
        self.assertEqual(134, len(index.exchange_rates_by_key))

    def test_context_contains_joined_request_data(self) -> None:
        index = load_dataset(REAL_DATASET)
        context = index.get_request_context("request_33")
        self.assertEqual("user_33", context.profile.user_id)
        self.assertGreater(len(context.events), 0)
        self.assertGreater(len(context.payment_options), 0)
        self.assertTrue(any(item.image_id == "image_06" for item in context.images))
        self.assertIn("event_3051", context.linked_images_by_event_id)

    def test_dates_currencies_and_money_are_typed(self) -> None:
        index = load_dataset(REAL_DATASET)
        event = index.events_by_id["event_253"]
        rate = index.exchange_rates_by_key[(date(2025, 10, 1), "USD", "INR")]
        self.assertIsNone(event.amount, "A missing financial amount must not become zero")
        self.assertEqual(date(2019, 8, 31), event.event_date)
        self.assertEqual("IDR", event.currency)
        self.assertEqual(Decimal("83.33"), rate.rate)
        self.assertIsInstance(index.profiles_by_user_id["user_01"].current_available_balance, Decimal)

    def test_missing_amount_and_optional_fields_remain_none(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_minimal_dataset(root)
            index = load_dataset(root)
            event = index.events_by_id["e1"]
            self.assertIsNone(event.amount)
            self.assertIsNone(event.minimum_allowed_amount)
            self.assertIsNone(index.profiles_by_user_id["u1"].max_installment_months)
            self.assertIsNone(index.payment_options_by_id["p1"].payment_frequency_days)

    def test_duplicate_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_minimal_dataset(root)
            with (root / "financial_events.csv").open("a", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow(["e1", "u1", "expense", "Duplicate", "rent", "debit", "1", "INR", "2026-01-03", "2026-01-03", "settled", "", "fixed", ""])
            with self.assertRaisesRegex(DatasetValidationError, "Duplicate event_id: e1"):
                load_dataset(root)

    def test_broken_foreign_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_minimal_dataset(root)
            with (root / "messages.csv").open("a", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow(["m2", "u1", "missing-request", "", "2026-01-01T00:00:00Z", "bank", "Broken"])
            with self.assertRaisesRegex(DatasetValidationError, "unknown request"):
                load_dataset(root)

    def test_missing_required_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_minimal_dataset(root)
            (root / "exchange_rates.csv").write_text("rate_date,from_currency,to_currency\n", encoding="utf-8")
            with self.assertRaisesRegex(DatasetValidationError, "missing required columns"):
                load_dataset(root)

    def test_duplicate_output_template_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_minimal_dataset(root)
            with (root / "output.csv").open("a", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow(["r1", "", "", "", "", "", "", ""])
            with self.assertRaisesRegex(DatasetValidationError, "duplicate request_id"):
                load_dataset(root)


if __name__ == "__main__":
    unittest.main()
