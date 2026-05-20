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

"""End-to-end tests for `MCP.Get Tool Discoverability` (Story 4.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.discoverability.schema import (
    DiscoverabilityResult,
    DiscoverabilitySummary,
    TaskResult,
)
from AgentEval.errors import InvalidDiscoverabilityTasksError
from AgentEval.mcp.library import MCPLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def _make_stub_adapter(tool_names_per_call: list[list[str]], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
    """Build a stub adapter class returning scripted tool_calls per run().

    Each element of `tool_names_per_call` is the list of tool names that
    `run()` should report on the i-th invocation. The class is fresh per
    test so the call counter resets cleanly.
    """

    class _StubAdapter(InProcessAdapter):
        _call_idx = 0

        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            self._kwargs = kwargs

        def run(
            self,
            prompt: str,
            tools: Any = None,
            mcp_servers: Any = None,
            **kwargs: Any,
        ) -> AgentRunResult:
            idx = type(self)._call_idx
            type(self)._call_idx += 1
            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
            tool_calls = [
                ToolCallTrace(
                    name=name,
                    args={},
                    result=None,
                    error=None,
                    latency_ms=1.0,
                    source="adapter",
                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
                    sequence_index=i,
                )
                for i, name in enumerate(names)
            ]
            return AgentRunResult(
                response_text=f"stub-{idx}",
                tool_calls=tool_calls,
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost_per_call,
                latency_seconds=0.001,
                trace_id=f"stub-id-{idx:032d}"[:32],
            )

    return _StubAdapter


def _make_stub_adapter_per_trial_costs(
    tool_names_per_call: list[list[str]], costs_per_call: list[float]
) -> type[InProcessAdapter]:
    """Stub adapter variant with distinct per-trial costs.

    Story 4.4 code-review LOW-B fix 2026-05-20 (Codex 244): the original
    fixture used `all(c == 0.002 ...)` which would pass under any list
    reordering. This variant scripts a distinct cost per call so the
    ordering invariant is testable.
    """

    class _StubAdapter(InProcessAdapter):
        _call_idx = 0

        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            self._kwargs = kwargs

        def run(
            self,
            prompt: str,
            tools: Any = None,
            mcp_servers: Any = None,
            **kwargs: Any,
        ) -> AgentRunResult:
            idx = type(self)._call_idx
            type(self)._call_idx += 1
            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
            cost = costs_per_call[idx] if idx < len(costs_per_call) else 0.0
            tool_calls = [
                ToolCallTrace(
                    name=name,
                    args={},
                    result=None,
                    error=None,
                    latency_ms=1.0,
                    source="adapter",
                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
                    sequence_index=i,
                )
                for i, name in enumerate(names)
            ]
            return AgentRunResult(
                response_text=f"stub-{idx}",
                tool_calls=tool_calls,
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=0.001,
                trace_id=f"stub-id-{idx:032d}"[:32],
            )

    return _StubAdapter


@pytest.fixture
def lib() -> MCPLibrary:
    return MCPLibrary()


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"


def test_get_tool_discoverability_returns_discoverability_result(lib: MCPLibrary, fixture_path: Path) -> None:
    """End-to-end happy path: all 9 trials report `echo_back` -> 100% pass.

    Verifies PRD FR10a L1499 ratified shape: `per_task_results` + `summary`
    nesting + `mcp_coverage` (Story 4.4 code-review HIGH-B fix 2026-05-20).
    """
    stub = _make_stub_adapter([["echo_back"]] * 9)
    register_adapter("stub_disco_all_pass", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_all_pass",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    assert isinstance(result, DiscoverabilityResult)
    assert isinstance(result.summary, DiscoverabilitySummary)
    assert len(result.per_task_results) == 3
    assert result.summary.overall_pass_rate == 1.0
    for tr in result.per_task_results:
        assert tr.success_count == 3
        assert tr.trials_run == 3
        assert tr.wilson_ci_upper == 1.0
        assert 0.4 < tr.wilson_ci_lower < 0.5
    assert abs(result.summary.total_cost_usd - 0.009) < 1e-9
    assert result.summary.total_runtime_seconds >= 0.0
    assert result.mcp_coverage == "hosted_in_process"


def test_get_tool_discoverability_no_tool_calls_zero_pass_rate(lib: MCPLibrary, fixture_path: Path) -> None:
    """Adapter returns NO tool calls -> 0/9 successes -> overall_pass_rate = 0."""
    stub = _make_stub_adapter([[]] * 9)
    register_adapter("stub_disco_no_calls", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_no_calls",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    assert result.summary.overall_pass_rate == 0.0
    for tr in result.per_task_results:
        assert tr.success_count == 0
        assert tr.wilson_ci_lower == 0.0


def test_get_tool_discoverability_competing_tools_tracked(lib: MCPLibrary, fixture_path: Path) -> None:
    """When the model picks a tool NOT in expected_tools, it's tracked."""
    stub = _make_stub_adapter([["wrong_tool"]] * 9)
    register_adapter("stub_disco_competing", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_competing",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    assert result.summary.overall_pass_rate == 0.0
    for tr in result.per_task_results:
        assert "wrong_tool" in tr.competing_tools_picked


def test_get_tool_discoverability_partial_pass_rate_with_wilson_ci(lib: MCPLibrary, fixture_path: Path) -> None:
    """Mixed success/failure per task — Wilson CI brackets pass rate.

    Story 4.4 code-review 2-way LOW-A fix 2026-05-20 (Blind LOW-2 + Codex 157):
    pre-edit asserted only edge bounds; the test name claimed "brackets pass
    rate" but the 2/3 mid-case wasn't bracket-checked. Per
    `feedback_test_name_assertion_match` (Epic 3 retro), test body must
    deliver on the name's promise — now asserts the full bracketing
    invariant for all 3 tasks AND the canonical Wilson reference value
    for 2/3 at 95% confidence ≈ (0.208, 0.939).
    """
    pattern = [
        ["echo_back"],
        ["echo_back"],
        [],  # task 1: 2/3
        [],
        [],
        [],  # task 2: 0/3
        ["echo_back"],
        ["echo_back"],
        ["echo_back"],  # task 3: 3/3
    ]
    stub = _make_stub_adapter(pattern)
    register_adapter("stub_disco_partial", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_partial",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    assert abs(result.summary.overall_pass_rate - 5 / 9) < 1e-9
    t1, t2, t3 = result.per_task_results
    assert t1.success_count == 2
    assert t2.success_count == 0
    assert t3.success_count == 3
    # Bracketing invariant for every task — Wilson CI MUST contain the
    # point estimate (Wilson is a "score" interval, not Wald; bracket is
    # guaranteed by construction).
    for tr in result.per_task_results:
        assert tr.wilson_ci_lower <= tr.pass_rate <= tr.wilson_ci_upper, (
            f"Wilson CI [{tr.wilson_ci_lower}, {tr.wilson_ci_upper}] does not "
            f"bracket pass_rate={tr.pass_rate} for task {tr.task_id}"
        )
    # Canonical Wilson reference for 2/3 at 95% ≈ (0.208, 0.939).
    assert 0.20 < t1.wilson_ci_lower < 0.22
    assert 0.93 < t1.wilson_ci_upper < 0.95
    # Edge cases still verified.
    assert t2.wilson_ci_lower == 0.0
    assert t3.wilson_ci_upper == 1.0


def test_get_tool_discoverability_missing_tasks_kwarg_raises(lib: MCPLibrary) -> None:
    with pytest.raises(ValueError, match="tasks"):
        lib.get_tool_discoverability(mcp_server="echo", adapter="generic")


def test_get_tool_discoverability_missing_mcp_server_kwarg_raises(lib: MCPLibrary, fixture_path: Path) -> None:
    """Story 4.4 code-review MED-E fix 2026-05-20 (Edge-cases M2): empty
    `mcp_server=""` was silently accepted pre-edit; now rejected so the
    DF-4.1-S2 carry-over future-proofs.
    """
    with pytest.raises(ValueError, match="mcp_server"):
        lib.get_tool_discoverability(mcp_server="", adapter="generic", tasks=str(fixture_path))


def test_get_tool_discoverability_invalid_yaml_raises(lib: MCPLibrary, tmp_path: Path) -> None:
    bad = tmp_path / "tasks.yaml"
    bad.write_text("not_tasks: x\n")
    with pytest.raises(InvalidDiscoverabilityTasksError):
        lib.get_tool_discoverability(mcp_server="echo", adapter="generic", tasks=str(bad))


def test_get_tool_discoverability_zero_trials_raises(lib: MCPLibrary, fixture_path: Path) -> None:
    with pytest.raises(ValueError, match="trials_per_task"):
        lib.get_tool_discoverability(
            mcp_server="echo",
            adapter="generic",
            tasks=str(fixture_path),
            trials_per_task=0,
        )


def test_get_tool_discoverability_unknown_adapter_raises(lib: MCPLibrary, fixture_path: Path) -> None:
    from AgentEval.errors import AdapterDiscoveryError

    with pytest.raises(AdapterDiscoveryError):
        lib.get_tool_discoverability(
            mcp_server="echo",
            adapter="nonexistent_xyz_42",
            tasks=str(fixture_path),
        )


def test_keyword_has_tier_3_annotation() -> None:
    assert get_keyword_tier(MCPLibrary.get_tool_discoverability) == 3


def test_keyword_has_robot_marker() -> None:
    assert hasattr(MCPLibrary.get_tool_discoverability, "robot_name")
    assert MCPLibrary.get_tool_discoverability.robot_name == "Get Tool Discoverability"


def test_task_result_pass_rate_property() -> None:
    tr = TaskResult(task_id="t", task_prompt="hi", trials_run=4, success_count=3)
    assert tr.pass_rate == 0.75


def test_task_result_pass_rate_zero_trials() -> None:
    tr = TaskResult(task_id="t", task_prompt="hi", trials_run=0, success_count=0)
    assert tr.pass_rate == 0.0


def test_get_tool_discoverability_tracks_per_trial_data(lib: MCPLibrary, fixture_path: Path) -> None:
    """Per-trial tool_calls + cost_per_trial preserved in order.

    Story 4.4 code-review LOW-B fix 2026-05-20 (Codex 244): pre-edit
    `assert all(c == 0.002 ...)` would pass under any list reordering.
    Now scripts distinct per-trial costs and asserts the exact sequence
    so any reordering regression fails loud.
    """
    stub = _make_stub_adapter_per_trial_costs(
        tool_names_per_call=[
            ["echo_back", "extra_tool"],
            ["wrong"],
            [],
            ["echo_back"],
            ["echo_back"],
            ["echo_back"],
            ["echo_back"],
            ["echo_back"],
            ["echo_back"],
        ],
        costs_per_call=[0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009],
    )
    register_adapter("stub_disco_per_trial", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_per_trial",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    t1, t2, t3 = result.per_task_results
    # Trial 1 of task 1 had 2 tool calls; trial 2 had 1; trial 3 had 0.
    assert [len(trial) for trial in t1.tool_calls_per_trial] == [2, 1, 0]
    # Costs preserved in trial order — distinct per trial.
    assert t1.cost_per_trial_usd == [0.001, 0.002, 0.003]
    assert t2.cost_per_trial_usd == [0.004, 0.005, 0.006]
    assert t3.cost_per_trial_usd == [0.007, 0.008, 0.009]
    # competing_tools_picked includes "extra_tool" + "wrong" (not in echo_back).
    assert "extra_tool" in t1.competing_tools_picked
    assert "wrong" in t1.competing_tools_picked


def test_get_tool_discoverability_empty_expected_tools_wildcard_mode(lib: MCPLibrary, tmp_path: Path) -> None:
    """Empty `expected_tools` -> ANY tool call counts as success AND all
    called names appear in `competing_tools_picked`.

    Story 4.4 code-review 3-way MED-A fix 2026-05-20 (Edge-cases M1 + Codex
    MED + Blind LOW-1): pre-edit `competing_set.update(...)` only ran in
    the populated-expected_tools branch, leaving wildcard-mode tasks with
    permanently-empty competing_tools_picked. Now wildcard mode
    populates competing_tools_picked with ALL called names so the verdict
    matrix retains visibility into what tool the model actually picked.
    """
    fixture = tmp_path / "wildcard.yaml"
    fixture.write_text(
        "tasks:\n  - id: wildcard_task\n    prompt: do anything\n"
        # expected_tools omitted -> defaults to []
    )
    stub = _make_stub_adapter([["some_tool"], ["another_tool"], ["some_tool"]])
    register_adapter("stub_disco_wildcard", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_wildcard",
        tasks=str(fixture),
        trials_per_task=3,
    )
    t = result.per_task_results[0]
    # ANY tool call counted as success.
    assert t.success_count == 3
    # ALL called names tracked in competing_tools_picked.
    assert set(t.competing_tools_picked) == {"some_tool", "another_tool"}


def test_get_tool_discoverability_runtime_includes_setup(lib: MCPLibrary, fixture_path: Path) -> None:
    """`total_runtime_seconds` captures end-to-end wall time including
    setup, NOT just the dispatch loop.

    Story 4.4 code-review MED-B fix 2026-05-20 (Codex empirical probe):
    pre-edit `t_start` fired after adapter construction, underreporting
    the budget audit by the ctor cost (probe showed 0.0202 vs 0.3712
    actual). Now `t_start` fires at function entry.
    """
    import time as _time

    class _SlowCtorStub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            _time.sleep(0.05)  # 50ms ctor cost

        def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="x",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.001,
                trace_id="x" * 32,
            )

    register_adapter("stub_disco_slow_ctor", _SlowCtorStub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_slow_ctor",
        tasks=str(fixture_path),
        trials_per_task=1,
    )
    # If t_start were inside the dispatch loop, runtime would be ~milliseconds.
    # With t_start at function entry, the 50ms ctor cost MUST be captured.
    assert result.summary.total_runtime_seconds >= 0.04, (
        f"total_runtime_seconds={result.summary.total_runtime_seconds} "
        f"too low — must include adapter ctor cost (~50ms slept)."
    )


def test_get_tool_discoverability_budget_carve_out_not_enforced(lib: MCPLibrary, fixture_path: Path) -> None:
    """Pin the current Phase-1 carve-out: `max_cost_usd` is tracked but
    NOT enforced (DF-4.4-S1 deferred).

    Story 4.4 code-review MED-F fix 2026-05-20 (Edge-cases M3): explicit
    test ratifying the carve-out so Phase-1.5 enforcement landing flips
    this assert and forces an explicit upgrade.
    """
    # Single task fixture (avoids needing 9 trials).
    stub = _make_stub_adapter([["echo_back"]] * 9, cost_per_call=2.0)
    register_adapter("stub_disco_overbudget", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_overbudget",
        tasks=str(fixture_path),
        trials_per_task=3,
        max_cost_usd=1.00,  # Cap = $1 but adapter charges $2/call -> $18 total.
    )
    # Phase-1 carve-out: total_cost_usd EXCEEDS max_cost_usd because
    # DF-4.4-S1 enforcement is deferred. When that lands, this assert
    # will flip + this test must be rewritten to verify enforcement.
    assert result.summary.total_cost_usd > 1.00
    assert abs(result.summary.total_cost_usd - 18.0) < 1e-9


def test_get_tool_discoverability_strict_signature_adapter_raises_with_df_4_4_s2_reference(
    lib: MCPLibrary, fixture_path: Path
) -> None:
    """Story 4.4 code-review MED-D fix 2026-05-20 (Blind): the comment-vs-code
    drift on the adapter-ctor TypeError path is now resolved — re-raise is
    intentional + the error message names DF-4.4-S2 as the carry-over.
    Test verifies the user-facing error mentions the carry-over so future
    maintainers can trace the deferred work.
    """

    class _StrictAdapter(InProcessAdapter):
        def __init__(self) -> None:  # NO kwargs accepted
            super().__init__()

        def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kwargs: Any) -> AgentRunResult:
            raise NotImplementedError

    register_adapter("stub_disco_strict", _StrictAdapter)
    with pytest.raises(TypeError, match="DF-4.4-S2"):
        lib.get_tool_discoverability(
            mcp_server="echo",
            adapter="stub_disco_strict",
            tasks=str(fixture_path),
            extra_kwarg="oops",  # not accepted by strict ctor
        )


def test_task_result_inner_list_mutation_blocked(lib: MCPLibrary, fixture_path: Path) -> None:
    """Story 4.4 code-review 2-way MED-C fix 2026-05-20 (Codex + Blind LOW-3):
    pre-edit `__post_init__` shallow-copied the outer list but aliased
    inner `list[ToolCallTrace]` references. Mutating an inner list leaked
    through despite `frozen=True`. Deep-copy now isolates inner lists.
    """
    stub = _make_stub_adapter([["echo_back"]] * 9)
    register_adapter("stub_disco_frozen_check", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_frozen_check",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    t = result.per_task_results[0]
    original_first_trial = list(t.tool_calls_per_trial[0])
    # Caller-side mutation attempt — direct on the leaked reference.
    leaked_ref = t.tool_calls_per_trial[0]
    leaked_ref.append("EVIL_MUTATION")  # type: ignore[arg-type]
    # The TaskResult itself must NOT reflect the mutation; this is the
    # deep-copy invariant. Build a fresh TaskResult to verify isolation:
    fresh = TaskResult(
        task_id="t",
        task_prompt="p",
        trials_run=1,
        success_count=0,
        tool_calls_per_trial=[original_first_trial],
    )
    # Mutate the source list AFTER construction.
    original_first_trial.append("LATER_MUTATION")  # type: ignore[arg-type]
    # The fresh TaskResult must NOT reflect the post-construction mutation.
    assert "LATER_MUTATION" not in fresh.tool_calls_per_trial[0]
    assert len(fresh.tool_calls_per_trial[0]) == len(original_first_trial) - 1


def test_get_tool_discoverability_summary_shape_per_prd_fr10a(lib: MCPLibrary, fixture_path: Path) -> None:
    """Story 4.4 code-review HIGH-B fix 2026-05-20 (Auditor citation-drift
    catch): PRD FR10a L1499 ratifies `DiscoverabilityResult` as
    `per_task_results` + `summary` (nested) + `mcp_coverage`. This test
    pins the ratified shape so future flattening regressions fail loud.
    """
    stub = _make_stub_adapter([["echo_back"]] * 9)
    register_adapter("stub_disco_shape_check", stub)
    result = lib.get_tool_discoverability(
        mcp_server="echo",
        adapter="stub_disco_shape_check",
        tasks=str(fixture_path),
        trials_per_task=3,
    )
    # Result shape MUST be nested.
    assert hasattr(result, "summary")
    assert isinstance(result.summary, DiscoverabilitySummary)
    # The 3 summary fields are reachable ONLY via `result.summary.*` —
    # NOT directly on the result. Verify the flattened-shape regression
    # would fail.
    assert not hasattr(result, "overall_pass_rate"), (
        "DiscoverabilityResult must NOT carry `overall_pass_rate` directly; "
        "PRD FR10a L1499 ratifies the nested `summary.overall_pass_rate` shape."
    )
    assert not hasattr(result, "total_cost_usd")
    assert not hasattr(result, "total_runtime_seconds")
    # Summary fields are present + correctly typed.
    assert isinstance(result.summary.overall_pass_rate, float)
    assert isinstance(result.summary.total_cost_usd, float)
    assert isinstance(result.summary.total_runtime_seconds, float)
