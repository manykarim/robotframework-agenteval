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

"""Unit tests for `Skill.Get Discoverability` + `Skill.Should Activate For` (Story 7.2).

Covers AC-7.2.1 through AC-7.2.11 (14 tests):
  - AC-7.2.1: load_skill_discoverability_tasks loader + SkillDiscoverabilityTask
  - AC-7.2.2: SkillTaskResult + SkillDiscoverabilityTaskSummary + SkillDiscoverabilityResult dataclasses
  - AC-7.2.3: SkillDidNotActivateError structured fields
  - AC-7.2.4: get_discoverability tier-3 + returns SkillDiscoverabilityResult
  - AC-7.2.5: should_activate_for tier-2 + passes / raises SkillDidNotActivateError
  - AC-7.2.6: polling= raises PollingDisallowedError on both keywords
  - AC-7.2.7: SkillDidNotActivateError carries 5 diagnostic fields
  - AC-7.2.9: InvalidSkillDiscoverabilityTasksError for invalid YAML
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import (
    InvalidSkillDiscoverabilityTasksError,
    PollingDisallowedError,
    SkillDidNotActivateError,
)
from AgentEval.skills._internal import SkillDiscoverabilityTask, load_skill_discoverability_tasks
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import (
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillTaskResult,
)
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILLS_DIR = FIXTURES_DIR / "skills"
DISCOVERABILITY_DIR = FIXTURES_DIR / "discoverability"

SEARCH_SKILL = SKILLS_DIR / "example-search.md"
# example-search.md has `name: example-search-skill`
SKILL_NAME = "example-search-skill"
SKILL_TASKS = DISCOVERABILITY_DIR / "skill-tasks-basic.yaml"


def _make_stub(response_text: str, cost: float = 0.001, latency: float = 0.002) -> type[InProcessAdapter]:
    """Build a one-shot stub adapter returning a scripted AgentRunResult."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=latency,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


# --------------------------------------------------------------------------- #
# AC-7.2.1: SkillDiscoverabilityTask + load_skill_discoverability_tasks        #
# --------------------------------------------------------------------------- #


def test_load_skill_discoverability_tasks_returns_correct_list() -> None:
    """load_skill_discoverability_tasks returns a list of SkillDiscoverabilityTask instances."""
    tasks = load_skill_discoverability_tasks(SKILL_TASKS)
    assert isinstance(tasks, list)
    assert len(tasks) == 5
    assert all(isinstance(t, SkillDiscoverabilityTask) for t in tasks)
    # First 3 should_activate=True, last 2 False
    assert tasks[0].should_activate is True
    assert tasks[3].should_activate is False
    assert tasks[4].should_activate is False


def test_load_skill_discoverability_tasks_invalid_missing_should_activate(tmp_path: Path) -> None:
    """Missing should_activate field raises InvalidSkillDiscoverabilityTasksError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        "tasks:\n  - id: task1\n    prompt: some prompt\n"
        # should_activate missing
    )
    with pytest.raises(InvalidSkillDiscoverabilityTasksError, match="should_activate"):
        load_skill_discoverability_tasks(bad_yaml)


def test_load_skill_discoverability_tasks_duplicate_id_raises(tmp_path: Path) -> None:
    """Duplicate task id raises InvalidSkillDiscoverabilityTasksError."""
    bad_yaml = tmp_path / "dup.yaml"
    bad_yaml.write_text(
        "tasks:\n"
        "  - id: t1\n"
        "    prompt: first\n"
        "    should_activate: true\n"
        "  - id: t1\n"
        "    prompt: second\n"
        "    should_activate: false\n"
    )
    with pytest.raises(InvalidSkillDiscoverabilityTasksError, match="duplicate"):
        load_skill_discoverability_tasks(bad_yaml)


# --------------------------------------------------------------------------- #
# AC-7.2.2: SkillTaskResult + SkillDiscoverabilityTaskSummary dataclasses      #
# --------------------------------------------------------------------------- #


def test_skill_task_result_is_frozen_dataclass() -> None:
    """SkillTaskResult is a frozen dataclass with the required fields."""
    from dataclasses import FrozenInstanceError

    r = SkillTaskResult(
        task_id="t1",
        task_prompt="prompt",
        should_activate=True,
        trials_run=3,
        activations_observed=2,
        pass_at_k=0.667,
        competing_skills_picked={},
        cost_per_trial_usd=0.001,
    )
    assert r.task_id == "t1"
    assert r.activations_observed == 2
    with pytest.raises(FrozenInstanceError):
        r.task_id = "t2"  # type: ignore[misc]


def test_skill_discoverability_result_is_frozen_dataclass() -> None:
    """SkillDiscoverabilityResult is a frozen dataclass with per_task_results + summary + adapter_coverage."""
    from dataclasses import FrozenInstanceError

    task_r = SkillTaskResult(
        task_id="t1",
        task_prompt="p",
        should_activate=True,
        trials_run=1,
        activations_observed=1,
        pass_at_k=1.0,
        competing_skills_picked={},
        cost_per_trial_usd=0.0,
    )
    summary = SkillDiscoverabilityTaskSummary(
        activation_accuracy=1.0,
        false_activation_rate=0.0,
        missed_activation_rate=0.0,
        total_cost_usd=0.0,
        total_runtime_seconds=0.1,
    )
    dr = SkillDiscoverabilityResult(
        per_task_results=(task_r,),
        summary=summary,
        adapter_coverage="in_process",
    )
    assert dr.adapter_coverage == "in_process"
    assert len(dr.per_task_results) == 1
    with pytest.raises(FrozenInstanceError):
        dr.adapter_coverage = "other"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# AC-7.2.3 + AC-7.2.7: SkillDidNotActivateError                               #
# --------------------------------------------------------------------------- #


def test_skill_did_not_activate_error_carries_diagnostic_fields() -> None:
    """SkillDidNotActivateError carries prompt, skill_path, skill_name, competing_skill, reasoning, fix_suggestion."""
    exc = SkillDidNotActivateError(
        "Skill 'example-search-skill' did not activate for prompt.",
        prompt="hello world",
        skill_path="/some/skill.md",
        skill_name="example-search-skill",
        competing_skill=None,
        reasoning="I decided not to search.",
        fix_suggestion="Rephrase the prompt.",
    )
    assert exc.prompt == "hello world"
    assert exc.skill_name == "example-search-skill"
    assert exc.competing_skill is None
    assert exc.reasoning == "I decided not to search."
    assert exc.fix_suggestion == "Rephrase the prompt."
    assert "SKILL_DID_NOT_ACTIVATE" in str(exc)
    assert "hello world" in str(exc)
    assert "example-search-skill" in str(exc)


# --------------------------------------------------------------------------- #
# AC-7.2.4: get_discoverability keyword + tier-3 annotation                   #
# --------------------------------------------------------------------------- #


def test_get_discoverability_returns_skill_discoverability_result(lib: SkillsLibrary) -> None:
    """Happy path: get_discoverability returns a SkillDiscoverabilityResult."""
    # Stub always mentions the skill name → all activations = True
    stub = _make_stub(response_text=f"I used the {SKILL_NAME} to find the answer.")
    register_adapter("stub_disc_happy", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_happy",
        trials_per_task=1,
    )
    assert isinstance(result, SkillDiscoverabilityResult)


def test_get_discoverability_has_tier_3_annotation(lib: SkillsLibrary) -> None:
    """@tier(3) is present on get_discoverability."""
    assert get_keyword_tier(lib.get_discoverability) == 3


def test_get_discoverability_activations_count_correct_when_all_activate(lib: SkillsLibrary) -> None:
    """activations_observed equals trials_run when stub always mentions skill name."""
    stub = _make_stub(response_text=f"I activated the {SKILL_NAME} skill.")
    register_adapter("stub_disc_all_act", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_all_act",
        trials_per_task=2,
    )
    for task_result in result.per_task_results:
        assert task_result.activations_observed == 2
        assert task_result.trials_run == 2


def test_get_discoverability_activations_count_zero_when_none_activate(lib: SkillsLibrary) -> None:
    """activations_observed equals 0 when stub never mentions skill name."""
    stub = _make_stub(response_text="I did something completely different here.")
    register_adapter("stub_disc_no_act", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_no_act",
        trials_per_task=2,
    )
    for task_result in result.per_task_results:
        assert task_result.activations_observed == 0


# --------------------------------------------------------------------------- #
# AC-7.2.5: should_activate_for keyword + tier-2 annotation                  #
# --------------------------------------------------------------------------- #


def test_should_activate_for_passes_when_skill_activates(lib: SkillsLibrary) -> None:
    """should_activate_for returns None when skill name is in response."""
    stub = _make_stub(response_text=f"The {SKILL_NAME} will handle this search.")
    register_adapter("stub_saf_pass", stub)
    result = lib.should_activate_for(
        "Search for Python tutorials",
        SEARCH_SKILL,
        adapter="stub_saf_pass",
    )
    assert result is None


def test_should_activate_for_has_tier_2_annotation(lib: SkillsLibrary) -> None:
    """@tier(2) is present on should_activate_for."""
    assert get_keyword_tier(lib.should_activate_for) == 2


def test_should_activate_for_raises_skill_did_not_activate_error(lib: SkillsLibrary) -> None:
    """should_activate_for raises SkillDidNotActivateError when skill not in response."""
    stub = _make_stub(response_text="I handled this request without any specialized skill.")
    register_adapter("stub_saf_fail", stub)
    with pytest.raises(SkillDidNotActivateError) as exc_info:
        lib.should_activate_for(
            "Search for Python tutorials",
            SEARCH_SKILL,
            adapter="stub_saf_fail",
        )
    exc = exc_info.value
    assert exc.skill_name == SKILL_NAME
    assert exc.prompt == "Search for Python tutorials"
    assert exc.reasoning == "I handled this request without any specialized skill."
    assert exc.competing_skill is None


# --------------------------------------------------------------------------- #
# AC-7.2.6: polling= raises PollingDisallowedError on both keywords           #
# --------------------------------------------------------------------------- #


def test_get_discoverability_polling_raises_polling_disallowed_error(lib: SkillsLibrary) -> None:
    """Passing polling= to get_discoverability raises PollingDisallowedError."""
    with pytest.raises(PollingDisallowedError):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, polling=1.0)


def test_should_activate_for_polling_raises_polling_disallowed_error(lib: SkillsLibrary) -> None:
    """Passing polling= to should_activate_for raises PollingDisallowedError."""
    with pytest.raises(PollingDisallowedError):
        lib.should_activate_for("some prompt", SEARCH_SKILL, polling=1.0)


# --------------------------------------------------------------------------- #
# trials_per_task validation (Codex MED-1)                                    #
# --------------------------------------------------------------------------- #


def test_get_discoverability_trials_per_task_zero_raises_value_error(lib: SkillsLibrary) -> None:
    """trials_per_task=0 raises ValueError before any adapter call."""
    with pytest.raises(ValueError, match="trials_per_task"):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, trials_per_task=0)


def test_get_discoverability_trials_per_task_negative_raises_value_error(lib: SkillsLibrary) -> None:
    """trials_per_task=-1 raises ValueError before any adapter call."""
    with pytest.raises(ValueError, match="trials_per_task"):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, trials_per_task=-1)


# --------------------------------------------------------------------------- #
# Summary math: activation_accuracy / false_activation_rate / missed_rate     #
# SKILL_TASKS: 3 should_activate=True + 2 should_activate=False               #
# --------------------------------------------------------------------------- #


def test_summary_all_activate_accuracy_and_rates(lib: SkillsLibrary) -> None:
    """With stub that always activates and trials_per_task=2:
    - activation_accuracy = 6/10 = 0.6  (3 should-tasks correct, 2 decoy-tasks wrong)
    - false_activation_rate = 4/4 = 1.0 (all decoy trials activated)
    - missed_activation_rate = 0/6 = 0.0 (no should-tasks missed)
    """
    stub = _make_stub(response_text=f"Using {SKILL_NAME} for everything.")
    register_adapter("stub_summary_all", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_summary_all",
        trials_per_task=2,
    )
    s = result.summary
    assert abs(s.activation_accuracy - 0.6) < 1e-9
    assert abs(s.false_activation_rate - 1.0) < 1e-9
    assert abs(s.missed_activation_rate - 0.0) < 1e-9


def test_summary_none_activate_accuracy_and_rates(lib: SkillsLibrary) -> None:
    """With stub that never activates and trials_per_task=2:
    - activation_accuracy = 4/10 = 0.4  (2 decoy-tasks correct, 3 should-tasks wrong)
    - false_activation_rate = 0/4 = 0.0 (no decoy trials activated)
    - missed_activation_rate = 6/6 = 1.0 (all should-tasks missed)
    """
    stub = _make_stub(response_text="I did something unrelated.")
    register_adapter("stub_summary_none", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_summary_none",
        trials_per_task=2,
    )
    s = result.summary
    assert abs(s.activation_accuracy - 0.4) < 1e-9
    assert abs(s.false_activation_rate - 0.0) < 1e-9
    assert abs(s.missed_activation_rate - 1.0) < 1e-9


def test_skill_discoverability_task_summary_is_frozen_dataclass() -> None:
    """SkillDiscoverabilityTaskSummary is frozen — assignment raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    s = SkillDiscoverabilityTaskSummary(
        activation_accuracy=0.8,
        false_activation_rate=0.1,
        missed_activation_rate=0.2,
        total_cost_usd=0.005,
        total_runtime_seconds=1.0,
    )
    with pytest.raises(FrozenInstanceError):
        s.activation_accuracy = 0.0  # type: ignore[misc]
