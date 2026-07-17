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

"""Frozen result types the Skills keywords hand back."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ActivationDecision",
    "JudgeActivationDecision",
    "ActivationPassAtK",
    "SkillTaskResult",
    "SkillDiscoverabilitySummary",
    "SkillDiscoverabilityResult",
]


@dataclass(frozen=True)
class ActivationDecision:
    """Agent-mode activation call: did the skill fire?

    ``activated`` is the substring-heuristic verdict; ``reasoning`` is the raw
    agent response used to decide it.
    """

    activated: bool
    reasoning: str
    cost_usd: float
    latency_seconds: float


@dataclass(frozen=True)
class JudgeActivationDecision:
    """Judge-mode activation call: did the response apply the skill's guidance?

    The judge, not a substring match, decides ``activated``. ``justification``
    carries the judge's reasoning and ``numeric_score`` its 0-10 grade.
    """

    activated: bool
    justification: str
    numeric_score: float
    cost_usd: float


@dataclass(frozen=True)
class ActivationPassAtK:
    """A pass@k estimate over activation trials, with a Wilson confidence band."""

    pass_at_k: float
    confidence_interval: tuple[float, float]
    successes: int
    trials: int
    k: int


@dataclass(frozen=True)
class SkillTaskResult:
    """Per-task activation outcome across the discoverability trials."""

    task_id: str
    task_prompt: str
    should_activate: bool
    trials_run: int
    activations_observed: int
    pass_at_k: float
    cost_per_trial_usd: float = 0.0


@dataclass(frozen=True)
class SkillDiscoverabilitySummary:
    """Roll-up across every task in a discoverability run.

    ``activation_accuracy`` counts a trial correct when it fired on a
    should-activate task or stayed quiet on a decoy. ``false_activation_rate``
    and ``missed_activation_rate`` split the two failure directions.
    """

    activation_accuracy: float
    false_activation_rate: float
    missed_activation_rate: float
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class SkillDiscoverabilityResult:
    """Everything a discoverability run produces: per-task rows plus the summary."""

    per_task_results: tuple[SkillTaskResult, ...] = field(default_factory=tuple)
    summary: SkillDiscoverabilitySummary | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))
