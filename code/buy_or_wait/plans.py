"""Generate and validate payment-plan candidates without ranking or recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from .forecast import forecast_balance, is_plan_safe
from .models import (
    NormalizedEvent, PaymentOption, PaymentPlan, PlanValidationResult,
    Request, ScheduledPayment, UserProfile,
)
from .spending_changes import SpendingChangeEngine


def _option_schedule(option: PaymentOption) -> tuple[ScheduledPayment, ...]:
    if option.number_of_payments <= 0:
        return ()
    if option.number_of_payments > 1 and option.payment_frequency_days is None:
        return ()
    interval = option.payment_frequency_days or 0
    return tuple(ScheduledPayment(
        option.first_payment_date + timedelta(days=interval * number), option.payment_amount,
        f"option:{option.payment_option_id}:{number + 1}",
    ) for number in range(option.number_of_payments))


@dataclass(frozen=True)
class PlanGenerator:
    """Create every syntactically eligible plan supported by request/profile/option data."""

    def generate(
        self,
        *,
        request: Request,
        profile: UserProfile,
        payment_options: Sequence[PaymentOption],
        amount_safe_to_pay: Decimal,
        earliest_full_payment_date: date | None,
    ) -> tuple[PaymentPlan, ...]:
        candidates: list[PaymentPlan] = []
        for option in payment_options:
            if option.request_id != request.request_id:
                continue
            if option.payment_method == "full_payment" and "full_payment" in profile.payment_methods:
                candidates.append(PaymentPlan(
                    "full_payment", _option_schedule(option), option.total_payable_amount,
                    option.payment_option_id, option.financing_fee,
                ))
            elif option.payment_method == "installments" and "installments" in profile.payment_methods:
                candidates.append(PaymentPlan(
                    "installments", _option_schedule(option), option.total_payable_amount,
                    option.payment_option_id, option.financing_fee,
                ))
        if (
            request.allows_partial_payment
            and "partial_payment" in profile.payment_methods
            and Decimal("0") < amount_safe_to_pay < request.requested_amount
            and earliest_full_payment_date is not None
            and earliest_full_payment_date <= request.desired_completion_date
        ):
            candidates.append(PaymentPlan(
                "partial_payment",
                (
                    ScheduledPayment(request.request_date, amount_safe_to_pay, "partial:first"),
                    ScheduledPayment(earliest_full_payment_date, request.requested_amount - amount_safe_to_pay, "partial:remainder"),
                ),
                request.requested_amount, None, Decimal("0"),
            ))
        if (
            earliest_full_payment_date is not None
            and earliest_full_payment_date > request.request_date
            and earliest_full_payment_date <= request.desired_completion_date
            and "full_payment" in profile.payment_methods
        ):
            candidates.append(PaymentPlan(
                "wait", (ScheduledPayment(earliest_full_payment_date, request.requested_amount, "wait:full"),),
                request.requested_amount, None, Decimal("0"),
            ))
        candidates.append(PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True))
        return tuple(candidates)


@dataclass(frozen=True)
class PlanValidator:
    """Validate plan eligibility, exact schedules, completion, and forecast safety."""

    horizon_days: int = 90

    def validate(
        self,
        *,
        plan: PaymentPlan,
        request: Request,
        profile: UserProfile,
        payment_options: Sequence[PaymentOption],
        normalized_events: Sequence[NormalizedEvent],
        amount_safe_to_pay: Decimal,
        earliest_full_payment_date: date | None,
    ) -> PlanValidationResult:
        errors: list[str] = []
        if plan.method == "not_recommended":
            if plan.payments or not plan.is_fallback:
                errors.append("invalid_fallback_shape")
            return PlanValidationResult(not errors, False, tuple(errors), None)
        if plan.method not in {"full_payment", "partial_payment", "installments", "wait"}:
            errors.append("unknown_payment_method")
        errors.extend(SpendingChangeEngine().validate_changes(
            changes=plan.spending_changes, profile=profile,
            normalized_events=normalized_events, request_date=request.request_date,
        ))
        accepted_method = "full_payment" if plan.method == "wait" else plan.method
        if accepted_method not in profile.payment_methods:
            errors.append("payment_method_not_accepted")
        if any(payment.amount <= Decimal("0") for payment in plan.payments):
            errors.append("payment_amount_must_be_positive")
        if tuple(sorted(payment.payment_date for payment in plan.payments)) != tuple(payment.payment_date for payment in plan.payments):
            errors.append("payment_schedule_not_chronological")
        option_by_id = {
            option.payment_option_id: option
            for option in payment_options
            if option.request_id == request.request_id
        }
        if plan.method in {"full_payment", "installments"}:
            self._validate_option_plan(plan, option_by_id, profile, errors)
        elif plan.method == "partial_payment":
            self._validate_partial_plan(plan, request, amount_safe_to_pay, earliest_full_payment_date, errors)
        elif plan.method == "wait":
            self._validate_wait_plan(plan, request, earliest_full_payment_date, errors)
        completes = self._completes_by_deadline(plan, request, option_by_id)
        if not completes:
            errors.append("request_not_completed_by_deadline")
        forecast = forecast_balance(
            starting_balance=profile.current_available_balance,
            minimum_balance_to_keep=profile.minimum_balance_to_keep,
            normalized_events=normalized_events,
            request_date=request.request_date,
            spending_changes=plan.spending_changes,
            proposed_payments=plan.payments,
            horizon_days=self.horizon_days,
        )
        if not is_plan_safe(forecast):
            errors.append("minimum_balance_breached")
        return PlanValidationResult(not errors, completes, tuple(errors), forecast)

    @staticmethod
    def _validate_option_plan(
        plan: PaymentPlan, option_by_id: dict[str, PaymentOption], profile: UserProfile, errors: list[str]
    ) -> None:
        option = option_by_id.get(plan.payment_option_id or "")
        if option is None:
            errors.append("payment_option_not_supplied")
            return
        if option.payment_method != plan.method:
            errors.append("payment_option_method_mismatch")
        expected = _option_schedule(option)
        if plan.payments != expected:
            errors.append("payment_schedule_does_not_match_option")
        if plan.total_paid != option.total_payable_amount or plan.financing_fee != option.financing_fee:
            errors.append("payment_option_total_mismatch")
        if plan.method == "installments":
            if profile.max_installment_months is None:
                errors.append("installments_not_permitted")
            elif option.number_of_payments > profile.max_installment_months:
                errors.append("installment_count_exceeds_preference")

    @staticmethod
    def _validate_partial_plan(
        plan: PaymentPlan, request: Request, amount_safe_to_pay: Decimal,
        earliest_full_payment_date: date | None, errors: list[str],
    ) -> None:
        if not request.allows_partial_payment:
            errors.append("partial_payment_not_allowed")
        if len(plan.payments) != 2:
            errors.append("partial_payment_requires_two_payments")
            return
        first, second = plan.payments
        if first.payment_date != request.request_date:
            errors.append("partial_first_payment_must_be_on_request_date")
        if not (Decimal("0") < first.amount < request.requested_amount):
            errors.append("partial_first_payment_out_of_range")
        if not (Decimal("0") < amount_safe_to_pay < request.requested_amount):
            errors.append("partial_safe_amount_not_eligible")
        if first.amount != amount_safe_to_pay:
            errors.append("partial_first_payment_must_equal_safe_amount")
        if earliest_full_payment_date is None:
            errors.append("partial_requires_earliest_full_payment_date")
        elif second.payment_date != earliest_full_payment_date:
            errors.append("partial_remainder_date_must_equal_earliest_full_date")
        if second.amount != request.requested_amount - first.amount:
            errors.append("partial_remainder_mismatch")
        if first.amount + second.amount != request.requested_amount:
            errors.append("partial_payments_do_not_total_request")

    @staticmethod
    def _validate_wait_plan(
        plan: PaymentPlan, request: Request, earliest_full_payment_date: date | None, errors: list[str]
    ) -> None:
        if len(plan.payments) != 1 or plan.payments[0].amount != request.requested_amount:
            errors.append("wait_requires_one_full_payment")
            return
        if plan.payments[0].payment_date <= request.request_date:
            errors.append("wait_payment_must_be_after_request_date")
        if earliest_full_payment_date is None or plan.payments[0].payment_date != earliest_full_payment_date:
            errors.append("wait_date_must_equal_earliest_full_date")

    @staticmethod
    def _completes_by_deadline(
        plan: PaymentPlan, request: Request, option_by_id: dict[str, PaymentOption]
    ) -> bool:
        if not plan.payments or plan.payments[-1].payment_date > request.desired_completion_date:
            return False
        if plan.method in {"partial_payment", "wait"}:
            return sum((payment.amount for payment in plan.payments), Decimal("0")) == request.requested_amount
        option = option_by_id.get(plan.payment_option_id or "")
        return option is not None and tuple(plan.payments) == _option_schedule(option)
