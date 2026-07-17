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

"""Tier-1 ``Subagent.Get Routed Subagents`` over an in-process run result."""

from __future__ import annotations

from AgentEval._core import AgentRunResult, ToolCallTrace, get_keyword_tier
from SubagentsLibrary import SubagentsLibrary
from SubagentsLibrary.types import RoutedSubagents


def _run(*calls: ToolCallTrace) -> AgentRunResult:
    return AgentRunResult(response_text="", tool_calls=list(calls))


def _delegate(agent_name: str | None, index: int, **extra: object) -> ToolCallTrace:
    args: dict[str, object] = dict(extra)
    if agent_name is not None:
        args["agent_name"] = agent_name
    return ToolCallTrace(name="delegate_task", args=args, sequence_index=index)


def test_reports_names_counts_and_total() -> None:
    result = _run(
        _delegate("code-reviewer", 0, task="a"),
        _delegate("docs-writer", 1, task="b"),
        _delegate("code-reviewer", 2, task="c"),
    )
    routed = SubagentsLibrary().get_routed_subagents(result)
    assert isinstance(routed, RoutedSubagents)
    assert routed.names == ("code-reviewer", "docs-writer")  # first-seen order, distinct
    assert routed.counts == {"code-reviewer": 2, "docs-writer": 1}
    assert routed.total == 3


def test_ignores_non_delegate_tool_calls() -> None:
    result = _run(
        ToolCallTrace(name="load_capability", args={"id": "x"}, sequence_index=0),
        _delegate("researcher", 1),
    )
    routed = SubagentsLibrary().get_routed_subagents(result)
    assert routed.names == ("researcher",)
    assert routed.total == 1


def test_unresolved_agent_name_stays_visible_in_total_only() -> None:
    # A delegate call with no resolvable agent_name is counted in total but in no
    # per-name bucket - a visible gap, never a silent drop.
    result = _run(
        _delegate("planner", 0),
        _delegate(None, 1, task="mystery"),
    )
    routed = SubagentsLibrary().get_routed_subagents(result)
    assert routed.counts == {"planner": 1}
    assert routed.total == 2
    assert sum(routed.counts.values()) < routed.total


def test_honors_custom_tool_and_identity_key() -> None:
    result = _run(
        ToolCallTrace(name="handoff", args={"to": "specialist"}, sequence_index=0),
    )
    lib = SubagentsLibrary()
    assert lib.get_routed_subagents(result).total == 0  # default delegate_task misses it
    routed = lib.get_routed_subagents(result, delegation_tool="handoff", identity_key="to")
    assert routed.names == ("specialist",)
    assert routed.counts == {"specialist": 1}


def test_delegate_tool_name_matched_case_insensitively() -> None:
    result = _run(ToolCallTrace(name="Delegate_Task", args={"agent_name": "x"}, sequence_index=0))
    routed = SubagentsLibrary().get_routed_subagents(result)
    assert routed.names == ("x",)


def test_hosted_mcp_tool_sharing_the_name_is_not_a_delegation() -> None:
    result = _run(
        ToolCallTrace(name="delegate_task", args={"agent_name": "x"}, sequence_index=0, source="hosted_mcp"),
    )
    routed = SubagentsLibrary().get_routed_subagents(result)
    assert routed.names == ()
    assert routed.total == 0


def test_empty_run_reports_nothing() -> None:
    routed = SubagentsLibrary().get_routed_subagents(_run())
    assert routed.names == ()
    assert routed.counts == {}
    assert routed.total == 0


def test_get_routed_subagents_is_tier_1() -> None:
    assert get_keyword_tier(SubagentsLibrary.get_routed_subagents) == 1
