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

"""Kernel-level `mcp_coverage` enforcement gate (FR37 / ADR-016 L44).

This module is **enforcement-only**. Detection of `mcp_coverage` happens in
adapters (Epic 4 — Generic + Claude Code CLI + future adapters) per
ADR-016 §D4 adapter contract. The kernel ONLY:

1. Reads the resolved `mcp_coverage` value from `AgentRunResult.metadata`.
2. Enforces the FR37 default-deny gate: when the value is `"external_mixed"`
   AND `allow_external_mcp_blind=False`, raises `IncompleteTraceError`.

The trust-floor decision tree (ADR-016 §Decision L17-28: when both
`hosted_in_process` AND `subprocess_with_observer` paths fire, the adapter
populates `hosted_in_process` — the stronger path wins) is exercised by
adapters at metadata-population time. The kernel just consumes the resolved
value.

Phase-1 forward-reference pattern for `AgentRunResult`:
    Story 1b.4 (CodingAgentAdapter Protocol + ABCs) lands `AgentRunResult` in
    `src/AgentEval/types.py`. Story 1b.2 ships this enforcement gate ahead of
    1b.4 via a TYPE_CHECKING-guarded import: type checkers see the
    `AgentRunResult` type, but runtime accepts any duck-typed object with the
    `.metadata.mcp_coverage` attribute shape. Tests use a `SimpleNamespace`
    or small `@dataclass` fake stand-in.

References:
    - ADR-016 §Decision L44: kernel raise contract
    - ADR-016 §Decision L17-28: trust-floor decision tree (adapter responsibility)
    - PRD §FR37: IncompleteTraceError on external_mixed runs
    - architecture L384, L1058, L1197: `_check_mcp_coverage` helper location
    - Story 1b.4 spec L924-930: AgentRunResult lands in src/AgentEval/types.py
    - Story 1b.2 errors.py: IncompleteTraceError leaf
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from AgentEval.errors import IncompleteTraceError

if TYPE_CHECKING:
    from AgentEval.types import AgentRunResult  # Story 1b.4 lands the dataclass

__all__ = ["_check_mcp_coverage"]


def _check_mcp_coverage(
    run: AgentRunResult,
    *,
    allow_external_mcp_blind: bool = False,
) -> None:
    """Enforce FR37: raise `IncompleteTraceError` on uninstrumented runs.

    Per ADR-016 §Decision L44 + L52: the kernel reads
    `run.metadata.mcp_coverage` (resolved by adapters at metadata-population
    time per ADR-016 §D4 trust-floor decision tree) and enforces the
    default-deny gate.

    Behavior matrix:

        | mcp_coverage                  | allow_external_mcp_blind | Outcome                          |
        |-------------------------------|--------------------------|----------------------------------|
        | "hosted_in_process"           | any                      | return None (trace complete)     |
        | "subprocess_with_observer"    | any                      | return None (trace complete)     |
        | "external_mixed"              | False (default)          | raise IncompleteTraceError       |
        | "external_mixed"              | True                     | return None (opt-in blind run)   |

    Args:
        run: An `AgentRunResult`-shaped object (any object with the
            `.metadata.mcp_coverage` attribute path; Phase-1 duck-typed
            until Story 1b.4 ratifies the type via `src/AgentEval/types.py`).
        allow_external_mcp_blind: When True, callers opt into running blind
            on `external_mixed` coverage. Default False enforces FR37's
            loud-refusal posture per ADR-016 §Decision L44.

    Raises:
        IncompleteTraceError: When `run.metadata.mcp_coverage == "external_mixed"`
            AND `allow_external_mcp_blind=False`. Carries `error_code =
            "INCOMPLETE_TRACE"` (per ADR-014) for downstream JUnit XML
            emission (FR49) + exit-code mapping (FR50).
    """
    coverage = run.metadata.mcp_coverage
    # M_R1 fix (Story 1b.2 code review): validate against ratified 3-state set
    # per ADR-016 §Decision L24-28. Unknown values (typo, future enum addition,
    # adapter bug) raise IncompleteTraceError so "loud refusal beats silent
    # half-truth" applies even outside the external_mixed case.
    ratified_coverage_values = ("hosted_in_process", "subprocess_with_observer", "external_mixed")
    if coverage not in ratified_coverage_values:
        raise IncompleteTraceError(
            f"Run reports unknown mcp_coverage={coverage!r}; ratified values "
            f"per ADR-016 §Decision L24-28 are {ratified_coverage_values}. "
            "Fix the adapter to emit a ratified value (see "
            "docs/contracts/mcp-coverage-detection.md)."
        )
    if coverage == "external_mixed" and not allow_external_mcp_blind:
        raise IncompleteTraceError(
            "Run reports mcp_coverage='external_mixed' (uninstrumented MCP usage "
            "detected); pass allow_external_mcp_blind=True at Library "
            "construction time to opt into a blind run, OR fix the adapter to "
            "populate full coverage (see docs/contracts/mcp-coverage-detection.md "
            "for the per-adapter detection contract per ADR-016 §D4)."
        )
