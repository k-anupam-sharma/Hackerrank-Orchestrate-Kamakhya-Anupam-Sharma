# Sample score root-cause final

## Frozen baseline

The OCR-enabled production baseline was evaluated on all 25 sample rows. [SAMPLE_BASELINE_COMPARISON.csv](SAMPLE_BASELINE_COMPARISON.csv) is the fresh per-request comparison. Sample expected values were read only after an independent solve.

- Exact structured rows: 4/25 (16%).
- Capped amount-safe cases: request_01, request_09, request_12, request_16.
- Uncapped amount-safe cases: 21/25.
- Amount-safe exact matches: 4/25.
- Status matches: 20/25.
- Method matches: 23/25.
- Payment-plan matches: 21/25.
- Earliest-date matches: 17/25.
- Spending-change matches: 22/25.

Capped cases establish only that available headroom was at least the requested amount. They are not evidence of an exact baseline forecast.

## Amount-safe forensics

The analytical amount-safe formula remains correct for a fixed baseline: the maximum request-date debit is the baseline minimum less the profile floor, constrained to zero and the requested amount. Independent capacity-reference, cent-boundary, monotonicity, same-day, and day-89 tests pass.

The 21 uncapped expected amounts imply 21 different baseline-minimum constraints. See [EXPECTED_FORECAST_CONSTRAINTS.csv](EXPECTED_FORECAST_CONSTRAINTS.csv). Production is higher than the implied benchmark baseline in 19 cases and lower in two: request_15 and request_19. This disproves a simple universal “reserve more historical spending” fix.

## Root causes ranked by impact

1. **Unspecified essential variable-spending policy.** Many overestimated contexts have protected groceries, transport, or healthcare histories but no explicit future scheduled obligation. The challenge requires conservative essential spending, but supplies no deterministic monthly budgeting formula. A raw category is not necessarily one recurring bill.
2. **Incomplete source evidence.** Local OCR recovered one defensible historical net-pay amount from image_01. Fifteen other blank image fields stayed unresolved because their OCR output did not yield one currency-paired final amount. Several salary or childcare messages also do not state enough amount/date information to create a forecast event.
3. **Recurrence/evidence timing ambiguity.** Some payroll date/amendment and variable stream contexts affect the forecast date/amount. The current model uses only source-backed recurrence and calendar-aware monthly expansion; the sample constraints do not demonstrate one alternative general rule.

The per-request, confidence-qualified view is [SAMPLE_ROOT_CAUSE_MATRIX.csv](SAMPLE_ROOT_CAUSE_MATRIX.csv). The full event inclusion/exclusion ledger is [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv).

## Disproven hypotheses

- The safe-amount formula itself is not the cause.
- Raw request/profile/event/payment-option joins are not the cause.
- Treating every protected variable category as a scheduled reserve is not supported and did not add an exact match.
- Tightening recurrence stream identity during expansion did not increase 4/25 and broke established recurrence/spending-change tests; it was reverted.
- OCR alone did not change the public benchmark because the recovered image_01 event is historic relative to request_03.

## Offline policy matrix

| variant | challenge-supported interpretation | exact structured / 25 | safe amount MAE on 21 uncapped | capped amount accuracy | uncapped amount accuracy |
|---|---|---:|---:|---:|---:|
| current | source-backed recurrence, scheduled items, pending debits | 4 | 367,112.84 | 4/4 | 0/21 |
| latest protected reserve | historical non-recurring protected category repeated on days 30/60 | 4 | 365,866.39 | 4/4 | 0/21 |
| median protected reserve | historical median protected amount repeated on days 30/60 | 4 | 365,620.56 | 4/4 | 0/21 |
| average protected reserve | historical average protected amount repeated on days 30/60 | 4 | 365,647.79 | 4/4 | 0/21 |
| confirmed future protected only | no change; those are already included | 4 | 367,112.84 | 4/4 | 0/21 |
| exact-description forecast identity | stricter recurrence projection identity | 4 | not retained | 4/4 | 0/21 |

The reserve metrics are analysis-only. None produced a fifth exact amount-safe result; they were not applied to production.

## Best policy and implementation decision

The best production policy remains the current source-backed baseline because it is the only candidate that both follows the stated rules and passes all existing safety/recurrence tests. No Phase 5 production forecast change was implemented. The OCR enhancement is general, provenance-bound, deterministic, and does not use expected sample fields, but it does not change the measured public score.

## Expected improvement

Before implementation: 4/25 exact structured rows, 4/25 exact safe amounts.
After the evidence/OCR implementation and controlled policy evaluation: 4/25 exact structured rows, 4/25 exact safe amounts.

There is no measured score improvement to claim. A defensible next improvement would require either reliable image/vision extraction for the unresolved receipts or organizer clarification defining the essential-variable-spending budget policy.
