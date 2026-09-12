from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("local_evaluate", ROOT / "evaluate.py")
assert SPEC is not None and SPEC.loader is not None
EVALUATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVALUATE
SPEC.loader.exec_module(EVALUATE)


class EvaluationIntegrationTests(unittest.TestCase):
    def test_complete_dataset_passes_independent_evaluation(self) -> None:
        result = EVALUATE.evaluate(ROOT / "dataset", ROOT / "output.csv")
        self.assertEqual(250, result.total_rows)
        self.assertEqual(250, sum(result.status_counts.values()))
        self.assertEqual((), result.failures)


if __name__ == "__main__":
    unittest.main()
