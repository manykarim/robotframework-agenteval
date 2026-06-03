# Story 14.1 — Codex-lens (Citation + Numeric Drift) Adversarial Review

Reviewer lens: CITATION + NUMERIC DRIFT. Every cited retro line number / Action #
re-derived from the actual source files. Date: 2026-06-03.

## Mandatory post-condition grep table

| # | Grep | Expect | Actual | Verdict |
|---|------|--------|--------|---------|
| 1 | `story-create-time retro\|Retro-debt mini-pass at story-create` CLAUDE.md | >=2 | 2 (L143 header, L197 closure-note) | PASS |
| 2 | `libdoc\|@keyword(name=` count template | >=4 | 15 | PASS |
| 3 | `wc -l` template | >=80 | 216 | PASS |
| 4 | `^\|\s*20` dated rows in 7-1 | >=3 | 4 | PASS |
| 5 | `DF-14.1-S[0-9]` in changed files | 0 | 0 (exit 1, no hits) | PASS |
| 6 | `uv run python -m robot.libdoc` template | >=1 | 1 (L86) | PASS |
| 7 | `@keyword(name=` template | >=1 | 4 (L30,L83,L107,L153) | PASS |
| 8 | `byte-for-byte` template | >=1 | 1 (L97) | PASS |
| 9 | `Story 12.3\|libdoc-display` template | >=1 | 2 (L98, L215) | PASS |
| 10 | `^\| 2026-06-03` rows in 7-1 | 2 | 2 (L262 v0.3.0, L263 v0.4.0) | PASS |

All 10 mechanical post-conditions PASS. Defects are in citation accuracy + a re-introduced
previously-corrected false claim, not in the mechanical post-conditions.

---

## HIGH findings

### HIGH-A — v0.3.0 Change Log row re-introduces a previously-CORRECTED false "4-reviewer" claim AND a wrong done-flip date
**File:** 7-1-...changelog.md L262 (v0.3.0 row); mirrored in spec L91 + Task 3 L148.
The v0.3.0 row states Story 7.1 reached `done` "after 4-reviewer cross-LLM code review on
**2026-05-25** (Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex)". Both halves are
false against the ratified Epic 7 retro (`epic-7-retro-2026-05-25.md`):
- **Reviewer count:** L39 records Story 7.1 as "Claude Blind Hunter + Codex CLI (**2 content
  reviewers**; ruff via Claude subagent does not count as content review)". L102 is an explicit
  patch: "*Patched 2026-05-25 per cross-LLM review HIGH-2 (Claude): original draft asserted
  '4-reviewer on 7.1' with sprint-status citation that doesn't exist.*" The 4-reviewer cycles were
  Stories 7.3 + 7.4, NOT 7.1. So v0.3.0 resurrects the exact claim Epic 7's own review already
  invalidated.
- **Date:** Epic 7 retro L13 + L17 put Story 7.1's `done` flip on **late 2026-05-20** (commits
  `fe82acf`+`22a59f1`+`11b974b`+`95e8bfb`); 2026-05-25 is the Epic 7 *retro/closure* date, not the
  7.1 done date.
This is the highest-severity finding: the backfill row's stated purpose is an honest retroactive
record, but it fabricates the review-count + done-date. Per `feedback_citation_drift_first_class`
and `feedback_honest_framing`.
**Fix:** rewrite v0.3.0 (L262) + spec L91 to "2 content reviewers (Claude Blind Hunter + Codex CLI;
ruff subagent not a content review) per Epic 7 retro L39; HIGH-1 null-name + HIGH-2 docstring
applied; done-flip late 2026-05-20 per Epic 7 retro L17, retroactively recorded 2026-06-03."

### HIGH-B — Epic 12 retro Action #2 / #3 line numbers are wrong (off by ~5)
**File:** CLAUDE.md L147-148; spec L52, L197; template L209.
Cited "Epic 12 retro **L156** Action #2" + "**L158** Action #3". Re-derived from
`epic-12-retro-2026-06-01.md`: L156 = `## Action items...` heading; L158 = table divider row;
**Action #2 is at L161**, **Action #3 at L162**. CLAUDE.md is auto-loaded into every session and
literally tells the operator "L156 Action #2" — opening L156 shows a heading.
**Fix:** "L161 Action #2" + "L162 Action #3" in CLAUDE.md L147-148, spec L52, spec L197, template
L209 (which also pins L158).

### HIGH-C — Spec L197 "Epic 12 retro L164 Action #8 (Story 7.1 Change Log carried)" is triple-wrong
**File:** spec L197.
Re-derived from `epic-12-retro-2026-06-01.md`: L164 = **Action #5** (DF-7.3-S1/C59); **Action #8**
(L167) = live integration tests (carried from Epic 11 #4); the Story 7.1 Change Log carryover is
**Action #10** at **L169**. The spec contradicts itself — its own L162 correctly says
"Epic 12 retro Action #10", but L197 says "L164 Action #8".
**Fix:** spec L197 → "Epic 12 retro L161 Action #2 + L162 Action #3 + L169 Action #10".

### HIGH-D — Epic 13 retro "L235-238 honest framing" for the 9% figure points at the wrong content
**File:** CLAUDE.md L150-151; spec L44.
Both cite the 9% follow-through figure as "Epic 13 retro **L235-238** honest framing". Re-derived
from `epic-13-retro-2026-06-03.md`: L235-238 = review-finding bullets MED-3/4/5/6 (norm N-counts +
command reproducibility), nothing about 9%. The 9% figure is at **L96** (`Score: 1 ✅ + 10 ❌ = 9.1%`),
**L195** (the actual "honest framing" wrap-up paragraph), and **L290**.
**Fix:** change "L235-238 honest framing" → "L96 / L195 honest framing" in CLAUDE.md L150-151 + spec L44.

### HIGH-E — Libdoc-bug empirical example is fabricated / misattributed (`Skill.Get Activation Pass At K`)
**File:** template L99-105; spec L17 (D-2).
The libdoc HIGH check cites "Epic 12 retro L116-125 (Story 12.3 libdoc-display bug)" and worked
example `Skill.Get Activation Pass At K` → `Skill.Get Activation PassAtK`. Re-derived from
`epic-12-retro-2026-06-01.md` L118-120: the ACTUAL shipped bug was `@keyword(name="Judge.Calibrate")`
(shipped by **Story 12.2**), rendered `'Judge. Calibrate'` (space after the dot). The keyword
`Skill.Get Activation Pass At K` was **never shipped** — Epic 13 retro L88 confirms it "was not
shipped". The template therefore presents an invented keyword + invented split-on-capital failure as
the documented evidence; a reviewer would hunt for the wrong failure mode.
**Fix:** use the real example — `@keyword(name="Judge.Calibrate")` → `Judge. Calibrate` (space
inserted on single-word post-dot name), per Epic 12 retro L118-120; attribute to "shipped Story 12.2,
surfaced post-Story-12.3-close".

---

## MED findings

### MED-1 — Epic 11 retro Action #8 line number wrong (cited L162, actual L158)
**File:** spec L176, L197, L255.
"Epic 11 retro **L162** Action #8" — re-derived from `epic-11-retro-2026-05-27.md`: Action #8
(Backfill Story 7.1 spec Change Log) is at **L158**; L162 is past the table. Action # itself correct.
**Fix:** "Epic 11 retro L158 Action #8" in spec L176, L197.

### MED-2 — Epic 13 retro "L177 Action #2 + L179 Action #3" off by two
**File:** spec L197; CLAUDE.md L148-149.
Re-derived from `epic-13-retro-2026-06-03.md`: L177 = table divider; **Action #2 = L179**,
**Action #3 = L180**. So "L177 Action #2" lands on the divider and "L179 Action #3" actually points
at Action #2.
**Fix:** "Epic 13 retro L179 Action #2 + L180 Action #3" in spec L197 + CLAUDE.md L148-149.

### MED-3 — D-2 spec line invents a "Story 12.3 retro" + repeats the 12.2-as-12.3 misattribution
**File:** spec L17.
D-2 writes "Story 12.3 retro (per Epic 12 retro L116-125)". No separate "Story 12.3 retro" exists;
L116-125 is a section of the Epic 12 retro that attributes the shipped keyword to Story 12.2.
Pairs with HIGH-E.
**Fix:** "Epic 12 retro §2 (L116-125): `Judge.Calibrate` shipped Story 12.2, libdoc-bug surfaced
post-Story-12.3-close".

---

## LOW findings

### LOW-1 — Template advertises "8 placeholder slots" but ships 9; all used (no dead slot)
**File:** spec L60, L146; template body.
Story says "8 placeholder slots". Template defines + uses 9: STORY_ID(10×), STORY_TITLE(3×),
STORY_SCOPE_BULLETS(2×), LIBDOC_TARGET_LIBRARY(2×), D_LIST_LESSONS_TABLE(2×), SOURCE_FILES_LIST(2×),
HIGH_CHECKLIST(2×), MED_CHECKLIST(2×), LOW_CHECKLIST(2×). No unused/dead slot (dead-slot check CLEAN);
only the count label is off (HIGH/MED/LOW counted as three slots).
**Fix:** say "9 placeholder slots" or describe HIGH/MED/LOW as one tri-part slot.

---

## Adversarial checks — explicit dispositions

- **#1 Citation drift:** FAILED — HIGH-A/B/C/D/E + MED-1/2/3. One re-introduced previously-corrected
  false claim (4-reviewer/date) + six wrong line-number / Action-# / example-fact misattributions.
- **#2 CLAUDE.md self-citation (L143/L197):** PASS. Header genuinely at L143; the closure-note phrase
  matched by the post-condition grep genuinely lands at L197. Self-line-refs accurate.
- **#3 Honest framing (dates):** PARTIAL. v0.3.0 + v0.4.0 are both dated 2026-06-03 (not backdated),
  v0.3.0 self-labels "Retroactive backfill" + "NOT a falsified 2026-05-21 date", v0.4.0 is a
  self-referential meta-entry — the DATING is honest. BUT the v0.3.0 BODY fabricates the historical
  4-reviewer count + the 2026-05-25 done-date (HIGH-A) — a transparency failure of a different kind.
  Author cells "Claude Opus 4.7" vs this Opus-4.8 review: no verifiably-false author claim (records
  implementing model, not reviewer), so no finding on that axis per instruction.
- **#4 Template completeness:** PASS on structure. Libdoc step is genuinely 4 concrete steps (run
  libdoc → grep+sed H-tags → grep+sed decorator names → byte-for-byte sort -u compare); not vague.
  All 9 slots used. (Step-4 EXAMPLE is wrong — HIGH-E — but the step STRUCTURE is sound.)
- **#5 Common-failure-mode:** PASS. CLAUDE.md L175-191 ships 3 concrete grep examples naming specific
  symbols/files (`@guarded_fanout`/`_max_cost_usd` in `src/AgentEval/mcp/library.py`;
  `^## Change Log`/`^\| 20` in `7-1-*.md`; `tests/integration/test_*_live.py`) AND states the intent
  "The grep is the audit; the action item text is only a pointer" (L191).
- **#6 Acceptance-flow split (D-4/D-5):** PASS (low ambiguity). Spec L26/L28 + ACs state AC-14.1.4 +
  AC-14.1.5 are Story-14.2-create/review-time checks; L28 names the canonical save path
  `_bmad-output/cross-llm-reviews/story-14-2-review-prompt.md`.
- **#7 Catalog-gate (DF-14.1-S*):** PASS. Zero `DF-14.1-S[0-9]` hits in all three changed content
  files (grep #5 exit 1). No scope violation.
- **#8 Sprint-status fidelity:** PASS. `epic-14: in-progress` (L161); `14-1-meta-...: review` (L162);
  `last_updated: 2026-06-03` with detailed note (L2). All three verified.

## Severity tally
HIGH: 5 (A,B,C,D,E) · MED: 3 (1,2,3) · LOW: 1
All HIGHs are citation/line-number/example-fact/re-introduced-false-claim drift — the codex-lens
class. Mechanical post-conditions (greps #1-10) and structural checks (#4 structure, #5, #6, #7, #8)
all PASS. The story's INSTALL is structurally sound; its CITATIONS are not.
