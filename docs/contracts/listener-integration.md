# RF Listener v3 Integration

**Status:** Phase-1 skeleton — content to be filled by Epic 5 Story 5.1 (OTel Listener — span generation + memory/JSONL backends).
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

*Phase-1 skeleton — Epic 5 Story 5.1 fills in the formal specification.*

The contract will at minimum include:

- The Regular Listener registration model + the canonical command-line invocation: `robot --listener AgentEval.telemetry.listener tests/`.
- The list of RF Listener v3 hooks agenteval consumes + the data each emits/expects (with explicit `xunit_file(path)` documentation for the Story 8a.1 enrichment hand-off).
- The per-test `test_id` extraction + scope-binding protocol (per ADR-009).
- The stderr-fd workaround + SIGTERM handler installation (load-bearing per Story 0.1+0.2 findings).
- Listener-ordering rules: agenteval's listener MUST be registered AFTER any user listener that writes RF context state agenteval reads.
- Backwards-compat guarantee for the listener's public surface (module path + class name + hook signatures).

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
