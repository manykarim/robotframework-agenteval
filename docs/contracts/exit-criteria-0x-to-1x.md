# Exit Criteria: 0.x → 1.x

**Status:** accepted (Story 1a.6 initial stub; concrete numeric bars filled by Epic 9 Story 9.3 at Phase 1 retrospective).
**Owning epic:** Epic 9 Story 9.3 — Dogfood Validation + Phase 1 Close (final content); Story 1a.6 — initial stub
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

**Phase-1 initial stub.** The 4 promotion criteria placeholders below are ratified by Story 1a.6 (2026-05-18). Concrete numeric bars (the `TBD` placeholders) are filled by Epic 9 Story 9.3 at Phase 1 retrospective.

### Promotion criteria (4 placeholders)

| # | Criterion | Phase-1 placeholder text | Rationale |
| --- | --- | --- | --- |
| 1 | **Conformance coverage threshold** | `≥<N>% of public keywords pass conformance suite against ≥2 Tier-1 adapters` (`N` TBD) | Filled in Phase 1 close per FR65; agenteval's `1.0` promise is that public keywords work consistently across adapters. The numeric threshold is empirically anchored at Phase 1 retrospective when the actual conformance-suite hit-rate is measurable across the 2 Tier-1 adapters (Generic LiteLLM + Claude Code CLI per ADR-002 Tier-1 ceiling). |
| 2 | **Dogfood parity bar** | `rf-mcp + robotframework-agentskills full-parity test suites green against agenteval wheel` (parity scope TBD) | Filled in Phase 1 close per FR65. Story 1a.2's `dogfood-integration.yml` is currently Phase-1 install-smoke (per Story 1a.2 HIGH-1 ratification); Story 9.1+9.2 land the full cross-repo integration. Exit criterion = Story 9.1+9.2 both green with `continue-on-error: true` removed. |
| 3 | **ADR completeness** | `all 18 ratified ADRs have epic-implementation status confirmed (no forward-reference banners in shipped code/docs)` | Filled in Phase 1 close per FR65. Currently SECURITY.md still has 1 forward-ref banner (NFR-SEC-01: `config.redact_env()` + `config.add_redaction_pattern()` are Epic 5 Story 5.3 deliverables). After Epic 5 Story 5.3 + Epic 6 ships, every forward-ref banner across the corpus must be either retired (replaced with current-state language) OR explicitly carried to Phase 1.5. |
| 4 | **Public API stability period** | `all "provisional" stability-surface entries promoted to "stable" OR demoted to "experimental"; zero "provisional" at 1.0 release` | Filled in Phase 1 close per FR65. `docs/contracts/stability-surface.md` currently labels `AgentEval` class + its 9 config params + `Get Effective Config` keyword as `provisional` (Story 1a.6 Phase-1 registry). 1.0 promotion requires either: (a) provisional → stable (with documented semver guarantees), or (b) provisional → experimental (with documented unstable-by-design status). No `provisional` entries at 1.0 release. |

### Additional Phase-1-close documentation requirements (Epic 9 Story 9.3 will detail)

The exit criteria document at Phase 1 close (Epic 9 Story 9.3) will additionally cover:

- **Functional coverage:** which Phase-1 FRs from PRD §Functional Requirements are wired + tested (per conformance suite + acceptance suite + unit suite).
- **Documentation coverage:** all `docs/contracts/*.md` files (11 contract files + `README.md` index = 12 total) have populated content (not Phase-1 stubs); ≥8 Phase-1 recipes in `docs/recipes/`; libdoc rendered + asserted via `docs-build.yml`.
- **Phase-1.5 carry-over registry:** macOS validation (D2.1 architect waiver), SHA-pinning of CI actions (Story 1a.2 LOW-3 deferred), full dogfood integration tests (Story 1a.2 + Stories 9.1/9.2), `src/AgentEval/conformance/` CLI proxy (Story 1a.4 HIGH-2 forward-reference), DCO check workflow (Story 1a.5 MED-3 deferred), PR template (Story 1a.5 LOW-8 deferred). Each carry-over documented with target story.

The 4 criteria + the additional requirements are the **objective bar** for agenteval to claim 1.0. Per `feedback_honest_framing` working norm, numeric bars MUST be specified (no vibes — empirical thresholds anchored to Phase-1-retrospective data).

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The criteria list itself is `provisional` until Epic 9 Story 9.3 ratifies the final form. After Story 9.3: changes to the criteria require an architect-approved ADR amendment + a documented migration plan for any consumer relying on a removed criterion.

## References

- FR65 (PRD): Exit Criteria documentation
- Epic 9 Story 9.3: owns final content authoring
- NFR-MAINT-04: this contract is one of the first-class doc deliverables
- D2.1 architect waiver (Story 0.2 review): macOS deferred to Phase-1.5 — documented as a carry-over
