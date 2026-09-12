from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from buy_or_wait.forecast import forecast_balance, get_minimum_projected_balance, is_plan_safe
from buy_or_wait.models import NormalizedEvent, ScheduledPayment, SpendingChange


START = date(2026, 1, 1)


def event(
    event_id: str,
    when: date,
    amount: str,
    *,
    direction: str = "debit",
    status: str = "settled",
    treatment: str = "settled_cash",
    event_type: str = "expense",
    category: str = "rent",
    recurring: bool = False,
) -> NormalizedEvent:
    money = Decimal(amount)
    return NormalizedEvent(
        event_id=event_id, user_id="u1", effective_date=when, event_date=when,
        settlement_date=when, amount=money, currency="INR", amount_in_home_currency=money,
        home_currency="INR", conversion_date=when, conversion_status="identity",
        event_type=event_type, event_kind=event_type, category=category, direction=direction,
        status=status, linked_event_id=None, lifecycle_role="standalone", cash_treatment=treatment,
        is_recurring=recurring, is_flexible=False, flexibility="fixed",
        minimum_allowed_amount=None, source="test", description=event_id,
    )


class ForecastTests(unittest.TestCase):
    def test_payment_exactly_at_minimum_is_safe(self) -> None:
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
            normalized_events=(), request_date=START,
            proposed_payments=(ScheduledPayment(START, Decimal("50")),), horizon_days=3,
        )
        self.assertEqual(Decimal("50"), forecast.days[0].closing_balance)
        self.assertEqual(Decimal("50"), get_minimum_projected_balance(forecast))
        self.assertTrue(is_plan_safe(forecast))

    def test_one_day_breach_is_unsafe_even_if_salary_arrives_next_day(self) -> None:
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("50"),
            normalized_events=(
                event("expense", START + timedelta(days=1), "51"),
                event("salary", START + timedelta(days=2), "100", direction="credit", event_type="income", category="salary"),
            ), request_date=START, horizon_days=4,
        )
        self.assertEqual(Decimal("49"), forecast.days[1].closing_balance)
        self.assertEqual(Decimal("149"), forecast.days[2].closing_balance)
        self.assertFalse(is_plan_safe(forecast))

    def test_later_salary_is_applied_on_its_effective_date_only(self) -> None:
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("10"),
            normalized_events=(event("salary", START + timedelta(days=2), "50", direction="credit", event_type="income", category="salary"),),
            request_date=START, proposed_payments=(ScheduledPayment(START, Decimal("90")),), horizon_days=4,
        )
        self.assertEqual([Decimal("10"), Decimal("10"), Decimal("60"), Decimal("60")], [day.closing_balance for day in forecast.days])
        self.assertTrue(is_plan_safe(forecast))

    def test_recurring_expense_is_expanded_after_request_date(self) -> None:
        rent = (
            event("rent-old", START - timedelta(days=14), "10", recurring=True),
            event("rent-prior", START - timedelta(days=7), "10", recurring=True),
            event("rent-now", START, "10", recurring=True),
        )
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("0"),
            normalized_events=rent, request_date=START, horizon_days=15,
        )
        self.assertEqual(Decimal("90"), forecast.days[0].closing_balance)
        self.assertEqual(Decimal("80"), forecast.days[7].closing_balance)
        self.assertEqual(Decimal("70"), forecast.days[14].closing_balance)
        self.assertIn("recurrence:rent-now", forecast.days[7].source_ids)

    def test_stop_change_cancels_future_recurring_charge(self) -> None:
        rent = (
            event("rent-old", START - timedelta(days=14), "10", recurring=True),
            event("rent-prior", START - timedelta(days=7), "10", recurring=True),
            event("rent-now", START, "10", recurring=True),
        )
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("0"),
            normalized_events=rent, request_date=START,
            spending_changes=(SpendingChange("rent-now", "stop", START + timedelta(days=5)),), horizon_days=15,
        )
        self.assertEqual(Decimal("90"), forecast.days[7].closing_balance)
        self.assertNotIn("recurrence:rent-now", forecast.days[7].source_ids)

    def test_stop_change_also_removes_listed_future_recurring_charge(self) -> None:
        rent = (
            event("rent-old", START - timedelta(days=14), "10", recurring=True),
            event("rent-prior", START - timedelta(days=7), "10", recurring=True),
            event("rent-now", START, "10", recurring=True),
            event("rent-listed-future", START + timedelta(days=7), "10", recurring=True, status="scheduled", treatment="scheduled_cash"),
        )
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("0"),
            normalized_events=rent, request_date=START,
            spending_changes=(SpendingChange("rent-now", "stop", START + timedelta(days=5)),), horizon_days=8,
        )
        self.assertEqual(Decimal("90"), forecast.days[7].closing_balance)
        self.assertIn("rent-listed-future", forecast.ignored_event_ids)

    def test_same_day_events_and_payment_are_aggregated_deterministically(self) -> None:
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("0"),
            normalized_events=(
                event("bill", START + timedelta(days=1), "20"),
                event("salary", START + timedelta(days=1), "50", direction="credit", event_type="income", category="salary"),
            ), request_date=START,
            proposed_payments=(ScheduledPayment(START + timedelta(days=1), Decimal("10"), "request"),), horizon_days=3,
        )
        day = forecast.days[1]
        self.assertEqual(Decimal("30"), day.event_delta)
        self.assertEqual(Decimal("-10"), day.payment_delta)
        self.assertEqual(Decimal("120"), day.closing_balance)
        self.assertEqual(("bill", "salary", "request"), day.source_ids)

    def test_pending_credits_and_non_cash_or_terminal_events_are_ignored(self) -> None:
        future = START + timedelta(days=1)
        forecast = forecast_balance(
            starting_balance=Decimal("100"), minimum_balance_to_keep=Decimal("0"),
            normalized_events=(
                event("pending-debit", future, "7", status="pending", treatment="reserve_pending_debit"),
                event("pending-credit", future, "30", direction="credit", status="pending", treatment="exclude_pending_credit", event_type="income", category="salary"),
                event("failed", future, "20", status="failed", treatment="excluded_failed"),
                event("cancelled", future, "20", status="cancelled", treatment="excluded_cancelled"),
                event("duplicate", future, "20", status="pending", treatment="excluded_duplicate"),
                event("valuation", future, "20", direction="credit", status="unrealized", treatment="excluded_non_cash_or_unrealized", event_type="investment_valuation", category="investment"),
            ), request_date=START, horizon_days=3,
        )
        self.assertEqual(Decimal("93"), forecast.days[1].closing_balance)
        self.assertEqual({"pending-credit", "failed", "cancelled", "duplicate", "valuation"}, set(forecast.ignored_event_ids))


if __name__ == "__main__":
    unittest.main()
