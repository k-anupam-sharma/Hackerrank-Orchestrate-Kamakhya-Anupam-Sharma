# Benchmark Ceiling Analysis

## Scope and guardrail

This is an offline forensic analysis. `sample_requests.csv` expected-answer
columns were used only to compare results. No production solver code, solver
inputs, or `output.csv` behavior was changed.

## Measured score

| Metric | Result |
|---|---:|
| Exact structured-output matches | 4 / 25 (16.0%) |
| Exact `amount_safe_to_pay` matches | 4 / 25 (16.0%) |
| Capped safe-amount cases | 4 / 4 matched |
| Uncapped safe-amount cases | 0 / 21 matched |

The direct capacity relation remains valid for a fixed forecast:

`safe_amount = clamp(baseline_minimum - minimum_balance, 0, requested_amount)`.

Thus the mismatch is not evidence that capacity arithmetic needs a new formula;
it is evidence that the benchmark's baseline forecast differs from the supplied
data's uniquely supported baseline.

## Why the four matches work

`request_01`, `request_09`, `request_12`, and `request_16` all have an expected
safe amount equal to the requested amount. They are capped cases: the solver's
baseline headroom is at least the requested amount, so both the benchmark and
the solver produce the cap. `request_16` has no projected cash-flow event before
the observed floor. The other three include repeat-stream forecasts but retain
more than enough headroom.

These are genuine affordability checks, but none reveals the benchmark's exact
minimum baseline. Consequently, they are not four independent validations of a
specific variable-spending forecast policy.

## Largest unexplained reserves

For each uncapped case, the oracle implies:

`expected implied floor = minimum_balance_to_keep + expected_safe_amount`.

`unexplained reserve = expected implied floor - predicted baseline minimum`.

A negative number means the current solver would need an additional future
debit/reserve to reach the benchmark floor; a positive number means it already
reserves more than the benchmark. The full numerical table is in
[`SAFE_AMOUNT_UNEXPLAINED_RESERVE.csv`](SAFE_AMOUNT_UNEXPLAINED_RESERVE.csv).

The largest additional-reserve cases are `request_04` (4,688,436.11),
`request_11` (3,709,732.90), `request_25` (1,938,300.00), `request_02`
(576,923.81), and `request_03` (221,847.18). Conversely, `request_19`
(994.09) and `request_15` (569.80) require the model to reserve *less* than the
current forecast. Those opposite-direction cases are decisive: a single
"reserve more for essentials" rule cannot explain all 21 uncapped samples.

## Supported hypotheses tested

### Variable essential-spending reserve — strongest but unproven

Nineteen uncapped cases have a predicted safe amount above the oracle. Many
have protected categories and repeated variable expenses, so the strongest
general hypothesis is that the benchmark reserves future variable essential
spending in addition to explicitly recurring / dated debits.

Evidence **for** it: the direction and magnitude of the 19 overestimates are
consistent with an omitted reserve, and the challenge requires conservative
essential-spending treatment.

Evidence **against** a production implementation: the public files do not
state a forward amount, cadence, aggregation statistic, or buffer rule for
those categories; current historical median, recent-value, and recurrence
identity variants did not increase the 4/25 exact score; and requests 15 and
19 need *less* reserve. An arbitrary category average/percentage would be
benchmark fitting rather than a deterministic reading of the supplied facts.

### OCR / message evidence

Local OCR recovered one unambiguous historical `Net Pay` amount for `image_01`.
It did not affect the relevant future cash-flow horizon. Other linked images
remain ambiguous and cannot safely be used as cash facts. A confirmed
message-derived income is already visible in request 15's decomposition.
Neither source supplies a cross-case missing reserve.

### FX, request-date ordering, lifecycle, and formula

The forensic rows identify actual binding dates and source IDs. The gaps are
not consistently one FX conversion, a request-day item, a pending-credit
violation, or a common failed/cancelled/duplicate treatment. The capacity
formula shifts every daily balance by a same-day one-off payment and remains
monotonic. No evidence supports changing it.

## Is the benchmark deterministically reproducible?

**Not uniquely from the participant-supplied information.** The challenge
requires a conservative treatment of essential variable spending but does not
specify how historical variable spending becomes a future dated 90-day schedule.
The expected values impose hidden numerical constraints that conflict in
direction across the uncapped requests. Multiple challenge-compliant forecasts
therefore remain possible.

The maximum defensible *observed* score under the current source-backed policy
is 4/25. There is no defensible numeric upper bound beyond that without a
specified essential-variable policy or additional future obligations. Reporting
a higher target would falsely imply that the missing data determines it.

## Decision

No general rule has been demonstrated across multiple cases strongly enough to
justify a production change. Production code remains unchanged. The next
legitimate way to improve reproducibility is to obtain an organizer-defined
policy for future essential variable spending (including cadence and amount
derivation) or additional dated financial evidence; it is not to tune values to
the sample oracle.
