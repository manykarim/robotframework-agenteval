# Story 9.2: Verify robotframework-agentskills Full Parity

Status: done

## Story

As a **Phase 1 close validator**,
I want `robotframework-agentskills` similarly verified to `rf-mcp` (Story 9.1) — full custom-test surface ported to `.robot` suites using Epic 6 metric keywords + Epic 7 Skill activation flow,
so that AC-DOGFOOD-01 is satisfied for both dogfood targets, not just one.

## Pre-create-story drift check (41st use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-25)

100% catch rate intact. 3 drifts caught:

- **D-1 (HIGH-decision):** Same as Story 9.1 D-1 — Phase-1 scope = gap-analysis + checklist closure + workflow extension; 7-day monitoring + downstream adoption deferred to DF-9.2-S1 / C66.
- **D-2 (MED):** Recipe #5 already has a rf-mcp worked example from Story 9.1. Story 9.2 amends Recipe #5 with a *second* worked example using agentskills' skill-discoverability port (Story 7.4) — demonstrates the same dogfood pattern applied to skills (not just MCP).
- **D-3 (LOW):** robotframework-agentskills has 11 skills; Story 7.4 dogfood ports 3 of them (rf-browser, rf-results, rf-libdoc-search per Story 7.4 D-4 scale constraint). The remaining 8 are deferred to "Epic 9" per DF-7.4-S1 / C60. Story 9.2 confirms this deferral + cross-references C60 — does NOT port the remaining 8 (Phase-2 work per DF-7.4-S1 closure note).

## Acceptance Criteria

### AC-9.2.1 — Gap analysis: every agentskills custom test classified

Inventory `robotframework-agentskills` `tests/test_*.py` + classify each test (port / stays-custom / Phase-2-batch). Result in `tests/dogfood/agentskills/parity-checklist-agentskills-FULL.md`.

### AC-9.2.2 — VALIDATION-CEILING lines on all agentskills parity checklists

Amend:
- `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md`
- `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md`
- (new) `parity-checklist-agentskills-FULL.md`

### AC-9.2.3 — Devon's Journey 4 Phase-1 portion exercised against real skills

Per AC L1969. Story 7.4 already runs the discoverability cohort against 3 real `robotframework-agentskills` skills (rf-browser, rf-results, rf-libdoc-search) with the stub-adapter limitation documented in C60. Story 9.2 confirms this is the Phase-1 closure state + documents the live-LLM Phase-2 extension path in C66.

### AC-9.2.4 — dogfood-integration.yml extended for agentskills

Add a sibling `agentskills-parity-suite-smoke` job (or extend the Story 9.1 job) that clones agentskills + runs the 3 dogfood suites: `test_metrics_parity.robot`, `test_assertions_parity.robot`, `test_skill_discoverability.robot`.

### AC-9.2.5 — Recipe #5 amended with agentskills worked example

Per D-2. Append a second worked example showing the skill-discoverability port pattern (Story 7.4).

### AC-9.2.6 — DF-9.2-S1 / C66 catalogued

Phase-2 work: downstream adoption + 8-remaining-skill discoverability coverage + 7-day monitoring evidence.

### AC-9.2.7 — `feedback_carry_over_catalog_gate` UPSTREAM (20th consecutive)

### AC-9.2.8 — All-gates pass

1353 pytest pass unchanged; ruff/format/mypy clean.

## Tasks / Subtasks

- [x] **Task 1**: inventory `robotframework-agentskills` tests + classify each.
- [x] **Task 2**: create `parity-checklist-agentskills-FULL.md` synthesis.
- [x] **Task 3**: VALIDATION-CEILING amendments on existing 2 parity checklists.
- [x] **Task 4**: extend `dogfood-integration.yml` with agentskills parity-suite-smoke job.
- [x] **Task 5**: amend Recipe #5 with agentskills worked example.
- [x] **Task 6**: catalog DF-9.2-S1 / C66.
- [x] **Task 7**: all-gates run.
- [x] **Task 8**: sprint-status → done.

## Dev Notes

agentskills' existing parity surface (Story 6.4 + Story 7.4):
- `parity-checklist-agentskills-metrics.md` — Story 6.4 (3 metrics suites + helper).
- `parity-checklist-agentskills-discoverability.md` — Story 7.4 (3 skills + DOGFOOD-FINDING-1 stub limitation).

Existing dogfood files in this repo:
- `test_metrics_parity.robot` (Story 6.4)
- `test_assertions_parity.robot` (Story 6.4)
- `test_skill_discoverability.robot` (Story 7.4)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

Story 9.2 complete 2026-05-25. All 8 ACs satisfied. Parallel to Story 9.1 pattern (verification/docs-only closure).

- **AC-9.2.1**: agentskills surface classified at `tests/dogfood/agentskills/parity-checklist-agentskills-FULL.md`. Phase-1 Surface: metrics+assertions+stats (Story 6.4) + 3-of-11-skills discoverability (Story 7.4) = 100% covered for Phase-1 scope. 8 remaining skills + live-provider quality deferred to C60 (existing carry-over, NOT a new one).
- **AC-9.2.2**: VALIDATION-CEILING lines on both existing checklists + new FULL doc.
- **AC-9.2.3**: Devon's Journey 4 Phase-1 end-to-end verified — Tier-1 static (Story 2.1) + Tier-3 cohort + activation reliability (Story 7.1/7.2/7.3/7.4) against rf-browser, rf-results, rf-libdoc-search real skills. Tier-2 Judge is Phase-2 (Recipe #4 placeholder).
- **AC-9.2.4**: `agentskills-parity-suite-smoke` job added to `dogfood-integration.yml` — runs 3 vendored dogfood suites (metrics + assertions + discoverability).
- **AC-9.2.5**: Recipe #5 amended with agentskills worked example (parallel-derivation pattern variation vs rf-mcp's 1:1 port).
- **AC-9.2.6**: DF-9.2-S1 / C66 catalogued.
- **AC-9.2.7**: `feedback_carry_over_catalog_gate` UPSTREAM (20th consecutive).
- **AC-9.2.8**: 1353 pytest pass (unchanged); ruff/format/mypy clean (94 src files).

### File List

**New files:**
- `tests/dogfood/agentskills/parity-checklist-agentskills-FULL.md` — synthesis gap-analysis doc.

**Modified files:**
- `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md` — VALIDATION-CEILING line.
- `tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md` — VALIDATION-CEILING line.
- `.github/workflows/dogfood-integration.yml` — new `agentskills-parity-suite-smoke` job.
- `docs/recipes/05-dogfood-replacing-custom-tests.md` — agentskills worked example section.
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-9.2-S1 entry.
- `docs/phase-1-5-carry-overs.md` — C66 row + counter to 66.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-25 | 0.1.0 | Initial story creation. 41st use of `feedback_spec_vs_ratified_doc_precheck` (100% catch rate intact). 3 drifts: D-1 7-day monitoring deferred (DF-9.2-S1/C66); D-2 Recipe #5 second worked example for agentskills; D-3 8 remaining skills stay deferred per DF-7.4-S1 / C60. 8 ACs. Closes AC-DOGFOOD-01 agentskills half. | Bob |
