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

"""Discoverability tasks + result schema (Story 4.4 / PRD FR10a).

Frozen dataclasses for the discoverability evaluation surface:

- `DiscoverabilityTask` — one task entry from the YAML; carries `id`,
  `prompt`, optional `expected_tools`, optional `required` flag.
- `TaskResult` — per-task aggregated trial outcomes with Wilson CI bounds.
- `DiscoverabilitySummary` — aggregate roll-up (overall pass rate, total
  cost, total runtime) per PRD FR10a L1499 ratified shape.
- `DiscoverabilityResult` — top-level result with `per_task_results` +
  `summary` + `mcp_coverage` per PRD FR10a L1499.

Per AC-DISCOVER-01: the result table supports the evidence block that
ships tool-name + Pass@k + per-task verdict + failed-task prompts +
competing-tools-picked + Wilson-CI bounds.

Story 4.4 code-review HIGH-B fix 2026-05-20 (Auditor citation-drift
catch): pre-edit shape flattened `summary` into 3 top-level fields
diverging from PRD FR10a L1499's ratified `summary` nesting. "Fix the
losing source NOW" pattern per `feedback_citation_drift_first_class` —
implementation realigned to the ratified shape rather than amending the
PRD a second time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from AgentEval.types import ToolCallTrace

__all__ = [
    "DiscoverabilityTask",
    "TaskResult",
    "DiscoverabilitySummary",
    "DiscoverabilityResult",
]


@dataclass(frozen=True)
class DiscoverabilityTask:
    """One natural-language task in a discoverability YAML (Story 4.4)."""

    id: str
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    required: bool = True

    def __post_init__(self) -> None:
        # M_R6 shallow-copy pattern.
        object.__setattr__(self, "expected_tools", list(self.expected_tools))


@dataclass(frozen=True)
class TaskResult:
    """Aggregated trial outcomes for one `DiscoverabilityTask` (Story 4.4).

    Per AC-DISCOVER-01 evidence-block design:
        - `success_count` / `trials_run` → Pass@k rate.
        - `wilson_ci_lower` / `wilson_ci_upper` → 95% CI bounds.
        - `tool_calls_per_trial` → trace evidence for the verdict matrix.
        - `competing_tools_picked` → tools called that aren't in
          `expected_tools` (debugging discoverability = debugging vocabulary).
        - `cost_per_trial_usd` → per-trial cost for AC-DISCOVER-02 audit.
    """

    task_id: str
    task_prompt: str
    trials_run: int
    success_count: int
    tool_calls_per_trial: list[list[ToolCallTrace]] = field(default_factory=list)
    competing_tools_picked: list[str] = field(default_factory=list)
    cost_per_trial_usd: list[float] = field(default_factory=list)
    wilson_ci_lower: float = 0.0
    wilson_ci_upper: float = 1.0

    def __post_init__(self) -> None:
        # Story 4.4 code-review MED-C fix 2026-05-20 (Codex empirical probe +
        # Blind LOW-3): pre-edit `list(self.tool_calls_per_trial)` was a SHALLOW
        # copy — inner `list[ToolCallTrace]` references aliased the source,
        # allowing post-construction mutation (`t.tool_calls_per_trial[0].append(...)`)
        # to leak through despite frozen=True. Deep-copy the inner lists so the
        # "frozen" invariant holds for the full nested structure.
        object.__setattr__(
            self,
            "tool_calls_per_trial",
            [list(inner) for inner in self.tool_calls_per_trial],
        )
        object.__setattr__(self, "competing_tools_picked", list(self.competing_tools_picked))
        object.__setattr__(self, "cost_per_trial_usd", list(self.cost_per_trial_usd))

    @property
    def pass_rate(self) -> float:
        """Pass rate (`success_count / trials_run`); 0.0 when `trials_run == 0`."""
        if self.trials_run == 0:
            return 0.0
        return self.success_count / self.trials_run


@dataclass(frozen=True)
class DiscoverabilitySummary:
    """Aggregate roll-up of `DiscoverabilityResult` per PRD FR10a L1499.

    Carries the trial-weighted overall pass rate + total cost + total
    runtime. Story 4.4 code-review HIGH-B fix 2026-05-20: extracted from
    the previous flattened-3-top-level-fields shape to match the ratified
    PRD wording (Auditor citation-drift catch).
    """

    overall_pass_rate: float
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class DiscoverabilityResult:
    """Top-level result of `MCP.Get Tool Discoverability` (Story 4.4 / PRD FR10a).

    Shape per PRD FR10a L1499:
        - `per_task_results: list[TaskResult]`
        - `summary: DiscoverabilitySummary` (overall pass rate, total cost,
          total runtime)
        - `mcp_coverage: Literal[...]` per Story 1b.2 `compute_mcp_coverage`
          + ADR-016 3-value enum.
    """

    per_task_results: list[TaskResult]
    summary: DiscoverabilitySummary
    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", list(self.per_task_results))
