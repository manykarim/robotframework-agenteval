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

"""Shared per-adapter discoverability helper (Story 13.3 refactor of Story 4.4).

Extracted from `MCPLibrary.get_tool_discoverability` so the new
`MCP.Compare Tool Discoverability` keyword (Story 13.3) can reuse the
per-adapter logic without duplicating ~80 LoC. Behavior MUST be
identical to the pre-refactor `get_tool_discoverability` body —
verified by Story 4.4's 50+ existing tests passing unchanged.

Architecture note: this is the canonical `_internal.py` helper module
per `feedback_full_surface_retro_review` discipline (mirrors
`stats/_internal.py` from Story 6.3 + `_assertions/_internal.py`-style
sibling). Pure functions; no side effects beyond the adapter calls
themselves.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from AgentEval._kernel.discovery import get_adapter
from AgentEval.discoverability.schema import (
    DiscoverabilityResult,
    DiscoverabilitySummary,
    TaskResult,
)
from AgentEval.discoverability.wilson_ci import wilson_score_interval

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import DiscoverabilityTask

__all__ = ["run_single_adapter_discoverability"]


def run_single_adapter_discoverability(
    *,
    mcp_server: str,
    adapter: str,
    model: str | None,
    task_list: list[DiscoverabilityTask],
    trials_per_task: int,
    max_cost_usd: float,
    max_runtime_seconds: float | None,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
) -> DiscoverabilityResult:
    """Run discoverability evaluation against ONE adapter; produce a `DiscoverabilityResult`.

    Internal helper extracted from `MCPLibrary.get_tool_discoverability`
    (Story 4.4) so the cross-adapter `Compare Tool Discoverability`
    keyword (Story 13.3) reuses the per-adapter logic without ~80 LoC
    duplication. Behavior MUST equal pre-refactor; verified by Story
    4.4's existing tests passing unchanged.

    Args:
        mcp_server: Already-validated non-empty MCP server name. NOT
            forwarded to `adapter.run(mcp_servers=...)` in Phase-1
            (DF-4.1-S2 + DF-4.2-S1 carve-out); accepted for
            forward-compat.
        adapter: Adapter name. Resolved via `_kernel.discovery.get_adapter`.
        model: Optional model identifier; forwarded to adapter ctor when
            non-None.
        task_list: Already-loaded + schema-validated list of tasks.
            Caller (single-adapter or compare-multi-adapter) loads the
            YAML ONCE and passes the parsed list here.
        trials_per_task: Pass@k trials per task; already validated >= 1.
        max_cost_usd: Budget cap. Phase-1: tracked, NOT enforced
            (DF-4.4-S1 carry-over).
        max_runtime_seconds: Runtime cap. Phase-1: tracked, NOT enforced.
        extra_adapter_kwargs: Forward-compat kwargs routed to adapter ctor.
        t_start: Wall-clock start time (from the caller's `time.monotonic()`).
            For single-adapter `MCP.Get Tool Discoverability`: captured BEFORE
            arg validation + YAML load so `total_runtime_seconds` includes
            both. For `MCP.Compare Tool Discoverability`: per-adapter anchor
            fired AFTER YAML load (which is amortized across N adapters);
            the comparison-level wall-clock is measured separately at the
            keyword body using its own `t_start`. Story 13.3 code-review
            Sonnet MED-2 fix 2026-06-01: pre-fix docstring claimed a "single
            anchor across all adapters" semantic that the compare loop does
            not implement (each iteration passes a fresh timer).

    Returns:
        ``DiscoverabilityResult`` with per-task results + summary +
        Phase-1 hardcoded ``mcp_coverage="hosted_in_process"`` (DF-4.4-S3
        carry-over).

    Raises:
        TypeError: When the adapter doesn't accept the forwarded kwargs
            (DF-4.4-S2 carry-over re ctor/run split parity).
    """
    adapter_cls = get_adapter(adapter)
    adapter_ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
    if model is not None:
        adapter_ctor_kwargs["model"] = model
    try:
        adapter_instance = adapter_cls(**adapter_ctor_kwargs)
    except TypeError as exc:
        raise TypeError(
            f"Adapter {adapter!r} doesn't accept kwargs {sorted(adapter_ctor_kwargs)}; "
            "DF-4.4-S2 carry-over (ctor/run split parity for MCPLibrary "
            "lands in Phase-1.5 — mirroring Story 4.3's "
            "`_split_adapter_kwargs` introspection on OrchestrationLibrary). "
            "For now, pass kwargs the adapter accepts."
        ) from exc

    # Per-call mcp_servers integration is DF-4.1-S2 / DF-4.2-S1.
    _ = mcp_server

    per_task: list[TaskResult] = []
    total_cost = 0.0
    for task in task_list:
        tool_calls_per_trial: list[list[Any]] = []
        cost_per_trial: list[float] = []
        success_count = 0
        competing_set: set[str] = set()
        for _ in range(trials_per_task):
            run_result = adapter_instance.run(task.prompt)
            tool_calls_per_trial.append(list(run_result.tool_calls))
            cost_per_trial.append(run_result.cost_usd)
            total_cost += run_result.cost_usd
            called_names = {tc.name for tc in run_result.tool_calls}
            # Story 4.4 3-way MED-A: wildcard-success mode when expected_tools empty.
            if task.expected_tools:
                expected_set = set(task.expected_tools)
                if called_names & expected_set:
                    success_count += 1
                competing_set.update(called_names - expected_set)
            else:
                if called_names:
                    success_count += 1
                competing_set.update(called_names)
        lower, upper = wilson_score_interval(success_count, trials_per_task)
        per_task.append(
            TaskResult(
                task_id=task.id,
                task_prompt=task.prompt,
                trials_run=trials_per_task,
                success_count=success_count,
                tool_calls_per_trial=tool_calls_per_trial,
                competing_tools_picked=sorted(competing_set),
                cost_per_trial_usd=cost_per_trial,
                wilson_ci_lower=lower,
                wilson_ci_upper=upper,
            )
        )
    total_runtime = time.monotonic() - t_start

    # Overall pass rate weighted by trials.
    total_trials = sum(t.trials_run for t in per_task)
    total_successes = sum(t.success_count for t in per_task)
    overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0

    # Phase-1: mcp_coverage hardcoded (DF-4.4-S3 carry-over).
    _ = max_cost_usd
    _ = max_runtime_seconds
    return DiscoverabilityResult(
        per_task_results=per_task,
        summary=DiscoverabilitySummary(
            overall_pass_rate=overall_pass_rate,
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
        ),
        mcp_coverage="hosted_in_process",
    )
