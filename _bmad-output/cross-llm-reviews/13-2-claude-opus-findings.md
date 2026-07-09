I have enough verified evidence. Let me confirm the shipped e2e test dropped the spec's `service.name` assertion and finalize.

The key facts are confirmed:
- `src/AgentEval/telemetry/listener.py:275` → `Resource.create({})` → `service.name='unknown_service'` (verified empirically).
- No code anywhere sets `service.name="robotframework-agenteval"`.
- The shipped `test_otlp_export_e2e.py` asserts span name + `agenteval.tier` but **not** `service.name` — whereas the AC-13.2.8 spec example explicitly asserted `service.name == "robotframework-agenteval"`.
- gRPC exporter stores `_endpoint`/`_insecure` (assertable), but tests assert neither.

---

# Adversarial Code Review — Story 13.2: OTLP Trace Backend (FR33b)

### [HIGH]-1: OTLP-exported spans carry `service.name="unknown_service"`, not `"robotframework-agenteval"` — the feature's core observability promise is broken and the docs/ADR/carry-over assert a value that is never set

**File:** `src/AgentEval/telemetry/listener.py:275` (resource) + `docs/adr/ADR-001...md` row + `docs/phase-1-5-carry-overs.md` C86 + `tests/integration/telemetry/test_otlp_export_e2e.py`

**Issue:** Story 13.2's entire value proposition (FR33b: "traces flow into Jaeger / Honeycomb / Tempo for production observability") depends on spans being discoverable by service name. The TracerProvider resource is `Resource.create({})`, which the OTel SDK resolves to `service.name="unknown_service"` (verified below). **Nothing in the codebase sets `service.name="robotframework-agenteval"`.** Yet the story asserts the opposite in four places:
- ADR-001 new row rationale: *"would diverge from `service.name="robotframework-agenteval"` resource conventions"* — implies it IS set.
- Carry-over **C86**: *"Story 13.2 ships OTLPBackend with `service.name="robotframework-agenteval"` ... baked into the Listener's resource"* — false; C86 is built on a non-existent premise.
- AC-13.2.8 spec example asserted `s["resource"]["attributes"]["service.name"] == "robotframework-agenteval"`.
- The new recipe cross-links `otel-trace-visual.md`, which tells users to open Jaeger at `?service=robotframework-agenteval` — which will return **zero** spans for natively-exported traces.

Critically, the **shipped** e2e test silently dropped the spec's `service.name` assertion (it would have failed) — a weakened-test that papers over the gap, and it's docker-gated/skipped so it never runs in CI anyway.

**Evidence:**
```
$ uv run python -c "from opentelemetry.sdk.resources import Resource; print(Resource.create({}).attributes.get('service.name'))"
unknown_service
```
```
$ grep -rn "service.name\|robotframework-agenteval" src/AgentEval/telemetry/
listener.py:275:        resource = Resource.create({})          # <-- empty; no service.name
(no occurrence sets service.name="robotframework-agenteval")
```
Shipped test asserts only:
```python
assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)
# spec's `service.name == "robotframework-agenteval"` assertion: DROPPED
```

**Fix:** Set the resource explicitly so exported spans are discoverable:
```python
resource = Resource.create({"service.name": "robotframework-agenteval"})
```
(Story 5.1's existing `Resource.create({})` is the upstream cause, but Story 13.2 is the first consumer that makes the value externally visible and the first to *document* it as set — so 13.2 must either set it or correct ADR-001 + C86 + the recipe to state spans land under `unknown_service` and require `OTEL_SERVICE_NAME`.) Restore the dropped `service.name` assertion in the e2e test.

---

### [MED]-1: gRPC unit tests never verify the load-bearing behavior (`insecure` flag + scheme stripping) — test names promise it, bodies don't assert it

**File:** `tests/unit/telemetry/test_backends_otlp.py:106-130`

**Issue:** Probe #2's correctness claim (`grpc://localhost:4317` → exporter gets `endpoint="localhost:4317"` + `insecure=True`; `grpcs://` → `insecure=False`) is asserted **nowhere**. The tests check only `isinstance(_GrpcExp)`, `_transport=="grpc"`, and the *backend's* stored full URL (`backend._endpoint == "grpc://localhost:4317"`) — never the exporter's stripped endpoint or insecure flag. The `insecure` flag is the entire behavioral difference between `grpc://` and `grpcs://`, and the gRPC path is the most error-prone (prefix-stripping is hand-rolled). This is the `feedback_test_name_assertion_match` fake-green pattern: `test_..._insecure` and `test_..._secure` assert identical things.

**Evidence:** The exporter exposes both attributes (verified):
```
$ uv run python -c "from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as G; e=G(endpoint='localhost:4317', insecure=True); print(e._endpoint, e._insecure)"
localhost:4317 True
```
Yet `test_otlp_backend_grpc_scheme_constructs_grpc_exporter_insecure` asserts neither `_endpoint` nor `_insecure`.

**Fix:** Add assertions on the exporter, not just the backend:
```python
assert backend._exporter._endpoint == "localhost:4317"   # scheme stripped
assert backend._exporter._insecure is True               # grpc:// → plaintext
# grpcs case:
assert backend._exporter._endpoint == "otel.example.com:4317"
assert backend._exporter._insecure is False              # grpcs:// → TLS
```

---

### [MED]-2: Recipe's Honeycomb HTTPS example is non-functional as shown — endpoint-only export to Honeycomb returns 401

**File:** `docs/recipes/08-ci-integration.md` (new OTLP section, env-var CI snippet)

**Issue:** The recipe presents
```bash
export AGENTEVAL_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
```
as a working CI example, but Honeycomb requires an `x-honeycomb-team` auth header. Story 13.2 ships **endpoint-only** (headers are deferred to DF-13.2-S2/C87, as the story itself states). So this example exports nothing usable — Honeycomb rejects unauthenticated traces. This violates the `feedback_honest_framing` norm (showing a broken example as if it works). The story's own otel-trace-visual.md even shows the required `-H "x-honeycomb-team: $HONEYCOMB_API_KEY"`.

**Fix:** Either (a) use a self-hostable endpoint (Jaeger/Tempo) for the env-var CI example, or (b) keep Honeycomb but document that auth requires `export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=$HONEYCOMB_API_KEY"` (the SDK-native path operators must use until C87 lands), with a one-line note that native header config is a Phase-2.5 carry-over.

---

### [MED]-3: The L-4 "empirical wire-format" e2e test hand-fabricates `agenteval.tier` — it proves OTLP transports arbitrary attributes, not that agenteval's instrumentation emits them

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:64-72`

**Issue:** L-4 (the Story 13.1 upstream lesson) demands empirically verifying the *claim* — here, that agenteval spans flow through the OTLP envelope. But `_emit_test_span_via_listener` manually calls `span.set_attribute("agenteval.tier", 2)` inside the same helper that the test then reads back. The assertion `any(a["key"] == "agenteval.tier")` therefore only proves "OTLP carries an attribute I just set by hand" — it never exercises the real tier-stamping instrumentation. Combined with HIGH-1 (resource not asserted), the e2e test verifies very little of the actual agenteval→OTLP path. (It's also docker-gated and skips in CI, so even this weak coverage rarely runs.)

**Fix:** Drive a real span through the framework's instrumentation (an actual keyword/adapter invocation that the tier processor stamps) rather than setting `agenteval.tier` manually, OR downgrade the test's self-description from "verifies agenteval-specific attributes flow through" to "verifies OTLP transport round-trips span attributes" to match what it actually proves.

---

### [MED]-4: Runtime collector unreachability silently slows every test — `end_test`'s `force_flush(5000ms)` now blocks on the OTLP BatchSpanProcessor

**File:** `src/AgentEval/telemetry/listener.py:455` + `_attach_otlp_exporter_if_needed:338`

**Issue:** The graceful-degrade narrative (AC-13.2.3) only covers **construction-time** failures (`ImportError`/`ValueError`). At runtime, `end_test` calls `provider.force_flush(timeout_millis=5000)` (line 455, pre-existing for the in-memory SimpleSpanProcessor). Once the OTLP `BatchSpanProcessor` is attached to the same provider, this `force_flush` now also drives a synchronous OTLP export+retry on **every test**. If the collector is down/misconfigured (a common ops reality), each `end_test` blocks up to ~5s with no warning — a large suite silently balloons in wall-clock. Nothing degrades or warns on sustained runtime export failure (C88 acknowledges the circuit-breaker gap, but the per-test 5s stall is undocumented and immediate).

**Fix:** Document the per-test flush cost of `trace_backend=otlp` in the recipe/stability-surface, and consider lowering the OTLP flush timeout or skipping the synchronous OTLP flush in `end_test` (let BatchSpanProcessor batch asynchronously + flush at `close`) so a down collector doesn't serialize the whole suite.

---

### [LOW]-1: AC-13.2.7 "≥15 unit tests" not met (13 shipped); AC text not amended per `feedback_in_flight_spec_amendment`

**File:** `_bmad-output/implementation-artifacts/13-2-otlp-trace-backend.md` (AC-13.2.7)

**Issue:** AC-13.2.7 mandates "≥15 unit tests" in `test_backends_otlp.py`; 13 shipped. The dev documented the shortfall in the "In-flight spec amendments" section but left the AC text reading "≥15", whereas the project norm requires amending the AC in the same commit (not just narrating the deviation in the dev-record). Minor process drift; the 13 tests are otherwise adequate in scope.

**Fix:** Edit AC-13.2.7 to "≥13 unit tests (consolidated co-existence test absorbs 2)" so the AC matches reality and the count claim is self-consistent.

---

### [LOW]-2: `minimal_otel_config` `file` exporter emits an empty `rotation:` key — possibly-invalid collector config that no CI run ever exercises

**File:** `tests/integration/telemetry/_otlp_helpers.py:124-128`

**Issue:** The generated collector config has:
```yaml
exporters:
  file:
    path: /etc/otelcol-contrib/spans.json
    rotation:
```
An empty `rotation:` maps to `null`, which the contrib `file` exporter may reject or interpret unexpectedly depending on version. Because the e2e tests are docker-gated and skip under this dev's snap-confined docker (and CI), this config is never executed — so a config defect here would persist invisibly behind a perpetual skip. The dev's own `+15 unit tests ... 2 docker integration tests correctly skipped` confirms the e2e path was never actually run.

**Fix:** Drop the empty `rotation:` key (omit it entirely) so the config is unambiguous, and run the e2e test at least once on a non-snap docker host to confirm the round-trip actually works before relying on it as the L-4 empirical check.

---

**Total: 1 HIGH + 4 MED + 2 LOW**

The standout is **HIGH-1**: spans export under `service.name=unknown_service`, directly contradicting the ADR-001 row, carry-over C86, the AC-13.2.8 example, and the cross-linked Jaeger-discovery contract — and the one test that would have caught it had its `service.name` assertion quietly removed. Everything else is test-fidelity / honest-framing polish. The core dispatch logic (URL-scheme parsing, graceful-degrade on construction, sentinel idempotency, dual-export ordering, redaction-before-OTLP) is correct as verified against source.
