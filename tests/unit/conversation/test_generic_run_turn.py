# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""GenericAdapter.run_turn native-continuation unit tests (add-multi-turn-conversation-testing Task 3.2)."""

from __future__ import annotations

import pytest

from AgentEval.conversation.state import ConversationState
from AgentEval.types import AgentRunResult, ConversationTurn

from .conftest import NativeMockAdapter, mk_result


def test_run_turn_first_turn_sends_only_the_prompt() -> None:
    adapter = NativeMockAdapter()
    state = ConversationState(prior_turns=())
    result = adapter.run_turn("hello", conversation_state=state)
    assert isinstance(result, AgentRunResult)
    assert adapter.recording_provider.calls[0] == [("user", "hello")]


def test_run_turn_second_turn_sends_full_history() -> None:
    adapter = NativeMockAdapter()
    prior = (
        ConversationTurn(index=0, role="user", content="first"),
        ConversationTurn(index=1, role="agent", content="echo:first", result=mk_result("echo:first")),
    )
    state = ConversationState(prior_turns=prior)
    adapter.run_turn("second", conversation_state=state)
    assert adapter.recording_provider.calls[0] == [
        ("user", "first"),
        ("assistant", "echo:first"),
        ("user", "second"),
    ]


def test_run_turn_rejects_tools_and_mcp_servers() -> None:
    adapter = NativeMockAdapter()
    state = ConversationState(prior_turns=())
    with pytest.raises(NotImplementedError):
        adapter.run_turn("x", conversation_state=state, tools=["web_search"])
    with pytest.raises(NotImplementedError):
        adapter.run_turn("x", conversation_state=state, mcp_servers={"echo": object()})
