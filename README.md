# Buy or Wait? — HackerRank Orchestrate 2026

This repository contains a fully local, deterministic financial-planning solver for the HackerRank **Buy or Wait?** challenge. It reads the supplied CSV dataset, produces one recommendation for every request, and validates the submission-shaped `output.csv`.

## Architecture and safety model

For each `request_id`, the agent loads the profile, financial events, payment options, messages, images, and dated exchange rates through validated ID-based joins. It normalizes source events into a home-currency cash ledger, reconciles validated evidence facts, calculates financial capacity, generates only source-supported payment plans, validates each plan with a 90-day daily forecast, and deterministically ranks the safe eligible plans. The final row is schema-validated before it is written.

Deterministic code owns all financial decisions: `Decimal` currency conversion using supplied dated rates; status/lifecycle treatment; recurrence expansion from source history; daily balance simulation; minimum-balance checks; safe-amount binary search; earliest-full-payment search; payment-plan validation; spending-change eligibility; ranking; and output validation.

Messages are interpreted by deterministic, bounded fact rules and reconciled with provenance. Final explanations are generated from verified structured facts using a deterministic template. Neither path has authority to alter a ledger, minimum balance, payment option, or recommendation.

### 90-day forecast

The simulator evaluates the request date plus the following 89 calendar days. It includes supplied settled cash events, reserves pending debits, includes scheduled debits and confirmed salary on their effective dates, and expands only recurrence patterns supported by history. It ignores pending credits, failed/cancelled records, recognized duplicates, and unrealized/non-cash investment values. A plan is safe only when every simulated closing balance remains at or above `minimum_balance_to_keep`.

### Plan selection

Only supplied payment options are used. Partial payment must use the exact two-payment public rule, while installment schedules must exactly equal a supplied option. Optional spending changes can target only permitted, non-protected, flexible recurring expenses and are capped at three actions. Among valid eligible plans, ranking is deterministic: complete by deadline, no spending changes, lower total paid, earlier start, fewer payments, then lower payment-option ID.

### Evidence limitations

Messages and images are untrusted data, never instructions. A missing event amount stays unknown—not zero—until local Tesseract OCR extracts a linked fact. To use local OCR, install Tesseract, set `LOCAL_OCR_ENABLED=1`, and optionally set `LOCAL_OCR_COMMAND` to its executable path. OCR contributes a fact only when exactly one amount is explicitly paired with the linked event's known currency; ambiguous results are ignored. See [FINAL_AUDIT.md](FINAL_AUDIT.md) for other limitations.

## Requirements

- Python 3.10 or newer
- The challenge `dataset/` directory included with this repository

No required third-party packages are used. `requirements.txt` is intentionally installable but empty of mandatory dependencies.

## Clean-machine quick start

From the repository root, create and activate a virtual environment.

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependency manifest (this is a no-op for the deterministic solver):

```bash
python -m pip install -r requirements.txt
```

Generate the submission output:

```bash
python main.py
```

This writes and validates `output.csv` in the repository root. The command is portable: `main.py` resolves the default `dataset/` and output paths relative to itself, not to the current working directory.

Run the complete test suite:

```bash
python run_tests.py
```

Run the independent full-dataset evaluator and write `evaluation_report.md`:

```bash
python evaluate.py
```

The expected success line is `Evaluated 250 rows; failures=0` for the included dataset and generated output.

## Commands and paths

| Purpose | Command |
| --- | --- |
| Generate output | `python main.py` |
| Use a different dataset/output location | `python main.py --dataset-dir path/to/dataset --output-path path/to/output.csv` |
| Run unit/integration tests | `python run_tests.py` |
| Validate an output file | `python evaluate.py` |
| Validate custom dataset/output paths | `python evaluate.py --dataset-dir path/to/dataset --output-path path/to/output.csv --report-path path/to/report.md` |

`main.py` is the sole public solver entry point. The implementation lives in `code/buy_or_wait/`; there is no second solver entry point under `code/`.

## Terminal request runner

Use the terminal request runner to inspect production requests without changing the financial engine:

```bash
python chat.py
python chat.py --debug
```

Enter one production request ID, for example `request_26`. The runner independently calls the same `solve_request` pipeline used by the submission flow and prints one concise labeled `REQUEST` / `AGENT DECISION` / `SOURCES` block. It then returns to the `>` prompt for another ID. Use `--csv` when a comma-separated record is required. There is no active conversation state, no natural-language follow-up mode, and no financial calculation in `chat.py`.

Process every production request without prompting:

```bash
python chat.py --all
python chat.py --all --output production_recommendations.txt
```

`chat.py` now defaults to `dataset/requests.csv` (currently 250 requests). `--all` processes every request in the selected production set; `--output` writes the same terminal records/diagnostics only and never replaces official `output.csv`. `--official` remains an explicit compatibility alias for the default. The optional `--debug` flag appends factual source/record diagnostics to each record. It does not expose chain-of-thought. The official solver remains `python main.py` and always uses `dataset/requests.csv` by default.

Run the labelled 25-request sample benchmark explicitly:

```bash
python chat.py --sample --all --compare
```

`--sample` is offline diagnostic mode only. It selects `dataset/sample_requests.csv`; its completed answer columns are loaded only after independent solving to display `--compare` results, never as solver input.

The exact 15-column terminal record header is available in `--all --csv` output and is also used by `--csv`. Sample comparison details, including every mismatch field and source context, are recorded in [SAMPLE_COMPARISON_AUDIT.md](SAMPLE_COMPARISON_AUDIT.md), with the current correctness findings in [SAMPLE_COMPARISON_REPORT.md](SAMPLE_COMPARISON_REPORT.md).

## Repository layout

```text
.
├── main.py                 # Portable solver entry point
├── run_tests.py            # Portable test runner
├── evaluate.py             # Independent output evaluator
├── requirements.txt        # Required dependencies (currently standard library only)
├── .env.example            # Optional local Tesseract OCR configuration
├── code/
│   ├── buy_or_wait/        # Solver, forecasting, planning, validation, evidence modules
│   └── tests/              # Unit and integration tests
├── dataset/                # Challenge inputs and referenced media
├── output.csv              # Generated submission output
└── evaluation_report.md    # Generated evaluation report
```

## Output contract

The solver writes these columns, in this exact order:

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

The system reads only `dataset/` as participant-facing input. It preserves amounts as `Decimal`, uses dated exchange rates supplied in the data, forecasts 90 days, and rejects unsafe plans that would breach the user’s minimum balance.

For complete challenge rules, input schema details, and submission requirements, see [problem_statement.md](problem_statement.md). The supporting engineering design is documented in [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Submission checklist

1. Run `python main.py`.
2. Run `python evaluate.py` and confirm zero failures.
3. Run `python run_tests.py`.
4. Run `python package_submission.py`. This creates a validated `code.zip` containing the runnable code, configuration template, README, prompts embedded in source, and the required `evaluation/usage_report.md`.
5. Submit `code.zip`, root `output.csv`, and the required chat transcript as separate artifacts. No deployment service, container, endpoint, or Docker image is required by the challenge materials.
6. Keep secrets, local virtual environments, datasets, generated outputs, and `log.txt` out of `code.zip`. Dataset paths remain configurable with `main.py --dataset-dir ...`.

The submission page is: <https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission>
