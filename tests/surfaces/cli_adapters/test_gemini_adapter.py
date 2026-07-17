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

"""Unit tests for ``GeminiAdapter.build_argv`` + ``parse_output``.

Uses a RECORDED/representative ``--output-format json`` payload - the real
``gemini`` binary is never invoked. Cost is derived via a stubbed ``litellm``.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import pytest

from AgentEval._core.cli_adapters.gemini import GeminiAdapter

# Representative gemini `--output-format json` object: one model, two tools,
# one of which failed once.
_RECORDED_JSON = json.dumps(
    {
        "response": "I read the file and ran the tests.",
        "stats": {
            "models": {
                "gemini-2.5-pro": {
                    "api": {"totalRequests": 2, "totalErrors": 0, "totalLatencyMs": 8000},
                    "tokens": {
                        "prompt": 1200,
                        "candidates": 380,
                        "thoughts": 20,
                        "cached": 150,
                        "total": 1600,
                    },
                }
            },
            "tools": {
                "totalCalls": 3,
                "totalSuccess": 2,
                "totalFail": 1,
                "totalDurationMs": 3400,
                "byName": {
                    "read_file": {"count": 2, "success": 2, "fail": 0},
                    "run_shell_command": {"count": 1, "success": 0, "fail": 1},
                },
            },
        },
    }
)


@pytest.fixture
def _stub_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("litellm")

    def _cost(**kwargs: Any) -> float:
        return 0.0123

    fake.completion_cost = _cost  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)


def test_build_argv_uses_prompt_flag_and_json_format() -> None:
    argv = GeminiAdapter().build_argv("write a haiku")
    assert argv == ["gemini", "-p", "write a haiku", "--output-format", "json"]


def test_parse_output_response_text() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    assert result.response_text == "I read the file and ran the tests."


def test_parse_output_usage_maps_gemini_token_fields() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    # input=prompt, output=candidates+thoughts, cached=cached
    assert result.usage.input_tokens == 1200
    assert result.usage.output_tokens == 400
    assert result.usage.cached_input_tokens == 150


def test_parse_output_expands_tool_aggregate_with_failed_marked() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    # 2 read_file + 1 run_shell_command = 3 total calls
    assert len(result.tool_calls) == 3
    names = [t.name for t in result.tool_calls]
    assert names.count("read_file") == 2
    assert names.count("run_shell_command") == 1
    # passed/failed derivable via error is None; exactly one failure
    failed = [t for t in result.tool_calls if t.error is not None]
    assert len(failed) == 1
    assert failed[0].name == "run_shell_command"
    # sequence indices are contiguous
    assert [t.sequence_index for t in result.tool_calls] == [0, 1, 2]


def test_parse_output_latency_from_tool_duration() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    assert result.latency_seconds == pytest.approx(3.4)


def test_parse_output_cost_is_derived(_stub_litellm: None) -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    assert result.cost_usd == pytest.approx(0.0123)
    assert result.metadata.metric_source == "derived"


def test_parse_output_cost_none_without_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the litellm import inside resolve_cost to fail -> cost degrades to none.
    monkeypatch.setitem(sys.modules, "litellm", None)
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"


def test_parse_output_nonzero_exit_marks_partial() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 2, None)
    assert result.metadata.completeness == "partial"


def test_parse_output_empty_stdout_is_safe() -> None:
    result = GeminiAdapter().parse_output("", "", 0, None)
    assert result.response_text == ""
    assert result.tool_calls == []
    assert result.usage.input_tokens == 0
    assert result.metadata.metric_source == "none"


def test_parse_output_tolerates_banner_prefixed_json() -> None:
    noisy = "Loading extensions...\nDeprecation notice\n" + _RECORDED_JSON
    result = GeminiAdapter().parse_output(noisy, "", 0, None)
    assert result.response_text == "I read the file and ran the tests."
    assert result.usage.input_tokens == 1200


def test_parse_output_leaves_agent_version_blank_for_base_to_stamp() -> None:
    result = GeminiAdapter().parse_output(_RECORDED_JSON, "", 0, None)
    assert result.metadata.agent_version == ""


def test_fidelity_and_ceiling_are_honest() -> None:
    adapter = GeminiAdapter()
    assert adapter.fidelity == "FULL"
    assert "derived" in adapter.validation_ceiling
    assert "arguments" in adapter.validation_ceiling or "args" in adapter.validation_ceiling.lower()
