# Story 5.1: OTel Listener + Span Generation + Memory/JSONL Backends

Status: done

## Story

As **Raj (Agent Developer)** or **Mei (Agent Surface Author)**,
I want **a Robot Framework Listener v3** at `src/AgentEval/telemetry/listener.py` that registers via `[project.entry-points."robot.listener"]` + `--listener AgentEval.telemetry.listener`, generates OTel GenAI-shape spans (`invoke_agent → chat → execute_tool`) populated by the spans-emission helpers at `src/AgentEval/telemetry/spans.py`, and writes them to **memory** + **JSONL** backends at `src/AgentEval/telemetry/backends.py` — with `gen_ai.*` attribute names routed through the internal `src/AgentEval/telemetry/semconv.py` facade per NFR-COMPAT-06,
So that every agent run captures auditable trace data with per-test scope (PRD FR32, FR33a, FR33b, FR40) — closing the agent-agnostic trace truth claim from Day 1 with zero consumer setup beyond the `--listener` flag.

## Pre-create-story drift check (22nd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

2 drifts caught + resolved pre-authoring (per fix-the-losing-source-NOW pattern):

- **(D-1 HIGH structural)** Architecture L208/L211/L352/L1248 used `telemetry/otel_listener.py` (borrowed from agentguard's filename). Ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 say `src/AgentEval/telemetry/listener.py` (module path `AgentEval.telemetry.listener`). Two-source ratified consensus wins. Architecture L211 + L352 + L1248 amended pre-authoring; agentguard's `otel_listener.py` reference row at L208 unchanged (agentguard's filename is correct for agentguard).
- **(D-2 MED)** epics.md L1437 listed 3 files (`listener.py` + `spans.py` + `backends.py`). Architecture L1248-1251 specifies 4 files including `semconv.py` (Internal facade for `gen_ai.*` attribute names per NFR-COMPAT-06 — "attribute-name churn is a single-file update"). epics.md L1437 amended pre-authoring to include `semconv.py`.

## Acceptance Criteria

### AC-5.1.1 — Listener v3 class + entry-point registration

**Given** the ratified `docs/contracts/listener-integration.md` Phase-1 skeleton + `pyproject.toml` L107 `[project.entry-points."robot.listener"]` empty table,
**When** Story 5.1 implements `src/AgentEval/telemetry/listener.py`,
**Then**:
- A `Listener` class exposes `ROBOT_LISTENER_API_VERSION = 3` (RF Listener v3 contract).
- The class implements `start_suite(data, result)`, `end_suite(data, result)`, `start_test(data, result)`, `end_test(data, result)`, `xunit_file(path)`, `output_file(path)`, `close()` hooks per RF Listener v3 ABI. (Story 5.1 code-review Auditor H6 fix 2026-05-20: pre-edit listed v2 signatures `start_test(name, attrs)`; v3 uses `(data, result)` where `data` is the live `TestCase`/`TestSuite` instance.)
- `start_test` extracts the test's full name from `data.full_name` (canonical RF Listener v3 path; pre-edit said `attrs["longname"]` which is v2 semantics) and calls `AgentEval._kernel.context.set_current_test_id(test_id, suite_id, scope=<resolved-from-mcp_per_test-config>)` — wires the per-test scope per Story 1b.1's API. The scope is resolved via `_kernel/context._resolve_scope(mcp_per_test_config_value)` per ADR-009 + PRD FR40 (Story 5.1 code-review Auditor H3 fix 2026-05-20: pre-edit dropped the `scope=` arg + ignored `mcp_per_test`).
- `end_test` flushes the JSONL backend if `trace_backend="jsonl"` then calls `AgentEval._kernel.trace_store.clear_spans(test_id)` for per-test isolation.
- `pyproject.toml` `[project.entry-points."robot.listener"]` populated with `agenteval = "AgentEval.telemetry.listener:Listener"` so consumers can use the entry-points-based path; the canonical Phase-1 path remains the explicit `--listener AgentEval.telemetry.listener` per listener-integration.md L20.
- **Regular RF Listener v3** (NOT Library Listener) per the empirically-disqualified Library Listener path documented at listener-integration.md L24 + epics.md L1440-1442 (Library Listeners' `close()` fires BEFORE RF writes xunit/output files; Story 8a.1's xunit-enrichment hook requires Regular semantics).

### AC-5.1.2 — TracerProvider wiring (RedactionProcessor → BatchSpanProcessor → InMemoryExporter chain)

**Given** Story 1b.2's `_configure_tracer_provider()` placeholder at `src/AgentEval/_kernel/trace_store.py:117` + Story 1b.2's `RedactionProcessor(SpanProcessor)` at `src/AgentEval/_kernel/redaction.py:205`,
**When** the Listener is loaded (Listener's `__init__` OR first `start_suite` hook),
**Then** Story 5.1's TracerProvider configuration adds `RedactionProcessor → BatchSpanProcessor(InMemorySpanExporter)` chain per architecture L679 + L1193 — single redaction choke point per NFR-SEC-01 / FR38a. Resource attributes include `agenteval.test_id` (read from `_kernel/context.current_context()`) per architecture L1003 + Story 1b.2 H_R2 fix.

### AC-5.1.3 — Span emission helpers (spans.py)

**And** `src/AgentEval/telemetry/spans.py` exposes context-manager helpers for the 3-level span hierarchy:
- `invoke_agent_span(agent_name: str, model: str | None = None) -> ContextManager[Span]` — top-level per agent run.
- `chat_span(model: str, provider: str | None = None) -> ContextManager[Span]` — per LLM round-trip (child of invoke_agent).
- `execute_tool_span(tool_name: str, source: Literal["adapter", "hosted_mcp"]) -> ContextManager[Span]` — per tool call (child of chat).
- Each helper sets the canonical `gen_ai.*` + `agenteval.*` attributes from `semconv.py` constants (see AC-5.1.4).
- `emit_tool_call_span(name, args, result, error, latency_ms, source)` — non-context-manager helper for adapters that already have a completed tool-call record (used by Story 5.2 hosted-MCP observer + Story 4.x adapter `_finalize` paths).

### AC-5.1.4 — semconv.py internal facade per NFR-COMPAT-06

**And** `src/AgentEval/telemetry/semconv.py` exposes string constants for every `gen_ai.*` + `agenteval.*` attribute key used in the codebase. Per NFR-COMPAT-06 ("GenAI semantic convention attribute names routed through internal facade so attribute-name churn is a single-file update") + architecture L999-1010 ratified `agenteval.*` namespacing extensions:

**`gen_ai.*` keys (per OTel GenAI semconv):**
- `GEN_AI_SYSTEM` = `"gen_ai.system"`
- `GEN_AI_REQUEST_MODEL` = `"gen_ai.request.model"`
- `GEN_AI_USAGE_INPUT_TOKENS` = `"gen_ai.usage.input_tokens"`
- `GEN_AI_USAGE_OUTPUT_TOKENS` = `"gen_ai.usage.output_tokens"`
- `GEN_AI_USAGE_CACHED_INPUT_TOKENS` = `"gen_ai.usage.cached_input_tokens"`
- `GEN_AI_RESPONSE_FINISH_REASONS` = `"gen_ai.response.finish_reasons"`
- `GEN_AI_TOOL_NAME` = `"gen_ai.tool.name"`
- `GEN_AI_TOOL_CALL_ID` = `"gen_ai.tool.call.id"`

**`agenteval.*` keys (per architecture L1003-1010):**
- `AGENTEVAL_TEST_ID` = `"agenteval.test_id"` (TracerProvider Resource attribute)
- `AGENTEVAL_TOOL_SUCCESS` = `"agenteval.tool.success"`
- `AGENTEVAL_TOOL_DURATION_MS` = `"agenteval.tool.duration_ms"`
- `AGENTEVAL_TOOL_SOURCE` = `"agenteval.tool.source"`
- `AGENTEVAL_TOOL_ARGS` = `"agenteval.tool.args"` (JSON-encoded string per Story 1b.2 H_R5)
- `AGENTEVAL_TOOL_RESULT` = `"agenteval.tool.result"`
- `AGENTEVAL_TOOL_ERROR` = `"agenteval.tool.error"`
- `AGENTEVAL_TIER` = `"agenteval.tier"` (per Story 1b.2 M_R5 ratification)

All other modules in the codebase MUST import these constants from `semconv.py` rather than hardcoding the string keys. Convention enforcement: `tests/conformance/test_otel_semconv_facade.py` greps `src/AgentEval/` for hardcoded `"gen_ai."` or `"agenteval."` string literals outside `semconv.py` and asserts NONE exist.

### AC-5.1.5 — Memory backend (default)

**Given** `trace_backend="memory"` (the Story 1a.6 / PRD FR42 default),
**When** spans are emitted during a test,
**Then** they land in the `InMemorySpanExporter` already configured by Story 1b.2's `_get_exporter()` + are queryable via the 5 projection accessors at `_kernel/trace_store.py` (`get_run_spans`, `get_tool_calls`, `get_usage`, `get_latency`, `get_run_manifest`). Memory backend isolation is enforced by the `agenteval.test_id` Resource attribute filter per Story 1b.2 H_R2.

### AC-5.1.6 — JSONL backend (opt-in via trace_backend config)

**Given** `trace_backend="jsonl"` resolved via Story 4.3 ConfigValue precedence (init_arg → env → dotenv → default),
**When** the Listener's `end_test` hook fires,
**Then** `src/AgentEval/telemetry/backends.py` `JSONLBackend.flush_test(test_id, output_dir)`:
- Reads all spans for `test_id` via `get_run_spans(test_id)`.
- Serializes each span to one JSON line per the OTel JSON envelope shape (span name + attributes + resource attributes + timestamps + parent span id).
- Writes to `<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl` per PRD FR51 + Story 5.1 path convention.
- Calls `_kernel.trace_store.clear_spans(test_id)` AFTER successful write (clearing-before-write would lose the spans on a write failure).
- On write failure: emits `DegradedTraceWarning` (forward-ref to Story 5.4; Story 5.1 issues a `warnings.warn(...)` with the eventual class slot reserved) + does NOT raise to avoid masking test outcomes; the test's `output.xml` still records the test result, and Story 5.4 surfaces the warning via `Get Last Warnings`.

### AC-5.1.7 — Entry-point registration + canonical CLI path documented

**And** `pyproject.toml` `[project.entry-points."robot.listener"]` populated:
```toml
[project.entry-points."robot.listener"]
agenteval = "AgentEval.telemetry.listener:Listener"
```
Canonical invocation per listener-integration.md L17 + L20:
```
robot --listener AgentEval.telemetry.listener tests/
```
The `--listener` flag remains REQUIRED per epics.md L1438 ("RF does NOT auto-discover listeners from PyPA entry-points; empirically verified 2026-05-17"). The entry-point registration is provided for Phase-2 convenience tooling that explicitly walks the `robot.listener` group.

### AC-5.1.8 — listener-integration.md skeleton filled

**And** `docs/contracts/listener-integration.md` "Contract" section (currently Phase-1 skeleton per L31) is filled with Story 5.1's formal specification:
- Regular Listener registration model + canonical CLI invocation.
- List of consumed Listener v3 hooks (start_suite, end_suite, start_test, end_test, xunit_file, output_file, close) + data shape each emits/expects.
- `test_id` extraction protocol (canonical: `attrs["longname"]` from `start_test`; fallback: empty string with `DegradedTraceWarning`).
- stderr-fd workaround already in Story 1b.1's `MCPLifecycleManager`; Story 5.1's Listener does NOT need to duplicate it.
- SIGTERM handler already auto-installed in `MCPLifecycleManager.__init__`; Story 5.1's Listener does NOT need to duplicate it.
- Listener ordering: agenteval's Listener MUST be registered AFTER any user Listener that writes RF context state agenteval reads.
- Stability label: `AgentEval.telemetry.listener` module path is `stable`; renaming requires major-version bump per NFR-MAINT-03 (per stability-surface.md).
- Hook-consumption list: `provisional` — adding new hooks consumed is minor-version-bump safe; removing hooks requires major bump.

### AC-5.1.9 — Unit tests at tests/unit/telemetry/

**And** unit tests cover:
- `tests/unit/telemetry/test_listener.py` (≥12 tests): ROBOT_LISTENER_API_VERSION = 3; entry-point registration round-trip; `start_test → set_current_test_id` propagation; `end_test → clear_spans` invocation; `xunit_file` + `output_file` hooks accept path arg + no-op (Story 8a.1 fills); `close()` is idempotent; listener handles missing `longname` gracefully with `DegradedTraceWarning`.
- `tests/unit/telemetry/test_spans.py` (≥10 tests): span hierarchy structure (invoke_agent → chat → execute_tool parent-child); GenAI attribute population via semconv constants; nested span context propagation; `emit_tool_call_span` synthesizes a complete `execute_tool` span for adapters that already have the record; JSON-serialization of `agenteval.tool.args` per Story 1b.2 H_R5.
- `tests/unit/telemetry/test_backends.py` (≥10 tests): memory backend isolation (test_id A spans NOT visible to test_id B query); JSONL backend write + parse round-trip; JSONL backend handles missing `output_dir` (creates it); JSONL backend write failure emits `DegradedTraceWarning` and does NOT raise; JSONL flush-then-clear ordering (write failure preserves spans for next attempt).
- `tests/unit/telemetry/test_semconv.py` (≥8 tests): all documented constants are non-empty strings; constant names match the `*_*_*` SCREAMING_SNAKE_CASE convention; values match architecture L1001-1010 ratified key names exactly.
- `tests/conformance/test_otel_semconv_facade.py` (NEW; 1 test): grep enforcer — no hardcoded `"gen_ai."` or `"agenteval."` string literals in `src/AgentEval/` outside `semconv.py`. Failure mode names the offending file + line so the dev knows where to refactor.

### AC-5.1.10 — Integration test for Listener v3 end-to-end

**And** `tests/integration/telemetry/test_listener_e2e.py` runs a minimal `.robot` test under `robot --listener AgentEval.telemetry.listener` against the Mock provider + asserts:
- A `trace__<suite>__<test>.jsonl` artifact exists at the configured `output_dir` (when `trace_backend="jsonl"` is set via env var).
- The JSONL contains ≥1 `invoke_agent` span with `agenteval.test_id` matching the RF test's longname.
- The memory backend is empty after `end_test` (i.e., `clear_spans` fired) when `trace_backend="memory"` is set.
- Test isolation: two consecutive RF tests don't see each other's spans via the projection accessors.

### AC-5.1.11 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean.
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance -q` regression-clean (866 Story 4.4 close baseline; +40-50 new from this story expected).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.

### AC-5.1.12 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (24th consecutive use; first use of the **extended** `feedback_n_way_agreement_weight` triage table — Auditor 1-way on PRD/ADR/architecture re-derivation = near-certain band).
- `feedback_test_name_assertion_match` applied to all new tests.
- `feedback_codex_sandbox_bypass_operational`: Codex CLI subagent uses `--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check` per the goal directive authorization.
- `feedback_carry_over_catalog_gate`: at story-close, grep `src/AgentEval/telemetry/` + spec for any new `DF-5.1-S<N>` patterns; verify each is in `docs/phase-1-5-carry-overs.md` AND `_bmad-output/implementation-artifacts/deferred-work.md` before flipping sprint-status `done`.
- Auditor citation-drift check on FR32 + FR33a + FR33b + FR40 + NFR-COMPAT-06 wording + listener-integration.md citations + architecture L999-1010 `agenteval.*` ratification.

## Tasks / Subtasks

- [x] **Task 1: Architecture + epics.md drift fixes applied pre-authoring** (D-1 + D-2 above). DONE during pre-create-story.
- [x] **Task 2: `src/AgentEval/telemetry/semconv.py`** — 19 string constants (8 `gen_ai.*` + 8 `agenteval.*` + 3 span names) per architecture L1001-1010 ratified table.
- [x] **Task 3: `src/AgentEval/telemetry/spans.py`** — 3 context-manager helpers + 1 non-CM helper (`emit_tool_call_span` synthesizes complete `execute_tool` span from already-finished tool-call record).
- [x] **Task 4: `src/AgentEval/telemetry/backends.py`** — `MemoryBackend` (no-op flush; queries via projection accessors) + `JSONLBackend.flush_test(test_id, suite_id, output_dir)` with path-sanitization + write-failure → warning fallback.
- [x] **Task 5: `src/AgentEval/telemetry/listener.py`** — `Listener` class with `ROBOT_LISTENER_API_VERSION = 3` + 7 hook methods (`start_suite`, `start_test`, `end_test`, `end_suite`, `xunit_file`, `output_file`, `close`). TracerProvider configured in first `start_suite` (idempotent + resilient to existing global provider). Added `TestIdContextSpanProcessor` per design note documenting the OTel SDK immutable-Resource-attribute constraint + the SpanProcessor-based per-test discriminator.
- [x] **Task 6: `pyproject.toml` `[project.entry-points."robot.listener"]`** populated with `agenteval = "AgentEval.telemetry.listener:Listener"` + canonical CLI invocation documented.
- [x] **Task 7: `docs/contracts/listener-integration.md`** Contract section filled per AC-5.1.8 (registration model, 7 consumed hooks table, test_id extraction protocol, TracerProvider chain, stderr-fd + SIGTERM hygiene cross-ref, listener ordering, stability labels).
- [x] **Task 8: Unit tests** — 56 tests across `test_listener.py` (16) + `test_spans.py` (14) + `test_backends.py` (10) + `test_semconv.py` (8) + conformance grep enforcer `test_otel_semconv_facade.py` (1 test, regex-bounded to OTel-spec attribute shapes — NOT entry-point group names).
- [x] **Task 9: Integration test** at `tests/integration/telemetry/test_listener_e2e.py` (4 e2e tests).
- [x] **Task 10: All-gates pass.** ruff clean, ruff format clean, mypy clean (62 src files), license headers PASS, 918 unit+conformance / 8 skipped (was 866 at Epic 4 close; +52 new from this story).
- [x] **Task 11: 4-reviewer cross-LLM code review with extended N-way agreement triage table + carry-over catalog gate.** 24th consecutive STAR catch. 3-way HIGH-A (Blind + Codex empirical probe + Edge-cases): duplicate processor leak under worker reuse — process-global sentinel fix. 6 Auditor 1-way HIGHs (validating the Epic 4 retro `feedback_n_way_agreement_weight` extension — Auditor citation-drift = near-certain band): NFR-COMPAT-06 OTel pin drift (`>=1.20` → `>=1.27`); DF-5.1-S1 catalog gate violation (C24 added); `mcp_per_test` scope not wired; FR40 pabot-parallel fixture deferred to C25/Story 5.5; listener-integration.md contract drifts (3 sub-drifts amended); spec hook signatures v2→v3 amended. Blind HIGH-4 `_extract_outputdir` dead path → use real RF EXECUTION_CONTEXTS API. Edge-cases HIGH-2 `_safe_dict` widened to catch ValueError + RecursionError. Edge-cases HIGH-1 (child-thread context loss) REFUTED by Codex empirical probe — no current production path emits spans from raw threads. 9 MEDs + 4 LOWs all applied. 5 new behavioral tests pinning the defenses. Catalog grew 23 → 28 (C24-C28). `feedback_carry_over_catalog_gate` validated as load-bearing (Auditor caught the gate violation that the dev workflow missed). 926 unit+conformance / 8 skipped (was 866 at Epic 4 close; **+60 net**).

## Dev Notes

### Architecture compliance

- **PRD FR32 (OTel GenAI spans)**: `invoke_agent → chat → execute_tool` hierarchy via spans.py helpers.
- **PRD FR33a (Listener v3 entry-point)**: pyproject.toml registration + `--listener AgentEval.telemetry.listener` canonical path.
- **PRD FR33b (memory + JSONL backends)**: backends.py implements both; OTLP is Phase 2 via `[otlp]` extra.
- **PRD FR40 (per-test MCP scope)**: Listener's `start_test` calls `set_current_test_id(test_id, suite_id, scope)`; MCPLifecycleManager (Story 1b.1) consumes scope.
- **NFR-COMPAT-06**: semconv.py facade — no hardcoded `"gen_ai."` strings outside the facade.
- **NFR-SEC-01 / FR38a**: RedactionProcessor → BatchSpanProcessor → InMemoryExporter chain (Story 1b.2's RedactionProcessor + Story 5.1's TracerProvider wiring).
- **ADR-009 (per-test scope)**: Listener honors `mcp_per_test` config; SIGTERM/atexit already in MCPLifecycleManager (Story 1b.1).
- **architecture L1248-1251**: 4 telemetry files (listener.py + spans.py + backends.py + semconv.py).
- **`docs/contracts/listener-integration.md`**: ratified contract that Story 5.1 fills (Phase-1 skeleton → formal spec).

### Integration with existing kernel infrastructure

Story 5.1 wires (does NOT re-implement) existing kernel infrastructure:
- `_kernel/trace_store.py` (Story 1b.2): `_configure_tracer_provider()`, `_get_exporter()`, `_set_exporter()`, `_reset_exporter()`, `clear_spans()`, 5 projection accessors. Story 5.1's Listener calls `_configure_tracer_provider()` once on first `start_suite`.
- `_kernel/redaction.py` (Story 1b.2): `RedactionProcessor(SpanProcessor)`. Story 5.1's TracerProvider configuration adds it BEFORE the BatchSpanProcessor in the processor chain.
- `_kernel/context.py` (Story 1b.1): `set_current_test_id(test_id, suite_id, scope)`, `current_context()`, `bind_context()`, `unbind_context()`. Listener's `start_test → set_current_test_id`; `end_test → unbind_context` (after JSONL flush + clear_spans).
- `_kernel/context.py` (Story 1b.1): `MCPLifecycleManager` already has SIGTERM auto-install + errlog stderr-fd workaround. Story 5.1's Listener does NOT duplicate these — the manager exists per-process from Story 1b.1.

### Phase-1 limitations explicitly documented

- **No OTLP backend yet** — Phase-2 via `[otlp]` extra per PRD FR33b. Story 5.1 ships memory + JSONL only.
- **No `DegradedTraceWarning` class yet** — Story 5.4 lands the class. Story 5.1 uses `warnings.warn(...)` with eventual class slot reserved + a TODO comment naming Story 5.4 as the upgrade point. Forward-ref tracked as DF-5.1-S1.
- **No xunit_file enrichment yet** — Story 8a.1 fills the hook body. Story 5.1 provisions the hook (accepts path arg, no-op).
- **Hosted-MCP observer NOT in this story** — Story 5.2 lands `mcp/observer.py`. Story 5.1's `execute_tool_span` helper accepts `source: Literal["adapter", "hosted_mcp"]` so Story 5.2 can call it without modifying spans.py.
- **No real MCP-tool-call traces emitted yet** — Story 4.x adapters (4.1 + 4.2) currently raise `NotImplementedError` on non-empty `mcp_servers` (DF-4.1-S2 + DF-4.2-S1). Story 5.2's scope-expansion lands the adapter-side integration. Story 5.1's spans + backends work end-to-end with `chat` + `invoke_agent` from the adapters, but `execute_tool` spans will be empty until Story 5.2.

### Risks + mitigations

- **R-1**: TracerProvider re-configuration in subsequent test invocations (especially under pabot) could create span-leakage. Mitigation: idempotent `_configure_tracer_provider()` — Story 1b.2's helper already handles this; Story 5.1's Listener calls it once at `start_suite` and trusts the singleton pattern.
- **R-2**: JSONL serialization of non-JSON-encodable span attributes (e.g., `agenteval.tool.args` is supposed to be JSON-string already per Story 1b.2 H_R5, but a buggy producer could emit a dict). Mitigation: backends.py JSONL serializer falls back to `str(value)` on `json.dumps` TypeError + emits `DegradedTraceWarning`.
- **R-3**: Listener loaded but RF context state not set (e.g., user invokes via Python directly outside RF). Mitigation: `_kernel/context.current_context()` returns None gracefully per ADR-009; spans get empty `agenteval.test_id` Resource attribute + projection accessors return empty results. Document this behavior in listener-integration.md.

## Dev Agent Record

### Implementation Plan (dev workflow 2026-05-20)

1. Apply pre-create-story drift fixes (D-1 architecture filename + D-2 epics.md missing `semconv.py`) — DONE during create-story.
2. Implement `src/AgentEval/telemetry/semconv.py` — 19 module-level string constants.
3. Implement `src/AgentEval/telemetry/spans.py` — 3 CM helpers + 1 non-CM helper using semconv constants exclusively.
4. Implement `src/AgentEval/telemetry/backends.py` — `MemoryBackend` (no-op flush per AC-5.1.5) + `JSONLBackend.flush_test` writing one JSON line per span to `<output_dir>/agenteval/trace__<suite>__<test>.jsonl`.
5. Implement `src/AgentEval/telemetry/listener.py` — `Listener` class with `ROBOT_LISTENER_API_VERSION = 3` + the 7 Listener v3 hooks per the listener-integration.md table. Add `TestIdContextSpanProcessor` to handle the OTel TracerProvider Resource-attribute immutability constraint: `on_start(span, parent_context)` stamps `agenteval.test_id` from `_kernel/context.current_context().test_id` so `trace_store._span_test_id` finds it via the span-attribute fallback path (Story 1b.2 H_R2 contract). TracerProvider configuration is resilient to an already-set global provider (attaches processors to the existing provider instead of fighting OTel's set-once protection). Listener uses `SimpleSpanProcessor` (not `BatchSpanProcessor`) for synchronous Phase-1 export — mid-test queries via projection accessors return correct data.
6. Add `trace_path: None` default + `AGENTEVAL_TRACE_PATH` env-var mapping to `_kernel/context.py` (was missing — Story 5.1 needs it for the JSONL backend's output_dir config-precedence resolution per AC-5.1.6).
7. Populate `pyproject.toml` `[project.entry-points."robot.listener"]` with `agenteval = "AgentEval.telemetry.listener:Listener"` per AC-5.1.7.
8. Fill `docs/contracts/listener-integration.md` Contract section per AC-5.1.8.
9. Write 56 tests across 5 files (4 unit + 1 conformance + 4 e2e).
10. Run all gates; update story spec + sprint-status to `review`; ready for 4-reviewer cross-LLM code review.

### Completion Notes

- **Key design decision: `TestIdContextSpanProcessor` per-span stamping over Resource-attribute approach.** OTel SDK semantics make `Resource` attributes immutable per-provider AND `set_tracer_provider` one-shot per process. The Story 1b.2 docstring claimed the test_id would be "populated at TracerProvider setup" but that's not feasible in practice. The SpanProcessor `on_start(span, parent_context)` hook IS the canonical per-span dynamic context injection point. Story 1b.2's `_span_test_id` fallback to `span.attributes` (added by H_R2) is the load-bearing contract we leverage. Architecture/contracts updated to reflect this in the docstring + listener-integration.md Trace backplane wiring table.
- **SimpleSpanProcessor over BatchSpanProcessor.** Phase-1 trace volume is small; synchronous export means mid-test projection-accessor queries (used by Story 5.4's `Get Last Warnings` + future metric keywords) return correct data without `force_flush` plumbing. Phase-2 OTLP backend can revisit if volume becomes a concern.
- **Listener resilience to pre-existing TracerProvider.** Test harnesses share a process across multiple suites; OTel's set-once protection would silently strand the Listener's processors. The `_configure_tracer_provider` method detects an existing `TracerProvider` and attaches its processors there instead of fighting the global state. Production RF processes don't hit this path (fresh process per `robot` invocation).
- **NFR-COMPAT-06 facade enforcer.** Conformance test grep is regex-bounded to OTel-spec attribute SHAPES (`gen_ai.system|request.|response.|usage.|tool.` + `agenteval.test_id|tool.|tier`) — NOT generic `gen_ai.*` / `agenteval.*` literals. This avoids false positives on entry-point group names like `agenteval.providers` / `agenteval.coding_agents` / `agenteval.sandboxes` which are governed by ADR-013 (separate concern from the OTel facade).
- **`trace_path` config key added to `_kernel/context.py` `_FR42_DEFAULTS` + `_ENV_VAR_NAMES`.** The 9-key set is now 10. Pre-existing tests `test_resolve_config_returns_all_9_fr42_fr11b_keys` + `test_resolve_config_layer4_defaults_match_fr42` + `test_get_effective_config_with_provenance_returns_full_dict` amended to expect 10 keys including `trace_path`. Test names preserved for git-blame continuity.
- **Forward-refs explicitly named in code.** Each Phase-1 limitation has an inline comment naming the closing story (Story 5.2 hosted-MCP observer; Story 5.4 `DegradedTraceWarning`; Story 8a.1 xunit-enrichment; DF-4.1-S2/DF-4.2-S1 adapter `mcp_servers` integration). Future maintainers can grep for `DF-5.1-S<N>` or `Story 5.<N>` to find the carry-over chain.

## File List

**New files:**
- `src/AgentEval/telemetry/semconv.py`
- `src/AgentEval/telemetry/spans.py`
- `src/AgentEval/telemetry/backends.py`
- `src/AgentEval/telemetry/listener.py`
- `tests/unit/telemetry/__init__.py`
- `tests/unit/telemetry/test_semconv.py`
- `tests/unit/telemetry/test_spans.py`
- `tests/unit/telemetry/test_backends.py`
- `tests/unit/telemetry/test_listener.py`
- `tests/conformance/test_otel_semconv_facade.py`
- `tests/integration/telemetry/__init__.py`
- `tests/integration/telemetry/test_listener_e2e.py`

**Modified files:**
- `_bmad-output/planning-artifacts/architecture.md` — D-1 drift fixes at L211 / L352 / L1248 (was `otel_listener.py` → now `listener.py`).
- `_bmad-output/planning-artifacts/epics.md` — D-2 drift fix at L1437 (added `semconv.py` to the 4-file Story 5.1 deliverable).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 5.1 status `backlog → ready-for-dev → in-progress → review`; Epic 5 status `backlog → in-progress`.
- `pyproject.toml` — populated `[project.entry-points."robot.listener"]` with `agenteval = "AgentEval.telemetry.listener:Listener"`.
- `docs/contracts/listener-integration.md` — status `Phase-1 skeleton → Phase-1 ratified`; Contract section filled per AC-5.1.8.
- `src/AgentEval/_kernel/context.py` — added `trace_path: None` to `_FR42_DEFAULTS` + `AGENTEVAL_TRACE_PATH` to `_ENV_VAR_NAMES`.
- `tests/unit/kernel/test_context.py` — amended 2 tests to expect 10 config keys (added `trace_path`).
- `tests/unit/orchestration/test_config_provenance.py` — amended 1 test to expect `trace_path` in the 10-key set.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (22nd consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate) caught 2 drifts: D-1 HIGH architecture L211/L352/L1248 `otel_listener.py` vs ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 `listener.py` — architecture amended pre-authoring per fix-the-losing-source-NOW pattern; D-2 MED epics.md L1437 missing `semconv.py` from the file list despite architecture L1251 specifying it + NFR-COMPAT-06 mandating it — epics.md amended pre-authoring. | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code review). 4 new telemetry modules shipped (semconv.py / spans.py / backends.py / listener.py); listener-integration.md Contract section filled; pyproject.toml entry-point populated; `trace_path` config key added to kernel/context.py with full 4-level precedence support. Key design decisions documented in completion notes: TestIdContextSpanProcessor per-span stamping (over Resource-attribute approach); SimpleSpanProcessor for synchronous Phase-1 export; resilient TracerProvider configuration. NFR-COMPAT-06 facade enforcer regex-bounded to OTel-spec attribute shapes (avoids entry-point group false positives). All gates green: ruff/format/mypy clean (62 src files); 918 unit+conformance / 8 skipped (was 866 at Epic 4 close; **+52 new tests**); license-headers PASS. | Amelia |
| 2026-05-20 | 0.3.0   | Code-review patches applied (24th consecutive cross-LLM STAR catch). **3-way HIGH-A** (Blind H1 + Codex empirical probe + Edge-cases M4): duplicate processor leak under worker reuse → process-global `_agenteval_listener_attached` sentinel. **6 Auditor 1-way HIGHs** validating the Epic 4 retro `feedback_n_way_agreement_weight` extension (Auditor citation-drift = near-certain band, now 7+ consecutive TPs across 6 epics): NFR-COMPAT-06 OTel pin drift `>=1.20` → `>=1.27`; DF-5.1-S1 catalog gate violation → C24 added; `mcp_per_test` scope not wired through `set_current_test_id` → fixed via `_resolve_scope`; FR40 pabot-parallel fixture deferred to C25/Story 5.5; listener-integration.md Contract 3 drifts amended (SimpleSpanProcessor, empty Resource, idempotent-attach branch); spec AC-5.1.1 v2 hook signatures → v3 amended. **Blind HIGH-4** `_extract_outputdir` dead path → use real `robot.running.context.EXECUTION_CONTEXTS` API. **Edge-cases HIGH-2** `_safe_dict` + `flush_test` widened to catch `(TypeError, ValueError, RecursionError)`. **Edge-cases HIGH-1** (child-thread context loss) REFUTED by Codex empirical analysis (no current production path emits spans from raw threads; `_run_async` uses `copy_context()`, guarded_fanout meter thread doesn't emit spans). 9 MEDs + 4 LOWs applied: path-sanitization `..` rejection (2-way Blind MED-2 + Edge-cases M1); unknown trace_backend warns + falls back (Edge-cases M2); phantom 0-byte JSONL skipped (Edge-cases M3); fake-green singleton test rewritten with processor-count assertion + new processor-leak regression test (Blind MED-4 — 7th catch of `feedback_test_name_assertion_match`); facade regex broadened from sub-namespace whitelist to OTel-spec-shape match with ADR-013 entry-point exemption (3-way Codex LOW + Blind MED-5 + Edge-cases L1); architecture L663 amended to describe SpanProcessor-stamping (Auditor M1); `chat_span` docstring fixed re. OTel parent-attribute inheritance (Auditor M3); relative trace_path resolved to absolute at suite-start (Edge-cases L2); misleading "operator hook" comment deleted (Blind L2); defensive `unbind_context` before warn-and-return (Blind MED-1). 4 new Phase-1.5 carry-overs (C24 DegradedTraceWarning; C25 pabot-parallel fixture; C26-C28 back-filled Story 4.3 missed entries). 5 new behavioral tests pinning the defenses. All-gates green: ruff/format/mypy clean (62 src files); **926 unit+conformance** (was 918 pre-review; +8 patches-pinning tests) / 8 skipped; license-headers PASS. Validates `feedback_carry_over_catalog_gate` (Epic 4 retro NEW norm) as load-bearing — Auditor caught the catalog gap that the dev workflow missed. | Amelia |
