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

"""Unit tests for ``CodexAdapter.build_argv`` + ``parse_output``.

Uses a RECORDED/representative ``codex exec --json`` JSONL stream - the real
``codex`` binary is never invoked. Exercises cumulative-token de-cumulation,
command/MCP tool-call projection, and the rollout-transcript fallback.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from AgentEval._core.cli_adapters.codex import CodexAdapter

# Representative codex `exec --json` JSONL. Two turns; token usage is CUMULATIVE
# (turn 2's snapshot includes turn 1). One shell command succeeds, one fails,
# one MCP tool call runs.
_EVENTS = [
    {"type": "thread.started", "thread_id": "t1", "model": "gpt-5-codex"},
    {"type": "turn.started"},
    {
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "ls -la", "exit_code": 0, "aggregated_output": "file.py"},
    },
    {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "docs",
            "tool": "search",
            "arguments": {"query": "usage"},
            "result": "found",
            "status": "completed",
        },
    },
    {"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 200, "cached_input_tokens": 40}},
    {
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "pytest", "exit_code": 1, "aggregated_output": "1 failed"},
    },
    # Cumulative: this snapshot is the running total across both turns.
    {"type": "turn.completed", "usage": {"input_tokens": 1750, "output_tokens": 480, "cached_input_tokens": 40}},
    {"type": "item.completed", "item": {"type": "assistant_message", "text": "Fixed the failing test."}},
]

_RECORDED_JSONL = "\n".join(json.dumps(e) for e in _EVENTS)


@pytest.fixture
def _stub_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("litellm")

    def _cost(**kwargs: Any) -> float:
        return 0.0456

    fake.completion_cost = _cost  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)


def test_build_argv_runs_non_interactively_with_a_bounded_sandbox() -> None:
    # codex 0.144.4+ needs --skip-git-repo-check and a non-interactive execution
    # mode; the default is a bounded sandbox + approval_policy=never, NOT the
    # dangerous full bypass.
    argv = CodexAdapter().build_argv("fix the bug")
    assert argv == [
        "codex",
        "exec",
        "fix the bug",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-c",
        "approval_policy=never",
    ]
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


def test_build_argv_sandbox_mode_is_configurable() -> None:
    argv = CodexAdapter(sandbox="read-only").build_argv("x")
    assert "--sandbox" in argv and argv[argv.index("--sandbox") + 1] == "read-only"


def test_build_argv_dangerous_bypass_is_opt_in() -> None:
    argv = CodexAdapter(dangerous_bypass=True).build_argv("x")
    assert "--dangerously-bypass-approvals-and-sandbox" in argv
    # the sandbox flags are dropped when the full bypass is chosen
    assert "--sandbox" not in argv and "approval_policy=never" not in argv


def test_invalid_sandbox_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="sandbox must be one of"):
        CodexAdapter(sandbox="bogus")


def test_parse_output_handles_live_0_144_schema() -> None:
    # The exact shape captured live from codex 0.144.4/0.147.0: assistant text on
    # item.type == "agent_message" and cumulative usage under turn.completed.
    events = [
        {"type": "thread.started", "thread_id": "01a0"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "PONG"}},
        {"type": "turn.completed", "usage": {"input_tokens": 14619, "cached_input_tokens": 9984, "output_tokens": 6}},
    ]
    result = CodexAdapter().parse_output("\n".join(json.dumps(e) for e in events), "", 0, None)
    assert result.response_text == "PONG"
    assert result.usage.input_tokens == 14619
    assert result.usage.output_tokens == 6
    assert result.usage.cached_input_tokens == 9984


def test_parse_output_response_is_last_assistant_message() -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, None)
    assert result.response_text == "Fixed the failing test."


def test_parse_output_decumulates_token_usage() -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, None)
    # Final cumulative snapshot is the run total (de-cumulated deltas re-sum to it).
    assert result.usage.input_tokens == 1750
    assert result.usage.output_tokens == 480
    assert result.usage.cached_input_tokens == 40


def test_decumulation_handles_a_mid_run_reset() -> None:
    # Two independent cumulative sequences (a reset between them): 1000 then 300.
    events = [
        {"type": "thread.started", "model": "gpt-5-codex"},
        {"type": "turn.completed", "usage": {"input_tokens": 600, "output_tokens": 100}},
        {"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 200}},
        # reset (smaller than previous) -> counted fresh
        {"type": "turn.completed", "usage": {"input_tokens": 300, "output_tokens": 50}},
    ]
    jsonl = "\n".join(json.dumps(e) for e in events)
    result = CodexAdapter().parse_output(jsonl, "", 0, None)
    assert result.usage.input_tokens == 1000 + 300
    assert result.usage.output_tokens == 200 + 50


def test_parse_output_projects_command_and_mcp_tool_calls() -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, None)
    assert len(result.tool_calls) == 3
    first, mcp, third = result.tool_calls
    assert first.name == "command_execution"
    assert first.args == {"command": "ls -la"}
    assert first.result == "file.py"
    assert first.error is None
    assert first.source == "adapter"

    assert mcp.name == "docs.search"
    assert mcp.args == {"query": "usage"}
    assert mcp.result == "found"
    assert mcp.source == "hosted_mcp"

    assert third.name == "command_execution"
    assert third.error is not None and "1" in third.error
    assert [t.sequence_index for t in result.tool_calls] == [0, 1, 2]


def test_parse_output_cost_is_derived(_stub_litellm: None) -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, None)
    assert result.cost_usd == pytest.approx(0.0456)
    assert result.metadata.metric_source == "derived"


def test_parse_output_cost_none_when_no_model() -> None:
    events = [
        {"type": "item.completed", "item": {"type": "assistant_message", "text": "hi"}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}},
    ]
    jsonl = "\n".join(json.dumps(e) for e in events)
    result = CodexAdapter().parse_output(jsonl, "", 0, None)
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"


def test_parse_output_latency_stays_zero() -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, None)
    assert result.latency_seconds == 0.0


def test_parse_output_nonzero_exit_marks_partial() -> None:
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 7, None)
    assert result.metadata.completeness == "partial"


def test_parse_output_empty_stdout_and_no_session_is_safe() -> None:
    result = CodexAdapter().parse_output("", "", 0, None)
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.usage.input_tokens == 0
    assert result.metadata.metric_source == "none"


def test_rollout_fallback_reads_newest_transcript(tmp_path: Path) -> None:
    # Thin stdout -> adapter reads the newest *.jsonl under the session dir.
    transcript = tmp_path / "rollout-2026.jsonl"
    transcript.write_text(_RECORDED_JSONL, encoding="utf-8")
    result = CodexAdapter().parse_output("", "", 0, str(tmp_path))
    assert result.response_text == "Fixed the failing test."
    assert result.usage.input_tokens == 1750
    assert len(result.tool_calls) == 3


def test_rollout_fallback_accepts_top_level_item_fields(tmp_path: Path) -> None:
    # Some rollout lines carry item fields at top level (no "item" envelope).
    events = [
        {"type": "command_execution", "command": "echo hi", "exit_code": 0, "aggregated_output": "hi"},
        {"type": "assistant_message", "text": "done"},
        {"usage": {"input_tokens": 50, "output_tokens": 5}},
    ]
    (tmp_path / "r.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    result = CodexAdapter().parse_output("", "", 0, str(tmp_path))
    assert result.response_text == "done"
    assert len(result.tool_calls) == 1
    assert result.usage.input_tokens == 50


def test_stdout_takes_precedence_over_rollout(tmp_path: Path) -> None:
    (tmp_path / "old.jsonl").write_text(
        json.dumps({"type": "item.completed", "item": {"type": "assistant_message", "text": "STALE"}}),
        encoding="utf-8",
    )
    result = CodexAdapter().parse_output(_RECORDED_JSONL, "", 0, str(tmp_path))
    assert result.response_text == "Fixed the failing test."


def test_fidelity_and_ceiling_are_honest() -> None:
    adapter = CodexAdapter()
    assert adapter.fidelity == "PARTIAL"
    ceiling = adapter.validation_ceiling.lower()
    assert "cumulative" in ceiling or "de-cumulate" in ceiling
    assert "derived" in ceiling


# --------------------------------------------------------------------------- #
# Live smoke - gated on the codex binary + explicit opt-in (spends credits).  #
# --------------------------------------------------------------------------- #

_LIVE = pytest.mark.skipif(
    os.environ.get("AGENTEVAL_LIVE_CLI_SMOKE") != "1",
    reason="set AGENTEVAL_LIVE_CLI_SMOKE=1 to run live codex smoke (spends credits)",
)


@_LIVE
def test_codex_live_smoke() -> None:
    import shutil
    import tempfile

    if shutil.which(CodexAdapter.binary_name) is None:
        pytest.skip("codex binary not installed")
    # Drives the real codex CLI end to end through the fixed non-interactive argv;
    # must return a non-empty result (not the pre-fix silent-empty).
    result = CodexAdapter().run("Reply with exactly one word: PONG", cwd=tempfile.mkdtemp(), timeout=200)
    assert result.response_text.strip(), "codex returned an empty response"
    assert result.usage.input_tokens > 0, "codex reported no token usage"
