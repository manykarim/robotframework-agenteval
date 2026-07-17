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

"""Tier-2 judge-based activation - the honest LLM mode (fake judge adapter)."""

from __future__ import annotations

from pathlib import Path

import pytest

from SkillsLibrary import SkillsLibrary

from .conftest import JudgeAdapter


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


def test_judge_activation_pass(lib: SkillsLibrary, skill_file: Path) -> None:
    # Scenario: Judge-based activation decision -> the judge decides the response
    # applied the skill and returns a decision with justification.
    adapter = JudgeAdapter(numeric_score=8.5, reasoning="the response searched the web")
    decision = lib.get_judge_activation_decision(
        "I searched several news sites and summarized the results.",
        skill_file,
        adapter=adapter,
    )
    assert decision.activated is True
    assert decision.numeric_score == 8.5
    assert decision.justification == "the response searched the web"
    assert decision.cost_usd == 0.03


def test_judge_activation_fail_below_threshold(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = JudgeAdapter(numeric_score=3.0, reasoning="the response ignored the skill")
    decision = lib.get_judge_activation_decision(
        "I made up an answer without searching.",
        skill_file,
        adapter=adapter,
    )
    assert decision.activated is False
    assert decision.numeric_score == 3.0


def test_judge_activation_custom_threshold(lib: SkillsLibrary, skill_file: Path) -> None:
    adapter = JudgeAdapter(numeric_score=5.0)
    # Score 5.0 clears a threshold of 4.0 but not the 7.0 default.
    lenient = lib.get_judge_activation_decision("resp", skill_file, adapter=adapter, threshold=4.0)
    assert lenient.activated is True
    strict = lib.get_judge_activation_decision("resp", skill_file, adapter=adapter, threshold=7.0)
    assert strict.activated is False
