# Exit Criteria: 0.x → 1.x

**Status:** Phase-1 skeleton — content to be filled by Epic 9 Story 9.3 (Phase 1 retrospective + FR65 exit criteria doc final content).
**Owning epic:** Epic 9 — Dogfood Validation + Phase 1 Close
**Related ADRs:** none directly; informed by all Phase-1 ADRs as the documented "Phase 1 complete" gate.
**Related FRs:** FR65 (Exit Criteria — Phase-1 to Phase-2 transition gate)

## Purpose

Documents the **objective gates** that must be satisfied before agenteval is released as `1.0.0` (general availability). Per the project's `feedback_honest_framing` working norm, the criteria are numeric where possible (counts, percentages, pass/fail booleans) — not vibes. This contract is the architect's commitment to consumers: agenteval will not pretend it's stable until it actually meets these gates.

## Scope

### In-scope

- Required functional criteria (which FRs MUST be wired + tested before 1.0).
- Required non-functional criteria (which NFRs MUST be measured + meet their bars).
- Required dogfood signal (rf-mcp + robotframework-agentskills integration evidence per NFR-REL-05).
- Required documentation criteria (which contracts in `docs/contracts/` MUST have populated content; which recipes in `docs/recipes/` MUST exist).
- Documented carry-forwards (items intentionally deferred to Phase 1.5 or Phase 2 with rationale).

### Out-of-scope

- Phase-2 scope decisions (those are PRD §`Phase 2 Scope` + a future epic decomposition; this contract documents the boundary, not the next phase).
- Marketing positioning + GA announcement copy.

## Contract

*Phase-1 skeleton — Epic 9 Story 9.3 fills in the formal specification at Phase 1 retrospective.*

The exit criteria will at minimum include:

- **Functional coverage:** all 56 Phase-1 FRs from PRD §Functional Requirements are wired + tested (per conformance suite + acceptance suite + unit suite).
- **Adapter coverage:** ≥2 Tier-1 adapters fully implemented (Phase 1 target: Generic LiteLLM + Claude Code CLI). Each adapter passes the full conformance suite.
- **Dogfood signal:** `rf-mcp` + `robotframework-agentskills` import agenteval + their conformance suites run against the agenteval wheel and produce per-AC reports. Per NFR-REL-05.
- **Documentation coverage:** all 11 `docs/contracts/` files have populated content (not Phase-1 stubs); ≥8 Phase-1 recipes in `docs/recipes/`; libdoc rendered + asserted via `docs-build.yml`.
- **Stability surface:** every public element has a stability label per FR64; no public elements unlabeled.
- **Phase-1.5 carry-over registry:** macOS validation, SHA-pinning of CI actions, full dogfood integration tests (Story 1a.2's `continue-on-error: true` removed), Phase-1 CLI proxy at `src/AgentEval/conformance/`. Each carry-over documented with target story.

Exact numeric bars + final criteria ratified at Epic 9 Story 9.3.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The criteria list itself is `provisional` until Epic 9 Story 9.3 ratifies the final form. After Story 9.3: changes to the criteria require an architect-approved ADR amendment + a documented migration plan for any consumer relying on a removed criterion.

## References

- FR65 (PRD): Exit Criteria documentation
- Epic 9 Story 9.3: owns final content authoring
- NFR-MAINT-04: this contract is one of the first-class doc deliverables
- D2.1 architect waiver (Story 0.2 review): macOS deferred to Phase-1.5 — documented as a carry-over
