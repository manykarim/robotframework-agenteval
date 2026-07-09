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

"""Unit tests for `Subagent.Get Routing Accuracy` (task 6.5).

2-task cohort scenario from the spec (routing_accuracy == 0.5), malformed-YAML
`InvalidSubagentRoutingTasksError`, `trials_per_task=0` ValueError, and polling
rejection. Routing-tasks YAML fixtures live under `tests/fixtures/subagents/routing/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import InvalidSubagentRoutingTasksError, PollingDisallowedError
from AgentEval.subagents._tasks import load_subagent_routing_tasks
from AgentEval.subagents.library import SubagentsLibrary
from AgentEval.subagents.types import SubagentRoutingResult
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "subagents" / "routing"
TWO_TASK_YAML = FIXTURES / "two-task-routing.yaml"
MALFORMED_YAML = FIXTURES / "missing-expected-subagent.yaml"


def _always_reviewer() -> type[InProcessAdapter]:
    class _Stub(InProcessAdapter):
        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="delegating to code-reviewer",
                tool_calls=[
                    ToolCallTrace(
                        name="Task",
                        args={"subagent_type": "code-reviewer", "prompt": prompt},
                        result=None,
                        error=None,
                        latency_ms=1.0,
                        source="adapter",
                        gen_ai_tool_call_id="d0",
                        sequence_index=0,
                    )
                ],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.01,
                trace_id="s" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SubagentsLibrary:
    return SubagentsLibrary()


def test_get_routing_accuracy_is_tier_3() -> None:
    func = SubagentsLibrary.get_routing_accuracy
    assert get_keyword_tier(func) == 3
    assert tier_badge(3) in (func.__doc__ or "")


def test_cohort_aggregates_routing_accuracy_half(lib: SubagentsLibrary) -> None:
    register_adapter("stub_routing_half", _always_reviewer())
    result = lib.get_routing_accuracy(TWO_TASK_YAML, adapter="stub_routing_half", trials_per_task=2)
    assert isinstance(result, SubagentRoutingResult)
    assert len(result.per_task_results) == 2
    assert result.summary.routing_accuracy == 0.5
    assert result.summary.total_trials == 4
    assert result.summary.total_matches == 2
    # Task 1 (expects code-reviewer) all pass; task 2 (expects test-writer) all miss.
    by_id = {t.task_id: t for t in result.per_task_results}
    assert by_id["review-task"].pass_at_k == 1.0
    assert by_id["test-task"].pass_at_k == 0.0


def test_malformed_yaml_raises(lib: SubagentsLibrary) -> None:
    register_adapter("stub_routing_malformed", _always_reviewer())
    with pytest.raises(InvalidSubagentRoutingTasksError) as exc_info:
        lib.get_routing_accuracy(MALFORMED_YAML, adapter="stub_routing_malformed")
    assert str(MALFORMED_YAML) in str(exc_info.value)


def test_trials_per_task_zero_raises(lib: SubagentsLibrary) -> None:
    register_adapter("stub_routing_zero", _always_reviewer())
    with pytest.raises(ValueError):
        lib.get_routing_accuracy(TWO_TASK_YAML, adapter="stub_routing_zero", trials_per_task=0)


def test_polling_rejected(lib: SubagentsLibrary) -> None:
    with pytest.raises(PollingDisallowedError):
        lib.get_routing_accuracy(TWO_TASK_YAML, adapter="stub_routing_half", polling=2.0)


# --------------------------------------------------------------------------- #
# Routing-tasks loader                                                        #
# --------------------------------------------------------------------------- #


def test_loader_reads_valid_tasks() -> None:
    tasks = load_subagent_routing_tasks(TWO_TASK_YAML)
    assert [t.id for t in tasks] == ["review-task", "test-task"]
    assert tasks[0].expected_subagent == "code-reviewer"


def test_loader_missing_expected_subagent_raises() -> None:
    with pytest.raises(InvalidSubagentRoutingTasksError) as exc_info:
        load_subagent_routing_tasks(MALFORMED_YAML)
    assert exc_info.value.field_name == "/tasks/1/expected_subagent"


def test_loader_rejects_non_list_tasks(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("tasks: not-a-list\n")
    with pytest.raises(InvalidSubagentRoutingTasksError):
        load_subagent_routing_tasks(p)


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidSubagentRoutingTasksError):
        load_subagent_routing_tasks(tmp_path / "nope.yaml")


def test_loader_rejects_wrong_extension(tmp_path: Path) -> None:
    p = tmp_path / "tasks.txt"
    p.write_text("tasks: []\n")
    with pytest.raises(InvalidSubagentRoutingTasksError):
        load_subagent_routing_tasks(p)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    p = tmp_path / "dup.yaml"
    p.write_text(
        "tasks:\n"
        "  - id: dup\n    prompt: a\n    expected_subagent: x\n"
        "  - id: dup\n    prompt: b\n    expected_subagent: y\n"
    )
    with pytest.raises(InvalidSubagentRoutingTasksError):
        load_subagent_routing_tasks(p)
