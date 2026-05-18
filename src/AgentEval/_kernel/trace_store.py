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

"""OTel SDK trace store with per-test-id partitioning + projection accessors.

Per architecture L600-682 Decision-2: wraps OpenTelemetry SDK
`InMemorySpanExporter` with the 5 projection accessors documented at L664-669.
Sub-libraries call the projection accessors; they DO NOT touch spans directly
(architecture L853 rule).

The 5 projection accessors:
    - `get_run_spans(test_id)` — chronological list of all spans for a test
    - `get_tool_calls(test_id, source=None)` — projection into `ToolCallTrace`
      typed records (per FR35 + OTel GenAI `execute_tool` span name)
    - `get_usage(test_id)` — sum of `gen_ai.usage.*` across `chat` spans
    - `get_latency(test_id)` — sum of span durations in seconds
    - `get_run_manifest(test_id)` — per FR39 reproducibility record

Per-test isolation is enforced via the `agenteval.test_id` resource attribute
populated at TracerProvider setup. Listener v3's `start_test` calls
Story 1b.1's `_kernel/context.set_current_test_id(test_id)` which the OTel
SDK reads into each span via the configured resource.

Phase-1 backend: `InMemorySpanExporter` (the default `memory` backend per
PRD FR33b). Phase-1 also supports `jsonl` backend in `agenteval/telemetry/`
(Epic 5 Story 5.1); `otlp` backend is Phase 2 via the `[otlp]` extra.

Per-test cleanup hook: `clear_spans(test_id)` removes only the spans for
the given test, NOT the full exporter state — supports the Listener's
`end_test` flush flow without losing cross-test data prematurely.

References:
    - architecture L600-682 Decision-2 (LOAD-BEARING)
    - architecture L968-990 OTel GenAI semconv span names + attribute namespacing
    - PRD §FR32-35 trace recording + projection
    - PRD §FR39 RunManifest assembly
    - Story 1b.1 `_kernel/context.current_context()` for test_id default
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

from datetime import UTC

from AgentEval._kernel.context import current_context
from AgentEval._kernel.redaction import redaction_policy_hash
from AgentEval.types import RunManifest, ToolCallTrace, Usage

__all__ = [
    "get_run_spans",
    "get_tool_calls",
    "get_usage",
    "get_latency",
    "get_run_manifest",
    "clear_spans",
    "_configure_tracer_provider",
    "_get_exporter",
    "_set_exporter",
]


# Module-level singleton exporter, lazy-initialized. Tests + Story 5.1's
# Listener configuration can override via `_set_exporter()`.
_exporter: InMemorySpanExporter | None = None


def _get_exporter() -> InMemorySpanExporter:
    """Return the module-level InMemorySpanExporter, creating it on first access."""
    global _exporter
    if _exporter is None:
        _exporter = InMemorySpanExporter()
    return _exporter


def _set_exporter(exporter: InMemorySpanExporter) -> None:
    """Override the module-level exporter (test + Listener-wiring use only).

    Story 5.1's TracerProvider configuration calls this with a freshly
    instantiated `InMemorySpanExporter` wrapped behind a `BatchSpanProcessor`
    AFTER `RedactionProcessor` per architecture L679 chain order.
    """
    global _exporter
    _exporter = exporter


def _configure_tracer_provider() -> None:
    """Phase-1 helper that signals the TracerProvider is ready to record spans.

    Story 1b.2 ships this as a placeholder; the actual TracerProvider
    configuration (adding `RedactionProcessor` + `BatchSpanProcessor(exporter)`
    + the `agenteval.test_id` resource attribute reader) lands in
    Epic 5 Story 5.1's OTel Listener. Story 1b.2 documents the contract so
    Story 5.1's wiring drops into a known integration point.

    Phase-1 behavior: ensures `_get_exporter()` has initialized the singleton,
    so direct callers (tests, ad-hoc scripts) can read spans without needing
    to wire a full TracerProvider.
    """
    _get_exporter()


def _resolve_test_id(test_id: str | None) -> str | None:
    """Return the explicit test_id, or fall back to `current_context().test_id`."""
    if test_id is not None:
        return test_id
    ctx = current_context()
    return ctx.test_id if ctx is not None else None


def _spans_for_test(test_id: str) -> list[ReadableSpan]:
    """Internal helper: filter exporter spans by `agenteval.test_id` attribute, chronological."""
    exporter = _get_exporter()
    all_spans = exporter.get_finished_spans()
    matching = [s for s in all_spans if s.attributes and s.attributes.get("agenteval.test_id") == test_id]
    # OTel `start_time` is nanoseconds since epoch (int); sort ascending.
    matching.sort(key=lambda s: s.start_time or 0)
    return list(matching)


def get_run_spans(test_id: str | None = None) -> list[ReadableSpan]:
    """Return all spans tagged with the given test_id, chronological.

    Args:
        test_id: Listener v3 test identifier. When omitted, falls back to
            `current_context().test_id` from Story 1b.1's `_kernel/context.py`.

    Returns:
        List of `ReadableSpan` instances in chronological order (by start_time).
        Empty list if no spans for the test (NOT raise; this is a normal state
        for tests that didn't emit any spans).

    Raises:
        ValueError: If no `test_id` provided AND no `current_context()` bound.
    """
    resolved = _resolve_test_id(test_id)
    if resolved is None:
        raise ValueError(
            "get_run_spans() requires a test_id, either explicit or via current_context(); neither was provided"
        )
    return _spans_for_test(resolved)


def get_tool_calls(
    test_id: str | None = None,
    source: Literal["adapter", "hosted_mcp"] | None = None,
) -> list[ToolCallTrace]:
    """Project `execute_tool` spans into `ToolCallTrace` typed records.

    Per FR35 + architecture L975-985 OTel GenAI semconv: only spans named
    `execute_tool` are included. Optional `source` filter narrows to adapter-
    or hosted-MCP-observed tool calls.

    Args:
        test_id: As in `get_run_spans`.
        source: Optional filter on the `agenteval.tool.source` attribute.

    Returns:
        List of `ToolCallTrace` records. May be empty.
    """
    spans = get_run_spans(test_id)
    results: list[ToolCallTrace] = []
    for s in spans:
        if s.name != "execute_tool":
            continue
        attrs = s.attributes or {}
        span_source = attrs.get("agenteval.tool.source")
        if source is not None and span_source != source:
            continue
        if span_source not in ("adapter", "hosted_mcp"):
            # Defensive: skip malformed spans that don't carry a valid source.
            continue
        results.append(
            ToolCallTrace(
                name=str(attrs.get("gen_ai.tool.name", "")),
                args=_attr_to_mapping(attrs.get("agenteval.tool.args")),
                result=attrs.get("agenteval.tool.result"),
                error=_attr_to_optional_str(attrs.get("agenteval.tool.error")),
                latency_ms=_attr_as_float(attrs.get("agenteval.tool.duration_ms"), default=0.0),
                source=span_source,  # type: ignore[arg-type]  # narrowed by L186 guard above
                gen_ai_tool_call_id=str(attrs.get("gen_ai.tool.call.id", "")),
            )
        )
    return results


def _attr_to_mapping(value: object) -> dict[str, object]:
    """Coerce an OTel attribute value (str | sequence | dict | None) to a Mapping for ToolCallTrace."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    # OTel typically serializes complex args to a JSON-encoded string; tests may
    # populate either form. Defer JSON parsing to consumers — return a 1-key
    # wrapper so the type contract holds.
    return {"_raw": value}


def _attr_to_optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _attr_as_int(value: object, *, default: int = 0) -> int:
    """Coerce an OTel attribute value (typed union) to int. Used for `gen_ai.usage.*`."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _attr_as_float(value: object, *, default: float = 0.0) -> float:
    """Coerce an OTel attribute value (typed union) to float. Used for latency."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def get_usage(test_id: str | None = None) -> Usage:
    """Sum `gen_ai.usage.*` token counts across the test's `chat` spans (FR35)."""
    spans = get_run_spans(test_id)
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    for s in spans:
        if s.name != "chat":
            continue
        attrs = s.attributes or {}
        input_tokens += _attr_as_int(attrs.get("gen_ai.usage.input_tokens"))
        output_tokens += _attr_as_int(attrs.get("gen_ai.usage.output_tokens"))
        cached_input_tokens += _attr_as_int(attrs.get("gen_ai.usage.cached_input_tokens"))
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
    )


def get_latency(test_id: str | None = None) -> float:
    """Return total span-duration latency in seconds across the test's spans."""
    spans = get_run_spans(test_id)
    total_ns = 0
    for s in spans:
        if s.start_time is None or s.end_time is None:
            continue
        total_ns += s.end_time - s.start_time
    return total_ns / 1_000_000_000.0


def get_run_manifest(test_id: str | None = None) -> RunManifest:
    """Assemble a `RunManifest` for the given test per FR39 + architecture L669.

    Fields populated:
        - `library_version` ← `AgentEval.__version__`
        - `test_id` / `suite_id` ← `current_context()` if not provided directly
        - `redaction_policy_hash` ← `redaction.redaction_policy_hash()`
        - `started_at` / `ended_at` ← min/max span timestamps (datetime UTC)
        - `agenteval_tier_breakdown` ← count of spans per `_agenteval_tier`
          attribute value
    """
    from datetime import datetime

    from AgentEval import __version__ as library_version

    resolved = _resolve_test_id(test_id)
    if resolved is None:
        raise ValueError(
            "get_run_manifest() requires a test_id, either explicit or via current_context(); neither was provided"
        )
    spans = _spans_for_test(resolved)

    ctx = current_context()
    suite_id = ctx.suite_id if ctx is not None else ""

    if spans:
        start_ns = min(s.start_time or 0 for s in spans)
        end_ns = max(s.end_time or 0 for s in spans)
        started_at = datetime.fromtimestamp(start_ns / 1_000_000_000.0, tz=UTC)
        ended_at = datetime.fromtimestamp(end_ns / 1_000_000_000.0, tz=UTC)
    else:
        # No spans → manifest still constructible with zero timestamps; caller
        # can distinguish empty runs via the tier breakdown.
        epoch = datetime.fromtimestamp(0, tz=UTC)
        started_at = epoch
        ended_at = epoch

    tier_breakdown: dict[int, int] = {}
    for s in spans:
        attrs = s.attributes or {}
        tier = attrs.get("_agenteval_tier")
        if isinstance(tier, int):
            tier_breakdown[tier] = tier_breakdown.get(tier, 0) + 1

    return RunManifest(
        library_version=library_version,
        test_id=resolved,
        suite_id=suite_id,
        redaction_policy_hash=redaction_policy_hash(),
        started_at=started_at,
        ended_at=ended_at,
        agenteval_tier_breakdown=tier_breakdown,
    )


def clear_spans(test_id: str) -> int:
    """Remove spans tagged with `test_id` from the exporter; return count removed.

    Called by the Listener's `end_test` hook (Epic 5 Story 5.1 wires it).
    Phase-1 implementation manipulates `InMemorySpanExporter`'s internal
    `_finished_spans` list directly — this attribute is private but stable
    in `opentelemetry-sdk` 1.20+.

    Args:
        test_id: Listener v3 test identifier.

    Returns:
        Count of spans cleared.
    """
    exporter = _get_exporter()
    # `_finished_spans` is the internal buffer; documented as private but
    # stable across opentelemetry-sdk 1.20+ minor versions. Phase-1 carry-over:
    # if a future SDK refactor removes it, swap to `clear()` + re-add the
    # surviving spans (more expensive but contract-public).
    finished = exporter._finished_spans
    before = len(finished)
    finished[:] = [s for s in finished if not (s.attributes and s.attributes.get("agenteval.test_id") == test_id)]
    return before - len(finished)
