"""Normalize raw financial events into an auditable, currency-aware user ledger."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Iterable, TextIO

from .loaders import DatasetIndex
from .models import FinancialEvent, NormalizedEvent, UserProfile


class CurrencyConversionError(ValueError):
    """A required fixed exchange rate is absent from the provided dataset."""


def convert_to_home_currency(
    amount: Decimal,
    from_currency: str,
    home_currency: str,
    settlement_date: date,
    rates: DatasetIndex,
) -> Decimal:
    """Convert using the exact supplied directed settlement-date rate."""
    if from_currency == home_currency:
        return amount
    rate = rates.exchange_rates_by_key.get((settlement_date, from_currency, home_currency))
    if rate is None:
        raise CurrencyConversionError(
            f"No rate for {from_currency}->{home_currency} on {settlement_date.isoformat()}"
        )
    return amount * rate.rate


def _event_kind(event: FinancialEvent) -> str:
    if event.event_type == "income":
        return "income"
    if event.event_type == "refund":
        return "refund"
    if event.event_type == "debt_payment":
        return "debt_payment"
    if event.event_type == "subscription":
        return "subscription"
    if event.event_type == "investment_purchase":
        return "investment_purchase"
    if event.event_type == "investment_sale":
        return "investment_sale"
    if event.event_type == "investment_valuation":
        return "investment_valuation"
    if event.category == "family_support":
        return "transfer"
    if event.event_type == "expense":
        return "expense"
    return "other"


def _is_linked_duplicate(event: FinancialEvent, by_id: dict[str, FinancialEvent]) -> bool:
    """Mark only explicit pending duplicates of the same settled cash record."""
    if event.status != "pending" or event.linked_event_id is None:
        return False
    earlier = by_id[event.linked_event_id]
    return (
        earlier.status == "settled"
        and earlier.direction == event.direction
        and earlier.amount == event.amount
        and earlier.currency == event.currency
        and earlier.category == event.category
    )


def _lifecycle_role(event: FinancialEvent, by_id: dict[str, FinancialEvent]) -> str:
    if _is_linked_duplicate(event, by_id):
        return "duplicate"
    if event.linked_event_id is None:
        return "standalone"
    prior = by_id[event.linked_event_id]
    if prior.status == "cancelled" and event.status in {"settled", "pending", "scheduled"}:
        return "replacement"
    if event.event_type == "refund":
        return "refund_of_linked_event"
    if event.event_type == "investment_valuation":
        return "valuation_of_linked_investment"
    if event.event_type == "investment_sale":
        return "sale_of_linked_investment"
    return "linked_follow_up"


def _cash_treatment(event: FinancialEvent, lifecycle_role: str) -> str:
    if lifecycle_role == "duplicate":
        return "excluded_duplicate"
    if event.status == "cancelled":
        return "excluded_cancelled"
    if event.status == "failed":
        return "excluded_failed"
    if event.status == "unrealized" or event.direction == "non_cash":
        return "excluded_non_cash_or_unrealized"
    if event.status == "pending":
        return "reserve_pending_debit" if event.direction == "debit" else "exclude_pending_credit"
    if event.status == "scheduled":
        return "scheduled_cash"
    if event.status == "settled":
        return "settled_cash"
    return "excluded_unknown_status"


def _recurring_event_ids(events: Iterable[FinancialEvent]) -> set[str]:
    """Infer recurrence only from regular observations of one financial stream.

    ``category`` alone is not an identity: a user's groceries, taxis, and
    restaurant visits can share a category while being unrelated one-off
    purchases.  Historical expense/income streams therefore also require the
    source description to match.  Subscription and debt-payment categories are
    contractual streams in the supplied data, so their category remains the
    stable identity even when a provider's wording changes slightly.

    Payroll-like income may vary while remaining a regular salary stream; its
    latest observed amount is used conservatively. Variable platform/gig
    payouts are historical observations, not confirmed recurring income, and
    must not be projected as guaranteed cash. A stream is also terminated by a
    later explicitly final/last payment.
    """
    events = tuple(events)
    groups: defaultdict[tuple[str, ...], list[FinancialEvent]] = defaultdict(list)
    for event in events:
        if event.status not in {"settled", "pending", "scheduled"}:
            continue
        if event.event_type not in {"income", "expense", "subscription", "debt_payment"}:
            continue
        if event.category == "windfall":
            continue
        key: tuple[str, ...] = (event.event_type, event.category, event.direction, event.currency)
        # A description identifies an ordinary expense/income stream. This
        # applies equally to flexible expenses: changing dining or transport
        # descriptions are variable spending, not a fixed future charge.
        if event.event_type not in {"subscription", "debt_payment"}:
            key += (event.description,)
        groups[key].append(event)
    recurring: set[str] = set()
    for values in groups.values():
        ordered = sorted(values, key=lambda item: item.settlement_date or item.event_date)
        if len(ordered) < 3:
            continue
        dates = [item.settlement_date or item.event_date for item in ordered]
        gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
        # Monthly, weekly, and biweekly patterns in the provided history are 7-35 days.
        if not (len(gaps) >= 2 and 7 <= median(gaps) <= 35 and all(1 <= gap <= 45 for gap in gaps)):
            continue
        if values[0].event_type == "income":
            amounts = {item.amount for item in ordered}
            payroll_like = any(
                token in values[0].description.lower()
                for token in ("payroll", "salary", "employer", "household income", "wage")
            )
            # Missing amounts cannot support a deterministic forecast. A
            # payroll-like stream may vary; other changing income is not
            # guaranteed recurring cash. Confirmed future rows are still
            # handled directly by the forecast engine.
            if None in amounts or (len(amounts) != 1 and not payroll_like):
                continue
            terminal_words = {"final", "last", "termination", "terminated"}
            terminal_dates = [
                item.settlement_date or item.event_date
                for item in events
                if item.event_type == "income"
                and item.category == values[0].category
                and item.direction == values[0].direction
                and item.currency == values[0].currency
                and any(word in item.description.lower().split() for word in terminal_words)
            ]
            latest_date = ordered[-1].settlement_date or ordered[-1].event_date
            if terminal_dates and max(terminal_dates) >= latest_date:
                continue
        recurring.update(item.event_id for item in ordered)
    return recurring


def normalize_user_events(index: DatasetIndex, user_id: str) -> tuple[NormalizedEvent, ...]:
    """Return a chronologically ordered, auditable normalized ledger for one user."""
    profile = index.profiles_by_user_id[user_id]
    raw_events = index.events_by_user_id.get(user_id, ())
    raw_by_id = {event.event_id: event for event in raw_events}
    recurring_ids = _recurring_event_ids(raw_events)
    normalized: list[NormalizedEvent] = []
    for event in raw_events:
        # A scheduled record names the planned payment/payday in event_date;
        # settlement_date is the later processing/settlement metadata. Pending
        # debits continue to reserve cash on settlement_date, while settled
        # cash uses its settlement date.
        effective_date = (
            event.event_date
            if event.status == "scheduled"
            else event.settlement_date or event.event_date
        )
        conversion_date = event.settlement_date
        home_amount: Decimal | None = None
        conversion_status = "missing_amount"
        if event.amount is not None:
            if event.currency == profile.home_currency:
                home_amount = event.amount
                conversion_status = "identity"
            elif conversion_date is None:
                conversion_status = "missing_settlement_date"
            else:
                try:
                    home_amount = convert_to_home_currency(
                        event.amount, event.currency, profile.home_currency, conversion_date, index
                    )
                    conversion_status = "converted"
                except CurrencyConversionError:
                    conversion_status = "missing_exchange_rate"
        lifecycle_role = _lifecycle_role(event, raw_by_id)
        normalized.append(NormalizedEvent(
            event_id=event.event_id,
            user_id=event.user_id,
            effective_date=effective_date,
            event_date=event.event_date,
            settlement_date=event.settlement_date,
            amount=event.amount,
            currency=event.currency,
            amount_in_home_currency=home_amount,
            home_currency=profile.home_currency,
            conversion_date=conversion_date,
            conversion_status=conversion_status,
            event_type=event.event_type,
            event_kind=_event_kind(event),
            category=event.category,
            direction=event.direction,
            status=event.status,
            linked_event_id=event.linked_event_id,
            lifecycle_role=lifecycle_role,
            cash_treatment=_cash_treatment(event, lifecycle_role),
            is_recurring=event.event_id in recurring_ids,
            is_flexible=event.flexibility != "fixed",
            flexibility=event.flexibility,
            minimum_allowed_amount=event.minimum_allowed_amount,
            source="financial_events.csv",
            description=event.description,
        ))
    return tuple(sorted(normalized, key=lambda item: (item.effective_date, item.event_id)))


def format_normalized_timeline(events: Iterable[NormalizedEvent]) -> str:
    """Return a human-readable timeline for diagnosis; it makes no financial decision."""
    lines = [
        "date       event_id     kind/status                 amount -> home       flags",
        "---------- ------------ --------------------------- -------------------- ----------------",
    ]
    for event in sorted(events, key=lambda item: (item.effective_date, item.event_id)):
        raw_amount = "missing" if event.amount is None else f"{event.amount} {event.currency}"
        home_amount = "unavailable" if event.amount_in_home_currency is None else f"{event.amount_in_home_currency} {event.home_currency}"
        flags = ",".join(filter(None, [
            "recurring" if event.is_recurring else "",
            "flexible" if event.is_flexible else "",
            event.lifecycle_role if event.lifecycle_role != "standalone" else "",
            event.cash_treatment,
        ]))
        lines.append(
            f"{event.effective_date.isoformat()} {event.event_id:<12} "
            f"{event.event_kind}/{event.status:<18} {raw_amount:<20} {home_amount:<20} {flags}"
        )
    return "\n".join(lines)


def print_normalized_timeline(events: Iterable[NormalizedEvent], file: TextIO | None = None) -> None:
    """Print the debug timeline; `file` supports tests and caller-owned streams."""
    print(format_normalized_timeline(events), file=file)
