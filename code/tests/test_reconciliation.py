from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from buy_or_wait.loaders import load_dataset
from buy_or_wait.models import EvidenceFact
from buy_or_wait.normalization import normalize_user_events
from buy_or_wait.reconciliation import reconcile_evidence_facts


DATASET = Path(__file__).resolve().parents[2] / "dataset"


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = load_dataset(DATASET)
        cls.events = normalize_user_events(cls.index, "user_01")

    def fact(self, fact_type: str, *, amount: Decimal | None = None) -> EvidenceFact:
        return EvidenceFact(
            fact_type, "user_01", "model-message", "message", datetime(2026, 1, 1, tzinfo=timezone.utc),
            "event_102", "request_01", amount, "ZAR" if amount is not None else None,
            None, Decimal("0.9"), "mocked evidence",
        )

    def test_explicit_cancellation_wins_and_does_not_create_a_new_record(self) -> None:
        reconciled = reconcile_evidence_facts(self.index, "user_01", self.events, (self.fact("event_cancelled"),))
        event = next(item for item in reconciled if item.event_id == "event_102")
        self.assertEqual("cancelled", event.status)
        self.assertEqual("excluded_cancelled", event.cash_treatment)
        self.assertEqual(len(self.events), len(reconciled))

    def test_validated_amendment_updates_only_the_existing_linked_event(self) -> None:
        reconciled = reconcile_evidence_facts(self.index, "user_01", self.events, (self.fact("event_amount_amended", amount=Decimal("321")),))
        event = next(item for item in reconciled if item.event_id == "event_102")
        self.assertEqual(Decimal("321"), event.amount)
        self.assertEqual(Decimal("321"), event.amount_in_home_currency)


if __name__ == "__main__":
    unittest.main()
