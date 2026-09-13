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

    # A message may explicitly confirm a future salary without having a
    # one-to-one ``related_event_id`` (the source CSV deliberately allows this).
    # Keep the claim as a bounded, provenance-carrying normalized event rather
    # than dropping it or inventing an amount.  Dated confirmations become a
    # recurring salary anchor; undated payroll notices amend the latest
    # source-backed salary amount used for future projections.
    unlinked_income = _latest_unlinked_income_facts(facts, user_id)
    for fact in unlinked_income:
        if fact.amount is None:
            continue
        dated = fact.effective_date
        if dated is not None:
            amount_home, conversion_status = _home_amount(
                index, fact.amount, fact.currency or "", _home_currency_for_user(index, user_id), dated,
            )
            if amount_home is None:
                continue
            reconciled.append(NormalizedEvent(
                event_id=f"evidence_income:{fact.source_id}", user_id=user_id,
                effective_date=dated, event_date=dated, settlement_date=dated,
                amount=fact.amount, currency=fact.currency or _home_currency_for_user(index, user_id),
                amount_in_home_currency=amount_home, home_currency=_home_currency_for_user(index, user_id),
                conversion_date=dated, conversion_status=conversion_status,
                event_type="income", event_kind="income", category="salary", direction="credit",
                status="scheduled", linked_event_id=None, lifecycle_role="evidence_confirmed",
                cash_treatment="scheduled_cash", is_recurring="recurring" in fact.rationale, is_flexible=False,
                flexibility="fixed", minimum_allowed_amount=None, source=f"messages.csv:{fact.source_id}",
                description="Confirmed salary from unlinked message",
            ))
        else:
            _amend_latest_salary_amount(reconciled, index, user_id, fact)
    return tuple(sorted(reconciled, key=lambda event: (event.effective_date, event.event_id)))


def _latest_unlinked_income_facts(facts: Sequence[EvidenceFact], user_id: str) -> tuple[EvidenceFact, ...]:
    candidates = [fact for fact in facts if fact.user_id == user_id and fact.fact_type == "income_confirmed" and fact.related_event_id is None]
    latest: dict[str, EvidenceFact] = {}
    for fact in candidates:
        origin = fact.source_origin or fact.source_kind or fact.source_id
        prior = latest.get(origin)
        if prior is None or _fact_order(fact) > _fact_order(prior):
            latest[origin] = fact
    return tuple(latest.values())


def _home_currency_for_user(index, user_id: str) -> str:
    return index.profiles_by_user_id[user_id].home_currency


def _amend_latest_salary_amount(reconciled: list[NormalizedEvent], index, user_id: str, fact: EvidenceFact) -> None:
    targets = [
        event for event in reconciled
        if event.user_id == user_id and event.event_type == "income" and event.category == "salary"
        and event.direction == "credit" and event.is_recurring
    ]
    if not targets:
        return
    target = max(targets, key=lambda event: (event.effective_date, event.event_id))
    currency = fact.currency or target.currency
    settlement = target.settlement_date or target.effective_date
    home_amount, conversion_status = _home_amount(index, fact.amount, currency, target.home_currency, settlement) if fact.amount is not None else (None, "missing_amount")
    if home_amount is None:
        return
    replacement = replace(
        target, amount=fact.amount, currency=currency, amount_in_home_currency=home_amount,
        conversion_date=settlement, conversion_status=conversion_status,
        source=f"{target.source}+evidence:{fact.source_id}",
    )
    reconciled[reconciled.index(target)] = replacement


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
