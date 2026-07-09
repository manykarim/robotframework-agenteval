# Story 14.1 — Reconciled Cross-LLM Review Findings

**Story:** `14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog`
**Reviewers:** codex (Tier 2) + claude-opus + claude-sonnet (Tier 1, 2 lenses)
**Reconciled:** 2026-06-03 by operator
**Method:** 3 reviewer finding-sets + per-finding adversarial verification verdicts, then operator re-derivation from ground-truth source files (every disputed anchor independently re-read before ratification).

---

## 1. Post-condition matrix (10 mandatory greps + key structural checks)

| # | Mandatory check | codex | opus | sonnet | Consensus |
|---|-----------------|-------|------|--------|-----------|
| 1 | `grep -nE "story-create-time retro\|Retro-debt mini-pass at story-create" CLAUDE.md` (≥2) | PASS (L143,L197) | PASS | PASS | **PASS** |
| 2 | `grep -cnE "libdoc\|@keyword(name=" template` (≥4) | PASS (15) | PASS (15) | PASS (15) | **PASS** |
| 3 | `wc -l template` (≥80) | PASS (216) | PASS (216) | PASS (216) | **PASS** |
| 4 | `grep -cE "^\|\s*20" 7-1 changelog` (≥3) | PASS (4) | PASS (4) | PASS (4) | **PASS** |
| 5 | `grep -rnE "DF-14.1-S[0-9]" changed files` (0) | PASS (0) | PASS (0) | PASS (0) | **PASS** |
| 6 | `grep -nE "uv run python -m robot.libdoc" template` (≥1) | PASS (L86) | PASS (L86) | PASS (L86) | **PASS** |
| 7 | `grep -nE "@keyword(name=" template` (≥1) | PASS (4) | PASS (4) | PASS (4) | **PASS** |
| 8 | `grep -nE "byte-for-byte" template` (≥1) | PASS (L97) | PASS (L97) | PASS (L97) | **PASS** |
| 9 | `grep -nE "Story 12.3\|libdoc-display" template` (≥1) | PASS (L98,L215)* | PASS* | PASS* | **PASS** (hit exists; *content mis-attributed — see HIGH-1*) |
| 10 | `grep -nE "^\| 2026-06-03" 7-1 changelog` (2: v0.3.0+v0.4.0) | PASS (L262,L263) | PASS | PASS | **PASS** |

Supplementary structural checks (consensus):
- sprint-status `epic-14: in-progress` + `14-1-*: review`: **PASS** (3/3).
- sprint-status `last_updated: 2026-06-03` (machine field L38): **PASS** — operator re-verified L38 = `2026-06-03`. (opus flagged MED-1 stale-field; **dropped on re-derivation, see §3.**)
- Libdoc step genuine 4-step grep+sed+diff procedure (not vague): **PASS** (3/3).
- Common-failure-mode ≥3 concrete greps + "grep is the audit" intent line: **PASS** (3/3).
- v0.3.0/v0.4.0 dated 2026-06-03, labeled retroactive/meta, NOT backdated to 2026-05-21: **PASS** (3/3) — date honesty intact. (Body content of v0.3.0 still false — see HIGH-2.)
- Zero src/ + tests/ changes (META story): **PASS** (3/3).
- All template placeholder slots used, no dead slot: **PASS** (3/3; label says 8, 9 named — LOW-4).

**Mechanical bar: 10/10 mandatory greps PASS. The install is structurally sound. All defects are evidence/citation drift in the codex/citation lens — the class the grep bars cannot catch.**

---

## 2. CONFIRMED findings (verdict real=true), deduped

### HIGH

**HIGH-1 — Fabricated libdoc worked-example baked into the canonical template (wrong story + wrong keyword + inverted mechanism).**
- Raised by: codex HIGH-E, opus HIGH-A, sonnet HIGH-A + HIGH-B (4-way agreement; all verdicts real=true, severity HIGH upheld by all three reviewers' verification).
- Files:line:
  - `_bmad/cross-llm-review-prompt-template.md` L98-105 (the worked example) + L215 ("Story 12.3 libdoc-display bug evidence").
  - `14-1-...changelog.md` L17 (D-2), L21, L22, L76, L179, L219.
- Defect (triple-wrong, re-derived from `epic-12-retro-2026-06-01.md` L116-124):
  1. **Wrong story** — bug shipped in **Story 12.2**, not 12.3 (retro L118; L138 explicitly clears 12.3 "didn't add a new keyword").
  2. **Wrong/fabricated keyword** — real keyword was `@keyword(name="Judge.Calibrate")` (retro L118). `Skill.Get Activation Pass At K` was NEVER shipped — it appears only as a *hypothetical* future C59 fix (Epic 12 Action #5 L164; Epic 13 Action #5 L182). `grep` of src/ for `PassAtK` = 0 hits.
  3. **Inverted mechanism** — real bug = a **space INSERTED** into a **single-word** post-dot name (`Judge.Calibrate` → `'Judge. Calibrate'`, retro L118). The fabricated example shows a **multi-word** name with spaces **collapsed** (`...Pass At K` → `...PassAtK`) — the opposite transformation. The ratified norm `feedback_libdoc_namespace_keyword_must_be_multiword` (retro L223) prescribes multi-word names as the FIX; the example presents the fix as the bug.
- Why HIGH: this is the load-bearing worked example in the canonical template (AC-14.1.2) that ALL future per-story review prompts derive from verbatim. It trains every future reviewer to probe for the inverse failure signature, defeating the smoke step's purpose, and violates `feedback_citation_drift_first_class` + `feedback_honest_framing`. (The 4-step grep PROCEDURE itself is mechanically sound and would catch the real bug — defect is the pedagogy/citation, not the mechanics.)
- Fix (apply to template L98-105 + L215 AND spec L17/L21-22/L76/L179/L219): replace with the real example — Story 12.2 `@keyword(name="Judge.Calibrate")` rendered by RF libdoc as `'Judge. Calibrate'` (space inserted into a single-word post-dot name), per Epic 12 retro L116-124. Relabel `Skill.Get Activation Pass At K → PassAtK` as a hypothetical future (Story 14.5 / C59) case, NOT the historical Epic 12 bug. Change all "Story 12.3 libdoc-display bug" → "Story 12.2 libdoc-display bug (Judge.Calibrate)".

**HIGH-2 — v0.3.0 backfill row re-introduces a previously-CORRECTED false claim (4-reviewer / 2026-05-25 / fabricated citation).**
- Raised by: codex HIGH-A (real=true, HIGH upheld). Not raised by opus/sonnet (their honest-framing checks validated the *dates* but not the *body*).
- File:line: `7-1-skill-get-activation-decision-keyword.md` L262 (v0.3.0 row). Secondary mirror imprecise (spec L91 is a test-name bullet — ignore that anchor).
- Defect (re-derived from `epic-7-retro-2026-05-25.md`): the row states Story 7.1 was flipped to done "after 4-reviewer cross-LLM code review on 2026-05-25 (Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex per Story 7.1 review record at `_bmad-output/cross-llm-reviews/`)". Three falsehoods: (1) **reviewer count** — Epic 7 retro L39 records exactly "2 content reviewers (Claude Blind Hunter + Codex CLI; ruff subagent ≠ content review)"; the 4-reviewer cycles were Stories 7.3+7.4; retro L102 is an EXPLICIT prior patch correcting this very "4-reviewer on 7.1" claim as unverifiable. (2) **date** — done-flip was late 2026-05-20 (retro L17; commits dated 2026-05-21); 2026-05-25 is the retro/closure date. (3) **citation** — no Story 7.1 review record exists under `_bmad-output/cross-llm-reviews/` (earliest files are Story 11.x / Epic 10 retro).
- Why HIGH: a falsehood living inside a "retroactive honest-framing" entry that explicitly invokes `feedback_honest_framing` falsifies the audit trail in the very record meant to repair it. Most damaging honest-framing failure class.
- Fix (rewrite L262 body): "Story 7.1 flipped `review → done` late 2026-05-20 (commits fe82acf/22a59f1/11b974b/95e8bfb, dated 2026-05-21) after 2 content reviewers (Claude Blind Hunter + Codex CLI; ruff subagent not a content review) per Epic 7 retro L39; HIGH-1 null-name + HIGH-2 docstring findings applied to v0.2.0 inline. Retroactively recorded 2026-06-03 per `feedback_honest_framing` — NOT a falsified historical date." Drop the fabricated `_bmad-output/cross-llm-reviews/` Story-7.1-record citation.

### MED

**MED-1 — Epic 12 retro Action #2/#3 line anchors wrong (off by ~4-5) in spec + template.**
- Raised by: codex HIGH-B, opus HIGH-B, sonnet MED-1 (all real=true). Severity reconciled to **MED** (opus + sonnet verifiers downgraded HIGH→MED/LOW: anchors land on the section header / table-header row, not a *different* action; Action # labels + quoted criteria are correct everywhere). Treated MED for ratification.
- Ground truth (`epic-12-retro-2026-06-01.md`): L156 = section heading; L158 = table-header row; L161 = Action #2; L162 = Action #3.
- **NOTE — CLAUDE.md already correct:** operator re-read CLAUDE.md L148 = "L161 Action #2" (already patched). The defect remains ONLY in:
  - `template` L12 ("L158") + L209 ("L158") → should be **L162** (Action #3).
  - spec L52 ("L156 Action #2") → **L161**; spec L197 ("L156 Action #2 + L158 Action #3") → **L161 + L162**.
- Fix: template L12/L209 `L158` → `L162`; spec L52 `L156` → `L161`; spec L197 `L156 Action #2 + L158 Action #3` → `L161 Action #2 + L162 Action #3`.

**MED-2 — Epic 13 retro Action #2/#3 line anchors wrong (off by ~1-2) in spec + template.**
- Raised by: codex MED-2, opus HIGH-C, sonnet MED-2 (all real=true; reconciled **MED**).
- Ground truth (`epic-13-retro-2026-06-03.md`): L177 = table separator; L179 = Action #2; L180 = Action #3; L182 = Action #5 (does NOT name the template path).
- **NOTE — CLAUDE.md already correct:** L149 = "L179 Action #2" (already patched). Defect remains in:
  - spec D-1 L15 ("Action #3 (L182) names the same path verbatim") → path is named at **L180** (Action #3), not L182.
  - spec L22 ("Story 12.3 retro precedent + Epic 13 retro Action #3") — see MED-4.
  - template L14 ("L179") + L211 ("L179") for Action #3 → should be **L180**.
  - spec L197 ("Epic 13 retro L177 Action #2 + L179 Action #3") → **L179 Action #2 + L180 Action #3**.
- Fix: spec L15 `L182` → `L180`; template L14/L211 `L179` → `L180`; spec L197 `L177 Action #2 + L179 Action #3` → `L179 Action #2 + L180 Action #3`.

**MED-3 — "9% follow-through" cited at Epic 13 retro L235-238 in the SPEC; actual is L195 (honest framing) / L96 (derivation).**
- Raised by: codex HIGH-D, opus HIGH-D, sonnet MED-3 (all real=true; reconciled **MED** — wrong-line-pointer to a correct fact in the same file).
- Ground truth: L235-238 = kilo/codex MED reviewer-finding bullets; the 9% honest-framing prose is at **L193-195** ("## Honest framing"), the 9.1% derivation at **L96** + L290.
- **NOTE — CLAUDE.md already correct:** L151 = "Epic 13 retro L193 honest framing" (already patched). Defect remains ONLY in spec L44 ("per Epic 13 retro L235-238 honest framing").
- Fix: spec L44 `L235-238` → `L195` (honest framing) `/ L96` (numeric derivation).

**MED-4 — "Story 12.3 retro" invented; Story-12.2-as-12.3 mis-attribution in spec prose.**
- Raised by: codex MED-3, opus MED-2, sonnet HIGH-B (all real=true; reconciled **MED** — folds into HIGH-1's story-number correction but tracked separately as it appears in spec narrative prose at L17/L22/L219, not just the worked example).
- Defect: no standalone "Story 12.3 retro" exists — L116-125 is section 2 OF the Epic 12 retro, documenting Story 12.2's `Judge.Calibrate` bug.
- Fix (folded into HIGH-1 application): spec L17/L22/L219 + template L98/L215 "Story 12.3 retro" / "Story 12.3 libdoc-display bug" → "Epic 12 retro section 2 (L116-124): Judge.Calibrate shipped Story 12.2, surfaced post-Story-12.3-close".

### LOW

**LOW-1 — Epic 11 retro Action #8 cited at L162 (blank line); actual L158.**
- Raised by: codex MED-1, opus MED-3, sonnet (postcondition). Reconciled **LOW** (opus verifier: symbolic "Action #8" + verbatim title intact; only line off by 4 into a blank line). Ground truth: `epic-11-retro-2026-05-27.md` L158 = Action #8. Appears at spec L176 + L197 (NOT L255 — that row carries no line number).
- Fix: spec L176 + L197 `Epic 11 retro L162 Action #8` → `Epic 11 retro L158 Action #8`.

**LOW-2 — Spec L197 third clause "Epic 12 retro L164 Action #8 (Story 7.1 Change Log carried)" is triple-wrong.**
- Raised by: codex HIGH-C (real=true; reconciled **LOW/MED** — codex verifier downgraded HIGH→MED; opus did not flag; adjacent spec L162 already carries the correct "Action #10" mapping, so artifact self-corrects). Tracked LOW.
- Ground truth: Story 7.1 Change Log carryover is **Action #10 at L169**; L164 = Action #5 (C59); Action #8 (L167) = live integration tests.
- Fix (folded into MED-1 spec L197 rewrite): third clause → `L169 Action #10 (Story 7.1 Change Log carried)`.

**LOW-3 — CLAUDE.md closure-note self-anchor "L197" imprecise (block starts L193).**
- Raised by: opus LOW-1, sonnet MED-5 (reconciled **LOW** — L197 IS the literal grep-hit line, so post-condition #1 is satisfied; imprecise only as a block-location label). Spec L144/L218/L243.
- Fix (optional): describe as "L193-198 (### Closure note block)" or leave — L197 is a valid line in the block.

**LOW-4 — Spec advertises "8 placeholder slots" but template defines/uses 9 (all used, no dead slot).**
- Raised by: codex LOW-1. Spec L60/L146/L219.
- Fix (optional): say "9 placeholder slots" or describe HIGH/MED/LOW as one tri-part checklist slot.

**LOW-5 — `story-14-1-review-prompt.md` L82 cites Epic 13 retro L116-125 for libdoc evidence; actual libdoc content is Epic 13 L110 (L116-125 is the Codex SDK-probe section).**
- Raised by: sonnet MED-4 (real=true; reconciled **LOW** — ephemeral per-story audit prompt, not a shipped canonical file; correct Epic 12 L116-125 citation is co-located two lines earlier).
- Fix (optional): L82 Epic 13 anchor `L116-125` → `L110`, or drop (redundant with Epic 12 L116-125 already cited).

---

## 3. REFUTED / INVALID / already-resolved findings (dropped)

- **opus MED-1 (sprint-status `last_updated` field stale at 2026-06-01)** — DROPPED. Operator re-read `sprint-status.yaml` L38 = `last_updated: 2026-06-03`. The machine field IS bumped; AC-14.1.8 is met. (opus read a stale snapshot.)
- **sonnet LOW-1 / opus LOW-2 (model attribution "Opus 4.7" vs review workflow 4.8)** — DROPPED. Both verdicts: dev self-reported model, not falsifiable from artifacts; no false date/author claim. No action.
- **Multiple reviewers' citation findings as they apply to CLAUDE.md (HIGH-B/C/D)** — PARTIALLY DROPPED for CLAUDE.md scope only: operator re-read CLAUDE.md L148/L149/L151 and confirmed they already carry the corrected anchors (L161, L179, L193). The CONFIRMED defects (MED-1/2/3) survive only for the SPEC + TEMPLATE files, which still carry the wrong anchors. (Reviewer snapshots predated the CLAUDE.md patch or conflated files.)

---

## 4. Verdict + v2 patch list

**Bar (per CLAUDE.md cross-LLM chain): ratify v2 patches inline if ≥1 HIGH OR ≥2 MED confirmed.**

**Confirmed: 2 HIGH + 4 MED + 5 LOW. Bar is met (and exceeded) on both clauses → RATIFY v2 patches inline. Story 14.1 stays at `review` until v2 patches are applied, then clears to `done`.**

The install is structurally sound (10/10 mandatory greps PASS); defects are concentrated in evidence/citation fidelity. The 2 HIGH (fabricated libdoc example in the canonical template; false v0.3.0 backfill body) propagate to all future derived prompts / falsify an honest-framing record and MUST be fixed before `done`.

### v2 patches to apply (in priority order)

1. **[HIGH-1]** Template `_bmad/cross-llm-review-prompt-template.md` L98-105 + L215 AND spec L17/L21-22/L76/L179/L219: replace fabricated `Skill.Get Activation Pass At K → PassAtK` example with real `@keyword(name="Judge.Calibrate") → 'Judge. Calibrate'` (single-word space-insertion, Story 12.2, Epic 12 retro L116-124); relabel the PassAtK example as hypothetical future (Story 14.5/C59); "Story 12.3 libdoc-display bug" → "Story 12.2 ...".
2. **[HIGH-2]** 7-1 changelog L262 (v0.3.0 row): rewrite body — 2 content reviewers (not 4), done-flip late 2026-05-20 (not 2026-05-25), drop fabricated cross-LLM-reviews/ Story-7.1 citation; keep 2026-06-03 retroactive-backfill date label.
3. **[MED-1]** template L12/L209 `L158`→`L162`; spec L52 `L156`→`L161`; spec L197 `L156 Action #2 + L158 Action #3`→`L161 Action #2 + L162 Action #3`.
4. **[MED-2]** spec L15 `L182`→`L180`; template L14/L211 `L179`→`L180`; spec L197 `L177 Action #2 + L179 Action #3`→`L179 Action #2 + L180 Action #3`.
5. **[MED-3]** spec L44 `Epic 13 retro L235-238 honest framing`→`Epic 13 retro L195 honest framing / L96 derivation`.
6. **[MED-4 / LOW-2]** spec L197 third clause `L164 Action #8`→`L169 Action #10`; spec prose "Story 12.3 retro" → "Epic 12 retro section 2 (L116-124)".
7. **[LOW-1]** spec L176 + L197 `Epic 11 retro L162 Action #8`→`L158 Action #8`.
8. **[LOW-3/4/5]** optional polish: closure-note anchor → "L193-198"; "8 placeholder slots"→"9"; review-prompt L82 Epic 13 anchor `L116-125`→`L110`.

After patches 1-7 land (v2), flip `14-1-meta-...` `review`→`done`. CLAUDE.md citations require NO change (already correct).
