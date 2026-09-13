"""Fact-bounded final explanations; no reasoning or decision authority lives here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Sequence

from .models import NormalizedEvent, Recommendation, Request, UserProfile


@dataclass(frozen=True)
class ExplanationFacts:
    amount_safe_to_pay: Decimal
    requested_amount: Decimal
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    request_date: date
    desired_completion_date: date
    recommendation: Recommendation
    earliest_full_payment_date: date | None
    confirmed_income: tuple[NormalizedEvent, ...]
    recurring_expenses: tuple[NormalizedEvent, ...]

    def closed_fields(self) -> dict[str, str]:
        fields = {
            "amount_safe_to_pay": _money(self.amount_safe_to_pay),
            "requested_amount": _money(self.requested_amount),
            "home_currency": self.home_currency,
            "current_available_balance": _money(self.current_available_balance),
            "minimum_balance_to_keep": _money(self.minimum_balance_to_keep),
            "request_date": self.request_date.isoformat(),
            "desired_completion_date": self.desired_completion_date.isoformat(),
            "recommended_payment_method": self.recommendation.recommended_payment_method,
            "affordability_status": self.recommendation.affordability_status,
            "payment_plan": self.recommendation.payment_plan,
            "spending_changes_needed": self.recommendation.spending_changes_needed,
            "earliest_date_for_full_payment": "" if self.earliest_full_payment_date is None else self.earliest_full_payment_date.isoformat(),
            "forecast_horizon_days": "90",
        }
        for index, event in enumerate(self.confirmed_income):
            fields[f"confirmed_income_{index}_amount"] = _money(event.amount_in_home_currency or Decimal("0"))
            fields[f"confirmed_income_{index}_date"] = event.effective_date.isoformat()
        for index, event in enumerate(self.recurring_expenses):
            fields[f"recurring_expense_{index}_amount"] = _money(event.amount_in_home_currency or Decimal("0"))
            fields[f"recurring_expense_{index}_date"] = event.effective_date.isoformat()
        return fields


def build_explanation_facts(
    *, profile: UserProfile, request: Request, normalized_events: Sequence[NormalizedEvent],
    amount_safe_to_pay: Decimal, recommendation: Recommendation, earliest_full_payment_date: date | None,
) -> ExplanationFacts:
    """Select a small deterministic set of source-backed facts for explanation only."""
    confirmed_income = tuple(sorted((
        event for event in normalized_events
        if request.request_date <= event.effective_date
        and event.direction == "credit"
        and event.event_type == "income"
        and event.category == "salary"
        and event.cash_treatment in {"settled_cash", "scheduled_cash"}
        and event.amount_in_home_currency is not None
    ), key=lambda event: (event.effective_date, event.event_id))[:2])
    recurring_expenses = tuple(sorted((
        event for event in normalized_events
        if event.is_recurring
        and event.direction == "debit"
        and event.amount_in_home_currency is not None
        and event.cash_treatment in {"settled_cash", "reserve_pending_debit", "scheduled_cash"}
    ), key=lambda event: (-event.amount_in_home_currency, event.event_id))[:2])
    return ExplanationFacts(
        amount_safe_to_pay, request.requested_amount, profile.home_currency,
        profile.current_available_balance, profile.minimum_balance_to_keep,
        request.request_date, request.desired_completion_date, recommendation,
        earliest_full_payment_date,
        confirmed_income, recurring_expenses,
    )


def generate_explanation(facts: ExplanationFacts) -> str:
    """Produce the concise deterministic explanation for an already-selected result."""
    return deterministic_explanation(facts)


def deterministic_explanation(facts: ExplanationFacts) -> str:
    """Explain an already-selected result; this function never decides it.

    The wording deliberately follows a consistent order: requested amount,
    immediately safe capacity, safety boundary, selected schedule, and the
    small number of verified cash-flow facts relevant to the 90-day forecast.
    This keeps the explanation useful in a CSV cell without turning it into a
    second financial engine.
    """
    currency = facts.home_currency
    safe = _money(facts.amount_safe_to_pay)
    requested = _money(facts.requested_amount)
    floor = _money(facts.minimum_balance_to_keep)
    balance = _money(facts.current_available_balance)
    recommendation = facts.recommendation
    text = (
        f"Requested: {currency} {requested}. Safe to pay today: {currency} {safe}. "
        f"Current available balance: {currency} {balance}; required minimum balance: {currency} {floor}. "
    )
    if recommendation.recommended_payment_method == "not_recommended":
        text += (
            f"Recommendation: not_recommended. No safe eligible supplied payment plan completes the request by {facts.desired_completion_date.isoformat()} "
            f"while preserving the 90-day minimum-balance requirement."
        )
    else:
        text += (
            f"Recommendation: {recommendation.recommended_payment_method}. "
            f"Payment plan: {recommendation.payment_plan}. "
        )
        if recommendation.affordability_status == "affordable_now":
            text += "The selected full payment is safe on the request date under the deterministic 90-day forecast."
        elif recommendation.affordability_status == "affordable_later":
            text += "The selected full payment becomes safe later within the forecast horizon."
        else:
            text += "The selected plan completes the request by its deadline while preserving the 90-day minimum-balance requirement."
    if facts.earliest_full_payment_date is not None and facts.earliest_full_payment_date != _plan_first_date(recommendation.payment_plan):
        text += f" Earliest safe full-payment date: {facts.earliest_full_payment_date.isoformat()}."
    if recommendation.spending_changes_needed != "none":
        text += f" Required spending changes: {recommendation.spending_changes_needed}."
    if facts.confirmed_income:
        income = facts.confirmed_income[0]
        text += f" Included confirmed salary: {currency} {_money(income.amount_in_home_currency or Decimal('0'))} on {income.effective_date.isoformat()}."
    if facts.recurring_expenses:
        expense = facts.recurring_expenses[0]
        expense_detail = f" Included recurring {expense.category} expense: {currency} {_money(expense.amount_in_home_currency or Decimal('0'))}."
        # The evaluator permits a compact CSV-cell explanation. Keep the most
        # decision-relevant, dated income fact when the selected plan itself
        # already consumes the available explanation budget.
        if len(text) + len(expense_detail) <= 500:
            text += expense_detail
    return text


def validate_explanation(explanation: str, facts: ExplanationFacts) -> bool:
    """Reject blank, contradictory, or fact-expanding text from an optional rephraser."""
    text = explanation.strip()
    if not text or len(text) > 500:
        return False
    method = facts.recommendation.recommended_payment_method
    if method not in text:
        return False
    # The transport already rejects unknown numeric/date/currency literals. These
    # checks additionally require any stated change to match structured output.
    if facts.recommendation.spending_changes_needed != "none" and facts.recommendation.spending_changes_needed not in text:
        return False
    prohibited_methods = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"} - {method}
    if any(other in text for other in prohibited_methods):
        return False
    allowed_text = " ".join(facts.closed_fields().values())
    literals = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d+(?:\.\d+)?|INR|ZAR|IDR|USD|EUR)\b", text)
    return all(literal in allowed_text for literal in literals)


def _money(value: Decimal) -> str:
    return format(value, "f")


def _plan_first_date(payment_plan: str) -> date | None:
    if payment_plan == "none":
        return None
    try:
        return date.fromisoformat(payment_plan.split("|", 1)[0].split(":", 1)[0])
    except ValueError:
        return None
