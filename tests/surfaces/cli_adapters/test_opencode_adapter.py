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

"""Fixture-driven unit tests for ``OpencodeAdapter`` (fidelity PARTIAL).

Fixtures under ``fixtures/opencode/`` are RECORDED ``opencode run --format json``
output (probe: opencode 1.15.12). The real binary is never invoked here; the
live smoke at the bottom is gated + skips when the binary/credentials are absent.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval._core import cli_adapter as cli_adapter_mod
from AgentEval._core.adapter import get_adapter
from AgentEval._core.cli_adapters.opencode import OpencodeAdapter
from AgentEval._core.types import AgentRunResult

_FIXTURES = Path(__file__).parent / "fixtures" / "opencode"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _parse(name: str, *, exit_code: int = 0) -> AgentRunResult:
    return OpencodeAdapter().parse_output(_fixture(name), "", exit_code, None)


# --------------------------------------------------------------------------- #
# build_argv                                                                  #
# --------------------------------------------------------------------------- #


def test_build_argv_starts_with_binary_and_streams_json() -> None:
    argv = OpencodeAdapter().build_argv("do a thing")
    assert argv[0] == "opencode"
    assert argv[1] == "run"
    assert "--format" in argv and argv[argv.index("--format") + 1] == "json"
    assert "--dangerously-skip-permissions" in argv


def test_build_argv_guards_leading_dash_prompt_with_sentinel() -> None:
    argv = OpencodeAdapter().build_argv("--help please")
    # The prompt is the trailing positional after a `--` end-of-options sentinel.
    assert argv[-2] == "--"
    assert argv[-1] == "--help please"


def test_build_argv_never_carries_a_secret() -> None:
    # Prompt is the only free text; no env/secret is spliced onto argv.
    argv = OpencodeAdapter().build_argv("hello")
    assert not any("sk-" in tok or "Bearer" in tok for tok in argv)


# --------------------------------------------------------------------------- #
# parse_output - simple text run                                              #
# --------------------------------------------------------------------------- #


def test_simple_prompt_response_text_and_native_usage() -> None:
    result = _parse("simple_prompt.jsonl")
    assert result.response_text == "hello world"
    assert result.tool_calls == []
    # One step_finish: input=15389, output=3, cache.read=1920.
    assert result.usage.input_tokens == 15389
    assert result.usage.output_tokens == 3
    assert result.usage.cached_input_tokens == 1920
    # opencode reports cost natively (0 on a free-tier model, but still native).
    assert result.metadata.metric_source == "native"
    assert result.cost_usd == pytest.approx(0.0)
    assert result.metadata.completeness == "complete"


# --------------------------------------------------------------------------- #
# parse_output - tool-use run                                                 #
# --------------------------------------------------------------------------- #


def test_tool_use_projects_toolcalltrace_and_sums_two_steps() -> None:
    result = _parse("tool_use.jsonl")
    assert result.response_text == "Done."
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.name == "bash"
    assert call.args == {"command": "ls", "description": "List files in current directory"}
    assert call.error is None
    assert call.tool_call_id == "call_00_wrulvU4LKQ203IhoszhT4285"
    assert call.sequence_index == 0
    assert call.source == "adapter"
    # state.time span 1782340784854..1782340784889 -> 35ms.
    assert call.latency_ms == pytest.approx(35.0)
    # Two step_finish events summed: input 37+234, output 63+3, cache 17280+17280.
    assert result.usage.input_tokens == 271
    assert result.usage.output_tokens == 66
    assert result.usage.cached_input_tokens == 34560
    assert result.metadata.metric_source == "native"
    assert result.metadata.completeness == "complete"


def test_tool_use_latency_derived_from_timestamp_span() -> None:
    result = _parse("tool_use.jsonl")
    # First event ts 1782340783318, last 1782340788430 -> 5.112s span.
    assert result.latency_seconds == pytest.approx(5.112, abs=1e-6)


def test_per_tool_token_and_cost_attribution_stays_zero() -> None:
    # PARTIAL ceiling: opencode reports tokens per step, not per tool.
    call = _parse("tool_use.jsonl").tool_calls[0]
    assert call.input_tokens == 0
    assert call.output_tokens == 0
    assert call.cost_usd == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# parse_output - tool error                                                   #
# --------------------------------------------------------------------------- #


def test_tool_error_surfaces_on_toolcalltrace_not_completeness() -> None:
    result = _parse("tool_error.jsonl")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error == "command exited non-zero"
    # A failed tool with the run still reaching reason=stop is a COMPLETE run;
    # the failure lives on the trace, not on completeness.
    assert result.metadata.completeness == "complete"


# --------------------------------------------------------------------------- #
# parse_output - truncated + fail-loud                                        #
# --------------------------------------------------------------------------- #


def test_truncated_run_has_no_step_finish_and_metric_source_none() -> None:
    result = _parse("truncated.jsonl")
    assert result.response_text == "Starting work..."
    assert result.metadata.completeness == "truncated"
    # No step_finish -> no token/cost data at all.
    assert result.metadata.metric_source == "none"
    assert result.usage.input_tokens == 0
    assert result.cost_usd == pytest.approx(0.0)


def test_nonzero_exit_with_no_text_emits_fail_loud_marker() -> None:
    result = OpencodeAdapter().parse_output(_fixture("nonzero_exit.jsonl"), "", 1, None)
    assert result.response_text == "[SUBPROCESS_NONZERO_EXIT exit_code=1]"
    assert result.metadata.completeness == "truncated"


def test_empty_stdout_yields_empty_result_not_crash() -> None:
    result = OpencodeAdapter().parse_output("", "", 0, None)
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.metadata.metric_source == "none"


def test_non_json_log_chatter_is_skipped() -> None:
    blob = "INFO some log line\n" + _fixture("simple_prompt.jsonl") + "\nWARN trailing noise"
    result = OpencodeAdapter().parse_output(blob, "", 0, None)
    assert result.response_text == "hello world"
    assert result.usage.input_tokens == 15389


# --------------------------------------------------------------------------- #
# session-transcript fallback                                                 #
# --------------------------------------------------------------------------- #


def test_session_dir_fallback_when_stdout_is_thin(tmp_path: Path) -> None:
    transcript = tmp_path / "nested" / "rollout.jsonl"
    transcript.parent.mkdir()
    transcript.write_text(_fixture("tool_use.jsonl"), encoding="utf-8")
    result = OpencodeAdapter().parse_output("", "", 0, str(tmp_path))
    # Same normalized shape as the stdout path.
    assert result.response_text == "Done."
    assert len(result.tool_calls) == 1
    assert result.usage.input_tokens == 271


def test_stdout_wins_over_session_dir_when_both_present(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(_fixture("tool_use.jsonl"), encoding="utf-8")
    # stdout has real events -> the on-disk transcript is never read.
    result = OpencodeAdapter().parse_output(_fixture("simple_prompt.jsonl"), "", 0, str(tmp_path))
    assert result.response_text == "hello world"
    assert result.tool_calls == []


# --------------------------------------------------------------------------- #
# base-run integration (subprocess stubbed) + registry                        #
# --------------------------------------------------------------------------- #


def test_run_drives_parse_output_through_base(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = _fixture("simple_prompt.jsonl")

    def fake_run(argv: list[str], **kwargs: Any) -> SimpleNamespace:
        if "--version" in argv[1:]:
            return SimpleNamespace(stdout="1.15.12", stderr="", returncode=0)
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)

    monkeypatch.setattr(cli_adapter_mod.shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(cli_adapter_mod.subprocess, "run", fake_run)

    result = OpencodeAdapter().run("say hello")
    assert result.response_text == "hello world"
    # Base stamps the probed --version onto blank metadata.
    assert result.metadata.agent_version == "1.15.12"


def test_get_adapter_returns_opencode_instance() -> None:
    adapter = get_adapter("opencode")
    assert isinstance(adapter, OpencodeAdapter)
    assert adapter.name == "opencode"
    assert adapter.fidelity == "PARTIAL"
    assert adapter.validation_ceiling


# --------------------------------------------------------------------------- #
# Live E2E smoke - gated; skips when binary or credentials are absent.         #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    shutil.which("opencode") is None or not os.environ.get("AGENTEVAL_LIVE_OPENCODE"),
    reason="opencode binary or AGENTEVAL_LIVE_OPENCODE credential gate not present",
)
def test_live_opencode_smoke() -> None:  # pragma: no cover - live, opt-in only
    result = OpencodeAdapter().run("Reply with exactly the word: pong", timeout=120.0)
    assert isinstance(result, AgentRunResult)
    assert result.metadata.agent_version  # a real --version was probed
