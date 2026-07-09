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

"""Helpers for the OTLP collector docker integration test (Story 13.2 AC-13.2.8).

`_docker_available` + minimal OTel collector config builder + thin context
manager wrapping `docker run otel/opentelemetry-collector-contrib:latest`.

Per Story 13.2 D-8: docker-gated. Routine `ci.yml` skips when docker is
unavailable; `dogfood-integration.yml` (or a manual local dev run) provisions
docker and exercises the round-trip.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _docker_available() -> bool:
    """Return True iff docker is on PATH, the daemon responds, AND `/tmp` bind-mounts work.

    Tests build on this gate via `pytest.mark.skipif(not _docker_available(),
    reason=...)` per Story 13.2 D-8.

    Snap-confined docker (`/snap/bin/docker`) silently rejects bind mounts
    from paths outside the snap's confinement (typically `/tmp` is one of
    them). The OTLP integration tests use `pytest`'s `tmp_path` fixture
    (rooted at `/tmp/pytest-of-USER/...`) for the collector config + output
    file, so snap docker fails the round-trip. We probe this case
    explicitly so the routine `ci.yml` skip path covers both
    "docker missing" + "snap-confined docker can't mount /tmp."
    """
    # Honor an explicit opt-out — useful when docker is installed but the
    # daemon isn't running OR when CI infra wants to suppress the test.
    if os.environ.get("AGENTEVAL_DISABLE_DOCKER_TESTS", "").lower() in ("1", "true", "yes"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    # Probe a /tmp bind mount with a hello-world container. Snap-confined
    # docker returns non-zero here even though `docker info` succeeded.
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fp:
            fp.write("agenteval-docker-mount-probe")
            probe_path = fp.name
        try:
            probe = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{probe_path}:/probe.txt:ro",
                    "alpine:3",
                    "cat",
                    "/probe.txt",
                ],
                check=False,
                capture_output=True,
                timeout=30,
            )
        finally:
            Path(probe_path).unlink(missing_ok=True)
        return probe.returncode == 0 and b"agenteval-docker-mount-probe" in probe.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def minimal_otel_config(output_file: Path) -> str:
    """Build a minimal OTel collector config that receives OTLP + writes to a file.

    The collector accepts BOTH HTTP (port 4318) and gRPC (port 4317) on
    OTLP receivers + writes spans to `output_file` in OTLP JSON format
    via the `file` exporter (contrib distribution only).
    """
    return """receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  file:
    path: /etc/otelcol-contrib/spans.json
    rotation:

processors:
  batch:
    timeout: 100ms
    send_batch_size: 1

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [file]
"""


@contextmanager
def docker_collector(
    config: Path,
    output_file: Path,
    http_port: int = 4318,
    grpc_port: int = 4317,
    image: str = "otel/opentelemetry-collector-contrib:latest",
    start_timeout_seconds: float = 30.0,
) -> Iterator[dict[str, int]]:
    """Spin up the OTel collector in docker; yield bound ports; teardown on exit.

    Args:
        config: Path to the collector YAML config (mounted read-only).
        output_file: Path the collector writes spans to (mounted read-write).
        http_port: Host port mapped to container's OTLP/HTTP listener (4318).
        grpc_port: Host port mapped to container's OTLP/gRPC listener (4317).
        image: Docker image; defaults to `otel/opentelemetry-collector-contrib:latest`.
        start_timeout_seconds: How long to wait for the collector to become
            reachable on the HTTP port before raising.

    Yields:
        Dict with the bound `http_port` + `grpc_port`.
    """
    container_name = f"agenteval-otelcol-{uuid.uuid4().hex[:8]}"
    # Create the output file empty so docker doesn't mount it as a
    # directory by accident.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("")
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "--rm",
                "-p",
                f"{http_port}:4318",
                "-p",
                f"{grpc_port}:4317",
                "-v",
                f"{config}:/etc/otelcol-contrib/config.yaml:ro",
                "-v",
                f"{output_file}:/etc/otelcol-contrib/spans.json",
                image,
                "--config=/etc/otelcol-contrib/config.yaml",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        # Poll until the OTLP HTTP receiver responds (POST with empty body
        # returns 400 once the receiver is up; connection refusal means
        # still starting).
        deadline = time.time() + start_timeout_seconds
        ready = False
        while time.time() < deadline:
            try:
                check = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "wget",
                        "-q",
                        "--spider",
                        "--timeout=1",
                        "http://127.0.0.1:4318/v1/traces",
                    ],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                check = None
            # wget --spider returns 0 on 200, 8 on HTTP error (e.g. 400 for
            # empty GET). Either is fine — the receiver is up.
            if check is not None and check.returncode in (0, 8):
                ready = True
                break
            time.sleep(0.5)
        if not ready:
            # Give it one more half-second + proceed anyway; the export
            # batch will retry. Collect container logs for diagnostics.
            logs = subprocess.run(
                ["docker", "logs", container_name],
                check=False,
                capture_output=True,
                timeout=5,
            )
            print("[docker_collector] startup probe inconclusive; container logs:")
            print(logs.stdout.decode(errors="replace"))
            print(logs.stderr.decode(errors="replace"))
        yield {"http_port": http_port, "grpc_port": grpc_port}
    finally:
        subprocess.run(
            ["docker", "stop", container_name],
            check=False,
            capture_output=True,
            timeout=20,
        )


def read_collector_spans(output_file: Path) -> list[dict]:
    """Parse the OTel collector's file-exporter output into Python dicts.

    The file exporter writes one OTLP-shaped JSON document per export batch
    (each line is an OTLP `ExportTraceServiceRequest` envelope). We flatten
    the `resourceSpans → scopeSpans → spans` nested structure into a flat
    list of span dicts with a `resource` + `scope` annotation per span.
    """
    if not output_file.exists():
        return []
    spans: list[dict] = []
    for line in output_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            batch = json.loads(line)
        except json.JSONDecodeError:
            continue
        for resource_span in batch.get("resourceSpans", []):
            resource = resource_span.get("resource", {})
            for scope_span in resource_span.get("scopeSpans", []):
                scope = scope_span.get("scope", {})
                for span in scope_span.get("spans", []):
                    spans.append(
                        {
                            **span,
                            "resource": resource,
                            "scope": scope,
                        }
                    )
    return spans
