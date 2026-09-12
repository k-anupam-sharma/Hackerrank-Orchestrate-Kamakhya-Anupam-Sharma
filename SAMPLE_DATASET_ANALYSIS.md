# Sample Dataset Analysis

## Scope and method

This audit uses the 25 rows in `dataset/sample_requests.csv` as an input
fixture and treats its seven completed-answer columns as an oracle only after
an independent call to `solve_request`. No answer column is present on the
canonical `Request` model or passed into the solver. Supporting context comes
from the profiles, the user's financial events, request payment options,
messages, images, and dated exchange rates.

The repository contains 25 sample requests and 250 evaluation requests. The
supporting data contains 25,342 financial events, 215 messages, 16 image
references (all referenced PNGs exist), 790 payment options, and 134 dated
exchange-rate rows. Event statuses are: 25,148 settled, 71 pending, 70
scheduled, 22 cancelled, 21 failed, and 10 unrealized. Event types include
expenses, subscriptions, income, debt payments, refunds, investment purchases,
investment sales, and unrealized investment valuations.

## Request-by-request reconstruction

The `Current` column is the post-audit deterministic engine result; `Expected`
is the sample's completed answer. “Sources” lists representative forecast
anchors or explicit future rows, followed by relevant evidence and option IDs.

| ID | User | Date | Type / deadline | Requested | Minimum | Current safe / earliest | Expected safe / earliest | Sources |
|---|---|---|---|---:|---:|---|---|---|
| request_01 | user_01 | 2024-03-03 | purchase / 2024-03-20 | 25256 ZAR | 18000 | 18641.95 / empty | 25256 / 2024-03-03 | events 85,86,01,02,03,87,04,05; options 01–04 |
| request_02 | user_02 | 2025-08-05 | travel / 2025-10-10 | 46018000 IDR | 29158400 | 20024204.62 / 2025-09-13 | 17229139.2 / 2025-09-15 | event 105–111,104; message_01; options 05–07 |
| request_03 | user_03 | 2019-09-03 | education / 2019-11-15 | 5491000 IDR | 2668700 | 1094847.18 / 2019-11-13 | 873000 / 2019-11-15 | events 217–219,187–191; message_02; image_01/event_253; options 08–10 |
| request_04 | user_04 | 2024-06-04 | family_transfer / 2024-06-19 | 12693000 IDR | 30686600 | 12693000 / 2024-06-04 | 8401800 / 2024-06-15 | event_318 and scheduled event_357; message_03; options 11–12 |
| request_05 | user_05 | 2025-11-06 | debt_repayment / 2026-01-12 | 15488 ZAR | 13100 | 15488 / 2025-11-06 | 737 / empty | events 359–365; options 13–15 |
| request_06 | user_06 | 2026-01-03 | investment / 2026-01-14 | 620.40 EUR | 800 | 620.40 / 2026-01-03 | 603.30 / 2026-01-15 | events 497,499,500,440–444; message_04; options 16–18 |
| request_07 | user_07 | 2024-09-05 | housing / 2024-11-14 | 197400 INR | 93000 | 92813.21 / 2024-10-22 | 87170.56 / 2024-10-23 | events 606,607,559–562,558; message_05; options 19–21 |
| request_08 | user_08 | 2025-02-07 | emergency_expense / 2025-04-15 | 996.60 EUR | 800 | 0 / empty | 284.57 / 2025-04-15 | events 652,704–705,616–620; message_06; options 22–23 |
| request_09 | user_09 | 2026-07-04 | other / 2026-07-23 | 166.61 EUR | 600 | 166.61 / 2026-07-04 | 166.61 / 2026-07-04 | events 719–723,726–729; options 24–26 |
| request_10 | user_10 | 2024-12-06 | purchase / 2025-02-10 | 266700 INR | 225400 | 266700 / 2024-12-06 | 12700 / empty | events 892,869,893,789,794–797; message_07; options 27–28 |
| request_11 | user_11 | 2025-05-03 | travel / 2025-06-12 | 13110000 IDR | 34140600 | 13110000 / 2025-05-03 | 12510645 / 2025-07-15 | events 981–982,907–913; message_08; options 29–32 |
| request_12 | user_12 | 2026-04-05 | education / 2026-06-20 | 65164 ZAR | 43200 | 65164 / 2026-04-05 | 65164 / 2026-04-05 | events 1046–1047,991–995; message_09; options 33–35 |
| request_13 | user_13 | 2024-03-07 | family_transfer / 2024-05-15 | 941.60 EUR | 1300 | 941.60 / 2024-03-07 | 433.40 / 2024-05-15 | events 1057–1062,1100,1055; options 36–38 |
| request_14 | user_14 | 2025-08-04 | debt_repayment / 2025-10-04 | 5414.20 EUR | 2200 | 0 / empty | 597.74 / empty | events 1203,1163–1169; message_10; options 39–40 |
| request_15 | user_15 | 2026-01-06 | investment / 2026-02-01 | 3685 EUR | 1200 | 0 / empty | 83.05 / empty | events 1323–1325,1240–1244; message_11; options 41–43 |
| request_16 | user_16 | 2023-08-12 | housing / 2023-10-11 | 122500 INR | 122400 | 122500 / 2023-08-12 | 122500 / 2023-08-12 | events 1337–1342,1336,1344; message_12; image_02/event_1442; options 44–46 |
| request_17 | user_17 | 2026-03-01 | emergency_expense / 2026-05-04 | 274600 INR | 166100 | 252715.26 / 2026-03-15 | 243849.58 / 2026-03-15 | events 1530–1532,1444–1448; image_03/event_1545; options 47–49 |
| request_18 | user_18 | 2026-07-07 | other / 2026-09-15 | 3246.10 EUR | 1400 | 694.61 / 2026-08-14 | 462 / 2026-09-15 | events 1609–1610,1548–1552,1598; message_13; options 50–51 |
| request_19 | user_19 | 2024-09-04 | purchase / 2024-10-04 | 39660 INR | 92800 | 39660 / 2024-09-04 | 28820 / 2024-09-15 | events 1664,1623–1629,1622; image_04/event_1700; options 52–54 |
| request_20 | user_20 | 2026-02-07 | travel / 2026-02-22 | 303700 INR | 64500 | 24522.57 / empty | 5400 / empty | events 1762,1775–1776,1702–1706; message_14; image_05/event_1786; options 55–56 |
| request_21 | user_21 | 2026-04-03 | education / 2026-04-14 | 1574.40 USD | 1800 | 1574.40 / 2026-04-03 | 1543.35 / 2026-04-15 | events 1846–1847,1821,1789–1793; options 57–60 |
| request_22 | user_22 | 2024-12-05 | family_transfer / 2025-02-10 | 731.50 EUR | 500 | 534.12 / 2024-12-16 | 475.46 / 2025-01-15 | events 1922,1860–1865,1859; message_15; options 61–63 |
| request_23 | user_23 | 2025-05-07 | debt_repayment / 2025-07-15 | 38016 ZAR | 27000 | 11917.43 / 2025-07-17 | 9152 / 2025-07-15 | events 2003,1963–1969,1962; message_16; options 64–66 |
| request_24 | user_24 | 2026-01-04 | investment / 2026-02-08 | 109600 INR | 51000 | 15770.47 / empty | 13420 / empty | events 2102–2103,2138–2141,2044; message_17; options 67–68 |
| request_25 | user_25 | 2024-03-06 | housing / 2024-04-17 | 60496000 IDR | 23379100 | 3789638.40 / 2024-05-18 | 1425000 / empty | events 2264,2168–2173,2230; options 69–71; dated USD→IDR rates used for event_2167 |

## Ten manual forecast checks

The following are independent arithmetic checks of the current deterministic
90-day simulation. “Net events” is the sum of eligible event deltas over the
forecast; “plan payments” is the selected schedule (negative cash flow).

| Request | Starting balance | Net events | Plan payments | Lowest closing balance / date | Required minimum | Safe? |
|---|---:|---:|---:|---:|---:|---|
| 01 | 58481.10 | -21839.15 | 0 | 36641.95 / 2024-05-28 | 18000 | yes for selected fallback; full request is not selected |
| 02 | 60383889.20 | +47969570.44 | -47858720.01 | 32048331.57 / 2025-10-11 | 29158400 | yes |
| 03 | 5810300 | +5762863.66 | -5491000 | 3763547.18 / 2019-09-13 | 2668700 | yes |
| 04 | 52206950 | +55857237.43 | -12693000 | 31083836.11 / 2024-06-12 | 30686600 | yes |
| 05 | 46475.10 | +18144.39 | -15488 | 27980.94 / 2025-11-12 | 13100 | yes |
| 06 | 1942.40 | +1217.31 | -620.40 | 1114.40 / 2026-01-12 | 800 | yes |
| 07 | 218945.56 | +268935.17 | -205296 | 117381.21 / 2024-09-20 | 93000 | yes |
| 08 | 1536.57 | -1238.83 | 0 | 297.74 / 2025-05-07 | 800 | no |
| 09 | 2231.10 | -967.80 | -166.61 | 1096.69 / 2026-09-30 | 600 | yes |
| 10 | 750155 | +80315.10 | 0 | 714469.31 / 2025-01-08 | 225400 | yes for capacity; selected plan remains deadline-ineligible |

These checks expose why label matching alone is not a proof of arithmetic
correctness: the engine's forecast and the sample's completed answers diverge
on several policy choices, especially which historical spending streams count.

## Recurrence audit and generalized change

The previous implementation grouped every eligible event by
`event_type/category/direction/currency`. That merged unrelated descriptions
such as groceries, taxis, and restaurant visits into one inferred stream. It
also merged unrelated fixed income descriptions. The revised normalization
requires a matching `description` for fixed expenses and income, while keeping
subscription/debt-payment categories as contractual streams and keeping
explicitly flexible categories together for spending-change eligibility. The
change is source-driven and request-ID agnostic; it does not read sample answer
columns. Existing recurrence, forecast, and spending-change tests pass after
the change.

The sample oracle still disagrees with the implementation on many rows. That
is reported in `SAMPLE_COMPARISON_REPORT.md`; no label-specific correction was
introduced.

## Rule coverage seen in the sample

- Minimum balances and 90-day forecasts: all 25 rows.
- Recurring salary/expense streams: every profile has historical streams;
  requests 01, 02, 04, 08, 10, 13, 19, and 25 are useful boundary cases.
- Confirmed future salary: requests 01, 04, 13, and 25 have scheduled income.
- Pending/failed/cancelled/duplicate/unrealized records: present in the
  supporting data; event normalization and forecast tests exercise their cash
  treatment.
- Images and blank amounts: requests 03, 16, 17, 19, and 20 are linked to
  image references; event_253 is a known blank-amount image case.
- Messages: every early sample request with a message is joined by user or
  request; message_11 confirms income for request 15.
- Foreign currency: request 25 uses dated USD→IDR conversion for event_2167.
- Payment preferences, installments, partial payment, deadlines, and ranking:
  options 01–71 cover full payment, installments, and constrained plans.
- Flexible spending: requests 07, 21, and 22 exercise recurring flexible
  spending and spending-change output.

