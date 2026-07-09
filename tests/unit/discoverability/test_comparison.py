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

"""Unit tests for `MCP.Compare Tool Discoverability` cross-adapter surface (Story 13.3).

Coverage:
- `DiscoverabilityComparisonResult` / `PairwiseAdapterDelta` /
  `DiscoverabilityComparisonSummary` dataclass validators.
- `CohortHeatmap.from_comparison` multi-column heatmap.
- Pairwise delta computation (C(N, 2) coverage for N=2 + N=3).
- Mann-Whitney U dispatch via the Story 13.1 pure helper.

ImportError-gate tests for the `[agenteval-advanced]` extra requirement
live in the companion `test_comparison_extras_gate.py` file per Story
13.1 L-2 lesson (NO top-level `importorskip` so they run in both base
+ WITH-extras CI envs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Phase-2 deps required.
pytest.importorskip("scipy")
pytest.importorskip("numpy")
pytest.importorskip("opentelemetry")

from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
from AgentEval.discoverability.schema import (  # noqa: E402
    DiscoverabilityComparisonResult,
    DiscoverabilityComparisonSummary,
    DiscoverabilityResult,
    DiscoverabilitySummary,
    PairwiseAdapterDelta,
    TaskResult,
)
from AgentEval.mcp.library import MCPLibrary  # noqa: E402
from AgentEval.stats.types import MannWhitneyResult  # noqa: E402
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402

# --------------------------------------------------------------------------- #
# Stub adapter factory (reused from test_keyword.py pattern)                  #
# --------------------------------------------------------------------------- #


def _make_stub_adapter(tool_names_per_call: list[list[str]], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
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


@pytest.fixture
def lib() -> MCPLibrary:
    return MCPLibrary()


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"


# --------------------------------------------------------------------------- #
# Helper builders for dataclass validator tests                               #
# --------------------------------------------------------------------------- #


def _make_mwu(p_value: float = 0.5) -> MannWhitneyResult:
    return MannWhitneyResult(u_statistic=10.0, p_value=p_value, effect_size_r=0.0, n_a=5, n_b=5)


def _make_discoverability_result(pass_rate: float, n_tasks: int = 3) -> DiscoverabilityResult:
    per_task = [
        TaskResult(
            task_id=f"t{i}",
            task_prompt=f"prompt {i}",
            trials_run=10,
            success_count=int(pass_rate * 10),
            tool_calls_per_trial=[],
            competing_tools_picked=[],
            cost_per_trial_usd=[],
            wilson_ci_lower=0.0,
            wilson_ci_upper=1.0,
        )
        for i in range(n_tasks)
    ]
    return DiscoverabilityResult(
        per_task_results=per_task,
        summary=DiscoverabilitySummary(overall_pass_rate=pass_rate, total_cost_usd=0.0, total_runtime_seconds=0.1),
        mcp_coverage="hosted_in_process",
    )


# --------------------------------------------------------------------------- #
# Dataclass validators (6 tests)                                              #
# --------------------------------------------------------------------------- #


def test_comparison_result_rejects_single_adapter() -> None:
    """len(adapters) < 2 raises ValueError."""
    per = {"a": _make_discoverability_result(1.0)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a",), cells=(("t0", "a", 1.0),))
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter={"a": 1.0},
        best_adapter="a",
        worst_adapter="a",
    )
    with pytest.raises(ValueError, match="len\\(adapters\\) >= 2"):
        DiscoverabilityComparisonResult(
            adapters=("a",),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_comparison_result_rejects_adapters_keys_mismatch() -> None:
    """adapters ↔ per_adapter_results key mismatch raises ValueError."""
    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
        best_adapter="a",
        worst_adapter="b",
    )
    with pytest.raises(ValueError, match="per_adapter_results keys"):
        DiscoverabilityComparisonResult(
            adapters=("a", "c"),  # 'c' not in per
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_comparison_result_rejects_heatmap_models_mismatch() -> None:
    """adapters ↔ heatmap.models mismatch raises ValueError."""
    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "wrong"), cells=())
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
        best_adapter="a",
        worst_adapter="b",
    )
    with pytest.raises(ValueError, match="heatmap.models"):
        DiscoverabilityComparisonResult(
            adapters=("a", "b"),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_pairwise_delta_rejects_identical_adapters() -> None:
    """adapter_a == adapter_b raises ValueError."""
    with pytest.raises(ValueError, match="distinct adapters"):
        PairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="a",
            pass_rate_delta=0.0,
            mann_whitney_result=_make_mwu(),
            significant_at_alpha_05=False,
        )


def test_pairwise_delta_rejects_out_of_range_delta() -> None:
    """pass_rate_delta outside [-1, 1] raises ValueError."""
    with pytest.raises(ValueError, match="pass_rate_delta"):
        PairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="b",
            pass_rate_delta=1.5,
            mann_whitney_result=_make_mwu(),
            significant_at_alpha_05=False,
        )


def test_pairwise_delta_rejects_significance_inconsistency() -> None:
    """significant_at_alpha_05 vs p_value inconsistency raises ValueError."""
    with pytest.raises(ValueError, match="significant_at_alpha_05"):
        PairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="b",
            pass_rate_delta=0.0,
            mann_whitney_result=_make_mwu(p_value=0.5),  # > 0.05
            significant_at_alpha_05=True,  # but claims significant
        )


def test_comparison_summary_rejects_unknown_best_adapter() -> None:
    """best_adapter not in pass_rate_per_adapter raises ValueError."""
    with pytest.raises(ValueError, match="best_adapter"):
        DiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            pass_rate_per_adapter={"a": 0.5},
            best_adapter="unknown",
            worst_adapter="a",
        )


def test_comparison_summary_rejects_unknown_worst_adapter() -> None:
    """worst_adapter not in pass_rate_per_adapter raises ValueError (Sonnet LOW-1 symmetry)."""
    with pytest.raises(ValueError, match="worst_adapter"):
        DiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            pass_rate_per_adapter={"a": 0.5},
            best_adapter="a",
            worst_adapter="unknown",
        )


def test_compare_keyword_docstring_anchors() -> None:
    """Per Story 13.3 L-5 lesson: keyword docstring contains required anchors.

    Browser-Library-convention test asserting "Mann-Whitney U" + "Story 13.1"
    + "FR10b" + "Phase-2" phrases are present + grep-discoverable.
    Sonnet LOW-2 fix 2026-06-01: spec mentioned the test but it was not
    implemented in the initial test set.
    """
    doc = MCPLibrary.get_tool_discoverability_comparison.__doc__ or ""
    assert "Mann-Whitney U" in doc
    assert "Story 13.1" in doc
    assert "FR10b" in doc
    assert "Phase-2" in doc


def test_comparison_summary_rejects_inconsistent_best_adapter_rate() -> None:
    """best_adapter must actually have the maximum pass rate (Codex HIGH-2 fix)."""
    with pytest.raises(ValueError, match="best_adapter"):
        DiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            pass_rate_per_adapter={"a": 1.0, "b": 0.0},
            best_adapter="b",  # b has 0.0 but a has 1.0
            worst_adapter="a",
        )


def test_comparison_summary_rejects_inconsistent_worst_adapter_rate() -> None:
    """worst_adapter must actually have the minimum pass rate (Codex HIGH-2 fix)."""
    with pytest.raises(ValueError, match="worst_adapter"):
        DiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            pass_rate_per_adapter={"a": 1.0, "b": 0.0},
            best_adapter="a",
            worst_adapter="a",  # a has 1.0 but b has 0.0
        )


def test_comparison_result_rejects_summary_adapter_mismatch() -> None:
    """summary.pass_rate_per_adapter keys must equal adapters (Codex HIGH-3 + Opus MED-1 fix)."""
    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
    # Summary claims about adapters NOT in the comparison.
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter={"x": 1.0, "y": 0.5},
        best_adapter="x",
        worst_adapter="y",
    )
    with pytest.raises(ValueError, match="summary.pass_rate_per_adapter"):
        DiscoverabilityComparisonResult(
            adapters=("a", "b"),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


# --------------------------------------------------------------------------- #
# CohortHeatmap.from_comparison (4 tests)                                     #
# --------------------------------------------------------------------------- #


def _make_minimal_comparison(adapters: list[str]) -> DiscoverabilityComparisonResult:
    """Build a minimal valid comparison for testing the heatmap classmethod."""
    per = {a: _make_discoverability_result(0.5, n_tasks=2) for a in adapters}
    cells = tuple((t.task_id, a, t.pass_rate) for a in adapters for t in per[a].per_task_results)
    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=tuple(adapters), cells=cells)
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter=dict.fromkeys(adapters, 0.5),
        best_adapter=adapters[0],
        worst_adapter=adapters[0],
    )
    return DiscoverabilityComparisonResult(
        adapters=tuple(adapters),
        per_adapter_results=per,
        cross_adapter_deltas={},
        heatmap=heatmap,
        summary=summary,
    )


def test_heatmap_from_comparison_2_adapters() -> None:
    """2-adapter comparison → 2-column heatmap."""
    result = _make_minimal_comparison(["a", "b"])
    h = CohortHeatmap.from_comparison(result)
    assert h.models == ("a", "b")
    assert h.tasks == ("t0", "t1")


def test_heatmap_from_comparison_3_adapters() -> None:
    """3-adapter comparison → 3-column heatmap."""
    result = _make_minimal_comparison(["a", "b", "c"])
    h = CohortHeatmap.from_comparison(result)
    assert h.models == ("a", "b", "c")
    assert len(h.tasks) == 2


def test_heatmap_from_comparison_per_task_pass_rate_in_cells() -> None:
    """Per-task pass rate dispatched to correct cell."""
    per = {
        "fast": _make_discoverability_result(1.0, n_tasks=2),
        "slow": _make_discoverability_result(0.0, n_tasks=2),
    }
    cells = tuple((t.task_id, a, t.pass_rate) for a in ("fast", "slow") for t in per[a].per_task_results)
    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=("fast", "slow"), cells=cells)
    summary = DiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        pass_rate_per_adapter={"fast": 1.0, "slow": 0.0},
        best_adapter="fast",
        worst_adapter="slow",
    )
    result = DiscoverabilityComparisonResult(
        adapters=("fast", "slow"),
        per_adapter_results=per,
        cross_adapter_deltas={},
        heatmap=heatmap,
        summary=summary,
    )
    h = CohortHeatmap.from_comparison(result)
    data = h.as_dict()
    assert data["t0"]["fast"] == 1.0
    assert data["t0"]["slow"] == 0.0


def test_heatmap_from_comparison_as_ascii_3_columns() -> None:
    """as_ascii() produces ≥3 columns when 3 adapters provided."""
    result = _make_minimal_comparison(["a", "b", "c"])
    h = CohortHeatmap.from_comparison(result)
    ascii_table = h.as_ascii()
    # Header row has 4 segments: Task + 3 adapter names.
    assert "a" in ascii_table
    assert "b" in ascii_table
    assert "c" in ascii_table
    assert "Task" in ascii_table


# --------------------------------------------------------------------------- #
# Pairwise delta computation via end-to-end keyword (3 tests)                 #
# --------------------------------------------------------------------------- #


def test_compare_2_adapters_produces_1_pairwise_delta(lib: MCPLibrary, fixture_path: Path) -> None:
    """2 adapters → 1 pairwise delta keyed `a_vs_b`."""
    register_adapter("c2_pass", _make_stub_adapter([["echo_back"]] * 30))
    register_adapter("c2_fail", _make_stub_adapter([[]] * 30))
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["c2_pass", "c2_fail"],
        tasks=str(fixture_path),
        trials_per_task=5,
    )
    assert len(result.cross_adapter_deltas) == 1
    assert "c2_pass_vs_c2_fail" in result.cross_adapter_deltas


def test_compare_3_adapters_produces_3_pairwise_deltas(lib: MCPLibrary, fixture_path: Path) -> None:
    """3 adapters → 3 pairwise deltas (C(3,2))."""
    register_adapter("c3_a", _make_stub_adapter([["echo_back"]] * 30))
    # Alternating pass/fail per call so per-task variance ≠ 0.
    register_adapter(
        "c3_b",
        _make_stub_adapter([(["echo_back"] if i % 2 == 0 else []) for i in range(30)]),
    )
    register_adapter("c3_c", _make_stub_adapter([[]] * 30))
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["c3_a", "c3_b", "c3_c"],
        tasks=str(fixture_path),
        trials_per_task=5,
    )
    assert len(result.cross_adapter_deltas) == 3
    assert set(result.cross_adapter_deltas.keys()) == {
        "c3_a_vs_c3_b",
        "c3_a_vs_c3_c",
        "c3_b_vs_c3_c",
    }


def test_compare_pairwise_keys_preserve_input_order(lib: MCPLibrary, fixture_path: Path) -> None:
    """Pairwise delta keys preserve input adapter order (a comes before b)."""
    register_adapter("zzz_first", _make_stub_adapter([[]] * 30))
    register_adapter("aaa_second", _make_stub_adapter([[]] * 30))
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["zzz_first", "aaa_second"],
        tasks=str(fixture_path),
        trials_per_task=5,
    )
    # 'zzz_first' was passed first → it's adapter_a; 'aaa_second' is adapter_b.
    assert "zzz_first_vs_aaa_second" in result.cross_adapter_deltas


# --------------------------------------------------------------------------- #
# Mann-Whitney U dispatch + significance ranking (2 tests)                    #
# --------------------------------------------------------------------------- #


def test_compare_clearly_different_distributions_significant(lib: MCPLibrary, fixture_path: Path) -> None:
    """2 adapters with KNOWN-different pass rates → Mann-Whitney p < 0.05.

    Stub 'always-pass' (100%) vs 'always-fail' (0%) across 5 tasks × 5 trials
    yields max-effect Mann-Whitney U. p_value should be small enough to
    reject the null at α=0.05.
    """
    register_adapter("mwu_pass", _make_stub_adapter([["echo_back"]] * 30))
    register_adapter("mwu_fail", _make_stub_adapter([[]] * 30))
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["mwu_pass", "mwu_fail"],
        tasks=str(fixture_path),
        trials_per_task=5,
    )
    delta = result.cross_adapter_deltas["mwu_pass_vs_mwu_fail"]
    # mwu_pass mean pass_rate = 1.0; mwu_fail = 0.0; delta = 1.0.
    assert delta.pass_rate_delta == pytest.approx(1.0)
    # Mann-Whitney U on identical-ranks-per-group should reject the null.
    assert delta.significant_at_alpha_05


def test_compare_identical_distributions_not_significant(lib: MCPLibrary, fixture_path: Path) -> None:
    """2 adapters with IDENTICAL pass-rate distributions → Mann-Whitney p > 0.05."""
    register_adapter("mwu_id_a", _make_stub_adapter([["echo_back"]] * 30))
    register_adapter("mwu_id_b", _make_stub_adapter([["echo_back"]] * 30))
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["mwu_id_a", "mwu_id_b"],
        tasks=str(fixture_path),
        trials_per_task=5,
    )
    delta = result.cross_adapter_deltas["mwu_id_a_vs_mwu_id_b"]
    assert delta.pass_rate_delta == pytest.approx(0.0)
    assert not delta.significant_at_alpha_05
