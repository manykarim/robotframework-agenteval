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

"""Unit tests for `subagents._internal.extract_delegations` (task 6.1).

Covers tool-name case-insensitivity, custom delegation tool, identity-probe
order, empty-string degradation, and sequence ordering — all from
constructed `ToolCallTrace` fixtures (no adapter).
"""

from __future__ import annotations

from typing import Any

from AgentEval.subagents._internal import extract_delegations
from AgentEval.subagents.types import DelegationRecord
from AgentEval.types import ToolCallTrace


def _tct(name: str, args: dict[str, Any], seq: int) -> ToolCallTrace:
    return ToolCallTrace(
        name=name,
        args=args,
        result=None,
        error=None,
        latency_ms=float(seq),
        source="adapter",
        gen_ai_tool_call_id=f"id-{seq}",
        sequence_index=seq,
    )


def test_two_task_traces_yield_two_ordered_records() -> None:
    traces = [
        _tct("Task", {"subagent_type": "code-reviewer", "prompt": "review the diff"}, 0),
        _tct("Bash", {"command": "ls"}, 1),
        _tct("Task", {"subagent_type": "test-writer", "prompt": "add tests"}, 2),
    ]
    records = extract_delegations(traces)
    assert [r.subagent for r in records] == ["code-reviewer", "test-writer"]
    assert records[0].prompt == "review the diff"
    assert records[1].prompt == "add tests"
    assert all(isinstance(r, DelegationRecord) for r in records)


def test_no_delegation_traces_yields_empty_list() -> None:
    traces = [_tct("Read", {"file": "x"}, 0), _tct("Bash", {"command": "ls"}, 1)]
    assert extract_delegations(traces) == []


def test_tool_name_match_is_case_insensitive() -> None:
    traces = [_tct("task", {"subagent_type": "code-reviewer"}, 0)]
    records = extract_delegations(traces)
    assert len(records) == 1
    assert records[0].subagent == "code-reviewer"


def test_custom_delegation_tool_name_is_honored() -> None:
    traces = [
        _tct("dispatch_agent", {"agent": "docs-writer"}, 0),
        _tct("Task", {"subagent_type": "code-reviewer"}, 1),
    ]
    records = extract_delegations(traces, delegation_tools=["dispatch_agent"])
    assert [r.subagent for r in records] == ["docs-writer"]


def test_identity_probe_order_prefers_subagent_type() -> None:
    # All four identity keys present; subagent_type wins.
    traces = [_tct("Task", {"subagent_type": "a", "agent_type": "b", "agent": "c", "name": "d"}, 0)]
    assert extract_delegations(traces)[0].subagent == "a"


def test_identity_probe_falls_through_key_order() -> None:
    traces = [
        _tct("Task", {"agent_type": "b"}, 0),
        _tct("Task", {"agent": "c"}, 1),
        _tct("Task", {"name": "d"}, 2),
    ]
    assert [r.subagent for r in extract_delegations(traces)] == ["b", "c", "d"]


def test_unrecognized_identity_degrades_to_empty_string() -> None:
    traces = [_tct("Task", {"unexpected_key": "code-reviewer"}, 0)]
    records = extract_delegations(traces)
    assert len(records) == 1
    assert records[0].subagent == ""
    # Raw args retained for diagnostics.
    assert records[0].args == {"unexpected_key": "code-reviewer"}


def test_records_ordered_by_sequence_index_not_input_order() -> None:
    traces = [
        _tct("Task", {"subagent_type": "second"}, 5),
        _tct("Task", {"subagent_type": "first"}, 1),
    ]
    records = extract_delegations(traces)
    assert [r.subagent for r in records] == ["first", "second"]
    assert [r.sequence_index for r in records] == [1, 5]


def test_description_and_error_fields_populated() -> None:
    t = ToolCallTrace(
        name="Task",
        args={"subagent_type": "code-reviewer", "description": "Review PR", "prompt": "p"},
        result=None,
        error="boom",
        latency_ms=12.5,
        source="adapter",
        gen_ai_tool_call_id="x",
        sequence_index=0,
    )
    r = extract_delegations([t])[0]
    assert r.description == "Review PR"
    assert r.error == "boom"
    assert r.latency_ms == 12.5


def test_hosted_mcp_tool_named_task_is_not_a_delegation() -> None:
    # Codex MED repro: a hosted MCP/user tool literally named "task" must NOT
    # be counted as a Claude Task delegation (adapter-surface guard).
    trace = ToolCallTrace(
        name="task",
        args={"input": "not delegation"},
        result=None,
        error=None,
        latency_ms=0.0,
        source="hosted_mcp",
        gen_ai_tool_call_id="mcp-1",
        sequence_index=0,
    )
    assert extract_delegations([trace]) == []


def test_adapter_task_still_counts_alongside_hosted_mcp_task() -> None:
    # An adapter-source Task call is a real delegation; a hosted_mcp "task"
    # collision in the same run is filtered out.
    adapter = _tct("Task", {"subagent_type": "code-reviewer"}, 0)
    hosted = ToolCallTrace(
        name="task",
        args={"name": "code-reviewer"},
        result=None,
        error=None,
        latency_ms=0.0,
        source="hosted_mcp",
        gen_ai_tool_call_id="mcp-2",
        sequence_index=1,
    )
    records = extract_delegations([adapter, hosted])
    assert [r.subagent for r in records] == ["code-reviewer"]


def test_delegation_record_args_is_defensively_copied() -> None:
    args = {"subagent_type": "code-reviewer"}
    t = _tct("Task", args, 0)
    r = extract_delegations([t])[0]
    args["subagent_type"] = "mutated"
    # The record's args snapshot is decoupled from later source mutation.
    assert r.args["subagent_type"] == "code-reviewer"
