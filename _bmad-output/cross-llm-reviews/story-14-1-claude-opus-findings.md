# Story 14.1 META — Claude Opus Adversarial Review Findings

Lens: SEMANTIC-SHAPE + COMPLETENESS (opus). Independent review; all greps re-run.

## Post-condition grep table (re-run, actual output)

| # | Check | Expect | Actual | PASS/FAIL |
|---|-------|--------|--------|-----------|
| 1 | `grep -nE "story-create-time retro\|Retro-debt mini-pass at story-create" CLAUDE.md` | ≥2 | 2 (L143 header, L197 closure prose) | PASS |
| 2 | `grep -cnE "libdoc\|@keyword\(name=" template` | ≥4 | 15 | PASS |
| 3 | `wc -l template` | ≥80 | 216 | PASS |
| 4 | `grep -cE "^\|\s*20" 7-1-*.md` | ≥3 | 4 | PASS |
| 5 | `grep -rnE "DF-14\.1-S[0-9]" <3 files>` | 0 | 0 (exit 1) | PASS |
| 6 | `grep -nE "uv run python -m robot.libdoc" template` | ≥1 | 1 (L86) | PASS |
| 7 | `grep -nE "@keyword\(name=" template` | ≥1 | 4 (L30,83,107,153) | PASS |
| 8 | `grep -nE "byte-for-byte" template` | ≥1 | 1 (L97) | PASS |
| 9 | `grep -nE "Story 12\.3\|libdoc-display" template` | ≥1 | 2 (L98,L215) | PASS |
| 10 | `grep -nE "^\| 2026-06-03" 7-1-*.md` | 2 | 2 (L262 v0.3.0, L263 v0.4.0) | PASS |

All 10 mandatory post-conditions PASS. Defects are in citation accuracy + honest framing + the sprint-status field, not the post-condition surface.

---

## HIGH

### HIGH-A — Fabricated/misattributed Story 12.3 libdoc-bug evidence in spec (citation + honest-framing drift)
**File:** spec L17 + L179 (also L21, L22, L219).
**Claim:** Spec D-2 (L17) states as documented fact: "Story 12.3 retro (per Epic 12 retro L116-125) documents the libdoc keyword-name display bug: `Skill.Get Activation Pass At K` shipped, but ... it displayed as `Skill.Get Activation PassAtK`." L179: "Story 12.3 shipped `Skill.Get Activation Pass At K` keyword ... rendered as `Skill.Get Activation PassAtK`."
**Evidence (re-derived):** Epic 12 retro L116-125 attributes the bug to **Story 12.2**, keyword **`@keyword(name="Judge.Calibrate")`** (single-word post-dot), rendered as **`Judge. Calibrate`** (space inserted). The string `Skill.Get Activation Pass At K`/`PassAtK` appears NOWHERE in the Epic 12 retro — a hypothetical presented as historical fact. Triple drift: wrong story (12.2 not 12.3), wrong keyword, wrong failure mode (space-on-single-word vs capital-split-on-multi-word). Template L102-104 is correctly hedged ("e.g."), so only the spec mis-states it as fact.
**Fix:** Rewrite spec D-2 L17 + L179: "Epic 12 retro L116-125 documents the libdoc bug for **Story 12.2's** `@keyword(name=\"Judge.Calibrate\")`, rendered as `Judge. Calibrate` (space inserted on single-word post-dot). The `Skill.Get Activation Pass At K → PassAtK` example is a *hypothetical* future case (Story 14.5's possible keyword), not the historical Story 12.2 bug."

### HIGH-B — Epic 12 retro Action #2 / #3 line numbers point to header/separator
**File:** CLAUDE.md L148 ("Epic 12 retro L156 Action #2"); template L12 + L209 ("Epic 12 retro Action #3 ... L158"); spec L52, L160, L197.
**Evidence:** Epic 12 retro: L156 = section header `## Action items for Epic 13 / next retrospective check`; L158 = table-header row `| # | Action | Owner | Class | Success Criteria |`; L160 = Action #1; **L161 = Action #2** (mini-pass); **L162 = Action #3** (libdoc smoke). "L156 Action #2" is off by 5 (points to a header); "L158 Action #3" points to the table header row.
**Fix:** CLAUDE.md L148 + spec: `L156 Action #2` → `L161 Action #2`. Template L12 + L209 + spec: `L158` → `L162` for Action #3.

### HIGH-C — Epic 13 retro Action #2 / #3 line numbers all wrong
**File:** CLAUDE.md L149 ("Epic 13 retro L177 Action #2"); spec D-1 L15 ("Epic 13 retro Action #3 (L182)"); template L13-14 + L211 ("Epic 13 retro Action #3 ... L179"); spec L52, L163, L197.
**Evidence:** Epic 13 retro: L177 = table-header row; **L179 = Action #2** (CLAUDE.md mini-pass); **L180 = Action #3** (libdoc smoke + names `_bmad/cross-llm-review-prompt-template.md`); **L182 = Action #5** (close C59). So "L177 Action #2" points to the table header (→L179); template "Action #3 (L179)" points to Action #2 (→L180); spec D-1 "Action #3 (L182)" naming the template path points to Action #5/C59 (→L180).
**Fix:** CLAUDE.md L149 + spec: `L177 Action #2` → `L179 Action #2`. Template L13-14 + L211 + spec L163: `Action #3 ... L179` → `L180`. Spec D-1 L15: `Action #3 (L182)` → `(L180)`.

### HIGH-D — "Epic 13 retro L235-238 = 9% honest framing" points to the kilo findings list
**File:** CLAUDE.md L150-151; spec L44, L178.
**Evidence:** Epic 13 retro L235-238 = kilo reviewer findings MED-3..MED-6 (no "9%", no honest-framing prose). The 9% / "worst consecutive-epic ratio" honest framing is at **L193-195** (`## Honest framing`); the 1/11 = 9.1% derivation is at **L96** + L290.
**Fix:** CLAUDE.md L151 + spec L44: `Epic 13 retro L235-238 honest framing` → `Epic 13 retro L193-195 honest framing` (or `L96` for the 9.1% derivation).

---

## MED

### MED-1 — sprint-status.yaml `last_updated` field NOT bumped to 2026-06-03 (AC-14.1.8 unmet on its own terms)
**File:** sprint-status.yaml L38.
**Evidence:** AC-14.1.8 + AC-14.1.9 + Task 6 + Completion-Notes all assert `last_updated: 2026-06-03`. The actual YAML field at L38 reads `last_updated: 2026-06-01` (unchanged). Only the top comment block (L2) carries the 2026-06-03 narrative. epic-14 (L161 `in-progress`) + 14-1 (L162 `review`) ARE correct.
**Fix:** Set L38 → `last_updated: 2026-06-03`. The story's own AC-14.1.8 post-condition is not satisfied until this field is bumped.

### MED-2 — "Story 12.3 libdoc-display bug" mis-attribution propagated into the canonical template
**File:** template L98 + L215; spec L21-22, L179.
**Evidence:** Same root cause as HIGH-A: Epic 12 retro L118 attributes the bug to Story **12.2** (`Judge.Calibrate`). The template hedges the keyword example but still labels the citation "Story 12.3 libdoc-display bug". Since this template is the canonical source future prompts derive from, the wrong story number propagates. MED (not HIGH) because the keyword example is framed illustratively.
**Fix:** template L98 + L215: `Story 12.3 libdoc-display bug` → `Story 12.2 libdoc-display bug (Judge.Calibrate)`. The L116-125 range citation itself is correct.

### MED-3 — Epic 11 retro Action #8 cited at L162 (a blank line); actual is L158
**File:** spec L176 + L197 ("Epic 11 retro L162 Action #8").
**Evidence:** Epic 11 retro L158 = Action #8 "Backfill Story 7.1 spec Change Log". L162 = blank line (between `---` L161 and `## Next epic preparation` L163).
**Fix:** spec L176 + L197: `Epic 11 retro L162 Action #8` → `Epic 11 retro L158 Action #8`.

---

## LOW

### LOW-1 — CLAUDE.md closure-note self-citation "L197" is the trailing prose line, not the note start
**File:** spec L144, L218, L243, L255.
**Evidence:** `### Closure note` header = CLAUDE.md L193; prose "This section installed by Story 14.1" starts L195; L197 is the 3rd prose line. L197 IS the literal grep-match line (the phrase "story-create-time retro-debt" lives there) so it satisfies the post-condition, but it is imprecise as a "closure-note location" anchor.
**Fix:** Optional — "closure-note L197" → "closure-note L193-198", or leave as-is since L197 is the literal grep-hit line.

### LOW-2 — Dev Agent model "claude-opus-4-7[1m]" vs Change Log "Claude Opus 4.7" — internally consistent, no false claim
**File:** spec L206 + Change Log L254-255 + Story 7.1 L262-263.
**Evidence:** Dev Agent Record `claude-opus-4-7[1m]` and Change Log `Claude Opus 4.7 (1M context)` are mutually consistent. The review workflow runs Opus 4.8 but the spec makes no claim about the reviewer model. No verifiably-false author/date claim. Dates all 2026-06-03; v0.3.0 explicitly "Retroactive backfill", v0.4.0 "Self-referential meta-entry"; honest-framing check PASSES.
**Fix:** None required.

---

## Checks that PASS (no finding)

- **#4 Template completeness:** All 9 named slots used inside the body fence (L44-195): {{STORY_ID}}×8, {{STORY_TITLE}}×2, others ×1. Zero dead slots. Libdoc step is genuinely 4 concrete steps (run L86 → extract H-tags L88-91 → extract decorator names L92-96 → byte-for-byte compare L97), NOT vague "check libdoc renders." PASS.
- **#5 Common-failure-mode:** CLAUDE.md L181-189 ships 3 concrete grep examples each naming a specific symbol/file (`@guarded_fanout|_max_cost_usd`, `## Change Log|^\| 20`, `test_*_live.py`), and L191 states the intent verbatim: "The grep is the audit; the action item text is only a pointer." PASS.
- **#6 Acceptance-flow split:** Spec D-4 (L26), D-5 (L28), AC-14.1.4 (L97-106), AC-14.1.5 (L108-114) unambiguously place AC-14.1.4/5 verification at Story-14.2-time, with the 14.2 prompt saved to `_bmad-output/cross-llm-reviews/story-14-2-review-prompt.md`. PASS.
- **#7 Catalog-gate:** Zero `DF-14.1-S*` hits across the 3 changed content files. PASS.
- **Zero src/ + tests/ changes:** Confirmed via `git status --porcelain`. PASS.

---

## Summary

10/10 mandatory post-conditions PASS. The deliverable's *structure* is sound: all 8/9 template slots used, the libdoc step is a real 4-step grep+diff procedure, the 3 concrete failure-mode greps + "the grep is the audit" intent are present, the acceptance-flow split is unambiguous, the backfill dates are honest (v0.3.0 labeled retroactive, v0.4.0 self-referential, no 2026-05-21 backdating), and there are zero DF-14.1-S* scope violations. Defects concentrate in **citation accuracy**: 4 HIGH (HIGH-A fabricated Story-12.2-vs-12.3 keyword example stated as fact; HIGH-B Epic 12 L156/L158; HIGH-C Epic 13 L177/L179/L182; HIGH-D Epic 13 L235-238 vs the real L193 honest-framing) + the same mis-attribution leaking into the canonical template (MED-2) + Epic 11 L162-vs-L158 (MED-3). One process defect: the machine-readable `last_updated` field was never bumped (MED-1), so AC-14.1.8 is unmet on its own terms. Because the template is the canonical source future prompts derive from, the wrong story-number + line anchors will propagate unless corrected now.
