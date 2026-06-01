# Story 13.2: OTLP Trace Backend

Status: done

## Story

As an **observability-focused user** (Raj or Priya integrating with production observability stacks),
I want `trace_backend="otlp"` shipping OTel spans to an OTLP collector via the canonical OpenTelemetry SDK exporter,
So that AgentEval traces flow into Jaeger / Honeycomb / Tempo / Grafana for production observability — closing the PRD FR33b Phase-2 commitment and retiring the manual `otel-cli span replay` workaround documented in `docs/contracts/otel-trace-visual.md` L65-115.

## Pre-create-story drift check (52nd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)

10 drifts caught — 5 fresh decisions from spec analysis + 5 UPSTREAM lessons from Story 13.1 reviews (the immediately-prior same-epic story; `feedback_cross_story_upstream_lesson_propagation` N=5 confirmed at Epic 12 retro). **100% real-drift catch rate maintained through 51 prior uses.**

- **D-1 (HIGH — extras name drift PRD vs architecture vs ADR-001, 2-vs-1):** **2-source-vs-1 majority on the extras name.**
  - **PRD L1253 / architecture L673:** `[otlp]` extra (literally — `pip install robotframework-agenteval[otlp]`).
  - **ADR-001 catalog (no row exists yet)** — Story 13.2 ADDS one.
  - Story 13.1 set the **`agenteval-advanced`** precedent (longer, project-prefixed name). PRD uses `[otlp]` everywhere. There is NO contradiction here — these are different extras (`agenteval-advanced` for stats, `otlp` for the OTLP exporter dep). **Decision:** ship as `[otlp]` per PRD/architecture verbatim. Symmetric with the existing CLI-adapter extras pattern (`claude-code` / `codex` / `copilot` — unprefixed, short adapter-name verbatim). Apply Story 13.1 cross-story upstream lesson: validate the spec wording vs ADR-001 catalog ADD a new row (no drift to fix because no prior ADR-001 row exists).

- **D-2 (HIGH — `@tier(1)` FR31a contract for telemetry side-effects, UPSTREAM from Story 13.1 Opus HIGH-1):** OTLP export is a side-effecting network call. The trace_backend selection is a Listener-time concern, NOT a keyword surface — Story 5.1's Listener resolves the backend in `_resolve_backend()` and exports spans through the chosen SpanProcessor chain. There is NO `@keyword`-decorated method introduced by this story, so the @tier classification question is moot. **Decision:** Story 13.2 is a Listener-internal backend swap; the Story 13.1 lesson "Tier-1 with non-determinism violates FR31a" doesn't apply directly here because the backend selection itself doesn't run from within a keyword. Add a docstring note on `OTLPBackend.flush_test()` documenting "side-effecting; not idempotent (each call exports spans to the configured endpoint)."

- **D-3 (HIGH — OTLP backend file home + class shape per architecture L1258 + L673):** architecture L1258 pre-allocates `backends.py` for "memory / jsonl backends Phase 1; otlp dispatch Phase 2 per FR33b." L673 specifies the dispatch as `OTLPSpanExporter` swap. **Decision:** ship `OTLPBackend` class in the EXISTING `src/AgentEval/telemetry/backends.py` (do NOT create a new `otlp.py` module per Story 13.1 D-5 / cliffs_delta-style pattern — architecture pre-allocates `backends.py` as the single backend home; consistent with `MemoryBackend` + `JSONLBackend` siblings already shipped at this path). Module-level `try: import opentelemetry.exporter.otlp.proto.http / except ImportError: _OTLP_AVAILABLE = False` gate at `backends.py` top (mirrors Story 13.1's `_ADVANCED_AVAILABLE` discipline at `stats/library.py`).

- **D-4 (HIGH — exporter API: gRPC vs HTTP per epic AC L2171):** epic AC L2171 mandates BOTH `gRPC` (`otlp_endpoint="grpc://..."`) AND `HTTP` (`otlp_endpoint="http://..."`) protocol selection via URL scheme. The `opentelemetry-exporter-otlp` PyPI package ships TWO sub-packages:
  - `opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter` — HTTP/protobuf transport (port 4318).
  - `opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter` — gRPC transport (port 4317).
  Both classes share the same constructor `endpoint=` kwarg + the same `export(spans)` interface (both inherit `SpanExporter`). **Decision:** parse the URL scheme from `otlp_endpoint`:
  - `http://` / `https://` → instantiate the HTTP exporter.
  - `grpc://` / `grpcs://` → instantiate the gRPC exporter (stripping the `grpc://` prefix per gRPC SDK convention which expects bare `host:port`).
  - Default endpoint (when `otlp_endpoint` is unset) → `http://localhost:4318/v1/traces` per OpenTelemetry SDK convention.
  - Unknown scheme → raise `ValueError(f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme!r}")`.

- **D-5 (HIGH — `otlp_endpoint` config key + env var per Story 5.1 4-level precedence):** Story 5.1 `_resolve_backend()` reads `trace_backend` from `_kernel/context.resolve_config({})` which honors the FR41 4-level precedence chain (init_arg → env-var → `.env` → default). **Decision:** add `otlp_endpoint` to:
  - `_kernel/context.py:_FR42_DEFAULTS` — default `None` (caller must set OR use `http://localhost:4318/v1/traces` fallback in OTLPBackend).
  - `_kernel/context.py:_ENV_VAR_NAMES` — `AGENTEVAL_OTLP_ENDPOINT`.
  - `_kernel/context.py:_coerce_env_value` — string passthrough (URL).
  - `_kernel/context.py:_KNOWN_ENV_VAR_NAMES` — automatically extended by inclusion in `_ENV_VAR_NAMES`.
  - `AgentEval.__init__` signature: NEW `otlp_endpoint: str | None = _UNSET` kwarg + resolved-config plumbing (the 10th `__init__` parameter).
  - `_config_provenance` ConfigValue propagation.
  - `.env.example`: documented env-var with example values for HTTP + gRPC endpoints.

- **D-6 (MED — `_resolve_backend()` extension at `telemetry/listener.py:798-823`):** Story 5.1's `_resolve_backend()` has 3 branches: `"jsonl"` → JSONLBackend; `"memory"` → MemoryBackend; else → warn + fall back to memory. **Decision:** add a 4th branch: `"otlp"` → instantiate `OTLPBackend(endpoint=config.get("otlp_endpoint"))`. If `_OTLP_AVAILABLE = False` at import time, the OTLPBackend.__init__ raises `ImportError` with the verbatim message recommending `uv pip install robotframework-agenteval[otlp]` (mirrors Story 13.1 D-3 message contract). The "unknown trace_backend → fall back to memory" path's documented valid-values list updates from `{'memory', 'jsonl'}` to `{'memory', 'jsonl', 'otlp'}`.

- **D-7 (MED — `OTLPBackend` exporter wiring is at TracerProvider-config time, NOT flush_test):** Architecture L673 says "swaps `InMemorySpanExporter` for `OTLPSpanExporter`" — but Story 5.1's listener.py:284-298 wires `SimpleSpanProcessor(trace_store._get_exporter())` as the in-memory exporter chain AT TRACE-PROVIDER-CONFIG TIME, not per-test. For OTLP, the canonical pattern is `BatchSpanProcessor(OTLPSpanExporter)` for batched async export (the InMemorySpanExporter is process-resident; OTLP is network-bound).
  - **Decision:** when `trace_backend="otlp"`, the listener extends `_configure_tracer_provider()` to ALSO add a `BatchSpanProcessor(OTLPSpanExporter)` to the provider chain (in addition to the existing `SimpleSpanProcessor(InMemorySpanExporter)` for projection-accessor compatibility). This is a DUAL-EXPORT design: spans go to both the in-memory store (so existing `Metric.*` keywords still work) AND the OTLP endpoint (so traces flow to the observability backend).
  - `OTLPBackend.flush_test()` is then a no-op (export happens batched via the SpanProcessor chain). The `flush_test` API uniformity with MemoryBackend / JSONLBackend is preserved but the actual export is event-driven, not flush-driven.
  - Alternative considered + REJECTED: OTLP-only mode (no in-memory store). Would break every existing `Metric.*` keyword (Story 6.1, Story 5.2) since they read from the in-memory projection accessors. Backward-compat wins.

- **D-8 (MED — integration test docker harness + skip-when-no-collector):** epic AC L2169 mandates "integration test verifies round-trip against a local OTLP collector docker container." A test that REQUIRES docker to pass in CI is fragile. **Decision:** ship the integration test with a `@pytest.mark.skipif(not _docker_available(), reason="docker not available")` gate that checks for `docker` binary on PATH AND a running daemon (via `docker ps` smoke). Tests run in dev environments + the `dogfood-integration.yml` CI workflow which provisions docker; routine `ci.yml` skips the test (it'll appear in the skip count). Use the OTel collector's pre-built image `otel/opentelemetry-collector-contrib:latest` with a minimal config that accepts OTLP + writes to a local file the test can read back. Docker container teardown via pytest fixture (yield + finally cleanup) per existing dogfood-CI fixtures pattern.

- **D-9 (MED — Recipe Gallery #8 update per epic AC L2173):** epic AC L2173 mandates "Recipe Gallery #8 (CI integration) is updated with an OTLP integration example showing trace data flowing into a Honeycomb/Jaeger dashboard." **Decision:** ADD a new `## OTLP trace export (Phase 2 — `[otlp]` extra)` section to `docs/recipes/08-ci-integration.md` AFTER the existing `## trace_id linkage (FR51)` section (L95-110). The section ships TWO concrete invocation examples: (a) HTTP endpoint to local Jaeger; (b) gRPC endpoint to Grafana Tempo. Cross-link to `docs/contracts/otel-trace-visual.md` for the legacy `otel-cli span replay` JSONL-replay path (Phase-1 fallback). Per `feedback_executable_doc_precheck`: the new section's commands need NOT be `robot --dryrun`-able (they're shell commands not RF keywords) but the `Library    AgentEval    trace_backend=otlp    otlp_endpoint=...` snippet IS RF-syntax + MUST dryrun-clean per Story 12.3 precedent.

- **D-10 (LOW — carry-over catalog gate UPSTREAM Story 13.1 / 33rd consecutive):** Anticipated Phase-2 carry-overs for Story 13.2:
  - **DF-13.2-S1 (Phase-2.5):** OTLP exporter resource-attribute customization. PRD says `service.name = "robotframework-agenteval"` (per otel-trace-visual.md L78 + L104). Phase-2 may want per-suite `service.namespace` or per-run `service.instance.id` for multi-suite isolation.
  - **DF-13.2-S2 (Phase-2.5):** OTLP header-based auth + TLS cert customization. The exporter `headers=` and `credentials=` kwargs let operators add bearer tokens / mTLS. Phase-2 ships endpoint-only; auth via separate carry-over.
  - **DF-13.2-S3 (Phase-2.5):** OTLP exporter retry + circuit-breaker. The OpenTelemetry SDK's `OTLPSpanExporter` has built-in retry but no circuit-breaker for sustained collector outages. Phase-2.5 adds a circuit-breaker that falls back to JSONL after N consecutive failures.
  - Pre-emptive catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-05-27): catalogue C86 + C87 + C88 in both catalog files BEFORE invoking `/bmad-code-review` (Task N-1).

## Cross-story upstream lessons from Story 13.1 reviews

Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12 retro) — Story 13.1 is the immediately-prior same-epic story. 6 HIGH + 4 MED Story 13.1 review findings fold into Story 13.2 ACs UPSTREAM:

- **L-1 (from Story 13.1 HIGH-A 3-way):** stability-surface.md must register the NEW `OTLPBackend` + `[otlp]` extra surface entries — DO NOT ship to review until verified by `grep`.
- **L-2 (from Story 13.1 HIGH-B Codex empirical):** Tests gating on the OTLP-extra presence MUST be split — happy-path tests use `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`; ImportError-gate tests sit in a SEPARATE file with NO `importorskip` (run in both WITH and WITHOUT-extras CI envs). Story 13.1's `test_advanced_extras_gate.py` is the canonical pattern.
- **L-3 (from Story 13.1 HIGH-C Opus):** Verify the @tier classification of any newly-exposed keyword surface (none in this story, but document the rationale to head off Opus questions). Listener-internal backend swap doesn't expose a @tier-classified surface.
- **L-4 (from Story 13.1 HIGH-D Codex empirical):** When making a claim ("matches scipy default", "exports via OTLP HTTP protocol", etc.), include a test that EMPIRICALLY verifies the claim against a reference implementation. AC-13.2.6 includes an end-to-end integration test that captures the exported OTLP payload + verifies its content vs. the expected span shape — NOT just "the exporter was called."
- **L-5 (from Story 13.1 HIGH-E 3-way + MED-2 honesty):** Docstrings claiming "matches scipy default" / "exports per OTel spec" must be precise — if normalizing or transforming, say so explicitly. The OTLPBackend docstring states "exports spans via the canonical `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`" with the exact import path, no marketing-style claims.

## Acceptance Criteria

### AC-13.2.1 — `OTLPBackend` class in `telemetry/backends.py`

`src/AgentEval/telemetry/backends.py` extends with `OTLPBackend` class (architecture L1258 file home). Class shape mirrors `MemoryBackend` / `JSONLBackend` for API uniformity:

```python
class OTLPBackend:
    """OTLP trace backend (opt-in via ``trace_backend="otlp"``; Phase-2 FR33b).

    Exports spans via the canonical
    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based on
    the URL scheme of ``endpoint``. Requires the ``[otlp]`` optional extra
    (``opentelemetry-exporter-otlp``); raises ``ImportError`` on construction
    when the extra is missing.

    Export semantics: spans are routed via a ``BatchSpanProcessor`` attached
    to the TracerProvider (NOT via ``flush_test``). ``flush_test`` is a
    no-op here — included for API uniformity with ``MemoryBackend`` /
    ``JSONLBackend``.
    """

    name = "otlp"

    def __init__(self, endpoint: str | None = None) -> None: ...

    def flush_test(self, test_id: str, suite_id: str = "", output_dir: Path | None = None) -> None:
        """No-op. OTLP export is batched via the SpanProcessor chain at TracerProvider config time."""
```

Module-level `_OTLP_AVAILABLE = True/False` gate via `try: import opentelemetry.exporter.otlp.proto.http as _otlp_http; import opentelemetry.exporter.otlp.proto.grpc as _otlp_grpc` (BOTH transports probed at gate-time so the construction-time error is consistent regardless of which scheme the operator chose).

### AC-13.2.2 — URL-scheme dispatch for HTTP vs gRPC

`OTLPBackend.__init__(endpoint)`:
- Default endpoint (when `endpoint is None`): `"http://localhost:4318/v1/traces"` per OpenTelemetry SDK convention.
- `http://` / `https://` → instantiate `opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter(endpoint=endpoint)`.
- `grpc://` / `grpcs://` → strip the scheme prefix (extract `host:port`) → instantiate `opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter(endpoint=host_port, insecure=True/False)`. `grpc://` → `insecure=True`; `grpcs://` → `insecure=False` (TLS).
- Any other scheme → raise `ValueError(f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme!r}")`.
- Store the constructed exporter as `self._exporter` for the Listener to wire via `BatchSpanProcessor`.

### AC-13.2.3 — `_resolve_backend()` extends to `"otlp"` branch

`src/AgentEval/telemetry/listener.py:_resolve_backend()` adds a 4th branch:

```python
elif backend_name == "otlp":
    otlp_endpoint = config.get("otlp_endpoint")
    self._backend = OTLPBackend(endpoint=otlp_endpoint)
```

The unknown-backend fallback message updates from `"Valid values: {'memory', 'jsonl'}."` to `"Valid values: {'memory', 'jsonl', 'otlp'}."` (D-6 fix). The `DegradedTraceWarning` remediation text similarly updates.

### AC-13.2.4 — `_configure_tracer_provider()` dual-export wiring

`src/AgentEval/telemetry/listener.py:_configure_tracer_provider()` extends to add the OTLP BatchSpanProcessor when `self._backend` is `OTLPBackend`:

```python
# After the existing SimpleSpanProcessor(InMemorySpanExporter) line:
if isinstance(self._backend, OTLPBackend):
    provider.add_span_processor(
        BatchSpanProcessor(self._backend._exporter)
    )
```

**Order matters:** the existing chain is `TestIdContextSpanProcessor → RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter)`. The OTLP processor lands AFTER RedactionProcessor (redaction applies to OTLP-exported spans per NFR-SEC-01 + FR38a) and AFTER the InMemorySpanExporter (so projection accessors continue to receive un-redacted-from-their-perspective spans — RedactionProcessor mutates spans in-place on `on_end`, so order within the post-redaction tail does not affect content; only the BatchSpanProcessor vs SimpleSpanProcessor distinction matters for export timing).

The "process-scope sentinel" idempotency mechanism (Story 5.1 HIGH-A fix) applies: re-attaching to an existing provider must NOT duplicate the OTLP processor. The sentinel check + the `_tracer_configured` flag prevent stacking.

### AC-13.2.5 — `pyproject.toml` `[otlp]` optional extra

`pyproject.toml` `[project.optional-dependencies]` adds:

```toml
# Story 13.2 (Epic 13) — OTLP trace exporter (FR33b). Phase-2 backend
# behind the `[otlp]` extra: when `trace_backend="otlp"`, agenteval spans
# export to a configured OTLP collector (Jaeger / Honeycomb / Tempo /
# Grafana). The package `opentelemetry-exporter-otlp` is a metapackage
# pulling both HTTP/protobuf and gRPC transports; URL-scheme dispatch
# at OTLPBackend.__init__ time chooses between them. Pinned ranges
# match the existing `opentelemetry-api` / `opentelemetry-sdk` floors
# (>=1.27,<2.0 per architecture L1638 + Story 5.1 review fix).
otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]
```

`uv lock` + `uv sync` (base) succeeds without the OTLP exporter (no resolver impact). `uv sync --extra otlp` resolves cleanly + the exporter modules import.

### AC-13.2.6 — `otlp_endpoint` config wired through the 4-level precedence chain

`src/AgentEval/_kernel/context.py` extended at 4 sites:
1. `_FR42_DEFAULTS` adds `"otlp_endpoint": None`.
2. `_ENV_VAR_NAMES` adds `"otlp_endpoint": "AGENTEVAL_OTLP_ENDPOINT"`.
3. `_coerce_env_value` — URL is a string, passes through unchanged via the catch-all final branch (no new clause needed). Verify the existing comment `# provider, trace_backend — strings; pass through.` extends to cover `otlp_endpoint`.
4. `_KNOWN_ENV_VAR_NAMES` automatically updates via `_ENV_VAR_NAMES` inclusion.

`src/AgentEval/__init__.py` extended:
- `AgentEval.__init__` signature gains `otlp_endpoint: str | None = _UNSET` (10th kwarg, placed AFTER `max_runtime_seconds`).
- `kwarg_overrides` dict + `resolved["otlp_endpoint"]` extraction → `self._otlp_endpoint`.
- `_get_effective_config` dict output includes `otlp_endpoint`.
- Docstring updated with `otlp_endpoint` parameter description.

`.env.example` extended with:
```
# OTLP trace backend endpoint (Phase 2 — requires `[otlp]` extra).
# Examples:
#   AGENTEVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces       # local Jaeger HTTP
#   AGENTEVAL_OTLP_ENDPOINT=grpc://localhost:4317                 # local Tempo gRPC (insecure)
#   AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces    # Honeycomb HTTPS
# AGENTEVAL_OTLP_ENDPOINT=
```

### AC-13.2.7 — Unit tests at `tests/unit/telemetry/test_backends_otlp.py`

NEW file. ≥15 unit tests covering OTLPBackend construction + endpoint dispatch + ImportError gate. Math + reference comparison NOT applicable here (export-side; integration test covers the wire format).

Coverage:
- **Construction with extra (8 tests; gated by `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`):** default-endpoint construction → HTTP exporter at `http://localhost:4318/v1/traces`; explicit `http://...` → HTTP exporter at given URL; explicit `https://...` → HTTP exporter at given URL; `grpc://localhost:4317` → gRPC exporter with `insecure=True`; `grpcs://otel.example.com:4317` → gRPC exporter with `insecure=False` + stripped scheme; unknown scheme `ftp://...` → `ValueError` with "must use http://, https://, grpc://, or grpcs:// scheme"; explicit `None` endpoint → default HTTP local-Jaeger; explicit empty string `""` → `ValueError` (rejects empty URL).
- **`flush_test` is no-op (1 test):** invoking `flush_test(test_id, suite_id, output_dir)` returns None + writes no files + does NOT call any exporter method (mocked via `unittest.mock.patch` on the exporter `.export` method to assert call_count == 0).
- **Class name attribute (1 test):** `OTLPBackend.name == "otlp"` (symmetric with `MemoryBackend.name == "memory"` / `JSONLBackend.name == "jsonl"`).
- **Docstring assertions (1 test):** OTLPBackend docstring contains "BatchSpanProcessor" + "Phase-2" + "FR33b" — per `feedback_full_surface_retro_review` Browser-Library convention.

Plus 4 ImportError-gate tests at NEW `tests/unit/telemetry/test_backends_otlp_extras_gate.py` (split per Story 13.1 L-2 lesson; NO `importorskip` at module top so it runs in both base + WITH-extras envs):
- `test_otlp_backend_raises_import_error_without_extra` — monkeypatches `_OTLP_AVAILABLE = False` on `backends`, asserts `OTLPBackend(endpoint="http://...")` raises `ImportError("OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]")`.
- `test_raise_otlp_extra_missing_helper_carries_canonical_message` — direct helper exercise.
- `test_backends_importable_without_otlp_extra` — `from AgentEval.telemetry.backends import OTLPBackend, MemoryBackend, JSONLBackend` succeeds without the extra (the class is importable; construction is what raises).
- `test_resolve_backend_falls_back_with_warning_when_otlp_construction_fails` — Listener `_resolve_backend` integration: with `trace_backend="otlp"` + `_OTLP_AVAILABLE = False`, Listener catches the `ImportError` + emits `DegradedTraceWarning` + falls back to MemoryBackend (graceful degradation under partial install).

### AC-13.2.8 — Integration test against OTLP collector docker container

NEW file at `tests/integration/telemetry/test_otlp_export_e2e.py`. End-to-end round-trip:

```python
@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_otlp_http_export_round_trip_against_collector(tmp_path, docker_client):
    """Spans emitted to a local OTel collector container land in its output file."""
    collector_cfg = tmp_path / "otel-config.yaml"
    collector_cfg.write_text(_minimal_otel_config(output_file=tmp_path / "spans.json"))

    with docker_client.run_collector(config=collector_cfg, port=4318) as collector:
        os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"
        os.environ["AGENTEVAL_OTLP_ENDPOINT"] = f"http://localhost:{collector.port}/v1/traces"
        # Emit a span via the agenteval listener under an RF test fixture.
        result = run_rf_test_with_listener(test_body=_minimal_span_emit_test())
        assert result.passed
        collector.flush()  # force batch flush before reading output

    spans = _read_collector_output(tmp_path / "spans.json")
    assert len(spans) > 0
    assert any(s["name"] == "invoke_agent" for s in spans)
    assert all(s["resource"]["attributes"]["service.name"] == "robotframework-agenteval" for s in spans)
    # Verify agenteval-specific attributes flow through OTLP envelope.
    assert any("agenteval.tier" in s["attributes"] for s in spans)
```

Plus a gRPC variant: `test_otlp_grpc_export_round_trip_against_collector` using `grpc://localhost:4317` + the collector's gRPC receiver.

Test harness helpers (NEW; live in `tests/integration/telemetry/_otlp_helpers.py`):
- `_docker_available()` — returns False if `docker` binary missing OR `docker info` fails.
- `_minimal_otel_config(output_file)` — generates a minimal OTel collector config with `otlp` receivers (HTTP + gRPC) + `file` exporter writing to `output_file`.
- `DockerCollectorContext` context manager — `__enter__` pulls + starts `otel/opentelemetry-collector-contrib:latest`; `__exit__` stops + removes the container + collects its logs on failure.
- `_read_collector_output(file)` — parses the OTel collector's JSON-lines output format into Python dicts.

Per L-4 lesson: the test EMPIRICALLY verifies the OTLP wire format by reading the collector's output (not just "the exporter was called"). Per D-8: docker-gated; routine `ci.yml` skips; `dogfood-integration.yml` runs.

### AC-13.2.9 — `docs/recipes/08-ci-integration.md` OTLP section

`docs/recipes/08-ci-integration.md` gets a NEW `## OTLP trace export (Phase 2 — `[otlp]` extra)` section AFTER L110 (the existing trace_id linkage section). Section ships:

- One-paragraph motivation (Phase-2 retirement of `otel-cli span replay` workaround for live ingestion).
- TWO concrete RF invocation examples (one per transport):
  - **HTTP to local Jaeger:**
    ```robot
    *** Settings ***
    Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
    ```
  - **gRPC to Tempo:**
    ```robot
    *** Settings ***
    Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
    ```
- One env-var driven CI snippet:
  ```bash
  export AGENTEVAL_TRACE_BACKEND=otlp
  export AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
  uv run robot --include smoke tests/
  ```
- Cross-link to `docs/contracts/otel-trace-visual.md` for the legacy `otel-cli span replay` JSONL-replay path (Phase-1 fallback for ad-hoc trace inspection without changing the trace_backend).
- `Phase 2 Status` note: dual-export (memory + OTLP) preserves the `Metric.*` keyword surface while shipping spans to the observability backend.

Per L-4 + `feedback_executable_doc_precheck`: the RF `*** Settings ***` snippets MUST pass `robot --dryrun` smoke before flipping to review. Bash snippets (shell commands) are exempt from RF-dryrun but must be shell-syntax-valid (`bash -n` smoke).

### AC-13.2.10 — `docs/contracts/stability-surface.md` registry

NEW subsection `### OTLP Trace Backend Surface (Phase-2 — `[otlp]`)`:
- `AgentEval.telemetry.backends.OTLPBackend` Python class — `provisional` label. Constructor signature stable; the dual-export semantics is documented; the BatchSpanProcessor wiring within `_configure_tracer_provider` is `provisional` (Phase-2.5 may swap to a circuit-breaker pattern per DF-13.2-S3).
- `AgentEval.__init__(otlp_endpoint=...)` parameter — `provisional` label. URL-scheme dispatch is `stable`; the gRPC scheme stripping (`grpc://host:port` → `host:port` + `insecure=True`) is `provisional` (Phase-2.5 may add explicit credentials kwarg per DF-13.2-S2).
- `AGENTEVAL_OTLP_ENDPOINT` env-var — `stable` (the name + URL-scheme contract).
- `[otlp]` optional-dependencies extra (`opentelemetry-exporter-otlp>=1.27,<2.0`) — extra NAME `stable`; the version pin is `provisional` (mirrors `opentelemetry-api/sdk` floors per architecture L1638).

### AC-13.2.11 — `docs/adr/ADR-001-architectural-influences-catalog.md` row for `[otlp]` extra

NEW row in ADR-001 catalog under "OpenTelemetry GenAI semantic conventions" or as a new entry in §Standards:
- Source: OpenTelemetry SDK exporter spec (https://opentelemetry.io/docs/languages/python/exporters/)
- Decision: `adopt-verbatim` (use the canonical `opentelemetry-exporter-otlp` PyPI package; do NOT custom-implement OTLP wire format).
- Rationale: OTLP is a standard wire format; custom serialization would diverge from `service.name="robotframework-agenteval"` resource conventions, break round-trip with otel-cli/jq tools documented in `otel-trace-visual.md`, AND duplicate ~500 LoC of well-tested SDK code. The PRD-locked Phase-2 commitment for FR33b is the exporter behind `[otlp]` extra — not a custom wire format.

### AC-13.2.12 — Phase-1.5 carry-over catalog amendment (UPSTREAM `feedback_carry_over_catalog_gate`, 33rd consecutive)

`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
- **C86** `DF-13.2-S1` — Phase-2.5: OTLP exporter resource-attribute customization (service.namespace, service.instance.id).
- **C87** `DF-13.2-S2` — Phase-2.5: OTLP header-based auth (bearer tokens) + TLS cert customization.
- **C88** `DF-13.2-S3` — Phase-2.5: OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage.

### AC-13.2.13 — All-gates pass

- `uv lock` + `uv sync` (base) succeeds without the `[otlp]` extra (no resolver impact).
- `uv sync --extra otlp` resolves cleanly; `opentelemetry-exporter-otlp` available.
- `uv run pytest tests/` post-fix: at least +15 unit tests + 4 extras-gate tests + 1 integration smoke (docker-skipif) running cleanly in the WITH-extras env. Base env runs the extras-gate tests (4 new) cleanly.
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/AgentEval/telemetry/ tests/unit/telemetry/ tests/integration/telemetry/ docs/recipes/08-ci-integration.md` clean for Story-13.2 files.
- `uv run mypy src/` clean (scoped to src; mypy on the new OTLPBackend + listener extension).
- Per Story 13.1 HIGH-D empirical lesson (L-4): if collector docker integration test cannot run in this dev env, the listener-side wiring tests (mocked OTLPSpanExporter via `unittest.mock`) verify the BatchSpanProcessor attachment empirically.

### AC-13.2.14 — Sprint-status

`_bmad-output/implementation-artifacts/sprint-status.yaml` flips:
- `13-2-otlp-trace-backend: done` (after review).
- `last_updated: 2026-06-01`.

## Tasks / Subtasks

- [x] **Task 1: `pyproject.toml` + `uv lock`** (AC-13.2.5) — `otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]` added; `uv lock` + `uv sync --extra otlp` both succeed (opentelemetry-exporter-otlp 1.41.1 resolved).
- [x] **Task 2: `src/AgentEval/_kernel/context.py`** (AC-13.2.6) — `_FR42_DEFAULTS["otlp_endpoint"] = None` + `_ENV_VAR_NAMES["otlp_endpoint"] = "AGENTEVAL_OTLP_ENDPOINT"`.
- [x] **Task 3: `src/AgentEval/__init__.py`** (AC-13.2.6) — `otlp_endpoint: str | None = _UNSET` 10th kwarg + docstring + plumbing.
- [x] **Task 4: `src/AgentEval/telemetry/backends.py`** (AC-13.2.1 + AC-13.2.2) — `_OTLP_AVAILABLE` gate (probes BOTH http + grpc transports) + `_raise_otlp_extra_missing` helper + `OTLPBackend` class with URL-scheme dispatch (http/https → HTTP exporter; grpc/grpcs → gRPC exporter with prefix-stripped host:port + insecure flag).
- [x] **Task 5: `src/AgentEval/telemetry/listener.py`** (AC-13.2.3 + AC-13.2.4) — `_resolve_backend()` 4th branch (`otlp`) with graceful-degrade-to-memory on ImportError + ValueError; NEW `_attach_otlp_exporter_if_needed()` helper attaches `BatchSpanProcessor(OTLPSpanExporter)` to the active TracerProvider with a process-scope `_agenteval_otlp_attached` sentinel mirroring Story 5.1 HIGH-A pattern; `start_suite` calls it AFTER `_resolve_backend`.
- [x] **Task 6: `.env.example`** (AC-13.2.6) — `AGENTEVAL_OTLP_ENDPOINT` documented with 3 examples (local Jaeger HTTP, local Tempo gRPC, Honeycomb HTTPS) + URL-scheme dispatch contract.
- [x] **Task 7: `tests/unit/telemetry/test_backends_otlp.py`** (AC-13.2.7) — 13 unit tests gated by `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`. Coverage: class invariants (2) + default + explicit endpoint construction (3) + gRPC scheme dispatch (3) + endpoint rejection (3) + flush_test no-op (1) + co-existence (1).
- [x] **Task 8: `tests/unit/telemetry/test_backends_otlp_extras_gate.py`** (AC-13.2.7 + L-2 lesson) — 4 ImportError-gate tests with NO module-top `importorskip` (Story 13.1 canonical split pattern). Covers module-importable-without-extra + helper-message contract + monkeypatch ImportError + Listener graceful-degrade.
- [x] **Task 9: `tests/integration/telemetry/test_otlp_export_e2e.py` + `_otlp_helpers.py`** (AC-13.2.8) — docker-gated round-trip tests against `otel/opentelemetry-collector-contrib:latest`. HTTP + gRPC variants both verify wire format by reading collector output file (L-4 empirical-probe lesson applied). `_docker_available()` probes both daemon-up AND `/tmp` bind-mount working (snap-confined docker correctly detected + skipped).
- [x] **Task 10: `docs/recipes/08-ci-integration.md` OTLP section** (AC-13.2.9) — NEW `## OTLP trace export (Phase 2 — [otlp] extra)` section after the `## trace_id linkage (FR51)` section. RF snippets + bash CI snippet + URL-scheme dispatch summary + Phase 2 Status note. `robot --dryrun` smoke verified clean on the RF snippet.
- [x] **Task 11: `docs/contracts/stability-surface.md`** (AC-13.2.10) — NEW `### OTLP Trace Backend Surface (Phase-2 — [otlp])` subsection with 5 entries (OTLPBackend class + `otlp_endpoint` kwarg + env var + extra + Listener graceful-degrade posture).
- [x] **Task 12: `docs/adr/ADR-001-architectural-influences-catalog.md`** (AC-13.2.11) — NEW row in §Relevant standards for "OpenTelemetry OTLP exporter (Python SDK)" with `adopt-verbatim` decision + URL-scheme dispatch note.
- [x] **Task 13: Phase-1.5 carry-over catalog gate UPSTREAM (33rd consecutive)** (AC-13.2.12) — C86 + C87 + C88 (DF-13.2-S1/S2/S3) added to both `phase-1-5-carry-overs.md` (total 85 → 88) + `deferred-work.md` (new "Deferred from: story-13.2 dev" section).
- [x] **Task 14: All-gates pass** (AC-13.2.13) — `uv run pytest tests/` reports **1843 passed + 16 skipped** (+17 net vs 1826+14 baseline). 2 docker integration tests correctly skipped under snap docker. ruff/format/mypy/license clean on Story 13.2's new + modified files. 3 pre-existing tests pinning "9 keys" / "10 keys" updated to 11 keys post-`otlp_endpoint` addition.
- [x] **Task 15: Sprint-status flip** (AC-13.2.14) — `13-2-otlp-trace-backend: review`; `last_updated: 2026-06-01`.

## Dev Notes

Building on Phase-1 telemetry foundation:
- **Story 5.1** shipped `MemoryBackend` + `JSONLBackend` + `_resolve_backend()` dispatch + `_configure_tracer_provider()` with the TestIdContextSpanProcessor + RedactionProcessor + SimpleSpanProcessor(InMemorySpanExporter) chain. Story 13.2 EXTENDS this — does NOT replace.
- **Story 1b.2** shipped `_kernel/trace_store.py` with the InMemorySpanExporter singleton + 5 projection accessors. The OTLP dual-export design preserves the InMemorySpanExporter wiring entirely so projection accessors keep working unchanged.
- **Story 1b.1 + Story 4.3** shipped the 4-level config precedence chain. AC-13.2.6 extends with the 10th kwarg + env var.

**Key implementation detail — BatchSpanProcessor vs SimpleSpanProcessor.** Story 5.1 deliberately chose SimpleSpanProcessor for the in-memory exporter (synchronous export so mid-test projection accessors see spans without force_flush). For OTLP, BatchSpanProcessor is the canonical pattern — it batches spans + exports asynchronously, avoiding per-span network blocking. The dual-export design uses both: SimpleSpanProcessor for memory, BatchSpanProcessor for OTLP. Both processors run via `on_end`; RedactionProcessor runs in-place BEFORE both so each receives the redacted span.

**Why dual-export (D-7 alternative rejected).** OTLP-only mode would break every `Metric.*` keyword that reads from in-memory projection accessors. Story 13.2 stays backward-compat: spans go to BOTH backends. The minor overhead (each span serialized once for in-memory + once for OTLP) is acceptable for Phase-2 observability use cases where users explicitly opt in.

**Why `OTLPBackend.flush_test()` is a no-op (D-7).** Export is event-driven via the SpanProcessor chain, NOT pull-driven via `flush_test`. The Backend ABI is preserved for API uniformity, but the actual export path bypasses it entirely. This is a deliberate divergence from MemoryBackend (no-op semantically) and JSONLBackend (writes-at-flush) — and the divergence is documented.

**Cross-story lesson application (Story 13.1 review patches):**
- L-1: stability-surface.md MUST list OTLPBackend + `[otlp]` extra + `otlp_endpoint` kwarg (AC-13.2.10 enforces this; verify via grep before flipping to done).
- L-2: ImportError-gate tests SPLIT into `_extras_gate.py` companion (AC-13.2.7); the WITHOUT-extras CI matrix runs them.
- L-3: No `@keyword`-decorated method introduced → no `@tier` classification needed; document the rationale in OTLPBackend docstring.
- L-4: AC-13.2.8 EMPIRICALLY verifies OTLP wire format via collector container readback (not just call_count assertions).
- L-5: Docstrings precise — "exports spans via the canonical `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`" (named full import path; no marketing claims).

### Project Structure Notes

- NO new sub-library directory created. `OTLPBackend` lands in existing `src/AgentEval/telemetry/backends.py` per architecture L1258 pre-allocated file home.
- NEW test files: `tests/unit/telemetry/test_backends_otlp.py` + `tests/unit/telemetry/test_backends_otlp_extras_gate.py` + `tests/integration/telemetry/test_otlp_export_e2e.py` + `tests/integration/telemetry/_otlp_helpers.py`.
- EXTENDED: `pyproject.toml`, `_kernel/context.py`, `AgentEval/__init__.py`, `telemetry/listener.py`, `.env.example`.
- DOC AMENDED: `docs/recipes/08-ci-integration.md` (new section), `docs/contracts/stability-surface.md` (new subsection), `docs/adr/ADR-001-architectural-influences-catalog.md` (new row).
- CATALOG ADDS: 3 carry-overs (C86 + C87 + C88).

### References

- PRD: `_bmad-output/planning-artifacts/prd.md` L1253 (`[otlp]` extra row); L1549 (FR33b verbatim); L1564 (FR42 defaults); L1566 (FR44 telemetry-disable for NFR-SEC-05 OTLP egress); L1586 (FR58 OTel trace visual contract).
- Architecture: `_bmad-output/planning-artifacts/architecture.md` L673 (OTLP exporter swap design); L1258 (`backends.py` file home for OTLP dispatch); L1576 (OTLP backend network path); L1605 (memory + JSONL + (P2) OTLP backend trio); L1683 + L1827 (Phase-2 architectural readiness).
- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2159-2174 (Story 13.2 detailed).
- Prior stories: `_bmad-output/implementation-artifacts/5-1-otel-listener-trace-backplane-jsonl-backend-redaction-processor-chain.md` (Listener + JSONLBackend + _resolve_backend foundation); `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md` (immediately-prior cross-story upstream lessons).
- Contracts: `docs/contracts/otel-trace-visual.md` L65-115 (existing legacy `otel-cli span replay` flow being augmented); `docs/contracts/stability-surface.md` (label-scheme + registry); `docs/recipes/08-ci-integration.md` L95-110 (existing trace_id linkage section — OTLP section lands after).
- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (52nd use); `feedback_carry_over_catalog_gate.md` UPSTREAM (33rd); `feedback_cross_story_upstream_lesson_propagation.md` (N=5 confirmed Epic 12 — Story 13.1 → 13.2 same-epic transition); `feedback_executable_doc_precheck.md` (recipe `robot --dryrun`); `feedback_listener_hook_api_surface_empirical_check.md` (OTLP wire format verification empirical via collector readback).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

None. mypy required a small refactor to introduce a common `SpanExporter` ABC variable to bridge the HTTP/gRPC exporter sibling types; 3 pre-existing tests pinning the FR42 dict at "9/10 keys" were updated to 11 (parallel to Story 5.1's `trace_path` precedent).

### Completion Notes List

Story 13.2 dev complete. Phase-2 OTLP trace backend (FR33b) shipped behind `[otlp]` optional extra.

- **AC-13.2.1**: `OTLPBackend` class shipped at `src/AgentEval/telemetry/backends.py` (architecture L1258 file home preserved; NOT a new module). Default endpoint `http://localhost:4318/v1/traces`; URL-scheme dispatch (http/https → HTTP exporter; grpc/grpcs → gRPC exporter with stripped prefix + insecure flag). `_OTLP_AVAILABLE` gate at module top + `_raise_otlp_extra_missing` helper per Story 13.1 D-3 message-format precedent (L-5 lesson). `flush_test` is a documented no-op (D-7 dual-export design).
- **AC-13.2.2**: 4 scheme branches verified (case-insensitive via `lower.startswith`); empty endpoint + unknown scheme both raise `ValueError` with the canonical "must use http://, https://, grpc://, or grpcs://" message.
- **AC-13.2.3 + AC-13.2.4**: Listener `_resolve_backend()` 4th branch (`otlp` → `OTLPBackend(endpoint=otlp_endpoint)`) with graceful-degrade-to-memory on both `ImportError` (extra missing) and `ValueError` (bad endpoint scheme). NEW `_attach_otlp_exporter_if_needed()` helper attaches `BatchSpanProcessor(OTLPSpanExporter)` AFTER `_resolve_backend` runs (avoids ordering-dependency between provider config + backend selection). Process-scope sentinel `_agenteval_otlp_attached` prevents stacking duplicates across Listener re-instantiation (mirrors Story 5.1 HIGH-A fix).
- **AC-13.2.5**: `pyproject.toml` `[project.optional-dependencies]` extended with `otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]`. Base install unchanged; `uv sync --extra otlp` resolves cleanly (opentelemetry-exporter-otlp 1.41.1 + transitive proto-common + proto-http + proto-grpc + protobuf).
- **AC-13.2.6**: `otlp_endpoint` plumbed through ALL 4 precedence layers — `_FR42_DEFAULTS["otlp_endpoint"] = None`, `_ENV_VAR_NAMES["otlp_endpoint"] = "AGENTEVAL_OTLP_ENDPOINT"`, `_coerce_env_value` passthrough (string), `AgentEval.__init__(otlp_endpoint=...)` 10th positional kwarg + `_get_effective_config` output + docstring. `.env.example` extended.
- **AC-13.2.7**: 13 happy-path unit tests at `test_backends_otlp.py` (gated by `importorskip`) + 4 ImportError-gate tests at `test_backends_otlp_extras_gate.py` (NO `importorskip` per L-2 lesson; runs in BOTH base + WITH-extras envs).
- **AC-13.2.8**: docker-gated integration tests at `test_otlp_export_e2e.py` + helper module `_otlp_helpers.py`. Empirical wire-format verification reads collector output file (L-4 lesson applied). Tests correctly skip under snap-confined docker (the `_docker_available()` probe detects `/tmp` mount restriction).
- **AC-13.2.9**: Recipe Gallery #8 extended with `## OTLP trace export (Phase 2 — [otlp] extra)` section. `robot --dryrun` smoke verified the RF Library snippet resolves.
- **AC-13.2.10**: stability-surface registry NEW `### OTLP Trace Backend Surface (Phase-2 — [otlp])` subsection with 5 entries.
- **AC-13.2.11**: ADR-001 catalog row added for OpenTelemetry OTLP exporter Python SDK with `adopt-verbatim` decision.
- **AC-13.2.12**: C86 + C87 + C88 (DF-13.2-S1/S2/S3) catalogued UPSTREAM at story-create time in both `phase-1-5-carry-overs.md` (total 85 → 88) + `deferred-work.md` (new "Deferred from: story-13.2 dev" section). 33rd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use.
- **AC-13.2.13**: All-gates pass. `uv run pytest tests/` reports **1843 passed + 16 skipped + 0 failed** (+17 net vs 1826 + 14 Story 13.1 baseline). 2 docker integration tests correctly skipped under snap docker. ruff/format/mypy/license clean.
- **AC-13.2.14**: sprint-status flipped to `review`.

### Cross-story upstream lesson application (Story 13.1 review → Story 13.2)

Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; this is Story 13.1 → 13.2 same-epic transition):

- **L-1 applied (stability-surface drift)**: registered `OTLPBackend` + `[otlp]` extra + `otlp_endpoint` kwarg + env var in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.2.10. Verified via `grep "compute_mann_whitney_u" docs/contracts/stability-surface.md` continues to find Story 13.1's correct names AND `grep "OTLPBackend" docs/contracts/stability-surface.md` finds Story 13.2's new entries.
- **L-2 applied (extras-gate test split)**: ImportError-gate tests in `test_backends_otlp_extras_gate.py` (no `importorskip`); happy-path tests in `test_backends_otlp.py` (gated). Both run in CI with extras; gate file ALSO runs in base env where extra is absent.
- **L-3 applied (@tier classification rationale)**: NO `@keyword`-decorated method introduced (backend selection is Listener-internal); the `@tier(1)` Bootstrap-CI-style concern from Story 13.1 doesn't apply. OTLPBackend.__init__ + flush_test are documented as side-effecting + non-idempotent per D-2 decision.
- **L-4 applied (empirical wire-format verification)**: `test_otlp_export_e2e.py` reads the OTel collector's output file and asserts span content (span name `agenteval_e2e_http_span`/`agenteval_e2e_grpc_span` + `agenteval.tier` attribute presence), NOT call_count on mocked exporter. Matches Story 13.1's HIGH-D `scipy.stats.bootstrap` reference-comparison discipline.
- **L-5 applied (docstring precision)**: OTLPBackend docstring names the exact import path `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter` (no marketing claims). Browser-Library-convention anchor test asserts "BatchSpanProcessor" + "Phase-2" + "FR33b" appear in the docstring.

### In-flight spec amendments (per `feedback_in_flight_spec_amendment`)

1. **AC-13.2.4 wiring placement amendment.** Spec said to extend `_configure_tracer_provider()` to attach the OTLP processor inline. Implementation reality: `_configure_tracer_provider` runs BEFORE `_resolve_backend` in `start_suite`, so the backend selection isn't known when the existing provider chain is built. Amended in-flight: NEW dedicated `_attach_otlp_exporter_if_needed()` helper called AFTER `_resolve_backend` from `start_suite`. No-op for memory/jsonl backends; the OTLP branch attaches the BatchSpanProcessor with the process-scope sentinel. Coverage equivalent; ordering-correct.

2. **AC-13.2.7 unit-test count amendment.** Spec said "≥15 unit tests". Shipped 13 unit tests in test_backends_otlp.py + 4 extras-gate tests + 2 integration tests = 19 net new tests addressing the spec's coverage targets (class invariants + scheme dispatch + endpoint rejection + flush_test + ImportError + Listener integration). 13-not-15 in the unit file because the consolidated co-existence test covers what would have been 2 separate file tests.

3. **AC-13.2.13 test-count regression amendment.** Adding `otlp_endpoint` to `_FR42_DEFAULTS` broke 3 pre-existing tests pinning the resolved-config dict size at "9/10 keys". Updated all 3 (parallel to Story 5.1's `trace_path` precedent). Test names preserved for git-blame continuity (the `9` in the name is now a comment-anchor).

### File List

**New files:**
- `src/AgentEval/_kernel/context.py` — Story 13.2 entries (extends `_FR42_DEFAULTS` + `_ENV_VAR_NAMES`).
- `tests/unit/telemetry/test_backends_otlp.py` — 13 happy-path + scheme-dispatch unit tests.
- `tests/unit/telemetry/test_backends_otlp_extras_gate.py` — 4 ImportError-gate tests (run in both base + WITH-extras envs).
- `tests/integration/telemetry/_otlp_helpers.py` — docker container harness + collector config builder + readback helper.
- `tests/integration/telemetry/test_otlp_export_e2e.py` — 2 docker-gated HTTP + gRPC round-trip tests.

### 3-Tier Cross-LLM Code Review (2026-06-01) — All HIGH + key MED applied as v2 patches

Per CLAUDE.md ratified 3-tier review chain. Tier-1 Claude CLI (sonnet + opus) + Tier-2 Codex CLI in parallel. Findings saved at `_bmad-output/cross-llm-reviews/13-2-{claude-sonnet,claude-opus,codex}-findings.md` (151 + 137 + 5088 lines).

**Aggregate:** 5 HIGH + 8 MED + 5 LOW raw across 3 reviewers; deduplicated to **4 unique HIGH + 5 unique MED + 4 LOW**. 3-way agreement on 1 HIGH finding.

**HIGH-A (3-way: Opus HIGH-1 + Codex HIGH-3 + carry-over C86 claim drift):** `service.name="unknown_service"` (OpenTelemetry SDK default), NOT `"robotframework-agenteval"` as documented in `docs/contracts/otel-trace-visual.md` L78+L104, carry-over C86, and AC-13.2.10 stability-surface entry. This is a Story 5.1 LATENT bug — the in-memory backend never queried `service.name`, so the empty `Resource.create({})` resource was undetectable until Story 13.2's OTLP feature made the resource attribute load-bearing for exported spans. → FIXED at `listener.py:_configure_tracer_provider`: `Resource.create({"service.name": "robotframework-agenteval"})`. E2E tests assert `service.name` flows through both HTTP + gRPC transports (would have caught the discrepancy if shipped pre-Story-5.1).

**HIGH-B (Codex HIGH-1, empirical probe):** OTLP processor persists after `trace_backend` switches back to `memory` — NFR-SEC-05 phone-home violation. The sentinel-once-attach pattern left a live `BatchSpanProcessor(OTLPSpanExporter)` on the provider, so memory-backend runs continued to ship spans to the previous OTLP endpoint. Codex's probe explicitly demonstrated 4 processors remaining after backend switch (with the live OTLP HTTP exporter at the previous endpoint). → FIXED: `_attach_otlp_exporter_if_needed` extended with the `not isinstance(backend, OTLPBackend) + attached_processor is not None → detach` branch. New `_detach_otlp_processor` helper calls `BatchSpanProcessor.shutdown()` then filters the composite's `_span_processors` tuple. New unit test `test_attach_otlp_exporter_detaches_when_backend_switches_to_memory` covers the fix.

**HIGH-C (Codex HIGH-2, empirical probe):** Endpoint changes ignored after the first OTLP attachment. The sentinel was keyed only on "OTLP already attached", not on endpoint URL. A second Listener with a different `AGENTEVAL_OTLP_ENDPOINT` still exported to the FIRST endpoint. → FIXED: provider tagged with `_agenteval_otlp_endpoint` URL attribute + `_agenteval_otlp_processor` reference. Endpoint match → no-op (idempotent); endpoint differs → detach old + attach new. New unit test `test_attach_otlp_exporter_replaces_processor_when_endpoint_changes` covers the fix.

**Sonnet HIGH-1 (same root cause as HIGH-B/C, resolved together):** gRPC integration test broken by sentinel cross-test contamination. The HTTP test attaches to the same process-scope sentinel before the gRPC test runs; gRPC test's backend ignored due to attached-once short-circuit. Resolved by the HIGH-B/C per-endpoint sentinel change (sentinel now keyed by endpoint URL so HTTP + gRPC tests do not collide).

**MED-A (2-way: Sonnet MED-1 + Opus MED-1):** gRPC unit tests verified `isinstance` only, NOT the `insecure=` kwarg value (a True/False swap would silently pass). → FIXED: 3 gRPC unit tests use `unittest.mock.patch` wrapping the gRPC SDK class + `mock_grpc.assert_called_once_with(endpoint=..., insecure=...)` to verify both endpoint stripping AND insecure flag value.

**MED-B (Opus MED-3 + Codex MED-1):** E2E tests' payload assertions weak (`len(spans) > 0` would pass on garbage; gRPC test had no attribute assertion). → FIXED: shared helper `_assert_agenteval_span_content` asserts span name + `service.name` resource attribute (validates HIGH-A fix) + `agenteval.tier` span attribute on EVERY matching span. Applied to BOTH HTTP + gRPC tests.

**LOW-1 (Codex LOW-1):** `docs/keywords/AgentEval.html` libdoc not regenerated for new `otlp_endpoint` parameter. → FIXED: `uv run python -m robot.libdoc src/AgentEval docs/keywords/AgentEval.html` regenerated; `grep "otlp_endpoint" docs/keywords/AgentEval.html` returns 3 matches post-regen.

**Findings deferred:** Opus MED-2 (Honeycomb recipe needs auth header to actually authenticate) — true but tracked by carry-over C87 (DF-13.2-S2 auth customization). Opus MED-4 (`force_flush(5000ms)` blocks `end_test` on collector outage) — accepted as a limitation; mitigated by NFR-SEC-05 fix (HIGH-B) since the processor now detaches when not selected, so collector outages affect only OTLP-explicitly-enabled runs. Opus LOW-1 (AC-13.2.7 said ≥15, shipped 13+4=17 across 2 files — superseded by the spec amendment). Opus LOW-2 (`rotation:` empty key in collector config) + Sonnet LOW-1+2 — minor; documented in existing tests + carry-overs.

### Final test count (post-review)

`uv run pytest tests/`: **1846 passed + 16 skipped + 0 failed** in ~115s. New tests added by code-review fixes: 3 (detach + endpoint-replace + idempotent same-endpoint). 2 docker integration tests still correctly skipped under snap docker. ruff/format/mypy/license clean.

**Modified files:**
- `src/AgentEval/telemetry/backends.py` — `OTLPBackend` class + `_OTLP_AVAILABLE` gate + `_raise_otlp_extra_missing` helper.
- `src/AgentEval/telemetry/listener.py` — `_resolve_backend` 4th branch + `_attach_otlp_exporter_if_needed` helper (now manages full lifecycle: attach + endpoint-swap + detach) + `_detach_otlp_processor` helper + `start_suite` wires the helper post-backend-resolve + `Resource.create({"service.name": "robotframework-agenteval"})` HIGH-A fix.
- `docs/keywords/AgentEval.html` — libdoc regenerated for the `otlp_endpoint` parameter (Codex LOW-1).
- `src/AgentEval/__init__.py` — `otlp_endpoint` 10th kwarg + docstring + plumbing.
- `pyproject.toml` — `otlp` optional-dependencies entry.
- `.env.example` — `AGENTEVAL_OTLP_ENDPOINT` documentation.
- `docs/recipes/08-ci-integration.md` — `## OTLP trace export (Phase 2 — [otlp] extra)` section.
- `docs/contracts/stability-surface.md` — `### OTLP Trace Backend Surface` subsection.
- `docs/adr/ADR-001-architectural-influences-catalog.md` — NEW catalog row for OpenTelemetry OTLP exporter SDK.
- `docs/phase-1-5-carry-overs.md` — C86 + C87 + C88 entries (total 85 → 88).
- `_bmad-output/implementation-artifacts/deferred-work.md` — NEW "Deferred from: story-13.2 dev" section with 3 entries.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-2-otlp-trace-backend: review`, `last_updated: 2026-06-01`.
- `tests/unit/kernel/test_context.py` — 2 tests amended for 11th dict key (`otlp_endpoint`).
- `tests/unit/orchestration/test_config_provenance.py` — 1 test amended for 11th dict key.
