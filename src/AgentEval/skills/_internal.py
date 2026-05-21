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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidSkillDiscoverabilityTasksError

__all__ = ["SkillDiscoverabilityTask", "load_skill_discoverability_tasks"]


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
