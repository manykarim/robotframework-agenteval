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

"""Subagent sub-library — static-inspection keyword for sub-agent `.md` files.

Story 2.2 ships 1 Tier-1 keyword per PRD FR3:
- `Get Frontmatter` — parse a sub-agent `.md` file's YAML frontmatter
  into a dict (required: `name`, `description`; optional: `tools`,
  `model`).

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval.subagents.library.SubagentsLibrary    WITH NAME    Subagent

    *** Test Cases ***
    Subagent Has Correct Name
        ${def}=    Subagent.Get Frontmatter    .claude/agents/code-reviewer.md
        Should Be Equal    ${def["name"]}    code-reviewer

Composition: registered in `AgentEval.__init__._SUB_LIBRARIES` so
`Library AgentEval` flattens the keyword into the parent namespace via
`robotlibcore.DynamicCore`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.subagents._parser import parse_subagent_frontmatter, validate_subagent_structure

__all__ = ["SubagentsLibrary"]

# Browser-Library-style docstring migration marker (Phase 1, 2026-05-26).
# Read by `tests/unit/conventions/test_docstring_browser_style.py` +
# `test_docstring_examples_dryrun.py` to determine which libraries are
# subject to the Browser-style structure + example-dryrun enforcement.
# Derived-via-marker pattern adopted per Kilo Phase 1 review HIGH (Patch A);
# replaces the hardcoded `MIGRATED_LIBRARIES` allow-list that drifted as
# new libraries shipped.
_BROWSER_STYLE_MIGRATED = True


class SubagentsLibrary:
    """Static-inspection keyword for sub-agent `.md` files [Tier 1 — Deterministic]."""

    @keyword(name="Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parses the YAML frontmatter at the head of a sub-agent ``.md`` file.

        [Tier 1 — Deterministic] — pure file-read + YAML parse + structural
        validation per PRD FR3. Returns a dict with at minimum ``name`` +
        ``description`` (both required); may carry optional ``tools`` (list)
        and ``model`` (str). Median ≤ 50 ms on typical sub-agent files per
        NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the sub-agent ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSubagentDefinitionError`` on any structural failure
        (missing file, broken YAML, missing or wrong-type required field).
        Error format per FR59 + `docs/contracts/error-class-hierarchy.md`
        L96-104.

        Note: this library is NOT composed into the top-level ``AgentEval``
        keyword surface because of the name collision with
        `Get Frontmatter` on `SkillsLibrary` (DF-7.1-S1 — see
        `docs/phase-1-5-carry-overs.md`). Import directly with
        ``Library    AgentEval.subagents.library.SubagentsLibrary    WITH NAME    Subagent``.

        Example:
        | ${frontmatter} =    `Get Frontmatter`    ${CURDIR}/agents/code-reviewer.md
        | Should Be Equal    ${frontmatter}[name]    code-reviewer
        | Should Contain    ${frontmatter}[description]    Reviews diffs
        | Should Contain    ${frontmatter}[tools]    Bash                            # When `tools` is present.

        Notes:
        - PRD FR3 ratifies the required ``name`` + ``description`` fields.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format: FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Parallel surface: `SkillsLibrary.Get Frontmatter` for skill ``.md`` files (different validation rules).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        frontmatter = parse_subagent_frontmatter(path)
        validate_subagent_structure(frontmatter, file_path=str(path))
        return frontmatter
