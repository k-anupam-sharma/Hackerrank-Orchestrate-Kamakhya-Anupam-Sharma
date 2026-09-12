"""Fact-bounded final explanations; no reasoning or decision authority lives here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Protocol, Sequence

from .models import NormalizedEvent, Recommendation, Request, UserProfile


@dataclass(frozen=True)
class ExplanationFacts:
    amount_safe_to_pay: Decimal
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    recommendation: Recommendation
    earliest_full_payment_date: date | None
    confirmed_income: tuple[NormalizedEvent, ...]
    recurring_expenses: tuple[NormalizedEvent, ...]

    def closed_fields(self) -> dict[str, str]:
        fields = {
            "amount_safe_to_pay": _money(self.amount_safe_to_pay),
            "home_currency": self.home_currency,
            "current_available_balance": _money(self.current_available_balance),
            "minimum_balance_to_keep": _money(self.minimum_balance_to_keep),
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


class OptionalExplanationRephraser(Protocol):
    def generate(self, *, verified_fields: dict[str, str], fallback: str) -> str: ...


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
        amount_safe_to_pay, profile.home_currency, profile.current_available_balance,
        profile.minimum_balance_to_keep, recommendation, earliest_full_payment_date,
        confirmed_income, recurring_expenses,
    )


def generate_explanation(facts: ExplanationFacts, rephraser: OptionalExplanationRephraser | None = None) -> str:
    """Produce a concise verified explanation, falling back whenever rephrasing is unsafe."""
    fallback = deterministic_explanation(facts)
    if rephraser is None:
        return fallback
    candidate = rephraser.generate(verified_fields=facts.closed_fields(), fallback=fallback)
    return candidate if validate_explanation(candidate, facts) else fallback


def deterministic_explanation(facts: ExplanationFacts) -> str:
    currency = facts.home_currency
    safe = _money(facts.amount_safe_to_pay)
    floor = _money(facts.minimum_balance_to_keep)
    balance = _money(facts.current_available_balance)
    recommendation = facts.recommendation
    if recommendation.recommended_payment_method == "not_recommended":
        text = f"Safe to pay now: {currency} {safe}. Selected method: not_recommended; no safe eligible payment plan was found while preserving the {currency} {floor} minimum balance."
    else:
        text = (
            f"Safe to pay now: {currency} {safe}. Selected method: {recommendation.recommended_payment_method}; "
            f"the deterministic 90-day forecast preserves the {currency} {floor} minimum balance from a current available balance of {currency} {balance}."
        )
    if facts.earliest_full_payment_date is not None and facts.earliest_full_payment_date != _plan_first_date(recommendation.payment_plan):
        text += f" Earliest safe full-payment date: {facts.earliest_full_payment_date.isoformat()}."
    elif recommendation.recommended_payment_method == "wait" and facts.earliest_full_payment_date is not None:
        text += f" Earliest safe full-payment date: {facts.earliest_full_payment_date.isoformat()}."
    if recommendation.spending_changes_needed != "none":
        text += f" Required spending changes: {recommendation.spending_changes_needed}."
    if facts.confirmed_income:
        income = facts.confirmed_income[0]
        text += f" Confirmed salary of {currency} {_money(income.amount_in_home_currency or Decimal('0'))} is included on {income.effective_date.isoformat()}."
    if facts.recurring_expenses:
        expense = facts.recurring_expenses[0]
        text += f" Recurring expense of {currency} {_money(expense.amount_in_home_currency or Decimal('0'))} is included."
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
