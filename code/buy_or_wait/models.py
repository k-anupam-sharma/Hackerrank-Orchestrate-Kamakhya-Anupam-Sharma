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
