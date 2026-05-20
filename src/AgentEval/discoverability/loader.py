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

"""Discoverability tasks YAML loader (Story 4.4 / PRD FR10a).

Reads + validates a tasks YAML file; returns `list[DiscoverabilityTask]`
or raises `InvalidDiscoverabilityTasksError` with an RFC 6901 JSON
Pointer `field_name` per the Tier-1 setup-failure convention (parallel
to Story 4.3's `scenarios/loader.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval.discoverability.schema import DiscoverabilityTask
from AgentEval.errors import InvalidDiscoverabilityTasksError

__all__ = ["load_discoverability_tasks"]


def load_discoverability_tasks(path: str | Path) -> list[DiscoverabilityTask]:
    """Load + validate a discoverability tasks YAML file.

    Raises:
        InvalidDiscoverabilityTasksError: on any structural failure
            (file missing, wrong extension, malformed YAML, schema
            violation). `field_name` carries an RFC 6901 JSON Pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidDiscoverabilityTasksError(
            f"discoverability tasks YAML file not found: {p}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidDiscoverabilityTasksError(
            f"discoverability tasks file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidDiscoverabilityTasksError(
            f"failed to read discoverability tasks YAML: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidDiscoverabilityTasksError(
            f"discoverability tasks YAML is not valid UTF-8: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidDiscoverabilityTasksError(
            f"malformed YAML: {exc}",
            file_path=str(p),
            line_number=line + 1 if line is not None else None,
            field_name="",
            fix_suggestion="Validate the YAML with `python -c 'import yaml; yaml.safe_load(open(...))'`.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidDiscoverabilityTasksError(
            f"discoverability tasks YAML top-level must be a mapping; got {type(parsed).__name__}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Wrap the content in a top-level YAML mapping with a `tasks:` key.",
        )

    if "tasks" not in parsed:
        raise InvalidDiscoverabilityTasksError(
            "discoverability tasks YAML missing required `tasks` field",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add a top-level `tasks:` list of task entries.",
        )
    tasks_raw = parsed["tasks"]
    if not isinstance(tasks_raw, list):
        raise InvalidDiscoverabilityTasksError(
            f"`tasks` must be a list; got {type(tasks_raw).__name__}",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Format as a YAML list of task entries.",
        )
    if not tasks_raw:
        raise InvalidDiscoverabilityTasksError(
            "discoverability tasks YAML `tasks` list is empty; at least one task is required",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add at least one task entry with `id:` + `prompt:` fields.",
        )

    out: list[DiscoverabilityTask] = []
    seen_ids: dict[str, int] = {}
    for idx, entry in enumerate(tasks_raw):
        task = _parse_task(entry, idx=idx, file_path=str(p))
        # Story 4.4 code-review 3-way HIGH-A fix 2026-05-20 (Edge-cases H1 +
        # Codex HIGH + Blind MED-1): pre-edit loader accepted duplicate task
        # ids silently — two `TaskResult.task_id` rows with the same id would
        # collide downstream in the AC-DISCOVER-01 verdict matrix / CSV export.
        # Reject the second occurrence with the first occurrence's index in
        # the fix suggestion so users can locate both copies.
        if task.id in seen_ids:
            prior_idx = seen_ids[task.id]
            raise InvalidDiscoverabilityTasksError(
                f"`tasks[{idx}].id` duplicates `tasks[{prior_idx}].id` "
                f"(both = {task.id!r}); task ids must be unique per the "
                f"AC-DISCOVER-01 verdict-matrix key contract",
                file_path=str(p),
                field_name=f"/tasks/{idx}/id",
                fix_suggestion=(f"Rename `tasks[{idx}].id` to a value distinct from `tasks[{prior_idx}].id`."),
            )
        seen_ids[task.id] = idx
        out.append(task)
    return out


def _parse_task(entry: Any, *, idx: int, file_path: str) -> DiscoverabilityTask:
    """Validate one `tasks[<idx>]` entry."""
    if not isinstance(entry, dict):
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}]` must be a mapping; got {type(entry).__name__}",
            file_path=file_path,
            field_name=f"/tasks/{idx}",
            fix_suggestion="Format each task as a YAML mapping with `id:` + `prompt:` fields.",
        )
    if "id" not in entry:
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}]` missing required `id` field",
            file_path=file_path,
            field_name=f"/tasks/{idx}/id",
            fix_suggestion="Add an `id:` key with a unique task identifier.",
        )
    task_id = entry["id"]
    if not isinstance(task_id, str) or not task_id.strip():
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}].id` must be a non-empty string; got {task_id!r}",
            file_path=file_path,
            field_name=f"/tasks/{idx}/id",
            fix_suggestion="Use a non-empty string task identifier.",
        )
    if "prompt" not in entry:
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}]` missing required `prompt` field",
            file_path=file_path,
            field_name=f"/tasks/{idx}/prompt",
            fix_suggestion="Add a `prompt:` key with the natural-language task text.",
        )
    prompt = entry["prompt"]
    if not isinstance(prompt, str):
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}].prompt` must be a string; got {type(prompt).__name__}",
            file_path=file_path,
            field_name=f"/tasks/{idx}/prompt",
            fix_suggestion="Use a string prompt.",
        )
    if not prompt.strip():
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}].prompt` must be non-empty; got {prompt!r}",
            file_path=file_path,
            field_name=f"/tasks/{idx}/prompt",
            fix_suggestion="Provide the prompt text; empty prompts are rejected.",
        )
    expected_tools_raw = entry.get("expected_tools")
    if expected_tools_raw is None:
        expected_tools: list[str] = []
    else:
        if not isinstance(expected_tools_raw, list):
            raise InvalidDiscoverabilityTasksError(
                f"`tasks[{idx}].expected_tools` must be a list of strings; got {type(expected_tools_raw).__name__}",
                file_path=file_path,
                field_name=f"/tasks/{idx}/expected_tools",
                fix_suggestion="Format `expected_tools` as a YAML list of tool names.",
            )
        for jdx, name in enumerate(expected_tools_raw):
            if not isinstance(name, str):
                raise InvalidDiscoverabilityTasksError(
                    f"`tasks[{idx}].expected_tools[{jdx}]` must be a string; got {type(name).__name__}",
                    file_path=file_path,
                    field_name=f"/tasks/{idx}/expected_tools/{jdx}",
                    fix_suggestion="Use string tool names.",
                )
        expected_tools = list(expected_tools_raw)
    required_raw = entry.get("required", True)
    if not isinstance(required_raw, bool):
        raise InvalidDiscoverabilityTasksError(
            f"`tasks[{idx}].required` must be a bool; got {type(required_raw).__name__}",
            file_path=file_path,
            field_name=f"/tasks/{idx}/required",
            fix_suggestion="Use true or false.",
        )
    return DiscoverabilityTask(
        id=task_id,
        prompt=prompt,
        expected_tools=expected_tools,
        required=required_raw,
    )
