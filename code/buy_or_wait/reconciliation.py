"""Apply validated evidence facts through deterministic conflict rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from .models import EvidenceFact, NormalizedEvent
from .normalization import CurrencyConversionError, convert_to_home_currency


def reconcile_evidence_facts(index, user_id: str, events: Sequence[NormalizedEvent], facts: Sequence[EvidenceFact]) -> tuple[NormalizedEvent, ...]:
    """Return evidence-amended records without inventing a new event or payment option.

    Conflict order is explicit: terminal cancellation/settlement/amendment facts;
    newest record per source; settled records over estimates/forecasts; then the
    financially safer remaining amount/date. Facts never create a new event.
    """
    by_event: dict[str, list[EvidenceFact]] = {}
    for fact in facts:
        if fact.user_id == user_id and fact.related_event_id is not None:
            by_event.setdefault(fact.related_event_id, []).append(fact)
    reconciled: list[NormalizedEvent] = []
    for event in events:
        related = by_event.get(event.event_id, ())
        if not related:
            reconciled.append(event)
            continue
        latest = _latest_per_source(related)
        if any(fact.fact_type == "event_cancelled" for fact in latest):
            reconciled.append(replace(event, status="cancelled", cash_treatment="excluded_cancelled", source="financial_events.csv+evidence"))
            continue
        current = event
        if any(fact.fact_type == "event_settled" for fact in latest):
            current = replace(current, status="settled", cash_treatment="settled_cash", source="financial_events.csv+evidence")
        # Existing settled structured records remain preferred to an estimate or
        # forecast. An explicit amount amendment is a higher-priority fact.
        if current.status in {"unrealized", "forecast", "estimated"} and event.status == "settled":
            current = event
        amendments = [fact for fact in latest if fact.fact_type in {"event_amount", "event_amount_amended", "income_confirmed"} and fact.amount is not None]
        if amendments:
            amendment = _safer_amount_fact(amendments, current.direction)
            currency = amendment.currency or current.currency
            settlement = current.settlement_date or current.effective_date
            home_amount, conversion_status = _home_amount(index, amendment.amount, currency, current.home_currency, settlement)
            current = replace(
                current, amount=amendment.amount, currency=currency, amount_in_home_currency=home_amount,
                conversion_date=settlement, conversion_status=conversion_status,
                cash_treatment="scheduled_cash" if amendment.fact_type == "income_confirmed" else current.cash_treatment,
                source="financial_events.csv+evidence",
            )
        delays = [fact for fact in latest if fact.fact_type == "payment_delayed" and fact.effective_date is not None]
        if delays:
            delay = _safer_date_fact(delays, current.direction)
            current = replace(current, effective_date=delay.effective_date, settlement_date=delay.effective_date, source="financial_events.csv+evidence")
        reconciled.append(current)
    return tuple(sorted(reconciled, key=lambda event: (event.effective_date, event.event_id)))


def _fact_order(fact: EvidenceFact) -> tuple[datetime, str]:
    return (fact.source_timestamp or datetime.min.replace(tzinfo=timezone.utc), fact.source_id)


def _latest_per_source(facts: Sequence[EvidenceFact]) -> tuple[EvidenceFact, ...]:
    latest: dict[str, EvidenceFact] = {}
    for fact in facts:
        origin = fact.source_origin or fact.source_kind or fact.source_id
        prior = latest.get(origin)
        if prior is None or _fact_order(fact) > _fact_order(prior):
            latest[origin] = fact
    return tuple(latest.values())


def _safer_amount_fact(facts: Sequence[EvidenceFact], direction: str) -> EvidenceFact:
    """For unresolved claims, reserve more for debits and count less for credits."""
    assert all(fact.amount is not None for fact in facts)
    key = lambda fact: (fact.amount, _fact_order(fact))
    return max(facts, key=key) if direction == "debit" else min(facts, key=key)


def _safer_date_fact(facts: Sequence[EvidenceFact], direction: str) -> EvidenceFact:
    """For unresolved claims, debit earlier and credit later."""
    assert all(fact.effective_date is not None for fact in facts)
    key = lambda fact: (fact.effective_date, _fact_order(fact))
    return min(facts, key=key) if direction == "debit" else max(facts, key=key)


def _home_amount(index, amount: Decimal, currency: str, home_currency: str, settlement_date) -> tuple[Decimal | None, str]:
    try:
        return convert_to_home_currency(amount, currency, home_currency, settlement_date, index), "identity" if currency == home_currency else "converted"
    except CurrencyConversionError:
        return None, "missing_exchange_rate"
