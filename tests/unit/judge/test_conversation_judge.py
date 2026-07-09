# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Judge-at-turn-and-transcript unit tests (add-multi-turn-conversation-testing Task 4.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.judge.library import JudgeLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, ConversationTranscript, ConversationTurn, Usage

from .test_library import _make_agent_run_result, _make_judge_response, _patch_adapter

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md"


def _agent_turn(index: int, text: str) -> ConversationTurn:
    result = AgentRunResult(
        response_text=text,
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.01,
        latency_seconds=0.1,
        trace_id=f"t{index}",
    )
    return ConversationTurn(index=index, role="agent", content=text, result=result, continuation="native_session")


def _transcript() -> ConversationTranscript:
    turns = (
        ConversationTurn(index=0, role="user", content="Book a flight to Oslo"),
        _agent_turn(1, "AGENT_TURN_ZERO booking started"),
        ConversationTurn(index=2, role="user", content="Make it business class"),
        _agent_turn(3, "AGENT_TURN_ONE upgraded to business"),
    )
    return ConversationTranscript(
        turns=turns,
        turn_count=2,
        total_cost_usd=0.02,
        total_latency_seconds=0.2,
        continuation_mode="native_session",
    )


def test_get_score_accepts_a_transcript_and_renders_full_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _make_judge_response(numeric_score=9.0))
    lib = JudgeLibrary()
    score = lib.get_score(result=_transcript(), rubric=FIXTURE_RUBRIC)
    assert score.numeric_score == 9.0
    # The composed judge prompt contains every turn's role + content in order.
    judge_prompt = spy.call_args.kwargs["prompt"]
    assert "Book a flight to Oslo" in judge_prompt
    assert "AGENT_TURN_ZERO" in judge_prompt
    assert "Make it business class" in judge_prompt
    assert "AGENT_TURN_ONE" in judge_prompt


def test_get_score_still_accepts_a_single_turn_result(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _make_judge_response(numeric_score=8.0))
    lib = JudgeLibrary()
    turn_result = _make_agent_run_result("SINGLE TURN OUTPUT")
    score = lib.get_score(result=turn_result, rubric=FIXTURE_RUBRIC)
    assert score.numeric_score == 8.0
    assert "SINGLE TURN OUTPUT" in spy.call_args.kwargs["prompt"]


def test_judge_turn_should_pass_passes_on_high_score(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _make_judge_response(numeric_score=9.5))
    lib = JudgeLibrary()
    score = lib.judge_turn_should_pass(_transcript(), FIXTURE_RUBRIC, turn=-1)
    assert score.pass_threshold_met


def test_judge_turn_should_pass_fails_with_score_and_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_adapter(monkeypatch, _make_judge_response(numeric_score=2.0, reasoning="Weak upsell attempt."))
    lib = JudgeLibrary()
    with pytest.raises(AssertionError) as exc:
        lib.judge_turn_should_pass(_transcript(), FIXTURE_RUBRIC, turn=-1)
    msg = str(exc.value)
    assert "2.0" in msg
    assert "Weak upsell attempt." in msg


def test_judge_turn_should_pass_selects_turn_by_index(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _make_judge_response(numeric_score=9.0))
    lib = JudgeLibrary()
    lib.judge_turn_should_pass(_transcript(), FIXTURE_RUBRIC, turn=0)
    # turn=0 scores the FIRST agent turn.
    judge_prompt = spy.call_args.kwargs["prompt"]
    assert "AGENT_TURN_ZERO" in judge_prompt
    assert "AGENT_TURN_ONE" not in judge_prompt


def test_judge_turn_should_pass_out_of_range_fails_without_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _patch_adapter(monkeypatch, _make_judge_response(numeric_score=9.0))
    lib = JudgeLibrary()
    with pytest.raises(AssertionError, match="out of range"):
        lib.judge_turn_should_pass(_transcript(), FIXTURE_RUBRIC, turn=5)
    # No LLM call was made.
    spy.assert_not_called()
