"""Deterministic, bounded spending-change candidates for a proposed payment plan."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import combinations
from typing import Sequence

from .forecast import forecast_balance, is_plan_safe
from .models import (
    NormalizedEvent, ScheduledPayment, SpendingChange, SpendingChangeCandidate, UserProfile,
)


def _stream_key(event: NormalizedEvent) -> tuple[str, str, str, str]:
    return (event.event_type, event.category, event.direction, event.currency)


class SpendingChangeEngine:
    """Enumerate up to three permitted recurring-expense interventions.

    A reduction is only emitted at the source-provided minimum amount; arbitrary
    reduction amounts would be unsupported financial facts.  One current source
    event represents each recurring stream, preventing duplicate historic rows
    from being changed independently.
    """

    max_changes: int = 3

    def eligible_events(
        self,
        *,
        profile: UserProfile,
        normalized_events: Sequence[NormalizedEvent],
        request_date: date,
    ) -> tuple[NormalizedEvent, ...]:
        """Return one eligible, source-backed event per recurring expense stream."""
        latest_by_stream: dict[tuple[str, str, str, str], NormalizedEvent] = {}
        for event in normalized_events:
            if not self._is_eligible_expense(event, profile):
                continue
            key = _stream_key(event)
            current = latest_by_stream.get(key)
            # Prefer the latest known event on/before the request date. If a stream
            # has only future observations, retain its earliest future record.
            if current is None or self._is_better_source(event, current, request_date):
                latest_by_stream[key] = event
        return tuple(sorted(latest_by_stream.values(), key=lambda event: event.event_id))

    def generate_safe_candidates(
        self,
        *,
        profile: UserProfile,
        normalized_events: Sequence[NormalizedEvent],
        request_date: date,
        proposed_payments: Sequence[ScheduledPayment],
        horizon_days: int = 90,
        candidate_actions: Sequence[SpendingChange] | None = None,
    ) -> tuple[SpendingChangeCandidate, ...]:
        """Return safe one-, two-, and three-change interventions in rank order."""
        actions = tuple(candidate_actions) if candidate_actions is not None else self.candidate_actions(
            profile=profile, normalized_events=normalized_events, request_date=request_date,
        )
        candidates: list[SpendingChangeCandidate] = []
        for count in range(1, min(self.max_changes, len(actions)) + 1):
            for change_set in combinations(actions, count):
                if self.validate_changes(
                    changes=change_set, profile=profile, normalized_events=normalized_events,
                    request_date=request_date,
                ):
                    continue
                forecast = forecast_balance(
                    starting_balance=profile.current_available_balance,
                    minimum_balance_to_keep=profile.minimum_balance_to_keep,
                    normalized_events=normalized_events,
                    request_date=request_date,
                    spending_changes=change_set,
                    proposed_payments=proposed_payments,
                    horizon_days=horizon_days,
                )
                if is_plan_safe(forecast):
                    candidates.append(SpendingChangeCandidate(tuple(change_set), forecast))
        return tuple(sorted(candidates, key=lambda candidate: self._rank_key(candidate, normalized_events)))

    def candidate_actions(
        self, *, profile: UserProfile, normalized_events: Sequence[NormalizedEvent], request_date: date,
    ) -> tuple[SpendingChange, ...]:
        """Cacheable, plan-independent action universe for one user/request date."""
        eligible = self.eligible_events(
            profile=profile, normalized_events=normalized_events, request_date=request_date,
        )
        return tuple(action for event in eligible for action in self._actions_for(event, profile, request_date))

    def validate_changes(
        self,
        *,
        changes: Sequence[SpendingChange],
        profile: UserProfile,
        normalized_events: Sequence[NormalizedEvent],
        request_date: date,
    ) -> tuple[str, ...]:
        """Return explicit rule violations; an empty tuple means changes are allowed."""
        errors: list[str] = []
        if len(changes) > self.max_changes:
            errors.append("too_many_spending_changes")
        by_id = {event.event_id: event for event in normalized_events}
        seen_ids: set[str] = set()
        seen_streams: set[tuple[str, str, str, str]] = set()
        for change in changes:
            event = by_id.get(change.event_id)
            if change.event_id in seen_ids:
                errors.append("same_event_changed_twice")
            seen_ids.add(change.event_id)
            if event is None:
                errors.append("spending_change_event_not_found")
                continue
            stream = _stream_key(event)
            if stream in seen_streams:
                errors.append("same_recurring_stream_changed_twice")
            seen_streams.add(stream)
            if not self._is_eligible_expense(event, profile):
                errors.append("spending_change_event_not_eligible")
            if change.effective_date < request_date:
                errors.append("spending_change_cannot_be_retroactive")
            if change.action == "stop":
                if event.category not in profile.stoppable_categories or event.flexibility not in {"stoppable", "reducible_or_stoppable"}:
                    errors.append("stop_not_permitted_for_event")
            elif change.action == "reduce_to":
                if event.category not in profile.reducible_categories or event.flexibility not in {"reducible", "reducible_or_stoppable"}:
                    errors.append("reduction_not_permitted_for_event")
                if change.new_amount is None or change.new_amount < Decimal("0"):
                    errors.append("reduction_amount_must_be_non_negative")
                elif event.minimum_allowed_amount is None or change.new_amount != event.minimum_allowed_amount:
                    errors.append("reduction_must_use_source_minimum")
                elif event.amount_in_home_currency is None or change.new_amount >= event.amount_in_home_currency:
                    errors.append("reduction_must_lower_expense")
            else:
                errors.append("unsupported_spending_change_action")
        return tuple(errors)

    @staticmethod
    def _is_eligible_expense(event: NormalizedEvent, profile: UserProfile) -> bool:
        return (
            event.is_recurring
            and event.is_flexible
            and event.direction == "debit"
            and event.event_type in {"expense", "subscription"}
            and event.amount_in_home_currency is not None
            and event.amount_in_home_currency > Decimal("0")
            and event.category not in profile.protected_categories
            and event.cash_treatment in {"settled_cash", "reserve_pending_debit", "scheduled_cash"}
        )

    @staticmethod
    def _is_better_source(candidate: NormalizedEvent, current: NormalizedEvent, request_date: date) -> bool:
        candidate_past = candidate.effective_date <= request_date
        current_past = current.effective_date <= request_date
        if candidate_past != current_past:
            return candidate_past
        if candidate_past:
            return candidate.effective_date > current.effective_date
        return candidate.effective_date < current.effective_date

    @staticmethod
    def _actions_for(event: NormalizedEvent, profile: UserProfile, request_date: date) -> tuple[SpendingChange, ...]:
        actions: list[SpendingChange] = []
        if event.category in profile.stoppable_categories and event.flexibility in {"stoppable", "reducible_or_stoppable"}:
            actions.append(SpendingChange(event.event_id, "stop", request_date))
        if (
            event.category in profile.reducible_categories
            and event.flexibility in {"reducible", "reducible_or_stoppable"}
            and event.minimum_allowed_amount is not None
            and event.amount_in_home_currency is not None
            and Decimal("0") <= event.minimum_allowed_amount < event.amount_in_home_currency
        ):
            actions.append(SpendingChange(event.event_id, "reduce_to", request_date, event.minimum_allowed_amount))
        return tuple(actions)

    @staticmethod
    def _rank_key(candidate: SpendingChangeCandidate, events: Sequence[NormalizedEvent]) -> tuple[object, ...]:
        by_id = {event.event_id: event for event in events}
        savings = Decimal("0")
        labels: list[str] = []
        for change in candidate.changes:
            event = by_id[change.event_id]
            original = event.amount_in_home_currency or Decimal("0")
            replacement = Decimal("0") if change.action == "stop" else change.new_amount or Decimal("0")
            savings += original - replacement
            labels.append(f"{change.action}:{change.event_id}")
        return (len(candidate.changes), savings, tuple(labels))
