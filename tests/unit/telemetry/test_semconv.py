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

"""semconv facade tests (Story 5.1 / NFR-COMPAT-06)."""

from __future__ import annotations

from AgentEval.telemetry import semconv


def test_all_gen_ai_constants_are_non_empty_strings() -> None:
    for name in [n for n in semconv.__all__ if n.startswith("GEN_AI_")]:
        value = getattr(semconv, name)
        assert isinstance(value, str), f"{name} must be a string"
        assert value, f"{name} must be non-empty"


def test_all_agenteval_constants_are_non_empty_strings() -> None:
    for name in [n for n in semconv.__all__ if n.startswith("AGENTEVAL_")]:
        value = getattr(semconv, name)
        assert isinstance(value, str), f"{name} must be a string"
        assert value, f"{name} must be non-empty"


def test_gen_ai_key_values_match_architecture_l1001_ratified_names() -> None:
    """Architecture L1001-1010 ratified the exact attribute key strings."""
    expected = {
        "GEN_AI_SYSTEM": "gen_ai.system",
        "GEN_AI_REQUEST_MODEL": "gen_ai.request.model",
        "GEN_AI_USAGE_INPUT_TOKENS": "gen_ai.usage.input_tokens",
        "GEN_AI_USAGE_OUTPUT_TOKENS": "gen_ai.usage.output_tokens",
        "GEN_AI_USAGE_CACHED_INPUT_TOKENS": "gen_ai.usage.cached_input_tokens",
        "GEN_AI_RESPONSE_FINISH_REASONS": "gen_ai.response.finish_reasons",
        "GEN_AI_TOOL_NAME": "gen_ai.tool.name",
        "GEN_AI_TOOL_CALL_ID": "gen_ai.tool.call.id",
    }
    for name, value in expected.items():
        assert getattr(semconv, name) == value, f"{name} drifted from architecture L1001-1010 ratified value {value!r}"


def test_agenteval_key_values_match_architecture_l1001_ratified_names() -> None:
    expected = {
        "AGENTEVAL_TEST_ID": "agenteval.test_id",
        "AGENTEVAL_TOOL_SUCCESS": "agenteval.tool.success",
        "AGENTEVAL_TOOL_DURATION_MS": "agenteval.tool.duration_ms",
        "AGENTEVAL_TOOL_SOURCE": "agenteval.tool.source",
        "AGENTEVAL_TOOL_ARGS": "agenteval.tool.args",
        "AGENTEVAL_TOOL_RESULT": "agenteval.tool.result",
        "AGENTEVAL_TOOL_ERROR": "agenteval.tool.error",
        "AGENTEVAL_TIER": "agenteval.tier",
    }
    for name, value in expected.items():
        assert getattr(semconv, name) == value, f"{name} drifted from architecture L1001-1010 ratified value {value!r}"


def test_span_names_match_architecture_l980_hierarchy() -> None:
    assert semconv.SPAN_INVOKE_AGENT == "invoke_agent"
    assert semconv.SPAN_CHAT == "chat"
    assert semconv.SPAN_EXECUTE_TOOL == "execute_tool"


def test_all_exports_are_documented_in_dunder_all() -> None:
    """Every constant defined in semconv.py must be re-exported via __all__."""
    expected = {
        # gen_ai.*
        "GEN_AI_SYSTEM",
        "GEN_AI_REQUEST_MODEL",
        "GEN_AI_USAGE_INPUT_TOKENS",
        "GEN_AI_USAGE_OUTPUT_TOKENS",
        "GEN_AI_USAGE_CACHED_INPUT_TOKENS",
        "GEN_AI_RESPONSE_FINISH_REASONS",
        "GEN_AI_TOOL_NAME",
        "GEN_AI_TOOL_CALL_ID",
        # agenteval.*
        "AGENTEVAL_TEST_ID",
        "AGENTEVAL_TOOL_SUCCESS",
        "AGENTEVAL_TOOL_DURATION_MS",
        "AGENTEVAL_TOOL_SOURCE",
        "AGENTEVAL_TOOL_ARGS",
        "AGENTEVAL_TOOL_RESULT",
        "AGENTEVAL_TOOL_ERROR",
        "AGENTEVAL_TIER",
        # Span names
        "SPAN_INVOKE_AGENT",
        "SPAN_CHAT",
        "SPAN_EXECUTE_TOOL",
    }
    assert set(semconv.__all__) == expected


def test_constants_follow_screaming_snake_case_convention() -> None:
    """All semconv constants use SCREAMING_SNAKE_CASE."""
    for name in semconv.__all__:
        assert name.isupper() or "_" in name, f"{name} should be SCREAMING_SNAKE_CASE"
        assert not name.startswith("_"), f"{name} should not start with underscore"


def test_constants_are_immutable_at_module_level() -> None:
    """Module-level constants — no functions/classes leak into __all__."""
    for name in semconv.__all__:
        value = getattr(semconv, name)
        assert isinstance(value, str), f"{name} is {type(value).__name__}; semconv.__all__ must export only strings"
