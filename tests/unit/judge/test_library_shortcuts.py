# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for the add-judge-criteria-shortcuts keyword surface.

Covers `Judge.Score With Criteria`, the metric presets, `Judge.Get Preset
Rubric`, and the `Judge Score Should Be Above` assertion form — all against a
fake adapter (no live API keys), plus the `calibrated`/`rubric_source` honesty
fields, the WARN-once behavior, and the byte-identical prompt regression.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.errors import InvalidJudgeRubricError, JudgeOutputParseError
from AgentEval.judge import library as libmod
from AgentEval.judge.library import (
    JudgeLibrary,
    _compose_judge_prompt,
    _reset_uncalibrated_warning_for_tests,
    _synthesize_criteria_rubric,
)
from AgentEval.judge.rubric import parse_rubric_text
from AgentEval.judge.types import CalibrationReport, JudgeRubric, JudgeScore
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def _make_result(response_text: str = "the agent's output") -> AgentRunResult:
    return AgentRunResult(
        response_text=response_text,
        tool_calls=[],
        usage=Usage(input_tokens=10, output_tokens=20),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.5,
        trace_id="test-trace",
    )


def _judge_response(
    numeric_score: float = 8.0,
    reasoning: str = "Solid response.",
    criteria_breakdown: dict[str, float] | None = None,
    cost_usd: float = 0.001,
) -> AgentRunResult:
    payload = {
        "numeric_score": numeric_score,
        "reasoning": reasoning,
        "criteria_breakdown": criteria_breakdown if criteria_breakdown is not None else {"user_criteria": numeric_score},
    }
    return AgentRunResult(
        response_text=json.dumps(payload),
        tool_calls=[],
        usage=Usage(input_tokens=200, output_tokens=80),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost_usd,
        latency_seconds=1.0,
        trace_id="judge-trace",
    )


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, judge_response: AgentRunResult) -> MagicMock:
    """Patch `get_adapter` in the innermost keyword's `__globals__` (module dict).

    Mirrors `test_library.py:_patch_adapter` — walks the decorator chain to the
    innermost function whose `__globals__` IS `library.py`'s module dict (where
    the runtime `get_adapter` lookup happens), robust to the conventions suite's
    module reload.
    """
    fake_run = MagicMock(return_value=judge_response)

    class _FakeAdapter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, *args: Any, **kwargs: Any) -> AgentRunResult:
            return fake_run(*args, **kwargs)

    innermost = JudgeLibrary.score_with_criteria
    while hasattr(innermost, "__wrapped__"):
        innermost = innermost.__wrapped__

    monkeypatch.setitem(innermost.__globals__, "get_adapter", lambda name: _FakeAdapter)
    return fake_run


@pytest.fixture(autouse=True)
def _reset_warn() -> None:
    _reset_uncalibrated_warning_for_tests()


# --------------------------------------------------------------------------- #
# JudgeScore honesty fields (Task 1.3)                                          #
# --------------------------------------------------------------------------- #


def test_judge_score_defaults_are_uncalibrated_file() -> None:
    """Existing construction sites keep working; new fields default honestly."""
    score = JudgeScore(numeric_score=8.0, pass_threshold_met=True, reasoning="ok")
    assert score.calibrated is False
    assert score.rubric_source == "file"
    d = dataclasses.asdict(score)
    assert d["calibrated"] is False
    assert d["rubric_source"] == "file"


# --------------------------------------------------------------------------- #
# parse_rubric_text direct use (Task 1.3)                                       #
# --------------------------------------------------------------------------- #


def test_parse_rubric_text_direct() -> None:
    raw = "## Criteria\n- correctness: did it work?\n\n## Threshold\nPass if numeric_score >= 6.0\n"
    rubric = parse_rubric_text(raw, source="<test>")
    assert rubric.criteria == (("correctness", "did it work?"),)
    assert rubric.threshold == 6.0


def test_parse_rubric_text_reports_source_in_error() -> None:
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        parse_rubric_text("## Threshold\nPass if numeric_score >= 6.0\n", source="<synthetic>")
    assert exc_info.value.file_path == "<synthetic>"


# --------------------------------------------------------------------------- #
# Criteria synthesis round-trip (Task 2.1)                                      #
# --------------------------------------------------------------------------- #


def test_synthesized_rubric_round_trips() -> None:
    rubric = _synthesize_criteria_rubric("Response is concise and correct", 7.0)
    assert rubric.criteria == (("user_criteria", "Response is concise and correct"),)
    assert rubric.threshold == 7.0
    # raw_text re-parses to an equivalent rubric via the shared parser.
    reparsed = parse_rubric_text(rubric.raw_text, source="<roundtrip>")
    assert reparsed.criteria == rubric.criteria
    assert reparsed.threshold == rubric.threshold


# --------------------------------------------------------------------------- #
# Fail-loud validation before any LLM call (Task 2.2)                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", ["", "   ", "\n\t ", "None", "none"])
def test_empty_or_nullish_criteria_fails_before_llm(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()
    with pytest.raises(InvalidJudgeRubricError) as exc_info:
        judge_lib.score_with_criteria(result=_make_result(), criteria=bad, threshold=7.0)
    assert exc_info.value.fix_suggestion
    assert spy.call_count == 0  # no LLM call


def test_out_of_range_threshold_fails_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()
    with pytest.raises(InvalidJudgeRubricError, match=r"\[0.0, 10.0\]"):
        judge_lib.score_with_criteria(result=_make_result(), criteria="ok", threshold=11.0)
    assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# Judge.Score With Criteria happy paths (Task 2.5)                              #
# --------------------------------------------------------------------------- #


def test_score_with_criteria_returns_uncalibrated_score(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response(numeric_score=8.5))
    judge_lib = JudgeLibrary()
    score = judge_lib.score_with_criteria(
        result=_make_result(),
        criteria="Response is polite and answers the question",
        threshold=7.0,
    )
    assert isinstance(score, JudgeScore)
    assert score.numeric_score == 8.5
    assert score.pass_threshold_met is True
    assert score.calibrated is False
    assert score.rubric_source == "criteria_string"
    assert spy.call_count == 1
    # Criteria string is reflected in the composed prompt.
    prompt = spy.call_args.kwargs.get("prompt") or spy.call_args.args[0]
    assert "Response is polite and answers the question" in prompt


def test_score_with_criteria_threshold_boundary_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=7.0))
    judge_lib = JudgeLibrary()
    score = judge_lib.score_with_criteria(result=_make_result(), criteria="ok", threshold=7.0)
    assert score.pass_threshold_met is True  # >= semantics


def test_score_with_criteria_malformed_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _make_result(response_text="not json at all")
    _patch_adapter(monkeypatch, bad)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError):
        judge_lib.score_with_criteria(result=_make_result(), criteria="ok", threshold=7.0)


# --------------------------------------------------------------------------- #
# WARN-once-per-process / INFO-thereafter (Task 2.4)                            #
# --------------------------------------------------------------------------- #


def test_warn_once_then_info(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()

    warn_calls: list[str] = []
    info_calls: list[str] = []
    monkeypatch.setattr(libmod.logger, "warn", lambda msg: warn_calls.append(msg))
    monkeypatch.setattr(libmod.logger, "info", lambda msg: info_calls.append(msg))

    judge_lib.score_with_criteria(result=_make_result(), criteria="ok", threshold=7.0)
    judge_lib.score_with_criteria(result=_make_result(), criteria="ok", threshold=7.0)

    assert len(warn_calls) == 1
    assert "judge-calibration.md" in warn_calls[0]
    assert len(info_calls) == 1  # second call logs at INFO


# --------------------------------------------------------------------------- #
# Presets (Task 3.5)                                                            #
# --------------------------------------------------------------------------- #


def test_faithfulness_includes_context_section(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response(criteria_breakdown={"faithfulness": 8.0}))
    judge_lib = JudgeLibrary()
    score = judge_lib.get_faithfulness(result=_make_result(), context="The sky is blue.")
    assert score.rubric_source == "preset:faithfulness"
    assert score.calibrated is False
    prompt = spy.call_args.kwargs.get("prompt") or spy.call_args.args[0]
    assert "# Context" in prompt
    assert "The sky is blue." in prompt


def test_answer_relevancy_includes_question_section(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response(criteria_breakdown={"answer_relevancy": 8.0}))
    judge_lib = JudgeLibrary()
    score = judge_lib.get_answer_relevancy(result=_make_result(), question="What is 2+2?")
    assert score.rubric_source == "preset:answer_relevancy"
    prompt = spy.call_args.kwargs.get("prompt") or spy.call_args.args[0]
    assert "# Question" in prompt
    assert "What is 2+2?" in prompt


def test_answer_relevancy_requires_question(monkeypatch: pytest.MonkeyPatch) -> None:
    """No silent substitution of the original prompt from AgentRunResult."""
    spy = _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()
    with pytest.raises(TypeError):
        judge_lib.get_answer_relevancy(result=_make_result())  # type: ignore[call-arg]
    assert spy.call_count == 0


def test_hallucination_higher_is_better_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=9.5, criteria_breakdown={"grounding": 9.5}))
    judge_lib = JudgeLibrary()
    score = judge_lib.get_hallucination_score(result=_make_result(), context="grounding text", threshold=7.0)
    assert score.numeric_score == 9.5
    assert score.pass_threshold_met is True  # high grounding == low hallucination == pass
    assert score.rubric_source == "preset:hallucination"


def test_preset_threshold_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=8.0, criteria_breakdown={"faithfulness": 8.0}))
    judge_lib = JudgeLibrary()
    score = judge_lib.get_faithfulness(result=_make_result(), context="ctx", threshold=9.0)
    assert score.pass_threshold_met is False  # 8.0 < 9.0 override, not the 7.0 default


def test_preset_threshold_override_out_of_range_raises_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An out-of-range preset threshold override MUST raise the public
    `InvalidJudgeRubricError` (source/field/fix_suggestion) — NOT a bare
    dataclass `ValueError` — before any LLM call, matching the criteria-string
    path (add-judge-criteria-shortcuts codex LOW).
    """
    spy = _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()
    with pytest.raises(InvalidJudgeRubricError, match=r"\[0.0, 10.0\]") as exc_info:
        judge_lib.get_faithfulness(result=_make_result(), context="ctx", threshold=11.0)
    err = exc_info.value
    assert err.field_name == "## Threshold"
    assert err.fix_suggestion
    assert spy.call_count == 0  # failed before the adapter was ever called


def test_get_preset_rubric_keyword_returns_rubric() -> None:
    judge_lib = JudgeLibrary()
    rubric = judge_lib.get_preset_rubric(name="faithfulness")
    assert isinstance(rubric, JudgeRubric)
    assert rubric.threshold == 7.0


def test_preset_rubric_feeds_calibrate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Graduation path: Get Preset Rubric -> Calibrate Rubric completes with a fake adapter."""
    import re
    from pathlib import Path

    # Patch the adapter used by `calibrate` (walk that keyword's chain).
    fake_run = MagicMock(return_value=_judge_response(numeric_score=8.0, criteria_breakdown={"faithfulness": 8.0}))

    class _FakeAdapter:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        def run(self, *a: Any, **k: Any) -> AgentRunResult:
            return fake_run(*a, **k)

    innermost = JudgeLibrary.calibrate
    while hasattr(innermost, "__wrapped__"):
        innermost = innermost.__wrapped__
    monkeypatch.setitem(innermost.__globals__, "get_adapter", lambda name: _FakeAdapter)

    judge_lib = JudgeLibrary()
    rubric = judge_lib.get_preset_rubric(name="faithfulness")
    calib = Path(__file__).resolve().parents[2] / "fixtures" / "calibration" / "skill-quality-calibration.yaml"
    if not calib.exists():
        # locate any 5-row fixture
        candidates = list((Path(__file__).resolve().parents[2] / "fixtures" / "calibration").glob("*.yaml"))
        assert candidates, "no calibration fixture found"
        calib = candidates[0]
    report = judge_lib.calibrate(rubric=rubric, calibration_set=calib)
    assert isinstance(report, CalibrationReport)
    assert re.search(r".", str(report.rubric_path))  # non-empty provenance


# --------------------------------------------------------------------------- #
# Judge Score Should Be Above assertion form (Task 4.3)                         #
# --------------------------------------------------------------------------- #


def test_assertion_fails_with_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=4.0, reasoning="Rude and off-topic."))
    judge_lib = JudgeLibrary()
    with pytest.raises(AssertionError) as exc_info:
        judge_lib.judge_score_should_be_above(result=_make_result(), criteria="be polite", threshold=7.0)
    msg = str(exc_info.value)
    assert "4.0" in msg
    assert "7.0" in msg
    assert "calibrated=False" in msg
    assert "rubric_source=criteria_string" in msg
    assert "Rude and off-topic." in msg


def test_assertion_passes_returns_score(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=8.5))
    judge_lib = JudgeLibrary()
    score = judge_lib.judge_score_should_be_above(result=_make_result(), criteria="be polite", threshold=7.0)
    assert isinstance(score, JudgeScore)
    assert score.calibrated is False
    assert score.rubric_source == "criteria_string"


def test_assertion_boundary_equality_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _judge_response(numeric_score=7.0))
    judge_lib = JudgeLibrary()
    score = judge_lib.judge_score_should_be_above(result=_make_result(), criteria="ok", threshold=7.0)
    assert score.numeric_score == 7.0  # >= threshold passes


def test_assertion_empty_criteria_fails_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _judge_response())
    judge_lib = JudgeLibrary()
    with pytest.raises(InvalidJudgeRubricError):
        judge_lib.judge_score_should_be_above(result=_make_result(), criteria="", threshold=7.0)
    assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# Byte-identical prompt regression (Task 3.2)                                   #
# --------------------------------------------------------------------------- #


def test_compose_prompt_byte_identical_without_extra_sections() -> None:
    """With no extra sections, the composed prompt is byte-identical to the
    pre-change composition (add-judge-criteria-shortcuts D7 regression guard)."""
    rubric = JudgeRubric(
        criteria=(("correctness", "did it work?"),),
        threshold=7.0,
        raw_text="## Criteria\n- correctness: did it work?\n\n## Threshold\nPass if numeric_score >= 7.0",
    )
    result = _make_result(response_text="hello")

    # Reconstruct the exact pre-change composition inline.
    from AgentEval.judge.library import _SYSTEM_PROMPT

    expected = "\n".join(
        [
            _SYSTEM_PROMPT,
            "",
            "# Rubric",
            rubric.raw_text.strip(),
            "",
            "# Agent Response",
            "hello",
        ]
    )
    assert _compose_judge_prompt(rubric, result) == expected


def test_compose_prompt_inserts_extra_sections_between_rubric_and_response() -> None:
    rubric = JudgeRubric(
        criteria=(("x", "y"),),
        threshold=7.0,
        raw_text="## Criteria\n- x: y\n\n## Threshold\nPass if numeric_score >= 7.0",
    )
    result = _make_result(response_text="resp")
    prompt = _compose_judge_prompt(rubric, result, extra_sections=(("Context", "CTX"),))
    # Ordering: rubric ... # Context ... CTX ... # Agent Response ... resp
    i_rubric = prompt.index("# Rubric")
    i_ctx = prompt.index("# Context")
    i_resp = prompt.index("# Agent Response")
    assert i_rubric < i_ctx < i_resp
    assert "CTX" in prompt


# --------------------------------------------------------------------------- #
# Tier annotations                                                             #
# --------------------------------------------------------------------------- #


def test_tier_annotations() -> None:
    judge_lib = JudgeLibrary()
    assert get_keyword_tier(judge_lib.score_with_criteria) == 2
    assert get_keyword_tier(judge_lib.get_faithfulness) == 2
    assert get_keyword_tier(judge_lib.get_answer_relevancy) == 2
    assert get_keyword_tier(judge_lib.get_hallucination_score) == 2
    assert get_keyword_tier(judge_lib.get_preset_rubric) == 1  # no LLM call
    assert get_keyword_tier(judge_lib.judge_score_should_be_above) == 2
