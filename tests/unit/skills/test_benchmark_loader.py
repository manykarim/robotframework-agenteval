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

"""Unit tests for `load_skill_benchmark_tasks` (add-skill-ab-benchmark / Task 1.4).

Covers: valid mixed-mode cohort, both grading modes on one task, neither mode
and no default, duplicate ids, missing file, non-YAML extension, malformed
YAML, and nullish-field fuzz per `feedback_nullish_input_fuzz_checklist`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.errors import InvalidSkillBenchmarkTasksError
from AgentEval.skills._benchmark import SkillBenchmarkTask, load_skill_benchmark_tasks


def _write(tmp_path: Path, text: str, name: str = "tasks.yaml") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_mixed_mode_cohort_loads_in_order(tmp_path: Path) -> None:
    """2 expected_content + 1 rubric task load in file order (spec scenario)."""
    p = _write(
        tmp_path,
        """
tasks:
  - id: a
    prompt: first
    expected_content: ["hello"]
  - id: b
    prompt: second
    expected_content: ["x", "y"]
  - id: c
    prompt: third
    rubric: some-rubric.md
""",
    )
    tasks = load_skill_benchmark_tasks(p)
    assert [t.id for t in tasks] == ["a", "b", "c"]
    assert tasks[0].grading_mode == "expected_content"
    assert tasks[0].expected_content == ("hello",)
    assert tasks[1].expected_content == ("x", "y")
    assert tasks[2].grading_mode == "judge"
    assert tasks[2].rubric_path == "some-rubric.md"


def test_defaults_rubric_fallback(tmp_path: Path) -> None:
    """A task with no grading mode inherits `defaults.rubric`."""
    p = _write(
        tmp_path,
        """
defaults:
  rubric: shared.md
tasks:
  - id: a
    prompt: p1
  - id: b
    prompt: p2
    expected_content: ["z"]
""",
    )
    tasks = load_skill_benchmark_tasks(p)
    assert tasks[0].rubric_path == "shared.md"
    assert tasks[0].grading_mode == "judge"
    assert tasks[1].grading_mode == "expected_content"


def test_task_with_both_grading_modes_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: a
    prompt: p
    expected_content: ["x"]
    rubric: r.md
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError) as exc:
        load_skill_benchmark_tasks(p)
    assert "/tasks/0" in str(exc.value)
    assert "both" in str(exc.value).lower()


def test_task_with_no_mode_and_no_default_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: a
    prompt: p
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="no grading mode"):
        load_skill_benchmark_tasks(p)


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: dup
    prompt: p1
    expected_content: ["a"]
  - id: dup
    prompt: p2
    expected_content: ["b"]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="duplicate task id 'dup'"):
        load_skill_benchmark_tasks(p)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="not found"):
        load_skill_benchmark_tasks(tmp_path / "nope.yaml")


def test_non_yaml_extension_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks: []", name="tasks.txt")
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="extension"):
        load_skill_benchmark_tasks(p)


def test_malformed_yaml_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks: [unclosed")
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="malformed YAML"):
        load_skill_benchmark_tasks(p)


def test_empty_tasks_list_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "tasks: []")
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="non-empty"):
        load_skill_benchmark_tasks(p)


def test_top_level_not_mapping_rejected(tmp_path: Path) -> None:
    p = _write(tmp_path, "- just\n- a\n- list")
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="mapping at the top level"):
        load_skill_benchmark_tasks(p)


@pytest.mark.parametrize("bad_id", ["", "null", "false", "zero"])
def test_nullish_id_fuzz(tmp_path: Path, bad_id: str) -> None:
    """id: None / "" / False / 0 / missing all rejected (nullish fuzz checklist)."""
    id_line = {
        "": 'id: ""',
        "null": "id: null",
        "false": "id: false",
        "zero": "id: 0",
    }[bad_id]
    p = _write(
        tmp_path,
        f"""
tasks:
  - {id_line}
    prompt: p
    expected_content: ["x"]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="`id`"):
        load_skill_benchmark_tasks(p)


def test_missing_id_key_fuzz(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - prompt: p
    expected_content: ["x"]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="`id`"):
        load_skill_benchmark_tasks(p)


@pytest.mark.parametrize("prompt_line", ['prompt: ""', "prompt: null", "prompt: false", "prompt: 0"])
def test_nullish_prompt_fuzz(tmp_path: Path, prompt_line: str) -> None:
    p = _write(
        tmp_path,
        f"""
tasks:
  - id: a
    {prompt_line}
    expected_content: ["x"]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="`prompt`"):
        load_skill_benchmark_tasks(p)


def test_expected_content_empty_list_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: a
    prompt: p
    expected_content: []
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="non-empty list"):
        load_skill_benchmark_tasks(p)


def test_expected_content_non_string_item_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
tasks:
  - id: a
    prompt: p
    expected_content: [123]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="expected_content"):
        load_skill_benchmark_tasks(p)


def test_defaults_not_mapping_rejected(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
defaults: not-a-mapping
tasks:
  - id: a
    prompt: p
    expected_content: ["x"]
""",
    )
    with pytest.raises(InvalidSkillBenchmarkTasksError, match="/defaults"):
        load_skill_benchmark_tasks(p)


def test_repo_fixture_expected_content_loads() -> None:
    """The committed expected_content fixture loads cleanly."""
    fixture = Path(__file__).parent.parent.parent / "fixtures" / "benchmark" / "tasks-expected-content.yaml"
    tasks = load_skill_benchmark_tasks(fixture)
    assert len(tasks) == 4
    assert all(isinstance(t, SkillBenchmarkTask) for t in tasks)
    assert all(t.grading_mode == "expected_content" for t in tasks)
