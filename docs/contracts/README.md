# Documentation Contracts

This directory holds **11 first-class doc contracts** per NFR-MAINT-04. Each contract governs a specific public surface of agenteval: API behavior, on-the-wire format, listener integration, JUnit emission, stability guarantees. Per the PRD's editorial-moat principle + architecture's §Project Tree (L1419-1430, ratified 2026-05-18), these docs are Phase-1 deliverables — not "after MVP" polish.

## Convention

Every contract follows the same 4-section template enforced by `.github/workflows/docs-build.yml`:

```markdown
# <Contract Name>

**Status:** Phase-1 skeleton — content to be filled by <Epic N>.
**Owning epic:** <Epic N: Title>
**Related ADRs:** <comma-separated list>
**Related FRs:** <comma-separated list>

## Purpose
(≤100 words explaining what this contract governs)

## Scope
### In-scope
- ...
### Out-of-scope
- ...

## Contract
(formal specification; placeholder content acceptable for Phase-1 stubs)
<optional ### Subsection-name for nested contracts>

## Change Policy
This contract evolves per [`stability-surface.md`](stability-surface.md) labels: `stable` / `provisional` / `experimental`.
Changes that break consumers require a major-version bump per NFR-MAINT-03.

## References
- ...
```

The `docs-build.yml` workflow (Story 1a.2) runs a per-file grep assertion (`^## (Purpose|Scope|Contract|Change Policy)$`) on every `*.md` file in this directory + asserts all 4 sections present. Files missing any of the 4 required section headers fail CI.

## Index

11 contracts (sorted alphabetically by slug).

| Contract | One-line description | Owning epic / story |
| --- | --- | --- |
| [coding-conventions](coding-conventions.md) | Good/anti-pattern reference card for contributors (naming, type annotations, docstrings, error wording). | Story 1a.5 |
| [conformance-fixture-format](conformance-fixture-format.md) | Schema + authoring guide for golden-trace fixtures used by `tests/conformance/` per AC-CONFORMANCE-01. | Epic 1b Story 1b.5 |
| [determinism-contract](determinism-contract.md) | 3-tier model + ACL gates + polling-ban + validate-disabled-by-default; `### Tier Model` subsection. | Epic 1b |
| [error-class-hierarchy](error-class-hierarchy.md) | `AgentEvalError` base + 4 sub-bases + 11 leaves; FR59 error-format; FR49 + FR50 mapping. **Substantive content authored 2026-05-18.** | Story 1a.4 + Epic 1b + per-leaf epics |
| [evidence-block-format](evidence-block-format.md) | Structure + content of the `Get Last Evidence Block` payload (PRD editorial-moat principle). | Epic 5 |
| [exit-criteria-0x-to-1x](exit-criteria-0x-to-1x.md) | Objective gates that must be satisfied before agenteval releases as `1.0.0`. | Epic 9 Story 9.3 |
| [junit-xml-enrichment](junit-xml-enrichment.md) | RF xUnit XML enrichment (`error_code` → `<failure type>`, evidence-block UUID, tier classification). | Epic 8a Story 8a.1 |
| [listener-integration](listener-integration.md) | RF Listener v3 integration; `test_id` scoping; stderr-fd + SIGTERM workarounds from Story 0.1/0.2 spikes. | Epic 5 Story 5.1 |
| [mcp-coverage-detection](mcp-coverage-detection.md) | Per-adapter `mcp_coverage` detection responsibility + D1 trust-floor + D4 adapter contract. | Epic 5 Story 5.2 |
| [otel-trace-visual](otel-trace-visual.md) | Visual representation of OTel traces; OTel GenAI semconv mapping. | Phase 2 |
| [stability-surface](stability-surface.md) | Per-API-element stability labels (`stable`/`provisional`/`experimental`); `### Sandbox Protocol Surface` subsection. | Story 1a.6 + Epic 6 |

## Phase-1 status

All 11 contracts exist as **skeletons** as of 2026-05-18 (Story 1a.4 ratification). One contract — `error-class-hierarchy.md` — was authored with **substantive content** per AC-1a.4.2 (FR59 + the 11-leaf ADR-014 table). The other 10 carry `**Status:** Phase-1 skeleton — content to be filled by <Epic N>` banners. The owning epic for each contract is documented in the Status banner + cross-referenced in the Index table above.

## Retired

- **`agentguard-inheritance.md`** — retired 2026-05-17 alongside ADR-A4 + NFR-MAINT-06. Per the project's `feedback_agentguard_inspiration_not_dependency` working norm, `robotframework-agentguard` is INSPIRATION ONLY (not a dependency); inheriting-from-agentguard is not a meaningful relationship to document. See `docs/adr/ADR-001-architectural-influences-catalog.md` §Scope + obligation framing for the canonical reasoning.

## Excluded explicitly

Two contracts were proposed in early drafts but ratified as **subsections of other contracts** during the 2026-05-18 architect review:

- **`tier-model.md`** — NOT a standalone contract. The 3-tier model lives as `### Tier Model` subsection inside [determinism-contract.md](determinism-contract.md).
- **`sandbox-protocol.md`** — NOT a standalone contract. The `SandboxBackend` Protocol surface lives as `### Sandbox Protocol Surface` subsection inside [stability-surface.md](stability-surface.md).

## Maintaining this index

When a new contract is added:

1. Author the file at `docs/contracts/<slug>.md` using the 4-section template above.
2. Append a row to the Index table (sorted alphabetically by slug).
3. Update architecture.md project tree (L1419-1430) to add the new file under `docs/contracts/`.
4. Update PRD NFR-MAINT-04 if the contract is FR-driven.

When an existing contract is finalized (skeleton → final content):

1. Update the file's `**Status:**` banner to remove the "Phase-1 skeleton" qualifier.
2. The owning epic's story file documents the transition + adds a `**Date:**` line.

Retirements (vs supersessions) are reserved for cases where the entire premise of a contract no longer applies — they are documented in the §Retired section above with a brief reason + ADR cross-reference.
