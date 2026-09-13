# After-fix sample comparison

Independent results are in `AFTER_FIX_SAMPLE_RESULTS.csv`. Completed columns are read only after solving. Amounts, payment amounts, and reduction amounts are compared as `Decimal` values.

- Total sample requests: 25
- Exact structured matches: 4
- Safe-amount exact matches: 4
- Structured mismatches: 21 requests / 44 fields

| request_id | field | agent value | expected value | difference | likely root cause |
|---|---|---|---|---:|---|
| request_02 | amount_safe_to_pay | `17806063.01` | `17229139.2` | `576923.81` | requires request-level forecast/recurrence interpretation audit |
| request_03 | amount_safe_to_pay | `1094847.18` | `873000` | `221847.18` | requires request-level forecast/recurrence interpretation audit |
| request_04 | amount_safe_to_pay | `12693000.00` | `8401800` | `4291200.00` | requires request-level forecast/recurrence interpretation audit |
| request_04 | affordability_status | `affordable_now` | `affordable_later` | `` | requires request-level forecast/recurrence interpretation audit |
| request_04 | recommended_payment_method | `full_payment` | `wait` | `` | requires request-level forecast/recurrence interpretation audit |
| request_04 | payment_plan | `2024-06-04:12693000` | `2024-06-15:12693000` | `` | requires request-level forecast/recurrence interpretation audit |
| request_04 | earliest_date_for_full_payment | `2024-06-04` | `2024-06-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_05 | amount_safe_to_pay | `7299.49` | `737` | `6562.49` | requires request-level forecast/recurrence interpretation audit |
| request_06 | amount_safe_to_pay | `620.40` | `603.3` | `17.10` | requires request-level forecast/recurrence interpretation audit |
| request_06 | affordability_status | `affordable_now` | `affordable_with_plan` | `` | requires request-level forecast/recurrence interpretation audit |
| request_06 | earliest_date_for_full_payment | `2026-01-03` | `2026-01-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_06 | spending_changes_needed | `none` | `stop:event_476` | `` | requires request-level forecast/recurrence interpretation audit |
| request_07 | amount_safe_to_pay | `99307.07` | `87170.56` | `12136.51` | requires request-level forecast/recurrence interpretation audit |
| request_07 | earliest_date_for_full_payment | `2024-10-22` | `2024-10-23` | `` | requires request-level forecast/recurrence interpretation audit |
| request_08 | amount_safe_to_pay | `366.65` | `284.57` | `82.08` | evidence-confirmed income handling |
| request_10 | amount_safe_to_pay | `44220.79` | `12700` | `31520.79` | requires request-level forecast/recurrence interpretation audit |
| request_11 | amount_safe_to_pay | `13110000.00` | `12510645` | `599355.00` | requires request-level forecast/recurrence interpretation audit |
| request_11 | affordability_status | `affordable_now` | `affordable_with_plan` | `` | requires request-level forecast/recurrence interpretation audit |
| request_11 | earliest_date_for_full_payment | `2025-05-03` | `2025-07-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_11 | spending_changes_needed | `none` | `reduce_to:event_989:665950` | `` | requires request-level forecast/recurrence interpretation audit |
| request_13 | amount_safe_to_pay | `941.60` | `433.4` | `508.20` | requires request-level forecast/recurrence interpretation audit |
| request_13 | affordability_status | `affordable_now` | `affordable_later` | `` | requires request-level forecast/recurrence interpretation audit |
| request_13 | recommended_payment_method | `full_payment` | `wait` | `` | requires request-level forecast/recurrence interpretation audit |
| request_13 | payment_plan | `2024-03-07:941.6` | `2024-05-15:941.60` | `` | requires request-level forecast/recurrence interpretation audit |
| request_13 | earliest_date_for_full_payment | `2024-03-07` | `2024-05-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_14 | amount_safe_to_pay | `759.82` | `597.74` | `162.08` | evidence-confirmed income handling |
| request_15 | amount_safe_to_pay | `0` | `83.05` | `-83.05` | evidence-confirmed income handling |
| request_17 | amount_safe_to_pay | `255788.02` | `243849.58` | `11938.44` | requires request-level forecast/recurrence interpretation audit |
| request_18 | amount_safe_to_pay | `694.61` | `462` | `232.61` | requires request-level forecast/recurrence interpretation audit |
| request_18 | payment_plan | `2026-08-15:3246.1` | `2026-09-15:3246.10` | `` | requires request-level forecast/recurrence interpretation audit |
| request_18 | earliest_date_for_full_payment | `2026-08-15` | `2026-09-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_19 | amount_safe_to_pay | `27825.91` | `28820` | `-994.09` | requires request-level forecast/recurrence interpretation audit |
| request_19 | payment_plan | `2024-09-04:27825.91|2024-09-15:11834.09` | `2024-09-04:28820|2024-09-15:10840` | `` | requires request-level forecast/recurrence interpretation audit |
| request_20 | amount_safe_to_pay | `15782.57` | `5400` | `10382.57` | requires request-level forecast/recurrence interpretation audit |
| request_21 | amount_safe_to_pay | `1574.40` | `1543.35` | `31.05` | requires request-level forecast/recurrence interpretation audit |
| request_21 | affordability_status | `affordable_now` | `affordable_with_plan` | `` | requires request-level forecast/recurrence interpretation audit |
| request_21 | earliest_date_for_full_payment | `2026-04-03` | `2026-04-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_21 | spending_changes_needed | `none` | `stop:event_1815|reduce_to:event_1816:23.50` | `` | requires request-level forecast/recurrence interpretation audit |
| request_22 | amount_safe_to_pay | `534.12` | `475.46` | `58.66` | requires request-level forecast/recurrence interpretation audit |
| request_22 | earliest_date_for_full_payment | `2024-12-15` | `2025-01-15` | `` | requires request-level forecast/recurrence interpretation audit |
| request_23 | amount_safe_to_pay | `11917.43` | `9152` | `2765.43` | requires request-level forecast/recurrence interpretation audit |
| request_24 | amount_safe_to_pay | `17688.49` | `13420` | `4268.49` | requires request-level forecast/recurrence interpretation audit |
| request_25 | amount_safe_to_pay | `3363300.00` | `1425000` | `1938300.00` | requires request-level forecast/recurrence interpretation audit |
| request_25 | earliest_date_for_full_payment | `2024-05-15` | `` | `` | requires request-level forecast/recurrence interpretation audit |

## Exact structured matches

request_01, request_09, request_12, request_16
