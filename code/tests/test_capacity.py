from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from buy_or_wait.capacity import (
    calculate_amount_safe_to_pay, find_earliest_safe_full_payment_date,
)
from buy_or_wait.forecast import calculate_baseline_forecast, get_minimum_projected_balance, is_plan_safe, forecast_balance
from buy_or_wait.models import ScheduledPayment
from test_forecast import START, event


class CapacityTests(unittest.TestCase):
    def capacity(self, *, balance, floor, requested, events=(), horizon=90):
        return calculate_amount_safe_to_pay(
            starting_balance=Decimal(balance), minimum_balance_to_keep=Decimal(floor),
            normalized_events=events, request_date=START, requested_amount=Decimal(requested),
            horizon_days=horizon,
        )

    def earliest(self, *, balance, floor, requested, events=(), horizon=90):
        return find_earliest_safe_full_payment_date(
            starting_balance=Decimal(balance), minimum_balance_to_keep=Decimal(floor),
            normalized_events=events, request_date=START, requested_amount=Decimal(requested),
            horizon_days=horizon,
        )

    def test_affordable_today_is_capped_and_earliest_date_is_request_date(self) -> None:
        self.assertEqual(Decimal("100.00"), self.capacity(balance="200", floor="50", requested="100"))
        self.assertEqual(START, self.earliest(balance="200", floor="50", requested="100"))

    def test_full_payment_becomes_safe_after_salary_arrives(self) -> None:
        salary = event("salary", START + timedelta(days=2), "50", direction="credit", event_type="income", category="salary")
        self.assertEqual(Decimal("50.00"), self.capacity(balance="100", floor="50", requested="100", events=(salary,)))
        self.assertEqual(START + timedelta(days=2), self.earliest(balance="100", floor="50", requested="100", events=(salary,)))

    def test_request_larger_than_capacity_is_not_overstated(self) -> None:
        self.assertEqual(Decimal("100.00"), self.capacity(balance="150", floor="50", requested="500"))

    def test_never_affordable_returns_none_for_full_payment_date(self) -> None:
        self.assertEqual(Decimal("50.00"), self.capacity(balance="100", floor="50", requested="200"))
        self.assertIsNone(self.earliest(balance="100", floor="50", requested="200"))

    def test_minimum_balance_constraint_accounts_for_future_expense(self) -> None:
        bill = event("bill", START + timedelta(days=1), "30")
        self.assertEqual(Decimal("20.00"), self.capacity(balance="150", floor="100", requested="100", events=(bill,)))

    def test_future_recurring_expenses_reduce_capacity(self) -> None:
        rent = (
            event("rent-old", START - timedelta(days=14), "20", recurring=True),
            event("rent-prior", START - timedelta(days=7), "20", recurring=True),
            event("rent-now", START, "20", recurring=True),
        )
        self.assertEqual(Decimal("90.00"), self.capacity(balance="200", floor="50", requested="200", events=rent, horizon=15))

    def test_exact_date_boundary_uses_income_on_that_date_but_not_after_horizon(self) -> None:
        boundary_salary = event("salary", START + timedelta(days=3), "50", direction="credit", event_type="income", category="salary")
        self.assertEqual(START + timedelta(days=3), self.earliest(balance="100", floor="50", requested="100", events=(boundary_salary,), horizon=4))
        after_horizon = event("later-salary", START + timedelta(days=4), "50", direction="credit", event_type="income", category="salary")
        self.assertIsNone(self.earliest(balance="100", floor="50", requested="100", events=(after_horizon,), horizon=4))

    def test_direct_capacity_equals_baseline_minimum_minus_floor(self) -> None:
        expense = event("expense", START + timedelta(days=2), "17.25")
        baseline = calculate_baseline_forecast(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
            normalized_events=(expense,), request_date=START, horizon_days=5,
        )
        self.assertEqual(Decimal("82.75"), get_minimum_projected_balance(baseline))
        self.assertEqual(Decimal("32.75"), self.capacity(balance="100", floor="50", requested="100", events=(expense,), horizon=5))
        safe = self.capacity(balance="100", floor="50", requested="100", events=(expense,), horizon=5)
        self.assertTrue(is_plan_safe(forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
            normalized_events=(expense,), request_date=START,
            proposed_payments=(ScheduledPayment(START, safe),), horizon_days=5,
        )))
        self.assertFalse(is_plan_safe(forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
            normalized_events=(expense,), request_date=START,
            proposed_payments=(ScheduledPayment(START, safe + Decimal("0.01")),), horizon_days=5,
        )))

    def test_same_day_events_are_part_of_the_fixed_baseline(self) -> None:
        income = event("income", START, "20", direction="credit", event_type="income", category="salary")
        expense = event("same-day-expense", START, "10")
        self.assertEqual(Decimal("60.00"), self.capacity(
            balance="100", floor="50", requested="100", events=(income, expense), horizon=3,
        ))

    def test_capacity_is_monotonic_in_payment_amount(self) -> None:
        event_after = event("expense", START + timedelta(days=1), "10")
        safe = self.capacity(balance="100", floor="50", requested="100", events=(event_after,))
        for amount in (Decimal("0"), safe, safe + Decimal("0.01"), Decimal("100")):
            forecast = forecast_balance(
                starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
                normalized_events=(event_after,), request_date=START,
                proposed_payments=(ScheduledPayment(START, amount),),
            )
            if amount <= safe:
                self.assertTrue(is_plan_safe(forecast))
            else:
                self.assertFalse(is_plan_safe(forecast))


if __name__ == "__main__":
    unittest.main()
