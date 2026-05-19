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

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "claude_code_cli"


@pytest.fixture(autouse=True)
def mock_claude_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch `subprocess.run` so `_assert_binary_version("claude")` passes
    without requiring the real `claude` binary in CI.
    """
    real_run = subprocess.run

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "claude" and cmd[1] == "--version":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="2.1.144 (Claude Code)\n", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)


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


def test_finalize_truncated_fixture_with_zero_exit_still_truncated() -> None:
    """If exit_code is 0 BUT no terminal `result` event, still `truncated`."""
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
