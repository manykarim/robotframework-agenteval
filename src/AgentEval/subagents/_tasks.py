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

"""Routing-tasks YAML loader for `Subagent.Get Routing Accuracy`.

Private module — not part of the public API. Mirrors the
skill-discoverability tasks loader
(`skills/_internal.load_skill_discoverability_tasks`), but with the routing
schema (`tasks: [{id, prompt, expected_subagent}]`) and its own error class
(`InvalidSubagentRoutingTasksError`) per design Decision 7 — the two
capabilities' schemas are deliberately NOT coupled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidSubagentRoutingTasksError

__all__ = [
    "SubagentRoutingTask",
    "load_subagent_routing_tasks",
]


@dataclass(frozen=True)
class SubagentRoutingTask:
    """One task entry in a subagent routing-tasks YAML.

    Fields:
        id: Unique string identifier for the task.
        prompt: Natural-language prompt sent to the orchestrator agent.
        expected_subagent: The subagent the orchestrator SHOULD delegate to.
    """

    id: str
    prompt: str
    expected_subagent: str


def load_subagent_routing_tasks(path: str | Path) -> list[SubagentRoutingTask]:
    """Load + validate a subagent routing-tasks YAML file.

    Args:
        path: Filesystem path to the tasks YAML file.

    Returns:
        List of validated `SubagentRoutingTask` instances in YAML order.

    Raises:
        InvalidSubagentRoutingTasksError: On any structural failure (file
            missing, wrong extension, malformed YAML, schema violation).
            `field_name` carries an RFC 6901 JSON Pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidSubagentRoutingTasksError(
            f"subagent routing tasks YAML file not found: {p}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidSubagentRoutingTasksError(
            f"subagent routing tasks file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidSubagentRoutingTasksError(
            f"failed to read subagent routing tasks YAML: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidSubagentRoutingTasksError(
            f"subagent routing tasks YAML is not valid UTF-8: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidSubagentRoutingTasksError(
            f"malformed YAML in subagent routing tasks file: {exc}",
            file_path=str(p),
            line_number=line,
            field_name="",
            fix_suggestion="Fix the YAML syntax error at the indicated line.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSubagentRoutingTasksError(
            "subagent routing tasks file must be a YAML mapping at the top level",
            file_path=str(p),
            field_name="",
            fix_suggestion="Add a top-level `tasks:` key with a list of task entries.",
        )

    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise InvalidSubagentRoutingTasksError(
            "subagent routing tasks file must have a non-empty `tasks:` list",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add at least one task entry under `tasks:`.",
        )

    seen_ids: set[str] = set()
    tasks: list[SubagentRoutingTask] = []
    for idx, raw_task in enumerate(raw_tasks):
        pointer_prefix = f"/tasks/{idx}"
        if not isinstance(raw_task, dict):
            raise InvalidSubagentRoutingTasksError(
                f"task at index {idx} must be a YAML mapping",
                file_path=str(p),
                field_name=pointer_prefix,
                fix_suggestion="Each task must be a mapping with `id`, `prompt`, `expected_subagent`.",
            )

        task_id = raw_task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise InvalidSubagentRoutingTasksError(
                f"task at index {idx} is missing required string field `id`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion="Add a unique string `id:` field to the task.",
            )

        if task_id in seen_ids:
            raise InvalidSubagentRoutingTasksError(
                f"duplicate task id {task_id!r} at index {idx}",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion=f"Each task must have a unique `id`. Rename the duplicate '{task_id}'.",
            )
        seen_ids.add(task_id)

        prompt = raw_task.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise InvalidSubagentRoutingTasksError(
                f"task '{task_id}' is missing required non-empty string field `prompt`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/prompt",
                fix_suggestion="Add a non-empty string `prompt:` field to the task.",
            )

        expected_subagent = raw_task.get("expected_subagent")
        if not isinstance(expected_subagent, str) or not expected_subagent:
            raise InvalidSubagentRoutingTasksError(
                f"task '{task_id}' is missing required non-empty string field `expected_subagent`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/expected_subagent",
                fix_suggestion="Add a non-empty string `expected_subagent:` field to the task.",
            )

        tasks.append(SubagentRoutingTask(id=task_id, prompt=prompt, expected_subagent=expected_subagent))

    return tasks
