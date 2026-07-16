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

"""Tests for the in-memory trace and the tool-call projection."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from AgentEval._core import trace
from AgentEval._core.types import ToolCallTrace


@pytest.fixture(autouse=True)
def _clean_trace() -> Iterator[None]:
    trace.clear()
    yield
    trace.clear()


def test_record_and_project_tool_call() -> None:
    trace.record_tool_call("search", {"query": "cats"}, result="ok")
    calls = trace.get_tool_calls()
    assert len(calls) == 1
    call = calls[0]
    assert isinstance(call, ToolCallTrace)
    assert call.name == "search"
    assert call.args == {"query": "cats"}
    assert call.result == "ok"
    assert call.sequence_index == 0


def test_sequence_index_is_monotonic() -> None:
    trace.record_tool_call("a")
    trace.record_tool_call("b")
    trace.record_tool_call("c")
    calls = trace.get_tool_calls()
    assert [c.name for c in calls] == ["a", "b", "c"]
    assert [c.sequence_index for c in calls] == [0, 1, 2]


def test_non_tool_spans_are_ignored_by_projection() -> None:
    trace.record_span("chat", {"model": "x"})
    trace.record_tool_call("search")
    assert len(trace.get_spans()) == 2
    assert len(trace.get_tool_calls()) == 1


def test_was_tool_called_by_name() -> None:
    trace.record_tool_call("write_file", {"path": "/x", "content": "hi"})
    assert trace.was_tool_called("write_file") is True
    assert trace.was_tool_called("read_file") is False


def test_was_tool_called_with_arg_subset() -> None:
    trace.record_tool_call("write_file", {"path": "/x", "content": "hi"})
    # Subset match: extra recorded args don't defeat the assertion.
    assert trace.was_tool_called("write_file", {"path": "/x"}) is True
    # Wrong value fails.
    assert trace.was_tool_called("write_file", {"path": "/y"}) is False


def test_source_filter() -> None:
    trace.record_tool_call("a", source="adapter")
    trace.record_tool_call("b", source="hosted_mcp")
    assert [c.name for c in trace.get_tool_calls(source="adapter")] == ["a"]
    assert [c.name for c in trace.get_tool_calls(source="hosted_mcp")] == ["b"]


def test_test_id_partitioning() -> None:
    trace.record_tool_call("a", test_id="t1")
    trace.record_tool_call("b", test_id="t2")
    assert [c.name for c in trace.get_tool_calls(test_id="t1")] == ["a"]
    assert [c.name for c in trace.get_tool_calls(test_id="t2")] == ["b"]
    trace.clear(test_id="t1")
    assert trace.get_tool_calls(test_id="t1") == []
    assert [c.name for c in trace.get_tool_calls(test_id="t2")] == ["b"]
