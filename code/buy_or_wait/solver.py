"""End-to-end deterministic solver for the Buy or Wait output contract."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping

from .capacity import calculate_amount_safe_to_pay, find_earliest_safe_full_payment_date
from .evidence import EvidenceProcessor, local_ocr_from_environment
from .explanations import build_explanation_facts, generate_explanation
from .loaders import OUTPUT_COLUMNS, DatasetIndex, load_dataset
from .models import PaymentPlan, PlanValidationResult, Recommendation
from .normalization import normalize_user_events
from .plans import PlanGenerator, PlanValidator
from .ranking import choose_best_plan, map_plan_to_recommendation
from .reconciliation import reconcile_evidence_facts
from .spending_changes import SpendingChangeEngine


ALLOWED_STATUSES = frozenset({"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"})
ALLOWED_METHODS = frozenset({"full_payment", "partial_payment", "installments", "wait", "not_recommended"})
_PAYMENT = re.compile(r"^(\d{4}-\d{2}-\d{2}):([-+]?[0-9]+(?:\.[0-9]+)?)$")
_STOP = re.compile(r"^stop:([^:|]+)$")
_REDUCE = re.compile(r"^reduce_to:([^:|]+):([-+]?[0-9]+(?:\.[0-9]+)?)$")


class OutputValidationError(ValueError):
    """A solver row does not conform to the public submission schema."""


@dataclass(frozen=True)
class SolvedRequest:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: date | None
    spending_changes_needed: str
    decision_explanation: str

    def as_csv_row(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "amount_safe_to_pay": format(self.amount_safe_to_pay, "f"),
            "affordability_status": self.affordability_status,
            "recommended_payment_method": self.recommended_payment_method,
            "payment_plan": self.payment_plan,
            "earliest_date_for_full_payment": "" if self.earliest_date_for_full_payment is None else self.earliest_date_for_full_payment.isoformat(),
            "spending_changes_needed": self.spending_changes_needed,
            "decision_explanation": self.decision_explanation,
        }


def solve_request(request_id: str, index: DatasetIndex, *, evidence_processor: EvidenceProcessor | None = None) -> SolvedRequest:
    """Solve one request using only deterministic financial logic and bounded facts."""
    context = index.get_request_context(request_id)
    request, profile = context.request, context.profile
    # Facts are extracted deterministically. Unknown image amounts remain unknown
    # rather than being fabricated or treated as zero.
    processor = evidence_processor or EvidenceProcessor(index, local_ocr_from_environment())
    facts = processor.extract_facts_for_request(request_id)
    normalized_events = reconcile_evidence_facts(
        index, request.user_id, normalize_user_events(index, request.user_id), facts,
    )
    safe_amount = calculate_amount_safe_to_pay(
        starting_balance=profile.current_available_balance,
        minimum_balance_to_keep=profile.minimum_balance_to_keep,
        normalized_events=normalized_events,
        request_date=request.request_date,
        requested_amount=request.requested_amount,
    )
    earliest = find_earliest_safe_full_payment_date(
        starting_balance=profile.current_available_balance,
        minimum_balance_to_keep=profile.minimum_balance_to_keep,
        normalized_events=normalized_events,
        request_date=request.request_date,
        requested_amount=request.requested_amount,
    )
    baseline_plans = PlanGenerator().generate(
        request=request, profile=profile, payment_options=context.payment_options,
        amount_safe_to_pay=safe_amount, earliest_full_payment_date=earliest,
    )
    validator = PlanValidator()
    baseline_validations = {
        plan: validator.validate(
            plan=plan, request=request, profile=profile, payment_options=context.payment_options,
            normalized_events=normalized_events, amount_safe_to_pay=safe_amount,
            earliest_full_payment_date=earliest,
        )
        for plan in baseline_plans
    }
    # A safe no-change plan outranks every spending-change plan. Avoid an
    # expensive variant search whenever it cannot alter the recommendation.
    if any(result.is_valid and result.completes_by_deadline for result in baseline_validations.values()):
        plans, validations = baseline_plans, baseline_validations
    else:
        plans = _add_spending_change_variants(
            baseline_plans=baseline_plans, profile=profile, normalized_events=normalized_events,
            request_date=request.request_date,
        )
        validations = dict(baseline_validations)
        validations.update({
            plan: validator.validate(
                plan=plan, request=request, profile=profile, payment_options=context.payment_options,
                normalized_events=normalized_events, amount_safe_to_pay=safe_amount,
                earliest_full_payment_date=earliest,
            )
            for plan in plans if plan not in validations
        })
    selected = choose_best_plan(plans=plans, validations=validations, profile=profile)
    rendered = map_plan_to_recommendation(
        plan=selected, request=request, earliest_full_payment_date=earliest,
    )
    return SolvedRequest(
        request_id=request.request_id,
        amount_safe_to_pay=safe_amount,
        affordability_status=rendered.affordability_status,
        recommended_payment_method=rendered.recommended_payment_method,
        payment_plan=rendered.payment_plan,
        earliest_date_for_full_payment=earliest,
        spending_changes_needed=rendered.spending_changes_needed,
        decision_explanation=generate_explanation(
            build_explanation_facts(
                profile=profile, request=request, normalized_events=normalized_events,
                amount_safe_to_pay=safe_amount, recommendation=rendered,
                earliest_full_payment_date=earliest,
            ),
        ),
    )


def solve_all_requests(index: DatasetIndex, *, evidence_processor: EvidenceProcessor | None = None) -> tuple[SolvedRequest, ...]:
    """Solve exactly the evaluation rows in the source CSV order."""
    processor = evidence_processor or EvidenceProcessor(index, local_ocr_from_environment())
    return tuple(
        solve_request(request.request_id, index, evidence_processor=processor)
        for request in index.evaluation_requests_by_id.values()
    )


def write_output_csv(rows: Iterable[SolvedRequest], output_path: str | Path, index: DatasetIndex) -> None:
    """Validate rows before writing the public submission CSV atomically enough for local runs."""
    materialized = tuple(rows)
    validate_output_rows(materialized, index)
    path = Path(output_path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(row.as_csv_row() for row in materialized)


def solve_dataset(dataset_dir: str | Path, output_path: str | Path) -> tuple[SolvedRequest, ...]:
    """Load, solve, validate, and write an entire challenge dataset."""
    index = load_dataset(dataset_dir)
    rows = solve_all_requests(index)
    write_output_csv(rows, output_path, index)
    return rows


def validate_output_csv(output_path: str | Path, index: DatasetIndex) -> None:
    """Read and validate a completed output.csv, including header order."""
    path = Path(output_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
            raise OutputValidationError("output.csv header does not exactly match required column order")
        raw_rows = tuple(reader)
    rows = tuple(_row_from_csv(raw) for raw in raw_rows)
    validate_output_rows(rows, index)


def validate_output_rows(rows: Iterable[SolvedRequest], index: DatasetIndex) -> None:
    """Validate every output invariant that can be checked without re-solving it."""
    materialized = tuple(rows)
    expected_ids = tuple(index.evaluation_requests_by_id)
    received_ids = tuple(row.request_id for row in materialized)
    if received_ids != expected_ids:
        raise OutputValidationError("output request IDs must exactly match requests.csv in source order")
    if len(received_ids) != len(set(received_ids)):
        raise OutputValidationError("output contains duplicate request_id values")
    for row in materialized:
        request = index.evaluation_requests_by_id[row.request_id]
        if not (Decimal("0") <= row.amount_safe_to_pay <= request.requested_amount):
            raise OutputValidationError(f"{row.request_id}: amount_safe_to_pay is out of bounds")
        if row.affordability_status not in ALLOWED_STATUSES:
            raise OutputValidationError(f"{row.request_id}: invalid affordability_status")
        if row.recommended_payment_method not in ALLOWED_METHODS:
            raise OutputValidationError(f"{row.request_id}: invalid recommended_payment_method")
        if row.earliest_date_for_full_payment is not None and not isinstance(row.earliest_date_for_full_payment, date):
            raise OutputValidationError(f"{row.request_id}: malformed earliest_date_for_full_payment")
        _validate_payment_fields(row, request, index)
        _validate_spending_changes(row, index)
        if not row.decision_explanation.strip():
            raise OutputValidationError(f"{row.request_id}: decision_explanation is empty")


def _add_spending_change_variants(
    *, baseline_plans: tuple[PaymentPlan, ...], profile, normalized_events, request_date: date,
) -> tuple[PaymentPlan, ...]:
    engine = SpendingChangeEngine()
    actions = engine.candidate_actions(
        profile=profile, normalized_events=normalized_events, request_date=request_date,
    )
    variants: list[PaymentPlan] = list(baseline_plans)
    for plan in baseline_plans:
        if plan.method == "not_recommended":
            continue
        for candidate in engine.generate_safe_candidates(
            profile=profile, normalized_events=normalized_events, request_date=request_date,
            proposed_payments=plan.payments,
            candidate_actions=actions,
        ):
            variants.append(replace(plan, spending_changes=candidate.changes))
    return tuple(dict.fromkeys(variants))


def _validate_payment_fields(row: SolvedRequest, request, index: DatasetIndex) -> None:
    if row.recommended_payment_method == "not_recommended":
        if row.affordability_status != "not_affordable" or row.payment_plan != "none":
            raise OutputValidationError(f"{row.request_id}: fallback fields are inconsistent")
        return
    if row.payment_plan == "none":
        raise OutputValidationError(f"{row.request_id}: a recommended method requires a payment plan")
    payments = _parse_payment_plan(row.payment_plan, row.request_id)
    if payments[-1][0] > request.desired_completion_date:
        raise OutputValidationError(f"{row.request_id}: payment plan misses desired_completion_date")
    total = sum((amount for _, amount in payments), Decimal("0"))
    if row.recommended_payment_method in {"full_payment", "partial_payment", "wait"} and total != request.requested_amount:
        raise OutputValidationError(f"{row.request_id}: payment plan total does not match requested amount")
    if row.recommended_payment_method == "partial_payment" and len(payments) != 2:
        raise OutputValidationError(f"{row.request_id}: partial payment must have exactly two payments")
    if row.recommended_payment_method == "partial_payment":
        if row.affordability_status != "affordable_with_plan" or payments[0][0] != request.request_date:
            raise OutputValidationError(f"{row.request_id}: partial-payment status or first date is invalid")
        if row.earliest_date_for_full_payment is None or payments[1][0] != row.earliest_date_for_full_payment:
            raise OutputValidationError(f"{row.request_id}: partial-payment remainder date is invalid")
    if row.recommended_payment_method == "wait":
        if row.affordability_status != "affordable_later" or len(payments) != 1:
            raise OutputValidationError(f"{row.request_id}: wait status or schedule is invalid")
        if row.earliest_date_for_full_payment is None or payments[0][0] != row.earliest_date_for_full_payment:
            raise OutputValidationError(f"{row.request_id}: wait date is invalid")
    if row.recommended_payment_method in {"full_payment", "installments"}:
        expected = tuple(payments)
        matches_option = False
        for option in index.payment_options_by_request_id.get(row.request_id, ()):
            if option.payment_method != row.recommended_payment_method:
                continue
            interval = option.payment_frequency_days or 0
            option_schedule = tuple(
                (option.first_payment_date + timedelta(days=interval * number), option.payment_amount)
                for number in range(option.number_of_payments)
            )
            if expected == option_schedule:
                matches_option = True
                break
        if not matches_option:
            raise OutputValidationError(f"{row.request_id}: payment plan does not match a supplied option")
    if row.affordability_status == "affordable_now" and row.earliest_date_for_full_payment != request.request_date:
        raise OutputValidationError(f"{row.request_id}: affordable_now needs request-date full capacity")


def _validate_spending_changes(row: SolvedRequest, index: DatasetIndex) -> None:
    if row.spending_changes_needed == "none":
        return
    actions = row.spending_changes_needed.split("|")
    if not 1 <= len(actions) <= 3:
        raise OutputValidationError(f"{row.request_id}: invalid number of spending changes")
    profile = index.profiles_by_user_id[index.evaluation_requests_by_id[row.request_id].user_id]
    normalized = {event.event_id: event for event in normalize_user_events(index, profile.user_id)}
    seen: set[str] = set()
    for action in actions:
        stop, reduce = _STOP.match(action), _REDUCE.match(action)
        if stop:
            event_id = stop.group(1)
        elif reduce:
            event_id = reduce.group(1)
            if Decimal(reduce.group(2)) < Decimal("0"):
                raise OutputValidationError(f"{row.request_id}: negative spending reduction")
        else:
            raise OutputValidationError(f"{row.request_id}: malformed spending change")
        if event_id in seen:
            raise OutputValidationError(f"{row.request_id}: same spending event changed twice")
        seen.add(event_id)
        event = normalized.get(event_id)
        if event is None or not event.is_recurring or not event.is_flexible or event.category in profile.protected_categories:
            raise OutputValidationError(f"{row.request_id}: ineligible spending change")


def _parse_payment_plan(value: str, request_id: str) -> tuple[tuple[date, Decimal], ...]:
    parsed: list[tuple[date, Decimal]] = []
    for part in value.split("|"):
        match = _PAYMENT.match(part)
        if match is None:
            raise OutputValidationError(f"{request_id}: malformed payment plan")
        try:
            payment_date, amount = date.fromisoformat(match.group(1)), Decimal(match.group(2))
        except (ValueError, InvalidOperation) as exc:
            raise OutputValidationError(f"{request_id}: malformed payment plan") from exc
        if amount <= Decimal("0"):
            raise OutputValidationError(f"{request_id}: payment amount must be positive")
        if parsed and payment_date < parsed[-1][0]:
            raise OutputValidationError(f"{request_id}: payment plan is not chronological")
        parsed.append((payment_date, amount))
    return tuple(parsed)


def _row_from_csv(raw: Mapping[str, str]) -> SolvedRequest:
    try:
        earliest = date.fromisoformat(raw["earliest_date_for_full_payment"]) if raw["earliest_date_for_full_payment"] else None
        amount = Decimal(raw["amount_safe_to_pay"])
    except (ValueError, InvalidOperation) as exc:
        raise OutputValidationError("output.csv contains malformed money or date values") from exc
    return SolvedRequest(
        request_id=raw["request_id"], amount_safe_to_pay=amount,
        affordability_status=raw["affordability_status"],
        recommended_payment_method=raw["recommended_payment_method"], payment_plan=raw["payment_plan"],
        earliest_date_for_full_payment=earliest, spending_changes_needed=raw["spending_changes_needed"],
        decision_explanation=raw["decision_explanation"],
    )
