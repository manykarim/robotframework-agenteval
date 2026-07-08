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

"""Docs keyword-count drift check.

Derives the true unique keyword count from libdoc and asserts that the
documented counts in `README.md` and `docs/index.md` match it. Run in the
docs-build CI path so a new keyword shipped without a doc update fails the
build.

The unique-keyword total is the sum of the libdoc keyword counts for the
libraries that contribute distinct keywords a user can call:

    AgentEval + SkillsLibrary + MCPLibrary + SubagentsLibrary

`JudgeLibrary` and `HooksLibrary` are composed into (re-exported through) the
top-level `AgentEval` library, so their keywords are already counted in
`AgentEval` and must NOT be added again. There are 6 libraries in total.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from robot.libdocpkg import LibraryDocumentation

REPO_ROOT = Path(__file__).resolve().parents[1]

# Libraries whose keyword sets are disjoint and together form the unique
# callable surface. Judge + Hooks are excluded because they are composed into
# AgentEval (their keywords are already present in AgentEval's count).
_COUNTED_LIBRARIES = (
    "AgentEval",
    "AgentEval.skills.library.SkillsLibrary",
    "AgentEval.mcp.library.MCPLibrary",
    "AgentEval.subagents.library.SubagentsLibrary",
)

# Total number of importable libraries (the 4 above + JudgeLibrary + HooksLibrary).
_LIBRARY_COUNT = 6


def derive_keyword_count() -> int:
    """Return the unique keyword total across the shipped libraries (via libdoc)."""
    return sum(len(LibraryDocumentation(lib).keywords) for lib in _COUNTED_LIBRARIES)


def _documented_numbers(text: str) -> list[tuple[int, int]]:
    """Return every `(keyword_count, library_count)` pair stated near each other.

    Matches the canonical phrasings used in the docs:
    - "56 keywords across 6 libraries"
    - "6 libraries · 56 keywords"
    """
    pairs: list[tuple[int, int]] = []
    for m in re.finditer(r"(\d+)\s+keywords?\s+across\s+(\d+)\s+librar", text):
        pairs.append((int(m.group(1)), int(m.group(2))))
    for m in re.finditer(r"(\d+)\s+librar\w*\s*[·|]\s*(\d+)\s+keywords?", text):
        pairs.append((int(m.group(2)), int(m.group(1))))
    return pairs


def check() -> list[str]:
    """Return a list of human-readable failures (empty when the docs are correct)."""
    expected_keywords = derive_keyword_count()
    failures: list[str] = []

    for rel in ("README.md", "docs/index.md"):
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        pairs = _documented_numbers(text)
        if not pairs:
            failures.append(
                f"{rel}: could not find a canonical count sentence "
                f'(expected e.g. "{expected_keywords} keywords across {_LIBRARY_COUNT} libraries").'
            )
            continue
        for kw, libs in pairs:
            if kw != expected_keywords:
                failures.append(f"{rel}: documents {kw} keywords but libdoc derives {expected_keywords}.")
            if libs != _LIBRARY_COUNT:
                failures.append(f"{rel}: documents {libs} libraries but there are {_LIBRARY_COUNT}.")
    return failures


def main() -> int:
    failures = check()
    expected = derive_keyword_count()
    if failures:
        print("::error::Doc keyword-count drift detected:")
        for f in failures:
            print(f"  - {f}")
        print(
            f"  Fix: update README.md + docs/index.md to state {expected} keywords across {_LIBRARY_COUNT} libraries."
        )
        return 1
    print(
        f"Doc keyword-count check passed: {expected} keywords across "
        f"{_LIBRARY_COUNT} libraries (README + docs/index.md agree)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
