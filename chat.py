"""Stateless terminal formatter for the existing Buy or Wait solver.

Each request ID is independently solved by the production pipeline.  This is a
testing/display interface only: it neither implements nor changes financial
calculations, plan selection, evidence reconciliation, or output.csv writing.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parent
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from buy_or_wait.evidence import EvidenceProcessor, model_adapter_from_environment  # noqa: E402
from buy_or_wait.forecast import calculate_baseline_forecast, forecast_balance, get_minimum_projected_balance  # noqa: E402
from buy_or_wait.loaders import DatasetIndex, RequestContext, load_dataset  # noqa: E402
from buy_or_wait.models import PaymentPlan, ScheduledPayment, SpendingChange  # noqa: E402
from buy_or_wait.normalization import normalize_user_events  # noqa: E402
from buy_or_wait.plans import PlanGenerator, PlanValidator  # noqa: E402
from buy_or_wait.reconciliation import reconcile_evidence_facts  # noqa: E402
from buy_or_wait.solver import SolvedRequest, solve_request  # noqa: E402


LINE = "-" * 50
CSV_FIELDS = (
    "request_id", "user_id", "request_date", "request_type", "requested_amount",
    "desired_completion_date", "allows_partial_payment", "request_text",
    "amount_safe_to_pay", "affordability_status", "recommended_payment_method",
    "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed",
    "decision_explanation",
)
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
    baseline_forecast: object
    forecast: object


class BuyOrWaitTerminal:
    """Thin stateless adapter around the real dataset and ``solve_request``.

    The terminal defaults to production ``requests.csv``.  ``--sample`` is an
    explicit offline benchmark mode. ``solve_request`` always receives only
    canonical :class:`Request` fields loaded by ``load_dataset``; sample answer
    columns are read separately and only by explicit comparison mode.
    """

    def __init__(
        self,
        dataset_dir: str | Path = ROOT / "dataset",
        *,
        debug: bool = False,
        sample_mode: bool = False,
    ) -> None:
        self.index: DatasetIndex = load_dataset(dataset_dir)
        self.debug = debug
        self.sample_mode = sample_mode
        self.dataset_dir = Path(dataset_dir)
        self.request_source_filename = "sample_requests.csv" if sample_mode else "requests.csv"
        self.requests_by_id = (
            self.index.sample_requests_by_id if sample_mode else self.index.evaluation_requests_by_id
        )
        # Expected sample answers are intentionally loaded lazily by comparison()
        # only after an independent solver result has been produced.
        self.sample_expected_by_id: dict[str, dict[str, str]] = {}
        self.evidence_processor = EvidenceProcessor(self.index, model_adapter_from_environment())

    def recommendation(self, request_id: str, *, csv_mode: bool = False) -> str:
        """Return one independent record without changing solver behavior.

        The default terminal format is a concise labeled recommendation block.
        ``csv_mode`` is retained for batch and machine consumers; both formats
        are serialized from the same solved record.
        """
        request_id = request_id.strip()
        if request_id not in self.requests_by_id:
            return f"Request ID not found: {request_id or '<empty>'}"
        try:
            view = self._build_view(request_id)
        except Exception as exc:
            return f"Unable to process {request_id}: {type(exc).__name__}: {exc}"
        text = self._csv_line(view) if csv_mode else self._format_view(view)
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
        actual = self._csv_line(view)
        self.sample_expected_by_id = self._load_sample_expected(self.dataset_dir)
        expected = self.sample_expected_by_id.get(request_id, {})
        agent_values = self._record_values(view)
        expected_values = self._expected_values(expected)
        comparisons = [(field, self._field_equal(field, agent_values[field], expected_values[field])) for field in CSV_FIELDS]
        lines = ["AGENT:", actual, "", "EXPECTED:", self._csv_line_from_values(expected_values), "", "FIELD COMPARISON:"]
        for field, matched in comparisons:
            lines.append(f"{field}: {'MATCH' if matched else 'MISMATCH'}")
        overall = all(matched for _, matched in comparisons)
        lines.extend(["", f"Overall: {'MATCH' if overall else 'MISMATCH'}", "", "Sources:"])
        lines.extend(self._source_lines(view))
        if self.debug:
            lines.extend(["", self._format_debug(view)])
        return "\n".join(lines), overall

    @staticmethod
    def _expected_values(row: dict[str, str]) -> dict[str, str]:
        return {field: row.get(field, "") for field in CSV_FIELDS}

    @staticmethod
    def _field_equal(field: str, actual: str, expected: str) -> bool:
        if field in {"requested_amount", "amount_safe_to_pay"}:
            try:
                return Decimal(actual) == Decimal(expected)
            except Exception:
                return False
        if field == "payment_plan":
            if actual == expected == "none":
                return True
            try:
                def parse(value: str):
                    return tuple((date.fromisoformat(token.split(":", 1)[0]), Decimal(token.split(":", 1)[1])) for token in value.split("|"))
                return parse(actual) == parse(expected)
            except Exception:
                return False
        if field == "spending_changes_needed":
            if actual == expected:
                return True
            try:
                def parse_change(value: str):
                    parsed = []
                    for token in value.split("|"):
                        parts = token.split(":")
                        if parts[0] == "reduce_to":
                            parsed.append((parts[0], parts[1], Decimal(parts[2])))
                        else:
                            parsed.append(tuple(parts))
                    return tuple(parsed)
                return parse_change(actual) == parse_change(expected)
            except Exception:
                return False
        if field == "allows_partial_payment":
            return actual.lower() == expected.lower()
        return actual == expected

    @staticmethod
    def _csv_line_from_values(values: dict[str, str]) -> str:
        stream = io.StringIO(newline="")
        csv.writer(stream, lineterminator="").writerow([values[field] for field in CSV_FIELDS])
        return stream.getvalue()

    @staticmethod
    def _record_values(view: RecommendationView) -> dict[str, str]:
        request, result = view.context.request, view.result
        return {
            "request_id": request.request_id,
            "user_id": request.user_id,
            "request_date": request.request_date.isoformat(),
            "request_type": request.request_type,
            "requested_amount": format(request.requested_amount, "f"),
            "desired_completion_date": request.desired_completion_date.isoformat(),
            "allows_partial_payment": str(request.allows_partial_payment).lower(),
            "request_text": request.request_text,
            "amount_safe_to_pay": format(result.amount_safe_to_pay, "f"),
            "affordability_status": result.affordability_status,
            "recommended_payment_method": result.recommended_payment_method,
            "payment_plan": result.payment_plan,
            "earliest_date_for_full_payment": result.earliest_date_for_full_payment.isoformat() if result.earliest_date_for_full_payment else "",
            "spending_changes_needed": result.spending_changes_needed,
            "decision_explanation": result.decision_explanation,
        }

    @classmethod
    def _csv_line(cls, view: RecommendationView) -> str:
        return cls._csv_line_from_values(cls._record_values(view))

    @classmethod
    def _line_record(cls, view: RecommendationView) -> str:
        """Render the 15 fields one-per-line, with no labels or headings."""
        values = cls._record_values(view)
        return "\n".join(values[field].replace("\r", " ").replace("\n", " ") for field in CSV_FIELDS)

    @staticmethod
    def csv_header() -> str:
        return ",".join(CSV_FIELDS)

    def _build_view(self, request_id: str) -> RecommendationView:
        context = self.index.get_request_context(request_id)
        # This is the same production call used by output.csv generation.
        result = solve_request(request_id, self.index, evidence_processor=self.evidence_processor)
        facts = self.evidence_processor.extract_facts_for_request(request_id)
        normalized = reconcile_evidence_facts(
            self.index, context.request.user_id, normalize_user_events(self.index, context.request.user_id), facts,
        )
        plan = self._display_plan(result, context.request.request_date)
        baseline = calculate_baseline_forecast(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=normalized,
            request_date=context.request.request_date,
        )
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
        return RecommendationView(context, result, facts, normalized, tuple(event_ids), tuple(rates), baseline, forecast)

    def _format_view(self, view: RecommendationView) -> str:
        request, profile, result = view.context.request, view.context.profile, view.result
        lines = [
            LINE,
            "REQUEST",
            LINE,
            f"Request ID: {request.request_id}",
            f"User ID: {request.user_id}",
            f"Request Date: {request.request_date.isoformat()}",
            f"Request Type: {request.request_type}",
            f"Requested Amount: {_money(request.requested_amount, profile.home_currency)}",
            f"Desired Completion Date: {request.desired_completion_date.isoformat()}",
            f"Allows Partial Payment: {str(request.allows_partial_payment).lower()}",
            f"Request: {request.request_text}",
            "",
            LINE,
            "AGENT DECISION",
            LINE,
            f"Safe to pay now: {_money(result.amount_safe_to_pay, profile.home_currency)}",
            f"Affordability Status: {result.affordability_status}",
            f"Recommended Payment Method: {result.recommended_payment_method}",
            f"Payment Plan: {result.payment_plan}",
            f"Earliest Date for Full Payment: {_date_text(result.earliest_date_for_full_payment)}",
            f"Spending Changes Needed: {result.spending_changes_needed}",
            "",
            "Decision Explanation:",
            result.decision_explanation,
            "",
            LINE,
            "SOURCES",
            LINE,
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
        relevant_options = self._matching_payment_options(view)
        if relevant_options:
            lines.append("- dataset/request_payment_options.csv -> payment_option_id: " + ", ".join(relevant_options))
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

    @staticmethod
    def _matching_payment_options(view: RecommendationView) -> tuple[str, ...]:
        """Return only supplied options whose exact schedule is selected."""
        result = view.result
        if result.recommended_payment_method not in {"full_payment", "installments"}:
            return ()
        if result.payment_plan == "none":
            return ()
        wanted = []
        for token in result.payment_plan.split("|"):
            when, amount = token.split(":", 1)
            wanted.append((date.fromisoformat(when), Decimal(amount)))
        matches: list[str] = []
        for option in view.context.payment_options:
            if option.payment_method != result.recommended_payment_method:
                continue
            interval = option.payment_frequency_days or 0
            schedule = tuple(
                (option.first_payment_date + timedelta(days=interval * number), option.payment_amount)
                for number in range(option.number_of_payments)
            )
            if schedule == tuple(wanted):
                matches.append(option.payment_option_id)
        return tuple(matches)

    def _format_debug(self, view: RecommendationView) -> str:
        """Factual implementation diagnostics only; never reasoning traces."""
        context = view.context
        facts = [f"{fact.fact_type}:{fact.source_id}:{fact.related_event_id or 'none'}" for fact in view.facts]
        future = [
            f"{event.effective_date.isoformat()} {event.event_id} {event.event_kind}/{event.category} "
            f"{event.amount_in_home_currency if event.amount_in_home_currency is not None else 'missing'} "
            f"{event.status} recurring={event.is_recurring} treatment={event.cash_treatment}"
            for event in view.normalized_events
            if event.effective_date >= context.request.request_date
        ]
        excluded = [
            f"{event.event_id}: {event.cash_treatment}"
            for event in view.normalized_events
            if event.effective_date >= context.request.request_date and event.cash_treatment.startswith("excluded")
        ]
        recurring_projection_days = [
            f"{day.forecast_date.isoformat()} {day.event_delta} {','.join(source_id for source_id in day.source_ids if source_id.startswith('recurrence:'))}"
            for day in view.baseline_forecast.days
            if any(source_id.startswith("recurrence:") for source_id in day.source_ids)
        ]
        candidates = PlanGenerator().generate(
            request=context.request, profile=context.profile, payment_options=context.payment_options,
            amount_safe_to_pay=view.result.amount_safe_to_pay,
            earliest_full_payment_date=view.result.earliest_date_for_full_payment,
        )
        validations = []
        for candidate in candidates:
            validation = PlanValidator().validate(
                plan=candidate, request=context.request, profile=context.profile,
                payment_options=context.payment_options, normalized_events=view.normalized_events,
                amount_safe_to_pay=view.result.amount_safe_to_pay,
                earliest_full_payment_date=view.result.earliest_date_for_full_payment,
            )
            validations.append(
                f"{candidate.method}/{candidate.payment_option_id or 'none'}: "
                f"{'valid' if validation.is_valid else 'rejected ' + ','.join(validation.errors)}"
            )
        baseline_minimum = get_minimum_projected_balance(view.baseline_forecast)
        baseline_day = min(view.baseline_forecast.days, key=lambda day: day.closing_balance)
        minimum = get_minimum_projected_balance(view.forecast)
        minimum_day = min(view.forecast.days, key=lambda day: day.closing_balance)
        raw_capacity = baseline_minimum - context.profile.minimum_balance_to_keep
        cap_amount = min(context.request.requested_amount, max(Decimal("0"), raw_capacity))
        lines = [
            "DEBUG",
            f"request_id: {context.request.request_id}",
            f"user_id: {context.request.user_id}",
            f"starting_balance: {context.profile.current_available_balance}",
            f"minimum_balance_to_keep: {context.profile.minimum_balance_to_keep}",
            f"baseline_minimum: {baseline_minimum} on {baseline_day.forecast_date.isoformat()}",
            f"baseline_minimum_minus_floor: {raw_capacity}",
            f"requested_amount_cap: {cap_amount}",
            f"amount_safe_to_pay: {view.result.amount_safe_to_pay}",
            f"request_payment: {context.request.request_date.isoformat()} {view.result.amount_safe_to_pay}",
            f"forecast_minimum: {minimum} on {minimum_day.forecast_date.isoformat()}",
            f"final_forecast_safe: {str(minimum >= context.profile.minimum_balance_to_keep).lower()}",
            "context event_ids: " + ", ".join(event.event_id for event in context.events[:20]),
            "payment_option_ids: " + ", ".join(option.payment_option_id for option in context.payment_options),
            "evidence facts: " + (", ".join(facts) if facts else "none"),
            "forecast event_ids: " + (", ".join(view.forecast_event_ids) if view.forecast_event_ids else "none"),
            "future normalized events: " + (" | ".join(future[:60]) if future else "none"),
            "excluded future events: " + (" | ".join(excluded) if excluded else "none"),
            "projected recurring entries: " + (" | ".join(recurring_projection_days[:60]) if recurring_projection_days else "none"),
            "candidate validation: " + (" | ".join(validations) if validations else "none"),
            "selected plan: " + view.result.recommended_payment_method + " / " + view.result.payment_plan,
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
    """Repeatedly accept independent IDs and print one recommendation block."""
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
    summary: bool = True,
    csv_mode: bool = False,
) -> tuple[int, int, tuple[str, ...]]:
    """Run every selected request and return summary counts.

    In sample comparison mode the returned counts are match/mismatch counts;
    otherwise they are successful/failed processing counts.
    """
    successful = 0
    failures: list[str] = []
    matches = 0
    mismatches: list[str] = []
    mismatch_fields: dict[str, tuple[str, ...]] = {}
    request_ids = tuple(terminal.requests_by_id)
    for request_id in request_ids:
        if compare:
            text, matched = terminal.comparison(request_id)
            if matched:
                matches += 1
            else:
                mismatches.append(request_id)
                mismatch_fields[request_id] = tuple(
                    field for field in CSV_FIELDS
                    if f"{field}: MISMATCH" in text
                )
        else:
            text = terminal.recommendation(request_id, csv_mode=csv_mode)
        output_fn(text)
        if not compare and text.startswith("Unable to process"):
            failures.append(request_id)
        else:
            if not compare:
                successful += 1
    if not summary:
        return (matches, len(mismatches), tuple(mismatches)) if compare else (successful, len(failures), tuple(failures))
    output_fn("=" * 50)
    if compare:
        output_fn(f"Requests processed: {len(request_ids)}")
        output_fn(f"Matches: {matches}")
        output_fn(f"Mismatches: {len(mismatches)}")
        if mismatches:
            output_fn("Mismatching request IDs: " + ", ".join(mismatches))
            output_fn("Mismatching fields:")
            for request_id in mismatches:
                output_fn(f"- {request_id}: {', '.join(mismatch_fields[request_id])}")
    else:
        output_fn(f"Processed: {successful + len(failures)} requests")
        output_fn(f"Successful: {successful}")
        output_fn(f"Failed: {len(failures)}")
    output_fn("=" * 50)
    return (matches, len(mismatches), tuple(mismatches)) if compare else (successful, len(failures), tuple(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description="Print one Buy or Wait recommendation per request ID.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset", help="Challenge dataset directory.")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--sample", action="store_true", help="Use sample_requests.csv for offline benchmark testing only.")
    source_group.add_argument("--official", action="store_true", help="Use production requests.csv (the default; retained for compatibility).")
    parser.add_argument("--all", action="store_true", help="Print independent recommendations for every selected request.")
    parser.add_argument("--csv", action="store_true", help="Emit comma-separated records; default interactive output is a labeled recommendation block.")
    parser.add_argument("--compare", action="store_true", help="Compare sample results with labelled columns without using them as inputs.")
    parser.add_argument("--output", type=Path, help="Optional human-readable output file for --all; never replaces output.csv.")
    parser.add_argument("--debug", action="store_true", help="Append factual source/record diagnostics to recommendations.")
    args = parser.parse_args()
    try:
        if args.compare and not args.sample:
            parser.error("--compare requires --sample and is unavailable for production requests.csv")
        terminal = BuyOrWaitTerminal(args.dataset_dir, debug=args.debug, sample_mode=args.sample)
        if not args.all:
            if args.output is not None:
                parser.error("--output is supported only with --all")
            return run_compare_terminal(terminal) if args.compare else run_terminal(terminal)
        blocks: list[str] = []
        if not args.compare and args.csv:
            blocks.append(terminal.csv_header())
        successful, failed, _ = run_all(
            terminal,
            output_fn=blocks.append,
            compare=args.compare,
            summary=not args.csv or args.compare,
            csv_mode=args.csv,
        )
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
