"""Deterministic 90-day balance simulation over normalized financial events."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable, Sequence

from .models import BalanceForecast, ForecastDay, NormalizedEvent, ScheduledPayment, SpendingChange


def _included_cash_delta(event: NormalizedEvent) -> Decimal | None:
    """Return a signed home-currency cash delta only for challenge-eligible events."""
    if event.amount_in_home_currency is None:
        return None
    if event.cash_treatment == "settled_cash":
        pass
    elif event.cash_treatment == "reserve_pending_debit":
        pass
    elif event.cash_treatment == "scheduled_cash":
        # Structured scheduled debits are commitments; scheduled salary is confirmed income.
        if event.direction == "credit" and not (event.event_type == "income" and event.category == "salary"):
            return None
    else:
        return None
    return event.amount_in_home_currency if event.direction == "credit" else -event.amount_in_home_currency


def _stream_key(event: NormalizedEvent) -> tuple[str, str, str, str]:
    # Normalization decides which records are recurring.  Once a source record
    # is marked recurring, the category/direction/currency identifies the cash
    # stream for forecast expansion and spending changes.
    return (event.event_type, event.category, event.direction, event.currency)


def _changes_by_stream(
    events: Sequence[NormalizedEvent], changes: Sequence[SpendingChange],
) -> dict[tuple[str, str, str, str], SpendingChange]:
    event_by_id = {event.event_id: event for event in events}
    result: dict[tuple[str, str, str, str], SpendingChange] = {}
    for change in changes:
        target = event_by_id.get(change.event_id)
        if target is None or not target.is_recurring:
            raise ValueError(f"Spending change must target a recurring event: {change.event_id}")
        if change.action not in {"stop", "reduce_to"}:
            raise ValueError(f"Unsupported spending-change action: {change.action}")
        if change.action == "reduce_to" and (change.new_amount is None or change.new_amount < Decimal("0")):
            raise ValueError("reduce_to requires a non-negative new_amount")
        key = _stream_key(target)
        if key in result:
            raise ValueError("Only one spending change per recurring stream is supported")
        result[key] = change
    return result


def _apply_change(
    event: NormalizedEvent, delta: Decimal, change: SpendingChange | None,
) -> Decimal | None:
    if change is None or event.effective_date < change.effective_date:
        return delta
    if change.action == "stop":
        return None
    assert change.new_amount is not None
    return change.new_amount if event.direction == "credit" else -change.new_amount


def _add_month(value: date) -> date:
    """Advance one calendar month while preserving a contractual day-of-month."""
    month = value.month + 1
    year = value.year
    if month == 13:
        year += 1
        month = 1
    # Avoid a dependency on calendar: clamp to the last day of the target
    # month by trying the requested day and moving backward when necessary.
    day = value.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def _recurring_projections(
    events: Sequence[NormalizedEvent], request_date: date, horizon_end: date,
    changes_by_stream: dict[tuple[str, str, str, str], SpendingChange],
) -> list[tuple[date, Decimal, str]]:
    """Expand only source-backed recurring streams with at least two dated observations."""
    by_key: defaultdict[tuple[str, str, str, str], list[NormalizedEvent]] = defaultdict(list)
    for event in events:
        if event.is_recurring and _included_cash_delta(event) is not None:
            by_key[_stream_key(event)].append(event)
    projections: list[tuple[date, Decimal, str]] = []
    for group in by_key.values():
        ordered = sorted(group, key=lambda item: item.effective_date)
        if len(ordered) < 2:
            continue
        gaps = [
            (later.effective_date - earlier.effective_date).days
            for earlier, later in zip(ordered, ordered[1:])
            if (later.effective_date - earlier.effective_date).days > 0
        ]
        if not gaps:
            continue
        interval = int(median(gaps))
        if interval <= 0:
            continue
        dates = [event.effective_date for event in ordered]
        calendar_monthly = 28 <= interval <= 31 and len({item.day for item in dates}) == 1
        observed_dates = {event.effective_date for event in ordered}
        anchor_candidates = [event for event in ordered if event.effective_date <= request_date]
        if not anchor_candidates:
            continue
        anchor = anchor_candidates[-1]
        next_date = _add_month(anchor.effective_date) if calendar_monthly else anchor.effective_date + timedelta(days=interval)
        latest_delta = _included_cash_delta(anchor)
        assert latest_delta is not None
        while next_date <= horizon_end:
            if next_date not in observed_dates:
                projected = _apply_change(anchor, latest_delta, changes_by_stream.get(_stream_key(anchor)))
                # Apply the change at the projected occurrence date, not the anchor's historic date.
                if projected is not None:
                    change = changes_by_stream.get(_stream_key(anchor))
                    if change is not None and next_date >= change.effective_date and change.action == "reduce_to":
                        projected = change.new_amount if anchor.direction == "credit" else -change.new_amount
                    if not (change is not None and next_date >= change.effective_date and change.action == "stop"):
                        suffix = ":reduced" if change is not None and next_date >= change.effective_date else ""
                        projections.append((next_date, projected, f"recurrence:{anchor.event_id}{suffix}"))
            next_date = _add_month(next_date) if calendar_monthly else next_date + timedelta(days=interval)
    return projections


def forecast_balance(
    *,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    normalized_events: Sequence[NormalizedEvent],
    request_date: date,
    spending_changes: Sequence[SpendingChange] = (),
    proposed_payments: Sequence[ScheduledPayment] = (),
    horizon_days: int = 90,
) -> BalanceForecast:
    """Simulate one opening day plus the next `horizon_days - 1` calendar days."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    horizon_end = request_date + timedelta(days=horizon_days - 1)
    deltas: defaultdict[date, list[tuple[Decimal, str, str]]] = defaultdict(list)
    ignored: list[str] = []
    changes_by_stream = _changes_by_stream(normalized_events, spending_changes)
    for event in normalized_events:
        if not request_date <= event.effective_date <= horizon_end:
            continue
        delta = _included_cash_delta(event)
        if delta is None:
            ignored.append(event.event_id)
            continue
        if event.is_recurring:
            delta = _apply_change(event, delta, changes_by_stream.get(_stream_key(event)))
            if delta is None:
                ignored.append(event.event_id)
                continue
        deltas[event.effective_date].append((delta, event.event_id, "event"))
    for forecast_date, delta, source_id in _recurring_projections(
        normalized_events, request_date, horizon_end, changes_by_stream
    ):
        deltas[forecast_date].append((delta, source_id, "event"))
    for payment in proposed_payments:
        if payment.amount < Decimal("0"):
            raise ValueError("Proposed payment amount cannot be negative")
        if request_date <= payment.payment_date <= horizon_end:
            deltas[payment.payment_date].append((-payment.amount, payment.source_id, "payment"))
    days: list[ForecastDay] = []
    balance = starting_balance
    for offset in range(horizon_days):
        current = request_date + timedelta(days=offset)
        entries = deltas[current]
        event_delta = sum((value for value, _, kind in entries if kind == "event"), Decimal("0"))
        payment_delta = sum((value for value, _, kind in entries if kind == "payment"), Decimal("0"))
        closing = balance + event_delta + payment_delta
        days.append(ForecastDay(
            forecast_date=current,
            opening_balance=balance,
            event_delta=event_delta,
            payment_delta=payment_delta,
            closing_balance=closing,
            source_ids=tuple(source_id for _, source_id, _ in entries),
        ))
        balance = closing
    return BalanceForecast(
        request_date=request_date,
        horizon_end=horizon_end,
        minimum_balance_to_keep=minimum_balance_to_keep,
        days=tuple(days),
        ignored_event_ids=tuple(ignored),
    )


def get_minimum_projected_balance(forecast: BalanceForecast) -> Decimal:
    """Return the lowest daily closing balance from a completed forecast."""
    return min(day.closing_balance for day in forecast.days)


def is_plan_safe(forecast: BalanceForecast) -> bool:
    """A plan is safe exactly when every simulated closing balance meets the floor."""
    return get_minimum_projected_balance(forecast) >= forecast.minimum_balance_to_keep
