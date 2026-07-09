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

"""Statistics + verdict + evidence-assembly tests (add-skill-ab-benchmark / Task 3.4).

Covers: the verdict truth table (all four verdicts + improvement-beats-
obsolescence + never-obsolete-in-v1v2), bootstrap reproducibility at fixed
seed, evidence count = 2 x N x trials, `asdict()` round-trip, and the frozen
dataclass closed-set validators.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("scipy")
pytest.importorskip("numpy")

from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
from AgentEval._kernel import discovery  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.skills._benchmark import (  # noqa: E402
    compute_benchmark_verdict,
    load_skill_benchmark_tasks,
    run_skill_benchmark,
)
from AgentEval.skills.types import (  # noqa: E402
    SkillBenchmarkArmSummary,
    SkillBenchmarkComparisonResult,
    SkillBenchmarkTrialEvidence,
)
from AgentEval.stats.types import MannWhitneyResult  # noqa: E402

from ._benchmark_helpers import make_conditional_stub, make_constant_stub  # noqa: E402

_SKILL = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
_TASKS_EC = Path(__file__).parent.parent.parent / "fixtures" / "benchmark" / "tasks-expected-content.yaml"
# A skill used only for the v1-vs-v2 baseline path (any valid skill file works).
_SKILL_V1 = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-valid.md"


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


def _run(adapter: str, *, baseline: str = "none", trials: int = 3, obsolescence_threshold: float = 0.9):
    tasks = load_skill_benchmark_tasks(_TASKS_EC)
    return run_skill_benchmark(
        skill=str(_SKILL),
        tasks=tasks,
        baseline=baseline,
        trials=trials,
        adapter=adapter,
        model=None,
        seed=42,
        alpha=0.05,
        obsolescence_threshold=obsolescence_threshold,
        judge_adapter="generic",
        judge_model=None,
        extra_adapter_kwargs={},
        t_start=0.0,
    )


# --------------------------------------------------------------------------- #
# Verdict truth table (pure function)                                         #
# --------------------------------------------------------------------------- #


def test_verdict_skill_improves() -> None:
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.9,
        baseline_pass_rate=0.1,
        p_value=0.01,
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=0.8,  # candidate distributionally higher
    )
    assert v == "skill_improves"


def test_verdict_skill_regresses() -> None:
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.1,
        baseline_pass_rate=0.9,
        p_value=0.01,
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=-0.8,  # candidate distributionally lower
    )
    assert v == "skill_regresses"


def test_verdict_skill_unnecessary_baseline_high_no_gain() -> None:
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.95,
        baseline_pass_rate=0.95,
        p_value=1.0,  # not significant
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=0.0,
    )
    assert v == "skill_unnecessary"


def test_verdict_no_significant_difference() -> None:
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.5,
        baseline_pass_rate=0.5,
        p_value=float("nan"),
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=0.0,
    )
    assert v == "no_significant_difference"


def test_verdict_improvement_beats_obsolescence() -> None:
    """Baseline exceeds threshold BUT candidate significantly better → skill_improves."""
    v = compute_benchmark_verdict(
        candidate_pass_rate=1.0,
        baseline_pass_rate=0.92,
        p_value=0.01,
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=0.5,  # candidate distributionally higher
    )
    assert v == "skill_improves"


def test_verdict_direction_uses_signed_effect_not_aggregate_mean() -> None:
    """codex HIGH regression: aggregate mean and significance test can disagree.

    A few large candidate wins raise the AGGREGATE pass rate above baseline while
    the candidate is significantly WORSE on most tasks (Cliff's delta < 0). The
    verdict must follow the SIGNED effect of the significance test, NOT the
    aggregate mean — so it must be `skill_regresses`, never `skill_improves`.
    Exact distributions from the codex finding.
    """
    from AgentEval.stats.cliffs_delta import compute_cliff_delta
    from AgentEval.stats.mannwhitney import compute_mann_whitney_u

    candidate = [1.0] * 10 + [0.49] * 90
    baseline = [0.5] * 90 + [0.0] * 10
    candidate_mean = sum(candidate) / len(candidate)
    baseline_mean = sum(baseline) / len(baseline)
    # Aggregate mean FAVORS candidate ...
    assert candidate_mean > baseline_mean

    mwu = compute_mann_whitney_u(candidate, baseline)
    delta = compute_cliff_delta(candidate, baseline)
    # ... but the distribution is significantly WORSE for candidate.
    assert mwu.p_value < 0.05
    assert delta < 0.0

    v = compute_benchmark_verdict(
        candidate_pass_rate=candidate_mean,
        baseline_pass_rate=baseline_mean,
        p_value=mwu.p_value,
        alpha=0.05,
        baseline_is_none=True,
        obsolescence_threshold=0.9,
        cliffs_delta=delta,
    )
    assert v != "skill_improves"
    assert v == "skill_regresses"


def test_verdict_never_obsolete_in_v1v2_mode() -> None:
    """v1-vs-v2 mode never emits skill_unnecessary even with high baseline."""
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.95,
        baseline_pass_rate=0.95,
        p_value=1.0,
        alpha=0.05,
        baseline_is_none=False,  # v1-vs-v2
        obsolescence_threshold=0.9,
        cliffs_delta=0.0,
    )
    assert v == "no_significant_difference"


# --------------------------------------------------------------------------- #
# End-to-end verdict via the engine                                           #
# --------------------------------------------------------------------------- #


def test_end_to_end_skill_improves() -> None:
    register_adapter(
        "sv_improve",
        make_conditional_stub(
            with_skill_text="root cause runbook table order id",
            without_skill_text="no idea",
        ),
    )
    result = _run("sv_improve", trials=4)
    assert result.candidate.pass_rate == pytest.approx(1.0)
    assert result.baseline.pass_rate == pytest.approx(0.0)
    assert result.verdict == "skill_improves"
    assert result.pass_rate_delta > 0.0


def test_end_to_end_skill_unnecessary() -> None:
    """Baseline already passes everything → skill_unnecessary."""
    register_adapter("sv_unnec", make_constant_stub("root cause runbook table order id"))
    result = _run("sv_unnec", trials=4)
    assert result.baseline.pass_rate == pytest.approx(1.0)
    assert result.candidate.pass_rate == pytest.approx(1.0)
    assert result.verdict == "skill_unnecessary"


def test_end_to_end_never_obsolete_v1v2() -> None:
    """v1-vs-v2: both arms pass, no significance → no_significant_difference (never unnecessary)."""
    register_adapter("sv_v1v2", make_constant_stub("root cause runbook table order id"))
    result = _run("sv_v1v2", baseline=str(_SKILL_V1), trials=4)
    assert result.verdict != "skill_unnecessary"
    assert result.verdict == "no_significant_difference"
    assert result.baseline.skill_path == str(_SKILL_V1)


# --------------------------------------------------------------------------- #
# Stats reproducibility + evidence count + serialization                      #
# --------------------------------------------------------------------------- #


def test_bootstrap_reproducible_at_fixed_seed() -> None:
    register_adapter("sv_boot", make_conditional_stub(with_skill_text="root cause", without_skill_text="x"))
    r1 = _run("sv_boot", trials=3)
    r2 = _run("sv_boot", trials=3)
    assert r1.bootstrap_ci == r2.bootstrap_ci
    assert r1.bootstrap_ci[0] <= r1.bootstrap_ci[1]


def test_significance_fields_populated() -> None:
    register_adapter("sv_sig", make_conditional_stub(with_skill_text="root cause runbook table order id", without_skill_text="x"))
    result = _run("sv_sig", trials=3)
    assert isinstance(result.mann_whitney, MannWhitneyResult)
    assert -1.0 <= result.cliffs_delta <= 1.0
    lo, hi = result.bootstrap_ci
    assert lo <= hi


def test_evidence_count_equals_2x_n_trials() -> None:
    register_adapter("sv_ev", make_conditional_stub(with_skill_text="root cause", without_skill_text="x"))
    result = _run("sv_ev", trials=2)
    # 4 tasks x 2 trials x 2 arms.
    assert len(result.evidence) == 16
    for e in result.evidence:
        assert isinstance(e, SkillBenchmarkTrialEvidence)
        assert e.arm in ("candidate", "baseline")


def test_result_asdict_round_trip() -> None:
    register_adapter("sv_ser", make_conditional_stub(with_skill_text="root cause", without_skill_text="x"))
    result = _run("sv_ser", trials=2)
    d = dataclasses.asdict(result)
    assert d["skill_delivery"] == "prompt_injected"
    assert d["verdict"] in {"skill_improves", "skill_unnecessary", "skill_regresses", "no_significant_difference"}
    assert len(d["evidence"]) == 16
    assert isinstance(d["candidate"], dict)


def test_arm_summaries_carry_tokens_time_cost() -> None:
    register_adapter(
        "sv_metrics",
        make_conditional_stub(with_skill_text="root cause", without_skill_text="x", cost=0.02),
    )
    result = _run("sv_metrics", trials=3)
    for arm in (result.candidate, result.baseline):
        assert arm.trials_run == 12
        assert arm.total_tokens > 0
        assert arm.mean_tokens > 0
        assert arm.total_elapsed_seconds >= 0.0
        assert arm.total_cost_usd == pytest.approx(0.02 * 12)
    assert result.total_cost_usd == pytest.approx(0.02 * 24)


# --------------------------------------------------------------------------- #
# Frozen dataclass closed-set validators                                      #
# --------------------------------------------------------------------------- #


def _mwu() -> MannWhitneyResult:
    return MannWhitneyResult(u_statistic=1.0, p_value=0.5, effect_size_r=0.0, n_a=3, n_b=3)


def _arm(name: str) -> SkillBenchmarkArmSummary:
    return SkillBenchmarkArmSummary(
        arm=name,
        skill_path=None,
        pass_rate=0.5,
        per_task_pass_rates={"t0": 0.5},
        total_tokens=10,
        mean_tokens=5.0,
        total_elapsed_seconds=0.1,
        total_cost_usd=0.0,
        trials_run=2,
    )


def test_trial_evidence_rejects_bad_arm() -> None:
    with pytest.raises(ValueError, match="arm must be one of"):
        SkillBenchmarkTrialEvidence(
            task_id="t",
            arm="both",
            trial_index=0,
            blinded_grading_id="g-1",
            passed=True,
            grading_mode="judge",
            judge_score=8.0,
            judge_reasoning="r",
            response_excerpt="x",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_seconds=0.0,
        )


def test_trial_evidence_rejects_bad_grading_mode() -> None:
    with pytest.raises(ValueError, match="grading_mode must be one of"):
        SkillBenchmarkTrialEvidence(
            task_id="t",
            arm="candidate",
            trial_index=0,
            blinded_grading_id="g-1",
            passed=True,
            grading_mode="magic",
            judge_score=None,
            judge_reasoning=None,
            response_excerpt="x",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_seconds=0.0,
        )


def test_result_rejects_bad_skill_delivery() -> None:
    heatmap = CohortHeatmap(tasks=("t0",), models=("candidate", "baseline"), cells=())
    with pytest.raises(ValueError, match="skill_delivery must be one of"):
        SkillBenchmarkComparisonResult(
            candidate=_arm("candidate"),
            baseline=_arm("baseline"),
            pass_rate_delta=0.0,
            mann_whitney=_mwu(),
            cliffs_delta=0.0,
            bootstrap_ci=(0.0, 0.0),
            verdict="no_significant_difference",
            skill_delivery="magic",
            blinding={"mode": "arm_label_blind", "seed": 42},
            evidence=(),
            heatmap=heatmap,
            total_runtime_seconds=0.0,
            total_cost_usd=0.0,
            judge_cost_usd=0.0,
        )


def test_result_rejects_bad_verdict() -> None:
    heatmap = CohortHeatmap(tasks=("t0",), models=("candidate", "baseline"), cells=())
    with pytest.raises(ValueError, match="verdict must be one of"):
        SkillBenchmarkComparisonResult(
            candidate=_arm("candidate"),
            baseline=_arm("baseline"),
            pass_rate_delta=0.0,
            mann_whitney=_mwu(),
            cliffs_delta=0.0,
            bootstrap_ci=(0.0, 0.0),
            verdict="skill_is_great",
            skill_delivery="prompt_injected",
            blinding={},
            evidence=(),
            heatmap=heatmap,
            total_runtime_seconds=0.0,
            total_cost_usd=0.0,
            judge_cost_usd=0.0,
        )


def test_result_rejects_inverted_bootstrap_ci() -> None:
    heatmap = CohortHeatmap(tasks=("t0",), models=("candidate", "baseline"), cells=())
    with pytest.raises(ValueError, match="lo <= hi"):
        SkillBenchmarkComparisonResult(
            candidate=_arm("candidate"),
            baseline=_arm("baseline"),
            pass_rate_delta=0.0,
            mann_whitney=_mwu(),
            cliffs_delta=0.0,
            bootstrap_ci=(0.5, 0.1),
            verdict="no_significant_difference",
            skill_delivery="prompt_injected",
            blinding={},
            evidence=(),
            heatmap=heatmap,
            total_runtime_seconds=0.0,
            total_cost_usd=0.0,
            judge_cost_usd=0.0,
        )


def test_arm_summary_rejects_out_of_range_pass_rate() -> None:
    with pytest.raises(ValueError, match="pass_rate must be in"):
        SkillBenchmarkArmSummary(
            arm="candidate",
            skill_path=None,
            pass_rate=1.5,
            per_task_pass_rates={},
            total_tokens=0,
            mean_tokens=0.0,
            total_elapsed_seconds=0.0,
            total_cost_usd=0.0,
            trials_run=0,
        )


def test_mann_whitney_nan_pvalue_not_significant_verdict() -> None:
    """Identical distributions → nan p-value → not significant."""
    assert math.isnan(float("nan"))
    v = compute_benchmark_verdict(
        candidate_pass_rate=0.5,
        baseline_pass_rate=0.5,
        p_value=float("nan"),
        alpha=0.05,
        baseline_is_none=False,
        obsolescence_threshold=0.9,
        cliffs_delta=0.0,
    )
    assert v == "no_significant_difference"
