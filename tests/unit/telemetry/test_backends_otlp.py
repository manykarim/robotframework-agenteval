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

"""Unit tests for `OTLPBackend` happy paths + URL-scheme dispatch (Story 13.2).

Math + reference comparison N/A here (export-side; integration test covers
the wire format). These tests verify construction-time behavior:
- Default + explicit endpoint resolution.
- URL-scheme dispatch (http / https / grpc / grpcs).
- ValueError on unknown scheme + empty endpoint.
- `flush_test` is a no-op.
- Class invariants (`name` attr, docstring contains expected anchors).

ImportError-gate tests live in the companion `test_backends_otlp_extras_gate.py`
file per Story 13.1 L-2 lesson (no top-level `importorskip` so they run in
both WITH-extras and WITHOUT-extras CI environments).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Phase-2 modules require opentelemetry-exporter-otlp. Skip the happy-path
# tests when the extra is not installed (ImportError-gate tests run separately).
pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc")

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: E402
    OTLPSpanExporter as _GrpcExp,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E402
    OTLPSpanExporter as _HttpExp,
)

from AgentEval.telemetry.backends import (  # noqa: E402
    _OTLP_DEFAULT_ENDPOINT_HTTP,
    JSONLBackend,
    MemoryBackend,
    OTLPBackend,
)

# --------------------------------------------------------------------------- #
# Class invariants (2 tests)                                                  #
# --------------------------------------------------------------------------- #


def test_otlp_backend_name_is_otlp() -> None:
    """OTLPBackend.name == 'otlp' (symmetric with MemoryBackend / JSONLBackend)."""
    assert OTLPBackend.name == "otlp"


def test_otlp_backend_docstring_carries_anchors() -> None:
    """Docstring contains Browser-Library-convention anchors (Story 13.1 L-5 lesson).

    Story 13.1 review found that docstrings claiming behavior must
    namedrop the responsible mechanism precisely. OTLPBackend docstring
    must mention `BatchSpanProcessor` + `Phase-2` + `FR33b` so the
    contract is grep-discoverable.
    """
    doc = OTLPBackend.__doc__ or ""
    assert "BatchSpanProcessor" in doc
    assert "Phase-2" in doc
    assert "FR33b" in doc


# --------------------------------------------------------------------------- #
# Default endpoint + explicit endpoint construction (3 tests)                 #
# --------------------------------------------------------------------------- #


def test_otlp_backend_default_endpoint_is_local_http_jaeger() -> None:
    """endpoint=None → http://localhost:4318/v1/traces (HTTP exporter)."""
    backend = OTLPBackend()
    assert backend._endpoint == _OTLP_DEFAULT_ENDPOINT_HTTP
    assert backend._transport == "http"
    assert isinstance(backend._exporter, _HttpExp)


def test_otlp_backend_explicit_http_endpoint_constructs_http_exporter() -> None:
    """Explicit http:// URL → HTTP exporter at that URL."""
    backend = OTLPBackend(endpoint="http://collector.example.com:4318/v1/traces")
    assert backend._endpoint == "http://collector.example.com:4318/v1/traces"
    assert backend._transport == "http"
    assert isinstance(backend._exporter, _HttpExp)


def test_otlp_backend_explicit_https_endpoint_constructs_http_exporter() -> None:
    """Explicit https:// URL → HTTP exporter (TLS handled by OpenTelemetry SDK)."""
    backend = OTLPBackend(endpoint="https://api.honeycomb.io/v1/traces")
    assert backend._endpoint == "https://api.honeycomb.io/v1/traces"
    assert backend._transport == "http"
    assert isinstance(backend._exporter, _HttpExp)


# --------------------------------------------------------------------------- #
# gRPC scheme dispatch (3 tests)                                              #
# --------------------------------------------------------------------------- #


def test_otlp_backend_grpc_scheme_constructs_grpc_exporter_insecure() -> None:
    """grpc:// → gRPC exporter with insecure=True + stripped scheme.

    Per Story 13.2 code-review 2-way MED (Sonnet MED-1 + Opus MED-1):
    verify the load-bearing `insecure` flag value + endpoint stripping
    via mock interception, NOT just `isinstance` (which a True/False
    swap would silently pass).
    """
    with patch("AgentEval.telemetry.backends._OTLPSpanExporterGRPC", wraps=_GrpcExp) as mock_grpc:
        backend = OTLPBackend(endpoint="grpc://localhost:4317")
    assert backend._endpoint == "grpc://localhost:4317"  # full URL preserved as input
    assert backend._transport == "grpc"
    assert isinstance(backend._exporter, _GrpcExp)
    # The gRPC SDK was called with stripped `host:port` + insecure=True.
    mock_grpc.assert_called_once_with(endpoint="localhost:4317", insecure=True)


def test_otlp_backend_grpcs_scheme_constructs_grpc_exporter_secure() -> None:
    """grpcs:// → gRPC exporter with insecure=False (TLS) + stripped scheme.

    Per Story 13.2 code-review 2-way MED: explicitly verify
    `insecure=False` value (TLS opt-in) via mock interception.
    """
    with patch("AgentEval.telemetry.backends._OTLPSpanExporterGRPC", wraps=_GrpcExp) as mock_grpc:
        backend = OTLPBackend(endpoint="grpcs://otel.example.com:4317")
    assert backend._endpoint == "grpcs://otel.example.com:4317"
    assert backend._transport == "grpc"
    assert isinstance(backend._exporter, _GrpcExp)
    # The gRPC SDK was called with stripped `host:port` + insecure=False (TLS).
    mock_grpc.assert_called_once_with(endpoint="otel.example.com:4317", insecure=False)


def test_otlp_backend_grpc_scheme_is_case_insensitive() -> None:
    """Mixed-case GRPC:// resolves the same as lowercase grpc:// (insecure=True)."""
    with patch("AgentEval.telemetry.backends._OTLPSpanExporterGRPC", wraps=_GrpcExp) as mock_grpc:
        backend = OTLPBackend(endpoint="GRPC://localhost:4317")
    assert backend._transport == "grpc"
    assert isinstance(backend._exporter, _GrpcExp)
    # Scheme-stripping is from the lowercased prefix-length but preserves
    # original-case host (lowercase here so this just verifies the call).
    mock_grpc.assert_called_once_with(endpoint="localhost:4317", insecure=True)


# --------------------------------------------------------------------------- #
# Endpoint rejection (3 tests)                                                #
# --------------------------------------------------------------------------- #


def test_otlp_backend_rejects_unknown_scheme_with_value_error() -> None:
    """ftp:// (or any other non-OTLP scheme) raises ValueError listing valid schemes."""
    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
        OTLPBackend(endpoint="ftp://collector.example.com:21")
    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
        OTLPBackend(endpoint="ws://collector.example.com:4318")


def test_otlp_backend_rejects_empty_string_endpoint_with_value_error() -> None:
    """endpoint='' raises ValueError (ambiguous fallback to OTel SDK env default rejected)."""
    with pytest.raises(ValueError, match="must not be empty"):
        OTLPBackend(endpoint="")


def test_otlp_backend_rejects_no_scheme_endpoint_with_value_error() -> None:
    """A bare host:port without `://` raises ValueError listing valid schemes."""
    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
        OTLPBackend(endpoint="localhost:4318")


# --------------------------------------------------------------------------- #
# flush_test is a no-op (1 test)                                              #
# --------------------------------------------------------------------------- #


def test_otlp_backend_flush_test_is_noop_and_does_not_export(tmp_path: Path) -> None:
    """flush_test does NOT call exporter.export + returns None + writes no files.

    Per Story 13.2 D-7: OTLP export is event-driven (BatchSpanProcessor at
    TracerProvider config time), NOT flush-driven. flush_test exists for
    API uniformity with MemoryBackend / JSONLBackend but does no work.
    """
    backend = OTLPBackend(endpoint="http://localhost:4318/v1/traces")
    with patch.object(backend._exporter, "export") as mock_export:
        result = backend.flush_test(test_id="suite.test_one", suite_id="suite", output_dir=tmp_path)
    assert result is None
    assert mock_export.call_count == 0
    # No files written under the output dir.
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# Co-existence with MemoryBackend / JSONLBackend (1 test)                     #
# --------------------------------------------------------------------------- #


def test_otlp_backend_is_distinct_class_from_memory_and_jsonl_backends() -> None:
    """OTLPBackend is a sibling class, not a subclass — verifies the union-type ABI."""
    backend = OTLPBackend()
    assert not isinstance(backend, MemoryBackend)
    assert not isinstance(backend, JSONLBackend)
    # All three have `name` + `flush_test` (duck-typed Backend ABI).
    assert hasattr(backend, "name")
    assert hasattr(backend, "flush_test")
