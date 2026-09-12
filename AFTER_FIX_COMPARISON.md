# After-fix sample comparison

Independent solver results are in `AFTER_FIX_SAMPLE_RESULTS.csv`. Completed columns in `dataset/sample_requests.csv` are read only after solving. Amounts, plan amounts, and reduction amounts are compared numerically as `Decimal`; dates and categorical fields use exact values.

- Total sample requests: 25
- Exact structured matches: 4
- Structured mismatches: 21 requests / 48 fields

| request_id | field | agent value | expected value | likely root cause |
|---|---|---|---|---|
| request_02 | amount_safe_to_pay | `17806063.01` | `17229139.2` | requires request-level source and forecast audit |
| request_03 | amount_safe_to_pay | `1094847.18` | `873000` | requires request-level source and forecast audit |
| request_04 | amount_safe_to_pay | `12693000.00` | `8401800` | requires request-level source and forecast audit |
| request_04 | affordability_status | `affordable_now` | `affordable_later` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_04 | recommended_payment_method | `full_payment` | `wait` | requires request-level source and forecast audit |
| request_04 | payment_plan | `2024-06-04:12693000` | `2024-06-15:12693000` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_04 | earliest_date_for_full_payment | `2024-06-04` | `2024-06-15` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_05 | amount_safe_to_pay | `7299.49` | `737` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_06 | amount_safe_to_pay | `620.40` | `603.3` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_06 | affordability_status | `affordable_now` | `affordable_with_plan` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_06 | earliest_date_for_full_payment | `2026-01-03` | `2026-01-15` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_06 | spending_changes_needed | `none` | `stop:event_476` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_07 | amount_safe_to_pay | `99307.07` | `87170.56` | requires request-level source and forecast audit |
| request_07 | earliest_date_for_full_payment | `2024-10-22` | `2024-10-23` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_08 | amount_safe_to_pay | `0.00` | `284.57` | requires request-level source and forecast audit |
| request_08 | affordability_status | `not_affordable` | `affordable_later` | requires request-level source and forecast audit |
| request_08 | recommended_payment_method | `not_recommended` | `wait` | requires request-level source and forecast audit |
| request_08 | payment_plan | `none` | `2025-04-15:996.60` | requires request-level source and forecast audit |
| request_08 | earliest_date_for_full_payment | `` | `2025-04-15` | requires request-level source and forecast audit |
| request_10 | amount_safe_to_pay | `44220.79` | `12700` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_11 | amount_safe_to_pay | `13110000.00` | `12510645` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_11 | affordability_status | `affordable_now` | `affordable_with_plan` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_11 | earliest_date_for_full_payment | `2025-05-03` | `2025-07-15` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_11 | spending_changes_needed | `none` | `reduce_to:event_989:665950` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_13 | amount_safe_to_pay | `941.60` | `433.4` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_13 | affordability_status | `affordable_now` | `affordable_later` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_13 | recommended_payment_method | `full_payment` | `wait` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_13 | payment_plan | `2024-03-07:941.6` | `2024-05-15:941.60` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_13 | earliest_date_for_full_payment | `2024-03-07` | `2024-05-15` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_14 | amount_safe_to_pay | `0.00` | `597.74` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_15 | amount_safe_to_pay | `0.00` | `83.05` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_17 | amount_safe_to_pay | `255788.02` | `243849.58` | requires request-level source and forecast audit |
| request_18 | amount_safe_to_pay | `694.61` | `462` | requires request-level source and forecast audit |
| request_18 | payment_plan | `2026-08-15:3246.1` | `2026-09-15:3246.10` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_18 | earliest_date_for_full_payment | `2026-08-15` | `2026-09-15` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_19 | amount_safe_to_pay | `27825.91` | `28820` | requires request-level source and forecast audit |
| request_19 | payment_plan | `2024-09-04:27825.91|2024-09-15:11834.09` | `2024-09-04:28820|2024-09-15:10840` | requires request-level source and forecast audit |
| request_20 | amount_safe_to_pay | `15782.57` | `5400` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_21 | amount_safe_to_pay | `1574.40` | `1543.35` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_21 | affordability_status | `affordable_now` | `affordable_with_plan` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_21 | earliest_date_for_full_payment | `2026-04-03` | `2026-04-15` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_21 | spending_changes_needed | `none` | `stop:event_1815|reduce_to:event_1816:23.50` | flexible-stream eligibility or future commitment interpretation remains under audit |
| request_22 | amount_safe_to_pay | `534.12` | `475.46` | requires request-level source and forecast audit |
| request_22 | earliest_date_for_full_payment | `2024-12-15` | `2025-01-15` | future cash-flow interpretation differs from public oracle; monthly dates now use calendar cadence |
| request_23 | amount_safe_to_pay | `11917.43` | `9152` | requires request-level source and forecast audit |
| request_24 | amount_safe_to_pay | `17688.49` | `13420` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_25 | amount_safe_to_pay | `3363300.00` | `1425000` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |
| request_25 | earliest_date_for_full_payment | `2024-05-15` | `` | variable/essential spending and long-horizon cash-flow interpretation remains under audit |

## Exact structured matches

request_01, request_09, request_12, request_16
