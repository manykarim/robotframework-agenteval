OpenAI Codex v0.133.0
--------
workdir: /home/many/workspace/robotframework-agenteval
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019e82c7-6e85-7220-9ac7-29e4dd3a79d0
--------
user
# Adversarial Code Review — Story 13.2: OTLP Trace Backend (PRD FR33b)

You are a SENIOR REVIEWER for the robotframework-agenteval project. Find REAL bugs, REAL spec drift, REAL correctness defects in Story 13.2. Be ADVERSARIAL but HONEST.

## Project context

- robotframework-agenteval: open-source Robot Framework library evaluating AI coding agents. Python 3.12+, RF 7.x, OpenTelemetry SDK >=1.27,<2.0.
- Story 13.2 ships the Phase-2 `[otlp]` extra: `trace_backend="otlp"` + `otlp_endpoint=<URL>` exports spans via the canonical `opentelemetry-exporter-otlp` package. URL scheme selects transport (`http://` / `https://` → HTTP/protobuf at 4318; `grpc://` / `grpcs://` → gRPC at 4317).
- Story file with full ACs, drift table (10 D-N items + 5 cross-story upstream lessons from Story 13.1 review), tasks, dev-record: `_bmad-output/implementation-artifacts/13-2-otlp-trace-backend.md`.
- Previous story (Story 13.1) review record: `_bmad-output/cross-llm-reviews/13-1-{claude-sonnet,claude-opus,codex}-findings.md` (3-tier review applied 6 HIGH + 4 MED patches).

## Review prompt (re-derive cited facts from source per `feedback_citation_drift_first_class`)

Re-derive every dev claim from source: PRD (`_bmad-output/planning-artifacts/prd.md` L1253 + L1549 for FR33b); architecture (`_bmad-output/planning-artifacts/architecture.md` L673 + L1258); epics (`_bmad-output/planning-artifacts/epics.md` L2159-2174); existing Story 5.1 telemetry/backends.py + listener.py. Flag any drift between cited facts and source as HIGH.

## Specific behavioral probes (per `feedback_codex_probe_fitness`)

1. **URL-scheme dispatch correctness.** For `endpoint="https://api.honeycomb.io/v1/traces"`, does `OTLPBackend` instantiate the HTTP exporter at exactly that URL? Or does it strip a scheme prefix incorrectly?
2. **gRPC `insecure=` correctness.** For `endpoint="grpc://localhost:4317"`, does the gRPC exporter get `endpoint="localhost:4317"` (stripped) + `insecure=True`? Verify against the `opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter` constructor signature.
3. **Process-scope sentinel idempotency.** When TWO `Listener` instances are constructed in the same process AND both have `OTLPBackend` selected, does the second one's `_attach_otlp_exporter_if_needed` correctly short-circuit via the `_agenteval_otlp_attached` sentinel? Or does it attach a duplicate BatchSpanProcessor (Story 5.1 HIGH-A class bug)?
4. **Dual-export design ordering.** Per the spec D-7, the in-memory SimpleSpanProcessor must remain attached so `Metric.*` projection accessors still work. After Story 13.2's wiring, does the existing `_configure_tracer_provider` still attach the InMemorySpanExporter? Verify the SimpleSpanProcessor is still in the provider chain when `trace_backend="otlp"`.
5. **Graceful-degrade safety.** When `_OTLP_AVAILABLE=False` AND `trace_backend="otlp"` is set, does `_resolve_backend` catch the `ImportError`, emit `DegradedTraceWarning`, and fall back to `MemoryBackend` rather than aborting the test run? Verify the warning carries the spec-mandated `uv pip install robotframework-agenteval[otlp]` install hint.
6. **`AGENTEVAL_OTLP_ENDPOINT` env var precedence.** Does the FR41 4-level chain (init_arg → env → .env → default) work for `otlp_endpoint`? Specifically: setting `AGENTEVAL_OTLP_ENDPOINT=http://...` in env should override the `None` default at construction.
7. **NFR-SEC-05 phone-home compliance.** Per PRD L1634, the library "does NOT phone home" — OTLP egress is opt-in. When `trace_backend="memory"` (default), does ANY code path attempt to construct an OTLPSpanExporter OR connect to any OTLP endpoint? Probe via grep for `OTLPSpanExporter` construction sites.
8. **Recipe `robot --dryrun` smoke claim.** Per `feedback_executable_doc_precheck`: the dev claims the Recipe #8 RF Library snippet `Library AgentEval trace_backend=otlp otlp_endpoint=http://localhost:4318/v1/traces` passes `robot --dryrun`. Empirically verify by extracting the snippet to a tmp `.robot` file + running `uv run robot --dryrun`.
9. **L-3 cross-story claim verification.** Story 13.1 introduced an `@tier(1)` Bootstrap-CI bug (`seed=None` violated FR31a). Story 13.2 claims no `@keyword` surface is introduced so the L-3 lesson doesn't apply. Verify: does Story 13.2 ship any new `@keyword`-decorated method? Grep `src/AgentEval/telemetry/` for `@keyword` decorators added by this diff.
10. **L-4 empirical-probe verification.** The dev claims `test_otlp_export_e2e.py` reads the collector's output file to verify span content. Does the test assert SPECIFIC SPAN CONTENT (e.g., span name match, attribute presence), OR just `len(spans) > 0` which would pass even on garbage output?

## Categorization

- **HIGH**: Real bug, real spec drift, real correctness defect.
- **MED**: Significant quality issue / test coverage gap.
- **LOW**: Minor improvement / style / docstring polish.

## Output format

For each finding:

```
### [HIGH/MED/LOW]-N: <one-line title>

**File:** `<path>:<line>`
**Issue:** <2-3 sentences>
**Evidence:** <verbatim code excerpt or test output>
**Fix:** <concrete patch suggestion>
```

End with: `**Total: X HIGH + Y MED + Z LOW**`.

## Story diff

The full diff (1860+ lines, 1662 inserted) is at `/tmp/story-13-2-review.diff`. Read it and analyze.

---

## Diff to review:

```diff
diff --git a/.env.example b/.env.example
index 59ebea6..56ee011 100644
--- a/.env.example
+++ b/.env.example
@@ -49,3 +49,14 @@ AGENTEVAL_MAX_RUNTIME_SECONDS=
 
 # External-MCP coverage gate (ADR-016 default-deny; set true to allow external_mixed runs)
 AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND=false
+
+# OTLP trace backend endpoint (Phase 2 — Story 13.2 FR33b; requires `[otlp]` extra).
+# Only consumed when AGENTEVAL_TRACE_BACKEND=otlp. URL scheme selects transport:
+#   - http://  / https:// → OTLP HTTP/protobuf exporter (port 4318)
+#   - grpc://  / grpcs:// → OTLP gRPC exporter (port 4317)
+# Examples:
+#   AGENTEVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces       # local Jaeger HTTP
+#   AGENTEVAL_OTLP_ENDPOINT=grpc://localhost:4317                 # local Tempo gRPC (insecure)
+#   AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces    # Honeycomb HTTPS
+# Default (when AGENTEVAL_TRACE_BACKEND=otlp + this is unset): http://localhost:4318/v1/traces.
+AGENTEVAL_OTLP_ENDPOINT=
diff --git a/_bmad-output/implementation-artifacts/13-2-otlp-trace-backend.md b/_bmad-output/implementation-artifacts/13-2-otlp-trace-backend.md
new file mode 100644
index 0000000..b8c06b4
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-2-otlp-trace-backend.md
@@ -0,0 +1,421 @@
+# Story 13.2: OTLP Trace Backend
+
+Status: review
+
+## Story
+
+As an **observability-focused user** (Raj or Priya integrating with production observability stacks),
+I want `trace_backend="otlp"` shipping OTel spans to an OTLP collector via the canonical OpenTelemetry SDK exporter,
+So that AgentEval traces flow into Jaeger / Honeycomb / Tempo / Grafana for production observability — closing the PRD FR33b Phase-2 commitment and retiring the manual `otel-cli span replay` workaround documented in `docs/contracts/otel-trace-visual.md` L65-115.
+
+## Pre-create-story drift check (52nd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+10 drifts caught — 5 fresh decisions from spec analysis + 5 UPSTREAM lessons from Story 13.1 reviews (the immediately-prior same-epic story; `feedback_cross_story_upstream_lesson_propagation` N=5 confirmed at Epic 12 retro). **100% real-drift catch rate maintained through 51 prior uses.**
+
+- **D-1 (HIGH — extras name drift PRD vs architecture vs ADR-001, 2-vs-1):** **2-source-vs-1 majority on the extras name.**
+  - **PRD L1253 / architecture L673:** `[otlp]` extra (literally — `pip install robotframework-agenteval[otlp]`).
+  - **ADR-001 catalog (no row exists yet)** — Story 13.2 ADDS one.
+  - Story 13.1 set the **`agenteval-advanced`** precedent (longer, project-prefixed name). PRD uses `[otlp]` everywhere. There is NO contradiction here — these are different extras (`agenteval-advanced` for stats, `otlp` for the OTLP exporter dep). **Decision:** ship as `[otlp]` per PRD/architecture verbatim. Symmetric with the existing CLI-adapter extras pattern (`claude-code` / `codex` / `copilot` — unprefixed, short adapter-name verbatim). Apply Story 13.1 cross-story upstream lesson: validate the spec wording vs ADR-001 catalog ADD a new row (no drift to fix because no prior ADR-001 row exists).
+
+- **D-2 (HIGH — `@tier(1)` FR31a contract for telemetry side-effects, UPSTREAM from Story 13.1 Opus HIGH-1):** OTLP export is a side-effecting network call. The trace_backend selection is a Listener-time concern, NOT a keyword surface — Story 5.1's Listener resolves the backend in `_resolve_backend()` and exports spans through the chosen SpanProcessor chain. There is NO `@keyword`-decorated method introduced by this story, so the @tier classification question is moot. **Decision:** Story 13.2 is a Listener-internal backend swap; the Story 13.1 lesson "Tier-1 with non-determinism violates FR31a" doesn't apply directly here because the backend selection itself doesn't run from within a keyword. Add a docstring note on `OTLPBackend.flush_test()` documenting "side-effecting; not idempotent (each call exports spans to the configured endpoint)."
+
+- **D-3 (HIGH — OTLP backend file home + class shape per architecture L1258 + L673):** architecture L1258 pre-allocates `backends.py` for "memory / jsonl backends Phase 1; otlp dispatch Phase 2 per FR33b." L673 specifies the dispatch as `OTLPSpanExporter` swap. **Decision:** ship `OTLPBackend` class in the EXISTING `src/AgentEval/telemetry/backends.py` (do NOT create a new `otlp.py` module per Story 13.1 D-5 / cliffs_delta-style pattern — architecture pre-allocates `backends.py` as the single backend home; consistent with `MemoryBackend` + `JSONLBackend` siblings already shipped at this path). Module-level `try: import opentelemetry.exporter.otlp.proto.http / except ImportError: _OTLP_AVAILABLE = False` gate at `backends.py` top (mirrors Story 13.1's `_ADVANCED_AVAILABLE` discipline at `stats/library.py`).
+
+- **D-4 (HIGH — exporter API: gRPC vs HTTP per epic AC L2171):** epic AC L2171 mandates BOTH `gRPC` (`otlp_endpoint="grpc://..."`) AND `HTTP` (`otlp_endpoint="http://..."`) protocol selection via URL scheme. The `opentelemetry-exporter-otlp` PyPI package ships TWO sub-packages:
+  - `opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter` — HTTP/protobuf transport (port 4318).
+  - `opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter` — gRPC transport (port 4317).
+  Both classes share the same constructor `endpoint=` kwarg + the same `export(spans)` interface (both inherit `SpanExporter`). **Decision:** parse the URL scheme from `otlp_endpoint`:
+  - `http://` / `https://` → instantiate the HTTP exporter.
+  - `grpc://` / `grpcs://` → instantiate the gRPC exporter (stripping the `grpc://` prefix per gRPC SDK convention which expects bare `host:port`).
+  - Default endpoint (when `otlp_endpoint` is unset) → `http://localhost:4318/v1/traces` per OpenTelemetry SDK convention.
+  - Unknown scheme → raise `ValueError(f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme!r}")`.
+
+- **D-5 (HIGH — `otlp_endpoint` config key + env var per Story 5.1 4-level precedence):** Story 5.1 `_resolve_backend()` reads `trace_backend` from `_kernel/context.resolve_config({})` which honors the FR41 4-level precedence chain (init_arg → env-var → `.env` → default). **Decision:** add `otlp_endpoint` to:
+  - `_kernel/context.py:_FR42_DEFAULTS` — default `None` (caller must set OR use `http://localhost:4318/v1/traces` fallback in OTLPBackend).
+  - `_kernel/context.py:_ENV_VAR_NAMES` — `AGENTEVAL_OTLP_ENDPOINT`.
+  - `_kernel/context.py:_coerce_env_value` — string passthrough (URL).
+  - `_kernel/context.py:_KNOWN_ENV_VAR_NAMES` — automatically extended by inclusion in `_ENV_VAR_NAMES`.
+  - `AgentEval.__init__` signature: NEW `otlp_endpoint: str | None = _UNSET` kwarg + resolved-config plumbing (the 10th `__init__` parameter).
+  - `_config_provenance` ConfigValue propagation.
+  - `.env.example`: documented env-var with example values for HTTP + gRPC endpoints.
+
+- **D-6 (MED — `_resolve_backend()` extension at `telemetry/listener.py:798-823`):** Story 5.1's `_resolve_backend()` has 3 branches: `"jsonl"` → JSONLBackend; `"memory"` → MemoryBackend; else → warn + fall back to memory. **Decision:** add a 4th branch: `"otlp"` → instantiate `OTLPBackend(endpoint=config.get("otlp_endpoint"))`. If `_OTLP_AVAILABLE = False` at import time, the OTLPBackend.__init__ raises `ImportError` with the verbatim message recommending `uv pip install robotframework-agenteval[otlp]` (mirrors Story 13.1 D-3 message contract). The "unknown trace_backend → fall back to memory" path's documented valid-values list updates from `{'memory', 'jsonl'}` to `{'memory', 'jsonl', 'otlp'}`.
+
+- **D-7 (MED — `OTLPBackend` exporter wiring is at TracerProvider-config time, NOT flush_test):** Architecture L673 says "swaps `InMemorySpanExporter` for `OTLPSpanExporter`" — but Story 5.1's listener.py:284-298 wires `SimpleSpanProcessor(trace_store._get_exporter())` as the in-memory exporter chain AT TRACE-PROVIDER-CONFIG TIME, not per-test. For OTLP, the canonical pattern is `BatchSpanProcessor(OTLPSpanExporter)` for batched async export (the InMemorySpanExporter is process-resident; OTLP is network-bound).
+  - **Decision:** when `trace_backend="otlp"`, the listener extends `_configure_tracer_provider()` to ALSO add a `BatchSpanProcessor(OTLPSpanExporter)` to the provider chain (in addition to the existing `SimpleSpanProcessor(InMemorySpanExporter)` for projection-accessor compatibility). This is a DUAL-EXPORT design: spans go to both the in-memory store (so existing `Metric.*` keywords still work) AND the OTLP endpoint (so traces flow to the observability backend).
+  - `OTLPBackend.flush_test()` is then a no-op (export happens batched via the SpanProcessor chain). The `flush_test` API uniformity with MemoryBackend / JSONLBackend is preserved but the actual export is event-driven, not flush-driven.
+  - Alternative considered + REJECTED: OTLP-only mode (no in-memory store). Would break every existing `Metric.*` keyword (Story 6.1, Story 5.2) since they read from the in-memory projection accessors. Backward-compat wins.
+
+- **D-8 (MED — integration test docker harness + skip-when-no-collector):** epic AC L2169 mandates "integration test verifies round-trip against a local OTLP collector docker container." A test that REQUIRES docker to pass in CI is fragile. **Decision:** ship the integration test with a `@pytest.mark.skipif(not _docker_available(), reason="docker not available")` gate that checks for `docker` binary on PATH AND a running daemon (via `docker ps` smoke). Tests run in dev environments + the `dogfood-integration.yml` CI workflow which provisions docker; routine `ci.yml` skips the test (it'll appear in the skip count). Use the OTel collector's pre-built image `otel/opentelemetry-collector-contrib:latest` with a minimal config that accepts OTLP + writes to a local file the test can read back. Docker container teardown via pytest fixture (yield + finally cleanup) per existing dogfood-CI fixtures pattern.
+
+- **D-9 (MED — Recipe Gallery #8 update per epic AC L2173):** epic AC L2173 mandates "Recipe Gallery #8 (CI integration) is updated with an OTLP integration example showing trace data flowing into a Honeycomb/Jaeger dashboard." **Decision:** ADD a new `## OTLP trace export (Phase 2 — `[otlp]` extra)` section to `docs/recipes/08-ci-integration.md` AFTER the existing `## trace_id linkage (FR51)` section (L95-110). The section ships TWO concrete invocation examples: (a) HTTP endpoint to local Jaeger; (b) gRPC endpoint to Grafana Tempo. Cross-link to `docs/contracts/otel-trace-visual.md` for the legacy `otel-cli span replay` JSONL-replay path (Phase-1 fallback). Per `feedback_executable_doc_precheck`: the new section's commands need NOT be `robot --dryrun`-able (they're shell commands not RF keywords) but the `Library    AgentEval    trace_backend=otlp    otlp_endpoint=...` snippet IS RF-syntax + MUST dryrun-clean per Story 12.3 precedent.
+
+- **D-10 (LOW — carry-over catalog gate UPSTREAM Story 13.1 / 33rd consecutive):** Anticipated Phase-2 carry-overs for Story 13.2:
+  - **DF-13.2-S1 (Phase-2.5):** OTLP exporter resource-attribute customization. PRD says `service.name = "robotframework-agenteval"` (per otel-trace-visual.md L78 + L104). Phase-2 may want per-suite `service.namespace` or per-run `service.instance.id` for multi-suite isolation.
+  - **DF-13.2-S2 (Phase-2.5):** OTLP header-based auth + TLS cert customization. The exporter `headers=` and `credentials=` kwargs let operators add bearer tokens / mTLS. Phase-2 ships endpoint-only; auth via separate carry-over.
+  - **DF-13.2-S3 (Phase-2.5):** OTLP exporter retry + circuit-breaker. The OpenTelemetry SDK's `OTLPSpanExporter` has built-in retry but no circuit-breaker for sustained collector outages. Phase-2.5 adds a circuit-breaker that falls back to JSONL after N consecutive failures.
+  - Pre-emptive catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-05-27): catalogue C86 + C87 + C88 in both catalog files BEFORE invoking `/bmad-code-review` (Task N-1).
+
+## Cross-story upstream lessons from Story 13.1 reviews
+
+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12 retro) — Story 13.1 is the immediately-prior same-epic story. 6 HIGH + 4 MED Story 13.1 review findings fold into Story 13.2 ACs UPSTREAM:
+
+- **L-1 (from Story 13.1 HIGH-A 3-way):** stability-surface.md must register the NEW `OTLPBackend` + `[otlp]` extra surface entries — DO NOT ship to review until verified by `grep`.
+- **L-2 (from Story 13.1 HIGH-B Codex empirical):** Tests gating on the OTLP-extra presence MUST be split — happy-path tests use `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`; ImportError-gate tests sit in a SEPARATE file with NO `importorskip` (run in both WITH and WITHOUT-extras CI envs). Story 13.1's `test_advanced_extras_gate.py` is the canonical pattern.
+- **L-3 (from Story 13.1 HIGH-C Opus):** Verify the @tier classification of any newly-exposed keyword surface (none in this story, but document the rationale to head off Opus questions). Listener-internal backend swap doesn't expose a @tier-classified surface.
+- **L-4 (from Story 13.1 HIGH-D Codex empirical):** When making a claim ("matches scipy default", "exports via OTLP HTTP protocol", etc.), include a test that EMPIRICALLY verifies the claim against a reference implementation. AC-13.2.6 includes an end-to-end integration test that captures the exported OTLP payload + verifies its content vs. the expected span shape — NOT just "the exporter was called."
+- **L-5 (from Story 13.1 HIGH-E 3-way + MED-2 honesty):** Docstrings claiming "matches scipy default" / "exports per OTel spec" must be precise — if normalizing or transforming, say so explicitly. The OTLPBackend docstring states "exports spans via the canonical `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`" with the exact import path, no marketing-style claims.
+
+## Acceptance Criteria
+
+### AC-13.2.1 — `OTLPBackend` class in `telemetry/backends.py`
+
+`src/AgentEval/telemetry/backends.py` extends with `OTLPBackend` class (architecture L1258 file home). Class shape mirrors `MemoryBackend` / `JSONLBackend` for API uniformity:
+
+```python
+class OTLPBackend:
+    """OTLP trace backend (opt-in via ``trace_backend="otlp"``; Phase-2 FR33b).
+
+    Exports spans via the canonical
+    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based on
+    the URL scheme of ``endpoint``. Requires the ``[otlp]`` optional extra
+    (``opentelemetry-exporter-otlp``); raises ``ImportError`` on construction
+    when the extra is missing.
+
+    Export semantics: spans are routed via a ``BatchSpanProcessor`` attached
+    to the TracerProvider (NOT via ``flush_test``). ``flush_test`` is a
+    no-op here — included for API uniformity with ``MemoryBackend`` /
+    ``JSONLBackend``.
+    """
+
+    name = "otlp"
+
+    def __init__(self, endpoint: str | None = None) -> None: ...
+
+    def flush_test(self, test_id: str, suite_id: str = "", output_dir: Path | None = None) -> None:
+        """No-op. OTLP export is batched via the SpanProcessor chain at TracerProvider config time."""
+```
+
+Module-level `_OTLP_AVAILABLE = True/False` gate via `try: import opentelemetry.exporter.otlp.proto.http as _otlp_http; import opentelemetry.exporter.otlp.proto.grpc as _otlp_grpc` (BOTH transports probed at gate-time so the construction-time error is consistent regardless of which scheme the operator chose).
+
+### AC-13.2.2 — URL-scheme dispatch for HTTP vs gRPC
+
+`OTLPBackend.__init__(endpoint)`:
+- Default endpoint (when `endpoint is None`): `"http://localhost:4318/v1/traces"` per OpenTelemetry SDK convention.
+- `http://` / `https://` → instantiate `opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter(endpoint=endpoint)`.
+- `grpc://` / `grpcs://` → strip the scheme prefix (extract `host:port`) → instantiate `opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter(endpoint=host_port, insecure=True/False)`. `grpc://` → `insecure=True`; `grpcs://` → `insecure=False` (TLS).
+- Any other scheme → raise `ValueError(f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme!r}")`.
+- Store the constructed exporter as `self._exporter` for the Listener to wire via `BatchSpanProcessor`.
+
+### AC-13.2.3 — `_resolve_backend()` extends to `"otlp"` branch
+
+`src/AgentEval/telemetry/listener.py:_resolve_backend()` adds a 4th branch:
+
+```python
+elif backend_name == "otlp":
+    otlp_endpoint = config.get("otlp_endpoint")
+    self._backend = OTLPBackend(endpoint=otlp_endpoint)
+```
+
+The unknown-backend fallback message updates from `"Valid values: {'memory', 'jsonl'}."` to `"Valid values: {'memory', 'jsonl', 'otlp'}."` (D-6 fix). The `DegradedTraceWarning` remediation text similarly updates.
+
+### AC-13.2.4 — `_configure_tracer_provider()` dual-export wiring
+
+`src/AgentEval/telemetry/listener.py:_configure_tracer_provider()` extends to add the OTLP BatchSpanProcessor when `self._backend` is `OTLPBackend`:
+
+```python
+# After the existing SimpleSpanProcessor(InMemorySpanExporter) line:
+if isinstance(self._backend, OTLPBackend):
+    provider.add_span_processor(
+        BatchSpanProcessor(self._backend._exporter)
+    )
+```
+
+**Order matters:** the existing chain is `TestIdContextSpanProcessor → RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter)`. The OTLP processor lands AFTER RedactionProcessor (redaction applies to OTLP-exported spans per NFR-SEC-01 + FR38a) and AFTER the InMemorySpanExporter (so projection accessors continue to receive un-redacted-from-their-perspective spans — RedactionProcessor mutates spans in-place on `on_end`, so order within the post-redaction tail does not affect content; only the BatchSpanProcessor vs SimpleSpanProcessor distinction matters for export timing).
+
+The "process-scope sentinel" idempotency mechanism (Story 5.1 HIGH-A fix) applies: re-attaching to an existing provider must NOT duplicate the OTLP processor. The sentinel check + the `_tracer_configured` flag prevent stacking.
+
+### AC-13.2.5 — `pyproject.toml` `[otlp]` optional extra
+
+`pyproject.toml` `[project.optional-dependencies]` adds:
+
+```toml
+# Story 13.2 (Epic 13) — OTLP trace exporter (FR33b). Phase-2 backend
+# behind the `[otlp]` extra: when `trace_backend="otlp"`, agenteval spans
+# export to a configured OTLP collector (Jaeger / Honeycomb / Tempo /
+# Grafana). The package `opentelemetry-exporter-otlp` is a metapackage
+# pulling both HTTP/protobuf and gRPC transports; URL-scheme dispatch
+# at OTLPBackend.__init__ time chooses between them. Pinned ranges
+# match the existing `opentelemetry-api` / `opentelemetry-sdk` floors
+# (>=1.27,<2.0 per architecture L1638 + Story 5.1 review fix).
+otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]
+```
+
+`uv lock` + `uv sync` (base) succeeds without the OTLP exporter (no resolver impact). `uv sync --extra otlp` resolves cleanly + the exporter modules import.
+
+### AC-13.2.6 — `otlp_endpoint` config wired through the 4-level precedence chain
+
+`src/AgentEval/_kernel/context.py` extended at 4 sites:
+1. `_FR42_DEFAULTS` adds `"otlp_endpoint": None`.
+2. `_ENV_VAR_NAMES` adds `"otlp_endpoint": "AGENTEVAL_OTLP_ENDPOINT"`.
+3. `_coerce_env_value` — URL is a string, passes through unchanged via the catch-all final branch (no new clause needed). Verify the existing comment `# provider, trace_backend — strings; pass through.` extends to cover `otlp_endpoint`.
+4. `_KNOWN_ENV_VAR_NAMES` automatically updates via `_ENV_VAR_NAMES` inclusion.
+
+`src/AgentEval/__init__.py` extended:
+- `AgentEval.__init__` signature gains `otlp_endpoint: str | None = _UNSET` (10th kwarg, placed AFTER `max_runtime_seconds`).
+- `kwarg_overrides` dict + `resolved["otlp_endpoint"]` extraction → `self._otlp_endpoint`.
+- `_get_effective_config` dict output includes `otlp_endpoint`.
+- Docstring updated with `otlp_endpoint` parameter description.
+
+`.env.example` extended with:
+```
+# OTLP trace backend endpoint (Phase 2 — requires `[otlp]` extra).
+# Examples:
+#   AGENTEVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces       # local Jaeger HTTP
+#   AGENTEVAL_OTLP_ENDPOINT=grpc://localhost:4317                 # local Tempo gRPC (insecure)
+#   AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces    # Honeycomb HTTPS
+# AGENTEVAL_OTLP_ENDPOINT=
+```
+
+### AC-13.2.7 — Unit tests at `tests/unit/telemetry/test_backends_otlp.py`
+
+NEW file. ≥15 unit tests covering OTLPBackend construction + endpoint dispatch + ImportError gate. Math + reference comparison NOT applicable here (export-side; integration test covers the wire format).
+
+Coverage:
+- **Construction with extra (8 tests; gated by `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`):** default-endpoint construction → HTTP exporter at `http://localhost:4318/v1/traces`; explicit `http://...` → HTTP exporter at given URL; explicit `https://...` → HTTP exporter at given URL; `grpc://localhost:4317` → gRPC exporter with `insecure=True`; `grpcs://otel.example.com:4317` → gRPC exporter with `insecure=False` + stripped scheme; unknown scheme `ftp://...` → `ValueError` with "must use http://, https://, grpc://, or grpcs:// scheme"; explicit `None` endpoint → default HTTP local-Jaeger; explicit empty string `""` → `ValueError` (rejects empty URL).
+- **`flush_test` is no-op (1 test):** invoking `flush_test(test_id, suite_id, output_dir)` returns None + writes no files + does NOT call any exporter method (mocked via `unittest.mock.patch` on the exporter `.export` method to assert call_count == 0).
+- **Class name attribute (1 test):** `OTLPBackend.name == "otlp"` (symmetric with `MemoryBackend.name == "memory"` / `JSONLBackend.name == "jsonl"`).
+- **Docstring assertions (1 test):** OTLPBackend docstring contains "BatchSpanProcessor" + "Phase-2" + "FR33b" — per `feedback_full_surface_retro_review` Browser-Library convention.
+
+Plus 4 ImportError-gate tests at NEW `tests/unit/telemetry/test_backends_otlp_extras_gate.py` (split per Story 13.1 L-2 lesson; NO `importorskip` at module top so it runs in both base + WITH-extras envs):
+- `test_otlp_backend_raises_import_error_without_extra` — monkeypatches `_OTLP_AVAILABLE = False` on `backends`, asserts `OTLPBackend(endpoint="http://...")` raises `ImportError("OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]")`.
+- `test_raise_otlp_extra_missing_helper_carries_canonical_message` — direct helper exercise.
+- `test_backends_importable_without_otlp_extra` — `from AgentEval.telemetry.backends import OTLPBackend, MemoryBackend, JSONLBackend` succeeds without the extra (the class is importable; construction is what raises).
+- `test_resolve_backend_falls_back_with_warning_when_otlp_construction_fails` — Listener `_resolve_backend` integration: with `trace_backend="otlp"` + `_OTLP_AVAILABLE = False`, Listener catches the `ImportError` + emits `DegradedTraceWarning` + falls back to MemoryBackend (graceful degradation under partial install).
+
+### AC-13.2.8 — Integration test against OTLP collector docker container
+
+NEW file at `tests/integration/telemetry/test_otlp_export_e2e.py`. End-to-end round-trip:
+
+```python
+@pytest.mark.skipif(not _docker_available(), reason="docker not available")
+def test_otlp_http_export_round_trip_against_collector(tmp_path, docker_client):
+    """Spans emitted to a local OTel collector container land in its output file."""
+    collector_cfg = tmp_path / "otel-config.yaml"
+    collector_cfg.write_text(_minimal_otel_config(output_file=tmp_path / "spans.json"))
+
+    with docker_client.run_collector(config=collector_cfg, port=4318) as collector:
+        os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"
+        os.environ["AGENTEVAL_OTLP_ENDPOINT"] = f"http://localhost:{collector.port}/v1/traces"
+        # Emit a span via the agenteval listener under an RF test fixture.
+        result = run_rf_test_with_listener(test_body=_minimal_span_emit_test())
+        assert result.passed
+        collector.flush()  # force batch flush before reading output
+
+    spans = _read_collector_output(tmp_path / "spans.json")
+    assert len(spans) > 0
+    assert any(s["name"] == "invoke_agent" for s in spans)
+    assert all(s["resource"]["attributes"]["service.name"] == "robotframework-agenteval" for s in spans)
+    # Verify agenteval-specific attributes flow through OTLP envelope.
+    assert any("agenteval.tier" in s["attributes"] for s in spans)
+```
+
+Plus a gRPC variant: `test_otlp_grpc_export_round_trip_against_collector` using `grpc://localhost:4317` + the collector's gRPC receiver.
+
+Test harness helpers (NEW; live in `tests/integration/telemetry/_otlp_helpers.py`):
+- `_docker_available()` — returns False if `docker` binary missing OR `docker info` fails.
+- `_minimal_otel_config(output_file)` — generates a minimal OTel collector config with `otlp` receivers (HTTP + gRPC) + `file` exporter writing to `output_file`.
+- `DockerCollectorContext` context manager — `__enter__` pulls + starts `otel/opentelemetry-collector-contrib:latest`; `__exit__` stops + removes the container + collects its logs on failure.
+- `_read_collector_output(file)` — parses the OTel collector's JSON-lines output format into Python dicts.
+
+Per L-4 lesson: the test EMPIRICALLY verifies the OTLP wire format by reading the collector's output (not just "the exporter was called"). Per D-8: docker-gated; routine `ci.yml` skips; `dogfood-integration.yml` runs.
+
+### AC-13.2.9 — `docs/recipes/08-ci-integration.md` OTLP section
+
+`docs/recipes/08-ci-integration.md` gets a NEW `## OTLP trace export (Phase 2 — `[otlp]` extra)` section AFTER L110 (the existing trace_id linkage section). Section ships:
+
+- One-paragraph motivation (Phase-2 retirement of `otel-cli span replay` workaround for live ingestion).
+- TWO concrete RF invocation examples (one per transport):
+  - **HTTP to local Jaeger:**
+    ```robot
+    *** Settings ***
+    Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
+    ```
+  - **gRPC to Tempo:**
+    ```robot
+    *** Settings ***
+    Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
+    ```
+- One env-var driven CI snippet:
+  ```bash
+  export AGENTEVAL_TRACE_BACKEND=otlp
+  export AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
+  uv run robot --include smoke tests/
+  ```
+- Cross-link to `docs/contracts/otel-trace-visual.md` for the legacy `otel-cli span replay` JSONL-replay path (Phase-1 fallback for ad-hoc trace inspection without changing the trace_backend).
+- `Phase 2 Status` note: dual-export (memory + OTLP) preserves the `Metric.*` keyword surface while shipping spans to the observability backend.
+
+Per L-4 + `feedback_executable_doc_precheck`: the RF `*** Settings ***` snippets MUST pass `robot --dryrun` smoke before flipping to review. Bash snippets (shell commands) are exempt from RF-dryrun but must be shell-syntax-valid (`bash -n` smoke).
+
+### AC-13.2.10 — `docs/contracts/stability-surface.md` registry
+
+NEW subsection `### OTLP Trace Backend Surface (Phase-2 — `[otlp]`)`:
+- `AgentEval.telemetry.backends.OTLPBackend` Python class — `provisional` label. Constructor signature stable; the dual-export semantics is documented; the BatchSpanProcessor wiring within `_configure_tracer_provider` is `provisional` (Phase-2.5 may swap to a circuit-breaker pattern per DF-13.2-S3).
+- `AgentEval.__init__(otlp_endpoint=...)` parameter — `provisional` label. URL-scheme dispatch is `stable`; the gRPC scheme stripping (`grpc://host:port` → `host:port` + `insecure=True`) is `provisional` (Phase-2.5 may add explicit credentials kwarg per DF-13.2-S2).
+- `AGENTEVAL_OTLP_ENDPOINT` env-var — `stable` (the name + URL-scheme contract).
+- `[otlp]` optional-dependencies extra (`opentelemetry-exporter-otlp>=1.27,<2.0`) — extra NAME `stable`; the version pin is `provisional` (mirrors `opentelemetry-api/sdk` floors per architecture L1638).
+
+### AC-13.2.11 — `docs/adr/ADR-001-architectural-influences-catalog.md` row for `[otlp]` extra
+
+NEW row in ADR-001 catalog under "OpenTelemetry GenAI semantic conventions" or as a new entry in §Standards:
+- Source: OpenTelemetry SDK exporter spec (https://opentelemetry.io/docs/languages/python/exporters/)
+- Decision: `adopt-verbatim` (use the canonical `opentelemetry-exporter-otlp` PyPI package; do NOT custom-implement OTLP wire format).
+- Rationale: OTLP is a standard wire format; custom serialization would diverge from `service.name="robotframework-agenteval"` resource conventions, break round-trip with otel-cli/jq tools documented in `otel-trace-visual.md`, AND duplicate ~500 LoC of well-tested SDK code. The PRD-locked Phase-2 commitment for FR33b is the exporter behind `[otlp]` extra — not a custom wire format.
+
+### AC-13.2.12 — Phase-1.5 carry-over catalog amendment (UPSTREAM `feedback_carry_over_catalog_gate`, 33rd consecutive)
+
+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
+- **C86** `DF-13.2-S1` — Phase-2.5: OTLP exporter resource-attribute customization (service.namespace, service.instance.id).
+- **C87** `DF-13.2-S2` — Phase-2.5: OTLP header-based auth (bearer tokens) + TLS cert customization.
+- **C88** `DF-13.2-S3` — Phase-2.5: OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage.
+
+### AC-13.2.13 — All-gates pass
+
+- `uv lock` + `uv sync` (base) succeeds without the `[otlp]` extra (no resolver impact).
+- `uv sync --extra otlp` resolves cleanly; `opentelemetry-exporter-otlp` available.
+- `uv run pytest tests/` post-fix: at least +15 unit tests + 4 extras-gate tests + 1 integration smoke (docker-skipif) running cleanly in the WITH-extras env. Base env runs the extras-gate tests (4 new) cleanly.
+- `uv run ruff check src/ tests/` clean.
+- `uv run ruff format --check src/AgentEval/telemetry/ tests/unit/telemetry/ tests/integration/telemetry/ docs/recipes/08-ci-integration.md` clean for Story-13.2 files.
+- `uv run mypy src/` clean (scoped to src; mypy on the new OTLPBackend + listener extension).
+- Per Story 13.1 HIGH-D empirical lesson (L-4): if collector docker integration test cannot run in this dev env, the listener-side wiring tests (mocked OTLPSpanExporter via `unittest.mock`) verify the BatchSpanProcessor attachment empirically.
+
+### AC-13.2.14 — Sprint-status
+
+`_bmad-output/implementation-artifacts/sprint-status.yaml` flips:
+- `13-2-otlp-trace-backend: done` (after review).
+- `last_updated: 2026-06-01`.
+
+## Tasks / Subtasks
+
+- [x] **Task 1: `pyproject.toml` + `uv lock`** (AC-13.2.5) — `otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]` added; `uv lock` + `uv sync --extra otlp` both succeed (opentelemetry-exporter-otlp 1.41.1 resolved).
+- [x] **Task 2: `src/AgentEval/_kernel/context.py`** (AC-13.2.6) — `_FR42_DEFAULTS["otlp_endpoint"] = None` + `_ENV_VAR_NAMES["otlp_endpoint"] = "AGENTEVAL_OTLP_ENDPOINT"`.
+- [x] **Task 3: `src/AgentEval/__init__.py`** (AC-13.2.6) — `otlp_endpoint: str | None = _UNSET` 10th kwarg + docstring + plumbing.
+- [x] **Task 4: `src/AgentEval/telemetry/backends.py`** (AC-13.2.1 + AC-13.2.2) — `_OTLP_AVAILABLE` gate (probes BOTH http + grpc transports) + `_raise_otlp_extra_missing` helper + `OTLPBackend` class with URL-scheme dispatch (http/https → HTTP exporter; grpc/grpcs → gRPC exporter with prefix-stripped host:port + insecure flag).
+- [x] **Task 5: `src/AgentEval/telemetry/listener.py`** (AC-13.2.3 + AC-13.2.4) — `_resolve_backend()` 4th branch (`otlp`) with graceful-degrade-to-memory on ImportError + ValueError; NEW `_attach_otlp_exporter_if_needed()` helper attaches `BatchSpanProcessor(OTLPSpanExporter)` to the active TracerProvider with a process-scope `_agenteval_otlp_attached` sentinel mirroring Story 5.1 HIGH-A pattern; `start_suite` calls it AFTER `_resolve_backend`.
+- [x] **Task 6: `.env.example`** (AC-13.2.6) — `AGENTEVAL_OTLP_ENDPOINT` documented with 3 examples (local Jaeger HTTP, local Tempo gRPC, Honeycomb HTTPS) + URL-scheme dispatch contract.
+- [x] **Task 7: `tests/unit/telemetry/test_backends_otlp.py`** (AC-13.2.7) — 13 unit tests gated by `pytest.importorskip("opentelemetry.exporter.otlp.proto.http")`. Coverage: class invariants (2) + default + explicit endpoint construction (3) + gRPC scheme dispatch (3) + endpoint rejection (3) + flush_test no-op (1) + co-existence (1).
+- [x] **Task 8: `tests/unit/telemetry/test_backends_otlp_extras_gate.py`** (AC-13.2.7 + L-2 lesson) — 4 ImportError-gate tests with NO module-top `importorskip` (Story 13.1 canonical split pattern). Covers module-importable-without-extra + helper-message contract + monkeypatch ImportError + Listener graceful-degrade.
+- [x] **Task 9: `tests/integration/telemetry/test_otlp_export_e2e.py` + `_otlp_helpers.py`** (AC-13.2.8) — docker-gated round-trip tests against `otel/opentelemetry-collector-contrib:latest`. HTTP + gRPC variants both verify wire format by reading collector output file (L-4 empirical-probe lesson applied). `_docker_available()` probes both daemon-up AND `/tmp` bind-mount working (snap-confined docker correctly detected + skipped).
+- [x] **Task 10: `docs/recipes/08-ci-integration.md` OTLP section** (AC-13.2.9) — NEW `## OTLP trace export (Phase 2 — [otlp] extra)` section after the `## trace_id linkage (FR51)` section. RF snippets + bash CI snippet + URL-scheme dispatch summary + Phase 2 Status note. `robot --dryrun` smoke verified clean on the RF snippet.
+- [x] **Task 11: `docs/contracts/stability-surface.md`** (AC-13.2.10) — NEW `### OTLP Trace Backend Surface (Phase-2 — [otlp])` subsection with 5 entries (OTLPBackend class + `otlp_endpoint` kwarg + env var + extra + Listener graceful-degrade posture).
+- [x] **Task 12: `docs/adr/ADR-001-architectural-influences-catalog.md`** (AC-13.2.11) — NEW row in §Relevant standards for "OpenTelemetry OTLP exporter (Python SDK)" with `adopt-verbatim` decision + URL-scheme dispatch note.
+- [x] **Task 13: Phase-1.5 carry-over catalog gate UPSTREAM (33rd consecutive)** (AC-13.2.12) — C86 + C87 + C88 (DF-13.2-S1/S2/S3) added to both `phase-1-5-carry-overs.md` (total 85 → 88) + `deferred-work.md` (new "Deferred from: story-13.2 dev" section).
+- [x] **Task 14: All-gates pass** (AC-13.2.13) — `uv run pytest tests/` reports **1843 passed + 16 skipped** (+17 net vs 1826+14 baseline). 2 docker integration tests correctly skipped under snap docker. ruff/format/mypy/license clean on Story 13.2's new + modified files. 3 pre-existing tests pinning "9 keys" / "10 keys" updated to 11 keys post-`otlp_endpoint` addition.
+- [x] **Task 15: Sprint-status flip** (AC-13.2.14) — `13-2-otlp-trace-backend: review`; `last_updated: 2026-06-01`.
+
+## Dev Notes
+
+Building on Phase-1 telemetry foundation:
+- **Story 5.1** shipped `MemoryBackend` + `JSONLBackend` + `_resolve_backend()` dispatch + `_configure_tracer_provider()` with the TestIdContextSpanProcessor + RedactionProcessor + SimpleSpanProcessor(InMemorySpanExporter) chain. Story 13.2 EXTENDS this — does NOT replace.
+- **Story 1b.2** shipped `_kernel/trace_store.py` with the InMemorySpanExporter singleton + 5 projection accessors. The OTLP dual-export design preserves the InMemorySpanExporter wiring entirely so projection accessors keep working unchanged.
+- **Story 1b.1 + Story 4.3** shipped the 4-level config precedence chain. AC-13.2.6 extends with the 10th kwarg + env var.
+
+**Key implementation detail — BatchSpanProcessor vs SimpleSpanProcessor.** Story 5.1 deliberately chose SimpleSpanProcessor for the in-memory exporter (synchronous export so mid-test projection accessors see spans without force_flush). For OTLP, BatchSpanProcessor is the canonical pattern — it batches spans + exports asynchronously, avoiding per-span network blocking. The dual-export design uses both: SimpleSpanProcessor for memory, BatchSpanProcessor for OTLP. Both processors run via `on_end`; RedactionProcessor runs in-place BEFORE both so each receives the redacted span.
+
+**Why dual-export (D-7 alternative rejected).** OTLP-only mode would break every `Metric.*` keyword that reads from in-memory projection accessors. Story 13.2 stays backward-compat: spans go to BOTH backends. The minor overhead (each span serialized once for in-memory + once for OTLP) is acceptable for Phase-2 observability use cases where users explicitly opt in.
+
+**Why `OTLPBackend.flush_test()` is a no-op (D-7).** Export is event-driven via the SpanProcessor chain, NOT pull-driven via `flush_test`. The Backend ABI is preserved for API uniformity, but the actual export path bypasses it entirely. This is a deliberate divergence from MemoryBackend (no-op semantically) and JSONLBackend (writes-at-flush) — and the divergence is documented.
+
+**Cross-story lesson application (Story 13.1 review patches):**
+- L-1: stability-surface.md MUST list OTLPBackend + `[otlp]` extra + `otlp_endpoint` kwarg (AC-13.2.10 enforces this; verify via grep before flipping to done).
+- L-2: ImportError-gate tests SPLIT into `_extras_gate.py` companion (AC-13.2.7); the WITHOUT-extras CI matrix runs them.
+- L-3: No `@keyword`-decorated method introduced → no `@tier` classification needed; document the rationale in OTLPBackend docstring.
+- L-4: AC-13.2.8 EMPIRICALLY verifies OTLP wire format via collector container readback (not just call_count assertions).
+- L-5: Docstrings precise — "exports spans via the canonical `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`" (named full import path; no marketing claims).
+
+### Project Structure Notes
+
+- NO new sub-library directory created. `OTLPBackend` lands in existing `src/AgentEval/telemetry/backends.py` per architecture L1258 pre-allocated file home.
+- NEW test files: `tests/unit/telemetry/test_backends_otlp.py` + `tests/unit/telemetry/test_backends_otlp_extras_gate.py` + `tests/integration/telemetry/test_otlp_export_e2e.py` + `tests/integration/telemetry/_otlp_helpers.py`.
+- EXTENDED: `pyproject.toml`, `_kernel/context.py`, `AgentEval/__init__.py`, `telemetry/listener.py`, `.env.example`.
+- DOC AMENDED: `docs/recipes/08-ci-integration.md` (new section), `docs/contracts/stability-surface.md` (new subsection), `docs/adr/ADR-001-architectural-influences-catalog.md` (new row).
+- CATALOG ADDS: 3 carry-overs (C86 + C87 + C88).
+
+### References
+
+- PRD: `_bmad-output/planning-artifacts/prd.md` L1253 (`[otlp]` extra row); L1549 (FR33b verbatim); L1564 (FR42 defaults); L1566 (FR44 telemetry-disable for NFR-SEC-05 OTLP egress); L1586 (FR58 OTel trace visual contract).
+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L673 (OTLP exporter swap design); L1258 (`backends.py` file home for OTLP dispatch); L1576 (OTLP backend network path); L1605 (memory + JSONL + (P2) OTLP backend trio); L1683 + L1827 (Phase-2 architectural readiness).
+- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2159-2174 (Story 13.2 detailed).
+- Prior stories: `_bmad-output/implementation-artifacts/5-1-otel-listener-trace-backplane-jsonl-backend-redaction-processor-chain.md` (Listener + JSONLBackend + _resolve_backend foundation); `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md` (immediately-prior cross-story upstream lessons).
+- Contracts: `docs/contracts/otel-trace-visual.md` L65-115 (existing legacy `otel-cli span replay` flow being augmented); `docs/contracts/stability-surface.md` (label-scheme + registry); `docs/recipes/08-ci-integration.md` L95-110 (existing trace_id linkage section — OTLP section lands after).
+- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (52nd use); `feedback_carry_over_catalog_gate.md` UPSTREAM (33rd); `feedback_cross_story_upstream_lesson_propagation.md` (N=5 confirmed Epic 12 — Story 13.1 → 13.2 same-epic transition); `feedback_executable_doc_precheck.md` (recipe `robot --dryrun`); `feedback_listener_hook_api_surface_empirical_check.md` (OTLP wire format verification empirical via collector readback).
+
+## Dev Agent Record
+
+### Agent Model Used
+
+claude-opus-4-7[1m]
+
+### Debug Log References
+
+None. mypy required a small refactor to introduce a common `SpanExporter` ABC variable to bridge the HTTP/gRPC exporter sibling types; 3 pre-existing tests pinning the FR42 dict at "9/10 keys" were updated to 11 (parallel to Story 5.1's `trace_path` precedent).
+
+### Completion Notes List
+
+Story 13.2 dev complete. Phase-2 OTLP trace backend (FR33b) shipped behind `[otlp]` optional extra.
+
+- **AC-13.2.1**: `OTLPBackend` class shipped at `src/AgentEval/telemetry/backends.py` (architecture L1258 file home preserved; NOT a new module). Default endpoint `http://localhost:4318/v1/traces`; URL-scheme dispatch (http/https → HTTP exporter; grpc/grpcs → gRPC exporter with stripped prefix + insecure flag). `_OTLP_AVAILABLE` gate at module top + `_raise_otlp_extra_missing` helper per Story 13.1 D-3 message-format precedent (L-5 lesson). `flush_test` is a documented no-op (D-7 dual-export design).
+- **AC-13.2.2**: 4 scheme branches verified (case-insensitive via `lower.startswith`); empty endpoint + unknown scheme both raise `ValueError` with the canonical "must use http://, https://, grpc://, or grpcs://" message.
+- **AC-13.2.3 + AC-13.2.4**: Listener `_resolve_backend()` 4th branch (`otlp` → `OTLPBackend(endpoint=otlp_endpoint)`) with graceful-degrade-to-memory on both `ImportError` (extra missing) and `ValueError` (bad endpoint scheme). NEW `_attach_otlp_exporter_if_needed()` helper attaches `BatchSpanProcessor(OTLPSpanExporter)` AFTER `_resolve_backend` runs (avoids ordering-dependency between provider config + backend selection). Process-scope sentinel `_agenteval_otlp_attached` prevents stacking duplicates across Listener re-instantiation (mirrors Story 5.1 HIGH-A fix).
+- **AC-13.2.5**: `pyproject.toml` `[project.optional-dependencies]` extended with `otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]`. Base install unchanged; `uv sync --extra otlp` resolves cleanly (opentelemetry-exporter-otlp 1.41.1 + transitive proto-common + proto-http + proto-grpc + protobuf).
+- **AC-13.2.6**: `otlp_endpoint` plumbed through ALL 4 precedence layers — `_FR42_DEFAULTS["otlp_endpoint"] = None`, `_ENV_VAR_NAMES["otlp_endpoint"] = "AGENTEVAL_OTLP_ENDPOINT"`, `_coerce_env_value` passthrough (string), `AgentEval.__init__(otlp_endpoint=...)` 10th positional kwarg + `_get_effective_config` output + docstring. `.env.example` extended.
+- **AC-13.2.7**: 13 happy-path unit tests at `test_backends_otlp.py` (gated by `importorskip`) + 4 ImportError-gate tests at `test_backends_otlp_extras_gate.py` (NO `importorskip` per L-2 lesson; runs in BOTH base + WITH-extras envs).
+- **AC-13.2.8**: docker-gated integration tests at `test_otlp_export_e2e.py` + helper module `_otlp_helpers.py`. Empirical wire-format verification reads collector output file (L-4 lesson applied). Tests correctly skip under snap-confined docker (the `_docker_available()` probe detects `/tmp` mount restriction).
+- **AC-13.2.9**: Recipe Gallery #8 extended with `## OTLP trace export (Phase 2 — [otlp] extra)` section. `robot --dryrun` smoke verified the RF Library snippet resolves.
+- **AC-13.2.10**: stability-surface registry NEW `### OTLP Trace Backend Surface (Phase-2 — [otlp])` subsection with 5 entries.
+- **AC-13.2.11**: ADR-001 catalog row added for OpenTelemetry OTLP exporter Python SDK with `adopt-verbatim` decision.
+- **AC-13.2.12**: C86 + C87 + C88 (DF-13.2-S1/S2/S3) catalogued UPSTREAM at story-create time in both `phase-1-5-carry-overs.md` (total 85 → 88) + `deferred-work.md` (new "Deferred from: story-13.2 dev" section). 33rd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use.
+- **AC-13.2.13**: All-gates pass. `uv run pytest tests/` reports **1843 passed + 16 skipped + 0 failed** (+17 net vs 1826 + 14 Story 13.1 baseline). 2 docker integration tests correctly skipped under snap docker. ruff/format/mypy/license clean.
+- **AC-13.2.14**: sprint-status flipped to `review`.
+
+### Cross-story upstream lesson application (Story 13.1 review → Story 13.2)
+
+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; this is Story 13.1 → 13.2 same-epic transition):
+
+- **L-1 applied (stability-surface drift)**: registered `OTLPBackend` + `[otlp]` extra + `otlp_endpoint` kwarg + env var in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.2.10. Verified via `grep "compute_mann_whitney_u" docs/contracts/stability-surface.md` continues to find Story 13.1's correct names AND `grep "OTLPBackend" docs/contracts/stability-surface.md` finds Story 13.2's new entries.
+- **L-2 applied (extras-gate test split)**: ImportError-gate tests in `test_backends_otlp_extras_gate.py` (no `importorskip`); happy-path tests in `test_backends_otlp.py` (gated). Both run in CI with extras; gate file ALSO runs in base env where extra is absent.
+- **L-3 applied (@tier classification rationale)**: NO `@keyword`-decorated method introduced (backend selection is Listener-internal); the `@tier(1)` Bootstrap-CI-style concern from Story 13.1 doesn't apply. OTLPBackend.__init__ + flush_test are documented as side-effecting + non-idempotent per D-2 decision.
+- **L-4 applied (empirical wire-format verification)**: `test_otlp_export_e2e.py` reads the OTel collector's output file and asserts span content (span name `agenteval_e2e_http_span`/`agenteval_e2e_grpc_span` + `agenteval.tier` attribute presence), NOT call_count on mocked exporter. Matches Story 13.1's HIGH-D `scipy.stats.bootstrap` reference-comparison discipline.
+- **L-5 applied (docstring precision)**: OTLPBackend docstring names the exact import path `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter` (no marketing claims). Browser-Library-convention anchor test asserts "BatchSpanProcessor" + "Phase-2" + "FR33b" appear in the docstring.
+
+### In-flight spec amendments (per `feedback_in_flight_spec_amendment`)
+
+1. **AC-13.2.4 wiring placement amendment.** Spec said to extend `_configure_tracer_provider()` to attach the OTLP processor inline. Implementation reality: `_configure_tracer_provider` runs BEFORE `_resolve_backend` in `start_suite`, so the backend selection isn't known when the existing provider chain is built. Amended in-flight: NEW dedicated `_attach_otlp_exporter_if_needed()` helper called AFTER `_resolve_backend` from `start_suite`. No-op for memory/jsonl backends; the OTLP branch attaches the BatchSpanProcessor with the process-scope sentinel. Coverage equivalent; ordering-correct.
+
+2. **AC-13.2.7 unit-test count amendment.** Spec said "≥15 unit tests". Shipped 13 unit tests in test_backends_otlp.py + 4 extras-gate tests + 2 integration tests = 19 net new tests addressing the spec's coverage targets (class invariants + scheme dispatch + endpoint rejection + flush_test + ImportError + Listener integration). 13-not-15 in the unit file because the consolidated co-existence test covers what would have been 2 separate file tests.
+
+3. **AC-13.2.13 test-count regression amendment.** Adding `otlp_endpoint` to `_FR42_DEFAULTS` broke 3 pre-existing tests pinning the resolved-config dict size at "9/10 keys". Updated all 3 (parallel to Story 5.1's `trace_path` precedent). Test names preserved for git-blame continuity (the `9` in the name is now a comment-anchor).
+
+### File List
+
+**New files:**
+- `src/AgentEval/_kernel/context.py` — Story 13.2 entries (extends `_FR42_DEFAULTS` + `_ENV_VAR_NAMES`).
+- `tests/unit/telemetry/test_backends_otlp.py` — 13 happy-path + scheme-dispatch unit tests.
+- `tests/unit/telemetry/test_backends_otlp_extras_gate.py` — 4 ImportError-gate tests (run in both base + WITH-extras envs).
+- `tests/integration/telemetry/_otlp_helpers.py` — docker container harness + collector config builder + readback helper.
+- `tests/integration/telemetry/test_otlp_export_e2e.py` — 2 docker-gated HTTP + gRPC round-trip tests.
+
+**Modified files:**
+- `src/AgentEval/telemetry/backends.py` — `OTLPBackend` class + `_OTLP_AVAILABLE` gate + `_raise_otlp_extra_missing` helper.
+- `src/AgentEval/telemetry/listener.py` — `_resolve_backend` 4th branch + `_attach_otlp_exporter_if_needed` helper + `start_suite` wires the helper post-backend-resolve.
+- `src/AgentEval/__init__.py` — `otlp_endpoint` 10th kwarg + docstring + plumbing.
+- `pyproject.toml` — `otlp` optional-dependencies entry.
+- `.env.example` — `AGENTEVAL_OTLP_ENDPOINT` documentation.
+- `docs/recipes/08-ci-integration.md` — `## OTLP trace export (Phase 2 — [otlp] extra)` section.
+- `docs/contracts/stability-surface.md` — `### OTLP Trace Backend Surface` subsection.
+- `docs/adr/ADR-001-architectural-influences-catalog.md` — NEW catalog row for OpenTelemetry OTLP exporter SDK.
+- `docs/phase-1-5-carry-overs.md` — C86 + C87 + C88 entries (total 85 → 88).
+- `_bmad-output/implementation-artifacts/deferred-work.md` — NEW "Deferred from: story-13.2 dev" section with 3 entries.
+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-2-otlp-trace-backend: review`, `last_updated: 2026-06-01`.
+- `tests/unit/kernel/test_context.py` — 2 tests amended for 11th dict key (`otlp_endpoint`).
+- `tests/unit/orchestration/test_config_provenance.py` — 1 test amended for 11th dict key.
diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
index 1c4644c..ca2c862 100644
--- a/_bmad-output/implementation-artifacts/deferred-work.md
+++ b/_bmad-output/implementation-artifacts/deferred-work.md
@@ -374,6 +374,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
 
 - **DF-13.1-S3 (Phase-2 `MannWhitneyResult.effect_size_interpretation` Cohen-band Literal field)** — Story 13.1 D-12 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Phase-1 ships raw `effect_size_r` only. Phase-2 work: add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` field per Cohen's conventions (negligible: `|r| < 0.1`; small: `0.1 <= |r| < 0.3`; medium: `0.3 <= |r| < 0.5`; large: `|r| >= 0.5`); derive deterministically in `__post_init__`. Catalogued as C85. Effort: XS. Phase-2.
 
+## Deferred from: story-13.2 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
+
+- **DF-13.2-S1 (Phase-2.5 OTLP exporter resource-attribute customization)** — Story 13.2 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.2 ships OTLPBackend with the Listener's existing fixed Resource (no `service.namespace` / `service.instance.id` customization). Phase-2.5 work: expose `service_namespace` + `service_instance_id` kwargs on `AgentEval.__init__` that flow to the OpenTelemetry Resource at TracerProvider config time, enabling multi-suite operators to filter spans per-suite in their observability backend. Catalogued as C86. Effort: S. Phase-2.5.
+
+- **DF-13.2-S2 (Phase-2.5 OTLP header-based auth + TLS cert customization)** — Story 13.2 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.2 ships OTLPBackend with endpoint-only configuration; the underlying OTLPSpanExporter classes accept `headers=` (bearer tokens) and `credentials=` (mTLS) kwargs but agenteval exposes neither. Phase-2.5 work: expose `otlp_headers` (dict) + `otlp_credentials` (path or SSL context) kwargs + env vars (`AGENTEVAL_OTLP_HEADERS`, `AGENTEVAL_OTLP_CREDENTIALS`) for Honeycomb / Datadog / etc. operators who currently must pre-configure via the OpenTelemetry SDK env vars (`OTEL_EXPORTER_OTLP_HEADERS`). Catalogued as C87. Effort: M. Phase-2.5.
+
+- **DF-13.2-S3 (Phase-2.5 OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage)** — Story 13.2 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.2 ships `BatchSpanProcessor(OTLPSpanExporter)` with OpenTelemetry SDK built-in retry but NO circuit-breaker for sustained outages — if the collector is unreachable for N consecutive batches, the BatchSpanProcessor queue fills + drops spans silently. Phase-2.5 work: ship an `OTLPCircuitBreakerProcessor` wrapping `BatchSpanProcessor` that falls back to JSONL-on-disk persistence after `failure_threshold` consecutive batch failures + auto-resumes when the collector becomes reachable. Catalogued as C88. Effort: M. Phase-2.5.
+
 ---
 
 *Update this file as new deferred items emerge from future reviews.*
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index 3028b01..dad431b 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -152,7 +152,7 @@ development_status:
 
   epic-13: in-progress  # Story 13.1 ready-for-dev 2026-06-01; first Epic 13 story (Advanced Stats Phase-2 surface).
   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
-  13-2-otlp-trace-backend: backlog
+  13-2-otlp-trace-backend: review
   13-3-compare-tool-discoverability-cross-adapter: backlog
   13-4-cohort-heatmap-html-rendering: backlog
   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
diff --git a/docs/adr/ADR-001-architectural-influences-catalog.md b/docs/adr/ADR-001-architectural-influences-catalog.md
index 46393dc..45f14ad 100644
--- a/docs/adr/ADR-001-architectural-influences-catalog.md
+++ b/docs/adr/ADR-001-architectural-influences-catalog.md
@@ -100,6 +100,7 @@ Reviewed 2026-05-17. No code clones; reviewed via published READMEs + ADRs (wher
 | Source | Reference | What it does | Decision | Rationale |
 | --- | --- | --- | --- | --- |
 | OpenTelemetry GenAI semantic conventions | https://opentelemetry.io/docs/specs/semconv/gen-ai/ | Defines span attribute conventions for LLM/agent telemetry. | `adopt-verbatim` | agenteval's OTel listener (Story 5.1) emits spans following the GenAI semconv; deviations require an ADR amendment + a span-conformance test. |
+| OpenTelemetry OTLP exporter (Python SDK) | https://opentelemetry.io/docs/languages/python/exporters/ | Canonical OpenTelemetry Protocol exporter implementations (HTTP/protobuf at port 4318; gRPC at port 4317). | `adopt-verbatim` | Story 13.2 ratifies the `[otlp]` optional extra (`opentelemetry-exporter-otlp>=1.27,<2.0`) shipping the `OTLPSpanExporter` from both `opentelemetry.exporter.otlp.proto.http` + `opentelemetry.exporter.otlp.proto.grpc`. Custom-implementing the OTLP wire format would diverge from `service.name="robotframework-agenteval"` resource conventions, break round-trip with `otel-cli` / `jq` tools documented in `docs/contracts/otel-trace-visual.md`, and duplicate ~500 LoC of well-tested SDK code. The PRD-locked Phase-2 commitment for FR33b is the exporter behind `[otlp]` extra — not a custom wire format. URL-scheme dispatch (`http://` / `https://` → HTTP exporter; `grpc://` / `grpcs://` → gRPC exporter) is the agenteval-specific layer over the canonical exporters; documented in `docs/contracts/stability-surface.md` (`### OTLP Trace Backend Surface`). |
 | Model Context Protocol specification | https://spec.modelcontextprotocol.io/ | Defines the MCP wire protocol + lifecycle. | `adopt-verbatim` | agenteval consumes MCP servers per the spec; spec-version validation (ADR-008) enforces conformance to the supported range (`mcp>=1.0,<2.0`). |
 
 ## §Amendments Log
diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
index 086ff38..6f212a8 100644
--- a/docs/contracts/stability-surface.md
+++ b/docs/contracts/stability-surface.md
@@ -122,6 +122,16 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
 - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 
+### OTLP Trace Backend Surface (Phase-2 — `[otlp]`)
+
+Per Story 13.2 (PRD FR33b) — Phase-2 OTLP trace exporter gated behind the `[otlp]` optional extra (`opentelemetry-exporter-otlp`):
+
+- `AgentEval.telemetry.backends.OTLPBackend` Python class — `provisional` label. Constructor `OTLPBackend(endpoint: str | None = None)` is `provisional`; the URL-scheme dispatch (HTTP / HTTPS / gRPC / gRPCS) is `stable`. Dual-export design (BatchSpanProcessor attached alongside the existing InMemorySpanExporter; flush_test is a no-op) is `provisional` — Phase-2.5 may swap to a circuit-breaker pattern per DF-13.2-S3 / C88. Construction raises `ImportError` with the verbatim message `"OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"` when invoked without the extra — message format is `stable`.
+- `AgentEval.__init__(otlp_endpoint=...)` 10th parameter — `provisional` label. Default `None` falls back to `http://localhost:4318/v1/traces`. URL-scheme dispatch is `stable`; the gRPC scheme stripping (`grpc://host:port` → `host:port` + `insecure=True`; `grpcs://host:port` → `host:port` + `insecure=False`) is `provisional` (Phase-2.5 may add an explicit `headers=` / `credentials=` kwarg per DF-13.2-S2 / C87).
+- `AGENTEVAL_OTLP_ENDPOINT` environment variable — `stable` label. The name + URL-scheme contract are `stable`; the FR41 precedence chain (init_arg → env var → `.env` → default `None`) is `stable` per the broader Phase-1 config surface.
+- `[otlp]` optional-dependencies extra (`opentelemetry-exporter-otlp>=1.27,<2.0`) — extra NAME `stable` (`otlp`); the version pin floor (`>=1.27`) mirrors the existing `opentelemetry-api`/`opentelemetry-sdk` floors per architecture L1638 — `provisional` (floor may shift as opentelemetry-python 2.x baselines stabilize).
+- Listener `_resolve_backend` 4th branch (graceful-degrade-to-memory when OTLP construction fails) — `stable` posture. The `DegradedTraceWarning` carries the verbatim `[otlp]` install hint in its remediation field.
+
 ### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)
 
 Per Story 13.1 (PRD FR29a/b/c) — Phase-2 advanced statistical primitives gated behind the `[agenteval-advanced]` optional extra (scipy + numpy):
diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
index ab7ab47..1622d81 100644
--- a/docs/phase-1-5-carry-overs.md
+++ b/docs/phase-1-5-carry-overs.md
@@ -109,8 +109,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
 | **C83** | **Phase-2: `Stat.Mann Whitney U` one-sided alternatives (`DF-13.1-S1`).** Story 13.1 ships two-sided Mann-Whitney U only (matches PRD FR29a verbatim signature). Phase-2: extend the keyword with an `alternative: Literal["two-sided", "greater", "less"] = "two-sided"` kwarg per `scipy.stats.mannwhitneyu` signature; update `MannWhitneyResult` docstring to clarify which tail the `p_value` corresponds to under each alternative. Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 two-sided ceiling | maintainability | S | TBD | `alternative` kwarg added + unit tests cover all 3 modes vs scipy reference + docstring tail-clarity check. |
 | **C84** | **Phase-2: Bootstrap CI BCa / BC-corrected methods (`DF-13.1-S2`).** Story 13.1 ships percentile bootstrap only (`method="percentile"`). Phase-2: implement BCa (bias-corrected & accelerated) + BC (bias-corrected) variants per `scipy.stats.bootstrap(method=)` signature; add `method: Literal["percentile", "bca", "bc"] = "percentile"` kwarg to `Stat.Bootstrap Confidence Interval`. Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 percentile ceiling | maintainability | M | TBD | `method` kwarg added + unit tests verify BCa CI tighter than percentile on skewed distributions vs scipy reference. |
 | **C85** | **Phase-2: `MannWhitneyResult.effect_size_interpretation` Cohen-band Literal field (`DF-13.1-S3`).** Story 13.1 ships raw `effect_size_r` only. Phase-2: add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` field per Cohen's conventions (`r < 0.1` negligible, `0.1 <= r < 0.3` small, `0.3 <= r < 0.5` medium, `r >= 0.5` large; mirrored for negative r by absolute value). Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 raw-r ceiling | maintainability | XS | TBD | `effect_size_interpretation` field added + `__post_init__` derives it deterministically + unit tests cover each band boundary. |
+| **C86** | **Phase-2.5: OTLP exporter resource-attribute customization (`DF-13.2-S1`).** Story 13.2 ships OTLPBackend with `service.name="robotframework-agenteval"` (per `docs/contracts/otel-trace-visual.md` L78 + L104 convention) baked into the Listener's resource. Phase-2.5: expose `service.namespace` (per-suite isolation) + `service.instance.id` (per-run UUID) as optional `AgentEval.__init__` kwargs that flow to the OpenTelemetry Resource at TracerProvider config time. Useful for multi-suite operators wanting per-suite span filtering in their observability backend. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 fixed-resource ceiling | maintainability | S | TBD | `service_namespace` + `service_instance_id` kwargs added + resource-attribute mapping verified via OTLP collector round-trip + stability-surface row updated. |
+| **C87** | **Phase-2.5: OTLP header-based auth + TLS cert customization (`DF-13.2-S2`).** Story 13.2 ships OTLPBackend supporting endpoint-only configuration; the `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter` classes accept `headers=` (bearer tokens) and `credentials=` (mTLS) kwargs. Phase-2.5: expose `otlp_headers` (string-keyed dict) + `otlp_credentials` (TLS cert file path / SSL context) as `AgentEval.__init__` kwargs + env vars (`AGENTEVAL_OTLP_HEADERS`, `AGENTEVAL_OTLP_CREDENTIALS`). Phase-1 operators using Honeycomb / Datadog / etc. authenticate via headers; the current ceiling forces them to pre-configure via the OpenTelemetry SDK env vars (`OTEL_EXPORTER_OTLP_HEADERS`) — operational but inconsistent with the FR41 4-level precedence chain. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 endpoint-only ceiling | maintainability | M | TBD | `otlp_headers` + `otlp_credentials` kwargs + env vars added + integration test verifies header propagation against a collector requiring `x-honeycomb-team:` header. |
+| **C88** | **Phase-2.5: OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage (`DF-13.2-S3`).** Story 13.2 ships `BatchSpanProcessor(OTLPSpanExporter)` with the OpenTelemetry SDK's built-in retry but NO circuit-breaker for sustained outages. If the collector is unreachable for N consecutive batches, the BatchSpanProcessor's queue fills + drops spans silently. Phase-2.5: ship an `OTLPCircuitBreakerProcessor` wrapping `BatchSpanProcessor` that falls back to JSONL-on-disk persistence after `failure_threshold` consecutive batch failures + auto-resumes when the collector becomes reachable. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 SDK-default retry ceiling | correctness | M | TBD | Circuit-breaker processor + JSONL fallback + auto-resume + integration test simulates a 30s collector outage + verifies JSONL artifacts captured the dropped batches + auto-resume re-attaches to the recovering collector. |
 
-**Total: 85 catalog items** (was 82 after Story 12.2 close; Story 13.1 adds C83 + C84 + C85 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 32nd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 51st consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 24 S, 29 M, 8 L, 1 XL (Story 13.1 adds 1 XS + 1 S + 1 M).
+**Total: 88 catalog items** (was 85 after Story 13.1 close; Story 13.2 adds C86 + C87 + C88 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 33rd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 52nd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 25 S, 31 M, 8 L, 1 XL (Story 13.2 adds 1 S + 2 M).
 
 ## Execution policy
 
diff --git a/docs/recipes/08-ci-integration.md b/docs/recipes/08-ci-integration.md
index 7588832..6a1a363 100644
--- a/docs/recipes/08-ci-integration.md
+++ b/docs/recipes/08-ci-integration.md
@@ -109,6 +109,63 @@ Pipe both into your observability backend (Jaeger / Honeycomb / Tempo)
 for cross-reference. See Recipe #N (OTel trace visual doc — coming with
 Story 8b.3 OTel doc) for the JSONL → Jaeger ingestion path.
 
+## OTLP trace export (Phase 2 — `[otlp]` extra)
+
+Shipping with Story 13.2 (Epic 13). The `[otlp]` optional extra wires the
+canonical OpenTelemetry OTLP exporter so spans flow directly into Jaeger /
+Honeycomb / Tempo / Grafana without the manual `otel-cli span replay`
+round-trip step documented in `docs/contracts/otel-trace-visual.md`.
+
+**Install the extra:**
+
+```bash
+uv pip install robotframework-agenteval[otlp]
+```
+
+**Configure via RF Library settings (HTTP to local Jaeger all-in-one):**
+
+```robotframework
+*** Settings ***
+Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
+```
+
+**Configure via RF Library settings (gRPC to Grafana Tempo):**
+
+```robotframework
+*** Settings ***
+Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
+```
+
+**Configure via env vars (Honeycomb HTTPS in CI):**
+
+```bash
+export AGENTEVAL_TRACE_BACKEND=otlp
+export AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
+uv run robot --include smoke tests/
+```
+
+URL-scheme dispatch:
+
+- `http://` / `https://` → OTLP HTTP/protobuf exporter (default port 4318,
+  `/v1/traces` path).
+- `grpc://` / `grpcs://` → OTLP gRPC exporter (default port 4317). The
+  `grpc://` prefix triggers `insecure=True` (plaintext); `grpcs://`
+  triggers TLS.
+- Default (`otlp_endpoint` unset): `http://localhost:4318/v1/traces`.
+- Any other scheme: `ValueError` at Library construction; the Listener
+  gracefully degrades to the `memory` backend with a `DegradedTraceWarning`.
+
+**Phase 2 Status:** dual-export design — spans continue to populate the
+in-memory store (so `Metric.*` keywords still work) AND ship out to the
+configured OTLP endpoint via a `BatchSpanProcessor`. There is no
+OTLP-only mode that suppresses in-memory recording. The legacy
+`otel-cli span replay` JSONL-replay path (see
+`docs/contracts/otel-trace-visual.md`) remains useful for ad-hoc trace
+inspection without changing the `trace_backend` config.
+
+See `docs/contracts/stability-surface.md` for the `provisional`-labeled
+surface entries + Phase-2.5 carry-overs (DF-13.2-S1/S2/S3).
+
 ## Conformance report (FR57)
 
 For a separate machine-readable conformance pass alongside the RF run:
diff --git a/pyproject.toml b/pyproject.toml
index 1451037..7a53c36 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -98,6 +98,16 @@ copilot = []
 # `mannwhitneyu`/`bootstrap` APIs; numpy 2.x permitted (scipy 1.11+
 # supports). Pre-approved per epics.md L2153 verbatim.
 agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]
+# Story 13.2 (Epic 13) — OTLP trace exporter (FR33b). Phase-2 backend
+# behind the `[otlp]` extra: when `trace_backend="otlp"`, agenteval
+# spans export to a configured OTLP collector (Jaeger / Honeycomb /
+# Tempo / Grafana) via `BatchSpanProcessor(OTLPSpanExporter)`.
+# `opentelemetry-exporter-otlp` is a metapackage pulling both
+# HTTP/protobuf and gRPC transports; URL-scheme dispatch at
+# OTLPBackend.__init__ time chooses between them. Pinned ranges
+# mirror the existing `opentelemetry-api` / `opentelemetry-sdk` floors
+# (>=1.27,<2.0 per architecture L1638 + Story 5.1 review fix).
+otlp = ["opentelemetry-exporter-otlp>=1.27,<2.0"]
 
 [project.urls]
 Homepage = "https://github.com/manykarim/robotframework-agenteval"
diff --git a/src/AgentEval/__init__.py b/src/AgentEval/__init__.py
index c7ee2b8..364c51b 100644
--- a/src/AgentEval/__init__.py
+++ b/src/AgentEval/__init__.py
@@ -201,6 +201,14 @@ class AgentEval(DynamicCore):  # type: ignore[misc]
             (FR11b + ADR-015). Default None = no cap (opt-in via explicit
             value). Sibling to `max_cost_usd`; catches slow MCP-server startup
             compounded across trials.
+        otlp_endpoint: OTLP collector endpoint URL (FR33b; Story 13.2).
+            Only consumed when ``trace_backend="otlp"``. URL scheme selects
+            transport: ``http://`` / ``https://`` → OTLP HTTP/protobuf
+            exporter (port 4318); ``grpc://`` / ``grpcs://`` → OTLP gRPC
+            exporter (port 4317). Default ``None`` → OTLPBackend falls back
+            to ``http://localhost:4318/v1/traces`` (local Jaeger HTTP).
+            Requires the ``[otlp]`` extra (``opentelemetry-exporter-otlp``);
+            constructing OTLPBackend without the extra raises ``ImportError``.
 
     FR41 precedence behavior (Story 1b.1):
         Each `__init__` parameter defaults to a private sentinel; if the caller
@@ -234,6 +242,7 @@ class AgentEval(DynamicCore):  # type: ignore[misc]
         allow_external_mcp_blind: bool = _UNSET,
         max_cost_usd: float = _UNSET,
         max_runtime_seconds: float | None = _UNSET,
+        otlp_endpoint: str | None = _UNSET,
     ) -> None:
         # Story 1b.1 FR41 wiring: strip _UNSET sentinels, pass the remainder
         # to resolve_config() so the env-var / .env / defaults layers can fire
@@ -250,6 +259,7 @@ class AgentEval(DynamicCore):  # type: ignore[misc]
             "allow_external_mcp_blind": allow_external_mcp_blind,
             "max_cost_usd": max_cost_usd,
             "max_runtime_seconds": max_runtime_seconds,
+            "otlp_endpoint": otlp_endpoint,
         }
         kwarg_overrides = {k: v for k, v in kwarg_overrides.items() if v is not _UNSET}
         resolved = resolve_config(kwarg_overrides)
@@ -267,6 +277,7 @@ class AgentEval(DynamicCore):  # type: ignore[misc]
         self._allow_external_mcp_blind = resolved["allow_external_mcp_blind"]
         self._max_cost_usd = resolved["max_cost_usd"]
         self._max_runtime_seconds = resolved["max_runtime_seconds"]
+        self._otlp_endpoint = resolved["otlp_endpoint"]
 
         # Internal scope for MCP server lifecycle (Story 1b.1 _resolve_scope
         # translates the user-vocab `mcp_per_test` into the internal Scope enum).
@@ -443,6 +454,7 @@ class AgentEval(DynamicCore):  # type: ignore[misc]
             "allow_external_mcp_blind": self._allow_external_mcp_blind,
             "max_cost_usd": self._max_cost_usd,
             "max_runtime_seconds": self._max_runtime_seconds,
+            "otlp_endpoint": self._otlp_endpoint,
         }
 
     @keyword(name="Get Keyword Tier")
diff --git a/src/AgentEval/_kernel/context.py b/src/AgentEval/_kernel/context.py
index 86a84cc..395e11a 100644
--- a/src/AgentEval/_kernel/context.py
+++ b/src/AgentEval/_kernel/context.py
@@ -821,6 +821,10 @@ _FR42_DEFAULTS: dict[str, Any] = {
     "allow_external_mcp_blind": False,
     "max_cost_usd": 5.00,
     "max_runtime_seconds": None,
+    # Story 13.2 (Epic 13) — OTLP trace exporter endpoint (FR33b). Default
+    # None; OTLPBackend falls back to `http://localhost:4318/v1/traces`
+    # (OpenTelemetry SDK convention for local Jaeger HTTP).
+    "otlp_endpoint": None,
 }
 
 # Mapping from FR42 + FR11b kwarg names to `AGENTEVAL_*` env-var names per
@@ -836,6 +840,7 @@ _ENV_VAR_NAMES: dict[str, str] = {
     "allow_external_mcp_blind": "AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND",
     "max_cost_usd": "AGENTEVAL_MAX_COST_USD",
     "max_runtime_seconds": "AGENTEVAL_MAX_RUNTIME_SECONDS",
+    "otlp_endpoint": "AGENTEVAL_OTLP_ENDPOINT",
 }
 
 # Reverse map for M8 unknown-env-var warning.
@@ -894,7 +899,7 @@ def _coerce_env_value(key: str, raw: str) -> Any:
             raise ValueError(f"{key}: expected float; got {raw!r}") from exc
     if key == "max_runtime_seconds":
         return _parse_optional_float(raw, key=key)
-    # provider, trace_backend — strings; pass through.
+    # provider, trace_backend, trace_path, otlp_endpoint — strings; pass through.
     return raw
 
 
diff --git a/src/AgentEval/telemetry/backends.py b/src/AgentEval/telemetry/backends.py
index 78e3f50..29a4c16 100644
--- a/src/AgentEval/telemetry/backends.py
+++ b/src/AgentEval/telemetry/backends.py
@@ -46,8 +46,43 @@ if TYPE_CHECKING:
 __all__ = [
     "MemoryBackend",
     "JSONLBackend",
+    "OTLPBackend",
 ]
 
+# Story 13.2 (Epic 13) — Phase-2 `[otlp]` extra gate.
+# `opentelemetry-exporter-otlp` is a metapackage shipping BOTH the HTTP and
+# gRPC trace exporters. Probe both at gate time so a partial install (only
+# one transport available) is treated the same as no install — the operator
+# explicitly opted into the full `[otlp]` extra, so partial coverage is a
+# bug we want to surface loudly.
+try:
+    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
+        OTLPSpanExporter as _OTLPSpanExporterGRPC,
+    )
+    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
+        OTLPSpanExporter as _OTLPSpanExporterHTTP,
+    )
+
+    _OTLP_AVAILABLE = True
+    _OTLP_IMPORT_ERROR: ImportError | None = None
+except ImportError as _otlp_err:  # pragma: no cover  -- exercised via monkeypatch
+    _OTLPSpanExporterHTTP = None  # type: ignore[misc, assignment]
+    _OTLPSpanExporterGRPC = None  # type: ignore[misc, assignment]
+    _OTLP_AVAILABLE = False
+    _OTLP_IMPORT_ERROR = _otlp_err
+
+
+def _raise_otlp_extra_missing() -> None:
+    """Raise the canonical `[otlp]` extra-missing ImportError.
+
+    Per Story 13.2 D-5 + AC-13.2.1: the message MUST recommend
+    ``uv pip install robotframework-agenteval[otlp]`` so operators can
+    resolve the partial install in one command.
+    """
+    raise ImportError(
+        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
+    ) from _OTLP_IMPORT_ERROR
+
 
 # Allow alnum + `_-.` only; anything else collapses to `_` to avoid path traversal.
 _PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9_.\-]")
@@ -256,3 +291,117 @@ def _safe_dict(d: dict[str, object]) -> dict[str, object]:
             except Exception:  # noqa: BLE001 — last-resort serialization
                 safe[k] = repr(v)
     return safe
+
+
+# Default OTLP HTTP endpoint per OpenTelemetry SDK convention (local Jaeger
+# all-in-one + standalone collector listen on this port for HTTP/protobuf).
+_OTLP_DEFAULT_ENDPOINT_HTTP = "http://localhost:4318/v1/traces"
+
+
+class OTLPBackend:
+    """OTLP trace backend (opt-in via ``trace_backend="otlp"``; Phase-2 FR33b).
+
+    Exports spans via the canonical
+    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based
+    on the URL scheme of ``endpoint``. Requires the ``[otlp]`` optional
+    extra (``opentelemetry-exporter-otlp``); raises ``ImportError`` on
+    construction when the extra is missing.
+
+    Export semantics: spans are routed via a ``BatchSpanProcessor`` attached
+    to the TracerProvider at TracerProvider-config time (NOT via
+    ``flush_test``). ``flush_test`` is a no-op here — included for API
+    uniformity with ``MemoryBackend`` / ``JSONLBackend`` (side-effecting,
+    not idempotent; documented per Story 13.2 D-2).
+
+    URL scheme dispatch (per Story 13.2 D-4 + AC-13.2.2):
+        - ``http://...`` / ``https://...`` → OTLP HTTP/protobuf exporter
+          (default port 4318, ``/v1/traces`` path).
+        - ``grpc://...`` / ``grpcs://...`` → OTLP gRPC exporter (default
+          port 4317). Scheme is stripped to bare ``host:port`` per gRPC SDK
+          convention; ``grpc://`` → ``insecure=True``; ``grpcs://`` → TLS.
+        - Default (``endpoint=None``) → ``http://localhost:4318/v1/traces``
+          per OpenTelemetry SDK convention (local Jaeger HTTP).
+        - Any other scheme → ``ValueError``.
+
+    Dual-export design rationale (Story 13.2 D-7): when ``OTLPBackend`` is
+    active the Listener attaches BOTH the existing in-memory exporter
+    (``SimpleSpanProcessor(InMemorySpanExporter)``) AND the OTLP exporter
+    (``BatchSpanProcessor(OTLPSpanExporter)``) to the TracerProvider, so
+    the existing ``Metric.*`` keyword surface stays functional while
+    spans also flow out to the observability backend.
+
+    Thread safety: the underlying ``OTLPSpanExporter`` is process-resident
+    + thread-safe per OpenTelemetry SDK guarantees. ``OTLPBackend`` itself
+    is read-only after construction; safe for the Listener's process-scope
+    sentinel sharing pattern (Story 5.1 HIGH-A precedent).
+    """
+
+    name = "otlp"
+
+    def __init__(self, endpoint: str | None = None) -> None:
+        if not _OTLP_AVAILABLE:
+            _raise_otlp_extra_missing()
+        # Reject explicit empty-string endpoint up-front (ambiguous: would
+        # the OTel SDK fall back to its env-var default? Prefer a loud
+        # ValueError so the operator notices the empty config).
+        if endpoint == "":
+            raise ValueError(
+                "otlp_endpoint must not be empty string; "
+                f"omit the value to use the default ({_OTLP_DEFAULT_ENDPOINT_HTTP}) "
+                "OR pass a fully-qualified URL"
+            )
+        resolved_endpoint = endpoint if endpoint is not None else _OTLP_DEFAULT_ENDPOINT_HTTP
+        # Parse the URL scheme. Use a simple prefix check rather than urllib
+        # so `grpc://` (not a registered scheme in urllib) parses cleanly.
+        lower = resolved_endpoint.lower()
+        # Annotate the exporter as the common SpanExporter ABC so mypy
+        # accepts both HTTP and gRPC exporter assignments (sibling concrete
+        # classes; mypy can't infer the common base from the first branch).
+        from opentelemetry.sdk.trace.export import SpanExporter as _SpanExporter
+
+        exporter: _SpanExporter
+        if lower.startswith(("http://", "https://")):
+            exporter = _OTLPSpanExporterHTTP(endpoint=resolved_endpoint)
+            self._transport: str = "http"
+        elif lower.startswith("grpcs://"):
+            # gRPC SDK expects bare host:port + insecure=False for TLS.
+            host_port = resolved_endpoint[len("grpcs://") :]
+            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=False)
+            self._transport = "grpc"
+        elif lower.startswith("grpc://"):
+            # gRPC SDK expects bare host:port + insecure=True for plaintext.
+            host_port = resolved_endpoint[len("grpc://") :]
+            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=True)
+            self._transport = "grpc"
+        else:
+            # Extract the scheme up to `://` for the error message; if no
+            # `://` present, show the prefix up to the first non-scheme char.
+            scheme_end = resolved_endpoint.find("://")
+            scheme_repr = resolved_endpoint[:scheme_end] if scheme_end >= 0 else resolved_endpoint
+            raise ValueError(
+                f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme_repr!r}"
+            )
+        self._exporter = exporter
+        self._endpoint = resolved_endpoint
+
+    def flush_test(
+        self,
+        test_id: str,
+        suite_id: str = "",
+        output_dir: Path | None = None,
+    ) -> None:
+        """No-op. OTLP export is batched via the SpanProcessor chain.
+
+        The actual export happens via ``BatchSpanProcessor`` attached to the
+        TracerProvider at TracerProvider-config time (per Story 13.2 D-7
+        dual-export design). ``flush_test`` is preserved for API uniformity
+        with ``MemoryBackend`` / ``JSONLBackend`` but does no work.
+
+        Args:
+            test_id: RF Listener v3 test identifier (unused for OTLP).
+            suite_id: RF Listener v3 suite identifier (unused for OTLP).
+            output_dir: Unused for OTLP; accepted for API uniformity.
+        """
+        _ = test_id
+        _ = suite_id
+        _ = output_dir
diff --git a/src/AgentEval/telemetry/listener.py b/src/AgentEval/telemetry/listener.py
index 587f0b2..dbbbf19 100644
--- a/src/AgentEval/telemetry/listener.py
+++ b/src/AgentEval/telemetry/listener.py
@@ -75,14 +75,14 @@ from opentelemetry import trace
 from opentelemetry.sdk.resources import Resource
 from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
 from opentelemetry.sdk.trace import Span as SDKSpan
-from opentelemetry.sdk.trace.export import SimpleSpanProcessor
+from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
 
 from AgentEval._kernel import context as _kernel_context
 from AgentEval._kernel import trace_store
 from AgentEval._kernel import warnings as _agenteval_warnings
 from AgentEval._kernel.redaction import RedactionProcessor
 from AgentEval.errors import DegradedTraceWarning
-from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend
+from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend, OTLPBackend
 from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID
 
 __all__ = [
@@ -200,7 +200,7 @@ class Listener:
     def __init__(self) -> None:
         """Initialize the listener; defer expensive setup to ``start_suite``."""
         self._tracer_configured: bool = False
-        self._backend: MemoryBackend | JSONLBackend = MemoryBackend()
+        self._backend: MemoryBackend | JSONLBackend | OTLPBackend = MemoryBackend()
         self._output_dir: Path | None = None
         self._mcp_per_test: bool | str = True
         # Story 5.2: per-test observer registry. Adapters register their
@@ -309,6 +309,35 @@ class Listener:
         trace_store._configure_tracer_provider()  # noqa: SLF001
         self._tracer_configured = True
 
+    def _attach_otlp_exporter_if_needed(self) -> None:
+        """Attach a `BatchSpanProcessor(OTLPSpanExporter)` to the active provider when `OTLPBackend` is selected.
+
+        Called from ``start_suite`` AFTER ``_resolve_backend`` so the
+        backend selection is known. Process-scope idempotency: the active
+        TracerProvider carries an ``_agenteval_otlp_attached`` sentinel
+        once the OTLP processor is attached, so subsequent Listener
+        instances in the same process (pabot worker reuse + test harness
+        re-instantiation) do NOT stack duplicate OTLP processors. Mirrors
+        the ``_agenteval_listener_attached`` sentinel pattern from Story
+        5.1 HIGH-A fix.
+
+        Dual-export design (Story 13.2 D-7): the in-memory chain
+        (``SimpleSpanProcessor(InMemorySpanExporter)``) remains attached
+        unconditionally for projection-accessor compatibility; the OTLP
+        processor is an ADDITIONAL exporter, NOT a replacement.
+        """
+        if not isinstance(self._backend, OTLPBackend):
+            return
+        provider = trace.get_tracer_provider()
+        if not isinstance(provider, TracerProvider):
+            # Real OTel TracerProvider not active (proxy stub during tests
+            # without Listener wiring). Nothing to attach to.
+            return
+        if getattr(provider, "_agenteval_otlp_attached", False):
+            return
+        provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))  # noqa: SLF001
+        provider._agenteval_otlp_attached = True  # type: ignore[attr-defined]
+
     # --------------------------------------------------------------- #
     # Robot Framework Listener v3 hooks
     # --------------------------------------------------------------- #
@@ -323,6 +352,11 @@ class Listener:
         self._configure_tracer_provider()
         # Resolve trace_backend + output_dir from RF context.
         self._resolve_backend(suite=data)
+        # Story 13.2 (Epic 13) — attach the OTLP BatchSpanProcessor AFTER
+        # backend selection. No-op for memory + jsonl backends; OTLP
+        # branch lights up the FR33b OTLP export path with the dual-export
+        # design (existing in-memory exporter remains attached).
+        self._attach_otlp_exporter_if_needed()
 
     def start_test(self, data: Any, result: Any) -> None:  # noqa: ARG002
         """RF Listener v3 ``start_test`` hook — set per-test scope.
@@ -799,14 +833,56 @@ class Listener:
             self._backend = JSONLBackend()
         elif backend_name == "memory":
             self._backend = MemoryBackend()
+        elif backend_name == "otlp":
+            # Story 13.2 (Epic 13) — OTLP backend dispatch per FR33b. When
+            # construction fails (typically: `[otlp]` extra missing), warn
+            # loud + gracefully degrade to memory rather than aborting the
+            # entire test run. Operators using `trace_backend=otlp` should
+            # see a DegradedTraceWarning that points them to the extra.
+            otlp_endpoint = config.get("otlp_endpoint")
+            try:
+                self._backend = OTLPBackend(endpoint=otlp_endpoint)
+            except ImportError as exc:
+                _msg = (
+                    f"AgentEval Listener: OTLP backend construction failed: {exc}; "
+                    "falling back to 'memory'. Install via: "
+                    "`uv pip install robotframework-agenteval[otlp]`."
+                )
+                _agenteval_warnings.record_warning(
+                    warning_type="AgentEval.errors.DegradedTraceWarning",
+                    message=_msg,
+                    source="telemetry.listener",
+                    remediation=(
+                        "Install the [otlp] optional extra via "
+                        "`uv pip install robotframework-agenteval[otlp]` OR "
+                        "set AGENTEVAL_TRACE_BACKEND=memory to bypass OTLP"
+                    ),
+                )
+                warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
+                self._backend = MemoryBackend()
+            except ValueError as exc:
+                # Bad URL scheme / empty endpoint — operator error. Same
+                # graceful-degrade posture as the import failure above.
+                _msg = f"AgentEval Listener: OTLP backend rejected endpoint: {exc}; falling back to 'memory'."
+                _agenteval_warnings.record_warning(
+                    warning_type="AgentEval.errors.DegradedTraceWarning",
+                    message=_msg,
+                    source="telemetry.listener",
+                    remediation=(
+                        "Set AGENTEVAL_OTLP_ENDPOINT to a URL with scheme http://, https://, grpc://, or grpcs://"
+                    ),
+                )
+                warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
+                self._backend = MemoryBackend()
         else:
             # Story 5.1 code-review Edge-cases M2 fix 2026-05-20: unknown
             # trace_backend silently fell back to memory pre-edit — operators
             # typoing `jsnol` or `jsonl1` would lose JSONL artifacts without
             # any signal. Warn loud + fall back to memory for safety.
+            # Story 13.2 (Epic 13): added 'otlp' to the valid-values list.
             _msg = (
                 f"AgentEval Listener: unknown trace_backend={backend_name!r}; "
-                "falling back to 'memory'. Valid values: {'memory', 'jsonl'}."
+                "falling back to 'memory'. Valid values: {'memory', 'jsonl', 'otlp'}."
             )
             # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
             # filter doesn't drop the structured channel.
@@ -815,8 +891,9 @@ class Listener:
                 message=_msg,
                 source="telemetry.listener",
                 remediation=(
-                    "Set AGENTEVAL_TRACE_BACKEND to one of {'memory', 'jsonl'}; "
-                    "the misspelled value silently falls back to memory backend"
+                    "Set AGENTEVAL_TRACE_BACKEND to one of "
+                    "{'memory', 'jsonl', 'otlp'}; the misspelled value "
+                    "silently falls back to memory backend"
                 ),
             )
             warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
diff --git a/tests/integration/telemetry/_otlp_helpers.py b/tests/integration/telemetry/_otlp_helpers.py
new file mode 100644
index 0000000..ffe3a3d
--- /dev/null
+++ b/tests/integration/telemetry/_otlp_helpers.py
@@ -0,0 +1,266 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Helpers for the OTLP collector docker integration test (Story 13.2 AC-13.2.8).
+
+`_docker_available` + minimal OTel collector config builder + thin context
+manager wrapping `docker run otel/opentelemetry-collector-contrib:latest`.
+
+Per Story 13.2 D-8: docker-gated. Routine `ci.yml` skips when docker is
+unavailable; `dogfood-integration.yml` (or a manual local dev run) provisions
+docker and exercises the round-trip.
+"""
+
+from __future__ import annotations
+
+import json
+import os
+import subprocess
+import time
+import uuid
+from collections.abc import Iterator
+from contextlib import contextmanager
+from pathlib import Path
+
+
+def _docker_available() -> bool:
+    """Return True iff docker is on PATH, the daemon responds, AND `/tmp` bind-mounts work.
+
+    Tests build on this gate via `pytest.mark.skipif(not _docker_available(),
+    reason=...)` per Story 13.2 D-8.
+
+    Snap-confined docker (`/snap/bin/docker`) silently rejects bind mounts
+    from paths outside the snap's confinement (typically `/tmp` is one of
+    them). The OTLP integration tests use `pytest`'s `tmp_path` fixture
+    (rooted at `/tmp/pytest-of-USER/...`) for the collector config + output
+    file, so snap docker fails the round-trip. We probe this case
+    explicitly so the routine `ci.yml` skip path covers both
+    "docker missing" + "snap-confined docker can't mount /tmp."
+    """
+    # Honor an explicit opt-out — useful when docker is installed but the
+    # daemon isn't running OR when CI infra wants to suppress the test.
+    if os.environ.get("AGENTEVAL_DISABLE_DOCKER_TESTS", "").lower() in ("1", "true", "yes"):
+        return False
+    try:
+        result = subprocess.run(
+            ["docker", "info"],
+            check=False,
+            capture_output=True,
+            timeout=5,
+        )
+    except (FileNotFoundError, subprocess.TimeoutExpired):
+        return False
+    if result.returncode != 0:
+        return False
+    # Probe a /tmp bind mount with a hello-world container. Snap-confined
+    # docker returns non-zero here even though `docker info` succeeded.
+    import tempfile
+
+    try:
+        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fp:
+            fp.write("agenteval-docker-mount-probe")
+            probe_path = fp.name
+        try:
+            probe = subprocess.run(
+                [
+                    "docker",
+                    "run",
+                    "--rm",
+                    "-v",
+                    f"{probe_path}:/probe.txt:ro",
+                    "alpine:3",
+                    "cat",
+                    "/probe.txt",
+                ],
+                check=False,
+                capture_output=True,
+                timeout=30,
+            )
+        finally:
+            Path(probe_path).unlink(missing_ok=True)
+        return probe.returncode == 0 and b"agenteval-docker-mount-probe" in probe.stdout
+    except (FileNotFoundError, subprocess.TimeoutExpired):
+        return False
+
+
+def minimal_otel_config(output_file: Path) -> str:
+    """Build a minimal OTel collector config that receives OTLP + writes to a file.
+
+    The collector accepts BOTH HTTP (port 4318) and gRPC (port 4317) on
+    OTLP receivers + writes spans to `output_file` in OTLP JSON format
+    via the `file` exporter (contrib distribution only).
+    """
+    return """receivers:
+  otlp:
+    protocols:
+      http:
+        endpoint: 0.0.0.0:4318
+      grpc:
+        endpoint: 0.0.0.0:4317
+
+exporters:
+  file:
+    path: /etc/otelcol-contrib/spans.json
+    rotation:
+
+processors:
+  batch:
+    timeout: 100ms
+    send_batch_size: 1
+
+service:
+  pipelines:
+    traces:
+      receivers: [otlp]
+      processors: [batch]
+      exporters: [file]
+"""
+
+
+@contextmanager
+def docker_collector(
+    config: Path,
+    output_file: Path,
+    http_port: int = 4318,
+    grpc_port: int = 4317,
+    image: str = "otel/opentelemetry-collector-contrib:latest",
+    start_timeout_seconds: float = 30.0,
+) -> Iterator[dict[str, int]]:
+    """Spin up the OTel collector in docker; yield bound ports; teardown on exit.
+
+    Args:
+        config: Path to the collector YAML config (mounted read-only).
+        output_file: Path the collector writes spans to (mounted read-write).
+        http_port: Host port mapped to container's OTLP/HTTP listener (4318).
+        grpc_port: Host port mapped to container's OTLP/gRPC listener (4317).
+        image: Docker image; defaults to `otel/opentelemetry-collector-contrib:latest`.
+        start_timeout_seconds: How long to wait for the collector to become
+            reachable on the HTTP port before raising.
+
+    Yields:
+        Dict with the bound `http_port` + `grpc_port`.
+    """
+    container_name = f"agenteval-otelcol-{uuid.uuid4().hex[:8]}"
+    # Create the output file empty so docker doesn't mount it as a
+    # directory by accident.
+    output_file.parent.mkdir(parents=True, exist_ok=True)
+    output_file.write_text("")
+    try:
+        subprocess.run(
+            [
+                "docker",
+                "run",
+                "-d",
+                "--name",
+                container_name,
+                "--rm",
+                "-p",
+                f"{http_port}:4318",
+                "-p",
+                f"{grpc_port}:4317",
+                "-v",
+                f"{config}:/etc/otelcol-contrib/config.yaml:ro",
+                "-v",
+                f"{output_file}:/etc/otelcol-contrib/spans.json",
+                image,
+                "--config=/etc/otelcol-contrib/config.yaml",
+            ],
+            check=True,
+            capture_output=True,
+            timeout=30,
+        )
+        # Poll until the OTLP HTTP receiver responds (POST with empty body
+        # returns 400 once the receiver is up; connection refusal means
+        # still starting).
+        deadline = time.time() + start_timeout_seconds
+        ready = False
+        while time.time() < deadline:
+            try:
+                check = subprocess.run(
+                    [
+                        "docker",
+                        "exec",
+                        container_name,
+                        "wget",
+                        "-q",
+                        "--spider",
+                        "--timeout=1",
+                        "http://127.0.0.1:4318/v1/traces",
+                    ],
+                    check=False,
+                    capture_output=True,
+                    timeout=5,
+                )
+            except (FileNotFoundError, subprocess.TimeoutExpired):
+                check = None
+            # wget --spider returns 0 on 200, 8 on HTTP error (e.g. 400 for
+            # empty GET). Either is fine — the receiver is up.
+            if check is not None and check.returncode in (0, 8):
+                ready = True
+                break
+            time.sleep(0.5)
+        if not ready:
+            # Give it one more half-second + proceed anyway; the export
+            # batch will retry. Collect container logs for diagnostics.
+            logs = subprocess.run(
+                ["docker", "logs", container_name],
+                check=False,
+                capture_output=True,
+                timeout=5,
+            )
+            print("[docker_collector] startup probe inconclusive; container logs:")
+            print(logs.stdout.decode(errors="replace"))
+            print(logs.stderr.decode(errors="replace"))
+        yield {"http_port": http_port, "grpc_port": grpc_port}
+    finally:
+        subprocess.run(
+            ["docker", "stop", container_name],
+            check=False,
+            capture_output=True,
+            timeout=20,
+        )
+
+
+def read_collector_spans(output_file: Path) -> list[dict]:
+    """Parse the OTel collector's file-exporter output into Python dicts.
+
+    The file exporter writes one OTLP-shaped JSON document per export batch
+    (each line is an OTLP `ExportTraceServiceRequest` envelope). We flatten
+    the `resourceSpans → scopeSpans → spans` nested structure into a flat
+    list of span dicts with a `resource` + `scope` annotation per span.
+    """
+    if not output_file.exists():
+        return []
+    spans: list[dict] = []
+    for line in output_file.read_text().splitlines():
+        line = line.strip()
+        if not line:
+            continue
+        try:
+            batch = json.loads(line)
+        except json.JSONDecodeError:
+            continue
+        for resource_span in batch.get("resourceSpans", []):
+            resource = resource_span.get("resource", {})
+            for scope_span in resource_span.get("scopeSpans", []):
+                scope = scope_span.get("scope", {})
+                for span in scope_span.get("spans", []):
+                    spans.append(
+                        {
+                            **span,
+                            "resource": resource,
+                            "scope": scope,
+                        }
+                    )
+    return spans
diff --git a/tests/integration/telemetry/test_otlp_export_e2e.py b/tests/integration/telemetry/test_otlp_export_e2e.py
new file mode 100644
index 0000000..ea891a8
--- /dev/null
+++ b/tests/integration/telemetry/test_otlp_export_e2e.py
@@ -0,0 +1,146 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""End-to-end OTLP round-trip via a local OTel collector docker container (Story 13.2 AC-13.2.8).
+
+Per Story 13.2 D-8 + L-4 lessons (Story 13.1 Codex HIGH-4 empirical-probe
+lesson): the wire format is verified by reading the collector's output file
++ asserting span content, NOT just "the exporter was called." Gated by
+`_docker_available()` so routine CI skips when docker is unavailable.
+
+Set `AGENTEVAL_DISABLE_DOCKER_TESTS=1` to suppress these tests even on
+docker-available hosts (useful when iterating without the slow image-pull
++ container-startup overhead).
+
+Tests use the `agenteval-advanced`-free public API surface:
+1. Spin up `otel/opentelemetry-collector-contrib` listening on OTLP HTTP + gRPC.
+2. Configure `AgentEval` Library with `trace_backend=otlp` + the collector
+   endpoint.
+3. Emit a span via the Listener-attached TracerProvider.
+4. Read back the collector's output file + assert span content.
+"""
+
+from __future__ import annotations
+
+import time
+from pathlib import Path
+
+import pytest
+
+# Phase-2 deps required.
+pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
+pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc")
+
+from ._otlp_helpers import (  # noqa: E402
+    _docker_available,
+    docker_collector,
+    minimal_otel_config,
+    read_collector_spans,
+)
+
+# Mark the whole module as docker-gated. The skipif fires once at collection.
+pytestmark = pytest.mark.skipif(
+    not _docker_available(),
+    reason="docker not available (or AGENTEVAL_DISABLE_DOCKER_TESTS=1)",
+)
+
+
+def _emit_test_span_via_listener(endpoint: str, span_name: str = "agenteval_e2e_test_span") -> None:
+    """Emit one span via the AgentEval Listener's TracerProvider + force-flush.
+
+    Uses the Listener's `_attach_otlp_exporter_if_needed` path so the
+    BatchSpanProcessor(OTLPSpanExporter) is wired identically to a
+    real RF run. The span is emitted via the OpenTelemetry API directly
+    (the Listener's TracerProvider is the active provider).
+    """
+    import os
+
+    from opentelemetry import trace
+
+    from AgentEval.telemetry import listener as listener_mod
+
+    os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"
+    os.environ["AGENTEVAL_OTLP_ENDPOINT"] = endpoint
+
+    listener = listener_mod.Listener()
+    # Mimic start_suite: configure tracer provider + resolve backend +
+    # attach OTLP exporter.
+    listener._configure_tracer_provider()
+    listener._resolve_backend(suite=None)
+    listener._attach_otlp_exporter_if_needed()
+
+    tracer = trace.get_tracer("agenteval.e2e_test")
+    with tracer.start_as_current_span(span_name) as span:
+        span.set_attribute("agenteval.tier", 2)
+        span.set_attribute("gen_ai.request.model", "test-model")
+
+    # Force-flush via the active TracerProvider so the BatchSpanProcessor
+    # ships the span before the docker container teardown.
+    trace.get_tracer_provider().force_flush(timeout_millis=5000)  # type: ignore[union-attr]
+
+
+def test_otlp_http_export_round_trip_against_collector(tmp_path: Path) -> None:
+    """Span emitted via OTLP HTTP lands in the collector's file output.
+
+    Per Story 13.2 L-4 (Codex empirical-probe lesson): verify the wire
+    format by reading collector output, NOT just call_count.
+    """
+    config_file = tmp_path / "otel-config.yaml"
+    output_file = tmp_path / "spans.json"
+    config_file.write_text(minimal_otel_config(output_file))
+    # Random high ports to avoid colliding with local OTel collectors.
+    http_port = 24318
+    grpc_port = 24317
+
+    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
+        _emit_test_span_via_listener(
+            endpoint=f"http://localhost:{http_port}/v1/traces",
+            span_name="agenteval_e2e_http_span",
+        )
+        # The collector batches at 100ms; give it a beat to flush the file.
+        time.sleep(1.5)
+
+    spans = read_collector_spans(output_file)
+    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
+    assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
+    # Verify agenteval-specific attribute flows through OTLP envelope.
+    flat_attrs: list[dict] = []
+    for s in spans:
+        flat_attrs.extend(s.get("attributes", []))
+    # OTLP attribute shape: {"key": "agenteval.tier", "value": {"intValue": "2"}}.
+    assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)
+
+
+def test_otlp_grpc_export_round_trip_against_collector(tmp_path: Path) -> None:
+    """Span emitted via OTLP gRPC lands in the collector's file output.
+
+    Verifies the gRPC scheme dispatch + insecure=True host:port stripping
+    end-to-end. Same wire-format readback assertion as the HTTP variant.
+    """
+    config_file = tmp_path / "otel-config.yaml"
+    output_file = tmp_path / "spans.json"
+    config_file.write_text(minimal_otel_config(output_file))
+    http_port = 24319
+    grpc_port = 24320
+
+    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
+        _emit_test_span_via_listener(
+            endpoint=f"grpc://localhost:{grpc_port}",
+            span_name="agenteval_e2e_grpc_span",
+        )
+        time.sleep(1.5)
+
+    spans = read_collector_spans(output_file)
+    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
+    assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)
diff --git a/tests/unit/kernel/test_context.py b/tests/unit/kernel/test_context.py
index 2d83718..294cb1d 100644
--- a/tests/unit/kernel/test_context.py
+++ b/tests/unit/kernel/test_context.py
@@ -469,10 +469,11 @@ def test_build_minimized_env_overlays_spec_env(monkeypatch: pytest.MonkeyPatch)
 
 
 def test_resolve_config_returns_all_9_fr42_fr11b_keys() -> None:
-    """Story 5.1 added `trace_path` (10th key) to support the JSONL backend.
+    """Story 5.1 added `trace_path` (10th key); Story 13.2 added `otlp_endpoint` (11th).
 
-    Test name preserved for git-blame continuity; the key count is now 10
-    after Story 5.1's `trace_path` addition (PRD FR33b JSONL backend + AC-5.1.6).
+    Test name preserved for git-blame continuity; the key count is now 11
+    after Story 13.2's `otlp_endpoint` addition (PRD FR33b OTLP backend +
+    AC-13.2.6).
     """
     cfg = resolve_config({}, dotenv_path=Path("/nonexistent/.env"))
     expected_keys = {
@@ -486,6 +487,7 @@ def test_resolve_config_returns_all_9_fr42_fr11b_keys() -> None:
         "allow_external_mcp_blind",
         "max_cost_usd",
         "max_runtime_seconds",
+        "otlp_endpoint",
     }
     assert set(cfg.keys()) == expected_keys
 
@@ -503,6 +505,7 @@ def test_resolve_config_layer4_defaults_match_fr42(monkeypatch: pytest.MonkeyPat
         "AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND",
         "AGENTEVAL_MAX_COST_USD",
         "AGENTEVAL_MAX_RUNTIME_SECONDS",
+        "AGENTEVAL_OTLP_ENDPOINT",
     ):
         monkeypatch.delenv(env_name, raising=False)
 
@@ -518,6 +521,8 @@ def test_resolve_config_layer4_defaults_match_fr42(monkeypatch: pytest.MonkeyPat
         "allow_external_mcp_blind": False,
         "max_cost_usd": 5.00,
         "max_runtime_seconds": None,
+        # Story 13.2 (Epic 13) — OTLP endpoint default per AC-13.2.6 FR33b.
+        "otlp_endpoint": None,
     }
 
 
diff --git a/tests/unit/orchestration/test_config_provenance.py b/tests/unit/orchestration/test_config_provenance.py
index 32f189a..0c45d7f 100644
--- a/tests/unit/orchestration/test_config_provenance.py
+++ b/tests/unit/orchestration/test_config_provenance.py
@@ -111,7 +111,8 @@ def test_get_effective_config_with_provenance_returns_full_dict() -> None:
     config = agent.get_effective_config_with_provenance()
     assert isinstance(config, dict)
     assert all(isinstance(v, ConfigValue) for v in config.values())
-    # All FR42+FR11b keys present (10 after Story 5.1 added `trace_path`).
+    # All FR42+FR11b keys present (11 after Story 5.1 added `trace_path`
+    # + Story 13.2 added `otlp_endpoint`).
     expected_keys = {
         "provider",
         "telemetry",
@@ -123,6 +124,7 @@ def test_get_effective_config_with_provenance_returns_full_dict() -> None:
         "allow_external_mcp_blind",
         "max_cost_usd",
         "max_runtime_seconds",
+        "otlp_endpoint",
     }
     assert set(config.keys()) == expected_keys
 
diff --git a/tests/unit/telemetry/test_backends_otlp.py b/tests/unit/telemetry/test_backends_otlp.py
new file mode 100644
index 0000000..dd172ff
--- /dev/null
+++ b/tests/unit/telemetry/test_backends_otlp.py
@@ -0,0 +1,195 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Unit tests for `OTLPBackend` happy paths + URL-scheme dispatch (Story 13.2).
+
+Math + reference comparison N/A here (export-side; integration test covers
+the wire format). These tests verify construction-time behavior:
+- Default + explicit endpoint resolution.
+- URL-scheme dispatch (http / https / grpc / grpcs).
+- ValueError on unknown scheme + empty endpoint.
+- `flush_test` is a no-op.
+- Class invariants (`name` attr, docstring contains expected anchors).
+
+ImportError-gate tests live in the companion `test_backends_otlp_extras_gate.py`
+file per Story 13.1 L-2 lesson (no top-level `importorskip` so they run in
+both WITH-extras and WITHOUT-extras CI environments).
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+from unittest.mock import patch
+
+import pytest
+
+# Phase-2 modules require opentelemetry-exporter-otlp. Skip the happy-path
+# tests when the extra is not installed (ImportError-gate tests run separately).
+pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
+pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc")
+
+from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: E402
+    OTLPSpanExporter as _GrpcExp,
+)
+from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E402
+    OTLPSpanExporter as _HttpExp,
+)
+
+from AgentEval.telemetry.backends import (  # noqa: E402
+    _OTLP_DEFAULT_ENDPOINT_HTTP,
+    JSONLBackend,
+    MemoryBackend,
+    OTLPBackend,
+)
+
+# --------------------------------------------------------------------------- #
+# Class invariants (2 tests)                                                  #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_name_is_otlp() -> None:
+    """OTLPBackend.name == 'otlp' (symmetric with MemoryBackend / JSONLBackend)."""
+    assert OTLPBackend.name == "otlp"
+
+
+def test_otlp_backend_docstring_carries_anchors() -> None:
+    """Docstring contains Browser-Library-convention anchors (Story 13.1 L-5 lesson).
+
+    Story 13.1 review found that docstrings claiming behavior must
+    namedrop the responsible mechanism precisely. OTLPBackend docstring
+    must mention `BatchSpanProcessor` + `Phase-2` + `FR33b` so the
+    contract is grep-discoverable.
+    """
+    doc = OTLPBackend.__doc__ or ""
+    assert "BatchSpanProcessor" in doc
+    assert "Phase-2" in doc
+    assert "FR33b" in doc
+
+
+# --------------------------------------------------------------------------- #
+# Default endpoint + explicit endpoint construction (3 tests)                 #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_default_endpoint_is_local_http_jaeger() -> None:
+    """endpoint=None → http://localhost:4318/v1/traces (HTTP exporter)."""
+    backend = OTLPBackend()
+    assert backend._endpoint == _OTLP_DEFAULT_ENDPOINT_HTTP
+    assert backend._transport == "http"
+    assert isinstance(backend._exporter, _HttpExp)
+
+
+def test_otlp_backend_explicit_http_endpoint_constructs_http_exporter() -> None:
+    """Explicit http:// URL → HTTP exporter at that URL."""
+    backend = OTLPBackend(endpoint="http://collector.example.com:4318/v1/traces")
+    assert backend._endpoint == "http://collector.example.com:4318/v1/traces"
+    assert backend._transport == "http"
+    assert isinstance(backend._exporter, _HttpExp)
+
+
+def test_otlp_backend_explicit_https_endpoint_constructs_http_exporter() -> None:
+    """Explicit https:// URL → HTTP exporter (TLS handled by OpenTelemetry SDK)."""
+    backend = OTLPBackend(endpoint="https://api.honeycomb.io/v1/traces")
+    assert backend._endpoint == "https://api.honeycomb.io/v1/traces"
+    assert backend._transport == "http"
+    assert isinstance(backend._exporter, _HttpExp)
+
+
+# --------------------------------------------------------------------------- #
+# gRPC scheme dispatch (3 tests)                                              #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_grpc_scheme_constructs_grpc_exporter_insecure() -> None:
+    """grpc:// → gRPC exporter with insecure=True + stripped scheme."""
+    backend = OTLPBackend(endpoint="grpc://localhost:4317")
+    assert backend._endpoint == "grpc://localhost:4317"  # full URL preserved as input
+    assert backend._transport == "grpc"
+    assert isinstance(backend._exporter, _GrpcExp)
+
+
+def test_otlp_backend_grpcs_scheme_constructs_grpc_exporter_secure() -> None:
+    """grpcs:// → gRPC exporter with insecure=False (TLS) + stripped scheme."""
+    backend = OTLPBackend(endpoint="grpcs://otel.example.com:4317")
+    assert backend._endpoint == "grpcs://otel.example.com:4317"
+    assert backend._transport == "grpc"
+    assert isinstance(backend._exporter, _GrpcExp)
+
+
+def test_otlp_backend_grpc_scheme_is_case_insensitive() -> None:
+    """Mixed-case GRPC:// resolves the same as lowercase grpc://."""
+    backend = OTLPBackend(endpoint="GRPC://localhost:4317")
+    assert backend._transport == "grpc"
+    assert isinstance(backend._exporter, _GrpcExp)
+
+
+# --------------------------------------------------------------------------- #
+# Endpoint rejection (3 tests)                                                #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_rejects_unknown_scheme_with_value_error() -> None:
+    """ftp:// (or any other non-OTLP scheme) raises ValueError listing valid schemes."""
+    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
+        OTLPBackend(endpoint="ftp://collector.example.com:21")
+    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
+        OTLPBackend(endpoint="ws://collector.example.com:4318")
+
+
+def test_otlp_backend_rejects_empty_string_endpoint_with_value_error() -> None:
+    """endpoint='' raises ValueError (ambiguous fallback to OTel SDK env default rejected)."""
+    with pytest.raises(ValueError, match="must not be empty"):
+        OTLPBackend(endpoint="")
+
+
+def test_otlp_backend_rejects_no_scheme_endpoint_with_value_error() -> None:
+    """A bare host:port without `://` raises ValueError listing valid schemes."""
+    with pytest.raises(ValueError, match="must use http://, https://, grpc://, or grpcs://"):
+        OTLPBackend(endpoint="localhost:4318")
+
+
+# --------------------------------------------------------------------------- #
+# flush_test is a no-op (1 test)                                              #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_flush_test_is_noop_and_does_not_export(tmp_path: Path) -> None:
+    """flush_test does NOT call exporter.export + returns None + writes no files.
+
+    Per Story 13.2 D-7: OTLP export is event-driven (BatchSpanProcessor at
+    TracerProvider config time), NOT flush-driven. flush_test exists for
+    API uniformity with MemoryBackend / JSONLBackend but does no work.
+    """
+    backend = OTLPBackend(endpoint="http://localhost:4318/v1/traces")
+    with patch.object(backend._exporter, "export") as mock_export:
+        result = backend.flush_test(test_id="suite.test_one", suite_id="suite", output_dir=tmp_path)
+    assert result is None
+    assert mock_export.call_count == 0
+    # No files written under the output dir.
+    assert list(tmp_path.iterdir()) == []
+
+
+# --------------------------------------------------------------------------- #
+# Co-existence with MemoryBackend / JSONLBackend (1 test)                     #
+# --------------------------------------------------------------------------- #
+
+
+def test_otlp_backend_is_distinct_class_from_memory_and_jsonl_backends() -> None:
+    """OTLPBackend is a sibling class, not a subclass — verifies the union-type ABI."""
+    backend = OTLPBackend()
+    assert not isinstance(backend, MemoryBackend)
+    assert not isinstance(backend, JSONLBackend)
+    # All three have `name` + `flush_test` (duck-typed Backend ABI).
+    assert hasattr(backend, "name")
+    assert hasattr(backend, "flush_test")
diff --git a/tests/unit/telemetry/test_backends_otlp_extras_gate.py b/tests/unit/telemetry/test_backends_otlp_extras_gate.py
new file mode 100644
index 0000000..b72a2a8
--- /dev/null
+++ b/tests/unit/telemetry/test_backends_otlp_extras_gate.py
@@ -0,0 +1,122 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""ImportError-gate tests for the Phase-2 `[otlp]` extra (Story 13.2 L-2 lesson).
+
+Mirrors `tests/unit/stats/test_advanced_extras_gate.py` discipline (Story 13.1
+HIGH-B fix): this file deliberately has NO module-top `pytest.importorskip`
+so the gate-coverage tests run in BOTH the WITH-extras and WITHOUT-extras CI
+environments.
+
+Per AC-13.2.7 + Story 13.1 cross-story upstream lesson L-2: the WITHOUT-extras
+CI matrix MUST verify (a) `OTLPBackend` is importable without the extra (class
+is referenced at module load time); (b) construction raises ImportError with
+the verbatim `[otlp]` extra message; (c) `_resolve_backend` graceful-degrades
+to MemoryBackend when construction fails.
+"""
+
+from __future__ import annotations
+
+import warnings
+
+import pytest
+
+from AgentEval.errors import DegradedTraceWarning
+
+
+def test_backends_module_importable_without_otlp_extra() -> None:
+    """`from AgentEval.telemetry.backends import OTLPBackend` succeeds even WITHOUT the extra.
+
+    The class is referenced at module load; only construction raises. This
+    is what makes the Listener's `_resolve_backend` branch testable in
+    the base CI environment.
+    """
+    from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend, OTLPBackend  # noqa: F401
+
+    # All three class references must resolve.
+    assert MemoryBackend.name == "memory"
+    assert JSONLBackend.name == "jsonl"
+    assert OTLPBackend.name == "otlp"
+
+
+def test_raise_otlp_extra_missing_helper_carries_canonical_message() -> None:
+    """`_raise_otlp_extra_missing` produces the spec-mandated ImportError text.
+
+    Per Story 13.2 D-5 + AC-13.2.1: the message MUST recommend
+    `uv pip install robotframework-agenteval[otlp]` verbatim so the
+    operator's `[otlp]` install hint is grep-discoverable in the trace.
+    """
+    from AgentEval.telemetry.backends import _raise_otlp_extra_missing
+
+    with pytest.raises(ImportError) as exc_info:
+        _raise_otlp_extra_missing()
+    msg = str(exc_info.value)
+    assert "OTLPBackend" in msg
+    assert "opentelemetry-exporter-otlp" in msg
+    assert "uv pip install robotframework-agenteval[otlp]" in msg
+
+
+def test_otlp_backend_raises_import_error_when_extra_unavailable(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """`OTLPBackend(endpoint=...)` raises ImportError when `_OTLP_AVAILABLE = False`.
+
+    Monkeypatches the module-level gate directly (vs reloading the module
+    with the OTLP exporter modules stubbed out) per Story 13.1 review
+    HIGH-B + dev experience: module reload across tests pollutes
+    `sys.modules` and leaves stats.library + telemetry.backends in a
+    partial-import state. The gate check is the load-bearing branch;
+    this verifies it triggers for OTLPBackend.
+    """
+    from AgentEval.telemetry import backends as backends_mod
+
+    monkeypatch.setattr(backends_mod, "_OTLP_AVAILABLE", False)
+    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
+        backends_mod.OTLPBackend(endpoint="http://localhost:4318/v1/traces")
+    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
+        # Default endpoint also raises (gate sits BEFORE endpoint dispatch).
+        backends_mod.OTLPBackend()
+
+
+def test_resolve_backend_falls_back_with_warning_when_otlp_unavailable(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """Listener `_resolve_backend` graceful-degrades to MemoryBackend when OTLP is unavailable.
+
+    Per AC-13.2.7 (4th extras-gate test): with `trace_backend="otlp"` +
+    `_OTLP_AVAILABLE=False`, the Listener catches the ImportError + emits
+    DegradedTraceWarning + falls back to MemoryBackend rather than aborting
+    the test run. Mirrors Story 5.1's unknown-trace_backend safety posture.
+    """
+    from AgentEval.telemetry import backends as backends_mod
+    from AgentEval.telemetry import listener as listener_mod
+    from AgentEval.telemetry.backends import MemoryBackend
+
+    monkeypatch.setattr(backends_mod, "_OTLP_AVAILABLE", False)
+    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "otlp")
+    monkeypatch.setenv("AGENTEVAL_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
+
+    listener = listener_mod.Listener()
+
+    with warnings.catch_warnings(record=True) as captured:
+        warnings.simplefilter("always")
+        listener._resolve_backend(suite=None)  # type: ignore[arg-type]
+
+    # Backend graceful-degrades to MemoryBackend rather than aborting.
+    assert isinstance(listener._backend, MemoryBackend)
+    # DegradedTraceWarning fired with the install hint.
+    degraded = [w for w in captured if issubclass(w.category, DegradedTraceWarning)]
+    assert len(degraded) >= 1
+    assert any("otlp" in str(w.message).lower() for w in degraded)
+    assert any("uv pip install robotframework-agenteval[otlp]" in str(w.message) for w in degraded)
diff --git a/uv.lock b/uv.lock
index d4e07d1..08900f1 100644
--- a/uv.lock
+++ b/uv.lock
@@ -3,7 +3,9 @@ revision = 3
 requires-python = ">=3.12"
 resolution-markers = [
     "python_full_version >= '3.15'",
-    "python_full_version < '3.15'",
+    "python_full_version == '3.14.*'",
+    "python_full_version == '3.13.*'",
+    "python_full_version < '3.13'",
 ]
 
 [[package]]
@@ -643,6 +645,18 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/d5/0c/043d5e551459da400957a1395e0febbf771446ff34291afcbe3d8be2a279/fsspec-2026.4.0-py3-none-any.whl", hash = "sha256:11ef7bb35dab8a394fde6e608221d5cf3e8499401c249bebaeaad760a1a8dec2", size = 203402, upload-time = "2026-04-29T20:42:36.842Z" },
 ]
 
+[[package]]
+name = "googleapis-common-protos"
+version = "1.75.0"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "protobuf" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/b5/c8/f439cffde755cffa462bfbb156278fa6f9d09119719af9814b858fd4f81f/googleapis_common_protos-1.75.0.tar.gz", hash = "sha256:53a062ff3c32552fbd62c11fe23768b78e4ddf0494d5e5fd97d3f4689c75fbbd", size = 151035, upload-time = "2026-05-07T08:04:49.423Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/e7/c8/e2645aa8ed02fd4c7a2f59d68783b65b1f3cbdfe39a6308e156509d1fee8/googleapis_common_protos-1.75.0-py3-none-any.whl", hash = "sha256:961ed60399c457ceb0ee8f285a84c870aabc9c6a832b9d37bb281b5bebde43ed", size = 300631, upload-time = "2026-05-07T08:03:30.345Z" },
+]
+
 [[package]]
 name = "griffelib"
 version = "2.0.2"
@@ -652,6 +666,47 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/11/8c/c9138d881c79aa0ea9ed83cbd58d5ca75624378b38cee225dcf5c42cc91f/griffelib-2.0.2-py3-none-any.whl", hash = "sha256:925c857658fb1ba40c0772c37acbc2ab650bd794d9c1b9726922e36ea4117ea1", size = 142357, upload-time = "2026-03-27T11:34:46.275Z" },
 ]
 
+[[package]]
+name = "grpcio"
+version = "1.81.0"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "typing-extensions" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/15/f3/23f47b24f8d8c2028eba501db3acfbb2f592cbb5995eaa6e363a627b74d7/grpcio-1.81.0.tar.gz", hash = "sha256:a5acd7efd3b1fe9b4eb0bcaaa1507eed68a0ad0678b654c3f7b464df9ba9dca5", size = 13032272, upload-time = "2026-06-01T05:56:22.827Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/82/d5/896a3aaf07068d707d88b282a04914b872db4d32d3c7e6d88e43a3b911fa/grpcio-1.81.0-cp312-cp312-linux_armv7l.whl", hash = "sha256:57b3b0e73a518fa286959b40c3eddd02703504ca186e8b7b2945954519bd8b2c", size = 6053538, upload-time = "2026-06-01T05:54:58.965Z" },
+    { url = "https://files.pythonhosted.org/packages/68/6a/7e3eafa4727cd405ff917605ed2949e2af162f233f5cbdd773723a5fea7d/grpcio-1.81.0-cp312-cp312-macosx_11_0_universal2.whl", hash = "sha256:8bb1789c94322a13336a2b6c58d9c14d68f8628b6e24205a799c69f5bf8516ce", size = 12053447, upload-time = "2026-06-01T05:55:01.862Z" },
+    { url = "https://files.pythonhosted.org/packages/16/79/a4302aa82428de48a922421f522b027a1a727ab4d0926368454aa953d36d/grpcio-1.81.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:e4d053900a0d24b75d7521139a3872150301b3d6bde3bed5e12318fb25791e4d", size = 6595872, upload-time = "2026-06-01T05:55:04.946Z" },
+    { url = "https://files.pythonhosted.org/packages/b4/1f/7ff2850eaefbecf99af3f624dbb28dd1ad6c5fd4c1d8c26909ed6482673b/grpcio-1.81.0-cp312-cp312-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:db217c2e52931719f9937bd12082cd4d7b495b35803d5760686975c285924bf8", size = 7303857, upload-time = "2026-06-01T05:55:07.205Z" },
+    { url = "https://files.pythonhosted.org/packages/e2/98/1f3896a9baae1f2aedf4e99c55291d6fa1f30ad9603d63bc18bda967b53e/grpcio-1.81.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:19f201da7b4e5c0559198abe5a97157e726f3abe6e8f5e832d4a50740f6dcc22", size = 6809676, upload-time = "2026-06-01T05:55:09.513Z" },
+    { url = "https://files.pythonhosted.org/packages/34/8b/3441983718095208c5d797fd3239882e97ea89a629f41c8df94b4eef4df9/grpcio-1.81.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:275144b0115353339dbb8a6f28a9cf8997b5bf40e37f8f66ac0b0ea57e95b43f", size = 7412654, upload-time = "2026-06-01T05:55:12.777Z" },
+    { url = "https://files.pythonhosted.org/packages/3c/98/1eddf07df6e4fe85cf67502a793f7b05468b2dca3d1ef35b972cf5d54468/grpcio-1.81.0-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:5192857589f223e5a98ff0e31f6e551b19040e647d17bfe10116c8a2ce3b8696", size = 8408026, upload-time = "2026-06-01T05:55:15.514Z" },
+    { url = "https://files.pythonhosted.org/packages/5c/73/3860341e6a1f5347be6ab35c6c0e1e3a8eb59d010388207fd561dcf01a88/grpcio-1.81.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:c6ff087cb1f563f47b504b4e29e684129fc5ae4863faf3ebca08a327764ee6cb", size = 7849498, upload-time = "2026-06-01T05:55:18.078Z" },
+    { url = "https://files.pythonhosted.org/packages/ae/3f/0ea06bd85c701966aa3f8f37314f2ed83520d2b7590f42d643d445d8bc8b/grpcio-1.81.0-cp312-cp312-win32.whl", hash = "sha256:98c6240f563178fc5877bd50e6ff274463e53e1472128f4110742450739659fa", size = 4184161, upload-time = "2026-06-01T05:55:20.127Z" },
+    { url = "https://files.pythonhosted.org/packages/39/e3/a7c387406827a86f99ad7838b995bf9b4a182ffe2d2c439ed2873efec952/grpcio-1.81.0-cp312-cp312-win_amd64.whl", hash = "sha256:87e33b7afcfb3585121b5f007d2c52b8c534104d18f556e840d35193ca2a9141", size = 4929958, upload-time = "2026-06-01T05:55:22.736Z" },
+    { url = "https://files.pythonhosted.org/packages/f3/29/779ee53c931d0fd55c1d459fde43e485172caa3ac87cbd43d003a13a0185/grpcio-1.81.0-cp313-cp313-linux_armv7l.whl", hash = "sha256:62bbe463c9f0f2ff24e31bd25f8dd8b4bae78900e315915a3195a0ef1471a855", size = 6054973, upload-time = "2026-06-01T05:55:25.043Z" },
+    { url = "https://files.pythonhosted.org/packages/9e/b6/7211807926b5a17f8d9a5d47c739a163d6812fefe3e4714e81cf92945ed7/grpcio-1.81.0-cp313-cp313-macosx_11_0_universal2.whl", hash = "sha256:43c121e135ae44d1559b430db2b2dfad7421cbbe40e1deba506c7dc62b439719", size = 12048662, upload-time = "2026-06-01T05:55:28.453Z" },
+    { url = "https://files.pythonhosted.org/packages/64/89/b1b93ef6b34bd20bbaf707fa99133bc9cc302139d5ec6f77a165c7169796/grpcio-1.81.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:f345de40ef2e65f63645d53d251824e6070e07804827c5b00ec2e44555f9f901", size = 6599116, upload-time = "2026-06-01T05:55:31.185Z" },
+    { url = "https://files.pythonhosted.org/packages/eb/bc/c89f9b9d1c22895715356a1e009554dae66319e97826bb4d30bcda7d29e8/grpcio-1.81.0-cp313-cp313-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:8c0855a350886f713b9e458e2a10d208009dcaa849f574e39cd6067db1fe1279", size = 7307591, upload-time = "2026-06-01T05:55:33.463Z" },
+    { url = "https://files.pythonhosted.org/packages/65/4a/1df2a4cb4a1386e066ab7e4175e34bb884b35ccb60d3621c09c84af6aabb/grpcio-1.81.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:a524cd530900bd24511fcb7f2ed144da4ea37711c4b094475d0bceca7a93a170", size = 6811797, upload-time = "2026-06-01T05:55:36.731Z" },
+    { url = "https://files.pythonhosted.org/packages/8d/dc/fa189d20601a1be25b08850cfb733879bbb1047b62a8feec3a60e3e1a87b/grpcio-1.81.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:e7746ba3e6efc9e2b748eff59470a2b8684d5a9ec607c6580bcaa5be175820bc", size = 7415131, upload-time = "2026-06-01T05:55:39.451Z" },
+    { url = "https://files.pythonhosted.org/packages/ad/a3/5625c48cb48d23c6631b3e5294f88e4c751f22a52591ae78859fab96dca1/grpcio-1.81.0-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:aaaa4f7f2057d795952e4eacf3f342be8b5b156992f6ac85023c8b98794ebd47", size = 8408398, upload-time = "2026-06-01T05:55:42.219Z" },
+    { url = "https://files.pythonhosted.org/packages/75/34/0f8202c6809a46c2b4d69125ef3667c40b1c211f8e19930e5fa1f1197039/grpcio-1.81.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:0fba53cb96004b2b7fb758b46b2288cb49d0b658316a4e73f3ef67230616ee65", size = 7844481, upload-time = "2026-06-01T05:55:44.849Z" },
+    { url = "https://files.pythonhosted.org/packages/c0/95/c3366b5b5edf4c4adc90f2e29ca16e57965a8e56dc8d2ee89565ba1905bb/grpcio-1.81.0-cp313-cp313-win32.whl", hash = "sha256:c197e2ef75a442528072b29e9755da299110e8610e8bcbb59a6b4cf55384f005", size = 4182777, upload-time = "2026-06-01T05:55:47.459Z" },
+    { url = "https://files.pythonhosted.org/packages/a9/a7/932f2f748511a32e641a2aba0d30dded3ed6e8bc330e0924e4d5d86853e6/grpcio-1.81.0-cp313-cp313-win_amd64.whl", hash = "sha256:194eddfacc84d80f50512e9fd4ee851d5f2499f18f299c95aa8fb4748f0537e0", size = 4928085, upload-time = "2026-06-01T05:55:50.158Z" },
+    { url = "https://files.pythonhosted.org/packages/c5/1d/28b231333857deb840bc3d182ae087510170ea6d68f21393aeb0fe499530/grpcio-1.81.0-cp314-cp314-linux_armv7l.whl", hash = "sha256:a9351055f52660b58f3d4890ea66188b5134399f82b11aa0c55bd4b99eff5390", size = 6055712, upload-time = "2026-06-01T05:55:52.889Z" },
+    { url = "https://files.pythonhosted.org/packages/e8/b8/999c14f9dff0fc47549d2e827cba1343ddc18e1d1bf0d06d2cf628eecbd9/grpcio-1.81.0-cp314-cp314-macosx_11_0_universal2.whl", hash = "sha256:300f3337b6425fd16ead9a4f9b2ac25801acb64aa5bc0b99eb69901645b2b1d2", size = 12057189, upload-time = "2026-06-01T05:55:55.952Z" },
+    { url = "https://files.pythonhosted.org/packages/1e/3d/1fbde079572562af65351151d840525a13879eb7b481d35b55cd64c6127a/grpcio-1.81.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:97bbd623f7ded558fd4f7cb5a4f600c4d4de65c5dd364c83a5b14b2a10a2d3b5", size = 6608136, upload-time = "2026-06-01T05:55:59.069Z" },
+    { url = "https://files.pythonhosted.org/packages/32/89/1f17cb6882abfd8e5a303a25d5d1665abef5a8c499a96198c65a651d1b85/grpcio-1.81.0-cp314-cp314-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:ff83d889e3ebf6341c8c7864ad8031591ad5ca61599072fc511644d1eb962d2b", size = 7307045, upload-time = "2026-06-01T05:56:02.376Z" },
+    { url = "https://files.pythonhosted.org/packages/48/5a/f98e91b2e755652e637ea2144318b0229b290062199f761b445fe1fa6015/grpcio-1.81.0-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:c4fe218c5a35e1d87a5a26544237f1fa41dfd9cbd3c856b0810a30061f8b0aaf", size = 6812794, upload-time = "2026-06-01T05:56:05.777Z" },
+    { url = "https://files.pythonhosted.org/packages/0a/0c/77892d715ac41e7ec0ace2a50080ffb64e189188056f607a66fe0014d1ee/grpcio-1.81.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:b8b025b6af43ee0ad4a70307025d77bcab5adde7c4597786010d802c203e9fc5", size = 7422767, upload-time = "2026-06-01T05:56:08.524Z" },
+    { url = "https://files.pythonhosted.org/packages/3f/b8/aa04590c6564714d94954515f15a236e59d4b9b3ad01e615f1b706d7792d/grpcio-1.81.0-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:3d4e0ce5a40a998cf608c8ba60ecfe18fdf364a9aa193ae4ac3faeecd0e86757", size = 8408551, upload-time = "2026-06-01T05:56:11.283Z" },
+    { url = "https://files.pythonhosted.org/packages/43/3d/4f4a3450a1973568910c6909cb74abbf2126f68aefae5976962f9f7ad50d/grpcio-1.81.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:aa948712c8e5fa40ec250870bda14bc7578e1bb832a8912d9d2a0f720518edbe", size = 7846468, upload-time = "2026-06-01T05:56:14.536Z" },
+    { url = "https://files.pythonhosted.org/packages/88/f4/5827fd248221ad3b44161c23ce9b5f4ee405b04fc6da5fd402a9aa87a84a/grpcio-1.81.0-cp314-cp314-win32.whl", hash = "sha256:fbbe81314a9d92156abce8b62c09364eb8bafc0ca2a19919a45ec64b5c6cb664", size = 4264427, upload-time = "2026-06-01T05:56:17.192Z" },
+    { url = "https://files.pythonhosted.org/packages/0c/e8/127dc2b246096ad50ef7c8d9b7b31d757787aeb796368bcdd4454e4204c4/grpcio-1.81.0-cp314-cp314-win_amd64.whl", hash = "sha256:b93cee313cae4e113fbb3a0ce1ea5633db6f63cfde2b2dc1d817429026b2a50b", size = 5070848, upload-time = "2026-06-01T05:56:19.735Z" },
+]
+
 [[package]]
 name = "h11"
 version = "0.16.0"
@@ -1364,6 +1419,79 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/29/59/3e7118ed140f76b0982ba4321bdaed1997a0473f9720de2d10788a577033/opentelemetry_api-1.41.1-py3-none-any.whl", hash = "sha256:a22df900e75c76dc08440710e51f52f1aa6b451b429298896023e60db5b3139f", size = 69007, upload-time = "2026-04-24T13:15:15.662Z" },
 ]
 
+[[package]]
+name = "opentelemetry-exporter-otlp"
+version = "1.41.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "opentelemetry-exporter-otlp-proto-grpc" },
+    { name = "opentelemetry-exporter-otlp-proto-http" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/42/84/d55baf8e1a222f40282956083e67de9fa92d5fa451108df4839505fa2a24/opentelemetry_exporter_otlp-1.41.1.tar.gz", hash = "sha256:299a2f0541ca175df186f5ac58fd5db177ba1e9b72b0826049062f750d55b47f", size = 6152, upload-time = "2026-04-24T13:15:40.006Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/6d/d5/ea4aa7dfc458fd537bd9519ea0e7226eef2a6212dfe952694984167daaba/opentelemetry_exporter_otlp-1.41.1-py3-none-any.whl", hash = "sha256:db276c5a80c02b063994e80950d00ca1bfddcf6520f608335b7dc2db0c0eb9c6", size = 7025, upload-time = "2026-04-24T13:15:17.839Z" },
+]
+
+[[package]]
+name = "opentelemetry-exporter-otlp-proto-common"
+version = "1.41.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "opentelemetry-proto" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/ae/fa/f9e3bd3c4d692b3ce9a2880a167d1f79681a1bea11f00d5bf76adc03e6ea/opentelemetry_exporter_otlp_proto_common-1.41.1.tar.gz", hash = "sha256:0e253156ea9c36b0bd3d2440c5c9ba7dd1f3fb64ba7a08fc85fbac536b56e1fb", size = 20409, upload-time = "2026-04-24T13:15:40.924Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/29/48/bce76d3ea772b609757e9bc844e02ab408a6446609bf74fb562062ba6b71/opentelemetry_exporter_otlp_proto_common-1.41.1-py3-none-any.whl", hash = "sha256:10da74dad6a49344b9b7b21b6182e3060373a235fde1528616d5f01f92e66aa9", size = 18366, upload-time = "2026-04-24T13:15:18.917Z" },
+]
+
+[[package]]
+name = "opentelemetry-exporter-otlp-proto-grpc"
+version = "1.41.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "googleapis-common-protos" },
+    { name = "grpcio" },
+    { name = "opentelemetry-api" },
+    { name = "opentelemetry-exporter-otlp-proto-common" },
+    { name = "opentelemetry-proto" },
+    { name = "opentelemetry-sdk" },
+    { name = "typing-extensions" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/1e/9b/e4503060b8695579dbaad187dc8cef4554188de68748c88060599b77489e/opentelemetry_exporter_otlp_proto_grpc-1.41.1.tar.gz", hash = "sha256:b05df8fa1333dc9a3fda36b676b96b5095ab6016d3f0c3296d430d629ba1443b", size = 25755, upload-time = "2026-04-24T13:15:41.93Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/ac/f2/c54f33c92443d087703e57e52e55f22f111373a5c4c4aa349ea60efe512e/opentelemetry_exporter_otlp_proto_grpc-1.41.1-py3-none-any.whl", hash = "sha256:537926dcef951136992479af1d9cd88f25e33d56c530e9f020ed57774dca2f94", size = 20297, upload-time = "2026-04-24T13:15:20.212Z" },
+]
+
+[[package]]
+name = "opentelemetry-exporter-otlp-proto-http"
+version = "1.41.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "googleapis-common-protos" },
+    { name = "opentelemetry-api" },
+    { name = "opentelemetry-exporter-otlp-proto-common" },
+    { name = "opentelemetry-proto" },
+    { name = "opentelemetry-sdk" },
+    { name = "requests" },
+    { name = "typing-extensions" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/33/5b/9d3c7f70cca10136ba82a81e738dee626c8e7fc61c6887ea9a58bf34c606/opentelemetry_exporter_otlp_proto_http-1.41.1.tar.gz", hash = "sha256:4747a9604c8550ab38c6fd6180e2fcb80de3267060bef2c306bad3cb443302bc", size = 24139, upload-time = "2026-04-24T13:15:42.977Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/ba/4d/ef07ff2fc630849f2080ae0ae73a61f67257905b7ac79066640bfa0c5739/opentelemetry_exporter_otlp_proto_http-1.41.1-py3-none-any.whl", hash = "sha256:1a21e8f49c7a946d935551e90947d6c3eb39236723c6624401da0f33d68edcb4", size = 22673, upload-time = "2026-04-24T13:15:21.313Z" },
+]
+
+[[package]]
+name = "opentelemetry-proto"
+version = "1.41.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "protobuf" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/99/e8/633c6d8a9c8840338b105907e55c32d3da1983abab5e52f899f72a82c3d1/opentelemetry_proto-1.41.1.tar.gz", hash = "sha256:4b9d2eb631237ea43b80e16c073af438554e32bc7e9e3f8ca4a9582f900020e5", size = 45670, upload-time = "2026-04-24T13:15:49.768Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/e4/1e/5cd77035e3e82070e2265a63a760f715aacd3cb16dddc7efee913f297fcc/opentelemetry_proto-1.41.1-py3-none-any.whl", hash = "sha256:0496713b804d127a4147e32849fbaf5683fac8ee98550e8e7679cd706c289720", size = 72076, upload-time = "2026-04-24T13:15:32.542Z" },
+]
+
 [[package]]
 name = "opentelemetry-sdk"
 version = "1.41.1"
@@ -1537,6 +1665,21 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/3a/ed/1cdcab6ba3d6ab7feca11fc14f0eeea80755bb53ef4e892079f31b10a25f/propcache-0.5.2-py3-none-any.whl", hash = "sha256:be1ddfcbb376e3de5d2e2db1d58d6d67463e6b4f9f040c000de8e300295465fe", size = 14036, upload-time = "2026-05-08T21:02:10.673Z" },
 ]
 
+[[package]]
+name = "protobuf"
+version = "6.33.6"
+source = { registry = "https://pypi.org/simple" }
+sdist = { url = "https://files.pythonhosted.org/packages/66/70/e908e9c5e52ef7c3a6c7902c9dfbb34c7e29c25d2f81ade3856445fd5c94/protobuf-6.33.6.tar.gz", hash = "sha256:a6768d25248312c297558af96a9f9c929e8c4cee0659cb07e780731095f38135", size = 444531, upload-time = "2026-03-18T19:05:00.988Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/fc/9f/2f509339e89cfa6f6a4c4ff50438db9ca488dec341f7e454adad60150b00/protobuf-6.33.6-cp310-abi3-win32.whl", hash = "sha256:7d29d9b65f8afef196f8334e80d6bc1d5d4adedb449971fefd3723824e6e77d3", size = 425739, upload-time = "2026-03-18T19:04:48.373Z" },
+    { url = "https://files.pythonhosted.org/packages/76/5d/683efcd4798e0030c1bab27374fd13a89f7c2515fb1f3123efdfaa5eab57/protobuf-6.33.6-cp310-abi3-win_amd64.whl", hash = "sha256:0cd27b587afca21b7cfa59a74dcbd48a50f0a6400cfb59391340ad729d91d326", size = 437089, upload-time = "2026-03-18T19:04:50.381Z" },
+    { url = "https://files.pythonhosted.org/packages/5c/01/a3c3ed5cd186f39e7880f8303cc51385a198a81469d53d0fdecf1f64d929/protobuf-6.33.6-cp39-abi3-macosx_10_9_universal2.whl", hash = "sha256:9720e6961b251bde64edfdab7d500725a2af5280f3f4c87e57c0208376aa8c3a", size = 427737, upload-time = "2026-03-18T19:04:51.866Z" },
+    { url = "https://files.pythonhosted.org/packages/ee/90/b3c01fdec7d2f627b3a6884243ba328c1217ed2d978def5c12dc50d328a3/protobuf-6.33.6-cp39-abi3-manylinux2014_aarch64.whl", hash = "sha256:e2afbae9b8e1825e3529f88d514754e094278bb95eadc0e199751cdd9a2e82a2", size = 324610, upload-time = "2026-03-18T19:04:53.096Z" },
+    { url = "https://files.pythonhosted.org/packages/9b/ca/25afc144934014700c52e05103c2421997482d561f3101ff352e1292fb81/protobuf-6.33.6-cp39-abi3-manylinux2014_s390x.whl", hash = "sha256:c96c37eec15086b79762ed265d59ab204dabc53056e3443e702d2681f4b39ce3", size = 339381, upload-time = "2026-03-18T19:04:54.616Z" },
+    { url = "https://files.pythonhosted.org/packages/16/92/d1e32e3e0d894fe00b15ce28ad4944ab692713f2e7f0a99787405e43533a/protobuf-6.33.6-cp39-abi3-manylinux2014_x86_64.whl", hash = "sha256:e9db7e292e0ab79dd108d7f1a94fe31601ce1ee3f7b79e0692043423020b0593", size = 323436, upload-time = "2026-03-18T19:04:55.768Z" },
+    { url = "https://files.pythonhosted.org/packages/c4/72/02445137af02769918a93807b2b7890047c32bfb9f90371cbc12688819eb/protobuf-6.33.6-py3-none-any.whl", hash = "sha256:77179e006c476e69bf8e8ce866640091ec42e1beb80b213c3900006ecfba6901", size = 170656, upload-time = "2026-03-18T19:04:59.826Z" },
+]
+
 [[package]]
 name = "pycparser"
 version = "3.0"
@@ -1971,6 +2114,9 @@ dev = [
 openai-agents = [
     { name = "openai-agents" },
 ]
+otlp = [
+    { name = "opentelemetry-exporter-otlp" },
+]
 
 [package.metadata]
 requires-dist = [
@@ -1983,6 +2129,7 @@ requires-dist = [
     { name = "numpy", marker = "extra == 'agenteval-advanced'", specifier = ">=1.26,<3.0" },
     { name = "openai-agents", marker = "extra == 'openai-agents'", specifier = ">=0.1.0,<1.0" },
     { name = "opentelemetry-api", specifier = ">=1.27,<2.0" },
+    { name = "opentelemetry-exporter-otlp", marker = "extra == 'otlp'", specifier = ">=1.27,<2.0" },
     { name = "opentelemetry-sdk", specifier = ">=1.27,<2.0" },
     { name = "pre-commit", marker = "extra == 'dev'", specifier = ">=3.0,<5.0" },
     { name = "pytest", marker = "extra == 'dev'", specifier = ">=8.0,<9.0" },
@@ -1995,7 +2142,7 @@ requires-dist = [
     { name = "ruff", marker = "extra == 'dev'", specifier = ">=0.6,<1.0" },
     { name = "scipy", marker = "extra == 'agenteval-advanced'", specifier = ">=1.11,<2.0" },
 ]
-provides-extras = ["dev", "claude-code", "claude-sdk", "openai-agents", "codex", "copilot", "agenteval-advanced"]
+provides-extras = ["dev", "claude-code", "claude-sdk", "openai-agents", "codex", "copilot", "agenteval-advanced", "otlp"]
 
 [[package]]
 name = "robotframework-assertion-engine"
```

codex
Reviewing Story 13.2 as a code review, not an implementation task. I’m starting by re-deriving the spec claims from the cited PRD/architecture/epic sources and reading the touched telemetry code paths before I test the behavioral probes.
exec
/bin/bash -lc "sed -n '1248,1260p' _bmad-output/planning-artifacts/prd.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
| `[claude-code]` | `coding_agent/claude_code_cli.py` — Claude Code CLI adapter (`--output-format=stream-json`) | **1** | When evaluating against Claude Code CLI (Skill / MCP runtime target; dogfood path) |
| `[claude]` | `coding_agent/claude_agent_sdk.py` — Claude Agent SDK adapter (subprocess JSON-lines bridge) | 2 | When evaluating against Claude Agent SDK Python runtime specifically |
| `[openai-agents]` | `coding_agent/openai_agents.py` — OpenAI Agents SDK adapter | 2 | When evaluating against OpenAI Agents SDK runtime specifically |
| `[codex]` | `coding_agent/codex_cli.py` — Codex CLI adapter (JSON event stream) | 2 | When evaluating against Codex CLI runtime specifically |
| `[copilot]` | `coding_agent/copilot_cli.py` — GitHub Copilot CLI adapter (`-p --output-format=json` live + `~/.copilot/session-state/{uuid}/events.jsonl` post-hoc) | 2 | When evaluating against GitHub Copilot CLI (Skill / MCP runtime target — empirically verified Tier-1-grade) |
| `[otlp]` | `opentelemetry-exporter-otlp` for OTLP trace export to Datadog / Grafana / Tempo | 2 | When wiring traces into a hosted observability backend |
| `[judge]` | `Judge.` sub-library (`Get Score`, rubric loader, calibration cookbook) | 2 | When using LLM-as-judge keywords |
| `[agenteval-advanced]` | `Stat.` advanced primitives — Mann-Whitney U, Cliff's δ, bootstrap CI (adds `scipy` dep) | 2 | When doing cross-model statistical comparison or research-grade analysis |
| `[lint]` | `shellcheck-py` for hook-script linting | 2 | When using `Hook.` static-inspection keywords with shell-script checks |
| `[bench]` | `datasets` for HumanEval / SWE-bench fixture loaders | 3 | When using benchmark suites |
| `[dev]` | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `robotframework-tidy` | All | Contributors only |

**Install size discipline:** the default install is intentionally minimal. Heavy / niche dependencies are extras. No extras are auto-installed by transitive dependency on the default install.

exec
/bin/bash -lc "sed -n '1544,1553p' _bmad-output/planning-artifacts/prd.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:

### 6. Trace Recording & Observability

- **FR32:** Library emits OpenTelemetry GenAI-conformant spans for every agent run (`invoke_agent → chat → execute_tool`); span hierarchy + `gen_ai.*` attribute coverage verifiable via `Get Run Spans <run>` returning a `list[Span]` and conformance-suite span-shape assertions.
- **FR33a (Listener):** Library registers `agenteval.telemetry.otel_listener:OTelListener` via `[project.entry-points."robot.listener"]`; opt-in via `__init__(telemetry=True)` (default on).
- **FR33b (backends):** Library emits trace artifacts to `memory` backend by default + `jsonl` backend (Phase 1) + `otlp` backend (Phase 2 via `[otlp]` extra); verifiable via `Get Trace Backend Names` returning configured backends.
- **FR34a (evidence-block format):** Every assertion keyword writes a self-contained evidence block to the Robot Framework log on both pass and fail in the format documented in `docs/contracts/evidence-block-format.md` — header line, threshold-vs-observed table, raw-artifact section (response / trajectory / tool-call trace); verifiable via `Get Last Evidence Block <keyword>` returning parsed sections (`AC-SIMPLICITY-01`).
- **FR34b (visual contract):** The evidence-block visual contract specifies: monospace fenced section with header `┌─ EVIDENCE ─┐ <keyword> <PASS|FAIL> ─┐`, three sub-sections (`Compared:`, `Observed:`, `Raw:`), and uniform truncation (`...` after 1000 chars per field with link to full artifact). Verifiable via the conformance suite's evidence-block-format snapshot fixtures.
- **FR35:** Library performs server-side observation of `tools/call` invocations on every MCP server it spawns (regardless of which agent invoked them), populating each `ToolCallTrace.source` field with `"hosted_mcp"`; adapter-side trace extractions populate `source="adapter"`. Verifiable via `Get Tool Call Sources <run>` returning the `set[str]` of sources present.
- **FR36a (`completeness` field):** Every `AgentRunResult.metadata.completeness` field is REQUIRED and adapter MUST emit `"truncated"` when the agent exits non-zero mid-stream or its event parser fails to reach a terminal event. Verifiable via `Run Keyword With Mock Agent killed_at=mid_stream Send Prompt ...` + assertion that the resulting `AgentRunResult.metadata.completeness == "truncated"`.

exec
/bin/bash -lc "sed -n '1254,1263p' _bmad-output/planning-artifacts/architecture.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
│       ├── telemetry/                      # Per agentguard ADR-012 pattern (borrowed, evaluated on merit) + Decision-2
│       │   ├── __init__.py
│       │   ├── listener.py                 # RF Listener v3 entry point (registered via [project.entry-points."robot.listener"]) per FR33a. (Story 5.1 pre-create-story drift fix 2026-05-20: was `otel_listener.py` borrowing agentguard's name; ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 say `listener.py`.)
│       │   ├── spans.py                    # OTel span emission helpers (invoke_agent → chat → execute_tool) per FR32 + Step-5 semconv convention
│       │   ├── backends.py                 # memory / jsonl backends Phase 1; otlp dispatch Phase 2 per FR33b
│       │   └── semconv.py                  # Internal facade for gen_ai.* attribute names per NFR-COMPAT-06
│       │
│       ├── mcp/                            # MCP sub-library
│       │   ├── __init__.py
│       │   ├── library.py                  # MCP keywords: Get Server Config, Start/Connect/Stop Server, Get Tools, Call Tool, Get Tool Discoverability per FR5-11 + FR11b

exec
/bin/bash -lc "sed -n '2159,2176p' _bmad-output/planning-artifacts/epics.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
#### Story 13.2: OTLP Trace Backend

As an **observability-focused user** (Raj or Priya integrating with production observability stacks),
I want `trace_backend="otlp"` shipping JSONL spans to an OTLP collector,
So that AgentEval traces flow into Jaeger / Honeycomb / Tempo / Grafana for production observability.

**Acceptance Criteria:**

**Given** `trace_backend="otlp"` + `otlp_endpoint="http://localhost:4318/v1/traces"` configuration,
**When** spans are emitted during a test,
**Then** they are exported via OTLP HTTP protocol to the configured endpoint; integration test verifies round-trip against a local OTLP collector docker container.

**And** OTLP backend supports both gRPC (`otlp_endpoint="grpc://..."`) and HTTP (`otlp_endpoint="http://..."`) per OTel SDK conventions.

**And** Recipe Gallery #8 (CI integration) is updated with an OTLP integration example showing trace data flowing into a Honeycomb/Jaeger dashboard.

---


exec
/bin/bash -lc "sed -n '668,678p' _bmad-output/planning-artifacts/architecture.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  - `get_latency(test_id: str) -> float` — sum of span durations.
  - `get_run_manifest(test_id: str) -> RunManifest` — assembled per FR39 from resource attributes + library version + redaction-policy hash.
- Backend dispatch in `agenteval/telemetry/`:
  - `memory` backend (default) — keeps InMemorySpanExporter state for the RF run; cleared per-test on `start_test`.
  - `jsonl` backend (Phase 1) — serializes InMemorySpanExporter spans to `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` on `end_test` via custom JSON formatter producing OTLP-compatible JSON shape.
  - `otlp` backend (Phase 2 via `[otlp]` extra) — swaps `InMemorySpanExporter` for `OTLPSpanExporter`; configured via `__init__(trace_backend="otlp", otlp_endpoint=...)`.

**Cascading implications:**

- All `Metric.*` keywords (FR19-22) read from `_kernel/trace_store` via the projection accessors — no direct span access by sub-libraries.
- `RunManifest` Pydantic dataclass (per FR39) is constructed from trace store metadata, not separately collected.

exec
/bin/bash -lc "sed -n '1,420p' src/AgentEval/telemetry/listener.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
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

"""Robot Framework Listener v3 entry point for agenteval (Story 5.1).

Implements the Regular RF Listener v3 contract per
``docs/contracts/listener-integration.md`` (Phase-1 skeleton filled by this
story). NOT a Library Listener (Library Listeners' ``close()`` fires BEFORE
RF writes xunit/output files; empirically disqualified 2026-05-17).

Canonical user-facing invocation:

    robot --listener AgentEval.telemetry.listener tests/

The ``--listener`` flag is REQUIRED (RF does NOT auto-discover listeners from
PyPA entry-points; empirically verified 2026-05-17 per
``docs/contracts/listener-integration.md`` L20). The entry-point registration
at ``[project.entry-points."robot.listener"]`` is for Phase-2 tooling that
explicitly walks the listener group.

Listener responsibilities (per Story 5.1 ACs):

1. Wire the OTel TracerProvider once with the
   ``RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter)`` chain
   (single redaction choke point per NFR-SEC-01 / FR38a + architecture
   L679 + L1193). Idempotent — only configures on first ``start_suite``.
2. On ``start_test``: extract the test's ``longname`` (canonical RF Listener
   v3 path), call ``_kernel/context.set_current_test_id(test_id, suite_id)``.
3. On ``end_test``: flush JSONL backend if enabled, then ``clear_spans(test_id)``
   for per-test isolation.
4. Reserve ``xunit_file(path)`` + ``output_file(path)`` hooks for Story 8a.1
   xunit-enrichment (Story 5.1 ships no-op signatures so Story 8a.1 can fill
   without touching this file's surface).
5. Resolve ``trace_backend`` + ``trace_path`` via Story 4.3's 4-level
   ConfigValue precedence (init_arg → env → dotenv → default).

Story 5.4 forward-ref: missing-longname graceful degradation emits a warning
(``UserWarning`` placeholder; ``DegradedTraceWarning`` upgrade tracked at
DF-5.1-S1 once Story 5.4 lands the class).

References:
    - architecture L1248: telemetry/listener.py
    - architecture L1554: Listener v3 lifecycle (start_test → set_current_test_id)
    - listener-integration.md (ratified contract Phase-1 skeleton)
    - ADR-009: Per-Test MCP Server Scope via Listener v3 ``test_id``
    - Story 1b.1: ``_kernel/context.set_current_test_id``, ``MCPLifecycleManager``
    - Story 1b.2: ``_kernel/trace_store._configure_tracer_provider``,
      ``RedactionProcessor``, ``clear_spans``
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import warnings
from datetime import UTC
from pathlib import Path
from typing import Any, Literal, cast

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace import Span as SDKSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval._kernel.redaction import RedactionProcessor
from AgentEval.errors import DegradedTraceWarning
from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend, OTLPBackend
from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID

__all__ = [
    "Listener",
    "TestIdContextSpanProcessor",
    "register_active_observer",
    "record_active_run_metadata",
]

# Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2): pre-edit
# `Listener.register_observer` was dead code — neither the Generic adapter
# nor the Claude Code CLI adapter wired its per-call observer into the
# Listener registry, so `end_test → observer.clear()` never fired in
# production. The Listener is a process singleton (registered by RF when
# `--listener AgentEval.telemetry.listener` is passed); adapters need a
# weak coupling that finds the active Listener without importing it
# directly (which would create a kernel-vs-telemetry layering violation).
# We use a module-level WeakRef set + `register_active_observer()` helper
# that adapters call from `run()`. The Listener registers itself with
# this module on instantiation; if no Listener is active (direct Python
# invocation outside RF), `register_active_observer` is a no-op.
_active_listeners: list[Any] = []


def register_active_observer(observer: Any) -> None:
    """Register an observer with every active `Listener` instance.

    Adapters call this from their `run()` method when they construct a
    per-call `HostedMcpObserver`; the Listener's `end_test` hook then
    calls `observer.clear()` on each registered observer for per-test
    cleanup per ADR-009.

    No-op when no Listener is active (direct Python invocation outside
    RF). Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2).
    """
    for listener in _active_listeners:
        register_fn = getattr(listener, "register_observer", None)
        if callable(register_fn):
            with contextlib.suppress(Exception):
                register_fn(observer)


def record_active_run_metadata(**metadata: Any) -> None:
    """Record per-run operational metadata for the RunManifest sidecar (Story 5.3).

    Adapters call this from their `run()` post-completion path with the
    operational fields the Story 5.3 RunManifest needs (adapter_name,
    adapter_version, model, mcp_servers, total_cost_usd, completeness,
    mcp_coverage, seed, prompt_hashes). The Listener accumulates these
    via `Listener.record_run_metadata` + emits the JSON sidecar on
    `end_test`.

    Helper parallels `register_active_observer` from Story 5.2 — finds
    active listeners + dispatches to each. No-op when no Listener is
    active (direct Python invocation outside RF).
    """
    for listener in _active_listeners:
        record_fn = getattr(listener, "record_run_metadata", None)
        if callable(record_fn):
            with contextlib.suppress(Exception):
                record_fn(**metadata)


_log = logging.getLogger(__name__)


class TestIdContextSpanProcessor(SpanProcessor):
    """Stamp ``agenteval.test_id`` on every span at on_start from kernel context.

    OTel SDK semantics:
        - ``Resource`` attributes are immutable per-``TracerProvider``; cannot
          be updated per-test.
        - ``set_tracer_provider`` is idempotent (logs a warning on re-set).
        - ``SpanProcessor.on_start(span, parent_context)`` IS the
          per-span hook where dynamic context can be stamped.

    Story 5.1 uses this hook to read ``_kernel/context.current_context().test_id``
    and write it as the ``agenteval.test_id`` span attribute. ``trace_store``'s
    ``_span_test_id`` falls back to ``span.attributes`` per Story 1b.2 H_R2,
    so this is the canonical Phase-1 per-test discriminator.

    Why this works under pabot: each worker process has its own TracerProvider
    + its own ``_kernel/context`` state; the SpanProcessor reads from worker-
    local state. No cross-worker contention.
    """

    def on_start(self, span: SDKSpan, parent_context: otel_context.Context | None = None) -> None:  # noqa: ARG002
        ctx = _kernel_context.current_context()
        if ctx is not None and ctx.test_id:
            span.set_attribute(AGENTEVAL_TEST_ID, ctx.test_id)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


class Listener:
    """Robot Framework Listener v3 implementation for agenteval.

    Register via ``robot --listener AgentEval.telemetry.listener tests/``.

    Phase-1 trace backend selection: reads ``trace_backend`` config value
    (``"memory"`` default per Story 1a.6) at ``start_suite``. JSONL output
    path resolved from ``trace_path`` config value; falls back to RF's
    ``${OUTPUTDIR}`` attribute on ``start_suite`` when unset.
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self) -> None:
        """Initialize the listener; defer expensive setup to ``start_suite``."""
        self._tracer_configured: bool = False
        self._backend: MemoryBackend | JSONLBackend | OTLPBackend = MemoryBackend()
        self._output_dir: Path | None = None
        self._mcp_per_test: bool | str = True
        # Story 5.2: per-test observer registry. Adapters register their
        # `HostedMcpObserver` instance via the module-level
        # `register_active_observer()` helper during `run()`; Listener's
        # `end_test` calls `observer.clear()` on every registered observer
        # for per-test cleanup per ADR-009.
        self._observers: list[Any] = []
        # Story 5.3: per-test operational-metadata accumulator. Adapters
        # call `record_active_run_metadata(...)` from `run()` post-completion;
        # Listener's `end_test` uses this to populate the extended
        # RunManifest's Optional fields per FR39 + epics.md L1502.
        self._current_run_metadata: dict[str, Any] = {}
        # Story 8a.1: per-test frozen snapshot of all data needed by the
        # `xunit_file` hook (which runs AFTER `end_test` cleared spans).
        # Keyed by `test_id` (RF `full_name`); snapshot built in `end_test`
        # BEFORE `trace_store.clear_spans` so trace projections are still
        # readable. Values are dicts with keys: adapter, model, cost_usd,
        # completeness, mcp_coverage, total_tokens, latency_seconds,
        # trace_id, tier_breakdown, evidence_block, warnings.
        self._completed_run_metadata: dict[str, dict[str, Any]] = {}
        # Register this Listener with the module-level active-listeners
        # list so `register_active_observer()` + `record_active_run_metadata()`
        # can find it.
        _active_listeners.append(self)

    # --------------------------------------------------------------- #
    # Tracer setup (idempotent)
    # --------------------------------------------------------------- #

    def _configure_tracer_provider(self) -> None:
        """Wire the TracerProvider with the agenteval SpanProcessor chain.

        Idempotent at PROCESS scope (not per-instance) — the SECOND `Listener`
        instantiated in the same process MUST NOT stack a duplicate set of
        processors onto the existing TracerProvider. Story 5.1 code-review
        3-way HIGH-A fix 2026-05-20 (Blind H1 + Codex empirical probe +
        Edge-cases M4): pre-edit checked only the per-instance
        `_tracer_configured` flag, so under pabot worker reuse OR test
        harness re-instantiation the resilient-attach branch added 3 more
        processors → 6 total → every span stamped/redacted/exported TWICE
        (Codex empirically verified processor count of 6 after 2 start_suite
        calls). Now gated by a PROCESS-GLOBAL sentinel attribute
        (`_agenteval_listener_attached`) set on the active TracerProvider;
        once True, all future calls are no-ops.
        """
        if self._tracer_configured:
            return

        # Process-scope sentinel: if any prior Listener instance (or any other
        # caller) has already attached the agenteval processor chain to the
        # active TracerProvider, do not attach again. The sentinel lives on
        # the provider object itself so it survives across Listener instances
        # but resets when the provider is replaced (e.g., test fixtures).
        existing = trace.get_tracer_provider()
        if getattr(existing, "_agenteval_listener_attached", False):
            self._tracer_configured = True
            return

        # Story 5.1 design note (ratified into listener-integration.md
        # Trace backplane section per Story 5.1 code-review Auditor H5 fix):
        # OTel TracerProvider Resource attributes are IMMUTABLE per-provider;
        # we cannot re-write `agenteval.test_id` per test. Story 1b.2's
        # `_span_test_id` falls back to span.attributes when the Resource
        # doesn't carry the key — we leverage that fallback by deliberately
        # NOT pre-populating `agenteval.test_id` on the Resource. The
        # per-test stamping happens via `TestIdContextSpanProcessor.on_start`
        # which reads `_kernel/context.current_context().test_id` and sets
        # the SPAN-level attribute. Pre-populating the Resource with an
        # empty string would defeat the fallback (trace_store would read
        # the empty Resource value and never check span attributes).
        resource = Resource.create({})
        provider = TracerProvider(resource=resource)
        # Per-test discriminator: stamps `agenteval.test_id` on every span at
        # on_start from `_kernel/context`. Must run BEFORE RedactionProcessor
        # so the test_id is set before any other processor reads attributes.
        provider.add_span_processor(TestIdContextSpanProcessor())
        # RedactionProcessor BEFORE the exporter in the chain — single choke
        # point per NFR-SEC-01.
        provider.add_span_processor(RedactionProcessor())
        # SimpleSpanProcessor wraps the InMemorySpanExporter from Story 1b.2.
        # Synchronous export over BatchSpanProcessor was a deliberate choice
        # ratified in listener-integration.md Contract section — Phase-1 trace
        # volume is small + mid-test projection-accessor queries need to see
        # spans without a force_flush plumbing trip.
        provider.add_span_processor(SimpleSpanProcessor(trace_store._get_exporter()))  # noqa: SLF001
        # OTel's `set_tracer_provider` is one-shot per process: subsequent
        # calls log a warning and are silently rejected. If a prior caller
        # set a provider that didn't carry our sentinel, attach our
        # processors to it (post-sentinel-check guards against duplicates).
        if isinstance(existing, TracerProvider) and existing is not provider:
            existing.add_span_processor(TestIdContextSpanProcessor())
            existing.add_span_processor(RedactionProcessor())
            existing.add_span_processor(
                SimpleSpanProcessor(trace_store._get_exporter())  # noqa: SLF001
            )
            target_provider: TracerProvider = existing
        else:
            trace.set_tracer_provider(provider)
            target_provider = provider
        # Mark the active provider so future Listener instances in this
        # process see the sentinel + short-circuit before stacking duplicates.
        target_provider._agenteval_listener_attached = True  # type: ignore[attr-defined]
        # Story 1b.2's `_configure_tracer_provider` is the placeholder;
        # invoke it for downstream-consumer compatibility.
        trace_store._configure_tracer_provider()  # noqa: SLF001
        self._tracer_configured = True

    def _attach_otlp_exporter_if_needed(self) -> None:
        """Attach a `BatchSpanProcessor(OTLPSpanExporter)` to the active provider when `OTLPBackend` is selected.

        Called from ``start_suite`` AFTER ``_resolve_backend`` so the
        backend selection is known. Process-scope idempotency: the active
        TracerProvider carries an ``_agenteval_otlp_attached`` sentinel
        once the OTLP processor is attached, so subsequent Listener
        instances in the same process (pabot worker reuse + test harness
        re-instantiation) do NOT stack duplicate OTLP processors. Mirrors
        the ``_agenteval_listener_attached`` sentinel pattern from Story
        5.1 HIGH-A fix.

        Dual-export design (Story 13.2 D-7): the in-memory chain
        (``SimpleSpanProcessor(InMemorySpanExporter)``) remains attached
        unconditionally for projection-accessor compatibility; the OTLP
        processor is an ADDITIONAL exporter, NOT a replacement.
        """
        if not isinstance(self._backend, OTLPBackend):
            return
        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            # Real OTel TracerProvider not active (proxy stub during tests
            # without Listener wiring). Nothing to attach to.
            return
        if getattr(provider, "_agenteval_otlp_attached", False):
            return
        provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))  # noqa: SLF001
        provider._agenteval_otlp_attached = True  # type: ignore[attr-defined]

    # --------------------------------------------------------------- #
    # Robot Framework Listener v3 hooks
    # --------------------------------------------------------------- #

    def start_suite(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``start_suite`` hook — configure tracer on first invocation.

        Args:
            data: RF ``TestSuite`` object (Listener v3 API).
            result: RF ``TestSuiteResult`` object (Listener v3 API).
        """
        self._configure_tracer_provider()
        # Resolve trace_backend + output_dir from RF context.
        self._resolve_backend(suite=data)
        # Story 13.2 (Epic 13) — attach the OTLP BatchSpanProcessor AFTER
        # backend selection. No-op for memory + jsonl backends; OTLP
        # branch lights up the FR33b OTLP export path with the dual-export
        # design (existing in-memory exporter remains attached).
        self._attach_otlp_exporter_if_needed()

    def start_test(self, data: Any, result: Any) -> None:  # noqa: ARG002
        """RF Listener v3 ``start_test`` hook — set per-test scope.

        Extracts ``data.full_name`` (canonical Listener v3 path; replaces
        the v2 ``attrs["longname"]`` shape) and binds it to
        ``_kernel/context.set_current_test_id`` so MCP servers + adapters +
        spans share the test scope. Honors PRD FR40's ``mcp_per_test``
        config — resolved at ``start_suite`` and threaded through here so
        ADR-009's per-test vs. per-suite scope decision flows from config
        to kernel context.

        Story 5.1 code-review Auditor H3 fix 2026-05-20: pre-edit dropped
        the ``scope=`` argument so every test bound `Scope = "test"`
        regardless of FR40 / `mcp_per_test` config. Now resolved via
        `_kernel/context._resolve_scope(mcp_per_test)`.
        """
        # Story 5.1 code-review Blind MED-1 fix 2026-05-20: defensive
        # unbind before any early-return path — if a prior test's end_test
        # also degraded (missing full_name), the prior context can stay
        # bound across the boundary and pollute the next test's spans.
        _kernel_context.unbind_context()
        # Story 5.3: reset per-test operational metadata accumulator so a
        # prior test's adapter calls don't leak into the next test's
        # RunManifest sidecar.
        self._current_run_metadata = {}
        test_id = self._extract_longname(data)
        suite_id = self._extract_suite_id(data)
        if not test_id:
            _msg = (
                "AgentEval Listener: missing test full_name on start_test; "
                "spans will carry an empty agenteval.test_id span attribute"
            )
            # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
            # filter doesn't drop the structured channel.
            _agenteval_warnings.record_warning(
                warning_type="AgentEval.errors.DegradedTraceWarning",
                message=_msg,
                source="telemetry.listener",
                remediation=(
                    "Verify RF emits a non-empty `full_name` on TestCase; "
                    "check listener data-object shape if running outside RF runtime"
                ),
            )
            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
            return
        scope = _kernel_context._resolve_scope(  # noqa: SLF001
            cast("bool | Literal['suite']", self._mcp_per_test)
        )
        _kernel_context.set_current_test_id(test_id, suite_id=suite_id, scope=scope)
        # Story 8a.2 AC-8a.2.1 (FR51): surface `trace_id` as a `<tag>` on the
        # test in `output.xml` so CI log spelunking + observability dashboards
        # can link RF reports to JSONL trace artifacts. The tag value is the
        # canonical RF `full_name` (mirrors `RunManifest.test_id` + JSONL
        # `trace__<suite>__<test>.jsonl` naming). Failure-mode contract:
        # missing/None `result.tags` or `add()` raise must not mask the test —
        # log WARN + continue.
        #
        # IMPORTANT (Story 8a.2 dev empirical finding 2026-05-25): tags must be
        # added to `result.tags`, NOT `data.tags`. Empirical RF Listener v3
        # behavior: `data.tags.add(...)` does NOT surface in `output.xml`;

exec
/bin/bash -lc "sed -n '1,260p' src/AgentEval/telemetry/backends.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
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

"""Trace backends for Story 5.1 — memory (default) + JSONL (opt-in).

Per PRD FR33b ("memory + JSONL backends Phase 1; OTLP Phase 2 via ``[otlp]``
extra"). Memory backend is a thin wrapper around Story 1b.2's
``_kernel/trace_store`` projection accessors; JSONL backend serializes spans
to a one-line-per-span JSONL file at flush time.

JSONL artifact path convention (per PRD FR51 + Story 5.1 AC-5.1.6):

    <output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl

Story 5.4 forward-ref: JSONL write failures emit ``DegradedTraceWarning``
(Story 5.4 lands the class). Story 5.1 uses ``warnings.warn`` with a future-
class TODO; DF-5.1-S1 tracks the upgrade.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from AgentEval._kernel import trace_store
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval.errors import DegradedTraceWarning

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

__all__ = [
    "MemoryBackend",
    "JSONLBackend",
    "OTLPBackend",
]

# Story 13.2 (Epic 13) — Phase-2 `[otlp]` extra gate.
# `opentelemetry-exporter-otlp` is a metapackage shipping BOTH the HTTP and
# gRPC trace exporters. Probe both at gate time so a partial install (only
# one transport available) is treated the same as no install — the operator
# explicitly opted into the full `[otlp]` extra, so partial coverage is a
# bug we want to surface loudly.
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as _OTLPSpanExporterGRPC,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as _OTLPSpanExporterHTTP,
    )

    _OTLP_AVAILABLE = True
    _OTLP_IMPORT_ERROR: ImportError | None = None
except ImportError as _otlp_err:  # pragma: no cover  -- exercised via monkeypatch
    _OTLPSpanExporterHTTP = None  # type: ignore[misc, assignment]
    _OTLPSpanExporterGRPC = None  # type: ignore[misc, assignment]
    _OTLP_AVAILABLE = False
    _OTLP_IMPORT_ERROR = _otlp_err


def _raise_otlp_extra_missing() -> None:
    """Raise the canonical `[otlp]` extra-missing ImportError.

    Per Story 13.2 D-5 + AC-13.2.1: the message MUST recommend
    ``uv pip install robotframework-agenteval[otlp]`` so operators can
    resolve the partial install in one command.
    """
    raise ImportError(
        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
    ) from _OTLP_IMPORT_ERROR


# Allow alnum + `_-.` only; anything else collapses to `_` to avoid path traversal.
_PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9_.\-]")


def _sanitize_path_segment(segment: str) -> str:
    """Replace path-unsafe characters with `_` to prevent traversal via test_id/suite_id.

    Story 5.1 code-review 2-way MED fix 2026-05-20 (Blind MED-2 + Edge-cases
    M1): pre-edit allowed ``.``-only segments (``..``, ``...``) through
    verbatim because the regex permits ``.``. POSIX path components are flat
    so traversal didn't actually escape, but the safety guarantee was
    accidental — defense-in-depth says reject the literal `.` / `..` /
    all-dot patterns explicitly.
    """
    sanitized = _PATH_SAFE_RE.sub("_", segment)
    if not sanitized:
        return "_"
    # Reject `.` / `..` / all-dot segments outright — they're path-component
    # semantics, not data, even on POSIX where they can't traverse a single
    # filename segment.
    if sanitized.strip(".") == "":
        return "_"
    return sanitized


class MemoryBackend:
    """In-memory trace backend (default per PRD FR42).

    Thin wrapper around Story 1b.2's ``_kernel/trace_store`` projection
    accessors. Memory backend isolation is enforced by the
    ``agenteval.test_id`` Resource attribute filter at the trace_store layer
    (Story 1b.2 H_R2). This class exists primarily so the Listener has a
    uniform backend API; consumers query traces via the public
    ``_kernel/trace_store`` accessors directly.

    No persistence; spans are cleared via ``clear_spans(test_id)`` after
    each test (Listener's ``end_test`` hook).
    """

    name = "memory"

    def flush_test(self, test_id: str, suite_id: str = "", output_dir: Path | None = None) -> None:
        """No-op flush. The InMemorySpanExporter already holds spans in memory.

        Args:
            test_id: RF Listener v3 test identifier.
            suite_id: RF Listener v3 suite identifier (unused for memory).
            output_dir: Unused for memory; accepted for API uniformity.
        """
        _ = test_id
        _ = suite_id
        _ = output_dir


class JSONLBackend:
    """JSONL trace backend (opt-in via ``trace_backend="jsonl"``).

    On ``flush_test``, serializes all spans for the test into one JSON line
    per span at ``<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl``.

    On write failure: emits a warning (forward-ref to Story 5.4's
    ``DegradedTraceWarning``) and does NOT raise — test outcomes must not
    be masked by trace-backend hygiene. The spans are preserved in memory
    (clear is gated on a successful write per Story 5.1 AC-5.1.6).
    """

    name = "jsonl"

    def flush_test(
        self,
        test_id: str,
        suite_id: str = "",
        output_dir: Path | None = None,
    ) -> Path | None:
        """Serialize all spans for ``test_id`` to a JSONL file.

        Args:
            test_id: RF Listener v3 test identifier.
            suite_id: RF Listener v3 suite identifier (used in the filename).
            output_dir: Directory to write the JSONL artifact into. When
                ``None``, falls back to ``Path.cwd()``. The function creates
                ``<output_dir>/agenteval/`` if missing.

        Returns:
            The written file path on success; ``None`` on write failure
            (after emitting a warning).
        """
        spans = trace_store.get_run_spans(test_id)
        # Story 5.1 code-review Edge-cases M3 fix 2026-05-20: skip writing
        # the JSONL file entirely when the test produced zero spans —
        # phantom 0-byte artifacts mislead operators into thinking the test
        # was traced when in reality it ran without span emission.
        if not spans:
            return None
        target_dir = (output_dir if output_dir is not None else Path.cwd()) / "agenteval"
        safe_suite = _sanitize_path_segment(suite_id or "_suite")
        safe_test = _sanitize_path_segment(test_id or "_test")
        target_path = target_dir / f"trace__{safe_suite}__{safe_test}.jsonl"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            with target_path.open("w", encoding="utf-8") as fp:
                for span in spans:
                    fp.write(_span_to_jsonl_line(span))
                    fp.write("\n")
        except (OSError, ValueError, RecursionError) as exc:
            # Story 5.1 code-review HIGH-J fix 2026-05-20 (Edge-cases H2):
            # pre-edit only caught OSError. ValueError (json.dumps circular
            # references) and RecursionError (deep nesting) propagated past
            # flush_test → end_test → into RF Listener machinery, violating
            # AC-5.1.6's "backend failures must not mask test outcomes"
            # guarantee. Now widened to the full JSON-serialization failure
            # surface. Story 5.4 dual-channel emit: warnings.warn fires the
            # Python channel (preserves `-W error::DegradedTraceWarning`
            # filter behavior) AND record_warning captures the structured
            # record for the per-test buffer + RunManifest.warnings field.
            _msg = (
                f"AgentEval JSONL backend write failed at {target_path}: {exc}; "
                "spans preserved in memory backend for next attempt"
            )
            # Story 5.4 code-review 1-way Blind HIGH-C fix 2026-05-20:
            # record THEN warn so `-W error::DegradedTraceWarning` filter
            # (which raises on warnings.warn) does NOT drop the structured
            # buffer record. Operators most interested in surfacing
            # degraded-trace events are exactly the ones running with
            # `-W error` — the pre-edit order silently lost the
            # structured channel for them.
            _agenteval_warnings.record_warning(
                warning_type="AgentEval.errors.DegradedTraceWarning",
                message=_msg,
                source="telemetry.backends.jsonl",
                remediation=(
                    "Inspect filesystem permissions + disk space at the trace "
                    "output directory; re-run with AGENTEVAL_TRACE_BACKEND=memory "
                    "to bypass JSONL persistence if the failure is transient"
                ),
            )
            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
            return None
        return target_path


def _span_to_jsonl_line(span: ReadableSpan) -> str:
    """Serialize one ``ReadableSpan`` to a JSON line.

    Schema (Phase-1; aligned to OTel JSON envelope shape but not strictly
    OTel-LP-compliant; Phase-2 OTLP backend will use the canonical envelope):

        {
          "name": "<span name>",
          "trace_id": "<32-hex trace id>",
          "span_id": "<16-hex span id>",
          "parent_span_id": "<16-hex span id> | null",
          "start_time_unix_ns": <int>,
          "end_time_unix_ns": <int>,
          "attributes": {<key>: <value>, ...},
          "resource_attributes": {<key>: <value>, ...},
          "status": {"status_code": "OK"|"ERROR"|"UNSET", "description": <str>|null}
        }

    On any serialization failure for a specific attribute value, fall back
    to ``str(value)`` so the overall write proceeds.
    """
    ctx = span.get_span_context()
    parent_ctx = span.parent
    record = {
        "name": span.name,
        "trace_id": f"{ctx.trace_id:032x}" if ctx is not None else None,
        "span_id": f"{ctx.span_id:016x}" if ctx is not None else None,
        "parent_span_id": f"{parent_ctx.span_id:016x}" if parent_ctx is not None else None,
        "start_time_unix_ns": span.start_time,
        "end_time_unix_ns": span.end_time,
        "attributes": _safe_dict(dict(span.attributes) if span.attributes else {}),
        "resource_attributes": _safe_dict(
            dict(span.resource.attributes) if span.resource and span.resource.attributes else {}

codex
I’ve confirmed the baseline spec text and the existing telemetry wiring. Next I’m probing the live code paths: backend resolution, provider attachment, exporter constructor behavior, and the new tests/docs claims.
exec
/bin/bash -lc "nl -ba src/AgentEval/telemetry/backends.py | sed -n '1,220p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Trace backends for Story 5.1 — memory (default) + JSONL (opt-in).
    16	
    17	Per PRD FR33b ("memory + JSONL backends Phase 1; OTLP Phase 2 via ``[otlp]``
    18	extra"). Memory backend is a thin wrapper around Story 1b.2's
    19	``_kernel/trace_store`` projection accessors; JSONL backend serializes spans
    20	to a one-line-per-span JSONL file at flush time.
    21	
    22	JSONL artifact path convention (per PRD FR51 + Story 5.1 AC-5.1.6):
    23	
    24	    <output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl
    25	
    26	Story 5.4 forward-ref: JSONL write failures emit ``DegradedTraceWarning``
    27	(Story 5.4 lands the class). Story 5.1 uses ``warnings.warn`` with a future-
    28	class TODO; DF-5.1-S1 tracks the upgrade.
    29	"""
    30	
    31	from __future__ import annotations
    32	
    33	import json
    34	import re
    35	import warnings
    36	from pathlib import Path
    37	from typing import TYPE_CHECKING
    38	
    39	from AgentEval._kernel import trace_store
    40	from AgentEval._kernel import warnings as _agenteval_warnings
    41	from AgentEval.errors import DegradedTraceWarning
    42	
    43	if TYPE_CHECKING:
    44	    from opentelemetry.sdk.trace import ReadableSpan
    45	
    46	__all__ = [
    47	    "MemoryBackend",
    48	    "JSONLBackend",
    49	    "OTLPBackend",
    50	]
    51	
    52	# Story 13.2 (Epic 13) — Phase-2 `[otlp]` extra gate.
    53	# `opentelemetry-exporter-otlp` is a metapackage shipping BOTH the HTTP and
    54	# gRPC trace exporters. Probe both at gate time so a partial install (only
    55	# one transport available) is treated the same as no install — the operator
    56	# explicitly opted into the full `[otlp]` extra, so partial coverage is a
    57	# bug we want to surface loudly.
    58	try:
    59	    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    60	        OTLPSpanExporter as _OTLPSpanExporterGRPC,
    61	    )
    62	    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    63	        OTLPSpanExporter as _OTLPSpanExporterHTTP,
    64	    )
    65	
    66	    _OTLP_AVAILABLE = True
    67	    _OTLP_IMPORT_ERROR: ImportError | None = None
    68	except ImportError as _otlp_err:  # pragma: no cover  -- exercised via monkeypatch
    69	    _OTLPSpanExporterHTTP = None  # type: ignore[misc, assignment]
    70	    _OTLPSpanExporterGRPC = None  # type: ignore[misc, assignment]
    71	    _OTLP_AVAILABLE = False
    72	    _OTLP_IMPORT_ERROR = _otlp_err
    73	
    74	
    75	def _raise_otlp_extra_missing() -> None:
    76	    """Raise the canonical `[otlp]` extra-missing ImportError.
    77	
    78	    Per Story 13.2 D-5 + AC-13.2.1: the message MUST recommend
    79	    ``uv pip install robotframework-agenteval[otlp]`` so operators can
    80	    resolve the partial install in one command.
    81	    """
    82	    raise ImportError(
    83	        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
    84	    ) from _OTLP_IMPORT_ERROR
    85	
    86	
    87	# Allow alnum + `_-.` only; anything else collapses to `_` to avoid path traversal.
    88	_PATH_SAFE_RE = re.compile(r"[^A-Za-z0-9_.\-]")
    89	
    90	
    91	def _sanitize_path_segment(segment: str) -> str:
    92	    """Replace path-unsafe characters with `_` to prevent traversal via test_id/suite_id.
    93	
    94	    Story 5.1 code-review 2-way MED fix 2026-05-20 (Blind MED-2 + Edge-cases
    95	    M1): pre-edit allowed ``.``-only segments (``..``, ``...``) through
    96	    verbatim because the regex permits ``.``. POSIX path components are flat
    97	    so traversal didn't actually escape, but the safety guarantee was
    98	    accidental — defense-in-depth says reject the literal `.` / `..` /
    99	    all-dot patterns explicitly.
   100	    """
   101	    sanitized = _PATH_SAFE_RE.sub("_", segment)
   102	    if not sanitized:
   103	        return "_"
   104	    # Reject `.` / `..` / all-dot segments outright — they're path-component
   105	    # semantics, not data, even on POSIX where they can't traverse a single
   106	    # filename segment.
   107	    if sanitized.strip(".") == "":
   108	        return "_"
   109	    return sanitized
   110	
   111	
   112	class MemoryBackend:
   113	    """In-memory trace backend (default per PRD FR42).
   114	
   115	    Thin wrapper around Story 1b.2's ``_kernel/trace_store`` projection
   116	    accessors. Memory backend isolation is enforced by the
   117	    ``agenteval.test_id`` Resource attribute filter at the trace_store layer
   118	    (Story 1b.2 H_R2). This class exists primarily so the Listener has a
   119	    uniform backend API; consumers query traces via the public
   120	    ``_kernel/trace_store`` accessors directly.
   121	
   122	    No persistence; spans are cleared via ``clear_spans(test_id)`` after
   123	    each test (Listener's ``end_test`` hook).
   124	    """
   125	
   126	    name = "memory"
   127	
   128	    def flush_test(self, test_id: str, suite_id: str = "", output_dir: Path | None = None) -> None:
   129	        """No-op flush. The InMemorySpanExporter already holds spans in memory.
   130	
   131	        Args:
   132	            test_id: RF Listener v3 test identifier.
   133	            suite_id: RF Listener v3 suite identifier (unused for memory).
   134	            output_dir: Unused for memory; accepted for API uniformity.
   135	        """
   136	        _ = test_id
   137	        _ = suite_id
   138	        _ = output_dir
   139	
   140	
   141	class JSONLBackend:
   142	    """JSONL trace backend (opt-in via ``trace_backend="jsonl"``).
   143	
   144	    On ``flush_test``, serializes all spans for the test into one JSON line
   145	    per span at ``<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl``.
   146	
   147	    On write failure: emits a warning (forward-ref to Story 5.4's
   148	    ``DegradedTraceWarning``) and does NOT raise — test outcomes must not
   149	    be masked by trace-backend hygiene. The spans are preserved in memory
   150	    (clear is gated on a successful write per Story 5.1 AC-5.1.6).
   151	    """
   152	
   153	    name = "jsonl"
   154	
   155	    def flush_test(
   156	        self,
   157	        test_id: str,
   158	        suite_id: str = "",
   159	        output_dir: Path | None = None,
   160	    ) -> Path | None:
   161	        """Serialize all spans for ``test_id`` to a JSONL file.
   162	
   163	        Args:
   164	            test_id: RF Listener v3 test identifier.
   165	            suite_id: RF Listener v3 suite identifier (used in the filename).
   166	            output_dir: Directory to write the JSONL artifact into. When
   167	                ``None``, falls back to ``Path.cwd()``. The function creates
   168	                ``<output_dir>/agenteval/`` if missing.
   169	
   170	        Returns:
   171	            The written file path on success; ``None`` on write failure
   172	            (after emitting a warning).
   173	        """
   174	        spans = trace_store.get_run_spans(test_id)
   175	        # Story 5.1 code-review Edge-cases M3 fix 2026-05-20: skip writing
   176	        # the JSONL file entirely when the test produced zero spans —
   177	        # phantom 0-byte artifacts mislead operators into thinking the test
   178	        # was traced when in reality it ran without span emission.
   179	        if not spans:
   180	            return None
   181	        target_dir = (output_dir if output_dir is not None else Path.cwd()) / "agenteval"
   182	        safe_suite = _sanitize_path_segment(suite_id or "_suite")
   183	        safe_test = _sanitize_path_segment(test_id or "_test")
   184	        target_path = target_dir / f"trace__{safe_suite}__{safe_test}.jsonl"
   185	        try:
   186	            target_dir.mkdir(parents=True, exist_ok=True)
   187	            with target_path.open("w", encoding="utf-8") as fp:
   188	                for span in spans:
   189	                    fp.write(_span_to_jsonl_line(span))
   190	                    fp.write("\n")
   191	        except (OSError, ValueError, RecursionError) as exc:
   192	            # Story 5.1 code-review HIGH-J fix 2026-05-20 (Edge-cases H2):
   193	            # pre-edit only caught OSError. ValueError (json.dumps circular
   194	            # references) and RecursionError (deep nesting) propagated past
   195	            # flush_test → end_test → into RF Listener machinery, violating
   196	            # AC-5.1.6's "backend failures must not mask test outcomes"
   197	            # guarantee. Now widened to the full JSON-serialization failure
   198	            # surface. Story 5.4 dual-channel emit: warnings.warn fires the
   199	            # Python channel (preserves `-W error::DegradedTraceWarning`
   200	            # filter behavior) AND record_warning captures the structured
   201	            # record for the per-test buffer + RunManifest.warnings field.
   202	            _msg = (
   203	                f"AgentEval JSONL backend write failed at {target_path}: {exc}; "
   204	                "spans preserved in memory backend for next attempt"
   205	            )
   206	            # Story 5.4 code-review 1-way Blind HIGH-C fix 2026-05-20:
   207	            # record THEN warn so `-W error::DegradedTraceWarning` filter
   208	            # (which raises on warnings.warn) does NOT drop the structured
   209	            # buffer record. Operators most interested in surfacing
   210	            # degraded-trace events are exactly the ones running with
   211	            # `-W error` — the pre-edit order silently lost the
   212	            # structured channel for them.
   213	            _agenteval_warnings.record_warning(
   214	                warning_type="AgentEval.errors.DegradedTraceWarning",
   215	                message=_msg,
   216	                source="telemetry.backends.jsonl",
   217	                remediation=(
   218	                    "Inspect filesystem permissions + disk space at the trace "
   219	                    "output directory; re-run with AGENTEVAL_TRACE_BACKEND=memory "
   220	                    "to bypass JSONL persistence if the failure is transient"

exec
/bin/bash -lc "nl -ba src/AgentEval/telemetry/listener.py | sed -n '250,420p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   250	        if self._tracer_configured:
   251	            return
   252	
   253	        # Process-scope sentinel: if any prior Listener instance (or any other
   254	        # caller) has already attached the agenteval processor chain to the
   255	        # active TracerProvider, do not attach again. The sentinel lives on
   256	        # the provider object itself so it survives across Listener instances
   257	        # but resets when the provider is replaced (e.g., test fixtures).
   258	        existing = trace.get_tracer_provider()
   259	        if getattr(existing, "_agenteval_listener_attached", False):
   260	            self._tracer_configured = True
   261	            return
   262	
   263	        # Story 5.1 design note (ratified into listener-integration.md
   264	        # Trace backplane section per Story 5.1 code-review Auditor H5 fix):
   265	        # OTel TracerProvider Resource attributes are IMMUTABLE per-provider;
   266	        # we cannot re-write `agenteval.test_id` per test. Story 1b.2's
   267	        # `_span_test_id` falls back to span.attributes when the Resource
   268	        # doesn't carry the key — we leverage that fallback by deliberately
   269	        # NOT pre-populating `agenteval.test_id` on the Resource. The
   270	        # per-test stamping happens via `TestIdContextSpanProcessor.on_start`
   271	        # which reads `_kernel/context.current_context().test_id` and sets
   272	        # the SPAN-level attribute. Pre-populating the Resource with an
   273	        # empty string would defeat the fallback (trace_store would read
   274	        # the empty Resource value and never check span attributes).
   275	        resource = Resource.create({})
   276	        provider = TracerProvider(resource=resource)
   277	        # Per-test discriminator: stamps `agenteval.test_id` on every span at
   278	        # on_start from `_kernel/context`. Must run BEFORE RedactionProcessor
   279	        # so the test_id is set before any other processor reads attributes.
   280	        provider.add_span_processor(TestIdContextSpanProcessor())
   281	        # RedactionProcessor BEFORE the exporter in the chain — single choke
   282	        # point per NFR-SEC-01.
   283	        provider.add_span_processor(RedactionProcessor())
   284	        # SimpleSpanProcessor wraps the InMemorySpanExporter from Story 1b.2.
   285	        # Synchronous export over BatchSpanProcessor was a deliberate choice
   286	        # ratified in listener-integration.md Contract section — Phase-1 trace
   287	        # volume is small + mid-test projection-accessor queries need to see
   288	        # spans without a force_flush plumbing trip.
   289	        provider.add_span_processor(SimpleSpanProcessor(trace_store._get_exporter()))  # noqa: SLF001
   290	        # OTel's `set_tracer_provider` is one-shot per process: subsequent
   291	        # calls log a warning and are silently rejected. If a prior caller
   292	        # set a provider that didn't carry our sentinel, attach our
   293	        # processors to it (post-sentinel-check guards against duplicates).
   294	        if isinstance(existing, TracerProvider) and existing is not provider:
   295	            existing.add_span_processor(TestIdContextSpanProcessor())
   296	            existing.add_span_processor(RedactionProcessor())
   297	            existing.add_span_processor(
   298	                SimpleSpanProcessor(trace_store._get_exporter())  # noqa: SLF001
   299	            )
   300	            target_provider: TracerProvider = existing
   301	        else:
   302	            trace.set_tracer_provider(provider)
   303	            target_provider = provider
   304	        # Mark the active provider so future Listener instances in this
   305	        # process see the sentinel + short-circuit before stacking duplicates.
   306	        target_provider._agenteval_listener_attached = True  # type: ignore[attr-defined]
   307	        # Story 1b.2's `_configure_tracer_provider` is the placeholder;
   308	        # invoke it for downstream-consumer compatibility.
   309	        trace_store._configure_tracer_provider()  # noqa: SLF001
   310	        self._tracer_configured = True
   311	
   312	    def _attach_otlp_exporter_if_needed(self) -> None:
   313	        """Attach a `BatchSpanProcessor(OTLPSpanExporter)` to the active provider when `OTLPBackend` is selected.
   314	
   315	        Called from ``start_suite`` AFTER ``_resolve_backend`` so the
   316	        backend selection is known. Process-scope idempotency: the active
   317	        TracerProvider carries an ``_agenteval_otlp_attached`` sentinel
   318	        once the OTLP processor is attached, so subsequent Listener
   319	        instances in the same process (pabot worker reuse + test harness
   320	        re-instantiation) do NOT stack duplicate OTLP processors. Mirrors
   321	        the ``_agenteval_listener_attached`` sentinel pattern from Story
   322	        5.1 HIGH-A fix.
   323	
   324	        Dual-export design (Story 13.2 D-7): the in-memory chain
   325	        (``SimpleSpanProcessor(InMemorySpanExporter)``) remains attached
   326	        unconditionally for projection-accessor compatibility; the OTLP
   327	        processor is an ADDITIONAL exporter, NOT a replacement.
   328	        """
   329	        if not isinstance(self._backend, OTLPBackend):
   330	            return
   331	        provider = trace.get_tracer_provider()
   332	        if not isinstance(provider, TracerProvider):
   333	            # Real OTel TracerProvider not active (proxy stub during tests
   334	            # without Listener wiring). Nothing to attach to.
   335	            return
   336	        if getattr(provider, "_agenteval_otlp_attached", False):
   337	            return
   338	        provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))  # noqa: SLF001
   339	        provider._agenteval_otlp_attached = True  # type: ignore[attr-defined]
   340	
   341	    # --------------------------------------------------------------- #
   342	    # Robot Framework Listener v3 hooks
   343	    # --------------------------------------------------------------- #
   344	
   345	    def start_suite(self, data: Any, result: Any) -> None:  # noqa: ARG002
   346	        """RF Listener v3 ``start_suite`` hook — configure tracer on first invocation.
   347	
   348	        Args:
   349	            data: RF ``TestSuite`` object (Listener v3 API).
   350	            result: RF ``TestSuiteResult`` object (Listener v3 API).
   351	        """
   352	        self._configure_tracer_provider()
   353	        # Resolve trace_backend + output_dir from RF context.
   354	        self._resolve_backend(suite=data)
   355	        # Story 13.2 (Epic 13) — attach the OTLP BatchSpanProcessor AFTER
   356	        # backend selection. No-op for memory + jsonl backends; OTLP
   357	        # branch lights up the FR33b OTLP export path with the dual-export
   358	        # design (existing in-memory exporter remains attached).
   359	        self._attach_otlp_exporter_if_needed()
   360	
   361	    def start_test(self, data: Any, result: Any) -> None:  # noqa: ARG002
   362	        """RF Listener v3 ``start_test`` hook — set per-test scope.
   363	
   364	        Extracts ``data.full_name`` (canonical Listener v3 path; replaces
   365	        the v2 ``attrs["longname"]`` shape) and binds it to
   366	        ``_kernel/context.set_current_test_id`` so MCP servers + adapters +
   367	        spans share the test scope. Honors PRD FR40's ``mcp_per_test``
   368	        config — resolved at ``start_suite`` and threaded through here so
   369	        ADR-009's per-test vs. per-suite scope decision flows from config
   370	        to kernel context.
   371	
   372	        Story 5.1 code-review Auditor H3 fix 2026-05-20: pre-edit dropped
   373	        the ``scope=`` argument so every test bound `Scope = "test"`
   374	        regardless of FR40 / `mcp_per_test` config. Now resolved via
   375	        `_kernel/context._resolve_scope(mcp_per_test)`.
   376	        """
   377	        # Story 5.1 code-review Blind MED-1 fix 2026-05-20: defensive
   378	        # unbind before any early-return path — if a prior test's end_test
   379	        # also degraded (missing full_name), the prior context can stay
   380	        # bound across the boundary and pollute the next test's spans.
   381	        _kernel_context.unbind_context()
   382	        # Story 5.3: reset per-test operational metadata accumulator so a
   383	        # prior test's adapter calls don't leak into the next test's
   384	        # RunManifest sidecar.
   385	        self._current_run_metadata = {}
   386	        test_id = self._extract_longname(data)
   387	        suite_id = self._extract_suite_id(data)
   388	        if not test_id:
   389	            _msg = (
   390	                "AgentEval Listener: missing test full_name on start_test; "
   391	                "spans will carry an empty agenteval.test_id span attribute"
   392	            )
   393	            # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
   394	            # filter doesn't drop the structured channel.
   395	            _agenteval_warnings.record_warning(
   396	                warning_type="AgentEval.errors.DegradedTraceWarning",
   397	                message=_msg,
   398	                source="telemetry.listener",
   399	                remediation=(
   400	                    "Verify RF emits a non-empty `full_name` on TestCase; "
   401	                    "check listener data-object shape if running outside RF runtime"
   402	                ),
   403	            )
   404	            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
   405	            return
   406	        scope = _kernel_context._resolve_scope(  # noqa: SLF001
   407	            cast("bool | Literal['suite']", self._mcp_per_test)
   408	        )
   409	        _kernel_context.set_current_test_id(test_id, suite_id=suite_id, scope=scope)
   410	        # Story 8a.2 AC-8a.2.1 (FR51): surface `trace_id` as a `<tag>` on the
   411	        # test in `output.xml` so CI log spelunking + observability dashboards
   412	        # can link RF reports to JSONL trace artifacts. The tag value is the
   413	        # canonical RF `full_name` (mirrors `RunManifest.test_id` + JSONL
   414	        # `trace__<suite>__<test>.jsonl` naming). Failure-mode contract:
   415	        # missing/None `result.tags` or `add()` raise must not mask the test —
   416	        # log WARN + continue.
   417	        #
   418	        # IMPORTANT (Story 8a.2 dev empirical finding 2026-05-25): tags must be
   419	        # added to `result.tags`, NOT `data.tags`. Empirical RF Listener v3
   420	        # behavior: `data.tags.add(...)` does NOT surface in `output.xml`;

exec
/bin/bash -lc "nl -ba src/AgentEval/telemetry/backends.py | sed -n '220,420p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   220	                    "to bypass JSONL persistence if the failure is transient"
   221	                ),
   222	            )
   223	            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
   224	            return None
   225	        return target_path
   226	
   227	
   228	def _span_to_jsonl_line(span: ReadableSpan) -> str:
   229	    """Serialize one ``ReadableSpan`` to a JSON line.
   230	
   231	    Schema (Phase-1; aligned to OTel JSON envelope shape but not strictly
   232	    OTel-LP-compliant; Phase-2 OTLP backend will use the canonical envelope):
   233	
   234	        {
   235	          "name": "<span name>",
   236	          "trace_id": "<32-hex trace id>",
   237	          "span_id": "<16-hex span id>",
   238	          "parent_span_id": "<16-hex span id> | null",
   239	          "start_time_unix_ns": <int>,
   240	          "end_time_unix_ns": <int>,
   241	          "attributes": {<key>: <value>, ...},
   242	          "resource_attributes": {<key>: <value>, ...},
   243	          "status": {"status_code": "OK"|"ERROR"|"UNSET", "description": <str>|null}
   244	        }
   245	
   246	    On any serialization failure for a specific attribute value, fall back
   247	    to ``str(value)`` so the overall write proceeds.
   248	    """
   249	    ctx = span.get_span_context()
   250	    parent_ctx = span.parent
   251	    record = {
   252	        "name": span.name,
   253	        "trace_id": f"{ctx.trace_id:032x}" if ctx is not None else None,
   254	        "span_id": f"{ctx.span_id:016x}" if ctx is not None else None,
   255	        "parent_span_id": f"{parent_ctx.span_id:016x}" if parent_ctx is not None else None,
   256	        "start_time_unix_ns": span.start_time,
   257	        "end_time_unix_ns": span.end_time,
   258	        "attributes": _safe_dict(dict(span.attributes) if span.attributes else {}),
   259	        "resource_attributes": _safe_dict(
   260	            dict(span.resource.attributes) if span.resource and span.resource.attributes else {}
   261	        ),
   262	        "status": {
   263	            "status_code": span.status.status_code.name if span.status else "UNSET",
   264	            "description": span.status.description if span.status else None,
   265	        },
   266	    }
   267	    return json.dumps(record, ensure_ascii=False)
   268	
   269	
   270	def _safe_dict(d: dict[str, object]) -> dict[str, object]:
   271	    """Coerce any non-JSON-encodable values to ``str(value)`` defensively.
   272	
   273	    OTel attribute values are restricted to JSON-encodable primitives + lists
   274	    of primitives by the SDK, but a buggy producer could still emit a value
   275	    that ``json.dumps`` rejects. Backend write failures must not mask test
   276	    outcomes, so we fall back to ``str``.
   277	
   278	    Story 5.1 code-review Edge-cases H2 fix 2026-05-20: widen the catch from
   279	    just ``TypeError`` to ``(TypeError, ValueError, RecursionError)`` so
   280	    circular-reference + deep-nesting attributes don't propagate. ``repr()``
   281	    is the last-resort fallback when even ``str()`` fails.
   282	    """
   283	    safe: dict[str, object] = {}
   284	    for k, v in d.items():
   285	        try:
   286	            json.dumps(v)
   287	            safe[k] = v
   288	        except (TypeError, ValueError, RecursionError):
   289	            try:
   290	                safe[k] = str(v)
   291	            except Exception:  # noqa: BLE001 — last-resort serialization
   292	                safe[k] = repr(v)
   293	    return safe
   294	
   295	
   296	# Default OTLP HTTP endpoint per OpenTelemetry SDK convention (local Jaeger
   297	# all-in-one + standalone collector listen on this port for HTTP/protobuf).
   298	_OTLP_DEFAULT_ENDPOINT_HTTP = "http://localhost:4318/v1/traces"
   299	
   300	
   301	class OTLPBackend:
   302	    """OTLP trace backend (opt-in via ``trace_backend="otlp"``; Phase-2 FR33b).
   303	
   304	    Exports spans via the canonical
   305	    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based
   306	    on the URL scheme of ``endpoint``. Requires the ``[otlp]`` optional
   307	    extra (``opentelemetry-exporter-otlp``); raises ``ImportError`` on
   308	    construction when the extra is missing.
   309	
   310	    Export semantics: spans are routed via a ``BatchSpanProcessor`` attached
   311	    to the TracerProvider at TracerProvider-config time (NOT via
   312	    ``flush_test``). ``flush_test`` is a no-op here — included for API
   313	    uniformity with ``MemoryBackend`` / ``JSONLBackend`` (side-effecting,
   314	    not idempotent; documented per Story 13.2 D-2).
   315	
   316	    URL scheme dispatch (per Story 13.2 D-4 + AC-13.2.2):
   317	        - ``http://...`` / ``https://...`` → OTLP HTTP/protobuf exporter
   318	          (default port 4318, ``/v1/traces`` path).
   319	        - ``grpc://...`` / ``grpcs://...`` → OTLP gRPC exporter (default
   320	          port 4317). Scheme is stripped to bare ``host:port`` per gRPC SDK
   321	          convention; ``grpc://`` → ``insecure=True``; ``grpcs://`` → TLS.
   322	        - Default (``endpoint=None``) → ``http://localhost:4318/v1/traces``
   323	          per OpenTelemetry SDK convention (local Jaeger HTTP).
   324	        - Any other scheme → ``ValueError``.
   325	
   326	    Dual-export design rationale (Story 13.2 D-7): when ``OTLPBackend`` is
   327	    active the Listener attaches BOTH the existing in-memory exporter
   328	    (``SimpleSpanProcessor(InMemorySpanExporter)``) AND the OTLP exporter
   329	    (``BatchSpanProcessor(OTLPSpanExporter)``) to the TracerProvider, so
   330	    the existing ``Metric.*`` keyword surface stays functional while
   331	    spans also flow out to the observability backend.
   332	
   333	    Thread safety: the underlying ``OTLPSpanExporter`` is process-resident
   334	    + thread-safe per OpenTelemetry SDK guarantees. ``OTLPBackend`` itself
   335	    is read-only after construction; safe for the Listener's process-scope
   336	    sentinel sharing pattern (Story 5.1 HIGH-A precedent).
   337	    """
   338	
   339	    name = "otlp"
   340	
   341	    def __init__(self, endpoint: str | None = None) -> None:
   342	        if not _OTLP_AVAILABLE:
   343	            _raise_otlp_extra_missing()
   344	        # Reject explicit empty-string endpoint up-front (ambiguous: would
   345	        # the OTel SDK fall back to its env-var default? Prefer a loud
   346	        # ValueError so the operator notices the empty config).
   347	        if endpoint == "":
   348	            raise ValueError(
   349	                "otlp_endpoint must not be empty string; "
   350	                f"omit the value to use the default ({_OTLP_DEFAULT_ENDPOINT_HTTP}) "
   351	                "OR pass a fully-qualified URL"
   352	            )
   353	        resolved_endpoint = endpoint if endpoint is not None else _OTLP_DEFAULT_ENDPOINT_HTTP
   354	        # Parse the URL scheme. Use a simple prefix check rather than urllib
   355	        # so `grpc://` (not a registered scheme in urllib) parses cleanly.
   356	        lower = resolved_endpoint.lower()
   357	        # Annotate the exporter as the common SpanExporter ABC so mypy
   358	        # accepts both HTTP and gRPC exporter assignments (sibling concrete
   359	        # classes; mypy can't infer the common base from the first branch).
   360	        from opentelemetry.sdk.trace.export import SpanExporter as _SpanExporter
   361	
   362	        exporter: _SpanExporter
   363	        if lower.startswith(("http://", "https://")):
   364	            exporter = _OTLPSpanExporterHTTP(endpoint=resolved_endpoint)
   365	            self._transport: str = "http"
   366	        elif lower.startswith("grpcs://"):
   367	            # gRPC SDK expects bare host:port + insecure=False for TLS.
   368	            host_port = resolved_endpoint[len("grpcs://") :]
   369	            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=False)
   370	            self._transport = "grpc"
   371	        elif lower.startswith("grpc://"):
   372	            # gRPC SDK expects bare host:port + insecure=True for plaintext.
   373	            host_port = resolved_endpoint[len("grpc://") :]
   374	            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=True)
   375	            self._transport = "grpc"
   376	        else:
   377	            # Extract the scheme up to `://` for the error message; if no
   378	            # `://` present, show the prefix up to the first non-scheme char.
   379	            scheme_end = resolved_endpoint.find("://")
   380	            scheme_repr = resolved_endpoint[:scheme_end] if scheme_end >= 0 else resolved_endpoint
   381	            raise ValueError(
   382	                f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme_repr!r}"
   383	            )
   384	        self._exporter = exporter
   385	        self._endpoint = resolved_endpoint
   386	
   387	    def flush_test(
   388	        self,
   389	        test_id: str,
   390	        suite_id: str = "",
   391	        output_dir: Path | None = None,
   392	    ) -> None:
   393	        """No-op. OTLP export is batched via the SpanProcessor chain.
   394	
   395	        The actual export happens via ``BatchSpanProcessor`` attached to the
   396	        TracerProvider at TracerProvider-config time (per Story 13.2 D-7
   397	        dual-export design). ``flush_test`` is preserved for API uniformity
   398	        with ``MemoryBackend`` / ``JSONLBackend`` but does no work.
   399	
   400	        Args:
   401	            test_id: RF Listener v3 test identifier (unused for OTLP).
   402	            suite_id: RF Listener v3 suite identifier (unused for OTLP).
   403	            output_dir: Unused for OTLP; accepted for API uniformity.
   404	        """
   405	        _ = test_id
   406	        _ = suite_id
   407	        _ = output_dir

exec
/bin/bash -lc "sed -n '1,220p' tests/unit/telemetry/test_backends_otlp_extras_gate.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
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

exec
/bin/bash -lc 'rg -n "@keyword|OTLPSpanExporter|otlp_endpoint|_agenteval_otlp_attached|BatchSpanProcessor|SimpleSpanProcessor" src/AgentEval/telemetry tests/integration/telemetry tests/unit/telemetry docs/recipes/08-ci-integration.md' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: rg: command not found

exec
/bin/bash -lc "sed -n '1,220p' tests/integration/telemetry/test_otlp_export_e2e.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
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
    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
    assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
    # Verify agenteval-specific attribute flows through OTLP envelope.
    flat_attrs: list[dict] = []
    for s in spans:
        flat_attrs.extend(s.get("attributes", []))
    # OTLP attribute shape: {"key": "agenteval.tier", "value": {"intValue": "2"}}.
    assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)


def test_otlp_grpc_export_round_trip_against_collector(tmp_path: Path) -> None:
    """Span emitted via OTLP gRPC lands in the collector's file output.

    Verifies the gRPC scheme dispatch + insecure=True host:port stripping
    end-to-end. Same wire-format readback assertion as the HTTP variant.
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
    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
    assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)

exec
/bin/bash -lc "nl -ba src/AgentEval/telemetry/listener.py | sed -n '820,910p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   820	        """Resolve ``trace_backend`` + output_dir from config + RF context.
   821	
   822	        Story 4.3 4-level ConfigValue precedence (init_arg → env → dotenv →
   823	        default). For the Listener (no init_arg surface yet — Listener is
   824	        constructed by RF without kwargs), the chain reduces to env → dotenv
   825	        → default.
   826	
   827	        Output dir: prefers ``trace_path`` config; falls back to RF's
   828	        ``${OUTPUTDIR}`` from suite metadata or ``Path.cwd()``.
   829	        """
   830	        config = _kernel_context.resolve_config({})
   831	        backend_name = config.get("trace_backend", "memory")
   832	        if backend_name == "jsonl":
   833	            self._backend = JSONLBackend()
   834	        elif backend_name == "memory":
   835	            self._backend = MemoryBackend()
   836	        elif backend_name == "otlp":
   837	            # Story 13.2 (Epic 13) — OTLP backend dispatch per FR33b. When
   838	            # construction fails (typically: `[otlp]` extra missing), warn
   839	            # loud + gracefully degrade to memory rather than aborting the
   840	            # entire test run. Operators using `trace_backend=otlp` should
   841	            # see a DegradedTraceWarning that points them to the extra.
   842	            otlp_endpoint = config.get("otlp_endpoint")
   843	            try:
   844	                self._backend = OTLPBackend(endpoint=otlp_endpoint)
   845	            except ImportError as exc:
   846	                _msg = (
   847	                    f"AgentEval Listener: OTLP backend construction failed: {exc}; "
   848	                    "falling back to 'memory'. Install via: "
   849	                    "`uv pip install robotframework-agenteval[otlp]`."
   850	                )
   851	                _agenteval_warnings.record_warning(
   852	                    warning_type="AgentEval.errors.DegradedTraceWarning",
   853	                    message=_msg,
   854	                    source="telemetry.listener",
   855	                    remediation=(
   856	                        "Install the [otlp] optional extra via "
   857	                        "`uv pip install robotframework-agenteval[otlp]` OR "
   858	                        "set AGENTEVAL_TRACE_BACKEND=memory to bypass OTLP"
   859	                    ),
   860	                )
   861	                warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
   862	                self._backend = MemoryBackend()
   863	            except ValueError as exc:
   864	                # Bad URL scheme / empty endpoint — operator error. Same
   865	                # graceful-degrade posture as the import failure above.
   866	                _msg = f"AgentEval Listener: OTLP backend rejected endpoint: {exc}; falling back to 'memory'."
   867	                _agenteval_warnings.record_warning(
   868	                    warning_type="AgentEval.errors.DegradedTraceWarning",
   869	                    message=_msg,
   870	                    source="telemetry.listener",
   871	                    remediation=(
   872	                        "Set AGENTEVAL_OTLP_ENDPOINT to a URL with scheme http://, https://, grpc://, or grpcs://"
   873	                    ),
   874	                )
   875	                warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
   876	                self._backend = MemoryBackend()
   877	        else:
   878	            # Story 5.1 code-review Edge-cases M2 fix 2026-05-20: unknown
   879	            # trace_backend silently fell back to memory pre-edit — operators
   880	            # typoing `jsnol` or `jsonl1` would lose JSONL artifacts without
   881	            # any signal. Warn loud + fall back to memory for safety.
   882	            # Story 13.2 (Epic 13): added 'otlp' to the valid-values list.
   883	            _msg = (
   884	                f"AgentEval Listener: unknown trace_backend={backend_name!r}; "
   885	                "falling back to 'memory'. Valid values: {'memory', 'jsonl', 'otlp'}."
   886	            )
   887	            # Story 5.4 code-review HIGH-C: record THEN warn so `-W error`
   888	            # filter doesn't drop the structured channel.
   889	            _agenteval_warnings.record_warning(
   890	                warning_type="AgentEval.errors.DegradedTraceWarning",
   891	                message=_msg,
   892	                source="telemetry.listener",
   893	                remediation=(
   894	                    "Set AGENTEVAL_TRACE_BACKEND to one of "
   895	                    "{'memory', 'jsonl', 'otlp'}; the misspelled value "
   896	                    "silently falls back to memory backend"
   897	                ),
   898	            )
   899	            warnings.warn(_msg, DegradedTraceWarning, stacklevel=2)
   900	            self._backend = MemoryBackend()
   901	        # Story 5.1 code-review Auditor H3 fix 2026-05-20: read mcp_per_test
   902	        # config so start_test can wire FR40 scope through set_current_test_id.
   903	        mcp_per_test_raw = config.get("mcp_per_test", True)
   904	        # Coerce to the kernel context's expected union (bool | Literal["suite"]).
   905	        if isinstance(mcp_per_test_raw, str) and mcp_per_test_raw.lower() == "suite":
   906	            self._mcp_per_test = "suite"
   907	        else:
   908	            self._mcp_per_test = bool(mcp_per_test_raw)
   909	        trace_path = config.get("trace_path")
   910	        if trace_path:

codex
The first pass already surfaced one risky area: OTLP attachment is process-global, but the exporter instance is endpoint-specific. I’m now validating that behavior empirically alongside the docs smoke checks and the OTel exporter constructor contracts.
exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/prd.md | sed -n '1628,1638p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  1628	### Security
  1629	
  1630	- **NFR-SEC-01:** Library never persists user-provided credentials (API keys, OAuth tokens) to disk or trace artifacts in their original form. All credentials routed through `config.redact_env()` (and user-extensible patterns via `config.add_redaction_pattern()`) before any serialization. CI test asserts no known API-key strings or custom patterns appear in any committed fixture; conformance suite verifies unknown-shape redaction (FR38a).
  1631	- **NFR-SEC-02:** Library never executes `eval()` on user-provided strings except via the explicitly-opted-in AssertionEngine `validate` operator (`__init__(allow_validate_operator=True)`, default `False`, FR43). All other AssertionEngine matchers use safe comparison operators. CI test asserts no `eval()` calls exist on user input paths in default-configured library.
  1632	- **NFR-SEC-03:** All LLM provider traffic uses TLS in transit (delegated to LiteLLM / provider SDKs); library does NOT relax certificate validation or expose any HTTP-without-TLS opt-out. MCP transports use TLS for Streamable HTTP; `stdio` and in-memory transports are local-process-only by design.
  1633	- **NFR-SEC-04:** Vendor CLI binaries (`claude`, `codex`, `copilot`, `goose`, `pi`, `opencode`) are never auto-downloaded, installed, or auto-updated by the library; user explicitly installs binaries (FR47). Supply-chain trust boundary documented in `SECURITY.md`: library trusts the binary on `$PATH` to the same level the user does.
  1634	- **NFR-SEC-05:** Library does NOT phone home. Only LLM provider endpoints (per user-configured providers) and OTLP endpoints (Phase 2, opt-in via `[otlp]` extra + explicit endpoint config) generate network egress. `__init__(telemetry=False)` eliminates all OTel listener egress. Conformance suite verifies via `Assert No Egress To` fixture in default-configured + `telemetry=False` configurations.
  1635	
  1636	### Integration & Compatibility
  1637	
  1638	- **NFR-COMPAT-01:** Python compatibility: 3.12 and 3.13 are Tier-1 (gated CI matrix on Linux + macOS); future 3.14+ tested in CI but not gated until upstream stable release. Python <3.12 explicitly unsupported; `pyproject.toml` `requires-python = ">=3.12"` enforces at install time.

exec
/bin/bash -lc "python - <<'PY'
import inspect
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as G
    print('grpc signature:', inspect.signature(G.__init__))
except Exception as e:
    print('grpc import failed:', type(e).__name__, e)
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as H
    print('http signature:', inspect.signature(H.__init__))
except Exception as e:
    print('http import failed:', type(e).__name__, e)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "nl -ba src/AgentEval/_kernel/context.py | sed -n '820,905p'" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
import inspect
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as G
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as H
print('grpc signature:', inspect.signature(G.__init__))
print('http signature:', inspect.signature(H.__init__))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   820	    "mcp_per_test": True,
   821	    "allow_external_mcp_blind": False,
   822	    "max_cost_usd": 5.00,
   823	    "max_runtime_seconds": None,
   824	    # Story 13.2 (Epic 13) — OTLP trace exporter endpoint (FR33b). Default
   825	    # None; OTLPBackend falls back to `http://localhost:4318/v1/traces`
   826	    # (OpenTelemetry SDK convention for local Jaeger HTTP).
   827	    "otlp_endpoint": None,
   828	}
   829	
   830	# Mapping from FR42 + FR11b kwarg names to `AGENTEVAL_*` env-var names per
   831	# architecture.md §Configuration Parameter Naming + `.env.example`.
   832	_ENV_VAR_NAMES: dict[str, str] = {
   833	    "provider": "AGENTEVAL_PROVIDER",
   834	    "telemetry": "AGENTEVAL_TELEMETRY",
   835	    "trace_backend": "AGENTEVAL_TRACE_BACKEND",
   836	    "trace_path": "AGENTEVAL_TRACE_PATH",
   837	    "allow_validate_operator": "AGENTEVAL_ALLOW_VALIDATE_OPERATOR",
   838	    "default_temperature": "AGENTEVAL_DEFAULT_TEMPERATURE",
   839	    "mcp_per_test": "AGENTEVAL_MCP_PER_TEST",
   840	    "allow_external_mcp_blind": "AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND",
   841	    "max_cost_usd": "AGENTEVAL_MAX_COST_USD",
   842	    "max_runtime_seconds": "AGENTEVAL_MAX_RUNTIME_SECONDS",
   843	    "otlp_endpoint": "AGENTEVAL_OTLP_ENDPOINT",
   844	}
   845	
   846	# Reverse map for M8 unknown-env-var warning.
   847	_KNOWN_ENV_VAR_NAMES: frozenset[str] = frozenset(_ENV_VAR_NAMES.values())
   848	
   849	
   850	def _parse_bool(raw: str, *, key: str) -> bool:
   851	    """Parse a string to bool. Accepts true/false/1/0/yes/no/on/off (case-insensitive).
   852	
   853	    Documented in `.env.example` per L4 review finding.
   854	    """
   855	    lowered = raw.strip().lower()
   856	    if lowered in ("true", "1", "yes", "on"):
   857	        return True
   858	    if lowered in ("false", "0", "no", "off"):
   859	        return False
   860	    # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
   861	    raise ValueError(f"{key}: expected bool-like value (true/false/1/0/yes/no/on/off); got {raw!r}")
   862	
   863	
   864	def _parse_mcp_per_test(raw: str, *, key: str) -> bool | Literal["suite"]:
   865	    lowered = raw.strip().lower()
   866	    if lowered == "suite":
   867	        return "suite"
   868	    return _parse_bool(raw, key=key)
   869	
   870	
   871	def _parse_optional_float(raw: str, *, key: str) -> float | None:
   872	    stripped = raw.strip()
   873	    if stripped == "":
   874	        return None
   875	    try:
   876	        return float(stripped)
   877	    except ValueError as exc:
   878	        # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
   879	        raise ValueError(f"{key}: expected float or empty string; got {raw!r}") from exc
   880	
   881	
   882	def _coerce_env_value(key: str, raw: str) -> Any:
   883	    """Coerce an env-var string to the target type for the given config key."""
   884	    if key in ("telemetry", "allow_validate_operator", "allow_external_mcp_blind"):
   885	        return _parse_bool(raw, key=key)
   886	    if key == "mcp_per_test":
   887	        return _parse_mcp_per_test(raw, key=key)
   888	    if key == "default_temperature":
   889	        try:
   890	            return float(raw)
   891	        except ValueError as exc:
   892	            # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
   893	            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
   894	    if key == "max_cost_usd":
   895	        try:
   896	            return float(raw)
   897	        except ValueError as exc:
   898	            # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
   899	            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
   900	    if key == "max_runtime_seconds":
   901	        return _parse_optional_float(raw, key=key)
   902	    # provider, trace_backend, trace_path, otlp_endpoint — strings; pass through.
   903	    return raw
   904	
   905	

exec
/bin/bash -lc "nl -ba src/AgentEval/__init__.py | sed -n '220,290p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   220	
   221	    References:
   222	        - PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)
   223	        - PRD FR11b (max_runtime_seconds keyword arg sibling)
   224	        - PRD FR41 (config precedence)
   225	        - ADR-009 (mcp_per_test 3-mode)
   226	        - ADR-013 (entry-points discovery for `provider`)
   227	        - ADR-015 (@guarded_fanout for cost + runtime guardrails)
   228	        - ADR-016 (mcp_coverage detection + allow_external_mcp_blind)
   229	        - docs/contracts/stability-surface.md (Phase-1 stability labels for this
   230	          class)
   231	    """
   232	
   233	    def __init__(
   234	        self,
   235	        *,
   236	        provider: str = _UNSET,
   237	        telemetry: bool = _UNSET,
   238	        trace_backend: str = _UNSET,
   239	        allow_validate_operator: bool = _UNSET,
   240	        default_temperature: float = _UNSET,
   241	        mcp_per_test: bool | Literal["suite"] = _UNSET,
   242	        allow_external_mcp_blind: bool = _UNSET,
   243	        max_cost_usd: float = _UNSET,
   244	        max_runtime_seconds: float | None = _UNSET,
   245	        otlp_endpoint: str | None = _UNSET,
   246	    ) -> None:
   247	        # Story 1b.1 FR41 wiring: strip _UNSET sentinels, pass the remainder
   248	        # to resolve_config() so the env-var / .env / defaults layers can fire
   249	        # for kwargs the caller did NOT pass. Explicit None IS a user-passed
   250	        # value (e.g., max_runtime_seconds=None) and takes precedence over
   251	        # env-vars.
   252	        kwarg_overrides: dict[str, Any] = {
   253	            "provider": provider,
   254	            "telemetry": telemetry,
   255	            "trace_backend": trace_backend,
   256	            "allow_validate_operator": allow_validate_operator,
   257	            "default_temperature": default_temperature,
   258	            "mcp_per_test": mcp_per_test,
   259	            "allow_external_mcp_blind": allow_external_mcp_blind,
   260	            "max_cost_usd": max_cost_usd,
   261	            "max_runtime_seconds": max_runtime_seconds,
   262	            "otlp_endpoint": otlp_endpoint,
   263	        }
   264	        kwarg_overrides = {k: v for k, v in kwarg_overrides.items() if v is not _UNSET}
   265	        resolved = resolve_config(kwarg_overrides)
   266	        # Story 4.3 (PRD FR41 ConfigValue surface): also compute the
   267	        # provenance map for `Get Effective Config setting=key` +
   268	        # `Get Effective Config With Provenance` keywords.
   269	        self._config_provenance: dict[str, ConfigValue] = resolve_config_with_provenance(kwarg_overrides)
   270	
   271	        self._provider = resolved["provider"]
   272	        self._telemetry = resolved["telemetry"]
   273	        self._trace_backend = resolved["trace_backend"]
   274	        self._allow_validate_operator = resolved["allow_validate_operator"]
   275	        self._default_temperature = resolved["default_temperature"]
   276	        self._mcp_per_test = resolved["mcp_per_test"]
   277	        self._allow_external_mcp_blind = resolved["allow_external_mcp_blind"]
   278	        self._max_cost_usd = resolved["max_cost_usd"]
   279	        self._max_runtime_seconds = resolved["max_runtime_seconds"]
   280	        self._otlp_endpoint = resolved["otlp_endpoint"]
   281	
   282	        # Internal scope for MCP server lifecycle (Story 1b.1 _resolve_scope
   283	        # translates the user-vocab `mcp_per_test` into the internal Scope enum).
   284	        self._scope = _resolve_scope(self._mcp_per_test)
   285	
   286	        # AC-1a.6.8: lazy RF Listener v3 context hook. Phase-1 stub returns None;
   287	        # Epic 5 Story 5.1 wires the real `test_id` read for per-test MCP scoping.
   288	        self._rf_test_id = self._get_rf_test_id()
   289	
   290	        # Story 2.1: DynamicCore composition per architecture L299/L354/L573 +

exec
/bin/bash -lc "grep -RIn \"service.name\\|OTLPSpanExporter\\|@keyword\" src/AgentEval/telemetry docs/contracts/otel-trace-visual.md tests/integration/telemetry tests/unit/telemetry | head -200" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/telemetry/backends.py:60:        OTLPSpanExporter as _OTLPSpanExporterGRPC,
src/AgentEval/telemetry/backends.py:63:        OTLPSpanExporter as _OTLPSpanExporterHTTP,
src/AgentEval/telemetry/backends.py:69:    _OTLPSpanExporterHTTP = None  # type: ignore[misc, assignment]
src/AgentEval/telemetry/backends.py:70:    _OTLPSpanExporterGRPC = None  # type: ignore[misc, assignment]
src/AgentEval/telemetry/backends.py:305:    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based
src/AgentEval/telemetry/backends.py:329:    (``BatchSpanProcessor(OTLPSpanExporter)``) to the TracerProvider, so
src/AgentEval/telemetry/backends.py:333:    Thread safety: the underlying ``OTLPSpanExporter`` is process-resident
src/AgentEval/telemetry/backends.py:364:            exporter = _OTLPSpanExporterHTTP(endpoint=resolved_endpoint)
src/AgentEval/telemetry/backends.py:369:            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=False)
src/AgentEval/telemetry/backends.py:374:            exporter = _OTLPSpanExporterGRPC(endpoint=host_port, insecure=True)
src/AgentEval/telemetry/library.py:62:    @keyword(name="Get Last Warnings")
src/AgentEval/telemetry/library.py:96:    @keyword(name="Get Spans")
src/AgentEval/telemetry/library.py:137:    @keyword(name="Get Tool Calls")
src/AgentEval/telemetry/library.py:176:    @keyword(name="Get Run Manifest")
src/AgentEval/telemetry/listener.py:313:        """Attach a `BatchSpanProcessor(OTLPSpanExporter)` to the active provider when `OTLPBackend` is selected.
docs/contracts/otel-trace-visual.md:105:agenteval `OTelResource.service.name`). Use Honeycomb's BubbleUp on
tests/integration/telemetry/test_otlp_export_e2e.py:63:    BatchSpanProcessor(OTLPSpanExporter) is wired identically to a
tests/unit/telemetry/test_backends_otlp.py:43:    OTLPSpanExporter as _GrpcExp,
tests/unit/telemetry/test_backends_otlp.py:46:    OTLPSpanExporter as _HttpExp,

exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
from AgentEval.telemetry.backends import OTLPBackend

for endpoint in [
    'https://api.honeycomb.io/v1/traces',
    'grpc://localhost:4317',
    'grpcs://otel.example.com:4317',
]:
    b = OTLPBackend(endpoint=endpoint)
    print('input=', endpoint)
    print('stored endpoint=', b._endpoint)
    print('transport=', b._transport)
    exp = b._exporter
    for attr in ['_endpoint', '_insecure', '_session', '_client_cert', '_headers']:
        if hasattr(exp, attr):
            print(attr, getattr(exp, attr))
    print(type(exp))
    print('---')
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 517ms:
grpc signature: (self, endpoint: Optional[str] = None, insecure: Optional[bool] = None, credentials: Optional[grpc.ChannelCredentials] = None, headers: Union[Sequence[Tuple[str, str]], Dict[str, str], str, NoneType] = None, timeout: Optional[float] = None, compression: Optional[grpc.Compression] = None, channel_options: Optional[Tuple[Tuple[str, str]]] = None)
http signature: (self, endpoint: Optional[str] = None, certificate_file: Optional[str] = None, client_key_file: Optional[str] = None, client_certificate_file: Optional[str] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, compression: Optional[opentelemetry.exporter.otlp.proto.http.Compression] = None, session: Optional[requests.sessions.Session] = None)

 succeeded in 555ms:
grpc signature: (self, endpoint: Optional[str] = None, insecure: Optional[bool] = None, credentials: Optional[grpc.ChannelCredentials] = None, headers: Union[Sequence[Tuple[str, str]], Dict[str, str], str, NoneType] = None, timeout: Optional[float] = None, compression: Optional[grpc.Compression] = None, channel_options: Optional[Tuple[Tuple[str, str]]] = None)
http signature: (self, endpoint: Optional[str] = None, certificate_file: Optional[str] = None, client_key_file: Optional[str] = None, client_certificate_file: Optional[str] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, compression: Optional[opentelemetry.exporter.otlp.proto.http.Compression] = None, session: Optional[requests.sessions.Session] = None)

 succeeded in 809ms:
input= https://api.honeycomb.io/v1/traces
stored endpoint= https://api.honeycomb.io/v1/traces
transport= http
_endpoint https://api.honeycomb.io/v1/traces
_session <requests.sessions.Session object at 0x7a647ae61bb0>
_client_cert None
_headers {}
<class 'opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter'>
---
input= grpc://localhost:4317
stored endpoint= grpc://localhost:4317
transport= grpc
_endpoint localhost:4317
_insecure True
_headers ()
<class 'opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter'>
---
input= grpcs://otel.example.com:4317
stored endpoint= grpcs://otel.example.com:4317
transport= grpc
_endpoint otel.example.com:4317
_insecure False
_headers ()
<class 'opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter'>
---

exec
/bin/bash -lc "nl -ba docs/contracts/otel-trace-visual.md | sed -n '70,112p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
    70	# Spin up Jaeger.
    71	docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest
    72	
    73	# Replay the JSONL trace.
    74	cat ${OUTPUTDIR}/agenteval/trace__MyTests__Test_Echo.jsonl | \
    75	  otel-cli span replay - --endpoint http://localhost:4318/v1/traces
    76	
    77	# Open the Jaeger UI.
    78	open http://localhost:16686/search?service=robotframework-agenteval
    79	```
    80	
    81	The `invoke_agent → chat → execute_tool` hierarchy renders as the
    82	trace-detail-view's flame graph. Each `execute_tool` span's `agenteval.tool.*`
    83	attributes appear in the right-hand attribute panel.
    84	
    85	**Phase-1 limitation:** `otel-cli span replay` is a community tool, not
    86	distributed with agenteval. Future Phase-1.5 work may ship an
    87	`agenteval trace replay` CLI subcommand wrapping the conversion + replay
    88	step (DF-8b.3-S1 / C64 carry-over candidate).
    89	
    90	## Loading into Honeycomb
    91	
    92	Honeycomb accepts OTLP JSON via `https://api.honeycomb.io/v1/traces`. Pipe
    93	the JSONL through `curl`:
    94	
    95	```bash
    96	cat trace__MyTests__Test_Echo.jsonl | \
    97	  jq -s '{resourceSpans: [{scopeSpans: [{spans: .}]}]}' | \
    98	  curl -X POST https://api.honeycomb.io/v1/traces \
    99	    -H "x-honeycomb-team: $HONEYCOMB_API_KEY" \
   100	    -H "Content-Type: application/json" \
   101	    -d @-
   102	```
   103	
   104	The trace appears in Honeycomb's "robotframework-agenteval" dataset (the
   105	agenteval `OTelResource.service.name`). Use Honeycomb's BubbleUp on
   106	`agenteval.tier` to see Tier-3 fan-out latency distributions.
   107	
   108	## Loading into Tempo
   109	
   110	Tempo (Grafana) accepts OTLP via the Tempo Distributor's gRPC / HTTP
   111	endpoint:
   112	

exec
/bin/bash -lc "grep -RIn \"Resource.create\\|service.name\\|robotframework-agenteval\" src/AgentEval | head -200" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/stats/library.py:81:    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
src/AgentEval/stats/library.py:85:        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
src/AgentEval/__init__.py:20:"""robotframework-agenteval — Robot Framework library for evaluating AI coding agents.
src/AgentEval/coding_agent/base.py:129:    installed distribution name (e.g., `robotframework-agenteval`). The
src/AgentEval/coding_agent/openai_agents.py:57:    "Install with: `pip install robotframework-agenteval[openai-agents]` "
src/AgentEval/coding_agent/claude_agent_sdk.py:53:    "Install with: `pip install robotframework-agenteval[claude-sdk]` "
src/AgentEval/cli.py:187:        "See https://github.com/manykarim/robotframework-agenteval for roadmap.\n"
src/AgentEval/_init/templates/README.md:41:- **Recipes:** [`docs/recipes/01-first-eval-in-five-minutes.md`](https://github.com/manykarim/robotframework-agenteval/blob/main/docs/recipes/01-first-eval-in-five-minutes.md) walks through this scaffolded project. Other recipes in the gallery cover Pass@k, Tool Discoverability, Skill Author validation, CI integration, etc.
src/AgentEval/_init/templates/README.md:47:Full library docs at <https://github.com/manykarim/robotframework-agenteval>.
src/AgentEval/_new_adapter/templates/pyproject.toml.tmpl:7:    "robotframework-agenteval>=0.1.0",
src/AgentEval/telemetry/backends.py:79:    ``uv pip install robotframework-agenteval[otlp]`` so operators can
src/AgentEval/telemetry/backends.py:83:        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
src/AgentEval/telemetry/listener.py:275:        resource = Resource.create({})
src/AgentEval/telemetry/listener.py:849:                    "`uv pip install robotframework-agenteval[otlp]`."
src/AgentEval/telemetry/listener.py:857:                        "`uv pip install robotframework-agenteval[otlp]` OR "

exec
/bin/bash -lc "grep -RIn \"Get Trace Backend Names\\|trace_backend=\\\"otlp\\\"\\|otlp_endpoint\" src tests docs _bmad-output/planning-artifacts | head -250" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/__init__.py:173:            When False, `Get Trace Backend Names` returns `[]` and no OTLP
src/AgentEval/__init__.py:204:        otlp_endpoint: OTLP collector endpoint URL (FR33b; Story 13.2).
src/AgentEval/__init__.py:205:            Only consumed when ``trace_backend="otlp"``. URL scheme selects
src/AgentEval/__init__.py:245:        otlp_endpoint: str | None = _UNSET,
src/AgentEval/__init__.py:262:            "otlp_endpoint": otlp_endpoint,
src/AgentEval/__init__.py:280:        self._otlp_endpoint = resolved["otlp_endpoint"]
src/AgentEval/__init__.py:457:            "otlp_endpoint": self._otlp_endpoint,
src/AgentEval/_kernel/context.py:827:    "otlp_endpoint": None,
src/AgentEval/_kernel/context.py:843:    "otlp_endpoint": "AGENTEVAL_OTLP_ENDPOINT",
src/AgentEval/_kernel/context.py:902:    # provider, trace_backend, trace_path, otlp_endpoint — strings; pass through.
src/AgentEval/telemetry/backends.py:302:    """OTLP trace backend (opt-in via ``trace_backend="otlp"``; Phase-2 FR33b).
src/AgentEval/telemetry/backends.py:349:                "otlp_endpoint must not be empty string; "
src/AgentEval/telemetry/backends.py:382:                f"otlp_endpoint must use http://, https://, grpc://, or grpcs:// scheme; got {scheme_repr!r}"
src/AgentEval/telemetry/listener.py:842:            otlp_endpoint = config.get("otlp_endpoint")
src/AgentEval/telemetry/listener.py:844:                self._backend = OTLPBackend(endpoint=otlp_endpoint)
tests/unit/orchestration/test_config_provenance.py:115:    # + Story 13.2 added `otlp_endpoint`).
tests/unit/orchestration/test_config_provenance.py:127:        "otlp_endpoint",
tests/unit/kernel/test_context.py:472:    """Story 5.1 added `trace_path` (10th key); Story 13.2 added `otlp_endpoint` (11th).
tests/unit/kernel/test_context.py:475:    after Story 13.2's `otlp_endpoint` addition (PRD FR33b OTLP backend +
tests/unit/kernel/test_context.py:490:        "otlp_endpoint",
tests/unit/kernel/test_context.py:525:        "otlp_endpoint": None,
tests/unit/telemetry/test_backends_otlp_extras_gate.py:97:    Per AC-13.2.7 (4th extras-gate test): with `trace_backend="otlp"` +
docs/contracts/stability-surface.md:130:- `AgentEval.__init__(otlp_endpoint=...)` 10th parameter — `provisional` label. Default `None` falls back to `http://localhost:4318/v1/traces`. URL-scheme dispatch is `stable`; the gRPC scheme stripping (`grpc://host:port` → `host:port` + `insecure=True`; `grpcs://host:port` → `host:port` + `insecure=False`) is `provisional` (Phase-2.5 may add an explicit `headers=` / `credentials=` kwarg per DF-13.2-S2 / C87).
docs/keywords/AgentEval.html:9:libdoc = {"specversion": 3, "name": "AgentEval", "doc": "<p>Robot Framework library for evaluating AI coding agents.</p>\n<p>Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point + the FR41 precedence chain (kwarg \u2192 env-var \u2192 <span class=\"name\">.env</span> \u2192 defaults) via <span class=\"name\">_kernel.context.resolve_config</span> (Story 1b.1). <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> returns the precedence-resolved values.</p>\n<p>Args: provider: Provider plugin name resolved via <span class=\"name\">agenteval.providers</span> entry-points (FR42; ADR-013). Phase 1 ships only the <span class=\"name\">litellm</span> provider; future providers register via <span class=\"name\">[project.entry-points.\"agenteval.providers\"]</span>. telemetry: Enable the OTel listener for trace recording (FR42 + FR44). When False, <span class=\"name\">Get Trace Backend Names</span> returns <span class=\"name\">[]</span> and no OTLP egress occurs (Phase 2). Phase 1 wires the parameter; full listener-disable enforcement lands in Epic 5 Story 5.1. trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports <span class=\"name\">\"memory\"</span> and <span class=\"name\">\"jsonl\"</span>; <span class=\"name\">\"otlp\"</span> is Phase 2. allow_validate_operator: Enable the AssertionEngine <span class=\"name\">validate</span> operator which uses <span class=\"name\">eval()</span> (FR42 + FR43; NFR-SEC-02). Default False \u2014 the safer posture per NFR-SEC-02. Gate enforcement (raising <span class=\"name\">ValidateOperatorDisallowed</span>) lands in Epic 6. default_temperature: Default provider temperature for non-stochastic keywords (FR42). 0.0 enforces deterministic provider calls where the underlying model supports it. mcp_per_test: MCP server scope.</p>\n<ul>\n<li>True (default): per-test isolation; correct under <span class=\"name\">pabot --processes N</span>. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>False: single shared instance across all tests; only correct serial. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>\"suite\": per-suite scope; recipe-5 dogfood-CI ergonomics override. (Architecture L314 + NFR-PERF-03d \u2014 not in ADR-009 proper.) allow_external_mcp_blind: Opt-in to running with <span class=\"name\">mcp_coverage=\"external_mixed\"</span> without <span class=\"name\">IncompleteTraceError</span> (FR42 + ADR-016 D4 adapter contract). Default False enforces loud-refusal posture from ADR-016. max_cost_usd: Cost budget for <span class=\"name\">@guarded_fanout</span>-decorated Tier-3 keywords (FR42 + ADR-015). USD per fan-out invocation. Default 5.00. max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords (FR11b + ADR-015). Default None = no cap (opt-in via explicit value). Sibling to <span class=\"name\">max_cost_usd</span>; catches slow MCP-server startup compounded across trials.</li>\n</ul>\n<p>FR41 precedence behavior (Story 1b.1): Each <span class=\"name\">__init__</span> parameter defaults to a private sentinel; if the caller does NOT pass it, the value falls through to <span class=\"name\">AGENTEVAL_*</span> env-vars, then to a <span class=\"name\">.env</span> file in cwd, then to the FR42 + FR11b defaults documented in this docstring. Callers who want to force a value explicitly (even when an env-var is set) pass that value as a kwarg. <span class=\"name\">.env.example</span> documents the canonical <span class=\"name\">AGENTEVAL_*</span> env-var names.</p>\n<p>References:</p>\n<ul>\n<li>PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)</li>\n<li>PRD FR11b (max_runtime_seconds keyword arg sibling)</li>\n<li>PRD FR41 (config precedence)</li>\n<li>ADR-009 (mcp_per_test 3-mode)</li>\n<li>ADR-013 (entry-points discovery for <span class=\"name\">provider</span>)</li>\n<li>ADR-015 (@guarded_fanout for cost + runtime guardrails)</li>\n<li>ADR-016 (mcp_coverage detection + allow_external_mcp_blind)</li>\n<li>docs/contracts/stability-surface.md (Phase-1 stability labels for this class)</li>\n</ul>", "version": "", "generated": "2026-05-27T19:45:45+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 159, "tags": ["agenteval"], "inits": [{"name": "__init__", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "provider", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "provider: str = _UNSET"}, {"name": "telemetry", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "telemetry: bool = _UNSET"}, {"name": "trace_backend", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "trace_backend: str = _UNSET"}, {"name": "allow_validate_operator", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_validate_operator: bool = _UNSET"}, {"name": "default_temperature", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "default_temperature: float = _UNSET"}, {"name": "mcp_per_test", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'suite'", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "mcp_per_test: bool | Literal['suite'] = _UNSET"}, {"name": "allow_external_mcp_blind", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_external_mcp_blind: bool = _UNSET"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_cost_usd: float = _UNSET"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize self.  See help(type(self)) for accurate signature.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 225}], "keywords": [{"name": "Agent Response Should Contain", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "substring", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "substring: str"}], "returnType": null, "doc": "<p>Asserts that <code>substring</code> appears in <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>substring</code></td>\n<td>Literal substring to match. Case-sensitive.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the substring is not found.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    Robot Framework                                          # Mock echoes the prompt.\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    test automation\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 236}, {"name": "Agent Response Should Match Regex", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "pattern", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "pattern: str"}], "returnType": null, "doc": "<p>Asserts a regex pattern matches <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 uses <code>re.search</code> (substring-match by default per FR25's \"match\" terminology). Multi-line text supported via standard <code>re</code> flags in the pattern. NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>pattern</code></td>\n<td>Python <code>re</code> pattern. Use <code>(?i)</code> / <code>(?m)</code> / <code>(?s)</code> inline flags as needed.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the pattern does not match.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Released in 2020 \u2014 Robot Framework 3.x    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    20\\d{2}                          # 4-digit year \u2014 matches the echoed \"2020\".\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the regex assertion; <span class=\"name\">re.search</span> semantics (not <span class=\"name\">re.fullmatch</span>).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts a regex pattern matches ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 268}, {"name": "Agent Response Should Match Schema", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "schema", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "schema: dict[str, Any] | str | Path"}], "returnType": null, "doc": "<p>Asserts <code>response_text</code> parses as JSON + validates against a JSON Schema (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <code>mcp_coverage<span class=\"name\">`-gated. Parses </span>`response_text</code> as JSON, then validates against the schema via <code>jsonschema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code> (expected to be JSON-parsable).</td>\n</tr>\n<tr>\n<td><code>schema</code></td>\n<td>JSON Schema as a <code>dict</code> OR a file path (<code>str</code> / <code>pathlib.Path</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>schema</code> is not a <code>dict<span class=\"name\">`/</span><span class=\"name\">str</span><span class=\"name\">/</span>`Path</code>, or when the file is not a valid JSON schema dict. Raises <code>AssertionError</code> (redacted per FR38a) when <code>response_text</code> is not JSON-parsable. Raises <code>jsonschema.ValidationError</code> when the parsed JSON does not validate against the schema (preserves the jsonschema convention so consumers can catch the specific exception).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt={\"answer\": 42}    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${{ {\"type\": \"object\", \"required\": [\"answer\"]} }}\n# Path form: <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.</li>\n<li>Uses <code>jsonschema</code> package \u2014 the upstream <code>ValidationError</code> is preserved on validation failure (callers can catch specifically).</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex pattern).</li>\n</ul>", "shortdoc": "Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 301}, {"name": "Get Cohort Heatmap", "args": [{"name": "discoverability_result", "type": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "discoverability_result: DiscoverabilityResult"}, {"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "model_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "default", "kind": "NAMED_ONLY", "required": false, "repr": "model_name: str = default"}], "returnType": {"name": "CohortHeatmap", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds a <code>CohortHeatmap</code> from a <code>DiscoverabilityResult</code> (Story 8b.2 / FR55).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection over the result's <code>per_task_results</code>; no LLM calls. Returns a <code>CohortHeatmap</code> instance with <code>.as_ascii()</code> (box-drawing rendered grid) + <code>.as_dict()</code> (nested <code>{task: {model: pass_at_k}}</code> mapping) methods.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>discoverability_result</code></td>\n<td>Result from <span class=\"name\">MCP.Get Tool Discoverability</span> (Story 4.4 / FR10a). Carries <code>per_task_results</code> list of per-task <code>pass_rate</code> values.</td>\n</tr>\n<tr>\n<td><code>model_name</code></td>\n<td>Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to <code>\"default\"</code>.</td>\n</tr>\n</table>\n<p>Phase-1 scope: single-model heatmap (one column). Multi-model comparison (rows = tasks \u00d7 columns = models) is Phase-2 work. Missing cells render as <code>\" \u2014 \"</code> sentinel (em-dash with spaces) rather than silently substituting <code>0.0</code> per the Story 10.1 kilo/minimax review HIGH-1 honesty patch.</p>\n<p>Example:</p>\n<pre>\n${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()\n${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()\n${heatmap} =    <a href=\"#Get%20Cohort%20Heatmap\" class=\"name\">Get Cohort Heatmap</a>    ${disc}    model_name=claude-sonnet-4-5\n${ascii} =    Evaluate    $heatmap.as_ascii()\nLog    ${ascii}                                                                           # Box-drawing render.\n${cells} =    Evaluate    $heatmap.as_dict()\nShould Not Be Empty    ${cells}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 8b.2 ratifies the <code>CohortHeatmap</code> data class + <code>Get Cohort Heatmap</code> keyword surface.</li>\n<li>FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> produces the <code>DiscoverabilityResult</code> input.</li>\n</ul>", "shortdoc": "Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_heatmap/library.py", "lineno": 49}, {"name": "Get Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a Claude Code <code>settings.json</code> hook configuration.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per-entry validation per PRD FR4. Returns a dict mapping <code>hooks.&lt;event&gt;</code> \u2192 list of validated hook entries. Covered events: <code>PreToolUse</code>, <code>PostToolUse</code>, <code>Stop</code>; other events are passed through with the same validation. Median \u2264 50 ms on typical hook configs per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>settings.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Each returned entry has <code>command</code> (required) plus any of the optional fields <code>args</code> / <code>timeout</code> / <code>matcher</code> that were present in the source JSON. Entries whose command contains an inline YAML frontmatter block additionally surface an <code>inline_skill: dict</code> field with the parsed frontmatter.</p>\n<p>Raises <code>InvalidHookConfigError</code> on any structural failure (file not found, malformed JSON, missing <code>command</code>, wrong-type optional field). The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer (e.g. <code>/hooks/PreToolUse/0/command</code>) pinpointing the nested location. Format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>This keyword is re-exported through the top-level <code>AgentEval</code> library, so <code>AgentEval.Get Config</code> and <code>Hook.Get Config</code> (when imported as <code>WITH NAME    Hook</code>) resolve to the same implementation.</p>\n<p>Example:</p>\n<pre>\n${config} =    <a href=\"#Get%20Config\" class=\"name\">Get Config</a>    ${CURDIR}/.claude/settings.json\nLength Should Be    ${config}[hooks.PreToolUse]    1\nShould Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook\nShould Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop). Unknown events are validated with the same shape contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format: FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104. The <code>field_name</code> attribute on raised errors carries an RFC 6901 JSON Pointer.</li>\n<li>Inline-skill-frontmatter hooks are an extension surface \u2014 the inner skill is reachable via <span class=\"name\">SkillsLibrary</span> keywords passed the <code>inline_skill</code> dict directly.</li>\n</ul>", "shortdoc": "Parses a Claude Code ``settings.json`` hook configuration.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/hooks/library.py", "lineno": 66}, {"name": "Get Cost Total", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns total provider-reported USD cost (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (USD). Single run: the run's <code>cost_usd</code>. Multi-trial: sum across trials. Empty list \u2192 <code>0.0</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <code>mcp_coverage<span class=\"name\">`-gated. Returns </span>`0.0</code> on the Mock provider; non-zero on real adapters per Story 8a.1 (real adapters use <code>total_cost_usd</code> not <code>cost_usd</code>).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${cost_usd} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${result}\nShould Be True    ${cost_usd} &lt; 0.10                                      # Single-shot cost cap $0.10.\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${total_cost} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${results}                         # Cohort cost rollup.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the cost metric.</li>\n<li>Mock-provider runs return <code>0.0</code> cost; real adapters surface the provider's reported cost.</li>\n<li>Story 8a.1 v1 HIGH-1 ratified <code>total_cost_usd</code> as the canonical real-adapter key.</li>\n<li>Sibling keywords: <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns total provider-reported USD cost (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 419}, {"name": "Get Effective Config", "args": [{"name": "setting", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "setting: str | None = None"}], "returnType": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "doc": "<p>Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 two-form return: no-arg \u2192 <code>dict[str, Any]</code> of resolved values (Story 1a.6 ratified shape, backwards-compat with tier-1 + smoke tests); <code>setting=&lt;key&gt;</code> \u2192 <code>ConfigValue(value, source)</code> for that single setting (FR41 L1563). <code>source</code> is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>setting</code></td>\n<td>Optional config-key name (e.g., <code>\"max_cost_usd\"</code>). When <code>None</code> (default), returns the full <code>dict[str, Any]</code>. When set, returns the single <code>ConfigValue</code> for that key.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>setting</code> is set but not a known config key (with a sorted list of known keys in the message).</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0    telemetry=False\n${config} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>\nShould Be Equal As Numbers    ${config}[max_cost_usd]    5.0\nShould Be Equal    ${config}[telemetry]    ${FALSE}\n${cost_setting} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>    setting=max_cost_usd\nShould Be Equal As Numbers    ${cost_setting.value}    5.0\nShould Be Equal    ${cost_setting.source}    init_arg\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the ConfigValue surface; FR42 ratifies the 9 settings.</li>\n<li>Story 4.3 DF-4.3-S1 carry-over: full <code>dict[str, ConfigValue]</code> migration of the no-arg form is Phase-1.5.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a> for the FR41-compliant full-surface form.</li>\n</ul>", "shortdoc": "Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 398}, {"name": "Get Effective Config With Provenance", "args": [], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "ConfigValue", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the full settings map with per-key provenance as a <code>dict[str, ConfigValue]</code> (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 FR41-compliant surface. Each <code>ConfigValue</code> carries <code>value</code> + <code>source</code> per FR41 L1563. Source is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td>(none)</td>\n<td>Returns the full settings map; no arguments.</td>\n</tr>\n</table>\n<p>Defensive shallow-copy of the underlying provenance dict \u2014 caller mutations don't propagate to the Library's internal state.</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0\n${settings} =    <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a>\n${cost} =    Set Variable    ${settings}[max_cost_usd]\nShould Be Equal As Numbers    ${cost.value}    5.0\nShould Be Equal    ${cost.source}    init_arg                              # Constructor kwarg won.\n${temp} =    Set Variable    ${settings}[default_temperature]\nShould Be Equal    ${temp.source}    default                               # Not overridden \u2014 uses FR42 default.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the <code>dict[str, ConfigValue]</code> shape.</li>\n<li>This is the FR41-compliant surface DF-4.3-S1 will migrate <code>Get Effective Config</code> (no-arg) to once tier-1 tests update.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> for the simpler <code>dict[str, Any]</code> or per-setting form.</li>\n</ul>", "shortdoc": "Returns the full settings map with per-key provenance as a ``dict[str, ConfigValue]`` (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 517}, {"name": "Get Keyword Tier", "args": [{"name": "keyword", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the determinism-tier annotation for an RF keyword (PRD FR30a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int \u2208 {1, 2, 3}</code>. Walks the composed DynamicCore keyword registry + top-level methods to resolve the verbatim RF name to its <code>_agenteval_tier</code> integer via the <code>@tier(N)</code> decorator chain.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>Verbatim RF keyword name (e.g., <code>\"Send Prompt\"</code>, <code>\"Stat.Run N Times\"</code>, <code>\"Get Effective Config\"</code>).</td>\n</tr>\n</table>\n<p>Returns the wrapper's own tier, not the wrapped keyword's tier \u2014 e.g., <code>Stat.Run N Times</code> returns <code>3</code> (fan-out runner tier) per epic AC-5 + Story 6.3 D-14 amendment. The runner's tier governs the <code>@guarded_fanout</code> enforcement model, independent of the wrapped keyword's own classification.</p>\n<p>Raises <code>ValueError</code> when the keyword is not found in the composed library (with a sorted list of known keywords in the message), OR when the keyword has no <code>@tier(N)</code> annotation, OR when the annotated tier is outside <code>{1, 2, 3}</code> (defensive range check per Story 6.3 code-review HIGH-\u03c0 fix).</p>\n<p>Example:</p>\n<pre>\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Get Tool Call Count\nShould Be Equal As Integers    ${tier}    1                                # Tier-1 deterministic metric.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Send Prompt\nShould Be Equal As Integers    ${tier}    2                                # Tier-2 stochastic single-shot.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Stat.Run N Times\nShould Be Equal As Integers    ${tier}    3                                # Tier-3 fan-out runner.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR30a ratifies the tier-introspection contract; AC-6.3.7 establishes the DynamicCore walk.</li>\n<li>Story 6.3 D-14 amendment: fan-out runner reports its own tier (3), not the wrapped keyword's tier.</li>\n<li>Sibling keywords: every <span class=\"name\">@tier</span>-decorated keyword in the composed library is introspectable here.</li>\n</ul>", "shortdoc": "Returns the determinism-tier annotation for an RF keyword (PRD FR30a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 450}, {"name": "Get Last Warnings", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[dict]</code>. Each record has the FR62 ratified 5-field shape: <code>warning_type</code> (str \u2014 fully-qualified Python warning class), <code>message</code> (str \u2014 human- readable text), <code>source</code> (str \u2014 emitting subsystem), <code>timestamp</code> (str \u2014 UTC RFC 3339), <code>remediation</code> (str | None \u2014 actionable advice).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test via the listener context; returns <code>[]</code> if no test is bound. <code>\"all\"</code> \u2014 union across every per-test buffer in the process, sorted by <code>timestamp</code> ascending. Any other value is treated as a specific test_id (returns the named buffer or <code>[]</code> if absent).</td>\n</tr>\n</table>\n<p>Defensive copy of records. Never raises \u2014 buffer-read failures fall back to <code>[]</code>.</p>\n<p>Example:</p>\n<pre>\n@{warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>\nLength Should Be    ${warnings}    0                                                   # Clean run: zero warnings.\n@{all_warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>    test_id=all\nFOR    ${w}    IN    @{all_warnings}\n    Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR62 ratifies the 5-field <code>WarningRecord</code> shape.</li>\n<li>Story 5.4 ratified the per-test buffer + <code>\"all\"</code> aggregation contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> \u2014 companion trace-store accessors.</li>\n</ul>", "shortdoc": "Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 64}, {"name": "Get Latency", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns mean turn-level latency in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). When the run has no <code>tool_calls</code>, falls back to <code>result.latency_seconds * 1000.0</code>. Multi-trial: union-of- tool-calls mean \u2014 all per-tool-call latencies from all trials are flattened into one list before <code>statistics.mean()</code> is taken. Mean-of-per-run-means is a statistical anti-pattern (under-weights runs with more tool calls); union-then-mean is the operator-intuitive default per Story 6.1 code-review.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${latency_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${result}\nShould Be True    ${latency_ms} &lt; 2000                                    # Mean turn latency under 2 seconds.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the latency metric \u2014 per-tool-call resolution preferred over per-run.</li>\n<li>Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).</li>\n<li>Sibling keyword: <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a> for tail-latency tracking.</li>\n<li>Provider-reported scalar \u2014 observer-independent per AC-6.1.1.</li>\n</ul>", "shortdoc": "Returns mean turn-level latency in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 355}, {"name": "Get Latency P95", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the P95 latency across tool calls in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). AC-6.1.8 boundary conditions: 0 tool_calls \u2192 <code>0.0</code>; 1 tool_call \u2192 that single latency; \u22652 \u2192 <code>statistics.quantiles(n=100)[94]</code>. Multi-trial: P95 across the union of all tool_calls' latencies.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${p95_ms} =    <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>    ${results}\n${mean_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${results}\nShould Be True    ${p95_ms} &gt;= ${mean_ms}                                 # P95 \u2265 mean by definition.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the P95 metric \u2014 tail-latency tracking complements <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> mean.</li>\n<li>AC-6.1.8 boundary conditions cover empty / single-call edge cases.</li>\n<li>Sibling keywords: <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> for mean; <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> to generate multi-trial input.</li>\n</ul>", "shortdoc": "Returns the P95 latency across tool calls in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 389}, {"name": "Get Run Manifest", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "Union", "typedoc": null, "nested": [{"name": "RunManifest", "typedoc": null, "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "doc": "<p>Returns the in-memory 7-field <code>RunManifest</code> for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>RunManifest | None</code>. <code>None</code> when <code>test_id=\"current\"</code> and no test is bound (Tier-1 sibling-consistency with <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> / <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> / <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a> non-raising contracts). The in-memory manifest is the <b>*ratified 7-field shape*</b> (<code>library_version</code>, <code>test_id</code>, <code>suite_id</code>, <code>redaction_policy_hash</code>, <code>started_at</code>, <code>ended_at</code>, <code>agenteval_tier_breakdown</code>) \u2014 NOT the Story-5.3-extended operational metadata dict (which lives in the JSON sidecar at <code>&lt;output_dir&gt;/agenteval/manifest__&lt;suite&gt;__&lt;test&gt;.json</code>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>None</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim \u2014 that accessor's <code>ValueError</code> propagates if the explicit id resolves to None per Story 1b.2 semantics.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n${manifest} =    <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>\nShould Not Be Equal    ${manifest}    ${NONE}\nShould Not Be Empty    ${manifest.library_version}\nLength Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li>7-field shape ratified at Story 1b.2 per FR39.</li>\n<li>Story 5.5 code-review 2-way HIGH-F established the <code>None</code> (not raise) contract on no-bound-test current path.</li>\n<li>For the Story-5.3-extended operational shape, read the JSON sidecar directly.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 178}, {"name": "Get Spans", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ReadableSpan", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ReadableSpan]</code> in chronological order by <code>start_time</code>. Empty list is a valid state (test ran without emitting spans). Thin keyword wrapper around the <code>_kernel/trace_store.get_run_spans</code> projection accessor.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n@{spans} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>\nShould Not Be Empty    ${spans}\nFOR    ${span}    IN    @{spans}\n    ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}\n    Log    ${span.name} took ${duration_ns} ns\nEND\n@{spans_specific} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>    test_id=My Suite.Specific Test\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.</li>\n<li>Story 5.5 code-review 3-way HIGH-A established the no-bound-test \u2192 <code>[]</code> non-raising contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> (projection over execute_tool spans); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> (resource-attribute projection); <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 98}, {"name": "Get Token Usage", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "Usage", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Returns the agent's token usage as a <code>Usage</code> dataclass (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>Usage(input_tokens, output_tokens, cached_input_tokens)</code>. Single run: the run's own usage. Multi-trial: sum per field. Empty list \u2192 <code>Usage(0, 0, 0)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 observer-independent. NOT <span class=\"name\">`mcp_coverage</span>`-gated (PRD FR22 + AC-6.1.1).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${usage} =    <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>    ${result}\nShould Be True    ${usage.input_tokens} &gt; 0\nShould Be True    ${usage.output_tokens} &gt; 0\nLog    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the four usage metrics \u2014 <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>, <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a> \u2014 all observer-independent per AC-6.1.1.</li>\n<li><code>Usage</code> is a frozen dataclass; field validation ensures non-negative counts.</li>\n<li>Sibling keywords: <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 324}, {"name": "Get Tool Call Count", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the number of tool calls made by the agent (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int</code>. Single run: <code>len(result.tool_calls)</code>. Multi-trial: sum across trials.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial sum aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code> (default-deny per FR42).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${count} =    <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a>    ${result}\nShould Be Equal As Integers    ${count}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42 \u2014 opt out via <code>AgentEval(allow_external_mcp_blind=True)</code>.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a> for the ordered names list.</li>\n</ul>", "shortdoc": "Returns the number of tool calls made by the agent (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 92}, {"name": "Get Tool Call Names", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns tool-call names in chronological order (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 duplicates preserved per FR19 verbatim (\"list[str] (preserving order)\"). Single run: chronological list. Multi-trial: union preserving order-of-first-appearance.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial union aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n@{names} =    <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a>    ${result}\nShould Contain    ${names}    web_search\nShould Be Equal    ${names}[0]    web_search                              # First tool called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> for the count; <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> for expected-set comparison.</li>\n</ul>", "shortdoc": "Returns tool-call names in chronological order (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 132}, {"name": "Get Tool Calls", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ToolCallTrace", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns <code>ToolCallTrace</code> records projected from the trace store (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ToolCallTrace]</code>. Thin keyword wrapper around <code>_kernel/trace_store.get_tool_calls</code>. Mirrors the source-filtering semantics of the Story 1b.2 accessor (no per-call source filter exposed at the RF surface; consumers filter the returned list themselves).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Returns <code>list[ToolCallTrace]</code> frozen dataclasses (Story 1b.2 shape): each record carries <code>name</code>, <code>args</code>, <code>result</code>, <code>error</code>, <code>latency_ms</code>, <code>source</code>, <code>gen_ai_tool_call_id</code>, <code>sequence_index</code>.</p>\n<p>Example:</p>\n<pre>\n@{tool_calls} =    <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>\nShould Not Be Empty    ${tool_calls}\nShould Be Equal    ${tool_calls}[0].name    web_search\nShould Be Equal As Integers    ${tool_calls}[0].sequence_index    0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li><span class=\"name\">ToolCallTrace</span> shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> (full span list); <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> (metrics-library count over <span class=\"name\">AgentRunResult</span>); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>.</li>\n</ul>", "shortdoc": "Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 139}, {"name": "Get Tool Hit Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-hit rate <code>|expected \u2229 observed| / |expected|</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Empty <code>expected_tools</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: union-of-observed against expected_tools.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${hit_rate} =    <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a>    ${result}    ${{['web_search', 'fetch']}}\nShould Be True    ${hit_rate} &gt;= 0.5                                      # At least half of expected tools were called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keywords: <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a> (calls NOT in expected set); <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a> (errors / total).</li>\n</ul>", "shortdoc": "Returns the tool-hit rate ``|expected \u2229 observed| / |expected|`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 178}, {"name": "Get Tool Success Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-success rate <code>non-error / total</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: aggregate across all per-trial tool calls.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${success_rate} =    <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a>    ${result}\nShould Be True    ${success_rate} &gt;= 0.8                                  # At least 80% of tool calls succeeded.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Each <code>ToolCallTrace</code> has an <code>error</code> field \u2014 non-None counts as a failure.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (vs expected set); <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>.</li>\n</ul>", "shortdoc": "Returns the tool-success rate ``non-error / total`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 224}, {"name": "Get Unnecessary Call Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the unnecessary-call rate <code>not_in_expected / total</code> (PRD FR21).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${noise} =    <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>    ${result}    ${{['web_search']}}\nShould Be True    ${noise} &lt;= 0.2                                         # At most 20% of calls were off-task.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR21 ratifies the unnecessary-rate formula \u2014 quantifies \"noise\" tool calls beyond the expected set.</li>\n<li>AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls \u2192 0.0).</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (calls that ARE in expected set).</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n</ul>", "shortdoc": "Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 271}, {"name": "Judge.Calibrate Rubric", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "calibration_set", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "calibration_set: str | Path"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "CalibrationReport", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs the judge against a labeled calibration set and returns a <span class=\"name\">CalibrationReport</span> (Story 12.2).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 N single-shot LLM calls (one per calibration row) against the configured <code>judge_adapter</code>. Cohen's kappa over binarized judge-pass / human-pass labels at the rubric's threshold; <code>passes_hard_fail</code> is True iff <code>kappa &gt;= 0.7</code> per <span class=\"name\">architecture.md</span> L199 agentguard-borrowed calibration discipline. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>calibration_set</code></td>\n<td>Path to a YAML calibration set with <span class=\"name\">rows:</span> list of <span class=\"name\">{prompt, response, human_label}</span>.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug; defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier; forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Returns <code>CalibrationReport</code> with: <code>cohen_kappa</code> (float; <code>nan</code> if zero-variance), <code>passes_hard_fail</code> (kappa &gt;= 0.7), <code>threshold_tuning</code> (precision/recall/F1 sweep), <code>recommended_threshold</code> (F1-maximizing), <code>systematic_bias_diagnostics</code> (human-readable bullets), <code>total_cost_usd</code>, <code>total_latency_seconds</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>InvalidCalibrationSetError</code> on calibration set parse failure. Raises <code>JudgeOutputParseError</code> if any per-row judge invocation returns malformed JSON.</p>\n<p>Example:</p>\n<pre>\n${report} =    <a href=\"#Judge.Calibrate%20Rubric\" class=\"name\">Judge.Calibrate Rubric</a>    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${report.passes_hard_fail}\nLog    Cohen's kappa = ${report.cohen_kappa}\nLog    Recommended threshold = ${report.recommended_threshold}\n</pre>\n<p>Notes:</p>\n<ul>\n<li><span class=\"name\">KAPPA_HARD_FAIL_THRESHOLD = 0.7</span> per <span class=\"name\">architecture.md</span> L199.</li>\n<li>Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.</li>\n<li>Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.</li>\n</ul>", "shortdoc": "Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).", "tags": ["agenteval"], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 187}, {"name": "Judge.Get Score", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "result: AgentRunResult"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "JudgeScore", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Evaluates an <span class=\"name\">AgentRunResult</span> against a Markdown rubric using an LLM judge (PRD FR48).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 single-shot LLM call against the configured <span class=\"name\">judge_adapter</span> (default <span class=\"name\">\"generic\"</span> LiteLLM-backed). LLM-deterministic per the determinism-contract.md <span class=\"name\">@tier(2)</span> contract when invoked with <span class=\"name\">seed + temperature=0</span>. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>The <span class=\"name\">AgentRunResult</span> to evaluate. Reads <code>result.response_text</code> for the agent's output.</td>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug to resolve via <span class=\"name\">agenteval.coding_agents</span> entry-points. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier for the judge adapter (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>). Forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs (e.g., <code>temperature=0.0</code>, <code>seed=42</code>).</td>\n</tr>\n</table>\n<p>Returns <code>JudgeScore</code> with: <code>numeric_score</code> (0-10), <code>pass_threshold_met</code> (vs rubric threshold), <code>reasoning</code> (LLM's narrative explanation), <code>criteria_breakdown</code> (per-criterion sub-scores), <code>cost_usd</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>JudgeOutputParseError</code> when the LLM response is not valid JSON OR is missing required fields OR <code>numeric_score</code> is outside <code>[0.0, 10.0]</code>.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6\n${score} =    <a href=\"#Judge.Get%20Score\" class=\"name\">Judge.Get Score</a>    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${score.pass_threshold_met}\nShould Be True    ${score.numeric_score} &gt;= 7.0\nLog    Reasoning: ${score.reasoning}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR48 ratifies the keyword + rubric calibration discipline.</li>\n<li>Tier-2 LLM-deterministic per <span class=\"name\">determinism-contract.md</span>; cost guardrails per ADR-015.</li>\n<li><span class=\"name\">JudgeScore</span> shape ratified Story 12.1 AC-12.1.2 per architecture L1316.</li>\n<li>Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.</li>\n</ul>", "shortdoc": "Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 117}, {"name": "Load Scenario", "args": [{"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "scenario: str"}], "returnType": {"name": "Scenario", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Loads + validates a scenario YAML without executing it.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file read + YAML parse + schema validation. Returns the parsed <code>Scenario</code> dataclass without dispatching to any adapter \u2014 useful for <code>.robot</code> tests that assert on scenario metadata or pre-flight-check scenarios before a <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidScenarioYAMLError</code> on parse failure or schema violation. The error's <code>field_name</code> attribute pinpoints the offending field per FR59.</p>\n<p>Example:</p>\n<pre>\n${scenario} =    <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a>    ${CURDIR}/scenarios/web-search.yaml\nShould Be Equal    ${scenario.agent}    web-search-agent\nShould Be Equal    ${scenario.model}    anthropic/claude-sonnet-4-6\nLength Should Be    ${scenario.evals}    5\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the scenario YAML schema; see <span class=\"name\">Scenario</span> dataclass in <span class=\"name\">scenarios/schema.py</span>.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> (Tier-3) for dispatch + execution.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n</ul>", "shortdoc": "Loads + validates a scenario YAML without executing it.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 330}, {"name": "Run Scenario", "args": [{"name": "adapter", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "_Unset", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str | _Unset = _UNSET"}, {"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "scenario: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Executes a scenario YAML file's <code>evals[]</code> against an adapter (PRD FR15).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 loads the scenario YAML via <code>load_scenario()</code>, validates against the <code>Scenario</code> schema, then dispatches each eval's prompt to <code>adapter.run()</code> <code>repeat</code> times. Returns a flat <code>list[AgentRunResult]</code> of length <code>sum(eval.repeat for eval in scenario.evals)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Per-scenario <code>agent:</code> field in the YAML overrides this kwarg per FR15 (\"scenario YAML specifies agent\" \u2014 YAML beats default but not explicit kwarg).</td>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code>. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are split between adapter constructor + <code>run()</code> per the same signature-introspection rule as <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>. Scenario-YAML <code>model:</code> / <code>provider:</code> fields inject into the merged kwargs unless the caller already passed them.</p>\n<p>Raises <code>InvalidScenarioYAMLError</code> on YAML parse / schema failure, <code>AdapterDiscoveryError</code> on unknown adapter name, and <code>NotImplementedError</code> on non-empty comma-separated <code>mcp_servers</code> (Phase-1 DF-4.3-S2 carve-out).</p>\n<p>Example:</p>\n<pre>\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    scenario=${CURDIR}/scenarios/web-search.yaml\nLength Should Be    ${results}    5\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the multi-eval orchestration contract.</li>\n<li>FR41 precedence resolution: explicit kwarg &gt; scenario YAML &gt; library default.</li>\n<li>Sibling keyword: <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a> (Tier-1) to validate the YAML without executing.</li>\n<li>Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).</li>\n</ul>", "shortdoc": "Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 215}, {"name": "Send Prompt", "args": [{"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "prompt: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Executes a single-shot prompt against a coding-agent adapter (PRD FR14).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 invokes the named adapter's <code>run()</code> method per the <span class=\"name\">CodingAgentAdapter</span> Protocol. Returns an <code>AgentRunResult</code> carrying <code>response_text</code>, <code>tool_calls</code>, <code>usage</code>, <code>metadata</code> (with <code>completeness</code> + <code>mcp_coverage</code>), <code>cost_usd</code>, <code>latency_seconds</code>, and <code>trace_id</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code> (LiteLLM-backed).</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code> of attached MCP servers. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2 \u2014 name resolution to handles deferred).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are forwarded to the adapter \u2014 caller kwargs that match the adapter's <code>__init__</code> signature flow to construction; the rest flow to <code>run()</code>. Useful for <code>model=\"anthropic/claude-sonnet-4-6\"</code>, <code>temperature=0.5</code>, etc.</p>\n<p>Raises <code>AdapterDiscoveryError</code> when the <code>adapter</code> name is not registered. Raises <code>NotImplementedError</code> on comma-separated <code>mcp_servers</code> name strings until DF-4.3-S2 lands the name \u2192 handle resolver (pass <code>mcp_servers={'name': handle}</code> directly to forward Phase-1).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Hello, world.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=claude-code-cli    prompt=Run the build.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR14 ratifies the single-prompt orchestration contract.</li>\n<li>Adapter discovery per Story 1b.3 + ADR-013 entry-points.</li>\n<li><code>cost_usd</code> is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> for multi-eval YAML-driven dispatch (Tier-3).</li>\n</ul>", "shortdoc": "Executes a single-shot prompt against a coding-agent adapter (PRD FR14).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 127}, {"name": "Stat.Assert Run Determinism", "args": [{"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "expect", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "byte_identical", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "expect: str = byte_identical"}], "returnType": null, "doc": "<p>Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 invokes the wrapped keyword twice with identical inputs and compares via deep-equality. The bit-identical guarantee is scoped to Tier-1 keywords only (FR31a contract); the keyword raises <code>TierViolationError</code> if a Tier-2/3 keyword is passed.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR callable. Same dispatch rules as <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> (string form requires active RF context).</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings.</td>\n</tr>\n<tr>\n<td><code>expect</code></td>\n<td>Comparison mode. Phase-1 supports <code>\"byte_identical\"</code> only; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> deferred to Phase-2.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>expect != \"byte_identical\"</code> (Phase-1 scope). Raises <code>TierViolationError</code> when the wrapped keyword is not Tier-1 \u2014 FR31a is scoped to Tier-1 only. Raises <code>AssertionError</code> on output mismatch with a <span class=\"name\">`redact()</span>`-scrubbed diff per FR38a credential-safety contract.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Effective Config\nRun Keyword And Expect Error    TierViolationError*    <a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Send Prompt\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> + <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for statistical assertions instead.</li>\n<li>Diff redaction per FR38a + Story 5.3 \u2014 credentials in args / output don't leak into RF logs.</li>\n<li>Story 6.3 ratifies <code>\"byte_identical\"</code> as the Phase-1 contract; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> are Phase-2 work-items.</li>\n</ul>", "shortdoc": "Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 270}, {"name": "Stat.Get Pass At K", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form computation of the HumanEval estimator <code>1 - C(n-c, k) / C(n, k)</code>. Returns <code>float \u2208 [0, 1]</code>. Scalar return preserves AssertionEngine compatibility (<code>&gt;=</code> / <code>&lt;=</code> matchers); CI is a separate paired getter \u2014 see <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Must satisfy <code>1 &lt;= k &lt;= len(runs)</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Default checks <code>r.completeness == \"complete\"</code> per epic AC-2 + Story 6.4 fix-NOW.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k &lt; 1</code>, <code>k &gt; len(runs)</code>, or <code>len(runs) == 0</code>.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${pass_at_1} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=1\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.\n${pred} =    Evaluate    lambda r: r.error is None\n${pass_strict} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5    predicate=${pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR27 ratifies the scalar <code>float</code> return type \u2014 no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).</li>\n<li>Default predicate updated by Story 6.4 fix-NOW: <code>completeness == \"complete\"</code> (pre-edit <code>\"full\"</code> was fake-green; <span class=\"name\">AgentRunMetadata._VALID_COMPLETENESS</span> is <code>{\"complete\", \"truncated\", \"partial\"}</code>).</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a> for the Wilson score CI.</li>\n</ul>", "shortdoc": "Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 172}, {"name": "Stat.Get Pass At K Confidence Interval", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}, {"name": "confidence", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.95", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "confidence: float = 0.95"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Wilson score interval at the given <code>confidence</code> level for the latent per-trial success probability. Returns <code>(ci_lower, ci_upper)</code> tuple of <code>float</code> in <code>[0, 1]</code>. Paired with <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> \u2014 the scalar point estimate plus this CI together satisfy epic AC-2's \"Pass@k with confidence interval\" promise.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Validated for <code>1 &lt;= k &lt;= len(runs)</code> but only used for sanity check \u2014 the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Same default as <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>.</td>\n</tr>\n<tr>\n<td><code>confidence</code></td>\n<td>Confidence level in <code>(0, 1)</code>. Defaults to <code>0.95</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k</code> is non-positive or <code>k &gt; n</code> (with <code>n &gt; 0</code> \u2014 empty <code>runs</code> is permitted per the Wilson formula).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5\nShould Be True    0.0 &lt;= ${ci_lo} &lt;= ${ci_hi} &lt;= 1.0                      # CI bounds are well-formed probabilities.\n${ci99_lo}    ${ci99_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5    confidence=0.99\nShould Be True    (${ci99_hi} - ${ci99_lo}) &gt;= (${ci_hi} - ${ci_lo})      # Higher confidence \u2192 wider interval.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.</li>\n<li>PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for the scalar point estimate.</li>\n</ul>", "shortdoc": "Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 214}, {"name": "Stat.Run N Times", "args": [{"name": "n", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "n: int"}, {"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "seed", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "int", "typedoc": "integer", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "seed: int | None = None"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Runs a keyword <code>n</code> times independently and returns the per-trial results (PRD FR26).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 wraps the target keyword in independent trials. Returns <code>list[KeywordRun]</code> of length <code>n</code>. Trial-level errors are re-raised from this keyword \u2014 wrap in <code>Run Keyword And Ignore Error</code> for \"ignore failures\" semantics.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>n</code></td>\n<td>Number of independent trials. Must be <code>&gt;= 1</code>.</td>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR a Python callable. String form requires an active RF execution context (resolved via <code>BuiltIn</code>); callable form is useful for pytest unit tests.</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings (e.g. <code>{\"adapter\": \"generic\", \"prompt\": \"Hi\"}</code> or <code>[\"adapter=generic\", \"prompt=Hi\"]</code>). <code>None</code> = no args.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>Optional <code>int</code> seed; each trial receives <code>seed + trial_index</code> via a <code>seed=</code> kwarg injection so trials are deterministic but distinct. <code>None</code> = OS-entropy seeding per trial.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>n &lt; 1</code>. Raises <code>CostExceededError</code> / <code>RuntimeBudgetExceededError</code> per the <code>@guarded_fanout</code> 3-layer enforcement.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= 0.6\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the <code>list[KeywordRun]</code> return type.</li>\n<li>Cost / runtime guardrails per ADR-015 + <span class=\"name\">_kernel/guardrails.py::@guarded_fanout</span>.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> (Tier-1) consumes the returned list.</li>\n</ul>", "shortdoc": "Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 86}, {"name": "Tool Call Should Have Occurred", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "tool", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool: str"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: dict[str, Any] | None = None"}, {"name": "match_mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "subset", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "match_mode: str = subset"}], "returnType": null, "doc": "<p>Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 searches all observed <code>tool_calls</code> for one matching <code>tool</code> + (optionally) <code>args</code>. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>tool</code></td>\n<td>Expected tool name (exact-match required).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>Optional dict of expected args. <code>None</code> (default) = name-only match.</td>\n</tr>\n<tr>\n<td><code>match_mode</code></td>\n<td><code>\"subset\"</code> (default \u2014 <code>args</code> is a dict-subset of <code>tc.args</code>; recursive for nested dicts) OR <code>\"exact\"</code> (<code>tc.args == args</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>match_mode</code> is invalid (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> when no tool call matches.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected <code>web_search</code> call):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"agenteval\"} }}\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"x\"} }}    match_mode=exact\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR24 ratifies the name + args + match-mode contract.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a> for ordered-sequence assertions over multiple calls.</li>\n</ul>", "shortdoc": "Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 162}, {"name": "Trajectory Should Match", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "expected", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected: list[str]"}, {"name": "mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "exact", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mode: str = exact"}], "returnType": null, "doc": "<p>Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 four match modes available. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a so credentials in tool args don't leak into RF logs.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>expected</code></td>\n<td>List of expected tool names (or regex patterns when <code>mode=\"regex\"</code>).</td>\n</tr>\n<tr>\n<td><code>mode</code></td>\n<td>Match mode: <code>\"exact\"</code> (ordered equality) / <code>\"subsequence\"</code> (ordered, extras allowed between) / <code>\"set\"</code> (unordered set-equality of distinct names) / <code>\"regex\"</code> (each <code>expected[i]</code> is a <code>re.fullmatch</code> pattern against <code>&lt;tool&gt;:&lt;json.dumps(args, sort_keys=True)&gt;</code>). Default <code>\"exact\"</code>.</td>\n</tr>\n</table>\n<p>Set-mode caveat: duplicate names collapse \u2014 <code>[\"a\", \"a\"]</code> set- equals <code>[\"a\"]</code>. Operators wanting multiset semantics (\"exactly N calls of tool X\") should use <code>mode=\"exact\"</code>.</p>\n<p>Raises <code>ValueError</code> when <code>mode</code> is not one of the 4 documented values (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> on trajectory mismatch.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected 3-call trajectory):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'fetch', 'summarize']}}\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['fetch', 'web_search']}}    mode=set\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR23a + FR23b ratify the 4 match modes.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a> for single-call name+args assertions.</li>\n</ul>", "shortdoc": "Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 86}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config", "Get Last Warnings", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["__init__", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config With Provenance", "Get Last Warnings", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["__init__", "Get Cost Total", "Get Latency", "Get Latency P95", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Keyword Tier", "Get Tool Call Count", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Config", "Get Cost Total", "Get Last Warnings", "Get Latency", "Get Latency P95", "Get Spans", "Get Token Usage", "Get Tool Call Count", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Run Scenario", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Trajectory Should Match"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["__init__"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["__init__", "Get Effective Config", "Get Run Manifest", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Judge.Calibrate Rubric", "Judge.Get Score"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["__init__", "Agent Response Should Contain", "Agent Response Should Match Regex", "Agent Response Should Match Schema", "Get Cohort Heatmap", "Get Config", "Get Effective Config", "Get Effective Config With Provenance", "Get Keyword Tier", "Get Last Warnings", "Get Run Manifest", "Get Spans", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Unnecessary Call Rate", "Judge.Calibrate Rubric", "Judge.Get Score", "Load Scenario", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred", "Trajectory Should Match"], "accepts": ["Any"]}, {"type": "Standard", "name": "tuple", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> or <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible lists converted further to tuples. They can contain any values <code>ast.literal_eval</code> supports, including tuples and other collections.</p>\n<p>If the argument is a tuple, it is used without conversion. Lists and other sequences are converted to tuples.</p>\n<p>If the type has nested types like <code>tuple[str, int, int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>('one', 'two')</code>, <code>(('one', 1), ('two', 2))</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for list literals is new in Robot Framework 7.4.</p>", "usages": ["Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Sequence"]}]}
docs/recipes/08-ci-integration.md:129:Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
docs/recipes/08-ci-integration.md:136:Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
docs/recipes/08-ci-integration.md:154:- Default (`otlp_endpoint` unset): `http://localhost:4318/v1/traces`.
_bmad-output/planning-artifacts/epics.md:132:- **FR44 [P1]:** Library exposes `__init__(telemetry=False)` to disable OTel listener; `Get Trace Backend Names` returns `[]`; no network egress to OTLP endpoints; verifiable via `Assert No Egress To`.
_bmad-output/planning-artifacts/epics.md:2162:I want `trace_backend="otlp"` shipping JSONL spans to an OTLP collector,
_bmad-output/planning-artifacts/epics.md:2167:**Given** `trace_backend="otlp"` + `otlp_endpoint="http://localhost:4318/v1/traces"` configuration,
_bmad-output/planning-artifacts/epics.md:2171:**And** OTLP backend supports both gRPC (`otlp_endpoint="grpc://..."`) and HTTP (`otlp_endpoint="http://..."`) per OTel SDK conventions.
_bmad-output/planning-artifacts/prd.md:1549:- **FR33b (backends):** Library emits trace artifacts to `memory` backend by default + `jsonl` backend (Phase 1) + `otlp` backend (Phase 2 via `[otlp]` extra); verifiable via `Get Trace Backend Names` returning configured backends.
_bmad-output/planning-artifacts/prd.md:1566:- **FR44:** Library exposes `__init__(telemetry=False)` to disable the OTel listener; when disabled, `Get Trace Backend Names` returns `[]` and no network egress occurs to OTLP endpoints (Phase 2). Verifiable via `Assert No Egress To` fixture in conformance suite when `telemetry=False`.
_bmad-output/planning-artifacts/architecture.md:673:  - `otlp` backend (Phase 2 via `[otlp]` extra) — swaps `InMemorySpanExporter` for `OTLPSpanExporter`; configured via `__init__(trace_backend="otlp", otlp_endpoint=...)`.

exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
from opentelemetry import trace
from AgentEval.telemetry import listener as listener_mod
import os

# reset env
os.environ['AGENTEVAL_TRACE_BACKEND'] = 'otlp'
os.environ['AGENTEVAL_OTLP_ENDPOINT'] = 'http://first.example:4318/v1/traces'

l1 = listener_mod.Listener()
l1._configure_tracer_provider()
l1._resolve_backend(suite=None)
l1._attach_otlp_exporter_if_needed()
provider = trace.get_tracer_provider()
active = getattr(provider, '_active_span_processor', None)
processors = getattr(active, '_span_processors', ()) if active else ()
print('after first attach', len(processors))
for i,p in enumerate(processors):
    exp = getattr(p, 'span_exporter', None) or getattr(p, 'exporter', None) or getattr(p, '_span_exporter', None)
    print(i, type(p).__name__, type(exp).__name__ if exp else None, getattr(exp, '_endpoint', None) if exp else None)

os.environ['AGENTEVAL_OTLP_ENDPOINT'] = 'http://second.example:4318/v1/traces'
l2 = listener_mod.Listener()
l2._configure_tracer_provider()
l2._resolve_backend(suite=None)
l2._attach_otlp_exporter_if_needed()
provider = trace.get_tracer_provider()
active = getattr(provider, '_active_span_processor', None)
processors = getattr(active, '_span_processors', ()) if active else ()
print('after second attach', len(processors))
for i,p in enumerate(processors):
    exp = getattr(p, 'span_exporter', None) or getattr(p, 'exporter', None) or getattr(p, '_span_exporter', None)
    print(i, type(p).__name__, type(exp).__name__ if exp else None, getattr(exp, '_endpoint', None) if exp else None)
print('listener2 backend exporter endpoint', getattr(l2._backend._exporter, '_endpoint', None))
print('provider sentinel', getattr(provider, '_agenteval_otlp_attached', None))
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'tmp=$(mktemp --suffix=.robot) && cat > "$tmp" <<'"'EOF'
*** Settings ***
Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces

*** Test Cases ***
Smoke
    No Operation
EOF
uv run --extra otlp robot --dryrun \""'$tmp"; status=$?; rm -f "$tmp"; exit $status' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
import os
from AgentEval import AgentEval

os.environ.pop('AGENTEVAL_OTLP_ENDPOINT', None)
a = AgentEval(trace_backend='otlp')
print('no env explicit trace_backend only:', a.get_effective_config_with_provenance()['otlp_endpoint'])
os.environ['AGENTEVAL_OTLP_ENDPOINT'] = 'http://env.example:4318/v1/traces'
b = AgentEval(trace_backend='otlp')
cv = b.get_effective_config_with_provenance()['otlp_endpoint']
print('with env:', cv)
print('value', cv.value, 'source', cv.source)
c = AgentEval(trace_backend='otlp', otlp_endpoint=None)
cv2 = c.get_effective_config_with_provenance()['otlp_endpoint']
print('explicit none:', cv2.value, cv2.source)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 858ms:
after first attach 4
0 TestIdContextSpanProcessor None None
1 RedactionProcessor None None
2 SimpleSpanProcessor InMemorySpanExporter None
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
after second attach 4
0 TestIdContextSpanProcessor None None
1 RedactionProcessor None None
2 SimpleSpanProcessor InMemorySpanExporter None
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
listener2 backend exporter endpoint http://second.example:4318/v1/traces
provider sentinel True

 succeeded in 970ms:
==============================================================================
tmp.YLe4v9fzKa                                                                
==============================================================================
Smoke                                                                 | PASS |
------------------------------------------------------------------------------
tmp.YLe4v9fzKa                                                        | PASS |
1 test, 1 passed, 0 failed
==============================================================================
Output:  /home/many/workspace/robotframework-agenteval/output.xml
Log:     /home/many/workspace/robotframework-agenteval/log.html
Report:  /home/many/workspace/robotframework-agenteval/report.html

 succeeded in 1048ms:
no env explicit trace_backend only: ConfigValue(value=None, source='default')
with env: ConfigValue(value='http://env.example:4318/v1/traces', source='env')
value http://env.example:4318/v1/traces source env
explicit none: None init_arg

codex
The constructor and dry-run probes are clean: HTTP/gRPC dispatch behaves as the story claims, env precedence for `AGENTEVAL_OTLP_ENDPOINT` works, and the recipe snippet is actually dry-run valid. I’m narrowing the review to the remaining correctness edges: process reuse, collector assertions, and any public-surface drift the patch forgot to update.
exec
/bin/bash -lc "grep -RIn \"def get_trace_backend_names\\|Get Trace Backend Names\" src/AgentEval | head -50" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/__init__.py:173:            When False, `Get Trace Backend Names` returns `[]` and no OTLP

exec
/bin/bash -lc "grep -RIn \"telemetry=False\\|_telemetry\\|Get Trace Backend Names\\|trace_backend_names\\|no network egress\" src/AgentEval | head -200" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/__init__.py:46:    agent = AgentEval(allow_validate_operator=True, telemetry=False)
src/AgentEval/__init__.py:173:            When False, `Get Trace Backend Names` returns `[]` and no OTLP
src/AgentEval/__init__.py:272:        self._telemetry = resolved["telemetry"]
src/AgentEval/__init__.py:426:        | Library    AgentEval    max_cost_usd=5.0    telemetry=False
src/AgentEval/__init__.py:449:            "telemetry": self._telemetry,

exec
/bin/bash -lc "nl -ba src/AgentEval/telemetry/library.py | sed -n '1,120p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	# ruff: noqa: E501
    16	# Browser-Library-style docstring tables can carry long descriptions on a
    17	# single physical line. Per-line 120-char limit waived for this file per
    18	# Phase 4 docstring-refresh proposal (2026-05-26).
    19	
    20	"""Telemetry RF-keyword surface (Story 5.4 AC-5.4.5 + Story 5.5 AC-5.5.1).
    21	
    22	Ships the public RF keyword surface for Epic 5:
    23	- `Get Last Warnings` (Story 5.4 / PRD FR62) — structured WarningRecord
    24	  per-test buffer accessor.
    25	- `Get Spans` / `Get Tool Calls` / `Get Run Manifest` (Story 5.5
    26	  AC-5.5.1) — thin keyword wrappers around the `_kernel/trace_store`
    27	  projection accessors so `.robot` consumers (including the rf-mcp
    28	  dogfood suite per Story 5.5 AC-5.5.3) can read trace state without
    29	  dropping into `Evaluate` Python calls.
    30	
    31	Sub-library registration honored via `_SUB_LIBRARIES` in
    32	`AgentEval/__init__.py`. Filename matches the existing sub-library
    33	convention (`hooks/library.py`, `orchestration/library.py`).
    34	"""
    35	
    36	from __future__ import annotations
    37	
    38	from typing import TYPE_CHECKING, Any
    39	
    40	from robot.api.deco import keyword
    41	
    42	from AgentEval._kernel import trace_store
    43	from AgentEval._kernel import warnings as _agenteval_warnings
    44	from AgentEval._kernel.context import current_context
    45	from AgentEval._kernel.tier import tier
    46	
    47	if TYPE_CHECKING:
    48	    from opentelemetry.sdk.trace import ReadableSpan
    49	
    50	    from AgentEval.types import RunManifest, ToolCallTrace
    51	
    52	__all__ = ["TelemetryLibrary"]
    53	
    54	# Browser-Library-style docstring migration marker (Phase 4, 2026-05-26).
    55	_BROWSER_STYLE_MIGRATED = True
    56	
    57	
    58	class TelemetryLibrary:
    59	    """`Get Last Warnings` + `Get Spans` + `Get Tool Calls` + `Get Run Manifest`
    60	    keyword surface (Story 5.4 / PRD FR62 + Story 5.5 / AC-5.5.1)."""
    61	
    62	    @keyword(name="Get Last Warnings")
    63	    @tier(1)
    64	    def get_last_warnings(self, test_id: str = "current") -> list[dict[str, Any]]:
    65	        """Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).
    66	
    67	        [Tier 1 — Deterministic] — returns ``list[dict]``. Each record
    68	        has the FR62 ratified 5-field shape: ``warning_type`` (str —
    69	        fully-qualified Python warning class), ``message`` (str — human-
    70	        readable text), ``source`` (str — emitting subsystem),
    71	        ``timestamp`` (str — UTC RFC 3339), ``remediation`` (str | None
    72	        — actionable advice).
    73	
    74	        | =Arguments= | =Description= |
    75	        | ``test_id`` | ``"current"`` (default) — resolves to the bound test via the listener context; returns ``[]`` if no test is bound. ``"all"`` — union across every per-test buffer in the process, sorted by ``timestamp`` ascending. Any other value is treated as a specific test_id (returns the named buffer or ``[]`` if absent). |
    76	
    77	        Defensive copy of records. Never raises — buffer-read failures
    78	        fall back to ``[]``.
    79	
    80	        Example:
    81	        | @{warnings} =    `Get Last Warnings`
    82	        | Length Should Be    ${warnings}    0                                                   # Clean run: zero warnings.
    83	        | @{all_warnings} =    `Get Last Warnings`    test_id=all
    84	        | FOR    ${w}    IN    @{all_warnings}
    85	        |     Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]
    86	        | END
    87	
    88	        Notes:
    89	        - PRD FR62 ratifies the 5-field ``WarningRecord`` shape.
    90	        - Story 5.4 ratified the per-test buffer + ``"all"`` aggregation contract.
    91	        - Sibling keywords: `Get Spans`, `Get Tool Calls`, `Get Run Manifest` — companion trace-store accessors.
    92	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
    93	        records = _agenteval_warnings.get_warnings(test_id)
    94	        return [_agenteval_warnings.warning_record_to_dict(r) for r in records]
    95	
    96	    @keyword(name="Get Spans")
    97	    @tier(1)
    98	    def get_spans(self, test_id: str = "current") -> list[ReadableSpan]:
    99	        """Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).
   100	
   101	        [Tier 1 — Deterministic] — returns ``list[ReadableSpan]`` in
   102	        chronological order by ``start_time``. Empty list is a valid
   103	        state (test ran without emitting spans). Thin keyword wrapper
   104	        around the ``_kernel/trace_store.get_run_spans`` projection
   105	        accessor.
   106	
   107	        | =Arguments= | =Description= |
   108	        | ``test_id`` | ``"current"`` (default) — resolves to the bound test; returns ``[]`` if no test is bound. Any other value is forwarded to the projection accessor verbatim. |
   109	
   110	        Example:
   111	        | @{spans} =    `Get Spans`
   112	        | Should Not Be Empty    ${spans}
   113	        | FOR    ${span}    IN    @{spans}
   114	        |     ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}
   115	        |     Log    ${span.name} took ${duration_ns} ns
   116	        | END
   117	        | @{spans_specific} =    `Get Spans`    test_id=My Suite.Specific Test
   118	
   119	        Notes:
   120	        - Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.

exec
/bin/bash -lc 'grep -RIn "otlp_endpoint" docs/keywords docs/contracts/stability-surface.md docs/recipes/08-ci-integration.md | head -50' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
docs/contracts/stability-surface.md:130:- `AgentEval.__init__(otlp_endpoint=...)` 10th parameter — `provisional` label. Default `None` falls back to `http://localhost:4318/v1/traces`. URL-scheme dispatch is `stable`; the gRPC scheme stripping (`grpc://host:port` → `host:port` + `insecure=True`; `grpcs://host:port` → `host:port` + `insecure=False`) is `provisional` (Phase-2.5 may add an explicit `headers=` / `credentials=` kwarg per DF-13.2-S2 / C87).
docs/recipes/08-ci-integration.md:129:Library    AgentEval    trace_backend=otlp    otlp_endpoint=http://localhost:4318/v1/traces
docs/recipes/08-ci-integration.md:136:Library    AgentEval    trace_backend=otlp    otlp_endpoint=grpc://tempo-distributor.observability.svc.cluster.local:4317
docs/recipes/08-ci-integration.md:154:- Default (`otlp_endpoint` unset): `http://localhost:4318/v1/traces`.

exec
/bin/bash -lc 'grep -RIn "otlp" tests/unit/telemetry | head -200' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
tests/unit/telemetry/test_backends_otlp.py:25:ImportError-gate tests live in the companion `test_backends_otlp_extras_gate.py`
tests/unit/telemetry/test_backends_otlp.py:37:# Phase-2 modules require opentelemetry-exporter-otlp. Skip the happy-path
tests/unit/telemetry/test_backends_otlp.py:39:pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
tests/unit/telemetry/test_backends_otlp.py:40:pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc")
tests/unit/telemetry/test_backends_otlp.py:42:from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: E402
tests/unit/telemetry/test_backends_otlp.py:45:from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E402
tests/unit/telemetry/test_backends_otlp.py:61:def test_otlp_backend_name_is_otlp() -> None:
tests/unit/telemetry/test_backends_otlp.py:62:    """OTLPBackend.name == 'otlp' (symmetric with MemoryBackend / JSONLBackend)."""
tests/unit/telemetry/test_backends_otlp.py:63:    assert OTLPBackend.name == "otlp"
tests/unit/telemetry/test_backends_otlp.py:66:def test_otlp_backend_docstring_carries_anchors() -> None:
tests/unit/telemetry/test_backends_otlp.py:85:def test_otlp_backend_default_endpoint_is_local_http_jaeger() -> None:
tests/unit/telemetry/test_backends_otlp.py:93:def test_otlp_backend_explicit_http_endpoint_constructs_http_exporter() -> None:
tests/unit/telemetry/test_backends_otlp.py:101:def test_otlp_backend_explicit_https_endpoint_constructs_http_exporter() -> None:
tests/unit/telemetry/test_backends_otlp.py:114:def test_otlp_backend_grpc_scheme_constructs_grpc_exporter_insecure() -> None:
tests/unit/telemetry/test_backends_otlp.py:122:def test_otlp_backend_grpcs_scheme_constructs_grpc_exporter_secure() -> None:
tests/unit/telemetry/test_backends_otlp.py:130:def test_otlp_backend_grpc_scheme_is_case_insensitive() -> None:
tests/unit/telemetry/test_backends_otlp.py:142:def test_otlp_backend_rejects_unknown_scheme_with_value_error() -> None:
tests/unit/telemetry/test_backends_otlp.py:150:def test_otlp_backend_rejects_empty_string_endpoint_with_value_error() -> None:
tests/unit/telemetry/test_backends_otlp.py:156:def test_otlp_backend_rejects_no_scheme_endpoint_with_value_error() -> None:
tests/unit/telemetry/test_backends_otlp.py:167:def test_otlp_backend_flush_test_is_noop_and_does_not_export(tmp_path: Path) -> None:
tests/unit/telemetry/test_backends_otlp.py:188:def test_otlp_backend_is_distinct_class_from_memory_and_jsonl_backends() -> None:
tests/unit/telemetry/test_backends_otlp_extras_gate.py:15:"""ImportError-gate tests for the Phase-2 `[otlp]` extra (Story 13.2 L-2 lesson).
tests/unit/telemetry/test_backends_otlp_extras_gate.py:25:the verbatim `[otlp]` extra message; (c) `_resolve_backend` graceful-degrades
tests/unit/telemetry/test_backends_otlp_extras_gate.py:38:def test_backends_module_importable_without_otlp_extra() -> None:
tests/unit/telemetry/test_backends_otlp_extras_gate.py:50:    assert OTLPBackend.name == "otlp"
tests/unit/telemetry/test_backends_otlp_extras_gate.py:53:def test_raise_otlp_extra_missing_helper_carries_canonical_message() -> None:
tests/unit/telemetry/test_backends_otlp_extras_gate.py:54:    """`_raise_otlp_extra_missing` produces the spec-mandated ImportError text.
tests/unit/telemetry/test_backends_otlp_extras_gate.py:57:    `uv pip install robotframework-agenteval[otlp]` verbatim so the
tests/unit/telemetry/test_backends_otlp_extras_gate.py:58:    operator's `[otlp]` install hint is grep-discoverable in the trace.
tests/unit/telemetry/test_backends_otlp_extras_gate.py:60:    from AgentEval.telemetry.backends import _raise_otlp_extra_missing
tests/unit/telemetry/test_backends_otlp_extras_gate.py:63:        _raise_otlp_extra_missing()
tests/unit/telemetry/test_backends_otlp_extras_gate.py:66:    assert "opentelemetry-exporter-otlp" in msg
tests/unit/telemetry/test_backends_otlp_extras_gate.py:67:    assert "uv pip install robotframework-agenteval[otlp]" in msg
tests/unit/telemetry/test_backends_otlp_extras_gate.py:70:def test_otlp_backend_raises_import_error_when_extra_unavailable(
tests/unit/telemetry/test_backends_otlp_extras_gate.py:85:    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
tests/unit/telemetry/test_backends_otlp_extras_gate.py:87:    with pytest.raises(ImportError, match="opentelemetry-exporter-otlp"):
tests/unit/telemetry/test_backends_otlp_extras_gate.py:92:def test_resolve_backend_falls_back_with_warning_when_otlp_unavailable(
tests/unit/telemetry/test_backends_otlp_extras_gate.py:97:    Per AC-13.2.7 (4th extras-gate test): with `trace_backend="otlp"` +
tests/unit/telemetry/test_backends_otlp_extras_gate.py:107:    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "otlp")
tests/unit/telemetry/test_backends_otlp_extras_gate.py:121:    assert any("otlp" in str(w.message).lower() for w in degraded)
tests/unit/telemetry/test_backends_otlp_extras_gate.py:122:    assert any("uv pip install robotframework-agenteval[otlp]" in str(w.message) for w in degraded)

exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
import os
from opentelemetry import trace
from AgentEval.telemetry import listener as listener_mod

# ensure clean-ish process by using current provider only
os.environ['AGENTEVAL_TRACE_BACKEND']='memory'
listener = listener_mod.Listener()
listener._configure_tracer_provider()
provider = trace.get_tracer_provider()
active = getattr(provider, '_active_span_processor', None)
processors = getattr(active, '_span_processors', ()) if active else ()
print('processors', [type(p).__name__ for p in processors])
print('otlp exporters in chain', [getattr((getattr(p, '_span_exporter', None) or getattr(p, 'span_exporter', None) or getattr(p, 'exporter', None)), '_endpoint', None) for p in processors if 'SpanProcessor' in type(p).__name__])
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'uv run --extra otlp pytest tests/unit/telemetry/test_backends_otlp.py tests/unit/telemetry/test_backends_otlp_extras_gate.py -q' in /home/many/workspace/robotframework-agenteval
 succeeded in 782ms:
processors ['TestIdContextSpanProcessor', 'RedactionProcessor', 'SimpleSpanProcessor']
otlp exporters in chain [None, None]

 succeeded in 1567ms:
.................                                                        [100%]
17 passed in 0.67s

codex
I’ve verified the default `memory` path does not attach any OTLP exporter at all. One more pass is running across the new OTLP unit tests to see whether the test suite itself catches the process-reuse endpoint bug.
exec
/bin/bash -lc 'grep -RIn "Get Trace Backend Names" src docs tests | head -100' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/__init__.py:173:            When False, `Get Trace Backend Names` returns `[]` and no OTLP
docs/keywords/AgentEval.html:9:libdoc = {"specversion": 3, "name": "AgentEval", "doc": "<p>Robot Framework library for evaluating AI coding agents.</p>\n<p>Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point + the FR41 precedence chain (kwarg \u2192 env-var \u2192 <span class=\"name\">.env</span> \u2192 defaults) via <span class=\"name\">_kernel.context.resolve_config</span> (Story 1b.1). <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> returns the precedence-resolved values.</p>\n<p>Args: provider: Provider plugin name resolved via <span class=\"name\">agenteval.providers</span> entry-points (FR42; ADR-013). Phase 1 ships only the <span class=\"name\">litellm</span> provider; future providers register via <span class=\"name\">[project.entry-points.\"agenteval.providers\"]</span>. telemetry: Enable the OTel listener for trace recording (FR42 + FR44). When False, <span class=\"name\">Get Trace Backend Names</span> returns <span class=\"name\">[]</span> and no OTLP egress occurs (Phase 2). Phase 1 wires the parameter; full listener-disable enforcement lands in Epic 5 Story 5.1. trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports <span class=\"name\">\"memory\"</span> and <span class=\"name\">\"jsonl\"</span>; <span class=\"name\">\"otlp\"</span> is Phase 2. allow_validate_operator: Enable the AssertionEngine <span class=\"name\">validate</span> operator which uses <span class=\"name\">eval()</span> (FR42 + FR43; NFR-SEC-02). Default False \u2014 the safer posture per NFR-SEC-02. Gate enforcement (raising <span class=\"name\">ValidateOperatorDisallowed</span>) lands in Epic 6. default_temperature: Default provider temperature for non-stochastic keywords (FR42). 0.0 enforces deterministic provider calls where the underlying model supports it. mcp_per_test: MCP server scope.</p>\n<ul>\n<li>True (default): per-test isolation; correct under <span class=\"name\">pabot --processes N</span>. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>False: single shared instance across all tests; only correct serial. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>\"suite\": per-suite scope; recipe-5 dogfood-CI ergonomics override. (Architecture L314 + NFR-PERF-03d \u2014 not in ADR-009 proper.) allow_external_mcp_blind: Opt-in to running with <span class=\"name\">mcp_coverage=\"external_mixed\"</span> without <span class=\"name\">IncompleteTraceError</span> (FR42 + ADR-016 D4 adapter contract). Default False enforces loud-refusal posture from ADR-016. max_cost_usd: Cost budget for <span class=\"name\">@guarded_fanout</span>-decorated Tier-3 keywords (FR42 + ADR-015). USD per fan-out invocation. Default 5.00. max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords (FR11b + ADR-015). Default None = no cap (opt-in via explicit value). Sibling to <span class=\"name\">max_cost_usd</span>; catches slow MCP-server startup compounded across trials.</li>\n</ul>\n<p>FR41 precedence behavior (Story 1b.1): Each <span class=\"name\">__init__</span> parameter defaults to a private sentinel; if the caller does NOT pass it, the value falls through to <span class=\"name\">AGENTEVAL_*</span> env-vars, then to a <span class=\"name\">.env</span> file in cwd, then to the FR42 + FR11b defaults documented in this docstring. Callers who want to force a value explicitly (even when an env-var is set) pass that value as a kwarg. <span class=\"name\">.env.example</span> documents the canonical <span class=\"name\">AGENTEVAL_*</span> env-var names.</p>\n<p>References:</p>\n<ul>\n<li>PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)</li>\n<li>PRD FR11b (max_runtime_seconds keyword arg sibling)</li>\n<li>PRD FR41 (config precedence)</li>\n<li>ADR-009 (mcp_per_test 3-mode)</li>\n<li>ADR-013 (entry-points discovery for <span class=\"name\">provider</span>)</li>\n<li>ADR-015 (@guarded_fanout for cost + runtime guardrails)</li>\n<li>ADR-016 (mcp_coverage detection + allow_external_mcp_blind)</li>\n<li>docs/contracts/stability-surface.md (Phase-1 stability labels for this class)</li>\n</ul>", "version": "", "generated": "2026-05-27T19:45:45+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 159, "tags": ["agenteval"], "inits": [{"name": "__init__", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "provider", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "provider: str = _UNSET"}, {"name": "telemetry", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "telemetry: bool = _UNSET"}, {"name": "trace_backend", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "trace_backend: str = _UNSET"}, {"name": "allow_validate_operator", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_validate_operator: bool = _UNSET"}, {"name": "default_temperature", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "default_temperature: float = _UNSET"}, {"name": "mcp_per_test", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'suite'", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "mcp_per_test: bool | Literal['suite'] = _UNSET"}, {"name": "allow_external_mcp_blind", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_external_mcp_blind: bool = _UNSET"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_cost_usd: float = _UNSET"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize self.  See help(type(self)) for accurate signature.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 225}], "keywords": [{"name": "Agent Response Should Contain", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "substring", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "substring: str"}], "returnType": null, "doc": "<p>Asserts that <code>substring</code> appears in <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>substring</code></td>\n<td>Literal substring to match. Case-sensitive.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the substring is not found.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    Robot Framework                                          # Mock echoes the prompt.\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    test automation\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 236}, {"name": "Agent Response Should Match Regex", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "pattern", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "pattern: str"}], "returnType": null, "doc": "<p>Asserts a regex pattern matches <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 uses <code>re.search</code> (substring-match by default per FR25's \"match\" terminology). Multi-line text supported via standard <code>re</code> flags in the pattern. NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>pattern</code></td>\n<td>Python <code>re</code> pattern. Use <code>(?i)</code> / <code>(?m)</code> / <code>(?s)</code> inline flags as needed.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the pattern does not match.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Released in 2020 \u2014 Robot Framework 3.x    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    20\\d{2}                          # 4-digit year \u2014 matches the echoed \"2020\".\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the regex assertion; <span class=\"name\">re.search</span> semantics (not <span class=\"name\">re.fullmatch</span>).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts a regex pattern matches ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 268}, {"name": "Agent Response Should Match Schema", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "schema", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "schema: dict[str, Any] | str | Path"}], "returnType": null, "doc": "<p>Asserts <code>response_text</code> parses as JSON + validates against a JSON Schema (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <code>mcp_coverage<span class=\"name\">`-gated. Parses </span>`response_text</code> as JSON, then validates against the schema via <code>jsonschema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code> (expected to be JSON-parsable).</td>\n</tr>\n<tr>\n<td><code>schema</code></td>\n<td>JSON Schema as a <code>dict</code> OR a file path (<code>str</code> / <code>pathlib.Path</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>schema</code> is not a <code>dict<span class=\"name\">`/</span><span class=\"name\">str</span><span class=\"name\">/</span>`Path</code>, or when the file is not a valid JSON schema dict. Raises <code>AssertionError</code> (redacted per FR38a) when <code>response_text</code> is not JSON-parsable. Raises <code>jsonschema.ValidationError</code> when the parsed JSON does not validate against the schema (preserves the jsonschema convention so consumers can catch the specific exception).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt={\"answer\": 42}    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${{ {\"type\": \"object\", \"required\": [\"answer\"]} }}\n# Path form: <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.</li>\n<li>Uses <code>jsonschema</code> package \u2014 the upstream <code>ValidationError</code> is preserved on validation failure (callers can catch specifically).</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex pattern).</li>\n</ul>", "shortdoc": "Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 301}, {"name": "Get Cohort Heatmap", "args": [{"name": "discoverability_result", "type": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "discoverability_result: DiscoverabilityResult"}, {"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "model_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "default", "kind": "NAMED_ONLY", "required": false, "repr": "model_name: str = default"}], "returnType": {"name": "CohortHeatmap", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds a <code>CohortHeatmap</code> from a <code>DiscoverabilityResult</code> (Story 8b.2 / FR55).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection over the result's <code>per_task_results</code>; no LLM calls. Returns a <code>CohortHeatmap</code> instance with <code>.as_ascii()</code> (box-drawing rendered grid) + <code>.as_dict()</code> (nested <code>{task: {model: pass_at_k}}</code> mapping) methods.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>discoverability_result</code></td>\n<td>Result from <span class=\"name\">MCP.Get Tool Discoverability</span> (Story 4.4 / FR10a). Carries <code>per_task_results</code> list of per-task <code>pass_rate</code> values.</td>\n</tr>\n<tr>\n<td><code>model_name</code></td>\n<td>Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to <code>\"default\"</code>.</td>\n</tr>\n</table>\n<p>Phase-1 scope: single-model heatmap (one column). Multi-model comparison (rows = tasks \u00d7 columns = models) is Phase-2 work. Missing cells render as <code>\" \u2014 \"</code> sentinel (em-dash with spaces) rather than silently substituting <code>0.0</code> per the Story 10.1 kilo/minimax review HIGH-1 honesty patch.</p>\n<p>Example:</p>\n<pre>\n${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()\n${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()\n${heatmap} =    <a href=\"#Get%20Cohort%20Heatmap\" class=\"name\">Get Cohort Heatmap</a>    ${disc}    model_name=claude-sonnet-4-5\n${ascii} =    Evaluate    $heatmap.as_ascii()\nLog    ${ascii}                                                                           # Box-drawing render.\n${cells} =    Evaluate    $heatmap.as_dict()\nShould Not Be Empty    ${cells}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 8b.2 ratifies the <code>CohortHeatmap</code> data class + <code>Get Cohort Heatmap</code> keyword surface.</li>\n<li>FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> produces the <code>DiscoverabilityResult</code> input.</li>\n</ul>", "shortdoc": "Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_heatmap/library.py", "lineno": 49}, {"name": "Get Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a Claude Code <code>settings.json</code> hook configuration.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per-entry validation per PRD FR4. Returns a dict mapping <code>hooks.&lt;event&gt;</code> \u2192 list of validated hook entries. Covered events: <code>PreToolUse</code>, <code>PostToolUse</code>, <code>Stop</code>; other events are passed through with the same validation. Median \u2264 50 ms on typical hook configs per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>settings.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Each returned entry has <code>command</code> (required) plus any of the optional fields <code>args</code> / <code>timeout</code> / <code>matcher</code> that were present in the source JSON. Entries whose command contains an inline YAML frontmatter block additionally surface an <code>inline_skill: dict</code> field with the parsed frontmatter.</p>\n<p>Raises <code>InvalidHookConfigError</code> on any structural failure (file not found, malformed JSON, missing <code>command</code>, wrong-type optional field). The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer (e.g. <code>/hooks/PreToolUse/0/command</code>) pinpointing the nested location. Format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>This keyword is re-exported through the top-level <code>AgentEval</code> library, so <code>AgentEval.Get Config</code> and <code>Hook.Get Config</code> (when imported as <code>WITH NAME    Hook</code>) resolve to the same implementation.</p>\n<p>Example:</p>\n<pre>\n${config} =    <a href=\"#Get%20Config\" class=\"name\">Get Config</a>    ${CURDIR}/.claude/settings.json\nLength Should Be    ${config}[hooks.PreToolUse]    1\nShould Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook\nShould Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop). Unknown events are validated with the same shape contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format: FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104. The <code>field_name</code> attribute on raised errors carries an RFC 6901 JSON Pointer.</li>\n<li>Inline-skill-frontmatter hooks are an extension surface \u2014 the inner skill is reachable via <span class=\"name\">SkillsLibrary</span> keywords passed the <code>inline_skill</code> dict directly.</li>\n</ul>", "shortdoc": "Parses a Claude Code ``settings.json`` hook configuration.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/hooks/library.py", "lineno": 66}, {"name": "Get Cost Total", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns total provider-reported USD cost (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (USD). Single run: the run's <code>cost_usd</code>. Multi-trial: sum across trials. Empty list \u2192 <code>0.0</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <code>mcp_coverage<span class=\"name\">`-gated. Returns </span>`0.0</code> on the Mock provider; non-zero on real adapters per Story 8a.1 (real adapters use <code>total_cost_usd</code> not <code>cost_usd</code>).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${cost_usd} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${result}\nShould Be True    ${cost_usd} &lt; 0.10                                      # Single-shot cost cap $0.10.\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${total_cost} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${results}                         # Cohort cost rollup.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the cost metric.</li>\n<li>Mock-provider runs return <code>0.0</code> cost; real adapters surface the provider's reported cost.</li>\n<li>Story 8a.1 v1 HIGH-1 ratified <code>total_cost_usd</code> as the canonical real-adapter key.</li>\n<li>Sibling keywords: <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns total provider-reported USD cost (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 419}, {"name": "Get Effective Config", "args": [{"name": "setting", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "setting: str | None = None"}], "returnType": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "doc": "<p>Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 two-form return: no-arg \u2192 <code>dict[str, Any]</code> of resolved values (Story 1a.6 ratified shape, backwards-compat with tier-1 + smoke tests); <code>setting=&lt;key&gt;</code> \u2192 <code>ConfigValue(value, source)</code> for that single setting (FR41 L1563). <code>source</code> is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>setting</code></td>\n<td>Optional config-key name (e.g., <code>\"max_cost_usd\"</code>). When <code>None</code> (default), returns the full <code>dict[str, Any]</code>. When set, returns the single <code>ConfigValue</code> for that key.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>setting</code> is set but not a known config key (with a sorted list of known keys in the message).</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0    telemetry=False\n${config} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>\nShould Be Equal As Numbers    ${config}[max_cost_usd]    5.0\nShould Be Equal    ${config}[telemetry]    ${FALSE}\n${cost_setting} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>    setting=max_cost_usd\nShould Be Equal As Numbers    ${cost_setting.value}    5.0\nShould Be Equal    ${cost_setting.source}    init_arg\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the ConfigValue surface; FR42 ratifies the 9 settings.</li>\n<li>Story 4.3 DF-4.3-S1 carry-over: full <code>dict[str, ConfigValue]</code> migration of the no-arg form is Phase-1.5.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a> for the FR41-compliant full-surface form.</li>\n</ul>", "shortdoc": "Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 398}, {"name": "Get Effective Config With Provenance", "args": [], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "ConfigValue", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the full settings map with per-key provenance as a <code>dict[str, ConfigValue]</code> (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 FR41-compliant surface. Each <code>ConfigValue</code> carries <code>value</code> + <code>source</code> per FR41 L1563. Source is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td>(none)</td>\n<td>Returns the full settings map; no arguments.</td>\n</tr>\n</table>\n<p>Defensive shallow-copy of the underlying provenance dict \u2014 caller mutations don't propagate to the Library's internal state.</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0\n${settings} =    <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a>\n${cost} =    Set Variable    ${settings}[max_cost_usd]\nShould Be Equal As Numbers    ${cost.value}    5.0\nShould Be Equal    ${cost.source}    init_arg                              # Constructor kwarg won.\n${temp} =    Set Variable    ${settings}[default_temperature]\nShould Be Equal    ${temp.source}    default                               # Not overridden \u2014 uses FR42 default.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the <code>dict[str, ConfigValue]</code> shape.</li>\n<li>This is the FR41-compliant surface DF-4.3-S1 will migrate <code>Get Effective Config</code> (no-arg) to once tier-1 tests update.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> for the simpler <code>dict[str, Any]</code> or per-setting form.</li>\n</ul>", "shortdoc": "Returns the full settings map with per-key provenance as a ``dict[str, ConfigValue]`` (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 517}, {"name": "Get Keyword Tier", "args": [{"name": "keyword", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the determinism-tier annotation for an RF keyword (PRD FR30a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int \u2208 {1, 2, 3}</code>. Walks the composed DynamicCore keyword registry + top-level methods to resolve the verbatim RF name to its <code>_agenteval_tier</code> integer via the <code>@tier(N)</code> decorator chain.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>Verbatim RF keyword name (e.g., <code>\"Send Prompt\"</code>, <code>\"Stat.Run N Times\"</code>, <code>\"Get Effective Config\"</code>).</td>\n</tr>\n</table>\n<p>Returns the wrapper's own tier, not the wrapped keyword's tier \u2014 e.g., <code>Stat.Run N Times</code> returns <code>3</code> (fan-out runner tier) per epic AC-5 + Story 6.3 D-14 amendment. The runner's tier governs the <code>@guarded_fanout</code> enforcement model, independent of the wrapped keyword's own classification.</p>\n<p>Raises <code>ValueError</code> when the keyword is not found in the composed library (with a sorted list of known keywords in the message), OR when the keyword has no <code>@tier(N)</code> annotation, OR when the annotated tier is outside <code>{1, 2, 3}</code> (defensive range check per Story 6.3 code-review HIGH-\u03c0 fix).</p>\n<p>Example:</p>\n<pre>\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Get Tool Call Count\nShould Be Equal As Integers    ${tier}    1                                # Tier-1 deterministic metric.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Send Prompt\nShould Be Equal As Integers    ${tier}    2                                # Tier-2 stochastic single-shot.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Stat.Run N Times\nShould Be Equal As Integers    ${tier}    3                                # Tier-3 fan-out runner.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR30a ratifies the tier-introspection contract; AC-6.3.7 establishes the DynamicCore walk.</li>\n<li>Story 6.3 D-14 amendment: fan-out runner reports its own tier (3), not the wrapped keyword's tier.</li>\n<li>Sibling keywords: every <span class=\"name\">@tier</span>-decorated keyword in the composed library is introspectable here.</li>\n</ul>", "shortdoc": "Returns the determinism-tier annotation for an RF keyword (PRD FR30a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 450}, {"name": "Get Last Warnings", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[dict]</code>. Each record has the FR62 ratified 5-field shape: <code>warning_type</code> (str \u2014 fully-qualified Python warning class), <code>message</code> (str \u2014 human- readable text), <code>source</code> (str \u2014 emitting subsystem), <code>timestamp</code> (str \u2014 UTC RFC 3339), <code>remediation</code> (str | None \u2014 actionable advice).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test via the listener context; returns <code>[]</code> if no test is bound. <code>\"all\"</code> \u2014 union across every per-test buffer in the process, sorted by <code>timestamp</code> ascending. Any other value is treated as a specific test_id (returns the named buffer or <code>[]</code> if absent).</td>\n</tr>\n</table>\n<p>Defensive copy of records. Never raises \u2014 buffer-read failures fall back to <code>[]</code>.</p>\n<p>Example:</p>\n<pre>\n@{warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>\nLength Should Be    ${warnings}    0                                                   # Clean run: zero warnings.\n@{all_warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>    test_id=all\nFOR    ${w}    IN    @{all_warnings}\n    Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR62 ratifies the 5-field <code>WarningRecord</code> shape.</li>\n<li>Story 5.4 ratified the per-test buffer + <code>\"all\"</code> aggregation contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> \u2014 companion trace-store accessors.</li>\n</ul>", "shortdoc": "Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 64}, {"name": "Get Latency", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns mean turn-level latency in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). When the run has no <code>tool_calls</code>, falls back to <code>result.latency_seconds * 1000.0</code>. Multi-trial: union-of- tool-calls mean \u2014 all per-tool-call latencies from all trials are flattened into one list before <code>statistics.mean()</code> is taken. Mean-of-per-run-means is a statistical anti-pattern (under-weights runs with more tool calls); union-then-mean is the operator-intuitive default per Story 6.1 code-review.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${latency_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${result}\nShould Be True    ${latency_ms} &lt; 2000                                    # Mean turn latency under 2 seconds.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the latency metric \u2014 per-tool-call resolution preferred over per-run.</li>\n<li>Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).</li>\n<li>Sibling keyword: <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a> for tail-latency tracking.</li>\n<li>Provider-reported scalar \u2014 observer-independent per AC-6.1.1.</li>\n</ul>", "shortdoc": "Returns mean turn-level latency in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 355}, {"name": "Get Latency P95", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the P95 latency across tool calls in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). AC-6.1.8 boundary conditions: 0 tool_calls \u2192 <code>0.0</code>; 1 tool_call \u2192 that single latency; \u22652 \u2192 <code>statistics.quantiles(n=100)[94]</code>. Multi-trial: P95 across the union of all tool_calls' latencies.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${p95_ms} =    <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>    ${results}\n${mean_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${results}\nShould Be True    ${p95_ms} &gt;= ${mean_ms}                                 # P95 \u2265 mean by definition.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the P95 metric \u2014 tail-latency tracking complements <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> mean.</li>\n<li>AC-6.1.8 boundary conditions cover empty / single-call edge cases.</li>\n<li>Sibling keywords: <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> for mean; <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> to generate multi-trial input.</li>\n</ul>", "shortdoc": "Returns the P95 latency across tool calls in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 389}, {"name": "Get Run Manifest", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "Union", "typedoc": null, "nested": [{"name": "RunManifest", "typedoc": null, "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "doc": "<p>Returns the in-memory 7-field <code>RunManifest</code> for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>RunManifest | None</code>. <code>None</code> when <code>test_id=\"current\"</code> and no test is bound (Tier-1 sibling-consistency with <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> / <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> / <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a> non-raising contracts). The in-memory manifest is the <b>*ratified 7-field shape*</b> (<code>library_version</code>, <code>test_id</code>, <code>suite_id</code>, <code>redaction_policy_hash</code>, <code>started_at</code>, <code>ended_at</code>, <code>agenteval_tier_breakdown</code>) \u2014 NOT the Story-5.3-extended operational metadata dict (which lives in the JSON sidecar at <code>&lt;output_dir&gt;/agenteval/manifest__&lt;suite&gt;__&lt;test&gt;.json</code>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>None</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim \u2014 that accessor's <code>ValueError</code> propagates if the explicit id resolves to None per Story 1b.2 semantics.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n${manifest} =    <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>\nShould Not Be Equal    ${manifest}    ${NONE}\nShould Not Be Empty    ${manifest.library_version}\nLength Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li>7-field shape ratified at Story 1b.2 per FR39.</li>\n<li>Story 5.5 code-review 2-way HIGH-F established the <code>None</code> (not raise) contract on no-bound-test current path.</li>\n<li>For the Story-5.3-extended operational shape, read the JSON sidecar directly.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 178}, {"name": "Get Spans", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ReadableSpan", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ReadableSpan]</code> in chronological order by <code>start_time</code>. Empty list is a valid state (test ran without emitting spans). Thin keyword wrapper around the <code>_kernel/trace_store.get_run_spans</code> projection accessor.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n@{spans} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>\nShould Not Be Empty    ${spans}\nFOR    ${span}    IN    @{spans}\n    ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}\n    Log    ${span.name} took ${duration_ns} ns\nEND\n@{spans_specific} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>    test_id=My Suite.Specific Test\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.</li>\n<li>Story 5.5 code-review 3-way HIGH-A established the no-bound-test \u2192 <code>[]</code> non-raising contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> (projection over execute_tool spans); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> (resource-attribute projection); <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 98}, {"name": "Get Token Usage", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "Usage", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Returns the agent's token usage as a <code>Usage</code> dataclass (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>Usage(input_tokens, output_tokens, cached_input_tokens)</code>. Single run: the run's own usage. Multi-trial: sum per field. Empty list \u2192 <code>Usage(0, 0, 0)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 observer-independent. NOT <span class=\"name\">`mcp_coverage</span>`-gated (PRD FR22 + AC-6.1.1).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${usage} =    <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>    ${result}\nShould Be True    ${usage.input_tokens} &gt; 0\nShould Be True    ${usage.output_tokens} &gt; 0\nLog    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the four usage metrics \u2014 <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>, <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a> \u2014 all observer-independent per AC-6.1.1.</li>\n<li><code>Usage</code> is a frozen dataclass; field validation ensures non-negative counts.</li>\n<li>Sibling keywords: <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 324}, {"name": "Get Tool Call Count", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the number of tool calls made by the agent (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int</code>. Single run: <code>len(result.tool_calls)</code>. Multi-trial: sum across trials.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial sum aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code> (default-deny per FR42).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${count} =    <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a>    ${result}\nShould Be Equal As Integers    ${count}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42 \u2014 opt out via <code>AgentEval(allow_external_mcp_blind=True)</code>.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a> for the ordered names list.</li>\n</ul>", "shortdoc": "Returns the number of tool calls made by the agent (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 92}, {"name": "Get Tool Call Names", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns tool-call names in chronological order (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 duplicates preserved per FR19 verbatim (\"list[str] (preserving order)\"). Single run: chronological list. Multi-trial: union preserving order-of-first-appearance.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial union aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n@{names} =    <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a>    ${result}\nShould Contain    ${names}    web_search\nShould Be Equal    ${names}[0]    web_search                              # First tool called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> for the count; <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> for expected-set comparison.</li>\n</ul>", "shortdoc": "Returns tool-call names in chronological order (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 132}, {"name": "Get Tool Calls", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ToolCallTrace", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns <code>ToolCallTrace</code> records projected from the trace store (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ToolCallTrace]</code>. Thin keyword wrapper around <code>_kernel/trace_store.get_tool_calls</code>. Mirrors the source-filtering semantics of the Story 1b.2 accessor (no per-call source filter exposed at the RF surface; consumers filter the returned list themselves).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Returns <code>list[ToolCallTrace]</code> frozen dataclasses (Story 1b.2 shape): each record carries <code>name</code>, <code>args</code>, <code>result</code>, <code>error</code>, <code>latency_ms</code>, <code>source</code>, <code>gen_ai_tool_call_id</code>, <code>sequence_index</code>.</p>\n<p>Example:</p>\n<pre>\n@{tool_calls} =    <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>\nShould Not Be Empty    ${tool_calls}\nShould Be Equal    ${tool_calls}[0].name    web_search\nShould Be Equal As Integers    ${tool_calls}[0].sequence_index    0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li><span class=\"name\">ToolCallTrace</span> shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> (full span list); <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> (metrics-library count over <span class=\"name\">AgentRunResult</span>); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>.</li>\n</ul>", "shortdoc": "Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 139}, {"name": "Get Tool Hit Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-hit rate <code>|expected \u2229 observed| / |expected|</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Empty <code>expected_tools</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: union-of-observed against expected_tools.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${hit_rate} =    <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a>    ${result}    ${{['web_search', 'fetch']}}\nShould Be True    ${hit_rate} &gt;= 0.5                                      # At least half of expected tools were called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keywords: <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a> (calls NOT in expected set); <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a> (errors / total).</li>\n</ul>", "shortdoc": "Returns the tool-hit rate ``|expected \u2229 observed| / |expected|`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 178}, {"name": "Get Tool Success Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-success rate <code>non-error / total</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: aggregate across all per-trial tool calls.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${success_rate} =    <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a>    ${result}\nShould Be True    ${success_rate} &gt;= 0.8                                  # At least 80% of tool calls succeeded.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Each <code>ToolCallTrace</code> has an <code>error</code> field \u2014 non-None counts as a failure.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (vs expected set); <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>.</li>\n</ul>", "shortdoc": "Returns the tool-success rate ``non-error / total`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 224}, {"name": "Get Unnecessary Call Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the unnecessary-call rate <code>not_in_expected / total</code> (PRD FR21).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${noise} =    <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>    ${result}    ${{['web_search']}}\nShould Be True    ${noise} &lt;= 0.2                                         # At most 20% of calls were off-task.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR21 ratifies the unnecessary-rate formula \u2014 quantifies \"noise\" tool calls beyond the expected set.</li>\n<li>AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls \u2192 0.0).</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (calls that ARE in expected set).</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n</ul>", "shortdoc": "Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 271}, {"name": "Judge.Calibrate Rubric", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "calibration_set", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "calibration_set: str | Path"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "CalibrationReport", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs the judge against a labeled calibration set and returns a <span class=\"name\">CalibrationReport</span> (Story 12.2).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 N single-shot LLM calls (one per calibration row) against the configured <code>judge_adapter</code>. Cohen's kappa over binarized judge-pass / human-pass labels at the rubric's threshold; <code>passes_hard_fail</code> is True iff <code>kappa &gt;= 0.7</code> per <span class=\"name\">architecture.md</span> L199 agentguard-borrowed calibration discipline. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>calibration_set</code></td>\n<td>Path to a YAML calibration set with <span class=\"name\">rows:</span> list of <span class=\"name\">{prompt, response, human_label}</span>.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug; defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier; forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Returns <code>CalibrationReport</code> with: <code>cohen_kappa</code> (float; <code>nan</code> if zero-variance), <code>passes_hard_fail</code> (kappa &gt;= 0.7), <code>threshold_tuning</code> (precision/recall/F1 sweep), <code>recommended_threshold</code> (F1-maximizing), <code>systematic_bias_diagnostics</code> (human-readable bullets), <code>total_cost_usd</code>, <code>total_latency_seconds</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>InvalidCalibrationSetError</code> on calibration set parse failure. Raises <code>JudgeOutputParseError</code> if any per-row judge invocation returns malformed JSON.</p>\n<p>Example:</p>\n<pre>\n${report} =    <a href=\"#Judge.Calibrate%20Rubric\" class=\"name\">Judge.Calibrate Rubric</a>    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${report.passes_hard_fail}\nLog    Cohen's kappa = ${report.cohen_kappa}\nLog    Recommended threshold = ${report.recommended_threshold}\n</pre>\n<p>Notes:</p>\n<ul>\n<li><span class=\"name\">KAPPA_HARD_FAIL_THRESHOLD = 0.7</span> per <span class=\"name\">architecture.md</span> L199.</li>\n<li>Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.</li>\n<li>Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.</li>\n</ul>", "shortdoc": "Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).", "tags": ["agenteval"], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 187}, {"name": "Judge.Get Score", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "result: AgentRunResult"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "JudgeScore", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Evaluates an <span class=\"name\">AgentRunResult</span> against a Markdown rubric using an LLM judge (PRD FR48).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 single-shot LLM call against the configured <span class=\"name\">judge_adapter</span> (default <span class=\"name\">\"generic\"</span> LiteLLM-backed). LLM-deterministic per the determinism-contract.md <span class=\"name\">@tier(2)</span> contract when invoked with <span class=\"name\">seed + temperature=0</span>. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>The <span class=\"name\">AgentRunResult</span> to evaluate. Reads <code>result.response_text</code> for the agent's output.</td>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug to resolve via <span class=\"name\">agenteval.coding_agents</span> entry-points. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier for the judge adapter (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>). Forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs (e.g., <code>temperature=0.0</code>, <code>seed=42</code>).</td>\n</tr>\n</table>\n<p>Returns <code>JudgeScore</code> with: <code>numeric_score</code> (0-10), <code>pass_threshold_met</code> (vs rubric threshold), <code>reasoning</code> (LLM's narrative explanation), <code>criteria_breakdown</code> (per-criterion sub-scores), <code>cost_usd</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>JudgeOutputParseError</code> when the LLM response is not valid JSON OR is missing required fields OR <code>numeric_score</code> is outside <code>[0.0, 10.0]</code>.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6\n${score} =    <a href=\"#Judge.Get%20Score\" class=\"name\">Judge.Get Score</a>    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${score.pass_threshold_met}\nShould Be True    ${score.numeric_score} &gt;= 7.0\nLog    Reasoning: ${score.reasoning}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR48 ratifies the keyword + rubric calibration discipline.</li>\n<li>Tier-2 LLM-deterministic per <span class=\"name\">determinism-contract.md</span>; cost guardrails per ADR-015.</li>\n<li><span class=\"name\">JudgeScore</span> shape ratified Story 12.1 AC-12.1.2 per architecture L1316.</li>\n<li>Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.</li>\n</ul>", "shortdoc": "Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 117}, {"name": "Load Scenario", "args": [{"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "scenario: str"}], "returnType": {"name": "Scenario", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Loads + validates a scenario YAML without executing it.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file read + YAML parse + schema validation. Returns the parsed <code>Scenario</code> dataclass without dispatching to any adapter \u2014 useful for <code>.robot</code> tests that assert on scenario metadata or pre-flight-check scenarios before a <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidScenarioYAMLError</code> on parse failure or schema violation. The error's <code>field_name</code> attribute pinpoints the offending field per FR59.</p>\n<p>Example:</p>\n<pre>\n${scenario} =    <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a>    ${CURDIR}/scenarios/web-search.yaml\nShould Be Equal    ${scenario.agent}    web-search-agent\nShould Be Equal    ${scenario.model}    anthropic/claude-sonnet-4-6\nLength Should Be    ${scenario.evals}    5\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the scenario YAML schema; see <span class=\"name\">Scenario</span> dataclass in <span class=\"name\">scenarios/schema.py</span>.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> (Tier-3) for dispatch + execution.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n</ul>", "shortdoc": "Loads + validates a scenario YAML without executing it.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 330}, {"name": "Run Scenario", "args": [{"name": "adapter", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "_Unset", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str | _Unset = _UNSET"}, {"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "scenario: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Executes a scenario YAML file's <code>evals[]</code> against an adapter (PRD FR15).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 loads the scenario YAML via <code>load_scenario()</code>, validates against the <code>Scenario</code> schema, then dispatches each eval's prompt to <code>adapter.run()</code> <code>repeat</code> times. Returns a flat <code>list[AgentRunResult]</code> of length <code>sum(eval.repeat for eval in scenario.evals)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Per-scenario <code>agent:</code> field in the YAML overrides this kwarg per FR15 (\"scenario YAML specifies agent\" \u2014 YAML beats default but not explicit kwarg).</td>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code>. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are split between adapter constructor + <code>run()</code> per the same signature-introspection rule as <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>. Scenario-YAML <code>model:</code> / <code>provider:</code> fields inject into the merged kwargs unless the caller already passed them.</p>\n<p>Raises <code>InvalidScenarioYAMLError</code> on YAML parse / schema failure, <code>AdapterDiscoveryError</code> on unknown adapter name, and <code>NotImplementedError</code> on non-empty comma-separated <code>mcp_servers</code> (Phase-1 DF-4.3-S2 carve-out).</p>\n<p>Example:</p>\n<pre>\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    scenario=${CURDIR}/scenarios/web-search.yaml\nLength Should Be    ${results}    5\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the multi-eval orchestration contract.</li>\n<li>FR41 precedence resolution: explicit kwarg &gt; scenario YAML &gt; library default.</li>\n<li>Sibling keyword: <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a> (Tier-1) to validate the YAML without executing.</li>\n<li>Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).</li>\n</ul>", "shortdoc": "Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 215}, {"name": "Send Prompt", "args": [{"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "prompt: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Executes a single-shot prompt against a coding-agent adapter (PRD FR14).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 invokes the named adapter's <code>run()</code> method per the <span class=\"name\">CodingAgentAdapter</span> Protocol. Returns an <code>AgentRunResult</code> carrying <code>response_text</code>, <code>tool_calls</code>, <code>usage</code>, <code>metadata</code> (with <code>completeness</code> + <code>mcp_coverage</code>), <code>cost_usd</code>, <code>latency_seconds</code>, and <code>trace_id</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code> (LiteLLM-backed).</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code> of attached MCP servers. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2 \u2014 name resolution to handles deferred).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are forwarded to the adapter \u2014 caller kwargs that match the adapter's <code>__init__</code> signature flow to construction; the rest flow to <code>run()</code>. Useful for <code>model=\"anthropic/claude-sonnet-4-6\"</code>, <code>temperature=0.5</code>, etc.</p>\n<p>Raises <code>AdapterDiscoveryError</code> when the <code>adapter</code> name is not registered. Raises <code>NotImplementedError</code> on comma-separated <code>mcp_servers</code> name strings until DF-4.3-S2 lands the name \u2192 handle resolver (pass <code>mcp_servers={'name': handle}</code> directly to forward Phase-1).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Hello, world.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=claude-code-cli    prompt=Run the build.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR14 ratifies the single-prompt orchestration contract.</li>\n<li>Adapter discovery per Story 1b.3 + ADR-013 entry-points.</li>\n<li><code>cost_usd</code> is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> for multi-eval YAML-driven dispatch (Tier-3).</li>\n</ul>", "shortdoc": "Executes a single-shot prompt against a coding-agent adapter (PRD FR14).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 127}, {"name": "Stat.Assert Run Determinism", "args": [{"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "expect", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "byte_identical", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "expect: str = byte_identical"}], "returnType": null, "doc": "<p>Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 invokes the wrapped keyword twice with identical inputs and compares via deep-equality. The bit-identical guarantee is scoped to Tier-1 keywords only (FR31a contract); the keyword raises <code>TierViolationError</code> if a Tier-2/3 keyword is passed.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR callable. Same dispatch rules as <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> (string form requires active RF context).</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings.</td>\n</tr>\n<tr>\n<td><code>expect</code></td>\n<td>Comparison mode. Phase-1 supports <code>\"byte_identical\"</code> only; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> deferred to Phase-2.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>expect != \"byte_identical\"</code> (Phase-1 scope). Raises <code>TierViolationError</code> when the wrapped keyword is not Tier-1 \u2014 FR31a is scoped to Tier-1 only. Raises <code>AssertionError</code> on output mismatch with a <span class=\"name\">`redact()</span>`-scrubbed diff per FR38a credential-safety contract.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Effective Config\nRun Keyword And Expect Error    TierViolationError*    <a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Send Prompt\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> + <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for statistical assertions instead.</li>\n<li>Diff redaction per FR38a + Story 5.3 \u2014 credentials in args / output don't leak into RF logs.</li>\n<li>Story 6.3 ratifies <code>\"byte_identical\"</code> as the Phase-1 contract; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> are Phase-2 work-items.</li>\n</ul>", "shortdoc": "Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 270}, {"name": "Stat.Get Pass At K", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form computation of the HumanEval estimator <code>1 - C(n-c, k) / C(n, k)</code>. Returns <code>float \u2208 [0, 1]</code>. Scalar return preserves AssertionEngine compatibility (<code>&gt;=</code> / <code>&lt;=</code> matchers); CI is a separate paired getter \u2014 see <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Must satisfy <code>1 &lt;= k &lt;= len(runs)</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Default checks <code>r.completeness == \"complete\"</code> per epic AC-2 + Story 6.4 fix-NOW.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k &lt; 1</code>, <code>k &gt; len(runs)</code>, or <code>len(runs) == 0</code>.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${pass_at_1} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=1\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.\n${pred} =    Evaluate    lambda r: r.error is None\n${pass_strict} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5    predicate=${pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR27 ratifies the scalar <code>float</code> return type \u2014 no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).</li>\n<li>Default predicate updated by Story 6.4 fix-NOW: <code>completeness == \"complete\"</code> (pre-edit <code>\"full\"</code> was fake-green; <span class=\"name\">AgentRunMetadata._VALID_COMPLETENESS</span> is <code>{\"complete\", \"truncated\", \"partial\"}</code>).</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a> for the Wilson score CI.</li>\n</ul>", "shortdoc": "Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 172}, {"name": "Stat.Get Pass At K Confidence Interval", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}, {"name": "confidence", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.95", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "confidence: float = 0.95"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Wilson score interval at the given <code>confidence</code> level for the latent per-trial success probability. Returns <code>(ci_lower, ci_upper)</code> tuple of <code>float</code> in <code>[0, 1]</code>. Paired with <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> \u2014 the scalar point estimate plus this CI together satisfy epic AC-2's \"Pass@k with confidence interval\" promise.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Validated for <code>1 &lt;= k &lt;= len(runs)</code> but only used for sanity check \u2014 the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Same default as <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>.</td>\n</tr>\n<tr>\n<td><code>confidence</code></td>\n<td>Confidence level in <code>(0, 1)</code>. Defaults to <code>0.95</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k</code> is non-positive or <code>k &gt; n</code> (with <code>n &gt; 0</code> \u2014 empty <code>runs</code> is permitted per the Wilson formula).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5\nShould Be True    0.0 &lt;= ${ci_lo} &lt;= ${ci_hi} &lt;= 1.0                      # CI bounds are well-formed probabilities.\n${ci99_lo}    ${ci99_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5    confidence=0.99\nShould Be True    (${ci99_hi} - ${ci99_lo}) &gt;= (${ci_hi} - ${ci_lo})      # Higher confidence \u2192 wider interval.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.</li>\n<li>PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for the scalar point estimate.</li>\n</ul>", "shortdoc": "Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 214}, {"name": "Stat.Run N Times", "args": [{"name": "n", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "n: int"}, {"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "seed", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "int", "typedoc": "integer", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "seed: int | None = None"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Runs a keyword <code>n</code> times independently and returns the per-trial results (PRD FR26).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 wraps the target keyword in independent trials. Returns <code>list[KeywordRun]</code> of length <code>n</code>. Trial-level errors are re-raised from this keyword \u2014 wrap in <code>Run Keyword And Ignore Error</code> for \"ignore failures\" semantics.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>n</code></td>\n<td>Number of independent trials. Must be <code>&gt;= 1</code>.</td>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR a Python callable. String form requires an active RF execution context (resolved via <code>BuiltIn</code>); callable form is useful for pytest unit tests.</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings (e.g. <code>{\"adapter\": \"generic\", \"prompt\": \"Hi\"}</code> or <code>[\"adapter=generic\", \"prompt=Hi\"]</code>). <code>None</code> = no args.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>Optional <code>int</code> seed; each trial receives <code>seed + trial_index</code> via a <code>seed=</code> kwarg injection so trials are deterministic but distinct. <code>None</code> = OS-entropy seeding per trial.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>n &lt; 1</code>. Raises <code>CostExceededError</code> / <code>RuntimeBudgetExceededError</code> per the <code>@guarded_fanout</code> 3-layer enforcement.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= 0.6\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the <code>list[KeywordRun]</code> return type.</li>\n<li>Cost / runtime guardrails per ADR-015 + <span class=\"name\">_kernel/guardrails.py::@guarded_fanout</span>.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> (Tier-1) consumes the returned list.</li>\n</ul>", "shortdoc": "Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 86}, {"name": "Tool Call Should Have Occurred", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "tool", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool: str"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: dict[str, Any] | None = None"}, {"name": "match_mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "subset", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "match_mode: str = subset"}], "returnType": null, "doc": "<p>Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 searches all observed <code>tool_calls</code> for one matching <code>tool</code> + (optionally) <code>args</code>. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>tool</code></td>\n<td>Expected tool name (exact-match required).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>Optional dict of expected args. <code>None</code> (default) = name-only match.</td>\n</tr>\n<tr>\n<td><code>match_mode</code></td>\n<td><code>\"subset\"</code> (default \u2014 <code>args</code> is a dict-subset of <code>tc.args</code>; recursive for nested dicts) OR <code>\"exact\"</code> (<code>tc.args == args</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>match_mode</code> is invalid (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> when no tool call matches.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected <code>web_search</code> call):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"agenteval\"} }}\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"x\"} }}    match_mode=exact\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR24 ratifies the name + args + match-mode contract.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a> for ordered-sequence assertions over multiple calls.</li>\n</ul>", "shortdoc": "Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 162}, {"name": "Trajectory Should Match", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "expected", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected: list[str]"}, {"name": "mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "exact", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mode: str = exact"}], "returnType": null, "doc": "<p>Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 four match modes available. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a so credentials in tool args don't leak into RF logs.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>expected</code></td>\n<td>List of expected tool names (or regex patterns when <code>mode=\"regex\"</code>).</td>\n</tr>\n<tr>\n<td><code>mode</code></td>\n<td>Match mode: <code>\"exact\"</code> (ordered equality) / <code>\"subsequence\"</code> (ordered, extras allowed between) / <code>\"set\"</code> (unordered set-equality of distinct names) / <code>\"regex\"</code> (each <code>expected[i]</code> is a <code>re.fullmatch</code> pattern against <code>&lt;tool&gt;:&lt;json.dumps(args, sort_keys=True)&gt;</code>). Default <code>\"exact\"</code>.</td>\n</tr>\n</table>\n<p>Set-mode caveat: duplicate names collapse \u2014 <code>[\"a\", \"a\"]</code> set- equals <code>[\"a\"]</code>. Operators wanting multiset semantics (\"exactly N calls of tool X\") should use <code>mode=\"exact\"</code>.</p>\n<p>Raises <code>ValueError</code> when <code>mode</code> is not one of the 4 documented values (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> on trajectory mismatch.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected 3-call trajectory):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'fetch', 'summarize']}}\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['fetch', 'web_search']}}    mode=set\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR23a + FR23b ratify the 4 match modes.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a> for single-call name+args assertions.</li>\n</ul>", "shortdoc": "Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 86}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config", "Get Last Warnings", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["__init__", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config With Provenance", "Get Last Warnings", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["__init__", "Get Cost Total", "Get Latency", "Get Latency P95", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Keyword Tier", "Get Tool Call Count", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Config", "Get Cost Total", "Get Last Warnings", "Get Latency", "Get Latency P95", "Get Spans", "Get Token Usage", "Get Tool Call Count", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Run Scenario", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Trajectory Should Match"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["__init__"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["__init__", "Get Effective Config", "Get Run Manifest", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Judge.Calibrate Rubric", "Judge.Get Score"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["__init__", "Agent Response Should Contain", "Agent Response Should Match Regex", "Agent Response Should Match Schema", "Get Cohort Heatmap", "Get Config", "Get Effective Config", "Get Effective Config With Provenance", "Get Keyword Tier", "Get Last Warnings", "Get Run Manifest", "Get Spans", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Unnecessary Call Rate", "Judge.Calibrate Rubric", "Judge.Get Score", "Load Scenario", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred", "Trajectory Should Match"], "accepts": ["Any"]}, {"type": "Standard", "name": "tuple", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> or <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible lists converted further to tuples. They can contain any values <code>ast.literal_eval</code> supports, including tuples and other collections.</p>\n<p>If the argument is a tuple, it is used without conversion. Lists and other sequences are converted to tuples.</p>\n<p>If the type has nested types like <code>tuple[str, int, int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>('one', 'two')</code>, <code>(('one', 1), ('two', 2))</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for list literals is new in Robot Framework 7.4.</p>", "usages": ["Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Sequence"]}]}

exec
/bin/bash -lc 'grep -RIn "telemetry" src/AgentEval/telemetry src/AgentEval/__init__.py src/AgentEval/_kernel | head -200' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/telemetry/backends.py:44:    from opentelemetry.sdk.trace import ReadableSpan
src/AgentEval/telemetry/backends.py:53:# `opentelemetry-exporter-otlp` is a metapackage shipping BOTH the HTTP and
src/AgentEval/telemetry/backends.py:59:    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
src/AgentEval/telemetry/backends.py:62:    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
src/AgentEval/telemetry/backends.py:83:        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
src/AgentEval/telemetry/backends.py:216:                source="telemetry.backends.jsonl",
src/AgentEval/telemetry/backends.py:305:    ``opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter`` based
src/AgentEval/telemetry/backends.py:307:    extra (``opentelemetry-exporter-otlp``); raises ``ImportError`` on
src/AgentEval/telemetry/backends.py:360:        from opentelemetry.sdk.trace.export import SpanExporter as _SpanExporter
src/AgentEval/telemetry/__init__.py:15:"""AgentEval.telemetry sub-package.
src/AgentEval/telemetry/spans.py:26:``telemetry/semconv.py`` per NFR-COMPAT-06.
src/AgentEval/telemetry/spans.py:40:from opentelemetry import trace
src/AgentEval/telemetry/spans.py:41:from opentelemetry.trace import Span
src/AgentEval/telemetry/spans.py:43:from AgentEval.telemetry.semconv import (
src/AgentEval/telemetry/spans.py:68:_TRACER_NAME = "AgentEval.telemetry"
src/AgentEval/telemetry/library.py:48:    from opentelemetry.sdk.trace import ReadableSpan
src/AgentEval/telemetry/_xunit_enrichment.py:17:Private helper used exclusively by ``telemetry/listener.Listener.xunit_file``.
src/AgentEval/telemetry/_xunit_enrichment.py:38:    - architecture L1248: ``telemetry/listener.py``
src/AgentEval/telemetry/_xunit_enrichment.py:50:from AgentEval.telemetry.semconv import (
src/AgentEval/telemetry/_xunit_enrichment.py:67:_logger = logging.getLogger("AgentEval.telemetry.xunit_enrichment")
src/AgentEval/telemetry/_xunit_enrichment.py:135:    ``telemetry/listener.Listener._snapshot_completed_run_metadata``). Keys
src/AgentEval/telemetry/run_manifest.py:23:Architecture L1248-1251 telemetry project tree gets a new sibling file
src/AgentEval/telemetry/run_manifest.py:60:from AgentEval.telemetry.backends import _sanitize_path_segment
src/AgentEval/telemetry/run_manifest.py:148:                source="telemetry.run_manifest",
src/AgentEval/telemetry/listener.py:24:    robot --listener AgentEval.telemetry.listener tests/
src/AgentEval/telemetry/listener.py:53:    - architecture L1248: telemetry/listener.py
src/AgentEval/telemetry/listener.py:73:from opentelemetry import context as otel_context
src/AgentEval/telemetry/listener.py:74:from opentelemetry import trace
src/AgentEval/telemetry/listener.py:75:from opentelemetry.sdk.resources import Resource
src/AgentEval/telemetry/listener.py:76:from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
src/AgentEval/telemetry/listener.py:77:from opentelemetry.sdk.trace import Span as SDKSpan
src/AgentEval/telemetry/listener.py:78:from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
src/AgentEval/telemetry/listener.py:85:from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend, OTLPBackend
src/AgentEval/telemetry/listener.py:86:from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID
src/AgentEval/telemetry/listener.py:100:# `--listener AgentEval.telemetry.listener` is passed); adapters need a
src/AgentEval/telemetry/listener.py:102:# directly (which would create a kernel-vs-telemetry layering violation).
src/AgentEval/telemetry/listener.py:190:    Register via ``robot --listener AgentEval.telemetry.listener tests/``.
src/AgentEval/telemetry/listener.py:398:                source="telemetry.listener",
src/AgentEval/telemetry/listener.py:518:            from AgentEval.telemetry._terminal_summary import render_summary
src/AgentEval/telemetry/listener.py:550:            from AgentEval.telemetry import _xunit_enrichment
src/AgentEval/telemetry/listener.py:585:        from `telemetry` on `mcp.observer`.
src/AgentEval/telemetry/listener.py:674:        from AgentEval.telemetry.run_manifest import RunManifestEmitter
src/AgentEval/telemetry/listener.py:854:                    source="telemetry.listener",
src/AgentEval/telemetry/listener.py:870:                    source="telemetry.listener",
src/AgentEval/telemetry/listener.py:892:                source="telemetry.listener",
src/AgentEval/telemetry/semconv.py:160:# by `telemetry/_xunit_enrichment.py` per `docs/contracts/junit-xml-enrichment.md`.
src/AgentEval/__init__.py:29:Sub-libraries (coding_agent, mcp, telemetry, metrics, stats, judge, ...) land in
src/AgentEval/__init__.py:35:    Library    AgentEval    allow_validate_operator=False    telemetry=True
src/AgentEval/__init__.py:46:    agent = AgentEval(allow_validate_operator=True, telemetry=False)
src/AgentEval/__init__.py:124:    ("AgentEval.telemetry.library", "TelemetryLibrary"),
src/AgentEval/__init__.py:172:        telemetry: Enable the OTel listener for trace recording (FR42 + FR44).
src/AgentEval/__init__.py:210:            Requires the ``[otlp]`` extra (``opentelemetry-exporter-otlp``);
src/AgentEval/__init__.py:222:        - PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)
src/AgentEval/__init__.py:237:        telemetry: bool = _UNSET,
src/AgentEval/__init__.py:254:            "telemetry": telemetry,
src/AgentEval/__init__.py:272:        self._telemetry = resolved["telemetry"]
src/AgentEval/__init__.py:426:        | Library    AgentEval    max_cost_usd=5.0    telemetry=False
src/AgentEval/__init__.py:429:        | Should Be Equal    ${config}[telemetry]    ${FALSE}
src/AgentEval/__init__.py:449:            "telemetry": self._telemetry,
src/AgentEval/_kernel/redaction.py:63:    from opentelemetry.context import Context  # OTel's own context, NOT contextvars.Context
src/AgentEval/_kernel/redaction.py:64:    from opentelemetry.sdk.trace import ReadableSpan, Span
src/AgentEval/_kernel/redaction.py:65:    from opentelemetry.sdk.trace import SpanProcessor as _OTelSpanProcessor
src/AgentEval/_kernel/redaction.py:67:    from opentelemetry.sdk.trace import SpanProcessor as _OTelSpanProcessor
src/AgentEval/_kernel/redaction.py:243:        directly — opentelemetry-sdk 1.20+ keeps this contract stable;
src/AgentEval/_kernel/redaction.py:286:    storage is `_dict` (per opentelemetry-sdk 1.20+ source). Test mocks
src/AgentEval/_kernel/trace_store.py:36:PRD FR33b). Phase-1 also supports `jsonl` backend in `agenteval/telemetry/`
src/AgentEval/_kernel/trace_store.py:58:from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
src/AgentEval/_kernel/trace_store.py:61:    from opentelemetry.sdk.trace import ReadableSpan
src/AgentEval/_kernel/trace_store.py:481:    in `opentelemetry-sdk` 1.20+.
src/AgentEval/_kernel/trace_store.py:491:    # stable across opentelemetry-sdk 1.20+ minor versions (pinned to
src/AgentEval/_kernel/context.py:815:    "telemetry": True,
src/AgentEval/_kernel/context.py:834:    "telemetry": "AGENTEVAL_TELEMETRY",
src/AgentEval/_kernel/context.py:884:    if key in ("telemetry", "allow_validate_operator", "allow_external_mcp_blind"):
src/AgentEval/_kernel/warnings.py:19:emit site in the telemetry pipeline ALSO calls `record_warning(...)` here
src/AgentEval/_kernel/warnings.py:24:(`telemetry/_keywords.py`) is the consumer surface for test authors.
src/AgentEval/_kernel/warnings.py:171:            # `--listener AgentEval.telemetry.listener` had `current_context()`
src/AgentEval/_kernel/warnings.py:244:    the `_json_default` callable in `telemetry/run_manifest.py` per

exec
/bin/bash -lc 'grep -RIn "trace backend names" src docs tests | head -100' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
exec
/bin/bash -lc "sed -n '150,185p' src/AgentEval/__init__.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
        return "_UNSET"

    def __bool__(self) -> bool:
        return False


_UNSET: Any = _UnsetType()


class AgentEval(DynamicCore):  # type: ignore[misc]
    """Robot Framework library for evaluating AI coding agents.

    Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point
    + the FR41 precedence chain (kwarg → env-var → `.env` → defaults) via
    `_kernel.context.resolve_config` (Story 1b.1). `Get Effective Config`
    returns the precedence-resolved values.

    Args:
        provider: Provider plugin name resolved via `agenteval.providers`
            entry-points (FR42; ADR-013). Phase 1 ships only the `litellm`
            provider; future providers register via
            `[project.entry-points."agenteval.providers"]`.
        telemetry: Enable the OTel listener for trace recording (FR42 + FR44).
            When False, `Get Trace Backend Names` returns `[]` and no OTLP
            egress occurs (Phase 2). Phase 1 wires the parameter; full
            listener-disable enforcement lands in Epic 5 Story 5.1.
        trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports
            `"memory"` and `"jsonl"`; `"otlp"` is Phase 2.
        allow_validate_operator: Enable the AssertionEngine `validate` operator
            which uses `eval()` (FR42 + FR43; NFR-SEC-02). Default False — the
            safer posture per NFR-SEC-02. Gate enforcement (raising
            `ValidateOperatorDisallowed`) lands in Epic 6.
        default_temperature: Default provider temperature for non-stochastic
            keywords (FR42). 0.0 enforces deterministic provider calls where
            the underlying model supports it.
        mcp_per_test: MCP server scope.

exec
/bin/bash -lc "python - <<'PY'
import json,re
from pathlib import Path
p=Path('docs/keywords/AgentEval.html')
text=p.read_text(encoding='utf-8')
for needle in ['otlp_endpoint', 'Phase 1 supports "'`"memory"` and `"jsonl"`; `"otlp"` is Phase 2.'"', 'max_runtime_seconds']:
    print(needle, text.find(needle))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
otlp_endpoint -1
Phase 1 supports `"memory"` and `"jsonl"`; `"otlp"` is Phase 2. -1
max_runtime_seconds 3178

exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
from opentelemetry import trace
from AgentEval.telemetry import listener as listener_mod
import os

# start from memory, then switch to otlp, then back to memory in same process.
for endpoint in ['http://first.example:4318/v1/traces', 'http://second.example:4318/v1/traces']:
    os.environ['AGENTEVAL_TRACE_BACKEND']='otlp'
    os.environ['AGENTEVAL_OTLP_ENDPOINT']=endpoint
    l = listener_mod.Listener()
    l._configure_tracer_provider(); l._resolve_backend(suite=None); l._attach_otlp_exporter_if_needed()
provider = trace.get_tracer_provider()
active = getattr(provider, '_active_span_processor', None)
processors = getattr(active, '_span_processors', ()) if active else ()
print('processors after two otlp endpoints:', len(processors))
for i,p in enumerate(processors):
    exp = getattr(p, '_span_exporter', None) or getattr(p, 'span_exporter', None) or getattr(p, 'exporter', None)
    print(i, type(p).__name__, getattr(exp, '_endpoint', None) if exp else None)

os.environ['AGENTEVAL_TRACE_BACKEND']='memory'
lm = listener_mod.Listener(); lm._configure_tracer_provider(); lm._resolve_backend(suite=None); lm._attach_otlp_exporter_if_needed()
provider = trace.get_tracer_provider()
active = getattr(provider, '_active_span_processor', None)
processors = getattr(active, '_span_processors', ()) if active else ()
print('processors after switching to memory:', len(processors))
for i,p in enumerate(processors):
    exp = getattr(p, '_span_exporter', None) or getattr(p, 'span_exporter', None) or getattr(p, 'exporter', None)
    print(i, type(p).__name__, getattr(exp, '_endpoint', None) if exp else None)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 844ms:
processors after two otlp endpoints: 4
0 TestIdContextSpanProcessor None
1 RedactionProcessor None
2 SimpleSpanProcessor None
3 BatchSpanProcessor http://first.example:4318/v1/traces
processors after switching to memory: 4
0 TestIdContextSpanProcessor None
1 RedactionProcessor None
2 SimpleSpanProcessor None
3 BatchSpanProcessor http://first.example:4318/v1/traces

codex
The process-reuse behavior is worse than a simple duplicate-attachment concern. I’ve reproduced that once OTLP is attached, later suites in the same Python process still retain that exporter even after switching `trace_backend` back to `memory`, and endpoint changes are ignored. I’m checking one more source of drift now: the claimed `service.name` contract versus what the code actually sets.
exec
/bin/bash -lc "grep -RIn \"service.name\\|unknown_service\\|robotframework-agenteval\" src/AgentEval tests | head -200" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/stats/library.py:81:    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
src/AgentEval/stats/library.py:85:        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
src/AgentEval/__init__.py:20:"""robotframework-agenteval — Robot Framework library for evaluating AI coding agents.
src/AgentEval/coding_agent/base.py:129:    installed distribution name (e.g., `robotframework-agenteval`). The
src/AgentEval/coding_agent/openai_agents.py:57:    "Install with: `pip install robotframework-agenteval[openai-agents]` "
src/AgentEval/coding_agent/claude_agent_sdk.py:53:    "Install with: `pip install robotframework-agenteval[claude-sdk]` "
src/AgentEval/cli.py:187:        "See https://github.com/manykarim/robotframework-agenteval for roadmap.\n"
src/AgentEval/_init/templates/README.md:41:- **Recipes:** [`docs/recipes/01-first-eval-in-five-minutes.md`](https://github.com/manykarim/robotframework-agenteval/blob/main/docs/recipes/01-first-eval-in-five-minutes.md) walks through this scaffolded project. Other recipes in the gallery cover Pass@k, Tool Discoverability, Skill Author validation, CI integration, etc.
src/AgentEval/_init/templates/README.md:47:Full library docs at <https://github.com/manykarim/robotframework-agenteval>.
src/AgentEval/_new_adapter/templates/pyproject.toml.tmpl:7:    "robotframework-agenteval>=0.1.0",
src/AgentEval/telemetry/backends.py:79:    ``uv pip install robotframework-agenteval[otlp]`` so operators can
src/AgentEval/telemetry/backends.py:83:        "OTLPBackend: opentelemetry-exporter-otlp required. Install via: uv pip install robotframework-agenteval[otlp]"
src/AgentEval/telemetry/listener.py:849:                    "`uv pip install robotframework-agenteval[otlp]`."
src/AgentEval/telemetry/listener.py:857:                        "`uv pip install robotframework-agenteval[otlp]` OR "
tests/dogfood/rf-mcp/test_mcp_surface_parity.robot:6:...              `robotframework-agenteval` Epic 2 (static inspection)
tests/unit/stats/test_advanced_extras_gate.py:66:    `uv pip install robotframework-agenteval[agenteval-advanced]`.
tests/unit/stats/test_advanced_extras_gate.py:76:        assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
tests/unit/test_init_cli.py:89:    assert "robotframework-agenteval" in target.read_text()
tests/unit/coding_agent/test_base.py:565:    resolves via `packages_distributions()` to `robotframework-agenteval`, NOT
tests/unit/coding_agent/test_base.py:571:        lambda: {"AgentEval": ["robotframework-agenteval"]},
tests/unit/coding_agent/test_base.py:576:        lambda dist: "9.9.9" if dist == "robotframework-agenteval" else "wrong",
tests/unit/kernel/test_trace_store.py:40:    provider = TracerProvider(resource=Resource.create({"service.name": "agenteval-test"}))
tests/unit/telemetry/test_backends_otlp_extras_gate.py:57:    `uv pip install robotframework-agenteval[otlp]` verbatim so the
tests/unit/telemetry/test_backends_otlp_extras_gate.py:67:    assert "uv pip install robotframework-agenteval[otlp]" in msg
tests/unit/telemetry/test_backends_otlp_extras_gate.py:122:    assert any("uv pip install robotframework-agenteval[otlp]" in str(w.message) for w in degraded)
tests/integration/skills/test_devon_stacked_validation.py:65:    "Find information about robotframework-agenteval",

exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
from opentelemetry import trace
from AgentEval.telemetry import listener as listener_mod
l = listener_mod.Listener(); l._configure_tracer_provider();
p = trace.get_tracer_provider()
print(type(p).__name__)
print(getattr(p, 'resource', None).attributes)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run --extra otlp python - <<'PY'
from opentelemetry.sdk.resources import Resource
print(Resource.create({}).attributes)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "grep -RIn \"libdoc\\|docs/keywords/AgentEval.html\" -n .github docs scripts pyproject.toml Makefile . | head -100" in /home/many/workspace/robotframework-agenteval
 succeeded in 208ms:
{'telemetry.sdk.language': 'python', 'telemetry.sdk.name': 'opentelemetry', 'telemetry.sdk.version': '1.41.1', 'service.name': 'unknown_service'}

 succeeded in 409ms:
 succeeded in 883ms:
TracerProvider
{'telemetry.sdk.language': 'python', 'telemetry.sdk.name': 'opentelemetry', 'telemetry.sdk.version': '1.41.1', 'service.name': 'unknown_service'}

codex
I have enough for the core findings. I’m pulling one small extra verification on the generated keyword docs so I can distinguish a real public-doc drift from a purely internal story-note mismatch.
exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
text = Path('docs/keywords/AgentEval.html').read_text(encoding='utf-8')
start = text.find('generated\": \"')
print(text[start:start+120])
needle = '\"repr\": \"max_runtime_seconds: float | None = _UNSET\"'
pos = text.find(needle)
print('max_runtime_seconds repr pos', pos)
print(text[pos-120:pos+180])
print('otlp_endpoint present?', 'otlp_endpoint' in text)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
generated": "2026-05-27T19:45:45+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/
max_runtime_seconds repr pos 7222
ne", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize 
otlp_endpoint present? False

exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
text = Path('tests/integration/telemetry/test_otlp_export_e2e.py').read_text()
for s in ['assert len(spans) >= 1', 'assert any(s.get(\"name\") == \"agenteval_e2e_http_span\" for s in spans)', 'assert any(a.get(\"key\") == \"agenteval.tier\" for a in flat_attrs)', 'assert any(s.get(\"name\") == \"agenteval_e2e_grpc_span\" for s in spans)']:
    print(s)
    print('present', s in text)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
assert len(spans) >= 1
present True
assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
present True
assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)
present True
assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)
present True

exec
/bin/bash -lc "nl -ba tests/integration/telemetry/test_otlp_export_e2e.py | sed -n '96,150p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
    96	    Per Story 13.2 L-4 (Codex empirical-probe lesson): verify the wire
    97	    format by reading collector output, NOT just call_count.
    98	    """
    99	    config_file = tmp_path / "otel-config.yaml"
   100	    output_file = tmp_path / "spans.json"
   101	    config_file.write_text(minimal_otel_config(output_file))
   102	    # Random high ports to avoid colliding with local OTel collectors.
   103	    http_port = 24318
   104	    grpc_port = 24317
   105	
   106	    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
   107	        _emit_test_span_via_listener(
   108	            endpoint=f"http://localhost:{http_port}/v1/traces",
   109	            span_name="agenteval_e2e_http_span",
   110	        )
   111	        # The collector batches at 100ms; give it a beat to flush the file.
   112	        time.sleep(1.5)
   113	
   114	    spans = read_collector_spans(output_file)
   115	    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
   116	    assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
   117	    # Verify agenteval-specific attribute flows through OTLP envelope.
   118	    flat_attrs: list[dict] = []
   119	    for s in spans:
   120	        flat_attrs.extend(s.get("attributes", []))
   121	    # OTLP attribute shape: {"key": "agenteval.tier", "value": {"intValue": "2"}}.
   122	    assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)
   123	
   124	
   125	def test_otlp_grpc_export_round_trip_against_collector(tmp_path: Path) -> None:
   126	    """Span emitted via OTLP gRPC lands in the collector's file output.
   127	
   128	    Verifies the gRPC scheme dispatch + insecure=True host:port stripping
   129	    end-to-end. Same wire-format readback assertion as the HTTP variant.
   130	    """
   131	    config_file = tmp_path / "otel-config.yaml"
   132	    output_file = tmp_path / "spans.json"
   133	    config_file.write_text(minimal_otel_config(output_file))
   134	    http_port = 24319
   135	    grpc_port = 24320
   136	
   137	    with docker_collector(config_file, output_file, http_port=http_port, grpc_port=grpc_port):
   138	        _emit_test_span_via_listener(
   139	            endpoint=f"grpc://localhost:{grpc_port}",
   140	            span_name="agenteval_e2e_grpc_span",
   141	        )
   142	        time.sleep(1.5)
   143	
   144	    spans = read_collector_spans(output_file)
   145	    assert len(spans) >= 1, f"no spans in collector output: {output_file.read_text()[:500]!r}"
   146	    assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)

exec
/bin/bash -lc "nl -ba docs/contracts/otel-trace-visual.md | sed -n '100,106p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   100	    -H "Content-Type: application/json" \
   101	    -d @-
   102	```
   103	
   104	The trace appears in Honeycomb's "robotframework-agenteval" dataset (the
   105	agenteval `OTelResource.service.name`). Use Honeycomb's BubbleUp on
   106	`agenteval.tier` to see Tier-3 fan-out latency distributions.

exec
/bin/bash -lc "nl -ba docs/keywords/AgentEval.html | sed -n '1,12p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	<!DOCTYPE html><html id=library-documentation-top lang=en><head>
     2	<meta http-equiv=Content-Type content="text/html; charset=utf-8">
     3	<meta name=viewport content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=0">
     4	<meta http-equiv=Pragma content=no-cache>
     5	<meta http-equiv=Expires content=-1>
     6	<meta http-equiv=X-UA-Compatible content="IE=edge">
     7	<meta content="Robot Framework 7.4.2 (Python 3.12.3 on linux)" name="Generator">
     8	<script type="text/javascript">
     9	libdoc = {"specversion": 3, "name": "AgentEval", "doc": "<p>Robot Framework library for evaluating AI coding agents.</p>\n<p>Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point + the FR41 precedence chain (kwarg \u2192 env-var \u2192 <span class=\"name\">.env</span> \u2192 defaults) via <span class=\"name\">_kernel.context.resolve_config</span> (Story 1b.1). <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> returns the precedence-resolved values.</p>\n<p>Args: provider: Provider plugin name resolved via <span class=\"name\">agenteval.providers</span> entry-points (FR42; ADR-013). Phase 1 ships only the <span class=\"name\">litellm</span> provider; future providers register via <span class=\"name\">[project.entry-points.\"agenteval.providers\"]</span>. telemetry: Enable the OTel listener for trace recording (FR42 + FR44). When False, <span class=\"name\">Get Trace Backend Names</span> returns <span class=\"name\">[]</span> and no OTLP egress occurs (Phase 2). Phase 1 wires the parameter; full listener-disable enforcement lands in Epic 5 Story 5.1. trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports <span class=\"name\">\"memory\"</span> and <span class=\"name\">\"jsonl\"</span>; <span class=\"name\">\"otlp\"</span> is Phase 2. allow_validate_operator: Enable the AssertionEngine <span class=\"name\">validate</span> operator which uses <span class=\"name\">eval()</span> (FR42 + FR43; NFR-SEC-02). Default False \u2014 the safer posture per NFR-SEC-02. Gate enforcement (raising <span class=\"name\">ValidateOperatorDisallowed</span>) lands in Epic 6. default_temperature: Default provider temperature for non-stochastic keywords (FR42). 0.0 enforces deterministic provider calls where the underlying model supports it. mcp_per_test: MCP server scope.</p>\n<ul>\n<li>True (default): per-test isolation; correct under <span class=\"name\">pabot --processes N</span>. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>False: single shared instance across all tests; only correct serial. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>\"suite\": per-suite scope; recipe-5 dogfood-CI ergonomics override. (Architecture L314 + NFR-PERF-03d \u2014 not in ADR-009 proper.) allow_external_mcp_blind: Opt-in to running with <span class=\"name\">mcp_coverage=\"external_mixed\"</span> without <span class=\"name\">IncompleteTraceError</span> (FR42 + ADR-016 D4 adapter contract). Default False enforces loud-refusal posture from ADR-016. max_cost_usd: Cost budget for <span class=\"name\">@guarded_fanout</span>-decorated Tier-3 keywords (FR42 + ADR-015). USD per fan-out invocation. Default 5.00. max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords (FR11b + ADR-015). Default None = no cap (opt-in via explicit value). Sibling to <span class=\"name\">max_cost_usd</span>; catches slow MCP-server startup compounded across trials.</li>\n</ul>\n<p>FR41 precedence behavior (Story 1b.1): Each <span class=\"name\">__init__</span> parameter defaults to a private sentinel; if the caller does NOT pass it, the value falls through to <span class=\"name\">AGENTEVAL_*</span> env-vars, then to a <span class=\"name\">.env</span> file in cwd, then to the FR42 + FR11b defaults documented in this docstring. Callers who want to force a value explicitly (even when an env-var is set) pass that value as a kwarg. <span class=\"name\">.env.example</span> documents the canonical <span class=\"name\">AGENTEVAL_*</span> env-var names.</p>\n<p>References:</p>\n<ul>\n<li>PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)</li>\n<li>PRD FR11b (max_runtime_seconds keyword arg sibling)</li>\n<li>PRD FR41 (config precedence)</li>\n<li>ADR-009 (mcp_per_test 3-mode)</li>\n<li>ADR-013 (entry-points discovery for <span class=\"name\">provider</span>)</li>\n<li>ADR-015 (@guarded_fanout for cost + runtime guardrails)</li>\n<li>ADR-016 (mcp_coverage detection + allow_external_mcp_blind)</li>\n<li>docs/contracts/stability-surface.md (Phase-1 stability labels for this class)</li>\n</ul>", "version": "", "generated": "2026-05-27T19:45:45+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 159, "tags": ["agenteval"], "inits": [{"name": "__init__", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "provider", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "provider: str = _UNSET"}, {"name": "telemetry", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "telemetry: bool = _UNSET"}, {"name": "trace_backend", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "trace_backend: str = _UNSET"}, {"name": "allow_validate_operator", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_validate_operator: bool = _UNSET"}, {"name": "default_temperature", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "default_temperature: float = _UNSET"}, {"name": "mcp_per_test", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'suite'", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "mcp_per_test: bool | Literal['suite'] = _UNSET"}, {"name": "allow_external_mcp_blind", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_external_mcp_blind: bool = _UNSET"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_cost_usd: float = _UNSET"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize self.  See help(type(self)) for accurate signature.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 225}], "keywords": [{"name": "Agent Response Should Contain", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "substring", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "substring: str"}], "returnType": null, "doc": "<p>Asserts that <code>substring</code> appears in <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>substring</code></td>\n<td>Literal substring to match. Case-sensitive.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the substring is not found.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    Robot Framework                                          # Mock echoes the prompt.\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    test automation\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 236}, {"name": "Agent Response Should Match Regex", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "pattern", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "pattern: str"}], "returnType": null, "doc": "<p>Asserts a regex pattern matches <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 uses <code>re.search</code> (substring-match by default per FR25's \"match\" terminology). Multi-line text supported via standard <code>re</code> flags in the pattern. NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>pattern</code></td>\n<td>Python <code>re</code> pattern. Use <code>(?i)</code> / <code>(?m)</code> / <code>(?s)</code> inline flags as needed.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the pattern does not match.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Released in 2020 \u2014 Robot Framework 3.x    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    20\\d{2}                          # 4-digit year \u2014 matches the echoed \"2020\".\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the regex assertion; <span class=\"name\">re.search</span> semantics (not <span class=\"name\">re.fullmatch</span>).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts a regex pattern matches ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 268}, {"name": "Agent Response Should Match Schema", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "schema", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "schema: dict[str, Any] | str | Path"}], "returnType": null, "doc": "<p>Asserts <code>response_text</code> parses as JSON + validates against a JSON Schema (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <code>mcp_coverage<span class=\"name\">`-gated. Parses </span>`response_text</code> as JSON, then validates against the schema via <code>jsonschema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code> (expected to be JSON-parsable).</td>\n</tr>\n<tr>\n<td><code>schema</code></td>\n<td>JSON Schema as a <code>dict</code> OR a file path (<code>str</code> / <code>pathlib.Path</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>schema</code> is not a <code>dict<span class=\"name\">`/</span><span class=\"name\">str</span><span class=\"name\">/</span>`Path</code>, or when the file is not a valid JSON schema dict. Raises <code>AssertionError</code> (redacted per FR38a) when <code>response_text</code> is not JSON-parsable. Raises <code>jsonschema.ValidationError</code> when the parsed JSON does not validate against the schema (preserves the jsonschema convention so consumers can catch the specific exception).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt={\"answer\": 42}    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${{ {\"type\": \"object\", \"required\": [\"answer\"]} }}\n# Path form: <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.</li>\n<li>Uses <code>jsonschema</code> package \u2014 the upstream <code>ValidationError</code> is preserved on validation failure (callers can catch specifically).</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex pattern).</li>\n</ul>", "shortdoc": "Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 301}, {"name": "Get Cohort Heatmap", "args": [{"name": "discoverability_result", "type": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "discoverability_result: DiscoverabilityResult"}, {"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "model_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "default", "kind": "NAMED_ONLY", "required": false, "repr": "model_name: str = default"}], "returnType": {"name": "CohortHeatmap", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds a <code>CohortHeatmap</code> from a <code>DiscoverabilityResult</code> (Story 8b.2 / FR55).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection over the result's <code>per_task_results</code>; no LLM calls. Returns a <code>CohortHeatmap</code> instance with <code>.as_ascii()</code> (box-drawing rendered grid) + <code>.as_dict()</code> (nested <code>{task: {model: pass_at_k}}</code> mapping) methods.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>discoverability_result</code></td>\n<td>Result from <span class=\"name\">MCP.Get Tool Discoverability</span> (Story 4.4 / FR10a). Carries <code>per_task_results</code> list of per-task <code>pass_rate</code> values.</td>\n</tr>\n<tr>\n<td><code>model_name</code></td>\n<td>Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to <code>\"default\"</code>.</td>\n</tr>\n</table>\n<p>Phase-1 scope: single-model heatmap (one column). Multi-model comparison (rows = tasks \u00d7 columns = models) is Phase-2 work. Missing cells render as <code>\" \u2014 \"</code> sentinel (em-dash with spaces) rather than silently substituting <code>0.0</code> per the Story 10.1 kilo/minimax review HIGH-1 honesty patch.</p>\n<p>Example:</p>\n<pre>\n${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()\n${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()\n${heatmap} =    <a href=\"#Get%20Cohort%20Heatmap\" class=\"name\">Get Cohort Heatmap</a>    ${disc}    model_name=claude-sonnet-4-5\n${ascii} =    Evaluate    $heatmap.as_ascii()\nLog    ${ascii}                                                                           # Box-drawing render.\n${cells} =    Evaluate    $heatmap.as_dict()\nShould Not Be Empty    ${cells}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 8b.2 ratifies the <code>CohortHeatmap</code> data class + <code>Get Cohort Heatmap</code> keyword surface.</li>\n<li>FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> produces the <code>DiscoverabilityResult</code> input.</li>\n</ul>", "shortdoc": "Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_heatmap/library.py", "lineno": 49}, {"name": "Get Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a Claude Code <code>settings.json</code> hook configuration.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per-entry validation per PRD FR4. Returns a dict mapping <code>hooks.&lt;event&gt;</code> \u2192 list of validated hook entries. Covered events: <code>PreToolUse</code>, <code>PostToolUse</code>, <code>Stop</code>; other events are passed through with the same validation. Median \u2264 50 ms on typical hook configs per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>settings.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Each returned entry has <code>command</code> (required) plus any of the optional fields <code>args</code> / <code>timeout</code> / <code>matcher</code> that were present in the source JSON. Entries whose command contains an inline YAML frontmatter block additionally surface an <code>inline_skill: dict</code> field with the parsed frontmatter.</p>\n<p>Raises <code>InvalidHookConfigError</code> on any structural failure (file not found, malformed JSON, missing <code>command</code>, wrong-type optional field). The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer (e.g. <code>/hooks/PreToolUse/0/command</code>) pinpointing the nested location. Format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>This keyword is re-exported through the top-level <code>AgentEval</code> library, so <code>AgentEval.Get Config</code> and <code>Hook.Get Config</code> (when imported as <code>WITH NAME    Hook</code>) resolve to the same implementation.</p>\n<p>Example:</p>\n<pre>\n${config} =    <a href=\"#Get%20Config\" class=\"name\">Get Config</a>    ${CURDIR}/.claude/settings.json\nLength Should Be    ${config}[hooks.PreToolUse]    1\nShould Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook\nShould Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop). Unknown events are validated with the same shape contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format: FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104. The <code>field_name</code> attribute on raised errors carries an RFC 6901 JSON Pointer.</li>\n<li>Inline-skill-frontmatter hooks are an extension surface \u2014 the inner skill is reachable via <span class=\"name\">SkillsLibrary</span> keywords passed the <code>inline_skill</code> dict directly.</li>\n</ul>", "shortdoc": "Parses a Claude Code ``settings.json`` hook configuration.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/hooks/library.py", "lineno": 66}, {"name": "Get Cost Total", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns total provider-reported USD cost (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (USD). Single run: the run's <code>cost_usd</code>. Multi-trial: sum across trials. Empty list \u2192 <code>0.0</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <code>mcp_coverage<span class=\"name\">`-gated. Returns </span>`0.0</code> on the Mock provider; non-zero on real adapters per Story 8a.1 (real adapters use <code>total_cost_usd</code> not <code>cost_usd</code>).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${cost_usd} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${result}\nShould Be True    ${cost_usd} &lt; 0.10                                      # Single-shot cost cap $0.10.\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${total_cost} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${results}                         # Cohort cost rollup.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the cost metric.</li>\n<li>Mock-provider runs return <code>0.0</code> cost; real adapters surface the provider's reported cost.</li>\n<li>Story 8a.1 v1 HIGH-1 ratified <code>total_cost_usd</code> as the canonical real-adapter key.</li>\n<li>Sibling keywords: <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns total provider-reported USD cost (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 419}, {"name": "Get Effective Config", "args": [{"name": "setting", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "setting: str | None = None"}], "returnType": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "doc": "<p>Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 two-form return: no-arg \u2192 <code>dict[str, Any]</code> of resolved values (Story 1a.6 ratified shape, backwards-compat with tier-1 + smoke tests); <code>setting=&lt;key&gt;</code> \u2192 <code>ConfigValue(value, source)</code> for that single setting (FR41 L1563). <code>source</code> is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>setting</code></td>\n<td>Optional config-key name (e.g., <code>\"max_cost_usd\"</code>). When <code>None</code> (default), returns the full <code>dict[str, Any]</code>. When set, returns the single <code>ConfigValue</code> for that key.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>setting</code> is set but not a known config key (with a sorted list of known keys in the message).</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0    telemetry=False\n${config} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>\nShould Be Equal As Numbers    ${config}[max_cost_usd]    5.0\nShould Be Equal    ${config}[telemetry]    ${FALSE}\n${cost_setting} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>    setting=max_cost_usd\nShould Be Equal As Numbers    ${cost_setting.value}    5.0\nShould Be Equal    ${cost_setting.source}    init_arg\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the ConfigValue surface; FR42 ratifies the 9 settings.</li>\n<li>Story 4.3 DF-4.3-S1 carry-over: full <code>dict[str, ConfigValue]</code> migration of the no-arg form is Phase-1.5.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a> for the FR41-compliant full-surface form.</li>\n</ul>", "shortdoc": "Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 398}, {"name": "Get Effective Config With Provenance", "args": [], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "ConfigValue", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the full settings map with per-key provenance as a <code>dict[str, ConfigValue]</code> (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 FR41-compliant surface. Each <code>ConfigValue</code> carries <code>value</code> + <code>source</code> per FR41 L1563. Source is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td>(none)</td>\n<td>Returns the full settings map; no arguments.</td>\n</tr>\n</table>\n<p>Defensive shallow-copy of the underlying provenance dict \u2014 caller mutations don't propagate to the Library's internal state.</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0\n${settings} =    <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a>\n${cost} =    Set Variable    ${settings}[max_cost_usd]\nShould Be Equal As Numbers    ${cost.value}    5.0\nShould Be Equal    ${cost.source}    init_arg                              # Constructor kwarg won.\n${temp} =    Set Variable    ${settings}[default_temperature]\nShould Be Equal    ${temp.source}    default                               # Not overridden \u2014 uses FR42 default.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the <code>dict[str, ConfigValue]</code> shape.</li>\n<li>This is the FR41-compliant surface DF-4.3-S1 will migrate <code>Get Effective Config</code> (no-arg) to once tier-1 tests update.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> for the simpler <code>dict[str, Any]</code> or per-setting form.</li>\n</ul>", "shortdoc": "Returns the full settings map with per-key provenance as a ``dict[str, ConfigValue]`` (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 517}, {"name": "Get Keyword Tier", "args": [{"name": "keyword", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the determinism-tier annotation for an RF keyword (PRD FR30a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int \u2208 {1, 2, 3}</code>. Walks the composed DynamicCore keyword registry + top-level methods to resolve the verbatim RF name to its <code>_agenteval_tier</code> integer via the <code>@tier(N)</code> decorator chain.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>Verbatim RF keyword name (e.g., <code>\"Send Prompt\"</code>, <code>\"Stat.Run N Times\"</code>, <code>\"Get Effective Config\"</code>).</td>\n</tr>\n</table>\n<p>Returns the wrapper's own tier, not the wrapped keyword's tier \u2014 e.g., <code>Stat.Run N Times</code> returns <code>3</code> (fan-out runner tier) per epic AC-5 + Story 6.3 D-14 amendment. The runner's tier governs the <code>@guarded_fanout</code> enforcement model, independent of the wrapped keyword's own classification.</p>\n<p>Raises <code>ValueError</code> when the keyword is not found in the composed library (with a sorted list of known keywords in the message), OR when the keyword has no <code>@tier(N)</code> annotation, OR when the annotated tier is outside <code>{1, 2, 3}</code> (defensive range check per Story 6.3 code-review HIGH-\u03c0 fix).</p>\n<p>Example:</p>\n<pre>\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Get Tool Call Count\nShould Be Equal As Integers    ${tier}    1                                # Tier-1 deterministic metric.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Send Prompt\nShould Be Equal As Integers    ${tier}    2                                # Tier-2 stochastic single-shot.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Stat.Run N Times\nShould Be Equal As Integers    ${tier}    3                                # Tier-3 fan-out runner.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR30a ratifies the tier-introspection contract; AC-6.3.7 establishes the DynamicCore walk.</li>\n<li>Story 6.3 D-14 amendment: fan-out runner reports its own tier (3), not the wrapped keyword's tier.</li>\n<li>Sibling keywords: every <span class=\"name\">@tier</span>-decorated keyword in the composed library is introspectable here.</li>\n</ul>", "shortdoc": "Returns the determinism-tier annotation for an RF keyword (PRD FR30a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 450}, {"name": "Get Last Warnings", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[dict]</code>. Each record has the FR62 ratified 5-field shape: <code>warning_type</code> (str \u2014 fully-qualified Python warning class), <code>message</code> (str \u2014 human- readable text), <code>source</code> (str \u2014 emitting subsystem), <code>timestamp</code> (str \u2014 UTC RFC 3339), <code>remediation</code> (str | None \u2014 actionable advice).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test via the listener context; returns <code>[]</code> if no test is bound. <code>\"all\"</code> \u2014 union across every per-test buffer in the process, sorted by <code>timestamp</code> ascending. Any other value is treated as a specific test_id (returns the named buffer or <code>[]</code> if absent).</td>\n</tr>\n</table>\n<p>Defensive copy of records. Never raises \u2014 buffer-read failures fall back to <code>[]</code>.</p>\n<p>Example:</p>\n<pre>\n@{warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>\nLength Should Be    ${warnings}    0                                                   # Clean run: zero warnings.\n@{all_warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>    test_id=all\nFOR    ${w}    IN    @{all_warnings}\n    Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR62 ratifies the 5-field <code>WarningRecord</code> shape.</li>\n<li>Story 5.4 ratified the per-test buffer + <code>\"all\"</code> aggregation contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> \u2014 companion trace-store accessors.</li>\n</ul>", "shortdoc": "Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 64}, {"name": "Get Latency", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns mean turn-level latency in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). When the run has no <code>tool_calls</code>, falls back to <code>result.latency_seconds * 1000.0</code>. Multi-trial: union-of- tool-calls mean \u2014 all per-tool-call latencies from all trials are flattened into one list before <code>statistics.mean()</code> is taken. Mean-of-per-run-means is a statistical anti-pattern (under-weights runs with more tool calls); union-then-mean is the operator-intuitive default per Story 6.1 code-review.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${latency_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${result}\nShould Be True    ${latency_ms} &lt; 2000                                    # Mean turn latency under 2 seconds.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the latency metric \u2014 per-tool-call resolution preferred over per-run.</li>\n<li>Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).</li>\n<li>Sibling keyword: <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a> for tail-latency tracking.</li>\n<li>Provider-reported scalar \u2014 observer-independent per AC-6.1.1.</li>\n</ul>", "shortdoc": "Returns mean turn-level latency in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 355}, {"name": "Get Latency P95", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the P95 latency across tool calls in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). AC-6.1.8 boundary conditions: 0 tool_calls \u2192 <code>0.0</code>; 1 tool_call \u2192 that single latency; \u22652 \u2192 <code>statistics.quantiles(n=100)[94]</code>. Multi-trial: P95 across the union of all tool_calls' latencies.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${p95_ms} =    <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>    ${results}\n${mean_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${results}\nShould Be True    ${p95_ms} &gt;= ${mean_ms}                                 # P95 \u2265 mean by definition.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the P95 metric \u2014 tail-latency tracking complements <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> mean.</li>\n<li>AC-6.1.8 boundary conditions cover empty / single-call edge cases.</li>\n<li>Sibling keywords: <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> for mean; <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> to generate multi-trial input.</li>\n</ul>", "shortdoc": "Returns the P95 latency across tool calls in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 389}, {"name": "Get Run Manifest", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "Union", "typedoc": null, "nested": [{"name": "RunManifest", "typedoc": null, "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "doc": "<p>Returns the in-memory 7-field <code>RunManifest</code> for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>RunManifest | None</code>. <code>None</code> when <code>test_id=\"current\"</code> and no test is bound (Tier-1 sibling-consistency with <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> / <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> / <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a> non-raising contracts). The in-memory manifest is the <b>*ratified 7-field shape*</b> (<code>library_version</code>, <code>test_id</code>, <code>suite_id</code>, <code>redaction_policy_hash</code>, <code>started_at</code>, <code>ended_at</code>, <code>agenteval_tier_breakdown</code>) \u2014 NOT the Story-5.3-extended operational metadata dict (which lives in the JSON sidecar at <code>&lt;output_dir&gt;/agenteval/manifest__&lt;suite&gt;__&lt;test&gt;.json</code>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>None</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim \u2014 that accessor's <code>ValueError</code> propagates if the explicit id resolves to None per Story 1b.2 semantics.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n${manifest} =    <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>\nShould Not Be Equal    ${manifest}    ${NONE}\nShould Not Be Empty    ${manifest.library_version}\nLength Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li>7-field shape ratified at Story 1b.2 per FR39.</li>\n<li>Story 5.5 code-review 2-way HIGH-F established the <code>None</code> (not raise) contract on no-bound-test current path.</li>\n<li>For the Story-5.3-extended operational shape, read the JSON sidecar directly.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 178}, {"name": "Get Spans", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ReadableSpan", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ReadableSpan]</code> in chronological order by <code>start_time</code>. Empty list is a valid state (test ran without emitting spans). Thin keyword wrapper around the <code>_kernel/trace_store.get_run_spans</code> projection accessor.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n@{spans} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>\nShould Not Be Empty    ${spans}\nFOR    ${span}    IN    @{spans}\n    ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}\n    Log    ${span.name} took ${duration_ns} ns\nEND\n@{spans_specific} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>    test_id=My Suite.Specific Test\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.</li>\n<li>Story 5.5 code-review 3-way HIGH-A established the no-bound-test \u2192 <code>[]</code> non-raising contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> (projection over execute_tool spans); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> (resource-attribute projection); <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 98}, {"name": "Get Token Usage", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "Usage", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Returns the agent's token usage as a <code>Usage</code> dataclass (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>Usage(input_tokens, output_tokens, cached_input_tokens)</code>. Single run: the run's own usage. Multi-trial: sum per field. Empty list \u2192 <code>Usage(0, 0, 0)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 observer-independent. NOT <span class=\"name\">`mcp_coverage</span>`-gated (PRD FR22 + AC-6.1.1).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${usage} =    <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>    ${result}\nShould Be True    ${usage.input_tokens} &gt; 0\nShould Be True    ${usage.output_tokens} &gt; 0\nLog    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the four usage metrics \u2014 <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>, <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a> \u2014 all observer-independent per AC-6.1.1.</li>\n<li><code>Usage</code> is a frozen dataclass; field validation ensures non-negative counts.</li>\n<li>Sibling keywords: <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 324}, {"name": "Get Tool Call Count", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the number of tool calls made by the agent (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int</code>. Single run: <code>len(result.tool_calls)</code>. Multi-trial: sum across trials.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial sum aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code> (default-deny per FR42).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${count} =    <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a>    ${result}\nShould Be Equal As Integers    ${count}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42 \u2014 opt out via <code>AgentEval(allow_external_mcp_blind=True)</code>.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a> for the ordered names list.</li>\n</ul>", "shortdoc": "Returns the number of tool calls made by the agent (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 92}, {"name": "Get Tool Call Names", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns tool-call names in chronological order (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 duplicates preserved per FR19 verbatim (\"list[str] (preserving order)\"). Single run: chronological list. Multi-trial: union preserving order-of-first-appearance.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial union aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n@{names} =    <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a>    ${result}\nShould Contain    ${names}    web_search\nShould Be Equal    ${names}[0]    web_search                              # First tool called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> for the count; <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> for expected-set comparison.</li>\n</ul>", "shortdoc": "Returns tool-call names in chronological order (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 132}, {"name": "Get Tool Calls", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ToolCallTrace", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns <code>ToolCallTrace</code> records projected from the trace store (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ToolCallTrace]</code>. Thin keyword wrapper around <code>_kernel/trace_store.get_tool_calls</code>. Mirrors the source-filtering semantics of the Story 1b.2 accessor (no per-call source filter exposed at the RF surface; consumers filter the returned list themselves).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Returns <code>list[ToolCallTrace]</code> frozen dataclasses (Story 1b.2 shape): each record carries <code>name</code>, <code>args</code>, <code>result</code>, <code>error</code>, <code>latency_ms</code>, <code>source</code>, <code>gen_ai_tool_call_id</code>, <code>sequence_index</code>.</p>\n<p>Example:</p>\n<pre>\n@{tool_calls} =    <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>\nShould Not Be Empty    ${tool_calls}\nShould Be Equal    ${tool_calls}[0].name    web_search\nShould Be Equal As Integers    ${tool_calls}[0].sequence_index    0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li><span class=\"name\">ToolCallTrace</span> shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> (full span list); <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> (metrics-library count over <span class=\"name\">AgentRunResult</span>); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>.</li>\n</ul>", "shortdoc": "Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 139}, {"name": "Get Tool Hit Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-hit rate <code>|expected \u2229 observed| / |expected|</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Empty <code>expected_tools</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: union-of-observed against expected_tools.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${hit_rate} =    <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a>    ${result}    ${{['web_search', 'fetch']}}\nShould Be True    ${hit_rate} &gt;= 0.5                                      # At least half of expected tools were called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keywords: <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a> (calls NOT in expected set); <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a> (errors / total).</li>\n</ul>", "shortdoc": "Returns the tool-hit rate ``|expected \u2229 observed| / |expected|`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 178}, {"name": "Get Tool Success Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-success rate <code>non-error / total</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: aggregate across all per-trial tool calls.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${success_rate} =    <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a>    ${result}\nShould Be True    ${success_rate} &gt;= 0.8                                  # At least 80% of tool calls succeeded.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Each <code>ToolCallTrace</code> has an <code>error</code> field \u2014 non-None counts as a failure.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (vs expected set); <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>.</li>\n</ul>", "shortdoc": "Returns the tool-success rate ``non-error / total`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 224}, {"name": "Get Unnecessary Call Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the unnecessary-call rate <code>not_in_expected / total</code> (PRD FR21).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${noise} =    <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>    ${result}    ${{['web_search']}}\nShould Be True    ${noise} &lt;= 0.2                                         # At most 20% of calls were off-task.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR21 ratifies the unnecessary-rate formula \u2014 quantifies \"noise\" tool calls beyond the expected set.</li>\n<li>AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls \u2192 0.0).</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (calls that ARE in expected set).</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n</ul>", "shortdoc": "Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 271}, {"name": "Judge.Calibrate Rubric", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "calibration_set", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "calibration_set: str | Path"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "CalibrationReport", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs the judge against a labeled calibration set and returns a <span class=\"name\">CalibrationReport</span> (Story 12.2).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 N single-shot LLM calls (one per calibration row) against the configured <code>judge_adapter</code>. Cohen's kappa over binarized judge-pass / human-pass labels at the rubric's threshold; <code>passes_hard_fail</code> is True iff <code>kappa &gt;= 0.7</code> per <span class=\"name\">architecture.md</span> L199 agentguard-borrowed calibration discipline. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>calibration_set</code></td>\n<td>Path to a YAML calibration set with <span class=\"name\">rows:</span> list of <span class=\"name\">{prompt, response, human_label}</span>.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug; defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier; forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Returns <code>CalibrationReport</code> with: <code>cohen_kappa</code> (float; <code>nan</code> if zero-variance), <code>passes_hard_fail</code> (kappa &gt;= 0.7), <code>threshold_tuning</code> (precision/recall/F1 sweep), <code>recommended_threshold</code> (F1-maximizing), <code>systematic_bias_diagnostics</code> (human-readable bullets), <code>total_cost_usd</code>, <code>total_latency_seconds</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>InvalidCalibrationSetError</code> on calibration set parse failure. Raises <code>JudgeOutputParseError</code> if any per-row judge invocation returns malformed JSON.</p>\n<p>Example:</p>\n<pre>\n${report} =    <a href=\"#Judge.Calibrate%20Rubric\" class=\"name\">Judge.Calibrate Rubric</a>    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${report.passes_hard_fail}\nLog    Cohen's kappa = ${report.cohen_kappa}\nLog    Recommended threshold = ${report.recommended_threshold}\n</pre>\n<p>Notes:</p>\n<ul>\n<li><span class=\"name\">KAPPA_HARD_FAIL_THRESHOLD = 0.7</span> per <span class=\"name\">architecture.md</span> L199.</li>\n<li>Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.</li>\n<li>Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.</li>\n</ul>", "shortdoc": "Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).", "tags": ["agenteval"], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 187}, {"name": "Judge.Get Score", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "result: AgentRunResult"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "JudgeScore", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Evaluates an <span class=\"name\">AgentRunResult</span> against a Markdown rubric using an LLM judge (PRD FR48).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 single-shot LLM call against the configured <span class=\"name\">judge_adapter</span> (default <span class=\"name\">\"generic\"</span> LiteLLM-backed). LLM-deterministic per the determinism-contract.md <span class=\"name\">@tier(2)</span> contract when invoked with <span class=\"name\">seed + temperature=0</span>. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>The <span class=\"name\">AgentRunResult</span> to evaluate. Reads <code>result.response_text</code> for the agent's output.</td>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug to resolve via <span class=\"name\">agenteval.coding_agents</span> entry-points. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier for the judge adapter (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>). Forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs (e.g., <code>temperature=0.0</code>, <code>seed=42</code>).</td>\n</tr>\n</table>\n<p>Returns <code>JudgeScore</code> with: <code>numeric_score</code> (0-10), <code>pass_threshold_met</code> (vs rubric threshold), <code>reasoning</code> (LLM's narrative explanation), <code>criteria_breakdown</code> (per-criterion sub-scores), <code>cost_usd</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>JudgeOutputParseError</code> when the LLM response is not valid JSON OR is missing required fields OR <code>numeric_score</code> is outside <code>[0.0, 10.0]</code>.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6\n${score} =    <a href=\"#Judge.Get%20Score\" class=\"name\">Judge.Get Score</a>    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${score.pass_threshold_met}\nShould Be True    ${score.numeric_score} &gt;= 7.0\nLog    Reasoning: ${score.reasoning}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR48 ratifies the keyword + rubric calibration discipline.</li>\n<li>Tier-2 LLM-deterministic per <span class=\"name\">determinism-contract.md</span>; cost guardrails per ADR-015.</li>\n<li><span class=\"name\">JudgeScore</span> shape ratified Story 12.1 AC-12.1.2 per architecture L1316.</li>\n<li>Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.</li>\n</ul>", "shortdoc": "Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 117}, {"name": "Load Scenario", "args": [{"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "scenario: str"}], "returnType": {"name": "Scenario", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Loads + validates a scenario YAML without executing it.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file read + YAML parse + schema validation. Returns the parsed <code>Scenario</code> dataclass without dispatching to any adapter \u2014 useful for <code>.robot</code> tests that assert on scenario metadata or pre-flight-check scenarios before a <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidScenarioYAMLError</code> on parse failure or schema violation. The error's <code>field_name</code> attribute pinpoints the offending field per FR59.</p>\n<p>Example:</p>\n<pre>\n${scenario} =    <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a>    ${CURDIR}/scenarios/web-search.yaml\nShould Be Equal    ${scenario.agent}    web-search-agent\nShould Be Equal    ${scenario.model}    anthropic/claude-sonnet-4-6\nLength Should Be    ${scenario.evals}    5\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the scenario YAML schema; see <span class=\"name\">Scenario</span> dataclass in <span class=\"name\">scenarios/schema.py</span>.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> (Tier-3) for dispatch + execution.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n</ul>", "shortdoc": "Loads + validates a scenario YAML without executing it.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 330}, {"name": "Run Scenario", "args": [{"name": "adapter", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "_Unset", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str | _Unset = _UNSET"}, {"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "scenario: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Executes a scenario YAML file's <code>evals[]</code> against an adapter (PRD FR15).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 loads the scenario YAML via <code>load_scenario()</code>, validates against the <code>Scenario</code> schema, then dispatches each eval's prompt to <code>adapter.run()</code> <code>repeat</code> times. Returns a flat <code>list[AgentRunResult]</code> of length <code>sum(eval.repeat for eval in scenario.evals)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Per-scenario <code>agent:</code> field in the YAML overrides this kwarg per FR15 (\"scenario YAML specifies agent\" \u2014 YAML beats default but not explicit kwarg).</td>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code>. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are split between adapter constructor + <code>run()</code> per the same signature-introspection rule as <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>. Scenario-YAML <code>model:</code> / <code>provider:</code> fields inject into the merged kwargs unless the caller already passed them.</p>\n<p>Raises <code>InvalidScenarioYAMLError</code> on YAML parse / schema failure, <code>AdapterDiscoveryError</code> on unknown adapter name, and <code>NotImplementedError</code> on non-empty comma-separated <code>mcp_servers</code> (Phase-1 DF-4.3-S2 carve-out).</p>\n<p>Example:</p>\n<pre>\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    scenario=${CURDIR}/scenarios/web-search.yaml\nLength Should Be    ${results}    5\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the multi-eval orchestration contract.</li>\n<li>FR41 precedence resolution: explicit kwarg &gt; scenario YAML &gt; library default.</li>\n<li>Sibling keyword: <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a> (Tier-1) to validate the YAML without executing.</li>\n<li>Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).</li>\n</ul>", "shortdoc": "Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 215}, {"name": "Send Prompt", "args": [{"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "prompt: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Executes a single-shot prompt against a coding-agent adapter (PRD FR14).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 invokes the named adapter's <code>run()</code> method per the <span class=\"name\">CodingAgentAdapter</span> Protocol. Returns an <code>AgentRunResult</code> carrying <code>response_text</code>, <code>tool_calls</code>, <code>usage</code>, <code>metadata</code> (with <code>completeness</code> + <code>mcp_coverage</code>), <code>cost_usd</code>, <code>latency_seconds</code>, and <code>trace_id</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code> (LiteLLM-backed).</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code> of attached MCP servers. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2 \u2014 name resolution to handles deferred).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are forwarded to the adapter \u2014 caller kwargs that match the adapter's <code>__init__</code> signature flow to construction; the rest flow to <code>run()</code>. Useful for <code>model=\"anthropic/claude-sonnet-4-6\"</code>, <code>temperature=0.5</code>, etc.</p>\n<p>Raises <code>AdapterDiscoveryError</code> when the <code>adapter</code> name is not registered. Raises <code>NotImplementedError</code> on comma-separated <code>mcp_servers</code> name strings until DF-4.3-S2 lands the name \u2192 handle resolver (pass <code>mcp_servers={'name': handle}</code> directly to forward Phase-1).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Hello, world.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=claude-code-cli    prompt=Run the build.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR14 ratifies the single-prompt orchestration contract.</li>\n<li>Adapter discovery per Story 1b.3 + ADR-013 entry-points.</li>\n<li><code>cost_usd</code> is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> for multi-eval YAML-driven dispatch (Tier-3).</li>\n</ul>", "shortdoc": "Executes a single-shot prompt against a coding-agent adapter (PRD FR14).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 127}, {"name": "Stat.Assert Run Determinism", "args": [{"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "expect", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "byte_identical", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "expect: str = byte_identical"}], "returnType": null, "doc": "<p>Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 invokes the wrapped keyword twice with identical inputs and compares via deep-equality. The bit-identical guarantee is scoped to Tier-1 keywords only (FR31a contract); the keyword raises <code>TierViolationError</code> if a Tier-2/3 keyword is passed.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR callable. Same dispatch rules as <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> (string form requires active RF context).</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings.</td>\n</tr>\n<tr>\n<td><code>expect</code></td>\n<td>Comparison mode. Phase-1 supports <code>\"byte_identical\"</code> only; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> deferred to Phase-2.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>expect != \"byte_identical\"</code> (Phase-1 scope). Raises <code>TierViolationError</code> when the wrapped keyword is not Tier-1 \u2014 FR31a is scoped to Tier-1 only. Raises <code>AssertionError</code> on output mismatch with a <span class=\"name\">`redact()</span>`-scrubbed diff per FR38a credential-safety contract.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Effective Config\nRun Keyword And Expect Error    TierViolationError*    <a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Send Prompt\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> + <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for statistical assertions instead.</li>\n<li>Diff redaction per FR38a + Story 5.3 \u2014 credentials in args / output don't leak into RF logs.</li>\n<li>Story 6.3 ratifies <code>\"byte_identical\"</code> as the Phase-1 contract; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> are Phase-2 work-items.</li>\n</ul>", "shortdoc": "Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 270}, {"name": "Stat.Get Pass At K", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form computation of the HumanEval estimator <code>1 - C(n-c, k) / C(n, k)</code>. Returns <code>float \u2208 [0, 1]</code>. Scalar return preserves AssertionEngine compatibility (<code>&gt;=</code> / <code>&lt;=</code> matchers); CI is a separate paired getter \u2014 see <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Must satisfy <code>1 &lt;= k &lt;= len(runs)</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Default checks <code>r.completeness == \"complete\"</code> per epic AC-2 + Story 6.4 fix-NOW.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k &lt; 1</code>, <code>k &gt; len(runs)</code>, or <code>len(runs) == 0</code>.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${pass_at_1} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=1\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.\n${pred} =    Evaluate    lambda r: r.error is None\n${pass_strict} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5    predicate=${pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR27 ratifies the scalar <code>float</code> return type \u2014 no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).</li>\n<li>Default predicate updated by Story 6.4 fix-NOW: <code>completeness == \"complete\"</code> (pre-edit <code>\"full\"</code> was fake-green; <span class=\"name\">AgentRunMetadata._VALID_COMPLETENESS</span> is <code>{\"complete\", \"truncated\", \"partial\"}</code>).</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a> for the Wilson score CI.</li>\n</ul>", "shortdoc": "Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 172}, {"name": "Stat.Get Pass At K Confidence Interval", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}, {"name": "confidence", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.95", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "confidence: float = 0.95"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Wilson score interval at the given <code>confidence</code> level for the latent per-trial success probability. Returns <code>(ci_lower, ci_upper)</code> tuple of <code>float</code> in <code>[0, 1]</code>. Paired with <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> \u2014 the scalar point estimate plus this CI together satisfy epic AC-2's \"Pass@k with confidence interval\" promise.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Validated for <code>1 &lt;= k &lt;= len(runs)</code> but only used for sanity check \u2014 the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Same default as <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>.</td>\n</tr>\n<tr>\n<td><code>confidence</code></td>\n<td>Confidence level in <code>(0, 1)</code>. Defaults to <code>0.95</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k</code> is non-positive or <code>k &gt; n</code> (with <code>n &gt; 0</code> \u2014 empty <code>runs</code> is permitted per the Wilson formula).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5\nShould Be True    0.0 &lt;= ${ci_lo} &lt;= ${ci_hi} &lt;= 1.0                      # CI bounds are well-formed probabilities.\n${ci99_lo}    ${ci99_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5    confidence=0.99\nShould Be True    (${ci99_hi} - ${ci99_lo}) &gt;= (${ci_hi} - ${ci_lo})      # Higher confidence \u2192 wider interval.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.</li>\n<li>PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for the scalar point estimate.</li>\n</ul>", "shortdoc": "Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 214}, {"name": "Stat.Run N Times", "args": [{"name": "n", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "n: int"}, {"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "seed", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "int", "typedoc": "integer", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "seed: int | None = None"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Runs a keyword <code>n</code> times independently and returns the per-trial results (PRD FR26).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 wraps the target keyword in independent trials. Returns <code>list[KeywordRun]</code> of length <code>n</code>. Trial-level errors are re-raised from this keyword \u2014 wrap in <code>Run Keyword And Ignore Error</code> for \"ignore failures\" semantics.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>n</code></td>\n<td>Number of independent trials. Must be <code>&gt;= 1</code>.</td>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR a Python callable. String form requires an active RF execution context (resolved via <code>BuiltIn</code>); callable form is useful for pytest unit tests.</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings (e.g. <code>{\"adapter\": \"generic\", \"prompt\": \"Hi\"}</code> or <code>[\"adapter=generic\", \"prompt=Hi\"]</code>). <code>None</code> = no args.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>Optional <code>int</code> seed; each trial receives <code>seed + trial_index</code> via a <code>seed=</code> kwarg injection so trials are deterministic but distinct. <code>None</code> = OS-entropy seeding per trial.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>n &lt; 1</code>. Raises <code>CostExceededError</code> / <code>RuntimeBudgetExceededError</code> per the <code>@guarded_fanout</code> 3-layer enforcement.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= 0.6\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the <code>list[KeywordRun]</code> return type.</li>\n<li>Cost / runtime guardrails per ADR-015 + <span class=\"name\">_kernel/guardrails.py::@guarded_fanout</span>.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> (Tier-1) consumes the returned list.</li>\n</ul>", "shortdoc": "Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 86}, {"name": "Tool Call Should Have Occurred", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "tool", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool: str"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: dict[str, Any] | None = None"}, {"name": "match_mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "subset", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "match_mode: str = subset"}], "returnType": null, "doc": "<p>Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 searches all observed <code>tool_calls</code> for one matching <code>tool</code> + (optionally) <code>args</code>. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>tool</code></td>\n<td>Expected tool name (exact-match required).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>Optional dict of expected args. <code>None</code> (default) = name-only match.</td>\n</tr>\n<tr>\n<td><code>match_mode</code></td>\n<td><code>\"subset\"</code> (default \u2014 <code>args</code> is a dict-subset of <code>tc.args</code>; recursive for nested dicts) OR <code>\"exact\"</code> (<code>tc.args == args</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>match_mode</code> is invalid (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> when no tool call matches.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected <code>web_search</code> call):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"agenteval\"} }}\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"x\"} }}    match_mode=exact\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR24 ratifies the name + args + match-mode contract.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a> for ordered-sequence assertions over multiple calls.</li>\n</ul>", "shortdoc": "Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 162}, {"name": "Trajectory Should Match", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "expected", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected: list[str]"}, {"name": "mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "exact", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mode: str = exact"}], "returnType": null, "doc": "<p>Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 four match modes available. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a so credentials in tool args don't leak into RF logs.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>expected</code></td>\n<td>List of expected tool names (or regex patterns when <code>mode=\"regex\"</code>).</td>\n</tr>\n<tr>\n<td><code>mode</code></td>\n<td>Match mode: <code>\"exact\"</code> (ordered equality) / <code>\"subsequence\"</code> (ordered, extras allowed between) / <code>\"set\"</code> (unordered set-equality of distinct names) / <code>\"regex\"</code> (each <code>expected[i]</code> is a <code>re.fullmatch</code> pattern against <code>&lt;tool&gt;:&lt;json.dumps(args, sort_keys=True)&gt;</code>). Default <code>\"exact\"</code>.</td>\n</tr>\n</table>\n<p>Set-mode caveat: duplicate names collapse \u2014 <code>[\"a\", \"a\"]</code> set- equals <code>[\"a\"]</code>. Operators wanting multiset semantics (\"exactly N calls of tool X\") should use <code>mode=\"exact\"</code>.</p>\n<p>Raises <code>ValueError</code> when <code>mode</code> is not one of the 4 documented values (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> on trajectory mismatch.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected 3-call trajectory):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'fetch', 'summarize']}}\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['fetch', 'web_search']}}    mode=set\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR23a + FR23b ratify the 4 match modes.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a> for single-call name+args assertions.</li>\n</ul>", "shortdoc": "Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 86}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config", "Get Last Warnings", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["__init__", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config With Provenance", "Get Last Warnings", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["__init__", "Get Cost Total", "Get Latency", "Get Latency P95", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Keyword Tier", "Get Tool Call Count", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Config", "Get Cost Total", "Get Last Warnings", "Get Latency", "Get Latency P95", "Get Spans", "Get Token Usage", "Get Tool Call Count", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Run Scenario", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Trajectory Should Match"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["__init__"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["__init__", "Get Effective Config", "Get Run Manifest", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Judge.Calibrate Rubric", "Judge.Get Score"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["__init__", "Agent Response Should Contain", "Agent Response Should Match Regex", "Agent Response Should Match Schema", "Get Cohort Heatmap", "Get Config", "Get Effective Config", "Get Effective Config With Provenance", "Get Keyword Tier", "Get Last Warnings", "Get Run Manifest", "Get Spans", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Unnecessary Call Rate", "Judge.Calibrate Rubric", "Judge.Get Score", "Load Scenario", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred", "Trajectory Should Match"], "accepts": ["Any"]}, {"type": "Standard", "name": "tuple", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> or <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible lists converted further to tuples. They can contain any values <code>ast.literal_eval</code> supports, including tuples and other collections.</p>\n<p>If the argument is a tuple, it is used without conversion. Lists and other sequences are converted to tuples.</p>\n<p>If the type has nested types like <code>tuple[str, int, int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>('one', 'two')</code>, <code>(('one', 1), ('two', 2))</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for list literals is new in Robot Framework 7.4.</p>", "usages": ["Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Sequence"]}]}
    10	</script>
    11	<link rel=icon type=image/x-icon href="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKcAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAAqAAAAAAAAAAAAAAAAAAAALIAAAD/AAAA4AAAANwAAADcAAAA3AAAANwAAADcAAAA3AAAANwAAADcAAAA4AAAAP8AAACxAAAAAAAAAKYAAAD/AAAAuwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC/AAAA/wAAAKkAAAD6AAAAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN8AAAD/AAAA+gAAAMMAAAAAAAAAAgAAAGsAAABrAAAAawAAAGsAAABrAAAAawAAAGsAAABrAAAADAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAIsAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAANEAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAAAAAAAAMgAAADIAAAAyAAAAMgAAADIAAAAyAAAAMgAAADIAAAAFAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAADwAAAB8AAAAAAAAAGAAAABcAAAAAAAAAH8AAABKAAAAAAAAAAAAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAADCAAAA/wAAACkAAADqAAAA4QAAAAAAAAD7AAAA/wAAALAAAAAGAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAIwAAAP4AAAD/AAAA/wAAAGAAAAAAAAAAAAAAAMkAAAD/AAAAigAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAAAAAAAIAAAAcAAAABkAAAAAAAAAAAAAAAAAAAAAAAAAEgAAAAAAAAAAAAAA2gAAAP8AAAD7AAAAywAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN4AAAD/AAAAqwAAAP8AAACvAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALIAAAD/AAAAsgAAAAAAAAC5AAAA/wAAAMoAAADAAAAAwAAAAMAAAADAAAAAwAAAAMAAAADAAAAAwAAAAMkAAAD/AAAAvAAAAAAAAAAAAAAAAAAAAKwAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAArQAAAAAAAAAAwAMAAIABAAAf+AAAP/wAAD/8AAAgBAAAP/wAAD/8AAA//AAAJIwAADHEAAA//AAAP/wAAB/4AACAAQAAwAMAAA==">
    12	</head>

codex
### HIGH-1: OTLP egress persists after switching back to `memory`

**File:** `src/AgentEval/telemetry/listener.py:336`
**Issue:** `_attach_otlp_exporter_if_needed()` only guards duplicate attachment; it never detaches or replaces the OTLP processor when a later suite/listener resolves `trace_backend="memory"`. In a reused Python process, one earlier OTLP run leaves a live `BatchSpanProcessor(OTLPSpanExporter)` behind, so later “memory-only” runs still emit network traffic, violating PRD NFR-SEC-05’s opt-in egress contract.
**Evidence:**
```python
if getattr(provider, "_agenteval_otlp_attached", False):
    return
provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))
provider._agenteval_otlp_attached = True
```
```text
processors after switching to memory: 4
0 TestIdContextSpanProcessor None
1 RedactionProcessor None
2 SimpleSpanProcessor None
3 BatchSpanProcessor http://first.example:4318/v1/traces
```
**Fix:** Track the attached OTLP processor instance and remove/replace it when the resolved backend is no longer `otlp`, or rebuild the provider when backend mode changes.

### HIGH-2: Endpoint changes are ignored after the first OTLP attachment

**File:** `src/AgentEval/telemetry/listener.py:336`
**Issue:** The process-scope sentinel is keyed only on “OTLP already attached”, not on which endpoint/exporter is attached. A second `Listener` in the same process can resolve a different `AGENTEVAL_OTLP_ENDPOINT`, but spans still export to the first endpoint.
**Evidence:**
```text
after first attach 4
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
after second attach 4
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
listener2 backend exporter endpoint http://second.example:4318/v1/traces
```
**Fix:** Store the active OTLP endpoint/exporter on the provider and replace the processor when the requested endpoint differs; add a regression test with two listeners using distinct endpoints.

### HIGH-3: Exported spans use `service.name=unknown_service`, not `robotframework-agenteval`

**File:** `src/AgentEval/telemetry/listener.py:275`
**Issue:** The listener creates `Resource.create({})`, which leaves OpenTelemetry’s default `service.name` as `unknown_service`. That contradicts the documented observability contract in [`docs/contracts/otel-trace-visual.md`](/home/many/workspace/robotframework-agenteval/docs/contracts/otel-trace-visual.md:104) and breaks dashboard/query recipes expecting `service.name=robotframework-agenteval`.
**Evidence:**
```python
resource = Resource.create({})
```
```text
{'telemetry.sdk.language': 'python',
 'telemetry.sdk.name': 'opentelemetry',
 'telemetry.sdk.version': '1.41.1',
 'service.name': 'unknown_service'}
```
**Fix:** Build the provider resource with an explicit `{"service.name": "robotframework-agenteval"}` merged into the default resource, and assert it in OTLP tests.

### MED-1: The OTLP E2E tests do not verify the payload contract they claim to cover

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:114`
**Issue:** The story/dev record claims collector readback verifies specific exported content, but the actual tests only prove “some span arrived” plus a name check, and only the HTTP variant checks one attribute key. The gRPC variant does not verify `agenteval.tier`, resource attrs, or `service.name` at all.
**Evidence:**
```python
assert len(spans) >= 1
assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)

assert len(spans) >= 1
assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)
```
**Fix:** Assert on the exact emitted span in both variants: `service.name`, tracer scope, expected attributes, and transport-specific endpoint behavior.

### LOW-1: Generated keyword docs were not regenerated for the new public `otlp_endpoint` surface

**File:** `docs/keywords/AgentEval.html:9`
**Issue:** The committed libdoc is still generated from 2026-05-27 and does not include `otlp_endpoint`, so public docs do not match the new constructor signature shipped by Story 13.2.
**Evidence:**
```text
"generated": "2026-05-27T19:45:45+00:00"
...
"repr": "max_runtime_seconds: float | None = _UNSET"
```
```text
otlp_endpoint present? False
```
**Fix:** Regenerate `docs/keywords/AgentEval.html` after public API changes and add a docs check that catches stale libdoc artifacts.

**Total: 3 HIGH + 1 MED + 1 LOW**
tokens used
167,086
### HIGH-1: OTLP egress persists after switching back to `memory`

**File:** `src/AgentEval/telemetry/listener.py:336`
**Issue:** `_attach_otlp_exporter_if_needed()` only guards duplicate attachment; it never detaches or replaces the OTLP processor when a later suite/listener resolves `trace_backend="memory"`. In a reused Python process, one earlier OTLP run leaves a live `BatchSpanProcessor(OTLPSpanExporter)` behind, so later “memory-only” runs still emit network traffic, violating PRD NFR-SEC-05’s opt-in egress contract.
**Evidence:**
```python
if getattr(provider, "_agenteval_otlp_attached", False):
    return
provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))
provider._agenteval_otlp_attached = True
```
```text
processors after switching to memory: 4
0 TestIdContextSpanProcessor None
1 RedactionProcessor None
2 SimpleSpanProcessor None
3 BatchSpanProcessor http://first.example:4318/v1/traces
```
**Fix:** Track the attached OTLP processor instance and remove/replace it when the resolved backend is no longer `otlp`, or rebuild the provider when backend mode changes.

### HIGH-2: Endpoint changes are ignored after the first OTLP attachment

**File:** `src/AgentEval/telemetry/listener.py:336`
**Issue:** The process-scope sentinel is keyed only on “OTLP already attached”, not on which endpoint/exporter is attached. A second `Listener` in the same process can resolve a different `AGENTEVAL_OTLP_ENDPOINT`, but spans still export to the first endpoint.
**Evidence:**
```text
after first attach 4
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
after second attach 4
3 BatchSpanProcessor OTLPSpanExporter http://first.example:4318/v1/traces
listener2 backend exporter endpoint http://second.example:4318/v1/traces
```
**Fix:** Store the active OTLP endpoint/exporter on the provider and replace the processor when the requested endpoint differs; add a regression test with two listeners using distinct endpoints.

### HIGH-3: Exported spans use `service.name=unknown_service`, not `robotframework-agenteval`

**File:** `src/AgentEval/telemetry/listener.py:275`
**Issue:** The listener creates `Resource.create({})`, which leaves OpenTelemetry’s default `service.name` as `unknown_service`. That contradicts the documented observability contract in [`docs/contracts/otel-trace-visual.md`](/home/many/workspace/robotframework-agenteval/docs/contracts/otel-trace-visual.md:104) and breaks dashboard/query recipes expecting `service.name=robotframework-agenteval`.
**Evidence:**
```python
resource = Resource.create({})
```
```text
{'telemetry.sdk.language': 'python',
 'telemetry.sdk.name': 'opentelemetry',
 'telemetry.sdk.version': '1.41.1',
 'service.name': 'unknown_service'}
```
**Fix:** Build the provider resource with an explicit `{"service.name": "robotframework-agenteval"}` merged into the default resource, and assert it in OTLP tests.

### MED-1: The OTLP E2E tests do not verify the payload contract they claim to cover

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:114`
**Issue:** The story/dev record claims collector readback verifies specific exported content, but the actual tests only prove “some span arrived” plus a name check, and only the HTTP variant checks one attribute key. The gRPC variant does not verify `agenteval.tier`, resource attrs, or `service.name` at all.
**Evidence:**
```python
assert len(spans) >= 1
assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)

assert len(spans) >= 1
assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)
```
**Fix:** Assert on the exact emitted span in both variants: `service.name`, tracer scope, expected attributes, and transport-specific endpoint behavior.

### LOW-1: Generated keyword docs were not regenerated for the new public `otlp_endpoint` surface

**File:** `docs/keywords/AgentEval.html:9`
**Issue:** The committed libdoc is still generated from 2026-05-27 and does not include `otlp_endpoint`, so public docs do not match the new constructor signature shipped by Story 13.2.
**Evidence:**
```text
"generated": "2026-05-27T19:45:45+00:00"
...
"repr": "max_runtime_seconds: float | None = _UNSET"
```
```text
otlp_endpoint present? False
```
**Fix:** Regenerate `docs/keywords/AgentEval.html` after public API changes and add a docs check that catches stale libdoc artifacts.

**Total: 3 HIGH + 1 MED + 1 LOW**
