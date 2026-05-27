# Story 12.3: Three-Tier Stacked Validation Integration (Completes Devon's Journey 4)

Status: done

## Dev Agent Record

### Completion Notes List

Story 12.3 dev complete + 2-tier Claude CLI review (sonnet + opus) per /goal directive. **Closes Epic 12** + closes Devon's Journey 4 Tier-2 slot per PRD L394-401.

- **AC-12.3.1**: Recipe Gallery #4 Tier-2 slot populated — overview table flipped from "Phase 2 only — see TODO below" to concrete description; placeholder block replaced with actual `Judge.Get Score` invocation; `## Phase 2 Status` section added; See-Also references both `judge-calibration.md` (Story 12.2) and `test_devon_three_tier_complete.py` (Story 12.3).
- **AC-12.3.2**: 5 integration tests at `tests/integration/skills/test_devon_three_tier_complete.py` — Tier-1 + Tier-2 + Tier-3 + coherent-pass + coherent-fail. THREE stubs via `register_adapter()` (in-flight amendment from spec text "two stubs" per Sonnet MED-1 review; coherent-fail test requires a separate failing stub).
- **AC-12.3.3**: `tests/integration/skills/test_devon_stacked_validation.py:160-169` amended: `test_recipe_stub_exists_with_phase2_placeholder` → `test_recipe_documents_complete_three_tier_pattern`; assertion flipped from "TODO Phase 2" to "Judge.Get Score" + "TODO Phase 2 NOT in content."
- **AC-12.3.4**: `robot --dryrun` smoke verified: full recipe code block dryruns clean after class-path import update (`AgentEval.skills.library.SkillsLibrary`, `AgentEval.judge.library.JudgeLibrary`, etc.) — retires the pre-existing SkillsLibrary `WITH NAME` dryrun-fail framing entirely (Opus HIGH-1 + Sonnet HIGH-1 2-way → fixed by full class-path import migration).
- **AC-12.3.5**: 1775 passed + 14 skipped (was 1770 + 14; +5 new integration tests). ruff/format/mypy clean.
- **AC-12.3.6**: `sprint-status.yaml` flipped: `12-3-*: done`; epic-12 set to `done`.

### 2-tier Claude CLI review summary (2026-05-27)

**Sonnet (3 findings: 1 HIGH + 1 MED + 1 LOW)**:
- HIGH-1: Recipe `*** Settings ***` missing `Judge.Get Score` + `Send Prompt` library imports → 2-WAY AGREEMENT with Opus HIGH-1 → FIXED (class-path import migration: `AgentEval.skills.library.SkillsLibrary WITH NAME Skill`, `AgentEval.stats.library.StatsLibrary WITH NAME Stat`, `AgentEval.judge.library.JudgeLibrary WITH NAME Judge`, `AgentEval.orchestration.library.OrchestrationLibrary`; full recipe now dryrun-clean — retires the long-standing SkillsLibrary dryrun-fail framing).
- MED-1: AC-12.3.2 says "two stubs" but implementation ships three → FIXED (AC amended per `feedback_in_flight_spec_amendment`).
- LOW-1: `agent_run` fixture creates unregistered stub instance → FIXED (now resolves via `get_adapter(AGENT_ADAPTER)`).

**Opus (3 findings: 1 HIGH + 1 MED + 1 LOW)**:
- HIGH-1: Recipe Tier-2 block does not resolve → 2-way agreement (see Sonnet HIGH-1).
- MED-1: Recipe foregrounds `seed + temperature=0` but integration test never passes them → FIXED (`judge_model="anthropic/claude-sonnet-4-6", temperature=0.0, seed=42` added to `test_tier2_judge_get_score_passes_against_stub`).
- LOW-1: Stale `TODO Phase 2: Judge.Get Score` docstrings in `test_devon_stacked_validation.py:22-23 + :135` → FIXED (docstrings now reference `test_devon_three_tier_complete.py`).

**2-way agreement on 1 finding**: missing library imports — near-certain bug per `feedback_n_way_agreement_weight`.

### File List

**New files:**
- `tests/integration/skills/test_devon_three_tier_complete.py` (~225 LoC, 5 integration tests).

**Modified files:**
- `docs/recipes/04-skill-author-stacked-validation.md` — Tier-2 slot populated + class-path imports + Phase 2 Status section + See-Also expanded.
- `tests/integration/skills/test_devon_stacked_validation.py` — D-1 amendment + Opus LOW-1 docstring updates.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `12-3-*: done` + `epic-12: done`.

## Story

As **Devon (Agent Surface Author)**,
I want Recipe Gallery #4 updated to plug in `Judge.Get Score` as the Tier-2 layer between Story 2.1's Tier-1 static validation and Story 7.2's Tier-3 cohort Discoverability — completing the full three-tier flow,
So that Devon's Journey 4 from PRD is end-to-end exercisable.

## Pre-create-story drift check (50th use of `feedback_spec_vs_ratified_doc_precheck`)

9 drift items surfaced — 5 fresh + 4 UPSTREAM from Story 12.2 review patterns:

- **D-1 (HIGH — existing test asserts the placeholder):** `tests/integration/skills/test_devon_stacked_validation.py:160-169` (`test_recipe_stub_exists_with_phase2_placeholder`) asserts the recipe CONTAINS the literal string `"TODO Phase 2: Judge.Get Score"`. Once Story 12.3 replaces that placeholder with the actual `Judge.Get Score` invocation, that test FAILS. **Decision:** amend `test_devon_stacked_validation.py` in lock-step (in-flight spec amendment per `feedback_in_flight_spec_amendment` — UPSTREAM from Story 12.2 Opus LOW-3 lesson). New assertion: `"Judge.Get Score"` MUST appear in the recipe AND `"TODO Phase 2"` MUST NOT appear; AC-7.3.6 + AC-7.3.7 effectively reframe from "stub draft" to "Phase-2-shipped." This is the only existing test affected.
- **D-2 (HIGH — recipe Tier-2 stub has wrong signature):** Existing Recipe #4 stub at `docs/recipes/04-skill-author-stacked-validation.md:53` shows `${score}=    Judge.Get Score    ${SKILL_PATH}    prompt=${REPRESENTATIVE_PROMPT}` — but `Judge.Get Score`'s actual signature is `result=AgentRunResult, rubric=..., judge_adapter=..., judge_model=...` (NOT `skill+prompt`). The recipe must invoke an agent first (via `Send Prompt` or similar), pass its `AgentRunResult` to `Judge.Get Score` with a rubric path. **Decision:** new recipe Tier-2 block models the canonical pattern: agent runs against the representative prompt → judge scores the response against `tests/fixtures/rubrics/skill-quality.md` → assert `${score.pass_threshold_met}`.
- **D-3 (HIGH — integration test must avoid real LLM cost):** epics.md L2133 says "Mock judge provider; integration test asserts coherent pass/fail." But agenteval's `MockProvider` (`src/AgentEval/providers/mock.py`) is at the provider layer, not the adapter layer; `Judge.Get Score` resolves adapters via `get_adapter()`. **Decision:** mirror the existing Story 7.3 pattern at `test_devon_stacked_validation.py:68-92` — register a `devon_judge_stub` adapter via `register_adapter()` returning JSON-formatted `JudgeScore` payloads. Avoid the MockProvider path entirely; use the `register_adapter` stub idiom that's already vetted across 8 Epic 7+ stories.
- **D-4 (MED — UPSTREAM Story 12.2 Sonnet HIGH-1 + Opus MED-1):** Integration test MUST exist at the spec-mandated path `tests/integration/skills/test_devon_three_tier_complete.py`. Don't claim the file in the File List if it doesn't get shipped — Story 12.2 Sonnet HIGH-1 lesson. Verify with `ls` BEFORE flipping to `done`.
- **D-5 (MED — UPSTREAM Story 12.2 2-way MED `recommended_threshold` reachability):** The new integration test asserting `Judge.Get Score` against a stub adapter returning a fixed `JudgeScore` should also verify the `JudgeScore.pass_threshold_met` invariant — `True` iff `numeric_score >= rubric.threshold`. Don't trust the stub's stated boolean; re-derive from the parsed rubric.
- **D-6 (MED — `feedback_executable_doc_precheck`):** Updated Recipe #4 code block MUST pass `robot --dryrun` before flipping to review. Same lesson as Story 12.2's calibration recipe smoke test. The recipe file is shipped through Story 7.3 + Story 8b.3; modifying it MUST not break dryrun for Recipes #1-#8 cross-references.
- **D-7 (MED — Devon's Journey 4 documentation update):** epics.md L2135 says "Devon's Journey 4 documentation marks the full flow as available from Phase 2 release onwards." There is no specific Devon's Journey 4 doc file — the canonical narrative is in PRD L394-401 + the recipe itself. **Decision:** the recipe's `## Overview` table flip ("Phase 2 only — see TODO below" → "Phase 2 — stochastic LLM-deterministic at `seed + temperature=0`") + a `## Phase 2 Status` section in the recipe IS the Devon's Journey 4 doc update. Don't author a separate file; the recipe is the authoritative pattern doc.
- **D-8 (LOW — pre-emptive carry-over catalog gate UPSTREAM, 31st consecutive):** Story 12.3 is pure integration — no new public surfaces, no new error classes, no new sub-libraries. Potential carry-over: Phase-2 work to extend the integration test to non-Anthropic judges (currently the stub mirrors Anthropic JSON shape). Defer cataloguing until dev surfaces a concrete need.
- **D-9 (UPSTREAM Story 12.2 in-flight spec amendment):** If dev decisions diverge from AC text mid-story, amend AC in same commit. Specifically: AC text "MockProvider" is shorthand for "stub adapter that bypasses real LLM" — amend to "stub adapter via `register_adapter()` returning JSON-formatted `JudgeScore` payloads" if the dev decision lands there.

## Acceptance Criteria

### AC-12.3.1 — Recipe Gallery #4 Tier-2 slot populated

`docs/recipes/04-skill-author-stacked-validation.md` updated:

1. The Tier-2 row in the Overview table (L28) changes from "Phase 2 only — see TODO below" to a concrete description: "Phase 2 — LLM-deterministic at `seed + temperature=0`; rubric ratifies pass/fail at threshold."
2. The Tier-2 placeholder block at L51-54 is replaced with an actual `Judge.Get Score` invocation. The block:
   - Invokes the agent first via `Send Prompt` to produce an `AgentRunResult` against `${REPRESENTATIVE_PROMPT}`.
   - Calls `Judge.Get Score    result=${run}    rubric=${RUBRIC_PATH}    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6`.
   - Asserts `${score.pass_threshold_met}` is True.
3. A new `## Phase 2 Status` section after the example clarifies: "As of Story 12.3 (Epic 12), the full three-tier stacked validation flow is shipping. Operators may opt out of Tier-2 by leaving the section blocked-out; Tier-1 + Tier-3 remain the Phase-1 ceiling for budget-constrained users."
4. The "See Also" section adds a reference to `docs/recipes/judge-calibration.md` (Story 12.2 cookbook).

### AC-12.3.2 — Integration test exercises all 3 tiers

`tests/integration/skills/test_devon_three_tier_complete.py` ships:

```python
class TestDevonThreeTierComplete:
    def test_tier1_frontmatter_validation(self): ...
    def test_tier2_judge_get_score_passes_against_stub(self): ...
    def test_tier3_cohort_discoverability(self): ...
    def test_three_tiers_combined_coherent_pass(self): ...
    def test_three_tiers_combined_coherent_fail_when_tier2_fails(self): ...
```

The test:
- Reuses `tests/fixtures/skills/example-search.md` + `tests/fixtures/discoverability/skill-tasks-basic.yaml` (existing) + `tests/fixtures/rubrics/skill-quality.md` (Story 12.1).
- Registers THREE stub adapters via `register_adapter()` (in-flight amendment per `feedback_in_flight_spec_amendment` Story 12.2 Opus LOW-3 lesson — original AC said "two stubs"; shipped three because the coherent-fail test requires a SEPARATE failing stub, not a re-registered/stateful single stub):
  - `devon_three_tier_agent_stub` — synthesizes the agent's `AgentRunResult` (mirrors `_make_stub()` from `test_devon_stacked_validation.py`).
  - `devon_three_tier_judge_stub_passing` — returns JSON-formatted `JudgeScore` payload (`numeric_score: 8.5`).
  - `devon_three_tier_judge_stub_failing` — returns JSON-formatted `JudgeScore` payload (`numeric_score: 4.0`, below rubric threshold 7.0).
- Asserts coherent pass: Tier-1 valid + Tier-2 `pass_threshold_met=True` + Tier-3 `pass_at_k >= 0.8`.
- Asserts coherent fail: same Tier-1 + Tier-3 valid, but Tier-2 stub returns `numeric_score: 4.0` (below threshold 7.0) → `pass_threshold_met=False` → composite assertion fails.

### AC-12.3.3 — `test_devon_stacked_validation.py` amendment (D-1)

`tests/integration/skills/test_devon_stacked_validation.py:160-169` amended:
- Old: `assert "TODO Phase 2: Judge.Get Score" in content`
- New: `assert "Judge.Get Score" in content; assert "TODO Phase 2: Judge.Get Score" not in content`

Test name updated: `test_recipe_stub_exists_with_phase2_placeholder` → `test_recipe_documents_complete_three_tier_pattern`. Per `feedback_in_flight_spec_amendment` Story 12.2 Opus LOW-3 lesson — amend AC text in same commit.

### AC-12.3.4 — `robot --dryrun` smoke verifies recipe code blocks

Per `feedback_executable_doc_precheck`: the updated Recipe #4 Tier-2 block + the full example test case MUST pass `robot --dryrun` smoke (keyword resolution) before flipping to review.

### AC-12.3.5 — Final test count

`uv run pytest` reports 1770 + 5 new integration tests = ~1775 passed + 14 skipped. ruff/format/mypy clean.

### AC-12.3.6 — Sprint-status closes Epic 12

`sprint-status.yaml` flips:
- `12-3-three-tier-stacked-validation-integration-completes-devons-journey-4: done`
- `epic-12: done` (after 12.3 closes — all 3 Epic 12 stories complete; closes Devon's Journey 4 Tier-2 slot per PRD L394-401).

## Tasks/Subtasks

- [ ] **Task 1** — Update `docs/recipes/04-skill-author-stacked-validation.md`: replace Tier-2 placeholder with actual `Judge.Get Score` invocation (AC-12.3.1); flip overview table Tier-2 row; add `## Phase 2 Status` section; add `judge-calibration.md` See-Also reference.
- [ ] **Task 2** — Ship `tests/integration/skills/test_devon_three_tier_complete.py` (AC-12.3.2) with 5 tests covering Tier-1 + Tier-2 + Tier-3 + coherent-pass + coherent-fail scenarios; uses 2 `register_adapter` stubs (agent stub + judge stub).
- [ ] **Task 3** — Amend `tests/integration/skills/test_devon_stacked_validation.py:160-169` to remove the "TODO Phase 2" assertion and add the post-12.3 assertion (AC-12.3.3); rename the test.
- [ ] **Task 4** — `robot --dryrun` smoke-test the updated Recipe #4 code block (AC-12.3.4) — extract the test case to a tmp `.robot` file + run dryrun.
- [ ] **Task 5** — Run full pytest + ruff + format + mypy clean (AC-12.3.5).
- [ ] **Task 6** — Flip `sprint-status.yaml` (AC-12.3.6): `12-3-*: done` + `epic-12: done`. Per `feedback_carry_over_catalog_gate` UPSTREAM (31st consecutive): grep new files for `DF-12.3-S\d` references; if any surface during dev, catalogue in BOTH `phase-1-5-carry-overs.md` + `deferred-work.md`.

## Dev Notes

Building on Stories 12.1 + 12.2 + the Phase-1 Devon stacked-validation pattern:
- Story 12.1: `Judge.Get Score` keyword + `JudgeLibrary` composed via `_SUB_LIBRARIES`.
- Story 12.2: `Judge.Calibrate` (NOT exercised in Story 12.3 — calibration is a pre-deployment activity, not a per-run gate).
- Story 7.3: `tests/integration/skills/test_devon_stacked_validation.py` — pattern for stub adapters; 5 tests cover Tier-1 + Tier-3 + Stat composition.
- Story 7.3: `docs/recipes/04-skill-author-stacked-validation.md` — recipe stub with the Phase-2 TODO placeholder.

Key implementation detail: `Judge.Get Score` requires an `AgentRunResult` (not a prompt + skill path). The Tier-2 invocation MUST first run the agent (`Send Prompt`) to produce the result, then pass it to the judge. This is a SEPARATE LLM call from any Tier-3 cohort run — Devon pays for it explicitly.

UPSTREAM lessons applied from Story 12.2 reviews:
- D-3 (Story 12.2 Sonnet HIGH-1 + Opus MED-1): ship the integration test at the spec-mandated path.
- D-5 (Story 12.2 Sonnet MED-2 + Opus MED-2 `recommended_threshold` reachability): re-derive boolean invariants instead of trusting the stub's stated values.
- D-9 (Story 12.2 Opus LOW-3 in-flight amendment): amend `test_devon_stacked_validation.py` IN THE SAME COMMIT as the recipe edit.

## File List

**New files:**
- `tests/integration/skills/test_devon_three_tier_complete.py` — 5 integration tests (~200 LoC).

**Modified files:**
- `docs/recipes/04-skill-author-stacked-validation.md` — Tier-2 slot populated + Phase 2 Status section + See-Also.
- `tests/integration/skills/test_devon_stacked_validation.py` — D-1 amendment (test renamed; assertion flipped from "TODO Phase 2" to "Judge.Get Score").
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `12-3-*: done` + `epic-12: done`.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-27 | 0.1.0 | Initial story creation (ready-for-dev). **50th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact across 50 consecutive uses). 9 drifts caught (5 fresh + 4 UPSTREAM Story 12.2 lessons). **Cross-story upstream lesson propagation** N=5 (Stories 11.1→11.2→11.3→12.1→12.2→12.3; 12.2→12.3 propagated Sonnet HIGH-1 ship-the-file lesson + Opus LOW-3 in-flight amendment + 2-way MED reachability/invariant lessons). 6 ACs + 6 Tasks. **Closes Epic 12** + closes Devon's Journey 4 Tier-2 slot per PRD L394-401. | Bob |
