from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from buy_or_wait.capacity import calculate_amount_safe_to_pay
from buy_or_wait.evidence import EvidenceProcessor
from buy_or_wait.forecast import calculate_baseline_forecast, forecast_balance, get_minimum_projected_balance, is_plan_safe
from buy_or_wait.loaders import load_dataset
from buy_or_wait.models import ScheduledPayment
from buy_or_wait.normalization import normalize_user_events
from buy_or_wait.reconciliation import reconcile_evidence_facts


DATASET = Path(__file__).resolve().parents[2] / "dataset"
QUANTUM = Decimal("0.01")


def _context_events(index, request_id: str):
    context = index.get_request_context(request_id)
    facts = EvidenceProcessor(index).extract_facts_for_request(request_id)
    return context, reconcile_evidence_facts(
        index, context.request.user_id, normalize_user_events(index, context.request.user_id), facts,
    )


def _reference_safe_amount(context, events) -> Decimal:
    """Independent test oracle: fixed baseline headroom, not sample labels."""
    baseline = calculate_baseline_forecast(
        starting_balance=context.profile.current_available_balance,
        minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
        normalized_events=events,
        request_date=context.request.request_date,
    )
    headroom = get_minimum_projected_balance(baseline) - context.profile.minimum_balance_to_keep
    return max(Decimal("0"), min(context.request.requested_amount, headroom)) // QUANTUM * QUANTUM


class AmountSafeReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = load_dataset(DATASET)

    def test_all_sample_requests_match_the_independent_baseline_reference(self) -> None:
        for request in self.index.sample_requests_by_id.values():
            with self.subTest(request_id=request.request_id):
                context, events = _context_events(self.index, request.request_id)
                production = calculate_amount_safe_to_pay(
                    starting_balance=context.profile.current_available_balance,
                    minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                    normalized_events=events,
                    request_date=context.request.request_date,
                    requested_amount=context.request.requested_amount,
                )
                self.assertEqual(_reference_safe_amount(context, events), production)

    def test_all_sample_capacity_boundaries_are_safe_then_unsafe_by_one_cent(self) -> None:
        for request in self.index.sample_requests_by_id.values():
            with self.subTest(request_id=request.request_id):
                context, events = _context_events(self.index, request.request_id)
                safe = calculate_amount_safe_to_pay(
                    starting_balance=context.profile.current_available_balance,
                    minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                    normalized_events=events,
                    request_date=context.request.request_date,
                    requested_amount=context.request.requested_amount,
                )
                safe_forecast = forecast_balance(
                    starting_balance=context.profile.current_available_balance,
                    minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                    normalized_events=events,
                    request_date=context.request.request_date,
                    proposed_payments=(ScheduledPayment(request.request_date, safe),),
                )
                baseline_is_safe = is_plan_safe(forecast_balance(
                    starting_balance=context.profile.current_available_balance,
                    minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                    normalized_events=events,
                    request_date=context.request.request_date,
                ))
                if baseline_is_safe:
                    self.assertTrue(is_plan_safe(safe_forecast))
                else:
                    self.assertEqual(Decimal("0"), safe)
                if safe < request.requested_amount:
                    unsafe_forecast = forecast_balance(
                        starting_balance=context.profile.current_available_balance,
                        minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                        normalized_events=events,
                        request_date=context.request.request_date,
                        proposed_payments=(ScheduledPayment(request.request_date, safe + QUANTUM),),
                    )
                    self.assertFalse(is_plan_safe(unsafe_forecast))

    def test_request_01_boundary_is_source_derived(self) -> None:
        context, events = _context_events(self.index, "request_01")
        safe = calculate_amount_safe_to_pay(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=events,
            request_date=context.request.request_date,
            requested_amount=context.request.requested_amount,
        )
        self.assertEqual(context.request.requested_amount, safe)
        self.assertTrue(is_plan_safe(forecast_balance(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=events,
            request_date=context.request.request_date,
            proposed_payments=(ScheduledPayment(context.request.request_date, safe),),
        )))

    def test_payment_monotonicity_for_representative_sample_contexts(self) -> None:
        for request_id in ("request_01", "request_07", "request_15", "request_25"):
            with self.subTest(request_id=request_id):
                context, events = _context_events(self.index, request_id)
                amounts = (Decimal("0"), context.request.requested_amount / 2, context.request.requested_amount)
                minima = []
                for amount in amounts:
                    forecast = forecast_balance(
                        starting_balance=context.profile.current_available_balance,
                        minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
                        normalized_events=events,
                        request_date=context.request.request_date,
                        proposed_payments=(ScheduledPayment(context.request.request_date, amount),),
                    )
                    minima.append(get_minimum_projected_balance(forecast))
                self.assertGreaterEqual(minima[0], minima[1])
                self.assertGreaterEqual(minima[1], minima[2])

    def test_horizon_is_request_day_through_day_89(self) -> None:
        context, events = _context_events(self.index, "request_01")
        baseline = calculate_baseline_forecast(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=events,
            request_date=context.request.request_date,
        )
        self.assertEqual(context.request.request_date, baseline.days[0].forecast_date)
        self.assertEqual(context.request.request_date + timedelta(days=89), baseline.horizon_end)


if __name__ == "__main__":
    unittest.main()
