# ADR-017: Conformance Suite Organization — Per-AC Test Files + Per-Adapter Parametrize

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A7 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A7. Renumbered to ADR-017 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

The conformance suite (FR45 / AC-CONFORMANCE-01 / AC-CONFORMANCE-02) tests every registered adapter against the project's 9+ load-bearing acceptance criteria PLUS the structural shape contracts (`AgentRunResult`, `ToolCallTrace`, `AgentRunMetadata`).

- Phase 1 ships with 2 adapters (Generic LiteLLM + Claude Code CLI).
- Phase 2 adds 4 more (Claude Agent SDK, OpenAI Agents SDK, Codex CLI, Copilot CLI).
- Community Tier-2 adapters register via `agenteval.coding_agents` entry-point group at any time.

Without organizational discipline, the suite becomes unmaintainable at 10+ ACs × 6+ adapters. The pattern chosen affects how adapter authors run the suite locally, how AC failures surface, and how AC changes propagate.

## Decision

Conformance suite lives at `tests/conformance/` with the following organization:

**Per-AC test files** — one file per load-bearing acceptance criterion:

- `test_ac_simplicity_01_evidence_block.py`
- `test_ac_simplicity_02_keyword_idiom.py`
- `test_ac_discover_01_cohort.py`
- `test_ac_discover_02_cost_guardrail.py`
- `test_ac_dogfood_01_replacement.py`
- `test_ac_conformance_01_fidelity_oracles.py`
- `test_ac_conformance_02_completeness.py`
- `test_ac_mcp_observe_01_coverage.py`
- `test_ac_mcp_observe_02_version_gate.py`
- `test_ac_mcp_observe_03_per_test_scope.py`

Each test file parametrizes over all registered adapters via an `adapter_registry` fixture in `harness.py`. When a new adapter registers, every test in the suite runs against it without modifying any test file.

**Structural shape file** — `test_structural_shape.py` asserts the `AgentRunResult`/`ToolCallTrace`/`AgentRunMetadata` schemas hold across all adapters.

**Fixtures** — `tests/conformance/fixtures/<adapter_name>/<scenario_name>.json` for golden-trace fidelity oracles per ADR-005.

**Harness** — `tests/conformance/harness.py` provides:
- `adapter_registry` fixture — yields all registered adapters from `agenteval.coding_agents` entry-points.
- Truncation-injection mock-agent harness per ADR-006.
- Mock provider with known cost/runtime characteristics per ADR-015.

**Entry point** — `tests/conformance/__init__.py` enables `python -m agenteval.conformance [--adapter <name>]` per FR45 + FR57. Community adapter authors run this command against their adapter from outside agenteval's repo.

## Consequences

- ~12 test files Phase 1 (9 AC files + 1 structural shape + harness + `__init__.py`).
- Community adapter authors run `python -m agenteval.conformance --adapter <my_adapter>` per FR45 to verify their adapter; failures produce per-AC actionable reports per FR57 (JSON-on-stdout + human-summary-on-stderr).
- AC failures point directly to a single test file → directly to the violated AC. The traceability from RF acceptance criteria → conformance test file → adapter is 1:1 → 1:N (one AC tests N adapters).
- Adding a new Tier-1 adapter: register in `agenteval.coding_agents` entry-point group; author golden-trace fixtures at `tests/conformance/fixtures/<adapter_name>/`; the suite auto-discovers + runs. No test-file changes needed.
- AC changes (e.g., a new mandatory field added to `AgentRunResult`): edit one test file; every adapter re-tested automatically.
- Architectural concern #11 from the architecture's Project Context Analysis (test infrastructure deliverable, NOT cross-cutting kernel concern).
- The conformance workflow (`conformance.yml` from Story 1a.2) runs this suite on a per-release schedule, NOT per-PR — it's slow-by-design (each test runs the real adapter against the real scenario).

## Alternatives

- **Per-adapter test files** (`test_generic_adapter.py`, `test_claude_code_cli.py`, ...) — rejected. Replicates ACs across adapters; an AC change requires N file updates. Worse, an adapter that "skipped" an AC requirement looks structurally indistinguishable from one that "implemented" it.
- **Per-capability-area files** (`test_static_inspection.py`, `test_dynamic_eval.py`, ...) — rejected. Mixes ACs within a file; failures don't point to a specific AC; AC ↔ test traceability is harder to maintain.
- **Single monolithic `test_conformance.py`** — rejected. Unwieldy at 10+ ACs × 6+ adapters; failures pile into one test file with verbose parametrize IDs.
- **Skipping AC-grouped organization entirely; rely on docstrings to label ACs** — rejected. Docstrings drift from filenames; the filename-as-AC-reference convention is more robust for grep/CI annotation purposes.

## References

- Architecture L429-434 (renumbering plan) + §Tests Folder Structure
- FR45 (conformance suite + per-adapter invocation) + FR57 (per-AC reporting) + AC-CONFORMANCE-01/02 (PRD)
- ADR-003 (CodingAgentAdapter Protocol) — adapter registration mechanism
- ADR-005 (Conformance Suite Fidelity Oracles) — golden-trace fixtures consumed by these tests
- ADR-006 (Completeness Field) — truncation-injection scenarios in this harness
- ADR-007 (mcp_coverage) + ADR-008 (Spec Version Validation) — tested by `test_ac_mcp_observe_*` files
- ADR-013 (Entry-Points Discovery) — `adapter_registry` fixture mechanism
- ADR-015 (Guarded Fanout Decorator) — `test_ac_discover_02_cost_guardrail.py` tests the decorator
- Story 1a.2 `conformance.yml` workflow — per-release CI scheduling
