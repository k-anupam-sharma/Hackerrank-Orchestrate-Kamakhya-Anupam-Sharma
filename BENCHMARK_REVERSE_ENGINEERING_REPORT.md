# Benchmark reverse-engineering report

## Summary

The four exact public-sample matches are capped cases: request_01, request_09, request_12, and request_16. Because their expected safe amount equals the request amount, they only establish that the benchmark has at least enough headroom for the request; they do not identify its exact minimum baseline.

The 21 uncapped cases are therefore the useful constraints. Their data is in [EXPECTED_FORECAST_CONSTRAINTS.csv](EXPECTED_FORECAST_CONSTRAINTS.csv). Production is above the benchmark in 19 cases and below it in 2. No controlled, general candidate policy produced a fifth exact amount-safe match, so production code was intentionally left unchanged.

## Constraint and direction analysis

- Agent too high: 19 cases; total absolute error 7,708,292.49; mean 405,699.60.
- Agent too low: request_15 and request_19; total absolute error 1,077.14; mean 538.57.

The magnitude is currency-dependent, so those absolute totals are diagnostic only. The important pattern is directional: a policy that simply reserves more money could help many high cases but necessarily worsens the two low cases.

## Current versus implied forecast

For every uncapped request, the expected implied minimum is the profile floor plus expected safe amount. This is a constraint rather than a reconstructed event schedule. An amount difference does not establish which event caused it. Event-level production inputs, source IDs, cash treatment, and dates are already available in [SAMPLE_EVENT_FORECAST_AUDIT.csv](SAMPLE_EVENT_FORECAST_AUDIT.csv); uncertainty is marked rather than converted into invented benchmark events.

## Protected and variable spending

[PROTECTED_EXPENSE_ANALYSIS.md](PROTECTED_EXPENSE_ANALYSIS.md) tests controlled analysis-only reserve policies. Historical protected groceries/transport/healthcare activity is common in the too-high group, but it is not universal and the too-low cases prove it is insufficient as a single rule.

Candidate results across all 21 uncapped cases:

| policy | exact matches | MAE |
|---|---:|---:|
| current baseline | 0 | 367,112.84 |
| latest protected-variable reserve | 0 | 365,866.39 |
| median protected-variable reserve | 0 | 365,620.56 |
| average protected-variable reserve | 0 | 365,647.79 |
| confirmed-future-protected only | 0 | 367,112.84 |

No candidate earns implementation: none improves exact matches, and the reserves are not supplied financial commitments.

## Recurrence and income findings

Recurring source streams, scheduled cash, pending debits, and confirmed salary are already inputs to the daily baseline. The formula itself is correct for a fixed baseline. A controlled attempt to make forecast recurrence identity stricter by source description did not improve the 4/25 safe-amount result and broke established recurrence/spending-change tests; it was reverted.

Potential evidence gaps include image-backed blank historical amounts for requests 03, 17, 19, and 20, and some unquantified/message-only payroll or expense context. The model deliberately does not create values from those gaps. Dated exchange-rate conversion was verified for the foreign-currency case.

## Lifecycle, timing, and horizon findings

No systematic raw data retrieval, double counting, failed/cancelled/duplicate inclusion, pending-credit inclusion, or unrealized-investment inclusion defect was found. Pending debits are reserved. The daily semantics use opening current balance plus all eligible same-day events less proposed payment; the 90-day range is day 0 through day 89. The capacity formula was independently boundary- and monotonicity-tested.

## Root-cause matrix

[SAMPLE_ROOT_CAUSE_MATRIX.csv](SAMPLE_ROOT_CAUSE_MATRIX.csv) records evidence-bounded likely causes and confidence per uncapped request. It distinguishes confirmed lifecycle handling from unresolved recurrence, evidence, and variable-spending interpretation. It deliberately labels unsupported claims as possible or low confidence.

## Smallest evidence-supported change

None was found that improves the exact benchmark above 4/25. The smallest sound action is no production behavior change. A category-level protected-variable reserve would be a new financial assumption, improves only mean error slightly, gains zero exact cases, and conflicts with the under-estimated cases.

## Before and after

Before analysis: 4/25 safe amounts, 16%.
After controlled analysis: 4/25 safe amounts, 16%.

No claim is made that the benchmark is solved. The reports identify the remaining information required for a defensible rule: an organizer-defined budgeting policy for essential variable spending and/or evidence extraction for blank image amounts.
