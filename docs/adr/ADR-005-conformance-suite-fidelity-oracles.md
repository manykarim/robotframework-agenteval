# ADR-005: Conformance Suite Includes Fidelity Oracles

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-008 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-008. Renumbered to ADR-005 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

A conformance suite that asserts only structural shape (e.g., "`ToolCallTrace` has `latency_ms: float`") can be passed by an adapter that emits nonsense data: all-zero latencies, hallucinated `sequence_index` ordering, fake `source` attribution. Structural conformance is necessary but not sufficient — it tells you the adapter speaks the schema, not that the adapter speaks the truth.

agenteval's goal is community-contributed adapters at Tier-1 quality (AC-CONFORMANCE-01 / AC-CONFORMANCE-02). The conformance suite is the published contract that adapter authors implement against. Without fidelity oracles, the suite defends against adversarial passes only structurally; well-meaning-but-broken adapters and adversarially-passing adapters both slip through.

## Decision

The conformance suite includes **golden-trace fixtures** as the executable spec for fidelity:

- A **deterministic mock agent** is published in `tests/conformance/harness.py`. It implements `CodingAgentAdapter` with hardcoded responses for a fixed scenario set (e.g., "the mock agent always emits 3 tool calls in this specific order against this specific MCP server").
- For each fixed scenario, a **golden-trace fixture** is recorded as JSON at `tests/conformance/fixtures/<adapter_name>/<scenario_name>.json`. The fixture captures the canonical `AgentRunResult` an adapter should produce for that scenario.
- Each adapter-under-test runs the fixed scenario and produces an `AgentRunResult`. The conformance suite asserts the output matches the golden fixture's structure AND its values, with **documented allowable variations**:
  - `latency_ms`: assert `> 0`, not exact value (real adapter timings vary).
  - `tool_call.timestamp`: assert ISO-8601-parseable + monotonically non-decreasing within a run, not exact wall-clock value.
  - `metadata.completeness`: must match golden fixture exactly (truncation injection per ADR-006 is the test).

Allowable-variation rules are documented per-field in `docs/contracts/conformance-suite.md` so adapter contributors know which fields are strict-match and which are constraint-match.

## Consequences

- Mock agent + fixed-scenario fixtures must ship in Phase 1 as part of the conformance suite deliverable.
- Adding a new Tier-1 adapter requires authoring its golden fixtures for each in-scope scenario. This is intentional friction: the per-adapter fixture authoring is the "I have actually run this adapter against the scenario and verified the output" gate.
- Community adapter authors get the fixture format published as part of the conformance-suite release; they author their own golden fixtures locally and submit them with their adapter PR.
- Conformance suite tests are slow-by-design (run real adapter against real scenario each test). They run in CI on `conformance.yml` (per-release), not on `ci.yml` (per-PR) — see Story 1a.2 + ADR-017.
- Disagreements between adapter-output and golden fixture trigger conformance failure. Resolution path: adapter author either fixes the adapter OR proposes an amendment to the golden fixture via ADR amendment to this one.

## Alternatives

- **Structural conformance only** — rejected. Original PRD draft; identified as a critical hole during ADR review. Lets adversarial/broken adapters pass.
- **Property-based testing (Hypothesis)** — rejected for the primary suite. Better at finding edge cases than at verifying "did you implement the documented behavior." Useful as a supplementary layer (Phase 2+); not a substitute for golden fixtures.
- **Manual review per adapter** — rejected. Doesn't scale beyond Tier 1's hand-curated adapter set; Tier 2 community adapters get no review-time gating from agenteval maintainers.

## References

- PRD §`Conformance Strategy` + AC-CONFORMANCE-01/02 (sidecar source, 2026-05-15)
- ADR-006 (AgentRunResult.metadata.completeness Field Required) — truncation-injection scenarios test this field via golden fixtures
- ADR-017 (Conformance Suite Organization) — directory layout + per-AC test files + `adapter_registry` fixture
