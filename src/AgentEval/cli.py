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

Story 8b.1 wires the `init` subcommand (per FR52) onto the existing
placeholder. Future subcommands: `new-adapter` (Story 8b.2). The FR50
exit-code mapping (Story 8a.1) is exposed via `error_code_to_exit_code`
+ `_ERROR_EXIT_CODES`.

Authoritative table at `docs/contracts/error-class-hierarchy.md` L66-L101
(count amended from "19" to "21" by Story 8a.1 fix-the-losing-source-NOW
after self-review surfaced the 2 Story-7.2 leaves missing from the
contract row).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
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
# channel. Values mirror the authoritative `error-class-hierarchy.md` L66-L101
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
    # Story 7.2 additions (added by Story 8a.1 self-review 2026-05-25; contract
    # amended in-place per fix-the-losing-source-NOW).
    "INVALID_SKILL_DISCOVERABILITY_TASKS": 65,  # EX_DATAERR — Tier-1 setup data error per Story 7.2.
    "SKILL_DID_NOT_ACTIVATE": 70,  # EX_SOFTWARE — Integrity-family generic per Story 7.2.
}


def error_code_to_exit_code(error_code: str | None) -> int:
    """Map an ``AgentEvalError`` leaf's ``error_code`` to a process exit code.

    Returns ``EXIT_CODE_FALLBACK`` (70 EX_SOFTWARE) for unknown / None /
    empty inputs. Per FR50 (sysexits-style per-leaf mapping ratified
    2026-05-18); authoritative table at
    ``docs/contracts/error-class-hierarchy.md`` L66-L101. Phase-1.5 will
    replace this lookup with a per-leaf ``exit_code: ClassVar[int]``
    attribute (DF-8a.1-S1 / C62).
    """
    if not error_code:
        return EXIT_CODE_FALLBACK
    return _ERROR_EXIT_CODES.get(error_code, EXIT_CODE_FALLBACK)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="agenteval",
        description=(
            "agenteval CLI — scaffold projects, generate conformance reports, and (Phase-1.5+) author custom adapters."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    # `init` subcommand (Story 8b.1 / FR52).
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new agenteval project with example tests + config.",
    )
    init_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Target directory for scaffolded files (default: CWD).",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (default: skip + warn).",
    )

    # `new-adapter` subcommand (Story 8b.2 / FR18).
    new_adapter_parser = subparsers.add_parser(
        "new-adapter",
        help="Scaffold a custom CodingAgentAdapter package (FR18).",
    )
    new_adapter_parser.add_argument(
        "--name",
        required=True,
        help="Package name (e.g., `my-adapter` → module `my_adapter`).",
    )
    new_adapter_parser.add_argument(
        "--type",
        dest="adapter_type",
        choices=["subprocess", "inprocess"],
        default="subprocess",
        help="Adapter base class: subprocess (CLI-driven, default) or inprocess (SDK-driven).",
    )
    new_adapter_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Parent directory for the new package (default: CWD).",
    )
    new_adapter_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Routes to subcommand handlers; falls through to a help message if no
    subcommand is given (matches Story 1a.1 placeholder behavior).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        from AgentEval._init import scaffold

        return scaffold(output_dir=args.output_dir, force=args.force)

    if args.command == "new-adapter":
        from AgentEval._new_adapter import scaffold_new_adapter

        return scaffold_new_adapter(
            name=args.name,
            adapter_type=args.adapter_type,
            output_dir=args.output_dir,
            force=args.force,
        )

    # No subcommand → print help, matching Story 1a.1 placeholder behavior.
    sys.stderr.write(
        "agenteval CLI: no subcommand given. Available:\n"
        "    agenteval init           — scaffold a new agenteval test suite (FR52)\n"
        "    agenteval new-adapter    — scaffold a new CodingAgentAdapter (FR18)\n"
        "See https://github.com/manykarim/robotframework-agenteval for roadmap.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
