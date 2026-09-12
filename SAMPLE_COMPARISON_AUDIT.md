# Sample comparison audit (historical pre-recurrence-fix snapshot)

> This file preserves the first full mismatch audit for traceability. The
> current post-fix values and field lists are in `SAMPLE_COMPARISON_REPORT.md`
> and `SAMPLE_DATASET_ANALYSIS.md`.

Run: `python chat.py --all --compare`

The agent result was generated first by the existing deterministic pipeline. The labelled columns from `sample_requests.csv` were loaded only afterward for comparison. No expected value was passed to forecasting, evidence reconciliation, plan generation, validation, ranking, or explanation generation.

## Result

- Sample rows processed: 25
- Exact 15-field matches: 0
- Mismatches: 25
- Input fields (`request_id` through `request_text`) matched for every row.
- The three rows whose non-explanation calculated fields match are `request_09`, `request_12`, and `request_16`; their explanation text still differs, so they are not exact 15-field matches.
- No sample image fact was used. `request_15` used `message_11`. `request_25` used dated USD→IDR exchange-rate rows.

The mismatch report below is diagnostic evidence, not a request to copy labels into the agent. `floor/date` is the minimum closing balance and date in the forecast built from the agent’s selected plan. Event and option IDs are the source records visible to the computation.

| Request | Balance / required minimum | Agent safe / expected safe | Agent earliest / expected | Forecast floor / date | Mismatching fields | Likely interpretation to investigate |
| --- | ---: | ---: | --- | --- | --- | --- |
| request_01 | 58481.10 / 18000 | 7325.14 / 25256 | none / 2024-03-03 | 25325.14 / 2024-05-31 | amount, status, method, plan, earliest, explanation | Expected full payment conflicts with recurring future debits and the minimum-balance floor. |
| request_02 | 60383889.20 / 29158400 | 18376094.03 / 17229139.2 | 2025-10-13 / 2025-09-15 | 47534494.03 / 2025-08-12 | amount, status, method, plan, earliest, explanation | Installment eligibility/date interpretation differs; supplied options are payment_option_05–07. |
| request_03 | 5810300 / 2668700 | 0.00 / 873000 | none / 2019-11-15 | 2015996.94 / 2019-11-17 | amount, status, method, plan, earliest, explanation | Future cash-flow interpretation keeps the balance below the required floor before the labelled wait date. |
| request_04 | 52206950 / 30686600 | 10283912.78 / 8401800 | 2024-06-13 / 2024-06-15 | 36415383.56 / 2024-07-11 | amount, plan, earliest, explanation | Date-boundary/recurrence interpretation differs by two days. |
| request_05 | 46475.10 / 13100 | 15488.00 / 737 | 2025-11-06 / none | 26871.69 / 2025-11-12 | amount, status, method, plan, earliest, explanation | Agent finds a safe supplied full-payment option; expected label rejects it. |
| request_06 | 1942.40 / 800 | 620.40 / 603.3 | 2026-01-03 / 2026-01-15 | 1050.85 / 2026-01-12 | amount, status, plan, earliest, spending, explanation | Label requires `stop:event_476`; current no-change plan already validates as safe. |
| request_07 | 218945.56 / 93000 | 87730.86 / 87170.56 | 2024-10-22 / 2024-10-23 | 110690.30 / 2024-11-18 | amount, earliest, explanation | One-day full-payment boundary differs. |
| request_08 | 1536.57 / 800 | 0.00 / 284.57 | none / 2025-04-15 | -399.97 / 2025-05-07 | amount, status, method, plan, earliest, explanation | Forecast reaches below the floor; labelled wait plan needs a different cash-treatment interpretation. |
| request_09 | 2231.10 / 600 | 166.61 / 166.61 | 2026-07-04 / 2026-07-04 | 1901.79 / 2026-07-12 | explanation | Calculated fields match; only deterministic explanation wording differs. |
| request_10 | 750155 / 225400 | 266700.00 / 12700 | 2024-12-06 / none | 726024.38 / 2024-12-08 | amount, earliest, explanation | Capacity is materially larger than the label; inspect the expected treatment of future income/expenses. |
| request_11 | 63531795 / 34140600 | 13110000.00 / 12510645 | 2025-05-03 / 2025-07-15 | 46162895.15 / 2025-05-11 | amount, status, earliest, spending, explanation | Label requires `reduce_to:event_989:665950`; no-change full payment validates under current rules. |
| request_12 | 193089.89 / 43200 | 65164.00 / 65164 | 2026-04-05 / 2026-04-05 | 187518.07 / 2026-04-10 | explanation | Calculated fields match; only explanation wording differs. |
| request_13 | 2789.52 / 1300 | 941.60 / 433.4 | 2024-03-07 / 2024-05-15 | 1847.92 / 2024-03-07 | amount, status, method, plan, earliest, explanation | Early capacity differs from labelled later-wait interpretation. |
| request_14 | 3931.74 / 2200 | 0.00 / 597.74 | none / none | -2179.22 / 2025-10-26 | amount, explanation | Both reject the request, but the available capacity differs while the forecast breaches the floor. |
| request_15 | 1770.05 / 1200 | 0.00 / 83.05 | none / none | -1774.32 / 2026-04-04 | amount, explanation | Both reject; message_11 is the only relevant message and must remain untrusted evidence. |
| request_16 | 362370 / 122400 | 122500.00 / 122500 | 2023-08-12 / 2023-08-12 | 239870 / 2023-08-12 | explanation | Calculated fields match; only explanation wording differs. |
| request_17 | 550379.58 / 166100 | 264785.37 / 243849.58 | 2026-03-15 / 2026-03-15 | 335690.70 / 2026-03-14 | amount, explanation | Same installment plan/date; safe-now capacity differs. |
| request_18 | 2486 / 1400 | 539.39 / 462 | 2026-09-13 / 2026-09-15 | 1939.39 / 2026-07-14 | amount, plan, earliest, explanation | Label waits two days longer; inspect date inclusion around the salary/expense boundary. |
| request_19 | 199545 / 92800 | 39660.00 / 28820 | 2024-09-04 / 2024-09-15 | 135568.84 / 2024-09-13 | amount, method, plan, earliest, explanation | Ranking chooses supplied installments; label chooses permitted partial payment. |
| request_20 | 102609.05 / 64500 | 16559.51 / 5400 | none / none | 81059.51 / 2026-02-12 | amount, explanation | Both reject; available capacity differs. |
| request_21 | 3911.35 / 1800 | 1574.40 / 1543.35 | 2026-04-03 / 2026-04-15 | 1877.94 / 2026-04-11 | amount, status, plan, earliest, spending, explanation | Label requires `stop:event_1815|reduce_to:event_1816:23.50`; current no-change plan is safe. |
| request_22 | 1132.46 / 500 | 458.85 / 475.46 | 2025-01-16 / 2025-01-15 | 522.94 / 2025-02-15 | amount, earliest, spending, explanation | Label has no spending change; current engine selects `stop:event_1892`; inspect flexible-change ranking. |
| request_23 | 51957.90 / 27000 | 8619.13 / 9152 | 2025-07-17 / 2025-07-15 | 35619.13 / 2025-05-15 | amount, status, method, plan, earliest, explanation | Expected wait plan is not selected under current safe-capacity/date scan. |
| request_24 | 85045 / 51000 | 15959.92 / 13420 | none / none | 66959.92 / 2026-01-12 | amount, explanation | Both reject; safe partial capacity differs. |
| request_25 | 32063050 / 23379100 | 968802.58 / 1425000 | 2024-05-18 / none | 24347902.58 / 2024-03-14 | amount, earliest, explanation | Foreign-currency conversion is present; inspect dated USD→IDR rate selection and future cash-flow treatment. |

## Source context by request

The following IDs are the forecast-affecting event records and supplied payment-option records observed in the comparison run. All rows also use the corresponding `financial_profiles.csv` user record and the request row from `sample_requests.csv`.

```text
request_01 events: event_102,event_58,event_27,event_84,event_97,event_28,event_29,event_30,event_103,event_31,event_32; options: payment_option_01..04
request_02 events: event_138,event_139,event_185,event_140,event_162,event_141,event_175,event_143,event_136,event_142,event_184,event_144; options: payment_option_05..07
request_03 events: event_212,event_254,event_213,event_234,event_215,event_214,event_216,event_252,event_243,event_211; options: payment_option_08..10
request_04 events: event_286,event_317,event_289,event_343,event_287,event_356,event_357,event_288,event_290,event_284,event_291; options: payment_option_11..12
request_05 events: event_394,event_393,event_424,event_396,event_397,event_437,event_395,event_390,event_398,event_392; options: payment_option_13..15
request_06 events: event_556,event_473,event_496,event_474,event_476,event_475,event_477,event_471,event_478,event_472; options: payment_option_16..18
request_07 events: event_580,event_596,event_581,event_582,event_614,event_605,event_578,event_583; options: payment_option_19..21
request_08 events: event_647,event_648,event_677,event_649,event_703,event_716,event_643,event_650,event_651,event_646; options: payment_option_22..23
request_09 events: event_748,event_770,event_750,event_749,event_751,event_746,event_779,event_788,event_752; options: payment_option_24..26
request_10 events: event_891,event_834,event_839,event_866,event_837,event_835,event_904,event_836,event_838,event_840; options: payment_option_27..28
request_11 events: event_942,event_943,event_967,event_944,event_945,event_980,event_946,event_947,event_989,event_949,event_948; options: payment_option_29..32
request_12 events: event_1036,event_1016,event_1015,event_1017,event_1002,event_1045,event_1054,event_1018,event_1014; options: payment_option_33..35
request_13 events: event_1087,event_1121,event_1092,event_1147,event_1090,event_1160,event_1161,event_1091,event_1093,event_1094,event_1095; options: payment_option_36..38
request_14 events: event_1194,event_1226,event_1196,event_1239,event_1195,event_1198,event_1199,event_1197,event_1200; options: payment_option_39..40
request_15 events: event_1297,event_1322,event_1267,event_1268,event_1335,event_1269,event_1270,event_1271,event_1272; message: message_11; options: payment_option_41..43
request_16 events: event_1364,event_1402,event_1428,event_1441,event_1371,event_1372,event_1374,event_1373,event_1375,event_1376; options: payment_option_44..46
request_17 events: event_1472,event_1529,event_1542,event_1473,event_1474,event_1475,event_1476,event_1546,event_1477,event_1471; options: payment_option_47..49
request_18 events: event_1573,event_1574,event_1576,event_1595,event_1575,event_1608,event_1621,event_1571,event_1577; options: payment_option_50..51
request_19 events: event_1686,event_1656,event_1658,event_1699,event_1657,event_1660,event_1661,event_1654,event_1659,event_1655; options: payment_option_52..54
request_20 events: event_1787,event_1738,event_1761,event_1740,event_1774,event_1739,event_1733,event_1783,event_1741,event_1742,event_1737,event_1743; options: payment_option_55..56
request_21 events: event_1857,event_1814,event_1836,event_1816,event_1815,event_1817,event_1858,event_1845,event_1854,event_1818,event_1812; options: payment_option_57..60
request_22 events: event_1945,event_1961,event_1889,event_1920,event_1958,event_1890,event_1891,event_1887,event_1893,event_1894; options: payment_option_61..63
request_23 events: event_2027,event_1996,event_2042,event_1998,event_1997,event_2040,event_2000,event_2001,event_1994,event_1999,event_2002; options: payment_option_64..66
request_24 events: event_2077,event_2101,event_2078,event_2080,event_2163,event_2079,event_2081,event_2166,event_2082,event_2075,event_2083; options: payment_option_67..68
request_25 events: event_2286,event_2201,event_2225,event_2202,event_2204,event_2203,event_2205,event_2288,event_2206,event_2199,event_2207; options: payment_option_69..71; rates: 2024-03-15 USD->IDR, 2024-02-15 USD->IDR
```

## Decision

No financial code was changed in response to these mismatches. The differences require a separate challenge-rule investigation, especially recurrence/date semantics, safe-capacity treatment, spending-change preference, and sample-label provenance. The CSV serializer and comparison report therefore preserve the independently calculated result exactly.
