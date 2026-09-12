"""Independent deterministic validation and reporting for Buy or Wait output.csv."""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))

from buy_or_wait.capacity import calculate_amount_safe_to_pay, find_earliest_safe_full_payment_date
from buy_or_wait.evidence import EvidenceProcessor
from buy_or_wait.explanations import build_explanation_facts, validate_explanation
from buy_or_wait.loaders import OUTPUT_COLUMNS, load_dataset
from buy_or_wait.models import PaymentPlan, Recommendation, ScheduledPayment, SpendingChange
from buy_or_wait.normalization import normalize_user_events
from buy_or_wait.plans import PlanValidator
from buy_or_wait.reconciliation import reconcile_evidence_facts
from buy_or_wait.solver import ALLOWED_METHODS, ALLOWED_STATUSES
from buy_or_wait.spending_changes import SpendingChangeEngine


@dataclass(frozen=True)
class EvaluationFailure:
    category: str
    request_id: str
    detail: str


@dataclass(frozen=True)
class EvaluationResult:
    total_rows: int
    status_counts: Counter
    failures: tuple[EvaluationFailure, ...]

    @property
    def failures_by_category(self) -> Counter:
        return Counter(failure.category for failure in self.failures)


def evaluate(dataset_dir: str | Path = "dataset", output_path: str | Path = "output.csv") -> EvaluationResult:
    index = load_dataset(dataset_dir)
    rows, header_failure = _read_rows(output_path)
    failures: list[EvaluationFailure] = []
    if header_failure:
        failures.append(EvaluationFailure("output_schema", "<file>", header_failure))
    expected_ids = list(index.evaluation_requests_by_id)
    actual_ids = [row.get("request_id", "") for row in rows]
    _check_row_identity(expected_ids, actual_ids, failures)
    rows_by_id = {row.get("request_id", ""): row for row in rows if row.get("request_id") in index.evaluation_requests_by_id}
    for request_id in expected_ids:
        row = rows_by_id.get(request_id)
        if row is None:
            continue
        _evaluate_row(index, request_id, row, failures)
    return EvaluationResult(len(rows), Counter(row.get("affordability_status", "") for row in rows), tuple(failures))


def write_report(result: EvaluationResult, report_path: str | Path = "evaluation_report.md") -> None:
    by_category = result.failures_by_category
    examples: dict[str, list[str]] = defaultdict(list)
    for failure in result.failures:
        if len(examples[failure.category]) < 5:
            examples[failure.category].append(failure.request_id)
    lines = [
        "# Evaluation Report",
        "",
        f"- Output rows read: {result.total_rows}",
        f"- Validation failures: {len(result.failures)}",
        "",
        "## Status counts",
        "",
    ]
    for status, count in sorted(result.status_counts.items()):
        lines.append(f"- `{status or '<blank>'}`: {count}")
    lines.extend(["", "## Failures by category", ""])
    if not by_category:
        lines.append("No validator failures were found in this run. This confirms only the implemented deterministic checks; it does not establish hidden-label correctness.")
    else:
        for category, count in sorted(by_category.items()):
            lines.append(f"- `{category}`: {count}; representative request IDs: {', '.join(examples[category])}")
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_rows(output_path: str | Path) -> tuple[list[dict[str, str]], str | None]:
    with Path(output_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header_error = None if tuple(reader.fieldnames or ()) == OUTPUT_COLUMNS else "header/order differs from required output schema"
        return list(reader), header_error


def _check_row_identity(expected: list[str], actual: list[str], failures: list[EvaluationFailure]) -> None:
    counts = Counter(actual)
    for request_id in expected:
        if counts[request_id] == 0:
            failures.append(EvaluationFailure("missing_request_id", request_id, "no output row"))
        elif counts[request_id] > 1:
            failures.append(EvaluationFailure("duplicate_request_id", request_id, "more than one output row"))
    for request_id in actual:
        if request_id not in expected:
            failures.append(EvaluationFailure("unknown_request_id", request_id or "<blank>", "not present in requests.csv"))


def _evaluate_row(index, request_id: str, row: dict[str, str], failures: list[EvaluationFailure]) -> None:
    request = index.evaluation_requests_by_id[request_id]
    profile = index.profiles_by_user_id[request.user_id]
    amount = _decimal(row.get("amount_safe_to_pay", ""), "amount_safe_to_pay", request_id, failures)
    if amount is not None and not Decimal("0") <= amount <= request.requested_amount:
        failures.append(EvaluationFailure("amount_safe_to_pay_bounds", request_id, "outside [0, requested_amount]"))
    status, method = row.get("affordability_status", ""), row.get("recommended_payment_method", "")
    if status not in ALLOWED_STATUSES:
        failures.append(EvaluationFailure("invalid_affordability_status", request_id, status))
    if method not in ALLOWED_METHODS:
        failures.append(EvaluationFailure("invalid_payment_method", request_id, method))
    earliest = _date(row.get("earliest_date_for_full_payment", ""), "earliest_date_for_full_payment", request_id, failures)
    if status == "affordable_now" and earliest != request.request_date:
        failures.append(EvaluationFailure("affordable_now_earliest_date", request_id, "must equal request_date"))
    payments = _payments(row.get("payment_plan", ""), request_id, failures)
    changes = _changes(row.get("spending_changes_needed", ""), request_id, failures)
    if payments is None or amount is None or changes is None:
        return
    _check_method_shape(method, payments, request, index, request_id, failures)
    normalized = normalize_user_events(index, request.user_id)
    facts = EvidenceProcessor(index).extract_facts_for_request(request_id)
    normalized = reconcile_evidence_facts(index, request.user_id, normalized, facts)
    safe_amount = calculate_amount_safe_to_pay(
        starting_balance=profile.current_available_balance, minimum_balance_to_keep=profile.minimum_balance_to_keep,
        normalized_events=normalized, request_date=request.request_date, requested_amount=request.requested_amount,
    )
    if amount != safe_amount:
        failures.append(EvaluationFailure("amount_safe_to_pay_mismatch", request_id, f"output {amount} != recomputed {safe_amount}"))
    recomputed_earliest = find_earliest_safe_full_payment_date(
        starting_balance=profile.current_available_balance, minimum_balance_to_keep=profile.minimum_balance_to_keep,
        normalized_events=normalized, request_date=request.request_date, requested_amount=request.requested_amount,
    )
    if earliest != recomputed_earliest:
        failures.append(EvaluationFailure("earliest_full_payment_mismatch", request_id, "does not match deterministic capacity scan"))
    _check_changes(changes, profile, normalized, request, request_id, failures)
    plan = _rebuild_plan(method, payments, changes, index, request)
    if plan is not None and method != "not_recommended":
        validation = PlanValidator().validate(
            plan=plan, request=request, profile=profile, payment_options=index.payment_options_by_request_id.get(request_id, ()),
            normalized_events=normalized, amount_safe_to_pay=safe_amount, earliest_full_payment_date=recomputed_earliest,
        )
        if "minimum_balance_breached" in validation.errors:
            failures.append(EvaluationFailure("minimum_balance_breach", request_id, "recommended plan breaches floor"))
        if not validation.completes_by_deadline:
            failures.append(EvaluationFailure("desired_completion_deadline", request_id, "plan does not complete by deadline"))
        if validation.errors:
            failures.append(EvaluationFailure("plan_validation", request_id, ", ".join(validation.errors)))
    recommendation = Recommendation(status, method, row.get("payment_plan", ""), row.get("spending_changes_needed", ""))
    explanation_facts = build_explanation_facts(
        profile=profile, request=request, normalized_events=normalized, amount_safe_to_pay=safe_amount,
        recommendation=recommendation, earliest_full_payment_date=recomputed_earliest,
    )
    if not validate_explanation(row.get("decision_explanation", ""), explanation_facts):
        failures.append(EvaluationFailure("unsupported_explanation_fact", request_id, "explanation is outside closed verified facts"))


def _decimal(value: str, field: str, request_id: str, failures: list[EvaluationFailure]) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        failures.append(EvaluationFailure("invalid_money", request_id, field))
        return None


def _date(value: str, field: str, request_id: str, failures: list[EvaluationFailure]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        failures.append(EvaluationFailure("malformed_date", request_id, field))
        return None


def _payments(value: str, request_id: str, failures: list[EvaluationFailure]) -> tuple[ScheduledPayment, ...] | None:
    if value == "none":
        return ()
    parsed: list[ScheduledPayment] = []
    for token in value.split("|"):
        try:
            when_text, amount_text = token.split(":", 1)
            payment = ScheduledPayment(date.fromisoformat(when_text), Decimal(amount_text), "output")
        except (ValueError, InvalidOperation):
            failures.append(EvaluationFailure("payment_plan_format", request_id, token))
            return None
        if payment.amount <= Decimal("0"):
            failures.append(EvaluationFailure("invalid_payment_amount", request_id, token))
        if parsed and payment.payment_date < parsed[-1].payment_date:
            failures.append(EvaluationFailure("payment_plan_chronology", request_id, token))
        parsed.append(payment)
    return tuple(parsed)


def _changes(value: str, request_id: str, failures: list[EvaluationFailure]) -> tuple[SpendingChange, ...] | None:
    if value == "none":
        return ()
    parsed: list[SpendingChange] = []
    for token in value.split("|"):
        pieces = token.split(":")
        try:
            if len(pieces) == 2 and pieces[0] == "stop":
                parsed.append(SpendingChange(pieces[1], "stop", date.min))
            elif len(pieces) == 3 and pieces[0] == "reduce_to":
                parsed.append(SpendingChange(pieces[1], "reduce_to", date.min, Decimal(pieces[2])))
            else:
                raise ValueError
        except (ValueError, InvalidOperation):
            failures.append(EvaluationFailure("spending_change_format", request_id, token))
            return None
    return tuple(parsed)


def _check_method_shape(method, payments, request, index, request_id, failures) -> None:
    total = sum((payment.amount for payment in payments), Decimal("0"))
    if method == "not_recommended" and payments:
        failures.append(EvaluationFailure("fallback_payment_plan", request_id, "not_recommended requires none"))
    if method in {"full_payment", "wait"} and (len(payments) != 1 or total != request.requested_amount):
        failures.append(EvaluationFailure("payment_plan_total", request_id, "full/wait plan must be one requested-amount payment"))
    if method == "partial_payment":
        if len(payments) != 2:
            failures.append(EvaluationFailure("partial_payment_count", request_id, "requires exactly two payments"))
        if total != request.requested_amount:
            failures.append(EvaluationFailure("partial_payment_total", request_id, "payments must sum to request"))
    if method == "installments":
        schedule = tuple((payment.payment_date, payment.amount) for payment in payments)
        supplied = []
        for option in index.payment_options_by_request_id.get(request_id, ()):
            interval = option.payment_frequency_days or 0
            supplied.append(tuple((option.first_payment_date + timedelta(days=interval * i), option.payment_amount) for i in range(option.number_of_payments)))
        if schedule not in supplied:
            failures.append(EvaluationFailure("installment_option_mismatch", request_id, "schedule is not supplied"))


def _check_changes(changes, profile, normalized, request, request_id, failures) -> None:
    adjusted = tuple(SpendingChange(change.event_id, change.action, request.request_date, change.new_amount) for change in changes)
    errors = SpendingChangeEngine().validate_changes(
        changes=adjusted, profile=profile, normalized_events=normalized, request_date=request.request_date,
    )
    for error in errors:
        category = "spending_change_conflict" if "twice" in error else "invalid_spending_change"
        failures.append(EvaluationFailure(category, request_id, error))


def _rebuild_plan(method, payments, changes, index, request):
    request_id = request.request_id
    effective_changes = tuple(
        SpendingChange(change.event_id, change.action, request.request_date, change.new_amount)
        for change in changes
    )
    if method == "not_recommended":
        return PaymentPlan("not_recommended", (), Decimal("0"), None, Decimal("0"), True)
    if method in {"full_payment", "installments"}:
        for option in index.payment_options_by_request_id.get(request_id, ()):
            interval = option.payment_frequency_days or 0
            schedule = tuple(ScheduledPayment(option.first_payment_date + timedelta(days=interval * i), option.payment_amount, f"option:{option.payment_option_id}:{i + 1}") for i in range(option.number_of_payments))
            if option.payment_method == method and tuple((p.payment_date, p.amount) for p in schedule) == tuple((p.payment_date, p.amount) for p in payments):
                return PaymentPlan(method, schedule, option.total_payable_amount, option.payment_option_id, option.financing_fee, spending_changes=effective_changes)
        return None
    return PaymentPlan(method, payments, sum((p.amount for p in payments), Decimal("0")), None, Decimal("0"), spending_changes=effective_changes)


if __name__ == "__main__":
    result = evaluate()
    write_report(result)
    print(f"Evaluated {result.total_rows} rows; failures={len(result.failures)}; report=evaluation_report.md")
