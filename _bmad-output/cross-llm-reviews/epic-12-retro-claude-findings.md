# Epic 12 Retro — Tier-1 (Claude CLI / opus) Cross-LLM Critical Review

**Reviewer:** Claude (Tier-1, semantic-shape + empirical-probe lens)
**Date:** 2026-06-01
**Artifact:** `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md`
**Method:** Every flagged claim re-derived from the live repo (`git rev-list`, `grep -c`, `wc -l`, `stat`, `pytest --collect-only`, memory-file inspection).

## Severity Summary
- HIGH: 3
- MED: 3
- LOW: 0

Most quantitative claims reconcile cleanly (catalog 82 ✅, src 103 ✅, keywords 32 ✅, D-drifts 10+10+9=29 ✅, tests 1775+14=1789 collected ✅, 24 error leaves per hierarchy doc ✅, both live test files exist ✅). The findings below are the claims that do NOT reconcile.

## Findings

### HIGH-1: The single "✅" action item (#5) is mis-attributed and mis-cited — the canonical memory file was NOT touched in Epic 12 and still reads N=3, not N=5
- **Section / line:** `epic-12-retro-2026-06-01.md:L104` (action table) + L55/L62/L110/L152/L213/L275 (N=5 framing)
- **Issue:** The retro's ONLY claimed Epic-12 follow-through win is item #5, with evidence "file shows N=5 evidence after Epic 12 additions (mtime later than Epic 11 retro close)" and body claims it was "done during Story 12.2 dev" / "drove from N=1 → N=4 → N=5 across Stories 12.1, 12.2, 12.3." All of this is false against source. The live memory file still reads `N=3`, lists only the Epic 10/11 transitions, contains no `12.x` content, and its mtime is **2026-05-27 13:32:42** — ~51s *before* the Epic 11 retro commit `4f39bb9` (13:33:33). It was last written at Epic 11 retro time and untouched in Epic 12. Per CLAUDE.md ("memory files are the canonical source of truth"), the body's promotion of `feedback_cross_story_upstream_lesson_propagation` to "N=5 confirmed / structurally load-bearing" is therefore **unrecorded in canonical source** — it is asserted only in the retro prose.
- **Evidence:**
  ```
  feedback_..._propagation.md L41: **Evidence base:** N=3 (Epic 11 retro 2026-05-27 promoted CANDIDATE → CONFIRMED). Three consecutive
  stat mtime: 2026-05-27 13:32:42   |   git log -1 4f39bb9: 2026-05-27 13:33:33
  grep "N=5|12\." memory file → (no matches)
  ```
- **Suggested fix:** Either (a) actually update the memory file to N=5 with the 12.1→12.2 + 12.2→12.3 evidence and re-stamp, then keep the ✅ but correct the mtime/"N=5" evidence wording; or (b) demote item #5 to ❌/⚠ and correct the body — the N=5 promotion cannot stand on prose alone while the canonical file says N=3. Remove "done during Story 12.2 dev" / "N=1→N=4→N=5 across 12.1/12.2/12.3" (the file was frozen before Epic 12 began).

### HIGH-2: Commit-range citation drift — `577cf36..77aa820` yields 5 commits, not the 4 claimed, and the extra commit is the Epic 11 retro, not "retro-prep"
- **Section / line:** `epic-12-retro-2026-06-01.md:L249` + L35
- **Issue:** L249 cites `git log --oneline 577cf36..77aa820` as showing exactly the 4 Epic-12 commits `b5ce6f8 + fd2ffe9 + 0788f0e + 77aa820`. Re-derived, that range returns **5** commits — it also includes `4f39bb9 docs(retro): Epic 11 retrospective`. L35 separately frames the 5th commit in `577cf36..HEAD` as "retro-prep work outside this scope," but `4f39bb9` is the *Epic 11* retrospective commit, not Epic 12 retro-prep. The base `577cf36` is the parent of the Epic 11 retro, not of the Epic 12 work.
- **Evidence:**
  ```
  $ git rev-list --count 577cf36..77aa820  → 5
  $ git log --oneline 577cf36..77aa820
  77aa820 ... | 0788f0e ... | fd2ffe9 ... | b5ce6f8 ... | 4f39bb9 docs(retro): Epic 11 retrospective ...
  ```
- **Suggested fix:** Use base `b5ce6f8^` (= `4f39bb9`): `git log --oneline b5ce6f8^..77aa820` returns exactly the 4 Epic-12 commits. Reword L35 to drop the "retro-prep" characterization (the 5th commit is Epic 11's retro).

### HIGH-3: "8 ❌" is a miscount — the Epic 11 follow-through table is 7 ❌ + 1 ⚠ Partial + 1 ✅; the three-strike narrative inflates Epic 12 from 7 to 8
- **Section / line:** `epic-12-retro-2026-06-01.md:L110` (also L96, L112, L152, L225, L236)
- **Issue:** The action table (L100–108) tallies: item 4 = "⚠ Partial" (2 live test files genuinely shipped), item 5 = "✅", items 1/2/3/6/7/8/9 = "❌" → **7 ❌ + 1 ⚠ + 1 ✅**. The draft repeatedly states "1 ✅ + 8 ❌," folding the ⚠ Partial into the ❌ bucket. This is load-bearing: the retirement of `feedback_retro_debt_block_forward_progress` is justified by the strictly-increasing sequence "Epic 10: 5 ❌; Epic 11: 7 ❌; Epic 12: 8 ❌." With the correct strict count (7 ❌), Epic 12 is **equal to** Epic 11, not worse — the "third strike, getting worse" framing does not hold on the numbers as tabulated.
- **Evidence:**
  ```
  L103 item 4: | 4 | ... | ⚠ Partial. Story 12.1 + 12.2 SHIPPED env-gated live integration tests ...
  L110: **Action-item follow-through: 1 ✅ + 8 ❌.**  ... **The 8 ❌ are MORE than Epic 11 close's 7 ❌.**
  ```
- **Suggested fix:** State the tally as "1 ✅ + 1 ⚠ Partial + 7 ❌." If the ⚠ is to be counted as a non-success, say "7 ❌ + 1 partial" and adjust the sequence to "5 → 7 → 7 (no decrease)" — which still supports "retro debt did not decrease" without the false "8 > 7" escalation. (See MED-2, which this compounds.)

### MED-1: The cited error-leaf verification command returns 28, not the claimed 24
- **Section / line:** `epic-12-retro-2026-06-01.md:L250` (and L28)
- **Issue:** The "Quantitative claims verified pre-commit" block cites `grep -c "^class.*Error.*:$" src/AgentEval/errors.py` as verifying "24 leaves total." Re-run, that command returns **28** (it counts every error class declared in `errors.py` — base + intermediate + leaf — and excludes leaves declared/stubbed elsewhere like `SandboxRequiredError`). The underlying *fact* (24 ratified leaves) is correct and independently verifiable — `docs/contracts/error-class-hierarchy.md` numbers them through "24th ratified leaf" (`InvalidCalibrationSetError`). Only the cited reproduction command is wrong.
- **Evidence:**
  ```
  $ grep -c "^class.*Error.*:$" src/AgentEval/errors.py  → 28
  error-class-hierarchy.md L104: ... | **Story 12.2 ...; 24th ratified leaf. ...
  ```
- **Suggested fix:** Replace the verification command with one that actually yields 24, e.g. count the numbered leaf rows in the hierarchy doc: `grep -cE "[0-9]+(st|nd|rd|th) ratified leaf" docs/contracts/error-class-hierarchy.md`, or cite the doc's numbered inventory directly rather than a `grep` over `errors.py`.

### MED-2: The retirement decision leans on a metric the project itself ruled "not a precise machine-verifiable sunset gate," without computing the cleaner baseline Epic 11 recommended
- **Section / line:** `epic-12-retro-2026-06-01.md:L112` + L225 (Norm #7)
- **Issue:** The Epic 11 retro explicitly flagged sunset-criterion-2 as structurally broken (cumulative ❌ grows mechanically each epic) and said the comparison "should be read as 'retro debt did not decrease' rather than as a precise machine-verifiable sunset gate," recommending a cleaner baseline: "counting only the items NEW in the prior retro, not cumulative" (`epic-11-retro-2026-05-27.md:L111`). The Epic 12 draft acknowledges the flaw (L114) but still retires on the raw cumulative sequence (5→7→8) without ever computing the recommended new-items-only baseline. Combined with HIGH-3 (strict count is 7, not 8), the "third consecutive failure" trigger is weaker than presented.
- **Evidence:**
  ```
  epic-11-retro L111: ... should be read as "retro debt did not decrease" rather than as a precise machine-verifiable sunset gate ... counting only the items NEW in the prior retro, not cumulative.
  epic-12-retro L112: ... fails for the **third** consecutive epic (Epic 10: 5 ❌; Epic 11: 7 ❌; Epic 12: 8 ❌).
  ```
- **Suggested fix:** The retire outcome may well be right (and the replacement mechanism is sensible), but justify it on the documented grounds — "the sunset criterion is structurally non-measurable, so retire it as non-load-bearing" — rather than on the cumulative ❌ comparison the project already disowned. Drop or correct the "5 → 7 → 8, getting worse" framing.

### MED-3: N=3 → N=5 transition accounting is internally inconsistent (Epic 11 transitions re-listed as the basis for the +2)
- **Section / line:** `epic-12-retro-2026-06-01.md:L55` (header) vs L62
- **Issue:** L55 titles the section "extends N=3 → N=5 with all 4 same-surface transitions verified," implying 4 *new* transitions, while the arithmetic elsewhere is N=3 + 2 new (12.1→12.2, 12.2→12.3) = 5. L62 then states "Total Epic 11→Epic 12 same-surface transition count: 4 (11.1→11.2, 11.2→11.3, 12.1→12.2, 12.2→12.3)" — but `11.1→11.2` and `11.2→11.3` were already inside the Epic 11 close N=3 evidence base (the memory file lists them). Listing them again as the support for the +2 double-counts and muddles which transitions justify N=5. (The Epic 11 retro itself called 4 transitions "N=3," so the N-vs-transition-count mismatch is inherited, but the Epic 12 draft should not compound it.)
- **Evidence:**
  ```
  L62: Total Epic 11→Epic 12 same-surface transition count: 4 (11.1→11.2, 11.2→11.3, 12.1→12.2, 12.2→12.3); ... Norm is now N=5 confirmed (was N=3 at Epic 11 close).
  memory file L3: ... CONFIRMED at N=3 across Stories 10.1→10.2, 10.2→11.1, 11.1→11.2, 11.2→11.3
  ```
- **Suggested fix:** State it as "N=3 (Epic 11 close) + 2 NEW Epic-12 same-surface transitions (12.1→12.2, 12.2→12.3) = N=5," and drop the re-listing of the already-counted 11.x transitions. Reconcile with HIGH-1 (the memory file must actually carry N=5 for this promotion to be canonical).

---

**Net:** The Epic 12 *code* facts reconcile well; the drift is concentrated in the **retro's self-accounting** — the one "win" (HIGH-1), the commit-range citation (HIGH-2), the ❌ tally driving a norm retirement (HIGH-3 + MED-2), and a verification command (MED-1). HIGH-1 and HIGH-3 are the most load-bearing: both touch headline framing repeated across the document.
