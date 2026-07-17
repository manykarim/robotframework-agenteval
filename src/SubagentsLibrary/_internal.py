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

"""Delegation extraction from an already-captured run's tool calls.

A Claude Code ``Task`` delegation surfaces as ``ToolCallTrace(name="Task",
args={"subagent_type": <name>, ...})``. We project those into ordered
``DelegationRecord`` values; the subagent identity is probed from ``args`` in a
fixed key order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from SubagentsLibrary.types import DelegationRecord, RoutedSubagents

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from AgentEval._core import ToolCallTrace

__all__ = [
    "DELEGATION_IDENTITY_KEYS",
    "DEFAULT_DELEGATION_TOOLS",
    "HARNESS_DELEGATION_TOOL",
    "HARNESS_IDENTITY_KEY",
    "extract_delegations",
    "extract_routed_subagents",
    "observed_subagents",
]

# Fixed identity-probe order: the first present, non-empty string value wins.
DELEGATION_IDENTITY_KEYS: tuple[str, ...] = ("subagent_type", "agent_type", "agent", "name")

# Default delegation-tool name set (Claude-Code shaped). Matched case-insensitively.
DEFAULT_DELEGATION_TOOLS: frozenset[str] = frozenset({"task"})

# The pydantic-ai-harness ``SubAgents`` capability exposes exactly one delegate
# tool - ``delegate_task`` - whose chosen subagent rides in the ``agent_name``
# argument. This is the in-process adapter's delegation shape (distinct from the
# Claude-Code ``Task`` / ``subagent_type`` shape the Tier-1 extractor defaults to).
HARNESS_DELEGATION_TOOL: str = "delegate_task"
HARNESS_IDENTITY_KEY: str = "agent_name"


def _resolve_identity(args: Any) -> str:
    """Probe ``args`` for the subagent identity in the fixed key order."""
    if not isinstance(args, dict):
        return ""
    for key in DELEGATION_IDENTITY_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _resolve_str_field(args: Any, key: str) -> str:
    """Return ``args[key]`` when it is a string, else ``""``."""
    if not isinstance(args, dict):
        return ""
    value = args.get(key)
    return value if isinstance(value, str) else ""


def extract_delegations(
    tool_calls: Iterable[ToolCallTrace],
    delegation_tools: Iterable[str] | None = None,
) -> list[DelegationRecord]:
    """Project a run's ``tool_calls`` into ordered ``DelegationRecord`` values.

    A delegation is any ``ToolCallTrace`` whose ``name`` is in the delegation-tool
    set (default ``{"Task"}``, matched case-insensitively) and whose ``source`` is
    not ``"hosted_mcp"`` - a hosted-MCP tool that merely shares the ``task`` name
    is not a delegation. Records are returned ordered by ``sequence_index``.
    """
    if delegation_tools is None:
        wanted = DEFAULT_DELEGATION_TOOLS
    else:
        wanted = frozenset(name.lower() for name in delegation_tools)

    records: list[DelegationRecord] = []
    for trace in tool_calls:
        if trace.name.lower() not in wanted:
            continue
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
    """Return the subagent identities of ``records``, in order (for diagnostics)."""
    return [r.subagent for r in records]


def extract_routed_subagents(
    tool_calls: Iterable[ToolCallTrace],
    delegation_tool: str = HARNESS_DELEGATION_TOOL,
    identity_key: str = HARNESS_IDENTITY_KEY,
) -> RoutedSubagents:
    """Project a run's ``tool_calls`` into a ``RoutedSubagents`` routing readout.

    Filters for tool calls whose ``name`` equals ``delegation_tool`` (default
    ``delegate_task``, matched case-insensitively) that are not hosted-MCP tools,
    then reads each call's ``identity_key`` argument (default ``agent_name``) as
    the delegated subagent. ``total`` counts every matching delegate call; a call
    whose identity cannot be resolved contributes to ``total`` but to no per-name
    count, so it stays visible rather than being silently dropped.
    """
    wanted = delegation_tool.lower()
    names: list[str] = []
    counts: dict[str, int] = {}
    total = 0
    for trace in tool_calls:
        if trace.name.lower() != wanted:
            continue
        if getattr(trace, "source", None) == "hosted_mcp":
            continue
        total += 1
        name = _resolve_str_field(trace.args, identity_key)
        if not name:
            continue
        if name not in counts:
            names.append(name)
        counts[name] = counts.get(name, 0) + 1
    return RoutedSubagents(names=tuple(names), counts=counts, total=total)
