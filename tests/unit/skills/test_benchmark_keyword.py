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

"""Keyword-surface + heatmap + budget tests (add-skill-ab-benchmark / Tasks 4.1 + 4.3).

Covers: validation matrix (polling, trials=0, missing skill/tasks, bad
alpha/threshold), extras-gate fail-fast with zero adapter constructions,
budget-cap trip parity with `Skill.Compare Discoverability`, baseline=none vs
baseline=path modes, and `CohortHeatmap.from_skill_benchmark` rendering.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from AgentEval._kernel import discovery
from AgentEval._kernel.discovery import register_adapter
from AgentEval.errors import PollingDisallowedError
from AgentEval.skills.library import SkillsLibrary

_SKILL = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
_TASKS_EC = Path(__file__).parent.parent.parent / "fixtures" / "benchmark" / "tasks-expected-content.yaml"
_SKILL_V1 = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-valid.md"


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


# --------------------------------------------------------------------------- #
# Validation matrix — all BEFORE any adapter fan-out                          #
# --------------------------------------------------------------------------- #


def test_polling_rejected(lib: SkillsLibrary) -> None:
    with pytest.raises(PollingDisallowedError):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), polling=2.0)


def test_missing_skill_rejected(lib: SkillsLibrary) -> None:
    with pytest.raises(ValueError, match="skill"):
        lib.compare_against_baseline(skill="", tasks=str(_TASKS_EC))


def test_missing_tasks_rejected(lib: SkillsLibrary) -> None:
    with pytest.raises(ValueError, match="tasks"):
        lib.compare_against_baseline(skill=str(_SKILL), tasks="")


def test_trials_zero_rejected(lib: SkillsLibrary) -> None:
    with pytest.raises(ValueError, match="trials must be >= 1"):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), trials=0)


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
def test_bad_alpha_rejected(lib: SkillsLibrary, alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), alpha=alpha)


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_bad_obsolescence_threshold_rejected(lib: SkillsLibrary, threshold: float) -> None:
    with pytest.raises(ValueError, match="obsolescence_threshold"):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), obsolescence_threshold=threshold)


def test_polling_rejected_before_any_adapter_construction(lib: SkillsLibrary) -> None:
    """No adapter is built when polling is provided."""
    constructed: list[str] = []

    from AgentEval.coding_agent.base import InProcessAdapter
    from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

    class _Tracker(InProcessAdapter):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            constructed.append("built")

        def run(self, prompt: str, **kwargs: object) -> AgentRunResult:
            return AgentRunResult(
                response_text="x",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.0,
                trace_id="a" * 32,
            )

    register_adapter("kw_tracker", _Tracker)
    with pytest.raises(PollingDisallowedError):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), adapter="kw_tracker", polling=1.0)
    assert constructed == []


# --------------------------------------------------------------------------- #
# Extras gate                                                                  #
# --------------------------------------------------------------------------- #


def test_extras_gate_import_error_before_fanout(lib: SkillsLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), trials=1)


def test_extras_gate_message_contract(lib: SkillsLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    with pytest.raises(ImportError) as exc:
        lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), trials=1)
    msg = str(exc.value)
    assert "Skill.Compare Against Baseline" in msg
    assert "scipy + numpy required" in msg
    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg


def test_arg_validation_runs_before_extras_gate(lib: SkillsLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    # Missing skill should surface the arg error first (more actionable).
    with pytest.raises(ValueError, match="skill"):
        lib.compare_against_baseline(skill="", tasks=str(_TASKS_EC), trials=1)


# --------------------------------------------------------------------------- #
# End-to-end keyword + heatmap                                                #
# --------------------------------------------------------------------------- #


def _register_helpful(name: str) -> None:
    from ._benchmark_helpers import make_conditional_stub

    register_adapter(
        name,
        make_conditional_stub(
            with_skill_text="root cause runbook table order id",
            without_skill_text="i cannot help",
        ),
    )


def test_baseline_none_end_to_end(lib: SkillsLibrary) -> None:
    pytest.importorskip("scipy")
    _register_helpful("kw_none")
    result = lib.compare_against_baseline(
        skill=str(_SKILL), tasks=str(_TASKS_EC), baseline="none", adapter="kw_none", trials=4
    )
    assert result.verdict == "skill_improves"
    assert result.skill_delivery == "prompt_injected"
    assert result.baseline.skill_path is None
    assert result.total_runtime_seconds >= 0.0


def test_baseline_path_end_to_end(lib: SkillsLibrary) -> None:
    pytest.importorskip("scipy")
    from ._benchmark_helpers import make_constant_stub

    register_adapter("kw_path", make_constant_stub("root cause runbook table order id"))
    result = lib.compare_against_baseline(
        skill=str(_SKILL), tasks=str(_TASKS_EC), baseline=str(_SKILL_V1), adapter="kw_path", trials=3
    )
    # v1-vs-v2: both arms deliver a skill; baseline.skill_path is the path.
    assert result.baseline.skill_path == str(_SKILL_V1)
    assert result.verdict != "skill_unnecessary"


def test_heatmap_two_columns(lib: SkillsLibrary) -> None:
    pytest.importorskip("scipy")
    _register_helpful("kw_hm")
    result = lib.compare_against_baseline(skill=str(_SKILL), tasks=str(_TASKS_EC), adapter="kw_hm", trials=2)
    data = result.heatmap.as_dict()
    assert len(data) == 4  # 4 tasks
    for _task, cols in data.items():
        assert set(cols.keys()) == {"candidate", "baseline"}
    # ASCII render works.
    ascii_render = result.heatmap.as_ascii()
    assert "candidate" in ascii_render
    assert "baseline" in ascii_render


# --------------------------------------------------------------------------- #
# Budget-cap trip parity (empirical @guarded_fanout probe)                    #
# --------------------------------------------------------------------------- #


def test_budget_cap_trips_cost_exceeded(lib: SkillsLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer-2 cost meter > budget → CostExceededError (parity with Compare Discoverability)."""
    pytest.importorskip("scipy")
    from AgentEval._kernel import guardrails
    from AgentEval.errors import CostExceededError

    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 1.0)
    _register_helpful("kw_budget")
    with pytest.raises(CostExceededError):
        lib.compare_against_baseline(
            skill=str(_SKILL),
            tasks=str(_TASKS_EC),
            adapter="kw_budget",
            trials=2,
            __agenteval_test_budget__=(0.001, None),
        )


def test_max_cost_usd_kwarg_enforced_via_explicit_accounting(lib: SkillsLibrary) -> None:
    """codex HIGH regression: the per-call `max_cost_usd=` actually caps real spend.

    The `@guarded_fanout` cost meter reads a Phase-1 0.0 stub, so a per-call
    `max_cost_usd=1.0` used to be invisible and a $5/run adapter overspent
    silently. Explicit cumulative accounting now raises `CostExceededError` at
    the first breach — no guardrail monkeypatch needed.
    """
    pytest.importorskip("scipy")
    from AgentEval.errors import CostExceededError

    from ._benchmark_helpers import make_constant_stub

    # $5.00 per adapter run — the very first candidate run breaches a $1.00 cap.
    register_adapter("kw_costly", make_constant_stub("root cause runbook table order id", cost=5.0))
    with pytest.raises(CostExceededError, match="max_cost_usd budget"):
        lib.compare_against_baseline(
            skill=str(_SKILL),
            tasks=str(_TASKS_EC),
            adapter="kw_costly",
            trials=1,
            max_cost_usd=1.0,
        )


def test_no_budget_none_does_not_enforce(lib: SkillsLibrary) -> None:
    """A no-budget run (`max_cost_usd=None`, host attr None) must NOT enforce a cap."""
    pytest.importorskip("scipy")
    from ._benchmark_helpers import make_constant_stub

    register_adapter("kw_nobudget", make_constant_stub("root cause runbook table order id", cost=5.0))
    # SkillsLibrary() defaults `_max_cost_usd` to None, and we clear the per-call
    # value too → the no-budget fast path runs to completion despite $5/run spend.
    result = lib.compare_against_baseline(
        skill=str(_SKILL),
        tasks=str(_TASKS_EC),
        adapter="kw_nobudget",
        trials=1,
        max_cost_usd=None,
    )
    assert result.total_cost_usd > 1.0
