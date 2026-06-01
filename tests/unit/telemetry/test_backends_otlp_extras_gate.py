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

"""ImportError-gate tests for the Phase-2 `[otlp]` extra (Story 13.2 L-2 lesson).

Mirrors `tests/unit/stats/test_advanced_extras_gate.py` discipline (Story 13.1
HIGH-B fix): this file deliberately has NO module-top `pytest.importorskip`
so the gate-coverage tests run in BOTH the WITH-extras and WITHOUT-extras CI
environments.

Per AC-13.2.7 + Story 13.1 cross-story upstream lesson L-2: the WITHOUT-extras
CI matrix MUST verify (a) `OTLPBackend` is importable without the extra (class
is referenced at module load time); (b) construction raises ImportError with
the verbatim `[otlp]` extra message; (c) `_resolve_backend` graceful-degrades
to MemoryBackend when construction fails.
"""

from __future__ import annotations

import warnings

import pytest

from AgentEval.errors import DegradedTraceWarning


def test_backends_module_importable_without_otlp_extra() -> None:
    """`from AgentEval.telemetry.backends import OTLPBackend` succeeds even WITHOUT the extra.

    The class is referenced at module load; only construction raises. This
    is what makes the Listener's `_resolve_backend` branch testable in
    the base CI environment.
    """
    from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend, OTLPBackend  # noqa: F401

    # All three class references must resolve.
    assert MemoryBackend.name == "memory"
    assert JSONLBackend.name == "jsonl"
    assert OTLPBackend.name == "otlp"


def test_raise_otlp_extra_missing_helper_carries_canonical_message() -> None:
    """`_raise_otlp_extra_missing` produces the spec-mandated ImportError text.

    Per Story 13.2 D-5 + AC-13.2.1: the message MUST recommend
    `uv pip install robotframework-agenteval[otlp]` verbatim so the
    operator's `[otlp]` install hint is grep-discoverable in the trace.
    """
    from AgentEval.telemetry.backends import _raise_otlp_extra_missing

    with pytest.raises(ImportError) as exc_info:
        _raise_otlp_extra_missing()
    msg = str(exc_info.value)
    assert "OTLPBackend" in msg
    assert "opentelemetry-exporter-otlp" in msg
    assert "uv pip install robotframework-agenteval[otlp]" in msg


def test_otlp_backend_raises_import_error_when_extra_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`OTLPBackend(endpoint=...)` raises ImportError when `_OTLP_AVAILABLE = False`.

    Monkeypatches the module-level gate directly (vs reloading the module
    with the OTLP exporter modules stubbed out) per Story 13.1 review
    HIGH-B + dev experience: module reload across tests pollutes
    `sys.modules` and leaves stats.library + telemetry.backends in a
    partial-import state. The gate check is the load-bearing branch;
    this verifies it triggers for OTLPBackend.
    """
    from AgentEval.telemetry import backends as backends_mod

    monkeypatch.setattr(backends_mod, "_OTLP_AVAILABLE", False)
    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
        backends_mod.OTLPBackend(endpoint="http://localhost:4318/v1/traces")
    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
        # Default endpoint also raises (gate sits BEFORE endpoint dispatch).
        backends_mod.OTLPBackend()


def test_attach_otlp_exporter_detaches_when_backend_switches_to_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listener detaches the OTLP processor when `trace_backend` switches to `memory` (Codex HIGH-1).

    Per Story 13.2 code-review Codex HIGH-1 + PRD NFR-SEC-05: once an
    operator switches `trace_backend` from `otlp` back to `memory` /
    `jsonl`, OTLP egress MUST stop. Pre-fix the sentinel-once-attach
    pattern left a live BatchSpanProcessor on the provider, so memory-
    backend runs continued to ship spans to the previous OTLP endpoint.
    """
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider

    from AgentEval.telemetry import listener as listener_mod
    from AgentEval.telemetry.backends import MemoryBackend, OTLPBackend

    # Force a fresh TracerProvider (the global may carry sentinels from
    # other tests in this session).
    provider = TracerProvider()
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: provider)
    listener = listener_mod.Listener()
    listener._backend = OTLPBackend(endpoint="http://localhost:4318/v1/traces")
    listener._attach_otlp_exporter_if_needed()
    assert getattr(provider, "_agenteval_otlp_processor", None) is not None
    # Switch to memory backend + re-attach.
    listener._backend = MemoryBackend()
    listener._attach_otlp_exporter_if_needed()
    assert getattr(provider, "_agenteval_otlp_processor", None) is None
    assert getattr(provider, "_agenteval_otlp_endpoint", None) is None


def test_attach_otlp_exporter_replaces_processor_when_endpoint_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listener replaces the OTLP processor when `otlp_endpoint` changes (Codex HIGH-2).

    Per Story 13.2 code-review Codex HIGH-2: pre-fix the sentinel was
    keyed on "OTLP attached" only — a second Listener in the same
    process with a different `AGENTEVAL_OTLP_ENDPOINT` left spans
    exporting to the FIRST endpoint. Now the sentinel tracks the
    endpoint URL so endpoint changes correctly swap exporters.
    """
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider

    from AgentEval.telemetry import listener as listener_mod
    from AgentEval.telemetry.backends import OTLPBackend

    provider = TracerProvider()
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: provider)
    listener = listener_mod.Listener()
    listener._backend = OTLPBackend(endpoint="http://first.example:4318/v1/traces")
    listener._attach_otlp_exporter_if_needed()
    first_processor = provider._agenteval_otlp_processor  # type: ignore[attr-defined]
    assert provider._agenteval_otlp_endpoint == "http://first.example:4318/v1/traces"  # type: ignore[attr-defined]
    # Swap to a different endpoint.
    listener._backend = OTLPBackend(endpoint="http://second.example:4318/v1/traces")
    listener._attach_otlp_exporter_if_needed()
    second_processor = provider._agenteval_otlp_processor  # type: ignore[attr-defined]
    assert second_processor is not first_processor
    assert provider._agenteval_otlp_endpoint == "http://second.example:4318/v1/traces"  # type: ignore[attr-defined]


def test_attach_otlp_exporter_is_idempotent_for_same_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeat attach with the same OTLP endpoint is a no-op (no duplicate processor)."""
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider

    from AgentEval.telemetry import listener as listener_mod
    from AgentEval.telemetry.backends import OTLPBackend

    provider = TracerProvider()
    monkeypatch.setattr(otel_trace, "get_tracer_provider", lambda: provider)
    listener = listener_mod.Listener()
    listener._backend = OTLPBackend(endpoint="http://localhost:4318/v1/traces")
    listener._attach_otlp_exporter_if_needed()
    first_processor = provider._agenteval_otlp_processor  # type: ignore[attr-defined]
    # Same endpoint → no-op.
    listener._attach_otlp_exporter_if_needed()
    second_processor = provider._agenteval_otlp_processor  # type: ignore[attr-defined]
    assert second_processor is first_processor


def test_resolve_backend_falls_back_with_warning_when_otlp_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listener `_resolve_backend` graceful-degrades to MemoryBackend when OTLP is unavailable.

    Per AC-13.2.7 (4th extras-gate test): with `trace_backend="otlp"` +
    `_OTLP_AVAILABLE=False`, the Listener catches the ImportError + emits
    DegradedTraceWarning + falls back to MemoryBackend rather than aborting
    the test run. Mirrors Story 5.1's unknown-trace_backend safety posture.
    """
    from AgentEval.telemetry import backends as backends_mod
    from AgentEval.telemetry import listener as listener_mod
    from AgentEval.telemetry.backends import MemoryBackend

    monkeypatch.setattr(backends_mod, "_OTLP_AVAILABLE", False)
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "otlp")
    monkeypatch.setenv("AGENTEVAL_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")

    listener = listener_mod.Listener()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        listener._resolve_backend(suite=None)  # type: ignore[arg-type]

    # Backend graceful-degrades to MemoryBackend rather than aborting.
    assert isinstance(listener._backend, MemoryBackend)
    # DegradedTraceWarning fired with the install hint.
    degraded = [w for w in captured if issubclass(w.category, DegradedTraceWarning)]
    assert len(degraded) >= 1
    assert any("otlp" in str(w.message).lower() for w in degraded)
    assert any("uv pip install robotframework-agenteval[otlp]" in str(w.message) for w in degraded)
