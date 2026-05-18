# JUnit XML Enrichment

**Status:** Phase-1 skeleton — content to be filled by Epic 8a Story 8a.1 (Enrich RF `--xunit` output via Regular Listener v3 `xunit_file(path)` hook + sysexits-style structured exit codes).
**Owning epic:** Epic 8a Story 8a.1
**Related ADRs:** ADR-014 (Error-Class Hierarchy — `error_code` class attribute drives `<failure type="...">`)
**Related FRs:** FR49 (JUnit XML emission), FR50 (Exit-code mapping — ratified 2026-05-18 as sysexits-style per-leaf, superseding the PRD-draft family codes 1/2/3)

## Purpose

Governs the **enrichment of RF's standard JUnit-XML output** (`xunit.xml`) with agenteval-specific structured metadata. RF's default xUnit output is minimal; agenteval injects (a) the `error_code` from raised `AgentEvalError` leaves into the `<failure type="...">` attribute, (b) the evidence-block UUID into a `<system-out>` block, (c) tier classification (Tier-1/2/3) into a `<properties>` block. This makes downstream CI reporters (GitHub Actions test-reporter, Jenkins JUnit plugin, Allure) surface actionable failure information without spelunking RF's log.html.

## Scope

### In-scope

- The fields enriched on each `<testcase>` element (`error_code`, `evidence_id`, `tier`, plus `<properties>` for cost/tokens/latency/coverage/completeness/trace_id/adapter/model per Story 8a.1 spec).
- The `xunit_file(path)` hook (Regular Listener v3 only — Library Listeners' `close()` fires before RF writes the xunit file; empirically disqualified 2026-05-17) used to apply enrichments (per `listener-integration.md`'s RF Listener v3 hook list).
- The mapping from `AgentEvalError` subclass → `<failure type="...">` attribute value (drives by `error_code` class attribute per ADR-014).
- The sysexits.h-style structured exit-code mapping per FR50 (ratified 2026-05-18): per-leaf codes anchored in the `docs/contracts/error-class-hierarchy.md` authoritative table.
- Backwards-compat with standard JUnit XML schema (i.e., enrichments are additive; non-agenteval consumers see standard xUnit + ignore the additions).

### Out-of-scope

- RF's own xUnit emission — agenteval enriches, doesn't replace.
- HTML report rendering (`log.html`) — that's RF's surface.
- OTel span emission — that's `otel-trace-visual.md` + `listener-integration.md`.

## Contract

*Phase-1 skeleton — Epic 8a Story 8a.1 fills in the formal specification.*

The contract will at minimum include:

- A table of standard xUnit fields + agenteval enrichments (which attributes are added; which child elements are added; semantics of each).
- The `AgentEvalError → <failure type=...>` mapping table (1:1 with ADR-014's `error_code` attributes — `SANDBOX_REQUIRED`, `COST_EXCEEDED`, `INCOMPLETE_TRACE`, etc.).
- The FR50 sysexits-style per-leaf exit-code table (cross-referenced from `error-class-hierarchy.md` — `65` for `PollingDisallowedError`, `66` for `CostExceededError`, `67` for `IncompleteTraceError`, `68` for `UnsupportedMCPVersionError`; other leaves get sysexits.h-aligned codes assigned by Story 8a.1).
- An example before/after `<testcase>` element showing the enrichments.
- Compatibility statement: enrichments are valid per standard xUnit schema; non-agenteval consumers MUST NOT break when consuming enriched output.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. Adding new enrichment fields is minor-version-bump safe (backwards-compat preserved). Removing an enrichment or changing the `<failure type="...">` mapping is a breaking change requiring major-version bump + a deprecation cycle. The FR50 exit-code mapping is `stable` from Phase-1 onward — changes require ADR amendment.

## References

- ADR-014: Error-Class Hierarchy (the `error_code` class attribute that drives this enrichment)
- FR49 (PRD): JUnit XML emission
- FR50 (PRD): Exit-code mapping
- `listener-integration.md`: the `output_xml` hook that fires this enrichment
- Epic 8a Story 8a.1: owns final content authoring
