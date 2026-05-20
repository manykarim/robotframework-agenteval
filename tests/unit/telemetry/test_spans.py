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

"""OTel span emission helper tests (Story 5.1)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from AgentEval.telemetry import spans
from AgentEval.telemetry.semconv import (
    AGENTEVAL_TIER,
    AGENTEVAL_TOOL_ARGS,
    AGENTEVAL_TOOL_DURATION_MS,
    AGENTEVAL_TOOL_ERROR,
    AGENTEVAL_TOOL_RESULT,
    AGENTEVAL_TOOL_SOURCE,
    AGENTEVAL_TOOL_SUCCESS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_NAME,
    SPAN_CHAT,
    SPAN_EXECUTE_TOOL,
    SPAN_INVOKE_AGENT,
)


@pytest.fixture
def isolated_exporter() -> Iterator[InMemorySpanExporter]:
    """Per-test isolated TracerProvider + InMemorySpanExporter.

    OTel SDK forbids replacing the global TracerProvider after first set
    (`_TRACER_PROVIDER_SET_ONCE` flag). We bypass that protection by
    resetting both the provider attribute AND the set-once flag for the
    duration of the test, then restoring after.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    prior_provider = getattr(trace, "_TRACER_PROVIDER", None)
    prior_set_once = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
    # Force reset so set_tracer_provider succeeds.
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    trace._TRACER_PROVIDER_SET_ONCE = type(prior_set_once)()  # noqa: SLF001
    trace.set_tracer_provider(provider)
    yield exporter
    # Restore prior provider + set-once state.
    trace._TRACER_PROVIDER = prior_provider  # type: ignore[attr-defined]  # noqa: SLF001
    trace._TRACER_PROVIDER_SET_ONCE = prior_set_once  # noqa: SLF001


def test_invoke_agent_span_sets_agent_name_as_gen_ai_system(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.invoke_agent_span("GenericAdapter"):
        pass
    finished = isolated_exporter.get_finished_spans()
    assert len(finished) == 1
    s = finished[0]
    assert s.name == SPAN_INVOKE_AGENT
    assert s.attributes is not None
    assert s.attributes[GEN_AI_SYSTEM] == "GenericAdapter"


def test_invoke_agent_span_with_model_sets_gen_ai_request_model(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.invoke_agent_span("GenericAdapter", model="claude-sonnet-4-6"):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-6"


def test_invoke_agent_span_with_tier_sets_agenteval_tier(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.invoke_agent_span("GenericAdapter", tier=3):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[AGENTEVAL_TIER] == 3


def test_invoke_agent_span_omits_model_when_none(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.invoke_agent_span("X", model=None):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert GEN_AI_REQUEST_MODEL not in s.attributes


def test_chat_span_is_child_of_invoke_agent(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    """The invoke_agent → chat parent-child hierarchy per architecture L980-982."""
    with spans.invoke_agent_span("A"), spans.chat_span(model="m"):
        pass
    finished = isolated_exporter.get_finished_spans()
    by_name = {s.name: s for s in finished}
    assert SPAN_CHAT in by_name
    assert SPAN_INVOKE_AGENT in by_name
    chat = by_name[SPAN_CHAT]
    parent = chat.parent
    assert parent is not None
    invoke = by_name[SPAN_INVOKE_AGENT]
    assert parent.span_id == invoke.context.span_id


def test_chat_span_sets_required_model(isolated_exporter: InMemorySpanExporter) -> None:
    with spans.chat_span(model="gpt-4o"):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[GEN_AI_REQUEST_MODEL] == "gpt-4o"


def test_chat_span_with_provider_sets_gen_ai_system(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.chat_span(model="m", provider="anthropic"):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[GEN_AI_SYSTEM] == "anthropic"


def test_execute_tool_span_is_child_of_chat(isolated_exporter: InMemorySpanExporter) -> None:
    """Full 3-level hierarchy: invoke_agent → chat → execute_tool."""
    with spans.invoke_agent_span("A"), spans.chat_span(model="m"):  # noqa: SIM117 — nested for OTel parent-child clarity
        with spans.execute_tool_span("search", source="adapter"):  # noqa: SIM117
            pass
    finished = isolated_exporter.get_finished_spans()
    by_name = {s.name: s for s in finished}
    et = by_name[SPAN_EXECUTE_TOOL]
    assert et.attributes is not None
    assert et.attributes[GEN_AI_TOOL_NAME] == "search"
    assert et.attributes[AGENTEVAL_TOOL_SOURCE] == "adapter"
    chat = by_name[SPAN_CHAT]
    assert et.parent is not None
    assert et.parent.span_id == chat.context.span_id


def test_execute_tool_span_with_tool_call_id_sets_gen_ai_tool_call_id(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    with spans.execute_tool_span("search", source="adapter", tool_call_id="tc-123"):
        pass
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[GEN_AI_TOOL_CALL_ID] == "tc-123"


def test_emit_tool_call_span_synthesizes_complete_execute_tool_span(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    spans.emit_tool_call_span(
        name="echo",
        args={"text": "hello"},
        result="hello",
        error=None,
        latency_ms=12.5,
        source="adapter",
        tool_call_id="tc-9",
    )
    s = isolated_exporter.get_finished_spans()[0]
    assert s.name == SPAN_EXECUTE_TOOL
    assert s.attributes is not None
    assert s.attributes[GEN_AI_TOOL_NAME] == "echo"
    assert s.attributes[AGENTEVAL_TOOL_SOURCE] == "adapter"
    assert s.attributes[AGENTEVAL_TOOL_SUCCESS] is True
    assert s.attributes[AGENTEVAL_TOOL_DURATION_MS] == 12.5
    assert s.attributes[GEN_AI_TOOL_CALL_ID] == "tc-9"
    # Story 1b.2 H_R5: args MUST be JSON-encoded string.
    assert isinstance(s.attributes[AGENTEVAL_TOOL_ARGS], str)
    assert json.loads(s.attributes[AGENTEVAL_TOOL_ARGS]) == {"text": "hello"}
    assert s.attributes[AGENTEVAL_TOOL_RESULT] == "hello"
    assert AGENTEVAL_TOOL_ERROR not in s.attributes


def test_emit_tool_call_span_error_sets_agenteval_tool_error(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    spans.emit_tool_call_span(
        name="boom",
        args=None,
        result=None,
        error="ToolFailed: invalid input",
        latency_ms=3.0,
        source="hosted_mcp",
    )
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[AGENTEVAL_TOOL_SUCCESS] is False
    assert s.attributes[AGENTEVAL_TOOL_ERROR] == "ToolFailed: invalid input"
    assert s.attributes[AGENTEVAL_TOOL_SOURCE] == "hosted_mcp"
    # Result is None → attribute omitted.
    assert AGENTEVAL_TOOL_RESULT not in s.attributes


def test_emit_tool_call_span_json_encodes_complex_result(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    complex_result = {"data": [1, 2, 3], "ok": True}
    spans.emit_tool_call_span(
        name="t",
        args={"a": 1},
        result=complex_result,
        error=None,
        latency_ms=1.0,
        source="adapter",
    )
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert isinstance(s.attributes[AGENTEVAL_TOOL_RESULT], str)
    assert json.loads(s.attributes[AGENTEVAL_TOOL_RESULT]) == complex_result


def test_emit_tool_call_span_falls_back_to_str_on_non_json_result(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    class Unencodable:
        def __str__(self) -> str:
            return "<unencodable-object>"

    spans.emit_tool_call_span(
        name="t",
        args={},
        result=Unencodable(),
        error=None,
        latency_ms=1.0,
        source="adapter",
    )
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert s.attributes[AGENTEVAL_TOOL_RESULT] == "<unencodable-object>"


def test_emit_tool_call_span_empty_args_serializes_to_empty_dict(
    isolated_exporter: InMemorySpanExporter,
) -> None:
    spans.emit_tool_call_span(
        name="t",
        args=None,
        result=None,
        error=None,
        latency_ms=0.0,
        source="adapter",
    )
    s = isolated_exporter.get_finished_spans()[0]
    assert s.attributes is not None
    assert json.loads(s.attributes[AGENTEVAL_TOOL_ARGS]) == {}
