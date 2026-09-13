# Final calculation audit

## Scope and conclusion

This pass traced the complete deterministic path from normalized events through the 90-day simulator, capacity, earliest-date search, plan validation, spending-change variants, ranking, and solver output. The current implementation is deterministic and passes its automated tests and the official output schema/evaluation. It does **not** reproduce all public sample labels: after the general fixes, 4 of 25 samples match every structured decision field and 4 of 25 match the safe amount. The remaining differences are reported rather than hidden or patched by request ID.

## Root causes addressed

1. `amount_safe_to_pay` previously reran a binary search over complete forecasts. The search was deterministic but hid the additive one-time-payment invariant and repeatedly rebuilt the same baseline.
2. There was no named reusable baseline forecast. Capacity now computes one no-payment/no-change baseline and applies the proven direct formula.
3. Unlinked payroll messages were extracted only in a narrow literal-"confirmed" case and then dropped by reconciliation. Explicit bounded messages such as “regular salary resumes on …” and “next salary is reduced …” now produce or amend source-backed salary evidence. They cannot change a balance, floor, policy, or payment option.
4. A dated, explicitly recurring salary confirmation is projected monthly from its evidence-backed anchor; an undated salary notice amends the latest recurring source amount. A singular “first salary” is not projected indefinitely.

The earlier recurrence correction remains in force: ordinary streams require an exact repeated description and regular history; contractual subscription/debt streams use category identity; variable non-payroll income is not treated as guaranteed; explicit final/last payroll terminates a stream; stable monthly streams use calendar month advancement.

## Correct mathematical model

For request date `D`, let `F(t)` be the daily closing balance from a fixed baseline forecast with no request payment and no optional spending changes, for `t = D ... D+89`. Let `M` be `minimum_balance_to_keep` and `R` be `requested_amount`. A request-date one-time payment `P` is an additive debit in the same date bucket as eligible events. Therefore every daily closing balance after applying it is `F(t) - P`, including request-date closing balance. Thus:

`min_t(F(t) - P) = min_t(F(t)) - P`

and the cent-quantized capacity is:

`max(0, min(R, baseline_minimum - M))`, rounded down to the configured money quantum.

This proof depends on the payment being one-time, on cash flows being independent of `P`, and on same-day entries being aggregated before closing balance. Those conditions are now explicit in `calculate_baseline_forecast`, `forecast_balance`, and tests. Earliest full-payment date remains a date-by-date safety search because a later payment affects only the suffix of the horizon.

## Forecast semantics audited

- Horizon is exactly request date through request date + 89 days.
- `current_available_balance` is the opening balance on request date; historical rows before the date are not replayed as direct cash flows.
- Eligible settled cash, pending debits that reserve cash, and eligible scheduled debits/salary credits enter once at their effective date.
- Pending credits, failed, cancelled, duplicate, unrealized/non-cash, amount-unknown, and unsupported scheduled credits are excluded.
- Recurring projections are source-backed. Direct future rows and recurring projections are kept distinct; the event audit records both.
- Foreign amounts use the dated directed exchange rate for the settlement/conversion date and `Decimal` arithmetic.
- Spending changes are not used to inflate `amount_safe_to_pay`; they are separate bounded plan variants.
- Plan safety is the minimum daily closing balance being at least the required floor, including every proposed payment.

## Request-date timing and conservation

Income, expense, pending debit, and request-payment entries on the same date are summed into one daily delta. This makes their internal order immaterial and prevents a hidden sequencing choice. The generated [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv) has 2,290 rows and records, for every sample request, event ID, dates, amount, direction, status, cash treatment, inclusion, and reason. It is the double-counting diagnostic table. [MANUAL_SAMPLE_CALCULATIONS.md](MANUAL_SAMPLE_CALCULATIONS.md) documents the 25 baseline minima and safe-amount derivations.

## Request 01 reconstruction

`user_01` starts at ZAR 58,481.10 with a ZAR 18,000 floor. The baseline minimum is ZAR 43,938.97 on 2024-05-28. Capacity is `43,938.97 - 18,000 = 25,938.97`, capped at the requested ZAR 25,256, so the independent safe amount is ZAR 25,256.00. After the request-date payment, the minimum is ZAR 18,682.97, still above the floor. The solver independently returns `affordable_now`, `full_payment`, `2024-03-03:25256`, earliest date `2024-03-03`, and no spending changes. No completed sample answer is passed into the solver.

## Sample benchmark

The final independent sample run processed all 25 requests. Structured comparison uses Decimal equality for money, payment amounts, and reductions; labels are loaded only after solving.

- Exact structured matches: **4 / 25** (`request_01`, `request_09`, `request_12`, `request_16`).
- Exact safe-amount matches: **4 / 25**.
- Structured mismatches: **21 requests / 44 fields**.
- Full field-level details: [AFTER_FIX_COMPARISON.md](AFTER_FIX_COMPARISON.md).

The sample mismatches are not suppressed. Several are consistent with additional public-oracle assumptions about variable essential spending, deadline treatment, or flexible streams that are not stated as raw event metadata. A mismatch is not used as permission to copy the expected answer.

## Regression and official run

`main.py` was run against official `dataset/requests.csv`; it produced 250 rows. `evaluate.py` reported 250 rows and zero evaluation failures. The selected regression IDs were compared with the previous committed output: `request_26`, `request_67`, `request_69`, `request_89`, `request_90`, and `request_95` are unchanged. Across all 250 official rows, 58 rows changed because the newly supported unlinked payroll evidence is legitimately relevant to some users; schema validation still passes.

## Tests and safety checks

The full suite passes: **104 tests, 104 passed, 0 failed**. New/updated coverage includes the direct baseline formula, exact floor and one-cent boundary, same-day events, monotonicity, horizon boundaries, evidence-confirmed recurring salary, cancellations, amendments, delayed payments, missing image amounts, and adversarial untrusted messages. The debug CLI now reports baseline minimum/date, formula terms, request payment, final minimum/date, included/excluded event facts, and plan validation without chain-of-thought.

## Remaining limitations and risks

- The public sample oracle is not fully reproduced; the unresolved cases require a challenge-authoritative decision about how conservative variable essential spending and deadline-relative forecasts should be. The implementation deliberately follows the written 90-day rule and reports the divergence.
- Evidence-only salary projections are created only for bounded, explicitly payroll/salary-worded messages with a stated amount; unsupported or ambiguous income remains excluded.
- The model adapter is optional and unavailable providers safely fall back to deterministic extraction. No LLM can perform arithmetic or override deterministic rules.
- This audit does not claim perfect challenge accuracy. It establishes a mathematically proven capacity calculation, auditable event conservation, and a reproducible discrepancy report.
