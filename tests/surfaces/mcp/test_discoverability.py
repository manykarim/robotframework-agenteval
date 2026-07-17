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

"""Tier-3 single-adapter tool discoverability, driven with a stub adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core.errors import InvalidConfigError
from MCPLibrary import MCPLibrary

from ._helpers import StubAdapter


def _tasks_yaml(tmp_path: Path, body: str) -> str:
    p = tmp_path / "tasks.yaml"
    p.write_text(body, encoding="utf-8")
    return str(p)


TASKS = """
tasks:
  - id: t1
    prompt: find the weather in Paris
    expected_tools: [search]
  - id: t2
    prompt: delete everything
    expected_tools: [search]
"""


def test_single_adapter_discoverability_scores_tool_selection(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(tmp_path, TASKS)
    # The stub calls `search` only for the "find" prompt, so t1 passes and t2 fails.
    stub = StubAdapter(calls_for={"find": ["search"]})
    result = lib.get_tool_discoverability(tasks, adapter=stub, trials_per_task=2)

    assert 0.0 <= result.summary.overall_pass_rate <= 1.0
    by_id = {t.task_id: t for t in result.per_task_results}
    assert by_id["t1"].success_count == 2
    assert by_id["t2"].success_count == 0
    assert result.summary.overall_pass_rate == pytest.approx(0.5)
    assert result.mcp_coverage == "hosted_in_process"


def test_discoverability_records_wilson_bounds_and_cost(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(tmp_path, TASKS)
    stub = StubAdapter(calls_for={"find": ["search"]}, cost_usd=0.02)
    result = lib.get_tool_discoverability(tasks, adapter=stub, trials_per_task=2)
    t1 = next(t for t in result.per_task_results if t.task_id == "t1")
    assert 0.0 <= t1.wilson_ci_lower <= t1.wilson_ci_upper <= 1.0
    # 2 tasks x 2 trials x 0.02 each.
    assert result.summary.total_cost_usd == pytest.approx(0.08)


def test_discoverability_empty_expected_tools_is_wildcard(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(
        tmp_path,
        """
tasks:
  - id: t1
    prompt: do anything
""",
    )
    # Any tool call counts as success when a task expects no specific tool.
    stub = StubAdapter(calls_for={"anything": ["whatever"]})
    result = lib.get_tool_discoverability(tasks, adapter=stub, trials_per_task=3)
    assert result.per_task_results[0].success_count == 3


def test_discoverability_competing_tools_are_recorded(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(tmp_path, TASKS)
    # `find` yields both the expected `search` and an off-task `gossip`.
    stub = StubAdapter(calls_for={"find": ["search", "gossip"]})
    result = lib.get_tool_discoverability(tasks, adapter=stub, trials_per_task=1)
    t1 = next(t for t in result.per_task_results if t.task_id == "t1")
    assert t1.competing_tools_picked == ["gossip"]


def test_discoverability_requires_tasks_path() -> None:
    lib = MCPLibrary()
    with pytest.raises(ValueError):
        lib.get_tool_discoverability("", adapter=StubAdapter())


def test_discoverability_rejects_bad_trials(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(tmp_path, TASKS)
    with pytest.raises(ValueError):
        lib.get_tool_discoverability(tasks, adapter=StubAdapter(), trials_per_task=0)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(
        tmp_path,
        """
tasks:
  - id: dup
    prompt: a
  - id: dup
    prompt: b
""",
    )
    with pytest.raises(InvalidConfigError):
        lib.get_tool_discoverability(tasks, adapter=StubAdapter())


def test_loader_rejects_missing_tasks_key(tmp_path: Path) -> None:
    lib = MCPLibrary()
    tasks = _tasks_yaml(tmp_path, "other: 1\n")
    with pytest.raises(InvalidConfigError) as exc:
        lib.get_tool_discoverability(tasks, adapter=StubAdapter())
    assert exc.value.field == "/tasks"
