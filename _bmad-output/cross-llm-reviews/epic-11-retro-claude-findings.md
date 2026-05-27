# Epic 11 retro — Claude CLI (Tier-1-alternative) adversarial review findings

**Reviewer:** Claude (Opus 4.7), executing the adversarial-review prompt at
`_bmad-output/cross-llm-reviews/epic-11-retro-review-prompt.md`.
**Date:** 2026-05-27
**Target:** `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md`
**Method:** every numeric claim re-derived from git / source / story records per
`feedback_citation_drift_first_class` + `feedback_honest_framing`.

**Empirical anchors verified this session:**
- `uv run pytest tests/ -q` → **`1696 passed, 12 skipped`** (real, 129s run).
- `grep -c "^| \*\*C" docs/phase-1-5-carry-overs.md` → **78**; C73–C78 all present.
- `find src -name "*.py" | wc -l` → **99**; `uv run mypy src/` → 99 source files.
- `git log --oneline 229313e..577cf36 | wc -l` → **3**.
- `git rev-list --count 229313e..HEAD` → **3** (NOT 4); `git rev-list --count 438b4a4..HEAD` → **4**.
- memory file `feedback_cross_story_upstream_lesson_propagation.md` **exists** (mtime 2026-05-26 19:02); both norms present in `MEMORY.md`.

---

## HIGH — numeric drift, citation drift, false invariant

### HIGH-1 — "7 commits post-Epic-10-close" contradicts its own verification parenthetical AND the rev-list claim is wrong

**Section:** Epic snapshot, L32.

> "**7 commits post-Epic-10-close** (verified: `git log --oneline 229313e..577cf36 | wc -l` → 3 Epic 11 commits; `git rev-list --count 229313e..HEAD` → 4 incl. the CLAUDE.md ratification at `229313e`)."

Three defects in one line:
1. **The headline "7 commits" is supported by nothing** — the parenthetical's own numbers are 3 and 4, never 7. The Honest-framing section L226 itself says "**3 Epic 11 commits** at retro time." So the document contradicts itself (7 vs 3).
2. **`git rev-list --count 229313e..HEAD` is 3, not 4** (verified this session). The draft states 4.
3. **"4 incl. the CLAUDE.md ratification at `229313e`" is logically impossible** — the range `229313e..HEAD` *excludes* its left endpoint `229313e`, so it can never "include" the ratification commit. The count that legitimately yields 4 *and* includes the ratification is `438b4a4..HEAD` (= 229313e + the 3 story commits).

**Concrete fix:** Drop "7 commits". Replace L32 with:
> "**Epic 11 = 3 story commits** (`git log --oneline 229313e..577cf36 | wc -l` → 3: `3f52ff2`, `cbe7521`, `577cf36`), preceded by the CLAUDE.md ratification at `229313e`. The full Epic-10-retro→Epic-11-close span is 4 commits: `git rev-list --count 438b4a4..HEAD` → 4."

---

### HIGH-2 — `feedback_third_llm_family_fallback` "N=12" arithmetic does not reconcile (and counts the wrong tool)

**Sections:** What worked #4, L75; Norms ratified #2, L196.

> "extends `feedback_third_llm_family_fallback` from N=9 … to **N=12** (3 more story-level substantive reviews via kilo + 3 via copilot)."

`9 + 3 + 3 = 15`, not 12. The stated composition (3 kilo **plus** 3 copilot) yields 15; the stated total is 12. The two cannot both be true.

Worse, the *category* is wrong: `feedback_third_llm_family_fallback` is specifically the **kilo/minimax (third-LLM-family) fallback** norm (memory file: "N=9 substantive reviews … `kilo run --auto --model minimax/MiniMax-M2.7` is canonical fallback"). GitHub Copilot CLI runs **claude-sonnet-4.6** — a Claude-family Tier-1 *alternative*, not the third family. Copilot reviews must not be counted toward this norm at all.

**Concrete fix:** State **N=12 = 9 (Epic 10) + 3 (Epic 11 kilo story-level reviews)** and remove "+ 3 via copilot" from this norm's count. If the intent is to track copilot's 3 reviews, do it under a *separate* Tier-1-alternative tally, not under the minimax-fallback norm. Apply the same fix at Norms #2 L196.

---

### HIGH-3 — UPSTREAM lesson counts mis-assigned: the 10.2→11.1 transition was **9/9**, not 5/5

**Sections:** What worked #1, L50; What worked #2, L52–56; Norms ratified #1, L194.

> L50: "Epic 11 closes with N=3 validated story-transitions (10.2→11.1, 11.1→11.2, 11.2→11.3). **5/5 + 5/5 + 6/6** UPSTREAM lessons applied at each transition."

Re-derived from the story records:
- **10.2→11.1**: `11-1-codex-cli-adapter.md` L105 / L191 / L255 — "**9 cross-story UPSTREAM lessons applied** … the reviewers verified ALL **9** lessons were correctly applied." → **9/9**, not 5/5.
- **11.1→11.2**: both 11.2 review files carry a "5-item checklist … **UPSTREAM pass rate: 5/5**." → 5/5. ✓
- **11.2→11.3**: `11-3-…md` L119 / L183 — "**6 cross-story UPSTREAM lessons applied**." → 6/6. ✓

So the correct sequence for the three Epic-11 transitions is **9/9 + 5/5 + 6/6**. The draft's first term (5/5 for 10.2→11.1) is wrong. The misplaced "5/5" actually belongs to the **10.1→10.2** Epic-10 transition — which is exactly how `11-3-…md` L246 wrote it ("Stories 10.1→10.2; 11.1→11.2; 11.2→11.3. 5/5 + 5/5 + 6/6"). The retro copied the counts but swapped the transition set, breaking the mapping.

This also **self-contradicts** the draft: What worked #2 L54 says Story 11.1 "folded **9** UPSTREAM lessons," while the matrix L50 says that same transition was 5/5.

**Concrete fix:** In What worked #1 L50 and Norms #1 L194, write the three Epic-11 transitions as **10.2→11.1 = 9/9; 11.1→11.2 = 5/5; 11.2→11.3 = 6/6**. Then reconcile What worked #2 L54–56: the "+3 new Story 11.1 review patches" / "+5 new Story 11.2 patches" figures are not supported by the records (the verified review-checklists were 5 items for 11.1→11.2 and 6 lessons for 11.2→11.3) — restate them to match the 9 / 5 / 6 numbers or delete the cumulative-arithmetic clause.

---

### HIGH-4 — "28 pre-create drifts caught in Epic 11" — the parts sum to 33, not 28

**Section:** Norms ratified #3, L198.

> "44 → **47 consecutive uses** + **28 pre-create drifts caught in Epic 11** (11 in 11.1; 12 in 11.2; 10 in 11.3)."

The three itemized counts are each correct (11.1=11 per `11-1-…md` L13; 11.2=12 per `11-2-…md` L13; 11.3=10 per `11-3-…md` L13) — but **11 + 12 + 10 = 33**, not 28. The "28" looks borrowed from the *adjacent* `feedback_carry_over_catalog_gate` "28 consecutive stories" metric (a conflation of two different norms' numbers).

**Concrete fix:** Change "28 pre-create drifts" → "**33 pre-create drifts** (11 in 11.1; 12 in 11.2; 10 in 11.3)."

---

## MED — accounting breakdown, citation, framing

### MED-1 — `feedback_carry_over_catalog_gate` "28 consecutive" step-breakdown contradicts the three story records

**Sections:** Epic snapshot L28; Honest framing L225.

> L28: "23 → **28 consecutive stories** (24 → 11.1; 25-27 → today's docstring-refresh + rf-mcp E2E + Epic 10 retro; 28 → 11.2 + 11.3 via review-time enforcement)."

The **end total 28 is correct** (`11-3-…md` L113/L181/L265 = 28th). But the per-step attribution is wrong. The dev-complete records number the three stories as **11.1 = 26th** (`11-1-…md` L189/L279), **11.2 = 27th** (`11-2-…md` L182/L259), **11.3 = 28th**. The draft instead puts 11.1 at 24 and lumps 11.2+11.3 both into "28," which fits neither the records nor simple counting (you cannot have two distinct stories both be the 28th consecutive application).

**Concrete fix:** Align the breakdown to the records: "23 (Epic 10 close) → 24 + 25 (ad-hoc 2026-05-26 docstring-refresh + rf-mcp E2E) → **26 = 11.1; 27 = 11.2; 28 = 11.3**." Fix the parallel "+5" itemization at L225 the same way (the +5 = 2 ad-hoc + 11.1 + 11.2 + 11.3, not "Epic 10 retro work + 3 stories").

---

### MED-2 — Test-count "confirmed via Story 11.3 v0.3.0 Change Log" is a false citation (the Change Log says 1700+)

**Section:** Honest framing, L221 (and Epic snapshot L24).

> "1696 pytest pass + 12 skipped at Epic-11-close: confirmed via Story 11.3 v0.3.0 Change Log + sprint-status footer."

The number **1696 is empirically correct** (verified by live `uv run pytest` this session). But the **cited source is wrong**: `11-3-…md` L256 and the v0.3.0 Change Log L264 both say "**1700+ pytest pass / expected 1700 passed + 12 skipped**" — an over-projection that never reconciled to the actual 1696. So the draft cites a source that states a *different, wrong* number to "confirm" the right one.

**Concrete fix:** Cite the actual run — "confirmed via `uv run pytest tests/ -q` → `1696 passed, 12 skipped`" — and add a one-line correction to the Story 11.3 record noting its "1700+" projection was 4 high (actual 1696). This keeps `feedback_honest_framing`'s "machine-verified, not projected" bar.

---

### MED-3 — Orthogonal-coverage matrix drops a Story 11.1 kilo-UNIQUE HIGH (kilo H-2)

**Section:** What worked #1 matrix, L44 (Story 11.1 row); echoed L79 / L210.

The matrix's Story 11.1 kilo-UNIQUE cell lists only "H-1 (`reasoning_output_tokens`)". But `story-11-1-kilo-findings.md` reports **2 HIGH** (H-1 data-loss + **H-2 citation-history drift**), and `11-1-…md` L219/L237 confirm kilo's review was "**2 HIGH** + 5 MED + 2 LOW" with the H-2 patch applied. The matrix therefore undercounts kilo's unique HIGHs on the very row that headlines "orthogonal coverage." (Note: copilot's MED-2 is genuinely copilot-unique per `11-1-…md` L228 — a *different* citation defect — so that cell is fine; the gap is the missing kilo H-2.)

**Concrete fix:** Add kilo H-2 to the Story 11.1 kilo-UNIQUE cell: "H-1 (`reasoning_output_tokens` data loss) + H-2 (inline ADR-A6 L384 renumbering-history citation drift)."

---

### MED-4 — "the 3-tier review chain ran at story-level for every story" overstates; only 2 tiers ran

**Sections:** Epic snapshot L14 + L30; Honest framing L210.

> L14: "First epic where the **3-tier cross-LLM review chain ran at story-level for every story.**"

Per `CLAUDE.md`, the ratified tiers are **Tier-1 = Claude CLI (`claude -p … --model opus`)**, **Tier-2 = Codex CLI**, **Tier-3 = kilo/minimax**. In Epic 11: Tier-2 (codex) was rate-limited every time (draft's own L30/L73), and the Tier-1 slot was filled by **GitHub Copilot CLI (claude-sonnet-4.6)** — a Tier-1 *alternative*, not the ratified Claude-CLI tool. So at most **2 of 3 tiers** ran (Tier-1-alternative copilot + Tier-3 kilo). "The 3-tier chain ran … for every story" while simultaneously stating Tier-2 never ran is contradictory. (L210's "Tier-1 + Tier-3 review" wording is the honest version.)

**Concrete fix:** Reword L14 to: "First epic where the cross-LLM review chain ran at story-level for every story — with **2 of 3 tiers active (Tier-1-alternative GitHub Copilot CLI + Tier-3 kilo); Tier-2 codex was rate-limited throughout.**" Keep the framing consistent wherever "3-tier chain ran" appears.

---

## LOW — wording, attribution, optional siblings

### LOW-1 — Action #5 "Done at `438b4a4`" mis-attributes a non-repo artifact to a repo commit

**Section:** What didn't #1 table, L99.

The promotion target is `~/.claude/projects/.../memory/MEMORY.md` + memory files — these live **outside the git repo**, so they are not literally part of commit `438b4a4`. The substance is verified ✅ (both norms in `MEMORY.md`; `feedback_cross_story_upstream_lesson_propagation.md` exists, mtime 2026-05-26 19:02). **Concrete fix:** reword to "Done during the Epic 10 retro (memory files dated 2026-05-26; both norms indexed in `MEMORY.md`)" rather than attributing it to the repo SHA.

### LOW-2 — "CONFIRMED + EXTENDED" norms (Norms #2–#5) state no next-test / falsification condition

**Section:** Norms ratified, L196–202. Per the prompt's MED checklist ("norm-ratification entries should state next-test condition"), only the CANDIDATE norm #6 states one (Epic 12 retro). The four CONFIRMED+EXTENDED norms give no re-test trigger. **Concrete fix:** add a one-line "next test:" to each (e.g., #2: "re-confirm at Epic 12; downgrade if kilo+copilot produce zero substantive findings across all Epic 12 stories").

### LOW-3 — Epic 12 Story 12.2 title is truncated

**Section:** Next-epic table, L168. Draft: "Judge Calibration Suite + Agreement Scoring." `epics.md` (Epic 12 block, ~L2103): "**Judge Calibration Suite + Agreement Scoring + Threshold Tuning**." **Concrete fix:** append "+ Threshold Tuning" for an exact title match (the "Distinct concerns" cell already covers threshold-tuning, so this is cosmetic).

---

## Items checked and found CORRECT (no action)

- Tests **1696 + 12 skipped** (L24) — matches live `pytest`; "+91" delta (1696−1605) correct; "+2 env-gated" matches skipped 10→12.
- Source files **96 → 99 (+3)** (L25) — `find`/`mypy` agree; the 3 named files exist.
- Catalog **72 → 78 (+6, C73–C78)** (L26) — `grep -c` → 78; all six rows present; per-story attribution (74/76+C77/78) matches records.
- `feedback_spec_vs_ratified_doc_precheck` **45/46/47** (L27) — matches `11-1`/`11-2`/`11-3` records (45th/46th/47th).
- Action-item follow-through table (L93–104) — all 9 Epic-10 actions map correctly; **2 ✅ (Actions 1 + 5) + 7 ❌**; Action #5 file existence verified.
- Retro-debt **5 ❌ (Epic 10 close) vs 7 ❌ (Epic 11 close)** (L107/L204) — Epic 10 retro's Epic-9 follow-through has exactly 5 ❌; Epic 11 table has exactly 7 ❌; "fails sunset criterion 2 AGAIN" is supported.
- `feedback_listener_hook_api_surface_empirical_check` **N=4** (L79/L202) — Listener v3 + Claude Agent SDK + OpenAI Agents SDK + Codex CLI JSONL; the `reasoning_output_tokens` catch fits the pattern.
- Story 11.2 + 11.3 matrix cells — spot-checked ≥2 per reviewer against the findings files; all match (copilot M-1/M-3 unique; kilo M-3 unique; H-1 + M-2 both for 11.2; copilot HIGH-2/MED-2/LOW-2 unique, kilo M-2 unique, H-1 + docstring-reuse both for 11.3; the "kilo M-1 32-vs-31 false positive" is real per `story-11-2-copilot-findings.md` L206–208).
- Codex rate-limit pattern (L30/L73) — all three `story-11-*-codex-stdout.txt` are 0 bytes; "retry 23:38, story-close ~20:40–21:30" consistent.

---

## Verdict

**4 HIGH + 4 MED + 3 LOW.** None of the HIGH findings undermine Epic 11's substance
(the chain did catch real bugs; the stories did ship). They are accounting/citation
defects that violate the project's own `feedback_honest_framing` numeric-bar standard:
- HIGH-1 (7-vs-3/4 commits) and HIGH-4 (33-vs-28 drifts) are arithmetic that doesn't reconcile against its own itemization.
- HIGH-2 (N=12 vs 9+3+3) and HIGH-3 (9/9 vs 5/5) are the load-bearing norm-graduation numbers — they should be exactly right before `feedback_cross_story_upstream_lesson_propagation` and `feedback_third_llm_family_fallback` are recorded as CONFIRMED at N=3 / N=12.

Apply HIGH-1 through HIGH-4 + MED-1/MED-2/MED-3/MED-4 inline as v2 before marking the retro `done`. The headline 1696/99/78 metrics are accurate; only their *derivations and norm-counts* drift.
