# Buy or Wait? — Implementation Plan

## Objective and constraints

Build a terminal-runnable Python program that reads only `dataset/`, evaluates all requests deterministically, and writes root `output.csv`. The only nondeterministic/LLM-capable component is a bounded evidence extractor. It may interpret language and images and draft explanations, but it cannot calculate money, simulate balances, choose a plan, or override validation.

Use the standard library for the core (`csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `pathlib`, `typing`, `json`, `argparse`, `unittest`). No LangChain, LangGraph, vector database, database, multi-agent framework, or cloud service is needed. Optional evidence-provider integration must be isolated behind one interface and disabled by default.

## Proposed project structure

```text
.
├── README.md
├── ARCHITECTURE_ANALYSIS.md
├── IMPLEMENTATION_PLAN.md
├── dataset/                         # supplied, read only
├── output.csv                       # generated at runtime; not created until implementation
├── code/
│   ├── buy_or_wait/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── models.py
│   │   ├── parsing.py
│   │   ├── loaders.py
│   │   ├── evidence.py
│   │   ├── reconciliation.py
│   │   ├── recurrence.py
│   │   ├── forecast.py
│   │   ├── plans.py
│   │   ├── validation.py
│   │   ├── ranking.py
│   │   ├── explanations.py
│   │   ├── pipeline.py
│   │   └── output.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── fixtures/
│   │   ├── test_parsing.py
│   │   ├── test_evidence.py
│   │   ├── test_reconciliation.py
│   │   ├── test_recurrence.py
│   │   ├── test_forecast.py
│   │   ├── test_plans.py
│   │   ├── test_validation.py
│   │   ├── test_ranking.py
│   │   ├── test_output.py
│   │   └── test_samples.py
│   └── evaluation/
│       ├── evaluator_entrypoint.py  # compatibility wrapper for evaluate.py
│       └── usage_report.md          # final-run report; populated at release
└── .gitignore
```

The package is deliberately flat. Each module owns one rule family and exposes pure functions where practical. The generated `output.csv`, local cache, and logs stay outside the package.

## Internal canonical data model

All currency values are `Decimal`; all calendar values are `date`; timestamps are timezone-aware `datetime`. No arithmetic uses `float`. CSV strings are converted at the boundary and never leak into financial logic.

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

Money = Decimal
Currency = str
```

### Enumerations

```python
class Direction(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    NON_CASH = "non_cash"

class EventStatus(str, Enum):
    SETTLED = "settled"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNREALIZED = "unrealized"

class Flexibility(str, Enum):
    FIXED = "fixed"
    REDUCIBLE = "reducible"
    STOPPABLE = "stoppable"
    REDUCIBLE_OR_STOPPABLE = "reducible_or_stoppable"

class PaymentMethod(str, Enum):
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    INSTALLMENTS = "installments"
    WAIT = "wait"
    NOT_RECOMMENDED = "not_recommended"
```

### User/profile

```python
@dataclass(frozen=True)
class UserProfile:
    user_id: str
    home_currency: Currency
    current_available_balance: Money
    minimum_balance_to_keep: Money
    financial_priorities: tuple[str, ...]
    protected_categories: frozenset[str]
    reducible_categories: frozenset[str]
    stoppable_categories: frozenset[str]
    accepted_payment_methods: frozenset[PaymentMethod]
    max_installment_months: int | None
```

### Request

```python
@dataclass(frozen=True)
class PurchaseRequest:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Money
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str
```

### Financial event and normalized cash movement

```python
@dataclass(frozen=True)
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: Direction
    amount: Money | None
    currency: Currency
    event_date: date
    settlement_date: date | None
    status: EventStatus
    linked_event_id: str | None
    flexibility: Flexibility
    minimum_allowed_amount: Money | None

@dataclass(frozen=True)
class CashMovement:
    source_event_id: str
    effective_date: date
    amount_home_currency: Money       # signed: credit positive, debit negative
    category: str
    cash_treatment: str               # settled, reserved_pending_debit, scheduled_confirmed
    is_recurring_candidate: bool
```

`FinancialEvent` preserves source truth. `CashMovement` is produced only after evidence, lifecycle reconciliation, status eligibility, and dated conversion. It is the sole historical/future event representation consumed by the simulator.

### Messages, images, and extracted evidence

```python
@dataclass(frozen=True)
class Message:
    message_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    sent_at: datetime
    source_type: str
    text: str

@dataclass(frozen=True)
class ImageReference:
    image_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    path: Path

class EvidenceFactKind(str, Enum):
    EVENT_AMOUNT = "event_amount"
    SALARY_AMOUNT = "salary_amount"
    SALARY_DATE = "salary_date"
    RECURRING_EXPENSE_AMOUNT = "recurring_expense_amount"
    INCOME_ENDED = "income_ended"
    CONFIRMED_CREDIT = "confirmed_credit"
    PENDING_CREDIT = "pending_credit"
    CANCELLATION = "cancellation"
    SELF_TRANSFER = "self_transfer"
    NON_CASH_VALUE = "non_cash_value"

@dataclass(frozen=True)
class EvidenceFact:
    kind: EvidenceFactKind
    value: str                         # normalized literal; Money/date parsed by consumer
    user_id: str
    request_id: str | None
    related_event_id: str | None
    effective_date: date | None
    source_id: str                     # message_id or image_id
    source_timestamp: datetime | None
    source_type: str
    rationale: str                     # concise extraction trace, never an instruction
```

Facts are an allowlist, not an arbitrary model response. The evidence layer returns only schema-valid facts associated with an actual user/request/event. The deterministic reconciliation layer decides whether a fact applies.

### Payment option, schedule, and spending change

```python
@dataclass(frozen=True)
class PaymentOption:
    payment_option_id: str
    request_id: str
    method: PaymentMethod              # full_payment or installments in source data
    payment_amount: Money
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: Money
    total_payable_amount: Money

@dataclass(frozen=True)
class ScheduledPayment:
    payment_date: date
    amount: Money

@dataclass(frozen=True)
class SpendingChange:
    action: str                        # "stop" or "reduce_to"
    event_id: str
    new_amount: Money | None
```

### Forecast and candidate plan

```python
@dataclass(frozen=True)
class ForecastInput:
    profile: UserProfile
    request_date: date
    historical_events: tuple[FinancialEvent, ...]
    reconciled_movements: tuple[CashMovement, ...]
    evidence_facts: tuple[EvidenceFact, ...]
    spending_changes: tuple[SpendingChange, ...] = ()
    candidate_payments: tuple[ScheduledPayment, ...] = ()
    horizon_days: int = 90

@dataclass(frozen=True)
class DailyBalance:
    balance_date: date
    opening_balance: Money
    cash_delta: Money
    closing_balance: Money
    source_ids: tuple[str, ...]

@dataclass(frozen=True)
class ForecastResult:
    horizon_start: date
    horizon_end: date
    daily_balances: tuple[DailyBalance, ...]
    minimum_observed_balance: Money
    first_floor_breach_date: date | None

@dataclass(frozen=True)
class CandidatePlan:
    method: PaymentMethod
    payments: tuple[ScheduledPayment, ...]
    total_paid: Money
    payment_option_id: str | None
    spending_changes: tuple[SpendingChange, ...]
    completes_by_deadline: bool
```

### Validated decision and output row

```python
@dataclass(frozen=True)
class PlanValidation:
    is_valid: bool
    violations: tuple[str, ...]
    forecast: ForecastResult | None

@dataclass(frozen=True)
class Decision:
    request_id: str
    amount_safe_to_pay: Money
    affordability_status: str
    recommended_payment_method: PaymentMethod
    payment_plan: tuple[ScheduledPayment, ...]
    earliest_date_for_full_payment: date | None
    spending_changes: tuple[SpendingChange, ...]
    explanation_facts: Mapping[str, str]
```

## Module responsibilities

| Module | Responsibilities | Must not do |
|---|---|---|
| `constants.py` | Output order, horizon, allowed values, decimal quantization policy. | Read files or make decisions. |
| `models.py` | Enums/dataclasses above. | Parse raw CSV or perform I/O. |
| `parsing.py` | Strict CSV-to-type conversion, pipe-list parsing, `Decimal`/date/timestamp validation. | Apply business/evidence rules. |
| `loaders.py` | Read every dataset CSV, resolve image paths, index joins, validate referential integrity. | Forecast or choose plans. |
| `evidence.py` | Extract/cache schema-valid facts from messages/images; expose provider interface. | Decide cash safety or alter output directly. |
| `reconciliation.py` | Apply facts, status rules, linked-event de-duplication, self-transfer treatment, dated conversion; emit `CashMovement`. | Infer plan rankings. |
| `recurrence.py` | Infer repeatable cash streams from reconciled history and generate conservative projected movements. Fixed expense/income streams require matching descriptions; contractual subscriptions/debt payments and explicitly flexible categories retain stable category grouping. | Treat one-off events or unrelated category descriptions as recurring without support. |
| `forecast.py` | Deterministic daily 90-day simulation and safe-amount/date queries. | Parse evidence or select methods. |
| `plans.py` | Enumerate full, partial, instalment, wait, and bounded spending-change candidates. | Declare a plan valid without validator. |
| `validation.py` | Validate eligibility, schedule, deadline, spending changes, floor, and output invariants. | Rank alternatives. |
| `ranking.py` | Sort only valid candidates by challenge order; select winner. | Recalculate balance. |
| `explanations.py` | Turn verified `Decision.explanation_facts` into concise output text; optional LLM phrasing behind interface. | Introduce facts or modify numeric decision fields. |
| `output.py` | Format exact CSV fields and validate complete row set/header. | Perform financial logic. |
| `pipeline.py` | Compose the modules for one request and full batch. | Contain duplicated domain rules. |
| `main.py` | Parse CLI options, invoke pipeline, return exit code. | Embed domain logic. |

## Raw CSV to `output.csv` data flow

```text
CSV files + PNG files
        │
        ▼
strict loaders / canonical parsing
        │  DatasetIndex(profiles, requests, events, options, messages, images, rates)
        ▼
bounded evidence extraction
        │  EvidenceFact[] + provenance
        ▼
event reconciliation and settlement-date conversion
        │  CashMovement[]
        ▼
recurrence inference + future stream projection
        │
        ├─────────────── baseline ForecastInput ───────────────┐
        ▼                                                      │
90-day simulator ──► amount_safe_to_pay / earliest full date   │
                                                               ▼
candidate generator (full / partial / instalments / wait / changes)
        ▼
validator (rules + 90-day simulation) ──► valid candidates only
        ▼
challenge-order ranker
        ▼
verified fact-based explanation generator
        ▼
output formatter + whole-file validator ──► root output.csv
```

For each request, the pipeline uses its profile, events, evidence in user/request/event scope, payment options, and needed exchange-rate rows. The current profile balance is always the starting balance; historical settled events establish recurrence but are not subtracted from it again.

## 90-day forecasting interface

```python
class ForecastEngine(Protocol):
    def simulate(self, forecast_input: ForecastInput) -> ForecastResult:
        """Return daily balances from request_date through request_date + 90 days."""

    def max_safe_payment_today(
        self,
        forecast_input: ForecastInput,
        requested_amount: Money,
    ) -> Money:
        """Largest request-date payment preserving the floor without spending changes."""

    def earliest_safe_full_payment_date(
        self,
        forecast_input: ForecastInput,
        full_amount: Money,
    ) -> date | None:
        """First date in horizon where a one-off full payment is floor-safe."""
```

Implementation rules:

* Materialize a daily calendar inclusive of the request date and 90 subsequent days.
* Use signed `CashMovement`s plus recurrent projections and candidate payments.
* Apply all known same-day deltas as one deterministic net cash delta; the day is safe only if its closing balance meets the floor. If a required intraday ordering cannot be established, use the safer temporary ordering in the movement builder.
* `max_safe_payment_today` must be found with deterministic monotonic search over money precision (binary search plus quantization), not an LLM estimate.
* `earliest_safe_full_payment_date` evaluates candidate full-payment dates chronologically under the no-optional-change baseline.
* Return all daily balances and source IDs, so failed plans explain precisely why they are invalid.

## Payment-plan generation interface

```python
class PlanGenerator(Protocol):
    def generate(
        self,
        request: PurchaseRequest,
        profile: UserProfile,
        payment_options: Sequence[PaymentOption],
        amount_safe_to_pay: Money,
        earliest_full_date: date | None,
        eligible_changes: Sequence[SpendingChange],
    ) -> tuple[CandidatePlan, ...]:
        """Generate syntactically legal plans only; validation establishes safety."""
```

Generation is bounded and deterministic:

1. Create full-payment plan from the supplied full option if profile permits it.
2. Create every supplied instalment schedule whose method is accepted and count is within `max_installment_months`.
3. Create a partial plan only if all hard partial conditions are met.
4. Create a wait plan only if baseline earliest full date exists after the request date and full payment is accepted.
5. Generate spending-change variants only from historical recurring events that pass flexibility, category preference, protection, and minimum-amount filters. Search singles, pairs, then triples; never produce both actions for the same event.

The generator does not adjust dates, invent an offer, or change an instalment amount. The full payment amount for a plan is `total_payable_amount`; partial payment always sums to `requested_amount` per the challenge rule.

## Plan validation interface

```python
class PlanValidator(Protocol):
    def validate(
        self,
        candidate: CandidatePlan,
        request: PurchaseRequest,
        profile: UserProfile,
        payment_options: Sequence[PaymentOption],
        baseline_forecast: ForecastInput,
    ) -> PlanValidation:
        """Return every violation and a simulation result for otherwise valid plans."""
```

The validator checks, in deterministic order:

1. method accepted by profile;
2. payment dates chronological, method-specific schedule rules, and exact option match for instalments;
3. partial-plan permission, two-payment shape, positive/current safe first payment, exact remainder, and completion deadline;
4. instalment max-count policy, full completion deadline, and total payable amount;
5. spending-change count, action format, distinctness, recurrence, flexibility, profile permission, protected category exclusion, and reduction floor;
6. complete-by-deadline status;
7. 90-day forecast with payments/changes, requiring no minimum-balance breach; and
8. output-domain invariants.

Plans that cannot complete by deadline may remain useful only as diagnostic capacity information; they cannot be returned as a safe immediate candidate.

## Plan-ranking interface

```python
class PlanRanker(Protocol):
    def rank(
        self,
        candidates: Sequence[CandidatePlan],
        validations: Mapping[CandidatePlan, PlanValidation],
    ) -> CandidatePlan | None:
        """Select one valid plan using the published lexicographic ordering."""
```

Filter invalid plans first. The ascending rank tuple is:

```python
(
    0 if candidate.completes_by_deadline else 1,
    0 if not candidate.spending_changes else 1,
    candidate.total_paid,
    candidate.payments[0].payment_date,
    len(candidate.payments),
    numeric_suffix(candidate.payment_option_id) if candidate.payment_option_id else -1,
)
```

The final option-ID component applies only when earlier criteria tie. A partial or wait plan has no source option ID; implementation should use a documented sentinel only after all meaningful prior criteria are equal. The ranker returns `None` when no candidate is valid; pipeline then creates `not_affordable` / `not_recommended` with `payment_plan=none`.

## LLM/evidence extraction interface

```python
class EvidenceExtractor(Protocol):
    def extract_message_facts(self, message: Message) -> tuple[EvidenceFact, ...]: ...
    def extract_image_facts(
        self, image: ImageReference, linked_event: FinancialEvent
    ) -> tuple[EvidenceFact, ...]: ...

class EvidenceStore(Protocol):
    def get(self, source_id: str) -> tuple[EvidenceFact, ...] | None: ...
    def put(self, source_id: str, facts: tuple[EvidenceFact, ...]) -> None: ...
```

The default first version may use a checked-in, human-reviewed `evidence_facts.json` compiled from these 215 messages and 16 images, keeping the production decision run fully deterministic. If an optional model provider is enabled, it receives only the source content and a schema-constrained task:

* extract facts from the `EvidenceFactKind` allowlist;
* cite source ID and exact supporting fragment/visual label in `rationale`;
* return no recommendation, instruction, calculation, safety score, or output-row field.

`evidence.py` rejects facts with unknown IDs, bad types, impossible dates/currencies, or unsupported source scope. It never executes text from evidence and never passes a model result directly to `forecast.py` or `plans.py` without reconciliation.

## Final explanation interface

```python
class ExplanationGenerator(Protocol):
    def generate(self, decision: Decision, profile: UserProfile) -> str:
        """Render a concise explanation from verified decision facts only."""
```

Default implementation is templated and deterministic. For example, it uses method, scheduled payments, floor, earliest safe date, and listed spending changes from `Decision.explanation_facts`. An optional LLM rephraser receives a closed fact bundle and must return plain text only; validation rejects numbers/dates/currencies not already present in the bundle. The result never feeds back into the decision engine.

## Pipeline orchestration

```python
def decide_one(request: PurchaseRequest, index: DatasetIndex) -> Decision:
    profile = index.profiles[request.user_id]
    facts = evidence_facts_in_scope(request, index)
    movements = reconcile_events(profile, index.events_by_user[request.user_id], facts, index.rates)
    projected = infer_recurring_movements(profile, movements, facts, request.request_date)
    baseline = ForecastInput(profile, request.request_date, ..., movements + projected, facts)
    safe_amount = forecast.max_safe_payment_today(baseline, request.requested_amount)
    earliest = forecast.earliest_safe_full_payment_date(baseline, request.requested_amount)
    candidates = plans.generate(request, profile, index.options_by_request[request.request_id], safe_amount, earliest, eligible_changes)
    validations = {plan: validator.validate(plan, request, profile, ..., baseline) for plan in candidates}
    winner = ranker.rank(candidates, validations)
    return make_decision(request, safe_amount, earliest, winner, validations)
```

The batch runner calls `decide_one` in request CSV order, renders explanations only after decisions are frozen, writes rows in that same order, and runs a whole-file validator before replacing root `output.csv` atomically.

## Testing strategy

### Unit tests

* Parsing: malformed decimals/dates, blank optional fields, pipe lists, and exact source enums.
* Currency: direct dated lookup, identity conversion, absent-rate error, and settlement-date rather than event-date use.
* Evidence: scope checking, invalid structured model output rejection, message amendment precedence, image amount selection, and instruction-injection resistance.
* Reconciliation: pending debit reservation, pending-credit exclusion, failed/cancelled exclusion, replacement inclusion, refund state, linked valuation exclusion, settled sale, and self-transfer handling.
* Recurrence: repeat cadence detection, non-recurring one-off rejection, conservative variable-spend quantity, and amendment/end-date application.
* Forecast: floor boundary equality, date horizon, existing scheduled cash flows, same-day handling, monotonic safe amount, and earliest date scan.
* Plans: exact instalment expansion for 28/30/31-day cadence, legal/illegal partial plans, max-installment rule, and change enumeration limits.
* Validation/ranking: every invalidity rule plus each pairwise ranking tie-break.
* Output: header/order, decimal rendering, `none` fields, exactly one row per request, and rejected invalid row values.

### Scenario/regression tests

Create small synthetic fixtures for all status/lifecycle anomalies and all plan types. Add a regression fixture for each of the 16 blank image amounts and for each message pattern that changes a forecast. Fixtures should contain the minimum data required to make expected balances transparent.

### Sample-set acceptance tests

`test_samples.py` runs the pipeline against `sample_requests.csv` and asserts all structural fields. During staged development, first require exact method/status/plan/date correctness and then tighten exact `amount_safe_to_pay`, spending changes, and explanation facts. Any intentional divergence requires a documented rule-based reason, never a hidden hardcoded sample exception.

### Full-dataset and release checks

Run these before packaging:

```bash
python -m unittest discover -s code/tests -v
python main.py --dataset-dir dataset --output-path output.csv
python evaluate.py --output-path output.csv
```

The release validator verifies 250 rows, exact header/order, unique request IDs, allowed enums, money bounds, plan chronology/sums, option equality, date/deadline compliance, allowable changes, and no simulated floor breach. If an optional LLM was used for the final evidence/explanation run, populate `evaluation/usage_report.md` from recorded provider/model/call/token/cost metrics; otherwise report zero model calls explicitly.

## Implementation sequence

1. Add models, parsers, dataset loaders, and strict schema tests.
2. Add rates, evidence registry interface, and reviewed source-fact fixtures.
3. Implement reconciliation and event-lifecycle tests.
4. Implement recurrence rules and 90-day simulator with transparent daily-ledger tests.
5. Implement baseline capacity metrics.
6. Implement candidate generation, validation, and ranking.
7. Add output formatting, explanation templates, and sample regression tests.
8. Run full-dataset validation, document runtime, and populate the required usage report.

No application code is created or modified by this plan.
