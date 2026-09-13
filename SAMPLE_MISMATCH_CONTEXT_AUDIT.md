# Sample mismatch context audit (21 requests)

## Scope and method

This is a read-only diagnostic of the 21 sample requests that were not exact
structured matches in the current run.  It does **not** compare request fields
to themselves.  The sample row is used only to select a request and to read the
oracle output fields after the independent run.  No completed answer column was
passed to the solver.

For every request I independently loaded the profile, all events for the user,
messages for the user/request, linked image references, request payment
options, and dated exchange-rate index.  I then ran the current deterministic
pipeline (normalization, evidence extraction/reconciliation, baseline
90-day forecast, capacity, plan generation/validation/ranking).  “Raw join
accuracy” below means that the IDs and foreign-key joins came from the
authoritative CSV rows; it is intentionally separate from whether a message or
image was interpreted.

The current default model adapter is disabled.  Therefore linked image files
are located and validated, but a blank source amount remains unknown unless a
provider returns an image fact.  This is reported as missing evidence, never as
zero.

### Independent result versus sample oracle

| request_id | agent safe | expected safe | difference (agent - expected) | agent status / method | agent plan | agent earliest full payment | agent changes |
|---|---:|---:|---:|---|---|---|---|
| request_02 | 17806063.01 | 17229139.2 | 576923.81 | affordable_with_plan / installments | 2025-08-08:15952906.67\|2025-09-07:15952906.67\|2025-10-07:15952906.67 | 2025-09-15 | none |
| request_03 | 1094847.18 | 873000 | 221847.18 | affordable_later / wait | 2019-11-15:5491000 | 2019-11-15 | none |
| request_04 | 12693000 | 8401800 | 4291200 | affordable_now / full_payment | 2024-06-04:12693000 | 2024-06-04 | none |
| request_05 | 7299.49 | 737 | 6562.49 | not_affordable / not_recommended | none | empty | none |
| request_06 | 620.40 | 603.3 | 17.10 | affordable_now / full_payment | 2026-01-03:620.40 | 2026-01-03 | none |
| request_07 | 99307.07 | 87170.56 | 12136.51 | affordable_with_plan / installments | 2024-09-12:68432\|2024-10-10:68432\|2024-11-07:68432 | 2024-10-22 | none |
| request_08 | 366.65 | 284.57 | 82.08 | affordable_later / wait | 2025-04-15:996.6 | 2025-04-15 | none |
| request_10 | 44220.79 | 12700 | 31520.79 | not_affordable / not_recommended | none | empty | none |
| request_11 | 13110000 | 12510645 | 599355 | affordable_now / full_payment | 2025-05-03:13110000 | 2025-05-03 | none |
| request_13 | 941.60 | 433.4 | 508.20 | affordable_now / full_payment | 2024-03-07:941.60 | 2024-03-07 | none |
| request_14 | 759.82 | 597.74 | 162.08 | not_affordable / not_recommended | none | empty | none |
| request_15 | 0 | 83.05 | -83.05 | not_affordable / not_recommended | none | empty | none |
| request_17 | 255788.02 | 243849.58 | 11938.44 | affordable_with_plan / installments | 2026-03-01:95194.67\|2026-03-31:95194.67\|2026-04-30:95194.67 | 2026-03-15 | none |
| request_18 | 694.61 | 462 | 232.61 | affordable_later / wait | 2026-08-15:3246.1 | 2026-08-15 | none |
| request_19 | 27825.91 | 28820 | -994.09 | affordable_with_plan / partial_payment | 2024-09-04:27825.91\|2024-09-15:11834.09 | 2024-09-15 | none |
| request_20 | 15782.57 | 5400 | 10382.57 | not_affordable / not_recommended | none | empty | none |
| request_21 | 1574.40 | 1543.35 | 31.05 | affordable_now / full_payment | 2026-04-03:1574.40 | 2026-04-03 | none |
| request_22 | 534.12 | 475.46 | 58.66 | affordable_with_plan / installments | 2024-12-08:253.59\|2025-01-05:253.59\|2025-02-02:253.59 | 2024-12-15 | none |
| request_23 | 11917.43 | 9152 | 2765.43 | affordable_later / wait | 2025-07-15:38016 | 2025-07-15 | none |
| request_24 | 17688.49 | 13420 | 4268.49 | not_affordable / not_recommended | none | empty | none |
| request_25 | 3363300 | 1425000 | 1938300 | not_affordable / not_recommended | none | 2024-05-15 | none |

The table is a comparison only; expected values were not used in any forecast
or plan calculation.

## What the agent actually retrieved and used

The following records are the exact request-level context passed through the
current pipeline.  “events” is raw authoritative event-row count followed by
normalized count.  Treatment counts are the normalized cash treatment used by
the simulator.  `settled_cash`, `scheduled_cash`, and
`reserve_pending_debit` are cash-flow inputs; excluded statuses are not cash
inputs.  “recurring” is the number of normalized source rows eligible for the
recurrence expansion.  “baseline” is the minimum closing balance/date before
the request payment and before spending changes.

| request_id | profile used (home currency; current balance; minimum) | events used | evidence actually interpreted | payment options retrieved | treatment / recurrence summary | baseline minimum | raw join accuracy |
|---|---|---|---|---|---|---|---:|
| request_02 | IDR; 60383889.2; 29158400 | 82 / 82 | message_01 present, no fact (Indonesian payroll increase not parsed); no images | payment_option_05,06,07 | 81 settled_cash + 1 reserve_pending_debit; 51 recurring; 1 direct future; 32 projected | 46964463.01 on 2025-08-14 | 100% |
| request_03 | IDR; 5810300; 2668700 | 69 / 69 | message_02 present, no fact; image_01 linked to event_253 exists, but blank amount has no image fact | payment_option_08,09,10 | 68 settled_cash + 1 reserve_pending_debit; 33 recurring; 1 direct; 27 projected | 3763547.18 on 2019-09-14 | 100% |
| request_04 | IDR; 52206950; 30686600 | 103 / 103 | message_03 present, no fact (bonus explicitly pending/not approved) | payment_option_11,12 | 102 settled_cash + 1 scheduled_cash; 53 recurring; 1 direct; 41 projected | 43776836.11 on 2024-06-13 | 100% |
| request_05 | ZAR; 46475.1; 13100 | 81 / 81 | no messages or images | payment_option_13,14,15 | 80 settled_cash + 1 excluded_failed; 36 recurring; 21 projected | 20399.49 on 2026-02-02 | 100% |
| request_06 | EUR; 1942.4; 800 | 119 / 119 | message_04 present, no fact (temporary salary reduction not parsed) | payment_option_16,17,18 | 118 settled_cash + 1 excluded_cancelled (event_557); 60 recurring; 42 projected | 1480.70 on 2026-01-13 | 100% |
| request_07 | INR; 218945.56; 93000 | 57 / 57 | message_05 present, no fact (confirmed payroll date change not parsed) | payment_option_19,20,21 | 57 settled_cash; 32 recurring; 21 projected | 192307.07 on 2024-09-20 | 100% |
| request_08 | EUR; 1536.57; 800 | 102 / 102 | message_06 produced `income_confirmed` EUR 1422.85, undated; no images | payment_option_22,23 | 102 settled_cash; 53 recurring; 35 projected | 1166.65 on 2025-02-12 | 100% |
| request_10 | INR; 750155; 225400 | 116 / 116 | message_07 present, no fact (pending/non-withdrawable gig payout correctly not credited) | payment_option_27,28 | 116 settled_cash; 53 recurring; 40 projected | 269620.79 on 2025-03-03 | 100% |
| request_11 | IDR; 63531795; 34140600 | 85 / 85 | message_08 present, no fact (base salary/commission wording not parsed) | payment_option_29,30,31,32 | 85 settled_cash; 40 recurring; 24 projected | 50360977.90 on 2025-05-14 | 100% |
| request_13 | EUR; 2789.52; 1300 | 107 / 107 | no messages or images | payment_option_36,37,38 | 106 settled_cash + 1 scheduled_cash; 55 recurring; 1 direct; 31 projected | 2648.13 on 2024-03-14 | 100% |
| request_14 | EUR; 3931.74; 2200 | 78 / 79 (one bounded synthetic evidence income row) | message_10 produced dated `income_confirmed` EUR 2717 on 2025-08-15; childcare addition was not quantified | payment_option_39,40 | 78 settled_cash + 1 scheduled_cash; 45 recurring; 1 direct; 28 projected | 2959.82 on 2025-08-14 | 100% |
| request_15 | EUR; 1770.05; 1200 | 96 / 97 (one bounded synthetic evidence income row) | message_11 produced dated `income_confirmed` EUR 1661 on 2026-01-15 | payment_option_41,42,43 | 96 settled_cash + 1 scheduled_cash; 38 recurring; 1 direct; 25 projected | 713.25 on 2026-04-04 | 100% |
| request_17 | INR; 550379.58; 166100 | 104 / 104 | image_03 linked to blank event_1545 exists, but no image amount fact | payment_option_47,48,49 | 103 settled_cash + 1 scheduled_cash; 49 recurring; 1 direct; 39 projected | 421888.02 on 2026-03-13 | 100% |
| request_18 | EUR; 2486; 1400 | 75 / 75 | message_13 transfer note present, no fact; no linked transfer rows were introduced | payment_option_50,51 | 75 settled_cash; 36 recurring; 21 projected | 2094.61 on 2026-07-11 | 100% |
| request_19 | INR; 199545; 92800 | 79 / 79 | image_04 linked to blank event_1700 exists, but no image amount fact | payment_option_52,53,54 | 79 settled_cash; 51 recurring; 37 projected | 120625.91 on 2024-09-14 | 100% |
| request_20 | INR; 102609.05; 64500 | 87 / 87 | message_14 refund remains uncredited; image_05 linked to blank pending event_1786 has no image fact | payment_option_55,56 | 84 settled_cash + 2 reserve_pending_debit + 1 excluded_pending_credit; 46 recurring; 1 direct; 29 projected | 80282.57 on 2026-02-13 | 100% |
| request_21 | USD; 3911.35; 1800 | 71 / 71 | no messages or images | payment_option_57,58,59,60 | 68 settled_cash + 1 excluded_non_cash_or_unrealized + 1 reserve_pending_debit + 1 scheduled_cash; 35 recurring; 2 direct; 20 projected | 3463.99 on 2026-04-12 | 100% |
| request_22 | EUR; 1132.46; 500 | 103 / 103 | message_15 explicitly says portfolio rise had no sale/cash; no fact | payment_option_61,62,63 | 101 settled_cash + 1 excluded_non_cash_or_unrealized + 1 reserve_pending_debit; 48 recurring; 1 direct; 30 projected | 1034.12 on 2024-12-14 | 100% |
| request_23 | ZAR; 51957.9; 27000 | 81 / 81 | message_16 prize claim pending, correctly no income fact; no images | payment_option_64,65,66 | 80 settled_cash + 1 reserve_pending_debit; 46 recurring; 1 direct; 27 projected | 38917.43 on 2025-05-14 | 100% |
| request_24 | INR; 85045; 51000 | 124 / 124 | message_17 confirms settled prize after withholding; no image fact | payment_option_67,68 | 123 settled_cash + 1 scheduled_cash; 72 recurring; 1 direct; 45 projected | 68688.49 on 2026-01-13 | 100% |
| request_25 | IDR; 32063050; 23379100 | 122 / 122 | no messages or images | payment_option_69,70,71 | 120 settled_cash + 1 excluded_failed + 1 scheduled_cash; 60 recurring; 1 direct; 42 projected | 26742400.00 on 2024-03-14 | 100% |

### Payment-option details used

The option IDs above were loaded directly from
`request_payment_options.csv`; no option was invented.  The options selected
by the current planner are reproduced in the first table.  Notable raw option
examples include request_02 option 05 (3 x IDR 15952906.67, first 2025-08-08,
30-day frequency), request_07 option 19 (3 x INR 68432, 28-day frequency),
request_17 option 47 (3 x INR 95194.67, 30-day frequency), request_21 option
57 (USD 1574.40 full payment), and request_22 option 61 (3 x EUR 253.59,
28-day frequency).  The complete amounts, counts, dates, fees and totals were
read from the authoritative rows; the agent did not synthesize financing terms.

### Currency and exchange-rate use

All requests except request_25 used home-currency events in the current
forecast.  Request_25 contains USD-to-IDR historical rows converted using the
dated exchange-rate rows for 2023-10-15, 2023-11-15, 2023-12-15, 2024-01-15,
2024-02-15, and 2024-03-15.  No request-level foreign-currency lookup was
missing in this run.

## Per-request discrepancy diagnosis

The following fields are deliberately about the *financial context*, not a
comparison of request columns.  “Missing context” means a raw fact was not
available to deterministic processing (most often an image amount or an
unparsed natural-language amendment).  “Incorrect context” means an
interpretation that changed forecast inputs; it does not claim the source CSV
row itself was wrong.

| request_id | context_retrieval_accuracy | missing_context | incorrect_context | incorrect_event_classification | incorrect_forecast_inputs | root cause (primary categories) |
|---|---:|---|---|---|---|---|
| request_02 | 100% raw joins; partial evidence interpretation | message_01 salary increase/effective date not structured | recurring salary remained at source amount | none in terminal status; salary amendment not propagated | future salary stream is not amended; variable/essential future spending is not conservative enough | C recurrence + D forecast; B evidence parsing |
| request_03 | 100% raw joins | image_01 amount for blank event_253; message_02 payroll adjustment not structured | blank salary evidence was omitted rather than resolved | blank linked salary is absent from forecast | missing future salary/adjustment and recurrence treatment alter minimum | B evidence + D forecast |
| request_04 | 100% raw joins | no missing row; bonus is explicitly unapproved | none for bonus (correctly not counted) | historical/variable expense streams are treated too lightly | baseline reaches safety too early; future expense profile differs from benchmark | C recurrence + D forecast |
| request_05 | 100% raw joins | none | none | failed event is correctly excluded | grocery/transport-like variable streams are not represented conservatively enough | C recurrence + D forecast |
| request_06 | 100% raw joins | message_04 salary reduction not structured | temporary reduced salary is not reflected | event_557 cancellation is correctly excluded | event_476 is not selected as an allowed spending intervention because forecast is already considered safe | C recurrence + D forecast + G plan eligibility |
| request_07 | 100% raw joins | message_05 date amendment not structured | payroll date remains source date | no terminal-status error | one-day income timing shifts earliest date and capacity | B evidence + C recurrence + D timing |
| request_08 | 100% raw joins; amount fact extracted | message amount has no explicit effective date | undated income amendment is applied as latest salary amount without dated schedule | no status error | recurring/variable expense treatment still produces a higher minimum | C recurrence + D forecast |
| request_10 | 100% raw joins | none; pending gig payout is intentionally not cash | none for pending/non-withdrawable income | pending income is correctly excluded | expense recurrence and conservative variable-spend treatment leave excess capacity | C recurrence + D forecast |
| request_11 | 100% raw joins | message_08 Indonesian salary/commission fact not structured | commission constraint is not represented as evidence | no terminal-status error | expected dining reduction is not required because forecast underestimates future debits | B evidence + C/D forecast + G spending plan |
| request_13 | 100% raw joins | none | none | scheduled salary is included | future expense/recurrence model makes full payment safe immediately instead of later | C recurrence + D forecast |
| request_14 | 100% raw joins; one evidence row appended | childcare amount is not stated, so no amount can be invented | salary fact is used, but new childcare is unquantified | no status error | missing conservative childcare amount and variable-spend treatment affect safety | C/D forecast; not a retrieval failure |
| request_15 | 100% raw joins; one evidence row appended | none for first salary date | first salary is represented, but later recurring debits drive the minimum below floor | no status error | recurrence/expense timing produces zero capacity instead of a small safe amount | C recurrence + D forecast |
| request_17 | 100% raw joins | image_03 amount for blank grocery event_1545 | unknown image event is omitted (not treated as zero) | no terminal-status error | missing grocery debit can raise projected capacity; other recurrence treatment dominates direction | B evidence + D forecast |
| request_18 | 100% raw joins | message_13 transfer note has no extracted fact; no linked transfer rows exist | message does not create unsupported transfer cash flow | no raw transfer row to classify | earliest date is one month earlier and capacity higher than benchmark; likely recurring/variable timing | C recurrence + D forecast |
| request_19 | 100% raw joins | image_04 amount for blank grocery event_1700 | unknown image event omitted safely | no terminal-status error | other recurring streams over/under-offset the missing grocery; partial amount is lower than expected | B evidence + C/D forecast |
| request_20 | 100% raw joins | image_05 amount for pending utility event_1786 | refund remains excluded and pending debits reserved correctly | pending credit is excluded; pending debits reserved | unquantified utility debit and variable-spend model leave excess capacity | B evidence + D forecast |
| request_21 | 100% raw joins | none | none for unrealized investment/pending debit; both handled per rules | unrealized event excluded; pending debit reserved | forecast says full payment is safe, so flexible stop/reduce variants are not generated/selected | C recurrence + D forecast + G spending plan |
| request_22 | 100% raw joins | none | portfolio increase is correctly treated as non-cash | unrealized value excluded and pending debit reserved | recurring/dated debits make safe full payment later than current model reports | C recurrence + D forecast |
| request_23 | 100% raw joins | prize is pending and intentionally has no cash fact | none; unsupported prize income is not added | pending debit reserved | variable/recurring expense profile is less conservative than benchmark | C recurrence + D forecast |
| request_24 | 100% raw joins | none | settled prize proceeds are included; no future prize is invented | settled event included, scheduled insurance included | future expense recurrence drives a lower benchmark capacity than current model | C recurrence + D forecast |
| request_25 | 100% raw joins | none | failed debit excluded; scheduled salary included | no terminal-status error | forecast reaches a later minimum and reports a later date while benchmark never permits full payment | C recurrence + D forecast |

## Classification of the failure modes requested in the audit

- **A — wrong data retrieval:** no raw foreign-key/join failure was found. All
  21 requests retrieved their profile, event set, messages/images, options,
  and rate index correctly. Image rows were found, but their blank amounts were
  not extracted with the disabled adapter.
- **B — wrong event/evidence classification:** secondary issue for requests
  02, 03, 06, 07, 11, 17, 19, and 20. The most concrete examples are
  unparsed multilingual/date amendments and unavailable linked-image amounts.
  Terminal statuses (failed, cancelled, pending credit, unrealized) were
  generally classified safely.
- **C — wrong recurrence detection:** the dominant model risk. Repeated
  historical rows are expanded as recurrence even where the data also looks
  variable/discretionary, and source amendments do not always update the
  recurrence anchor.
- **D — wrong 90-day forecast:** the dominant observable consequence. The
  baseline minimum, minimum date, and therefore capacity/earliest-date result
  disagree for most rows even when joins and terminal-status handling are
  correct.
- **E — wrong minimum-balance calculation:** not demonstrated by this audit;
  the simulator applies the profile floor and the analytical capacity is
  internally consistent with the baseline it receives.
- **F — wrong amount mathematics:** not the primary explanation. The safe
  amount is calculated from the baseline minimum minus the floor; the input
  baseline is what differs. Boundary tests in the existing suite pass for the
  supplied forecast model.
- **G — wrong payment-plan logic:** downstream effects occur for requests 04,
  06, 11, 18, 21, 22, and 25 because the wrong capacity/earliest date changes
  eligibility. The supplied installment schedules themselves are reproduced,
  not invented.
- **H — wrong ranking logic:** no independent ranking-only defect was isolated;
  ranking follows the deterministic plan keys once candidate safety and
  eligibility have been computed.

## Conclusion

The most common root cause is **C/D: recurrence and 90-day forecast-input
treatment**, not request retrieval and not arithmetic in isolation.  The model
has the authoritative rows and correctly ignores the major unsafe terminal
states, but it does not yet represent the benchmark's future cash-flow profile
consistently: variable versus contractual streams, evidence-amended salary/date
facts, and blank image amounts are the recurring gaps.  These forecast-input
differences then propagate deterministically into safe amount, earliest date,
spending-change selection, and (where applicable) plan status.

No application code or financial logic was modified for this diagnostic.
