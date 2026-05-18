"""Unit tests for _kernel/trace_store.py (AC-1b.2.1, AC-1b.2.2, AC-1b.2.8).

Uses the OTel SDK directly: a real TracerProvider + InMemorySpanExporter +
SimpleSpanProcessor, configured per-test in fixtures so the trace_store
module sees fresh state every test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from AgentEval._kernel import trace_store as ts
from AgentEval._kernel.context import (
    TestContext,
    bind_context,
    unbind_context,
)


@pytest.fixture
def fresh_exporter() -> Iterator[InMemorySpanExporter]:
    """Each test gets a fresh exporter, registered as the trace_store module's singleton."""
    exporter = InMemorySpanExporter()
    ts._set_exporter(exporter)
    yield exporter
    # Clean up: reset the module singleton so the next test gets a clean slate.
    ts._set_exporter(InMemorySpanExporter())


@pytest.fixture
def tracer(fresh_exporter: InMemorySpanExporter) -> Iterator[trace.Tracer]:
    """A real Tracer wired to the fresh exporter for span emission in tests."""
    provider = TracerProvider(resource=Resource.create({"service.name": "agenteval-test"}))
    provider.add_span_processor(SimpleSpanProcessor(fresh_exporter))
    yield provider.get_tracer("agenteval.test")
    # No global state to reset; the trace_store fixture handles exporter cleanup.


@pytest.fixture(autouse=True)
def _clear_context() -> Iterator[None]:
    yield
    unbind_context()


def _emit_span(tracer: trace.Tracer, name: str, test_id: str, attributes: dict[str, object] | None = None) -> None:
    """Helper: emit a span with the `agenteval.test_id` attribute set."""
    attrs = {"agenteval.test_id": test_id}
    if attributes:
        attrs.update(attributes)
    span = tracer.start_span(name, attributes=attrs)
    span.end()


# ---- AC-1b.2.1: get_run_spans ------------------------------------------ #


def test_get_run_spans_returns_only_matching_test_id(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "op1", test_id="t1")
    _emit_span(tracer, "op2", test_id="t2")
    _emit_span(tracer, "op3", test_id="t1")

    spans_t1 = ts.get_run_spans("t1")
    assert len(spans_t1) == 2
    assert {s.name for s in spans_t1} == {"op1", "op3"}
    # t2 spans not in t1 result.
    assert all(s.attributes["agenteval.test_id"] == "t1" for s in spans_t1)  # type: ignore[index]


def test_get_run_spans_chronological_order(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "first", test_id="t1")
    _emit_span(tracer, "second", test_id="t1")
    _emit_span(tracer, "third", test_id="t1")

    spans = ts.get_run_spans("t1")
    assert [s.name for s in spans] == ["first", "second", "third"]


def test_get_run_spans_empty_for_unknown_test_id(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "op1", test_id="t1")
    assert ts.get_run_spans("nonexistent") == []


def test_get_run_spans_defaults_to_current_context(tracer: trace.Tracer) -> None:
    bind_context(TestContext(test_id="t-current", suite_id="s", scope="test"))
    _emit_span(tracer, "op", test_id="t-current")

    spans = ts.get_run_spans()  # no explicit test_id
    assert len(spans) == 1
    assert spans[0].name == "op"


def test_get_run_spans_raises_without_test_id_or_context(tracer: trace.Tracer) -> None:
    """If neither explicit nor current_context provides a test_id, raise ValueError."""
    with pytest.raises(ValueError, match="requires a test_id"):
        ts.get_run_spans()


# ---- AC-1b.2.1: get_tool_calls ----------------------------------------- #


def test_get_tool_calls_projects_execute_tool_spans(tracer: trace.Tracer) -> None:
    _emit_span(
        tracer,
        "execute_tool",
        test_id="t1",
        attributes={
            "gen_ai.tool.name": "bash",
            "gen_ai.tool.call.id": "call-1",
            "agenteval.tool.args": {"cmd": "ls"},
            "agenteval.tool.result": "file1",
            "agenteval.tool.duration_ms": 12.3,
            "agenteval.tool.source": "adapter",
        },
    )
    # Non-execute_tool span ignored.
    _emit_span(tracer, "chat", test_id="t1", attributes={"agenteval.tool.source": "adapter"})

    tool_calls = ts.get_tool_calls("t1")
    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert tc.name == "bash"
    assert tc.gen_ai_tool_call_id == "call-1"
    assert tc.latency_ms == 12.3
    assert tc.source == "adapter"


def test_get_tool_calls_source_filter(tracer: trace.Tracer) -> None:
    _emit_span(
        tracer,
        "execute_tool",
        test_id="t1",
        attributes={"gen_ai.tool.name": "tool-a", "agenteval.tool.source": "adapter"},
    )
    _emit_span(
        tracer,
        "execute_tool",
        test_id="t1",
        attributes={"gen_ai.tool.name": "tool-b", "agenteval.tool.source": "hosted_mcp"},
    )

    adapter_only = ts.get_tool_calls("t1", source="adapter")
    assert len(adapter_only) == 1
    assert adapter_only[0].name == "tool-a"

    hosted_only = ts.get_tool_calls("t1", source="hosted_mcp")
    assert len(hosted_only) == 1
    assert hosted_only[0].name == "tool-b"


# ---- AC-1b.2.1: get_usage ---------------------------------------------- #


def test_get_usage_sums_gen_ai_usage_attributes(tracer: trace.Tracer) -> None:
    _emit_span(
        tracer,
        "chat",
        test_id="t1",
        attributes={
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 50,
            "gen_ai.usage.cached_input_tokens": 30,
        },
    )
    _emit_span(
        tracer,
        "chat",
        test_id="t1",
        attributes={
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 80,
        },
    )
    # Non-chat span (e.g., execute_tool) does NOT contribute to usage.
    _emit_span(
        tracer,
        "execute_tool",
        test_id="t1",
        attributes={"gen_ai.usage.input_tokens": 9999},  # MUST be ignored
    )

    usage = ts.get_usage("t1")
    assert usage.input_tokens == 300
    assert usage.output_tokens == 130
    assert usage.cached_input_tokens == 30


def test_get_usage_empty_returns_zero_usage(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "execute_tool", test_id="t1")  # no chat spans
    u = ts.get_usage("t1")
    assert u.input_tokens == 0
    assert u.output_tokens == 0
    assert u.cached_input_tokens == 0


# ---- AC-1b.2.1: get_latency -------------------------------------------- #


def test_get_latency_sums_span_durations(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "op1", test_id="t1")
    _emit_span(tracer, "op2", test_id="t1")
    latency = ts.get_latency("t1")
    assert latency >= 0.0
    # Each span ends immediately; sum should be small but non-negative.


# ---- AC-1b.2.1: get_run_manifest --------------------------------------- #


def test_get_run_manifest_populates_all_fields(tracer: trace.Tracer) -> None:
    bind_context(TestContext(test_id="t-mani", suite_id="s-mani", scope="test"))
    _emit_span(
        tracer,
        "op",
        test_id="t-mani",
        attributes={"_agenteval_tier": 1},
    )
    _emit_span(
        tracer,
        "op",
        test_id="t-mani",
        attributes={"_agenteval_tier": 1},
    )
    _emit_span(
        tracer,
        "op",
        test_id="t-mani",
        attributes={"_agenteval_tier": 2},
    )

    manifest = ts.get_run_manifest("t-mani")
    assert manifest.test_id == "t-mani"
    assert manifest.suite_id == "s-mani"
    assert manifest.library_version  # non-empty (the actual version from AgentEval.__version__)
    assert len(manifest.redaction_policy_hash) == 64  # SHA-256 hex
    assert dict(manifest.agenteval_tier_breakdown) == {1: 2, 2: 1}


def test_get_run_manifest_empty_run(tracer: trace.Tracer) -> None:
    """A test with no spans gets a manifest with zero-epoch timestamps + empty tier breakdown."""
    bind_context(TestContext(test_id="t-empty", suite_id="s", scope="test"))
    manifest = ts.get_run_manifest("t-empty")
    assert manifest.test_id == "t-empty"
    assert dict(manifest.agenteval_tier_breakdown) == {}


# ---- AC-1b.2.2: clear_spans -------------------------------------------- #


def test_clear_spans_removes_only_matching_test_id(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "op-a", test_id="t1")
    _emit_span(tracer, "op-b", test_id="t1")
    _emit_span(tracer, "op-c", test_id="t2")

    cleared = ts.clear_spans("t1")
    assert cleared == 2
    # t1 gone; t2 retained.
    assert ts.get_run_spans("t1") == []
    assert len(ts.get_run_spans("t2")) == 1


def test_clear_spans_returns_zero_for_unknown_test_id(tracer: trace.Tracer) -> None:
    _emit_span(tracer, "op", test_id="t1")
    assert ts.clear_spans("nonexistent") == 0
    assert len(ts.get_run_spans("t1")) == 1


# ---- AC-1b.2.2: _configure_tracer_provider ---------------------------- #


def test_configure_tracer_provider_initializes_exporter() -> None:
    """The Phase-1 helper just ensures the exporter singleton is initialized."""
    # Force the singleton to None to test lazy initialization.
    ts._exporter = None
    ts._configure_tracer_provider()
    assert ts._exporter is not None
    assert isinstance(ts._exporter, InMemorySpanExporter)
