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

"""Unit tests for `AgentEval.coding_agent.claude_code_cli.ClaudeCodeCLIAdapter` (Story 4.2)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.claude_code_cli import ClaudeCodeCLIAdapter, ClaudeCodeEvent
from AgentEval.errors import UnsupportedBinaryVersionError
from AgentEval.types import AgentRunResult

# Story 4.2 code-review Edge-cases MED-1 fix 2026-05-20: the
# `mock_claude_version` autouse fixture was hoisted to
# `tests/unit/coding_agent/conftest.py` for cross-module protection.
# This file no longer declares its own fixture.

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "claude_code_cli"


def _load_fixture(name: str) -> list[ClaudeCodeEvent]:
    """Read one of the vendored stream-json fixtures + parse via the adapter."""
    adapter = ClaudeCodeCLIAdapter()
    events: list[ClaudeCodeEvent] = []
    for line in (FIXTURE_DIR / name).read_text().splitlines():
        parsed = adapter._parse_event(line)
        if parsed is not None:
            events.append(parsed)
    return events


# --------------------------------------------------------------------------- #
# Construction + Protocol surface
# --------------------------------------------------------------------------- #


def test_claude_adapter_is_subprocess_adapter() -> None:
    adapter = ClaudeCodeCLIAdapter()
    assert isinstance(adapter, SubprocessAdapter)


def test_claude_adapter_name_is_claude_code_cli() -> None:
    assert ClaudeCodeCLIAdapter().name == "claude-code-cli"


def test_claude_adapter_construction_invokes_version_check() -> None:
    """`__init__` MUST call `_assert_binary_version("claude", min, max)`."""
    # Construction succeeds with mocked claude --version returning 2.1.144.
    adapter = ClaudeCodeCLIAdapter()
    assert adapter.name == "claude-code-cli"


# --------------------------------------------------------------------------- #
# Binary version gate (PRD FR47 / AC-4.2.4 / AC-4.2.8)
# --------------------------------------------------------------------------- #


def test_claude_adapter_raises_on_below_floor_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """`claude --version` returning 1.9.0 → UnsupportedBinaryVersionError."""

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="1.9.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        ClaudeCodeCLIAdapter()
    assert exc_info.value.detected == "1.9.0"
    assert exc_info.value.min_version == "2.0.0"
    assert exc_info.value.max_version == "3.0.0"


def test_claude_adapter_raises_on_above_ceiling_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """`claude --version` returning 3.0.0 → UnsupportedBinaryVersionError (max is exclusive)."""

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="3.0.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(UnsupportedBinaryVersionError):
        ClaudeCodeCLIAdapter()


def test_claude_adapter_accepts_in_range_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any version in `[2.0.0, 3.0.0)` is accepted."""
    for ver in ("2.0.0", "2.1.144", "2.99.0"):

        def _fake_run(cmd: Any, _ver: str = ver, **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=f"{_ver}\n", stderr="")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        ClaudeCodeCLIAdapter()  # MUST NOT raise


def test_claude_adapter_raises_on_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """`FileNotFoundError` on `claude --version` invocation → typed UnsupportedBinaryVersionError."""

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("claude")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(UnsupportedBinaryVersionError):
        ClaudeCodeCLIAdapter()


# --------------------------------------------------------------------------- #
# `_parse_event` (AC-4.2.1 / AC-4.2.2)
# --------------------------------------------------------------------------- #


def test_parse_event_returns_none_on_blank_line() -> None:
    adapter = ClaudeCodeCLIAdapter()
    assert adapter._parse_event("") is None
    assert adapter._parse_event("   \n") is None


def test_parse_event_returns_none_on_non_json_line() -> None:
    adapter = ClaudeCodeCLIAdapter()
    # Progress chatter, debug output — not JSON.
    assert adapter._parse_event("Loading session...") is None


def test_parse_event_returns_none_on_non_object_json() -> None:
    """JSON arrays / scalars are not Claude Code events."""
    adapter = ClaudeCodeCLIAdapter()
    assert adapter._parse_event("[1, 2, 3]") is None
    assert adapter._parse_event('"a string"') is None


def test_parse_event_extracts_event_type() -> None:
    adapter = ClaudeCodeCLIAdapter()
    ev = adapter._parse_event('{"type":"system","subtype":"init"}')
    assert ev is not None
    assert ev.event_type == "system"


def test_parse_event_unknown_type_falls_back_to_unknown() -> None:
    """Forward-compat: events without `type` field are tagged `"unknown"`."""
    adapter = ClaudeCodeCLIAdapter()
    ev = adapter._parse_event('{"foo": "bar"}')
    assert ev is not None
    assert ev.event_type == "unknown"


def test_claude_code_event_raw_defensively_copied() -> None:
    """ClaudeCodeEvent applies M_R6 shallow-copy pattern."""
    src = {"type": "system", "data": "v"}
    ev = ClaudeCodeEvent(event_type="system", raw=src)
    src["data"] = "MUTATED"
    assert ev.raw["data"] == "v"


# --------------------------------------------------------------------------- #
# `_finalize` (AC-4.2.3) — fixture-driven
# --------------------------------------------------------------------------- #


def test_finalize_simple_prompt_fixture() -> None:
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("simple_prompt.jsonl")
    result = adapter._finalize(events, exit_code=0)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Hello, world!"
    assert result.tool_calls == []
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.cost_usd == 0.001234
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "external_mixed"
    assert result.latency_seconds == 1.5  # 1500 ms → 1.5 s


def test_finalize_tool_use_fixture_extracts_tool_calls() -> None:
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("tool_use.jsonl")
    result = adapter._finalize(events, exit_code=0)
    # The final assistant turn produces the response_text.
    assert "Found 2 results" in result.response_text
    # One tool_use block recorded.
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.name == "search"
    assert tc.args == {"query": "hello world"}
    assert tc.source == "adapter"
    # Story 4.2 code-review Edge-cases M5 fix 2026-05-20: pin the
    # Phase-1 DF-4.2-S2 placeholders so when Epic 5 hosted-MCP observer
    # wires real OTel-span correlation + tool-result attribution, this
    # test fails + reminds reviewers to drop the placeholders.
    assert tc.result is None  # Phase-1 placeholder; Epic 5 correlates with tool_result events
    assert tc.error is None  # Phase-1 placeholder
    assert tc.latency_ms == 0.0  # Phase-1 placeholder; Epic 5 correlates real per-call latency
    assert tc.gen_ai_tool_call_id == "toolu_test_1"  # captured from the tool_use block's id


def test_finalize_truncated_fixture_yields_truncated_completeness() -> None:
    """Missing terminal event AND non-zero exit_code → `completeness="truncated"`."""
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("truncated.jsonl")
    result = adapter._finalize(events, exit_code=1)
    assert result.metadata.completeness == "truncated"
    # response_text falls back to the partial assistant text.
    assert "Starting response" in result.response_text
    # Cost defaults to 0.0 when terminal absent.
    assert result.cost_usd == 0.0


def test_finalize_no_terminal_event_yields_truncated_even_with_zero_exit() -> None:
    """If no terminal `result` event exists, completeness="truncated" even when exit_code==0.

    Story 4.2 code-review Edge-cases M4 fix 2026-05-20: renamed for body-name
    alignment per `feedback_test_name_assertion_match`. The PRIMARY cause is
    missing terminal event; zero exit_code is the secondary surprise. Pre-edit
    name `_truncated_fixture_with_zero_exit_still_truncated` over-emphasized
    the exit_code aspect.
    """
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("truncated.jsonl")
    result = adapter._finalize(events, exit_code=0)
    assert result.metadata.completeness == "truncated"


def test_finalize_multi_assistant_takes_final_turn_response() -> None:
    """Multi-assistant fixtures use the TERMINAL result's `result` field as the canonical answer."""
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("multi_assistant.jsonl")
    result = adapter._finalize(events, exit_code=0)
    assert result.response_text == "Final answer: 42"
    assert result.metadata.completeness == "complete"


def test_finalize_is_error_terminal_yields_truncated() -> None:
    """`result.is_error=True` (even with exit_code=0) yields `completeness="truncated"`."""
    adapter = ClaudeCodeCLIAdapter()
    err_event = ClaudeCodeEvent(
        event_type="result",
        raw={
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "duration_ms": 500,
            "result": "Error occurred",
            "total_cost_usd": 0.0001,
            "usage": {"input_tokens": 1, "output_tokens": 0},
        },
    )
    result = adapter._finalize([err_event], exit_code=0)
    assert result.metadata.completeness == "truncated"


def test_finalize_generates_uuid4_trace_id() -> None:
    import re

    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("simple_prompt.jsonl")
    result = adapter._finalize(events, exit_code=0)
    assert re.fullmatch(r"[0-9a-f]{32}", result.trace_id) is not None


def test_finalize_generates_unique_trace_id_per_call() -> None:
    adapter = ClaudeCodeCLIAdapter()
    events = _load_fixture("simple_prompt.jsonl")
    r1 = adapter._finalize(events, exit_code=0)
    r2 = adapter._finalize(events, exit_code=0)
    assert r1.trace_id != r2.trace_id


# --------------------------------------------------------------------------- #
# ClaudeCodeEvent convenience accessors (AC-4.2.2)
# --------------------------------------------------------------------------- #


def test_event_text_content_joins_text_blocks() -> None:
    ev = ClaudeCodeEvent(
        event_type="assistant",
        raw={"message": {"content": [{"type": "text", "text": "Hi"}, {"type": "text", "text": ", world"}]}},
    )
    assert ev.text_content == "Hi, world"


def test_event_text_content_empty_for_non_assistant() -> None:
    ev = ClaudeCodeEvent(event_type="system", raw={"data": "x"})
    assert ev.text_content == ""


def test_event_tool_use_blocks_filters_correctly() -> None:
    ev = ClaudeCodeEvent(
        event_type="assistant",
        raw={
            "message": {
                "content": [
                    {"type": "text", "text": "Calling tool"},
                    {"type": "tool_use", "id": "t1", "name": "search", "input": {"q": "hi"}},
                ]
            }
        },
    )
    blocks = ev.tool_use_blocks
    assert len(blocks) == 1
    assert blocks[0]["name"] == "search"


def test_event_is_terminal_true_only_for_result_events() -> None:
    assert ClaudeCodeEvent(event_type="result", raw={}).is_terminal is True
    assert ClaudeCodeEvent(event_type="assistant", raw={}).is_terminal is False


def test_event_total_cost_usd_extracts_from_result() -> None:
    ev = ClaudeCodeEvent(event_type="result", raw={"total_cost_usd": 0.00123})
    assert ev.total_cost_usd == 0.00123


def test_event_total_cost_usd_none_for_non_result() -> None:
    assert ClaudeCodeEvent(event_type="assistant", raw={}).total_cost_usd is None


def test_event_is_error_extracts_from_result() -> None:
    assert ClaudeCodeEvent(event_type="result", raw={"is_error": True}).is_error is True
    assert ClaudeCodeEvent(event_type="result", raw={"is_error": False}).is_error is False
    assert ClaudeCodeEvent(event_type="result", raw={}).is_error is False


def test_event_terminal_usage_extracts_from_result() -> None:
    ev = ClaudeCodeEvent(
        event_type="result",
        raw={"usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 20}},
    )
    usage = ev.terminal_usage
    assert usage is not None
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cached_input_tokens == 20


def test_event_duration_seconds_converts_ms_to_s() -> None:
    ev = ClaudeCodeEvent(event_type="result", raw={"duration_ms": 1234})
    assert ev.duration_seconds == 1.234


# --------------------------------------------------------------------------- #
# Entry-points registration
# --------------------------------------------------------------------------- #


def test_claude_code_cli_registered_in_coding_agents_entry_points() -> None:
    """`claude-code-cli` MUST be discoverable via `agenteval.coding_agents` entry-points."""
    from AgentEval._kernel.discovery import discover_adapters

    adapters = discover_adapters()
    assert "claude-code-cli" in adapters
    assert adapters["claude-code-cli"] is ClaudeCodeCLIAdapter


# --------------------------------------------------------------------------- #
# Story 4.2 code-review patches 2026-05-20 — additional behavioral tests
# --------------------------------------------------------------------------- #


def test_spawn_passes_prompt_as_positional_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 4.2 code-review 3-way HIGH fix 2026-05-20 (Blind H1 + Edge-cases H1 +
    Codex Probe 5): the prompt MUST appear as the positional argv argument
    after the `--` end-of-options sentinel. Pre-fix `_spawn` opened
    `stdin=subprocess.PIPE` but never wrote the prompt — adapter was
    non-functional in production. This test captures the spawned cmd list
    + verifies the prompt is the final argv element.
    """
    captured_cmd: list[list[str]] = []
    real_popen = subprocess.Popen

    def _fake_popen(cmd: Any, **kwargs: Any) -> Any:
        captured_cmd.append(list(cmd))
        # Return a real Popen against /bin/true so cleanup works.
        return real_popen(["/bin/true"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter = ClaudeCodeCLIAdapter()
    proc = adapter._spawn("Hello, claude!")
    try:
        proc.wait(timeout=5)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    assert len(captured_cmd) == 1
    cmd = captured_cmd[0]
    # Verify the prompt is the final argv element + `--` precedes it.
    assert cmd[-1] == "Hello, claude!"
    assert cmd[-2] == "--"
    assert cmd[0] == "claude"
    assert "--output-format=stream-json" in cmd
    assert "--print" in cmd


def test_spawn_uses_stderr_stdout_multiplex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 4.2 code-review 2-way HIGH fix 2026-05-20 (Edge-cases H2 + Codex):
    `_spawn` MUST use `stderr=subprocess.STDOUT` to avoid pipe-deadlock when
    `--verbose` writes enough stderr to fill the ~64KB Linux pipe buffer.
    Pre-fix used `stderr=subprocess.PIPE` which the base `run()` doesn't drain.
    """
    captured_kwargs: list[dict[str, Any]] = []
    real_popen = subprocess.Popen

    def _fake_popen(cmd: Any, **kwargs: Any) -> Any:
        captured_kwargs.append(dict(kwargs))
        return real_popen(["/bin/true"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter = ClaudeCodeCLIAdapter()
    proc = adapter._spawn("ignored")
    try:
        proc.wait(timeout=5)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    assert captured_kwargs[0]["stderr"] is subprocess.STDOUT
    # AND no `stdin=subprocess.PIPE` (we use positional argv, not stdin).
    assert "stdin" not in captured_kwargs[0] or captured_kwargs[0].get("stdin") is None


def test_run_end_to_end_against_faked_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 4.2 code-review Blind H2 fix 2026-05-20: pre-edit zero tests
    exercised `adapter.run()` end-to-end — all 31 tests bypassed `_spawn` /
    `run()` and drove `_parse_event` + `_finalize` directly. This integration
    test fakes `Popen` to return a stdout pipe streaming the simple_prompt
    fixture, then drives the full `run()` template. Verifies the prompt-
    delivery + event-loop + finalize chain works end-to-end.
    """
    import io

    fixture_lines = (FIXTURE_DIR / "simple_prompt.jsonl").read_text()

    class _FakePopen:
        def __init__(self, cmd: Any, **kwargs: Any) -> None:
            self.cmd = cmd
            self.stdout = io.StringIO(fixture_lines)
            self.stderr = None
            self.returncode = 0
            self.pid = 99999

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            pass

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    adapter = ClaudeCodeCLIAdapter()
    result = adapter.run("ignored — fixture replay")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Hello, world!"
    assert result.cost_usd == 0.001234
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "external_mixed"


def test_finalize_handles_rate_limit_event_as_no_op() -> None:
    """Story 4.2 code-review Edge-cases L1 fix 2026-05-20: real claude output
    interleaves `rate_limit_event` between system + assistant + result. Pin
    that the parser handles it cleanly + `_finalize` skips it without
    affecting the AgentRunResult shape.
    """
    adapter = ClaudeCodeCLIAdapter()
    events = [
        ClaudeCodeEvent(event_type="system", raw={"type": "system", "subtype": "init"}),
        ClaudeCodeEvent(
            event_type="rate_limit_event",
            raw={"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
        ),
        ClaudeCodeEvent(
            event_type="assistant",
            raw={
                "message": {
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            },
        ),
        ClaudeCodeEvent(
            event_type="result",
            raw={
                "type": "result",
                "is_error": False,
                "result": "ok",
                "duration_ms": 100,
                "total_cost_usd": 0.0001,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        ),
    ]
    result = adapter._finalize(events, exit_code=0)
    assert result.response_text == "ok"
    assert result.metadata.completeness == "complete"
    # rate_limit_event neither contributes to tool_calls nor breaks usage.
    assert result.tool_calls == []


def test_finalize_non_string_result_field_falls_back_cleanly() -> None:
    """Story 4.2 code-review Edge-cases M2 fix 2026-05-20: if `terminal.result`
    is a dict/list (forward-compat schema shape change), `_finalize` MUST
    fall back to the last assistant's text_content rather than raise.
    """
    adapter = ClaudeCodeCLIAdapter()
    events = [
        ClaudeCodeEvent(
            event_type="assistant",
            raw={"message": {"content": [{"type": "text", "text": "fallback text"}]}},
        ),
        ClaudeCodeEvent(
            event_type="result",
            raw={
                "type": "result",
                "is_error": False,
                "result": {"unexpected": "dict shape"},  # non-string
                "duration_ms": 50,
                "total_cost_usd": 0.0,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        ),
    ]
    result = adapter._finalize(events, exit_code=0)
    # Falls back to the assistant's text_content; no exception raised.
    assert result.response_text == "fallback text"
    assert result.metadata.completeness == "complete"


def test_finalize_nonzero_exit_no_terminal_yields_diagnostic_marker() -> None:
    """Story 4.2 code-review Codex MED-3 fix 2026-05-20: when subprocess exits
    non-zero AND no terminal event AND no assistant text, surface a structured
    diagnostic marker so consumers can distinguish "agent declined to respond"
    (empty response_text) from "binary refused to run" (SUBPROCESS_NONZERO_EXIT).
    Per `feedback_ci_log_forensics` + M_R11 fail-loud.
    """
    adapter = ClaudeCodeCLIAdapter()
    # No events at all — subprocess emitted nothing before exiting non-zero.
    result = adapter._finalize([], exit_code=1)
    assert "SUBPROCESS_NONZERO_EXIT" in result.response_text
    assert "exit_code=1" in result.response_text
    assert result.metadata.completeness == "truncated"


def test_finalize_nonzero_exit_with_assistant_text_does_not_overwrite() -> None:
    """When the assistant DID emit partial text before non-zero exit, preserve
    the partial text rather than overwriting with the SUBPROCESS_NONZERO_EXIT
    diagnostic. Pin the fallback precedence.
    """
    adapter = ClaudeCodeCLIAdapter()
    events = [
        ClaudeCodeEvent(
            event_type="assistant",
            raw={"message": {"content": [{"type": "text", "text": "partial output"}]}},
        ),
    ]
    result = adapter._finalize(events, exit_code=1)
    assert result.response_text == "partial output"  # NOT overwritten
    assert result.metadata.completeness == "truncated"
