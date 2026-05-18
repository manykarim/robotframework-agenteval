# ADR-014: Error-Class Hierarchy

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A3 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A3. Renumbered to ADR-014 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

agenteval raises 9+ distinct error classes across its surface. FR49 (JUnit XML emission) and FR50 (exit-code mapping) need structured error information: a JUnit-emitting RF listener must surface `<failure type="...">` with semantically meaningful type strings, and the `agenteval` CLI must map raised errors to documented exit codes.

Currently no common base class exists. Each sub-library raising a custom error invents its own type and `error_code` convention, making programmatic catch (`except SomeFamily: ...`) inconsistent and making the FR49/FR50 mappings brittle.

## Decision

agenteval publishes a unified error hierarchy at `src/AgentEval/errors.py`:

- **Base:** `AgentEvalError(Exception)` — every agenteval-raised error inherits. Carries a structured `error_code: str` class attribute (e.g., `error_code = "INCOMPLETE_TRACE"`).

- **4 semantic sub-bases**, each mapping to a distinct exit-code family per FR50:

  | Sub-base | Leaf error classes | FR50 exit code |
  | --- | --- | --- |
  | `AgentEvalSafetyError` | `SandboxRequiredError`, `ValidateOperatorDisallowed` | 3 |
  | `AgentEvalBudgetError` | `CostExceededError`, `RuntimeBudgetExceededError` | 2 |
  | `AgentEvalCompatError` | `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `AdapterDiscoveryError`, `AdapterVersionDriftWarning` | 3 |
  | `AgentEvalIntegrityError` | `PollingDisallowedError`, `IncompleteTraceError`, `TierViolationError` | 2 or 3 (per-leaf override) |

- **Single import path:** `from AgentEval.errors import AgentEvalError, AgentEvalBudgetError, ...`.

- **Each leaf class sets its own `error_code` class attribute** (e.g., `class PollingDisallowedError(AgentEvalIntegrityError): error_code = "POLLING_DISALLOWED"`). The FR49 JUnit XML emitter reads `error_code` for the `<failure type="...">` attribute. The FR50 exit-code mapper reads it for the documented exit-code lookup.

- **11 leaves explicitly named** above (2 Safety + 2 Budget + 4 Compat + 3 Integrity); additional leaves require an ADR amendment to keep the surface auditable. (Count corrected 2026-05-18 by Story 1a.5 per Story 1a.3 code-review LOW-1 follow-up; the leaf-inventory table is authoritative.)

## Consequences

- `src/AgentEval/errors.py` is one file; the whole hierarchy lives in one place for grep-ability + documentation-ability.
- Conformance suite (ADR-005, ADR-017) validates `error_code` is populated for every raised leaf class — adapters that raise generic exceptions instead of the hierarchy fail conformance.
- A documentation contract `docs/contracts/error-class-hierarchy.md` is published as part of NFR-MAINT-04 doc deliverables (Story 1a.4) — contributors and consumers see the full error surface in one place.
- Cross-cutting concern #11 from the architecture's Project Context Analysis. Touches every sub-library that raises errors.
- **Adds 1 new doc contract to NFR-MAINT-04's enumerated list** (`error-class-hierarchy.md`).
- Programmatic catch is consistent: `try/except AgentEvalError` catches everything agenteval raises; `try/except AgentEvalBudgetError` catches just budget-family for retry-with-smaller-scope logic.

## Alternatives

- **Flat hierarchy (no semantic sub-bases)** — rejected. Consumers can't catch by semantic family; everyone catches `AgentEvalError` or specific leaves. Loses the retry-by-family pattern.
- **Inherit from `RobotError`** — rejected. Couples agenteval to RF internals; breaks for non-RF programmatic use (e.g., a Python script that imports `from AgentEval import AgentEval` directly).
- **Per-sub-library base classes (`MCPError`, `SkillError`, `CodingAgentError`, etc.)** — rejected. 4× more bases at the sub-library boundary with no semantic value for users; cross-cutting errors (e.g., `IncompleteTraceError` raised from `mcp/` but caught in user's `skills/` test) become awkward.
- **No structured `error_code` (just the class name as the type)** — rejected. Class-name-as-type couples consumers to internal naming; FR49 JUnit XML breaks every time we rename an error class.

## References

- Architecture L429-434 (renumbering plan) + §Cross-Cutting Concerns
- FR49 (JUnit XML emission) + FR50 (exit-code mapping) in PRD — the functional requirements this hierarchy serves
- ADR-007 (`mcp_coverage` + IncompleteTraceError) — `IncompleteTraceError` leaf
- ADR-008 (MCP Spec Version Validation) — `UnsupportedMCPVersionError` leaf
- ADR-013 (Entry-Points Discovery Infrastructure) — `AdapterDiscoveryError` leaf
- ADR-015 (Cost + Runtime Guardrail Decorator) — `CostExceededError` + `RuntimeBudgetExceededError` leaves
- ADR-018 (Sandbox Phase 1 Policy) — `SandboxRequiredError` leaf
- `docs/contracts/error-class-hierarchy.md` (to be authored by Story 1a.4)
