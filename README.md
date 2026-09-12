# Buy or Wait? — HackerRank Orchestrate 2026

This repository contains a deterministic financial-planning solver for the HackerRank **Buy or Wait?** challenge. It reads the supplied CSV dataset, produces one recommendation for every request, and validates the submission-shaped `output.csv`.

The default solver is offline and needs no API key or third-party package. Optional LLM assistance is strictly bounded to extracting facts from untrusted messages/images and rephrasing already verified explanations; financial arithmetic, forecasting, validation, and ranking remain deterministic.

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

`main.py` is the single solver entry point. `code/main.py` remains a compatibility entry point for the original starter layout; use the root command above for a portable clean-machine workflow.

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
4. Include the runnable code, `output.csv`, and `evaluation/usage_report.md` in the required submission archive.
5. Keep secrets, local virtual environments, and `log.txt` out of version control.
