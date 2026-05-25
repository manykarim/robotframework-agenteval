# Exit Criteria: 0.x → 1.x

**Status:** accepted (Story 9.3 Phase-1 close, 2026-05-25 — concrete numeric bars finalized).
**Owning epic:** Epic 9 Story 9.3 (final content); Story 1a.6 (initial stub).
**Related ADRs:** none directly; informed by all Phase-1 ADRs as the documented "Phase 1 complete" gate.
**Related FRs:** FR65 (Exit Criteria — Phase-1 to Phase-2 transition gate).

## Purpose

Documents the **objective gates** that must be satisfied before agenteval is released as `1.0.0` (general availability). Per the project's `feedback_honest_framing` working norm, the criteria are numeric where possible (counts, percentages, pass/fail booleans) — not vibes. This contract is the architect's commitment to consumers: agenteval will not pretend it's stable until it actually meets these gates.

## Scope

### In-scope

- Required functional criteria (which FRs MUST be wired + tested before 1.0).
- Required non-functional criteria (which NFRs MUST be measured + meet their bars).
- Required dogfood signal (rf-mcp + robotframework-agentskills integration evidence per NFR-REL-05).
- Required documentation criteria (which contracts in `docs/contracts/` MUST have populated content; which recipes in `docs/recipes/` MUST exist).
- Required adoption signals (external contributor count + documented downstream use cases).
- Documented carry-forwards (items intentionally deferred to Phase 1.5 or Phase 2 with rationale).

### Out-of-scope

- Phase-2 scope decisions (those are PRD §`Phase 2 Scope` + a future epic decomposition; this contract documents the boundary, not the next phase).
- Marketing positioning + GA announcement copy.

## The 6 promotion criteria

| # | Criterion | Numeric bar | Verification path | Phase-1 status |
| --- | --- | --- | --- | --- |
| 1 | **Conformance coverage** | ≥90% of public keywords pass conformance suite against ≥2 Tier-1 adapters (Generic LiteLLM + Claude Code CLI per ADR-002). | `python -m AgentEval.conformance --adapter generic` + `--adapter claude_code` both report `summary.passed / summary.total ≥ 0.9`. | ⚠ Conformance CLI ships Story 8a.2 with `status="skipped"` Phase-1 records (DF-8a.2-S1 / C63). Real adapter dispatch wires in Phase-1.5. **Blocker for 1.0**. |
| 2 | **Dogfood parity (sustained)** | rf-mcp + agentskills parity suites green for ≥3 consecutive months in `dogfood-integration.yml`. | `parity-suite-smoke` + `agentskills-parity-suite-smoke` jobs (Story 9.1 + 9.2) green across 12+ consecutive weekly runs. | ⚠ Workflows shipped in Stories 9.1 + 9.2. **3-month sustained window starts on first green release run** (Phase-1 close validator manual verification per DF-9.1-S1 / C65 + DF-9.2-S1 / C66). |
| 3 | **ADR completeness** | All 19 ratified ADRs at `accepted` status (per `docs/adr/`); zero forward-reference banners in shipped code/docs. | `grep -rE "Phase 1\.5\|Phase 2\|forward[- ]ref" docs/ src/ \| wc -l` ≤ documented carry-over count (currently 66 entries in `phase-1-5-carry-overs.md`). | ⚠ Some Phase-1.5 forward-refs remain (per DF-8a.1-S1 leaf-attribute work; DF-8b.3-S1 recipe CI extraction; etc.). **All must resolve OR be explicitly demoted to `experimental` before 1.0**. |
| 4 | **Public API stability** | ≥3 months without breaking changes to `stable`-marked surface; zero `provisional` entries in `docs/contracts/stability-surface.md` at 1.0 release. | `git log --since="3 months ago" -- src/AgentEval/__init__.py` shows no breaking-API commits; `grep -c "provisional" docs/contracts/stability-surface.md` = 0. | ⚠ Phase-1 ships `AgentEval` class + 9 config params + `Get Effective Config` as `provisional` (Story 1a.6 registry). **3-month-no-break window starts when last `provisional` is resolved**. |
| 5 | **External contributors** | ≥3 external contributors with merged PRs (≠ project owner). | `git shortlog -sn HEAD` reports ≥4 distinct authors (1 project owner + 3 external). | ❌ Phase-1 solo + AI-agent-assisted (0 external contributors as of Phase-1 close). **Blocker for 1.0**; pre-requires public-release announcement + community-onboarding work in Phase-2 / Epic 13+. |
| 6 | **Documented downstream use cases** | ≥1 documented use case beyond rf-mcp + agentskills (e.g., a third downstream library OR a new persona-specific recipe demonstrating real-world adoption). | `docs/recipes/` carries ≥1 case study referencing a downstream consumer not named `rf-mcp` or `robotframework-agentskills`. | ❌ Phase-1 dogfood is rf-mcp + agentskills only. **Blocker for 1.0**; pre-requires Phase-2 outreach + recipe authoring. |

**At Phase-1 close (2026-05-25): 0 of 6 criteria fully satisfied; 4 ⚠ (work shipped, sustained-window evidence collection pending); 2 ❌ (community + adoption work explicitly Phase-2).**

## Functional coverage (FRs delivered Phase-1)

Per PRD §Functional Requirements + the cross-references in epic story sprint-status entries:

- **Wired + tested (Epic 0 → 9):** FR1–FR4d (skill validation + activation), FR5–FR9b (MCP static + runtime), FR10a (MVP discoverability), FR11/FR11b (guardrails), FR12–FR17a (adapters + entry-points), FR18 (`new-adapter`), FR19–FR22 (metrics — token / cost / latency), FR23–FR25 (assertions), FR26–FR31b (stats + tier ACL), FR32–FR40 (trace observability), FR41–FR48 (config + library bootstrap), FR49–FR51 (CI integration), FR52 (`agenteval init`), FR54 (terminal summary), FR55-ASCII+dict (CohortHeatmap), FR56–FR58 (polling-ban regex + conformance report + OTel trace visual doc), FR59 (Tier-1 setup-failure error format), FR60–FR62 (warnings + run manifest), FR63–FR64 (deterministic doc + stability surface), FR65 (this Exit Criteria doc).
- **Phase-2 deferred (explicitly):** FR4c (cross-adapter Skill Discoverability variant) → Epic 13 Story 13.5. FR10b/c (Phase-2 Tool Discoverability variants) → Epic 13. FR53 (auto-discovery via PyPA entry-points) → Phase-2 per `listener-integration.md`.

## Non-functional criteria (NFRs validated Phase-1)

- **NFR-COMPAT-06** (single-file `gen_ai.*` + `agenteval.*` facade): ✅ enforced via `tests/conformance/test_otel_semconv_facade.py`.
- **NFR-SEC-01** (redaction choke point): ✅ Story 5.3 + Story 1b.2.
- **NFR-REL-05** (cross-repo dogfood): ⚠ Phase-1 install-smoke + Story 9.1/9.2 parity-suite-smoke jobs shipped; 3-month sustained window pending.
- **NFR-UX-01** (5-min first-run): ✅ Story 8b.1 `agenteval init` + Recipe #1 + integration test verifies end-to-end <5 min.
- **NFR-MAINT-04** (contract docs as first-class deliverables): ✅ 11 `docs/contracts/*.md` files populated by Phase-1 close.

## Documentation coverage

- ✅ 11 `docs/contracts/*.md` files populated (no Phase-1 stubs remain after this Story 9.3 rewrite).
- ✅ 8 Phase-1 recipes shipped (#1 from Story 8b.1, #2–#8 + #4 polished from Story 8b.3).
- ✅ libdoc rendered via `docs-build.yml` (Epic 1a) + asserted via `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- ✅ ADR catalog at `docs/adr/` with 19 ratified entries.
- ✅ Phase-1.5 carry-over catalog at `docs/phase-1-5-carry-overs.md` (66 entries).
- ✅ Phase-1 retrospective at `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md` (Story 9.3 deliverable).

## Phase-1.5 carry-over registry (high-level)

Full registry at `docs/phase-1-5-carry-overs.md` (66 entries as of Phase-1 close). High-level categories:

- **Hygiene (XS / S):** docstring drift fixes, dead-code removal, citation-line precision, caller-gap entries (~32 entries).
- **Correctness (M / L):** conformance-CLI real adapter dispatch (C63); per-leaf exit_code ClassVar (C62); listener-variable trigger (C63); recipe CI extraction (C64); `@guarded_fanout` MCPLibrary legacy gap (Epic 4 retro Action #6 inherited, 5+ epics old); SkillsLibrary budget propagation (C55) (~24 entries).
- **Downstream-adoption-blocked (L):** rf-mcp adoption + 38-test batch port + 7-day monitoring (C65); agentskills adoption + 7-day monitoring (C66); 8 remaining agentskills skills + live-provider quality (C60) (~3 entries).
- **Phase-2 (M):** multi-turn agent loop (C43); adapter span instrumentation (C44); Wilson CI for pass_at_k (C58); cross-adapter Discoverability (FR4c → Epic 13) (~7 entries).

Each carry-over documented with effort estimate (XS / S / M / L / XL) + target story OR explicit Phase-2 deferral.

## Change Policy

This contract is `accepted`-status from Phase-1 close onward. The 6 criteria above are the **canonical 1.0 gates**. Changes require an architect-approved ADR amendment + a documented migration plan for any consumer relying on a removed criterion.

The numeric bars are minimum thresholds; exceeding them is fine. Adding new criteria is minor-version-bump safe at the contract level (any added criterion delays 1.0 but doesn't break existing 0.x users). Relaxing a criterion (lowering a bar) is a breaking change requiring major-contract-version bump.

## References

- FR65 (PRD): Exit Criteria documentation.
- Epic 9 Story 9.3 (this story): final content authoring.
- NFR-MAINT-04: this contract is one of the first-class doc deliverables.
- D2.1 architect waiver (Story 0.2 review): macOS deferred to Phase-1.5.
- `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md` (Story 9.3): retrospective + scorecard.
- `docs/phase-1-5-carry-overs.md`: full carry-over catalog (66 entries).
- `docs/adr/`: 19 ratified ADRs.
