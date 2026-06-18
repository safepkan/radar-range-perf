#!/usr/bin/env python3
"""Lint, format and type-check all Python files in the repository.

By default ``black`` reformats files in place.  Pass ``--no-dirty`` (used in CI)
to run ``black`` in check-only mode so the run fails instead of mutating files.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

# Directories whose Python files are not subject to our tooling.
EXCLUDED_DIRS = {"venv", "build", "dist"}


def _check_command(cmd: List[str]) -> bool:
    print("=" * 65)
    print(" ".join(cmd))
    print("=" * 65)
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _get_python_files() -> List[str]:
    """All repository Python files except excluded and dot-prefixed dirs."""
    return [
        str(f)
        for f in Path(".").rglob("*.py")
        if not any(part.startswith(".") or part in EXCLUDED_DIRS for part in f.parts)
    ]


def _check_python(pyfiles: List[str], *, no_dirty: bool) -> bool:
    if not pyfiles:
        print("No Python files to check")
        return True

    print(f"Checking {len(pyfiles)} Python files:")
    print("\n".join(pyfiles))
    print()

    black_cmd = ["black"] + (["--check"] if no_dirty else []) + pyfiles
    success = _check_command(black_cmd)
    success = _check_command(["flake8"] + pyfiles) and success
    success = (
        _check_command(["mypy", "--install-types", "--non-interactive"] + pyfiles)
        and success
    )
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-dirty",
        action="store_true",
        help="run black in --check mode instead of reformatting in place",
    )
    args = parser.parse_args()

    pyfiles = _get_python_files()
    ok = _check_python(pyfiles, no_dirty=args.no_dirty)
    sys.exit(0 if ok else 1)
