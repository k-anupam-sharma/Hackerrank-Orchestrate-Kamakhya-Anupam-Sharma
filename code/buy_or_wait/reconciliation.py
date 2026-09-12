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

    Per the challenge order, an explicit cancellation wins first; otherwise the
    newest applicable amendment/delay from the same source ordering is used.
    Facts with no linked source event remain provenance for explanations only.
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
        if any(fact.fact_type == "event_cancelled" for fact in related):
            reconciled.append(replace(event, status="cancelled", cash_treatment="excluded_cancelled", source="financial_events.csv+evidence"))
            continue
        current = event
        amendments = [fact for fact in related if fact.fact_type in {"event_amount", "event_amount_amended", "income_confirmed"} and fact.amount is not None]
        if amendments:
            amendment = max(amendments, key=_fact_order)
            currency = amendment.currency or current.currency
            settlement = current.settlement_date or current.effective_date
            home_amount, conversion_status = _home_amount(index, amendment.amount, currency, current.home_currency, settlement)
            current = replace(
                current, amount=amendment.amount, currency=currency, amount_in_home_currency=home_amount,
                conversion_date=settlement, conversion_status=conversion_status,
                cash_treatment="scheduled_cash" if amendment.fact_type == "income_confirmed" else current.cash_treatment,
                source="financial_events.csv+evidence",
            )
        delays = [fact for fact in related if fact.fact_type == "payment_delayed" and fact.effective_date is not None]
        if delays:
            delay = max(delays, key=_fact_order)
            current = replace(current, effective_date=delay.effective_date, settlement_date=delay.effective_date, source="financial_events.csv+evidence")
        reconciled.append(current)
    return tuple(sorted(reconciled, key=lambda event: (event.effective_date, event.event_id)))


def _fact_order(fact: EvidenceFact) -> tuple[datetime, str]:
    return (fact.source_timestamp or datetime.min.replace(tzinfo=timezone.utc), fact.source_id)


def _home_amount(index, amount: Decimal, currency: str, home_currency: str, settlement_date) -> tuple[Decimal | None, str]:
    try:
        return convert_to_home_currency(amount, currency, home_currency, settlement_date, index), "identity" if currency == home_currency else "converted"
    except CurrencyConversionError:
        return None, "missing_exchange_rate"
