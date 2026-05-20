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

"""End-to-end Listener + warnings buffer + Get Last Warnings integration (Story 5.4).

8 tests covering AC-5.4.7:

- happy-path: no degradation → empty warning list.
- mark_external_mixed canonical FR61 trigger → 1 record + mcp_coverage=external_mixed.
- JSONL write failure → 1 record + test outcome NOT raised.
- RunManifest.warnings field populated with 5-key dicts (NOT list[str]).
- Per-test isolation: Test A warning doesn't pollute Test B's buffer.
- test_id="all" merges across tests sorted by timestamp ascending.
- Pre-test sentinel records flush into the first bound test.
- clear_warnings fires at end_test (buffer drained post-end_test).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.mcp.observer import HostedMcpObserver
from AgentEval.providers.base import ChatResponse, ProviderUsage
from AgentEval.providers.mock import MockProvider
from AgentEval.telemetry.library import TelemetryLibrary
from AgentEval.telemetry.listener import Listener, _active_listeners


@pytest.fixture(autouse=True)
def isolated_tracer_state() -> Iterator[None]:
    """Reset OTel + Listener + warnings state before + after each test."""
    snapshot_listeners = list(_active_listeners)
    _active_listeners[:] = []
    _agenteval_warnings.clear_warnings(None)
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()
    yield
    _active_listeners[:] = snapshot_listeners
    _agenteval_warnings.clear_warnings(None)
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()


class _MockData:
    def __init__(self, *, full_name: str, parent: Any | None = None) -> None:
        self.full_name = full_name
        self.parent = parent


def _mock_provider() -> MockProvider:
    return MockProvider(
        responses=[
            ChatResponse(
                text="ok",
                tool_calls=[],
                usage=ProviderUsage(input_tokens=10, output_tokens=5),
                cost_usd=0.001,
            )
        ]
    )


def test_e2e_get_last_warnings_returns_empty_list_when_no_degradation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy-path agent run with no degradation → `Get Last Warnings` returns `[]`."""
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.happy", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    GenericAdapter(provider_instance=_mock_provider()).run("hi")
    out = TelemetryLibrary().get_last_warnings("current")
    assert out == []
    listener.end_test(test, None)


def test_e2e_get_last_warnings_captures_mark_external_mixed_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR61 canonical trigger: `mark_external_mixed` after prior observation
    emits both Python channel + structured record. `Get Last Warnings`
    surfaces the record + `mcp_coverage` is `"external_mixed"`.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.external_mixed", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Simulate prior hosted observation: append a ToolCallTrace to the
    # observer's internal state via the public observation flow. The
    # AC-5.4.3 contract reads `len(self._state.tool_calls) >= 1`.
    obs = HostedMcpObserver()
    # Directly inject a ToolCallTrace under the lock to simulate that
    # ≥1 tool call was intercepted before the degradation. Mirrors the
    # internal pattern at `mcp/observer.py:_record`.
    from AgentEval.types import ToolCallTrace

    with obs._lock:  # noqa: SLF001 — test fixture validates AC-5.4.3 invariant
        obs._state.tool_calls.append(  # noqa: SLF001
            ToolCallTrace(
                name="echo",
                args={"x": 1},
                result="ok",
                error=None,
                latency_ms=1.0,
                source="hosted_mcp",
                gen_ai_tool_call_id="t-1",
                sequence_index=1,
            )
        )
    # Now degrade.
    obs.mark_external_mixed("subprocess MCP detected post-hosted-call")
    out = TelemetryLibrary().get_last_warnings("current")
    assert len(out) == 1
    assert out[0]["source"] == "mcp.observer"
    assert "subprocess MCP detected" in out[0]["message"]
    assert out[0]["remediation"] is not None
    # mcp_coverage now resolves to external_mixed.
    assert obs.compute_coverage() == "external_mixed"
    # Story 5.4 code-review 3-way HIGH-B regression: call mark_external_mixed
    # a second time. The dedupe sentinel (`_external_mixed_warned`) must
    # prevent a second warning emit + a second structured record. The
    # `external_mixed_reasons` list still appends (forensic trail
    # preservation per ADR-016).
    obs.mark_external_mixed("subprocess MCP detected — second signal")
    after_second = TelemetryLibrary().get_last_warnings("current")
    assert len(after_second) == 1, (
        f"HIGH-B regression: dedupe sentinel must suppress second emit; got {len(after_second)} records"
    )
    assert len(obs.external_mixed_reasons()) == 2, "forensic trail: external_mixed_reasons MUST accumulate both signals"
    listener.end_test(test, None)


def test_e2e_dual_channel_order_record_first_warn_second() -> None:
    """Story 5.4 code-review 1-way Blind HIGH-C regression: when `warnings`
    filter is set to `error::DegradedTraceWarning`, the `warnings.warn`
    call raises. The structured `record_warning` MUST fire BEFORE the
    Python channel so the buffer is populated even under -W error.

    Uses the RunManifest emit path (which always runs regardless of
    spans) so we can deterministically trigger the dual-channel emit
    site under a `-W error` filter.
    """
    import warnings as py_warnings
    from datetime import UTC, datetime

    from AgentEval.errors import DegradedTraceWarning
    from AgentEval.telemetry.run_manifest import RunManifestEmitter
    from AgentEval.types import RunManifest

    _kernel_context.set_current_test_id("S.W_error", suite_id="S")
    now = datetime.now(UTC)
    # Construct a minimal manifest + try to emit at a path that will
    # fail mkdir (Path("/dev/null/agenteval") raises OSError because
    # /dev/null is not a directory). The emitter catches OSError, runs
    # record_warning(), then calls warnings.warn(...) which raises
    # under -W error.
    manifest = RunManifest(
        library_version="0.1.0",
        test_id="S.W_error",
        suite_id="S",
        redaction_policy_hash="0" * 64,
        started_at=now,
        ended_at=now,
    )
    with py_warnings.catch_warnings():
        py_warnings.simplefilter("error", DegradedTraceWarning)
        with contextlib.suppress(DegradedTraceWarning):
            RunManifestEmitter().emit(
                manifest,
                output_dir=Path("/dev/null"),
                suite_id="S",
                test_id="S.W_error",
            )

    # After `-W error` raised, the structured record MUST still be present.
    records = _agenteval_warnings.get_warnings("S.W_error")
    assert len(records) >= 1, (
        "HIGH-C regression: with -W error::DegradedTraceWarning, the "
        "structured record_warning() call MUST fire BEFORE warnings.warn(); "
        "pre-fix order dropped the structured record."
    )
    assert any(r.source == "telemetry.run_manifest" for r in records), (
        f"HIGH-C regression: expected source='telemetry.run_manifest'; got {[r.source for r in records]}"
    )
    _agenteval_warnings.clear_warnings("S.W_error")


def test_e2e_get_last_warnings_captures_jsonl_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JSONL write failure → structured record captured + test outcome NOT raised (AC-5.3.2).

    Story 5.4 code-review 3-way HIGH-G fix 2026-05-20 (Blind MED-G +
    Edge-cases HIGH-2 + Auditor HIGH-1) — pre-edit fake-green: the
    bad_target fixture (writing a file at `<tmp>/agenteval/`) defeated
    BOTH the JSONL write AND the manifest sidecar write, then asserted
    only `out == []` (which is trivially true post-end_test clear).
    Now: snapshot the buffer BEFORE end_test runs, AND verify the
    structured record was captured with the correct source identifier.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.jsonl_fail", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Force ONLY the JSONL flush to fail: pre-create the `<tmp>/agenteval/`
    # DIRECTORY (so manifest emit + sidecar still works) + then write a
    # file at the exact JSONL target path inside it.
    target_dir = tmp_path / "agenteval"
    target_dir.mkdir(parents=True, exist_ok=True)
    bad_jsonl = target_dir / "trace__S__S.jsonl_fail.jsonl"
    bad_jsonl.mkdir()  # `Path.mkdir` on a path where a directory of the
    # same name should be a file → JSONL write will OSError.
    # Generate a span so JSONL flush has something to write.
    from AgentEval.telemetry import spans

    with spans.invoke_agent_span("A"):
        pass
    # Trigger the flush via end_test. JSONLBackend.flush_test raises +
    # records the structured warning before returning; the listener
    # proceeds with manifest emit (which succeeds because target_dir
    # already exists as a directory) + clear_warnings.
    listener.end_test(test, None)
    # AC-5.4.4: the manifest sidecar captured the structured record
    # BEFORE the clear_warnings call. Read it back.
    expected_manifest = target_dir / "manifest__S__S.jsonl_fail.json"
    assert expected_manifest.exists(), "manifest sidecar must emit even when JSONL fails"
    payload = json.loads(expected_manifest.read_text(encoding="utf-8"))
    records = payload.get("warnings", [])
    # At least one warning must be present + identify the JSONL source.
    sources = {r.get("source") for r in records}
    assert "telemetry.backends.jsonl" in sources, (
        f"HIGH-G regression: expected JSONL write-failure record with "
        f"source='telemetry.backends.jsonl'; got sources={sources}"
    )
    # AC-5.3.2: post-end_test, the buffer is cleared.
    assert TelemetryLibrary().get_last_warnings("S.jsonl_fail") == []


def test_e2e_runmanifest_warnings_field_populated_with_warning_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RunManifest sidecar `warnings` field is list[dict] with 5-key shape."""
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.manifest_warnings", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Inject a structured warning into the per-test buffer directly.
    _agenteval_warnings.record_warning(
        warning_type="AgentEval.errors.DegradedTraceWarning",
        message="injected for manifest test",
        source="test_fixture",
        remediation="none",
    )
    listener.end_test(test, None)
    expected_path = tmp_path / "agenteval" / "manifest__S__S.manifest_warnings.json"
    assert expected_path.exists()
    payload = json.loads(expected_path.read_text(encoding="utf-8"))
    warnings_list = payload.get("warnings", [])
    assert len(warnings_list) == 1
    record = warnings_list[0]
    assert set(record.keys()) == {"warning_type", "message", "source", "timestamp", "remediation"}
    assert record["message"] == "injected for manifest test"
    assert record["source"] == "test_fixture"


def test_e2e_per_test_buffer_keys_by_test_id_no_cross_pollution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Routing isolation: Test A's record + Test B's record live in their own
    buffers AND `Get Last Warnings test_id="<other>"` proves the keying.

    Story 5.4 code-review 3-way MED-pabot fix 2026-05-20 (Blind MED-H +
    Edge-cases MED-6 + Auditor MED-2) — pre-edit was tautological:
    after end_test_a cleared A's buffer, asserting B's empty buffer
    proved nothing (any bug merging A→B would still leave B empty
    because A had ALREADY been cleared). Now: bind BOTH tests
    independently before either end_test fires, and verify cross-key
    routing while both buffers have content.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    # Bind Test A + record into A's buffer (no Listener end_test yet).
    _kernel_context.set_current_test_id("S.A", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="a-only", source="s")
    # Bind Test B + record into B's buffer.
    _kernel_context.set_current_test_id("S.B", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="b-only", source="s")
    lib = TelemetryLibrary()
    # While Test B is bound, "current" returns ONLY B's record.
    b_current = lib.get_last_warnings("current")
    assert [r["message"] for r in b_current] == ["b-only"], (
        f"MED-pabot regression: current-test-id keying leaked; got {b_current}"
    )
    # Explicit lookups by test_id prove key-routing isolation.
    assert [r["message"] for r in lib.get_last_warnings("S.A")] == ["a-only"]
    assert [r["message"] for r in lib.get_last_warnings("S.B")] == ["b-only"]
    # "all" sees both records.
    all_msgs = [r["message"] for r in lib.get_last_warnings("all")]
    assert set(all_msgs) == {"a-only", "b-only"}


def test_e2e_get_last_warnings_test_id_all_merges_across_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`test_id="all"` returns the union of per-test buffers sorted by timestamp."""
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    # Skip Listener; exercise the keyword directly under explicit context binds
    # so neither end_test fires (which would clear the buffers before "all").
    _kernel_context.set_current_test_id("S.A", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="a-first", source="s")
    _kernel_context.set_current_test_id("S.B", suite_id="S")
    _agenteval_warnings.record_warning(warning_type="X", message="b-second", source="s")
    out = TelemetryLibrary().get_last_warnings("all")
    assert len(out) == 2
    assert out[0]["message"] == "a-first"
    assert out[1]["message"] == "b-second"
    assert out[0]["timestamp"] <= out[1]["timestamp"]


def test_e2e_pre_test_buffer_merges_into_first_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Suite-level warnings merge into the first test's buffer via start_test flush."""
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    listener.start_suite(suite, None)
    # At this point no test is bound; emit a warning that lands in the sentinel.
    assert _kernel_context.current_context() is None
    _agenteval_warnings.record_warning(warning_type="X", message="suite-bootstrap", source="discovery")
    # First start_test must flush the sentinel.
    test = _MockData(full_name="S.first", parent=suite)
    listener.start_test(test, None)
    out = TelemetryLibrary().get_last_warnings("current")
    assert len(out) == 1
    assert out[0]["message"] == "suite-bootstrap"
    listener.end_test(test, None)


def test_e2e_span_less_test_with_warning_emits_minimal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 5.4 code-review 1-way Edge-cases HIGH-4 regression: a test that
    records a `DegradedTraceWarning` but produces ZERO spans must still
    emit a minimal manifest sidecar carrying the warnings — pre-fix the
    no-spans branch returned early before warning serialization.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.no_spans_but_warning", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    # Record a warning WITHOUT generating any spans.
    _agenteval_warnings.record_warning(
        warning_type="AgentEval.errors.DegradedTraceWarning",
        message="config-only test with no spans",
        source="test_fixture",
    )
    listener.end_test(test, None)
    # HIGH-4: minimal manifest sidecar present + carries the warning.
    expected = tmp_path / "agenteval" / "manifest__S__S.no_spans_but_warning.json"
    assert expected.exists(), (
        "HIGH-4 regression: minimal manifest sidecar MUST emit when warnings exist even if no spans were recorded"
    )
    payload = json.loads(expected.read_text(encoding="utf-8"))
    assert len(payload["warnings"]) == 1
    assert payload["warnings"][0]["message"] == "config-only test with no spans"


def test_e2e_warnings_buffer_cleared_at_end_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`clear_warnings(test_id)` fires in end_test after manifest emit."""
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.cleared", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    _agenteval_warnings.record_warning(warning_type="X", message="visible-pre-end", source="s")
    # Visible before end_test.
    pre = _agenteval_warnings.get_warnings("S.cleared")
    assert len(pre) == 1
    listener.end_test(test, None)
    # Cleared after end_test — buffer is empty.
    post = _agenteval_warnings.get_warnings("S.cleared")
    assert post == []
    # But the manifest sidecar persisted the record.
    expected_path = tmp_path / "agenteval" / "manifest__S__S.cleared.json"
    assert expected_path.exists()
    payload = json.loads(expected_path.read_text(encoding="utf-8"))
    assert len(payload["warnings"]) == 1
    assert payload["warnings"][0]["message"] == "visible-pre-end"
