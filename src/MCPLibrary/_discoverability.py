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

"""Single-adapter tool discoverability - drive an agent, score its tool picks.

Loads a task set, runs an adapter over each task ``trials_per_task`` times, and
scores whether the agent called the expected tools. Wilson bounds come from the
shared ``stats`` module. Cross-adapter comparison lives elsewhere - not here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from AgentEval._core import stats
from AgentEval._core.adapter import get_adapter
from AgentEval._core.errors import InvalidConfigError
from AgentEval._core.types import ToolCallTrace

__all__ = [
    "DiscoverabilityTask",
    "TaskResult",
    "DiscoverabilitySummary",
    "DiscoverabilityResult",
    "load_discoverability_tasks",
    "run_discoverability",
]


@dataclass(frozen=True)
class DiscoverabilityTask:
    """One natural-language task from a discoverability YAML."""

    id: str
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_tools", list(self.expected_tools))


@dataclass(frozen=True)
class TaskResult:
    """Aggregated trial outcomes for one task.

    ``competing_tools_picked`` are tools called that were not expected - the
    vocabulary an agent reaches for instead.
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
        object.__setattr__(self, "tool_calls_per_trial", [list(inner) for inner in self.tool_calls_per_trial])
        object.__setattr__(self, "competing_tools_picked", list(self.competing_tools_picked))
        object.__setattr__(self, "cost_per_trial_usd", list(self.cost_per_trial_usd))

    @property
    def pass_rate(self) -> float:
        """``success_count / trials_run``; 0.0 when no trials ran."""
        if self.trials_run == 0:
            return 0.0
        return self.success_count / self.trials_run


@dataclass(frozen=True)
class DiscoverabilitySummary:
    """Aggregate roll-up: trial-weighted pass rate, total cost, total runtime."""

    overall_pass_rate: float
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class DiscoverabilityResult:
    """Top-level result of ``MCP.Get Tool Discoverability``."""

    per_task_results: list[TaskResult]
    summary: DiscoverabilitySummary
    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", list(self.per_task_results))


def load_discoverability_tasks(path: str | Path) -> list[DiscoverabilityTask]:
    """Load and validate a discoverability tasks YAML into ``DiscoverabilityTask``.

    Raises ``InvalidConfigError`` on any structural problem; ``field`` carries
    an RFC 6901 JSON Pointer at the offending entry.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidConfigError(
            f"discoverability tasks file not found: {p}",
            file_path=str(p),
            field="",
            fix="Check the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidConfigError(
            f"discoverability tasks file must end in .yaml or .yml; got {p.suffix!r}",
            file_path=str(p),
            field="",
            fix="Rename the file to use a .yaml or .yml extension.",
        )
    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidConfigError(
            f"failed to read discoverability tasks file: {exc}",
            file_path=str(p),
            field="",
            fix="Check the file is readable and UTF-8 encoded.",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise InvalidConfigError(
            f"malformed YAML: {exc}",
            file_path=str(p),
            field="",
            fix="Validate the YAML with a linter.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidConfigError(
            f"tasks YAML top level must be a mapping; got {type(parsed).__name__}",
            file_path=str(p),
            field="",
            fix="Wrap the content in a top-level mapping with a `tasks:` key.",
        )
    if "tasks" not in parsed:
        raise InvalidConfigError(
            "tasks YAML missing required `tasks` field",
            file_path=str(p),
            field="/tasks",
            fix="Add a top-level `tasks:` list of task entries.",
        )
    tasks_raw = parsed["tasks"]
    if not isinstance(tasks_raw, list):
        raise InvalidConfigError(
            f"`tasks` must be a list; got {type(tasks_raw).__name__}",
            file_path=str(p),
            field="/tasks",
            fix="Format `tasks` as a YAML list of entries.",
        )
    if not tasks_raw:
        raise InvalidConfigError(
            "`tasks` list is empty; at least one task is required",
            file_path=str(p),
            field="/tasks",
            fix="Add at least one task with `id:` and `prompt:` fields.",
        )

    out: list[DiscoverabilityTask] = []
    seen_ids: dict[str, int] = {}
    for idx, entry in enumerate(tasks_raw):
        task = _parse_task(entry, idx=idx, file_path=str(p))
        if task.id in seen_ids:
            prior = seen_ids[task.id]
            raise InvalidConfigError(
                f"`tasks[{idx}].id` duplicates `tasks[{prior}].id` (both = {task.id!r}); ids must be unique",
                file_path=str(p),
                field=f"/tasks/{idx}/id",
                fix=f"Rename `tasks[{idx}].id` to something distinct from `tasks[{prior}].id`.",
            )
        seen_ids[task.id] = idx
        out.append(task)
    return out


def _parse_task(entry: Any, *, idx: int, file_path: str) -> DiscoverabilityTask:
    """Validate one ``tasks[idx]`` entry."""
    if not isinstance(entry, dict):
        raise InvalidConfigError(
            f"`tasks[{idx}]` must be a mapping; got {type(entry).__name__}",
            file_path=file_path,
            field=f"/tasks/{idx}",
            fix="Format each task as a mapping with `id:` and `prompt:` fields.",
        )
    task_id = entry.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise InvalidConfigError(
            f"`tasks[{idx}].id` must be a non-empty string; got {task_id!r}",
            file_path=file_path,
            field=f"/tasks/{idx}/id",
            fix="Add an `id:` with a unique, non-empty task identifier.",
        )
    prompt = entry.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise InvalidConfigError(
            f"`tasks[{idx}].prompt` must be a non-empty string; got {prompt!r}",
            file_path=file_path,
            field=f"/tasks/{idx}/prompt",
            fix="Add a `prompt:` with the natural-language task text.",
        )
    expected_raw = entry.get("expected_tools")
    if expected_raw is None:
        expected_tools: list[str] = []
    elif isinstance(expected_raw, list) and all(isinstance(x, str) for x in expected_raw):
        expected_tools = list(expected_raw)
    else:
        raise InvalidConfigError(
            f"`tasks[{idx}].expected_tools` must be a list of strings; got {expected_raw!r}",
            file_path=file_path,
            field=f"/tasks/{idx}/expected_tools",
            fix="Format `expected_tools` as a YAML list of tool names.",
        )
    required_raw = entry.get("required", True)
    if not isinstance(required_raw, bool):
        raise InvalidConfigError(
            f"`tasks[{idx}].required` must be a bool; got {type(required_raw).__name__}",
            file_path=file_path,
            field=f"/tasks/{idx}/required",
            fix="Use true or false.",
        )
    return DiscoverabilityTask(id=task_id, prompt=prompt, expected_tools=expected_tools, required=required_raw)


def run_discoverability(
    *,
    tasks: list[DiscoverabilityTask],
    adapter: str | Any,
    model: str | None,
    trials_per_task: int,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
) -> DiscoverabilityResult:
    """Run one adapter over ``tasks`` and score its tool selection.

    ``adapter`` is a slug or an object satisfying the ``Adapter`` protocol.
    When a task lists no ``expected_tools``, any tool call counts as success.
    """
    ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
    if model is not None:
        ctor_kwargs["model"] = model
    adapter_instance = get_adapter(adapter, **ctor_kwargs)

    per_task: list[TaskResult] = []
    total_cost = 0.0
    for task in tasks:
        tool_calls_per_trial: list[list[ToolCallTrace]] = []
        cost_per_trial: list[float] = []
        success_count = 0
        competing: set[str] = set()
        for _ in range(trials_per_task):
            run_result = adapter_instance.run(task.prompt)
            tool_calls_per_trial.append(list(run_result.tool_calls))
            cost_per_trial.append(run_result.cost_usd)
            total_cost += run_result.cost_usd
            called = {tc.name for tc in run_result.tool_calls}
            if task.expected_tools:
                expected = set(task.expected_tools)
                if called & expected:
                    success_count += 1
                competing.update(called - expected)
            else:
                if called:
                    success_count += 1
                competing.update(called)
        lower, upper = stats.wilson_interval(success_count, trials_per_task)
        per_task.append(
            TaskResult(
                task_id=task.id,
                task_prompt=task.prompt,
                trials_run=trials_per_task,
                success_count=success_count,
                tool_calls_per_trial=tool_calls_per_trial,
                competing_tools_picked=sorted(competing),
                cost_per_trial_usd=cost_per_trial,
                wilson_ci_lower=lower,
                wilson_ci_upper=upper,
            )
        )

    total_trials = sum(t.trials_run for t in per_task)
    total_successes = sum(t.success_count for t in per_task)
    overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0

    return DiscoverabilityResult(
        per_task_results=per_task,
        summary=DiscoverabilitySummary(
            overall_pass_rate=overall_pass_rate,
            total_cost_usd=total_cost,
            total_runtime_seconds=time.monotonic() - t_start,
        ),
        mcp_coverage="hosted_in_process",
    )
