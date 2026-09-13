# Manual sample financial calculations

These rows are deterministic reconstructions from the canonical request/profile/event/evidence path. Completed sample answer columns are used only in the comparison columns; they are never passed to the solver.

| request_id | starting balance | floor | requested | baseline minimum | min date | calculated safe | expected safe | difference |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| request_01 | 58481.1 | 18000 | 25256 | 43938.97 | 2024-05-28 | 25256.00 | 25256 | 0.00 |
| request_02 | 60383889.2 | 29158400 | 46018000 | 46964463.01 | 2025-08-14 | 17806063.01 | 17229139.2 | 576923.81 |
| request_03 | 5810300 | 2668700 | 5491000 | 3763547.18 | 2019-09-14 | 1094847.18 | 873000 | 221847.18 |
| request_04 | 52206950 | 30686600 | 12693000 | 43776836.11 | 2024-06-13 | 12693000.00 | 8401800 | 4291200.00 |
| request_05 | 46475.1 | 13100 | 15488 | 20399.49 | 2026-02-02 | 7299.49 | 737 | 6562.49 |
| request_06 | 1942.4 | 800 | 620.4 | 1480.70 | 2026-01-13 | 620.40 | 603.3 | 17.10 |
| request_07 | 218945.56 | 93000 | 197400 | 192307.07 | 2024-09-20 | 99307.07 | 87170.56 | 12136.51 |
| request_08 | 1536.57 | 800 | 996.6 | 1166.65 | 2025-02-12 | 366.65 | 284.57 | 82.08 |
| request_09 | 2231.1 | 600 | 166.61 | 1474.50 | 2026-09-12 | 166.61 | 166.61 | 0.00 |
| request_10 | 750155 | 225400 | 266700 | 269620.79 | 2025-03-03 | 44220.79 | 12700 | 31520.79 |
| request_11 | 63531795 | 34140600 | 13110000 | 50360977.90 | 2025-05-14 | 13110000.00 | 12510645 | 599355.00 |
| request_12 | 193089.89 | 43200 | 65164 | 123677.54 | 2026-07-01 | 65164.00 | 65164 | 0.00 |
| request_13 | 2789.52 | 1300 | 941.6 | 2648.13 | 2024-03-14 | 941.60 | 433.4 | 508.20 |
| request_14 | 3931.74 | 2200 | 5414.2 | 2959.82 | 2025-08-14 | 759.82 | 597.74 | 162.08 |
| request_15 | 1770.05 | 1200 | 3685 | 713.25 | 2026-04-04 | 0 | 83.05 | -83.05 |
| request_16 | 362370 | 122400 | 122500 | 362370 | 2023-08-12 | 122500.00 | 122500 | 0.00 |
| request_17 | 550379.58 | 166100 | 274600 | 421888.02 | 2026-03-13 | 255788.02 | 243849.58 | 11938.44 |
| request_18 | 2486 | 1400 | 3246.1 | 2094.61 | 2026-07-11 | 694.61 | 462 | 232.61 |
| request_19 | 199545 | 92800 | 39660 | 120625.91 | 2024-09-14 | 27825.91 | 28820 | -994.09 |
| request_20 | 102609.05 | 64500 | 303700 | 80282.57 | 2026-02-13 | 15782.57 | 5400 | 10382.57 |
| request_21 | 3911.35 | 1800 | 1574.4 | 3463.99 | 2026-04-12 | 1574.40 | 1543.35 | 31.05 |
| request_22 | 1132.46 | 500 | 731.5 | 1034.12 | 2024-12-14 | 534.12 | 475.46 | 58.66 |
| request_23 | 51957.9 | 27000 | 38016 | 38917.43 | 2025-05-14 | 11917.43 | 9152 | 2765.43 |
| request_24 | 85045 | 51000 | 109600 | 68688.49 | 2026-01-13 | 17688.49 | 13420 | 4268.49 |
| request_25 | 32063050 | 23379100 | 60496000 | 26742400.00 | 2024-03-14 | 3363300.00 | 1425000 | 1938300.00 |

## Interpretation

- `minimum_baseline_projected_balance` is the minimum closing balance over request date through request date + 89 days, before the requested payment and before optional spending changes.
- `calculated_safe_amount` is `max(0, min(requested_amount, baseline_minimum - minimum_balance_to_keep))`, quantized to cents.
- The complete per-event inclusion table is in [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv). It records every normalized event for every sample request, including whether it is a direct future cash flow, an evidence-backed recurrence source, or excluded and why.

## Primary request_01 reconstruction

- Starting balance: 58481.1 ZAR; required floor: 18000 ZAR; requested amount: 25256 ZAR.
- Baseline minimum: 43938.97 ZAR on 2024-05-28.
- Capacity: baseline minimum minus floor = 25938.97 ZAR, capped at requested amount = 25256.00 ZAR.
- The request-date payment is an additive debit in the same date bucket as any eligible request-date event; all same-day deltas are summed before the daily closing balance.
- After paying 25,256 ZAR, the minimum projected closing balance is 18,682.97 ZAR, above the 18,000 ZAR floor.

### Request 01 cash-flow ledger

- `event_102` is a pending debit of ZAR 567.60 effective 2024-03-05 and is reserved once.
- `event_103` is a scheduled confirmed salary credit of ZAR 23,320 effective 2024-03-15 and is included once.
- Historical settled rows before 2024-03-03 are not replayed as direct cash flows; their source-backed recurring streams generate the future rent, utility, education, debt, subscription, delivery, and grocery entries recorded in the event-audit CSV.
- Failed, cancelled, duplicate, unrealized, pending-credit, and amount-unknown rows are excluded. No image-derived amount is needed for this request.
- After the request-date debit, the minimum is ZAR 18,682.97 on 2024-05-28. The exact one-cent boundary is safe at ZAR 25,256.00 and would be unsafe at ZAR 25,256.01, but the latter exceeds this request's amount and is therefore not a candidate output.
