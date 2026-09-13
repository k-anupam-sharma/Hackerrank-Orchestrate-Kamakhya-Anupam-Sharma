# Final amount-safe report

## Outcome

The production safe-capacity calculation is mathematically consistent with the implemented 90-day forecast: its independent reference test, cent-boundary tests, and monotonicity tests all pass for each public sample context. The public sample benchmark is **not** fully reproduced: 4 of 25 safe amounts match numerically. This report intentionally does not claim that the benchmark target of 25/25 has been achieved. No sample answer columns or request-ID-specific branches were added.

## Mathematical model

Let `C_t` be the closing balance in the baseline forecast on day `t`, with no request payment and no optional spending changes. Let `B = min(C_t)` across the inclusive 90-day range, and `M` be `minimum_balance_to_keep`. A one-time payment `P` on `request_date` contributes `-P` to that date's closing balance and to every later daily closing balance. All other baseline deltas are independent of `P`. Therefore:

```text
min_t(C_t - P) = B - P
B - P >= M  iff  P <= B - M
safe amount = max(0, min(requested_amount, floor_to_cent(B - M)))
```

The formula remains valid when the request date has one or more event deltas: those deltas are first included in `C_request_date`; payment is then an additional debit in the same day total. Addition is commutative, so there is no inconsistent intra-day order. It also remains valid for dated incomes, expenses, pending-debit reserves, recurring expansions, and validated evidence amendments because they are all fixed baseline deltas. The relationship would cease to hold only if an event's existence or amount depended on the proposed request payment; the challenge data and the implementation do not permit that dependency.

`calculate_baseline_forecast()` makes this separation explicit and `calculate_amount_safe_to_pay()` uses the formula above. The 90-day interval is `request_date` through `request_date + 89 days`, inclusive.

## Cash-flow treatment

Historical rows before the request date are already reflected in the profile's current available balance and are not replayed. In-horizon scheduled cash, confirmed salary, and reserved pending debits are included once. Pending credits, failed, cancelled, duplicate, and unrealized records are excluded. Recurrence is expanded only from normalized source-backed streams; its observed anchor is never added a second time as a projection. Dated exchange rates are applied during normalization, preserving `Decimal` amounts.

The detailed row-level classification is in [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv). It contains the requested event ID, date/settlement date, amount, direction, status, cash treatment, inclusion decision, and reason.

## Correction made

The audit found a real evidence-reconciliation defect: an unlinked, date-only, explicit payroll confirmation could not move a verified salary stream because it did not repeat an amount. This either omitted the confirmed replacement date or encouraged a historical salary to be replayed as a future row.

The reconciler now accepts a date-only payroll confirmation only when it explicitly identifies confirmed payroll timing. It reuses the latest verified recurring salary amount for that same user, creates a source-provenanced scheduled evidence event, and disables the superseded historic salary recurrence. It never fabricates an amount, moves a settled historic event, or accepts an embedded instruction. The test `test_dated_payroll_amendment_without_amount_uses_verified_salary_anchor` covers this behavior.

## Request_01 boundary audit

| item | value |
|---|---:|
| current balance | ZAR 58,481.10 |
| required minimum | ZAR 18,000.00 |
| requested amount | ZAR 25,256.00 |
| baseline minimum | ZAR 43,938.97 on 2024-05-28 |
| unconstrained headroom | ZAR 25,938.97 |
| capped safe amount | ZAR 25,256.00 |
| minimum after paying full request | ZAR 18,682.97 on 2024-05-28 |

`request_01` has no relevant extracted evidence facts. The in-horizon source IDs are surfaced in the event audit. Paying the requested amount is safe; the requested cap means the amount one cent higher is outside the request, so it is not a required unsafe-boundary case.

## Sample benchmark

The complete 25-row calculation table is [AMOUNT_SAFE_25_CASE_AUDIT.md](AMOUNT_SAFE_25_CASE_AUDIT.md). Comparison is numeric for money and parsed for payment plans, rather than a fragile textual comparison of trailing zeroes.

| field | exact semantic matches | total |
|---|---:|---:|
| amount_safe_to_pay | 4 | 25 |
| affordability_status | 20 | 25 |
| recommended_payment_method | 23 | 25 |
| payment_plan | 21 | 25 |
| earliest_date_for_full_payment | 17 | 25 |
| spending_changes_needed | 22 | 25 |
| all six structured fields | 4 | 25 |

The exact safe-amount matches are `request_01`, `request_09`, `request_12`, and `request_16`. The 21 retained divergences do not indicate a binary-search or payment-application error: for each, production capacity equals the independent baseline-minimum reference. Examples such as `request_15` demonstrate an underlying interpretation conflict: the source-backed baseline minimum is EUR 713.25, below the EUR 1,200 floor, which mathematically yields zero capacity, while the labelled sample answer is EUR 83.05. Making that answer pass would require altering event eligibility/recurrence semantics beyond the supplied source facts or copying the label.

## Tests and official regression

Added `code/tests/test_amount_safe_reference.py`:

- production capacity equals an independent no-payment-baseline reference for all 25 sample contexts;
- all-capacity cent boundaries are safe at the returned amount and unsafe one cent higher when the returned amount is below the requested cap;
- request-date-through-day-89 horizon;
- monotonicity for representative mixed-currency/evidence contexts;
- a source-derived `request_01` full-request boundary.

The complete suite passes: **110 tests, 0 failures**. `python main.py` regenerated all 250 official rows and `python evaluate.py` reported **0 failures**.

The representative official requests `request_26`, `request_67`, `request_69`, `request_89`, and `request_90` retain their structured recommendations. `request_95` retains every structured field; its explanation now also reports the source-backed confirmed salary from the dated payroll confirmation. Other official changes are limited to the same evidence reconciliation behavior and can alter a full-payment date where a source-backed payroll date replaces the old recurrence calendar.

## Remaining limitations

The challenge statement requires image-derived missing amounts, but the default model adapter is deliberately disabled without configured vision credentials; such amounts remain unknown rather than becoming zero. More importantly, the public sample labels cannot currently be treated as a proof that a different source-event interpretation is correct. The retained mismatches need a challenge-authoritative recurrence/essential-variable-spending policy or hidden evaluation feedback before a general correction can be justified.

