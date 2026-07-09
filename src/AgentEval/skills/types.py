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

"""Shared types for the skills sub-library (Stories 7.1 + 7.2 + 13.5).

Exported:
    ActivationDecision — frozen dataclass returned by `Skill.Get Activation Decision`.
    SkillTaskResult — per-task aggregated trial outcomes for `Skill.Get Discoverability`.
    SkillDiscoverabilityTaskSummary — aggregate summary for `Skill.Get Discoverability`.
    SkillDiscoverabilityResult — top-level result from `Skill.Get Discoverability`.

Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c):
    SkillDiscoverabilityComparisonResult — top-level result from `Skill.Compare Discoverability`.
    SkillPairwiseAdapterDelta — one pairwise cross-adapter delta.
    SkillDiscoverabilityComparisonSummary — aggregate roll-up of the comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from AgentEval._heatmap.models import CohortHeatmap
    from AgentEval.stats.types import MannWhitneyResult

__all__ = [
    "ActivationDecision",
    "SkillTaskResult",
    "SkillDiscoverabilityTaskSummary",
    "SkillDiscoverabilityResult",
    # Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c).
    "SkillDiscoverabilityComparisonResult",
    "SkillPairwiseAdapterDelta",
    "SkillDiscoverabilityComparisonSummary",
    # add-skill-ab-benchmark — two-arm A/B benchmark surface.
    "SkillBenchmarkTrialEvidence",
    "SkillBenchmarkArmSummary",
    "SkillBenchmarkComparisonResult",
    "BENCHMARK_ARMS",
    "BENCHMARK_VERDICTS",
    "BENCHMARK_SKILL_DELIVERY_MODES",
    "BENCHMARK_GRADING_MODES",
]

# --------------------------------------------------------------------------- #
# add-skill-ab-benchmark — closed value spaces (runtime-validated honesty      #
# fields, mirroring `AgentRunMetadata.mcp_coverage`'s closed-set discipline).  #
# --------------------------------------------------------------------------- #

#: The two fixed arms of a benchmark (design D1).
BENCHMARK_ARMS: frozenset[str] = frozenset({"candidate", "baseline"})

#: The closed verdict value space (design D6). `skill_unnecessary` is the
#: first-class skill-obsolescence signal; only emitted in `baseline=none` mode.
BENCHMARK_VERDICTS: frozenset[str] = frozenset(
    {"skill_improves", "skill_unnecessary", "skill_regresses", "no_significant_difference"}
)

#: The closed skill-delivery honesty value space (design D2). Phase-1 emits
#: ONLY `"prompt_injected"` — prompt-context injection, NOT native skill
#: installation. Phase-2 `"workspace_installed"` is a deliberate future addition
#: (adding a value we do not yet perform would be a dishonesty bug).
BENCHMARK_SKILL_DELIVERY_MODES: frozenset[str] = frozenset({"prompt_injected"})

#: The closed grading-mode value space (design D3).
BENCHMARK_GRADING_MODES: frozenset[str] = frozenset({"expected_content", "judge"})


@dataclass(frozen=True)
class ActivationDecision:
    """Result of `Skill.Get Activation Decision` [Tier 3].

    Fields:
        activated: True iff the skill name was found in the agent response text
            (case-insensitive substring match — Phase-1 heuristic per AC-7.1.4).
        reasoning: Full agent response text used for the activation inference.
        cost_usd: LLM call cost in USD from the adapter run.
        latency_seconds: Wall-clock seconds for the adapter run.
    """

    activated: bool
    reasoning: str
    cost_usd: float
    latency_seconds: float


@dataclass(frozen=True)
class SkillTaskResult:
    """Per-task aggregated trial outcomes for `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        task_id: The task's `id` field from the YAML.
        task_prompt: The task's `prompt` field.
        should_activate: Whether the skill SHOULD have activated for this task.
        trials_run: Number of adapter calls made for this task.
        activations_observed: Number of trials where the skill name appeared
            in the adapter response (Phase-1 heuristic — case-insensitive
            substring match).
        pass_at_k: Activation rate estimate (activations_observed / trials_run,
            or 0.0 when trials_run == 0). Phase-1 simplification — Phase-2 will
            wire Wilson CI lower bound from Story 6.3 stats.
        competing_skills_picked: Phase-1 always `{}` — competing skill detection
            deferred to Phase-2 (DF-7.2-S1 / C56). Phase-1 heuristic cannot
            determine which other skill the agent chose.
        cost_per_trial_usd: Average adapter cost per trial in USD.
    """

    task_id: str
    task_prompt: str
    should_activate: bool
    trials_run: int
    activations_observed: int
    pass_at_k: float
    competing_skills_picked: dict[str, int] = field(default_factory=dict)
    cost_per_trial_usd: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "competing_skills_picked", dict(self.competing_skills_picked))


@dataclass(frozen=True)
class SkillDiscoverabilityTaskSummary:
    """Aggregate summary for `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        activation_accuracy: Fraction of trials where the keyword activated
            correctly (i.e., activated when should_activate=True AND did not
            activate when should_activate=False).
        false_activation_rate: Fraction of decoy-task trials (should_activate=False)
            where the skill incorrectly activated.
        missed_activation_rate: Fraction of should-activate-task trials
            (should_activate=True) where the skill failed to activate.
        total_cost_usd: Sum of all adapter trial costs.
        total_runtime_seconds: Wall-clock seconds for the full cohort run.
    """

    activation_accuracy: float
    false_activation_rate: float
    missed_activation_rate: float
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class SkillDiscoverabilityResult:
    """Top-level result from `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        per_task_results: Tuple of `SkillTaskResult` instances in YAML task order.
        summary: Aggregated `SkillDiscoverabilityTaskSummary` across all tasks.
        adapter_coverage: Phase-1 always `"in_process"` — skills use
            `InProcessAdapter` from Story 1b.4 which is fully observable.
            NOT `mcp_coverage` (which is MCP-server-specific per ADR-016;
            D-2 pre-create-story drift fix 2026-05-21).
    """

    per_task_results: tuple[SkillTaskResult, ...]
    summary: SkillDiscoverabilityTaskSummary
    adapter_coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))


# --------------------------------------------------------------------------- #
# Story 13.5 (Epic 13) — cross-adapter Skill Discoverability surface (FR4c)   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillPairwiseAdapterDelta:
    """One pairwise cross-adapter delta within `SkillDiscoverabilityComparisonResult` (Story 13.5).

    Symmetric to Story 13.3's `PairwiseAdapterDelta` but extended with
    Skill-domain metrics (false_activation_rate_delta +
    missed_activation_rate_delta) because Skill discoverability has TWO
    primary failure modes (false-positive activation on decoy tasks +
    false-negative missed activation on should-activate tasks). MCP
    discoverability has only ONE primary failure mode.

    Fields:
        adapter_a: First adapter name.
        adapter_b: Second adapter name (must differ from `adapter_a`).
        pass_at_k_delta: ``mean(adapter_a per-task pass_at_k) -
            mean(adapter_b per-task pass_at_k)``; in ``[-1.0, 1.0]``.
            Positive → adapter_a achieves higher Pass@k.
        pass_at_k_mann_whitney_result: Story 13.1 ``MannWhitneyResult``
            (Mann-Whitney U on the per-task ``pass_at_k`` lists).
        false_activation_rate_delta: ``summary.false_activation_rate(a)
            - summary.false_activation_rate(b)``. Positive → adapter_a
            MORE often falsely activates the skill on decoy tasks
            (worse than adapter_b). Range: ``[-1.0, 1.0]``.
        missed_activation_rate_delta: ``summary.missed_activation_rate(a)
            - summary.missed_activation_rate(b)``. Positive → adapter_a
            MORE often misses activating when it should (worse than
            adapter_b). Range: ``[-1.0, 1.0]``.
        significant_at_alpha_05: ``pass_at_k_mann_whitney_result.p_value
            < 0.05``; nan-aware (Story 13.3 + 13.4 convention — nan
            treated as not-significant).
    """

    adapter_a: str
    adapter_b: str
    pass_at_k_delta: float
    pass_at_k_mann_whitney_result: MannWhitneyResult
    false_activation_rate_delta: float
    missed_activation_rate_delta: float
    significant_at_alpha_05: bool

    def __post_init__(self) -> None:
        if self.adapter_a == self.adapter_b:
            raise ValueError(
                f"SkillPairwiseAdapterDelta requires distinct adapters; "
                f"got adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
            )
        for name, val in (
            ("pass_at_k_delta", self.pass_at_k_delta),
            ("false_activation_rate_delta", self.false_activation_rate_delta),
            ("missed_activation_rate_delta", self.missed_activation_rate_delta),
        ):
            if not (-1.0 <= val <= 1.0):
                raise ValueError(f"{name} must be in [-1.0, 1.0]; got {val!r}")
        import math

        p = self.pass_at_k_mann_whitney_result.p_value
        expected = (not math.isnan(p)) and p < 0.05
        if self.significant_at_alpha_05 != expected:
            raise ValueError(
                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as "
                f"not significant); got significant_at_alpha_05={self.significant_at_alpha_05!r} "
                f"but p_value={self.pass_at_k_mann_whitney_result.p_value!r}"
            )


@dataclass(frozen=True)
class SkillDiscoverabilityComparisonSummary:
    """Aggregate roll-up of `SkillDiscoverabilityComparisonResult` (Story 13.5).

    Fields:
        total_cost_usd: Sum of per-adapter `summary.total_cost_usd`.
        total_runtime_seconds: End-to-end wall-clock for the
            ``Skill.Compare Discoverability`` call (what the operator
            ACTUALLY waited for). Story 13.3 HIGH-A precedent applied.
        activation_accuracy_per_adapter: Mapping adapter name →
            ``summary.activation_accuracy`` from each adapter's per-run
            ``SkillDiscoverabilityResult``.
        best_adapter: Adapter name with the highest activation_accuracy
            (validated in `__post_init__`).
        worst_adapter: Adapter name with the lowest activation_accuracy
            (validated in `__post_init__`).
    """

    total_cost_usd: float
    total_runtime_seconds: float
    activation_accuracy_per_adapter: Mapping[str, float]
    best_adapter: str
    worst_adapter: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_accuracy_per_adapter", dict(self.activation_accuracy_per_adapter))
        if self.best_adapter not in self.activation_accuracy_per_adapter:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} not in "
                f"activation_accuracy_per_adapter keys "
                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
            )
        if self.worst_adapter not in self.activation_accuracy_per_adapter:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} not in "
                f"activation_accuracy_per_adapter keys "
                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
            )
        # Story 13.4 Codex HIGH-2 lesson: validate best/worst match argmax/argmin.
        max_acc = max(self.activation_accuracy_per_adapter.values())
        min_acc = min(self.activation_accuracy_per_adapter.values())
        if self.activation_accuracy_per_adapter[self.best_adapter] != max_acc:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} has activation_accuracy "
                f"{self.activation_accuracy_per_adapter[self.best_adapter]!r} but the "
                f"max observed is {max_acc!r}"
            )
        if self.activation_accuracy_per_adapter[self.worst_adapter] != min_acc:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} has activation_accuracy "
                f"{self.activation_accuracy_per_adapter[self.worst_adapter]!r} but the "
                f"min observed is {min_acc!r}"
            )


@dataclass(frozen=True)
class SkillDiscoverabilityComparisonResult:
    """Top-level result of `Skill.Compare Discoverability` (Story 13.5 / PRD FR4c).

    Shape per epics.md L2218-2219 + Story 13.5 D-1 ratified shape:
        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
        - `per_adapter_results: Mapping[str, SkillDiscoverabilityResult]` —
          one full `SkillDiscoverabilityResult` per adapter (mirrors what
          `Skill.Get Discoverability` returns for the single-adapter case).
        - `cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]` —
          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
          adapter; rows = task IDs). Built via
          `CohortHeatmap.from_skill_comparison(self)`.
        - `summary: SkillDiscoverabilityComparisonSummary` — aggregate roll-up.

    Cross-consistency invariants checked in `__post_init__` (Story 13.3 +
    13.4 lessons applied):
        - `len(adapters) >= 2`.
        - `set(adapters) == set(per_adapter_results.keys())`.
        - `set(adapters) == set(heatmap.models)`.
        - `set(adapters) == set(summary.activation_accuracy_per_adapter.keys())`.
    """

    adapters: tuple[str, ...]
    per_adapter_results: Mapping[str, SkillDiscoverabilityResult]
    cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]
    heatmap: CohortHeatmap
    summary: SkillDiscoverabilityComparisonSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapters", tuple(self.adapters))
        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
        if len(self.adapters) < 2:
            raise ValueError(f"SkillDiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
        if set(self.adapters) != set(self.per_adapter_results.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
            )
        if set(self.adapters) != set(self.heatmap.models):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
            )
        if set(self.adapters) != set(self.summary.activation_accuracy_per_adapter.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"summary.activation_accuracy_per_adapter keys "
                f"{sorted(self.summary.activation_accuracy_per_adapter.keys())!r}"
            )


# --------------------------------------------------------------------------- #
# add-skill-ab-benchmark — two-arm A/B benchmark result surface (design D7)    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillBenchmarkTrialEvidence:
    """One evidence-bearing trial record from `Skill.Compare Against Baseline`.

    Every trial (per arm, per task, per trial index) produces exactly one of
    these so a reviewer can trace each pass/fail verdict back to the trial
    output, its grading mode, and (for judged trials) the judge's reasoning.

    Fields:
        task_id: The task's `id` field from the benchmark YAML.
        arm: Which arm produced the output (`"candidate"` or `"baseline"`).
        trial_index: 0-indexed trial number within this (arm, task) cell.
        blinded_grading_id: Opaque seed-derived id (`"g-<hex>"`) — carries NO
            arm/task information; the grader never sees the true coordinates.
        passed: Whether this trial passed its grading.
        grading_mode: `"expected_content"` (deterministic substring check) or
            `"judge"` (LLM rubric grading).
        judge_score: The judge's `numeric_score` (judge mode only; else None).
        judge_reasoning: The judge's narrative reasoning (judge mode only).
        response_excerpt: Truncated `response_text` with the project redaction
            pass applied (credential scrubbing per `_kernel.redaction`).
        input_tokens / output_tokens: Token usage from the trial's `AgentRunResult.usage`.
        cost_usd: Adapter cost for this trial (judge cost is aggregated separately).
        latency_seconds: Wall-clock seconds for the trial's adapter run.
        error: When the trial's adapter (or judge) execution RAISED at runtime,
            the string reason (`"<ExceptionType>: <message>"`); `None` for a
            trial that executed cleanly. A failed trial is recorded as
            non-passing (`passed=False`) evidence rather than aborting the whole
            benchmark — every trial stays auditable (codex MED). Setup/config
            errors (bad skill path, unresolvable adapter, invalid tasks file)
            still fail loud BEFORE any trial runs.
    """

    task_id: str
    arm: str
    trial_index: int
    blinded_grading_id: str
    passed: bool
    grading_mode: str
    judge_score: float | None
    judge_reasoning: str | None
    response_excerpt: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    error: str | None = None

    def __post_init__(self) -> None:
        if self.arm not in BENCHMARK_ARMS:
            raise ValueError(
                f"SkillBenchmarkTrialEvidence.arm must be one of {sorted(BENCHMARK_ARMS)}; got {self.arm!r}"
            )
        if self.grading_mode not in BENCHMARK_GRADING_MODES:
            raise ValueError(
                f"SkillBenchmarkTrialEvidence.grading_mode must be one of "
                f"{sorted(BENCHMARK_GRADING_MODES)}; got {self.grading_mode!r}"
            )


@dataclass(frozen=True)
class SkillBenchmarkArmSummary:
    """Per-arm outcome metrics for `Skill.Compare Against Baseline` (design D7).

    Fields:
        arm: `"candidate"` or `"baseline"`.
        skill_path: Filesystem path of the skill delivered to this arm, or
            `None` for the no-skill baseline (`baseline=none`).
        pass_rate: Fraction of this arm's trials that passed (`[0.0, 1.0]`).
        per_task_pass_rates: Mapping task_id → per-task pass rate (in task order).
        total_tokens: Sum of input+output tokens across the arm's trials.
        mean_tokens: `total_tokens / trials_run` (0.0 when no trials).
        total_elapsed_seconds: Sum of the arm's trial `latency_seconds`.
        total_cost_usd: Sum of the arm's trial adapter costs.
        trials_run: Total adapter runs in this arm (`N tasks * trials`).
    """

    arm: str
    skill_path: str | None
    pass_rate: float
    per_task_pass_rates: Mapping[str, float]
    total_tokens: int
    mean_tokens: float
    total_elapsed_seconds: float
    total_cost_usd: float
    trials_run: int

    def __post_init__(self) -> None:
        if self.arm not in BENCHMARK_ARMS:
            raise ValueError(f"SkillBenchmarkArmSummary.arm must be one of {sorted(BENCHMARK_ARMS)}; got {self.arm!r}")
        if not 0.0 <= self.pass_rate <= 1.0:
            raise ValueError(f"SkillBenchmarkArmSummary.pass_rate must be in [0.0, 1.0]; got {self.pass_rate!r}")
        # M_R6 defensive copy.
        object.__setattr__(self, "per_task_pass_rates", dict(self.per_task_pass_rates))


@dataclass(frozen=True)
class SkillBenchmarkComparisonResult:
    """Top-level result of `Skill.Compare Against Baseline` (design D7 / PRD-adjacent).

    Frozen + `dataclasses.asdict()`-serializable. Carries per-arm metrics,
    cross-arm statistical significance (Epic-13 primitives), the closed-set
    obsolescence verdict, the `skill_delivery` honesty field, an auditable
    blinding record, per-trial evidence, and the cohort heatmap.

    Fields:
        candidate / baseline: `SkillBenchmarkArmSummary` per arm.
        pass_rate_delta: `candidate.pass_rate - baseline.pass_rate`.
        mann_whitney: `MannWhitneyResult` over the two arms' per-task
            pass-rate distributions (Epic-13 `compute_mann_whitney_u`).
        cliffs_delta: Cliff's delta over the same samples.
        bootstrap_ci: Seeded percentile bootstrap CI `(lo, hi)` on the
            per-task pass-rate delta (candidate − baseline).
        verdict: Closed set — see `BENCHMARK_VERDICTS`.
        skill_delivery: Honesty field — Phase-1 always `"prompt_injected"`.
        blinding: Auditable record `{"mode", "seed", "grading_order"}`.
        evidence: One `SkillBenchmarkTrialEvidence` per trial per arm.
        heatmap: `CohortHeatmap` (rows = tasks, columns = the two arms).
        total_runtime_seconds: Wall-clock anchored at keyword entry.
        total_cost_usd: Adapter + judge cost combined.
        judge_cost_usd: Judge-only cost, broken out of `total_cost_usd`.
    """

    candidate: SkillBenchmarkArmSummary
    baseline: SkillBenchmarkArmSummary
    pass_rate_delta: float
    mann_whitney: MannWhitneyResult
    cliffs_delta: float
    bootstrap_ci: tuple[float, float]
    verdict: str
    skill_delivery: str
    blinding: Mapping[str, Any]
    evidence: tuple[SkillBenchmarkTrialEvidence, ...]
    heatmap: CohortHeatmap
    total_runtime_seconds: float
    total_cost_usd: float
    judge_cost_usd: float

    def __post_init__(self) -> None:
        if self.verdict not in BENCHMARK_VERDICTS:
            raise ValueError(
                f"SkillBenchmarkComparisonResult.verdict must be one of "
                f"{sorted(BENCHMARK_VERDICTS)}; got {self.verdict!r}"
            )
        if self.skill_delivery not in BENCHMARK_SKILL_DELIVERY_MODES:
            raise ValueError(
                f"SkillBenchmarkComparisonResult.skill_delivery must be one of "
                f"{sorted(BENCHMARK_SKILL_DELIVERY_MODES)}; got {self.skill_delivery!r}"
            )
        lo, hi = self.bootstrap_ci
        if lo > hi:
            raise ValueError(
                f"SkillBenchmarkComparisonResult.bootstrap_ci must have lo <= hi; got {self.bootstrap_ci!r}"
            )
        if self.candidate.arm != "candidate":
            raise ValueError(f"candidate arm summary must have arm='candidate'; got {self.candidate.arm!r}")
        if self.baseline.arm != "baseline":
            raise ValueError(f"baseline arm summary must have arm='baseline'; got {self.baseline.arm!r}")
        # Defensive copies (M_R6): freeze the blinding mapping + evidence tuple.
        object.__setattr__(self, "blinding", dict(self.blinding))
        object.__setattr__(self, "evidence", tuple(self.evidence))
