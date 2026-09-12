# Buy or Wait? — HackerRank Orchestrate 2026

This repository contains a deterministic financial-planning solver for the HackerRank **Buy or Wait?** challenge. It reads the supplied CSV dataset, produces one recommendation for every request, and validates the submission-shaped `output.csv`.

The default solver is offline and needs no API key or third-party package. Optional LLM assistance is strictly bounded to extracting facts from untrusted messages/images and rephrasing already verified explanations; financial arithmetic, forecasting, validation, and ranking remain deterministic.

## Architecture and safety model

For each `request_id`, the agent loads the profile, financial events, payment options, messages, images, and dated exchange rates through validated ID-based joins. It normalizes source events into a home-currency cash ledger, reconciles validated evidence facts, calculates financial capacity, generates only source-supported payment plans, validates each plan with a 90-day daily forecast, and deterministically ranks the safe eligible plans. The final row is schema-validated before it is written.

Deterministic code owns all financial decisions: `Decimal` currency conversion using supplied dated rates; status/lifecycle treatment; recurrence expansion from source history; daily balance simulation; minimum-balance checks; safe-amount binary search; earliest-full-payment search; payment-plan validation; spending-change eligibility; ranking; and output validation.

The optional LLM layer has no financial authority. It may turn relevant message/image content into bounded, provenance-carrying facts and may rephrase a closed set of already verified explanation fields. Its response is schema-validated and reconciled before use. It cannot create a new ledger event, alter a minimum balance, choose a plan, calculate money, or follow instructions contained in untrusted evidence. If it is unavailable or invalid, the solver safely falls back to deterministic behavior.

### 90-day forecast

The simulator evaluates the request date plus the following 89 calendar days. It includes supplied settled cash events, reserves pending debits, includes scheduled debits and confirmed salary on their effective dates, and expands only recurrence patterns supported by history. It ignores pending credits, failed/cancelled records, recognized duplicates, and unrealized/non-cash investment values. A plan is safe only when every simulated closing balance remains at or above `minimum_balance_to_keep`.

### Plan selection

Only supplied payment options are used. Partial payment must use the exact two-payment public rule, while installment schedules must exactly equal a supplied option. Optional spending changes can target only permitted, non-protected, flexible recurring expenses and are capped at three actions. Among valid eligible plans, ranking is deterministic: complete by deadline, no spending changes, lower total paid, earlier start, fewer payments, then lower payment-option ID.

### Evidence limitations

Messages and images are untrusted data, never instructions. A missing event amount stays unknown—not zero—until a validated image-capable adapter extracts a linked fact. The offline default deliberately does not perform image OCR/vision extraction; see [FINAL_AUDIT.md](FINAL_AUDIT.md) for this and other known limitations.

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

Install the dependency manifest (this is a no-op for the deterministic solver, but keeps the workflow stable if optional dependencies are enabled later):

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

## Optional LLM configuration

The solver works without these settings. To enable the optional OpenAI adapter, first install its SDK explicitly and create a local environment file from the example:

```bash
python -m pip install openai
cp .env.example .env                 # macOS / Linux
Copy-Item .env.example .env          # Windows PowerShell
```

Set values in `.env` through your shell or environment manager before running; the application reads environment variables but intentionally does not load `.env` files itself. This avoids a hidden dependency and keeps deployment configuration explicit.

```text
LLM_PROVIDER=openai
LLM_MODEL=<supported-model-name>
OPENAI_API_KEY=<your-api-key>
LLM_MAX_RETRIES=2
```

Never commit `.env` or an API key. If the provider, model, or key is absent, unavailable, or returns invalid data, the solver falls back safely to deterministic behavior.

## Commands and paths

| Purpose | Command |
| --- | --- |
| Generate output | `python main.py` |
| Use a different dataset/output location | `python main.py --dataset-dir path/to/dataset --output-path path/to/output.csv` |
| Run unit/integration tests | `python run_tests.py` |
| Validate an output file | `python evaluate.py` |
| Validate custom dataset/output paths | `python evaluate.py --dataset-dir path/to/dataset --output-path path/to/output.csv --report-path path/to/report.md` |

`main.py` is the single solver entry point. `code/main.py` remains a compatibility entry point for the original starter layout; use the root command above for a portable clean-machine workflow.

## Interactive testing chatbot

Use the terminal chatbot to inspect real request decisions without changing the financial engine:

```bash
python chat.py
python chat.py --debug
```

Type `list` to see evaluation request IDs, then `select request_26` (or enter an ID directly). That creates an active request session containing the loaded request context, the computed solver result, validated evidence facts, normalized events, displayed payment plan, and 90-day forecast. Every follow-up keeps using that cached active state until `select <another_request>`, `reset`, or `exit`; normal questions do not rerun the solver.

Use `summary`, `forecast`, `plan`, `explanation`, and `sources`. `sources` shows factual provenance for the active request, while `sources request_69` inspects a different request without replacing the active one. Plain-language follow-ups cover affordability, safe amount, current/minimum balance, income, expenses, payment options, plan, forecast, and sources. The `--debug` mode shows source-backed events/facts, messages, images when a validated image fact exists, candidate plans, rejection reasons, and the selected plan; it does not expose chain-of-thought. The chatbot uses the same dataset and `solve_request` pipeline as the submission runner and does not ask an LLM to calculate money or make a recommendation.

## Repository layout

```text
.
├── main.py                 # Portable solver entry point
├── run_tests.py            # Portable test runner
├── evaluate.py             # Independent output evaluator
├── requirements.txt        # Required dependencies (currently standard library only)
├── .env.example            # Optional LLM configuration template; no secrets
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
