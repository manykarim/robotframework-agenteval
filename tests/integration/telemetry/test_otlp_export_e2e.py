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

"""End-to-end OTLP round-trip via a local OTel collector docker container (Story 13.2 AC-13.2.8).

Per Story 13.2 D-8 + L-4 lessons (Story 13.1 Codex HIGH-4 empirical-probe
lesson): the wire format is verified by reading the collector's output file
+ asserting span content, NOT just "the exporter was called." Gated by
`_docker_available()` so routine CI skips when docker is unavailable.

Set `AGENTEVAL_DISABLE_DOCKER_TESTS=1` to suppress these tests even on
docker-available hosts (useful when iterating without the slow image-pull
+ container-startup overhead).

Tests use the `agenteval-advanced`-free public API surface:
1. Spin up `otel/opentelemetry-collector-contrib` listening on OTLP HTTP + gRPC.
2. Configure `AgentEval` Library with `trace_backend=otlp` + the collector
   endpoint.
3. Emit a span via the Listener-attached TracerProvider.
4. Read back the collector's output file + assert span content.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

# Phase-2 deps required.
pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc")

from ._otlp_helpers import (  # noqa: E402
    _docker_available,
    docker_collector,
    minimal_otel_config,
    read_collector_spans,
)

# Mark the whole module as docker-gated. The skipif fires once at collection.
pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="docker not available (or AGENTEVAL_DISABLE_DOCKER_TESTS=1)",
)


def _emit_test_span_via_listener(endpoint: str, span_name: str = "agenteval_e2e_test_span") -> None:
    """Emit one span via the AgentEval Listener's TracerProvider + force-flush.

    Uses the Listener's `_attach_otlp_exporter_if_needed` path so the
    BatchSpanProcessor(OTLPSpanExporter) is wired identically to a
    real RF run. The span is emitted via the OpenTelemetry API directly
    (the Listener's TracerProvider is the active provider).
    """
    import os

    from opentelemetry import trace

    from AgentEval.telemetry import listener as listener_mod

    os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"
    os.environ["AGENTEVAL_OTLP_ENDPOINT"] = endpoint

    listener = listener_mod.Listener()
    # Mimic start_suite: configure tracer provider + resolve backend +
    # attach OTLP exporter.
    listener._configure_tracer_provider()
    listener._resolve_backend(suite=None)
    listener._attach_otlp_exporter_if_needed()

    tracer = trace.get_tracer("agenteval.e2e_test")
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("agenteval.tier", 2)
        span.set_attribute("gen_ai.request.model", "test-model")

    # Force-flush via the active TracerProvider so the BatchSpanProcessor
    # ships the span before the docker container teardown.
    trace.get_tracer_provider().force_flush(timeout_millis=5000)  # type: ignore[union-attr]


def test_otlp_http_export_round_trip_against_collector(tmp_path: Path) -> None:
    """Span emitted via OTLP HTTP lands in the collector's file output.

    Per Story 13.2 L-4 (Codex empirical-probe lesson): verify the wire
    format by reading collector output, NOT just call_count.
    """
    config_file = tmp_path / "otel-config.yaml"
    output_file = tmp_path / "spans.json"
    config_file.write_text(minimal_otel_config(output_file))
    # Random high ports to avoid colliding with local OTel collectors.
    http_port = 24318
    grpc_port = 24317

    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
        _emit_test_span_via_listener(
            endpoint=f"http://localhost:{http_port}/v1/traces",
            span_name="agenteval_e2e_http_span",
        )
        # The collector batches at 100ms; give it a beat to flush the file.
        time.sleep(1.5)

    spans = read_collector_spans(output_file)
    _assert_agenteval_span_content(spans, expected_name="agenteval_e2e_http_span")


def test_otlp_grpc_export_round_trip_against_collector(tmp_path: Path) -> None:
    """Span emitted via OTLP gRPC lands in the collector with the full contract payload.

    Verifies the gRPC scheme dispatch + insecure=True host:port stripping
    end-to-end + that the `service.name` resource attribute + the
    `agenteval.tier` span attribute flow through the gRPC transport
    identically to HTTP (Story 13.2 code-review HIGH-A + MED-1 + MED-3
    fix asymmetric-attribute-coverage).
    """
    config_file = tmp_path / "otel-config.yaml"
    output_file = tmp_path / "spans.json"
    config_file.write_text(minimal_otel_config(output_file))
    http_port = 24319
    grpc_port = 24320

    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
        _emit_test_span_via_listener(
            endpoint=f"grpc://localhost:{grpc_port}",
            span_name="agenteval_e2e_grpc_span",
        )
        time.sleep(1.5)

    spans = read_collector_spans(output_file)
    _assert_agenteval_span_content(spans, expected_name="agenteval_e2e_grpc_span")


def _assert_agenteval_span_content(spans: list[dict], expected_name: str) -> None:
    """Assert OTLP-roundtripped span carries the Story 13.2 contract payload.

    Per Story 13.2 code-review fixes:
    - HIGH-A (3-way Opus + Codex + carry-over claim drift): assert
      `service.name="robotframework-agenteval"` flows through the OTLP
      Resource. Pre-fix the Listener's empty `Resource.create({})` left
      the default `unknown_service` and this assertion would have caught
      the discrepancy.
    - MED-1 (Codex + Opus): assert specific span content (name + the
      load-bearing `agenteval.tier` attribute) — NOT just `len(spans) > 0`
      which would pass for any garbage span the collector received.
    - MED-3 (Sonnet asymmetric): applies BOTH HTTP + gRPC tests
      identically.
    """
    assert len(spans) >= 1, "no spans in collector output"
    matching = [s for s in spans if s.get("name") == expected_name]
    assert matching, f"expected span name {expected_name!r}, got names: {[s.get('name') for s in spans]!r}"
    # service.name resource attribute (post-HIGH-A fix).
    for span in matching:
        resource_attrs = span.get("resource", {}).get("attributes", [])
        service_name_attrs = [
            a.get("value", {}).get("stringValue") for a in resource_attrs if a.get("key") == "service.name"
        ]
        assert "robotframework-agenteval" in service_name_attrs, (
            f"expected service.name=robotframework-agenteval; got resource attrs: {resource_attrs!r}"
        )
    # agenteval.tier span attribute on EVERY matching span (not just
    # `any`-across-flat-attrs which would pass for arbitrary spans on
    # the collector — pre-Opus-MED-3 assertion shape).
    for span in matching:
        attrs = span.get("attributes", [])
        tier_keys = [a.get("key") for a in attrs if a.get("key") == "agenteval.tier"]
        assert tier_keys, f"expected agenteval.tier attribute on {span.get('name')!r}; got {attrs!r}"
