# RF Listener v3 Integration

**Status:** Phase-1 skeleton — content to be filled by Epic 5 Story 5.1 (OTel Listener — span generation + memory/JSONL backends).
**Owning epic:** Epic 5 Story 5.1
**Related ADRs:** ADR-009 (Per-Test MCP Server Scope via Listener v3 `test_id`), ADR-004 (Hosted-MCP Universal Trace Observation), `agentguard ADR-012` catalog row (OTel RF Listener — `adapt`)
**Related FRs:** FR33a (RF Listener v3 entry point), FR40 (per-test test_id scoping)

## Purpose

Governs the **RF Library vs Regular Listener vs RF Listener v3 scoping** for agenteval's listener entry point. Per the empirical findings from Story 0.1 + Story 0.2 spikes, the per-test test_id read from Listener v3 context is the load-bearing scope for the MCP observer + the OTel trace exporter. This contract documents which listener kind agenteval ships, what hooks it consumes, and how it interacts with the user's other listeners (per-suite ordering, conflict resolution).

## Scope

### In-scope

- Which Listener v3 hooks agenteval consumes (`start_test`, `end_test`, `start_suite`, `end_suite`, `output_xml`).
- The per-test `test_id` extraction protocol (how the observer + trace exporter read it from RF context).
- The `errlog=open(stderr_path, 'w')` workaround for the RF/pabot stderr-fd issue (per ADR-009 + Story 0.1 spike).
- The `SIGTERM → sys.exit` auto-install in `MCPLifecycleManager.__init__` (per ADR-009 + Story 0.2 spike).
- Listener ordering: agenteval's listener MUST be ordered AFTER user listeners that produce data agenteval consumes (e.g., if a user listener writes RF context state).
- The `Library AgentEval.telemetry.Listener` registration pattern (per `pyproject.toml`'s `robot.listener` entry-point group per FR33a).

### Out-of-scope

- RF Library Listener vs Regular Listener taxonomy in general — that's RF's own documentation; agenteval ships ONE specific RF Listener v3 implementation.
- OTel span generation details — that's `otel-trace-visual.md` + ADR-012 catalog row.
- The JUnit XML enrichment hooks — that's `junit-xml-enrichment.md` per Epic 8a.

## Contract

*Phase-1 skeleton — Epic 5 Story 5.1 fills in the formal specification.*

The contract will at minimum include:

- The list of RF Listener v3 hooks agenteval consumes + the data each emits/expects.
- The per-test `test_id` extraction + scope-binding protocol.
- The stderr-fd workaround + SIGTERM handler installation (load-bearing per Story 0.1+0.2 findings).
- Listener-ordering rules + recommended invocation: `robot --listener AgentEval.telemetry.Listener ...`.
- Backwards-compat guarantee for the listener's public surface.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The listener entry-point name (`agenteval.telemetry.Listener`) is `stable` from Phase-1 onward — renaming requires major-version bump. The hook-consumption list is `provisional` until Story 5.1 finalizes; additions (consuming more hooks) are minor-version-bump safe.

## References

- ADR-009: Per-Test MCP Server Scope (Listener v3 `test_id`)
- ADR-004: Hosted-MCP Universal Trace Observation
- `agentguard ADR-012` row in `docs/adr/ADR-001-architectural-influences-catalog.md`: OTel RF Listener (`adapt`)
- FR33a (PRD): RF Listener v3 entry point
- Story 0.1 spike findings: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` (stderr-fd + 75/75 pabot runs)
- Story 0.2 spike findings: `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` (SIGTERM atexit gap)
