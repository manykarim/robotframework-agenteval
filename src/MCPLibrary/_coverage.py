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

"""Deterministic tool-call coverage metrics over the shared trace projection.

Everything here reads ``ToolCallTrace`` records - the spine's trace projection.
A keyword can hand these helpers a single ``AgentRunResult``, a list of them
(multi-trial), or a raw list of ``ToolCallTrace``; they all normalize to a flat
call list first.
"""

from __future__ import annotations

from typing import Any

from AgentEval._core.types import AgentRunResult, ToolCallTrace

__all__ = [
    "as_tool_calls",
    "tool_call_count",
    "tool_call_names",
    "tool_hit_rate",
    "tool_success_rate",
    "unnecessary_call_rate",
    "was_tool_called",
]


def as_tool_calls(source: Any) -> list[ToolCallTrace]:
    """Normalize a run, a list of runs, or a call list into ``list[ToolCallTrace]``.

    Raises ``TypeError`` on anything else.
    """
    if isinstance(source, AgentRunResult):
        return list(source.tool_calls)
    if isinstance(source, ToolCallTrace):
        return [source]
    if isinstance(source, list):
        calls: list[ToolCallTrace] = []
        for item in source:
            if isinstance(item, AgentRunResult):
                calls.extend(item.tool_calls)
            elif isinstance(item, ToolCallTrace):
                calls.append(item)
            else:
                raise TypeError(f"expected AgentRunResult or ToolCallTrace items; got {type(item).__name__}")
        return calls
    raise TypeError(f"expected an AgentRunResult, a ToolCallTrace, or a list of either; got {type(source).__name__}")


def tool_call_count(source: Any) -> int:
    """Total number of tool calls."""
    return len(as_tool_calls(source))


def tool_call_names(source: Any) -> list[str]:
    """Tool-call names in order, duplicates preserved."""
    return [tc.name for tc in as_tool_calls(source)]


def tool_hit_rate(source: Any, expected_tools: list[str]) -> float:
    """``|expected ∩ observed| / |expected|``. Empty ``expected_tools`` -> 0.0."""
    if not expected_tools:
        return 0.0
    expected = set(expected_tools)
    observed = {tc.name for tc in as_tool_calls(source)}
    return len(expected & observed) / len(expected)


def tool_success_rate(source: Any) -> float:
    """Fraction of calls without an error. Zero calls -> 0.0."""
    calls = as_tool_calls(source)
    if not calls:
        return 0.0
    return sum(1 for tc in calls if tc.error is None) / len(calls)


def unnecessary_call_rate(source: Any, expected_tools: list[str]) -> float:
    """Fraction of calls not in ``expected_tools``. Zero calls -> 0.0."""
    calls = as_tool_calls(source)
    if not calls:
        return 0.0
    expected = set(expected_tools)
    return sum(1 for tc in calls if tc.name not in expected) / len(calls)


def was_tool_called(source: Any, tool_name: str, args: dict[str, Any] | None = None) -> bool:
    """True if ``tool_name`` was called, and (when given) with ``args`` as a subset."""
    for tc in as_tool_calls(source):
        if tc.name != tool_name:
            continue
        if args is None:
            return True
        if all(tc.args.get(k) == v for k, v in args.items()):
            return True
    return False
