# Sample Comparison Report

## Run

Command used:

```text
python chat.py --all --compare
```

The run independently solved all 25 rows from `sample_requests.csv`, then
loaded the completed answer columns for comparison. The expected columns were
never supplied to `solve_request`.

- Requests processed: **25**
- Exact 15-field matches: **0**
- Mismatches: **25**
- Input-field mismatches: **0** (the eight request fields come from the same
  source row)
- Calculated-field mismatches: **25** (at least the explanation differs on
  every row; requests 09, 12, and 16 match on all non-explanation calculated
  fields)

## Mismatch table

The field lists below are exact output from the comparison harness. `amount`
means `amount_safe_to_pay`; all other names are output column names.

| Request | Mismatching fields |
|---|---|
| request_01 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_02 | amount_safe_to_pay, earliest_date_for_full_payment, decision_explanation |
| request_03 | amount_safe_to_pay, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_04 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_05 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_06 | amount_safe_to_pay, affordability_status, payment_plan, earliest_date_for_full_payment, spending_changes_needed, decision_explanation |
| request_07 | amount_safe_to_pay, earliest_date_for_full_payment, decision_explanation |
| request_08 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_09 | decision_explanation |
| request_10 | amount_safe_to_pay, earliest_date_for_full_payment, decision_explanation |
| request_11 | amount_safe_to_pay, affordability_status, earliest_date_for_full_payment, spending_changes_needed, decision_explanation |
| request_12 | decision_explanation |
| request_13 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_14 | amount_safe_to_pay, decision_explanation |
| request_15 | amount_safe_to_pay, decision_explanation |
| request_16 | decision_explanation |
| request_17 | amount_safe_to_pay, decision_explanation |
| request_18 | amount_safe_to_pay, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_19 | amount_safe_to_pay, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_20 | amount_safe_to_pay, decision_explanation |
| request_21 | amount_safe_to_pay, affordability_status, payment_plan, earliest_date_for_full_payment, spending_changes_needed, decision_explanation |
| request_22 | amount_safe_to_pay, earliest_date_for_full_payment, decision_explanation |
| request_23 | amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment, decision_explanation |
| request_24 | amount_safe_to_pay, decision_explanation |
| request_25 | amount_safe_to_pay, earliest_date_for_full_payment, decision_explanation |

The detailed prior-value/source audit is retained in
`SAMPLE_COMPARISON_AUDIT.md`. `SAMPLE_DATASET_ANALYSIS.md` adds the complete
request context and ten hand-checkable forecasts.

## Investigation findings

### Recurrence inference

The old code used only `event_type/category/direction/currency` as a stream
identity. In the actual data this merged unrelated descriptions (for example,
multiple kinds of groceries, transport, and dining) and could project a
historical category as one contractual stream. The audit changed recurrence
inference so fixed expense/income records require a matching description,
while subscription/debt-payment streams remain category-level and explicitly
flexible expenses remain grouped for spending-change eligibility. This is a
general source-backed rule, not a sample-ID exception.

This change explains why current results move substantially for requests 01,
03, 08, 10, 13, 19, and 25. It does not make the sample labels match, and it
was not tuned against individual expected values.

### Evidence and currency

The comparison confirms direct ID joins for messages/options/images. Blank
event amounts remain `None` until an image fact is validated; no missing amount
is converted to zero. Request 25 uses the dated USD→IDR exchange-rate rows.
Messages remain untrusted facts and cannot alter system rules or create
unsupported income/expenses.

### Plans and ranking

Installment schedules are copied from the supplied option exactly; partial
plans are generated only under the request permission, user method preference,
positive partial capacity, deadline, and exact two-payment constraints. Plan
validation and ranking are deterministic. Several sample label differences are
therefore downstream consequences of the forecast/capacity interpretation,
not invented payment options.

### Explanation differences

The sample explanations are prose labels, not a machine-normalized field. The
current explanation generator deliberately describes the computed amount,
minimum, selected method, date, and recurring constraints. It is not rewritten
to copy sample wording or numbers.

## Decision

No request-ID-specific or ground-truth-driven correction was made. The
recurrence identity fix is the only financial-engine change in this pass. The
remaining mismatches are preserved as visible failures for further challenge
interpretation rather than silently “corrected” to the oracle. The official
pipeline still reads `dataset/requests.csv` and its generated output passes
the repository's independent structural evaluator after regeneration.

