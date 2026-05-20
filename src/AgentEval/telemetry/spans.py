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

"""OTel GenAI span emission helpers (Story 5.1).

Per architecture L980-982 + PRD FR32, the OTel span hierarchy is:

    invoke_agent       (top-level per agent run)
        └── chat        (per LLM round-trip)
            └── execute_tool   (per tool call)

This module exposes context-manager helpers for the 3-level hierarchy plus a
non-CM ``emit_tool_call_span`` for adapter/observer callers that already have
a completed tool-call record. All attribute keys route through
``telemetry/semconv.py`` per NFR-COMPAT-06.

Story 5.2 forward-ref: the hosted-MCP observer calls ``emit_tool_call_span``
with ``source="hosted_mcp"``; adapter-side recordings use ``source="adapter"``
per FR35.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Literal

from opentelemetry import trace
from opentelemetry.trace import Span

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

__all__ = [
    "invoke_agent_span",
    "chat_span",
    "execute_tool_span",
    "emit_tool_call_span",
]


_TRACER_NAME = "AgentEval.telemetry"


def _get_tracer() -> trace.Tracer:
    """Return the agenteval tracer; lazy + module-local for testability."""
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def invoke_agent_span(agent_name: str, model: str | None = None, *, tier: int | None = None) -> Iterator[Span]:
    """Open an ``invoke_agent`` span — top-level per agent run.

    Args:
        agent_name: Logical name of the agent (e.g., ``"GenericAdapter"`` /
            ``"ClaudeCodeCLIAdapter"``). Set as ``gen_ai.system``.
        model: Optional model identifier (e.g., ``"claude-sonnet-4-6"``).
            Set as ``gen_ai.request.model`` when provided.
        tier: Optional keyword tier (1/2/3). Set as ``agenteval.tier`` when
            provided. Listener propagates the ``_agenteval_tier`` decorator
            attribute here.

    Yields:
        The active OTel ``Span``; caller may set additional attributes.
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(SPAN_INVOKE_AGENT) as span:
        span.set_attribute(GEN_AI_SYSTEM, agent_name)
        if model is not None:
            span.set_attribute(GEN_AI_REQUEST_MODEL, model)
        if tier is not None:
            span.set_attribute(AGENTEVAL_TIER, tier)
        yield span


@contextmanager
def chat_span(model: str, provider: str | None = None) -> Iterator[Span]:
    """Open a ``chat`` span — per LLM round-trip (child of ``invoke_agent``).

    Args:
        model: Model identifier (e.g., ``"claude-sonnet-4-6"``). Required
            because ``chat`` spans without a model are not useful for
            cost/latency aggregation.
        provider: Optional provider name (e.g., ``"anthropic"`` / ``"openai"``).
            Set as ``gen_ai.system`` when provided. (Story 5.1 code-review
            Auditor M3 fix 2026-05-20: pre-edit docstring claimed parent-span
            attribute inheritance via OTel context — OTel SDK only propagates
            trace_id/span_id via context, NOT span attributes. When the
            caller passes ``provider=None``, the chat span carries no
            ``gen_ai.system`` attribute; consumers MUST set it explicitly
            on every chat span where the value matters.)

    Yields:
        The active OTel ``Span``; caller sets ``gen_ai.usage.*`` +
        ``gen_ai.response.finish_reasons`` on completion.
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(SPAN_CHAT) as span:
        span.set_attribute(GEN_AI_REQUEST_MODEL, model)
        if provider is not None:
            span.set_attribute(GEN_AI_SYSTEM, provider)
        yield span


@contextmanager
def execute_tool_span(
    tool_name: str,
    source: Literal["adapter", "hosted_mcp"],
    *,
    tool_call_id: str | None = None,
) -> Iterator[Span]:
    """Open an ``execute_tool`` span — per tool call (child of ``chat``).

    Args:
        tool_name: Tool name (e.g., ``"search"`` / ``"echo_back"``).
            Set as ``gen_ai.tool.name``.
        source: ``"adapter"`` when the tool-call record came from the
            adapter's response parsing; ``"hosted_mcp"`` when from the
            server-side observer (FR35).
        tool_call_id: Optional pre-existing tool-call identifier. When
            omitted, callers should set ``gen_ai.tool.call.id`` themselves
            after generating a uuid4 hex on the yielded span.

    Yields:
        The active OTel ``Span``; caller sets ``agenteval.tool.{success,
        duration_ms, args, result, error}`` on completion.
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(SPAN_EXECUTE_TOOL) as span:
        span.set_attribute(GEN_AI_TOOL_NAME, tool_name)
        span.set_attribute(AGENTEVAL_TOOL_SOURCE, source)
        if tool_call_id is not None:
            span.set_attribute(GEN_AI_TOOL_CALL_ID, tool_call_id)
        yield span


def emit_tool_call_span(
    *,
    name: str,
    args: Mapping[str, Any] | None,
    result: Any,
    error: str | None,
    latency_ms: float,
    source: Literal["adapter", "hosted_mcp"],
    tool_call_id: str | None = None,
) -> None:
    """Synthesize a complete ``execute_tool`` span from an already-finished tool-call record.

    Used by adapter ``_finalize`` paths (Stories 4.1 + 4.2) and the Story 5.2
    hosted-MCP observer that observe tool calls AFTER they complete (no live
    span context). Args are JSON-encoded at emission time per Story 1b.2 H_R5
    (OTel SDK rejects dict attribute values).

    Args:
        name: Tool name.
        args: Tool-call arguments (post-redaction); JSON-encoded for the
            ``agenteval.tool.args`` attribute.
        result: Tool-call return value (post-redaction). Primitive types
            (str/int/float/bool) pass through; complex values JSON-encoded.
        error: Error message (``None`` on success — ``agenteval.tool.error``
            attribute omitted when ``None``).
        latency_ms: Tool-call wall-clock duration in milliseconds.
        source: ``"adapter"`` or ``"hosted_mcp"`` (FR35).
        tool_call_id: Optional pre-existing tool-call identifier. Set as
            ``gen_ai.tool.call.id`` when provided.
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(SPAN_EXECUTE_TOOL) as span:
        span.set_attribute(GEN_AI_TOOL_NAME, name)
        span.set_attribute(AGENTEVAL_TOOL_SOURCE, source)
        span.set_attribute(AGENTEVAL_TOOL_SUCCESS, error is None)
        span.set_attribute(AGENTEVAL_TOOL_DURATION_MS, latency_ms)
        if tool_call_id is not None:
            span.set_attribute(GEN_AI_TOOL_CALL_ID, tool_call_id)
        # Story 1b.2 H_R5: args MUST be JSON-encoded string for OTel SDK.
        span.set_attribute(AGENTEVAL_TOOL_ARGS, json.dumps(dict(args) if args else {}))
        if error is not None:
            span.set_attribute(AGENTEVAL_TOOL_ERROR, error)
        # Result: primitives pass through; complex values JSON-encoded.
        if result is None:
            pass  # omit attribute on None result
        elif isinstance(result, str | int | float | bool):
            span.set_attribute(AGENTEVAL_TOOL_RESULT, result)
        else:
            try:
                span.set_attribute(AGENTEVAL_TOOL_RESULT, json.dumps(result))
            except TypeError:
                span.set_attribute(AGENTEVAL_TOOL_RESULT, str(result))
