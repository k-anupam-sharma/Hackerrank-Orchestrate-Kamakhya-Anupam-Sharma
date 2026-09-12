"""Portable entry point for generating Buy or Wait predictions.

This wrapper makes the package importable when invoked from any working
directory and defaults paths to this repository rather than the caller's CWD.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from buy_or_wait.solver import solve_dataset, validate_output_csv  # noqa: E402
from buy_or_wait.loaders import load_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate validated Buy or Wait predictions.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "dataset", help="Input dataset directory.")
    parser.add_argument("--output-path", type=Path, default=ROOT / "output.csv", help="Output CSV path.")
    args = parser.parse_args()

    rows = solve_dataset(args.dataset_dir, args.output_path)
    validate_output_csv(args.output_path, load_dataset(args.dataset_dir))
    print(f"Wrote {len(rows)} validated rows to {args.output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
