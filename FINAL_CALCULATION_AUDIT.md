# Final calculation audit

## Root cause found

The request 01 error was caused by category-level recurrence inference for flexible expenses. Unrelated dining descriptions were merged into one recurring stream and projected at the latest amount. That was an unsupported future commitment. A second general issue was advancing monthly recurrences by a fixed median day interval, which drifted 15th-of-month records earlier over time. Variable income descriptions were also being projected despite changing amounts, and final payroll was not treated as a terminal stream.

## Corrected behavior

Normal expenses/income now require an exact repeated source description and regular history; subscription/debt streams retain contractual category identity. Variable-amount income is not forecast as guaranteed recurring cash. Explicit final/last income terminates a prior stream. Monthly same-day streams advance by calendar month. Scheduled cash uses `event_date`; pending debit reservation still uses settlement date. All changes are deterministic and use `Decimal`.

## Request 01 result

Independent result: amount safe `25256.00` (numeric value `25256`), `affordable_now`, `full_payment`, plan `2024-03-03:25256`, earliest date `2024-03-03`, spending changes `none`. The minimum projected balance after the payment is `18682.97` on `2024-05-28`, above the `18000` floor. No sample answer column is supplied to the solver.

## Verification

- `BEFORE_FIX_SAMPLE_RESULTS.csv` and `BEFORE_FIX_COMPARISON.md` freeze the pre-fix behavior.
- `AFTER_FIX_SAMPLE_RESULTS.csv` and `AFTER_FIX_COMPARISON.md` contain independent post-fix results and field-level mismatches.
- The post-fix sample run processed all 25 rows. It has 4 exact structured matches and 21 requests with one or more mismatches; this is not claimed as perfect oracle accuracy.
- Official `requests.csv` remains the production input. `main.py` regenerated 250 output rows and `evaluate.py` is used to validate them.
- Regression IDs checked include request_26, request_67, request_69, request_89, request_90, and request_95. Requests 26, 69, 90, and 95 are unchanged. Request 67 changes from `413.97`/2024-09-14 to `475.28`/2024-09-15, and request 89 changes from `10445495.42`/2025-11-14 to `10945379.21`/2025-11-15; these are the generalized calendar-month/payroll recurrence corrections, not request-ID patches.

## Remaining limitations

The public sample appears to encode additional assumptions for variable essential spending and some flexible categories that are not explicit in row metadata. Those cases remain visible as mismatches and require a challenge-authoritative interpretation before further code changes. No request-specific exception or sample-label leakage was introduced.
