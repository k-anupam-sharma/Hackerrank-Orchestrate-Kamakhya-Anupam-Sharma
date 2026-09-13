# Amount-safe-to-pay mathematical audit (pre-fix)

## Scope and current path

Before changing the implementation, the complete path was traced through `normalization.py`, `forecast.py`, `capacity.py`, `plans.py`, `spending_changes.py`, `ranking.py`, and `solver.py`. `solver.solve_request` normalizes and reconciles a user's events, calls `calculate_amount_safe_to_pay`, then uses that result for plan generation and validation. No sample answer column is read by this path.

## 1. Current formula

The current implementation uses a cent-quantized binary search. For each candidate `P` in `[0, requested_amount]`, it calls `forecast_balance` with one proposed payment `-P` on `request_date`, then accepts the candidate when the minimum daily closing balance is at least `minimum_balance_to_keep`. The greatest accepted cent value is returned. In notation:

`safe(P) := min_t(balance_without_request(t) - P) >= M`

where `M` is the required minimum balance, assuming the request payment is additive and no spending changes are supplied. The implementation does not currently construct or expose a named baseline forecast; it recomputes the complete forecast at every binary-search probe.

## 2. Exact inputs

Inputs are the profile's `current_available_balance` and `minimum_balance_to_keep`; the request's date and requested amount; the normalized, evidence-reconciled financial events; and the 90-day horizon (default 90 days). Monetary values are `Decimal`. The safe amount is explicitly calculated before optional spending changes. Payment-method preferences are not inputs to this capacity calculation.

## 3. Forecast construction

`forecast_balance` uses dates `request_date` through `request_date + horizon_days - 1` (90 calendar dates). It starts at `current_available_balance`, groups eligible direct-event deltas and proposed-payment deltas by date, expands normalized recurring streams, and records each day's opening balance, event delta, payment delta, and closing balance. Safety is the minimum daily closing balance being at least the floor.

Direct event treatment is supplied by normalization: settled cash is included, pending debits reserve cash, salary-like scheduled income is included on its scheduled/effective date, and non-salary scheduled credits are excluded. Failed, cancelled, duplicate, unrealized, and amount-unknown records are excluded. Historical events before the request date are not replayed as direct forecast entries; recurring streams are expanded from source-backed history.

## 4. Proposed payment timing

The proposed payment is placed in the same dated delta bucket as any other request-date event. Because all same-day deltas are summed before the closing balance is recorded, ordering within a date is immaterial to the current model: every daily balance after the request date is reduced by exactly `P`. This convention must be documented and tested for request-date income, expenses, and multiple events.

## 5. Future income and expenses

Eligible future direct events are included once at their effective date. Confirmed salary-like scheduled income is included; pending credits and unsupported scheduled credits are not. Eligible expenses include settled cash, reserved pending debits, scheduled debits, and normalized recurring projections. Recurring projections use source-backed histories and the latest observed eligible amount, with calendar-month handling for stable monthly streams. Spending changes are deliberately absent from `amount_safe_to_pay` and are evaluated only by later plan variants.

## 6. Recurrence and status handling

Normalization marks a source event recurring only when supported by repeated dated observations and the event/category rules. Forecast expansion groups recurring records by event type/category/direction/currency and projects a median cadence (calendar months for stable monthly day-of-month streams). `_included_cash_delta` admits `settled_cash`, `reserve_pending_debit`, and eligible `scheduled_cash`; all other cash treatments are ignored. Reconciliation applies cancellation/amendment/settlement/source-newness rules before normalization. A linked ID alone does not make an event cash-eligible.

## 7. Minimum-balance check

`is_plan_safe` computes the minimum closing balance across all simulated days and compares it to `minimum_balance_to_keep` using `Decimal` comparison. Thus a payment exactly at the available capacity is safe when the resulting minimum equals the floor; one cent more is unsafe, subject to the selected monetary quantum.

## 8. Mathematical divergence risks found

1. **Repeated simulation rather than an explicit baseline.** The binary search is deterministic but obscures the additive relationship and repeats date/recurrence work. It also makes it harder to prove that the same baseline is used by capacity, earliest-date, and plan validation.
2. **Baseline is implicit.** There is no named reusable `calculate_baseline_forecast`, so future changes could accidentally calculate capacity against a different event set.
3. **Same-day semantics are implicit.** Date buckets make same-day order commute, but this must be explicit: `current_available_balance` is the opening balance for the request date, and only eligible events whose cash is not already reflected in that balance may be applied.
4. **Historical/recurring boundary.** Historical events are correctly excluded as direct rows by date, but recurring expansion can still be wrong if a variable historical stream is classified as contractual recurrence. This is the primary data/model risk and is audited separately in `RECURRENCE_MODEL.md` and the sample reconstruction.
5. **Recurring anchor amount.** Projections use the latest eligible anchor amount. A later confirmed amendment must therefore be reconciled before recurrence expansion; otherwise a stale anchor changes the baseline minimum.
6. **Horizon boundary.** The current horizon includes day 0 through day 89 and excludes day 90. Tests must make this contract explicit.
7. **Pending obligations.** Pending debits reserve cash while pending credits do not add cash. Confusing these signs would change the baseline minimum.
8. **Evidence and unknown amounts.** Blank amounts remain unknown and are not zero. An image extraction that fails must not silently create a cash flow.

## Formula to implement after this audit

For a fixed no-change baseline forecast `F(t)`, a one-time request-date payment is an additive `-P` on every day in the horizon. Therefore `min_t(F(t)-P) = min_t(F(t)) - P`. The direct capacity is valid **only** after the baseline event set, recurrence, same-day timing, and horizon semantics are fixed:

`capacity = max(0, min(requested_amount, baseline_minimum - minimum_balance_to_keep))`, quantized down to the smallest monetary unit.

The implementation change will create one reusable baseline forecast and use this formula for `amount_safe_to_pay`. Earliest full-payment dates remain date-specific simulations because a payment on a later date affects only the suffix of the horizon. Boundary and monotonicity tests will prove the relationship.
