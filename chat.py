"""Terminal testing interface for the existing deterministic Buy or Wait agent.

This module deliberately delegates every financial decision to the production
pipeline.  It only presents already computed records and asks fact-bounded
follow-up questions about the selected request.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from buy_or_wait.capacity import find_earliest_safe_full_payment_date  # noqa: E402
from buy_or_wait.evidence import EvidenceProcessor, model_adapter_from_environment  # noqa: E402
from buy_or_wait.forecast import forecast_balance, get_minimum_projected_balance, is_plan_safe  # noqa: E402
from buy_or_wait.loaders import DatasetIndex, RequestContext, load_dataset  # noqa: E402
from buy_or_wait.models import PaymentPlan, ScheduledPayment, SpendingChange  # noqa: E402
from buy_or_wait.normalization import normalize_user_events  # noqa: E402
from buy_or_wait.plans import PlanGenerator, PlanValidator  # noqa: E402
from buy_or_wait.ranking import choose_best_plan  # noqa: E402
from buy_or_wait.reconciliation import reconcile_evidence_facts  # noqa: E402
from buy_or_wait.solver import SolvedRequest, _add_spending_change_variants, solve_request  # noqa: E402


LINE = "-" * 50
COMMANDS = "help, list, select <request_id>, summary, forecast, plan, explanation, sources [request_id], reset, exit"
_PAYMENT_TOKEN = re.compile(r"^(\d{4}-\d{2}-\d{2}):([0-9]+(?:\.[0-9]+)?)$")


def _money(amount: Decimal, currency: str) -> str:
    # Keep the fallback ASCII-friendly for common Windows terminal encodings.
    symbols = {"INR": "INR ", "USD": "$", "EUR": "EUR ", "ZAR": "R", "IDR": "Rp "}
    return f"{symbols.get(currency, currency + ' ')}{format(amount, 'f')}"


def _format_date(value: date | None) -> str:
    return value.isoformat() if value is not None else "not forecast safe within 90 days"


@dataclass(frozen=True)
class SelectedRequest:
    context: RequestContext
    result: SolvedRequest
    facts: tuple
    normalized_events: tuple
    displayed_plan: PaymentPlan
    forecast: object


class BuyOrWaitChat:
    """Presentation layer around the real dataset and existing solver."""

    def __init__(self, dataset_dir: str | Path = ROOT / "dataset", *, debug: bool = False) -> None:
        self.index: DatasetIndex = load_dataset(dataset_dir)
        self.debug = debug
        self.evidence_processor = EvidenceProcessor(self.index, model_adapter_from_environment())
        self.selected: SelectedRequest | None = None

    @property
    def active_request_id(self) -> str | None:
        return None if self.selected is None else self.selected.context.request.request_id

    @property
    def active_request_context(self) -> RequestContext | None:
        return None if self.selected is None else self.selected.context

    @property
    def active_request_result(self) -> SolvedRequest | None:
        return None if self.selected is None else self.selected.result

    def list_requests(self, limit: int | None = None) -> str:
        requests = tuple(self.index.evaluation_requests_by_id.values())
        if limit is not None:
            requests = requests[:limit]
        lines = [f"Available evaluation requests ({len(self.index.evaluation_requests_by_id)} total):"]
        for request in requests:
            currency = self.index.profiles_by_user_id[request.user_id].home_currency
            lines.append(f"{request.request_id} | {request.request_type} | {_money(request.requested_amount, currency)} | due {request.desired_completion_date.isoformat()}")
        if limit is not None and len(self.index.evaluation_requests_by_id) > limit:
            lines.append(f"... use select <request_id>; showing first {limit}.")
        return "\n".join(lines)

    def select(self, request_id: str) -> str:
        request_id = request_id.strip()
        if request_id not in self.index.evaluation_requests_by_id:
            return f"Unknown evaluation request ID: {request_id or '<empty>'}. Type 'list' to see available requests."
        try:
            self.selected = self._build_selected_request(request_id)
        except Exception as exc:  # source/data failures are reported without ending the chat
            return f"Agent error while solving {request_id}: {type(exc).__name__}: {exc}"
        return f"ACTIVE REQUEST: {request_id}\n" + self.summary()

    def summary(self) -> str:
        selected = self._require_selected()
        if isinstance(selected, str):
            return selected
        request, profile, result = selected.context.request, selected.context.profile, selected.result
        return "\n".join((
            LINE, "REQUEST", LINE,
            f"Request ID: {request.request_id}",
            f"Type: {request.request_type}",
            f"Requested amount: {_money(request.requested_amount, profile.home_currency)}",
            f"Desired completion date: {request.desired_completion_date.isoformat()}",
            LINE, "AGENT DECISION", LINE,
            f"Safe to pay today: {_money(result.amount_safe_to_pay, profile.home_currency)}",
            f"Status: {result.affordability_status}",
            f"Recommended method: {result.recommended_payment_method}",
            f"Earliest full payment: {_format_date(result.earliest_date_for_full_payment)}",
            f"Spending changes: {result.spending_changes_needed}",
            f"Payment plan: {result.payment_plan}",
            f"Explanation: {result.decision_explanation}", LINE,
        ))

    def plan(self) -> str:
        selected = self._require_selected()
        if isinstance(selected, str):
            return selected
        result = selected.result
        if result.payment_plan == "none":
            return "No payment is recommended because no safe eligible plan was found within the forecast."
        return "\n".join((
            "PAYMENT PLAN",
            f"Method: {result.recommended_payment_method}",
            f"Schedule: {result.payment_plan}",
            f"Completion target: {selected.context.request.desired_completion_date.isoformat()}",
            f"Why selected: {self._plan_reason(result)}",
        ))

    def explanation(self) -> str:
        selected = self._require_selected()
        return selected if isinstance(selected, str) else selected.result.decision_explanation

    def forecast(self) -> str:
        selected = self._require_selected()
        if isinstance(selected, str):
            return selected
        context, projected = selected.context, selected.forecast
        lowest = min(projected.days, key=lambda day: day.closing_balance)
        relevant = [day for day in projected.days if day.event_delta or day.payment_delta]
        lines = [
            "90-DAY FORECAST", f"Starting balance: {_money(context.profile.current_available_balance, context.profile.home_currency)}",
            f"Minimum balance: {_money(context.profile.minimum_balance_to_keep, context.profile.home_currency)}",
            f"Lowest projected balance: {_money(get_minimum_projected_balance(projected), context.profile.home_currency)} on {lowest.forecast_date.isoformat()}",
            f"Plan stays above minimum: {'yes' if is_plan_safe(projected) else 'no'}", "Important dated activity:",
        ]
        for day in relevant[:14]:
            sources = ", ".join(day.source_ids) or "balance movement"
            lines.append(f"- {day.forecast_date.isoformat()}: event {format(day.event_delta, 'f')}, payment {format(day.payment_delta, 'f')}; closing {_money(day.closing_balance, context.profile.home_currency)} ({sources})")
        if len(relevant) > 14:
            lines.append(f"- ... {len(relevant) - 14} additional dated movements omitted.")
        return "\n".join(lines)

    def debug_report(self) -> str:
        if not self.debug:
            return "Debug mode is off. Start with: python chat.py --debug"
        selected = self._require_selected()
        if isinstance(selected, str):
            return selected
        context, result, facts, normalized = selected.context, selected.result, selected.facts, selected.normalized_events
        earliest = find_earliest_safe_full_payment_date(
            starting_balance=context.profile.current_available_balance, minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=normalized, request_date=context.request.request_date, requested_amount=context.request.requested_amount,
        )
        baseline = PlanGenerator().generate(request=context.request, profile=context.profile, payment_options=context.payment_options, amount_safe_to_pay=result.amount_safe_to_pay, earliest_full_payment_date=earliest)
        validator = PlanValidator()
        validations = {plan: validator.validate(plan=plan, request=context.request, profile=context.profile, payment_options=context.payment_options, normalized_events=normalized, amount_safe_to_pay=result.amount_safe_to_pay, earliest_full_payment_date=earliest) for plan in baseline}
        candidates = baseline if any(value.is_valid and value.completes_by_deadline for value in validations.values()) else _add_spending_change_variants(baseline_plans=baseline, profile=context.profile, normalized_events=normalized, request_date=context.request.request_date)
        if candidates is not baseline:
            validations.update({plan: validator.validate(plan=plan, request=context.request, profile=context.profile, payment_options=context.payment_options, normalized_events=normalized, amount_safe_to_pay=result.amount_safe_to_pay, earliest_full_payment_date=earliest) for plan in candidates if plan not in validations})
        chosen = choose_best_plan(plans=candidates, validations=validations, profile=context.profile)
        lines = ["DEBUG (DECISION-RELEVANT FACTS ONLY)", f"Active request: {context.request.request_id}", f"Active user: {context.request.user_id}", f"Relevant raw events: {len(context.events)}", f"Relevant messages: {len(context.messages)}", f"Relevant images: {len(context.images)}", f"Payment options: {len(context.payment_options)}", f"Extracted facts: {len(facts)}", f"Candidate plans: {len(candidates)}"]
        for fact in facts:
            lines.append(f"- fact {fact.fact_type} for {fact.related_event_id or 'unlinked'} from {fact.source_id}")
        rendered_plans: set[PaymentPlan] = set()
        for plan in candidates:
            if plan in rendered_plans:
                continue
            rendered_plans.add(plan)
            validation = validations[plan]
            if validation.is_valid and validation.completes_by_deadline:
                state = "accepted"
            else:
                reasons = list(validation.errors)
                if not validation.completes_by_deadline:
                    reasons.append("does not complete by deadline")
                state = "rejected: " + ", ".join(reasons)
            lines.append(f"- {plan.method} ({plan.payment_option_id or 'no option'}): {state}")
        lines.append(f"Selected plan: {chosen.method} ({chosen.payment_option_id or 'no option'})")
        lines.append("")
        lines.append(self._sources_for_selected(selected))
        return "\n".join(lines)

    def answer_question(self, question: str) -> str:
        selected = self._require_selected()
        if isinstance(selected, str):
            return selected
        question = question.strip().lower()
        result, context = selected.result, selected.context
        if not question:
            return "Please ask a question or type 'help'."
        if any(term in question for term in ("source", "which file", "provenance")):
            return self._sources_for_selected(selected)
        if "message" in question:
            return self._message_answer(selected)
        if any(term in question for term in ("which event", "what event", "financial event", "events affected", "upcoming transaction", "upcoming expense", "expenses affecting", "affecting the decision")):
            return self._events_answer(selected)
        if any(term in question for term in ("forecast", "what happens to my balance", "after paying", "projected balance")):
            return self.forecast()
        if any(term in question for term in ("current balance", "my balance", "available balance")):
            return f"Current available balance in financial_profiles.csv: {_money(context.profile.current_available_balance, context.profile.home_currency)}."
        if any(term in question for term in ("minimum balance", "minimum keep", "balance floor")):
            return f"Minimum balance to keep: {_money(context.profile.minimum_balance_to_keep, context.profile.home_currency)}."
        if any(term in question for term in ("upcoming income", "income coming", "salary")):
            return self._upcoming_answer(selected, direction="credit", label="income")
        if any(term in question for term in ("recurring expense", "recurring spending")):
            return self._recurring_expenses_answer(selected)
        if any(term in question for term in ("safe", "how much", "pay today")):
            return f"The deterministic 90-day calculation says {_money(result.amount_safe_to_pay, context.profile.home_currency)} is safe to pay today before any optional spending changes."
        if any(term in question for term in ("when", "full amount", "full payment", "afford later", "what if i wait")):
            return f"Earliest safe full-payment date: {_format_date(result.earliest_date_for_full_payment)}."
        if any(term in question for term in ("installment", "payment option", "options available")):
            options = [option for option in context.payment_options if option.payment_method == "installments"]
            if not options:
                return "The available data contains no installment option for this request."
            rendered = "; ".join(f"{option.payment_option_id}: {option.number_of_payments} payments of {_money(option.payment_amount, context.profile.home_currency)}" for option in options)
            return f"Available installment options: {rendered}. Recommended method: {result.recommended_payment_method}."
        if any(term in question for term in ("spending", "reduce", "cut", "change")):
            return f"Required spending changes in the selected plan: {result.spending_changes_needed}."
        if any(term in question for term in ("plan", "schedule")):
            return self.plan()
        if any(term in question for term in ("why", "explain", "afford", "recommend", "method")):
            return f"{result.decision_explanation}\n\nWhy this recommendation: {self._plan_reason(result)}"
        return "The available request, profile, events, evidence, payment options, and computed decision do not establish an answer to that question. Try 'summary', 'forecast', 'plan', or 'explanation'."

    def handle(self, text: str) -> tuple[str, bool]:
        command = text.strip()
        if not command:
            return "Please enter a command, a request ID, or a question.", True
        lowered = command.lower()
        if lowered in {"exit", "quit"}:
            return "Goodbye.", False
        if lowered == "help":
            return f"Commands: {COMMANDS}. After selecting a request, ask a plain-language question about its computed result.", True
        if lowered == "list":
            return self.list_requests(), True
        if lowered == "summary":
            return self.summary(), True
        if lowered == "forecast":
            return self.forecast(), True
        if lowered == "plan":
            return self.plan(), True
        if lowered == "explanation":
            return self.explanation(), True
        if lowered == "sources":
            selected = self._require_selected()
            return (selected if isinstance(selected, str) else self._sources_for_selected(selected)), True
        if lowered.startswith("sources "):
            request_id = command.split(None, 1)[1].strip()
            return self.sources(request_id), True
        if lowered == "debug":
            return self.debug_report(), True
        if lowered == "reset":
            self.selected = None
            return "Selection cleared. Enter a request ID or type 'list'.", True
        if lowered.startswith("select "):
            return self.select(command.split(None, 1)[1]), True
        if self.selected is None:
            if command in self.index.evaluation_requests_by_id:
                return self.select(command), True
            return "No request is selected. Type 'list' or 'select <request_id>' before asking a question.", True
        return self.answer_question(command), True

    def _require_selected(self) -> SelectedRequest | str:
        return self.selected if self.selected is not None else "No request is selected. Type 'list' or 'select <request_id>'."

    def sources(self, request_id: str) -> str:
        """Show factual source provenance without changing the active request."""
        if request_id not in self.index.evaluation_requests_by_id:
            return f"Unknown evaluation request ID: {request_id or '<empty>'}. Type 'list' to see available requests."
        if self.selected is not None and self.selected.context.request.request_id == request_id:
            return self._sources_for_selected(self.selected)
        context = self.index.get_request_context(request_id)
        facts = self.evidence_processor.extract_facts_for_request(request_id)
        return self._sources_report(context, facts, ())

    def _build_selected_request(self, request_id: str) -> SelectedRequest:
        """Compute once at selection time; all normal follow-ups reuse this state."""
        context = self.index.get_request_context(request_id)
        result = solve_request(request_id, self.index, evidence_processor=self.evidence_processor)
        facts = self.evidence_processor.extract_facts_for_request(request_id)
        normalized = reconcile_evidence_facts(
            self.index, context.request.user_id, normalize_user_events(self.index, context.request.user_id), facts,
        )
        plan = self._display_plan(result, context.request.request_date)
        projected = forecast_balance(
            starting_balance=context.profile.current_available_balance,
            minimum_balance_to_keep=context.profile.minimum_balance_to_keep,
            normalized_events=normalized,
            request_date=context.request.request_date,
            spending_changes=plan.spending_changes,
            proposed_payments=plan.payments,
        )
        return SelectedRequest(context, result, facts, normalized, plan, projected)

    def _sources_for_selected(self, selected: SelectedRequest) -> str:
        return self._sources_report(selected.context, selected.facts, self._affected_event_ids(selected))

    def _sources_report(self, context: RequestContext, facts: tuple, event_ids: tuple[str, ...]) -> str:
        request, profile = context.request, context.profile
        lines = [LINE, f"SOURCES FOR {request.request_id}", LINE]
        lines.extend((
            "1. dataset/requests.csv",
            f"   request_id: {request.request_id}; user_id: {request.user_id}",
            "   fields used: request date, requested amount, completion date, partial-payment setting, request text",
            "2. dataset/financial_profiles.csv",
            f"   user_id: {profile.user_id}",
            "   fields used: home currency, available balance, minimum balance, protected/flexible categories, payment preferences",
        ))
        if event_ids:
            lines.extend(("3. dataset/financial_events.csv", f"   user_id: {request.user_id}", "   forecast event_ids: " + ", ".join(event_ids)))
        elif context.events:
            preview = ", ".join(event.event_id for event in context.events[:12])
            lines.extend(("3. dataset/financial_events.csv", f"   user_id: {request.user_id}", f"   context event_ids (not a forecast-use claim): {preview}"))
        if context.payment_options:
            lines.extend(("4. dataset/request_payment_options.csv", f"   request_id: {request.request_id}", "   payment_option_ids: " + ", ".join(option.payment_option_id for option in context.payment_options)))
        foreign = [event for event in context.events if event.event_id in event_ids and event.currency != profile.home_currency and event.amount is not None]
        if foreign:
            lines.extend(("5. dataset/exchange_rates.csv", "   used for dated conversion of foreign-currency event records when forecast-eligible."))
        message_facts = [fact for fact in facts if fact.source_kind == "message"]
        if message_facts:
            lines.append("6. dataset/messages.csv")
            lines.extend(f"   message_id: {fact.source_id}; related_event_id: {fact.related_event_id or 'none'}; fact: {fact.fact_type}" for fact in message_facts)
        image_facts = [fact for fact in facts if fact.source_kind == "image"]
        if image_facts:
            lines.append("7. dataset/images.csv / dataset/media/images")
            lines.extend(f"   image_id: {fact.source_id}; related_event_id: {fact.related_event_id or 'none'}; fact: {fact.fact_type}" for fact in image_facts)
        return "\n".join(lines)

    @staticmethod
    def _affected_event_ids(selected: SelectedRequest) -> tuple[str, ...]:
        event_ids: list[str] = []
        available = {event.event_id for event in selected.normalized_events}
        for day in selected.forecast.days:
            for source_id in day.source_ids:
                event_id = source_id.removeprefix("recurrence:").split(":", 1)[0]
                if event_id in available and event_id not in event_ids:
                    event_ids.append(event_id)
        return tuple(event_ids)

    def _events_answer(self, selected: SelectedRequest) -> str:
        affected = self._affected_event_ids(selected)
        by_id = {event.event_id: event for event in selected.normalized_events}
        if not affected:
            return "No supplied financial-event record produced a dated movement in the selected 90-day forecast."
        lines = ["FINANCIAL EVENTS AFFECTING THE FORECAST"]
        for event_id in affected[:12]:
            event = by_id[event_id]
            amount = "unknown" if event.amount_in_home_currency is None else _money(event.amount_in_home_currency, event.home_currency)
            lines.append(f"- financial_events.csv | event_id: {event_id} | {event.effective_date.isoformat()} | {event.direction} | {amount} | {event.description}")
        if len(affected) > 12:
            lines.append(f"- ... {len(affected) - 12} additional forecast events omitted.")
        return "\n".join(lines)

    def _message_answer(self, selected: SelectedRequest) -> str:
        facts = [fact for fact in selected.facts if fact.source_kind == "message"]
        if not facts:
            return "No message produced a validated financial fact for this active request; messages did not alter the computed decision."
        return "\n".join(["MESSAGES WITH VALIDATED FACTS"] + [f"- messages.csv | message_id: {fact.source_id} | related_event_id: {fact.related_event_id or 'none'} | {fact.fact_type}" for fact in facts])

    def _upcoming_answer(self, selected: SelectedRequest, *, direction: str, label: str) -> str:
        events = [event for event in selected.normalized_events if event.event_id in self._affected_event_ids(selected) and event.direction == direction]
        if not events:
            return f"The active 90-day forecast contains no supplied {label} event contributing to the result."
        return "\n".join([f"UPCOMING {label.upper()}"] + [f"- event_id: {event.event_id}; {event.effective_date.isoformat()}; {_money(event.amount_in_home_currency or Decimal('0'), event.home_currency)}; {event.description}" for event in events[:8]])

    def _recurring_expenses_answer(self, selected: SelectedRequest) -> str:
        events = [event for event in selected.normalized_events if event.event_id in self._affected_event_ids(selected) and event.is_recurring and event.direction == "debit"]
        if not events:
            return "The active 90-day forecast contains no recurring debit event with a source record to list."
        return "\n".join(["RECURRING EXPENSES IN THE FORECAST"] + [f"- event_id: {event.event_id}; {_money(event.amount_in_home_currency or Decimal('0'), event.home_currency)}; {event.description}" for event in events[:8]])

    @staticmethod
    def _plan_reason(result: SolvedRequest) -> str:
        if result.recommended_payment_method == "not_recommended":
            return "No safe eligible plan completed the request within the forecast and deadline."
        if result.spending_changes_needed != "none":
            return "It is the selected safe plan after the listed permitted spending changes."
        return "It is the highest-ranked safe eligible plan under the deterministic challenge rules."

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


def run_chat(chat: BuyOrWaitChat, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> int:
    def emit(text: str) -> None:
        try:
            output_fn(text)
        except UnicodeEncodeError:
            output_fn(text.encode("ascii", errors="replace").decode("ascii"))

    emit("=" * 50)
    emit("BUY OR WAIT - AI FINANCIAL AGENT")
    emit("=" * 50)
    emit("Enter a request ID to test, or type 'list' to see available requests.")
    emit("Type 'help' for commands or 'exit' to quit.")
    while True:
        try:
            text = input_fn("\n> ")
        except (EOFError, KeyboardInterrupt):
            emit("\nGoodbye.")
            return 0
        try:
            response, keep_running = chat.handle(text)
        except Exception as exc:  # defensive UI boundary: preserve prompt after malformed user input
            response, keep_running = f"Chat error: {type(exc).__name__}: {exc}", True
        emit(response)
        if not keep_running:
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Test the existing Buy or Wait solver interactively.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset", help="Challenge dataset directory.")
    parser.add_argument("--debug", action="store_true", help="Show concise candidate/fact diagnostics after selection.")
    args = parser.parse_args()
    try:
        return run_chat(BuyOrWaitChat(args.dataset_dir, debug=args.debug))
    except Exception as exc:
        print(f"Unable to start chat: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
