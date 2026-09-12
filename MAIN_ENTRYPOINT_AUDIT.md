# Main entry-point audit

## Repository inventory

The initial audit found three files whose basename was `main.py`:

| Path | Purpose before cleanup | Status | References/usage |
| --- | --- | --- | --- |
| `main.py` | Portable root wrapper. Adds `code/` to `sys.path`, calls `solve_dataset`, validates the written CSV, and defaults paths relative to the repository. | **Retained; sole public solver entry point.** | README commands, final run instructions, packaging, and the official `python main.py` workflow. |
| `code/main.py` | A second, nearly identical solver wrapper. It used current-working-directory defaults and duplicated the root wrapper’s orchestration. | **Removed as redundant.** | It was mentioned by older design notes and the generic `AGENTS.md` contract, but no live script imported it and the package builder archives root `main.py`. The current design notes now point to root `main.py`. |
| `evaluation/main.py` | A compatibility shim that forwarded execution to root `evaluate.py`; it was not the application solver. | **Renamed to `evaluation/evaluator_entrypoint.py`.** | This preserves the evaluator wrapper’s separate purpose without leaving another ambiguous application `main.py`. |

`package_submission.py` includes root `main.py` and the `evaluation/` directory; it does not require a file named `code/main.py` or `evaluation/main.py`. No imports reference either removed/renamed path. `AGENTS.md` contains a historical generic note that `code/main.py` is a possible entry point; it is preserved as repository governance text and is superseded by the actual root workflow documented here.

## Final entry-point structure

```text
project/
├── main.py                              # sole public solver entry point
├── chat.py                              # temporary sample/official terminal tester
├── evaluate.py                          # independent output validator
├── evaluation/
│   ├── evaluator_entrypoint.py          # optional evaluator compatibility shim
│   └── usage_report.md
└── code/buy_or_wait/                    # library modules; no main.py
```

The root entry point remains deliberately thin. It invokes the unchanged solver and output validation logic; no financial/business logic was moved into it.

## Dataset boundaries

`python main.py` continues to load `dataset/requests.csv` through `solve_dataset` and writes the official root `output.csv`. `chat.py` defaults temporarily to `dataset/sample_requests.csv` for local testing and has an explicit `--official` switch for the evaluation request set. Sample answer columns are loaded only into a comparison-only mapping; the canonical `Request` model contains only the eight input fields, so labels cannot enter the solver.

## Verification checklist

- Root `main.py` is the only public solver command.
- `code/main.py` is absent; no duplicate solver wrapper remains.
- `evaluation/evaluator_entrypoint.py` has a descriptive non-application name.
- `python main.py` still uses `requests.csv` and writes `output.csv`.
- `python chat.py --all` processes IDs read from `sample_requests.csv` (currently 25), not hardcoded request boundaries.
- `python chat.py --all --compare` independently solves every sample request and reports field-level matches/mismatches without changing `output.csv`.
