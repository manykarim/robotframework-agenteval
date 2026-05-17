# Architecture Decision Records

This directory holds the **18 ratified Architecture Decision Records (ADRs)** that govern agenteval's Phase-1 architectural choices.

## Convention

agenteval ADRs follow the [MADR (Markdown Any Decision Record)](https://adr.github.io/madr/) template:

```markdown
# ADR-NNN: <Title>

**Status:** accepted | proposed | superseded
**Date:** YYYY-MM-DD
**Renumbering history:** (if applicable — sources renumbered from prior IDs)

## Context
## Decision
## Consequences
## Alternatives

## References
```

**Numbering scheme** (locked in architecture.md §`ADR numbering scheme`, L282):

- **ADR-001** is the Architectural Influences Catalog — a meta-ADR listing reviewed patterns from `robotframework-agentguard`, competitor MCP-eval projects, and industry standards. Each pattern carries an explicit `adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable` decision for agenteval.
- **ADR-002 through ADR-018** are agenteval's original + extended architectural decisions. Sources renumbered from the PRD-backlog sidecar (ADR-005..014 → agenteval ADR-002..011, with ADR-007 → ADR-004 already filled by Epic 0) and the architecture-backlog sidecar (ADR-A1..A8 → agenteval ADR-012..018; ADR-A4 retired; A6 → ADR-016 + A8 → ADR-018 filled by Epic 0). The renumbering plan is documented at `_bmad-output/planning-artifacts/architecture.md` L429-434.

**Status workflow:** `proposed → accepted → superseded`. Superseded ADRs remain in this directory with a `**Status:** superseded` line + a `Superseded-by:` reference; never deleted. ADR-A4 was *retired* (not superseded) on 2026-05-17 per the project's `feedback_agentguard_inspiration_not_dependency` working norm — see the relevant entry in the architecture-backlog sidecar for the reasoning.

**Renumbering history** is recorded on every renumbered ADR (lines 4-5 of the file). The history line cites the source sidecar + original ID; preserves the auditable trail from PRD/architecture-step working IDs to ratified `docs/adr/` filenames.

## Index

Sorted by ADR number.

| ADR | Title | Status | Date | Source |
| --- | --- | --- | --- | --- |
| [ADR-001](ADR-001-architectural-influences-catalog.md) | Architectural Influences Catalog | accepted | 2026-05-17 | agenteval-original (catalog of reviewed patterns) |
| [ADR-002](ADR-002-tier-1-adapter-ceiling-rule.md) | Tier-1 Adapter Ceiling Rule | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-005 |
| [ADR-003](ADR-003-coding-agent-adapter-protocol-internal-class-split.md) | CodingAgentAdapter Protocol — Internal Class Split | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-006 |
| [ADR-004](ADR-004-hosted-mcp-observation.md) | Hosted-MCP Universal Trace Observation Pattern | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-007 (Epic 0 ratified, Story 0.1 spike-validated) |
| [ADR-005](ADR-005-conformance-suite-fidelity-oracles.md) | Conformance Suite Includes Fidelity Oracles | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-008 |
| [ADR-006](ADR-006-agent-run-result-completeness-field.md) | `AgentRunResult.metadata.completeness` Field Required | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-009 |
| [ADR-007](ADR-007-agent-run-result-mcp-coverage-incomplete-trace-error.md) | `AgentRunResult.metadata.mcp_coverage` + `IncompleteTraceError` | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-010 |
| [ADR-008](ADR-008-mcp-spec-version-validation.md) | MCP Spec Version Validation | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-011 |
| [ADR-009](ADR-009-per-test-mcp-server-scope.md) | Per-Test MCP Server Scope (Listener v3 `test_id`) | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-012 |
| [ADR-010](ADR-010-copilot-cli-adapter-trace-extraction.md) | Copilot CLI Adapter — Trace Extraction Strategy | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-013 |
| [ADR-011](ADR-011-three-persona-model.md) | Three-Persona Model + Persona-Split Test | accepted | 2026-05-17 | renumbered from PRD-backlog ADR-014 |
| [ADR-012](ADR-012-async-to-sync-bridge-kernel-module.md) | Async-to-Sync Bridge as Kernel Module (`_run_async`) | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A1 |
| [ADR-013](ADR-013-entry-points-discovery-infrastructure.md) | Entry-Points Discovery Infrastructure | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A2 |
| [ADR-014](ADR-014-error-class-hierarchy.md) | Error-Class Hierarchy | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A3 |
| [ADR-015](ADR-015-cost-runtime-guardrail-decorator.md) | Cost + Runtime Guardrail as `@guarded_fanout` Decorator | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A5 |
| [ADR-016](ADR-016-mcp-coverage-detection-default.md) | MCP Coverage Detection Default — Trust-Floor with Adapter Contract | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A6 (Epic 0 ratified, Story 0.1 spike-amended D1 trust-floor + D4 adapter contract) |
| [ADR-017](ADR-017-conformance-suite-organization-per-ac-test-files.md) | Conformance Suite Organization — Per-AC Test Files + Per-Adapter Parametrize | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A7 |
| [ADR-018](ADR-018-sandbox-phase-1-policy.md) | Sandbox Policy in Phase 1 — Policy + Gate + Protocol | accepted | 2026-05-17 | renumbered from architecture-backlog ADR-A8 (Epic 0 ratified, no spike amendments) |

## Cross-references

ADR-001 (the Catalog) catalogs ~22 reviewed `robotframework-agentguard` patterns + 2 competitor MCP-eval projects + 2 industry standards (OpenTelemetry GenAI semconv, Model Context Protocol specification). Each catalog row carries an explicit decision for agenteval. Per the catalog's `§Scope + obligation framing` section, **inclusion does not create any obligation** for agenteval to track the source's future evolution — agentguard and other sources are reference points, not dependencies.

ADRs cross-reference each other via Markdown relative links (e.g., ADR-007 cites ADR-016 for `mcp_coverage` field literal semantics). The cross-reference graph is intentional: each ADR's `## References` section lists the catalog row(s) and sibling ADRs that informed it.

## Retired

- **ADR-A4** (working ID from the architecture-backlog sidecar) was **retired** on 2026-05-17. The retirement reasoning lives in the architecture-backlog sidecar (`_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A4) and is summarized in the project's `feedback_agentguard_inspiration_not_dependency` working norm: `robotframework-agentguard` is one reviewed pattern source among others; no drift-check CI is needed because there is no dependency to drift-check.

## Maintaining this index

When a new ADR is ratified:

1. Author the ADR file at `docs/adr/ADR-NNN-<slug>.md` using the MADR template.
2. Append the entry to the Index table above (sorted by ADR number).
3. If the ADR adopts a reviewed pattern, also append a row to the `§Body` table in `ADR-001-architectural-influences-catalog.md`.
4. Append a `§Amendments Log` entry in ADR-001 documenting the ratification (date, ADR ID, one-line summary, evidence pointer).

When an ADR is superseded:

1. Update the superseded ADR's `**Status:**` line to `superseded` + add a `**Superseded-by:** ADR-MMM` line.
2. The replacement ADR cites the superseded one in its `## References` section.
3. Keep the superseded ADR file in this directory — never delete (history is auditable).

Retirements (vs supersessions) are reserved for cases where the entire premise of an ADR no longer applies — they are recorded in the §Retired section above with a brief reason.
