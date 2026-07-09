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

"""Internal helpers for the subagent delegation-testing surface.

Private module — not part of the public API. Contains:

- `DELEGATION_IDENTITY_KEYS` — the fixed identity-probe order (Decision 1).
- `extract_delegations(tool_calls, delegation_tools)` — project a run's
  `tool_calls` into ordered `DelegationRecord`s (Task-tool extraction).
- `_routing_pass_predicate(run)` — pass-predicate for
  `Subagent.Get Routing Pass At K` (C59 hard-coded-predicate lesson).

Empirical trace-probe finding (add-subagent-delegation-testing, task 1.1):
the `claude_code_cli` adapter normalizes every Claude Code `tool_use`
content block into a `ToolCallTrace(name=block["name"], args=block["input"])`
verbatim (`coding_agent/claude_code_cli.py:459-468`). A Claude Code `Task`
delegation therefore surfaces as `ToolCallTrace(name="Task",
args={"subagent_type": <name>, "description": ..., "prompt": ...})`. This
confirms Decision 1's default tool-name set (`{"Task"}`) and identity-probe
order (`subagent_type` first) against the real trace shape — no design
adaptation required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from AgentEval.subagents.types import DelegationRecord

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from AgentEval.stats.types import KeywordRun
    from AgentEval.types import ToolCallTrace

__all__ = [
    "DELEGATION_IDENTITY_KEYS",
    "DEFAULT_DELEGATION_TOOLS",
    "extract_delegations",
]

# Fixed identity-probe order (design Decision 1). The subagent identity is
# read from the delegation trace `args` by probing these keys in order; the
# first present + string value wins. An unrecognized shape degrades to
# `subagent=""` (visible non-match, never a silent drop).
DELEGATION_IDENTITY_KEYS: tuple[str, ...] = ("subagent_type", "agent_type", "agent", "name")

# Default delegation-tool name set (design Decision 1) — Claude-Code-shaped.
# Matched case-insensitively to absorb `task`/`Task` variance across CLIs.
DEFAULT_DELEGATION_TOOLS: frozenset[str] = frozenset({"task"})


def _resolve_identity(args: Any) -> str:
    """Probe `args` for the subagent identity in the fixed key order.

    Returns the first present string value among `DELEGATION_IDENTITY_KEYS`,
    or `""` when no recognized identity key carries a string value.
    """
    if not isinstance(args, dict):
        return ""
    for key in DELEGATION_IDENTITY_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _resolve_str_field(args: Any, key: str) -> str:
    """Return `args[key]` when it is a non-empty string, else `""`."""
    if not isinstance(args, dict):
        return ""
    value = args.get(key)
    return value if isinstance(value, str) else ""


def extract_delegations(
    tool_calls: Iterable[ToolCallTrace],
    delegation_tools: Iterable[str] | None = None,
) -> list[DelegationRecord]:
    """Project a run's `tool_calls` into ordered `DelegationRecord`s.

    A delegation is any `ToolCallTrace` whose `name` is in the
    delegation-tool set (default `{"Task"}`, matched case-insensitively) AND
    whose `source` is NOT `"hosted_mcp"`. A Claude Code `Task` delegation is an
    ADAPTER surface, so a hosted-MCP/user tool that merely happens to be named
    `task` is NOT a delegation (it can legally carry a lower-case `task` name).
    Adapter/observed/absent sources are all eligible. The subagent identity is
    probed from the trace `args` in the fixed key order `subagent_type` →
    `agent_type` → `agent` → `name`. Records are returned ordered by
    `sequence_index`.

    Args:
        tool_calls: The `AgentRunResult.tool_calls` list (or any iterable of
            `ToolCallTrace`).
        delegation_tools: Optional override of the tool-name set. `None` uses
            the default `{"Task"}`. Names are matched case-insensitively.

    Returns:
        A `list[DelegationRecord]` ordered by `sequence_index`. Empty when no
        delegation-tool traces are present.
    """
    if delegation_tools is None:
        wanted = DEFAULT_DELEGATION_TOOLS
    else:
        wanted = frozenset(name.lower() for name in delegation_tools)

    records: list[DelegationRecord] = []
    for trace in tool_calls:
        if trace.name.lower() not in wanted:
            continue
        # A Task delegation is an adapter surface — a hosted-MCP/user tool that
        # merely shares the `task` name is NOT a delegation (source overmatch).
        # Adapter/observed/absent sources stay eligible.
        if getattr(trace, "source", None) == "hosted_mcp":
            continue
        records.append(
            DelegationRecord(
                subagent=_resolve_identity(trace.args),
                prompt=_resolve_str_field(trace.args, "prompt"),
                description=_resolve_str_field(trace.args, "description"),
                sequence_index=trace.sequence_index,
                latency_ms=trace.latency_ms,
                error=trace.error,
                args=trace.args,
            )
        )
    records.sort(key=lambda r: r.sequence_index)
    return records


def observed_subagents(records: Sequence[DelegationRecord]) -> list[str]:
    """Return the subagent identities of `records`, in order (for diagnostics)."""
    return [r.subagent for r in records]


# ---------------------------------------------------------------------------
# add-subagent-delegation-testing / C59 lesson: hard-coded pass-predicate for
# the dedicated `Subagent.Get Routing Pass At K` keyword. Lives in this module
# (not `stats/_internal.py`) because the predicate is delegation-domain
# specific — `DelegationDecision` is a subagents surface type.
# ---------------------------------------------------------------------------


def _routing_pass_predicate(run: KeywordRun) -> bool:
    """Pass-predicate for ``Subagent.Get Routing Pass At K`` (C59 lesson).

    Returns ``True`` iff the wrapped keyword's result is a
    ``DelegationDecision`` with ``delegated=True``. Mirrors
    ``skills._internal._activation_pass_predicate``: the default
    ``Stat.Get Pass At K`` predicate (``completeness == "complete"``) would
    silently return ``False`` for a ``DelegationDecision`` result (it has no
    ``metadata.completeness`` attribute) — the C59 silent-zero failure mode.
    Foreign result types therefore count as a non-pass, never a crash.
    """
    from AgentEval.subagents.types import DelegationDecision

    return isinstance(run.result, DelegationDecision) and run.result.delegated
