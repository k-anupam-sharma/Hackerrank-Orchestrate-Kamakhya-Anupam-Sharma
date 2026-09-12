"""Deterministic safe-plan selection and output-field rendering."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from .models import PaymentPlan, PlanValidationResult, Recommendation, Request, UserProfile


def choose_best_plan(
    *,
    plans: Sequence[PaymentPlan],
    validations: Mapping[PaymentPlan, PlanValidationResult],
    profile: UserProfile,
) -> PaymentPlan:
    """Choose the best validated eligible plan, or a `not_recommended` fallback.

    The sort key exactly follows the published ordering. A source option ID's
    numeric suffix is used only at the final tie-break, as the dataset's option
    IDs are numbered identifiers. Plans without a source option sort before a
    source option only when every substantive criterion is identical.
    """
    eligible = [
        plan for plan in plans
        if _is_safe_eligible(plan, validations.get(plan), profile)
    ]
    if eligible:
        return min(eligible, key=_rank_key)
    return next(
        (plan for plan in plans if plan.method == "not_recommended" and plan.is_fallback),
        PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True),
    )


def map_plan_to_recommendation(
    *,
    plan: PaymentPlan,
    request: Request,
    earliest_full_payment_date: date | None,
) -> Recommendation:
    """Render allowed output fields from a selected, already validated plan."""
    if plan.method == "not_recommended":
        return Recommendation("not_affordable", "not_recommended", "none", "none")
    if (
        plan.method == "full_payment"
        and not plan.spending_changes
        and earliest_full_payment_date == request.request_date
    ):
        status = "affordable_now"
    elif plan.method == "wait":
        status = "affordable_later"
    else:
        status = "affordable_with_plan"
    return Recommendation(
        status,
        plan.method,
        _format_payment_plan(plan),
        _format_spending_changes(plan),
    )


def _is_safe_eligible(
    plan: PaymentPlan,
    validation: PlanValidationResult | None,
    profile: UserProfile,
) -> bool:
    if plan.method == "not_recommended" or validation is None:
        return False
    if not validation.is_valid or not validation.completes_by_deadline:
        return False
    accepted_method = "full_payment" if plan.method == "wait" else plan.method
    return accepted_method in profile.payment_methods


def _rank_key(plan: PaymentPlan) -> tuple[object, ...]:
    # Completion is retained in the key as a defensive assertion of the public
    # ordering, even though only completed validated candidates reach this point.
    first_date = plan.payments[0].payment_date if plan.payments else date.max
    return (
        0,  # completes by deadline (enforced by _is_safe_eligible)
        0 if not plan.spending_changes else 1,
        plan.total_paid,
        first_date,
        len(plan.payments),
        _payment_option_key(plan.payment_option_id),
    )


def _payment_option_key(option_id: str | None) -> tuple[int, int, str]:
    if option_id is None:
        return (0, -1, "")
    match = re.search(r"(\d+)$", option_id)
    return (1, int(match.group(1)) if match else 0, option_id)


def _format_money(amount: Decimal) -> str:
    return format(amount, "f")


def _format_payment_plan(plan: PaymentPlan) -> str:
    if not plan.payments:
        return "none"
    return "|".join(
        f"{payment.payment_date.isoformat()}:{_format_money(payment.amount)}"
        for payment in plan.payments
    )


def _format_spending_changes(plan: PaymentPlan) -> str:
    if not plan.spending_changes:
        return "none"
    rendered: list[str] = []
    for change in plan.spending_changes:
        if change.action == "stop":
            rendered.append(f"stop:{change.event_id}")
        else:
            assert change.new_amount is not None
            rendered.append(f"reduce_to:{change.event_id}:{_format_money(change.new_amount)}")
    return "|".join(rendered)
