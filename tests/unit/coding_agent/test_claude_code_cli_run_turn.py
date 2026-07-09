# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Fixture-driven `ClaudeCodeCLIAdapter.run_turn` unit tests (add-multi-turn-conversation-testing Task 6.3).

The empirical `--resume` probe (Task 6.1) is gated behind
`AGENTEVAL_INTEGRATION_TESTS` in
`tests/integration/test_claude_code_cli_multiturn_live.py`; these unit tests
drive the adapter against CAPTURED stream-json fixtures so no `claude` binary is
needed. The `mock_claude_version` autouse fixture (package conftest) lets the
adapter construct without the real binary.
"""

from __future__ import annotations

import io
import json
from typing import Any

from AgentEval.coding_agent.claude_code_cli import ClaudeCodeCLIAdapter
from AgentEval.conversation.state import ConversationState
from AgentEval.types import ConversationTurn


class _FakePopen:
    def __init__(self, lines: list[str]) -> None:
        self.stdout = io.StringIO("\n".join(lines) + "\n")
        self.stderr = io.StringIO("")
        self.pid = 4321
        self.returncode = 0

    def wait(self) -> int:
        return 0


def _stream(session_id: str | None, text: str, cost: float = 0.01) -> list[str]:
    events: list[dict[str, Any]] = []
    init: dict[str, Any] = {"type": "system", "subtype": "init", "model": "claude"}
    if session_id is not None:
        init["session_id"] = session_id
    events.append(init)
    result: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "result": text,
        "total_cost_usd": cost,
        "usage": {"input_tokens": 5, "output_tokens": 7},
        "duration_ms": 120,
        "is_error": False,
    }
    if session_id is not None:
        result["session_id"] = session_id
    events.append(result)
    return [json.dumps(e) for e in events]


def _install_spawn(adapter: ClaudeCodeCLIAdapter, monkeypatch: Any, streams: list[list[str]]) -> list[dict[str, Any]]:
    """Install a fake `_spawn` returning successive `streams`; record spawn kwargs."""
    spawn_calls: list[dict[str, Any]] = []
    state = {"idx": 0}

    def _fake_spawn(prompt: str, **kwargs: Any) -> _FakePopen:
        spawn_calls.append({"prompt": prompt, **kwargs})
        lines = streams[state["idx"]]
        state["idx"] += 1
        return _FakePopen(lines)

    monkeypatch.setattr(adapter, "_spawn", _fake_spawn)
    return spawn_calls


def test_run_turn_first_turn_captures_session_id(monkeypatch: Any) -> None:
    adapter = ClaudeCodeCLIAdapter()
    _install_spawn(adapter, monkeypatch, [_stream("sess-123", "reply one")])
    state = ConversationState(prior_turns=())
    result = adapter.run_turn("hello", conversation_state=state)
    assert result.response_text == "reply one"
    assert adapter._last_session_id == "sess-123"
    assert state.session_ref == "sess-123"
    assert state.continuation == "native_session"


def test_run_turn_second_turn_resumes_native_session(monkeypatch: Any) -> None:
    adapter = ClaudeCodeCLIAdapter()
    spawn_calls = _install_spawn(
        adapter,
        monkeypatch,
        [_stream("sess-123", "reply one"), _stream("sess-123", "reply two")],
    )
    prior = (
        ConversationTurn(index=0, role="user", content="first"),
        ConversationTurn(index=1, role="agent", content="reply one"),
    )
    state = ConversationState(prior_turns=(), session_ref=None)
    # Turn 1
    adapter.run_turn("first", conversation_state=ConversationState(prior_turns=()))
    # Turn 2 with the captured session id
    state = ConversationState(prior_turns=prior, session_ref="sess-123")
    adapter.run_turn("second", conversation_state=state)
    assert state.continuation == "native_session"
    # The second spawn passed `--resume` via `_resume_session_id`.
    assert spawn_calls[1]["_resume_session_id"] == "sess-123"
    # And the prompt was just the new message (native session carries history).
    assert spawn_calls[1]["prompt"] == "second"


def test_run_turn_degrades_to_replay_when_no_session_captured(monkeypatch: Any) -> None:
    adapter = ClaudeCodeCLIAdapter()
    spawn_calls = _install_spawn(
        adapter,
        monkeypatch,
        [_stream(None, "reply one"), _stream(None, "reply two")],
    )
    # Turn 1: no session id in the stream.
    state1 = ConversationState(prior_turns=())
    adapter.run_turn("first", conversation_state=state1)
    assert adapter._last_session_id is None
    assert state1.continuation == "replayed_history"
    # Turn 2: no session ref → replay preamble into run().
    prior = (
        ConversationTurn(index=0, role="user", content="first"),
        ConversationTurn(index=1, role="agent", content="reply one"),
    )
    state2 = ConversationState(prior_turns=prior, session_ref=None)
    adapter.run_turn("second", conversation_state=state2)
    assert state2.continuation == "replayed_history"
    assert "--resume" not in spawn_calls[1].get("_resume_session_id", "") if spawn_calls[1].get("_resume_session_id") else True
    # The replay prompt contains the prior turns rendered as text.
    assert "first" in spawn_calls[1]["prompt"]
    assert "reply one" in spawn_calls[1]["prompt"]


def test_spawn_includes_resume_flag_in_cmd(monkeypatch: Any) -> None:
    # White-box: `_spawn` builds `--resume <sid>` into the argv when
    # `_resume_session_id` is passed (the real spawn path, subprocess mocked).
    import subprocess

    adapter = ClaudeCodeCLIAdapter()
    captured: dict[str, Any] = {}

    class _P:
        stdout = io.StringIO("")
        stderr = io.StringIO("")
        pid = 1
        returncode = 0

        def wait(self) -> int:
            return 0

    def _fake_popen(cmd: list[str], **kwargs: Any) -> _P:
        captured["cmd"] = cmd
        return _P()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter._spawn("hi there", _resume_session_id="sess-xyz")
    assert "--resume" in captured["cmd"]
    assert "sess-xyz" in captured["cmd"]
    # Resume flag sits before the `--` end-of-options sentinel.
    assert captured["cmd"].index("--resume") < captured["cmd"].index("--")
