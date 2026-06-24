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

"""Unit tests for `OpenCodeCLIAdapter` (OpenSpec `add-opencode-support`).

Mirrors `tests/unit/coding_agent/test_codex_cli.py` (streamed-JSONL Case
A precedent) + applies cross-story UPSTREAM regression guards per
`feedback_cross_story_upstream_lesson_propagation`. Fixtures under
`tests/fixtures/opencode_cli/` are real `opencode run --format json`
probe captures (2026-06-25) plus synthetic edge-case streams.
"""

from __future__ import annotations

import importlib.metadata
import io
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.opencode_cli import (
    OpenCodeCLIAdapter,
    OpenCodeEvent,
)
from AgentEval.errors import UnsupportedBinaryVersionError
from AgentEval.types import AgentRunResult, ToolCallTrace

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "opencode_cli"


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    """Load a JSONL fixture file as a list of parsed dicts."""
    return [json.loads(line) for line in (FIXTURE_DIR / name).read_text().splitlines() if line.strip()]


def _events_from_fixture(name: str) -> list[OpenCodeEvent]:
    raw_events = _read_jsonl(name)
    return [OpenCodeEvent(event_type=str(e.get("type") or "unknown"), raw=e) for e in raw_events]


# --------------------------------------------------------------------------- #
# Version gate (4 tests)                                                       #
# --------------------------------------------------------------------------- #


def test_version_gate_passes_with_default_mock_version() -> None:
    """Conftest's `mock_opencode_version` stubs ``opencode --version`` → ``1.15.12``,
    which is in range. Construction succeeds."""
    adapter = OpenCodeCLIAdapter()
    assert adapter.name == "opencode-cli"


def test_version_gate_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """FileNotFoundError on ``opencode --version`` → `UnsupportedBinaryVersionError`."""

    def _missing(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["opencode", "--version"]:
            raise FileNotFoundError("opencode: command not found")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _missing)
    with pytest.raises(UnsupportedBinaryVersionError):
        OpenCodeCLIAdapter()


def test_version_gate_raises_below_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """``1.14.9`` is below the floor 1.15.0 → typed error."""

    def _below(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["opencode", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="1.14.9\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _below)
    with pytest.raises(UnsupportedBinaryVersionError) as exc_info:
        OpenCodeCLIAdapter()
    assert "1.14.9" in str(exc_info.value)


def test_version_gate_raises_above_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """``2.0.0`` is at the exclusive ceiling 2.0.0 → typed error."""

    def _above(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and cmd[:2] == ["opencode", "--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="2.0.0\n", stderr="")
        return subprocess.run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _above)
    with pytest.raises(UnsupportedBinaryVersionError):
        OpenCodeCLIAdapter()


def test_in_range_binary_constructs_without_spurious_drift_warning() -> None:
    """The default in-range mock version (`1.15.12`) constructs without emitting
    `AdapterVersionDriftWarning`.

    Honest-framing note (apply-time amendment): the shared `version_drift`
    helper fires only when the detected binary is OLDER than `_TESTED_UP_TO`
    (`tested.minor - detected.minor >= 2`) or on a previous major — NOT newer.
    Because `MIN_VERSION=1.15.0` and `_TESTED_UP_TO=1.15.12` share minor 15,
    the within-range drift window is empty (anything ≥2 minors behind tested is
    below the floor and rejected by `_assert_binary_version` first). So the only
    behavior testable at these pins is the no-spurious-warning common case.
    """
    import warnings

    from AgentEval.mcp.observer import AdapterVersionDriftWarning

    with warnings.catch_warnings():
        warnings.simplefilter("error", AdapterVersionDriftWarning)
        adapter = OpenCodeCLIAdapter()  # default mock → 1.15.12, in range
    assert adapter.name == "opencode-cli"


# --------------------------------------------------------------------------- #
# Constructor + ABC inheritance                                                #
# --------------------------------------------------------------------------- #


def test_inherits_from_subprocess_adapter() -> None:
    """Must subclass `SubprocessAdapter` per ADR-003."""
    assert issubclass(OpenCodeCLIAdapter, SubprocessAdapter)


def test_constructor_accepts_model_kwarg() -> None:
    """`__init__(*, model=...)` stores the model + forwards **kwargs."""
    adapter = OpenCodeCLIAdapter(model="opencode/deepseek-v4-flash-free", extra_key="extra_value")
    assert adapter._model == "opencode/deepseek-v4-flash-free"
    assert adapter._adapter_config["extra_key"] == "extra_value"


def test_constructor_model_defaults_to_none() -> None:
    adapter = OpenCodeCLIAdapter()
    assert adapter._model is None


def test_name_property_returns_opencode_cli() -> None:
    """Adapter name MUST be ``opencode-cli`` (matches entry-point slug)."""
    assert OpenCodeCLIAdapter().name == "opencode-cli"


def test_version_property_returns_distribution_version() -> None:
    adapter = OpenCodeCLIAdapter()
    assert isinstance(adapter.version, str)
    assert adapter.version  # non-empty


# --------------------------------------------------------------------------- #
# `_parse_event`                                                               #
# --------------------------------------------------------------------------- #


def test_parse_event_step_start() -> None:
    event = OpenCodeCLIAdapter()._parse_event('{"type":"step_start","part":{"type":"step-start"}}')
    assert event is not None
    assert event.event_type == "step_start"
    assert not event.is_step_finish


def test_parse_event_text() -> None:
    line = '{"type":"text","part":{"type":"text","text":"hello world"}}'
    event = OpenCodeCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.event_type == "text"
    assert event.text_content == "hello world"


def test_parse_event_tool_use() -> None:
    line = (
        '{"type":"tool_use","part":{"type":"tool","tool":"bash","callID":"call_1",'
        '"state":{"status":"completed","input":{"command":"ls"},"output":"a\\nb\\n",'
        '"metadata":{"exit":0}}}}'
    )
    event = OpenCodeCLIAdapter()._parse_event(line)
    assert event is not None
    payload = event.tool_payload
    assert payload is not None
    assert payload["tool"] == "bash"
    assert payload["callID"] == "call_1"
    assert payload["state"]["input"] == {"command": "ls"}


def test_parse_event_step_finish_terminal() -> None:
    line = (
        '{"type":"step_finish","part":{"type":"step-finish","reason":"stop",'
        '"tokens":{"total":100,"input":50,"output":20,"reasoning":5,"cache":{"write":0,"read":10}},'
        '"cost":0.0012}}'
    )
    event = OpenCodeCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.is_step_finish
    assert event.is_terminal
    assert event.finish_reason == "stop"
    assert event.step_tokens["input"] == 50
    assert event.step_cost == pytest.approx(0.0012)


def test_parse_event_step_finish_tool_calls_is_not_terminal() -> None:
    """A ``step_finish`` with ``reason=tool-calls`` is a step boundary but NOT terminal."""
    line = '{"type":"step_finish","part":{"type":"step-finish","reason":"tool-calls","tokens":{}}}'
    event = OpenCodeCLIAdapter()._parse_event(line)
    assert event is not None
    assert event.is_step_finish
    assert not event.is_terminal
    assert event.finish_reason == "tool-calls"


def test_parse_event_returns_none_on_non_json_line() -> None:
    """Log chatter multiplexed in via stderr must be skipped without raising."""
    assert OpenCodeCLIAdapter()._parse_event("INFO starting up...") is None
    assert OpenCodeCLIAdapter()._parse_event("") is None
    assert OpenCodeCLIAdapter()._parse_event("   \n") is None


def test_parse_event_returns_none_on_non_string_type() -> None:
    assert OpenCodeCLIAdapter()._parse_event('{"type":42}') is None


def test_parse_event_returns_none_on_non_dict_json() -> None:
    assert OpenCodeCLIAdapter()._parse_event("[1, 2, 3]") is None
    assert OpenCodeCLIAdapter()._parse_event('"just-a-string"') is None
    assert OpenCodeCLIAdapter()._parse_event("42") is None


# --------------------------------------------------------------------------- #
# `_finalize` against fixtures                                                 #
# --------------------------------------------------------------------------- #


def test_finalize_simple_prompt_happy_path() -> None:
    """`simple_prompt.jsonl` (real probe): clean exit + terminal step_finish + text."""
    events = _events_from_fixture("simple_prompt.jsonl")
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=0)
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "hello world"
    assert result.tool_calls == []
    # Single step_finish: input=15389, output=3, reasoning=16, cache.read=1920
    assert result.usage.input_tokens == 15389
    assert result.usage.output_tokens == 3
    assert result.usage.reasoning_output_tokens == 16
    assert result.usage.cached_input_tokens == 1920
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.cost_usd == 0.0


def test_finalize_tool_use_extracts_tool_call_and_sums_tokens() -> None:
    """`tool_use.jsonl` (real probe): a bash tool_use bracketed by 2 step_finish events.

    Verifies per-step token summing (NOT cumulative) per the empirical probe:
    step1 input=37/output=63/reasoning=21/cache.read=17280;
    step2 input=234/output=3/reasoning=21/cache.read=17280.
    """
    events = _events_from_fixture("tool_use.jsonl")
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=0)
    # Final answer text
    assert result.response_text == "Done."
    # Exactly one tool call projected
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert isinstance(tc, ToolCallTrace)
    assert tc.name == "bash"
    assert tc.args == {"command": "ls", "description": "List files in current directory"}
    assert tc.error is None
    assert tc.source == "adapter"
    assert tc.sequence_index == 0
    assert tc.gen_ai_tool_call_id == "call_00_wrulvU4LKQ203IhoszhT4285"
    # Per-step summed usage
    assert result.usage.input_tokens == 37 + 234
    assert result.usage.output_tokens == 63 + 3
    assert result.usage.reasoning_output_tokens == 21 + 21
    assert result.usage.cached_input_tokens == 17280 + 17280
    assert result.metadata.completeness == "complete"


def test_finalize_tool_error_marks_error() -> None:
    """`tool_error.jsonl`: a tool with state.status=error → `ToolCallTrace.error` set."""
    events = _events_from_fixture("tool_error.jsonl")
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=0)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error == "command exited non-zero"


def test_finalize_completed_tool_with_nonzero_command_exit_marks_error() -> None:
    """Cross-LLM review 2026-06-25 Claude MED-2: isolate the `metadata.exit != 0`
    elif arm — the realistic case where the tool itself "completed" but the
    shell command it ran exited non-zero (e.g. `bash` returning 1). The
    `tool_error.jsonl` fixture has status="error" AND exit=1, so it fires the
    FIRST branch and shadows this elif; this test exercises the elif directly.
    """
    tool = OpenCodeEvent(
        event_type="tool_use",
        raw={
            "type": "tool_use",
            "part": {
                "type": "tool",
                "tool": "bash",
                "callID": "call_exit1",
                "state": {
                    "status": "completed",
                    "input": {"command": "false"},
                    "output": "",
                    "metadata": {"exit": 1},
                },
            },
        },
    )
    terminal = OpenCodeEvent(
        event_type="step_finish",
        raw={"type": "step_finish", "part": {"type": "step-finish", "reason": "stop", "tokens": {}}},
    )
    result = OpenCodeCLIAdapter()._finalize([tool, terminal], exit_code=0)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error == "exit_code=1"


def test_finalize_truncated_no_terminal_yields_truncated() -> None:
    """`truncated.jsonl`: text but no terminal `step_finish reason=stop` → truncated.

    Story 4.2 MED-4 lesson UPSTREAM (test-name vs assertion-body match):
    the load-bearing condition is "no terminal", NOT the exit code.
    """
    events = _events_from_fixture("truncated.jsonl")
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=0)
    assert result.response_text == "Starting work..."
    assert result.metadata.completeness == "truncated"
    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0


def test_finalize_nonzero_exit_with_no_message_emits_diagnostic() -> None:
    """Story 4.2 MED-3 / Story 11.1 D-3 UPSTREAM: exit_code != 0 AND no terminal
    AND no text → ``[SUBPROCESS_NONZERO_EXIT exit_code=<N>]`` diagnostic."""
    events = _events_from_fixture("nonzero_exit.jsonl")
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=2)
    assert result.response_text == "[SUBPROCESS_NONZERO_EXIT exit_code=2]"
    assert result.metadata.completeness == "truncated"


def test_finalize_nonzero_exit_with_text_does_not_emit_diagnostic() -> None:
    """Negative-path: when text WAS produced, the diagnostic-suppression branch
    fires even on non-zero exit — response_text wins."""
    events = _events_from_fixture("simple_prompt.jsonl")  # has "hello world"
    result = OpenCodeCLIAdapter()._finalize(events, exit_code=1)
    assert result.response_text == "hello world"
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text


def test_finalize_nonzero_exit_with_text_but_no_terminal_isolates_not_response_text_clause() -> None:
    """Cross-LLM review 2026-06-25 Claude MED-1: isolate the `not response_text`
    sub-clause of the 3-condition diagnostic guard.

    `test_finalize_nonzero_exit_with_text_does_not_emit_diagnostic` uses
    `simple_prompt.jsonl` which ALSO has a terminal step_finish, so `terminal
    is None` independently suppresses the diagnostic — that test can't tell
    which clause fired. Here: text present, NO terminal (a `tool-calls`
    step_finish, not `stop`), nonzero exit. The ONLY thing suppressing the
    diagnostic is `not response_text` → if a refactor drops that clause, the
    marker would be appended and this assertion fails. (feedback_test_name_assertion_match.)
    """
    text = OpenCodeEvent(
        event_type="text",
        raw={"type": "text", "part": {"type": "text", "text": "partial output before crash"}},
    )
    non_terminal_finish = OpenCodeEvent(
        event_type="step_finish",
        raw={"type": "step_finish", "part": {"type": "step-finish", "reason": "tool-calls", "tokens": {}}},
    )
    result = OpenCodeCLIAdapter()._finalize([text, non_terminal_finish], exit_code=3)
    assert result.response_text == "partial output before crash"
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text
    # No terminal `reason=stop` → truncated despite the text.
    assert result.metadata.completeness == "truncated"


def test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic() -> None:
    """Negative-path: when a terminal step_finish was observed, the
    `terminal is None` condition fails → no diagnostic marker appended."""
    terminal = OpenCodeEvent(
        event_type="step_finish",
        raw={"type": "step_finish", "part": {"type": "step-finish", "reason": "stop", "tokens": {}}},
    )
    result = OpenCodeCLIAdapter()._finalize([terminal], exit_code=1)
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text
    assert result.response_text == ""


def test_finalize_populates_cost_from_step_finish() -> None:
    """Unlike Codex, opencode surfaces per-step `cost`; `cost_usd` sums them."""
    step1 = OpenCodeEvent(
        event_type="step_finish",
        raw={"type": "step_finish", "part": {"type": "step-finish", "reason": "tool-calls", "tokens": {}, "cost": 0.002}},
    )
    step2 = OpenCodeEvent(
        event_type="step_finish",
        raw={"type": "step_finish", "part": {"type": "step-finish", "reason": "stop", "tokens": {}, "cost": 0.003}},
    )
    result = OpenCodeCLIAdapter()._finalize([step1, step2], exit_code=0)
    assert result.cost_usd == pytest.approx(0.005)


# --------------------------------------------------------------------------- #
# `_spawn` argv construction                                                   #
# --------------------------------------------------------------------------- #


def _capture_spawn(monkeypatch: pytest.MonkeyPatch, **adapter_kwargs: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    OpenCodeCLIAdapter(**adapter_kwargs)._spawn("Find the largest file.")
    return captured


def test_spawn_uses_run_format_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """``opencode run --format json`` non-interactive invocation (probe-verified)."""
    captured = _capture_spawn(monkeypatch)
    cmd = captured["cmd"]
    assert cmd[0] == "opencode"
    assert cmd[1] == "run"
    assert "--format" in cmd
    assert cmd[cmd.index("--format") + 1] == "json"
    assert "--dangerously-skip-permissions" in cmd


def test_spawn_passes_prompt_as_trailing_positional(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 4.2 HIGH-A / Story 11.1 D-1 UPSTREAM: prompt is positional argv, not stdin."""
    captured = _capture_spawn(monkeypatch)
    assert captured["cmd"][-1] == "Find the largest file."


def test_spawn_forwards_model_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_spawn(monkeypatch, model="opencode/deepseek-v4-flash-free")
    cmd = captured["cmd"]
    assert "--model" in cmd
    assert cmd[cmd.index("--model") + 1] == "opencode/deepseek-v4-flash-free"
    # prompt still trailing
    assert cmd[-1] == "Find the largest file."


def test_spawn_omits_model_flag_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_spawn(monkeypatch)
    assert "--model" not in captured["cmd"]


def test_spawn_inserts_end_of_options_sentinel_before_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cross-LLM review 2026-06-25 Claude MED-4: a `--` sentinel MUST immediately
    precede the positional prompt so a dataset-supplied prompt beginning with
    `-` is treated as the message, not parsed as a flag (argv-injection guard;
    probe-verified that `opencode run ... -- "<prompt>"` honors the sentinel)."""
    captured: dict[str, Any] = {}

    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    OpenCodeCLIAdapter()._spawn("--help just say hi")
    cmd = captured["cmd"]
    # The prompt is the final element and `--` is the element immediately before it.
    assert cmd[-1] == "--help just say hi"
    assert cmd[-2] == "--"


def test_spawn_uses_stderr_stdout_multiplex_and_pgroup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 4.2 HIGH-B / Story 11.1 D-2 UPSTREAM: stderr=STDOUT multiplex +
    process-group hygiene flags + stdin=DEVNULL (Claude LOW-5)."""
    captured = _capture_spawn(monkeypatch)
    kwargs = captured["kwargs"]
    assert kwargs["stderr"] == subprocess.STDOUT
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["text"] is True
    assert kwargs["start_new_session"] is True


# --------------------------------------------------------------------------- #
# End-to-end `run()` against a faked subprocess                                #
# --------------------------------------------------------------------------- #


def _make_fake_popen_class(fixture_filename: str, returncode: int = 0) -> type:
    """Build a `_FakePopen` class replaying a fixture file (closeable stdout via
    `io.StringIO` so the base `run()`'s `proc.stdout.close()` cleanup works)."""
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
    """Drives the full template-method `run()` chain end-to-end with a faked
    Popen replaying `simple_prompt.jsonl` + asserts the listener helper fired."""
    monkeypatch.setattr(subprocess, "Popen", _make_fake_popen_class("simple_prompt.jsonl"))
    fake_listener = MagicMock()
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", fake_listener)

    adapter = OpenCodeCLIAdapter()
    result = adapter.run("Say hello world.")
    assert result.response_text == "hello world"
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"  # empty mcp_servers
    assert result.usage.input_tokens == 15389
    assert fake_listener.call_count == 1
    call_kwargs = fake_listener.call_args.kwargs
    assert call_kwargs["adapter_name"] == "opencode-cli"
    assert call_kwargs["completeness"] == "complete"


def test_run_with_unverified_mcp_marks_external_mixed(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-016 §Decision L33: non-empty ``mcp_servers`` → ``external_mixed`` until
    observer wiring lands (DF-OPENCODE-S1 / C99)."""
    monkeypatch.setattr(subprocess, "Popen", _make_fake_popen_class("simple_prompt.jsonl"))
    monkeypatch.setattr("AgentEval.telemetry.listener.record_active_run_metadata", MagicMock())

    adapter = OpenCodeCLIAdapter()
    fake_handle = MagicMock()
    fake_handle.transport = "stdio"
    result = adapter.run("hi", mcp_servers={"echo": fake_handle})
    assert result.metadata.mcp_coverage == "external_mixed"


def test_detect_mcp_coverage_empty_returns_hosted_in_process() -> None:
    adapter = OpenCodeCLIAdapter()
    assert adapter._detect_mcp_coverage(None) == "hosted_in_process"
    assert adapter._detect_mcp_coverage({}) == "hosted_in_process"


def test_detect_mcp_coverage_nonempty_returns_external_mixed() -> None:
    adapter = OpenCodeCLIAdapter()
    assert adapter._detect_mcp_coverage({"any": object()}) == "external_mixed"


# --------------------------------------------------------------------------- #
# `OpenCodeEvent` accessors                                                    #
# --------------------------------------------------------------------------- #


def test_opencode_event_post_init_defensive_copy() -> None:
    """`__post_init__` shallow-copies raw so caller mutations don't leak."""
    raw = {"type": "step_start", "_marker": "original"}
    event = OpenCodeEvent(event_type="step_start", raw=raw)
    raw["_marker"] = "mutated"
    assert event.raw["_marker"] == "original"


def test_opencode_event_text_content_empty_for_non_text_event() -> None:
    event = OpenCodeEvent(event_type="step_start", raw={"type": "step_start", "part": {}})
    assert event.text_content == ""


def test_opencode_event_tool_payload_none_for_non_tool_event() -> None:
    event = OpenCodeEvent(event_type="text", raw={"type": "text", "part": {"text": "x"}})
    assert event.tool_payload is None


def test_opencode_event_handles_missing_part() -> None:
    """A malformed event with no `part` key degrades to empty accessors, not a crash."""
    event = OpenCodeEvent(event_type="text", raw={"type": "text"})
    assert event.text_content == ""
    assert event.step_tokens == {}
    assert event.step_cost == 0.0


# --------------------------------------------------------------------------- #
# Entry-point registration (conformance smoke)                                 #
# --------------------------------------------------------------------------- #


def test_entry_point_registration() -> None:
    """`importlib.metadata.entry_points` returns `OpenCodeCLIAdapter` under
    `agenteval.coding_agents` slug `opencode-cli`."""
    eps = importlib.metadata.entry_points(group="agenteval.coding_agents")
    matching = [ep for ep in eps if ep.name == "opencode-cli"]
    assert len(matching) == 1, f"Expected exactly one `opencode-cli` entry-point; got {[ep.name for ep in eps]}"
    loaded = matching[0].load()
    assert loaded is OpenCodeCLIAdapter
