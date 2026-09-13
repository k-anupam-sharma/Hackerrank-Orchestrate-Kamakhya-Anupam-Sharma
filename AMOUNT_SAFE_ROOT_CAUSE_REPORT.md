# Amount-safe root-cause report

## Result

The safe-amount match rate remains **4/25 (16%)**. This investigation did not identify a source-backed, general baseline correction that improves that score without violating existing recurrence tests or inferring financial facts that the dataset does not establish. No downstream recommendation fields were patched and no sample answer was used as an input.

## Algorithm and proof

Production builds a 90-day no-payment, no-spending-change baseline first. The range is inclusive from request_date through request_date + 89 days. It calculates:

    B = minimum baseline daily closing balance
    M = minimum_balance_to_keep
    amount_safe_to_pay = min(requested_amount, max(0, floor_to_cent(B - M)))

A payment on the request date subtracts the same amount from that day's closing balance and every later closing balance. Same-day event deltas and the payment are summed in the deterministic daily ledger, so income, expenses, scheduled items, and multiple same-day events do not change this relationship. The independent reference test, 25-context boundary tests, and monotonicity tests validate the formula.

## Reverse check

[SAFE_AMOUNT_DIAGNOSTIC.csv](SAFE_AMOUNT_DIAGNOSTIC.csv) records expected safe amount, expected implied baseline minimum (floor plus expected safe amount), independently calculated baseline minimum, and their differences. It is post-calculation only. It shows that the mismatch arises in baseline cash-flow interpretation, not capacity arithmetic. For a capped result such as request_01, an implied-baseline difference cannot affect the result because both headroom values exceed the requested amount.

## Event accounting and forecast input audit

Per-event cash treatment and inclusion reasons are in [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv). The request-context and recurrence/evidence audit is in [SAMPLE_MISMATCH_CONTEXT_AUDIT.md](SAMPLE_MISMATCH_CONTEXT_AUDIT.md).

Verified rules:

- Historic transactions before the request date are not replayed.
- Scheduled cash and confirmed salary are dated cash-flow entries.
- Pending debits are reserved.
- Pending credits, failed, cancelled, explicit duplicates, and unrealized assets are excluded.
- Foreign-currency values use the supplied dated directed rate.
- Messages and images stay untrusted, provenance-bound facts.
- The horizon ends on day 89, and an item one day after it is excluded.

## Root causes

1. **Not safe-amount arithmetic.** Production capacity equals the independent B-minus-M capacity for every sample context.
2. **No raw context lookup failure.** Profiles, events, messages, image links, payment options, and rates join by authoritative IDs.
3. **Recurrence/variable-spending ambiguity is primary.** The specification calls for conservative treatment of essential variable spending but does not define a deterministic budget formula. Exact merchant-description streams avoid turning unrelated purchases into contractual charges; category-level merging is overbroad.
4. **A stream-identity experiment was rejected.** Using exact descriptions during forecast expansion remained 4/25 and broke five recurrence/spending-change tests. It was reverted.
5. **Some source facts need image extraction.** Blank image-backed amounts remain unknown rather than becoming zero. This avoids fabrication but can differ from a labelled benchmark.
6. **Labelled baselines move in opposite directions.** request_15 implies a baseline minimum EUR 569.80 higher than production, while most mismatches imply a lower benchmark baseline. A rule that only adds conservative expenses cannot explain both.

## Request-date and horizon tests

Existing tests cover an empty request day, same-day income, same-day expense, multiple same-day entries, and a one-day breach before later salary. The model treats current balance as the request-date opening balance, adds all eligible same-day event deltas, subtracts payment, and checks that daily closing balance against the floor. Separate tests cover day 0, day 89, and post-horizon exclusion.

## Request_01

| item | value |
|---|---:|
| current balance | ZAR 58,481.10 |
| floor | ZAR 18,000.00 |
| requested amount | ZAR 25,256.00 |
| baseline minimum | ZAR 43,938.97 on 2024-05-28 |
| headroom | ZAR 25,938.97 |
| returned amount | ZAR 25,256.00 |
| minimum after full request payment | ZAR 18,682.97 |

This independently matches the sample amount and stays above the required minimum.

## Benchmark and regression

| field | matches | rate |
|---|---:|---:|
| amount_safe_to_pay | 4 / 25 | 16% |
| affordability_status | 20 / 25 | 80% |
| recommended_payment_method | 23 / 25 | 92% |
| payment_plan | 21 / 25 | 84% |
| earliest_date_for_full_payment | 17 / 25 | 68% |
| spending_changes_needed | 22 / 25 | 88% |

The full suite remains 110 passing tests. The official evaluation dataset was not changed in this investigation; output.csv remains valid. No request-specific branches or sample constants were introduced.

## Recommendation

A defensible improvement requires an authoritative general rule for budgeting essential variable categories or usable image extraction for blank source amounts. Selecting recurrence policy only to force the 21 labels would be sample overfitting, not a mathematical correction.
