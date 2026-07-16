# Documentation Contracts

This directory holds the doc contracts that govern agenteval's public surfaces after
the four-surface refocus (2026-07). agenteval is four libraries — HooksLibrary,
MCPLibrary, SkillsLibrary, SubagentsLibrary — testing the agentic stack
deterministically, with an LLM judge, or by driving a real coding agent. Each contract
below governs a surface that still ships.

The refocus retired the contracts that described removed machinery: the evidence-block
format, JUnit XML enrichment, the OTel trace visual, listener integration, the
metrics-baseline and run-manifest schemas, the conformance fixture format, and the
0.x→1.x exit criteria. Those files were deleted. The survivors that had drifted carry
a short "Superseded by the four-surface refocus" note at the top and were trimmed to
match what ships.

## Convention

Every contract follows the same 4-section template, enforced by
`scripts/check-contract-sections.py` (mirrored in `.github/workflows/docs-build.yml`):

```markdown
# <Contract Name>

**Status:** accepted
**Related ADRs:** <comma-separated list>

## Purpose
(what this contract governs)

## Scope
### In-scope
### Out-of-scope

## Contract
(the formal specification)

## Change Policy
This contract evolves per [`stability-surface.md`](stability-surface.md) labels.

## References
```

The check greps every `*.md` file in this directory for the four required level-2
headers (`## Purpose`, `## Scope`, `## Contract`, `## Change Policy`) and fails CI when
any is missing.

## Index

| Contract | One-line description |
| --- | --- |
| [coding-conventions](coding-conventions.md) | Good/anti-pattern reference card for contributors — naming, type annotations, docstrings, error wording. |
| [determinism-contract](determinism-contract.md) | The 3-tier model (deterministic / LLM judge / coding agent) and its determinism guarantees. |
| [error-class-hierarchy](error-class-hierarchy.md) | `AgentEvalError` base plus the flat set of leaves, each with a stable `error_code` and exit code. |
| [mcp-coverage-detection](mcp-coverage-detection.md) | How MCPLibrary reports `mcp_coverage` via the trust-floor, and the `IncompleteTraceError` gate. |
| [metrics-contract](metrics-contract.md) | MCPLibrary's tool-call metric keywords — boundary rules, multi-trial aggregation, coverage gate. |
| [stability-surface](stability-surface.md) | The `stable` / `provisional` / `experimental` label scheme and the four-library surface it labels. |

## Maintaining this index

When a new contract is added:

1. Author the file at `<slug>.md` using the 4-section template above.
2. Append a row to the Index table (sorted alphabetically by slug).

Retirements (vs supersessions) are reserved for cases where the entire premise of a
contract no longer applies — the retired contract's file is deleted and its row removed
here.
