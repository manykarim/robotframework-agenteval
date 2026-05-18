# Determinism Contract

**Status:** Phase-1 skeleton — content to be filled by Epic 1b (Foundational Kernel stories).
**Owning epic:** Epic 1b — Foundational Kernel
**Related ADRs:** ADR-014 (Error-Class Hierarchy — `PollingDisallowedError`, `TierViolationError`), ADR-022 catalog row (AssertionEngine adoption — polling-ban + validate-disabled negative-consequence clauses)
**Related FRs:** FR26-31 (Statistical primitives + Tier model + ACL gates + determinism contract)

## Purpose

Governs the **determinism guarantees** agenteval offers (and explicitly does NOT offer) for evaluation runs. Specifically: which keywords are deterministic by construction, which are stochastic and how their non-determinism is bounded (`Stat.Run N Times`, `Stat.Pass At K`), which keyword families forbid retry-style polling (`PollingDisallowedError`), and which Tier of model is allowed at each ACL gate (`TierViolationError`).

## Scope

### In-scope

- The 3-tier model (Tier-1 static inspection / Tier-2 single-LLM-call / Tier-3 fan-out + statistical) — see `### Tier Model` subsection.
- Polling-ban policy on Tier-2/3 keywords (raises `PollingDisallowedError` per ADR-014).
- `validate`-operator disabled by default (raises `ValidateOperatorDisallowed`; opt-in via `allow_validate_operator=True` per FR43).
- ACL gates: which user-supplied callable/keyword combinations are blocked at each tier.

### Out-of-scope

- Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap) — that's the `Stat.` library docstrings + `stability-surface.md`.
- The specific seed-management strategy for `Stat.Run N Times` — Epic 6 Story 6.x owns the seed contract.

## Contract

*Phase-1 skeleton — Epic 1b fills in the formal specification.*

### Tier Model

agenteval keywords belong to one of three tiers (formalized 2026-05-18 per ADR-011 + this contract):

- **Tier-1 (static inspection):** zero LLM calls per invocation. Examples: `Skill.Get Activation Decision` (parses skill YAML), `MCP.List Tools` (reads schema). Deterministic by construction.
- **Tier-2 (single LLM call):** one provider call per invocation. Examples: `Run Scenario` (one agent run), `Trajectory.Compare`. Non-determinism bounded by provider temperature + seed where supported.
- **Tier-3 (fan-out + statistical):** N provider calls per invocation, statistical aggregation. Examples: `Stat.Run N Times`, `Stat.Pass At K`, `MCP.Get Tool Discoverability`. Cost + runtime guardrails per ADR-015 `@guarded_fanout` decorator.

ACL gates per-tier: Tier-1 may not call Tier-2/3 internally; Tier-2 may not embed Tier-3 fan-outs; Tier-3 may compose any tier. Violations raise `TierViolationError` per ADR-014.

Phase-1 enforcement: subject to ADR-022 catalog row (`adapt`) + AssertionEngine adoption ADR (Phase 2). Phase-1 enforces via direct raise from `_kernel/`; Phase-2 adoption of `robotframework-assertion-engine` formalizes the contract surface.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-tier model is `stable` from Phase-1 onward — changes to tier definitions require major-version bump per NFR-MAINT-03. ACL gate additions are minor-version-bump safe; loosening an existing gate requires major bump (it weakens a documented guarantee).

## References

- ADR-014: Error-Class Hierarchy (`PollingDisallowedError`, `TierViolationError`, `ValidateOperatorDisallowed`)
- ADR-011: Three-Persona Model (the tier model serves the QA Engineer + Agent Developer personas)
- ADR-022 catalog row in `docs/adr/ADR-001-architectural-influences-catalog.md`: AssertionEngine adoption
- FR26-31 (PRD): Statistical primitives + Tier-1/2/3 model + ACL gates + determinism contract
