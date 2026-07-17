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

"""Tier-3 skill discoverability scoring over a task cohort."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError
from SkillsLibrary import SkillsLibrary

from .conftest import PromptRoutedAdapter

TASKS_YAML = """tasks:
  - id: should-fire
    prompt: Find news about the release
    should_activate: true
  - id: decoy
    prompt: Add two numbers together
    should_activate: false
"""


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def tasks_file(tmp_path: Path) -> Path:
    path = tmp_path / "tasks.yaml"
    path.write_text(TASKS_YAML, encoding="utf-8")
    return path


def test_discoverability_returns_score(lib: SkillsLibrary, skill_file: Path, tasks_file: Path) -> None:
    # Scenario: Score discoverability -> returns a discoverability score.
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    result = lib.get_discoverability(skill_file, tasks_file, adapter=adapter, trials_per_task=3)
    assert result.summary is not None
    # Should-fire task triggers on "news"; decoy never triggers -> perfect accuracy.
    assert result.summary.activation_accuracy == 1.0
    assert result.summary.false_activation_rate == 0.0
    assert result.summary.missed_activation_rate == 0.0
    assert len(result.per_task_results) == 2


def test_discoverability_per_task_rows(lib: SkillsLibrary, skill_file: Path, tasks_file: Path) -> None:
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    result = lib.get_discoverability(skill_file, tasks_file, adapter=adapter, trials_per_task=4)
    by_id = {r.task_id: r for r in result.per_task_results}
    assert by_id["should-fire"].activations_observed == 4
    assert by_id["should-fire"].pass_at_k == 1.0
    assert by_id["decoy"].activations_observed == 0
    assert by_id["decoy"].pass_at_k == 0.0


def test_discoverability_detects_false_activation(lib: SkillsLibrary, skill_file: Path, tmp_path: Path) -> None:
    # A skill that fires even on the decoy: trigger word appears in both prompts.
    tasks = tmp_path / "greedy.yaml"
    tasks.write_text(
        "tasks:\n"
        "  - id: real\n    prompt: search the web\n    should_activate: true\n"
        "  - id: decoy\n    prompt: search my memory\n    should_activate: false\n",
        encoding="utf-8",
    )
    adapter = PromptRoutedAdapter("web-search", trigger="search")
    result = lib.get_discoverability(skill_file, tasks, adapter=adapter, trials_per_task=2)
    assert result.summary is not None
    assert result.summary.false_activation_rate == 1.0


def test_discoverability_rejects_zero_trials(lib: SkillsLibrary, skill_file: Path, tasks_file: Path) -> None:
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    with pytest.raises(ValueError):
        lib.get_discoverability(skill_file, tasks_file, adapter=adapter, trials_per_task=0)


def test_discoverability_rejects_bad_tasks_file(lib: SkillsLibrary, skill_file: Path, tmp_path: Path) -> None:
    tasks = tmp_path / "empty.yaml"
    tasks.write_text("tasks: []\n", encoding="utf-8")
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    with pytest.raises(InvalidConfigError):
        lib.get_discoverability(skill_file, tasks, adapter=adapter)
