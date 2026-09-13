# Performance Report

## Scope

Profiled the deterministic full run over `dataset/requests.csv` (250 requests) with no external inference configured.

## Benchmark

| Version | Dataset load | Solve 250 requests | Total | Notes |
|---|---:|---:|---:|---|
| Pre-optimization | completed load, full solve did not return a completed timing in the 30-second benchmark harness window | >30s | >30s | Conservative censored baseline |
| Optimized | 0.462s | 26.229s | 26.691s | Full 250-row run completed |

The measured improvement is therefore at least 11% versus the 30-second lower bound for the prior full solve. No stronger percentage is claimed because the prior harness result was censored rather than timed to completion.

## Behavior check

The optimized solver was run over all 250 requests and its serialized rows were compared directly with the committed `output.csv`.

```text
rows=250
row_mismatches=0
```

## Changes

1. Validate baseline plans before expanding spending-change combinations. If any no-change plan is valid and completes by the deadline, skip spending-change generation because the challenge ranking always prefers no spending changes. This cannot change the selected plan.
2. Compute the eligible spending-change action universe once per request and reuse it across candidate schedules.
3. Cache extracted evidence facts by request within an `EvidenceProcessor` instance. This prevents repeated deterministic parsing, optional model calls, and image handling when a request context is revisited.

## Deliberately unchanged

- CSV loading remains a single initial parse through `DatasetIndex`.
- Currency conversions remain deterministic and source-date-specific; no approximate cache was introduced.
- Capacity scans and 90-day forecasts are not shared across different payment schedules because their inputs differ.
- No external inference is invoked; the solver runs locally.
