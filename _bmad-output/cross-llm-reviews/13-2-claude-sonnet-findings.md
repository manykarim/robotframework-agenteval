I have enough evidence. Here is my adversarial review.

---

## Story 13.2 Code Review — OTLP Trace Backend

Reviewed all 10 behavioral probes against live source. Probes 1, 5, 6, 7, 9 pass cleanly. Four real defects follow.

---

### [HIGH]-1: gRPC integration test is structurally broken by `_agenteval_otlp_attached` sentinel cross-test contamination

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:59-91` + `src/AgentEval/telemetry/listener.py:336-339`

**Issue:** Both integration tests call `_emit_test_span_via_listener()`, which creates a new `Listener`, calls `_configure_tracer_provider()` + `_resolve_backend()` + `_attach_otlp_exporter_if_needed()`. In the default pytest process (no `--forked`), the HTTP test runs first and sets `provider._agenteval_otlp_attached = True` on the process-global `TracerProvider`. When the gRPC test runs next, `_configure_tracer_provider()` short-circuits at line 259 (`_agenteval_listener_attached` sentinel), then `_attach_otlp_exporter_if_needed()` short-circuits at line 336 (`_agenteval_otlp_attached` sentinel). The gRPC `BatchSpanProcessor` is **never attached**. The gRPC collector receives zero spans. `assert len(spans) >= 1` fails.

**Evidence:**
```python
# listener.py:336-339 — the sentinel that blocks the gRPC test:
if getattr(provider, "_agenteval_otlp_attached", False):
    return            # <— HTTP test set this; gRPC test hits it
provider.add_span_processor(BatchSpanProcessor(self._backend._exporter))
provider._agenteval_otlp_attached = True
```

This is currently masked because docker is skipped under snap-confined docker (`2 docker integration tests correctly skipped`). The bug surfaces the first time both tests run sequentially in a docker-available environment.

**Fix:** Add a module-level `autouse` fixture that clears the sentinel (and the stale `BatchSpanProcessor`) before each test:
```python
@pytest.fixture(autouse=True)
def _reset_otel_provider():
    from opentelemetry import trace as otel_trace
    provider = otel_trace.get_tracer_provider()
    for attr in ("_agenteval_otlp_attached", "_agenteval_listener_attached"):
        provider.__dict__.pop(attr, None)  # type: ignore[union-attr]
    yield
```
Or, simpler: pass `--forked` for these two tests via a `pytest.ini` mark. The root design is correct for production; the tests need process isolation.

---

### [MED]-1: `grpc://` and `grpcs://` unit tests don't verify the `insecure=` kwarg value — a `True/False` swap would silently pass

**File:** `tests/unit/telemetry/test_backends_otlp.py:107-127`

**Issue:** Both `test_otlp_backend_grpc_scheme_constructs_grpc_exporter_insecure` and `test_otlp_backend_grpcs_scheme_constructs_grpc_exporter_secure` only assert `isinstance(backend._exporter, _GrpcExp)`. Neither verifies whether `insecure=True` or `insecure=False` was actually passed to the gRPC exporter constructor. Per `feedback_codex_probe_fitness`: behavioral probes must empirically verify the invariant, not just the type. A code change that swaps the `True`/`False` values (mixing TLS and plaintext) would pass this test suite.

**Evidence:**
```python
def test_otlp_backend_grpcs_scheme_constructs_grpc_exporter_secure() -> None:
    """grpcs:// → gRPC exporter with insecure=False (TLS) + stripped scheme."""
    backend = OTLPBackend(endpoint="grpcs://otel.example.com:4317")
    assert backend._transport == "grpc"
    assert isinstance(backend._exporter, _GrpcExp)   # ← only type check; insecure= unchecked
```

**Fix:** Patch the gRPC exporter constructor and assert the `insecure` kwarg:
```python
from unittest.mock import patch, call
with patch("AgentEval.telemetry.backends._OTLPSpanExporterGRPC") as mock_grpc:
    OTLPBackend(endpoint="grpcs://otel.example.com:4317")
assert mock_grpc.call_args == call(endpoint="otel.example.com:4317", insecure=False)
```
Apply symmetrically for the `grpc://` (insecure=True) test.

---

### [MED]-2: `_emit_test_span_via_listener` mutates `os.environ` without cleanup — env vars leak across subsequent tests

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:73-74`

**Issue:** `os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"` and `os.environ["AGENTEVAL_OTLP_ENDPOINT"] = endpoint` are set globally without using `monkeypatch` or a `try/finally` restore. These env vars persist for every test executed after the integration tests in the same pytest session. Any test in `tests/unit/` or `tests/integration/` that calls `resolve_config({})` without explicitly unsetting `AGENTEVAL_TRACE_BACKEND` will silently get `trace_backend="otlp"` — likely triggering `DegradedTraceWarning` (OTLP extra unavailable in unit env) or worse.

**Evidence:**
```python
# test_otlp_export_e2e.py:67-74 — no cleanup, no monkeypatch
import os
os.environ["AGENTEVAL_TRACE_BACKEND"] = "otlp"
os.environ["AGENTEVAL_OTLP_ENDPOINT"] = endpoint
listener = listener_mod.Listener()
```

**Fix:** Refactor `_emit_test_span_via_listener` to accept `monkeypatch` or use `try/finally`:
```python
def _emit_test_span_via_listener(monkeypatch, endpoint: str, span_name: str = ...) -> None:
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "otlp")
    monkeypatch.setenv("AGENTEVAL_OTLP_ENDPOINT", endpoint)
    ...
```

---

### [MED]-3: gRPC integration test missing `agenteval.tier` attribute assertion — L-4 empirical-probe coverage is asymmetric

**File:** `tests/integration/telemetry/test_otlp_export_e2e.py:125-146`

**Issue:** The HTTP test verifies span name AND that `agenteval.tier` flows through the OTLP envelope. The gRPC test only verifies span name. Per the L-4 lesson from Story 13.1 ("include a test that EMPIRICALLY verifies the claim against a reference implementation"), the gRPC transport path should carry the same attribute-presence assertion. The AC-13.2.8 spec describes equal verification for both variants.

**Evidence:**
```python
# HTTP test (complete):
assert any(s.get("name") == "agenteval_e2e_http_span" for s in spans)
assert any(a.get("key") == "agenteval.tier" for a in flat_attrs)   # ← L-4 probe

# gRPC test (truncated):
assert any(s.get("name") == "agenteval_e2e_grpc_span" for s in spans)
# agenteval.tier assertion absent — gRPC OTLP attribute propagation unverified
```

**Fix:** Add the attribute assertion to the gRPC test (same pattern as the HTTP test, lines 118-122).

---

### [LOW]-1: `minimal_otel_config(output_file)` silently ignores its `output_file` parameter

**File:** `tests/integration/telemetry/_otlp_helpers.py:97-128`

**Issue:** The function signature accepts `output_file: Path` but the returned YAML hardcodes `/etc/otelcol-contrib/spans.json`. The actual mapping is performed separately via docker volume mount in `docker_collector`. A future caller invoking `minimal_otel_config(different_path)` expecting the path to appear in the config will be silently wrong. The misleading signature violates the principle of least astonishment.

**Evidence:**
```python
def minimal_otel_config(output_file: Path) -> str:   # ← parameter accepted
    return """...
exporters:
  file:
    path: /etc/otelcol-contrib/spans.json   # ← hardcoded, output_file never used
```

**Fix:** Either remove the parameter and document the docker-mount coupling, or embed the path: `path: {output_file}` (YAML-safe via the helper formatting it as the in-container path, derived from the mount destination).

---

### [LOW]-2: C86 carry-over falsely claims `service.name="robotframework-agenteval"` is set; integration test conspicuously omits the AC-spec assertion

**File:** `docs/phase-1-5-carry-overs.md` (C86 row) + `tests/integration/telemetry/test_otlp_export_e2e.py`

**Issue:** C86 states "Story 13.2 ships OTLPBackend with `service.name="robotframework-agenteval"` baked into the Listener's resource." But `_configure_tracer_provider()` uses `resource = Resource.create({})` with an empty dict — no explicit `service.name` attribute. The OTel Python SDK default for `service.name` in this scenario is `"unknown_service"` (unless `OTEL_SERVICE_NAME` env var is set). Confirming the discrepancy: the AC-13.2.8 spec showed `assert all(s["resource"]["attributes"]["service.name"] == "robotframework-agenteval" for s in spans)` — the actual test omits this assertion entirely, suggesting the dev knows it would fail.

**Evidence:**
```python
# listener.py:275 — no service.name in resource:
resource = Resource.create({})   # service.name defaults to "unknown_service"
provider = TracerProvider(resource=resource)
```
Grep for `service.name` in `src/AgentEval/telemetry/` returns zero matches.

**Fix:** Either (a) amend C86 to accurately state `service.name` is NOT yet set in Phase-2 (correcting the false claim), or (b) add `resource = Resource.create({"service.name": "robotframework-agenteval"})` to `_configure_tracer_provider()` and restore the integration test assertion.

---

**Total: 1 HIGH + 3 MED + 2 LOW**
