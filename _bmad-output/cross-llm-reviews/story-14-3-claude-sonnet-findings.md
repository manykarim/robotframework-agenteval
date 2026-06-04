# Story 14.3 — Cross-LLM Adversarial Review — Claude Sonnet 4.6 Findings (v2)

**Reviewer:** Claude Sonnet 4.6 (claude-sonnet-4-6) — Tier 1a (second pass; first pass at same path had errors — see below)
**Date:** 2026-06-04
**Story:** 14.3 — Recipe CI Extraction (`test_all_recipes_dryrun.py`)

## Prior-pass correction notice

An earlier version of this file (same path, prior session) made 4 errors:
1. Marked Epic 11 retro L158 citation "CLEAN" — it is L157 (Opus + Codex both flagged independently).
2. Missed `FileNotFoundError` dead-code bug (D-4 claim false — Codex HIGH-1).
3. Missed ≥6-pass criterion unmet / closure overclaimed (Opus HIGH-1+2).
4. Missed C64 L91→L88 citation drift in deployed docstring.
This version corrects all four.

## Summary

**7 HIGH** (5 code/framing + 2 citation), **5 MED**, **3 LOW**. The harness machinery is empirically
sound (skip-list exact, negative guards correct, catalog gate EXIT 0). The HIGH findings are a mix
of: (a) a dead-code D-4 bug, (b) honest-framing overclaim on the retro-action closures, and (c) citation
drifts. All are cheap fixes; none require architectural rework.

---

## HIGH

### HIGH-1 — D-4 "SKIP gracefully when robot absent" is dead code; missing robot returns exit 1, not `FileNotFoundError`

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:283-287`
**Source:** Codex HIGH-1 (independently verified here)

```python
except FileNotFoundError:  # pragma: no cover — `uv` env always ships robot
    pytest.skip(...)
```

`_run_robot_dryrun` calls `subprocess.run([sys.executable, "-m", "robot", ...])`. `subprocess.run` raises `FileNotFoundError` only if the *executable* (`sys.executable`) is not found — which cannot happen since `sys.executable` is the currently-running Python interpreter. If the `robot` *module* is absent, Python returns `exit 1` with `stderr: No module named robot`. The harness then checks `result.returncode == 0` and FAILs the test (not SKIPs). D-4 claim ("SKIP gracefully when robot absent") is not implemented.

**Fix**: Replace the `except FileNotFoundError` block with an explicit preflight:
```python
try:
    result = _run_robot_dryrun(suite_text, tmp_path, suite_name)
except FileNotFoundError:
    pytest.skip("sys.executable not found — environment severely broken")
if "No module named robot" in (result.stderr or ""):
    pytest.skip("robot module not available in environment")
```
Or use `importlib.util.find_spec("robot") is None` as the preflight. The `pragma: no cover` comment must be removed if the branch becomes reachable via test.

---

### HIGH-2 — Retro-action "≥6 passing" bar unmet; 3-epic carryover closure overclaimed

**File:** `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md`, `docs/phase-1-5-carry-overs.md` C64 row
**Source:** Opus HIGH-1 (independently verified here)

The three carried action items each specify a **passing** bar:
- Epic 11 retro L157 Action #7: "…returns **≥6 passed** at HEAD CI."
- Epic 12 retro L168 Action #9: "**≥6** fenced robotframework blocks **pass** dryrun in CI."
- Epic 13 retro L186 Action #9: "ships with **≥6** fenced blocks **tested**."

Empirical (`uv run pytest tests/integration/recipes/test_all_recipes_dryrun.py -v`):
```
PASS 02-pass-at-k-over-polling.md::block-0
PASS 04-skill-author-stacked-validation.md::block-0
PASS 04-skill-author-stacked-validation.md::block-1
PASS 06-custom-protocol-adapter.md::block-0
SKIP 03/05/05/07 (known-broken-DF-14.3-S1)
=> 4 passing, 4 known-broken-skipped
```

**Only 4 blocks pass.** The story marks Epic 11 #7 / Epic 12 #9 / Epic 13 #9 "✅ Closing this" and C64 "DONE 2026-06-04". Per `feedback_honest_framing` this is overclaimed. The harness *ships* (one half of the criterion), but the ≥6-pass half is deferred to DF-14.3-S1.

**Fix:** Reframe as *partial* closure in the spec, the C64 row, and the retro-action closures:
> "✅ Partially closed by Story 14.3 — harness ships and is active; ≥6-pass criterion unmet (4/8 eligible pass; 4 skip as DF-14.3-S1 pre-existing regressions). Full ≥6-pass closure pending fix-recipe-rot story (DF-14.3-S1)."

---

### HIGH-3 — AC-14.3.3 amendment conflates "eligible" vs "passing"; original bar was already met; amendment is manufactured

**File:** `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md` AC-14.3.3, `tests/integration/recipes/test_all_recipes_dryrun.py:220-229`
**Source:** Opus HIGH-2

AC-14.3.3 as written measures "≥6 **dryrun-eligible** blocks" (blocks containing `*** Test Cases ***`). Empirically there are **8 eligible** blocks → the original AC was met **without any amendment**. The dev amended ≥6→≥4 AND simultaneously switched the measured metric from *eligible* to *passing* (`_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT - len(_KNOWN_BROKEN_BLOCKS)`). Two changes conflated into one amendment narrative.

The bar that is actually NOT met is the **retro-actions' "≥6 passing"** (HIGH-2 above), not AC-14.3.3's "≥6 eligible." The amendment manufacture a threshold relaxation the original AC did not require.

**Fix:** Keep AC-14.3.3's eligible bar (8 ≥ 6, no amendment needed). Add a *separate* named metric for the passing count: `_PASSING_BLOCKS_COUNT` is the one that doesn't meet the retro-action target. Rename the module-load assertion to make the distinction clear, and correct the AC text to show both metrics explicitly.

---

### HIGH-4 — Citation drift: C64 catalog row cited at L91 in deployed docstring; actual row is L88

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:26`

```python
- C64 / DF-8b.3-S1 (catalog row at ``docs/phase-1-5-carry-overs.md`` L91).
```

**Empirical check:** `grep -n "C64" docs/phase-1-5-carry-overs.md` → C64 is at **line 88**, not L91. L91 is C67 (ClaudeAgentSDKAdapter HostedMcpObserver). Off by 3.

**Fix:** Change `L91` → `L88` in `test_all_recipes_dryrun.py:26`. Same error in story spec line 25.

---

### HIGH-5 — Citation drift: Epic 11 retro Action #7 cited at L158; actual line is L157

**File:** `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md` (lines 23, 68, 204, 252), review prompt
**Source:** Unanimous — all three reviewers found independently (Sonnet, Opus HIGH-3, Codex MED-2)

The spec cites "Epic 11 retro **L158** Action #7." Empirical:
- `epic-11-retro-2026-05-27.md:157` = Action #7 (C64 recipe CI extraction).
- `epic-11-retro-2026-05-27.md:158` = **Action #8** (Story 7.1 Change Log backfill).

The cited line points at the *wrong action*. L-1 of this story claims citations were "re-derived from source via direct grep before writing" — this one was not verified to the correct line. (Epic 12 L168 and Epic 13 L186 confirmed correct.)

**Fix:** Change `L158` → `L157` in all references in the story spec.

---

### HIGH-6 — Missing unit test for `extract_robotframework_blocks` unclosed-block `ValueError` path

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py` (no such test)
**Source:** Sonnet + Opus MED-1 (both independent)

The function docstring (line 86-88) documents "Unclosed blocks raise `ValueError`." The implementation at lines 120-123 is correct. But no unit test exercises this path. The `pytest.raises(ValueError)` calls at lines 421 and 427 test `wrap_block_for_dryrun`, not `extract_robotframework_blocks`. The review checklist explicitly required this test.

**Fix:** Add after `test_extract_robotframework_blocks__counts_match_grep`:
```python
def test_extract_robotframework_blocks__unclosed_raises_value_error(tmp_path: Path) -> None:
    md = tmp_path / "unclosed.md"
    md.write_text("```robotframework\n*** Test Cases ***\nFoo\n    Log    hi\n")
    with pytest.raises(ValueError, match="Unclosed"):
        extract_robotframework_blocks(md)
```

---

### HIGH-7 — Module-load `assert` fires as cryptic collection error, masking all 33 test IDs

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:222-229`
**Source:** Sonnet + Opus LOW-3

```python
assert _PASSING_BLOCKS_COUNT >= _AC_14_3_3_THRESHOLD, (...)
```

This runs at import time. If it fires, pytest reports an `AssertionError` collection error and drops **all 33 test IDs** from the report — they disappear rather than failing. The dedicated test `test_collect_passable_blocks_meets_amended_ac_14_3_3_threshold` (line 443) covers the same condition with better UX (named test failure visible in CI output).

**Fix:** Remove the module-load `assert`. Keep only the dedicated test. If an early-fail guard is truly needed, document the collection-error ergonomic explicitly.

---

## MED

### MED-A — `feedback_executable_doc_precheck` memory file not annotated as CI-automated

**File:** `memory/feedback_executable_doc_precheck.md`
**Source:** Unanimous (Sonnet MED-B, Opus MED-3, Codex MED-3)

Story 14.3 IS the CI automation of this Epic-7 norm for `docs/recipes/*.md` RF blocks. The memory file describes only the manual process. Future sessions will instruct operators to manually smoke-execute recipe RF blocks that the CI gate now covers automatically.

**Fix:** Append one-line update: "CI-enforced as of Story 14.3 via `tests/integration/recipes/test_all_recipes_dryrun.py` for `docs/recipes/*` robotframework blocks. Manual precheck still required for Python/shell blocks and non-recipe paths."

---

### MED-B — `05-dogfood-replacing-custom-tests.md::block-1` skip reason names secondary failure

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:201-205`, `deferred-work.md:417`
**Source:** Codex MED-1

Current reason: "Library `${CURDIR}/fixtures/agentskills_discoverability.py` not present in temp dryrun dir."  
Actual first failure from dryrun: `No keyword with name 'Register Skill Stubs' found.` (the Library import fails before the keyword is even reached, but the fixture-not-found is not the triggering error).

**Fix:** Update `_KNOWN_BROKEN_BLOCKS` entry to lead with the first dryrun error surfaced by Robot, or list both in failure order.

---

### MED-C — Parametrize count "13 pytest IDs" in review prompt and spec is wrong; actual is 20

**File:** `_bmad-output/cross-llm-reviews/story-14-3-review-prompt.md:16`, story spec
**Source:** Sonnet MED-C, Opus MED-2, Codex LOW-1

Empirical `--collect-only`: **20 parametrized IDs** (one per block). Spec says "13 pytest IDs" (wrong) in one place and "33 parametrizations" in Task 1 (wrong — 33 is the total, only 20 are parametrized). Correct accounting: 20 parametrized + 2 negative + 11 helper = 33 total.

**Fix:** Standardize to "20 parametrized block IDs + 2 negative + 11 helper = 33 total" in the story spec review-prompt and task notes.

---

### MED-D — Nested-fence parser: longer outer fences (4+ backticks) not recognized; bare ``` inside RF block would prematurely close

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:61-62, 97-103`
**Source:** Codex HIGH-2 (empirically probed)

The parser checks `line.strip() == "```robotframework"` (exact 3-backtick match). A fence written with 4+ backticks (valid Markdown for showing triple-backtick fences inside) is ignored. Also, any bare ` ``` ` line inside a robotframework block closes the block prematurely (before the actual closing fence). Neither case exists in the current corpus, but neither is tested.

**Fix:** Either (a) document the parser limitations in the function docstring ("only recognizes exact 3-backtick fences; longer outer fences and nested triple-backtick closings are not handled"), or (b) use `re.match(r"^```robotframework\s*$", line)` / `re.match(r"^```\s*$", line)` for stricter boundary matching. Add a unit test for each limitation.

---

### MED-E — `feedback_executable_doc_precheck` norm propagation: memory update missing

*(Duplicate of MED-A — see above. Tracking separately to note it is unanimous across all 3 tiers.)*

---

## LOW

### LOW-A — Module docstring doesn't note the 4+4 eligible/skip split

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:28-29`

Says "runs `robot --dryrun` against each dryrun-eligible block" without noting 4 of 8 are `_KNOWN_BROKEN_BLOCKS`. Add one sentence.

### LOW-B — Story spec line 23 cites Epic 11 retro L158 (separate from HIGH-5 which is in deployed code)

Same L157/L158 drift in the spec narrative text; tracked in HIGH-5 for the code.

### LOW-C — Module-load assertion duplicates dedicated test (ergonomics subissue)

Tracked in HIGH-7. If HIGH-7 is applied (remove assertion), this LOW becomes N/A.

---

## Verified CLEAN (empirically probed)

- **Skip-list completeness**: `uv run pytest -v` → exactly 4 PASS (02::0, 04::0, 04::1, 06::0) + 4 SKIP (known-broken) + 12 SKIP (non-eligible). Zero unaccounted FAILures. ✓
- **Story 13.5 HIGH-B guard**: `Get From Dictionary` fixture has no `Library Collections`; assertion checks exact error string; test PASSES empirically. ✓
- **Catalog gate (AC-14.3.9)**: `scripts/check-catalog-references.py --all-tracked` EXIT 0. DF-14.3-S1 row resolves 4 inline refs. ✓
- **Self-recursion guard**: harness globs `docs/recipes/*.md` only; never `tests/`. ✓
- **Epic 12 L168 + Epic 13 L186 citations**: both confirmed correct via grep. ✓
- **Pytest count**: 17 passed + 16 skipped, 4.63s. ✓

---

## Triage summary

| ID | Severity | Source | Action required before `done` |
| --- | --- | --- | --- |
| HIGH-1 | HIGH | Codex | Fix `except FileNotFoundError` dead code or document limitation |
| HIGH-2 | HIGH | Opus | Reframe retro closures as partial (≥6-pass unmet) |
| HIGH-3 | HIGH | Opus | Separate AC-14.3.3 eligible bar from passing bar |
| HIGH-4 | HIGH | Sonnet | Fix `L91` → `L88` in deployed docstring |
| HIGH-5 | HIGH | All 3 | Fix `L158` → `L157` in spec |
| HIGH-6 | HIGH | Sonnet+Opus | Add unclosed-block unit test |
| HIGH-7 | HIGH | Sonnet+Opus | Remove/replace module-load assert |
| MED-A | MED | All 3 | Update `feedback_executable_doc_precheck.md` |
| MED-B | MED | Codex | Fix block-1 skip-reason to lead with actual first failure |
| MED-C | MED | All 3 | Fix parametrize counts in spec/prompt |
| MED-D | MED | Codex | Document parser limitations or harden parser |
| LOW-A | LOW | Sonnet | Docstring 4+4 split note |
