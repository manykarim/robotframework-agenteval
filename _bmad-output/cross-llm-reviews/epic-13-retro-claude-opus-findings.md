The 15-probe verification workflow finished (15 agents, 128 read-only tool calls). Here is the synthesized adversarial review.

---

# Adversarial Cross-LLM Review — Epic 13 Retro Draft

**Reviewer identity:** I ran this as a fan-out of 15 read-only verification probes (git/grep/wc/ls re-derivation per claim). My strongest coverage is **numeric-citation drift** (Codex-class — I re-derived every count from source files and prior retros) and **framing-process drift** (Kilo-class — superlatives, vanity metrics, candidate over-reach). My weakest coverage is **semantic-shape** (Claude-class — dataclass-attribute / API-surface bugs), but that class barely applies here: this is a prose retro, not code. I did NOT pass it overall — 6 HIGH below.

The good news first: **probes 1, 2, 3, 4, 10, 11, 13 all check out exactly.** Test-count math (+166/+2), carry-over count (98, contiguous C1–C98, newest C95–C98), the 5-commit `da6ea20..HEAD` range with correct parent-exclusive notation, the 15 cross-LLM files (5×{opus,sonnet,codex}), "no Epic 14 in epics.md," all-commits-2026-06-01, and the Story-13.4-reverse-propagation fix (verified landed in `a52a464`, not deferred) are all accurate. The off-by-one git-range trap in probe 3 is NOT present — the draft uses the correct notation.

The bad news is concentrated in the **norm-extension N-counts and prior-retro comparison ratios** — exactly the citation-drift class.

---

### [HIGH]-1: Epic 10→11 follow-through ratio "4 ✅ + 4 ❌ = 50%" is fabricated — actual is 2 ✅ + 7 ❌ ≈ 22%
**Section/line:** What didn't work #1, Score line (L96)
**Issue:** The draft anchors its "worst in project history" claim on prior ratios. The Epic 10→11 figure is invented: not one of the four numbers (4 done, 4 not-done, denominator 8, 50%) matches the actual Epic 11 retro, which audited a 9-item table and recorded **2 ✅ + 7 ❌ (2/9 ≈ 22%)**.
**Evidence:**
```
Epic 13 retro L96: "...Epic 10 → 11 was 4 ✅ + 4 ❌ = 50%)."
Epic 11 retro L107: "Action-item follow-through: 2 ✅ + 7 ❌."
grep "4 ✅|50%|4 done \+ 4" epic-1[01]-retro-*.md → only "4 ✅ + 5 ❌" (unrelated Epic 9 baseline); no "50%" exists.
```
**Fix:** Replace with "Epic 10 → 11 was 2 ✅ + 7 ❌ (9 actions, ~22%)." Note this *strengthens* the trajectory (22% → 11% → 9% is monotone-decreasing), so "worst in project history" survives — but only after the number is corrected.

---

### [HIGH]-2: Snapshot precheck row contradicts the body and the spec-file headers (+4 vs +5; use-51-on-a-12.x-story)
**Section/line:** Snapshot table L26 vs body §5 (L132–138, L149)
**Issue:** The snapshot says `51 → 55 (+4 in Epic 13; 1 use was on a 12.x story late in epic 12)`. The body and all five spec-file headers say uses **51–55 are Stories 13.1–13.5 (+5)**, and the Epic 12 retro closes Epic 12 at use 50 = Story 12.3. So use 51 is Story 13.1, not a 12.x story. The snapshot row's own cited evidence refutes the value it presents.
**Evidence:**
```
13-1 spec L11: "(51st use ... 2026-06-01)" ... 13-5 spec L11: "(55th use ... 2026-06-01)"
Epic 12 retro L246: "47 (Epic 11 close) + 3 (12.1=48; 12.2=49; 12.3=50) = 50."
Retro body L138: "55 consecutive uses (... → 50 at Story 12.3 → 55 by Story 13.5)" [correct]
```
**Fix:** Rewrite L26 to `50 → 55 (+5 in Epic 13; Stories 13.1–13.5 = uses 51–55)`.

---

### [HIGH]-3: "N=12+ cumulative same-surface transitions" mixes units (transitions vs lessons) and inflates the count
**Section/line:** What worked #2 (L52) + Extended table (L148)
**Issue:** Prior N=5 was counted in *transitions*. Epic 13 has 5 stories = **4** consecutive transitions, not 7. The "12" arises only from 5(transitions) + 7(named lessons L-1…L-7), conflating two non-comparable units. Correct: 5 + 4 = **9**. The inflated figure appears in both body and table as the new evidence-base anchor a future reader will carry forward.
**Evidence:**
```
L52/L148: "N=12+ cumulative same-surface transitions (was N=5 at Epic 12 retro)"
L28: "L-1 → L-7 (7 named lessons)"  ← 7 is the lesson count, not transitions
Memory frontmatter: prior N counted as transitions (10.1→10.2 ... 12.2→12.3)
```
**Fix:** State "N=9 cumulative same-surface transitions (5 prior + 4 in Epic 13)"; keep "7 lessons" as a separate, clearly-labeled unit. (Secondary, LOW: the memory file itself labels a 6-transition list as N=5 — reconcile before re-anchoring.)

---

### [HIGH]-4: `feedback_codex_probe_fitness` "N=8 stories (Epic 10 retro)" baseline is fabricated
**Section/line:** Extended table (L153)
**Issue:** The Epic 10 retro never assigns this norm any N. It is discussed qualitatively from Epic 2 (ratified N=1, Story 2.2) through Epic 8 as "CONFIRMED" — never with a story-count. The only "N=9" in the Epic 10 retro is `feedback_third_llm_family_fallback`. Both the prior value (8) and its citation (Epic 10 retro) are unsupported, making the whole 8→13 delta uncheckable.
**Evidence:**
```
grep "probe_fitness|N=8 stories" epic-10-retro*.md → 0 hits
Epic 10 retro L236 "N=9 substantive reviews" → third_llm_family_fallback, NOT probe_fitness
Memory file: "Ratified Epic 2 retro" with N=1 (Story 2.2); records no running N
```
**Fix:** Drop the fabricated "N=8 (Epic 10 retro)" prior. Either state "qualitatively CONFIRMED Epics 2/3/5/7/8; first quantified here," or derive a count bottom-up from enumerated per-story Codex-unique catches.

---

### [HIGH]-5: The codex-probe-fitness +5 addend is internally unsupported; 13.5 is a MED, not a HIGH; 13.4 is absent
**Section/line:** Extended table L153 vs What worked #4 (L62, L116–123)
**Issue:** L153 claims 8→13 (+5) on evidence "5 Codex-unique empirical HIGHs across Stories 13.1 + 13.2 + 13.3 + 13.5" — that string lists only **4** stories (13.4 absent), and the draft itself classifies 13.5's catch as **Codex MED-2**, not a HIGH. So HIGH-only addend = 3 (13.1/13.2/13.3); any-catch addend = 4. Neither is 5. Plus (MED): Epics 11+12 had *zero* story-level Codex catches (rate-limited per both retros), so an 8→13 chain through them is incoherent. And within the same retro N is stated as both "N=10+" (L125) and "N=13" (L153).
**Evidence:**
```
L153: "5 Codex-unique empirical HIGHs across Stories 13.1 + 13.2 + 13.3 + 13.5" (4 stories listed)
L62: "Codex caught reviewer-UNIQUE empirical HIGHs in 4/5 stories"
L106/L123: "Codex MED-2" for 13.5
epic-11-retro L218 / epic-12-retro L235: Codex unavailable at story-level both epics
```
**Fix:** Relabel to "4 Codex-unique catches (3 HIGH + 1 MED) across 13.1/13.2/13.3/13.5"; pick a single consistent N derived from an explicit enumeration; footnote the Epics 11+12 zero-contribution.

---

### [HIGH]-6: "Story-level test count grew 1.7× the rate of source files" is an unsupported vanity ratio
**Section/line:** What worked #5, header (L66)
**Issue:** The "1.7×" appears only in the header; the body (L68) is entirely test *counts* (+166, 33/story, 24 in 13.5) and never mentions source files. No numerator/denominator is cited anywhere, and no git-derived combination yields 1.7× (test-files/src-files ≈ 1.25×).
**Evidence:**
```
grep -niE "1\.7|source files" retro → single hit, the header only
git diff --name-only da6ea20..HEAD -- src/ | wc -l → 16 (4 new); tests/ → 20
```
**Fix:** Delete the "1.7×" claim. Retitle #5 to a defensible figure, e.g. "Review chain forced +166 net new tests across 5 stories," or cite the real "20 test files vs 16 source files touched."

---

### [MED]-1: Epic 11→12 ratio "1 ✅ + 8 ❌" re-imports a breakdown the Epic 12 retro explicitly retracted
**Section/line:** L96 (also candidate #1 body L160)
**Issue:** Epic 12 retro was *patched* (its own Claude HIGH-3 + Codex HIGH-2) from "1 ✅ + 8 ❌" to "1 ✅ + 1 ⚠ Partial + 7 ❌" because folding the Partial into ❌ inflated the three-strike narrative. Epic 13 resurrects the retracted tally. The **percentage is coincidentally unaffected** (1/9 = 11% either way), which is why this is MED not HIGH — but the breakdown drift re-propagates a corrected error.
**Evidence:** `Epic 12 retro L110: "Patched ... original draft tallied '1 ✅ + 8 ❌' folding the ⚠ Partial into ❌, inflating Epic 12 from 7 to 8."`
**Fix:** Change to "1 ✅ + 1 ⚠ + 7 ❌ = 11%."

---

### [MED]-2: Body L138 "49 entering Epic 12" — actual entering count was 47 (49 = Story 12.2)
**Section/line:** §5 closing sentence (L138)
**Issue:** Story 12.1 = use 48, 12.2 = 49, 12.3 = 50, so Epic 12 was *entered* at 47 (Epic 11 close). The phrase conflates "use 49 = Story 12.2" with "entering Epic 12." Downstream "→ 55 by Story 13.5" is correct, so the +5 conclusion is unaffected.
**Fix:** "(47 entering Epic 12 → 50 at Story 12.3 → 55 by Story 13.5)."

---

### [MED]-3: "Most load-bearing norm by usage count and confirmed catch rate" is a self-graded superlative over incommensurable units
**Section/line:** §5 / Honest framing (L138, L195)
**Issue:** The Extended table measures each norm in a *different* unit (precheck=55 "uses," catalog_gate=36 "stories," third_llm=24+ "reviews," n_way=17+ "TPs"). "55 uses" is the highest raw integer, but "uses" is a per-story-authoring counter that ticks by construction — it measures cadence, not load-bearing-ness. And "100% catch rate" is author-graded with no independent adjudicator, so it is structurally unfalsifiable.
**Fix:** Soften to "highest raw consecutive-use count (55) and zero self-recorded misses"; drop the unqualified "the project's most load-bearing norm."

---

### [MED]-4: CANDIDATE #1's justification is factually false — Epic 13 is NOT the project's first autonomous /goal loop
**Section/line:** CANDIDATE #1 (L160), supported by L98 "debt grows monotonically"
**Issue:** The candidate's stated reason ("single data point — Epic 13 is the project's first end-to-end autonomous /goal loop") is wrong: Epics 11 and 12 retros both describe themselves as autonomous /goal loops. So there *is* a prior baseline — and it contradicts "monotonic" debt growth: 50% → 11% → 9% is a 39-pt cliff then a 2-pt drift (noisy/decelerating, not monotone). The candidate is correctly held, but its evidence shape doesn't match its generalization.
**Evidence:** `epic-11-retro L14: "3/3 stories done across 2 autonomous /goal iterations"; epic-12-retro L14: "single autonomous /goal iteration on 2026-05-27."`
**Fix:** Drop the false "first autonomous loop" claim; reframe as "first single-day 5-story autonomous loop; prior loops (Epics 11, 12) gave 11% and 50%, N≈3 with confounds." Soften "monotonically" → "follow-through has stayed low (50% → 11% → 9%)."

---

### [MED]-5: "What worked" #6 reframes routine fix-during-review as a structural "pattern inversion," and framing leans celebratory
**Section/line:** What worked #6 (L70–72); also velocity superlatives L6/L34/L36/L38/L195/L229
**Issue:** Fixing a pre-existing bug the moment a reviewer surfaces it is ordinary review hygiene, not "the cross-story lesson propagation working in REVERSE" (lesson-propagation is about folding into *future* ACs). Dressing it as a named inversion pads the celebratory ledger. More broadly, "first single-calendar-day epic" is asserted 3× plus a stack of "strongest/most/survived maximum velocity" superlatives, while the 9% finding (the epic's most operationally important takeaway) gets a deliberately measured tone. The debt *is* honestly recorded (11-row table, prominent) — so it doesn't collapse into self-congratulation — but the framing weight tilts.
**Fix:** Demote #6 to a one-line note; cut the repeated "first single-calendar-day" to one occurrence; give the 9% finding equal framing prominence (e.g., lead Closure with it).

---

### [LOW]-1: Action #8 says "5 live test files" — there are 6 (omits `test_openai_agents_sdk_live.py`)
**Section/line:** Follow-through table Action #8 (L91) + forward Action #8 (L183)
**Evidence:** `ls tests/integration/test_*_live.py → 6` (claude_agent_sdk, codex_cli, copilot_cli, judge_calibrate, judge, **openai_agents_sdk**). Doesn't change the NOT-DONE status.
**Fix:** "6 files"; add the missing one to the enumeration.

---

### [LOW]-2: "first single-calendar-day epic" superlative is weakly anchored — Epic 12's 3 story commits also landed in one day (2026-05-27)
**Section/line:** Cross-cutting note (L6)
**Evidence:** Epic 12 commits 12.1/12.2/12.3 all dated 2026-05-27. Epic 13's real distinction is the *5-story* count same-day, not same-day per se.
**Fix:** "first epic where all 5 stories shipped within a single calendar day," or note Epic 12 was also same-day (retro deferred).

---

**Verified-clean (NONE) and NOT flagged:** test-count math (P1), carry-over count + contiguity (P2), commit range + correct `da6ea20..HEAD` notation (P3), 15 review files (P4), the 7 audited action statuses #1/#2/#5/#6/#7/#8/#9 (P5), no-Epic-14 / Phase-3-is-historical (P10), all-commits-2026-06-01 (P11), Story-13.4 reverse-propagation fix landed in `a52a464` (P13), CANDIDATE #2 and #3 correctly scoped to their N=1 instances (P15). The Epic-13 *internal* 1/11 = 9% math is also correct — only the *prior-epic comparison ratios* are wrong.

**Total: 6 HIGH + 5 MED + 2 LOW**

**Class I caught best:** numeric-citation drift — every HIGH is a fabricated/inflated/inconsistent count traceable to a source file (prior-retro ratios, norm N-counts, snapshot-vs-body contradictions, the vanity ratio). **Class I caught second:** framing-process — superlatives, candidate over-reach, celebratory tilt. **Class I likely under-probed:** semantic-shape — I verified the *existence and landing* of cited code fixes (P13) but did not re-audit the underlying Story 13.x *implementations* for dataclass-attribute / API-surface bugs (those were the per-story reviews' job; this retro doesn't re-assert them). If a HIGH hides anywhere I'd be weak, it's a mischaracterized *technical nature* of one of the enumerated Codex catches — I confirmed counts and severities, not the SDK-behavior claims themselves.

---

Note: there's already an untracked `_bmad-output/cross-llm-reviews/epic-13-retro-claude-opus-findings.md` in the tree. I did not touch it (read-only review). Want me to write these findings to a `epic-13-retro-claude-opus-findings.md` for the audit trail, or apply the HIGH fixes as a v2 of the retro?
