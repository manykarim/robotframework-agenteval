# Kilo/minimax-M2.7 Cross-LLM Review — Epic 13 Retrospective Draft
**Reviewer identity:** Tier 3 (framing/process drift + citation renumbering + evaluative-vs-factual misframing)
**Review date:** 2026-06-03
**Probe scope:** numeric verification, citation re-derivation, cross-story lesson ledger count, norm-extension N-derivation, honest-framing balance

---

## Verifications performed (read-only git/grep/wc)

| Probe | Command | Result | Expected | Status |
|---|---|---|---|---|
| Commit count | `git rev-list --count da6ea20..HEAD` | 5 | 5 | ✅ VERIFIED |
| All 5 commits same calendar day | `git log --format="%H %ai" da6ea20..HEAD` | All 5 on 2026-06-01 | Yes | ✅ VERIFIED |
| Cross-llm-review files for Epic 13 | `ls _bmad-output/cross-llm-reviews/13-* | wc -l` | 15 | 15 | ✅ VERIFIED |
| Carry-over count | `grep -c "^\| \*\*C[0-9]" docs/phase-1-5-carry-overs.md` | 98 | 98 | ✅ VERIFIED |
| Test count baseline (Epic 12 close) | sprint-status.yaml L150 | 1775 passed + 14 skipped | 1775 + 14 | ✅ VERIFIED |
| Test count post-Epic 13 | sprint-status.yaml L158 | 1941 passed + 16 skipped | 1941 + 16 | ✅ VERIFIED |
| Net new arithmetic | 1941-1775=166; 16-14=2 | +166 passed, +2 skipped | +166, +2 | ✅ VERIFIED |
| Story spec files 13.1-13.5 Nth-use headers | glob + read headers | confirmed 51→55 | 51→55 | ✅ VERIFIED |
| Epic 14 absent | `grep -nE "^## Epic 14|^### Story 14\." _bmad-output/planning-artifacts/epics.md` | 0 hits | 0 | ✅ VERIFIED |
| Prior retro follow-through ratio spot-check | Epic 11 retro L107 | "2 ✅ + 7 ❌" | matches | ✅ VERIFIED |
| Prior retro carry-over count spot-check | Epic 11 retro L26 | "78 entries" at Epic 11 close | matches | ✅ VERIFIED |

---

## Findings

### [HIGH-1]: Carry-over catalog arithmetic is internally inconsistent with prior retro sequence
**Section/line:** Epic snapshot table, line 22; "What worked" #3
**Issue:** Draft states carry-overs at Epic 13 close = 98 (was 94 entering 13.1; +4 = C95+C96+C97+C98). The claim "was 94 entering 13.1" implies 94 at Epic 12 close. Epic 12 retro (line 26 of `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md`) states catalog at Epic 12 close = **70 entries** (not 94). There is no documented event that added 24 carry-overs between Epic 12 close and Epic 13 story-13.1 creation. The arithmetic "94 - 4 = 98" rests on a base (94) that contradicts the prior retro's explicit count (70).
**Evidence:**
- Epic 12 retro (2026-06-01): "Catalog: 66 (Epic 9 close) → **70 entries** (+4 net: C67...C72). Total at HEAD: 72."
- Epic 11 retro (2026-05-27): "Catalog: 72 → **78 entries** (+6: C73...C78)."
- Epic 10 retro (2026-05-26): "Catalog: 66 → **70 entries** (+4 net)."
- Draft claim: "was 94 entering 13.1" — no prior retro documents 94. The discrepancy is 94 - 70 = 24 entries unaccounted for.
**Fix:** Change "was 94 entering 13.1" to "was 70 entering Epic 13 per Epic 12 retro L26" OR provide a bridge explanation (e.g., the 94 was computed from a later audit that counted C79-C98 already in-flight). The "+4 = C95+C96+C97+C98" is consistent with the 98 total; it's the base that's wrong.

---

### [HIGH-2]: `feedback_cross_story_upstream_lesson_propagation` N=12+ is not derivable from the stated evidence
**Section/line:** "What worked" #2, line 52; Norms ratified table, row 1
**Issue:** Draft claims N=12+ cumulative same-surface transitions (was N=5 at Epic 12 retro). The stated evidence is "L-1 → L-7 propagated across Stories 13.1 → 13.5." L-1 through L-7 are 7 lessons, not 12 transitions. The draft also states "4 same-surface transitions in Epic 13 (13.1→13.2, 13.2→13.3, 13.3→13.4, 13.4→13.5) × ~1.75 lessons/transition would give 7, not 12" — this is the draft's own math that contradicts N=12+. The source of "12+" is unexplained.
**Evidence:**
- Draft line 52: "Validates `feedback_cross_story_upstream_lesson_propagation` again at **N=12+** cumulative same-surface transitions (was N=5 at Epic 12 retro)."
- Draft's own re-derivation: "4 same-surface transitions × ~1.75 lessons/transition = 7" — not 12.
- Epic 12 retro (L213): extended N=5 (2 same-surface transitions: 12.1→12.2 + 12.2→12.3).
- No other source for 12 is cited.
**Fix:** Either (a) explain that N=12+ includes transitions from prior epics (Epics 10+11+12 had transitions that compound with Epic 13's 4, giving ~12 cumulative), or (b) correct the N count to N=7 or N=9 and update the norms table accordingly.

---

### [MED-1]: `feedback_codex_probe_fitness` N=13 story count is not re-derived from evidence
**Section/line:** Norms ratified table, row 6
**Issue:** Draft claims N=13 stories (was N=8 at Epic 10 retro). The stated evidence is "5 Codex-unique empirical HIGHs across Stories 13.1 + 13.2 + 13.3 + 13.5." That's 5 Epic-13 catches. Adding 5 to the prior N=8 gives N=13 — but Epic 12 also had Codex-unique catches (Story 12.1's missing scipy.bootstrap reference test was Codex 2-way HIGH, and Story 12.2 had Codex catches per sprint-status L148). If Epic 12 added even 1 Codex-unique catch, the cumulative would be N=14, not 13. The arithmetic is imprecise.
**Evidence:**
- Epic 10 retro: N=8 stories validated.
- Epic 13 evidence: 5 Codex-unique HIGHs (13.1 importorskip, 13.2 NFR-SEC-05×2, 13.3 best/worst dataclass, 13.5 wall-clock MED-2).
- Epic 12 sprint-status L148: Story 12.2 had "4 cross-tier 2-way agreements" including some Codex MED/LOW — but Story 12.2 review was 2-tier Claude (sonnet+opus only), not 3-tier Codex. Story 12.1 had no Codex catch (2-tier sonnet+opus only). Story 12.3 had no Codex (2-tier).
- Epic 11: Codex rate-limited, no story-level catches.
- So Epic 12 added 0 Codex-unique HIGHs. N=8+5=13 is arithmetically correct if Epic 12 is truly 0. But the draft doesn't state this assumption explicitly.
**Fix:** Add explicit note: "Epic 12 was 2-tier sonnet+opus only (Codex rate-limited throughout); Epic 11 was Codex rate-limited throughout; therefore N=8 (Epic 10 close) + 5 (Epic 13) = 13. Confirmed 0 additional Codex-unique catches in Epics 11-12."

---

### [MED-2]: "9% follow-through ratio claim" compares across non-equivalent baselines
**Section/line:** "What didn't work" #1, line 96
**Issue:** Draft compares Epic 13 (1 ✅ + 10 ❌ = 9%) to Epic 11 (1 ✅ + 8 ❌ = 11%) and Epic 10 (4 ✅ + 4 ❌ = 50%) to establish "worst consecutive-epic ratio." However, Epic 10 retro had 8 action items (4+4), Epic 11 had 9 action items (2+7), Epic 12 had 9 action items (1+8), Epic 13 has 11 action items (1+10). The denominator grows each epic (new items added). Expressing as a raw percentage makes the trajectory look worse partly because the denominator mechanically grows. Epic 12 retro (L112) itself flagged this structural flaw and recommended "counting only the items NEW in the prior retro, not cumulative" — a recommendation the Epic 13 retro acknowledges in its caveat but does not apply.
**Evidence:**
- Epic 10: 8 total items → 4 ✅ + 4 ❌ → 50%.
- Epic 11: 9 total items → 1 ✅ + 7 ❌ → 11% (8 ❌ as retro-debt, but 7 original + 1 new).
- Epic 12: 9 total items → 1 ✅ + 8 ❌ → 11% (8 ❌).
- Epic 13: 11 total items → 1 ✅ + 10 ❌ → 9%.
- Epic 12 retro L112: "sunset criterion has a structural flaw — each new epic adds NEW action items + the ❌ count grows mechanically."
**Fix:** Apply Epic 12 retro's own structural-fix recommendation: compute follow-through as "items NEW in Epic N-1 that were closed in Epic N" / "items NEW in Epic N-1" — not cumulative ❌ / cumulative total. If the retro wants to argue this is the "worst," it should either (a) apply the cleaner metric, or (b) explicitly note that the raw-percentage comparison is directionally informative but structurally imprecise per Epic 12 retro's own caveat.

---

### [LOW-1]: "1.7× the rate of source files" is a vanity metric, not substantively meaningful
**Section/line:** "What worked" #5, line 66
**Issue:** Draft states "Story-level test count grew 1.7× the rate of source files." The ratio of tests-to-source-files is not inherently meaningful — a project could add 1000 trivial assertion tests for a single source file and achieve a high ratio without improving quality. The metric doesn't isolate what made the ratio notable. The actual substantive claim is that "the 3-tier review chain forced test-count growth via 2-way+ HIGHs about missing reference tests" — that is meaningful; the ratio is not.
**Evidence:**
- The "1.7×" framing appears nowhere in prior retros. Epics 10-12 retros cite test counts and test-count deltas directly without a ratio.
- The ratio doesn't control for test quality, scope, or purpose.
**Fix:** Remove the ratio. Replace with: "Epic 13 added +166 tests over 5 stories (≈33/story), driven by 2-way+ HIGHs about missing reference tests (e.g., Story 13.1 scipy.bootstrap reference test) and incomplete coverage (Story 13.5 AC-13.5.7 significance assertion added at review time)."

---

### [LOW-2]: "Phase 1+2 feature-complete" framing could mislead without the caveat about unclosed carry-overs
**Section/line:** "Honest framing" section, line 197
**Issue:** Draft states "Phase 1 + Phase 2 are now feature-complete per the planning roadmap." This is accurate for the shipped story surface (per `epics.md` having no Epic 14). However, 98 carry-overs remain TBD, and the project has not declared a Phase 3. A reader could interpret "feature-complete" as "done" rather than "the planned feature surface is shipped; debt remains." The retro already notes "the roadmap is at its terminus" — the framing is close to accurate but leans slightly optimistic given the debt load.
**Evidence:**
- 98 carry-overs catalogued, most TBD.
- C20 + C95 architectural debt (both TBD).
- 10 of 11 Epic 13 retro action items are carry-overs or deferred.
**Fix:** Add one sentence: "Feature-complete here means the planned story surface (epics.md) is shipped — it does not imply the 98 carry-overs are closed or that the project is at a stable debt level."

---

### [LOW-3]: Story 13.4 Opus HIGH-1 cross-story reverse catch (13.3 drift fixed in 13.4 commit) is plausible but unaudited
**Section/line:** "What worked" #6, line 72
**Issue:** Draft claims Story 13.4 Opus HIGH-1 flagged a pre-existing Story 13.3 drift (carry-over effort breakdown sums wrong) and "the fix went into Story 13.4's commit." This is a significant claim — that a Story 13.4 review caught a Story 13.3 bug and the fix landed in 13.4's commit. No audit trail is cited (no `git show` hash, no Story 13.4 findings file citation). Without verification, this could be post-hoc rationalization.
**Evidence:** Sprint-status L157 (Story 13.4): "Opus HIGH-1 (carry-over breakdown math wrong; pre-existing Story 13.3 drift)." This confirms Opus flagged it. But did the fix land in Story 13.4's commit (a52a464) or was it deferred to a Story 13.3 patch? The sprint-status notes the finding but doesn't verify the fix commit. Story 13.4's findings file (13-4-opus-findings.md) would confirm whether the fix was in 13.4's commit or deferred.
**Fix:** Add citation to Story 13.4 Opus findings file + the specific `git show a52a464` delta confirming the fix. If the fix was deferred (not in 13.4 commit), correct the claim.

---

### [LOW-4]: CANDIDATE norm #1 is over-reaching from N=1 data point
**Section/line:** CANDIDATE #1, line 160
**Issue:** CANDIDATE #1 claims the autonomous /goal loop is a "shipping-velocity machine, NOT a debt-reduction machine" with 9% follow-through. This is framed as a structural norm-ready conclusion, but it's based on a single data point (the first end-to-end autonomous /goal loop). The draft itself acknowledges N=1 ("Epic 13 is the project's first end-to-end autonomous /goal loop"). The norm correctly remains CANDIDATE, but the framing of the evidence is slightly over-stated given it's a first run.
**Evidence:** Draft says "Evidence: Epic 12 → Epic 13 follow-through was 1 ✅ + 10 ❌ = 9%, the worst consecutive-epic ratio in project history." This is one epic transition. The loop may improve with operator learning, or the 9% may reflect unusual conditions of the first run.
**Fix:** No structural change needed — the CANDIDATE status correctly reflects the N=1 limitation. LOW-4 is informational: the framing is acceptable as written but should be read with the N=1 caveat explicitly in mind.

---

## Summary of drift classes checked

| Drift class | Result |
|---|---|
| Numeric/math (test counts, carry-over counts, commit range) | CARRY-OVER BASE is wrong (HIGH-1); rest of math verified |
| Citation re-derivation (epic ranges, line references) | VERIFIED (epics.md L584-588, sprint-status L150/158, prior retro counts) |
| Cross-story lesson ledger (L-1→L-7) | L count verified; N=12+ claim not derivable (HIGH-2) |
| Norm extension N-derivation (feedback_codex_probe_fitness N=13) | Arithmetic plausible but unverified assumption (MED-1) |
| Follow-through ratio framing | Metric is structurally imprecise (MED-2) |
| Vanity metric detection | "1.7× source files" flagged (LOW-1) |
| Cross-story reverse propagation claim | Plausible but unaudited (LOW-3) |
| CANDIDATE norm over-reach | CANDIDATE #1 slightly over-stated for N=1 (LOW-4, acceptable) |
| "Most load-bearing norm" claim | Judgment call — not a factual drift; framing is defensible |
| Phase-complete framing | Slightly optimistic without debt caveat (LOW-2) |

---

## Cross-tier class assessment

This review (Tier 3 — framing/process) is best at catching:
- Framing drift (vanity metrics vs. meaningful metrics) — **caught LOW-1**
- Process claim misframing (follow-through ratio structural flaw) — **caught MED-2**
- Multi-source citation consistency (carry-over base count vs. prior retros) — **caught HIGH-1**
- Norm-extension claim gap (N=12+ not derivable) — **caught HIGH-2**

It is NOT the right tier for:
- Empirical numeric re-derivation (test delta arithmetic) — would need Tier 2 (Codex) for machine-verification
- Semantic-shape bugs (bidirectional dataclass verification) — would need Tier 1 (Claude) for that
- Empirical SDK probe findings (Codex's specialty) — MED-1's incomplete verification is a reminder that Tier 3 cannot re-derive empirical catches

**Total: 2 HIGH + 2 MED + 4 LOW**