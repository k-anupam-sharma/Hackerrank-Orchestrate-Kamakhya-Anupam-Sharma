# Recurrence model

## Why the old rule was unsafe

The previous implementation grouped every flexible expense in a category and projected the latest amount. In `user_01`, unrelated dining descriptions (bakery, lunch, takeaway, and delivery) therefore became one mandatory recurring stream. That manufactured future debits and reduced the safe amount from the supplied independent result of `25256` to `18641.95`.

The forecast also advanced monthly records by a median number of days. A 15th-of-the-month salary consequently drifted to the 14th and then the 13th, which caused date errors in requests 02–04 and similar cases.

## Current general rule

1. Ignore failed, cancelled, duplicate, unrealized, windfall, and non-cash records for recurrence inference.
2. A normal `expense` or `income` stream is identified by event type, category, direction, currency, and exact source description. A category alone is not an identity for ordinary spending.
3. `subscription` and `debt_payment` are contractual categories, so their category-level identity is retained when dates show a regular 7–35 day cadence.
4. At least three source observations and regular gaps (median 7–35 days, no gap over 45 days) are required.
5. Payroll-like repeated income (`payroll`, `salary`, `employer`, household income, or wage descriptions) may vary in amount and uses the latest observed amount conservatively. Other changing income, including platform/gig payouts, is not invented future salary. A later description containing an explicit terminal marker (`final`, `last`, `termination`, or `terminated`) stops the prior income stream.
6. Flexible expenses are not automatically recurring merely because their category repeats. They remain eligible for a spending change only when the source data establishes a recurring stream.
7. Monthly streams with a stable day-of-month advance by calendar month, clamping only for short months. Weekly/biweekly/irregular streams retain a median-day cadence.
8. A scheduled record uses its planned `event_date` as the cash-flow date; its later `settlement_date` is preserved for provenance and currency conversion. Pending debits reserve cash on settlement; pending credits remain excluded.
9. An unlinked message can be a source-backed payroll anchor only when it states a currency amount and explicit salary/payroll confirmation language. A dated message saying a regular salary resumes is projected monthly from that date; an undated notice amends the latest recurring payroll amount; a singular first-salary notice is a one-time confirmed credit. No amount, balance, or expense is inferred from vague text.

## Actual-data implications

`user_01` now keeps rent, utilities, education, debt, subscriptions, the evidenced `Supermarket basket` stream, the pending debit, and the confirmed scheduled salary. Changing dining descriptions are not projected as a fixed charge. The 90-day minimum after paying `ZAR 25,256` is `ZAR 18,682.97` on 2024-05-28, above the `ZAR 18,000` floor.

This model intentionally does not turn every weekly grocery/transport observation into a fixed commitment. The challenge says to detect recurrence only when history supports it and to forecast essential variable spending conservatively; category-level conservative budgeting remains a documented limitation for users whose only evidence is highly variable category history. It is safer than treating unrelated descriptions as contractual charges and is auditable from source IDs.
