# Cross-LLM Adversarial Review Prompt Template

## Purpose

This is the **canonical template** for per-story cross-LLM review prompts
used by the project's 3-tier review chain (Claude sonnet + Claude opus +
Codex, with kilo/minimax-M2.7 fallback). Per-story review prompts under
`_bmad-output/cross-llm-reviews/story-<X>-<Y>-review-prompt.md` derive from
this template by filling the placeholder slots.

**Installed by Story 14.1 META on 2026-06-03** per Epic 12 retro Action #3
(`_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L162) +
Epic 13 retro Action #3 (`_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md`
L180) "add libdoc-rendering smoke step to cross-LLM review prompt template."

**Pre-existing per-story prompts** at `_bmad-output/cross-llm-reviews/story-11-{1,2,3}-review-prompt.md`
+ `_bmad-output/cross-llm-reviews/phase-7-mcp-review-prompt.md` are
**historical instances**; they are NOT migrated retroactively. New
per-story prompts from Story 14.2 onward derive from THIS template.

## Placeholder slots

The operator fills these 9 slots per story when deriving a concrete per-story prompt:

- `{{STORY_ID}}` — e.g., `14-2` (matches the filename pattern).
- `{{STORY_TITLE}}` — e.g., `Pre-Commit Catalog-Gate Hook`.
- `{{STORY_SCOPE_BULLETS}}` — bulleted list of what ships (new files,
  modified files, contracts).
- `{{LIBDOC_TARGET_LIBRARY}}` — fully-qualified library path if the story
  adds/modifies a `@keyword(name=...)` surface (e.g.,
  `AgentEval.skills.library.SkillsLibrary`); else `N/A — no keyword surface`.
- `{{D_LIST_LESSONS_TABLE}}` — drift-check D-N list + cross-story upstream
  lessons L-N table from the story spec (the audit trail the reviewer
  verifies application of).
- `{{SOURCE_FILES_LIST}}` — source files the reviewer should read for
  citation drift / shape verification.
- `{{HIGH_CHECKLIST}}` — story-specific HIGH checks (in addition to the
  standard checklist below).
- `{{MED_CHECKLIST}}` — story-specific MED checks.
- `{{LOW_CHECKLIST}}` — story-specific LOW checks.

## Template body — derive per-story prompt by filling slots

```markdown
# Story {{STORY_ID}} — {{STORY_TITLE}} — Cross-LLM Adversarial Review Prompt

## Context

Story {{STORY_ID}} ships {{STORY_TITLE}}. Per CLAUDE.md ratified 3-tier
cross-LLM review chain (Epic 10 retro 2026-05-26):

- **Tier 1a: Claude CLI sonnet** (`claude -p --dangerously-skip-permissions --model sonnet "<prompt>"`)
- **Tier 1b: Claude CLI opus** (`claude -p --dangerously-skip-permissions --model opus "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- **Tier 3 (fallback): kilo/minimax-M2.7** (`~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "<prompt>"`)

Each reviewer runs INDEPENDENTLY. Coverage is multiplicative, not redundant
(Epic 10 retro evidence: zero finding-overlap across the 3 tiers).

## What Story {{STORY_ID}} ships

{{STORY_SCOPE_BULLETS}}

The diff is at `_bmad-output/cross-llm-reviews/story-{{STORY_ID}}-diff.patch`.

## What's load-bearing — read the story spec first

The story spec at `_bmad-output/implementation-artifacts/{{STORY_ID}}-*.md`
documents the drift-check D-N list + cross-story upstream lessons L-N
folded into the AC text. Your job is to verify whether each is correctly
applied:

{{D_LIST_LESSONS_TABLE}}

## Source files to verify against

{{SOURCE_FILES_LIST}}

## Adversarial review checklist

### HIGH — libdoc keyword-name rendering match (per Epic 12 retro Action #3 + Epic 13 retro Action #3)

If this story adds or modifies any `@keyword(name=...)`-decorated method on
a Library class, the reviewer MUST:

1. Run: `uv run python -m robot.libdoc {{LIBDOC_TARGET_LIBRARY}} /tmp/story-{{STORY_ID}}-libdoc-probe.html`
2. Extract rendered keyword names (the H-tag hits in the rendered HTML):
   ```bash
   grep -oE '<h[0-9][^>]*>[^<]+</h[0-9]>' /tmp/story-{{STORY_ID}}-libdoc-probe.html \
     | sed 's/<[^>]*>//g' | sort -u
   ```
3. Extract source-side decorator names:
   ```bash
   grep -nE '@keyword\(name=' src/AgentEval/<lib>/library.py \
     | sed -E 's/.*name="([^"]+)".*/\1/' | sort -u
   ```
4. The two lists MUST match byte-for-byte. **Any mismatch is a HIGH
   finding.** Per Epic 12 retro L116-125 evidence (Story 12.2
   libdoc-display bug shipped through the entire Epic 12 dev cycle, caught
   only at post-merge README hygiene because the reviewer never ran
   libdoc): the historical failure mode was a single-word post-dot
   keyword name `@keyword(name="Judge.Calibrate")` rendered as
   `Judge. Calibrate` (libdoc auto-inserted a space). A related
   hypothetical multi-word-name failure mode would be a decorator
   `@keyword(name="Skill.Get Activation Pass At K")` rendered as
   `Skill.Get Activation PassAtK` (libdoc auto-splitting on a capital).
   Both classes would have been caught at code-review-time if this smoke
   step had been part of the review prompt.

If this story does NOT add or modify any `@keyword(name=...)` surface,
this section may be marked **"N/A for this story (no new/modified keyword
surface)"** but MUST APPEAR in the prompt for auditability.

### HIGH — citation drift (per `feedback_citation_drift_first_class`, Epic 1a)

Every `ADR-XX`, `FR-XX`, `Story X.Y`, `DF-X.Y-SZ`, `L<N>` line-range, or
filename in the code/spec docstrings + the story spec text MUST point to a
real, current target. **Codex + kilo are particularly good at this class —
re-derive each cited fact from source rather than checking only that the
citation exists.**

### HIGH — test-name vs assertion-body match (per `feedback_test_name_assertion_match`, Epic 3)

Every test name's promise MUST be delivered by its assertion body. Test
name `test_foo_returns_bar_when_baz` MUST contain an assertion that
evidences `returns bar when baz`. Fake-green pattern catches: Epic 3
Story 3.2 args-copy + Story 3.3 invalid-keyword error path.

### HIGH — semantic-shape correctness

Trace any new dataclass / public surface end-to-end. Verify each field's
provenance against the source data, the docstring's "Returns: ..." promise,
and downstream consumer expectations. Per Epic 8 retro
`feedback_listener_hook_api_surface_empirical_check`: when extending an
RF Listener v3 hook or a `@dataclass(frozen=True)` surface, empirically
verify via probe (e.g., `tests/integration/probes/debug_listener.py`).

### HIGH — empirical-SDK-probe accuracy (per `feedback_codex_probe_fitness`, Epic 2)

If the story ships fixtures captured from a real binary's output (e.g.,
`/tmp/codex_probe.jsonl`, JSONL fixtures under `tests/fixtures/<adapter>/`),
re-run a 1-line probe against the live binary if possible to verify the
schema hasn't drifted since story-authoring.

### HIGH — `mcp_coverage` safer-default (per Stories 10.1 + 10.2 HIGH-2 cross-story lesson)

If this story adds or modifies a `CodingAgentAdapter` / `SubprocessAdapter`
implementation that returns an `AgentRunResult`, the reviewer MUST verify
that:

1. When `mcp_servers` is empty → `mcp_coverage="hosted_in_process"` is
   acceptable (no external attachment to observe).
2. When `mcp_servers` is non-empty BUT no observer has confirmed coverage
   → `mcp_coverage` MUST default to `"external_mixed"`, NOT
   `"hosted_in_process"`. Per ADR-016 L59 safer-default.
3. Probe: any test exercising the adapter with `mcp_servers=[...]` MUST
   assert `result.mcp_coverage == "external_mixed"` unless the observer
   explicitly upgrades the field.

If the story does NOT touch an adapter surface, mark this section
**"N/A for this story (no adapter modification)"** but keep it in the
prompt for auditability.

{{HIGH_CHECKLIST}}

### MED — process discipline, hygiene

- **Carry-over catalog-gate** (per `feedback_carry_over_catalog_gate` UPSTREAM,
  37+ uses): every `DF-X.Y-SZ` reference in new code/docstrings/specs MUST
  have a corresponding row in `docs/phase-1-5-carry-overs.md` +
  `_bmad-output/implementation-artifacts/deferred-work.md`. (Story 14.2's
  pre-commit hook automates this — but reviewer cross-checks
  defense-in-depth until the hook has shipped + been verified.)
- **Stability-surface registration** (per `feedback_cross_story_upstream_lesson_propagation`
  L-1, Epic 13): new public dataclasses + new `@keyword(name=...)`
  decorations + new public classmethods MUST appear in
  `docs/contracts/stability-surface.md` with `provisional` label.
- **Executable-doc precheck** (per `feedback_executable_doc_precheck`, Epic 7):
  every fenced ` ```robotframework ` block in `docs/recipes/*` + `README.md`
  shipped by the story MUST pass `robot --dryrun`. (Story 14.3's recipe CI
  extraction automates this — but reviewer cross-checks until shipped.)
- **Contract-doc invocation smoke test** (per `feedback_contract_doc_invocation_smoke_test`,
  Epic 8): contract docs documenting CLI/RF invocations MUST carry a
  subprocess integration smoke test.

{{MED_CHECKLIST}}

### LOW — wording, optional siblings, style

- Style, ordering, sibling cross-refs, docstring wording, dead-code
  constants, unused imports.

{{LOW_CHECKLIST}}

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.
Use the project's standard finding-codename format:

- `HIGH-A`, `HIGH-B`, ... `HIGH-N` per reviewer
- `MED-1`, `MED-2`, ...
- `LOW-1`, `LOW-2`, ...

Reviewer-internal numbering is fine; the operator reconciles across
reviewers when applying the v2 patches.

## Save findings to

`_bmad-output/cross-llm-reviews/story-{{STORY_ID}}-<reviewer>-findings.md`

Where `<reviewer>` is one of: `claude-sonnet`, `claude-opus`, `codex`, `kilo`.

For kilo invocations specifically: kilo's `--auto` mode invokes Write tool
autonomously; the prompt MUST instruct kilo to `Write` findings to the
specific path above or the final answer may be lost to streaming output
(per `feedback_third_llm_family_fallback` Epic 10 operational note).
```

## How to derive a per-story prompt

1. Copy the template body above (between the ` ```markdown ` fences).
2. Fill the 9 placeholder slots with the story-specific content.
3. Save the derived prompt to `_bmad-output/cross-llm-reviews/story-{{STORY_ID}}-review-prompt.md`.
4. Pipe the prompt verbatim to each Tier 1+2 reviewer in parallel via
   background Bash. Tier 3 (kilo) is fallback per CLAUDE.md degradation
   rules; for non-trivial retros, run all 3 tiers regardless.
5. Findings land at the paths under "Save findings to" above.

## Source

- Epic 12 retro Action #3 (`_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L162):
  add libdoc-rendering smoke step to the cross-LLM review prompt template.
- Epic 13 retro Action #3 (`_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L180):
  install Epic 12 Action #3 NOW, not deferred. Carryover-1-epic-old.
- Story 14.1 META spec (`_bmad-output/implementation-artifacts/14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog.md`):
  the install vehicle. AC-14.1.2 pins this template's location + structure.
- Epic 12 retro L116-125 (Story 12.2 libdoc-display bug evidence —
  `@keyword(name="Judge.Calibrate")` → `Judge. Calibrate`):
  the empirical motivation for the libdoc smoke step.
