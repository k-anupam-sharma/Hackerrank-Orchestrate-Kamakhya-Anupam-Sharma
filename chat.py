"""Stateless terminal formatter for the existing Buy or Wait solver.

Each request ID is independently solved by the production pipeline.  This is a
testing/display interface only: it neither implements nor changes financial
calculations, plan selection, evidence reconciliation, or output.csv writing.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parent
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from buy_or_wait.evidence import EvidenceProcessor, model_adapter_from_environment  # noqa: E402
from buy_or_wait.forecast import forecast_balance  # noqa: E402
from buy_or_wait.loaders import DatasetIndex, RequestContext, load_dataset  # noqa: E402
from buy_or_wait.models import PaymentPlan, ScheduledPayment, SpendingChange  # noqa: E402
from buy_or_wait.normalization import normalize_user_events  # noqa: E402
from buy_or_wait.reconciliation import reconcile_evidence_facts  # noqa: E402
from buy_or_wait.solver import SolvedRequest, solve_request  # noqa: E402


LINE = "-" * 50
_PAYMENT_TOKEN = re.compile(r"^(\d{4}-\d{2}-\d{2}):([0-9]+(?:\.[0-9]+)?)$")


def _money(amount: Decimal, currency: str) -> str:
    """Use ASCII-friendly currency labels for cross-platform terminals."""
    return f"{currency} {format(amount, 'f')}"


def _date_text(value: date | None) -> str:
    return value.isoformat() if value is not None else "not safe within the 90-day forecast"


@dataclass(frozen=True)
class RecommendationView:
    """Already-computed solver result plus factual provenance for formatting."""

    context: RequestContext
    result: SolvedRequest
    facts: tuple
    normalized_events: tuple
    forecast_event_ids: tuple[str, ...]
    converted_rate_keys: tuple[tuple[date, str, str], ...]


class BuyOrWaitTerminal:
    """Thin stateless adapter around the real dataset and `solve_request`."""

    def __init__(self, dataset_dir: str | Path = ROOT / "dataset", *, debug: bool = False) -> None:
        self.index: DatasetIndex = load_dataset(dataset_dir)
        self.debug = debug
        self.evidence_processor = EvidenceProcessor(self.index, model_adapter_from_environment())

    def recommendation(self, request_id: str) -> str:
        """Return one complete independent recommendation block for a valid ID."""
        request_id = request_id.strip()
        if request_id not in self.index.evaluation_requests_by_id:
            return f"Request ID not found: {request_id or '<empty>'}"
        try:
            view = self._build_view(request_id)
        except Exception as exc:
            return f"Unable to process {request_id}: {type(exc).__name__}: {exc}"
        text = self._format_view(view)
        return text if not self.debug else text + "\n" + self._format_debug(view)

    def all_recommendations(self) -> Iterable[tuple[str, str]]:
        """Yield one formatted block per evaluation request in source CSV order."""
        for request_id in self.index.evaluation_requests_by_id:
            yield request_id, self.recommendation(request_id)

    def _build_view(self, request_id: str) -> RecommendationView:
        context = self.index.get_request_context(request_id)
        # This is the same production call used by output.csv generation.
        result = solve_request(request_id, self.index, evidence_processor=self.evidence_processor)
        facts = self.evidence_processor.extract_facts_for_request(request_id)
        normalized = reconcile_evidence_facts(
            self.index, context.request.user_id, normalize_user_events(self.index, context.request.user_id), facts,
        )
        plan = self._display_plan(result, context.request.request_date)
        forecast = forecast_balance(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=normalized,
            request_date=context.request.request_date,
            spending_changes=plan.spending_changes,
            proposed_payments=plan.payments,
        )
        known_ids = {event.event_id for event in normalized}
        event_ids: list[str] = []
        for day in forecast.days:
            for source_id in day.source_ids:
                event_id = source_id.removeprefix("recurrence:").split(":", 1)[0]
                if event_id in known_ids and event_id not in event_ids:
                    event_ids.append(event_id)
        by_id = {event.event_id: event for event in normalized}
        rates: list[tuple[date, str, str]] = []
        for event_id in event_ids:
            event = by_id[event_id]
            if event.conversion_status == "converted" and event.conversion_date is not None:
                key = (event.conversion_date, event.currency, event.home_currency)
                if key not in rates:
                    rates.append(key)
        return RecommendationView(context, result, facts, normalized, tuple(event_ids), tuple(rates))

    def _format_view(self, view: RecommendationView) -> str:
        request, profile, result = view.context.request, view.context.profile, view.result
        lines = [
            LINE,
            f"Recommendation for {request.request_id}",
            "",
            "Request:",
            request.request_text,
            "",
            f"Requested: {_money(request.requested_amount, profile.home_currency)}",
            f"Deadline: {request.desired_completion_date.isoformat()}",
            "",
            f"Safe to pay now: {_money(result.amount_safe_to_pay, profile.home_currency)}",
            f"Decision: {result.affordability_status}",
            f"Recommended method: {result.recommended_payment_method}",
            f"Plan: {result.payment_plan}",
            f"Earliest safe full payment: {_date_text(result.earliest_date_for_full_payment)}",
            f"Spending changes: {result.spending_changes_needed}",
            "",
            "Why:",
            result.decision_explanation,
            "",
            "Sources:",
            *self._source_lines(view),
            LINE,
        ]
        return "\n".join(lines)

    def _source_lines(self, view: RecommendationView) -> list[str]:
        context, profile = view.context, view.context.profile
        lines = [
            f"- dataset/requests.csv -> request_id: {context.request.request_id}",
            f"- dataset/financial_profiles.csv -> user_id: {context.profile.user_id}",
        ]
        if view.forecast_event_ids:
            lines.append("- dataset/financial_events.csv -> event_id: " + ", ".join(view.forecast_event_ids))
        if context.payment_options:
            lines.append("- dataset/request_payment_options.csv -> payment_option_id: " + ", ".join(option.payment_option_id for option in context.payment_options))
        if view.converted_rate_keys:
            rendered = ", ".join(f"{when.isoformat()} {source}->{target}" for when, source, target in view.converted_rate_keys)
            lines.append(f"- dataset/exchange_rates.csv -> {rendered}")
        message_facts = [fact for fact in view.facts if fact.source_kind == "message"]
        if message_facts:
            lines.append("- dataset/messages.csv -> message_id: " + ", ".join(fact.source_id for fact in message_facts))
        image_facts = [fact for fact in view.facts if fact.source_kind == "image"]
        if image_facts:
            lines.append("- dataset/images.csv / dataset/media/images -> image_id: " + ", ".join(fact.source_id for fact in image_facts))
        return lines

    def _format_debug(self, view: RecommendationView) -> str:
        """Factual implementation diagnostics only; never reasoning traces."""
        context = view.context
        facts = [f"{fact.fact_type}:{fact.source_id}:{fact.related_event_id or 'none'}" for fact in view.facts]
        lines = [
            "DEBUG",
            f"request_id: {context.request.request_id}",
            f"user_id: {context.request.user_id}",
            "context event_ids: " + ", ".join(event.event_id for event in context.events[:20]),
            "payment_option_ids: " + ", ".join(option.payment_option_id for option in context.payment_options),
            "evidence facts: " + (", ".join(facts) if facts else "none"),
            "forecast event_ids: " + (", ".join(view.forecast_event_ids) if view.forecast_event_ids else "none"),
        ]
        return "\n".join(lines)

    @staticmethod
    def _display_plan(result: SolvedRequest, request_date: date) -> PaymentPlan:
        payments: list[ScheduledPayment] = []
        if result.payment_plan != "none":
            for index, token in enumerate(result.payment_plan.split("|"), start=1):
                match = _PAYMENT_TOKEN.match(token)
                if match is None:
                    raise ValueError(f"Malformed solver payment plan token: {token}")
                payments.append(ScheduledPayment(date.fromisoformat(match.group(1)), Decimal(match.group(2)), f"chat-payment:{index}"))
        changes: list[SpendingChange] = []
        if result.spending_changes_needed != "none":
            for token in result.spending_changes_needed.split("|"):
                parts = token.split(":")
                if parts[0] == "stop" and len(parts) == 2:
                    changes.append(SpendingChange(parts[1], "stop", request_date))
                elif parts[0] == "reduce_to" and len(parts) == 3:
                    changes.append(SpendingChange(parts[1], "reduce_to", request_date, Decimal(parts[2])))
                else:
                    raise ValueError(f"Malformed solver spending change: {token}")
        return PaymentPlan(result.recommended_payment_method, tuple(payments), sum((payment.amount for payment in payments), Decimal("0")), None, Decimal("0"), result.recommended_payment_method == "not_recommended", tuple(changes))


def run_terminal(terminal: BuyOrWaitTerminal, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> int:
    """Repeatedly accept independent request IDs; no conversational state exists."""
    output_fn("BUY OR WAIT - REQUEST RUNNER")
    output_fn("Enter a request ID. Type 'exit' to quit.")
    while True:
        try:
            value = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Goodbye.")
            return 0
        if not value:
            output_fn("Enter a request ID or 'exit'.")
            continue
        if value.lower() in {"exit", "quit"}:
            output_fn("Goodbye.")
            return 0
        output_fn(terminal.recommendation(value))


def run_all(terminal: BuyOrWaitTerminal, output_fn: Callable[[str], None] = print) -> tuple[int, int, tuple[str, ...]]:
    """Run every evaluation request without prompting and return summary counts."""
    successful = 0
    failures: list[str] = []
    for request_id, text in terminal.all_recommendations():
        output_fn(text)
        if text.startswith("Unable to process"):
            failures.append(request_id)
        else:
            successful += 1
    output_fn("=" * 50)
    output_fn(f"Processed: {successful + len(failures)} requests")
    output_fn(f"Successful: {successful}")
    output_fn(f"Failed: {len(failures)}")
    output_fn("=" * 50)
    return successful, len(failures), tuple(failures)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print one Buy or Wait recommendation per request ID.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset", help="Challenge dataset directory.")
    parser.add_argument("--all", action="store_true", help="Print independent recommendations for every evaluation request.")
    parser.add_argument("--output", type=Path, help="Optional human-readable output file for --all; never replaces output.csv.")
    parser.add_argument("--debug", action="store_true", help="Append factual source/record diagnostics to recommendations.")
    args = parser.parse_args()
    try:
        terminal = BuyOrWaitTerminal(args.dataset_dir, debug=args.debug)
        if not args.all:
            if args.output is not None:
                parser.error("--output is supported only with --all")
            return run_terminal(terminal)
        blocks: list[str] = []
        successful, failed, _ = run_all(terminal, output_fn=blocks.append)
        text = "\n".join(blocks) + "\n"
        print(text, end="")
        if args.output is not None:
            args.output.write_text(text, encoding="utf-8", newline="\n")
        return 0 if failed == 0 else 1
    except Exception as exc:
        print(f"Unable to start request runner: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
