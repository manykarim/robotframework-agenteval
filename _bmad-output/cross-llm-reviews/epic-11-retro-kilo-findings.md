# Epic 11 Retrospective — kilo/minimax-M2.7 Adversarial Review Findings

**Reviewer:** kilo/minimax-M2.7 (Tier 3)
**Date:** 2026-05-27
**Draft reviewed:** `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md`
**Sources verified:** All source files cited in the prompt

---

## HIGH — citation drift, numeric drift, false invariant claim

### HIGH-1: `feedback_third_llm_family_fallback` N=12 arithmetic does not reconcile

**Section:** "What worked" #4 / "Norms ratified this retro" #2
**Claim:** N=9 (Epic 10 retro) + 3 (Epic 11 kilo) + 3 (Epic 11 copilot) = **N=12**.
**Re-derivation:** The claim in the retro says "9 + 3 + 3 = 12" but the footnote/explanation reads "3 more substantive kilo reviews + 3 more substantive copilot reviews." That would be 9 + 3 + 3 = **15**, not 12.

Per the Epic 10 retro (source: `epic-ten-retro-2026-05-26.md` L148): N=9 was established by counting **7 retroactive Epic 8/9 story reviews** (via `16ee936`) **+ Story 10.1 + Story 10.2** = 9 story-level substantive reviews. Epic 11 adds 3 kilo reviews (Stories 11.1, 11.2, 11.3) + 3 copilot reviews (Stories 11.1, 11.2, 11.3) = 6 more. 9 + 6 = **15**.

The retro itself says "N=12 (3 more story-level substantive reviews via kilo + 3 via copilot)" which implies 9-EXISTING + 3-NEW + 3-NEW = 15. The number "12" in the summary sentence contradicts the body arithmetic and the source file's own explanation.

**Concrete fix:** Either (a) correct the headline number to N=15 and amend the body explanation to clarify whether the counting is story-level or review-level — "9 (Epic 10 retro: 7 retroactive + Story 10.1 + Story 10.2) + 6 (Epic 11: 3 kilo + 3 copilot) = 15 story-level substantive reviews" — or (b) if "substantive only" means something different (e.g., discounting the 7 retroactive as lower-confidence), state the excluding logic explicitly.

---

### HIGH-2: `feedback_cross_story_upstream_lesson_propagation` N=3 UPSTREAM lesson counts require re-derivation against source

**Section:** "What worked" #2 / "Norms ratified this retro" #1
**Claim:** 10.2→11.1: 5/5 UPSTREAM; 11.1→11.2: 5/5 UPSTREAM; 11.2→11.3: 6/6 UPSTREAM.
**Re-derivation from source:**

| Transition | Claimed | Story record | Retro check |
|---|---|---|---|
| 10.2→11.1 | 9 UPSTREAM lessons | Story 11.1 spec AC-11.1.10 says "9 cross-story UPSTREAM lessons from Stories 4.2 + 10.1 + 10.2". Story 11.1 review says "9 UPSTREAM lessons verified applied." | Source says 9, not 5. The retro's "5/5" figure appears nowhere in the source records. |
| 11.1→11.2 | 5/5 claimed | Story 11.2 spec AC-11.2.10 says **12 UPSTREAM lessons** (D-1 through D-12) from Stories 4.2 + 10.1 + 10.2 + **11.1**. Story 11.2 Senior Developer Review confirms "12 cross-story UPSTREAM lessons applied. 5/5 UPSTREAM verified by BOTH reviewers." The per-reviewer verification verifies only the Story 11.1→11.2 slice of the 12, not the full 12. | 5/5 is the reviewer-verified slice, not the total count. The full count from source is 12. |
| 11.2→11.3 | 6/6 claimed | Story 11.3 spec AC-11.3.10 says **6 UPSTREAM lessons** from Stories 4.2 + 10.1 + 10.2 + 11.1 + 11.2. This matches the retro's 6/6. | Correct. |

**Concrete fix (3 separate corrections):**

1. Transition 10.2→11.1: The N=3 retro says "5/5 + 5/5 + 6/6". The source for 10.2→11.1 shows **9** UPSTREAM lessons (not 5). Change "5/5" to "9/9" for the first transition, or reconcile with the source definition difference.

2. Transition 11.1→11.2: The "5/5" in the retro refers to the reviewer-verified slice of Story 11.1 lessons only (the Story 11.2 review record explicitly says "5/5 Story 11.1 UPSTREAM lessons verified applied by BOTH reviewers"). The total from Story 11.2 source is **12** UPSTREAM lessons. Clarify: "12 total from all sources; 5/5 from Story 11.1 verified by both reviewers."

3. Transition 11.2→11.3: **6/6 matches source** — Story 11.3 spec AC-11.3.10 confirms 6 UPSTREAM lessons. This one is correct as-is.

---

### HIGH-3: `feedback_retro_debt_block_forward_progress` sunset criterion reference is self-contradictory

**Section:** "What didn't" #1 / Action item consequence
**Claim:** "Per Epic 10 retro's sunset criterion 2 ('Epic 11 close shows fewer ❌ action-items than Epic 10 close'), the norm fails sunset criterion 2 AGAIN."
**Self-contradiction in the Epic 10 retro:** The Epic 10 retro at its L123 says:
> "Epic 9 retro's own action-item follow-through (Epic 9 retro L127) reported `4 ✅ + 5 ❌` on the inherited Epic 8 actions. The L173 sunset criterion's `N=4 ❌` count is itself inconsistent with L127 — but EITHER reading (4 or 5) leaves Epic 10's outcome (5 ❌) at 'not fewer than' the Epic 9 baseline."

And at L129:
> "Next test condition: at Epic 11 retro, recount Epic 10 action-items at-close. If Epic 11 reduces the ❌ count by ≥2, promote... If Epic 11 ❌ count holds at 5 or grows, retire the norm."

The Epic 10 retro itself documented that its own action-item count was inconsistent. The Epic 11 retro's claim that "sunset criterion 2 fails AGAIN" is based on a baseline (Epic 10 close: 5 ❌) that Epic 10's own reviewers flagged as possibly wrong (Epic 9 close: either 4 or 5 ❌). The retro is applying the sunset criterion to a number that was flagged as uncertain in the SAME document.

**Concrete fix:** To be machine-verifiable, Epic 11 should have counted the Epic 10 action items at-close directly from the Epic 10 retro source. Instead of "5 ❌ → 7 ❌," the retro should say "Epic 9 close was either 4 or 5 ❌ (Epic 10 retro flagged its own baseline inconsistency). Epic 10 close per the Epic 10 retro's own reconciled count was N ❌." If the baseline is uncertain, it cannot be used as a machine-verifiable anchor for the "fails again" claim.

---

## MED — style, ordering, vague framing

### MED-1: Action items lack explicit next-test conditions

**Section:** "Action items for Epic 12 / next retrospective check" (table header)
**Retro precedent:** The Epic 10 retro action items included an explicit "binary completion check" column required for each row (per codex review HIGH-4 which patched this in). The Epic 11 retro action items have a "Success criterion" column, BUT Actions #1–#9 do NOT state a next-test condition for when the norm should be re-evaluated.

The retro itself mentions sunset criteria for `feedback_retro_debt_block_forward_progress` ("next test at Epic 12 retro") and for the upgraded norms (`feedback_cross_story_upstream_lesson_propagation` Action #5), but the other 7 action items do not analogously state when they would be considered resolved or retired.

**Concrete fix:** For each of the 9 action items, add a "Next test condition" field. For example:
- Action #3 (`@guarded_fanout` MCPLibrary): "Next test: Epic 12 retro counts the C20 carry-over status — if marked done OR formally Phase-2-only, this item passes."
- Action #7 (C64 recipe CI): "Next test: the new `test_all_recipes_dryrun.py` script runs in HEAD CI and returns ≥6 passed."

---

### MED-2: `feedback_carry_over_catalog_gate` consecutive story count claim (28) may double-count

**Section:** "Epic snapshot" / "Headline metrics"
**Claim:** "28 consecutive stories (24 → 11.1; 25-27 → today's docstring-refresh + rf-mcp E2E + Epic 10 retro; 28 → 11.2 + 11.3 via review-time enforcement)."
**Verification:** Story 11.1 source (AC-11.1.8) says "24th consecutive." Story 11.2 source (AC-11.2.8) says "27th consecutive." Story 11.3 source (AC-11.3.9) says "28th consecutive." The Epic 11 retro says the sequence is: 24 → 11.1; then "25-27 → today's docstring-refresh + rf-mcp E2E + Epic 10 retro" (which are not story numbers); then 28 → 11.2 + 11.3.

The "docstring-refresh + rf-mcp E2E + Epic 10 retro" are NOT BMad story-flow items — they bypass the story numbering. The retro's parenthetical "(24 → 11.1; 25-27 → today's docstring-refresh + rf-mcp E2E + Epic 10 retro; 28 → 11.2 + 11.3)" conflates non-story events into the consecutive story count, making it impossible to apply the same count to a future retro.

**Concrete fix:** State the 28 simply as the verified consecutive count per story records, without inserting non-story events into the sequence. If the non-story events added UPSTREAM lessons, say "Stories 11.2 + 11.3 applied 5 + 6 UPSTREAM lessons respectively, bringing the total to 28 consecutive uses."

---

### MED-3: Epic 10 action-item follow-through table: Action #5 verification step only confirms file exists, not norm promotion

**Section:** "What didn't" #1 — Action #5 row
**Claim:** "✅ Done at `438b4a4` (Epic 10 retro commit itself) — Verified: both norms appear in MEMORY.md as ratified entries."
**Actual verification:** I verified the memory files DO exist at the paths. However, confirming they "appear in MEMORY.md as ratified entries" requires checking `memory/MEMORY.md` (the index) — which was not listed in my verification scope but is mentioned in the claim. If the index file has the one-line entries, the claim passes. If it doesn't, `438b4a4` created the files but they may not be auto-loaded into sessions (breaking the operational trigger).

**Note:** Per the prompt I was asked to verify action #5 specifically against the file paths — both files exist. The MEMORY.md index entry is a separate concern that should ideally be verifiable via `grep "feedback_third_llm_family_fallback" ~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md`.

---

## LOW — wording, optional siblings

### LOW-1: "Orthogonal-coverage matrix" claims about copilot catching kilo's false positive use vague terms

**Section:** "What worked" #1 — Story 11.2 cell
**Claim:** "Plus copilot caught kilo's M-1 ('31 tests vs docstring 32') as FALSE POSITIVE — independent grep confirmed 32."
**Source:** The story-level reviews support this. The kilo findings file for Story 11.2 says "31 tests... docstring says 32" (M-1). The copilot findings file for Story 11.2 explicitly says "This reviewer's independent `grep -n "^def test_"` count returns **32**. Kilo's M-1 finding is a **false positive**."

**Vague framing issue:** "FALSE POSITIVE" in all caps in the retro cell carries a judgmental tone. The kilo M-1 was a reasonable enumeration error (kilo's own notes in `story-11-2-kilo-findings.md` show the 32nd test was listed at position 32 in the enumeration but then re-counted as 31 — an honest off-by-one in a complex enumeration). Framing it as "caught by independent re-count" rather than "false positive" would be more precise.

**No structural fix required** — this is informational. The underlying finding (copilot's independent grep confirmed 32) is correct.

---

### LOW-2: `feedback_listener_hook_api_surface_empirical_check` N=4 surface list is not re-derived against source

**Section:** "What worked" #5 / "Norms ratified this retro" #5
**Claim:** N=3 (Epic 10 retro) → N=4. 4 surfaces: Listener v3 + Claude Agent SDK + OpenAI Agents SDK + Codex CLI JSONL.
**Re-derivation:** Per Epic 10 retro source (L78): "feedback_listener_hook_api_surface_empirical_check is now validated across **3 distinct surfaces**: Listener v3 hook (Story 8a.2 origin), Claude Agent SDK (Story 10.1), OpenAI Agents SDK (Story 10.2)." Epic 11 adds Codex CLI JSONL (Story 11.1 kilo H-1 catch: `Usage` dataclass dropped `reasoning_output_tokens`). The 4 counts are consistent. No finding here — the claim is verifiable.

---

## Summary of Machine-Verifiable Claims

| Claim | Section | Verdict |
|---|---|---|
| 1696 pytest pass + 12 skipped | Epic snapshot | ✅ VERIFIED per Story 11.3 Change Log |
| 99 source files mypy clean | Epic snapshot | ✅ VERIFIED per Story 11.3 AC-11.3.8 |
| 78 catalog entries | Epic snapshot | ✅ VERIFIED via grep against phase-1-5-carry-overs.md (C73-C78 present) |
| 47 consecutive `feedback_spec_vs_ratified_doc_precheck` uses | Epic snapshot | ✅ VERIFIED: 44 Epic 10 + 3 Epic 11 = 47 |
| 28 consecutive `feedback_carry_over_catalog_gate` UPSTREAM | Epic snapshot | ✅ VERIFIED per 11.3 spec (28th) |
| 3 Epic 11 commits | Epic snapshot | ✅ `git log --oneline 229313e..577cf36` → 3 commits |
| Action #5 memory files exist | What didn't #1 | ✅ Both files verified at mandated paths |
| `feedback_cross_story_upstream_lesson_propagation` N=3 with 5/5+5/5+6/6 | What worked #2 + Norms #1 | ⚠️ **MISMATCHED** — 11.2→11.3 is 6/6 (correct); 11.1→11.2 is 12 total / 5 Story 11.1 slice; 10.2→11.1 is 9 not 5 |
| `feedback_third_llm_family_fallback` N=12 | What worked #4 + Norms #2 | ⚠️ **MATH ERROR** — 9+3+3=15, not 12 |
| 2 ✅ + 7 ❌ action-item follow-through from Epic 10 | What didn't #1 | ℹ️ Acceptable — source records verified by existence |
| `feedback_retro_debt_block_forward_progress` fails sunset criterion 2 AGAIN | What didn't #1 / Norms #6 | ⚠️ CRITICAL BASELINE UNCERTAINTY — Epic 10 retro flagged its own count as inconsistent (4 or 5 ❌ at Epic 9 close) |
| Action items have Success criterion column | Action items table | ✅ Present and specific for all 9 items |

---

## Findings Severity Summary

| # | Severity | Section | Issue |
|---|---|---|---|
| 1 | HIGH | Norms #2; What worked #4 | `feedback_third_llm_family_fallback` N=12 arithmetic error: 9+3+3=15 |
| 2 | HIGH | What worked #2; Norms #1 | UPSTREAM lesson counts mismatched vs source: 10.2→11.1 claims 5/5 but source says 9; 11.1→11.2 claims 5/5 but source says 12 total (5 is the Story 11.1 slice) |
| 3 | HIGH | What didn't #1; Norms #6 | `feedback_retro_debt_block_forward_progress` sunset criterion 2 comparison baseline (Epic 10 close) was flagged as uncertain in the Epic 10 retro itself |
| 4 | MED | Action items | No explicit next-test condition for 7/9 action items (beyond "Epic 12") |
| 5 | MED | Epic snapshot | `feedback_carry_over_catalog_gate` consecutive count parenthetical injects non-story events into a story-sequence, making replication impossible |
| 6 | MED | What didn't #1 | Action #5 MEMORY.md index entry verification not independently verifiable from source scope |
| 7 | LOW | What worked #1 | "FALSE POSITIVE" framing on kilo M-1 is accurate but tone-heavy; underlying fact is correct |
| 8 | LOW | Norms #5 | `feedback_listener_hook_api_surface_empirical_check` N=4 claim is correctly derived (no finding) |
