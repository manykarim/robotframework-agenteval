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

"""Shared types for the skills sub-library (Stories 7.1 + 7.2).

Exported:
    ActivationDecision — frozen dataclass returned by `Skill.Get Activation Decision`.
    SkillTaskResult — per-task aggregated trial outcomes for `Skill.Get Discoverability`.
    SkillDiscoverabilityTaskSummary — aggregate summary for `Skill.Get Discoverability`.
    SkillDiscoverabilityResult — top-level result from `Skill.Get Discoverability`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ActivationDecision",
    "SkillTaskResult",
    "SkillDiscoverabilityTaskSummary",
    "SkillDiscoverabilityResult",
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
