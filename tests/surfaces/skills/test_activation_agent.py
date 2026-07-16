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

"""Tier-3 agent-mode activation: decision, assertion, and pass@k."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import SkillDidNotActivateError, stats
from SkillsLibrary import SkillsLibrary
from SkillsLibrary._types import ActivationDecision

from .conftest import FixedAdapter, PromptRoutedAdapter, ScriptedAdapter


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


def test_activation_decision_true_when_name_in_response(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = FixedAdapter("I will use the web-search skill.")
    decision = lib.get_activation_decision(skill_file, "find news", adapter=adapter)
    assert decision.activated is True
    assert decision.cost_usd == 0.01
    assert decision.latency_seconds == 0.5


def test_activation_decision_false_when_name_absent(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = FixedAdapter("I can answer that without any tool.")
    decision = lib.get_activation_decision(skill_file, "add 2 and 2", adapter=adapter)
    assert decision.activated is False


def test_activation_is_case_insensitive(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = FixedAdapter("Deploying WEB-SEARCH now.")
    decision = lib.get_activation_decision(skill_file, "prompt", adapter=adapter)
    assert decision.activated is True


def test_should_activate_for_passes_when_triggered(lib: SkillsLibrary, skill_file: Path) -> None:
    # Scenario: Assert a skill activates for a prompt -> passes only if activated.
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    lib.should_activate_for("Find news about Robot Framework", skill_file, adapter=adapter)


def test_should_activate_for_raises_when_not_triggered(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = PromptRoutedAdapter("web-search", trigger="news")
    with pytest.raises(SkillDidNotActivateError) as excinfo:
        lib.should_activate_for("Calculate 2 + 2", skill_file, adapter=adapter)
    assert "web-search" in str(excinfo.value)


def test_pass_at_k_reports_estimate_and_interval(lib: SkillsLibrary, skill_file: Path) -> None:
    # Scenario: Activation pass@k over trials -> reports pass@k estimate + CI.
    # 6 of 10 trials activate (alternating 3:2 pattern -> 6 activations).
    adapter = ScriptedAdapter(
        [
            "web-search fired",
            "web-search fired",
            "web-search fired",
            "no skill here",
            "no skill here",
        ]
    )
    runs = stats.run_n(lib.get_activation_decision, 10, skill_file, "prompt", adapter=adapter)
    result = lib.get_activation_pass_at_k(runs, k=5)
    assert result.trials == 10
    assert result.successes == 6
    assert 0.0 <= result.pass_at_k <= 1.0
    lo, hi = result.confidence_interval
    assert 0.0 <= lo <= hi <= 1.0


def test_pass_at_k_all_activate_is_one(lib: SkillsLibrary) -> None:
    runs = [
        stats.KeywordRun(
            trial_index=i,
            result=ActivationDecision(activated=True, reasoning="x", cost_usd=0.0, latency_seconds=0.0),
            error=None,
            completeness="n/a",
            latency_seconds=0.0,
        )
        for i in range(5)
    ]
    result = lib.get_activation_pass_at_k(runs, k=3)
    assert result.pass_at_k == 1.0
    assert result.successes == 5


def test_pass_at_k_none_activate_is_zero(lib: SkillsLibrary) -> None:
    runs = [
        stats.KeywordRun(
            trial_index=i,
            result=ActivationDecision(activated=False, reasoning="x", cost_usd=0.0, latency_seconds=0.0),
            error=None,
            completeness="n/a",
            latency_seconds=0.0,
        )
        for i in range(5)
    ]
    result = lib.get_activation_pass_at_k(runs, k=3)
    assert result.pass_at_k == 0.0
    assert result.successes == 0


def test_pass_at_k_rejects_k_over_n(lib: SkillsLibrary) -> None:
    runs = [
        stats.KeywordRun(
            trial_index=0,
            result=ActivationDecision(activated=True, reasoning="x", cost_usd=0.0, latency_seconds=0.0),
            error=None,
            completeness="n/a",
            latency_seconds=0.0,
        )
    ]
    with pytest.raises(ValueError):
        lib.get_activation_pass_at_k(runs, k=5)
