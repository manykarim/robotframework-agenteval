# OTel Trace Visual

**Status:** Phase-1 skeleton — content authored as part of Phase 2 visual rendering work (deferred); Phase-1 contract is the placeholder.
**Owning epic:** Phase 2 (epic TBD during Phase 2 planning)
**Related ADRs:** ADR-012 (catalog row: agentguard ADR-012 OTel RF Listener — `adapt`), `agentguard ADR-012` review in `docs/adr/ADR-001-architectural-influences-catalog.md`
**Related FRs:** FR60+ (trace recording family); industry standard: OpenTelemetry GenAI semantic conventions

## Purpose

Governs the **visual representation of OpenTelemetry traces** emitted by agenteval's OTel listener (Story 5.1 lands the listener; Phase 2 lands the visual rendering). This contract defines how a trace looks when rendered in a span explorer (Jaeger, Tempo, Honeycomb, etc.) — what attributes are required on which span types, what naming conventions resolve to canonical visual hierarchies, and which fields map to UI affordances (link, filter, search).

## Scope

### In-scope

- Required + optional attributes on each agenteval span type (`agenteval.run`, `agenteval.tool_call`, `agenteval.assertion`, etc.).
- Semantic-convention mapping: agenteval span attributes → OTel GenAI semconv attribute names.
- Visual hierarchy rules: which span is the parent of which (`agenteval.run` is parent of all `agenteval.tool_call` spans within the run, etc.).
- Color + iconography hints for span types (informational for renderer authors; not normative).

### Out-of-scope

- The OTel listener's internal implementation (`src/AgentEval/telemetry/listener.py`) — that's libdoc + ADR-012 catalog row.
- Specific tracing-backend (Jaeger, Tempo, Honeycomb) configuration; this contract is renderer-agnostic.
- Phase-2 visual rendering tooling itself (a hypothetical `agenteval-trace-viewer` CLI).

## Contract

*Phase-1 skeleton — Phase 2 epic fills in the formal specification.* The contract will at minimum include:

- A table of agenteval span types with: span name, span kind (server / client / internal), required attributes, optional attributes, parent-child relationship rules.
- The OTel GenAI semantic-convention mapping (e.g., `agenteval.run.model` ↔ `gen_ai.request.model`).
- Visual hierarchy + grouping rules.

Phase 1 baseline: the OTel listener emits spans (Epic 5 Story 5.1); the spans MUST follow OTel GenAI semconv (per `docs/adr/ADR-001-architectural-influences-catalog.md` — OTel GenAI semconv has `adopt-verbatim` decision). The visual-rendering contract evolves in Phase 2.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. Phase-1 status: `provisional`. Phase-2 ratification will promote to `stable` after the rendering tooling validates the contract. Changes to OTel semconv mapping require coordination with upstream OTel — agenteval follows semconv versions.

## References

- agentguard ADR-012 row in `docs/adr/ADR-001-architectural-influences-catalog.md`: OTel RF Listener (`adapt` decision)
- OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Epic 5 Story 5.1: ships the OTel listener (Phase-1 baseline)
- FR60+ trace recording family (PRD)
