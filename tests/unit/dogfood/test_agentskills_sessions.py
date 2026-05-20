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

"""Unit tests for the Story 6.4 `agentskills_sessions.py` fixture helper
(per AC-6.4.11 — fixture helper has unit-test coverage).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Story 6.4 dogfood fixture helper isn't on sys.path by default — load it
# directly via importlib so the unit tests don't depend on pytest rootdir
# layout. The Robot Framework `.robot` suites at `tests/dogfood/agentskills/`
# use a sibling `Library` directive that resolves via the same mechanism.
_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "dogfood" / "agentskills" / "fixtures" / "agentskills_sessions.py"
_spec = importlib.util.spec_from_file_location("agentskills_sessions", _FIXTURE_PATH)
assert _spec is not None and _spec.loader is not None
agentskills_sessions = importlib.util.module_from_spec(_spec)
sys.modules["agentskills_sessions"] = agentskills_sessions
_spec.loader.exec_module(agentskills_sessions)

build_run_from_session = agentskills_sessions.build_run_from_session
get_external_mixed_coverage_run = agentskills_sessions.get_external_mixed_coverage_run
get_partial_completeness_run = agentskills_sessions.get_partial_completeness_run
get_runs_with_mixed_outcomes = agentskills_sessions.get_runs_with_mixed_outcomes
get_successful_search_run = agentskills_sessions.get_successful_search_run
get_unnecessary_tool_call_run = agentskills_sessions.get_unnecessary_tool_call_run
load_fixture_session = agentskills_sessions.load_fixture_session
successful_search_session = agentskills_sessions.successful_search_session


def test_build_run_from_session_returns_agent_run_result() -> None:
    from AgentEval.types import AgentRunResult

    result = build_run_from_session(successful_search_session())
    assert isinstance(result, AgentRunResult)


def test_successful_search_run_shape() -> None:
    """Canned successful session → 1 tool_call, `complete` completeness, hosted MCP."""
    result = get_successful_search_run()
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search"
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.usage.input_tokens == 50
    assert result.cost_usd > 0


def test_unnecessary_tool_call_run_has_two_calls_with_delete() -> None:
    """Unnecessary-call session has both search + delete (delete is the unnecessary one)."""
    result = get_unnecessary_tool_call_run()
    names = [tc.name for tc in result.tool_calls]
    assert names == ["search", "delete"]


def test_partial_completeness_run_has_partial_marker() -> None:
    """Partial session → completeness="partial", tool_call has error="timeout"."""
    result = get_partial_completeness_run()
    assert result.metadata.completeness == "partial"
    assert result.tool_calls[0].error == "timeout"


def test_external_mixed_coverage_run_flips_mcp_coverage() -> None:
    """External-mixed session triggers FR37 gate."""
    result = get_external_mixed_coverage_run()
    assert result.metadata.mcp_coverage == "external_mixed"


def test_load_fixture_session_reads_vendored_json() -> None:
    """`load_fixture_session("successful_search")` loads the vendored JSON."""
    session = load_fixture_session("successful_search")
    assert session["completeness"] == "complete"
    assert session["tool_calls"][0]["name"] == "search"


def test_load_fixture_session_missing_name_raises() -> None:
    with pytest.raises(FileNotFoundError, match=r"not found"):
        load_fixture_session("does_not_exist")


def test_get_runs_with_mixed_outcomes_count_and_predicate() -> None:
    """`get_runs_with_mixed_outcomes(n=10, pass_count=6)` → 6/10 with completeness=complete."""
    runs = get_runs_with_mixed_outcomes(n=10, pass_count=6)
    assert len(runs) == 10
    complete_count = sum(1 for r in runs if r.metadata.completeness == "complete")
    assert complete_count == 6


def test_get_runs_with_mixed_outcomes_validates_inputs() -> None:
    with pytest.raises(ValueError, match=r"pass_count must be in"):
        get_runs_with_mixed_outcomes(n=10, pass_count=15)
    with pytest.raises(ValueError, match=r"pass_count must be in"):
        get_runs_with_mixed_outcomes(n=10, pass_count=-1)


def test_build_run_from_session_round_trips_json_fixture() -> None:
    """Loading a JSON fixture + building from it produces a valid AgentRunResult."""
    from AgentEval.types import AgentRunResult

    session = load_fixture_session("partial_completeness")
    result = build_run_from_session(session)
    assert isinstance(result, AgentRunResult)
    assert result.metadata.completeness == "partial"
    assert result.tool_calls[0].error == "timeout"


def test_runs_with_mixed_outcomes_each_has_unique_trace_id() -> None:
    """Independent trials must have distinct trace_ids."""
    runs = get_runs_with_mixed_outcomes(n=5, pass_count=3)
    trace_ids = {r.trace_id for r in runs}
    assert len(trace_ids) == 5
