"""Tests for the temporary sample-testing terminal interface."""

from __future__ import annotations

import csv
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat import BuyOrWaitTerminal, run_all, run_terminal  # noqa: E402
from buy_or_wait.loaders import load_dataset  # noqa: E402


class TerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample = BuyOrWaitTerminal(ROOT / "dataset")
        cls.official = BuyOrWaitTerminal(ROOT / "dataset", sample_mode=False)
        with (ROOT / "output.csv").open(encoding="utf-8", newline="") as handle:
            cls.output_by_id = {row["request_id"]: row for row in csv.DictReader(handle)}

    def test_sample_and_official_request_sets_load(self) -> None:
        index = load_dataset(ROOT / "dataset")
        self.assertEqual(25, len(index.sample_requests_by_id))
        self.assertEqual(250, len(index.evaluation_requests_by_id))
        self.assertEqual(25, len(self.sample.requests_by_id))
        self.assertEqual(250, len(self.official.requests_by_id))

    def test_sample_request_01_and_request_25_lookup(self) -> None:
        self.assertIn("REQUEST", self.sample.recommendation("request_01"))
        self.assertIn("AGENT DECISION", self.sample.recommendation("request_25"))
        self.assertEqual("Request ID not found: request_26", self.sample.recommendation("request_26"))

    def test_default_record_is_labeled_and_csv_mode_is_explicit(self) -> None:
        text = self.sample.recommendation("request_01")
        self.assertIn("Request ID: request_01", text)
        self.assertIn("Safe to pay now:", text)
        self.assertIn("SOURCES", text)
        csv_values = next(csv.reader([self.sample.recommendation("request_01", csv_mode=True)]))
        self.assertEqual(15, len(csv_values))
        self.assertEqual("request_01", csv_values[0])

    def test_csv_header_has_exact_required_order(self) -> None:
        self.assertEqual(
            "request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation",
            self.sample.csv_header(),
        )

    def test_official_request_26_69_and_final_lookup(self) -> None:
        for request_id in ("request_26", "request_69", "request_275"):
            with self.subTest(request_id=request_id):
                values = self.official.recommendation(request_id, csv_mode=True).split(",", 1)
                self.assertEqual(request_id, values[0])
                self.assertEqual(15, len(next(csv.reader([self.official.recommendation(request_id, csv_mode=True)]))))

    def test_sample_answer_columns_are_not_on_canonical_request(self) -> None:
        request = self.sample.index.get_request_context("request_01").request
        canonical_fields = {
            "request_id", "user_id", "request_date", "request_type", "requested_amount",
            "desired_completion_date", "allows_partial_payment", "request_text",
        }
        self.assertEqual(canonical_fields, set(request.__dataclass_fields__))
        for answer_field in (
            "amount_safe_to_pay", "affordability_status", "recommended_payment_method",
            "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed",
            "decision_explanation",
        ):
            self.assertNotIn(answer_field, request.__dataclass_fields__)
        self.assertEqual({}, self.sample.sample_expected_by_id)
        self.sample.comparison("request_01")
        self.assertIn("amount_safe_to_pay", self.sample.sample_expected_by_id["request_01"])

    def test_sample_comparison_is_display_only(self) -> None:
        text, matched = self.sample.comparison("request_01")
        self.assertIn("AGENT:", text)
        self.assertIn("EXPECTED:", text)
        self.assertIn("FIELD COMPARISON:", text)
        self.assertIn("Overall:", text)
        self.assertIsInstance(matched, bool)
        self.assertIn("dataset/sample_requests.csv", text)

    def test_sample_batch_processes_all_source_rows_and_compares(self) -> None:
        output: list[str] = []
        matches, mismatches, mismatch_ids = run_all(self.sample, output_fn=output.append, compare=True)
        self.assertEqual(25, matches + mismatches)
        self.assertEqual(mismatches, len(mismatch_ids))
        self.assertIn("Requests processed: 25", output)
        self.assertTrue(any(item.startswith("Matches: ") for item in output))
        self.assertTrue(any(item.startswith("Mismatches: ") for item in output))
        self.assertIn("Mismatching fields:", output)
        self.assertTrue(any(item.startswith("- request_01:") for item in output))

    def test_all_sample_structured_results_are_independent_and_request01_matches(self) -> None:
        expected = self.sample._load_sample_expected(ROOT / "dataset")
        for request_id in self.sample.requests_by_id:
            with self.subTest(request_id=request_id):
                view = self.sample._build_view(request_id)
                values = self.sample._record_values(view)
                self.assertEqual(request_id, values["request_id"])
                self.assertGreaterEqual(Decimal(values["amount_safe_to_pay"]), Decimal("0"))
                self.assertLessEqual(Decimal(values["amount_safe_to_pay"]), view.context.request.requested_amount)
        # Oracle labels are consulted only after the independent result exists;
        # this guards the primary diagnosed case without leaking labels into
        # Request construction or the solver call.
        actual = self.sample._record_values(self.sample._build_view("request_01"))
        oracle = expected["request_01"]
        for field in ("amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"):
            self.assertTrue(self.sample._field_equal(field, actual[field], oracle[field]), field)

    def test_consecutive_sample_requests_are_independent(self) -> None:
        ids = ("request_01", "request_02", "request_10", "request_20", "request_25")
        texts = [self.sample.recommendation(request_id) for request_id in ids]
        for request_id, text in zip(ids, texts):
            self.assertIn(f"Request ID: {request_id}", text)
            self.assertIn("AGENT DECISION", text)
        self.assertIn("Request ID: request_02", texts[1])

    def test_runner_accepts_request_ids_and_exit_without_chat_prompts(self) -> None:
        inputs = iter(("request_01", "request_999", "exit"))
        output: list[str] = []
        self.assertEqual(0, run_terminal(self.sample, input_fn=lambda _prompt: next(inputs), output_fn=output.append))
        self.assertTrue(any("Request ID: request_01" in item for item in output))
        self.assertIn("Request ID not found: request_999", output)
        self.assertFalse(any("What would you like to ask" in item for item in output))

    def test_debug_mode_is_explicit(self) -> None:
        normal = self.sample.recommendation("request_10")
        debug = BuyOrWaitTerminal(ROOT / "dataset", debug=True).recommendation("request_10")
        self.assertNotIn("DEBUG", normal)
        self.assertIn("DEBUG", debug)

    def test_main_is_thin_official_entrypoint_and_output_rows_are_available(self) -> None:
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("solve_dataset", source)
        self.assertIn('default=ROOT / "dataset"', source)
        self.assertEqual(250, len(self.output_by_id))


if __name__ == "__main__":
    unittest.main()
