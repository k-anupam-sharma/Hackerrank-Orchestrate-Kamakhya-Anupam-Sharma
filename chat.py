"""Stateless terminal formatter for the existing Buy or Wait solver.

Each request ID is independently solved by the production pipeline.  This is a
testing/display interface only: it neither implements nor changes financial
calculations, plan selection, evidence reconciliation, or output.csv writing.
"""

from __future__ import annotations

import argparse
import csv
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
    """Thin stateless adapter around the real dataset and ``solve_request``.

    The terminal defaults to the labelled sample requests so it is convenient
    for local testing.  ``solve_request`` still receives only the canonical
    :class:`Request` fields loaded by ``load_dataset``; sample answer columns
    are read separately and are used only by explicit comparison mode.
    """

    def __init__(
        self,
        dataset_dir: str | Path = ROOT / "dataset",
        *,
        debug: bool = False,
        sample_mode: bool = True,
    ) -> None:
        self.index: DatasetIndex = load_dataset(dataset_dir)
        self.debug = debug
        self.sample_mode = sample_mode
        self.request_source_filename = "sample_requests.csv" if sample_mode else "requests.csv"
        self.requests_by_id = (
            self.index.sample_requests_by_id if sample_mode else self.index.evaluation_requests_by_id
        )
        self.sample_expected_by_id = self._load_sample_expected(dataset_dir) if sample_mode else {}
        self.evidence_processor = EvidenceProcessor(self.index, model_adapter_from_environment())

    def recommendation(self, request_id: str) -> str:
        """Return one complete independent recommendation block for a valid ID."""
        request_id = request_id.strip()
        if request_id not in self.requests_by_id:
            return f"Request ID not found: {request_id or '<empty>'}"
        try:
            view = self._build_view(request_id)
        except Exception as exc:
            return f"Unable to process {request_id}: {type(exc).__name__}: {exc}"
        text = self._format_view(view)
        return text if not self.debug else text + "\n" + self._format_debug(view)

    def all_recommendations(self) -> Iterable[tuple[str, str]]:
        """Yield one formatted block per evaluation request in source CSV order."""
        for request_id in self.requests_by_id:
            yield request_id, self.recommendation(request_id)

    @staticmethod
    def _load_sample_expected(dataset_dir: str | Path) -> dict[str, dict[str, str]]:
        """Read labelled columns for comparison only, never as solver input."""
        path = Path(dataset_dir) / "sample_requests.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {
                row["request_id"]: row
                for row in csv.DictReader(handle)
                if row.get("request_id")
            }

    def comparison(self, request_id: str) -> tuple[str, bool]:
        """Render an independently solved sample request beside its labels."""
        request_id = request_id.strip()
        if not self.sample_mode:
            return "Comparison mode requires sample_requests.csv mode.", False
        if request_id not in self.requests_by_id:
            return f"Request ID not found: {request_id or '<empty>'}", False
        try:
            view = self._build_view(request_id)
        except Exception as exc:
            return f"Unable to process {request_id}: {type(exc).__name__}: {exc}", False
        actual = self._format_view(view)
        expected = self.sample_expected_by_id.get(request_id, {})
        comparisons = [
            ("amount_safe_to_pay", self._decimal_equal(view.result.amount_safe_to_pay, expected.get("amount_safe_to_pay", ""))),
            ("affordability_status", view.result.affordability_status == expected.get("affordability_status", "")),
            ("recommended_payment_method", view.result.recommended_payment_method == expected.get("recommended_payment_method", "")),
            ("payment_plan", view.result.payment_plan == expected.get("payment_plan", "")),
            ("earliest_date_for_full_payment", (view.result.earliest_date_for_full_payment.isoformat() if view.result.earliest_date_for_full_payment else "") == expected.get("earliest_date_for_full_payment", "")),
            ("spending_changes_needed", view.result.spending_changes_needed == expected.get("spending_changes_needed", "")),
        ]
        lines = ["AGENT RESULT", actual, "", "SAMPLE EXPECTED RESULT"]
        for field, value in expected.items():
            if field in {name for name, _ in comparisons}:
                lines.append(f"{field}: {value}")
        lines.extend(["", "COMPARISON"])
        for field, matched in comparisons:
            lines.append(f"- {field}: {'MATCH' if matched else 'MISMATCH'}")
        overall = all(matched for _, matched in comparisons)
        lines.extend(["", f"Overall: {'MATCH' if overall else 'MISMATCH'}"])
        return "\n".join(lines), overall

    @staticmethod
    def _decimal_equal(actual: Decimal, expected: str) -> bool:
        try:
            return actual == Decimal(expected)
        except Exception:
            return False

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
            f"- dataset/{self.request_source_filename} -> request_id: {context.request.request_id}",
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


def run_compare_terminal(
    terminal: BuyOrWaitTerminal,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    """Interactive sample comparison loop; expected labels remain display-only."""
    output_fn("BUY OR WAIT - SAMPLE COMPARISON")
    output_fn("Enter a sample request ID. Type 'exit' to quit.")
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
        text, _ = terminal.comparison(value)
        output_fn(text)


def run_all(
    terminal: BuyOrWaitTerminal,
    output_fn: Callable[[str], None] = print,
    *,
    compare: bool = False,
) -> tuple[int, int, tuple[str, ...]]:
    """Run every selected request and return summary counts.

    In sample comparison mode the returned counts are match/mismatch counts;
    otherwise they are successful/failed processing counts.
    """
    successful = 0
    failures: list[str] = []
    matches = 0
    mismatches: list[str] = []
    request_ids = tuple(terminal.requests_by_id)
    for request_id in request_ids:
        if compare:
            text, matched = terminal.comparison(request_id)
            if matched:
                matches += 1
            else:
                mismatches.append(request_id)
        else:
            text = terminal.recommendation(request_id)
        output_fn(text)
        if not compare and text.startswith("Unable to process"):
            failures.append(request_id)
        else:
            if not compare:
                successful += 1
    output_fn("=" * 50)
    if compare:
        output_fn(f"Requests processed: {len(request_ids)}")
        output_fn(f"Matches: {matches}")
        output_fn(f"Mismatches: {len(mismatches)}")
        if mismatches:
            output_fn("Mismatching request IDs: " + ", ".join(mismatches))
    else:
        output_fn(f"Processed: {successful + len(failures)} requests")
        output_fn(f"Successful: {successful}")
        output_fn(f"Failed: {len(failures)}")
    output_fn("=" * 50)
    return (matches, len(mismatches), tuple(mismatches)) if compare else (successful, len(failures), tuple(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description="Print one Buy or Wait recommendation per request ID.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset", help="Challenge dataset directory.")
    parser.add_argument("--official", action="store_true", help="Use requests.csv instead of the default sample_requests.csv test set.")
    parser.add_argument("--all", action="store_true", help="Print independent recommendations for every selected request.")
    parser.add_argument("--compare", action="store_true", help="Compare sample results with labelled columns without using them as inputs.")
    parser.add_argument("--output", type=Path, help="Optional human-readable output file for --all; never replaces output.csv.")
    parser.add_argument("--debug", action="store_true", help="Append factual source/record diagnostics to recommendations.")
    args = parser.parse_args()
    try:
        if args.compare and args.official:
            parser.error("--compare is available only with the sample request set")
        terminal = BuyOrWaitTerminal(args.dataset_dir, debug=args.debug, sample_mode=not args.official)
        if not args.all:
            if args.output is not None:
                parser.error("--output is supported only with --all")
            return run_compare_terminal(terminal) if args.compare else run_terminal(terminal)
        blocks: list[str] = []
        successful, failed, _ = run_all(terminal, output_fn=blocks.append, compare=args.compare)
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
