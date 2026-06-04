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

"""Internal helpers for the skills sub-library (Story 7.2).

Private module — not part of the public API. Contains:

- `SkillDiscoverabilityTask` — one task entry from the skill-discoverability
  YAML; carries `id`, `prompt`, `should_activate`.
- `load_skill_discoverability_tasks(path)` — load + validate a
  skill-discoverability tasks YAML file; returns
  `list[SkillDiscoverabilityTask]` or raises
  `InvalidSkillDiscoverabilityTasksError` per the FR59 Tier-1
  setup-failure convention.

Parallel to `src/AgentEval/discoverability/loader.py` (Story 4.4) which
handles MCP tool discoverability tasks. The skill variant adds the
`should_activate: bool` field (distinguishes "should trigger" prompts
from decoys) and raises `InvalidSkillDiscoverabilityTasksError` instead of
`InvalidDiscoverabilityTasksError`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from AgentEval._kernel.discovery import get_adapter
from AgentEval.errors import InvalidSkillDiscoverabilityTasksError

if TYPE_CHECKING:
    from AgentEval.stats.types import KeywordRun
from AgentEval.skills.types import (
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillTaskResult,
)

__all__ = [
    "SkillDiscoverabilityTask",
    "load_skill_discoverability_tasks",
    # Story 13.5 (Epic 13) — shared per-adapter helper for FR4c.
    "build_skill_discoverability_summary",
    "run_single_adapter_skill_discoverability",
]


@dataclass(frozen=True)
class SkillDiscoverabilityTask:
    """One task entry in a skill-discoverability YAML (Story 7.2 / FR4b).

    Fields:
        id: Unique string identifier for the task.
        prompt: Natural-language prompt sent to the agent.
        should_activate: True when the target skill SHOULD be triggered by
            this prompt; False for decoy prompts that should NOT activate
            the skill (false-activation rate measurement).
    """

    id: str
    prompt: str
    should_activate: bool


def load_skill_discoverability_tasks(path: str | Path) -> list[SkillDiscoverabilityTask]:
    """Load + validate a skill-discoverability tasks YAML file.

    Args:
        path: Filesystem path to the tasks YAML file.

    Returns:
        List of validated `SkillDiscoverabilityTask` instances in YAML order.

    Raises:
        InvalidSkillDiscoverabilityTasksError: On any structural failure
            (file missing, wrong extension, malformed YAML, schema violation).
            `field_name` carries an RFC 6901 JSON Pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks YAML file not found: {p}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidSkillDiscoverabilityTasksError(
            f"failed to read skill discoverability tasks YAML: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks YAML is not valid UTF-8: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidSkillDiscoverabilityTasksError(
            f"malformed YAML in skill discoverability tasks file: {exc}",
            file_path=str(p),
            line_number=line,
            field_name="",
            fix_suggestion="Fix the YAML syntax error at the indicated line.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSkillDiscoverabilityTasksError(
            "skill discoverability tasks file must be a YAML mapping at the top level",
            file_path=str(p),
            field_name="",
            fix_suggestion="Add a top-level `tasks:` key with a list of task entries.",
        )

    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise InvalidSkillDiscoverabilityTasksError(
            "skill discoverability tasks file must have a non-empty `tasks:` list",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add at least one task entry under `tasks:`.",
        )

    seen_ids: set[str] = set()
    tasks: list[SkillDiscoverabilityTask] = []
    for idx, raw_task in enumerate(raw_tasks):
        pointer_prefix = f"/tasks/{idx}"
        if not isinstance(raw_task, dict):
            raise InvalidSkillDiscoverabilityTasksError(
                f"task at index {idx} must be a YAML mapping",
                file_path=str(p),
                field_name=pointer_prefix,
                fix_suggestion="Each task must be a mapping with `id`, `prompt`, `should_activate`.",
            )

        task_id = raw_task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise InvalidSkillDiscoverabilityTasksError(
                f"task at index {idx} is missing required string field `id`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion="Add a unique string `id:` field to the task.",
            )

        if task_id in seen_ids:
            raise InvalidSkillDiscoverabilityTasksError(
                f"duplicate task id {task_id!r} at index {idx}",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion=f"Each task must have a unique `id`. Rename the duplicate '{task_id}'.",
            )
        seen_ids.add(task_id)

        prompt = raw_task.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise InvalidSkillDiscoverabilityTasksError(
                f"task '{task_id}' is missing required non-empty string field `prompt`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/prompt",
                fix_suggestion="Add a non-empty string `prompt:` field to the task.",
            )

        should_activate = raw_task.get("should_activate")
        if not isinstance(should_activate, bool):
            got = type(should_activate).__name__
            raise InvalidSkillDiscoverabilityTasksError(
                f"task '{task_id}' field `should_activate` must be a bool (true/false); got {got!r}",
                file_path=str(p),
                field_name=f"{pointer_prefix}/should_activate",
                fix_suggestion="Set `should_activate: true` or `should_activate: false` for the task.",
            )

        tasks.append(SkillDiscoverabilityTask(id=task_id, prompt=prompt, should_activate=should_activate))

    return tasks


# --------------------------------------------------------------------------- #
# Story 13.5 (Epic 13) — Shared per-adapter helpers for FR4c                  #
# --------------------------------------------------------------------------- #


def build_skill_discoverability_summary(
    task_results: list[SkillTaskResult], total_runtime: float
) -> SkillDiscoverabilityTaskSummary:
    """Compute aggregate `SkillDiscoverabilityTaskSummary` across task results.

    Story 13.5 extraction of `SkillsLibrary._build_discoverability_summary`
    (Story 7.2) to module scope so both `get_discoverability` (single
    adapter) and `get_discoverability_comparison` (Story 13.5 N-adapter)
    compute summaries identically.
    """
    total_trials = sum(r.trials_run for r in task_results)
    total_correct = sum(
        r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed) for r in task_results
    )
    activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0

    decoy_results = [r for r in task_results if not r.should_activate]
    false_act_obs = sum(r.activations_observed for r in decoy_results)
    false_act_denom = sum(r.trials_run for r in decoy_results)
    false_activation_rate = false_act_obs / false_act_denom if false_act_denom > 0 else 0.0

    should_act_results = [r for r in task_results if r.should_activate]
    missed_obs = sum(r.trials_run - r.activations_observed for r in should_act_results)
    missed_denom = sum(r.trials_run for r in should_act_results)
    missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0

    total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)

    return SkillDiscoverabilityTaskSummary(
        activation_accuracy=activation_accuracy,
        false_activation_rate=false_activation_rate,
        missed_activation_rate=missed_activation_rate,
        total_cost_usd=total_cost,
        total_runtime_seconds=total_runtime,
    )


def run_single_adapter_skill_discoverability(
    *,
    skill_name: str,
    task_list: list[SkillDiscoverabilityTask],
    adapter: str,
    model: str | None,
    trials_per_task: int,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
) -> SkillDiscoverabilityResult:
    """Run Skill discoverability against ONE adapter (Story 13.5 helper extraction).

    Internal helper extracted from `SkillsLibrary.get_discoverability`
    (Story 7.2) so the cross-adapter `Compare Discoverability` keyword
    (Story 13.5) reuses the per-adapter logic. Behavior MUST equal
    pre-refactor; verified by Story 7.2's existing tests passing
    unchanged.

    Args:
        skill_name: Pre-parsed skill name (from frontmatter). Used for
            case-insensitive substring match against `response_text`.
        task_list: Already-loaded + schema-validated skill tasks.
        adapter: Adapter name. Resolved via `_kernel.discovery.get_adapter`.
        model: Optional model identifier; forwarded to adapter ctor.
        trials_per_task: Trials per task; already validated >= 1.
        extra_adapter_kwargs: Forward-compat kwargs routed to adapter ctor.
        t_start: Wall-clock anchor (caller-provided). Single-adapter
            captures before YAML load; comparison uses a per-adapter
            anchor (comparison-level wall-clock measured separately
            per Story 13.3 HIGH-A fix).

    Returns:
        ``SkillDiscoverabilityResult`` with per-task results + summary
        + Phase-1 hardcoded ``adapter_coverage="in_process"`` (Story
        7.2 D-2 ratified shape).
    """
    adapter_cls = get_adapter(adapter)
    ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
    if model is not None:
        ctor_kwargs["model"] = model

    task_results: list[SkillTaskResult] = []
    for task in task_list:
        activations = 0
        trial_costs: list[float] = []
        for _ in range(trials_per_task):
            adapter_instance = adapter_cls(**ctor_kwargs)
            run_result = adapter_instance.run(task.prompt)
            activated = bool(skill_name) and skill_name.lower() in run_result.response_text.lower()
            if activated:
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
                competing_skills_picked={},
                cost_per_trial_usd=cost_per_trial,
            )
        )
    total_runtime = time.perf_counter() - t_start
    summary = build_skill_discoverability_summary(task_results, total_runtime)
    return SkillDiscoverabilityResult(
        per_task_results=tuple(task_results),
        summary=summary,
        adapter_coverage="in_process",
    )


# ---------------------------------------------------------------------------
# Story 14.5 / C59 / DF-7.3-S1 closure: predicate helper for the new dedicated
# `Skill.Get Activation Pass At K` keyword. Lives in this module (not in
# `stats/_internal.py`) because the predicate is skill-domain specific —
# `ActivationDecision` is a skills surface type.
# ---------------------------------------------------------------------------


def _activation_pass_predicate(run: KeywordRun) -> bool:
    """Pass-predicate for ``Skill.Get Activation Pass At K`` (Story 14.5 / C59).

    Returns ``True`` iff the wrapped keyword's result is an
    ``ActivationDecision`` with ``activated=True``. Avoids the default
    ``Stat.Get Pass At K`` predicate (``completeness == "complete"``)
    silently returning ``False`` for activation results (Story 7.3 D-1;
    C59 / DF-7.3-S1; documented as 6-epic-old silent-zero failure mode).

    Local imports defer the dependency on ``stats.types.KeywordRun`` +
    ``skills.types.ActivationDecision`` until call time to keep this module
    import-light + avoid circulars (``ActivationDecision`` lives in
    ``skills.types`` which is imported by ``skills.library`` which imports
    this module).
    """
    from AgentEval.skills.types import ActivationDecision

    return isinstance(run.result, ActivationDecision) and run.result.activated
