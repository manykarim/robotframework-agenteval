# RF Listener v3 Integration

**Status:** Phase-1 ratified — Story 5.1 filled the Contract section 2026-05-20.
**Owning epic:** Epic 5 Story 5.1
**Related ADRs:** ADR-009 (Per-Test MCP Server Scope via Listener v3 `test_id`), ADR-004 (Hosted-MCP Universal Trace Observation), `agentguard ADR-012` catalog row (OTel RF Listener — `adapt`)
**Related FRs:** FR33a (RF Listener v3 entry point), FR40 (per-test test_id scoping)

## Purpose

Governs agenteval's **RF Listener v3 integration model** — specifically: **Regular RF Listener v3** (registered via `--listener AgentEval.telemetry.listener`), **NOT** a Library Listener. Per the empirical findings ratified 2026-05-17, Library Listeners do NOT receive the `xunit_file(path)` / `output_file(path)` hooks (their `close()` fires BEFORE RF writes those files); the Regular Listener model IS the only viable path for the xunit enrichment that Epic 8a Story 8a.1 requires. The listener also reads per-test `test_id` from Listener v3 context per ADR-009, scoping the MCP observer + OTel trace exporter per RF test.

## Scope

### In-scope

- Listener kind: **Regular RF Listener v3** registered via `--listener AgentEval.telemetry.listener` (module path; RF auto-resolves to the `Listener` class within `src/AgentEval/telemetry/listener.py`).
- Which Listener v3 hooks agenteval consumes (e.g., `start_test`, `end_test`, `start_suite`, `end_suite`, `xunit_file(path)`, `output_file(path)`).
- The per-test `test_id` extraction protocol (how the observer + trace exporter read it from RF context).
- The `errlog=open(stderr_path, 'w')` workaround for the RF/pabot stderr-fd issue (per ADR-009 + Story 0.1 spike).
- The `SIGTERM → sys.exit` auto-install in `MCPLifecycleManager.__init__` (per ADR-009 + Story 0.2 spike).
- Listener ordering: agenteval's listener MUST be ordered AFTER user listeners that produce data agenteval consumes (e.g., if a user listener writes RF context state).
- The `robot.listener` entry-point registration in `pyproject.toml` per FR33a (a Phase-2 convenience for entry-points-based discovery; the canonical Phase-1 path is the explicit `--listener` flag).

### Out-of-scope

- RF Library Listener pattern (the `ROBOT_LIBRARY_LISTENER` class attribute on the Library class itself) — empirically disqualified 2026-05-17 because Library Listeners' `close()` fires BEFORE RF writes xunit/output files; the Story 8a.1 enrichment hook requires Regular Listener semantics.
- OTel span generation details — that's `otel-trace-visual.md` + ADR-012 catalog row.
- The xunit-XML enrichment fields (cost / tokens / latency / coverage / etc.) — that's `junit-xml-enrichment.md` per Epic 8a Story 8a.1.

## Contract

*Phase-1 ratified by Story 5.1 (2026-05-20).*

### Registration model

- **Regular RF Listener v3** registered via:
  ```
  robot --listener AgentEval.telemetry.listener.Listener tests/
  ```
  Use the **explicit `Module.Class` path**. **Story 8a.2 dev empirical finding (2026-05-25):** the short `--listener AgentEval.telemetry.listener` (module-path-only) form is *accepted* by RF 7.x without error but the `Listener` class hooks (`start_suite` / `start_test` / `xunit_file`) do NOT fire — RF takes the "module-as-listener" path which expects a top-level `ROBOT_LISTENER_API_VERSION` (not present at module scope). Verified empirically via probe + reproduction with a standalone DebugListener: `result.tags.add("from_result")` surfaces in `output.xml` only when the class-path form is used. The `--listener` flag is REQUIRED — RF does NOT auto-discover listeners from PyPA entry-points (empirically verified 2026-05-17). The `[project.entry-points."robot.listener"]` registration in `pyproject.toml` (populated by Story 5.1 with `agenteval = "AgentEval.telemetry.listener:Listener"`) is provided for Phase-2 tooling that explicitly walks the listener group.
- The class exposes `ROBOT_LISTENER_API_VERSION = 3`.
- NOT a Library Listener — the `ROBOT_LIBRARY_LISTENER` class attribute is NOT set on `AgentEval` itself. Library Listeners' `close()` fires BEFORE RF writes the xunit/output files, which would break Story 8a.1's `xunit_file(path)` enrichment hook.

### Consumed Listener v3 hooks

| Hook | Listener behavior |
| --- | --- |
| `start_suite(data, result)` | Configure the OTel TracerProvider on first invocation (idempotent across suites). Wires `RedactionProcessor → BatchSpanProcessor(InMemorySpanExporter)`. Resolves `trace_backend` + `trace_path` from Story 4.3 config precedence. |
| `start_test(data, result)` | Extract `data.full_name` (canonical Listener v3 path); call `_kernel/context.set_current_test_id(test_id, suite_id)`. On missing/empty `full_name`: emit `UserWarning` (DF-5.1-S1 upgrade to `DegradedTraceWarning` once Story 5.4 lands) and skip the scope binding. |
| `end_test(data, result)` | When `trace_backend="jsonl"`: flush spans for the test to `<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl`. On successful flush (or memory-backend mode): call `_kernel/trace_store.clear_spans(test_id)` then `_kernel/context.unbind_context()`. On JSONL write failure: warning emitted, spans preserved in memory, context unbound. |
| `end_suite(data, result)` | Phase-1 no-op. Reserved for Story 8a.1 enrichment hand-off. |
| `xunit_file(path)` | Phase-1 no-op. Reserved for Story 8a.1 per-testcase `<properties>` enrichment per `docs/contracts/junit-xml-enrichment.md`. |
| `output_file(path)` | Phase-1 no-op. Symmetric to `xunit_file` for the canonical `output.xml` artifact. |
| `close()` | Idempotent. TracerProvider stays configured for cross-suite re-use (correct under pabot worker reuse). |

### `test_id` extraction protocol

Listener v3's `data` parameter is the live `TestCase`/`TestSuite` instance (NOT the v2 `attrs` dict). Canonical extraction: `data.full_name` (the dotted path). Fallback chain: `full_name` → `longname` → `name` → empty string (emits warning + skips scope binding).

Suite identifier extraction walks `data.parent` until the root suite, then returns that node's `full_name`.

### Trace backplane wiring (TracerProvider chain)

The Listener configures the TracerProvider once at PROCESS scope (not per-Listener-instance) on first `start_suite` — subsequent `Listener()` instances in the same process detect the sentinel attribute on the active provider and short-circuit before stacking duplicate processors (Story 5.1 code-review 3-way HIGH-A fix 2026-05-20):

1. `Resource.create({})` — Story 5.1 deliberately does NOT pre-populate `agenteval.test_id` on the Resource. OTel TracerProvider Resource attributes are immutable per-provider so they can't be re-written per test; pre-populating with an empty string would defeat Story 1b.2's `_span_test_id` fallback to span attributes. Per-test test_id stamping happens via `TestIdContextSpanProcessor.on_start` (#2 below).
2. `TestIdContextSpanProcessor()` added first — per-test discriminator that reads `_kernel/context.current_context().test_id` and stamps it as a SPAN-level `agenteval.test_id` attribute. Must run BEFORE RedactionProcessor so the test_id is set before any other processor reads attributes.
3. `RedactionProcessor()` added second — single redaction choke point per NFR-SEC-01 / FR38a (architecture L679 + L1193).
4. `SimpleSpanProcessor(trace_store._get_exporter())` added third — Story 1b.2's singleton `InMemorySpanExporter`. Phase-1 uses `SimpleSpanProcessor` over `BatchSpanProcessor` so synchronously-ended spans are immediately visible via projection accessors without a `force_flush` plumbing trip — the Phase-1 trade-off accepts the per-span synchronous-export cost for mid-test query correctness.
5. `trace.set_tracer_provider(provider)` — global provider. If a prior caller already set a TracerProvider (test fixtures + repeated `python -m robot` invocations), the Listener attaches its 3 processors to the existing provider then marks it with the `_agenteval_listener_attached` sentinel so future Listener instances don't re-attach.
6. `trace_store._configure_tracer_provider()` called for downstream-consumer compatibility.

### stderr-fd + SIGTERM hygiene (already in Story 1b.1)

The Listener does NOT install these — they're already provisioned by Story 1b.1's `MCPLifecycleManager.__init__`:

- `errlog=open(stderr_path, 'w')` passed to `stdio_client` to work around the RF/pabot stderr-fd issue (per ADR-009 + Story 0.1 spike findings).
- `signal.signal(signal.SIGTERM, sys.exit)` auto-installed in `MCPLifecycleManager.__init__` so `atexit` handlers fire on pabot worker SIGTERM (per ADR-009 + Story 0.2 spike findings).

### Listener ordering

agenteval's Listener MUST be registered AFTER any user Listener that writes RF context state agenteval reads. Recommended order: `--listener UserContextListener --listener AgentEval.telemetry.listener`. Reverse order is silently incorrect (user state not visible to agenteval) — Phase-1 ships no runtime check (Phase-1.5 hygiene carry-over candidate).

### Stability labels

| Surface | Label | Notes |
| --- | --- | --- |
| Module path `AgentEval.telemetry.listener` + class name `Listener` | `stable` | Renaming requires major-version bump per NFR-MAINT-03. |
| Regular-Listener vs Library-Listener choice | `stable` | Empirically ratified 2026-05-17; reverting requires evidence the Library-Listener path can support `xunit_file(path)`. |
| Hook consumption list | `provisional` | Adding hooks consumed is minor-version-bump safe; removing hooks requires major bump. |
| JSONL artifact path schema `<output_dir>/agenteval/trace__<suite_id>__<test_id>.jsonl` | `provisional` | Phase-1.5 may add `<adapter>__` segment per Phase-2 multi-adapter scoping needs. |

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The listener registration path `AgentEval.telemetry.listener` is `stable` from Phase-1 onward — renaming requires major-version bump per NFR-MAINT-03. The Regular-Listener vs Library-Listener choice is `stable` (empirically ratified 2026-05-17; reverting requires evidence that the Library-Listener path can support `xunit_file(path)`). The hook-consumption list is `provisional` until Story 5.1 finalizes; additions (consuming more hooks) are minor-version-bump safe.

## References

- ADR-009: Per-Test MCP Server Scope (Listener v3 `test_id`)
- ADR-004: Hosted-MCP Universal Trace Observation
- `agentguard ADR-012` row in `docs/adr/ADR-001-architectural-influences-catalog.md`: OTel RF Listener (`adapt`)
- FR33a (PRD): RF Listener v3 entry point
- epics.md Story 5.1 (L1287-1292): the empirical-grounding text that disqualifies Library Listener for xunit enrichment + ratifies the Regular Listener model
- Story 0.1 spike findings: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` (stderr-fd + 75/75 pabot runs)
- Story 0.2 spike findings: `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` (SIGTERM atexit gap)
