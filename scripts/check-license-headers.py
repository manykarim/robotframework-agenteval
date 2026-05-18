#!/usr/bin/env python3
"""Check that every .py file under src/AgentEval/ contains the Apache 2.0 license header.

Fail-loud (exit 1) if any file is missing the header. Used by:
- The pre-commit hook (local enforcement on every commit)
- The .github/workflows/ci.yml `License headers check` step (CI enforcement; catches `--no-verify` bypass)

Story 1a.5 deliverable. See apply-license-headers.py for the one-time backfill script.
"""

from __future__ import annotations

import sys
from pathlib import Path

LICENSE_MARKER = "Licensed under the Apache License"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    target_root = repo_root / "src" / "AgentEval"

    if not target_root.is_dir():
        print(f"ERROR: target directory {target_root} does not exist", file=sys.stderr)
        return 1

    checked = 0
    missing: list[Path] = []
    for py_file in sorted(target_root.rglob("*.py")):
        checked += 1
        content = py_file.read_text(encoding="utf-8")
        if LICENSE_MARKER not in content:
            missing.append(py_file.relative_to(repo_root))

    if missing:
        print(f"FAIL: {len(missing)} of {checked} .py files missing Apache 2.0 license header:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print(
            "\nFix: run `uv run python scripts/apply-license-headers.py` to backfill headers idempotently.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: all {checked} .py files have Apache 2.0 license headers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
