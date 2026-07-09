# Copyright 2026 Many Kasiriha
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

"""NFR-MAINT-04: assert every `docs/contracts/*.md` carries the 4 required sections.

Local mirror of the `docs-build.yml` "Assert NFR-MAINT-04 per-file section
presence" CI step, so the gate runs in the local pre-commit sequence instead of
only surfacing at PR time. Each contract doc MUST contain, as exact level-2
headers, `## Purpose`, `## Scope`, `## Contract`, and `## Change Policy`.

Exit codes: 0 = all present (or no contract dir/files yet), 1 = violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = ("Purpose", "Scope", "Contract", "Change Policy")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    contracts = repo_root / "docs" / "contracts"
    if not contracts.is_dir():
        print("NOTE: docs/contracts/ missing — nothing to check.")
        return 0

    files = sorted(contracts.glob("*.md"))
    if not files:
        print("NOTE: docs/contracts/ has no .md files — nothing to check.")
        return 0

    fail = False
    for f in files:
        text = f.read_text(encoding="utf-8")
        missing = [
            f"## {section}"
            for section in REQUIRED_SECTIONS
            # Exact level-2 header line (trailing whitespace tolerated), mirroring
            # the CI grep `^## <section>$`.
            if not re.search(rf"^## {re.escape(section)}\s*$", text, re.MULTILINE)
        ]
        if missing:
            rel = f.relative_to(repo_root)
            print(f"FAIL: {rel} — missing required section header(s): {', '.join(missing)}")
            fail = True

    if fail:
        print("\nEach contract doc MUST contain: ## Purpose, ## Scope, ## Contract, ## Change Policy")
        return 1

    print(f"PASS: all {len(files)} docs/contracts/*.md files have the 4 NFR-MAINT-04 sections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
