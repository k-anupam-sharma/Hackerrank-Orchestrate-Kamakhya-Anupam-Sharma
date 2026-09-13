from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from buy_or_wait.explanations import build_explanation_facts, generate_explanation, validate_explanation
from buy_or_wait.models import Recommendation, Request, UserProfile
from test_forecast import START, event


class ExplanationTests(unittest.TestCase):
    def profile(self) -> UserProfile:
        return UserProfile("u1", "INR", Decimal("500"), Decimal("100"), (), (), (), (), ("full_payment",), None)

    def request(self) -> Request:
        return Request("r1", "u1", START, "purchase", Decimal("200"), START + timedelta(days=20), False, "")

    def facts(self):
        income = event("salary", START + timedelta(days=2), "100", direction="credit", event_type="income", category="salary")
        recurring = replace(event("rent", START, "50", recurring=True), is_recurring=True)
        recommendation = Recommendation("affordable_now", "full_payment", "2026-01-01:200", "none")
        return build_explanation_facts(
            profile=self.profile(), request=self.request(), normalized_events=(income, recurring),
            amount_safe_to_pay=Decimal("200"), recommendation=recommendation,
            earliest_full_payment_date=START,
        )

    def test_deterministic_explanation_uses_only_verified_constraints(self) -> None:
        explanation = generate_explanation(self.facts())
        self.assertIn("full_payment", explanation)
        self.assertIn("Requested: INR 200", explanation)
        self.assertIn("Safe to pay today: INR 200", explanation)
        self.assertIn("Payment plan: 2026-01-01:200", explanation)
        self.assertIn("INR 200", explanation)
        self.assertIn("INR 100", explanation)
        self.assertIn("2026-01-03", explanation)

    def test_explanation_uses_selected_result_without_making_a_new_decision(self) -> None:
        facts = build_explanation_facts(
            profile=self.profile(), request=self.request(), normalized_events=(), amount_safe_to_pay=Decimal("40"),
            recommendation=Recommendation(
                "affordable_with_plan", "partial_payment", "2026-01-01:40|2026-01-03:160", "none",
            ),
            earliest_full_payment_date=START + timedelta(days=2),
        )
        explanation = generate_explanation(facts)
        self.assertIn("partial_payment", explanation)
        self.assertIn("2026-01-01:40|2026-01-03:160", explanation)
        self.assertIn("Safe to pay today: INR 40", explanation)
        self.assertTrue(validate_explanation(explanation, facts))

    def test_fallback_for_not_recommended_still_names_selected_method(self) -> None:
        facts = build_explanation_facts(
            profile=self.profile(), request=self.request(), normalized_events=(), amount_safe_to_pay=Decimal("0"),
            recommendation=Recommendation("not_affordable", "not_recommended", "none", "none"),
            earliest_full_payment_date=None,
        )
        explanation = generate_explanation(facts)
        self.assertIn("not_recommended", explanation)
        self.assertIn("2026-01-21", explanation)
        self.assertTrue(validate_explanation(explanation, facts))


if __name__ == "__main__":
    unittest.main()
