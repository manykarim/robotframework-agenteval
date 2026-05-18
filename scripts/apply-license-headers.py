#!/usr/bin/env python3
"""Idempotently prepend the Apache 2.0 license header to every .py file under src/AgentEval/.

Re-running adds zero new headers. Intended to be run ONCE (Story 1a.5 deliverable) to
backfill headers across the existing baseline. New .py files going forward are gated by
`scripts/check-license-headers.py` via the pre-commit hook + the ci.yml License headers
check step.
"""

from __future__ import annotations

import sys
from pathlib import Path

LICENSE_MARKER = "Licensed under the Apache License"

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
        if LICENSE_MARKER in content:
            already_present += 1
            continue
        # Prepend header + one blank line separator before existing content.
        new_content = LICENSE_HEADER + "\n" + content
        py_file.write_text(new_content, encoding="utf-8")
        applied += 1

    print(f"Applied {applied} headers; {already_present} files already had headers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
