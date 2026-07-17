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

"""Unit tests for ``ClaudeCodeAdapter`` parse logic.

Drives the reference FULL adapter against RECORDED representative stream-json
fixtures - never the real ``claude`` binary. Covers build_argv shape, stdout
stream normalization (tool calls with an error result, cache-token usage,
native cost, latency, completeness), the newest-transcript fallback when stdout
is thin, and honest-empty behavior when nothing parses.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval._core import cli_adapter as cli_adapter_mod
from AgentEval._core.cli_adapters.claude_code import ClaudeCodeAdapter
from AgentEval._core.types import AgentRunResult

FIXTURES = Path(__file__).parent / "fixtures"
STREAM_JSON = (FIXTURES / "claude_code_stream.jsonl").read_text(encoding="utf-8")
SESSION_JSONL = (FIXTURES / "claude_code_session.jsonl").read_text(encoding="utf-8")


@pytest.fixture
def adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


# --------------------------------------------------------------------------- #
# Metadata / identity                                                         #
# --------------------------------------------------------------------------- #


def test_metadata_and_slug(adapter: ClaudeCodeAdapter) -> None:
    assert adapter.slug == "claude-code"
    assert adapter.name == "claude-code"
    assert adapter.binary_name == "claude"
    assert adapter.fidelity == "FULL"
    assert adapter.validation_ceiling
    assert adapter.pinned_version_range == ("1.0.0", "3.0.0")


# --------------------------------------------------------------------------- #
# build_argv                                                                   #
# --------------------------------------------------------------------------- #


def test_build_argv_shape_and_no_secrets(adapter: ClaudeCodeAdapter) -> None:
    argv = adapter.build_argv("list the files")
    assert argv == [
        "claude",
        "-p",
        "list the files",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    # No secret material is placed on argv; keys flow via the child environment.
    assert not any("sk-" in token or "ANTHROPIC_API_KEY" in token for token in argv)


# --------------------------------------------------------------------------- #
# stdout stream-json normalization                                            #
# --------------------------------------------------------------------------- #


def test_parse_stream_response_text(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output(STREAM_JSON, "", 0, None)
    assert isinstance(result, AgentRunResult)
    # Settled `result` field wins over concatenated assistant text.
    assert result.response_text == "The directory has one file, file.py."


def test_parse_stream_tool_calls(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output(STREAM_JSON, "", 0, None)
    assert [tc.name for tc in result.tool_calls] == ["Bash", "Read"]

    bash, read = result.tool_calls
    assert bash.args == {"command": "ls -la"}
    assert bash.sequence_index == 0
    assert bash.tool_call_id == "toolu_01"
    assert bash.error is None
    assert bash.result == "total 8\ndrwxr-xr-x  2 u u 4096 file.py"
    assert bash.source == "adapter"

    # The Read tool_result was is_error=true: error is captured, result cleared.
    assert read.sequence_index == 1
    assert read.result is None
    assert read.error == "Error: file not found: /tmp/missing.py"


def test_parse_stream_usage_uses_cache_read(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output(STREAM_JSON, "", 0, None)
    # Settled usage comes from the terminal result event.
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 83
    assert result.usage.cached_input_tokens == 2000


def test_parse_stream_native_cost_and_latency(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output(STREAM_JSON, "", 0, None)
    assert result.cost_usd == pytest.approx(0.0731)
    assert result.metadata.metric_source == "native"
    assert result.latency_seconds == pytest.approx(8.45)
    assert result.trace_id == "sess-abc123"


def test_parse_stream_completeness_and_coverage(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output(STREAM_JSON, "", 0, None)
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "subprocess_with_observer"
    # agent_version is left blank for the base to stamp from --version.
    assert result.metadata.agent_version == ""


# --------------------------------------------------------------------------- #
# Session-transcript fallback (thin stdout)                                   #
# --------------------------------------------------------------------------- #


def test_transcript_fallback_when_stdout_thin(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    session_dir = tmp_path / "projects" / "slug"
    session_dir.mkdir(parents=True)
    transcript = session_dir / "sess-abc123.jsonl"
    transcript.write_text(SESSION_JSONL, encoding="utf-8")

    # Stdout is empty (thin) -> adapter reads the newest on-disk transcript.
    result = adapter.parse_output("", "", 0, str(tmp_path))
    # No settled `result` field in a transcript: all assistant text is joined.
    assert result.response_text == "Listing now.You are in /home/u/work."
    assert [tc.name for tc in result.tool_calls] == ["Bash"]
    assert result.tool_calls[0].args == {"command": "pwd"}
    # Transcript carries no terminal result event: usage from the last assistant
    # turn, no native cost, completeness is honestly partial.
    assert result.usage.output_tokens == 9
    assert result.usage.cached_input_tokens == 950
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"
    assert result.metadata.completeness == "partial"


def test_transcript_fallback_prefers_newest(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    older = tmp_path / "old.jsonl"
    newer = tmp_path / "new.jsonl"
    older.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":'
        '[{"type":"text","text":"stale"}],"usage":{"input_tokens":1,"output_tokens":1}}}\n',
        encoding="utf-8",
    )
    newer.write_text(SESSION_JSONL, encoding="utf-8")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    result = adapter.parse_output("", "", 0, str(tmp_path))
    # The newest transcript (SESSION_JSONL) is read, not the stale one.
    assert result.response_text == "Listing now.You are in /home/u/work."
    assert "stale" not in result.response_text


def test_stdout_wins_over_transcript(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    # A present stream-json stdout is used; the transcript is not consulted.
    transcript = tmp_path / "sess.jsonl"
    transcript.write_text(SESSION_JSONL, encoding="utf-8")
    result = adapter.parse_output(STREAM_JSON, "", 0, str(tmp_path))
    assert result.response_text == "The directory has one file, file.py."
    assert result.metadata.metric_source == "native"


# --------------------------------------------------------------------------- #
# Honest-empty behavior                                                        #
# --------------------------------------------------------------------------- #


def test_empty_stdout_no_session_dir_is_honest_empty(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output("", "", 1, None)
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"
    assert result.metadata.completeness == "partial"
    # No numbers fabricated for an unreadable run.
    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0


def test_garbage_stdout_does_not_raise(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.parse_output("not json\n{broken\n", "some stderr", 2, None)
    assert result.response_text == ""
    assert result.metadata.metric_source == "none"


def test_no_result_event_falls_back_to_assistant_text(adapter: ClaudeCodeAdapter) -> None:
    # A truncated stream (assistant events but no terminal result) still parses.
    partial = (
        '{"type":"assistant","message":{"role":"assistant","content":'
        '[{"type":"text","text":"partial answer"}],'
        '"usage":{"input_tokens":5,"cache_read_input_tokens":10,"output_tokens":7}}}\n'
    )
    result = adapter.parse_output(partial, "", 0, None)
    assert result.response_text == "partial answer"
    assert result.usage.output_tokens == 7
    assert result.usage.cached_input_tokens == 10
    assert result.metadata.completeness == "partial"


# --------------------------------------------------------------------------- #
# Full run() path through the base (stubbed subprocess) - version stamping     #
# --------------------------------------------------------------------------- #


def test_run_stamps_probed_version(monkeypatch: pytest.MonkeyPatch, adapter: ClaudeCodeAdapter) -> None:
    """build_argv + parse_output flow through the inherited run(); version is stamped."""
    monkeypatch.setattr(cli_adapter_mod.shutil, "which", lambda name: "/usr/bin/claude")

    def fake_run(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        if "--version" in argv[1:]:
            return SimpleNamespace(stdout="2.1.0 (Claude Code)", stderr="", returncode=0)
        assert argv[0] == "claude" and "stream-json" in argv
        return SimpleNamespace(stdout=STREAM_JSON, stderr="", returncode=0)

    monkeypatch.setattr(cli_adapter_mod.subprocess, "run", fake_run)
    result = adapter.run("list the files")
    assert result.response_text == "The directory has one file, file.py."
    assert result.metadata.metric_source == "native"
    # The base stamps the probed --version onto the blank slot the adapter left.
    assert result.metadata.agent_version == "2.1.0"


# --------------------------------------------------------------------------- #
# Live E2E smoke - skips unless the real binary + credentials are present      #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    shutil.which("claude") is None or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="claude binary and ANTHROPIC_API_KEY required for the live E2E smoke",
)
def test_live_smoke_claude_code() -> None:  # pragma: no cover - live, env-gated
    result = ClaudeCodeAdapter().run("Reply with exactly the word: pong", timeout=120.0)
    assert isinstance(result, AgentRunResult)
    assert result.response_text
    assert result.metadata.agent_version
