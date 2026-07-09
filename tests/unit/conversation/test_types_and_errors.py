# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Shared-type + error unit tests (add-multi-turn-conversation-testing Tasks 1.1 + 1.2)."""

from __future__ import annotations

import dataclasses

import pytest

from AgentEval.errors import (
    AgentEvalCompatError,
    AgentEvalError,
    AgentEvalIntegrityError,
    ConversationClosedError,
    ConversationContinuationUnsupportedError,
)
from AgentEval.types import AgentRunMetadata, AgentRunResult, ConversationTranscript, ConversationTurn, Usage


def _agent_result() -> AgentRunResult:
    return AgentRunResult(
        response_text="hi",
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.02,
        latency_seconds=0.5,
        trace_id="abc",
    )


def test_conversation_turn_is_frozen() -> None:
    turn = ConversationTurn(index=0, role="user", content="hello")
    with pytest.raises(dataclasses.FrozenInstanceError):
        turn.content = "mutated"  # type: ignore[misc]


def test_conversation_turn_asdict_round_trip() -> None:
    turn = ConversationTurn(index=1, role="agent", content="hi", result=_agent_result(), continuation="initial")
    d = dataclasses.asdict(turn)
    assert d["index"] == 1
    assert d["role"] == "agent"
    assert d["continuation"] == "initial"
    assert d["result"]["response_text"] == "hi"


def test_transcript_coerces_turns_to_tuple_and_is_frozen() -> None:
    turns = [ConversationTurn(index=0, role="user", content="q")]
    t = ConversationTranscript(
        turns=turns,  # passed a list; coerced to tuple
        turn_count=0,
        total_cost_usd=0.0,
        total_latency_seconds=0.0,
        continuation_mode="none",
    )
    assert isinstance(t.turns, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.turn_count = 5  # type: ignore[misc]
    # Mutating the source list does NOT change the snapshot.
    turns.append(ConversationTurn(index=1, role="agent", content="a"))
    assert len(t.turns) == 1


def test_transcript_asdict_round_trip() -> None:
    t = ConversationTranscript(
        turns=(ConversationTurn(index=0, role="agent", content="a", result=_agent_result(), continuation="initial"),),
        turn_count=1,
        total_cost_usd=0.02,
        total_latency_seconds=0.5,
        continuation_mode="initial",
        stop_reason="goal_achieved",
    )
    d = dataclasses.asdict(t)
    assert d["turn_count"] == 1
    assert d["stop_reason"] == "goal_achieved"
    assert d["turns"][0]["continuation"] == "initial"


def test_conversation_closed_error_shape() -> None:
    exc = ConversationClosedError("conversation is closed", fix_suggestion="Start a fresh conversation.")
    assert isinstance(exc, AgentEvalIntegrityError)
    assert isinstance(exc, AgentEvalError)
    assert exc.error_code == "CONVERSATION_CLOSED"
    rendered = str(exc)
    assert rendered.startswith("CONVERSATION_CLOSED: conversation is closed")
    assert "Fix: Start a fresh conversation." in rendered


def test_continuation_unsupported_error_shape() -> None:
    exc = ConversationContinuationUnsupportedError(
        "adapter 'copilot' has no run_turn", adapter="copilot", fix_suggestion="Omit require_native."
    )
    assert isinstance(exc, AgentEvalCompatError)
    assert exc.error_code == "CONVERSATION_CONTINUATION_UNSUPPORTED"
    assert exc.adapter == "copilot"
    rendered = str(exc)
    assert "CONVERSATION_CONTINUATION_UNSUPPORTED:" in rendered
    assert "Adapter: copilot" in rendered
    assert "Fix: Omit require_native." in rendered
