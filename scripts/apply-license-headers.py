#!/usr/bin/env python3
"""Idempotently prepend the Apache 2.0 license header to every .py file under src/AgentEval/.

Re-running adds zero new headers. Intended to be run ONCE (Story 1a.5 deliverable) to
backfill headers across the existing baseline. New .py files going forward are gated by
`scripts/check-license-headers.py` via the pre-commit hook + the ci.yml License headers
check step.

Edge cases handled (per Story 1a.5 code-review MED-4 + MED-5):
- The "header present" check validates the canonical block at the FILE PROLOGUE
  (first non-shebang / non-encoding lines), not a substring anywhere in the file.
- Shebangs (`#!...` on line 1) are preserved + the license header is inserted AFTER.
- PEP 263 encoding cookies (`# -*- coding: ... -*-` or `# coding: ...`) on line 1 OR
  line 2 are preserved + the license header is inserted AFTER.
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
# PEP 263 encoding declaration: must match `coding[=:]\s*([-\w.]+)` on line 1 or 2.
ENCODING_RE = re.compile(r"^[ \t\v]*#.*?coding[=:]\s*[-\w.]+")


def split_prologue(content: str) -> tuple[list[str], list[str]]:
    """Return (prologue_lines, body_lines) where prologue is optional shebang + optional encoding cookie.

    Per PEP 263 + standard Python interpreter conventions:
    - Line 1 may be a shebang (`#!...`).
    - Line 1 OR line 2 may be an encoding cookie (must match ENCODING_RE).
    - Both may be absent.
    """
    lines = content.splitlines(keepends=True)
    prologue: list[str] = []
    i = 0
    if i < len(lines) and SHEBANG_RE.match(lines[i]):
        prologue.append(lines[i])
        i += 1
    if i < len(lines) and ENCODING_RE.match(lines[i]):
        prologue.append(lines[i])
        i += 1
    elif i == 1 and len(lines) >= 2 and ENCODING_RE.match(lines[1]):
        # Encoding cookie on line 2 when line 1 is a shebang — handled by previous block.
        pass
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

    applied = 0
    already_present = 0
    for py_file in sorted(target_root.rglob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        prologue, body = split_prologue(content)
        if has_header_at_prologue(body):
            already_present += 1
            continue
        # Insert header AFTER prologue + a blank line separator before existing body.
        new_content = "".join(prologue) + LICENSE_HEADER + "\n" + "".join(body)
        py_file.write_text(new_content, encoding="utf-8")
        applied += 1

    print(f"Applied {applied} headers; {already_present} files already had headers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
