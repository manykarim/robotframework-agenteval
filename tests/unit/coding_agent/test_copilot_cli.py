# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `CopilotCLIAdapter` (Story 11.2).

Mirrors Story 11.1's `test_codex_cli.py` patterns + applies the
UPSTREAM-seed lessons enumerated in Story 11.1's Senior Developer
Review record per `feedback_cross_story_upstream_lesson_propagation`
(2nd application).
"""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.copilot_cli import (
    CopilotCLIAdapter,
    CopilotEvent,
)
from AgentEval.errors import UnsupportedBinaryVersionError
from AgentEval.types import AgentRunResult, ToolCallTrace

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "copilot_cli"


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (FIXTURE_DIR / name).read_text().splitlines() if line.strip()]


def _events_from_fixture(name: str) -> list[CopilotEvent]:
    raw_events = _read_jsonl(name)
    return [CopilotEvent(event_type=str(e.get("type") or "unknown"), raw=e) for e in raw_events]


# --------------------------------------------------------------------------- #
# Version gate                                                                  #
# --------------------------------------------------------------------------- #


def test_version_gate_passes_with_default_mock_version() -> None:
    """Conftest's `mock_copilot_version` stubs ``copilot --version`` →
    ``GitHub Copilot CLI 1.0.54.`` (in range). Construction succeeds.

    Tests Story 11.2 D-11 lesson UPSTREAM: base `_SEMVER_RE.search()`
    extracts `1.0.54` from the prefixed + period-suffixed output.
    """
    adapter = CopilotCLIAdapter()
    assert adapter.name == "copilot-cli"


def test_version_gate_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["copilot", "--version"]:
            raise FileNotFoundError("copilot: command not found")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _missing)
    with pytest.raises(UnsupportedBinaryVersionError):
        CopilotCLIAdapter()


def test_version_gate_raises_below_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    def _below(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["copilot", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="GitHub Copilot CLI 1.0.8\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _below)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        CopilotCLIAdapter()
    assert "1.0.8" in str(exc_info.value)


def test_version_gate_raises_above_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    def _above(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["copilot", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="GitHub Copilot CLI 2.0.0\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _above)
    with pytest.raises(UnsupportedBinaryVersionError):
        CopilotCLIAdapter()


# --------------------------------------------------------------------------- #
# Constructor + ABC inheritance                                                 #
# --------------------------------------------------------------------------- #


def test_inherits_from_subprocess_adapter() -> None:
    assert issubclass(CopilotCLIAdapter, SubprocessAdapter)


def test_constructor_accepts_model_kwarg() -> None:
    adapter = CopilotCLIAdapter(model="claude-sonnet-4.6", extra_key="extra_value")
    assert adapter._model == "claude-sonnet-4.6"
    assert adapter._adapter_config["extra_key"] == "extra_value"


def test_constructor_model_defaults_to_none() -> None:
    adapter = CopilotCLIAdapter()
    assert adapter._model is None


def test_name_property_returns_copilot_cli() -> None:
    assert CopilotCLIAdapter().name == "copilot-cli"


# --------------------------------------------------------------------------- #
# `_parse_event` per event type                                                  #
# --------------------------------------------------------------------------- #


def test_parse_event_session_start() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"session.start","data":{"sessionId":"abc"}}')
    assert event is not None
    assert event.event_type == "session.start"
    assert event.raw["data"]["sessionId"] == "abc"


def test_parse_event_session_model_change() -> None:
    """AC-11.2.4 mandate (Story 11.2 copilot M-3 review 2026-05-26)."""
    event = CopilotCLIAdapter()._parse_event('{"type":"session.model_change","data":{"newModel":"gpt-5"}}')
    assert event is not None
    assert event.event_type == "session.model_change"


def test_parse_event_user_message() -> None:
    """AC-11.2.4 mandate (Story 11.2 copilot M-3 review 2026-05-26)."""
    event = CopilotCLIAdapter()._parse_event('{"type":"user.message","data":{"content":"hi"}}')
    assert event is not None
    assert event.event_type == "user.message"


def test_parse_event_assistant_turn_start() -> None:
    """AC-11.2.4 mandate (Story 11.2 copilot M-3 review 2026-05-26)."""
    event = CopilotCLIAdapter()._parse_event('{"type":"assistant.turn_start","data":{"turnId":"0"}}')
    assert event is not None
    assert event.event_type == "assistant.turn_start"


def test_parse_event_assistant_turn_end() -> None:
    """AC-11.2.4 mandate (Story 11.2 copilot M-3 review 2026-05-26)."""
    event = CopilotCLIAdapter()._parse_event('{"type":"assistant.turn_end","data":{"turnId":"0"}}')
    assert event is not None
    assert event.event_type == "assistant.turn_end"


def test_parse_event_tool_execution_start() -> None:
    """AC-11.2.4 mandate (Story 11.2 copilot M-3 review 2026-05-26)."""
    event = CopilotCLIAdapter()._parse_event(
        '{"type":"tool.execution_start","data":{"toolCallId":"c1","toolName":"shell"}}'
    )
    assert event is not None
    assert event.event_type == "tool.execution_start"


def test_parse_event_session_shutdown_is_terminal() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"session.shutdown","data":{}}')
    assert event is not None
    assert event.is_terminal


def test_parse_event_assistant_message_text_and_output_tokens() -> None:
    line = '{"type":"assistant.message","data":{"messageId":"m1","content":"Hello","toolRequests":[],"outputTokens":42}}'
    event = CopilotCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.assistant_text == "Hello"
    assert event.assistant_output_tokens == 42


def test_parse_event_assistant_message_tool_requests() -> None:
    line = (
        '{"type":"assistant.message","data":{"messageId":"m1","content":"",'
        '"toolRequests":[{"toolCallId":"c1","name":"shell","arguments":{"cmd":"ls"}}],"outputTokens":5}}'
    )
    event = CopilotCLIAdapter()._parse_event(line)
    assert event is not None
    requests = event.tool_requests
    assert len(requests) == 1
    assert requests[0]["toolCallId"] == "c1"
    assert requests[0]["name"] == "shell"


def test_parse_event_tool_execution_complete_payload() -> None:
    line = '{"type":"tool.execution_complete","data":{"toolCallId":"c1","success":true,"result":{"x":1}}}'
    event = CopilotCLIAdapter()._parse_event(line)
    assert event is not None
    payload = event.tool_execution_complete_payload
    assert payload is not None
    assert payload["toolCallId"] == "c1"
    assert payload["success"] is True


def test_parse_event_returns_none_on_non_json() -> None:
    assert CopilotCLIAdapter()._parse_event("Starting up...") is None
    assert CopilotCLIAdapter()._parse_event("") is None


def test_parse_event_returns_none_on_non_string_type() -> None:
    """Forward-compat: non-string type discriminator → None.

    Story 11.1 copilot LOW-1 lesson UPSTREAM (split from generic
    'unknown_type' test per `feedback_test_name_assertion_match`).
    """
    assert CopilotCLIAdapter()._parse_event('{"type":42}') is None


def test_parse_event_returns_none_on_non_dict_json() -> None:
    """Forward-compat: top-level non-dict JSON → None."""
    assert CopilotCLIAdapter()._parse_event("[1,2,3]") is None
    assert CopilotCLIAdapter()._parse_event("42") is None


# --------------------------------------------------------------------------- #
# `_finalize` against fixtures                                                   #
# --------------------------------------------------------------------------- #


def test_finalize_simple_prompt_happy_path() -> None:
    events = _events_from_fixture("simple_prompt.jsonl")
    result = CopilotCLIAdapter()._finalize(events, exit_code=0)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Hi"
    assert result.tool_calls == []
    assert result.usage.output_tokens == 1
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.cost_usd == 0.0


def test_finalize_tool_use_extracts_tool_requests() -> None:
    events = _events_from_fixture("tool_use.jsonl")
    result = CopilotCLIAdapter()._finalize(events, exit_code=0)
    # Both narration + final answer concatenated
    assert "Running echo command" in result.response_text
    assert "Output:" in result.response_text
    # One tool call with completion paired
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert isinstance(tc, ToolCallTrace)
    assert tc.name == "shell"
    assert tc.args == {"command": "echo hello"}
    assert tc.gen_ai_tool_call_id == "call_001"
    assert tc.source == "adapter"
    assert tc.error is None
    # Output tokens summed across both assistant.message events
    assert result.usage.output_tokens == 23  # 15 + 8


def test_finalize_nonzero_exit_with_no_message_emits_diagnostic() -> None:
    """Story 11.2 D-3 (cross-story UPSTREAM from Story 11.1 D-3 +
    Story 4.2 MED-3)."""
    events = _events_from_fixture("nonzero_exit.jsonl")
    result = CopilotCLIAdapter()._finalize(events, exit_code=2)
    assert result.response_text == "[SUBPROCESS_NONZERO_EXIT exit_code=2]"
    assert result.metadata.completeness == "truncated"


def test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic() -> None:
    """Negative-path coverage from Story 11.1 copilot MED-4 UPSTREAM."""
    events = _events_from_fixture("simple_prompt.jsonl")
    result = CopilotCLIAdapter()._finalize(events, exit_code=1)
    assert result.response_text == "Hi"
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text


def test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic() -> None:
    """Negative-path coverage from Story 11.1 copilot MED-4 UPSTREAM."""
    terminal = CopilotEvent(event_type="session.shutdown", raw={"type": "session.shutdown", "data": {}})
    result = CopilotCLIAdapter()._finalize([terminal], exit_code=1)
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text
    assert result.response_text == ""


def test_finalize_reasoning_tokens_populated_if_present() -> None:
    """Story 11.2 D-8 (cross-story UPSTREAM from Story 11.1 kilo HIGH-1):
    if Copilot's assistant.message carries `reasoningTokens`,
    `Usage.reasoning_output_tokens` MUST be populated — no silent drop."""
    events = [
        CopilotEvent(
            event_type="assistant.message",
            raw={"type": "assistant.message", "data": {"content": "x", "outputTokens": 10, "reasoningTokens": 5}},
        ),
        CopilotEvent(event_type="session.shutdown", raw={"type": "session.shutdown", "data": {}}),
    ]
    result = CopilotCLIAdapter()._finalize(events, exit_code=0)
    assert result.usage.output_tokens == 10
    assert result.usage.reasoning_output_tokens == 5


# --------------------------------------------------------------------------- #
# Cross-story UPSTREAM regression guards                                         #
# --------------------------------------------------------------------------- #


def test_spawn_passes_prompt_via_prompt_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.2 D-1 (cross-story UPSTREAM from Story 11.1 D-1 +
    Story 4.2 HIGH-A): prompt passed via `-p` flag, not stdin."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter()._spawn("Find the bug.")
    assert captured["cmd"][0] == "copilot"
    assert "-p" in captured["cmd"]
    p_idx = captured["cmd"].index("-p")
    assert captured["cmd"][p_idx + 1] == "Find the bug."


def test_spawn_includes_allow_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--allow-all-tools` is required for non-interactive mode per
    `copilot --help`."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter()._spawn("hi")
    assert "--allow-all-tools" in captured["cmd"]


def test_spawn_uses_stderr_stdout_multiplex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.2 D-2 (cross-story UPSTREAM from Story 11.1 D-2 + Story 4.2 HIGH-B)."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter()._spawn("hi")
    assert captured["kwargs"]["stderr"] == subprocess.STDOUT
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["stdout"] == subprocess.PIPE


def test_spawn_uses_start_new_session_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 1b.4 D1 process-group hygiene regression guard (AC-11.2.4 mandate;
    Story 11.2 kilo M-2 + copilot M-2 review 2026-05-26).

    `_spawn` MUST set ``start_new_session=True`` so the base
    `_terminate_process_group` can safely SIGTERM the subprocess process
    group without accidentally killing the test runner itself."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter()._spawn("hi")
    assert captured["kwargs"]["start_new_session"] is True


def test_spawn_includes_model_flag_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """When `model=` is passed to the constructor, `_spawn` MUST include
    `--model <model>` in the argv."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter(model="claude-sonnet-4.6")._spawn("hi")
    assert "--model" in captured["cmd"]
    m_idx = captured["cmd"].index("--model")
    assert captured["cmd"][m_idx + 1] == "claude-sonnet-4.6"


def _make_fake_popen_class(returncode: int = 0) -> type:
    """Fake Popen with empty stdout — used for `run()` e2e tests where
    events come from events.jsonl on disk (not stdout)."""
    import io

    class _FakePopen:
        def __init__(self, cmd: Any, **kwargs: Any) -> None:
            self.cmd = cmd
            self.stdout = io.StringIO("")  # Copilot writes to events.jsonl, not stdout
            self.stderr = None
            self.returncode = returncode
            self.pid = 99999

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def terminate(self) -> None:
            pass

    return _FakePopen


def test_run_end_to_end_against_faked_subprocess_and_events_jsonl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Story 11.2 D-9 (Copilot-specific): override `run()` reads
    events.jsonl post-hoc from `~/.copilot/session-state/{uuid}/`.
    Stub the path + fake the Popen + assert end-to-end."""
    # Set up a fake session-state directory with a new session created
    # AFTER the snapshot (simulating the spawn lifecycle).
    fake_session_root = tmp_path / "session-state"
    fake_session_root.mkdir()
    # An old session exists pre-spawn (so the snapshot is non-empty).
    old = fake_session_root / "old-session-uuid"
    old.mkdir()
    (old / "events.jsonl").write_text("{}")
    # Patch the session-root constant to point at our tmp dir.
    monkeypatch.setattr("AgentEval.coding_agent.copilot_cli.DEFAULT_COPILOT_SESSION_STATE_DIR", fake_session_root)
    # Patch the listener helper so the test doesn't depend on RF Listener install.
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", MagicMock())

    # Fake Popen creates a NEW session directory + events.jsonl during "spawn".
    new_session_uuid = "fresh-session-uuid"
    fixture_text = (FIXTURE_DIR / "simple_prompt.jsonl").read_text()

    class _FakePopen:
        def __init__(self, cmd: Any, **kwargs: Any) -> None:
            new_dir = fake_session_root / new_session_uuid
            new_dir.mkdir()
            (new_dir / "events.jsonl").write_text(fixture_text)
            import io

            self.cmd = cmd
            self.stdout = io.StringIO("")
            self.stderr = None
            self.returncode = 0
            self.pid = 12345

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            pass

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    adapter = CopilotCLIAdapter()
    result = adapter.run("Say hi")
    assert result.response_text == "Hi"
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.usage.output_tokens == 1


def test_run_with_unverified_mcp_marks_external_mixed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Story 11.2 D-7 (cross-story UPSTREAM from Stories 10.1 + 10.2 + 11.1)."""
    fake_session_root = tmp_path / "session-state"
    fake_session_root.mkdir()
    monkeypatch.setattr("AgentEval.coding_agent.copilot_cli.DEFAULT_COPILOT_SESSION_STATE_DIR", fake_session_root)
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", MagicMock())

    fixture_text = (FIXTURE_DIR / "simple_prompt.jsonl").read_text()

    class _FakePopen:
        def __init__(self, cmd: Any, **kwargs: Any) -> None:
            new_dir = fake_session_root / "fresh-session-mcp"
            new_dir.mkdir()
            (new_dir / "events.jsonl").write_text(fixture_text)
            import io

            self.cmd = cmd
            self.stdout = io.StringIO("")
            self.stderr = None
            self.returncode = 0
            self.pid = 12345

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            pass

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)

    fake_handle = MagicMock()
    fake_handle.transport = "stdio"
    adapter = CopilotCLIAdapter()
    result = adapter.run("hi", mcp_servers={"echo": fake_handle})
    assert result.metadata.mcp_coverage == "external_mixed"


def test_detect_mcp_coverage_empty_returns_hosted_in_process() -> None:
    assert CopilotCLIAdapter()._detect_mcp_coverage(None) == "hosted_in_process"
    assert CopilotCLIAdapter()._detect_mcp_coverage({}) == "hosted_in_process"


def test_detect_mcp_coverage_nonempty_returns_external_mixed() -> None:
    assert CopilotCLIAdapter()._detect_mcp_coverage({"any": object()}) == "external_mixed"


# --------------------------------------------------------------------------- #
# `CopilotEvent` accessors                                                       #
# --------------------------------------------------------------------------- #


def test_copilot_event_post_init_defensive_copy() -> None:
    raw = {"type": "session.start", "_marker": "original"}
    event = CopilotEvent(event_type="session.start", raw=raw)
    raw["_marker"] = "mutated"
    assert event.raw["_marker"] == "original"


# --------------------------------------------------------------------------- #
# Entry-point registration                                                       #
# --------------------------------------------------------------------------- #


def test_entry_point_registration() -> None:
    eps = importlib.metadata.entry_points(group="agenteval.coding_agents")
    matching = [ep for ep in eps if ep.name == "copilot-cli"]
    assert len(matching) == 1
    loaded = matching[0].load()
    assert loaded is CopilotCLIAdapter
