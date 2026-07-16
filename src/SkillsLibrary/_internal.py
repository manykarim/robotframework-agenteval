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

"""Private helpers for the Skills surface: task loading, the shared activation
heuristic, and the discoverability cohort runner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from AgentEval._core import Adapter, InvalidConfigError, get_adapter, stats
from SkillsLibrary._types import (
    ActivationDecision,
    SkillDiscoverabilityResult,
    SkillDiscoverabilitySummary,
    SkillTaskResult,
)

__all__ = [
    "SkillDiscoverabilityTask",
    "skill_activated_in",
    "resolve_skill_adapter",
    "activation_pass_predicate",
    "load_skill_discoverability_tasks",
    "run_skill_discoverability",
    "build_skill_discoverability_summary",
]


# --------------------------------------------------------------------------- #
# The one shared activation heuristic - collapsed from four copy-pasted sites. #
# --------------------------------------------------------------------------- #


def skill_activated_in(skill_name: str, response_text: str) -> bool:
    """Case-insensitive substring check: did the skill name surface in the response?

    This is the single activation heuristic every agent-mode keyword shares. An
    empty skill name never counts as activated.
    """
    return bool(skill_name) and skill_name.lower() in response_text.lower()


def resolve_skill_adapter(
    adapter: str | Adapter,
    model: str | None,
    extra_kwargs: dict[str, Any],
) -> Adapter:
    """Resolve an adapter slug (or pass through an adapter object), folding in ``model``."""
    ctor_kwargs: dict[str, Any] = dict(extra_kwargs)
    if model is not None:
        ctor_kwargs["model"] = model
    return get_adapter(adapter, **ctor_kwargs)


def activation_pass_predicate(run: stats.KeywordRun) -> bool:
    """Pass predicate for activation pass@k: the trial produced an ``ActivationDecision`` that fired."""
    return isinstance(run.result, ActivationDecision) and run.result.activated


# --------------------------------------------------------------------------- #
# Discoverability task loading.                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillDiscoverabilityTask:
    """One task from a discoverability YAML.

    ``should_activate`` distinguishes a should-trigger prompt from a decoy that
    should leave the skill quiet.
    """

    id: str
    prompt: str
    should_activate: bool


def load_skill_discoverability_tasks(path: str | Path) -> list[SkillDiscoverabilityTask]:
    """Load and validate a discoverability tasks YAML file.

    Raises ``InvalidConfigError`` on any structural failure (missing file, wrong
    extension, malformed YAML, or a schema violation), naming the offending
    location as an RFC 6901 JSON pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidConfigError(
            f"skill discoverability tasks YAML file not found: {p}",
            file_path=str(p),
            fix="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidConfigError(
            f"skill discoverability tasks file must have a .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            fix="Rename the file to use a .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidConfigError(
            f"failed to read skill discoverability tasks YAML: {exc}",
            file_path=str(p),
            fix="Verify the file is readable + UTF-8 encoded.",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise InvalidConfigError(
            f"malformed YAML in skill discoverability tasks file: {exc}",
            file_path=str(p),
            fix="Fix the YAML syntax error at the indicated line.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidConfigError(
            "skill discoverability tasks file must be a YAML mapping at the top level",
            file_path=str(p),
            fix="Add a top-level `tasks:` key with a list of task entries.",
        )

    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise InvalidConfigError(
            "skill discoverability tasks file must have a non-empty `tasks:` list",
            file_path=str(p),
            field="/tasks",
            fix="Add at least one task entry under `tasks:`.",
        )

    seen_ids: set[str] = set()
    tasks: list[SkillDiscoverabilityTask] = []
    for idx, raw_task in enumerate(raw_tasks):
        pointer = f"/tasks/{idx}"
        if not isinstance(raw_task, dict):
            raise InvalidConfigError(
                f"task at index {idx} must be a YAML mapping",
                file_path=str(p),
                field=pointer,
                fix="Each task must be a mapping with `id`, `prompt`, `should_activate`.",
            )

        task_id = raw_task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise InvalidConfigError(
                f"task at index {idx} is missing required string field `id`",
                file_path=str(p),
                field=f"{pointer}/id",
                fix="Add a unique string `id:` field to the task.",
            )
        if task_id in seen_ids:
            raise InvalidConfigError(
                f"duplicate task id {task_id!r} at index {idx}",
                file_path=str(p),
                field=f"{pointer}/id",
                fix=f"Each task must have a unique `id`. Rename the duplicate '{task_id}'.",
            )
        seen_ids.add(task_id)

        prompt = raw_task.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise InvalidConfigError(
                f"task '{task_id}' is missing required non-empty string field `prompt`",
                file_path=str(p),
                field=f"{pointer}/prompt",
                fix="Add a non-empty string `prompt:` field to the task.",
            )

        should_activate = raw_task.get("should_activate")
        if not isinstance(should_activate, bool):
            got = type(should_activate).__name__
            raise InvalidConfigError(
                f"task '{task_id}' field `should_activate` must be a bool (true/false); got {got!r}",
                file_path=str(p),
                field=f"{pointer}/should_activate",
                fix="Set `should_activate: true` or `should_activate: false` for the task.",
            )

        tasks.append(SkillDiscoverabilityTask(id=task_id, prompt=prompt, should_activate=should_activate))

    return tasks


# --------------------------------------------------------------------------- #
# Discoverability cohort runner.                                              #
# --------------------------------------------------------------------------- #


def build_skill_discoverability_summary(
    task_results: list[SkillTaskResult], total_runtime: float
) -> SkillDiscoverabilitySummary:
    """Aggregate per-task rows into a ``SkillDiscoverabilitySummary``."""
    total_trials = sum(r.trials_run for r in task_results)
    total_correct = sum(
        r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed) for r in task_results
    )
    activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0

    decoys = [r for r in task_results if not r.should_activate]
    false_obs = sum(r.activations_observed for r in decoys)
    false_denom = sum(r.trials_run for r in decoys)
    false_activation_rate = false_obs / false_denom if false_denom > 0 else 0.0

    should = [r for r in task_results if r.should_activate]
    missed_obs = sum(r.trials_run - r.activations_observed for r in should)
    missed_denom = sum(r.trials_run for r in should)
    missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0

    total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)

    return SkillDiscoverabilitySummary(
        activation_accuracy=activation_accuracy,
        false_activation_rate=false_activation_rate,
        missed_activation_rate=missed_activation_rate,
        total_cost_usd=total_cost,
        total_runtime_seconds=total_runtime,
    )


def run_skill_discoverability(
    *,
    skill_name: str,
    task_list: list[SkillDiscoverabilityTask],
    adapter: str | Adapter,
    model: str | None,
    trials_per_task: int,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
) -> SkillDiscoverabilityResult:
    """Run every task ``trials_per_task`` times and aggregate the activation outcomes."""
    adapter_obj = resolve_skill_adapter(adapter, model, extra_adapter_kwargs)

    task_results: list[SkillTaskResult] = []
    for task in task_list:
        activations = 0
        trial_costs: list[float] = []
        for _ in range(trials_per_task):
            run_result = adapter_obj.run(task.prompt)
            if skill_activated_in(skill_name, run_result.response_text):
                activations += 1
            trial_costs.append(run_result.cost_usd)
        pass_at_k = activations / trials_per_task if trials_per_task > 0 else 0.0
        cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
        task_results.append(
            SkillTaskResult(
                task_id=task.id,
                task_prompt=task.prompt,
                should_activate=task.should_activate,
                trials_run=trials_per_task,
                activations_observed=activations,
                pass_at_k=pass_at_k,
                cost_per_trial_usd=cost_per_trial,
            )
        )

    total_runtime = time.perf_counter() - t_start
    summary = build_skill_discoverability_summary(task_results, total_runtime)
    return SkillDiscoverabilityResult(per_task_results=tuple(task_results), summary=summary)
