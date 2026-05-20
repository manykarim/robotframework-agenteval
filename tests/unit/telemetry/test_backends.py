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

"""Memory + JSONL trace backend tests (Story 5.1)."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval.telemetry import spans
from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend
from AgentEval.telemetry.listener import TestIdContextSpanProcessor
from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID, GEN_AI_TOOL_NAME


@pytest.fixture
def per_test_exporter() -> Iterator[None]:
    """Per-test isolation for the shared trace_store exporter.

    Clears any spans accumulated across tests so each test starts fresh.
    """
    yield
    # Best-effort cleanup; tests that clear_spans-then-assert should not
    # rely on this for correctness.
    with contextlib.suppress(Exception):
        trace_store._get_exporter().clear()
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()


_provider_configured = False


def _configure_provider_once() -> None:
    """Configure a TracerProvider with the `TestIdContextSpanProcessor` chain.

    OTel only allows one TracerProvider per process; configure on first call.
    Subsequent calls are no-ops.
    """
    global _provider_configured
    if _provider_configured:
        return
    # Resource intentionally does NOT pre-populate AGENTEVAL_TEST_ID — the
    # SpanProcessor stamps it per-span from kernel context. See Listener.
    resource = Resource.create({})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(TestIdContextSpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(trace_store._get_exporter()))  # noqa: SLF001
    trace.set_tracer_provider(provider)
    _provider_configured = True


def _set_active_test_id(test_id: str) -> None:
    """Set the test_id on `_kernel/context` so the SpanProcessor reads it."""
    _kernel_context.set_current_test_id(test_id, suite_id="suite")


def _configure_provider_with_test_id(test_id: str) -> None:
    """Configure the shared provider (once) + activate `test_id` in kernel context."""
    _configure_provider_once()
    _set_active_test_id(test_id)


def test_memory_backend_flush_is_noop(tmp_path: Path, per_test_exporter: None) -> None:
    backend = MemoryBackend()
    # flush_test on memory is a no-op; should not raise + should not write files.
    backend.flush_test("test-id", suite_id="suite-id", output_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_memory_backend_name_is_memory() -> None:
    assert MemoryBackend.name == "memory"


def test_jsonl_backend_name_is_jsonl() -> None:
    assert JSONLBackend.name == "jsonl"


def test_jsonl_backend_writes_one_line_per_span(tmp_path: Path, per_test_exporter: None) -> None:
    """JSONL artifact: one span per line at the canonical path."""
    test_id = "suite.test_one"
    suite_id = "suite"
    _configure_provider_with_test_id(test_id)
    # Generate 3 spans for this test.
    with spans.invoke_agent_span("Adapter"), spans.chat_span(model="m"):  # noqa: SIM117 — nested for OTel parent-child clarity
        with spans.execute_tool_span("echo", source="adapter"):  # noqa: SIM117
            pass
    backend = JSONLBackend()
    result_path = backend.flush_test(test_id, suite_id=suite_id, output_dir=tmp_path)
    assert result_path is not None
    assert result_path == tmp_path / "agenteval" / "trace__suite__suite.test_one.jsonl"
    assert result_path.exists()
    lines = result_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    # Each line must be a valid JSON envelope with the required schema fields.
    for line in lines:
        record = json.loads(line)
        assert "name" in record
        assert "trace_id" in record
        assert "span_id" in record
        assert "attributes" in record
        assert "resource_attributes" in record
        assert "status" in record


def test_jsonl_backend_creates_missing_output_dir(tmp_path: Path, per_test_exporter: None) -> None:
    """Backend creates `<output_dir>/agenteval/` if missing."""
    test_id = "suite.test_mkdir"
    _configure_provider_with_test_id(test_id)
    with spans.invoke_agent_span("A"):
        pass
    nonexistent = tmp_path / "deeply" / "nested" / "dir"
    backend = JSONLBackend()
    result_path = backend.flush_test(test_id, suite_id="suite", output_dir=nonexistent)
    assert result_path is not None
    assert result_path.exists()
    assert (nonexistent / "agenteval").is_dir()


def test_jsonl_backend_test_id_isolation(tmp_path: Path, per_test_exporter: None) -> None:
    """Two test_ids share the exporter but get separate JSONL files with non-overlapping spans."""
    backend = JSONLBackend()
    # Test A
    _configure_provider_with_test_id("suite.test_a")
    with spans.invoke_agent_span("A"):
        pass
    path_a = backend.flush_test("suite.test_a", suite_id="suite", output_dir=tmp_path)
    trace_store.clear_spans("suite.test_a")
    _kernel_context.unbind_context()
    # Test B (same provider, new context test_id)
    _configure_provider_with_test_id("suite.test_b")
    with spans.invoke_agent_span("B"):
        pass
    path_b = backend.flush_test("suite.test_b", suite_id="suite", output_dir=tmp_path)
    assert path_a is not None
    assert path_b is not None
    assert path_a != path_b
    # Each file has 1 invoke_agent span; no cross-pollution.
    lines_a = path_a.read_text(encoding="utf-8").strip().split("\n")
    lines_b = path_b.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines_a) == 1, f"test_a JSONL has {len(lines_a)} lines: {lines_a}"
    assert len(lines_b) == 1, f"test_b JSONL has {len(lines_b)} lines: {lines_b}"
    record_a = json.loads(lines_a[0])
    record_b = json.loads(lines_b[0])
    # Per Story 5.1: test_id is stamped as a SPAN attribute (not Resource)
    # by TestIdContextSpanProcessor reading from `_kernel/context`.
    assert record_a["attributes"][AGENTEVAL_TEST_ID] == "suite.test_a"
    assert record_b["attributes"][AGENTEVAL_TEST_ID] == "suite.test_b"


def test_jsonl_backend_path_sanitizes_unsafe_test_id(tmp_path: Path, per_test_exporter: None) -> None:
    """Path-traversal attempts in test_id are sanitized to underscores."""
    evil_id = "../../../etc/passwd"
    _configure_provider_with_test_id(evil_id)
    with spans.invoke_agent_span("A"):
        pass
    backend = JSONLBackend()
    result_path = backend.flush_test(evil_id, suite_id="ok", output_dir=tmp_path)
    assert result_path is not None
    # Path must NOT escape tmp_path/agenteval/.
    assert tmp_path in result_path.parents
    assert result_path.parent == tmp_path / "agenteval"
    # Sanitized filename should contain underscores (slashes replaced).
    assert "/" not in result_path.name
    assert result_path.exists()


def test_jsonl_backend_write_failure_returns_none_and_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, per_test_exporter: None
) -> None:
    """On write failure, return None + emit a warning; do NOT raise."""
    test_id = "suite.test_fail"
    _configure_provider_with_test_id(test_id)
    with spans.invoke_agent_span("A"):
        pass

    def _explode_open(self: Path, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise OSError("simulated disk failure")

    monkeypatch.setattr(Path, "open", _explode_open)
    backend = JSONLBackend()
    with pytest.warns(UserWarning, match="JSONL backend write failed"):
        result_path = backend.flush_test(test_id, suite_id="suite", output_dir=tmp_path)
    assert result_path is None


def test_jsonl_backend_empty_suite_id_uses_placeholder(tmp_path: Path, per_test_exporter: None) -> None:
    """Empty suite_id falls back to `_suite` placeholder in the filename."""
    test_id = "lonely_test"
    _configure_provider_with_test_id(test_id)
    with spans.invoke_agent_span("A"):
        pass
    backend = JSONLBackend()
    result_path = backend.flush_test(test_id, suite_id="", output_dir=tmp_path)
    assert result_path is not None
    assert "_suite" in result_path.name


def test_jsonl_backend_falls_back_to_cwd_when_output_dir_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, per_test_exporter: None
) -> None:
    """output_dir=None → write under Path.cwd()/agenteval/."""
    monkeypatch.chdir(tmp_path)
    test_id = "suite.test_cwd"
    _configure_provider_with_test_id(test_id)
    with spans.invoke_agent_span("A"):
        pass
    backend = JSONLBackend()
    result_path = backend.flush_test(test_id, suite_id="suite", output_dir=None)
    assert result_path is not None
    assert tmp_path in result_path.parents


def test_jsonl_serialized_attributes_include_tool_name(tmp_path: Path, per_test_exporter: None) -> None:
    """gen_ai.tool.name attribute survives the JSONL round-trip."""
    test_id = "suite.test_attrs"
    _configure_provider_with_test_id(test_id)
    with spans.execute_tool_span("echo_back", source="adapter"):
        pass
    backend = JSONLBackend()
    result_path = backend.flush_test(test_id, suite_id="suite", output_dir=tmp_path)
    assert result_path is not None
    record = json.loads(result_path.read_text(encoding="utf-8").strip().split("\n")[0])
    assert record["attributes"][GEN_AI_TOOL_NAME] == "echo_back"


def test_sanitize_rejects_dot_only_segments() -> None:
    """Story 5.1 code-review 2-way MED fix 2026-05-20 (Blind MED-2 + Edge-cases M1):
    `_sanitize_path_segment` must reject `.` / `..` / all-dot segments
    explicitly, not just rely on POSIX semantics blocking traversal.
    """
    from AgentEval.telemetry.backends import _sanitize_path_segment

    assert _sanitize_path_segment(".") == "_"
    assert _sanitize_path_segment("..") == "_"
    assert _sanitize_path_segment("...") == "_"
    # Legit segments with embedded dots still pass through.
    assert _sanitize_path_segment("test.one") == "test.one"
    assert _sanitize_path_segment("a.b.c") == "a.b.c"


def test_jsonl_backend_skips_write_when_no_spans(tmp_path: Path, per_test_exporter: None) -> None:
    """Story 5.1 code-review Edge-cases M3 fix 2026-05-20: zero spans → no
    phantom 0-byte JSONL artifact.
    """
    backend = JSONLBackend()
    # No spans emitted — flush should return None + create no file.
    _configure_provider_with_test_id("suite.empty_test")
    result_path = backend.flush_test("suite.empty_test", suite_id="suite", output_dir=tmp_path)
    assert result_path is None
    assert not (tmp_path / "agenteval" / "trace__suite__suite.empty_test.jsonl").exists()


def test_jsonl_backend_catches_value_error_in_serialization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, per_test_exporter: None
) -> None:
    """Story 5.1 code-review Edge-cases H2 fix 2026-05-20: pre-edit `flush_test`
    only caught `OSError`. A `ValueError` from `json.dumps` on circular
    references (or from `_span_to_jsonl_line` more broadly) propagated past
    `flush_test` → masked test outcomes via the RF Listener machinery.
    Now widened to `(OSError, ValueError, RecursionError)`. Patch
    `_span_to_jsonl_line` to raise `ValueError` directly + verify the
    outer except catches it gracefully.
    """
    from AgentEval.telemetry import backends as _backends

    def _raises_value_error(span: Any) -> str:  # noqa: ARG001
        raise ValueError("Circular reference detected (simulated)")

    monkeypatch.setattr(_backends, "_span_to_jsonl_line", _raises_value_error)
    _configure_provider_with_test_id("suite.bad_test")
    with spans.invoke_agent_span("A"):
        pass
    backend = JSONLBackend()
    with pytest.warns(UserWarning, match="JSONL backend write failed"):
        result_path = backend.flush_test("suite.bad_test", suite_id="suite", output_dir=tmp_path)
    assert result_path is None  # graceful failure, no propagation


def test_safe_dict_handles_value_error_via_str_fallback() -> None:
    """`_safe_dict` widened to catch (TypeError, ValueError, RecursionError)
    per Edge-cases H2 fix; verify each non-JSON-encodable input gets the
    `str()` fallback.
    """
    from AgentEval.telemetry.backends import _safe_dict

    # Circular reference → json.dumps raises ValueError → str fallback.
    a: dict[str, object] = {}
    a["self"] = a
    safe = _safe_dict({"circular_attr": a})
    assert isinstance(safe["circular_attr"], str)
    # Bytes → TypeError → str fallback.
    safe = _safe_dict({"bytes_attr": b"raw bytes"})
    assert isinstance(safe["bytes_attr"], str)
    # Encodable values pass through unchanged.
    safe = _safe_dict({"ok": 42, "ok_str": "hello"})
    assert safe == {"ok": 42, "ok_str": "hello"}
