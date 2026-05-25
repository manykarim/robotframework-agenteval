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

"""Unit tests for `CohortHeatmap` (Story 8b.2 AC-8b.2.7)."""

from __future__ import annotations

from AgentEval._heatmap.models import CohortHeatmap
from AgentEval.discoverability.schema import (
    DiscoverabilityResult,
    DiscoverabilitySummary,
    TaskResult,
)


def _task(task_id: str, success: int, trials: int) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        task_prompt=f"prompt for {task_id}",
        trials_run=trials,
        success_count=success,
    )


def _result(*tasks: TaskResult) -> DiscoverabilityResult:
    return DiscoverabilityResult(
        per_task_results=list(tasks),
        summary=DiscoverabilitySummary(overall_pass_rate=0.0, total_cost_usd=0.0, total_runtime_seconds=0.0),
        mcp_coverage="hosted_in_process",
    )


def test_empty_heatmap_renders_placeholder() -> None:
    """AC-8b.2.7 #1: empty per_task_results → empty heatmap."""
    h = CohortHeatmap.from_discoverability(_result())
    assert h.tasks == ()
    assert h.as_ascii() == "(empty heatmap)"
    assert h.as_dict() == {}


def test_single_task_single_model_ascii() -> None:
    """AC-8b.2.7 #2: 1 task / 1 model → 1x1 table with box-drawing chars."""
    h = CohortHeatmap.from_discoverability(_result(_task("t1", 8, 10)))
    ascii_out = h.as_ascii()
    assert "│" in ascii_out
    assert "┌" in ascii_out
    assert "└" in ascii_out
    assert "0.80" in ascii_out
    assert "t1" in ascii_out


def test_multi_task_single_model() -> None:
    """AC-8b.2.7 #3: N tasks / 1 model → Nx1 table."""
    h = CohortHeatmap.from_discoverability(_result(_task("t1", 10, 10), _task("t2", 5, 10), _task("t3", 0, 10)))
    assert h.tasks == ("t1", "t2", "t3")
    ascii_out = h.as_ascii()
    assert "1.00" in ascii_out
    assert "0.50" in ascii_out
    assert "0.00" in ascii_out


def test_as_dict_roundtrip() -> None:
    """AC-8b.2.7 #4: `.as_dict()` returns the expected nested-dict shape."""
    h = CohortHeatmap.from_discoverability(
        _result(_task("alpha", 7, 10), _task("beta", 3, 10)),
        model_name="claude-sonnet",
    )
    d = h.as_dict()
    assert d == {
        "alpha": {"claude-sonnet": 0.7},
        "beta": {"claude-sonnet": 0.3},
    }


def test_ascii_pass_at_k_2_decimal_format() -> None:
    """AC-8b.2.7 #5: cell values rendered as 2-decimal floats."""
    h = CohortHeatmap.from_discoverability(_result(_task("t", 1, 3)))
    # 1/3 = 0.333... → rendered as "0.33".
    assert "0.33" in h.as_ascii()


def test_custom_model_name_in_ascii_header() -> None:
    """Bonus: explicit `model_name` shows in the header column."""
    h = CohortHeatmap.from_discoverability(_result(_task("t", 5, 10)), model_name="gpt-5")
    ascii_out = h.as_ascii()
    assert "gpt-5" in ascii_out
