from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from buy_or_wait.models import ScheduledPayment, SpendingChange, UserProfile
from buy_or_wait.spending_changes import SpendingChangeEngine
from test_forecast import START, event


def profile(
    *, reducible: tuple[str, ...] = (), stoppable: tuple[str, ...] = (),
    protected: tuple[str, ...] = (), balance: str = "180", floor: str = "50",
) -> UserProfile:
    return UserProfile(
        "u1", "INR", Decimal(balance), Decimal(floor), (), protected, reducible, stoppable,
        ("full_payment",), None,
    )


def recurring_stream(
    prefix: str, category: str, amount: str, *, flexibility: str,
    minimum: str | None = None,
) -> tuple:
    dates = (START - timedelta(days=14), START - timedelta(days=7), START)
    return tuple(replace(
        event(f"{prefix}-{index}", when, amount, recurring=True, category=category),
        is_flexible=flexibility != "fixed", flexibility=flexibility,
        minimum_allowed_amount=None if minimum is None else Decimal(minimum),
    ) for index, when in enumerate(dates))


class SpendingChangeTests(unittest.TestCase):
    def test_only_flexible_non_protected_recurring_expenses_are_eligible(self) -> None:
        flexible = recurring_stream("dining", "dining", "20", flexibility="reducible", minimum="10")
        fixed = recurring_stream("fixed", "movies", "20", flexibility="fixed")
        protected = recurring_stream("protected", "groceries", "20", flexibility="stoppable")
        engine = SpendingChangeEngine()
        eligible = engine.eligible_events(
            profile=profile(reducible=("dining",), stoppable=("groceries",), protected=("groceries",)),
            normalized_events=flexible + fixed + protected, request_date=START,
        )
        self.assertEqual(("dining-2",), tuple(item.event_id for item in eligible))

    def test_stopping_a_permitted_expense_makes_the_payment_safe(self) -> None:
        subscriptions = recurring_stream("subscription", "delivery", "20", flexibility="stoppable")
        candidates = SpendingChangeEngine().generate_safe_candidates(
            profile=profile(stoppable=("delivery",)), normalized_events=subscriptions,
            request_date=START, proposed_payments=(ScheduledPayment(START, Decimal("100")),), horizon_days=15,
        )
        self.assertEqual(1, len(candidates))
        self.assertEqual((SpendingChange("subscription-2", "stop", START),), candidates[0].changes)

    def test_reduction_uses_the_recorded_minimum_and_makes_plan_safe(self) -> None:
        dining = recurring_stream("dining", "dining", "50", flexibility="reducible", minimum="20")
        candidates = SpendingChangeEngine().generate_safe_candidates(
            profile=profile(reducible=("dining",), balance="220"), normalized_events=dining,
            request_date=START, proposed_payments=(ScheduledPayment(START, Decimal("100")),), horizon_days=15,
        )
        self.assertEqual(
            (SpendingChange("dining-2", "reduce_to", START, Decimal("20")),), candidates[0].changes,
        )

    def test_two_changes_can_be_necessary_and_are_returned_without_duplicates(self) -> None:
        dining = recurring_stream("dining", "dining", "40", flexibility="stoppable")
        delivery = recurring_stream("delivery", "delivery", "30", flexibility="stoppable")
        candidates = SpendingChangeEngine().generate_safe_candidates(
            profile=profile(stoppable=("dining", "delivery"), balance="200"),
            normalized_events=dining + delivery, request_date=START,
            proposed_payments=(ScheduledPayment(START, Decimal("100")),), horizon_days=15,
        )
        self.assertEqual(1, len(candidates))
        self.assertEqual({"dining-2", "delivery-2"}, {change.event_id for change in candidates[0].changes})
        self.assertEqual(2, len(candidates[0].changes))

    def test_same_event_stop_and_reduce_conflict_is_rejected(self) -> None:
        dining = recurring_stream("dining", "dining", "50", flexibility="reducible_or_stoppable", minimum="20")
        errors = SpendingChangeEngine().validate_changes(
            changes=(
                SpendingChange("dining-2", "stop", START),
                SpendingChange("dining-2", "reduce_to", START, Decimal("20")),
            ),
            profile=profile(reducible=("dining",), stoppable=("dining",)),
            normalized_events=dining, request_date=START,
        )
        self.assertIn("same_event_changed_twice", errors)
        self.assertIn("same_recurring_stream_changed_twice", errors)

    def test_insufficient_change_is_not_returned_as_safe(self) -> None:
        dining = recurring_stream("dining", "dining", "20", flexibility="reducible", minimum="15")
        candidates = SpendingChangeEngine().generate_safe_candidates(
            profile=profile(reducible=("dining",), balance="160"), normalized_events=dining,
            request_date=START, proposed_payments=(ScheduledPayment(START, Decimal("100")),), horizon_days=15,
        )
        self.assertEqual((), candidates)

    def test_change_validation_rejects_negative_and_non_source_reductions(self) -> None:
        dining = recurring_stream("dining", "dining", "50", flexibility="reducible", minimum="20")
        engine = SpendingChangeEngine()
        negative = engine.validate_changes(
            changes=(SpendingChange("dining-2", "reduce_to", START, Decimal("-1")),),
            profile=profile(reducible=("dining",)), normalized_events=dining, request_date=START,
        )
        invented = engine.validate_changes(
            changes=(SpendingChange("dining-2", "reduce_to", START, Decimal("25")),),
            profile=profile(reducible=("dining",)), normalized_events=dining, request_date=START,
        )
        self.assertIn("reduction_amount_must_be_non_negative", negative)
        self.assertIn("reduction_must_use_source_minimum", invented)


if __name__ == "__main__":
    unittest.main()
