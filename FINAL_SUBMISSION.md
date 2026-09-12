# Final Submission Pass

## Architecture summary

The solution is a terminal-run Python pipeline rooted at `main.py`. It loads validated CSV data from a configurable dataset directory, joins each request to its user profile, financial events, payment options, messages, images, and dated exchange rates, then emits one validated `output.csv` row per evaluation request.

The financial core is deterministic. Raw events are normalized into a home-currency ledger using `Decimal`; evidence facts are reconciled only onto existing events; a daily 90-day cash forecast calculates capacity; source-backed payment plans are generated and validated; and a deterministic ranker selects the final recommendation. The output writer revalidates the generated CSV against the public schema.

## Key design decisions

- Use `Decimal`, never binary floating point, for financial amounts.
- Use exact supplied settlement-date exchange rates; missing rates fail closed rather than inventing a conversion.
- Forecast the request date plus the following 89 calendar days, with a plan safe only when every daily closing balance remains at or above the configured minimum.
- Reserve pending debits; exclude pending credits, failed/cancelled events, recognized duplicates, and unrealized/non-cash values.
- Infer recurrence only from source history and never invent income, expenses, payment options, or reductions.
- Require installment schedules to exactly equal supplied options and enforce the exact two-payment partial-payment rule.
- Rank valid eligible plans by deadline completion, no spending changes, lower total cost, earlier start, fewer payments, then payment-option ID.

## Safety mechanisms

- Messages and images are untrusted data, not instructions. Their model/deterministic extraction surface accepts only bounded fact types with source IDs and validation.
- Optional LLM use is restricted to fact extraction and closed-fact explanation phrasing. It cannot calculate balances, determine safety, change rules, create records, or rank plans.
- Conflict reconciliation applies explicit cancellation/settlement/amendment, newer same-source evidence, settled-state preference, then a financially conservative interpretation.
- Spending changes are limited to up to three permitted, non-protected, flexible recurring expenses; stopping and reducing the same event is rejected.
- The output evaluator independently checks identities, enums, money bounds, plan shape/totals, deadlines, installment equality, change eligibility, and simulated safety.

## Final validation results

| Check | Result |
| --- | --- |
| Discovered test count | 84 |
| Full test suite | Passed (no failures observed) |
| Additional hostile matrix | 36 named adversarial subcases passed |
| Generated output rows | 250 |
| Required header/order | Valid |
| NaN/null literal scan | 0 findings |
| Amount bounds, dates, enums, request-ID scan | 0 findings |
| Independent `evaluate.py` result | 250 rows; 0 validation failures |
| Submission archive | `python package_submission.py` built and validated `code.zip` |

The evaluator result verifies implemented structural and financial safety checks; it does not establish hidden-label accuracy.

## Known limitations and risks

- Default offline execution follows image links and preserves missing amounts as unknown, but it does **not** perform OCR/vision extraction from image pixels unless a validated image-capable adapter is configured. It fails closed rather than treating a missing amount as zero.
- Duplicate recognition is deliberately conservative and primarily covers the linked pending/settled duplicate lifecycle. A differently encoded duplicate could require additional source-specific reconciliation.
- The forecast uses daily closing balances, not an unspecified intraday event order.
- No claim of perfect prediction accuracy is made; hidden ground-truth scoring remains external.

See [FINAL_AUDIT.md](FINAL_AUDIT.md) for rule-level traceability and adversarial coverage.

## Reproducible run instructions

```bash
python -m venv .venv
# Activate .venv for your platform.
python -m pip install -r requirements.txt
python main.py
python run_tests.py
python evaluate.py
python package_submission.py
```

`main.py` accepts `--dataset-dir` and `--output-path`; `evaluate.py` accepts `--dataset-dir`, `--output-path`, and `--report-path`. The deterministic default requires no secrets or network. Optional provider configuration is documented in `.env.example` and `README.md`; API keys must stay in environment variables and out of version control.

The challenge submission is repository-based: submit the generated `code.zip`, root `output.csv`, and the required chat transcript separately.
