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

"""Hook sub-library — static-inspection keyword for `settings.json` files.

Story 2.2 ships 1 Tier-1 keyword per PRD FR4:
- `Get Config` — parse a Claude Code `settings.json` hook configuration
  into a dict mapping `hooks.<event>` → list of validated hook entries.
  Each entry has `command` (required) + optional `args` / `timeout` /
  `matcher`. Inline-skill-frontmatter hooks surface as an extra
  `inline_skill: dict` field on the entry.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval.hooks.library.HooksLibrary    WITH NAME    Hook

    *** Test Cases ***
    PreToolUse Has Audit Hook
        ${config}=    Hook.Get Config    .claude/settings.json
        Length Should Be    ${config["hooks.PreToolUse"]}    1

Composition: registered in `AgentEval.__init__._SUB_LIBRARIES` so
`Library AgentEval` flattens the keyword into the parent namespace via
`robotlibcore.DynamicCore`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.hooks._parser import parse_hook_config

__all__ = ["HooksLibrary"]


class HooksLibrary:
    """Static-inspection keyword for `settings.json` hook configs [Tier 1 — Deterministic]."""

    @keyword(name="Get Config")
    @tier(1)
    def get_config(self, path: str | Path) -> dict[str, list[dict[str, Any]]]:
        """Parse a Claude Code `settings.json` hook configuration.

        [Tier 1 — Deterministic] — pure file-read + JSON parse +
        per-entry validation per PRD FR4. Median ≤ 50 ms on typical
        hook configs per NFR-PERF-02 (PRD L1608).

        Args:
            path: Filesystem path to the `settings.json` file.

        Returns:
            A dict mapping `hooks.<event>` → list of validated hook
            entries. Events covered: `PreToolUse`, `PostToolUse`,
            `Stop` (per PRD FR4); other events are passed through with
            the same validation. Each entry has `command` plus any
            optional fields (`args`, `timeout`, `matcher`) that were
            present + `inline_skill: dict` if the entry's command
            contained an inline YAML frontmatter block.

        Raises:
            InvalidHookConfigError: On any structural failure (file
                not found, malformed JSON, missing `command`, wrong
                optional-field types). The `field_name` attribute
                carries an RFC 6901 JSON Pointer (e.g.,
                `/hooks/PreToolUse/0/command`) into the offending
                location for nested-JSON pinpointing. Format per FR59
                + `docs/contracts/error-class-hierarchy.md` L96-104.
        """
        return parse_hook_config(path)
