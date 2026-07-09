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

"""Shared types for the subagent delegation-testing surface.

Exported (add-subagent-delegation-testing change):
    DelegationRecord — one extracted Task-tool delegation from an
        `AgentRunResult.tool_calls` stream.
    DelegationDecision — frozen dataclass returned by
        `Subagent.Get Delegation Decision` (Tier-3); the
        `Stat.Run N Times`-composable sibling mirroring
        `skills.types.ActivationDecision`.
    SubagentRoutingTaskResult — per-task aggregated trial outcomes for
        `Subagent.Get Routing Accuracy`.
    SubagentRoutingSummary — aggregate summary for
        `Subagent.Get Routing Accuracy`.
    SubagentRoutingResult — top-level result from
        `Subagent.Get Routing Accuracy`.

Follows the `skills/types.py` conventions (frozen dataclasses, defensive
copies of mapping/sequence fields in `__post_init__`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DelegationRecord",
    "DelegationDecision",
    "SubagentRoutingTaskResult",
    "SubagentRoutingSummary",
    "SubagentRoutingResult",
]


@dataclass(frozen=True)
class DelegationRecord:
    """One orchestrator→subagent delegation extracted from a run's tool-call trace.

    Produced by `subagents._internal.extract_delegations` — one record per
    `ToolCallTrace` whose `name` is in the delegation-tool set (default
    `{"Task"}`). The subagent identity is probed from the trace `args` in
    the fixed key order `subagent_type` → `agent_type` → `agent` → `name`;
    an unrecognized shape degrades to `subagent=""` (visible non-match, never
    a silent drop).

    Fields:
        subagent: Resolved subagent identity (empty string when no identity
            key was recognized in `args`).
        prompt: The delegation prompt when present in `args` (`prompt` key);
            empty string otherwise.
        description: The delegation task description when present in `args`
            (`description` key); empty string otherwise.
        sequence_index: The trace `sequence_index` (chronological ordering).
        latency_ms: The trace `latency_ms`.
        error: The trace `error` (None on success).
        args: Defensive copy of the raw trace `args` mapping (retained for
            diagnostics so unrecognized shapes are inspectable).
    """

    subagent: str
    prompt: str
    description: str
    sequence_index: int
    latency_ms: float
    error: str | None
    args: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", dict(self.args))


@dataclass(frozen=True)
class DelegationDecision:
    """Result of `Subagent.Get Delegation Decision` [Tier 3].

    The `Stat.Run N Times`-composable sibling of the Tier-2
    `Subagent.Should Delegate To` assertion, mirroring
    `skills.types.ActivationDecision`. Never raised on a routing miss —
    the decision is reported so cohorts can aggregate it.

    Fields:
        delegated: True iff at least one delegation to the expected subagent
            occurred in the run.
        delegations: All extracted `DelegationRecord`s from the run (in
            `sequence_index` order), NOT only the matching ones.
        reasoning: The agent response text (parallels
            `ActivationDecision.reasoning`).
        cost_usd: LLM call cost in USD from the adapter run.
        latency_seconds: Wall-clock seconds for the adapter run.
    """

    delegated: bool
    delegations: tuple[DelegationRecord, ...]
    reasoning: str
    cost_usd: float
    latency_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "delegations", tuple(self.delegations))


@dataclass(frozen=True)
class SubagentRoutingTaskResult:
    """Per-task aggregated trial outcomes for `Subagent.Get Routing Accuracy`.

    Fields:
        task_id: The task's `id` field from the routing-tasks YAML.
        prompt: The task's `prompt` field.
        expected_subagent: The task's `expected_subagent` field.
        trials_run: Number of adapter calls made for this task.
        matches_observed: Number of trials whose delegations included the
            expected subagent.
        pass_at_k: Match rate estimate (`matches_observed / trials_run`, or
            `0.0` when `trials_run == 0`).
        cost_per_trial_usd: Average adapter cost per trial in USD.
    """

    task_id: str
    prompt: str
    expected_subagent: str
    trials_run: int
    matches_observed: int
    pass_at_k: float
    cost_per_trial_usd: float = 0.0


@dataclass(frozen=True)
class SubagentRoutingSummary:
    """Aggregate summary for `Subagent.Get Routing Accuracy`.

    Fields:
        routing_accuracy: Fraction of all trials (across all tasks) whose
            delegations included that task's expected subagent.
        total_trials: Total adapter calls across all tasks.
        total_matches: Total trials that routed to the expected subagent.
        total_cost_usd: Sum of all adapter trial costs.
        total_runtime_seconds: Wall-clock seconds for the full cohort run.
    """

    routing_accuracy: float
    total_trials: int
    total_matches: int
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class SubagentRoutingResult:
    """Top-level result from `Subagent.Get Routing Accuracy` [Tier 3].

    Fields:
        per_task_results: Tuple of `SubagentRoutingTaskResult` in YAML order.
        summary: Aggregated `SubagentRoutingSummary` across all tasks.
    """

    per_task_results: tuple[SubagentRoutingTaskResult, ...]
    summary: SubagentRoutingSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))
