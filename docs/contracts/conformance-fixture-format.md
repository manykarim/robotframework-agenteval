# Conformance Fixture Format

**Status:** Phase-1 skeleton — content to be filled by Epic 1b Story 1b.5 (Conformance Harness Loader + 6 Reference Fixtures).
**Owning epic:** Epic 1b Story 1b.5
**Related ADRs:** ADR-005 (Conformance Suite Includes Fidelity Oracles), ADR-017 (Conformance Suite Organization — per-AC test files + per-adapter parametrize)
**Related FRs:** FR45 (Conformance suite), AC-CONFORMANCE-01 (Fidelity oracles), AC-CONFORMANCE-02 (Completeness oracle)

## Purpose

Governs the **schema + authoring guide for golden-trace fixtures** at `tests/conformance/fixtures/<adapter_name>/<scenario_name>.json`. Each fixture captures the canonical `AgentRunResult` an adapter MUST produce when run against a fixed scenario from the deterministic mock harness. Community adapter authors author their own fixtures locally + submit alongside their adapter PR.

## Scope

### In-scope

- JSON schema of the fixture file (top-level keys, types, optionality).
- The "strict-match" vs "constraint-match" rules per field (e.g., `latency_ms` is `>0` constraint; `metadata.completeness` is exact-match).
- Mock-agent + fixed-scenario fixture catalog (what the 6 Phase-1 reference fixtures cover).
- Adapter-authoring workflow: how a contributor authors a new fixture (run the mock harness against their adapter, capture output, hand-tune allowable variations).
- Test-suite consumption: how `tests/conformance/test_ac_*.py` files load + assert against fixtures via the `adapter_registry` fixture.

### Out-of-scope

- The mock agent's internal implementation (`tests/conformance/harness.py`) — that's libdoc + ADR-017.
- Per-adapter `AgentRunResult` schema — that's `evidence-block-format.md` + ADR-006/007.

## Contract

*Phase-1 skeleton — Epic 1b Story 1b.5 fills in the formal specification.*

The contract will at minimum include:

- JSON schema for fixture files (validates via `jsonschema` per Story 1a.1's `jsonschema>=4.0,<5.0` dependency).
- Per-field strict-match vs constraint-match rules (with examples).
- The 6 Phase-1 reference fixtures' names + scenarios + expected behavior.
- Adapter-authoring workflow: a 5-step checklist for community adapter authors.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The fixture schema is `provisional` in Phase 1 (Story 1b.5 finalizes); after Story 1b.5 it promotes to `stable`. Adding fields with optional default is minor-version-bump safe; removing a field requires major-version bump (breaks existing fixtures).

## References

- ADR-005: Conformance Suite Includes Fidelity Oracles
- ADR-017: Conformance Suite Organization
- Story 1a.2 `conformance.yml` workflow runs these fixtures per release
- FR45 + AC-CONFORMANCE-01/02 (PRD)
