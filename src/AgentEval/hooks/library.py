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

# Browser-Library-style docstring migration marker (Phase 1, 2026-05-26).
# Read by `tests/unit/conventions/test_docstring_browser_style.py` +
# `test_docstring_examples_dryrun.py` to determine which libraries are
# subject to the Browser-style structure + example-dryrun enforcement.
# Derived-via-marker pattern adopted per Kilo Phase 1 review HIGH (Patch B);
# replaces the hardcoded `MIGRATED_LIBRARIES` allow-list that drifted as
# new libraries shipped.
_BROWSER_STYLE_MIGRATED = True


class HooksLibrary:
    """Static-inspection keyword for `settings.json` hook configs [Tier 1 — Deterministic]."""

    @keyword(name="Get Config")
    @tier(1)
    def get_config(self, path: str | Path) -> dict[str, list[dict[str, Any]]]:
        """Parses a Claude Code ``settings.json`` hook configuration.

        [Tier 1 — Deterministic] — pure file-read + JSON parse + per-entry
        validation per PRD FR4. Returns a dict mapping ``hooks.<event>`` →
        list of validated hook entries. Covered events: ``PreToolUse``,
        ``PostToolUse``, ``Stop``; other events are passed through with the
        same validation. Median ≤ 50 ms on typical hook configs per
        NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the ``settings.json`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Each returned entry has ``command`` (required) plus any of the
        optional fields ``args`` / ``timeout`` / ``matcher`` that were
        present in the source JSON. Entries whose command contains an
        inline YAML frontmatter block additionally surface an
        ``inline_skill: dict`` field with the parsed frontmatter.

        Raises ``InvalidHookConfigError`` on any structural failure (file
        not found, malformed JSON, missing ``command``, wrong-type optional
        field). The error's ``field_name`` attribute carries an RFC 6901
        JSON Pointer (e.g. ``/hooks/PreToolUse/0/command``) pinpointing the
        nested location. Format per FR59 +
        `docs/contracts/error-class-hierarchy.md` L96-104.

        This keyword is re-exported through the top-level ``AgentEval``
        library, so ``AgentEval.Get Config`` and ``Hook.Get Config`` (when
        imported as ``WITH NAME    Hook``) resolve to the same
        implementation.

        Example:
        | ${config} =    `Get Config`    ${CURDIR}/.claude/settings.json
        | Length Should Be    ${config}[hooks.PreToolUse]    1
        | Should Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook
        | Should Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30

        Notes:
        - PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop).
          Unknown events are validated with the same shape contract.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format: FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
          The ``field_name`` attribute on raised errors carries an RFC 6901 JSON Pointer.
        - Inline-skill-frontmatter hooks are an extension surface — the inner skill
          is reachable via `SkillsLibrary` keywords passed the ``inline_skill`` dict directly.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return parse_hook_config(path)
