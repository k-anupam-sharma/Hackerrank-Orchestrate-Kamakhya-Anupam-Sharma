# Downstream Score Dependency Analysis

## Scope

This is an offline analysis only. `sample_requests.csv` expected fields were
read after independent solving for comparison and for one diagnostic
counterfactual. They are not imported by production code. No forecast,
capacity, planner, ranking, evidence, or output code was modified.

## Actual dependency path

`solve_request` computes capacity and earliest date independently in
[`solver.py`](code/buy_or_wait/solver.py): `safe_amount` at lines 76–82 and
`earliest` at lines 83–89. It passes both to candidate generation at lines
90–94, validates every candidate against a newly simulated forecast at lines
96–103, optionally searches permitted spending changes at lines 106–119, and
ranks the validated candidates at lines 121–123.

`amount_safe_to_pay` directly controls only whether the partial-plan candidate
exists and its required first payment ([`plans.py`](code/buy_or_wait/plans.py),
lines 58–73 and 173–195). It does **not** establish the safety of full-payment
or installment options: every option is independently forecast-validated.
`earliest_date_for_full_payment` is independently calculated, controls wait and
partial dates, and is not recalculated from the safe amount. Payment preference,
maximum installment months, exact supplied schedules, and payment totals are
checked by `PlanValidator` (lines 108–216). Ranking is deterministic and uses
deadline completion, changes, total paid, start date, payment count, then option
ID ([`ranking.py`](code/buy_or_wait/ranking.py), lines 65–93).

## Field-level baseline accuracy

Fresh raw value comparison gives the following. This differs from the supplied
23/25 method and 21/25 plan counts: the current comparison has five method and
seven plan mismatches, respectively. The difference appears to be a prior
semantic/older-run aggregation; the per-request rows below are the source of
record for this analysis.

| Field | Correct | Accuracy |
|---|---:|---:|
| amount_safe_to_pay | 4 / 25 | 16.0% |
| affordability_status | 20 / 25 | 80.0% |
| recommended_payment_method | 20 / 25 | 80.0% |
| payment_plan | 18 / 25 | 72.0% |
| earliest_date_for_full_payment | 17 / 25 | 68.0% |
| spending_changes_needed | 22 / 25 | 88.0% |

## Per-request dependency matrix

`Safe` is the only capacity field. For a wrong downstream field, `I` means
independent of the *safe-amount scalar* (although it may share the underlying
baseline-forecast cause), and `P` means partially dependent. `—` means the
field already matches. No incorrect downstream field was found to be directly
repairable by substituting the safe amount alone.

| request_id | Safe correct? | Status | Method | Plan | Earliest | Changes | Mismatch dependency / code path |
|---|---|---|---|---|---|---|---|
| request_01 | yes | yes | yes | yes | yes | yes | — |
| request_02 | no | yes | yes | yes | yes | yes | — |
| request_03 | no | yes | yes | yes | yes | yes | — |
| request_04 | no | no | no | no | no | yes | I — independently simulated full option and independent earliest date are too early under the current forecast. |
| request_05 | no | yes | yes | yes | yes | yes | — |
| request_06 | no | no | no | no | no | no | I — full option remains forecast-safe under the current baseline; expected change is never searched because a safe no-change plan exists. |
| request_07 | no | yes | yes | yes | yes | yes | — |
| request_08 | no | yes | yes | yes | yes | yes | — |
| request_09 | yes | yes | yes | yes | yes | yes | — |
| request_10 | no | yes | yes | yes | yes | yes | — |
| request_11 | no | no | no | no | no | no | I — independently simulated full option is safe; expected reduction requires a less favorable baseline forecast. |
| request_12 | yes | yes | yes | yes | yes | yes | — |
| request_13 | no | no | no | no | no | yes | I — independently simulated full option and earliest date are too early. |
| request_14 | no | yes | yes | yes | yes | yes | — |
| request_15 | no | yes | yes | yes | yes | yes | — |
| request_16 | yes | yes | yes | yes | yes | yes | — |
| request_17 | no | yes | yes | yes | yes | yes | — |
| request_18 | no | yes | yes | no | no | yes | I — wait option timing is determined by independently calculated earliest full date. |
| request_19 | no | yes | yes | no | yes | yes | P — partial amount is directly tied to safe amount, but the oracle partial plan still fails the current simulated forecast at that amount. |
| request_20 | no | yes | yes | yes | yes | yes | — |
| request_21 | no | no | no | no | no | no | I — current full option is independently forecast-safe; expected two changes are not considered because the solver correctly short-circuits after finding a safe no-change plan. |
| request_22 | no | yes | yes | yes | no | yes | I — installment schedule is correct; earliest date is a separate forecast calculation. |
| request_23 | no | yes | yes | yes | yes | yes | — |
| request_24 | no | yes | yes | yes | yes | yes | — |
| request_25 | no | yes | yes | yes | no | yes | I — the current forecast finds a later safe full-payment date, while the oracle leaves it empty. |

## Mismatch root causes and challenge-rule audit

### Status / method / plan: requests 04, 06, 11, 13, and 21

Each selects `full_payment` because the supplied full-payment option passes the
same 90-day simulator used for all plans. That selection correctly obeys user
payment preference and supplied-option schedule requirements. The benchmark
expects a wait, installment, or spending-change plan because its implied
baseline forecast is lower. Substituting the oracle safe amount does not make
the current full option unsafe, so these are independent of the safe scalar and
are not an installment, preference, partial-rule, or ranking violation.

For requests 06, 11, and 21, expected spending changes are absent because the
solver deliberately does not enumerate changes after discovering a safe
no-change completion. This honors the published preference for no spending
changes. Searching changes merely to imitate the oracle would violate ranking.

### Earliest date: requests 04, 06, 11, 13, 18, 21, 22, and 25

`find_earliest_safe_full_payment_date` re-simulates a full payment on each
candidate date. Its result is independent of `amount_safe_to_pay`. These
mismatches therefore trace to the same disputed baseline forecast inputs, not
to plan generation or tie-breaking. No safe-amount-only counterfactual changes
any earliest date.

### Partial plan: request 19

The current plan uses its calculated safe first payment, so the rendered
partial schedule differs. With the oracle safe amount supplied only to the
offline candidate generator, that partial plan must still pass the actual
current 90-day forecast. It does not; the candidate set instead ranks a valid
installment option. Thus the mismatch is partly scalar-dependent but cannot be
fixed without changing the underlying forecast/safety assessment.

### Wait plan: request 18

The method is correct. Its scheduled date follows the independently calculated
earliest full-payment date, so the plan mismatch is entirely caused by the
same earliest-date disagreement.

## Offline safe-amount counterfactual

Two diagnostic runs were made per request:

- **A:** current independently calculated safe amount.
- **B:** sample expected safe amount passed only to `PlanGenerator` and
  `PlanValidator`; normalized events, the baseline, `earliest`, preferences,
  option schedules, ranking, and all forecast safety checks remained current.

This is intentionally not a valid production scenario. It answers only whether
the scalar itself is the blocker.

| Field | A correct | B correct | Mismatches repaired by B |
|---|---:|---:|---:|
| affordability_status | 20 | 20 | 0 |
| recommended_payment_method | 20 | 19 | 0 (one worsened: request_19) |
| payment_plan | 18 | 18 | 0 |
| earliest_date_for_full_payment | 17 | 17 | 0 |
| spending_changes_needed | 22 | 22 | 0 |

All B outputs equal A except request 19: B makes the current partial candidate
unsafe under the unchanged forecast, and the ranking selects installments.
Therefore a magically correct scalar does not recover an exact structured
match for any additional request.

## Independently fixable mismatches

None were found. The planner correctly:

- accepts only user-approved full/partial/installment methods;
- treats wait as the accepted full-payment method;
- rejects installment options above `max_installment_months`;
- reproduces supplied option schedules exactly;
- requires exactly two complete partial payments, with the first matching the
  safe amount and the remainder on the earliest full date;
- validates every selected option against the daily forecast; and
- prefers a safe no-change plan over an otherwise comparable change plan.

Changing any of those behaviors to match a sample row would contradict either
the stated rules or the current source-backed forecast result.

## Maximum defensible improvement without safe-amount / forecast changes

The offline experiment measures **zero** repaired downstream mismatches from
the safe scalar alone. Since no independent planner, preference, installment,
partial, earliest-date, spending-change, or ranking rule violation was found,
the defensible expected exact-score improvement is **0 requests**. Production
change is not justified.
