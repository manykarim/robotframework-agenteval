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

"""Unit tests for discoverability tasks loader (Story 4.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.discoverability.loader import load_discoverability_tasks
from AgentEval.discoverability.schema import DiscoverabilityTask
from AgentEval.errors import InvalidDiscoverabilityTasksError


def _write(tmp_path: Path, content: str, name: str = "tasks.yaml") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_load_minimal_task(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: t1\n    prompt: hi\n")
    tasks = load_discoverability_tasks(p)
    assert len(tasks) == 1
    assert tasks[0].id == "t1"
    assert tasks[0].prompt == "hi"
    assert tasks[0].expected_tools == []
    assert tasks[0].required is True


def test_load_full_task(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: t1
    prompt: search for X
    expected_tools:
      - search
      - find
    required: false
""",
    )
    tasks = load_discoverability_tasks(p)
    assert tasks[0].expected_tools == ["search", "find"]
    assert tasks[0].required is False


def test_load_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(InvalidDiscoverabilityTasksError, match="not found"):
        load_discoverability_tasks(tmp_path / "missing.yaml")


def test_load_wrong_extension(tmp_path: Path) -> None:
    p = tmp_path / "tasks.txt"
    p.write_text("tasks:\n  - id: t\n    prompt: hi\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="extension"):
        load_discoverability_tasks(p)


def test_load_malformed_yaml(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: 'unclosed\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="malformed YAML"):
        load_discoverability_tasks(p)


def test_load_non_utf8(tmp_path: Path) -> None:
    p = tmp_path / "tasks.yaml"
    p.write_bytes(b"\xff\xff invalid utf8 \xfe\xfe")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="UTF-8"):
        load_discoverability_tasks(p)


def test_load_top_level_not_mapping(tmp_path: Path) -> None:
    p = _write(tmp_path, "- just_a_list\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a mapping"):
        load_discoverability_tasks(p)


def test_load_missing_tasks_field(tmp_path: Path) -> None:
    p = _write(tmp_path, "some_other_field: x\n")
    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
        load_discoverability_tasks(p)
    assert exc_info.value.field_name == "/tasks"


def test_load_tasks_not_list(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks: not_a_list\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a list"):
        load_discoverability_tasks(p)


def test_load_empty_tasks(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks: []\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="empty"):
        load_discoverability_tasks(p)


def test_load_task_missing_id(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - prompt: hi\n")
    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
        load_discoverability_tasks(p)
    assert exc_info.value.field_name == "/tasks/0/id"


def test_load_task_empty_id(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: ''\n    prompt: hi\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty"):
        load_discoverability_tasks(p)


def test_load_task_missing_prompt(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: t1\n")
    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
        load_discoverability_tasks(p)
    assert exc_info.value.field_name == "/tasks/0/prompt"


def test_load_task_empty_prompt_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, 'tasks:\n  - id: t1\n    prompt: ""\n')
    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty"):
        load_discoverability_tasks(p)


def test_load_task_non_string_id_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: 42\n    prompt: hi\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty string"):
        load_discoverability_tasks(p)


def test_load_task_expected_tools_not_list(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: t\n    prompt: hi\n    expected_tools: search\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="list of strings"):
        load_discoverability_tasks(p)


def test_load_task_expected_tools_non_string_element(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: t\n    prompt: hi\n    expected_tools:\n      - 42\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a string"):
        load_discoverability_tasks(p)


def test_load_task_required_not_bool(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks:\n  - id: t\n    prompt: hi\n    required: yes-please\n")
    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a bool"):
        load_discoverability_tasks(p)


def test_load_duplicate_task_ids_rejected(tmp_path: Path) -> None:
    """Story 4.4 code-review 3-way HIGH-A fix 2026-05-20 (Edge-cases H1 +
    Codex HIGH + Blind MED-1): pre-edit accepted duplicate task ids
    silently. Per AC-DISCOVER-01, task_id is the verdict-matrix key —
    duplicates collide downstream. Loader now rejects with RFC 6901
    field_name pointing at the second occurrence.
    """
    p = _write(
        tmp_path,
        "tasks:\n  - id: dup\n    prompt: first\n  - id: dup\n    prompt: second\n",
    )
    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
        load_discoverability_tasks(p)
    assert exc_info.value.field_name == "/tasks/1/id"
    assert "duplicates" in str(exc_info.value).lower()
    # Fix suggestion should reference both indices.
    assert "tasks[0].id" in (exc_info.value.fix_suggestion or "")
    assert "tasks[1].id" in (exc_info.value.fix_suggestion or "")


def test_load_bundled_fixture() -> None:
    """The vendored Story 4.4 bundled fixture loads cleanly."""
    p = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    tasks = load_discoverability_tasks(p)
    assert len(tasks) == 3
    ids = {t.id for t in tasks}
    assert ids == {"echo_simple", "echo_with_context", "echo_indirect"}


def test_discoverability_task_dataclass_frozen() -> None:
    import dataclasses

    t = DiscoverabilityTask(id="t", prompt="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.id = "mutated"  # type: ignore[misc]
