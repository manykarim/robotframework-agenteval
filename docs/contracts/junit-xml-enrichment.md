# JUnit XML Enrichment

**Status:** Phase-1 skeleton — content to be filled by Epic 8a Story 8a.1 (Enrich RF xUnit output via Listener v3 + structured exit codes).
**Owning epic:** Epic 8a Story 8a.1
**Related ADRs:** ADR-014 (Error-Class Hierarchy — `error_code` class attribute drives `<failure type="...">`)
**Related FRs:** FR49 (JUnit XML emission), FR50 (Exit-code mapping)

## Purpose

Governs the **enrichment of RF's standard JUnit-XML output** (`xunit.xml`) with agenteval-specific structured metadata. RF's default xUnit output is minimal; agenteval injects (a) the `error_code` from raised `AgentEvalError` leaves into the `<failure type="...">` attribute, (b) the evidence-block UUID into a `<system-out>` block, (c) tier classification (Tier-1/2/3) into a `<properties>` block. This makes downstream CI reporters (GitHub Actions test-reporter, Jenkins JUnit plugin, Allure) surface actionable failure information without spelunking RF's log.html.

## Scope

### In-scope

- The fields enriched on each `<testcase>` element (`error_code`, `evidence_id`, `tier`).
- The `output_xml` hook used to apply enrichments (per `listener-integration.md`'s RF Listener v3 hook list).
- The mapping from `AgentEvalError` subclass → `<failure type="...">` attribute value.
- The structured exit-code mapping per FR50 (Safety:3 / Budget:2 / Compat:3 / Integrity:2-or-3-per-leaf).
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
- The FR50 exit-code lookup table (4 sub-base families → 4 exit-code ranges).
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
