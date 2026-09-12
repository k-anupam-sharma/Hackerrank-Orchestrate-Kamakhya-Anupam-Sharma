from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from buy_or_wait.models import (
    PaymentPlan, PlanValidationResult, Request, ScheduledPayment, SpendingChange, UserProfile,
)
from buy_or_wait.ranking import choose_best_plan, map_plan_to_recommendation
from test_forecast import START


def profile(methods: tuple[str, ...] = ("full_payment", "partial_payment", "installments")) -> UserProfile:
    return UserProfile("u1", "INR", Decimal("500"), Decimal("0"), (), (), (), (), methods, 12)


def request() -> Request:
    return Request("r1", "u1", START, "purchase", Decimal("100"), START + timedelta(days=30), True, "")


def plan(
    method: str, *, amount: str = "100", first_day: int = 0, count: int = 1,
    option_id: str | None = "payment_option_01", changes: tuple[SpendingChange, ...] = (),
) -> PaymentPlan:
    payments = tuple(
        ScheduledPayment(START + timedelta(days=first_day + index * 7), Decimal(amount) / count, f"{method}:{index}")
        for index in range(count)
    )
    return PaymentPlan(method, payments, Decimal(amount), option_id, Decimal("0"), spending_changes=changes)


VALID = PlanValidationResult(True, True, (), None)
INVALID = PlanValidationResult(False, True, ("minimum_balance_breached",), None)
INCOMPLETE = PlanValidationResult(True, False, ("request_not_completed_by_deadline",), None)


class RankingTests(unittest.TestCase):
    def choose(self, candidates: tuple[PaymentPlan, ...], user: UserProfile | None = None) -> PaymentPlan:
        return choose_best_plan(
            plans=candidates,
            validations={candidate: VALID for candidate in candidates},
            profile=user or profile(),
        )

    def test_no_spending_changes_outrank_a_cheaper_changed_plan(self) -> None:
        unchanged = plan("full_payment", amount="100", option_id="payment_option_01")
        changed = plan(
            "full_payment", amount="90", option_id="payment_option_02",
            changes=(SpendingChange("event_1", "stop", START),),
        )
        self.assertEqual(unchanged, self.choose((changed, unchanged)))

    def test_lower_total_paid_outranks_otherwise_equal_plan(self) -> None:
        expensive = plan("installments", amount="110", option_id="payment_option_01")
        cheap = plan("installments", amount="100", option_id="payment_option_02")
        self.assertEqual(cheap, self.choose((expensive, cheap)))

    def test_earlier_payment_start_outranks_fewer_payments(self) -> None:
        earlier_many = plan("installments", first_day=0, count=3, option_id="payment_option_02")
        later_one = plan("full_payment", first_day=1, count=1, option_id="payment_option_01")
        self.assertEqual(earlier_many, self.choose((later_one, earlier_many)))

    def test_fewer_payments_then_lowest_numeric_option_id_break_ties(self) -> None:
        many = plan("installments", count=2, option_id="payment_option_01")
        one = plan("full_payment", count=1, option_id="payment_option_10")
        lower_option = plan("full_payment", count=1, option_id="payment_option_02")
        self.assertEqual(lower_option, self.choose((many, one, lower_option)))

    def test_invalid_or_incomplete_plans_are_excluded_and_fallback_is_used(self) -> None:
        unsafe = plan("full_payment")
        late = plan("installments")
        fallback = PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True)
        selected = choose_best_plan(
            plans=(unsafe, late, fallback),
            validations={unsafe: INVALID, late: INCOMPLETE, fallback: PlanValidationResult(True, False, (), None)},
            profile=profile(),
        )
        self.assertEqual(fallback, selected)

    def test_unaccepted_immediate_method_is_excluded_and_wait_needs_full_payment_preference(self) -> None:
        installment = plan("installments")
        wait = plan("wait", first_day=5, option_id=None)
        fallback = PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True)
        selected = self.choose((installment, wait, fallback), profile(methods=("full_payment",)))
        self.assertEqual(wait, selected)
        self.assertEqual(
            fallback,
            self.choose((wait, fallback), profile(methods=("installments",))),
        )

    def test_mapping_uses_exact_allowed_statuses_and_output_format(self) -> None:
        full = plan("full_payment", amount="100", option_id="payment_option_01")
        now = map_plan_to_recommendation(plan=full, request=request(), earliest_full_payment_date=START)
        self.assertEqual("affordable_now", now.affordability_status)
        self.assertEqual("2026-01-01:100", now.payment_plan)
        partial = plan("partial_payment", amount="100", count=2, option_id=None)
        with_plan = map_plan_to_recommendation(plan=partial, request=request(), earliest_full_payment_date=START + timedelta(days=5))
        self.assertEqual("affordable_with_plan", with_plan.affordability_status)
        wait = plan("wait", first_day=5, option_id=None)
        self.assertEqual("affordable_later", map_plan_to_recommendation(plan=wait, request=request(), earliest_full_payment_date=START + timedelta(days=5)).affordability_status)
        changed = plan(
            "installments", changes=(
                SpendingChange("event_1", "stop", START),
                SpendingChange("event_2", "reduce_to", START, Decimal("10")),
            ),
        )
        rendered = map_plan_to_recommendation(plan=changed, request=request(), earliest_full_payment_date=START)
        self.assertEqual("stop:event_1|reduce_to:event_2:10", rendered.spending_changes_needed)
        fallback = PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True)
        unavailable = map_plan_to_recommendation(plan=fallback, request=request(), earliest_full_payment_date=None)
        self.assertEqual(("not_affordable", "not_recommended", "none", "none"), (unavailable.affordability_status, unavailable.recommended_payment_method, unavailable.payment_plan, unavailable.spending_changes_needed))


if __name__ == "__main__":
    unittest.main()
