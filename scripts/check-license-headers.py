#!/usr/bin/env python3
"""Check that every .py file under src/AgentEval/ contains the canonical Apache 2.0 header at its prologue.

Fail-loud (exit 1) if any file is missing the header OR the header is not at the
expected position (after optional shebang + encoding cookie). Used by:
- The pre-commit hook (local enforcement on every commit)
- The .github/workflows/ci.yml `License headers check` step (CI enforcement; catches `--no-verify` bypass)

Story 1a.5 deliverable. See apply-license-headers.py for the one-time backfill script.

Edge cases handled (per Story 1a.5 code-review MED-4 + MED-5):
- Validates the canonical header BLOCK at the file prologue (after optional shebang +
  encoding cookie), not a substring anywhere in the file. A stray comment or docstring
  containing "Licensed under the Apache License" elsewhere in the file does NOT pass
  the check.
- Shebangs (`#!...`) and PEP 263 encoding cookies are tolerated above the header.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LICENSE_HEADER = """# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""

HEADER_LINES = LICENSE_HEADER.rstrip("\n").splitlines()
SHEBANG_RE = re.compile(r"^#!")
ENCODING_RE = re.compile(r"^[ \t\v]*#.*?coding[=:]\s*[-\w.]+")


def split_prologue(content: str) -> tuple[list[str], list[str]]:
    """Return (prologue_lines, body_lines) where prologue is optional shebang + optional encoding cookie."""
    lines = content.splitlines(keepends=True)
    prologue: list[str] = []
    i = 0
    if i < len(lines) and SHEBANG_RE.match(lines[i]):
        prologue.append(lines[i])
        i += 1
    if i < len(lines) and ENCODING_RE.match(lines[i]):
        prologue.append(lines[i])
        i += 1
    return prologue, lines[i:]


def has_header_at_prologue(body: list[str]) -> bool:
    """Return True iff the canonical header block appears at the START of body (after prologue)."""
    if len(body) < len(HEADER_LINES):
        return False
    body_prefix = [line.rstrip("\n") for line in body[: len(HEADER_LINES)]]
    return body_prefix == HEADER_LINES


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
        _prologue, body = split_prologue(content)
        if not has_header_at_prologue(body):
            missing.append(py_file.relative_to(repo_root))

    if missing:
        print(
            f"FAIL: {len(missing)} of {checked} .py files missing canonical Apache 2.0 license header at file prologue:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print(
            "\nFix: run `uv run python scripts/apply-license-headers.py` to backfill headers idempotently.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: all {checked} .py files have the canonical Apache 2.0 license header at prologue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
