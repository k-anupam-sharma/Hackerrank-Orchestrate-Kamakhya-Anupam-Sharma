# Benchmark Information Completeness

This assessment treats `dataset/sample_requests.csv` answer columns only as an
offline oracle. They were not read by the solver. The assessment is based on
the request input, profile, event, message, image, payment-option, and fixed-FX
files available to a participant.

## Meaning of the classifications

- **Deterministically derivable**: the files specify the fact and its timing or
  amount sufficiently for the current challenge rules to apply it.
- **Partially derivable**: the fact exists, but a required interpretation such
  as recurrence identity, future cadence, or cash treatment remains open.
- **Ambiguous**: more than one challenge-consistent forecast follows from the
  supplied history and metadata.
- **Not derivable**: no supplied evidence establishes the value.

The eight request-input fields are deterministically derivable for all 25
samples. The table concerns the forecast-dependent output fields, especially
`amount_safe_to_pay`.

| Request | Structured profile / dated events | Message / image evidence | 90-day cash-flow model | Exact safe amount | Assessment |
|---|---|---|---|---|---|
| request_01 | Deterministically derivable | No required unstructured evidence | Partially derivable | Partially derivable (capped) | A full payment is demonstrably safe under the observed model, but the cap does not reveal the benchmark floor. |
| request_02 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Large recurring-category reserve is required by the oracle but no unique forward schedule is supplied. |
| request_03 | Partially derivable | Linked image amount is historical; OCR can identify it but it does not uniquely specify future spending | Ambiguous | Ambiguous | Several historical debit streams can be treated as recurring or variable essential spending. |
| request_04 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | The oracle implies a multi-million reserve beyond the current repeat-stream schedule. |
| request_05 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Repeated discretionary/variable history does not define a future contractual amount. |
| request_06 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Small residual reserve cannot be uniquely allocated to a dated future event. |
| request_07 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Category history supports more than one recurrence/essential interpretation. |
| request_08 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | The difference is smaller than one clear independently scheduled obligation. |
| request_09 | Deterministically derivable | No required unstructured evidence | Partially derivable | Partially derivable (capped) | Full payment is safe; the cap supplies no exact baseline constraint. |
| request_10 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Essential-variable versus optional history is not supplied as a dated commitment. |
| request_11 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | The implied additional reserve is large but cannot be mapped one-to-one to a provided future event. |
| request_12 | Deterministically derivable | No required unstructured evidence | Partially derivable | Partially derivable (capped) | Full payment is safe; exact floor remains unknown. |
| request_13 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | A historical category stream does not carry an explicit next-payment date/amount. |
| request_14 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Competing valid recurrence cadence interpretations remain. |
| request_15 | Partially derivable | A confirmed message-derived income is deterministic once accepted | Ambiguous | Ambiguous | The oracle requires less reserve than the current conservative schedule; files do not establish which current debit should be excluded. |
| request_16 | Deterministically derivable | No required unstructured evidence | Deterministically derivable for affordability | Partially derivable (capped) | There are no projected cash-flow events before the observed floor; full payment remains above the minimum. |
| request_17 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Variable spending / recurrence policy controls the gap. |
| request_18 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | No explicit future item accounts for the required residual reserve. |
| request_19 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | The oracle is less conservative than the current forecast, so an unproven reserve rule cannot explain it. |
| request_20 | Partially derivable | Dated debit evidence is derivable | Ambiguous | Ambiguous | Mandatory, optional, and repeated expenditure categories do not uniquely yield the oracle reserve. |
| request_21 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Small gap has no uniquely identified future source. |
| request_22 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | Small gap is not tied to an explicit event. |
| request_23 | Partially derivable | Dated debit evidence is derivable | Ambiguous | Ambiguous | Fixed versus variable portions of repeated spending remain open. |
| request_24 | Partially derivable | Dated debit evidence is derivable | Ambiguous | Ambiguous | The oracle requires an extra reserve, but no single supplied stream defines it. |
| request_25 | Deterministically derivable | No required unstructured evidence | Ambiguous | Ambiguous | The large implied reserve cannot be reconstructed from an explicit dated obligation. |

## Information that is actually missing from the public inputs

The dataset includes historical transactions, categories, flexibility flags,
and protected-category preferences. It does **not** give a deterministic
forward schedule or required future amount for variable essential categories.
Nor does it prescribe a rule such as average, median, latest transaction, or a
percentage buffer for turning those historical purchases into 90-day cash-flow
commitments. The challenge asks that essential variable spending be forecast
conservatively, but does not mathematically resolve this choice.

For linked blank-amount images, only `image_01` produced a uniquely usable OCR
amount. The other linked images did not yield an unambiguous final amount and
currency. Using a speculative OCR number would violate the requirement not to
invent financial facts.

## Consequence

The benchmark's full-payment affordability is reproducible for the four capped
cases. The exact uncapped safety floors are not uniquely reproducible from the
available inputs without selecting an unsupported policy for future variable
essential spending or selectively relaxing existing projected streams.
