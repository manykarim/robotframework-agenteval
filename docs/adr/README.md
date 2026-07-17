# Architecture Decision Records

This directory holds the Architecture Decision Records that still govern agenteval's
architecture after the four-surface refocus (2026-07). agenteval is four libraries —
HooksLibrary, MCPLibrary, SkillsLibrary, SubagentsLibrary — that test the agentic
stack deterministically, with an LLM judge, or by driving a real coding agent.

The refocus retired a batch of ADRs whose subject matter was removed (the coding-agent
adapter protocol and its vendor CLIs, the conformance suite, entry-points discovery,
the cost/runtime guardrail decorator, the three-persona model, the async-to-sync
kernel, assertion-engine adoption, the agent-run-result completeness/coverage fields,
and the sandbox Protocol). Their files were deleted rather than kept as gravestones.
The survivors that had drifted carry a short "Superseded by the four-surface refocus"
note at the top and were trimmed to match what ships.

## Convention

agenteval ADRs follow the [MADR (Markdown Any Decision Record)](https://adr.github.io/madr/)
template:

```markdown
# ADR-NNN: <Title>

**Status:** accepted | proposed | superseded
**Date:** YYYY-MM-DD

## Context
## Decision
## Consequences
## Alternatives

## References
```

ADR-001 is the Architectural Influences Catalog — a meta-ADR recording the patterns
agenteval reviewed (chiefly from `robotframework-agentguard`) and the explicit
`adopt` / `adapt` / `borrow-concept` / `diverge` / `not-applicable` decision taken for
each. Inclusion credits an influence; it creates no obligation to track that source's
future. `robotframework-agentguard` is inspiration, not a dependency.

## Index

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-001](ADR-001-architectural-influences-catalog.md) | Architectural Influences Catalog | accepted | 2026-05-17 |
| [ADR-004](ADR-004-hosted-mcp-observation.md) | Hosted-MCP Universal Trace Observation Pattern | accepted | 2026-05-17 |
| [ADR-008](ADR-008-mcp-spec-version-validation.md) | MCP Spec Version Validation | accepted | 2026-05-17 |
| [ADR-009](ADR-009-per-test-mcp-server-scope.md) | Per-Test MCP Server Scope (Listener v3 `test_id`) | accepted | 2026-05-17 |
| [ADR-014](ADR-014-error-class-hierarchy.md) | Error-Class Hierarchy | accepted | 2026-05-17 |
| [ADR-016](ADR-016-mcp-coverage-detection-default.md) | MCP Coverage Detection Default — Trust-Floor | accepted | 2026-05-17 |

The ADR numbers are not renumbered when a neighbour is retired — a stable number is
easier to cite than a tidy sequence. Gaps in the sequence are retired ADRs, nothing more.

## Status workflow

`proposed → accepted → superseded`. A superseded ADR keeps its file with a
`**Status:** superseded` line and a `Superseded-by:` reference — history stays auditable.
An ADR is *deleted* (not superseded) only when its entire subject was removed from the
product, as happened in the four-surface refocus.

## Maintaining this index

When a new ADR is ratified:

1. Author the file at `ADR-NNN-<slug>.md` using the MADR template.
2. Append a row to the Index table above (sorted by ADR number).
3. If the ADR adopts a reviewed pattern, add a row to ADR-001's `§Body` table and an
   entry to its `§Amendments Log`.
