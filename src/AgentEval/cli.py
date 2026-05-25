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

"""agenteval CLI entry point.

Phase-1 placeholder per FR18 + FR52. Real subcommand routing (`init`,
`new-adapter`) lands in Epic 8b Story 8b.1 (init) + Story 8b.2 (new-adapter).

Wired up early so the `[project.scripts] agenteval = "AgentEval.cli:main"`
entry point in pyproject.toml resolves cleanly. Without this stub, `uv run
agenteval` raises ModuleNotFoundError — caught by Story 1a.1 code review
(Codex CLI + Claude Opus, 2026-05-17).

Story 8a.1: Ships `error_code_to_exit_code` + `_ERROR_EXIT_CODES` lookup
table consulted at process exit per FR50. Per-leaf `exit_code: ClassVar[int]`
on the 21 error leaves is deferred to Phase-1.5 (DF-8a.1-S1 / C62 — path-of-
least-amendment decision per Story 8a.1 D-2). Authoritative table lives at
`docs/contracts/error-class-hierarchy.md` L66-L101 (count amended from "19"
to "21" by Story 8a.1 fix-the-losing-source-NOW after self-review surfaced
the 2 Story-7.2 leaves missing from the contract row).
"""

from __future__ import annotations

import sys
from typing import Final

__all__ = [
    "EXIT_CODE_FALLBACK",
    "error_code_to_exit_code",
    "main",
]

# Sysexits-style fallback for unknown `error_code` strings + as the generic
# agenteval-failure exit code per FR50. Mirrors EX_SOFTWARE (sysexits.h L96).
EXIT_CODE_FALLBACK: Final[int] = 70

# Story 8a.1 FR50 lookup table — single source-of-truth for the CLI exit
# channel. Values mirror the authoritative `error-class-hierarchy.md` L73-L94
# table; keys are the leaf-class `error_code: str` class attribute values.
#
# The 4 pinned codes are tied to `epics.md` L1660 (PollingDisallowed=65,
# CostExceeded=66, IncompleteTrace=67, UnsupportedMCPVersion=68). The
# remaining codes use sysexits.h alignment ratified 2026-05-18 via Story
# 1a.4 code-review HIGH-6.
_ERROR_EXIT_CODES: Final[dict[str, int]] = {
    # AgentEvalSafetyError family — EX_NOPERM (77).
    "SANDBOX_REQUIRED": 77,  # ADR-018 / planned per error-class-hierarchy.md L66.
    "VALIDATE_OPERATOR_DISALLOWED": 77,  # Story 6.3 — IMPLEMENTED per L67.
    # AgentEvalBudgetError family.
    "COST_EXCEEDED": 66,  # epics.md L1660 pinned.
    "RUNTIME_BUDGET_EXCEEDED": 75,  # EX_TEMPFAIL.
    # AgentEvalCompatError family.
    "UNSUPPORTED_MCP_VERSION": 68,  # epics.md L1660 pinned.
    "UNSUPPORTED_BINARY_VERSION": 78,  # EX_CONFIG.
    "ADAPTER_DISCOVERY_ERROR": 78,  # EX_CONFIG.
    "ADAPTER_VERSION_DRIFT": 0,  # warning-class — exit 0 (contract L83).
    "MCP_CONNECTION_LOST": 69,  # sysexits-extended, Compat-family runtime.
    # AgentEvalIntegrityError family.
    "POLLING_DISALLOWED": 65,  # epics.md L1660 pinned (EX_DATAERR).
    "INCOMPLETE_TRACE": 67,  # epics.md L1660 pinned.
    "TIER_VIOLATION": 70,  # EX_SOFTWARE.
    "INVALID_SKILL_FRONTMATTER": 65,  # EX_DATAERR — setup data error.
    "INVALID_SUBAGENT_DEFINITION": 65,  # EX_DATAERR.
    "INVALID_HOOK_CONFIG": 65,  # EX_DATAERR.
    "INVALID_MCP_SERVER_CONFIG": 65,  # EX_DATAERR.
    "INVALID_MCP_TOOL_SCHEMA": 65,  # EX_DATAERR.
    "INVALID_SCENARIO_YAML": 65,  # EX_DATAERR.
    "INVALID_DISCOVERABILITY_TASKS": 65,  # EX_DATAERR.
    # Story 7.2 additions (NOT yet in error-class-hierarchy.md L52-L56 — drift
    # caught by Story 8a.1 self-review 2026-05-25; contract amended below to
    # reflect). Both fall under the family-default exit codes pending an ADR
    # amendment that pins per-leaf codes.
    "INVALID_SKILL_DISCOVERABILITY_TASKS": 65,  # EX_DATAERR — Tier-1 setup data error per Story 7.2.
    "SKILL_DID_NOT_ACTIVATE": 70,  # EX_SOFTWARE — Integrity-family generic per Story 7.2.
}


def error_code_to_exit_code(error_code: str | None) -> int:
    """Map an ``AgentEvalError`` leaf's ``error_code`` to a process exit code.

    Returns ``EXIT_CODE_FALLBACK`` (70 EX_SOFTWARE) for unknown / None /
    empty inputs. Per FR50 (sysexits-style per-leaf mapping ratified
    2026-05-18); authoritative table at
    ``docs/contracts/error-class-hierarchy.md`` L73-L94. Phase-1.5 will
    replace this lookup with a per-leaf ``exit_code: ClassVar[int]``
    attribute (DF-8a.1-S1 / C62).

    This function is NOT yet wired into the CLI's main exit path — wiring
    lands with the Epic 8b subcommand structure (Story 8b.1 ``init`` /
    Story 8b.2 ``new-adapter``).
    """
    # Phase-1.5: wire into CLI main exit channel when subcommand structure
    # lands (Story 8b.1 onward).
    if not error_code:
        return EXIT_CODE_FALLBACK
    return _ERROR_EXIT_CODES.get(error_code, EXIT_CODE_FALLBACK)


def main() -> int:
    """CLI entry point. Phase-1 placeholder.

    Returns 0 with a help message until Epic 8b ships the real subcommand
    implementations. The current exit code is intentionally success (0) so that
    contributors can verify the entry point is wired (`uv run agenteval`)
    without the bootstrap looking like a hard failure.
    """
    sys.stderr.write(
        "agenteval CLI: subcommands not yet implemented.\n"
        "  Planned subcommands (Epic 8b deliverables per FR18 + FR52):\n"
        "    agenteval init           — scaffold a new agenteval test suite\n"
        "    agenteval new-adapter    — scaffold a new CodingAgentAdapter\n"
        "See https://github.com/manykarim/robotframework-agenteval for roadmap.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
