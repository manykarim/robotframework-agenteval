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

"""Tier-1 tool-call coverage metrics over the shared trace projection."""

from __future__ import annotations

import pytest

from MCPLibrary import MCPLibrary

from ._helpers import run_with_calls, trace


def test_count_and_names_over_single_run() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search"), trace("fetch"), trace("search"))
    assert lib.get_tool_call_count(run) == 3
    assert lib.get_tool_call_names(run) == ["search", "fetch", "search"]


def test_count_over_list_of_runs() -> None:
    lib = MCPLibrary()
    runs = [run_with_calls(trace("a")), run_with_calls(trace("b"), trace("c"))]
    assert lib.get_tool_call_count(runs) == 3


def test_count_over_raw_trace_list() -> None:
    lib = MCPLibrary()
    calls = [trace("search"), trace("fetch")]
    assert lib.get_tool_call_count(calls) == 2
    assert lib.get_tool_call_names(calls) == ["search", "fetch"]


def test_hit_rate() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search"))
    assert lib.get_tool_hit_rate(run, ["search", "fetch"]) == pytest.approx(0.5)


def test_hit_rate_empty_expected_is_zero() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search"))
    assert lib.get_tool_hit_rate(run, []) == 0.0


def test_success_rate_counts_non_error_calls() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("a"), trace("b", error="boom"))
    assert lib.get_tool_success_rate(run) == pytest.approx(0.5)


def test_success_rate_zero_calls_is_zero() -> None:
    lib = MCPLibrary()
    assert lib.get_tool_success_rate(run_with_calls()) == 0.0


def test_unnecessary_call_rate() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search"), trace("gossip"))
    assert lib.get_unnecessary_call_rate(run, ["search"]) == pytest.approx(0.5)


def test_was_tool_called_asserts_expected_and_flags_never_called() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search", {"query": "robots"}))
    # An expected tool was exercised ...
    assert lib.was_tool_called(run, "search") is True
    assert lib.was_tool_called(run, "search", {"query": "robots"}) is True
    # ... and one that was never called is flagged.
    assert lib.was_tool_called(run, "delete") is False


def test_was_tool_called_arg_subset_mismatch() -> None:
    lib = MCPLibrary()
    run = run_with_calls(trace("search", {"query": "robots"}))
    assert lib.was_tool_called(run, "search", {"query": "cats"}) is False


def test_coverage_rejects_bad_input_type() -> None:
    lib = MCPLibrary()
    with pytest.raises(TypeError):
        lib.get_tool_call_count("not a run")
