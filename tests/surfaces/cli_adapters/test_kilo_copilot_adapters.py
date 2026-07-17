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

"""Unit tests for the DEGRADED kilo + copilot CLI adapters.

The fixtures are representative of the real CLI output shapes confirmed by
inspecting a kilo export transcript (opencode-derived {info, messages/parts})
and a copilot ``events.jsonl`` session log (JSONL events with a
``session.shutdown`` summary). The real binaries are never invoked here - argv
is asserted structurally and parse_output is driven from recorded strings /
temp files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from AgentEval._core.cli_adapters.copilot import CopilotAdapter
from AgentEval._core.cli_adapters.kilo import KiloAdapter
from AgentEval._core.types import AgentRunResult

# --------------------------------------------------------------------------- #
# kilo fixtures                                                               #
# --------------------------------------------------------------------------- #

_KILO_EXPORT: dict[str, Any] = {
    "info": {"id": "ses_x", "time": {"created": 1000, "updated": 5000}},
    "messages": [
        {
            "info": {"id": "msg_u", "role": "user", "time": {"created": 1000}},
            "parts": [{"type": "text", "text": "list the directory", "id": "prt_u"}],
        },
        {
            "info": {
                "id": "msg_a",
                "role": "assistant",
                "cost": 0.0123,
                "tokens": {"input": 2000, "output": 50, "reasoning": 0, "cache": {"write": 0, "read": 1280}},
                "time": {"created": 1100, "completed": 4800},
            },
            "parts": [
                {
                    "type": "tool",
                    "tool": "bash",
                    "callID": "call_1",
                    "state": {
                        "status": "completed",
                        "input": {"command": "ls"},
                        "output": "file.txt\n",
                        "time": {"start": 1200, "end": 1260},
                    },
                    "id": "prt_t1",
                },
                {
                    "type": "tool",
                    "tool": "read",
                    "callID": "call_2",
                    "state": {
                        "status": "error",
                        "input": {"path": "/nope"},
                        "error": "ENOENT",
                        "time": {"start": 1300, "end": 1305},
                    },
                    "id": "prt_t2",
                },
                {"type": "text", "text": "Done: listed the directory.", "id": "prt_a"},
            ],
        },
    ],
}


def _kilo_export_json() -> str:
    return json.dumps(_KILO_EXPORT)


# --------------------------------------------------------------------------- #
# kilo: build_argv                                                            #
# --------------------------------------------------------------------------- #


def test_kilo_build_argv_uses_format_json_and_auto() -> None:
    argv = KiloAdapter().build_argv("do the thing")
    assert argv == ["kilo", "run", "--auto", "--format", "json", "do the thing"]
    # No `--json` misspelling; the prompt is a positional (no secret flags).
    assert "--json" not in argv


# --------------------------------------------------------------------------- #
# kilo: parse_output                                                          #
# --------------------------------------------------------------------------- #


def test_kilo_parse_full_transcript_from_stdout() -> None:
    result = KiloAdapter().parse_output(_kilo_export_json(), "", 0, None)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Done: listed the directory."
    # Native tokens + cost were exposed by the transcript.
    assert result.usage.input_tokens == 2000
    assert result.usage.output_tokens == 50
    assert result.usage.cached_input_tokens == 1280
    assert result.cost_usd == pytest.approx(0.0123)
    assert result.metadata.metric_source == "native"
    assert result.metadata.completeness == "complete"
    assert result.latency_seconds == pytest.approx(3.8)  # (4800 - 1000) / 1000


def test_kilo_parse_tool_calls_projected_in_order_with_error() -> None:
    result = KiloAdapter().parse_output(_kilo_export_json(), "", 0, None)
    assert [t.name for t in result.tool_calls] == ["bash", "read"]
    bash, read = result.tool_calls
    assert bash.args == {"command": "ls"}
    assert bash.result == "file.txt\n"
    assert bash.error is None
    assert bash.sequence_index == 0
    assert bash.tool_call_id == "call_1"
    assert bash.latency_ms == pytest.approx(60.0)
    # The failing tool surfaces its error string.
    assert read.error == "ENOENT"
    assert read.sequence_index == 1


def test_kilo_parse_ndjson_stream_events_deduped() -> None:
    # A `--format json` stream: the same assistant message emitted twice as it
    # updates (cumulative), wrapped in an event envelope. Must NOT double-count.
    envelope = {
        "type": "message.updated",
        "properties": {
            "info": {"id": "msg_a", "role": "assistant", "cost": 0.005, "tokens": {"input": 100, "output": 10}},
            "parts": [
                {"type": "tool", "tool": "bash", "callID": "c1", "state": {"status": "completed", "output": "ok"}},
                {"type": "text", "text": "final answer"},
            ],
        },
    }
    stream = json.dumps(envelope) + "\n" + json.dumps(envelope) + "\n"
    result = KiloAdapter().parse_output(stream, "", 0, None)
    assert result.response_text == "final answer"
    assert result.usage.input_tokens == 100  # not 200
    assert result.usage.output_tokens == 10
    assert result.cost_usd == pytest.approx(0.005)
    assert len(result.tool_calls) == 1


def test_kilo_parse_falls_back_to_session_file(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text(_kilo_export_json(), encoding="utf-8")
    # Empty stdout forces the on-disk transcript fallback.
    result = KiloAdapter().parse_output("", "", 0, str(tmp_path))
    assert result.usage.input_tokens == 2000
    assert result.response_text == "Done: listed the directory."


def test_kilo_parse_empty_is_partial_not_fabricated() -> None:
    result = KiloAdapter().parse_output("", "", 0, None)
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.usage.input_tokens == 0
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"
    assert result.metadata.completeness == "partial"


def test_kilo_ignores_interleaved_log_noise() -> None:
    noisy = "INFO  2026-07-17 starting\n" + _kilo_export_json() + "\nINFO done\n"
    result = KiloAdapter().parse_output(noisy, "", 0, None)
    assert result.usage.input_tokens == 2000


# --------------------------------------------------------------------------- #
# copilot fixtures                                                           #
# --------------------------------------------------------------------------- #

_COPILOT_EVENTS: list[dict[str, Any]] = [
    {"type": "session.start", "data": {}, "timestamp": 1000},
    {
        "type": "assistant.message",
        "timestamp": 1100,
        "data": {
            "content": "",
            "toolRequests": [{"toolCallId": "tc1", "name": "bash", "arguments": {"command": "ls"}, "type": "function"}],
            "outputTokens": 20,
        },
    },
    {
        "type": "tool.execution_start",
        "timestamp": 1150,
        "data": {"toolCallId": "tc1", "toolName": "bash", "arguments": {"command": "ls"}, "turnId": "0"},
    },
    {
        "type": "tool.execution_complete",
        "timestamp": 1200,
        "data": {"toolCallId": "tc1", "success": True, "result": {"content": "file.txt"}, "turnId": "0"},
    },
    {
        "type": "tool.execution_start",
        "timestamp": 1250,
        "data": {"toolCallId": "tc2", "toolName": "read", "arguments": {"path": "/nope"}, "turnId": "0"},
    },
    {
        "type": "tool.execution_complete",
        "timestamp": 1300,
        "data": {"toolCallId": "tc2", "success": False, "result": {"content": "no such file"}, "turnId": "0"},
    },
    {"type": "assistant.message", "timestamp": 1400, "data": {"content": "All done.", "toolRequests": []}},
    {
        "type": "session.shutdown",
        "timestamp": 1500,
        "data": {
            "shutdownType": "routine",
            "totalPremiumRequests": 3,
            "sessionStartTime": 1000,
            "modelMetrics": {
                "claude-sonnet-4.6": {
                    "requests": {"count": 2, "cost": 3},
                    "usage": {
                        "inputTokens": 2145889,
                        "outputTokens": 19580,
                        "cacheReadTokens": 2032988,
                        "cacheWriteTokens": 105067,
                    },
                }
            },
        },
    },
]


def _copilot_jsonl(events: list[dict[str, Any]] | None = None) -> str:
    return "\n".join(json.dumps(e) for e in (events if events is not None else _COPILOT_EVENTS)) + "\n"


# --------------------------------------------------------------------------- #
# copilot: build_argv                                                        #
# --------------------------------------------------------------------------- #


def test_copilot_build_argv_requests_json_and_allows_tools() -> None:
    argv = CopilotAdapter().build_argv("do the thing")
    assert argv == ["copilot", "-p", "do the thing", "--allow-all-tools", "--output-format", "json"]


# --------------------------------------------------------------------------- #
# copilot: parse_output                                                      #
# --------------------------------------------------------------------------- #


def test_copilot_parse_events_from_stdout() -> None:
    result = CopilotAdapter().parse_output(_copilot_jsonl(), "", 0, None)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "All done."  # only the non-empty content
    assert result.usage.input_tokens == 2145889
    assert result.usage.output_tokens == 19580
    assert result.usage.cached_input_tokens == 2032988
    assert result.metadata.completeness == "complete"
    assert result.latency_seconds == pytest.approx(0.5)  # (1500 - 1000) / 1000


def test_copilot_never_reports_usd_cost() -> None:
    result = CopilotAdapter().parse_output(_copilot_jsonl(), "", 0, None)
    # premiumRequests is a request counter, not dollars -> cost stays 0, none.
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"


def test_copilot_tool_calls_match_start_to_complete() -> None:
    result = CopilotAdapter().parse_output(_copilot_jsonl(), "", 0, None)
    assert [t.name for t in result.tool_calls] == ["bash", "read"]
    bash, read = result.tool_calls
    assert bash.args == {"command": "ls"}
    assert bash.result == "file.txt"
    assert bash.error is None
    assert bash.tool_call_id == "tc1"
    assert bash.sequence_index == 0
    # A failed tool surfaces success=False as an error string.
    assert read.error == "no such file"
    assert read.sequence_index == 1


def test_copilot_tool_calls_fallback_to_tool_requests() -> None:
    # No execution_start events: reconstruct request-only traces (no results).
    thin = [e for e in _COPILOT_EVENTS if not e["type"].startswith("tool.execution")]
    result = CopilotAdapter().parse_output(_copilot_jsonl(thin), "", 0, None)
    assert [t.name for t in result.tool_calls] == ["bash"]
    assert result.tool_calls[0].args == {"command": "ls"}
    assert result.tool_calls[0].result is None


def test_copilot_parse_falls_back_to_session_log(tmp_path: Path) -> None:
    session = tmp_path / "abc-uuid"
    session.mkdir()
    (session / "events.jsonl").write_text(_copilot_jsonl(), encoding="utf-8")
    # Empty stdout forces the on-disk events.jsonl fallback under session_dir.
    result = CopilotAdapter().parse_output("", "", 0, str(tmp_path))
    assert result.usage.input_tokens == 2145889
    assert result.response_text == "All done."


def test_copilot_parse_empty_is_partial(tmp_path: Path) -> None:
    # Point session_dir at an empty dir so the real ~/.copilot is not consulted.
    result = CopilotAdapter().parse_output("", "", 0, str(tmp_path))
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.usage.input_tokens == 0
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"
    assert result.metadata.completeness == "partial"


def test_copilot_truncated_when_no_shutdown(tmp_path: Path) -> None:
    # Events present but the session never emitted session.shutdown.
    no_shutdown = [e for e in _COPILOT_EVENTS if e["type"] != "session.shutdown"]
    result = CopilotAdapter().parse_output(_copilot_jsonl(no_shutdown), "", 0, str(tmp_path))
    assert result.metadata.completeness == "truncated"
    assert result.usage.input_tokens == 0  # token totals only come from shutdown
