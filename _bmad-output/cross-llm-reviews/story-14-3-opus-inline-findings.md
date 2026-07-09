# Story 14.3 — Cross-LLM Adversarial Review — Claude Opus (in-session, empirically probed)

**Reviewer:** Claude Opus 4.8 (this session, acting as Tier-1b substitute).
**Date:** 2026-06-04.
**Why this file exists:** The operator's background CLI invocations for Tier-1a (sonnet) and
Tier-1b (opus) returned **0 bytes** (`story-14-3-claude-{opus,sonnet}-findings.md` both empty
with live PIDs) — the documented Claude-CLI empty-output failure mode (CLAUDE.md Tier-1 failure
modes). Codex (Tier-2) produced a 1.4 MB file dominated by prompt/diff echo. This file is the
empirically-probed Opus review, written to a distinct path to avoid racing the live CLI process.

Every finding below was verified with a real Bash/`robot --dryrun` probe, not inferred.

---

## HIGH

### HIGH-1 — Retro-action bar "≥6 **passing**" is genuinely UNMET; the 3-epic carryover "closure" is overclaimed

**Files:** `14-3-...md` (Change Log, Retro-debt mini-pass, C64 closure note), `docs/phase-1-5-carry-overs.md` C64.

The three carried action items each set a **passing** bar of ≥6:

- Epic 11 retro **L157** Action #7: "…returns **≥6 passed** at HEAD CI."
- Epic 12 retro L168 Action #9: "**≥6** fenced robotframework blocks **pass** dryrun in CI."
- Epic 13 retro L186 Action #9: "ships with **≥6** fenced blocks **tested**."

Empirical (`pytest -v` + direct dryrun loop over `_ELIGIBLE_BLOCKS`):

```
PASS 02-pass-at-k-over-polling.md::block-0
PASS 04-skill-author-stacked-validation.md::block-0
PASS 04-skill-author-stacked-validation.md::block-1
PASS 06-custom-protocol-adapter.md::block-0
FAIL 03-...::block-0 / 05-...::block-0 / 05-...::block-1 / 07-...::block-0   (skip-listed)
=> 4 passing, 4 known-broken-skipped
```

Only **4** blocks pass dryrun. The story nonetheless marks Epic 11 #7 / Epic 12 #9 / Epic 13 #9
"✅ Closing this" and C64 "**DONE** 2026-06-04". Per `feedback_honest_framing`: the harness *ships*
(one half of each criterion) but the "≥6 pass" half is **not** satisfied — it is deferred to
DF-14.3-S1. **Fix:** reframe as a *partial* closure. The retro actions and C64 should read
"harness ships; full ≥6-passing closure blocked on DF-14.3-S1 (fix-recipe-rot)" rather than
fully-closed/DONE. This is the single most load-bearing finding — it is exactly the
process-drift / evaluative-vs-factual misframing class the chain exists to catch.

### HIGH-2 — AC-14.3.3 amendment conflates "eligible" with "passing"; the story-internal AC was already satisfied and never needed lowering

**File:** `14-3-...md` AC-14.3.3 + `test_all_recipes_dryrun.py` L377-L395.

AC-14.3.3 as written measures "≥6 **dryrun-eligible** blocks" and its implementation note specifies
`assert len(_collect_eligible_blocks()) >= 6`. Empirically there are **8 eligible** blocks → the
original AC is met **without any amendment**. The dev instead amended ≥6→≥4 *and silently switched
the measured quantity* from *eligible* to *passing* (`_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT -
len(_KNOWN_BROKEN_BLOCKS)`). So the "≥6 → ≥4" amendment narrative is measuring a different metric
than AC-14.3.3 originally specified. The bar that actually fails is the retro actions' "≥6
**passing**" (HIGH-1), not AC-14.3.3's "≥6 eligible." **Fix:** keep AC-14.3.3's eligible bar
(8 ≥ 6, unchanged, no amendment) and track the passing count as a *separate, explicitly-named*
metric that honestly reports 4 < the 6-retro-target as a known gap tied to DF-14.3-S1. As written,
the amendment manufactures a threshold relaxation that the story's own AC did not require.

### HIGH-3 — Citation drift: Epic 11 retro Action #7 is at L157, not L158

**File:** `14-3-...md` L23, L204, L252, L68 (+ review prompt L36/L40 lineage).

The spec cites "Epic 11 retro **L158** Action #7." Empirically:
- `epic-11-retro-2026-05-27.md:157` = Action #7 (C64 recipe CI extraction). ✓ correct action, wrong line.
- `epic-11-retro-2026-05-27.md:158` = **Action #8** (Story 7.1 Change Log backfill).

Off-by-one citation drift; the cited line points at the *wrong action*. **Fix:** L158 → L157 in all
four references. (Epic 12 L168 and Epic 13 L186 re-derived and **confirmed correct**.) Note the irony:
L-1 of this very story claims citations were "re-derived from source via direct grep before writing" —
this one was not.

---

## MED

### MED-1 — Claimed `extract_robotframework_blocks` unclosed-block `ValueError` path has ZERO test coverage

**File:** `test_all_recipes_dryrun.py` L120-123 (raise) vs test suite.

AC-14.3.1(2) + the docstring claim "unclosed blocks raise `ValueError`," and the review prompt's
HIGH §"diff-parser fidelity" item #2 explicitly asks for a synthetic-md unclosed-block test. No such
test exists — the only `pytest.raises(ValueError)` cases (L421/L427) cover `wrap_block_for_dryrun`'s
"not dryrun-eligible" path, not the parser's unclosed branch. The empty-block branch is exercised
indirectly via recipe-1, but the unclosed branch is untested. **Fix:** add
`test_extract__unclosed_block_raises_value_error` writing a synthetic `.md` with a dangling
` ```robotframework ` to `tmp_path` and asserting `pytest.raises(ValueError, match="Unclosed")`.

### MED-2 — Numeric drift: "13 parametrized tests" vs "33 parametrizations" vs actual 20; "10 helper" vs actual 11

**File:** `14-3-...md` Task 1 (L156), Task 5 (L164), File List (L258), Change Log (L274).

Internally contradictory counts:
- Task 1: "**33** parametrizations covering all 20 blocks."
- File List + Change Log: "**13** parametrized tests across 20 blocks" (self-contradictory — one
  case per block ⇒ 20, not 13).

Empirical: `test_recipe_block_dryruns` has **20** parametrizations (one per block); the file totals
20 param + 2 negative + 11 helper = **33** tests (run: 17 passed + 16 skipped = 33). Helper count is
claimed "**10**" but is **11** (`grep -cE '^def test_'` = 14 = 1 parametrized def + 2 negative + 11
helper). **Fix:** standardize to "20 parametrized block cases + 2 negative + 11 helper = 33 tests."

### MED-3 — `feedback_executable_doc_precheck` norm not annotated despite Story 14.3 being its CI automation

**File:** `~/.claude/.../memory/feedback_executable_doc_precheck.md` (mtime 2026-05-25; no 14.3 ref).

Story 14.3 *is* the CI automation of this Epic-7 norm, but the memory file carries no note that the
manual precheck is now backstopped by `test_all_recipes_dryrun.py`. The review prompt's MED item asks
this directly. **Fix:** one-line update to the norm: "CI-enforced as of Story 14.3 via
`tests/integration/recipes/test_all_recipes_dryrun.py` for `docs/recipes/*` robotframework blocks."

---

## LOW

- **LOW-1** — Module docstring says "8 dryrun-eligible" without noting the live split (4 pass / 4
  known-broken-skipped). The prompt's LOW item flags this; a one-line "(4 PASSING in CI + 4 skipped
  per `_KNOWN_BROKEN_BLOCKS`)" would align the docstring with reality.
- **LOW-2** — Nested-fence fragility: the parser closes on any bare ` ``` `, so a nested ` ```python `
  block inside a robotframework block would close the block prematurely. None exist in the corpus and
  the docstring does not claim nesting support, so non-blocking — but a one-line docstring caveat is
  cheap insurance.
- **LOW-3** — The module-load `assert _PASSING_BLOCKS_COUNT >= _AC_14_3_3_THRESHOLD` (L385) duplicates
  `test_collect_passable_blocks_meets_amended_ac_14_3_3_threshold` (L443). The dedicated test is the
  better ergonomic (a corpus-empty or threshold regression surfaces as a clean test failure, not a
  cryptic collection-time `AssertionError`). Consider relying on the test alone, or keep the assert
  but ensure its message is the one operators see at collection time.

---

## Verified CLEAN (probed, no finding)

- **Skip-list completeness (HIGH §`_KNOWN_BROKEN_BLOCKS`)** — direct dryrun over all 8 eligible blocks:
  the 4 skip-listed genuinely FAIL, the 4 non-listed genuinely PASS, **zero unaccounted failures, zero
  stale skip entries**. The failure surface is fully and exactly accounted. ✓
- **Negative-guard fidelity (D-3 / HIGH §Story 13.5 HIGH-B)** — both negative tests PASS; the
  `Get From Dictionary` suite ships no `Library Collections` and the assertion on
  `No keyword with name 'Get From Dictionary'` holds empirically. ✓
- **Catalog gate (AC-14.3.9)** — `scripts/check-catalog-references.py --all-tracked` EXIT 0; the 4
  inline `DF-14.3-S1` refs resolve to the deferred-work row. ✓
- **Fence counts (D-1)** — `grep -cE '^```robotframework'` = 20 total / 8 eligible, matches spec. ✓
- **Self-recursion guard (L-2)** — harness globs `docs/recipes/*.md` only; never `tests/`. ✓
- **Wrap-transform (D-2) + settings-only raise (Amendment 3)** — both unit tests pass. ✓

---

## Triage recommendation

Apply **HIGH-1 / HIGH-2 / HIGH-3** before marking the story `done`: they are honest-framing /
numeric / citation drifts, all cheap doc-only edits, and HIGH-1+HIGH-2 go to the core claim that the
carryover chain is "closed." MED-1 (missing unclosed-block test) is a real coverage gap on a claimed
behavior — add the test. MED-2/MED-3 are doc/norm hygiene. LOWs optional.

**No code-correctness defect in the harness itself** — the extraction/classification/wrap/dryrun
machinery is empirically sound and the skip-list is exact. The findings are about *framing of the
closure* and *citation/count accuracy*, which is precisely the drift class this chain targets.
