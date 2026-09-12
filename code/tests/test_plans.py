from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from buy_or_wait.models import PaymentOption, PaymentPlan, Request, ScheduledPayment, UserProfile
from buy_or_wait.plans import PlanGenerator, PlanValidator
from test_forecast import START


def profile(
    *, methods: tuple[str, ...] = ("full_payment", "partial_payment", "installments"),
    max_installments: int | None = 3, balance: str = "250", floor: str = "50",
) -> UserProfile:
    return UserProfile(
        "u1", "INR", Decimal(balance), Decimal(floor), (), (), (), (), methods, max_installments,
    )


def request(*, partial: bool = True, deadline_days: int = 40) -> Request:
    return Request(
        "r1", "u1", START, "purchase", Decimal("100"), START + timedelta(days=deadline_days),
        partial, "test request",
    )


def option(
    option_id: str, method: str, amount: str, count: int, first_day: int,
    frequency: int | None, total: str, fee: str = "0", request_id: str = "r1",
) -> PaymentOption:
    return PaymentOption(
        option_id, request_id, method, Decimal(amount), count, START + timedelta(days=first_day),
        frequency, Decimal(fee), Decimal(total),
    )


FULL = option("full", "full_payment", "100", 1, 0, None, "100")
INSTALLMENTS = option("installments", "installments", "50", 2, 1, 30, "100")


class PlanTests(unittest.TestCase):
    def validate(
        self, plan: PaymentPlan, *, user: UserProfile | None = None,
        purchase: Request | None = None, options: tuple[PaymentOption, ...] = (FULL, INSTALLMENTS),
        safe: str = "40", earliest_days: int | None = 5,
    ):
        return PlanValidator(horizon_days=40).validate(
            plan=plan, request=purchase or request(), profile=user or profile(), payment_options=options,
            normalized_events=(), amount_safe_to_pay=Decimal(safe),
            earliest_full_payment_date=None if earliest_days is None else START + timedelta(days=earliest_days),
        )

    def test_generator_returns_supported_candidate_types_and_exact_option_schedule(self) -> None:
        plans = PlanGenerator().generate(
            request=request(), profile=profile(), payment_options=(FULL, INSTALLMENTS),
            amount_safe_to_pay=Decimal("40"), earliest_full_payment_date=START + timedelta(days=5),
        )
        self.assertEqual(
            {"full_payment", "partial_payment", "installments", "wait", "not_recommended"},
            {candidate.method for candidate in plans},
        )
        installment = next(candidate for candidate in plans if candidate.method == "installments")
        self.assertEqual(
            (ScheduledPayment(START + timedelta(days=1), Decimal("50"), "option:installments:1"),
             ScheduledPayment(START + timedelta(days=31), Decimal("50"), "option:installments:2")),
            installment.payments,
        )

    def test_generator_excludes_options_for_other_requests_and_partial_when_ineligible(self) -> None:
        foreign = option("other", "full_payment", "100", 1, 0, None, "100", request_id="other-request")
        plans = PlanGenerator().generate(
            request=request(partial=False), profile=profile(methods=("full_payment",)),
            payment_options=(FULL, foreign), amount_safe_to_pay=Decimal("40"),
            earliest_full_payment_date=START + timedelta(days=5),
        )
        self.assertEqual({"full_payment", "wait", "not_recommended"}, {plan.method for plan in plans})
        self.assertNotIn("other", {plan.payment_option_id for plan in plans})

    def test_supplied_full_and_installment_plans_validate(self) -> None:
        generated = PlanGenerator().generate(
            request=request(), profile=profile(), payment_options=(FULL, INSTALLMENTS),
            amount_safe_to_pay=Decimal("40"), earliest_full_payment_date=START + timedelta(days=5),
        )
        for method in ("full_payment", "installments"):
            with self.subTest(method=method):
                result = self.validate(next(plan for plan in generated if plan.method == method))
                self.assertTrue(result.is_valid, result.errors)
                self.assertTrue(result.completes_by_deadline)

    def test_installment_schedule_must_exactly_match_supplied_option(self) -> None:
        invalid = PaymentPlan(
            "installments",
            (ScheduledPayment(START + timedelta(days=1), Decimal("50"), "option:installments:1"),
             ScheduledPayment(START + timedelta(days=32), Decimal("50"), "option:installments:2")),
            Decimal("100"), "installments", Decimal("0"),
        )
        self.assertIn("payment_schedule_does_not_match_option", self.validate(invalid).errors)

    def test_payment_method_and_installment_limit_preferences_are_enforced(self) -> None:
        full_plan = PaymentPlan("full_payment", (ScheduledPayment(START, Decimal("100"), "option:full:1"),), Decimal("100"), "full", Decimal("0"))
        self.assertIn("payment_method_not_accepted", self.validate(full_plan, user=profile(methods=("installments",))).errors)
        self.assertIn(
            "installment_count_exceeds_preference",
            self.validate(PaymentPlan("installments", (ScheduledPayment(START + timedelta(days=1), Decimal("50"), "option:installments:1"), ScheduledPayment(START + timedelta(days=31), Decimal("50"), "option:installments:2")), Decimal("100"), "installments", Decimal("0")), user=profile(max_installments=1)).errors,
        )

    def test_partial_plan_requires_exact_two_payment_rule(self) -> None:
        valid = PaymentPlan(
            "partial_payment", (ScheduledPayment(START, Decimal("40"), "partial:first"), ScheduledPayment(START + timedelta(days=5), Decimal("60"), "partial:remainder")),
            Decimal("100"), None, Decimal("0"),
        )
        self.assertTrue(self.validate(valid).is_valid)
        invalid = PaymentPlan(
            "partial_payment", (ScheduledPayment(START, Decimal("30"), "partial:first"), ScheduledPayment(START + timedelta(days=5), Decimal("60"), "partial:remainder")),
            Decimal("90"), None, Decimal("0"),
        )
        errors = self.validate(invalid).errors
        self.assertIn("partial_first_payment_must_equal_safe_amount", errors)
        self.assertIn("partial_remainder_mismatch", errors)
        self.assertIn("partial_payments_do_not_total_request", errors)

    def test_partial_plan_checks_request_permission_and_deadline(self) -> None:
        plan = PaymentPlan(
            "partial_payment", (ScheduledPayment(START, Decimal("40")), ScheduledPayment(START + timedelta(days=5), Decimal("60"))),
            Decimal("100"), None, Decimal("0"),
        )
        self.assertIn("partial_payment_not_allowed", self.validate(plan, purchase=request(partial=False)).errors)
        late = PaymentPlan(
            "partial_payment", (ScheduledPayment(START, Decimal("40")), ScheduledPayment(START + timedelta(days=6), Decimal("60"))),
            Decimal("100"), None, Decimal("0"),
        )
        errors = self.validate(late, purchase=request(deadline_days=5), earliest_days=6).errors
        self.assertIn("request_not_completed_by_deadline", errors)

    def test_wait_plan_requires_the_computed_full_payment_date(self) -> None:
        valid = PaymentPlan("wait", (ScheduledPayment(START + timedelta(days=5), Decimal("100"), "wait:full"),), Decimal("100"), None, Decimal("0"))
        self.assertTrue(self.validate(valid).is_valid)
        invalid = PaymentPlan("wait", (ScheduledPayment(START + timedelta(days=6), Decimal("100"), "wait:full"),), Decimal("100"), None, Decimal("0"))
        self.assertIn("wait_date_must_equal_earliest_full_date", self.validate(invalid).errors)

    def test_forecast_safety_and_deadline_errors_are_exposed(self) -> None:
        unsafe = PaymentPlan("full_payment", (ScheduledPayment(START, Decimal("100"), "option:full:1"),), Decimal("100"), "full", Decimal("0"))
        self.assertIn("minimum_balance_breached", self.validate(unsafe, user=profile(balance="140", floor="50")).errors)
        late_option = option("late", "full_payment", "100", 1, 41, None, "100")
        late = PaymentPlan("full_payment", (ScheduledPayment(START + timedelta(days=41), Decimal("100"), "option:late:1"),), Decimal("100"), "late", Decimal("0"))
        self.assertIn("request_not_completed_by_deadline", self.validate(late, options=(late_option,)).errors)

    def test_not_recommended_is_a_non_payment_fallback(self) -> None:
        result = self.validate(PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True))
        self.assertTrue(result.is_valid)
        self.assertFalse(result.completes_by_deadline)
        self.assertIsNone(result.forecast)


if __name__ == "__main__":
    unittest.main()
