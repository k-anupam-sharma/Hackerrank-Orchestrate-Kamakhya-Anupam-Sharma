"""Build the repository-based HackerRank submission archive deterministically.

The challenge requires code.zip separately from output.csv and the chat
transcript. This script deliberately excludes datasets, outputs, environments,
logs, and credentials from the code archive.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_ARCHIVE = ROOT / "code.zip"
ROOT_FILES = (
    "README.md",
    "requirements.txt",
    ".env.example",
    "main.py",
    "run_tests.py",
    "evaluate.py",
    "package_submission.py",
    "problem_statement.md",
)
DIRECTORIES = ("code/buy_or_wait", "code/tests", "evaluation")
REQUIRED_ARCHIVE_MEMBERS = frozenset({"main.py", "README.md", "evaluation/usage_report.md"})
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _source_files() -> tuple[Path, ...]:
    files = [ROOT / name for name in ROOT_FILES]
    for relative_directory in DIRECTORIES:
        directory = ROOT / relative_directory
        files.extend(
            path for path in directory.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".md"}
        )
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot package required files: {', '.join(missing)}")
    return tuple(sorted(files, key=lambda path: path.relative_to(ROOT).as_posix()))


def build_submission_archive(output_path: str | Path = DEFAULT_ARCHIVE) -> Path:
    """Create a stable zip containing code and required submission metadata."""
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = _source_files()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            member_name = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(member_name, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    validate_submission_archive(destination)
    return destination


def validate_submission_archive(archive_path: str | Path) -> None:
    """Fail early if a produced artifact lacks a required runnable component."""
    with zipfile.ZipFile(archive_path) as archive:
        members = set(archive.namelist())
        missing = sorted(REQUIRED_ARCHIVE_MEMBERS - members)
        if missing:
            raise ValueError(f"Submission archive is missing: {', '.join(missing)}")
        if not archive.read("evaluation/usage_report.md").strip():
            raise ValueError("evaluation/usage_report.md must not be empty")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the required HackerRank code.zip artifact.")
    parser.add_argument("--output", type=Path, default=DEFAULT_ARCHIVE, help="Archive destination (default: code.zip).")
    args = parser.parse_args()
    archive = build_submission_archive(args.output)
    print(f"Built validated submission archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
