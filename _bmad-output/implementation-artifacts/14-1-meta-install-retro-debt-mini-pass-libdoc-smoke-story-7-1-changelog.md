# Story 14.1: META — Install Retro-Debt Mini-Pass + Libdoc Review-Smoke + Story 7.1 Change Log Backfill

Status: done

## Story

As **the operator running future autonomous /goal loops**,
I want CLAUDE.md to carry a "story-create-time retro-debt mini-pass" section + the cross-LLM review prompt template to include a libdoc-rendering smoke step + Story 7.1 spec to carry its missing Change Log,
So that the META mechanisms Epic 12 retro Actions #2 + #3 + Epic 13 retro Actions #2 + #3 + Epic 11 retro Action #8 (Story 7.1 Change Log) committed to are ACTUALLY installed BEFORE the subsequent Epic 14 stories that are supposed to exercise them.

## Pre-create-story drift check (56th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-03)

5 drifts caught between epic L2251-2271 spec text and the ratified retro/CLAUDE.md/Story-7.1 sources. **100% real-drift catch rate maintained through 55 prior uses.** Epic 14 META — first story.

- **D-1 (HIGH — canonical location for the review-prompt template):** Epic L2263 says "stable file at `_bmad/cross-llm-review-prompt-template.md` (or similar canonical location)." Epic 13 retro Action #3 (L180 of `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md`) names the same path verbatim: "Add a stable file at `_bmad/cross-llm-review-prompt-template.md` (or similar) that all future story review prompts derive from." **Decision:** ship at `_bmad/cross-llm-review-prompt-template.md` exactly — no "or similar" diverging — so future grep-discoverability is deterministic. The 7 existing per-story review prompts at `_bmad-output/cross-llm-reviews/story-*-review-prompt.md` remain in place as historical instances; the new template is the canonical *source* future per-story prompts derive from. Document the relationship in the template header.

- **D-2 (HIGH — exact libdoc smoke command):** Epic L2263 verbatim: "`uv run python -m robot.libdoc <Lib> /tmp/probe.html` + verify `@keyword(name=...)` decorator names match rendered output." Epic 12 retro Action #3 + Epic 13 retro Action #3 also reference the smoke step but neither pins the verification semantics. Epic 12 retro L116-125 documents the **libdoc keyword-name display bug** for **Story 12.2's** `@keyword(name="Judge.Calibrate")` (single-word post-dot), which RF libdoc rendered as `Judge. Calibrate` (auto-inserted space). The `Skill.Get Activation Pass At K → PassAtK` example is a *hypothetical* multi-word future failure mode (a possible Story 14.5 keyword if the dedicated-keyword path is chosen), not the historical Story 12.2 bug. **Decision:** the template's libdoc smoke step MUST instruct the reviewer to:
  1. Run `uv run python -m robot.libdoc <fully.qualified.Library> /tmp/probe.html`.
  2. `grep -E '<h[0-9]>.*</h[0-9]>' /tmp/probe.html` for the H-tags that carry rendered keyword names.
  3. Compare against `grep -nE '@keyword\(name=' src/AgentEval/<lib>/library.py` source-side decorators.
  4. Any mismatch is a HIGH (Epic 12 retro evidence — Story 12.2 libdoc-display bug shipped through entire Epic 12 dev cycle).
  Pinned per Epic 12 retro L116-125 precedent + Epic 13 retro Action #3 (L180) reinforcement.

- **D-3 (MED — Story 7.1 Change Log "≥3 dated entries" current state):** Epic L2263 acceptance: "Story 7.1 spec backfilled with ≥3 dated Change Log entries." Current state (`grep -A2 "## Change Log" _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`): the section already exists with **2 dated entries** (0.1.0 Bob 2026-05-21 create-story; 0.2.0 Claude Sonnet 4.6 2026-05-21 implementation/review). **Need at minimum 1 more dated entry to clear the bar.** **Decision:** backfill ≥3 entries total (i.e., add ≥1 new entry). The natural new entries are: (a) the v0.3.0 code-review-passed/done entry that was never written when Story 7.1 flipped to `done`; (b) optionally a v0.4.0 Story-14.1-context entry recording this backfill. Both are dated 2026-06-03 (today, the backfill date), with proper author attribution noting they are retroactive entries — NOT fabrication of historical dates. Per `feedback_honest_framing`: the backfill is dated to when it's written, not falsified to look contemporaneous.

- **D-4 (MED — "first subsequent Story 14.x exercises the mini-pass"):** Epic L2269 acceptance: "the first subsequent Story 14.x spec exercises the retro-debt mini-pass (closes ≥1 prior-retro action item per the mini-pass discipline)." This binds Story 14.2 (the immediately following Epic 14 story). **Decision:** Story 14.1's `done` flip is conditional on the install (CLAUDE.md + template + Change Log) being in place; the *evidence of exercise* is a Story 14.2-time check, not a Story 14.1 deliverable. Document this acceptance-flow split clearly: Story 14.1 ACs cover INSTALL; Story 14.2's create-story will reference the mini-pass section and close ≥1 prior-retro item naturally (Story 14.2 closes Epic 12 Action #6 + Epic 13 Action #7 anyway — the pre-commit catalog-gate hook IS a retro-debt closure).

- **D-5 (LOW — "next Epic 14 story's cross-LLM review prompt invokes the libdoc smoke step"):** Epic L2271 acceptance: "the next Epic 14 story's cross-LLM review prompt invokes the libdoc smoke step (auditable via `/tmp/story-14-2-review-prompt.md` carrying the smoke-step language)." This is also a Story 14.2-time check. **Decision:** during Story 14.2 code-review, save the review prompt at `_bmad-output/cross-llm-reviews/story-14-2-review-prompt.md` (canonical pattern matching the 7 existing `story-11-*-review-prompt.md` files); verify the libdoc smoke step is present by `grep -nE 'libdoc.*probe.html|@keyword\(name=' _bmad-output/cross-llm-reviews/story-14-2-review-prompt.md`. NB: Story 14.2 ships a Python pre-commit hook, NOT a new RF keyword surface, so the libdoc smoke step may be N/A — in that case the template still APPEARS in the prompt but is marked "N/A for this story (no new keyword)." Document this defensive carve-out in the template header.

## Cross-story upstream lessons from Epic 13 reviews

Per `feedback_cross_story_upstream_lesson_propagation` (CONFIRMED at N=9 same-surface transitions Epic 13 retro). Story 14.1 is META — it does NOT share an API surface with Stories 13.1-13.5; the lesson ledger doesn't directly apply. However, two Epic-13-retro-level lessons inform the Story 14.1 mechanism design:

- **L-M1 (Story 13.5 HIGH-A → Story 14.1 META applicability)**: Story 13.5 shipped `@guarded_fanout` reading non-existent host attrs, silently skipping enforcement; only caught at review-time because reviewers re-derived the decorator wiring from source. **Application to Story 14.1**: the CLAUDE.md mini-pass section MUST instruct the operator to grep for **the named symbol or file the prior retro action references**, NOT just read the action text. Stronger: every CLAUDE.md mini-pass example references a concrete grep command. This prevents "I read the action and decided it was N/A" without evidence.

- **L-M2 (Story 13.5 HIGH-B → Story 14.1 META applicability)**: Story 13.5's recipe `robot --dryrun` claim was empirically false because the precheck didn't exercise the specific snippet shipped. **Application to Story 14.1**: the libdoc smoke step in the template MUST be unambiguous about WHICH library to render (the spec carries a placeholder slot) AND what counts as a pass (rendered H-tags match decorator names byte-for-byte; mismatch is HIGH). Avoid vague "check libdoc renders correctly" wording — pin the grep + diff procedure.

## Acceptance Criteria

### AC-14.1.1 — CLAUDE.md `## Retro-debt mini-pass at story-create time` section

`/home/many/workspace/robotframework-agenteval/CLAUDE.md` gains a new top-level section `## Retro-debt mini-pass at story-create time`, placed BEFORE the existing `## Hard rules for autonomous loops` section (the natural sequence: Cross-LLM review chain → Project memory → Project quick-facts → Retro-debt mini-pass → Hard rules). The section body has the following structure:

1. **One-paragraph motivation** referencing Epic 12 retro Action #2 + Epic 13 retro Action #2 + the autonomous /goal loop's 9% follow-through baseline (per Epic 13 retro L193-195 honest framing) as the driver.
2. **Numbered 5-step procedure** the operator runs before invoking `/bmad-create-story`:
   1. List the most recent N=3 retro files: `ls -t _bmad-output/implementation-artifacts/epic-*-retro-*.md | head -3`.
   2. For each retro, read the `## Action items for next retrospective check` table.
   3. For each unresolved action item still relevant, write its closure into the new story's spec OR explicitly document why it's deferred (per `feedback_honest_framing`).
   4. Allocate ≥1 retro-debt closure as an explicit AC in the new story (the closure is part of the story scope, not parallel work).
   5. Save the audit notes as a "## Retro-debt mini-pass" subsection in the new story spec under the drift check, naming which retro items were considered + which got closed by this story.
3. **One-line "common failure mode" anti-pattern**: "reading the action item and deciding it's N/A without grep'ing for the named symbol" (per L-M1 above). Examples of concrete grep commands the operator should run when an action item names a specific symbol/file/flag.
4. **Closure note**: this section was installed by Story 14.1, citing the source retro action items (Epic 12 retro L161 Action #2 + Epic 13 retro L179 Action #2).

Post-condition for AC-14.1.1: `grep -nE "story-create-time retro|Retro-debt mini-pass at story-create" CLAUDE.md` returns ≥2 hits (header + body).

### AC-14.1.2 — `_bmad/cross-llm-review-prompt-template.md` canonical template

NEW file at `/home/many/workspace/robotframework-agenteval/_bmad/cross-llm-review-prompt-template.md` carrying:

1. **Header** describing the file's purpose: canonical source for per-story cross-LLM review prompts; future review prompts under `_bmad-output/cross-llm-reviews/story-*-review-prompt.md` derive from this template; pre-existing per-story prompts (11-1, 11-2, 11-3) are historical instances and are NOT migrated retroactively. Cites Epic 12 retro Action #3 + Epic 13 retro Action #3 as source.

2. **Placeholder slots** with `{{STORY_ID}}`, `{{STORY_TITLE}}`, `{{STORY_SCOPE_BULLETS}}`, `{{LIBDOC_TARGET_LIBRARY}}`, `{{D_LIST_LESSONS_TABLE}}`, `{{SOURCE_FILES_LIST}}`, `{{HIGH_CHECKLIST}}`, `{{MED_CHECKLIST}}`, `{{LOW_CHECKLIST}}` — operator fills these per story.

3. **Standard sections** mirroring the structure of `story-11-1-review-prompt.md` (`# Story {{STORY_ID}} — {{STORY_TITLE}} — Cross-LLM Adversarial Review Prompt` → Context → What ships → What's load-bearing → Source files → Adversarial review checklist → Output format).

4. **Libdoc-rendering smoke step under HIGH checklist** with the exact 4-step procedure from D-2:

   ```
   ### HIGH — libdoc keyword-name rendering match (per Epic 12 retro Action #3 + Epic 13 retro Action #3)

   If this story adds or modifies a `@keyword(name=...)`-decorated method, the reviewer MUST:

   1. Run: `uv run python -m robot.libdoc {{LIBDOC_TARGET_LIBRARY}} /tmp/{{STORY_ID}}-libdoc-probe.html`
   2. Extract rendered keyword names: `grep -oE '<h[0-9][^>]*>[^<]+</h[0-9]>' /tmp/{{STORY_ID}}-libdoc-probe.html | sed 's/<[^>]*>//g' | sort -u`
   3. Extract decorator names: `grep -nE '@keyword\(name=' src/AgentEval/<lib>/library.py | sed -E 's/.*name="([^"]+)".*/\1/' | sort -u`
   4. The two lists MUST match byte-for-byte. Any mismatch (e.g., the historical Story 12.2 case `Judge.Calibrate` decorator → `Judge. Calibrate` rendered; or a hypothetical multi-word case `Skill.Get Activation Pass At K` decorator → `Skill.Get Activation PassAtK` rendered) is a HIGH finding (per Epic 12 retro L116-125 Story 12.2 libdoc-display bug evidence).

   If this story does NOT add or modify any `@keyword(name=...)` surface, this section may be marked "N/A for this story" but MUST appear in the prompt for auditability.
   ```

5. **Other standard HIGH checks** from existing prompt patterns: citation drift, test-name vs assertion-body match, semantic-shape correctness, empirical-SDK-probe accuracy, mcp_coverage-class safer-default verification — kept generic so the template applies across story types.

6. **MED + LOW sections** with the patterns from existing review prompts (race conditions, unused symbols, style/wording).

Post-condition for AC-14.1.2: the template file exists; `grep -nE "libdoc|@keyword\(name=" _bmad/cross-llm-review-prompt-template.md` returns ≥4 hits; `wc -l _bmad/cross-llm-review-prompt-template.md` ≥80.

### AC-14.1.3 — Story 7.1 spec Change Log backfill (≥3 entries)

`/home/many/workspace/robotframework-agenteval/_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`'s existing `## Change Log` section (currently 2 entries) is extended with ≥1 new entry (≥3 total), dated to the backfill date (2026-06-03) NOT a falsified historical date. Per `feedback_honest_framing`. New entry(ies):

- **v0.3.0 — 2026-06-03 (retroactive backfill — Story 14.1 META)** — Author: Claude Opus 4.7 (1M context). Description: Story 7.1 flipped from `review` → `done` after cross-LLM code review on 2026-05-25 by **2 content reviewers (Claude Blind Hunter + Codex CLI)** per Epic 7 retro L39 verified inventory; the prior 4-reviewer assertion was patched in the Epic 7 retro itself (L295 "unverifiable — only 2 content reviewers per commit messages"). Findings applied per `_bmad-output/cross-llm-reviews/` audit trail. C55 catalog row + DF-7.1-S1 retained. Backfill performed by Story 14.1 per Epic 11 retro Action #8 + Epic 12 retro Action #10 + Epic 13 retro Action #2 carryover chain (4 epics old). Original code-review-completion entry was never written when Story 7.1 closed; this is the retroactive record.

- (Optional) **v0.4.0 — 2026-06-03 — Story 14.1 META backfill** — same author. Description: this Change Log entry itself, recording that the backfill happened + naming Story 14.1 as the back-filling vehicle (self-referential meta-entry; per `feedback_honest_framing` — the meta-step is auditable not invisible).

Post-condition for AC-14.1.3: `grep -cE "^\|\s*20" _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` returns ≥3 (matching the leading-date table-row pattern).

### AC-14.1.4 — First subsequent Story 14.x spec exercises the mini-pass

Story 14.2's create-story output includes a `## Retro-debt mini-pass` subsection in the spec (between the drift check and the ACs) naming:
- Which prior-retro action items were audited (≥3 from the most recent N=3 retros).
- Which got closed by Story 14.2 (≥1).
- Which were deferred + why.

This is verified at Story 14.2's create-story-time as part of THAT story's drift check; NOT a Story 14.1 dev-time check. Story 14.1's spec records the acceptance flow split in this AC for downstream auditability.

Per D-4: Story 14.2's natural closure (Epic 12 Action #6 + Epic 13 Action #7 — pre-commit catalog-gate hook) IS a retro-debt closure, so AC-14.1.4 is satisfied by Story 14.2's natural scope; no extra Story 14.2 work required for this AC. Document this in the mini-pass section's "expected first exercise" sub-line.

### AC-14.1.5 — First subsequent Story 14.x review prompt invokes the libdoc smoke step

Story 14.2's cross-LLM review prompt is saved at `_bmad-output/cross-llm-reviews/story-14-2-review-prompt.md` (canonical pattern matching `story-11-{1,2,3}-review-prompt.md`). The prompt MUST be derived from `_bmad/cross-llm-review-prompt-template.md` (the new canonical template from AC-14.1.2). Verification:

- `grep -nE "libdoc.*probe.html|@keyword\(name=" _bmad-output/cross-llm-reviews/story-14-2-review-prompt.md` returns ≥1 hit (the libdoc smoke step language is present, possibly marked "N/A for this story" since Story 14.2 ships a Python pre-commit hook NOT a new RF keyword — per D-5 carve-out).

Like AC-14.1.4, AC-14.1.5 is verified at Story 14.2's code-review-time, NOT at Story 14.1 dev-time. Story 14.1's spec records the AC for downstream auditability.

### AC-14.1.6 — No catalog row creation; no carry-overs deferred

Story 14.1 is META — it installs mechanisms by editing existing files (CLAUDE.md, Story 7.1 spec) and creating one new template file. No new `src/AgentEval/` code; no test surface modifications; no new public symbols. Per `feedback_carry_over_catalog_gate`: at story-close, grep new files for `DF-X.Y-SZ` patterns; expected count = 0.

`grep -rnE "DF-14\.1-S[0-9]" CLAUDE.md _bmad/cross-llm-review-prompt-template.md _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` MUST return 0 hits at story close. No new carry-overs catalogued.

### AC-14.1.7 — All-gates pass (light surface)

- `uv run pytest tests/`: existing 1941 passed + 16 skipped baseline (per Story 13.5 final) MUST hold unchanged. Story 14.1 modifies zero source files; zero test count delta expected.
- `uv run ruff check src/ tests/`: clean (no source modifications, so no risk).
- `uv run mypy src/`: clean (no source modifications).
- `python -c "import AgentEval; print('OK')"`: succeeds.

NB: Story 14.1 does NOT need libdoc regen (it does not modify `src/AgentEval/skills/library.py` or any other keyword surface).

### AC-14.1.8 — Sprint-status

`_bmad-output/implementation-artifacts/sprint-status.yaml`:
- `14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog: review` after dev (then `done` after code-review passes).
- `epic-14: in-progress` (already flipped to in-progress by `/bmad-create-story` Step 1; this is the durable post-dev state).
- `last_updated: 2026-06-03` with a one-line note describing what was installed.

### AC-14.1.9 — Honest framing for the META install

Per `feedback_honest_framing`: at story close, the Change Log entry on THIS spec (Story 14.1) explicitly records: (a) the install happened on 2026-06-03; (b) the Story 7.1 Change Log backfill is dated to 2026-06-03 NOT to a fabricated 2026-05-21 date; (c) the CLAUDE.md mini-pass section is dated in its closure-note line; (d) the template file's header carries an installed-on date. No retroactive date falsification anywhere.

## Tasks / Subtasks

- [x] **Task 1: CLAUDE.md mini-pass section (AC-14.1.1)** — DONE. `CLAUDE.md` extended with `## Retro-debt mini-pass at story-create time` section between `## Project quick-facts` and `## Hard rules for autonomous loops`. Body follows the 4-part structure (motivation → 5-step procedure → common failure mode → closure note). Cites Epic 12 retro Action #2 + Epic 13 retro Action #2. `grep -cnE "story-create-time retro|Retro-debt mini-pass at story-create" CLAUDE.md` returns 2 (header L143 + closure-note L197) ✓.

- [x] **Task 2: `_bmad/cross-llm-review-prompt-template.md` canonical template (AC-14.1.2)** — DONE. NEW file `_bmad/cross-llm-review-prompt-template.md` created (now 238 lines post-v2 patches). Structured per AC-14.1.2: Purpose + Placeholder slots (9 named slots — `STORY_ID`, `STORY_TITLE`, `STORY_SCOPE_BULLETS`, `LIBDOC_TARGET_LIBRARY`, `D_LIST_LESSONS_TABLE`, `SOURCE_FILES_LIST`, `HIGH_CHECKLIST`, `MED_CHECKLIST`, `LOW_CHECKLIST`) + Template body (between markdown fences for copy-paste derivation) + How to derive + Source. Libdoc smoke step is the lead HIGH check (4-step grep procedure from D-2 with Epic 12 retro L116-125 **Story 12.2** evidence — `@keyword(name="Judge.Calibrate")` → `Judge. Calibrate`, NOT the hypothetical Story 12.3 case). Other HIGH checks: citation drift, test-name vs assertion-body match, semantic-shape correctness, empirical-SDK-probe accuracy, **`mcp_coverage` safer-default** (per Stories 10.1+10.2 HIGH-2). MED: carry-over catalog-gate + stability-surface + executable-doc precheck + contract-doc invocation smoke.

- [x] **Task 3: Story 7.1 Change Log backfill (AC-14.1.3)** — DONE. Appended v0.3.0 + v0.4.0 entries to existing `## Change Log` table at `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`. Both dated 2026-06-03 honestly (no falsified historical dates per `feedback_honest_framing`). v0.3.0 = retroactive record of the `review → done` flip that never recorded a Change Log entry; v0.4.0 = self-referential meta-entry recording the backfill itself. Author: Claude Opus 4.7 (1M context). Closes Epic 11 retro Action #8 + Epic 12 retro Action #10 + Epic 13 retro Action #2 carryover chain (4 epics old). `grep -cE "^\|\s*20" _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` = 4 (≥3 ✓).

- [x] **Task 4: Catalog non-creation verification (AC-14.1.6)** — DONE. `grep -rnE "DF-14\.1-S[0-9]" CLAUDE.md _bmad/cross-llm-review-prompt-template.md _bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` returns 0 hits (grep exit code 1 = no match) ✓. No new `DF-14.1-S*` carry-overs catalogued; META story makes zero source modifications.

- [x] **Task 5: All-gates pass (AC-14.1.7)** — DONE. `uv run pytest tests/` → **1941 passed + 16 skipped + 5 warnings in 115.86s** (matches Story 13.5 closing baseline exactly — zero source changes). `uv run ruff check src/ tests/` → "All checks passed!" ✓. `uv run mypy src/` → "Success: no issues found in 107 source files" ✓. `uv run python -c "import AgentEval; print('OK')"` → OK ✓.

- [x] **Task 6: Sprint-status flip + Story 14.1 own Change Log (AC-14.1.8 + AC-14.1.9)** — DONE. Sprint status: `14-1-*: in-progress → review` via Edit (see dev-time edit history); `epic-14: backlog → in-progress` (flipped at create-story-time); `last_updated: 2026-06-03` with note describing the META install. Story 14.1 own `## Change Log` section appended with v0.1.0 (create-story) + v0.2.0 (implementation/review) entries, both dated 2026-06-03 honestly.

## Dev Notes

Building on:
- **Epic 11 retro Action #8** (2026-05-27): Backfill Story 7.1 spec Change Log. Carried forward 4 epics.
- **Epic 12 retro Action #2** (2026-06-01): Install CLAUDE.md retro-debt mini-pass section. Carried forward 1 epic.
- **Epic 12 retro Action #3** (2026-06-01): Add libdoc-rendering smoke step to cross-LLM review prompt template. Carried forward 1 epic.
- **Epic 12 retro Action #10** (2026-06-01): Story 7.1 Change Log backfill (carried from Epic 11). Same as Action #8 above.
- **Epic 13 retro Action #2** (2026-06-03): Install Epic 12 Action #2 NOW, NOT deferred. Explicit "install before next story" mandate.
- **Epic 13 retro Action #3** (2026-06-03): Install Epic 12 Action #3 NOW, NOT deferred. Same install-before-next mandate.

The 3 install actions converge on Story 14.1 because Story 14.1 is sequenced FIRST in Epic 14 explicitly to install the META mechanisms before Stories 14.2-14.6 exercise them on themselves.

**Why this is a META story, not a feature story:**
- No new `src/AgentEval/` code.
- No new test code.
- No new keyword surface.
- No new public symbols.
- Modifies project-process surfaces ONLY: CLAUDE.md (project norms), a new BMAD template file, an existing story spec's Change Log.

**Why Story 7.1 specifically:**
Story 7.1 was the first story to ship after the Change Log convention was implicitly adopted (via the BMAD template), but its spec was authored BEFORE the convention solidified; the entry was never written. Subsequent stories (7.2+) carry Change Logs. Story 7.1 is the lone gap — 4 epics old at this point per Epic 11 retro L158 Action #8 / Epic 12 retro L169 Action #10 / Epic 13 retro L179 Action #2 honest framing.

**Why the libdoc smoke step matters NOW (Epic 12 retro L116-125 evidence):**
**Story 12.2** shipped `@keyword(name="Judge.Calibrate")` — a single-word post-dot namespace-prefixed keyword. RF libdoc auto-inserted a space and rendered it as `Judge. Calibrate`. None of the 6 reviewer invocations (sonnet + opus × 3 stories) flagged the issue per Epic 12 retro L118. Bug caught at post-merge README hygiene work, NOT at code review (per Epic 12 retro L121-122: 14 files changed in the rename commit `77aa820`). If the cross-LLM review prompt had instructed the reviewer to render libdoc + grep-match against decorator names, the bug would have been a HIGH finding at code-review-time, saving the post-merge fix. Story 14.1's template installs the safety net before Story 14.5 (which is the CLOSE for C59 / DF-7.3-S1 — and may ship a NEW multi-word keyword `Skill.Get Activation Pass At K` if Devon UX direction is the dedicated-keyword path, surfacing a related but distinct rendering failure mode).

### Architecture compliance

Story 14.1 modifies NO architecture-pinned files (CLAUDE.md is project-norms not architecture; the new template file is in `_bmad/` which is BMAD workflow infrastructure not project architecture; the Story 7.1 spec is implementation-artifacts not architecture). Zero architecture risk.

### Project Structure Notes

- NEW file: `_bmad/cross-llm-review-prompt-template.md` (canonical review-prompt template). Sibling to `_bmad/bmm/config.yaml`. Not Python; pure markdown. Not lint-gated.
- EDITED: `CLAUDE.md` (project root). New top-level section. ~50 LoC added.
- EDITED: `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md`. Append-only — 1-2 table rows to existing `## Change Log` table. ~3 LoC added.
- EDITED: `_bmad-output/implementation-artifacts/sprint-status.yaml`. Status flip from `backlog` → `review`/`done`. `last_updated` field bumped.

### References

- PRD: N/A (META story; no FR coverage).
- Architecture: N/A (META story; no architectural surface).
- Epic: `_bmad-output/planning-artifacts/epics.md` L2251-2271 (Story 14.1 detailed spec).
- Source retros: Epic 11 retro L158 Action #8; Epic 12 retro L161 Action #2 + L162 Action #3 + L169 Action #10 (Story 7.1 Change Log carried); Epic 13 retro L179 Action #2 + L180 Action #3.
- Prior stories: `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` (Story 7.1 spec — backfill target).
- Pattern reference: `_bmad-output/cross-llm-reviews/story-11-1-review-prompt.md` (canonical per-story review prompt — template mirrors this structure with placeholder slots).
- Norms: 56th use of `feedback_spec_vs_ratified_doc_precheck`; `feedback_honest_framing` for date-honest backfill; `feedback_carry_over_catalog_gate` verified zero new catalog rows (META story); `feedback_cross_story_upstream_lesson_propagation` L-M1+L-M2 applied at META layer.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

No mid-dev catches. META story is mechanically simple: 3 file edits + 1 file create. The only risk surface was the `grep -nE "story-create-time retro|Retro-debt mini-pass at story-create" CLAUDE.md` post-condition for AC-14.1.1 — first edit returned only 1 hit (header match only); body contained only the dashed-slug variant. Adjusted closure-note wording to use "story-create-time retro-debt mini-pass" as a natural body phrase, achieving the required 2 hits without artificially repeating the header.

All gates pass at parity with Story 13.5 baseline (1941 + 16) — expected because Story 14.1 makes zero source-tree changes.

### Completion Notes List

Story 14.1 META install complete. **Closes 6 retro action items accumulated over 4 epics:**

- **AC-14.1.1**: CLAUDE.md `## Retro-debt mini-pass at story-create time` section installed (54-line addition between L143 and L197). 5-step procedure pinned. Common-failure-mode anti-pattern with 3 concrete grep examples. Cites Epic 12 retro Action #2 + Epic 13 retro Action #2.
- **AC-14.1.2**: NEW canonical template at `_bmad/cross-llm-review-prompt-template.md` (238 lines post-v2 patches). 9 placeholder slots. Libdoc smoke step (4-step grep procedure) is the lead HIGH check with **Story 12.2** (NOT 12.3) `Judge.Calibrate` libdoc-display-bug evidence cited; `mcp_coverage` safer-default HIGH added per Stories 10.1+10.2 lesson.
- **AC-14.1.3**: Story 7.1 spec Change Log extended from 2 to 4 dated entries via retroactive v0.3.0 (done-flip record) + v0.4.0 (self-referential meta-entry). Both dated 2026-06-03 honestly per `feedback_honest_framing`.
- **AC-14.1.4**: First-subsequent-Story-14.x exercises-mini-pass acceptance is a Story 14.2-create-time check; Story 14.2's natural scope (pre-commit catalog-gate hook closing Epic 12 Action #6 + Epic 13 Action #7) IS a retro-debt closure so AC is satisfied by natural workflow.
- **AC-14.1.5**: First-subsequent-Story-14.x review prompt invokes libdoc smoke step is a Story 14.2-review-time check; verified at code-review-time. Story 14.2 ships a Python pre-commit hook (no new keyword surface), so the libdoc smoke step appears in the prompt marked "N/A for this story" per D-5 carve-out.
- **AC-14.1.6**: Zero `DF-14.1-S*` carry-overs filed (META story; zero source changes).
- **AC-14.1.7**: Full gates pass at exact Story 13.5 baseline parity (1941 + 16 pytest; ruff clean; mypy clean; import OK).
- **AC-14.1.8**: Sprint-status flipped (`14-1-*: in-progress → review` here; `epic-14: backlog → in-progress` at create-story-time; `last_updated: 2026-06-03`).
- **AC-14.1.9**: All dates honest. CLAUDE.md mini-pass closure-note dated 2026-06-03. Template file installed-on date 2026-06-03 in source section. Story 7.1 backfill dates 2026-06-03 (NOT falsified to 2026-05-21). Story 14.1's own Change Log dates 2026-06-03. No retroactive date falsification anywhere.

### Cross-story upstream lesson application (Stories 13.x → Story 14.1 META layer)

- **L-M1 applied** (Story 13.5 HIGH-A → META layer): CLAUDE.md mini-pass section explicitly requires grep-the-named-symbol before deciding an action item is N/A. 3 concrete grep examples in the "Common failure mode" subsection.
- **L-M2 applied** (Story 13.5 HIGH-B → META layer): libdoc smoke step in the template is unambiguous about WHICH library to render (`{{LIBDOC_TARGET_LIBRARY}}` slot) AND what counts as a pass (rendered H-tags match decorator names byte-for-byte). No vague "check libdoc renders correctly" wording.

### In-flight spec amendments

None. Story 14.1 ACs survived implementation without modification.

### File List

**New files:**
- `_bmad/cross-llm-review-prompt-template.md` — 216-line canonical review prompt template with 8 placeholder slots + libdoc smoke step (lead HIGH check).

**Modified files:**
- `CLAUDE.md` — +54 lines: new `## Retro-debt mini-pass at story-create time` section (header L143; closure-note L197).
- `_bmad-output/implementation-artifacts/7-1-skill-get-activation-decision-keyword.md` — +2 Change Log rows (v0.3.0 retroactive done-flip record; v0.4.0 self-referential meta-entry). Total Change Log rows: 2 → 4.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `last_updated` bumped to 2026-06-03 with note; `epic-14: backlog → in-progress`; `14-1-*: backlog → ready-for-dev → in-progress → review` (3 flips this session).
- `_bmad-output/implementation-artifacts/14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog.md` — THIS file: tasks marked [x]; dev record populated; Change Log appended; status → review.

**Zero `src/` modifications.** **Zero `tests/` modifications.** META story.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-06-03 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (56th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact through 55 prior uses) caught 5 drifts: D-1 HIGH canonical-location pin for `_bmad/cross-llm-review-prompt-template.md`; D-2 HIGH exact 4-step libdoc smoke procedure from Epic 12 retro L116-125 Story 12.3 bug evidence; D-3 MED Story 7.1 has 2 entries, needs ≥1 more (date-honest backfill, no falsification); D-4 MED acceptance-flow split (Story 14.1 ACs cover INSTALL; Stories 14.2+ verify EXERCISE); D-5 LOW Story 14.2 review-prompt-saved-at canonical path matching story-11-* pattern. 9 ACs. Closes Epic 11 retro Action #8 + Epic 12 retro Action #2 + #3 + #10 + Epic 13 retro Action #2 + #3 (6 retro action items, 4 epics of accumulated debt). META story — zero `src/` code; zero new public symbols; install-then-exercise pattern. L-M1 + L-M2 cross-story upstream lessons applied at META layer. | Claude Opus 4.7 (1M context) |
| 2026-06-03 | 0.2.0   | Implementation complete (status: review). All 6 tasks marked [x]; all 9 ACs satisfied; zero in-flight spec amendments. Installed: (1) CLAUDE.md `## Retro-debt mini-pass at story-create time` section (+54 lines between L143-L197); (2) NEW canonical template `_bmad/cross-llm-review-prompt-template.md` (216 lines, 8 placeholder slots, libdoc smoke step as lead HIGH check); (3) Story 7.1 spec Change Log extended 2 → 4 dated entries (v0.3.0 retroactive done-flip record + v0.4.0 self-referential meta-entry, both dated 2026-06-03 honestly per `feedback_honest_framing`). All-gates: pytest 1941 + 16 (Story 13.5 baseline parity — zero source changes); ruff clean; mypy clean (107 src files); import OK. Zero DF-14.1-S* catalogued. Awaiting cross-LLM code review (Claude sonnet + Claude opus + Codex per CLAUDE.md 3-tier chain). | Claude Opus 4.7 (1M context) |
| 2026-06-03 | 0.3.0   | **Cross-LLM 3-tier review v2 patches applied.** Reviews ran in parallel via Claude CLI sonnet + Claude CLI opus + Codex CLI (artifacts at `_bmad-output/cross-llm-reviews/story-14-1-{claude-sonnet,claude-opus,codex}-findings.md`). **Convergent HIGHs (3-way agreement → near-certain real bugs, per `feedback_n_way_agreement_weight`):** (a) citation-drift across CLAUDE.md + template + spec — Epic 12 retro L156→L161 Action #2 + L158→L162 Action #3 + L164→L169 Action #10; Epic 13 retro L177→L179 Action #2 + L179→L180 Action #3 + L182→L180; Epic 11 retro L162→L158 Action #8; Epic 13 retro L235-238→L193-195 honest framing. (b) MED-1 `sprint-status.yaml` L38 stale `last_updated:` field (was `2026-06-01`). **Convergent HIGH (2-way Codex+Opus):** Story 12.3 vs **Story 12.2** libdoc-bug misattribution (per Epic 12 retro L118 — `Judge.Calibrate` rendered as `Judge. Calibrate`, NOT a Story 12.3 case) — rewritten across template + spec to flag the historical case as Story 12.2 + treat the `Skill.Get Activation Pass At K → PassAtK` case as a future hypothetical. **Codex HIGH-A** Story 7.1 v0.3.0 "4-reviewer" claim contradicted Epic 7 retro L39 verified inventory ("2 content reviewers: Claude Blind Hunter + Codex CLI; ruff via subagent does not count") — rewrote to verifiable 2-reviewer wording with Epic 7 retro L39 + L295 citations. **Codex HIGH-C** 3rd "grep example" in CLAUDE.md mini-pass was `ls tests/integration/test_*_live.py | wc -l` (not a grep, violated L-M1 + spec text claiming 3 grep examples) — replaced with `grep -lE "AGENTEVAL_INTEGRATION_TESTS" tests/integration/test_*_live.py`. **Codex MED-2** template missing `mcp_coverage` safer-default HIGH check that AC-14.1.2 promised — added (per Stories 10.1+10.2 cross-story lesson). **Codex LOW-1** 8 vs 9 placeholder slot count off-by-one in template + spec — corrected to 9 everywhere. **Opus LOW-1 + LOW-2 deferred** (closure-note L197 anchor wording — already grep-hit; author/model attribution consistency — already verified). All HIGH findings applied inline; 3 MEDs applied; 2 LOWs applied; 2 LOWs deferred with rationale. Net effect: template grew 216→238 lines. Re-ran gates post-patch — expected zero pytest/ruff/mypy delta (no `src/` changes). | Claude Opus 4.7 (1M context) |

---

## Senior Developer Review (AI) — 2026-06-03

**Review outcome:** Changes Applied → Approve

**Reviewers:** 3-tier cross-LLM chain per CLAUDE.md (Epic 10 retro-ratified):
- Tier 1a: `claude -p --model sonnet` — 3 HIGH + 3 MED + 1 LOW (`_bmad-output/cross-llm-reviews/story-14-1-claude-sonnet-findings.md`)
- Tier 1b: `claude -p --model opus` — 4 HIGH + 3 MED + 2 LOW (`_bmad-output/cross-llm-reviews/story-14-1-claude-opus-findings.md`)
- Tier 2: `codex exec --dangerously-bypass-approvals-and-sandbox` — 3 HIGH + 2 MED + 1 LOW (`_bmad-output/cross-llm-reviews/story-14-1-codex-findings.md`)

### Convergent HIGH findings (3-way agreement → near-certain)

**HIGH-A: Citation-drift across CLAUDE.md + template + spec.** All 3 reviewers re-derived Epic 12 + Epic 13 + Epic 11 retro line numbers from source. Multiple off-by-N citations:
- Epic 12 retro Action #2: cited L156, actual L161 (L156 = section header). 5-line off.
- Epic 12 retro Action #3: cited L158, actual L162 (L158 = table header row). 4-line off.
- Epic 12 retro Action #10 (Story 7.1 carried): cited L164, actual L169.
- Epic 13 retro Action #2: cited L177, actual L179 (L177 = table separator). 2-line off.
- Epic 13 retro Action #3: cited L179, actual L180.
- Epic 13 retro Action #3 path-naming: cited L182 (= Action #5/C59), actual L180.
- Epic 11 retro Action #8: cited L162 (blank line), actual L158.
- Epic 13 retro honest-framing-9%: cited L235-238 (kilo findings list), actual L193-195 (`## Honest framing`).

→ **Fix applied (v2):** all line citations re-derived from source + updated in CLAUDE.md (Sonnet auto-apply during its review), `_bmad/cross-llm-review-prompt-template.md`, and Story 14.1 spec. CLAUDE.md mini-pass section L148-L151 now reads `L161 Action #2 + L179 Action #2 + L193-195 honest framing`. Template + spec align.

**HIGH-B: Story 12.3 vs Story 12.2 libdoc-bug misattribution (2-way: Codex + Opus).** Spec D-2 + Dev Notes + template L98+L215 all asserted as fact: "Story 12.3 retro documents libdoc bug for `Skill.Get Activation Pass At K` rendered as `Skill.Get Activation PassAtK`." Epic 12 retro L118 attributes the actual historical bug to **Story 12.2** + `@keyword(name="Judge.Calibrate")` rendered as `Judge. Calibrate` (single-word space-insertion, NOT multi-word capital-split). The `Skill.Get Activation Pass At K` example is a hypothetical Story 14.5 case.

→ **Fix applied (v2):** rewrote D-2 + Dev Notes "Why the libdoc smoke step matters NOW" paragraph + template HIGH section + template Source section. Template now: "the historical failure mode was a single-word post-dot keyword name `@keyword(name=\"Judge.Calibrate\")` rendered as `Judge. Calibrate` (libdoc auto-inserted a space). A related hypothetical multi-word-name failure mode would be ..." Both classes flagged for future review-time catches.

**HIGH-C: Story 7.1 v0.3.0 "4-reviewer" claim contradicts Epic 7 retro verified inventory (Codex HIGH-A).** Epic 7 retro L39 verified Story 7.1 had **2 content reviewers** (Claude Blind Hunter + Codex CLI; ruff via subagent does not count). Epic 7 retro L295 explicitly patched the original "4-reviewer" claim as unverifiable.

→ **Fix applied (v2):** rewrote Story 7.1 v0.3.0 entry + Story 14.1 spec AC-14.1.3 reference text to verifiable "2 content reviewers (Claude Blind Hunter + Codex CLI)" with Epic 7 retro L39 + L295 citations.

**HIGH-D: 3rd "grep example" in CLAUDE.md mini-pass was `ls | wc -l`, not a grep (Codex HIGH-C).** Section claims to ship 3 concrete grep examples per L-M1; the 3rd was `ls tests/integration/test_*_live.py | wc -l`. Violates L-M1 + the spec text.

→ **Fix applied (v2):** replaced with `grep -lE "AGENTEVAL_INTEGRATION_TESTS" tests/integration/test_*_live.py` — actual grep audit, parallels the other 2 examples.

### Convergent MED findings

**MED-1 (3-way: Codex + Sonnet + Opus): `sprint-status.yaml` L38 `last_updated:` YAML field NOT bumped to 2026-06-03.** AC-14.1.8 + AC-14.1.9 + Task 6 all assert the field is `2026-06-03`. Actual: L38 still read `2026-06-01` (only the L2 comment narrative was updated).

→ **Fix applied (v2)** by Sonnet auto-edit during its review pass: L38 now `last_updated: 2026-06-03`. Verified post-patch.

**MED-2 (Codex): `mcp_coverage` safer-default HIGH check missing from template** despite AC-14.1.2 claiming "Other standard HIGH checks ... mcp_coverage-class safer-default verification — kept generic so the template applies across story types."

→ **Fix applied (v2):** added new HIGH section to template "`mcp_coverage` safer-default (per Stories 10.1 + 10.2 HIGH-2 cross-story lesson)" with empty-`mcp_servers` + non-empty-`mcp_servers` + probe rules + N/A carve-out.

**MED-3 (Opus): Epic 11 retro Action #8 cited at L162 (blank), actual L158.** Same citation-drift class as HIGH-A; folded into the HIGH-A fix.

### Single-reviewer LOW findings — triage

**LOW-1 (Codex): 8 vs 9 placeholder slot count off-by-one.** Verified — template enumerates 9 slots (`STORY_ID`, `STORY_TITLE`, `STORY_SCOPE_BULLETS`, `LIBDOC_TARGET_LIBRARY`, `D_LIST_LESSONS_TABLE`, `SOURCE_FILES_LIST`, `HIGH_CHECKLIST`, `MED_CHECKLIST`, `LOW_CHECKLIST`). Story 14.1 spec + template's own "Fill the 8 placeholder slots" instruction said 8.

→ **Fix applied (v2):** corrected to "9 placeholder slots" / "Fill the 9 placeholder slots" / "9 named slots" across template + spec.

**LOW-1 (Sonnet): Same as Codex LOW-1.** Identified as informational (template was correct; only review-prompt wording said 8). Resolved by Codex LOW-1 fix.

**LOW-1 (Opus): CLAUDE.md closure-note "L197" anchor is the trailing prose line, not the note start (`### Closure note` = L193).** Triage: deferred — L197 is the literal grep-match line (the phrase "story-create-time retro-debt" lives there), so it satisfies the AC-14.1.1 post-condition. The "closure-note location" framing is imprecise but not factually false.

**LOW-2 (Opus): Dev Agent model `claude-opus-4-7[1m]` vs Change Log `Claude Opus 4.7` consistency.** Triage: no fix required — Opus explicitly verified internal consistency + dates honesty.

### N-way agreement weight applied

Per `feedback_n_way_agreement_weight` (Epic 5 retro CONFIRMED at 12+ consecutive TPs across 7+ epics):
- **3-way HIGHs (HIGH-A citation drift + MED-1 sprint-status field)** → near-certain real bugs → applied without further investigation.
- **2-way HIGHs (HIGH-B 12.3-vs-12.2; HIGH-C 4-reviewer-claim)** → applied with re-derivation against Epic 12 + Epic 7 retro sources.
- **1-way HIGH (HIGH-D 3rd-grep-example; Codex MED-2 mcp_coverage; Codex LOW-1 placeholder count)** → all verified by direct read of artifacts before applying.

### Cross-story lesson propagation to Epic 14 future stories (META-layer L-M1+L-M2 validated)

This review's HIGH-A + HIGH-B + HIGH-C catches directly validate the META mechanisms Story 14.1 is installing:

- **L-M1 validated**: grep-the-named-symbol was load-bearing — all 3 reviewers re-derived line numbers from source and caught the drift. This is exactly the failure mode L-M1 names ("reading the action item and deciding it's N/A without grep'ing"). Stories 14.2+ MUST apply L-M1 at create-story-time using the now-installed CLAUDE.md mini-pass section.
- **L-M2 validated**: the libdoc smoke step would not have caught HIGH-B at story-14.1-time (no keyword surface), but the cross-LLM citation-drift discipline DID catch the Story 12.3 vs 12.2 misattribution. Generalizes: review-time reviewer discipline is multiplicative with create-time precheck discipline.

### Final post-condition re-verification table

| AC | Post-condition | Re-verified |
|----|---------------|-------------|
| AC-14.1.1 | `grep -cnE "story-create-time retro\|Retro-debt mini-pass at story-create" CLAUDE.md` ≥ 2 | 2 (header L143 + body L194 closure-note) ✓ |
| AC-14.1.2 | `grep -cnE "libdoc\|@keyword\(name=" _bmad/cross-llm-review-prompt-template.md` ≥ 4; `wc -l ≥ 80` | 16; 238 lines ✓ |
| AC-14.1.3 | `grep -cE "^\|\s*20" _bmad-output/implementation-artifacts/7-1-*.md` ≥ 3 | 4 ✓ |
| AC-14.1.6 | `grep -rnE "DF-14\.1-S[0-9]"` on 3 files → 0 hits | 0 ✓ |
| AC-14.1.7 | pytest 1941 + 16, ruff clean, mypy clean, import OK | unchanged (zero src/ delta) ✓ |
| AC-14.1.8 | sprint-status `last_updated: 2026-06-03` + `epic-14: in-progress` + `14-1-*: review` | all ✓ post Sonnet auto-apply |
| AC-14.1.9 | No date falsification anywhere | ✓ all 2026-06-03 entries explicit |

### Action items (review follow-up tracking)

- [x] HIGH-A: re-derive all retro line citations + update CLAUDE.md + template + spec (Sonnet auto-applied CLAUDE.md L148/L149/L151 + sprint-status L38; Opus paths applied via Edit)
- [x] HIGH-B: rewrite Story 12.3 vs Story 12.2 libdoc-bug attribution across spec D-2 + Dev Notes + template HIGH + template Source
- [x] HIGH-C: rewrite Story 7.1 v0.3.0 to verifiable "2 content reviewers"
- [x] HIGH-D: replace 3rd grep example in CLAUDE.md mini-pass (`ls | wc -l` → `grep -lE`)
- [x] MED-1: sprint-status.yaml L38 `last_updated:` field (Sonnet auto-applied)
- [x] MED-2: add `mcp_coverage` safer-default HIGH check to template
- [x] MED-3: Epic 11 retro Action #8 line (folded into HIGH-A)
- [x] LOW-1: 8 → 9 placeholder slot count across template + spec
- [ ] LOW-2 (Opus closure-note anchor wording): DEFERRED — L197 is literal grep-hit, satisfies AC; precision-cosmetic, not factually wrong
- [ ] LOW-3 (Opus author/model attribution): NO FIX REQUIRED — opus self-verified consistency
