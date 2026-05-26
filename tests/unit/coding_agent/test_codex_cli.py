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

"""Unit tests for `CodexCLIAdapter` (Story 11.1).

Mirrors `tests/unit/coding_agent/test_claude_code_cli.py` patterns +
adds cross-story UPSTREAM regression guards per
`feedback_cross_story_upstream_lesson_propagation` (Epic 10 retro NEW
norm, 1st application). Each guard test name includes the source-
story / source-finding citation in its docstring.
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
from AgentEval.coding_agent.codex_cli import (
    CodexCLIAdapter,
    CodexEvent,
)
from AgentEval.errors import UnsupportedBinaryVersionError
from AgentEval.types import AgentRunResult, ToolCallTrace

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "codex_cli"


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    """Load a JSONL fixture file as a list of parsed dicts."""
    return [json.loads(line) for line in (FIXTURE_DIR / name).read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# Version gate (4 tests per AC-11.1.4)                                        #
# --------------------------------------------------------------------------- #


def test_version_gate_passes_with_default_mock_version() -> None:
    """Conftest's `mock_codex_version` fixture stubs ``codex --version`` →
    ``codex-cli 0.133.0``, which is in range. Construction succeeds."""
    adapter = CodexCLIAdapter()
    assert adapter.name == "codex-cli"


def test_version_gate_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """FileNotFoundError on ``codex --version`` → `UnsupportedBinaryVersionError`."""

    def _missing(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["codex", "--version"]:
            raise FileNotFoundError("codex: command not found")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _missing)
    with pytest.raises(UnsupportedBinaryVersionError):
        CodexCLIAdapter()


def test_version_gate_raises_below_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """``codex-cli 0.99.0`` is below the floor 0.100.0 → typed error."""

    def _below(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["codex", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex-cli 0.99.0\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _below)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        CodexCLIAdapter()
    assert "0.99.0" in str(exc_info.value)


def test_version_gate_raises_above_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """``codex-cli 1.0.0`` is at the exclusive ceiling 1.0.0 → typed error."""

    def _above(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["codex", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex-cli 1.0.0\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _above)
    with pytest.raises(UnsupportedBinaryVersionError):
        CodexCLIAdapter()


# --------------------------------------------------------------------------- #
# Constructor + ABC inheritance                                                #
# --------------------------------------------------------------------------- #


def test_inherits_from_subprocess_adapter() -> None:
    """Story 11.1 AC-11.1.1: must subclass `SubprocessAdapter` per ADR-003."""
    assert issubclass(CodexCLIAdapter, SubprocessAdapter)


def test_constructor_accepts_model_kwarg() -> None:
    """`__init__(*, model="gpt-5-codex")` stores the model + forwards **kwargs."""
    adapter = CodexCLIAdapter(model="gpt-5-codex", extra_key="extra_value")
    assert adapter._model == "gpt-5-codex"
    assert adapter._adapter_config["extra_key"] == "extra_value"


def test_constructor_model_defaults_to_none() -> None:
    """Default `model=None` per AC-11.1.1 signature."""
    adapter = CodexCLIAdapter()
    assert adapter._model is None


def test_name_property_returns_codex_cli() -> None:
    """Adapter name MUST be ``codex-cli`` (matches entry-point slug)."""
    assert CodexCLIAdapter().name == "codex-cli"


def test_version_property_returns_distribution_version() -> None:
    """`SubprocessAdapter.version` returns the distribution version string."""
    adapter = CodexCLIAdapter()
    assert isinstance(adapter.version, str)
    assert adapter.version  # non-empty


# --------------------------------------------------------------------------- #
# `_parse_event` per AC-11.1.4 (7 tests)                                       #
# --------------------------------------------------------------------------- #


def test_parse_event_thread_started() -> None:
    """``thread.started`` produces a `CodexEvent` carrying ``thread_id`` in raw."""
    event = CodexCLIAdapter()._parse_event('{"type":"thread.started","thread_id":"abc-123"}')
    assert event is not None
    assert event.event_type == "thread.started"
    assert event.raw["thread_id"] == "abc-123"


def test_parse_event_turn_started() -> None:
    event = CodexCLIAdapter()._parse_event('{"type":"turn.started"}')
    assert event is not None
    assert event.event_type == "turn.started"


def test_parse_event_item_completed_agent_message() -> None:
    """``item.completed`` with ``item.type=agent_message`` exposes ``agent_message_text``."""
    line = '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hi"}}'
    event = CodexCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.event_type == "item.completed"
    assert event.item_type == "agent_message"
    assert event.agent_message_text == "Hi"


def test_parse_event_item_completed_command_execution() -> None:
    """``item.completed`` with ``item.type=command_execution`` exposes payload."""
    line = (
        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
        '"command":"echo hi","aggregated_output":"hi\\n","exit_code":0,"status":"completed"}}'
    )
    event = CodexCLIAdapter()._parse_event(line)
    assert event is not None
    payload = event.command_execution_payload
    assert payload is not None
    assert payload["command"] == "echo hi"
    assert payload["aggregated_output"] == "hi\n"
    assert payload["exit_code"] == 0


def test_parse_event_turn_completed_usage() -> None:
    """Full 4-field shape assertion per kilo L-2 cross-LLM review 2026-05-26:
    `reasoning_output_tokens` MUST be preserved (was silently dropped pre-
    kilo HIGH-1 patch). Regression-guard for the `Usage` 4-field extension.
    """
    line = (
        '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":50,'
        '"output_tokens":20,"reasoning_output_tokens":5}}'
    )
    event = CodexCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.is_terminal
    usage = event.terminal_usage
    assert usage is not None
    assert usage.input_tokens == 100
    assert usage.output_tokens == 20
    assert usage.cached_input_tokens == 50
    # kilo HIGH-1 + L-2 regression guard: 4th field MUST be preserved.
    assert usage.reasoning_output_tokens == 5


def test_parse_event_returns_none_on_non_json_line() -> None:
    """Stderr chatter multiplexed in per D-2 must be skipped without raising."""
    assert CodexCLIAdapter()._parse_event("Starting up...") is None
    assert CodexCLIAdapter()._parse_event("") is None
    assert CodexCLIAdapter()._parse_event("   \n") is None


def test_parse_event_returns_none_on_non_string_type() -> None:
    """Forward-compat: type discriminator must be a string; non-string → None.

    Split from `test_parse_event_returns_none_on_unknown_type` per copilot
    cross-LLM review LOW-1 2026-05-26 (`feedback_test_name_assertion_match` —
    original test bundled two semantically-distinct failure modes).
    """
    event = CodexCLIAdapter()._parse_event('{"type":42}')
    assert event is None


def test_parse_event_returns_none_on_non_dict_json() -> None:
    """Forward-compat: top-level JSON must be a dict; non-dict (e.g., list,
    string, number) → None. Split per copilot LOW-1 from the original
    `_returns_none_on_unknown_type` test.
    """
    assert CodexCLIAdapter()._parse_event("[1, 2, 3]") is None
    assert CodexCLIAdapter()._parse_event('"just-a-string"') is None
    assert CodexCLIAdapter()._parse_event("42") is None


# --------------------------------------------------------------------------- #
# `_finalize` against the 4 fixtures (AC-11.1.4)                               #
# --------------------------------------------------------------------------- #


def _events_from_fixture(name: str) -> list[CodexEvent]:
    raw_events = _read_jsonl(name)
    return [CodexEvent(event_type=str(e.get("type") or "unknown"), raw=e) for e in raw_events]


def test_finalize_simple_prompt_happy_path() -> None:
    """`simple_prompt.jsonl` (real probe): clean exit + terminal + agent_message."""
    events = _events_from_fixture("simple_prompt.jsonl")
    result = CodexCLIAdapter()._finalize(events, exit_code=0)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Hi"
    assert result.tool_calls == []
    assert result.usage.input_tokens == 23160
    assert result.usage.output_tokens == 5
    assert result.usage.cached_input_tokens == 4480
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.cost_usd == 0.0


def test_finalize_tool_use_extracts_command_execution() -> None:
    """`tool_use.jsonl` (real probe): two agent_messages bracketing a command_execution."""
    events = _events_from_fixture("tool_use.jsonl")
    result = CodexCLIAdapter()._finalize(events, exit_code=0)
    # Both narration + final answer concatenated
    assert "Running `echo hello`" in result.response_text
    assert "`echo hello` produced" in result.response_text
    # Exactly one command_execution tool call projected
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert isinstance(tc, ToolCallTrace)
    assert tc.name == "command_execution"
    assert tc.args == {"command": "/bin/bash -lc 'echo hello'"}
    assert tc.result == "hello\n"
    assert tc.error is None
    assert tc.source == "adapter"
    assert tc.sequence_index == 0
    assert result.metadata.completeness == "complete"


def test_finalize_truncated_no_terminal_yields_truncated() -> None:
    """`truncated.jsonl`: missing `turn.completed` → completeness=truncated.

    Story 4.2 Edge-cases MED-4 lesson UPSTREAM (test-name vs assertion-body
    match): the test name explicitly states "no_terminal" because that's
    the load-bearing condition, NOT the exit code.
    """
    events = _events_from_fixture("truncated.jsonl")
    result = CodexCLIAdapter()._finalize(events, exit_code=0)
    # Has the narration, but no terminal → truncated
    assert result.response_text == "Starting work..."
    assert result.metadata.completeness == "truncated"
    # Usage falls back to zeros on truncated
    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0


def test_finalize_nonzero_exit_with_no_message_emits_diagnostic() -> None:
    """Story 11.1 D-3 (cross-story UPSTREAM from Story 4.2 MED-3):
    when exit_code != 0 AND no terminal AND no agent_message text, surface
    the ``[SUBPROCESS_NONZERO_EXIT exit_code=<N>]`` diagnostic marker
    instead of silently returning empty response_text."""
    events = _events_from_fixture("nonzero_exit.jsonl")
    result = CodexCLIAdapter()._finalize(events, exit_code=2)
    assert result.response_text == "[SUBPROCESS_NONZERO_EXIT exit_code=2]"
    assert result.metadata.completeness == "truncated"


def test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic() -> None:
    """Copilot cross-LLM review MED-4 2026-05-26 negative-path coverage:
    when exit_code != 0 BUT response_text was populated (agent_message
    landed before the subprocess died), the diagnostic suppression branch
    of the 3-condition guard MUST fire — response_text wins."""
    events = _events_from_fixture("simple_prompt.jsonl")  # has "Hi" agent_message
    result = CodexCLIAdapter()._finalize(events, exit_code=1)
    assert result.response_text == "Hi"
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text


def test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic() -> None:
    """Copilot cross-LLM review MED-4 2026-05-26 negative-path coverage:
    when exit_code != 0 BUT a `turn.completed` terminal event was observed,
    the diagnostic gate's `terminal is None` condition fails → no marker
    appended. Regression-guard against a future refactor dropping the
    `terminal is None` part of the 3-condition guard."""
    # Construct a synthetic event stream: terminal only, no agent_message
    terminal = CodexEvent(
        event_type="turn.completed",
        raw={"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
    )
    result = CodexCLIAdapter()._finalize([terminal], exit_code=1)
    # response_text is empty (no agent_message) AND exit_code != 0 BUT terminal is present
    # → diagnostic suppressed by the `terminal is None` guard.
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text
    assert result.response_text == ""


# --------------------------------------------------------------------------- #
# Cross-story UPSTREAM regression guards (per `feedback_cross_story_upstream_lesson_propagation`)
# --------------------------------------------------------------------------- #


def test_spawn_passes_prompt_as_positional_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.1 D-1 (cross-story UPSTREAM from Story 4.2 HIGH-A):
    the prompt MUST be passed as positional argv to ``codex exec``, NOT
    via stdin (stdin caused 4-second indefinite hang on Claude Code)."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter = CodexCLIAdapter()
    adapter._spawn("Find the largest file.")
    assert captured["cmd"][0] == "codex"
    assert captured["cmd"][1] == "exec"
    # The prompt is the LAST positional argument
    assert captured["cmd"][-1] == "Find the largest file."


def test_spawn_uses_stderr_stdout_multiplex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.1 D-2 (cross-story UPSTREAM from Story 4.2 HIGH-B):
    ``stderr=subprocess.STDOUT`` multiplex avoids pipe-deadlock under
    verbose subprocess output."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CodexCLIAdapter()._spawn("hi")
    assert captured["kwargs"]["stderr"] == subprocess.STDOUT


def test_spawn_uses_start_new_session_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 1b.4 D1 process-group hygiene: ``start_new_session=True`` so
    cleanup-on-exception can ``os.killpg`` the whole subprocess group."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CodexCLIAdapter()._spawn("hi")
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["stdout"] == subprocess.PIPE


def test_spawn_includes_dangerous_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """The non-interactive sandbox-bypass flags MUST be in the argv list."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CodexCLIAdapter()._spawn("hi")
    assert "--dangerously-bypass-approvals-and-sandbox" in captured["cmd"]
    assert "--skip-git-repo-check" in captured["cmd"]
    assert "--json" in captured["cmd"]


def _make_fake_popen_class(fixture_filename: str, returncode: int = 0) -> type:
    """Build a `_FakePopen` class replaying a fixture file (Story 4.2 e2e
    pattern — closeable stdout via `io.StringIO` so the base `run()`'s
    `proc.stdout.close()` cleanup path works)."""
    import io

    fixture_text = (FIXTURE_DIR / fixture_filename).read_text()

    class _FakePopen:
        def __init__(self, cmd: Any, **kwargs: Any) -> None:
            self.cmd = cmd
            self.stdout = io.StringIO(fixture_text)
            self.stderr = None
            self.returncode = returncode
            self.pid = 99999

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

        def terminate(self) -> None:
            pass

    return _FakePopen


def test_run_end_to_end_against_faked_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.1 cross-story UPSTREAM (Story 4.2 Blind H2 closure mirror):
    drives the full template-method `run()` chain end-to-end with a faked
    Popen replaying `simple_prompt.jsonl`. Pre-edit zero tests exercised
    this path."""
    monkeypatch.setattr(subprocess, "Popen", _make_fake_popen_class("simple_prompt.jsonl"))
    fake_listener = MagicMock()
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", fake_listener)

    adapter = CodexCLIAdapter()
    result = adapter.run("Say hi in one word, no thinking.")
    assert result.response_text == "Hi"
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"  # empty mcp_servers
    assert result.usage.input_tokens == 23160
    # Verify the listener helper was called once (HIGH-4 lesson applied UPSTREAM)
    assert fake_listener.call_count == 1
    call_kwargs = fake_listener.call_args.kwargs
    assert call_kwargs["adapter_name"] == "codex-cli"
    assert call_kwargs["completeness"] == "complete"


def test_run_with_unverified_mcp_marks_external_mixed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 11.1 D-7 (cross-story UPSTREAM from Stories 10.1 + 10.2):
    non-empty ``mcp_servers`` MUST be marked ``external_mixed`` per
    ADR-016 L59 (safer-default rule) until observer wiring lands
    (DF-11.1-S1)."""
    monkeypatch.setattr(subprocess, "Popen", _make_fake_popen_class("simple_prompt.jsonl"))
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", MagicMock())

    adapter = CodexCLIAdapter()
    # Non-empty mcp_servers with a fake handle should NOT optimistically
    # mark hosted_in_process.
    fake_handle = MagicMock()
    fake_handle.transport = "stdio"
    result = adapter.run("hi", mcp_servers={"echo": fake_handle})
    assert result.metadata.mcp_coverage == "external_mixed"


def test_detect_mcp_coverage_empty_returns_hosted_in_process() -> None:
    """Empty / None mcp_servers → trivially honest `hosted_in_process`."""
    adapter = CodexCLIAdapter()
    assert adapter._detect_mcp_coverage(None) == "hosted_in_process"
    assert adapter._detect_mcp_coverage({}) == "hosted_in_process"


def test_detect_mcp_coverage_nonempty_returns_external_mixed() -> None:
    """Non-empty mcp_servers → ADR-016 L59 safer-default `external_mixed`."""
    adapter = CodexCLIAdapter()
    assert adapter._detect_mcp_coverage({"any": object()}) == "external_mixed"


# --------------------------------------------------------------------------- #
# `CodexEvent` accessors                                                       #
# --------------------------------------------------------------------------- #


def test_codex_event_post_init_defensive_copy() -> None:
    """`__post_init__` shallow-copies raw so caller mutations don't leak."""
    raw = {"type": "turn.started", "_marker": "original"}
    event = CodexEvent(event_type="turn.started", raw=raw)
    raw["_marker"] = "mutated"
    assert event.raw["_marker"] == "original"


def test_codex_event_item_type_returns_empty_for_non_item_event() -> None:
    """`item_type` returns empty string for non-`item.*` events."""
    event = CodexEvent(event_type="turn.completed", raw={"type": "turn.completed"})
    assert event.item_type == ""


def test_codex_event_command_execution_payload_returns_none_for_in_progress() -> None:
    """In-progress (`item.started`) commands return None — we only project completed ones."""
    line = (
        '{"type":"item.started","item":{"id":"item_1","type":"command_execution",'
        '"command":"echo hi","aggregated_output":"","exit_code":null,"status":"in_progress"}}'
    )
    event = CodexCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.command_execution_payload is None


def test_finalize_command_execution_with_nonzero_exit_marks_error() -> None:
    """A command_execution with non-zero exit_code projects with `error` set."""
    line = (
        '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
        '"command":"false","aggregated_output":"","exit_code":1,"status":"completed"}}'
    )
    event = CodexCLIAdapter()._parse_event(line)
    assert event is not None
    terminal = CodexEvent(event_type="turn.completed", raw={"type": "turn.completed", "usage": {}})
    result = CodexCLIAdapter()._finalize([event, terminal], exit_code=0)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error == "exit_code=1"


# --------------------------------------------------------------------------- #
# Entry-point registration (AC-11.1.6 — conformance smoke)                     #
# --------------------------------------------------------------------------- #


def test_entry_point_registration() -> None:
    """`importlib.metadata.entry_points` returns `CodexCLIAdapter` under
    `agenteval.coding_agents` slug `codex-cli`. Conformance smoke per
    AC-11.1.6 (mirrors Story 10.1's in-suite smoke pattern)."""
    eps = importlib.metadata.entry_points(group="agenteval.coding_agents")
    matching = [ep for ep in eps if ep.name == "codex-cli"]
    assert len(matching) == 1, f"Expected exactly one `codex-cli` entry-point; got {[ep.name for ep in eps]}"
    loaded = matching[0].load()
    assert loaded is CodexCLIAdapter
