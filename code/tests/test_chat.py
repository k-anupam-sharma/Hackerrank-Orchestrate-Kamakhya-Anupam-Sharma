"""Tests for the stateless request-ID terminal interface using real solver data."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat import BuyOrWaitTerminal, run_all, run_terminal


class TerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terminal = BuyOrWaitTerminal(ROOT / "dataset")
        with (ROOT / "output.csv").open(encoding="utf-8", newline="") as handle:
            cls.output_by_id = {row["request_id"]: row for row in csv.DictReader(handle)}

    def test_valid_request_has_concise_recommendation_and_sources(self) -> None:
        text = self.terminal.recommendation("request_67")
        self.assertIn("Recommendation for request_67", text)
        self.assertIn("Sources:", text)
        self.assertIn("dataset/requests.csv -> request_id: request_67", text)
        self.assertNotIn("90-DAY FORECAST", text)
        self.assertNotIn("What would you like to ask", text)

    def test_invalid_request_id_is_short_error(self) -> None:
        self.assertEqual("Request ID not found: request_999", self.terminal.recommendation("request_999"))

    def test_several_request_ids_match_existing_output_rows(self) -> None:
        for request_id in ("request_67", "request_69", "request_89", "request_90", "request_95"):
            with self.subTest(request_id=request_id):
                text = self.terminal.recommendation(request_id)
                row = self.output_by_id[request_id]
                profile = self.terminal.index.profiles_by_user_id[self.terminal.index.evaluation_requests_by_id[request_id].user_id]
                self.assertIn(f"Safe to pay now: {profile.home_currency} {row['amount_safe_to_pay']}", text)
                self.assertIn(f"Decision: {row['affordability_status']}", text)
                self.assertIn(f"Recommended method: {row['recommended_payment_method']}", text)
                self.assertIn(f"Plan: {row['payment_plan']}", text)
                self.assertIn(f"Spending changes: {row['spending_changes_needed']}", text)

    def test_consecutive_requests_are_independent(self) -> None:
        texts = [self.terminal.recommendation(request_id) for request_id in ("request_67", "request_69", "request_89")]
        for request_id, text in zip(("request_67", "request_69", "request_89"), texts):
            self.assertIn(f"Recommendation for {request_id}", text)
            self.assertIn(f"request_id: {request_id}", text)
        self.assertNotIn("request_id: request_67", texts[1])

    def test_runner_only_accepts_request_ids_or_exit(self) -> None:
        inputs = iter(("request_67", "summary", "exit"))
        output: list[str] = []
        self.assertEqual(0, run_terminal(self.terminal, input_fn=lambda _prompt: next(inputs), output_fn=output.append))
        self.assertTrue(any("Recommendation for request_67" in item for item in output))
        self.assertIn("Request ID not found: summary", output)
        self.assertFalse(any("Try summary" in item for item in output))

    def test_all_mode_and_output_file_use_real_requests(self) -> None:
        # Exercise the all-mode formatter with a real subset; the CLI full run is
        # separately covered by the evaluator/integration workflow.
        subset_ids = tuple(self.terminal.index.evaluation_requests_by_id)[:2]
        original = self.terminal.all_recommendations
        self.terminal.all_recommendations = lambda: ((request_id, self.terminal.recommendation(request_id)) for request_id in subset_ids)
        output: list[str] = []
        successful, failed, failures = run_all(self.terminal, output_fn=output.append)
        self.terminal.all_recommendations = original
        self.assertEqual((2, 0, ()), (successful, failed, failures))
        self.assertIn("Processed: 2 requests", output)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "recommendations.txt"
            path.write_text("\n".join(output), encoding="utf-8")
            self.assertIn("Recommendation for", path.read_text(encoding="utf-8"))

    def test_debug_mode_is_explicit(self) -> None:
        normal = self.terminal.recommendation("request_69")
        debug = BuyOrWaitTerminal(ROOT / "dataset", debug=True).recommendation("request_69")
        self.assertNotIn("DEBUG", normal)
        self.assertIn("DEBUG", debug)
        self.assertIn("forecast event_ids:", debug)


if __name__ == "__main__":
    unittest.main()
