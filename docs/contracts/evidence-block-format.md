# Evidence Block Format

**Status:** Phase-1 skeleton — content to be filled by Epic 5 (Trace Observability + Honesty Fields stories).
**Owning epic:** Epic 5 — Trace Observability Kernel
**Related ADRs:** ADR-004 (Hosted-MCP Universal Trace Observation), ADR-007 (mcp_coverage + IncompleteTraceError)
**Related FRs:** FR34a (evidence-block format), FR34b (evidence-block visual contract), PRD §Editorial Moat

## Purpose

Governs the structure + content of the **Evidence Block** that agenteval emits with every assertion outcome. The `Get Last Evidence Block` keyword returns this block; CI report renderers + the `agenteval` CLI consume it. The block is the PRD's "editorial moat" — it makes WHY an assertion passed or failed structurally inspectable, not narrated.

## Scope

### In-scope

- Field-level schema of the evidence block (keys, types, optionality).
- Required fields per assertion family (trace-based, metric-based, judge-based).
- Serialization format (JSON-on-the-wire; rendered Markdown in the run report).
- Stability label assignment for each field (`stable` / `provisional` / `experimental`).

### Out-of-scope

- How the block is *rendered* in any specific report format (HTML, JUnit XML, OTel span attributes) — those live in their own contracts (`junit-xml-enrichment.md`, `otel-trace-visual.md`).
- How adapters *capture* the underlying tool-call traces — see `listener-integration.md` (Listener v3 hook surface) + ADR-004 (hosted-MCP observation pattern).
- Span-attribute mapping that drives Epic 5.3 evidence-block production — see [`otel-trace-visual.md`](otel-trace-visual.md).

## Contract

*Phase-1 skeleton — Epic 5 fills in the formal specification.* The block at minimum will include:

- `evidence_id: str` — UUID4
- `assertion_name: str` — RF keyword that produced this block
- `outcome: Literal["pass", "fail", "skip", "degraded"]`
- `traces: list[ToolCallTrace]` — observed tool calls (see ADR-004 + ADR-007)
- `metadata: AgentRunMetadata` — completeness + mcp_coverage fields
- `redaction: RedactionReport` — what was redacted + why (FR38a/b)

Exact field set + format ratified by Epic 5 Story 5.1+5.2+5.3 implementations.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. Field additions are minor-version-bump safe; field removals or type changes require major-version bump per NFR-MAINT-03. Changes to redaction rules require security review per `SECURITY.md`.

## References

- ADR-004: hosted-MCP universal trace observation
- ADR-007: mcp_coverage + IncompleteTraceError
- PRD §Editorial Moat + FR34a (format) + FR34b (visual contract)
- [`otel-trace-visual.md`](otel-trace-visual.md): span-attribute mapping that drives evidence-block production (Epic 5.3)
- [`listener-integration.md`](listener-integration.md): Listener v3 hook surface that captures the underlying traces
