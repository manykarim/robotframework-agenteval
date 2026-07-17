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

"""Tests for the rubric parser, prompt compose, and strict JSON scoring."""

from __future__ import annotations

import json
from typing import Any

import pytest

from AgentEval._core.errors import InvalidRubricError, JudgeOutputParseError
from AgentEval._core.judge import (
    JudgeRubric,
    compose_judge_prompt,
    parse_judge_response,
    parse_rubric_text,
    rubric_from_criteria,
    score,
)
from AgentEval._core.types import AgentRunResult

_RUBRIC_MD = """# Quality

## Criteria
- clarity: The answer is clear.
- accuracy: The answer is correct.

## Threshold
Pass if numeric_score >= 7.0
"""


def _rubric() -> JudgeRubric:
    return parse_rubric_text(_RUBRIC_MD, source="<test>")


class _ScriptedAdapter:
    """Returns a canned judge response so scoring is deterministic offline."""

    name = "scripted"

    def __init__(self, payload: dict[str, Any], cost: float = 0.0) -> None:
        self._payload = payload
        self._cost = cost

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        return AgentRunResult(response_text=json.dumps(self._payload), cost_usd=self._cost)


def test_parse_rubric_ok() -> None:
    rubric = _rubric()
    assert rubric.threshold == 7.0
    assert rubric.criteria == (("clarity", "The answer is clear."), ("accuracy", "The answer is correct."))


def test_parse_rubric_missing_criteria() -> None:
    with pytest.raises(InvalidRubricError):
        parse_rubric_text("## Threshold\nPass if numeric_score >= 5.0\n", source="<x>")


def test_parse_rubric_missing_threshold() -> None:
    with pytest.raises(InvalidRubricError):
        parse_rubric_text("## Criteria\n- a: b\n", source="<x>")


def test_parse_rubric_malformed_bullet() -> None:
    text = "## Criteria\n- no colon here\n\n## Threshold\nPass if numeric_score >= 5.0\n"
    with pytest.raises(InvalidRubricError):
        parse_rubric_text(text, source="<x>")


def test_rubric_from_criteria() -> None:
    rubric = rubric_from_criteria("Response is polite", threshold=6.0)
    assert rubric.threshold == 6.0
    assert rubric.criteria[0][0] == "criteria"


def test_rubric_from_criteria_rejects_nullish() -> None:
    for bad in ["", "   ", "none", "None"]:
        with pytest.raises(InvalidRubricError):
            rubric_from_criteria(bad)


def test_compose_judge_prompt_includes_sections() -> None:
    prompt = compose_judge_prompt(_rubric(), "the answer", extra_sections=(("Context", "grounding"),))
    assert "# Rubric" in prompt
    assert "# Context" in prompt
    assert "grounding" in prompt
    assert "# Agent Response" in prompt
    assert "the answer" in prompt


def test_parse_judge_response_ok() -> None:
    raw = json.dumps({"numeric_score": 8.5, "reasoning": "solid", "criteria_breakdown": {"clarity": 9, "accuracy": 8}})
    result = parse_judge_response(raw, _rubric(), cost_usd=0.01)
    assert result.numeric_score == 8.5
    assert result.pass_threshold_met is True
    assert result.criteria_breakdown == {"clarity": 9.0, "accuracy": 8.0}
    assert result.cost_usd == 0.01


def test_parse_judge_response_below_threshold() -> None:
    raw = json.dumps({"numeric_score": 4.0, "reasoning": "weak"})
    assert parse_judge_response(raw, _rubric()).pass_threshold_met is False


def test_parse_judge_response_not_json() -> None:
    with pytest.raises(JudgeOutputParseError):
        parse_judge_response("not json", _rubric())


def test_parse_judge_response_missing_field() -> None:
    with pytest.raises(JudgeOutputParseError):
        parse_judge_response(json.dumps({"numeric_score": 5.0}), _rubric())


def test_parse_judge_response_bool_score_rejected() -> None:
    raw = json.dumps({"numeric_score": True, "reasoning": "x"})
    with pytest.raises(JudgeOutputParseError):
        parse_judge_response(raw, _rubric())


def test_parse_judge_response_out_of_range() -> None:
    raw = json.dumps({"numeric_score": 42.0, "reasoning": "x"})
    with pytest.raises(JudgeOutputParseError):
        parse_judge_response(raw, _rubric())


def test_score_end_to_end_with_stub_adapter() -> None:
    adapter = _ScriptedAdapter({"numeric_score": 9.0, "reasoning": "great", "criteria_breakdown": {}}, cost=0.02)
    result = score("the response", _rubric(), adapter=adapter)
    assert result.numeric_score == 9.0
    assert result.pass_threshold_met is True
    assert result.cost_usd == 0.02
