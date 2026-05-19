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


class SubagentsLibrary:
    """Static-inspection keyword for sub-agent `.md` files [Tier 1 — Deterministic]."""

    @keyword(name="Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parse the YAML frontmatter at the head of a sub-agent `.md` file.

        [Tier 1 — Deterministic] — pure file-read + YAML parse + structural
        validation per PRD FR3. Median ≤ 50 ms on typical sub-agent files
        per NFR-PERF-02 (PRD L1608).

        Args:
            path: Filesystem path to the sub-agent `.md` file.

        Returns:
            The parsed YAML frontmatter as a dict. Always contains
            `name` + `description` (required); may contain `tools` +
            `model` (optional per PRD FR3).

        Raises:
            InvalidSubagentDefinitionError: On any structural failure
                (missing file, broken YAML, missing/wrong-type required
                fields). Error format per FR59 +
                `docs/contracts/error-class-hierarchy.md` L96-104.
        """
        frontmatter = parse_subagent_frontmatter(path)
        validate_subagent_structure(frontmatter, file_path=str(path))
        return frontmatter
