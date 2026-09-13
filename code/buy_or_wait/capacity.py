"""Deterministic financial-capacity calculations built on the 90-day simulator."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from .forecast import calculate_baseline_forecast, forecast_balance, get_minimum_projected_balance, is_plan_safe
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
    """Return the maximum safe request-date payment before optional changes.

    A one-time request-date payment is an additive ``-P`` to every daily
    closing balance in the fixed baseline forecast.  Consequently the minimum
    after payment is ``baseline_minimum - P`` and the capacity is the amount
    above the required floor.  The result is quantized down to the configured
    monetary unit and capped at the request amount.  This is mathematically
    equivalent to the former binary search, but computes the baseline once and
    makes the invariant explicit.
    """
    if requested_amount < Decimal("0"):
        raise ValueError("requested_amount cannot be negative")
    if money_quantum <= Decimal("0"):
        raise ValueError("money_quantum must be positive")
    baseline = calculate_baseline_forecast(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        normalized_events=normalized_events,
        request_date=request_date,
        horizon_days=horizon_days,
    )
    available = get_minimum_projected_balance(baseline) - minimum_balance_to_keep
    if available <= Decimal("0"):
        return Decimal("0")
    capacity = min(requested_amount, available)
    return Decimal(_units(capacity, money_quantum)) * money_quantum


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
