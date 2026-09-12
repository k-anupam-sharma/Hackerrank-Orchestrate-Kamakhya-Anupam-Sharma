"""Terminal entry point for the deterministic Buy or Wait solver."""

from __future__ import annotations

import argparse
from pathlib import Path

from buy_or_wait.solver import solve_dataset, validate_output_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Buy or Wait predictions.")
    parser.add_argument("--dataset-dir", default="dataset")
    parser.add_argument("--output-path", default="output.csv")
    args = parser.parse_args()
    rows = solve_dataset(args.dataset_dir, args.output_path)
    # Re-read the file to prove its exact on-disk CSV schema before returning.
    from buy_or_wait.loaders import load_dataset
    validate_output_csv(args.output_path, load_dataset(args.dataset_dir))
    print(f"Wrote {len(rows)} validated rows to {Path(args.output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
