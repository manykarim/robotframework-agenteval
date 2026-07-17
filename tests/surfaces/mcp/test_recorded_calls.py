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

"""Live ``MCP.Call Tool`` recording feeds the coverage keywords natively."""

from __future__ import annotations

import pytest

from MCPLibrary import MCPLibrary

from ._helpers import build_echo_server, build_error_server, trace


def test_recorded_calls_feed_coverage_keywords() -> None:
    lib = MCPLibrary()
    echo = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    boom = lib.start_server("boom", "in_memory", server_factory=build_error_server)

    # One ok call, one erroring call.
    ok = lib.call_tool(echo, "search", query="robots")
    assert ok.is_error is False
    err = lib.call_tool(boom, "boom")
    assert err.is_error is True

    calls = lib.get_recorded_tool_calls()
    assert len(calls) == 2

    # The recorded traces carry the hosted-MCP provenance + captured inputs.
    assert [c.source for c in calls] == ["hosted_mcp", "hosted_mcp"]
    assert calls[0].name == "search"
    assert calls[0].args == {"query": "robots"}
    assert calls[0].error is None
    assert calls[1].name == "boom"
    assert calls[1].error  # error_message surfaced onto the trace

    # ... and they feed the existing coverage keywords with no projection.
    assert lib.get_tool_call_count(calls) == 2
    assert lib.get_tool_call_names(calls) == ["search", "boom"]
    assert lib.was_tool_called(calls, "search", {"query": "robots"}) is True
    assert lib.was_tool_called(calls, "search", {"query": "cats"}) is False
    assert lib.get_tool_success_rate(calls) == pytest.approx(0.5)


def test_get_recorded_tool_calls_starts_empty_and_is_a_copy() -> None:
    lib = MCPLibrary()
    calls = lib.get_recorded_tool_calls()
    assert calls == []
    # Returned list is a copy - mutating it can't corrupt the recording.
    calls.append(trace("junk"))
    assert lib.get_recorded_tool_calls() == []


def test_clear_recorded_tool_calls_resets_between_tests() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    lib.call_tool(handle, "echo_back", text="hi")
    assert len(lib.get_recorded_tool_calls()) == 1

    lib.clear_recorded_tool_calls()
    assert lib.get_recorded_tool_calls() == []

    lib.call_tool(handle, "search", query="cats")
    assert lib.get_tool_call_names(lib.get_recorded_tool_calls()) == ["search"]
