"""Run the display-free test suite and fail if a test file skips definitions."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "test_burraco.py",
    "test_catalog.py",
    "test_engine.py",
    "test_features.py",
    "test_layout.py",
    "test_records.py",
    "test_scopa.py",
    "test_tressette.py",
)


def defined_tests(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    )


def main() -> int:
    total = 0
    for name in TESTS:
        path = ROOT / "tests" / name
        expected = defined_tests(path)
        result = subprocess.run(
            [sys.executable, "-u", str(path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        passed = sum(line.startswith("ok") for line in result.stdout.splitlines())
        if passed != expected:
            raise RuntimeError(f"{name}: {passed} tests ran, {expected} are defined")
        print(f"{name}: {passed} passed")
        total += passed
    print(f"total: {total} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
