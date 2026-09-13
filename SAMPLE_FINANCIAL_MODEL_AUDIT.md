# Sample financial-model audit

## Dataset inventory and joins

The files contain 275 profiles, 25 public sample requests, 250 evaluation requests, 25,342 financial events, 790 request payment options, 215 messages, 16 image links, and 134 dated exchange-rate rows. `user_id` joins requests to profiles/events/messages/images; `request_id` joins requests to payment options and request-scoped messages/images; `related_event_id` joins messages/images to one supplied event; exchange rates join on `(rate_date, from_currency, to_currency)`.

Actual event types are: expense 20,525; subscription 2,488; income 1,696; debt_payment 567; investment_purchase 29; refund 22; investment_valuation 10; investment_sale 5. Statuses are: settled 25,148; pending 71; scheduled 70; cancelled 22; failed 21; unrealized 10. Flexibility values are fixed 21,138, reducible 2,682, stoppable 1,297, and reducible_or_stoppable 225.

## Rules checked

- Historical settled events are not replayed directly before the request date; the profile balance is the starting balance.
- Future settled/scheduled cash is included at its effective cash date. Pending debits reserve cash, pending credits are excluded. Failed, cancelled, duplicates, unrealized valuations, and non-cash records are excluded.
- Recurrence is source-backed, described in `RECURRENCE_MODEL.md`, and expanded over the 90-day inclusive horizon.
- Conversion uses the exact dated supplied rate and `Decimal`; no live rate or float arithmetic is used.
- Amount capacity is the deterministic maximum request-date payment before changes. A plan is safe only when every daily closing balance is at least the profile floor.
- Payment options are copied exactly; partial plans require two payments and the request permission; waiting is independent of payment-method preference for capacity but requires accepted `full_payment` for recommendation.
- Plans are validated before ranking. Ranking is deterministic and local.

## Request 01 reconstruction

Profile: `user_01`, home currency ZAR, starting balance `58481.10`, minimum `18000`. Request date is `2024-03-03`; requested amount is `25256`; deadline is `2024-03-20`; only `full_payment` is accepted.

Relevant future cash-flow records after the request date:

| date | source | signed amount | treatment | reason |
|---|---|---:|---|---|
| 2024-03-04 | recurring `event_56` grocery stream | -881.22 | recurring settled cash | exact repeated description |
| 2024-03-05 | `event_102` | -567.60 | pending debit reserve | settlement date is future |
| 2024-03-06/08/11/13 | `event_27`–`event_31` | -10,653.07 total | recurring settled cash | utilities, education, debt, subscriptions |
| 2024-03-15 | `event_103` | +23,320.00 | scheduled cash | confirmed next salary |
| 2024-03-21 onward | recurring `event_56`, `event_27`–`event_32` | debits | recurring settled cash | source-backed monthly/weekly streams |

Historical rows before 2024-03-03 are used only as recurrence evidence, not replayed as cash. No cancelled, failed, duplicate, unrealized investment, image-derived amount, or foreign-currency conversion contributes to this request. Flexible dining descriptions are not treated as one fixed recurring charge.

With a `ZAR 25,256` payment on 2024-03-03, the deterministic minimum projected closing balance is `ZAR 18,682.97` on 2024-05-28. Therefore the payment is safe, the earliest full-payment date is the request date, and the selected method is `full_payment`. The sample oracle's required floor is met without copying any answer column.

## Before/after sample result

The pre-change independent freeze is in `BEFORE_FIX_SAMPLE_RESULTS.csv` and `BEFORE_FIX_COMPARISON.md`. The post-change independent results are in `AFTER_FIX_SAMPLE_RESULTS.csv` and `AFTER_FIX_COMPARISON.md`. The completed answer columns are read only for comparison. Amounts in comparisons are numeric `Decimal` comparisons, not string-format comparisons.

The current post-change comparison has 25 processed requests, 4 exact structured matches, and 21 requests with at least one structured mismatch. Request 01 is now an independent structured match (including amount, status, method, plan, earliest date, and spending changes). Remaining mismatches are reported rather than silently corrected; they mostly involve conservative treatment of highly variable essential spending, flexible streams, and oracle-specific future cash-flow assumptions.

## Double-counting audit

No historical event before the request date is directly applied to the opening balance. Explicit linked duplicates are excluded. Cancelled/failed/pending-credit/unrealized records do not create cash. A scheduled event is applied once at its planned event date. The remaining model risk is semantic, not an accidental duplicate replay: recurrence inference can be more conservative or less conservative than the public sample oracle when a category contains variable purchases.
