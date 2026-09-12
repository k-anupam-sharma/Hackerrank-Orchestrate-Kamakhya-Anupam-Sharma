# Buy or Wait? — Engineering Analysis

## Scope and repository state

This repository is a starter submission for HackerRank Orchestrate 2026. The work is to create a deterministic, AI-assisted financial-decision pipeline that emits one prediction for each evaluation request. The supplied evaluation cohort has 250 requests (`request_26` through `request_275`); 25 labelled examples (`request_01` through `request_25`) are available solely to infer the intended decision style and validate an implementation.

The initial application entry-point layout contained multiple wrappers:

* `main.py` — the portable root solver wrapper now used by the documented commands.
* `code/main.py` — a duplicate solver wrapper, removed during the entry-point cleanup.
* `evaluation/main.py` — compatibility wrapper for the independent evaluator, renamed to `evaluation/evaluator_entrypoint.py`.
* `evaluation/usage_report.md` — required final-run model-usage report.

`README.md`, `problem_statement.md`, `AGENTS.md`, all CSV files, and all 16 PNG evidence files were inspected. There is no root-level `output.csv` yet; `dataset/output.csv` is a blank 250-row template. `README.md` requires the eventual program to write the final file to the repository root, not overwrite the dataset template.

## 1. Exact problem to solve

For every row in `dataset/requests.csv`, reconstruct the requesting user's cash position as of `request_date`, forecast it for 90 days, and recommend a safe way to fulfill (or decline) that specific request.

The output must have exactly these columns, in exactly this order:

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

The forecast must incorporate confirmed future cash movements, defensibly inferred recurring income and spending, pending debits, payment-plan instalments, and relevant amendments in messages/images. Any recommended plan must preserve the user’s `minimum_balance_to_keep` at every point in the next 90 days. The task is affordability, not investment advice or asset-price forecasting.

The output choices are constrained:

* `affordability_status`: `affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable`.
* `recommended_payment_method`: `full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended`.
* `amount_safe_to_pay`: numeric and within `[0, requested_amount]`; it is calculated before optional spending changes.

## 2. Dataset inventory and every CSV schema

### `financial_profiles.csv` — 275 rows, one per user

This is the canonical user-level configuration, joined by `user_id`.

| Column | Meaning |
|---|---|
| `user_id` | Unique user identifier. There are 275 users. |
| `home_currency` | Currency in which balances, requests, output amounts, and final affordability are expressed. Actual values: `INR`, `ZAR`, `IDR`, `USD`, `EUR`. |
| `current_available_balance` | Starting available cash at the relevant request evaluation point; do not recompute it from historical transactions. |
| `minimum_balance_to_keep` | Hard cash floor that every forecast and plan must retain. |
| `financial_priorities` | Pipe-delimited priorities (for example `education|debt_repayment` or `emergency_savings|travel`). It informs personalization, but cannot override explicit safety rules. |
| `expense_categories_to_protect` | Pipe-delimited categories that must not be sacrificed. |
| `expense_categories_user_is_willing_to_reduce` | Pipe-delimited categories in which a qualifying recurring expense may be reduced. Blank means none. |
| `expense_categories_user_is_willing_to_stop` | Pipe-delimited categories in which a qualifying recurring expense may be stopped. Blank means none. |
| `payment_methods_user_will_consider` | Pipe-delimited eligible immediate methods: `full_payment`, `partial_payment`, and/or `installments`. |
| `max_installment_months` | Maximum acceptable number of instalments; blank means the user will not consider instalments. Values present are 2–12, excluding 1. |

### `financial_events.csv` — 25,342 rows

This is the cash-flow and history ledger, joined by `user_id`; some rows link to a prior lifecycle record through `linked_event_id`.

| Column | Meaning |
|---|---|
| `event_id` | Unique ledger event identifier. It is also the target for message/image evidence and spending-change directives. |
| `user_id` | Owner; joins to profile and request. |
| `event_type` | Business event class. Actual values/counts: `expense` 20,525; `subscription` 2,488; `income` 1,696; `debt_payment` 567; `investment_purchase` 29; `refund` 22; `investment_valuation` 10; `investment_sale` 5. |
| `description` | Human-readable descriptor; fixed expense/income recurrence streams require a matching description, while contractual subscription/debt streams and explicitly flexible categories use their stable category identity. |
| `category` | Spending/income category. Actual categories: rent, utilities, education, debt_repayment, music_subscription, delivery_membership, salary, groceries, transport, dining, shopping, housing, insurance, healthcare, entertainment, cloud_storage, streaming, gym, family_support, work_expense, investment, windfall. |
| `direction` | `debit`, `credit`, or `non_cash`. Actual counts: 23,609, 1,723, and 10 respectively. |
| `amount` | Event amount in `currency`. Sixteen actual rows are blank and must be read from their linked PNG, never converted to zero. |
| `currency` | Event currency (all five home-currency set values occur). Foreign cash events need dated conversion. |
| `event_date` | Event/authorization/origin date. |
| `settlement_date` | Cash-effective date for a usable or reserved cash movement. Ten rows have no settlement date. |
| `status` | Lifecycle state: `settled` (25,148), `pending` (71), `scheduled` (70), `cancelled` (22), `failed` (21), `unrealized` (10). |
| `linked_event_id` | Optional pointer to the earlier record in the same lifecycle; 58 rows contain one. It does not by itself establish cash-flow treatment. |
| `flexibility` | `fixed`, `reducible`, `stoppable`, or `reducible_or_stoppable`. |
| `minimum_allowed_amount` | Minimum remaining amount for a reducible expense; blank for events that are not reducible. |

### `exchange_rates.csv` — 134 rows

| Column | Meaning |
|---|---|
| `rate_date` | Date for which the fixed conversion is valid. |
| `from_currency` | Source currency. Only EUR and USD appear as sources. |
| `to_currency` | Target currency. EUR, USD, INR, IDR, and ZAR appear. |
| `rate` | Multiply the source amount by this fixed rate for that exact directed pair/date. |

There are 39 rate dates and five observed directed pair/rate conventions: EUR→ZAR (20), USD→EUR (0.92), USD→IDR (15,833.33), USD→INR (83.33), and EUR→USD (1.09). The date coverage is deliberately irregular, so lookup must use the supplied rate for the event settlement date and direction, rather than infer or fetch a market rate.

### `requests.csv` — 250 evaluation rows

One output row is required for each row. Actual request types are `family_transfer`, `purchase`, `investment`, `debt_repayment`, `travel`, `housing`, `education`, `emergency_expense`, and `other`.

| Column | Meaning |
|---|---|
| `request_id` | Unique request key; joins to payment options, messages, images, and output. |
| `user_id` | Requesting user; joins to profile/events/evidence. |
| `request_date` | The cash-state and forecast anchor date. |
| `request_type` | Requested commitment category; it does not change the core cash safety test. |
| `requested_amount` | Requested total in the user’s home currency. |
| `desired_completion_date` | Deadline for a plan that claims to complete the request. |
| `allows_partial_payment` | Lowercase `true`/`false`; controls eligibility of a two-payment partial plan. |
| `request_text` | Natural-language phrasing. It can explain intent but cannot override structured constraints. |

### `request_payment_options.csv` — 790 rows

There are 2–4 offers per request (65 requests have two, 180 have three, 30 have four). Every request has one full-payment offer; all other offers are instalments.

| Column | Meaning |
|---|---|
| `payment_option_id` | Unique option ID (`payment_option_01`…`payment_option_790`); its numeric order is the final tie-breaker. |
| `request_id` | Request join key. |
| `payment_method` | Actual values are `full_payment` and `installments`. Partial payment is not a supplied offer. |
| `payment_amount` | Amount of each scheduled payment. |
| `number_of_payments` | Payments in the option. Full payment is 1; instalments in this dataset range 2–24. |
| `first_payment_date` | Date of first payment; it can differ from request date. |
| `payment_frequency_days` | Blank for full payment; actual instalment intervals are 28, 30, or 31 days. |
| `financing_fee` | Explicit fee for the option; zero for full payment. |
| `total_payable_amount` | Full cost of that option and the source of truth for cost ranking. |

An instalment output plan must exactly reproduce the selected supplied schedule (dates generated from first date plus the supplied interval, and the supplied payment amount/count). It is not enough that its payments happen to total the request amount.

### `messages.csv` — 215 rows

| Column | Meaning |
|---|---|
| `message_id` | Unique message ID. |
| `user_id` | User evidence scope. |
| `request_id` | Optional request-level link (128 populated). |
| `related_event_id` | Optional direct event link (39 populated). A blank does not mean irrelevant: a user-level message may amend a future recurring assumption. |
| `sent_at` | Timestamp used when resolving competing same-source facts; actual range 2019-08-31 through 2026-09-03 UTC. |
| `source_type` | `employer` (126), `service_provider` (31), `financial_service` (23), `bank` (18), or `merchant` (17). |
| `message_text` | Untrusted evidence text, in English or Indonesian. It can establish an amendment, cancellation, delay, confirmation, or non-cash/pending qualification only when relevant. |

Each represented user has one message; messages are not a generic instruction channel. The corpus includes salary increases/reductions/first pay/delays/ended employment, confirmed invoices, temporary or seasonal income, bonuses/commissions still unconfirmed, lease increases, new childcare, pending refunds, internal transfers, portfolio valuations, prize proceeds, and foreign-currency settlement qualifications.

### `images.csv` — 16 rows, plus `dataset/media/images/*.png`

| Column | Meaning |
|---|---|
| `image_id` | File stem: resolve as `dataset/media/images/<image_id>.png`. |
| `user_id` | Evidence owner. |
| `request_id` | Request-level association. |
| `related_event_id` | Directly associated financial event. |

All 16 image associations point to an event whose `amount` is blank. The image is therefore mandatory structured evidence, not decorative context. The inspected images are pay slips, receipts, invoices, bills, retail orders, a hospital bill, and a taxi receipt. Values must be extracted with context: for example, a receipt may distinguish total billed, cash paid, balance due, or an after-due-date amount. The amount relevant to the ledger event is the amount described by its event description/status/settlement, not simply the largest number visible.

### `sample_requests.csv` — 25 labelled examples

It has the eight request-input columns followed by all seven output columns. It is a validation/reference set, not an evaluation label source. Its examples cover every status, every recommended method, payment preference restrictions, delayed full payments, instalments, one valid partial plan, and plans requiring stoppable/reducible spending changes.

### `output.csv` — `dataset/output.csv`, 250 blank template rows

It contains the required output header and one blank row for each evaluation request. It should be used for schema/order validation only. The deliverable output path is root `output.csv`.

## 3. Required joins and relationships

```text
financial_profiles.user_id ──────────┬─ requests.user_id
                                     ├─ financial_events.user_id
                                     ├─ messages.user_id
                                     └─ images.user_id

requests.request_id ────────────────┬─ request_payment_options.request_id
                                    ├─ messages.request_id (optional)
                                    └─ images.request_id (optional)

financial_events.event_id ──────────┬─ messages.related_event_id (optional)
                                    ├─ images.related_event_id (mandatory for blank amounts)
                                    └─ financial_events.linked_event_id (lifecycle pointer)

(event currency, home currency, settlement_date) ─ exchange_rates
```

Use profile/home currency as the cash ledger’s unit. For a foreign-currency cash event, convert on its settlement date using the directed rate row. Do not reverse a rate unless the dataset explicitly supplies that direction; do not use an event date, current rate, or live data.

## 4. Actual financial event lifecycles and status treatment

The actual data intentionally includes all status types, lifecycle links, reversals, failed/replacement payments, investment flows, and blank amounts. Relevant examples of linked patterns include:

* settled expense followed by settled refund;
* cancelled authorization followed by settled replacement expense;
* failed debt payment followed by a scheduled replacement debt payment;
* settled investment purchase followed by `unrealized` valuation (not cash);
* settled investment purchase followed by settled investment sale (cash only when settled);
* settled debit followed by an apparently duplicate pending debit; and
* settled expense followed by a pending refund (not available cash yet).

Treatment must be fact- and status-based:

* Reserve a pending debit; it remains a foreseeable outflow.
* Exclude pending credits, pending refunds, bonuses, commissions, lottery/prize proceeds, and unconfirmed provider payout income until settled.
* Exclude failed and cancelled records themselves, while including a separately scheduled/settled replacement if evidence establishes it.
* Exclude `unrealized` and `non_cash` investment valuations from liquidity.
* Include settled cash events at settlement date; include confirmed scheduled salary at its stated settlement date.
* Do not double-count duplicate representations, self-transfers, a cancelled authorization plus replacement, an investment purchase plus valuation, or linked lifecycle records merely because they are both present.

Where conflicting facts exist, enforce the specified order: explicit cancellation/settlement/amendment; newer same-source record; settled record over estimate/forecast; then the financially safer interpretation. The phrase “financially safer” should lower available cash or increase reserved expense, never invent a fact.

## 5. Recurrence and 90-day forecasting

Recurrence is represented implicitly by historical sequences, not by a recurrence column. Historical sequences must support the inference; a one-time purchase, transfer, refund, unusual payment, valuation, or windfall is not recurring merely because it has a familiar category. The implementation keeps contractual subscription/debt streams and explicit flexible categories together, but requires fixed expense/income descriptions to match so unrelated category members are not merged.

The forecast starts at each request’s `request_date` and runs through the next 90 calendar days. It needs a date-ordered cash ledger with:

1. current available balance as opening cash;
2. all future scheduled/pending qualifying movements on their settlement date;
3. recurring income/expenses inferred from prior cadence and amended by later relevant evidence;
4. conservatively forecast essential variable spending, especially protected categories; and
5. candidate request-plan payments.

At every dated movement (and after same-day aggregate/order handled consistently), the balance must be no lower than `minimum_balance_to_keep`. `amount_safe_to_pay` is the largest current-date payment passing this baseline 90-day test, capped at the requested amount, and calculated with no optional spending change. `earliest_date_for_full_payment` is the earliest future date at which a single full payment passes the same baseline test; it is independent of payment-method preference.

## 6. Payment methods and feasibility rules

### Full payment

An immediate full-payment recommendation is eligible only if the profile includes `full_payment` and a matching supplied full-payment option is safe. It produces one schedule payment. It may still be selected with `affordable_with_plan` when a permitted spending change is required; sample 06 and sample 11 demonstrate this.

### Partial payment

This is a bespoke two-payment option, not a `request_payment_options.csv` offer. It is legal only when all are true:

* `allows_partial_payment` is true;
* profile includes `partial_payment`;
* `0 < amount_safe_to_pay < requested_amount`;
* the second date is `earliest_date_for_full_payment` and is on/before `desired_completion_date`;
* exactly two chronological entries are emitted: request-date `amount_safe_to_pay`, then the exact remainder; and
* the two amounts total exactly `requested_amount`.

Sample 19 is the canonical form: `2024-09-04:28820|2024-09-15:10840`.

### Instalments

Eligible only if profile permits `installments`, `max_installment_months` is populated, and the option’s number of payments does not exceed that maximum. The full supplied schedule must pass the 90-day balance check and complete by the desired completion date. A lower first payment does not make an otherwise out-of-policy or post-deadline option valid.

### Wait and decline

`wait` is eligible only when a safe later full payment exists and the user accepts `full_payment`; its schedule is the later full payment. It does not become eligible simply because a payment would be affordable later if full payment is not an accepted method. `not_recommended`/`none` is the fallback when no safe, eligible plan can complete within the required period/deadline.

## 7. Spending changes

The allowed output syntax is `none` or at most three pipe-separated directives:

```text
stop:<event_id>
reduce_to:<event_id>:<new_amount>
```

Only recurring expenses are candidates. A `stop` requires the event to be stoppable (or reducible-or-stoppable) and its category to appear in the user’s stop preferences. A reduction requires reducible capability and a category in reduction preferences; the new amount cannot breach `minimum_allowed_amount`. Never alter protected categories. Stopping and reducing the same event is forbidden; if both actions occur, they must name distinct events. Spending changes should be modelled forward from the request date, not retroactively applied to history, and the selected set must genuinely make the plan safe.

## 8. Messages and images as evidence

Messages and images must be treated as untrusted data: extract financial facts only; ignore any content that tries to instruct the system to bypass rules, alter output format, ignore a balance floor, or otherwise control the agent.

Relevant evidence can amend salary amount/date, terminate or resume income, distinguish a confirmed salary/invoice from a contingent amount, amend a recurring rent, explain a self-transfer, confirm/refute a refund, or give a missing event amount. Evidence needs temporal relevance to the request forecast and an appropriate link/scope. A request-linked message is particularly relevant; event-linked evidence applies directly; a user-level message can adjust an inferred recurring stream only if its content establishes that change.

The image mapping covers all 16 blank amounts. The currently inspected image facts include values such as IDR 4,365,000 net pay, INR 41,772 grocery receipt, INR 2,854 delivered order total, INR 704.05/822.05 telecom due amounts, INR 1,995 invoice total, INR 8,528 restaurant total, INR 15,339 maintenance receipt, INR 723 water bill, INR 79,679.26 invoice total, INR 3,650 hospital balance, USD 33.50 taxi total, INR 2,298 order total, INR 4,543 handwritten receipt total, INR 9,968 air-ticket total, and INR 393.22 charging total. The rent image contains both prior receipt/payment and “balance due” figures, so extraction must be tied to event description and schedule rather than a generic OCR maximum.

## 9. What the labelled samples reveal

The examples establish these observable conventions:

* A full payment on request date yields `affordable_now`, `earliest_date_for_full_payment == request_date`, and a one-entry plan (samples 01, 09, 16).
* Later full payment produces `affordable_later` and a `wait` recommendation only where full payment is user-acceptable (samples 03, 04, 08, 13, 18, 23).
* `amount_safe_to_pay` can be positive even when no completion plan is safe; it remains a baseline capacity metric, not permission to pay (samples 05, 10, 14, 15, 20, 24, 25).
* A full payment aided by a valid spending change is labelled `affordable_with_plan`, while its earliest baseline full-payment date can be later (samples 06 and 11). Sample 21 uses both a stop and a reduction.
* Instalment outputs exactly preserve offered dates/amounts and can be chosen even when full payment is already safe, because user payment preferences govern recommended method while earliest full-payment capacity remains independent (sample 12).
* Financing fees matter: examples pick safe instalments only after eligibility/safety, and explanations give the number, payment amount, first date, and preserved minimum balance.
* Explanations are concise, use the home currency and concrete action, and name the constraint (minimum balance, waiting date, or spending change). They do not narrate unsupported speculation.

## 10. Explicit rules that must be enforced

1. Produce exactly one row per evaluation request and use the exact output column order.
2. Use only participant-facing `dataset/` files for predictions; no organizer-only data or hardcoded labels.
3. Do not use live banking, market, or exchange-rate data.
4. Do not invent income, expenses, payment offers, dates, or other financial facts.
5. Detect recurrence only with supporting history; forecast essential variable expense conservatively.
6. Reserve pending debits; exclude pending credits/refunds, bonuses, commissions, lottery proceeds, investment gains, failed/cancelled transactions, duplicates, and unrealized investments as available cash.
7. Count confirmed salary on settlement date.
8. Convert foreign cash events with supplied directed, dated settlement-date exchange rates.
9. Keep forecast balance at or above `minimum_balance_to_keep` after every projected essential expense or recommended payment through 90 days.
10. Respect protected categories, payment-method preferences, `max_installment_months`, partial-payment permission, and flexible-spending permissions.
11. Instalment plans must exactly match an available option; partial payment has exactly two prescribed payments and must meet the completion deadline.
12. `earliest_date_for_full_payment` is a baseline single-payment capacity date, not a preferred-method date; it equals request date for `affordable_now` and is blank if absent in the forecast period.
13. Apply the specified conflict-resolution order.
14. Rank feasible eligible plans by: deadline completion, no spending changes, lowest total paid, earlier start, fewer payments, then lowest numeric `payment_option_id`.
15. Keep code runnable from a terminal, deterministic where possible, secret-free, and document setup/run steps. Submission additionally needs `code.zip`, root output, chat transcript, and populated `evaluation/usage_report.md`.

## 11. Edge cases and hidden-test traps

* Treat a blank amount as missing evidence, not zero; several blank events are settled, scheduled, or pending and therefore materially affect safety.
* Preserve decimal precision. Use `Decimal` for money, schedule construction, comparison, and CSV formatting; float rounding can invalidate plan totals or exact sample-style amounts.
* The profile balance is the starting state for each request, even though historical events may precede it. Do not subtract historical settled transactions a second time.
* A request/payment deadline may fall inside or outside the 90-day horizon. A claimed completion still must meet its deadline; an unavailable full-payment date is blank when no safe payment occurs within forecast horizon.
* A plan may begin after request date. It must remain safe before, on, and after every payment date, including future essential debits.
* Same-day salary and debits need deterministic ordering/aggregation. Aggregate known same-day cash movements before testing the end-of-day balance, and apply a documented conservative convention for intraday ambiguity.
* A pending debit must be reserved even if its settlement date is later; a pending refund is not usable merely because it is linked to a settled charge.
* A cancelled event can have a valid replacement. Conversely, a linked event is not necessarily a replacement and must not erase a settled cash event without explicit evidence.
* Internal transfer debit/credit pairs must not inflate cash. Investment purchase is an outflow; a valuation is not liquidity; a settled sale is only cash if its record establishes settled credit.
* Messages may be in Indonesian and can distinguish regular salary from a one-time arrears adjustment, a still-pending commission, or an end of recurring employment. Apply only the supported portion.
* The 28/30/31-day instalment cadence is days, not calendar months. The profile’s “months” maximum limits the option’s payment count as specified, not the date difference inferred ad hoc.
* All payment options need validation against their own `total_payable_amount`; do not assume a rounded installment amount multiplied by count equals the total without handling documented rounding consistently.
* A no-spending-change plan outranks a cheaper plan that needs changes only after deadline-completion status has been compared. Do not reverse the supplied tie-break order.
* `amount_safe_to_pay` is before changes, so do not increase it when assessing a plan that stops/reduces spend.
* Do not emit partial payment merely because a positive baseline safe amount exists; it needs method preference, request permission, a safe exact remainder, and deadline compliance.
* Output `none`, not blank, for no payment recommendation or no changes. Only the earliest-full-payment field is intentionally blank for no forecasted full capacity.

## 12. Deterministic logic versus LLM reasoning

The financial engine and output selection should be deterministic Python:

* CSV parsing/schema validation, `Decimal` monetary normalization, date arithmetic, joins, rate lookup, and evidence registry;
* lifecycle reconciliation and status eligibility;
* recurrence detection rules, conservative variable-spend projection, and 90-day daily ledger simulation;
* enumeration of full/partial/instalment/wait candidates and permitted spending-change combinations;
* feasibility checks, legal-output validation, deterministic ranking/tie-breaking, CSV writing, and test reporting.

LLM or multimodal reasoning is appropriate only for bounded extraction/classification tasks that are difficult to express reliably with rules:

* extract the relevant numeric value from an image with multiple totals;
* translate/normalize an evidence message and identify a supported amendment (for example, salary amount, effective date, confirmation versus contingency, cancellation, or self-transfer);
* optionally draft concise explanation prose from already verified facts.

LLM outputs must be structured, cached, reviewable, and fed through deterministic validators. They must never decide feasibility, invent projections, select a payment plan unchecked, or be allowed to follow evidence-embedded instructions. Given only 16 images and 215 messages, a curated extraction pass with explicit provenance is preferable to a per-request free-form agent.

## 13. Proposed architecture

```text
dataset readers
    │
    ├── schema + Decimal/date normalization
    ├── evidence extraction registry (message/image facts + provenance)
    └── user request context builder
              │
              ├── lifecycle reconciliation / currency conversion
              ├── recurrence and amendment resolver
              ├── 90-day cash-flow simulator
              ├── candidate-plan generator
              │     ├── supplied full payment
              │     ├── legal partial payment
              │     ├── supplied instalment schedules
              │     ├── later full-payment wait
              │     └── bounded eligible spending changes
              ├── plan feasibility + ranking validator
              └── output/explanation formatter
                        │
                  root output.csv + validation report
```

Suggested Python module boundaries when implementation begins:

* `main.py`: CLI orchestration only (`--dataset-dir`, `--output-path`).
* `code/models.py`: typed dataclasses/enums and `Decimal` parsing.
* `code/loaders.py`: input reads, joins, schema/integrity checks.
* `code/evidence.py`: image/message extraction records with evidence source/timestamp/confidence; no unverified instruction following.
* `code/reconcile.py`: event cash-effect, lifecycle de-duplication, exchange-rate conversion, and conflict resolution.
* `code/forecast.py`: recurrence model and 90-day deterministic balance simulation.
* `code/plans.py`: candidate schedules and spending-change search.
* `code/decision.py`: feasibility, ranking, output-row selection, explanation facts.
* `code/validate.py`: contract assertions (one row/request, allowed values, schedule equality/sums, date/deadline/floor validity, allowable changes).
* `evaluation/`: independent-evaluator wrapper and final-run token/cost report.

Implementation should first encode baseline rules and sample assertions, then add evidence facts and regression cases for each lifecycle anomaly. A test fixture should prove each output method, blank-image extraction, rate conversion, cancellation/replacement, pending debit/credit handling, salary amendment, recurrence inference, and every ranking tie-break.

## 14. Simplest supported deployment/run mechanism

Use the standard-library-first root entry point `main.py`:

```bash
python3 main.py
```

On Windows, `python main.py` is the portable equivalent. It should read `dataset/`, write root `output.csv`, use no secret or network dependency for deterministic core logic, and document any optional OCR/LLM setup separately. This directly matches the README and challenge contract: `python package_submission.py` builds `code.zip` with the runnable source, prompts/configuration, and `evaluation/usage_report.md`; submit it with root `output.csv` and `log.txt` as the chat transcript.

No application code has been modified during this analysis.
