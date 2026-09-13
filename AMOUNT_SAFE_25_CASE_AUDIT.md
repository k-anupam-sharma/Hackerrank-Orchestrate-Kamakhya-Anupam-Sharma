# Amount-safe 25-case audit

This audit was produced by loading the canonical request fields, profile, financial
events, payment options, messages, images, and dated exchange rates.  The expected
columns in `dataset/sample_requests.csv` were read only after each result was
calculated, for comparison.  They are not attributes of the `Request` model and do
not enter the solver.

## Method

For each request, the solver first reconciles source-backed evidence, normalizes the
user's events, and produces a no-request-payment forecast for the inclusive range
`request_date` through `request_date + 89 days`.  The table reports that forecast's
minimum closing balance and date.  `calculated_safe_amount` is the production value,
not a manually entered value.

| request_id | current_balance | minimum_balance | requested_amount | min_baseline_balance | calculated_safe_amount | expected_safe_amount | difference |
|---|---:|---:|---:|---:|---:|---:|---:|
| request_01 | 58481.10 | 18000 | 25256 | 43938.97 (2024-05-28) | 25256.00 | 25256 | 0.00 |
| request_02 | 60383889.20 | 29158400 | 46018000 | 46964463.01 (2025-08-14) | 17806063.01 | 17229139.20 | 576923.81 |
| request_03 | 5810300 | 2668700 | 5491000 | 3763547.18 (2019-09-14) | 1094847.18 | 873000 | 221847.18 |
| request_04 | 52206950 | 30686600 | 12693000 | 43776836.11 (2024-06-13) | 12693000.00 | 8401800 | 4291200.00 |
| request_05 | 46475.10 | 13100 | 15488 | 20399.49 (2026-02-02) | 7299.49 | 737 | 6562.49 |
| request_06 | 1942.40 | 800 | 620.40 | 1480.70 (2026-01-13) | 620.40 | 603.30 | 17.10 |
| request_07 | 218945.56 | 93000 | 197400 | 192307.07 (2024-09-20) | 99307.07 | 87170.56 | 12136.51 |
| request_08 | 1536.57 | 800 | 996.60 | 1166.65 (2025-02-12) | 366.65 | 284.57 | 82.08 |
| request_09 | 2231.10 | 600 | 166.61 | 1474.50 (2026-09-12) | 166.61 | 166.61 | 0.00 |
| request_10 | 750155 | 225400 | 266700 | 269620.79 (2025-03-03) | 44220.79 | 12700 | 31520.79 |
| request_11 | 63531795 | 34140600 | 13110000 | 50360977.90 (2025-05-14) | 13110000.00 | 12510645 | 599355.00 |
| request_12 | 193089.89 | 43200 | 65164 | 123677.54 (2026-07-01) | 65164.00 | 65164 | 0.00 |
| request_13 | 2789.52 | 1300 | 941.60 | 2648.13 (2024-03-14) | 941.60 | 433.40 | 508.20 |
| request_14 | 3931.74 | 2200 | 5414.20 | 2959.82 (2025-08-14) | 759.82 | 597.74 | 162.08 |
| request_15 | 1770.05 | 1200 | 3685 | 713.25 (2026-04-04) | 0.00 | 83.05 | -83.05 |
| request_16 | 362370 | 122400 | 122500 | 362370.00 (2023-08-12) | 122500.00 | 122500 | 0.00 |
| request_17 | 550379.58 | 166100 | 274600 | 421888.02 (2026-03-13) | 255788.02 | 243849.58 | 11938.44 |
| request_18 | 2486 | 1400 | 3246.10 | 2094.61 (2026-07-11) | 694.61 | 462 | 232.61 |
| request_19 | 199545 | 92800 | 39660 | 120625.91 (2024-09-14) | 27825.91 | 28820 | -994.09 |
| request_20 | 102609.05 | 64500 | 303700 | 80282.57 (2026-02-13) | 15782.57 | 5400 | 10382.57 |
| request_21 | 3911.35 | 1800 | 1574.40 | 3463.99 (2026-04-12) | 1574.40 | 1543.35 | 31.05 |
| request_22 | 1132.46 | 500 | 731.50 | 1034.12 (2024-12-14) | 534.12 | 475.46 | 58.66 |
| request_23 | 51957.90 | 27000 | 38016 | 38917.43 (2025-05-14) | 11917.43 | 9152 | 2765.43 |
| request_24 | 85045 | 51000 | 109600 | 68688.49 (2026-01-13) | 17688.49 | 13420 | 4268.49 |
| request_25 | 32063050 | 23379100 | 60496000 | 26742400.00 (2024-03-14) | 3363300.00 | 1425000 | 1938300.00 |

The four exact safe-amount matches are `request_01`, `request_09`, `request_12`,
and `request_16` (4/25, 16%).  The mismatches are deliberately retained: changing a
calculated result to the sample value would be label leakage rather than a financial
model correction.

## Event-accounting diagnostics

The exhaustive per-event diagnostics are in
[`SAMPLE_EVENT_FORECAST_AUDIT.csv`](SAMPLE_EVENT_FORECAST_AUDIT.csv).  For each
canonical row it records the event ID, effective/settlement date, monetary value and
direction, status, normalized cash treatment, whether it entered the baseline, and
the inclusion/exclusion reason.  Event rows before the request date are classified
as already represented by `current_available_balance` and do not re-enter the daily
forecast.  Within the horizon, scheduled cash and reserved pending debits enter once;
failed, cancelled, duplicate, pending-credit, and unrealized rows do not.  A
recurrence projection is separately marked as a future projection, rather than a
replay of its observed historic row.

The source joins used for the 25 cases were also checked in
[`SAMPLE_MISMATCH_CONTEXT_AUDIT.md`](SAMPLE_MISMATCH_CONTEXT_AUDIT.md): the canonical
request/profile/event/message/image/payment-option joins match the authoritative
source rows.  The remaining disagreement is consequently a forecast interpretation
and benchmark issue, not request-context lookup or a request-ID-specific override.
