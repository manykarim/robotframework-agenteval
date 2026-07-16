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

"""Frozen result types the subagent surface passes around."""

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
    """One orchestrator to subagent delegation pulled from a run's tool calls.

    The subagent identity is probed from the trace ``args`` in the fixed key
    order ``subagent_type`` then ``agent_type`` then ``agent`` then ``name``; an
    unrecognized shape leaves ``subagent=""`` - a visible non-match, never a
    silent drop.
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
    """What ``Subagent.Get Delegation Decision`` returns.

    The fan-out-composable sibling of the ``Subagent.Should Delegate To``
    assertion: never raised on a routing miss, so cohorts can aggregate it.
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
    """Per-task aggregated trial outcomes for ``Subagent.Get Routing Accuracy``."""

    task_id: str
    prompt: str
    expected_subagent: str
    trials_run: int
    matches_observed: int
    pass_at_k: float
    cost_per_trial_usd: float = 0.0


@dataclass(frozen=True)
class SubagentRoutingSummary:
    """Aggregate summary for ``Subagent.Get Routing Accuracy``.

    ``routing_accuracy`` is the fraction of all trials that routed to their
    expected subagent; ``ci_lower`` / ``ci_upper`` are the Wilson 95% band on
    that proportion.
    """

    routing_accuracy: float
    ci_lower: float
    ci_upper: float
    total_trials: int
    total_matches: int
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class SubagentRoutingResult:
    """Top-level result from ``Subagent.Get Routing Accuracy``."""

    per_task_results: tuple[SubagentRoutingTaskResult, ...]
    summary: SubagentRoutingSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))
