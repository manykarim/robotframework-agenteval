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

"""Unit tests for `Skill.Compare Discoverability` cross-adapter surface (Story 13.5 / PRD FR4c).

Coverage:
- 3 new frozen dataclass validators (SkillDiscoverabilityComparisonResult +
  SkillPairwiseAdapterDelta + SkillDiscoverabilityComparisonSummary).
- `CohortHeatmap.from_skill_comparison` multi-column heatmap.
- Pairwise delta counting (N=2 + N=3).
- Mann-Whitney U dispatch + significance.
- False-activation + missed-activation deltas (Skill-domain extension
  beyond Story 13.3 D-1).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# Phase-2 deps required for math.
pytest.importorskip("scipy")
pytest.importorskip("numpy")

from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
from AgentEval._kernel import discovery  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
from AgentEval.skills.library import SkillsLibrary  # noqa: E402
from AgentEval.skills.types import (  # noqa: E402
    SkillDiscoverabilityComparisonResult,
    SkillDiscoverabilityComparisonSummary,
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillPairwiseAdapterDelta,
    SkillTaskResult,
)
from AgentEval.stats.types import MannWhitneyResult  # noqa: E402
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    """Snapshot + restore the programmatic adapter registry per test."""
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


# --------------------------------------------------------------------------- #
# Helper builders                                                             #
# --------------------------------------------------------------------------- #


def _make_mwu(p_value: float = 0.5) -> MannWhitneyResult:
    return MannWhitneyResult(u_statistic=10.0, p_value=p_value, effect_size_r=0.0, n_a=5, n_b=5)


def _make_skill_result(
    activation_accuracy: float = 0.5,
    false_activation_rate: float = 0.0,
    missed_activation_rate: float = 0.0,
    n_tasks: int = 3,
) -> SkillDiscoverabilityResult:
    per_task = tuple(
        SkillTaskResult(
            task_id=f"t{i}",
            task_prompt=f"prompt {i}",
            should_activate=True,
            trials_run=10,
            activations_observed=int(activation_accuracy * 10),
            pass_at_k=activation_accuracy,
            competing_skills_picked={},
            cost_per_trial_usd=0.0,
        )
        for i in range(n_tasks)
    )
    return SkillDiscoverabilityResult(
        per_task_results=per_task,
        summary=SkillDiscoverabilityTaskSummary(
            activation_accuracy=activation_accuracy,
            false_activation_rate=false_activation_rate,
            missed_activation_rate=missed_activation_rate,
            total_cost_usd=0.0,
            total_runtime_seconds=0.1,
        ),
        adapter_coverage="in_process",
    )


def _make_stub(response_text: str, cost: float = 0.0) -> type[InProcessAdapter]:
    """Stub adapter; default `cost=0.0` per Story 13.3 Codex MED-1 lesson."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=0.001,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def skill_fixture_path() -> Path:
    return Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"


@pytest.fixture
def tasks_fixture_path() -> Path:
    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"


# --------------------------------------------------------------------------- #
# Dataclass validators (8 tests)                                              #
# --------------------------------------------------------------------------- #


def test_comparison_result_rejects_single_adapter() -> None:
    per = {"a": _make_skill_result(1.0)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a",), cells=(("t0", "a", 1.0),))
    summary = SkillDiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        activation_accuracy_per_adapter={"a": 1.0},
        best_adapter="a",
        worst_adapter="a",
    )
    with pytest.raises(ValueError, match="len\\(adapters\\) >= 2"):
        SkillDiscoverabilityComparisonResult(
            adapters=("a",),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_comparison_result_rejects_adapters_keys_mismatch() -> None:
    per = {"a": _make_skill_result(1.0), "b": _make_skill_result(0.5)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
    summary = SkillDiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        activation_accuracy_per_adapter={"a": 1.0, "b": 0.5},
        best_adapter="a",
        worst_adapter="b",
    )
    with pytest.raises(ValueError, match="per_adapter_results keys"):
        SkillDiscoverabilityComparisonResult(
            adapters=("a", "c"),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_comparison_result_rejects_summary_keys_mismatch() -> None:
    """summary.activation_accuracy_per_adapter must equal adapters (Story 13.4 HIGH-C)."""
    per = {"a": _make_skill_result(1.0), "b": _make_skill_result(0.5)}
    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
    summary = SkillDiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        activation_accuracy_per_adapter={"x": 1.0, "y": 0.5},
        best_adapter="x",
        worst_adapter="y",
    )
    with pytest.raises(ValueError, match="activation_accuracy_per_adapter"):
        SkillDiscoverabilityComparisonResult(
            adapters=("a", "b"),
            per_adapter_results=per,
            cross_adapter_deltas={},
            heatmap=heatmap,
            summary=summary,
        )


def test_pairwise_delta_rejects_identical_adapters() -> None:
    with pytest.raises(ValueError, match="distinct adapters"):
        SkillPairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="a",
            pass_at_k_delta=0.0,
            pass_at_k_mann_whitney_result=_make_mwu(),
            false_activation_rate_delta=0.0,
            missed_activation_rate_delta=0.0,
            significant_at_alpha_05=False,
        )


def test_pairwise_delta_rejects_out_of_range_deltas() -> None:
    with pytest.raises(ValueError, match="pass_at_k_delta"):
        SkillPairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="b",
            pass_at_k_delta=1.5,
            pass_at_k_mann_whitney_result=_make_mwu(),
            false_activation_rate_delta=0.0,
            missed_activation_rate_delta=0.0,
            significant_at_alpha_05=False,
        )
    with pytest.raises(ValueError, match="false_activation_rate_delta"):
        SkillPairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="b",
            pass_at_k_delta=0.0,
            pass_at_k_mann_whitney_result=_make_mwu(),
            false_activation_rate_delta=-1.5,
            missed_activation_rate_delta=0.0,
            significant_at_alpha_05=False,
        )


def test_pairwise_delta_significance_consistency_check() -> None:
    with pytest.raises(ValueError, match="significant_at_alpha_05"):
        SkillPairwiseAdapterDelta(
            adapter_a="a",
            adapter_b="b",
            pass_at_k_delta=0.0,
            pass_at_k_mann_whitney_result=_make_mwu(p_value=0.5),
            false_activation_rate_delta=0.0,
            missed_activation_rate_delta=0.0,
            significant_at_alpha_05=True,  # but p > 0.05
        )


def test_summary_rejects_inconsistent_best_worst() -> None:
    """best/worst must match argmax/argmin of activation_accuracy_per_adapter (Story 13.4 HIGH-B)."""
    with pytest.raises(ValueError, match="best_adapter"):
        SkillDiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            activation_accuracy_per_adapter={"a": 1.0, "b": 0.0},
            best_adapter="b",  # b has 0.0 but a has 1.0
            worst_adapter="a",
        )


def test_summary_rejects_unknown_best_adapter() -> None:
    with pytest.raises(ValueError, match="best_adapter"):
        SkillDiscoverabilityComparisonSummary(
            total_cost_usd=0.0,
            total_runtime_seconds=0.0,
            activation_accuracy_per_adapter={"a": 0.5},
            best_adapter="unknown",
            worst_adapter="a",
        )


# --------------------------------------------------------------------------- #
# CohortHeatmap.from_skill_comparison (3 tests)                               #
# --------------------------------------------------------------------------- #


def _make_minimal_comparison(adapters: list[str]) -> SkillDiscoverabilityComparisonResult:
    per = {a: _make_skill_result(0.5, n_tasks=2) for a in adapters}
    cells = tuple((t.task_id, a, t.pass_at_k) for a in adapters for t in per[a].per_task_results)
    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=tuple(adapters), cells=cells)
    summary = SkillDiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        activation_accuracy_per_adapter=dict.fromkeys(adapters, 0.5),
        best_adapter=adapters[0],
        worst_adapter=adapters[0],
    )
    return SkillDiscoverabilityComparisonResult(
        adapters=tuple(adapters),
        per_adapter_results=per,
        cross_adapter_deltas={},
        heatmap=heatmap,
        summary=summary,
    )


def test_heatmap_from_skill_comparison_2_adapters() -> None:
    result = _make_minimal_comparison(["a", "b"])
    h = CohortHeatmap.from_skill_comparison(result)
    assert h.models == ("a", "b")
    assert h.tasks == ("t0", "t1")


def test_heatmap_from_skill_comparison_3_adapters() -> None:
    result = _make_minimal_comparison(["a", "b", "c"])
    h = CohortHeatmap.from_skill_comparison(result)
    assert h.models == ("a", "b", "c")
    assert len(h.tasks) == 2


def test_heatmap_from_skill_comparison_pass_at_k_dispatched() -> None:
    """Per-task pass_at_k dispatched to correct cell."""
    per = {
        "fast": _make_skill_result(1.0, n_tasks=2),
        "slow": _make_skill_result(0.0, n_tasks=2),
    }
    cells = tuple((t.task_id, a, t.pass_at_k) for a in ("fast", "slow") for t in per[a].per_task_results)
    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=("fast", "slow"), cells=cells)
    summary = SkillDiscoverabilityComparisonSummary(
        total_cost_usd=0.0,
        total_runtime_seconds=0.0,
        activation_accuracy_per_adapter={"fast": 1.0, "slow": 0.0},
        best_adapter="fast",
        worst_adapter="slow",
    )
    result = SkillDiscoverabilityComparisonResult(
        adapters=("fast", "slow"),
        per_adapter_results=per,
        cross_adapter_deltas={},
        heatmap=heatmap,
        summary=summary,
    )
    h = CohortHeatmap.from_skill_comparison(result)
    data = h.as_dict()
    assert data["t0"]["fast"] == 1.0
    assert data["t0"]["slow"] == 0.0


# --------------------------------------------------------------------------- #
# Pairwise delta computation via end-to-end keyword (3 tests)                 #
# --------------------------------------------------------------------------- #


def test_compare_2_adapters_produces_1_pairwise_delta(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    """2 adapters → 1 pairwise delta."""
    register_adapter("s2_act", _make_stub("example-search-skill response"))
    register_adapter("s2_no", _make_stub("nothing happens here"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["s2_act", "s2_no"],
        trials_per_task=3,
    )
    assert len(result.cross_adapter_deltas) == 1
    assert "s2_act_vs_s2_no" in result.cross_adapter_deltas


def test_compare_3_adapters_produces_3_pairwise_deltas(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    """3 adapters → 3 pairwise deltas (C(3,2))."""
    register_adapter("s3_a", _make_stub("example-search-skill: yes"))
    register_adapter("s3_b", _make_stub("nothing"))
    register_adapter("s3_c", _make_stub("example-search-skill: maybe"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["s3_a", "s3_b", "s3_c"],
        trials_per_task=3,
    )
    assert len(result.cross_adapter_deltas) == 3
    assert set(result.cross_adapter_deltas.keys()) == {
        "s3_a_vs_s3_b",
        "s3_a_vs_s3_c",
        "s3_b_vs_s3_c",
    }


def test_compare_pairwise_keys_preserve_input_order(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    register_adapter("zzz_first", _make_stub("nothing"))
    register_adapter("aaa_second", _make_stub("nothing"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["zzz_first", "aaa_second"],
        trials_per_task=3,
    )
    assert "zzz_first_vs_aaa_second" in result.cross_adapter_deltas


# --------------------------------------------------------------------------- #
# False-activation + missed-activation deltas (2 tests)                       #
# --------------------------------------------------------------------------- #


def test_compare_missed_activation_rate_delta(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    """Stub that NEVER activates → high missed_activation_rate.

    Stub-a always activates (skill name present in response); stub-b
    never does. missed_activation_rate_delta (b - a) > 0 → b is WORSE.
    """
    register_adapter("miss_a", _make_stub("example-search-skill is here"))
    register_adapter("miss_b", _make_stub("totally unrelated"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["miss_a", "miss_b"],
        trials_per_task=3,
    )
    delta = result.cross_adapter_deltas["miss_a_vs_miss_b"]
    # a misses 0; b misses all should-activate trials → b - a > 0 wait,
    # delta is `a - b`, so a's rate minus b's rate → negative.
    a_summary = result.per_adapter_results["miss_a"].summary
    b_summary = result.per_adapter_results["miss_b"].summary
    assert b_summary.missed_activation_rate > a_summary.missed_activation_rate
    # delta = a - b → since a < b, delta is NEGATIVE.
    assert delta.missed_activation_rate_delta < 0


def test_compare_false_activation_rate_delta(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    """Stub that ALWAYS activates including on decoys → high false_activation_rate.

    Stub-a always activates (high false_activation on decoy tasks);
    stub-b never activates. false_activation_rate_delta (a - b) > 0 →
    a is WORSE on decoys.
    """
    register_adapter("false_a", _make_stub("example-search-skill always shouts"))
    register_adapter("false_b", _make_stub("nothing here"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["false_a", "false_b"],
        trials_per_task=3,
    )
    delta = result.cross_adapter_deltas["false_a_vs_false_b"]
    a_summary = result.per_adapter_results["false_a"].summary
    b_summary = result.per_adapter_results["false_b"].summary
    assert a_summary.false_activation_rate > b_summary.false_activation_rate
    assert delta.false_activation_rate_delta > 0


# --------------------------------------------------------------------------- #
# Mann-Whitney significance (1 test — already covered in MCP variant; light here) #
# --------------------------------------------------------------------------- #


def test_compare_identical_distributions_not_significant(
    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
) -> None:
    """Identical pass-rate distributions → not significant (nan handling)."""
    register_adapter("id_a", _make_stub("example-search-skill identical"))
    register_adapter("id_b", _make_stub("example-search-skill identical"))
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture_path),
        tasks=str(tasks_fixture_path),
        adapters=["id_a", "id_b"],
        trials_per_task=3,
    )
    delta = result.cross_adapter_deltas["id_a_vs_id_b"]
    assert delta.pass_at_k_delta == pytest.approx(0.0)
    assert not delta.significant_at_alpha_05
