# Final Hostile Evaluator Audit

## Scope and verdict

This audit reread `problem_statement.md` in full and inspected the deterministic solver, loaders, normalization, evidence, reconciliation, forecasting, planning, ranking, output validator, and tests. The public rules are mostly implemented deterministically. This is **not a blanket correctness certification**: the default offline path does not extract blank financial amounts from image pixels, so the mandatory image-amount rule is only satisfied when a validated image-capable adapter is configured. A narrower duplicate detector is also a residual risk for duplicate forms other than the explicit linked pending/settled representation.

`test_final_audit_adversarial.py` contributes **36 named adversarial subcases**. The test names below identify the exact matrix grouping; existing tests identify the narrower regression test where applicable.

| Requirement | Implementation | Test coverage | Deterministic? | Status and possible failure mode |
| --- | --- | --- | --- | --- |
| One output row for every evaluation request | `solve_all_requests`, `solve_dataset`, `validate_output_csv` | `test_evaluation`, `test_loaders.test_loads_every_real_dataset_and_builds_indexes` | Yes | Covered. A malformed externally edited CSV is rejected, but only after generation/validation. |
| Exact eight output columns and order | `loaders.OUTPUT_COLUMNS`, `SolvedRequest.as_csv_row`, `validate_output_csv` | `test_evaluation`, audit `output_mapping_uses_allowed_none_shape` | Yes | Covered. Hand-edited output is rejected by the evaluator. |
| `0 <= amount_safe_to_pay <= requested_amount` | `calculate_amount_safe_to_pay` binary search, output validator | `test_capacity`, `test_evaluation` | Yes | Covered to `0.01` quantum. Amounts with finer-than-cent precision would be rounded down by the search quantum. |
| **1. Maximum safe amount today** | `capacity.calculate_amount_safe_to_pay` simulates a request-date payment against the horizon | `test_capacity`, audit `safe_amount_is_capped_at_request`, `future_recurring_debits_reduce_capacity` | Yes | Covered. Depends on correct normalized facts; unknown image amounts are not treated as zero. |
| **2. 90-day safety check** | `forecast.forecast_balance`, `is_plan_safe`; default horizon is 90 calendar days including request day | `test_forecast`, audit `income_after_horizon_does_not_make_payment_safe` | Yes | Covered. Interpretation is day 0 through day 89; an evaluator interpreting “next 90” as day 1 through day 90 would differ at a boundary. |
| **3. Minimum balance never breached** | Daily closing balance compared by `is_plan_safe`; every candidate is validated | `test_forecast.test_payment_exactly_at_minimum_is_safe`, audit `one_cent_below_floor_is_unsafe` | Yes | Covered. Same-day flows are netted into a closing balance, not sequenced intraday; statement gives no intraday ordering rule. |
| **4. Recurring income** | Recurrence inference in `normalization._recurring_event_ids`; expansion in `_recurring_projections` | `test_forecast`, audit `recurring_income_cannot_rescue_request_day_breach` | Yes | Covered. Requires regular source history; irregular or sparse future income is intentionally not invented. |
| **5. Recurring expenses** | Same recurrence inference/expansion; debit sign applied in forecast | `test_forecast.test_recurring_expense_is_expanded_after_request_date`, audit `future_recurring_debits_reduce_capacity` | Yes | Covered. Inference uses a 7–35-day median/45-day gap heuristic; an unusual legitimate cadence may be missed. |
| **6. Confirmed future payments and salary** | `forecast._included_cash_delta` includes scheduled debits and scheduled salary credits | `test_forecast`, audit `scheduled_salary_is_counted` | Yes | Covered. Scheduled non-salary credits are deliberately excluded; this is conservative and aligned with explicit salary wording. |
| **7. Pending credits ignored** | `normalization._cash_treatment` -> `exclude_pending_credit`; forecast ignores it | `test_forecast`, audit `pending_credit_is_not_cash` | Yes | Covered. |
| Pending debits reserved | `reserve_pending_debit` and forecast inclusion | `test_forecast`, audit `pending_debit_is_reserved` | Yes | Covered. |
| **8. Failed transactions ignored** | `excluded_failed` | `test_forecast`, audit `failed_debit_is_ignored` | Yes | Covered. |
| **9. Cancelled transactions ignored** | `excluded_cancelled`; evidence cancellation replaces status | `test_forecast`, `test_reconciliation`, audit `cancelled_debit_is_ignored` | Yes | Covered. A cancellation can only affect an existing linked event. |
| **10. Duplicate records ignored** | `_is_linked_duplicate` recognizes a pending linked duplicate of an equal settled cash event | `test_normalization`, `test_forecast`, audit `duplicate_record_is_ignored` | Yes | Partial. Duplicate recognition is intentionally narrow; differently encoded duplicate rows may be counted unless linked/lifecycle rules identify them. |
| **11. Unrealized investments ignored** | `excluded_non_cash_or_unrealized` | `test_normalization`, `test_security`, audit `unrealized_value_is_ignored` | Yes | Covered. Investment requests remain affordability-only; no price prediction is performed. |
| **12. Dated foreign-currency conversion** | `convert_to_home_currency` requires exact `(settlement_date, from, to)` rate using `Decimal` | `test_normalization`, audit `dated_exchange_rate_uses_decimal`, `missing_exchange_rate_fails_closed` | Yes | Covered. Missing rate produces unknown conversion / explicit error, not invented money. |
| **13. Missing image amounts** | Blank raw amount remains `None`; `EvidenceProcessor` follows `event_id -> images.related_event_id -> image` and accepts validated adapter facts | `test_evidence.test_missing_amount_uses_event_to_image_link_and_keeps_provenance`, audit `missing_event_amount_remains_unknown` | Core pipeline yes; pixel extraction no | **Gap.** Default adapter is disabled and no OCR/vision provider is bundled, so default full-dataset execution does not extract image-only amounts. It fails closed rather than treating them as zero, but does not meet the “extract” requirement unaided. |
| **14. Messages/images are untrusted data** | `evidence` bounded fact types and provenance checks; `ai_adapter.FACT_SYSTEM_PROMPT`; reconciliation never executes content | `test_evidence`, `test_ai_adapter`, `test_security`, audit `hostile_instruction_is_not_fact` | Yes after extraction | Covered. A configured model may still return no useful facts; invalid/un-grounded candidates are rejected. |
| **15. Conflict resolution order** | `reconcile_evidence_facts`: cancellation/settlement/amendment, latest per source, settled preference, conservative amount/date chooser | `test_reconciliation`, `test_security`, audit `explicit_cancellation_becomes_bounded_fact`, `conflicting_debits_reserve_larger_amount`, `newer_same_source_amendment_wins` | Yes | Covered for supported fact types. Cross-source authority is represented only by source origin/timestamp, not a richer issuer-trust hierarchy. |
| Do not invent financial records/options | Evidence validation requires existing same-user linked event; plans originate in supplied options; reconciliation edits existing event only | `test_security`, `test_ai_adapter`, `test_plans` | Yes | Covered. `income_confirmed` is only attached to existing evidence context, not a new ledger record. |
| **16. Payment-method preferences** | `PlanGenerator` and `PlanValidator` require accepted method; `wait` maps to `full_payment` preference | `test_plans.test_payment_method_and_installment_limit_preferences_are_enforced`, `test_ranking` | Yes | Covered. |
| **17. Partial-payment rules** | `PlanGenerator` gates eligibility; `_validate_partial_plan` checks exactly two payments, dates, amount, sum, permission and earliest date | `test_plans`, audit `valid_partial_has_exact_two_payments`, `partial_remainder_mismatch_is_rejected` | Yes | Covered. |
| **18. Installment matching** | `_option_schedule`, `_validate_option_plan` compare all dates/amounts/total/fee to a supplied option | `test_plans.test_installment_schedule_must_exactly_match_supplied_option`, audit `installment_schedule_must_match_option` | Yes | Covered. |
| Installment-month preference | `_validate_option_plan` rejects absent/exceeded `max_installment_months` | `test_plans.test_payment_method_and_installment_limit_preferences_are_enforced` | Yes | Covered. |
| **19. Completion deadline** | `_completes_by_deadline`, PlanValidator error, ranking excludes incomplete plans | `test_plans.test_forecast_safety_and_deadline_errors_are_exposed`, audit `late_option_fails_deadline` | Yes | Covered. |
| **20. Flexible spending changes only** | `SpendingChangeEngine` requires recurring, flexible, debit expense/subscription, permitted category, non-protected stream, up to three actions | `test_spending_changes`, audit `protected_recurring_expense_cannot_change`, `stop_and_reduce_same_event_conflict` | Yes | Covered. Only source minimum reductions are emitted; no arbitrary reduction is invented. |
| **21. Earliest safe full-payment date** | `find_earliest_safe_full_payment_date` scans chronological candidate dates without spending changes | `test_capacity`, audit `earliest_safe_date_is_first_salary_date` | Yes | Covered. It is independent of method preference as required. |
| **22. Plan ranking** | `ranking._rank_key`: completion, no changes, lower total, earlier start, fewer payments, option ID | `test_ranking`, audit `no_change_plan_outranks_cheaper_changed_plan` | Yes | Covered. Option IDs use trailing numeric order; nonnumeric IDs would use a deterministic but potentially different interpretation of “lowest.” |
| **23. Output formatting** | `ranking._format_payment_plan`, `_format_spending_changes`, `SolvedRequest.as_csv_row`, whole-file validator | `test_ranking.test_mapping_uses_exact_allowed_statuses_and_output_format`, `test_evaluation` | Yes | Covered. Formatting uses non-scientific Decimal text. |
| **24. Explanation consistency** | `build_explanation_facts`, deterministic template, `validate_explanation` rejects unverified literals/methods | `test_explanations`, `test_ai_adapter`, audit `explanation_with_invented_amount_is_rejected`, `explanation_with_conflicting_method_is_rejected` | Yes after optional rephrase | Covered. The fallback can only state selected structured facts; optional rephrase is rejected on mismatch. |
| Required allowed statuses/methods | Constants and output validator | `test_ranking`, `test_evaluation` | Yes | Covered. |
| Dataset joins, IDs, dates, Decimals | `loaders.load_dataset` validates columns, IDs, foreign keys, media paths, parsed dates, and Decimals | `test_loaders` | Yes | Covered. Missing/invalid source rows stop loading with diagnostics. |
| Required submission artifacts | `package_submission.py`, `evaluation/usage_report.md`, archive validator | `test_evaluation` plus end-to-end package run documented in `README.md` | Yes | Outside financial engine. Archive validation checks presence/nonempty report, not HackerRank upload success. |

## Adversarial test inventory

The new matrix has 36 scenarios across these named groups:

1. Cash-treatment matrix: pending credit/debit, failed, cancelled, duplicate, unrealized, scheduled bonus, scheduled salary (8).
2. Floor/horizon matrix: exact floor, one-cent breach, post-horizon income, negative proposed payment (4).
3. Capacity/recurrence matrix: request cap, recurring debit, recurring income at request-day boundary, first salary date (4).
4. Currency/missing-amount matrix: dated Decimal rate, absent rate, missing amount, identity precision (4).
5. Untrusted-evidence/conflict matrix: hostile prompt, cancellation, conflicting debits, newest same-source amendment (4).
6. Payment-plan matrix: valid partial, incorrect remainder, preference rejection, altered installment schedule (4).
7. Deadline/spending/ranking/output matrix: late plan, protected expense, same-event conflict, fallback shape (4).
8. Explanation/ranking matrix: invented amount, conflicting method, no-change precedence, nonempty deterministic explanation (4).

## Result to report

Run after adding the matrix:

```text
python -m unittest test_final_audit_adversarial -v
Ran 8 tests (36 named subcases): OK
```

The audit intentionally reports the image-extraction and duplicate-detection limitations above rather than claiming full compliance. No solver feature or financial behavior was changed during this audit.
