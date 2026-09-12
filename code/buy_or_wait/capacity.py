"""Deterministic financial-capacity calculations built on the 90-day simulator."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from .forecast import forecast_balance, is_plan_safe
from .models import NormalizedEvent, ScheduledPayment


DEFAULT_MONEY_QUANTUM = Decimal("0.01")


def _units(value: Decimal, quantum: Decimal) -> int:
    if quantum <= Decimal("0"):
        raise ValueError("money_quantum must be positive")
    return int(value // quantum)


def _is_single_payment_safe(
    *,
    amount: Decimal,
    payment_date: date,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    normalized_events: Sequence[NormalizedEvent],
    request_date: date,
    horizon_days: int,
) -> bool:
    forecast = forecast_balance(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        normalized_events=normalized_events,
        request_date=request_date,
        proposed_payments=(ScheduledPayment(payment_date, amount, "capacity_payment"),),
        horizon_days=horizon_days,
    )
    return is_plan_safe(forecast)


def calculate_amount_safe_to_pay(
    *,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    normalized_events: Sequence[NormalizedEvent],
    request_date: date,
    requested_amount: Decimal,
    horizon_days: int = 90,
    money_quantum: Decimal = DEFAULT_MONEY_QUANTUM,
) -> Decimal:
    """Return the maximum safe request-date payment before optional spending changes.

    The search operates in integer units of ``money_quantum`` so it is deterministic,
    monotonic, and never depends on floating-point rounding or an LLM.
    """
    if requested_amount < Decimal("0"):
        raise ValueError("requested_amount cannot be negative")
    maximum_units = _units(requested_amount, money_quantum)
    low, high, best = 0, maximum_units, 0
    while low <= high:
        middle = (low + high) // 2
        amount = Decimal(middle) * money_quantum
        if _is_single_payment_safe(
            amount=amount, payment_date=request_date, starting_balance=starting_balance,
            minimum_balance_to_keep=minimum_balance_to_keep, normalized_events=normalized_events,
            request_date=request_date, horizon_days=horizon_days,
        ):
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    return Decimal(best) * money_quantum


def find_earliest_safe_full_payment_date(
    *,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    normalized_events: Sequence[NormalizedEvent],
    request_date: date,
    requested_amount: Decimal,
    horizon_days: int = 90,
) -> date | None:
    """Return first safe full-payment date in forecast horizon, or None when absent."""
    if requested_amount < Decimal("0"):
        raise ValueError("requested_amount cannot be negative")
    for offset in range(horizon_days):
        candidate_date = request_date + timedelta(days=offset)
        if _is_single_payment_safe(
            amount=requested_amount, payment_date=candidate_date,
            starting_balance=starting_balance, minimum_balance_to_keep=minimum_balance_to_keep,
            normalized_events=normalized_events, request_date=request_date, horizon_days=horizon_days,
        ):
            return candidate_date
    return None
