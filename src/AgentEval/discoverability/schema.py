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

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from AgentEval.types import ToolCallTrace

if TYPE_CHECKING:
    from AgentEval._heatmap.models import CohortHeatmap
    from AgentEval.stats.types import MannWhitneyResult

__all__ = [
    "DiscoverabilityTask",
    "TaskResult",
    "DiscoverabilitySummary",
    "DiscoverabilityResult",
    # Story 13.3 (Epic 13) — cross-adapter comparison surface (FR10b).
    "DiscoverabilityComparisonResult",
    "PairwiseAdapterDelta",
    "DiscoverabilityComparisonSummary",
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


# --------------------------------------------------------------------------- #
# Story 13.3 (Epic 13) — cross-adapter comparison surface (FR10b)             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PairwiseAdapterDelta:
    """One pairwise cross-adapter delta within `DiscoverabilityComparisonResult` (Story 13.3).

    Carries the Mann-Whitney U result + the per-task pass-rate
    differential between two adapters. The cohort comparison ships
    C(N, 2) pairwise deltas across N adapters; each delta is indexed by
    the ordered key `f"{adapter_a}_vs_{adapter_b}"` in
    `DiscoverabilityComparisonResult.cross_adapter_deltas`.

    Fields:
        adapter_a: First adapter name.
        adapter_b: Second adapter name (must differ from `adapter_a`).
        pass_rate_delta: ``mean(adapter_a per-task pass rates) - mean(adapter_b)``;
            in ``[-1.0, 1.0]``. Positive → adapter_a outperforms adapter_b.
        mann_whitney_result: Story 13.1 ``MannWhitneyResult`` (Mann-Whitney
            U on the per-task pass rates with `predicate=lambda r: r.pass_rate`).
        significant_at_alpha_05: ``mann_whitney_result.p_value < 0.05``;
            redundant with the Mann-Whitney p-value but stored explicitly so
            consumers can ``Should Be True ${delta.significant_at_alpha_05}``
            without re-deriving.
    """

    adapter_a: str
    adapter_b: str
    pass_rate_delta: float
    mann_whitney_result: MannWhitneyResult
    significant_at_alpha_05: bool

    def __post_init__(self) -> None:
        if self.adapter_a == self.adapter_b:
            raise ValueError(
                f"PairwiseAdapterDelta requires distinct adapters; got "
                f"adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
            )
        if not (-1.0 <= self.pass_rate_delta <= 1.0):
            raise ValueError(f"pass_rate_delta must be in [-1.0, 1.0]; got {self.pass_rate_delta!r}")
        # `nan < 0.05` evaluates to False, so significant_at_alpha_05 is
        # False for nan p_values (identical-samples scipy convention) —
        # consistent with "cannot reject the null."
        import math

        p = self.mann_whitney_result.p_value
        expected = (not math.isnan(p)) and p < 0.05
        if self.significant_at_alpha_05 != expected:
            raise ValueError(
                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as not significant); "
                f"got significant_at_alpha_05={self.significant_at_alpha_05!r} but "
                f"p_value={self.mann_whitney_result.p_value!r}"
            )


@dataclass(frozen=True)
class DiscoverabilityComparisonSummary:
    """Aggregate roll-up of `DiscoverabilityComparisonResult` (Story 13.3).

    Fields:
        total_cost_usd: Sum of per-adapter `summary.total_cost_usd` across all adapters.
        total_runtime_seconds: End-to-end wall-clock for the `Compare Tool
            Discoverability` call (what the operator ACTUALLY waited for).
            Phase-2 serial execution → `total_runtime_seconds ≈ sum(per-adapter
            runtimes)`; Phase-2.5 parallel target → `total_runtime_seconds ≈
            max(per-adapter runtimes)`. Per-adapter runtimes remain in
            `per_adapter_results[adapter].summary.total_runtime_seconds`.
            Story 13.3 code-review HIGH-A fix 2026-06-01 (Codex HIGH-1 + Opus
            MED-2 2-way): pre-fix `max(per-adapter runtimes)` underreported
            actual wait time by ~N-1× under serial execution.
        pass_rate_per_adapter: Mapping of adapter name → overall pass rate
            (i.e., `per_adapter_results[adapter].summary.overall_pass_rate`).
        best_adapter: Adapter name with the highest pass rate.
        worst_adapter: Adapter name with the lowest pass rate. Equals
            `best_adapter` only when all adapters tie.
    """

    total_cost_usd: float
    total_runtime_seconds: float
    pass_rate_per_adapter: Mapping[str, float]
    best_adapter: str
    worst_adapter: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "pass_rate_per_adapter", dict(self.pass_rate_per_adapter))
        if self.best_adapter not in self.pass_rate_per_adapter:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} not in "
                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
            )
        if self.worst_adapter not in self.pass_rate_per_adapter:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} not in "
                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
            )
        # Story 13.3 code-review HIGH-B fix 2026-06-01 (Codex HIGH-2): re-derive
        # max/min from pass_rate_per_adapter to verify best_adapter / worst_adapter
        # are CONSISTENT with the data. Pre-fix the constructor accepted
        # nonsense like `best_adapter='b'` when 'a' actually had a higher rate.
        max_rate = max(self.pass_rate_per_adapter.values())
        min_rate = min(self.pass_rate_per_adapter.values())
        if self.pass_rate_per_adapter[self.best_adapter] != max_rate:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} has pass rate "
                f"{self.pass_rate_per_adapter[self.best_adapter]!r} but the max "
                f"observed is {max_rate!r}"
            )
        if self.pass_rate_per_adapter[self.worst_adapter] != min_rate:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} has pass rate "
                f"{self.pass_rate_per_adapter[self.worst_adapter]!r} but the min "
                f"observed is {min_rate!r}"
            )


@dataclass(frozen=True)
class DiscoverabilityComparisonResult:
    """Top-level result of `MCP.Compare Tool Discoverability` (Story 13.3 / PRD FR10b).

    Shape per epics.md L2186-2187 + Story 13.3 D-2 ratified shape:
        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
        - `per_adapter_results: Mapping[str, DiscoverabilityResult]` —
          one full `DiscoverabilityResult` per adapter (mirrors what
          `MCP.Get Tool Discoverability` returns for the single-adapter case).
        - `cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]` —
          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
          For N=2 there is 1 delta; for N=3 there are 3 deltas.
        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
          adapter; rows = task IDs). Built via
          `CohortHeatmap.from_comparison(self)`.
        - `summary: DiscoverabilityComparisonSummary` — aggregate roll-up.

    Cross-consistency invariants checked in `__post_init__`:
        - `len(adapters) >= 2`.
        - `set(adapters) == set(per_adapter_results.keys())`.
        - `set(adapters) == set(heatmap.models)`.
    """

    adapters: tuple[str, ...]
    per_adapter_results: Mapping[str, DiscoverabilityResult]
    cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]
    heatmap: CohortHeatmap
    summary: DiscoverabilityComparisonSummary

    def __post_init__(self) -> None:
        # Tuple coercion + defensive Mapping → dict casts (Story 1b.2 M_R6).
        object.__setattr__(self, "adapters", tuple(self.adapters))
        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
        if len(self.adapters) < 2:
            raise ValueError(f"DiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
        if set(self.adapters) != set(self.per_adapter_results.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
            )
        if set(self.adapters) != set(self.heatmap.models):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
            )
        # Story 13.3 code-review HIGH-C fix 2026-06-01 (Codex HIGH-3 + Opus
        # MED-1 2-way): also cross-check `summary.pass_rate_per_adapter`
        # against `adapters`. Pre-fix the result accepted a summary whose
        # pass_rate_per_adapter was about completely different adapter names,
        # silently shipping nonsense.
        if set(self.adapters) != set(self.summary.pass_rate_per_adapter.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"summary.pass_rate_per_adapter keys "
                f"{sorted(self.summary.pass_rate_per_adapter.keys())!r}"
            )
