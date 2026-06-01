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
from typing import TYPE_CHECKING

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
]


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
