# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Conversation lifecycle unit tests (add-multi-turn-conversation-testing Task 2.7).

Mock-provider deterministic; no API keys. Covers the happy path, snapshot
stability, closed-handle errors, replay-fallback prompt content, and
`require_native` fast-fail.
"""

from __future__ import annotations

import pytest

from AgentEval.conversation._handle import ConversationHandle
from AgentEval.conversation.library import ConversationLibrary
from AgentEval.errors import ConversationClosedError, ConversationContinuationUnsupportedError
from AgentEval.types import ConversationTranscript

from .conftest import REPLAY_CALLS


def test_start_conversation_returns_handle_without_llm_call(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    assert isinstance(conv, ConversationHandle)
    assert conv.turns == ()
    assert conv.agent_turn_count == 0
    assert conv.supports_native is True
    # No provider call happened at Start Conversation time.
    assert conv._adapter.recording_provider.calls == []


def test_scripted_conversation_records_four_turns_in_order(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    r1 = lib.send_message(conv, "Book a flight to Oslo")
    r2 = lib.send_message(conv, "Actually make it business class")
    assert r1.response_text == "echo:Book a flight to Oslo"
    assert r2.response_text.startswith("echo:")
    turns = conv.turns
    assert [t.role for t in turns] == ["user", "agent", "user", "agent"]
    assert [t.index for t in turns] == [0, 1, 2, 3]
    assert turns[1].continuation == "initial"
    assert turns[3].continuation == "native_session"


def test_adapter_instance_reused_across_turns(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    provider = conv._adapter.recording_provider
    lib.send_message(conv, "one")
    lib.send_message(conv, "two")
    # Same provider instance recorded both calls (session affinity).
    assert len(provider.calls) == 2
    # Turn 2 saw the full prior history (user1, agent1, user2).
    assert provider.calls[1] == [
        ("user", "one"),
        ("assistant", "echo:one"),
        ("user", "two"),
    ]


def test_transcript_is_a_stable_snapshot(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "one")
    lib.send_message(conv, "two")
    t1 = lib.get_conversation_transcript(conv)
    assert isinstance(t1, ConversationTranscript)
    assert t1.turn_count == 2
    lib.send_message(conv, "three")
    # The earlier snapshot did NOT mutate.
    assert t1.turn_count == 2
    assert lib.get_conversation_transcript(conv).turn_count == 3


def test_aggregates_reconcile_with_per_turn_results(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    r1 = lib.send_message(conv, "one")
    r2 = lib.send_message(conv, "two")
    t = lib.get_conversation_transcript(conv)
    assert t.total_cost_usd == pytest.approx(r1.cost_usd + r2.cost_usd)
    assert t.total_latency_seconds == pytest.approx(r1.latency_seconds + r2.latency_seconds)
    assert t.continuation_mode == "native_session"


def test_send_after_close_raises_and_transcript_survives(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "one")
    lib.send_message(conv, "two")
    lib.end_conversation(conv)
    with pytest.raises(ConversationClosedError):
        lib.send_message(conv, "three")
    # Transcript still readable after close.
    assert lib.get_conversation_transcript(conv).turn_count == 2


def test_replay_only_adapter_degrades_honestly(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="replay-only")
    assert conv.supports_native is False
    lib.send_message(conv, "first message")
    lib.send_message(conv, "second message")
    turns = conv.turns
    assert turns[1].continuation == "initial"
    assert turns[3].continuation == "replayed_history"
    # The replay preamble passed to run() on turn 2 contains the prior turns.
    replay_prompt = REPLAY_CALLS[1]
    assert "first message" in replay_prompt
    assert "second message" in replay_prompt
    assert "Conversation so far" in replay_prompt


def test_require_native_fast_fails_on_replay_only_adapter(lib: ConversationLibrary) -> None:
    with pytest.raises(ConversationContinuationUnsupportedError) as exc:
        lib.start_conversation(adapter="replay-only", require_native=True)
    assert exc.value.adapter == "replay-only"
    assert "replay-only" in str(exc.value)
    # No run() call happened.
    assert REPLAY_CALLS == []


def test_require_native_allows_native_adapter(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock", require_native=True)
    assert conv.supports_native is True


def test_transcript_should_contain_role_filtered(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "hello there")
    lib.transcript_should_contain(conv, "echo:hello there", role="agent")
    lib.transcript_should_contain(conv, "hello there", role="user")
    with pytest.raises(AssertionError, match="refund"):
        lib.transcript_should_contain(conv, "refund")
    # regex form
    lib.transcript_should_contain(conv, r"echo:\w+", role="agent", as_regex=True)


def test_transcript_should_contain_rejects_bad_role(lib: ConversationLibrary) -> None:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "hi")
    with pytest.raises(ValueError, match="role must be one of"):
        lib.transcript_should_contain(conv, "hi", role="bogus")
