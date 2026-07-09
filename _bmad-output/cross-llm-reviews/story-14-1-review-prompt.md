# Story 14-1 — META: Install Retro-Debt Mini-Pass + Libdoc Review-Smoke + Story 7.1 Change Log Backfill — Cross-LLM Adversarial Review Prompt

## Context

Story 14.1 ships the **META install** for 6 retro action items accumulated
across 4 epics: Epic 11 retro Action #8 (Story 7.1 Change Log backfill) +
Epic 12 retro Actions #2 + #3 + #10 + Epic 13 retro Actions #2 + #3. Per
CLAUDE.md ratified 3-tier cross-LLM review chain (Epic 10 retro 2026-05-26):

- **Tier 1a: Claude CLI sonnet** (`claude -p --dangerously-skip-permissions --model sonnet "<prompt>"`)
- **Tier 1b: Claude CLI opus** (`claude -p --dangerously-skip-permissions --model opus "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- Tier 3 (fallback): kilo/minimax-M2.7 — reserved.

Each reviewer runs INDEPENDENTLY. Coverage is multiplicative, not redundant.

**Self-referential meta-note**: this prompt is the FIRST use of the canonical
template introduced by AC-14.1.2 (`_bmad/cross-llm-review-prompt-template.md`).
Story 14.1 installs the template AND exercises it on itself in the same
session — by design, per the install-then-exercise pattern.

## What Story 14.1 ships

- **NEW file:** `_bmad/cross-llm-review-prompt-template.md` (216 lines) —
  canonical review-prompt template with 8 placeholder slots
  (`{{STORY_ID}}`, `{{STORY_TITLE}}`, `{{STORY_SCOPE_BULLETS}}`,
  `{{LIBDOC_TARGET_LIBRARY}}`, `{{D_LIST_LESSONS_TABLE}}`,
  `{{SOURCE_FILES_LIST}}`, `{{HIGH_CHECKLIST}}`, `{{MED_CHECKLIST}}`,
  `{{LOW_CHECKLIST}}`). Libdoc smoke step (4-step grep procedure) is the
  lead HIGH check with Epic 12 retro L116-125 Story 12.3
  libdoc-display-bug evidence cited inline.
- **Modified:** `CLAUDE.md` — +54 lines: new `## Retro-debt mini-pass at
  story-create time` top-level section between `## Project quick-facts`
  and `## Hard rules for autonomous loops` (header L143; closure-note L197).
  4-part structure: motivation → 5-step procedure → common-failure-mode
  anti-pattern with 3 concrete grep examples → closure note.
- **Modified:** `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`
  — Change Log table extended from 2 to 4 dated rows: v0.3.0 retroactive
  done-flip record + v0.4.0 self-referential meta-entry, both dated
  2026-06-03 honestly (NOT falsified to 2026-05-21 historical dates) per
  `feedback_honest_framing`.
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml`
  — `epic-14: backlog → in-progress`; `14-1-*: backlog → review`;
  `last_updated: 2026-06-03` with extended note.

The full change bundle (diff + new files) is at `/tmp/story-14-1-fullchanges.txt`
(554 lines). The story spec itself is at
`_bmad-output/implementation-artifacts/14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog.md`.

**Zero `src/` modifications. Zero `tests/` modifications. META story.**

## What's load-bearing — read the story spec first

The story spec documents 5 drift-check D-N entries + 2 META-layer
cross-story upstream lessons L-M1 + L-M2 folded into the AC text. Verify
whether each is correctly applied:

| D-/L-# | Claim | What to verify |
| --- | --- | --- |
| D-1 | Canonical location pinned to `_bmad/cross-llm-review-prompt-template.md` (NOT "or similar") | New file exists at exactly that path; no diverging alternatives shipped. |
| D-2 | Libdoc smoke step is a 4-step grep procedure with Epic 12 retro L116-125 evidence | Template's HIGH section names the 4 steps + cites Story 12.3 libdoc-display-bug evidence; not vague "check libdoc renders" wording. |
| D-3 | Story 7.1 Change Log backfilled date-honestly (≥3 entries; new entries dated 2026-06-03 NOT 2026-05-21) | `grep -cE "^\|\s*20" _bmad-output/implementation-artifacts/7-1-*.md` returns ≥3; v0.3.0 + v0.4.0 dated 2026-06-03 NOT historically falsified. |
| D-4 | AC-14.1.4 acceptance-flow split: install at Story 14.1; exercise-evidence at Story 14.2-create-time | Spec clearly says AC-14.1.4 is verified at Story 14.2-create-time, not Story 14.1-dev-time. |
| D-5 | Story 14.2 review prompt save-path matches `story-X-Y-review-prompt.md` canonical pattern | Spec calls out `_bmad-output/cross-llm-reviews/story-14-2-review-prompt.md` matching `story-11-{1,2,3}-review-prompt.md` precedent. |
| L-M1 | CLAUDE.md mini-pass section requires grep-the-named-symbol before deciding action item N/A | 3 concrete grep examples in the "Common failure mode" subsection. |
| L-M2 | Libdoc smoke step is unambiguous about WHICH library + what counts as a pass | `{{LIBDOC_TARGET_LIBRARY}}` slot named; rendered H-tags MUST match decorator names byte-for-byte (no vague wording). |

## Source files to verify against

- `_bmad-output/implementation-artifacts/14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog.md`
  (story spec — primary contract)
- `CLAUDE.md` (project root — modified with mini-pass section)
- `_bmad/cross-llm-review-prompt-template.md` (NEW canonical template)
- `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`
  (Story 7.1 spec — Change Log backfill target)
- `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md` L162
  (Action #8: Story 7.1 Change Log backfill source)
- `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L156-164
  (Actions #2, #3, #8, #10: retro-debt mini-pass + libdoc smoke + Story 7.1 carryovers)
- `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L174-220
  (Actions #2, #3: install Epic 12 #2 + #3 NOW, not deferred)
- `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L116-125
  (Story 12.3 libdoc-display-bug evidence — motivation for the libdoc smoke step)
- `_bmad-output/cross-llm-reviews/story-11-1-review-prompt.md` (canonical
  per-story prompt structure that the new template mirrors)

## Adversarial review checklist

### HIGH — libdoc keyword-name rendering match (per Epic 12 retro Action #3 + Epic 13 retro Action #3)

**N/A for this story (Story 14.1 ships zero `@keyword(name=...)` surface
changes — it modifies CLAUDE.md, creates a markdown template, and edits a
Story 7.1 spec Change Log). Per D-5 carve-out + AC-14.1.5, this section
APPEARS in the prompt for auditability even when not exercised.**

However, the reviewer SHOULD verify that the template file at
`_bmad/cross-llm-review-prompt-template.md` HIGH section
correctly carries the 4-step procedure (this is a meta-verification — is
the libdoc smoke step ITSELF correctly installed?). Specifically:

1. `grep -nE "uv run python -m robot.libdoc" _bmad/cross-llm-review-prompt-template.md`
   → ≥1 hit.
2. `grep -nE "@keyword\\(name=" _bmad/cross-llm-review-prompt-template.md`
   → ≥1 hit (decorator extraction step).
3. `grep -nE "byte-for-byte" _bmad/cross-llm-review-prompt-template.md`
   → ≥1 hit (the pass criterion).
4. `grep -nE "Story 12\\.3|libdoc-display" _bmad/cross-llm-review-prompt-template.md`
   → ≥1 hit (the empirical motivation citation).

If ANY of these 4 grep'd elements is absent or wrong, that's a HIGH —
the META install is mechanically incomplete.

### HIGH — citation drift (per `feedback_citation_drift_first_class`, Epic 1a)

Every `Epic <N> retro Action #<M>`, `L<N>` line-range, file path, and
date reference in the story spec + the modified CLAUDE.md + the new
template + the Story 7.1 Change Log entries MUST point to a real, current
target. Re-derive each cited fact from source:

- "Epic 12 retro Action #2" at `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L156 — is the action # correct? Is L156 the right line?
- "Epic 13 retro Action #2" at L177 — verify.
- "Epic 12 retro L116-125 (Story 12.3 libdoc-display bug evidence)" —
  verify the line range cites the actual libdoc bug evidence.
- CLAUDE.md L143 + L197 (header + closure-note lines) — verify those are
  the actual line numbers post-edit.
- Story 7.1 backfill claims v0.3.0 + v0.4.0 are "retroactive" — verify the
  honest-framing language is accurate (the entries don't claim to be from
  2026-05-21).

### HIGH — honest-framing audit (per `feedback_honest_framing`)

Story 7.1 Change Log v0.3.0 + v0.4.0 entries MUST be dated 2026-06-03
(today), NOT backdated to 2026-05-21 (when the story was originally
implemented). Verify:

1. `grep -E "^\\| 2026-06-03" _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`
   → 2 hits (v0.3.0 + v0.4.0).
2. The v0.3.0 entry explicitly labels itself "Retroactive backfill" —
   transparency about the backfill rather than silent fabrication.
3. The v0.4.0 entry is a "self-referential meta-entry" recording that
   v0.3.0 was the backfill — auditable meta-step.
4. CLAUDE.md mini-pass closure-note dates the install (2026-06-03) clearly.
5. Template file's source section dates the install + cites Epic 13 retro
   Action #3 carryover-1-epic-old.

ANY date falsification, ANY missing transparency label on a retroactive
entry, is a HIGH.

### HIGH — META install completeness (per AC-14.1.1, AC-14.1.2, AC-14.1.3 post-conditions)

Run the exact post-conditions specified in the ACs:

1. AC-14.1.1: `grep -cnE "story-create-time retro|Retro-debt mini-pass at story-create" CLAUDE.md` → MUST return ≥2.
2. AC-14.1.2: `grep -cnE "libdoc|@keyword\\(name=" _bmad/cross-llm-review-prompt-template.md` → MUST return ≥4; `wc -l _bmad/cross-llm-review-prompt-template.md` → MUST be ≥80.
3. AC-14.1.3: `grep -cE "^\\|\\s*20" _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` → MUST return ≥3.
4. AC-14.1.6: `grep -rnE "DF-14\\.1-S[0-9]" CLAUDE.md _bmad/cross-llm-review-prompt-template.md _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` → MUST return 0 hits.

Run each grep. Report failures.

### HIGH — common-failure-mode anti-pattern grep examples (per L-M1)

The CLAUDE.md mini-pass section's "Common failure mode" subsection MUST
ship 3 concrete grep examples (NOT abstract advice). Verify:

1. ≥3 ` ```bash ` or backtick'd `grep -nE` invocations in the subsection.
2. Each invocation references a specific symbol (e.g., `@guarded_fanout`,
   `## Change Log`, `test_*_live.py`).
3. The intent — "the grep is the audit; the action item text is only a
   pointer" — is explicitly stated.

If the section ships only abstract advice ("be careful to grep for
specific symbols"), that's a HIGH — L-M1 was not applied.

### MED — process discipline, hygiene

- **Carry-over catalog-gate** (per `feedback_carry_over_catalog_gate` UPSTREAM,
  37+ uses): zero new `DF-14.1-S*` references should appear in changed
  files. META story by spec. AC-14.1.6 verifies. If the reviewer finds
  ANY `DF-14.1-S*` reference, that's a MED — META story scope violation.
- **Stability-surface registration** (per L-1 Stories 13.x): N/A — META
  story ships no new public API surface. Confirm by inspection.
- **Sprint-status fidelity**: `epic-14: in-progress`; `14-1-*: review`;
  `last_updated: 2026-06-03` with a note. Verify all 3.
- **Acceptance-flow split clarity** (per D-4): the spec MUST be
  unambiguous that AC-14.1.4 + AC-14.1.5 are verified at Story 14.2-time,
  NOT Story 14.1-dev-time. If unclear, that's a MED — operator confusion
  risk for the next story in the loop.

### LOW — wording, optional siblings, style

- Template file's placeholder-slot list (8 slots) — are all 8 actually
  used in the template body? An unused slot is dead-code.
- CLAUDE.md mini-pass section's "5-step procedure" — are the 5 steps
  numbered + parallel in structure (per Bash-block + Markdown-list
  convention)?
- Story 7.1 v0.3.0 + v0.4.0 author attribution — does it correctly note
  "retroactive" status?

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.
Use the project's standard finding-codename format: `HIGH-A`, `HIGH-B`,
... per reviewer; `MED-1`, `MED-2`, ...; `LOW-1`, `LOW-2`, ...

## Save findings to

- Claude sonnet → `_bmad-output/cross-llm-reviews/story-14-1-claude-sonnet-findings.md`
- Claude opus → `_bmad-output/cross-llm-reviews/story-14-1-claude-opus-findings.md`
- Codex → `_bmad-output/cross-llm-reviews/story-14-1-codex-findings.md`
