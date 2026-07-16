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

"""A tiny in-memory trace so a Tier-1 test can check what a tool call did.

Record spans and tool calls into a per-test buffer, then project the tool calls
back out as ``ToolCallTrace`` records. ``was_tool_called`` answers the one
question the deterministic path cares about: did a named tool run, optionally
with these arguments? No OTLP, no JSONL, no god-listener - just enough to assert.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from AgentEval._core.types import ToolCallTrace

__all__ = [
    "Span",
    "record_span",
    "record_tool_call",
    "get_spans",
    "get_tool_calls",
    "was_tool_called",
    "clear",
]

_DEFAULT_TEST_ID = "__default__"

# Tool-call spans are named this; the projection filters on it.
SPAN_EXECUTE_TOOL = "execute_tool"


@dataclass
class Span:
    """A recorded span: a name plus a bag of attributes, in insertion order."""

    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


# Per-test-id span buffers. Keyed so surfaces can isolate one test's evidence.
_STORE: dict[str, list[Span]] = {}


def _key(test_id: str | None) -> str:
    return test_id if test_id is not None else _DEFAULT_TEST_ID


def record_span(name: str, attributes: Mapping[str, Any] | None = None, *, test_id: str | None = None) -> Span:
    """Record a span under ``test_id`` and return it."""
    span = Span(name=name, attributes=dict(attributes or {}))
    _STORE.setdefault(_key(test_id), []).append(span)
    return span


def record_tool_call(
    name: str,
    args: Mapping[str, Any] | None = None,
    *,
    result: Any | None = None,
    error: str | None = None,
    latency_ms: float = 0.0,
    source: Literal["adapter", "hosted_mcp"] = "adapter",
    tool_call_id: str = "",
    test_id: str | None = None,
) -> Span:
    """Record one completed tool call as an ``execute_tool`` span."""
    return record_span(
        SPAN_EXECUTE_TOOL,
        {
            "tool.name": name,
            "tool.args": dict(args or {}),
            "tool.result": result,
            "tool.error": error,
            "tool.latency_ms": latency_ms,
            "tool.source": source,
            "tool.call_id": tool_call_id,
        },
        test_id=test_id,
    )


def get_spans(test_id: str | None = None) -> list[Span]:
    """Return all spans recorded under ``test_id``, in order."""
    return list(_STORE.get(_key(test_id), []))


def get_tool_calls(
    test_id: str | None = None,
    source: Literal["adapter", "hosted_mcp"] | None = None,
) -> list[ToolCallTrace]:
    """Project ``execute_tool`` spans into ``ToolCallTrace`` records.

    ``sequence_index`` is assigned from recording order; ``source`` optionally
    filters to adapter- or MCP-observed calls.
    """
    results: list[ToolCallTrace] = []
    sequence_index = 0
    for span in get_spans(test_id):
        if span.name != SPAN_EXECUTE_TOOL:
            continue
        attrs = span.attributes
        span_source = attrs.get("tool.source", "adapter")
        if source is not None and span_source != source:
            continue
        results.append(
            ToolCallTrace(
                name=str(attrs.get("tool.name", "")),
                args=_as_mapping(attrs.get("tool.args")),
                result=attrs.get("tool.result"),
                error=attrs.get("tool.error"),
                latency_ms=float(attrs.get("tool.latency_ms", 0.0) or 0.0),
                source=span_source,
                tool_call_id=str(attrs.get("tool.call_id", "")),
                sequence_index=sequence_index,
            )
        )
        sequence_index += 1
    return results


def was_tool_called(
    name: str,
    args: Mapping[str, Any] | None = None,
    *,
    test_id: str | None = None,
) -> bool:
    """Return True if ``name`` was called, and (when given) with ``args`` as a subset.

    A subset match keeps the assertion robust to extra arguments the caller
    doesn't care to pin.
    """
    for call in get_tool_calls(test_id):
        if call.name != name:
            continue
        if args is None:
            return True
        if all(call.args.get(k) == v for k, v in args.items()):
            return True
    return False


def clear(test_id: str | None = None) -> None:
    """Drop recorded spans for ``test_id`` (or all tests when ``test_id`` is None)."""
    if test_id is None:
        _STORE.clear()
    else:
        _STORE.pop(_key(test_id), None)


def _as_mapping(value: Any) -> dict[str, Any]:
    """Coerce a stored args value into a plain dict."""
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    return {"_raw": value}
