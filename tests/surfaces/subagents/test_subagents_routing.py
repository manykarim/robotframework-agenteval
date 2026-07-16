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

"""Tier-3 routing keywords, driven with a fake adapter (no real LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from AgentEval._core import (
    MissingExtraError,
    SubagentDelegationError,
    deterministic_scope,
    get_keyword_tier,
)
from SubagentsLibrary import SubagentsLibrary
from SubagentsLibrary.types import DelegationDecision, SubagentRoutingResult

from ._fakes import FakeRoutingAdapter


def test_should_delegate_to_passes_when_routed() -> None:
    adapter = FakeRoutingAdapter({"route please": "test-writer"})
    SubagentsLibrary().should_delegate_to("route please", "test-writer", adapter=adapter)


def test_should_delegate_to_fails_when_not_routed() -> None:
    adapter = FakeRoutingAdapter({"route please": "docs-writer"})
    with pytest.raises(SubagentDelegationError):
        SubagentsLibrary().should_delegate_to("route please", "test-writer", adapter=adapter)


def test_get_delegation_decision_reports_without_raising() -> None:
    adapter = FakeRoutingAdapter({"p": "docs-writer"}, cost_usd=0.01)
    decision = SubagentsLibrary().get_delegation_decision("p", "test-writer", adapter=adapter)
    assert isinstance(decision, DelegationDecision)
    assert decision.delegated is False
    assert decision.cost_usd == 0.01
    assert [d.subagent for d in decision.delegations] == ["docs-writer"]


def test_get_delegation_decision_delegated_true_on_hit() -> None:
    adapter = FakeRoutingAdapter({"p": "test-writer"})
    decision = SubagentsLibrary().get_delegation_decision("p", "test-writer", adapter=adapter)
    assert decision.delegated is True


def _write_tasks(tmp_path: Path) -> Path:
    path = tmp_path / "routing.yaml"
    path.write_text(
        "tasks:\n"
        "  - id: t1\n    prompt: route to test\n    expected_subagent: test-writer\n"
        "  - id: t2\n    prompt: route to docs\n    expected_subagent: db-admin\n",
        encoding="utf-8",
    )
    return path


def test_get_routing_accuracy_reports_fraction_and_ci(tmp_path: Path) -> None:
    adapter = FakeRoutingAdapter({"route to test": "test-writer", "route to docs": "docs-writer"}, cost_usd=0.02)
    result = SubagentsLibrary().get_routing_accuracy(_write_tasks(tmp_path), adapter=adapter, trials_per_task=2)
    assert isinstance(result, SubagentRoutingResult)
    assert result.summary.total_trials == 4
    assert result.summary.total_matches == 2
    assert result.summary.routing_accuracy == pytest.approx(0.5)
    assert 0.0 <= result.summary.ci_lower <= 0.5 <= result.summary.ci_upper <= 1.0
    assert result.summary.total_cost_usd == pytest.approx(0.08)

    by_id = {t.task_id: t for t in result.per_task_results}
    assert by_id["t1"].matches_observed == 2
    assert by_id["t1"].pass_at_k == pytest.approx(1.0)
    assert by_id["t2"].matches_observed == 0
    assert by_id["t2"].pass_at_k == pytest.approx(0.0)


def test_get_routing_accuracy_rejects_zero_trials(tmp_path: Path) -> None:
    adapter = FakeRoutingAdapter({})
    with pytest.raises(ValueError):
        SubagentsLibrary().get_routing_accuracy(_write_tasks(tmp_path), adapter=adapter, trials_per_task=0)


def test_get_routing_accuracy_bad_tasks_file(tmp_path: Path) -> None:
    from AgentEval._core import InvalidConfigError

    path = tmp_path / "empty.yaml"
    path.write_text("tasks: []\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        SubagentsLibrary().get_routing_accuracy(path, adapter=FakeRoutingAdapter({}))


def test_routing_keywords_are_tier_3() -> None:
    assert get_keyword_tier(SubagentsLibrary.should_delegate_to) == 3
    assert get_keyword_tier(SubagentsLibrary.get_delegation_decision) == 3
    assert get_keyword_tier(SubagentsLibrary.get_routing_accuracy) == 3


def test_generic_adapter_missing_llm_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "litellm", None)
    with pytest.raises(MissingExtraError):
        SubagentsLibrary().get_delegation_decision("p", "x", adapter="generic", model="gpt-4o")


def test_generic_adapter_blocked_in_deterministic_scope() -> None:
    from AgentEval._core import TierViolationError

    with deterministic_scope(), pytest.raises(TierViolationError):
        SubagentsLibrary().should_delegate_to("p", "x", adapter="generic", model="gpt-4o")
