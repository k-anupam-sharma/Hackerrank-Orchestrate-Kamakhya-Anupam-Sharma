"""Canonical immutable records used by the data layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


Money = Decimal


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    home_currency: str
    current_available_balance: Money
    minimum_balance_to_keep: Money
    financial_priorities: tuple[str, ...]
    protected_categories: tuple[str, ...]
    reducible_categories: tuple[str, ...]
    stoppable_categories: tuple[str, ...]
    payment_methods: tuple[str, ...]
    max_installment_months: int | None


@dataclass(frozen=True)
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Money | None
    currency: str
    event_date: date
    settlement_date: date | None
    status: str
    linked_event_id: str | None
    flexibility: str
    minimum_allowed_amount: Money | None


@dataclass(frozen=True)
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Money
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str


@dataclass(frozen=True)
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: Money
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: Money
    total_payable_amount: Money


@dataclass(frozen=True)
class Message:
    message_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    sent_at: datetime
    source_type: str
    message_text: str


@dataclass(frozen=True)
class ImageReference:
    image_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    path: Path


@dataclass(frozen=True)
class ExchangeRate:
    rate_date: date
    from_currency: str
    to_currency: str
    rate: Money


@dataclass(frozen=True)
class OutputTemplateRow:
    request_id: str


@dataclass(frozen=True)
class NormalizedEvent:
    """A source event annotated for later forecasting, without changing source facts."""

    event_id: str
    user_id: str
    effective_date: date
    event_date: date
    settlement_date: date | None
    amount: Money | None
    currency: str
    amount_in_home_currency: Money | None
    home_currency: str
    conversion_date: date | None
    conversion_status: str
    event_type: str
    event_kind: str
    category: str
    direction: str
    status: str
    linked_event_id: str | None
    lifecycle_role: str
    cash_treatment: str
    is_recurring: bool
    is_flexible: bool
    flexibility: str
    minimum_allowed_amount: Money | None
    source: str
    description: str


@dataclass(frozen=True)
class EvidenceFact:
    """A bounded claim extracted from untrusted message or image content."""

    fact_type: str
    user_id: str
    source_id: str
    source_kind: str
    source_timestamp: datetime | None
    related_event_id: str | None
    related_request_id: str | None
    amount: Money | None
    currency: str | None
    effective_date: date | None
    confidence: Decimal
    rationale: str


@dataclass(frozen=True)
class EvidenceCandidate:
    """Untrusted adapter output, validated before becoming an EvidenceFact."""

    fact_type: str
    related_event_id: str | None = None
    amount: Money | None = None
    currency: str | None = None
    effective_date: date | None = None
    confidence: Decimal = Decimal("0")
    rationale: str = ""


@dataclass(frozen=True)
class ScheduledPayment:
    payment_date: date
    amount: Money
    source_id: str = "proposed_payment"


@dataclass(frozen=True)
class SpendingChange:
    """A future-only stop/reduction applied to a recurring source event."""

    event_id: str
    action: str
    effective_date: date
    new_amount: Money | None = None


@dataclass(frozen=True)
class ForecastDay:
    forecast_date: date
    opening_balance: Money
    event_delta: Money
    payment_delta: Money
    closing_balance: Money
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class BalanceForecast:
    request_date: date
    horizon_end: date
    minimum_balance_to_keep: Money
    days: tuple[ForecastDay, ...]
    ignored_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class PaymentPlan:
    """A candidate request plan, before ranking or final decision selection."""

    method: str
    payments: tuple[ScheduledPayment, ...]
    total_paid: Money
    payment_option_id: str | None
    financing_fee: Money
    is_fallback: bool = False
    spending_changes: tuple[SpendingChange, ...] = ()


@dataclass(frozen=True)
class PlanValidationResult:
    is_valid: bool
    completes_by_deadline: bool
    errors: tuple[str, ...]
    forecast: BalanceForecast | None


@dataclass(frozen=True)
class Recommendation:
    """Output-ready deterministic fields for a selected payment plan."""

    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    spending_changes_needed: str


@dataclass(frozen=True)
class SpendingChangeCandidate:
    """A bounded, source-backed intervention that makes one payment schedule safe."""

    changes: tuple[SpendingChange, ...]
    forecast: BalanceForecast
