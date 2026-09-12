"""Run the complete test suite without needing PYTHONPATH configuration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
for directory in (ROOT / "code", ROOT / "code" / "tests"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "code" / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
