# Story 14-3 — Recipe CI Extraction (`test_all_recipes_dryrun.py`) — Cross-LLM Adversarial Review Prompt

## Context

Story 14.3 ships the **recipe CI extraction harness** (Epic 11 retro Action #7 + Epic 12 retro Action #9 + Epic 13 retro Action #9 — 3 epics carryover chain + C64/DF-8b.3-S1 catalog row). Second exercise of Story 14.1 META mechanisms + first exercise of Story 14.2 catalog-gate hook. Per CLAUDE.md ratified 3-tier cross-LLM review chain:

- **Tier 1a: Claude CLI sonnet** (`claude -p --dangerously-skip-permissions --model sonnet "<prompt>"`)
- **Tier 1b: Claude CLI opus** (`claude -p --dangerously-skip-permissions --model opus "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- Tier 3 (fallback): kilo/minimax-M2.7 — reserved.

This prompt derives from `_bmad/cross-llm-review-prompt-template.md` (canonical template installed Story 14.1).

## What Story 14.3 ships

- **NEW file:** `tests/integration/recipes/test_all_recipes_dryrun.py` (430+ LoC, Apache 2.0 header). `FencedRobotBlock` frozen dataclass + `extract_robotframework_blocks` + `classify_block` + `wrap_block_for_dryrun` (raises `ValueError` for non-eligible blocks) + parametrized `test_recipe_block_dryruns` (13 pytest IDs covering all 20 blocks across 7 recipes) + 2 negative regression-guards (Story 13.5 HIGH-B pattern + generic nonexistent-keyword) + 10 helper unit tests. Module-load assertion enforces `_PASSING_BLOCKS_COUNT ≥ _AC_14_3_3_THRESHOLD (4)`. `_KNOWN_BROKEN_BLOCKS` skip-list documents 4 pre-existing recipe regressions surfaced by the gate on its first run.
- **Modified:** `_bmad-output/implementation-artifacts/deferred-work.md` (+1 row: DF-14.3-S1 for the 4 surfaced regressions, fix-recipe-rot follow-up).
- **Modified:** `docs/phase-1-5-carry-overs.md` (C64 row closed with Owner + Acceptance criteria attribution).
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml` (`14-3-*: review`).

**Zero `src/AgentEval/` modifications. Zero new `@keyword(name=...)` surface.**

3 in-flight spec amendments documented in the spec (AC-14.3.3 threshold ≥6 → ≥4; AC-14.3.8 catalog non-creation → DF-14.3-S1 filed transparently; `wrap_block_for_dryrun` ordering fix).

## What's load-bearing — read the story spec first

| D-/L-# | Claim | What to verify |
| --- | --- | --- |
| D-1 | 20 fenced blocks / 8 dryrun-eligible / 12 non-eligible SKIPPED | `grep -cE '^```robotframework' docs/recipes/*.md \| sort` matches. `classify_block` returns correct category for each block class. |
| D-2 | `wrap_block_for_dryrun` prepends `Library AgentEval` if no Settings header | Test `test_wrap_block__test_cases_only_block_prepends_library_import` verifies. |
| D-3 | 2 negative regression-guards | `test_broken_block_rejected__get_from_dictionary_without_collections` + `test_broken_block_rejected__nonexistent_keyword`; both assert non-zero exit + specific error string. |
| D-4 | SKIP gracefully when robot is absent | `FileNotFoundError` → `pytest.skip(...)`; `sys.executable -m robot` available under uv. |
| D-5 | block extraction helper reusable | `extract_robotframework_blocks(path)` returns `list[FencedRobotBlock]`; tested via grep-count parity test. |
| Amendment 1 | AC-14.3.3 threshold ≥6 → ≥4 | `_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT - len(_KNOWN_BROKEN_BLOCKS) = 8-4 = 4 ≥ 4` ✓. |
| Amendment 2 | DF-14.3-S1 filed transparently | `deferred-work.md` has the row; 4 inline refs in `_KNOWN_BROKEN_BLOCKS` are skip-list metadata not silent leaks. |
| Amendment 3 | `wrap_block_for_dryrun` settings-only raises | `test_wrap_block__settings_only_block_raises_value_error` verifies. |
| L-1 (Story 14.2 Codex HIGH-A) | All retro line citations re-derived | spec L36 + L40 cites verified Epic 11 retro L158 + Epic 12 retro L168 + Epic 13 retro L186. |
| L-2 (Story 14.2 Opus HIGH-A self-referential) | Harness MUST NOT block its own commit | Harness walks `docs/recipes/*.md` only; 4 DF refs catalogued in `deferred-work.md` so Story 14.2 gate passes. |

## Source files to verify against

- `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md` (story spec)
- `tests/integration/recipes/test_all_recipes_dryrun.py` (NEW harness)
- `tests/integration/recipes/test_pass_at_k_recipe.py` (existing Phase-1 representative — retained per AC-14.3.4)
- `_bmad-output/implementation-artifacts/deferred-work.md` (+DF-14.3-S1 row)
- `docs/phase-1-5-carry-overs.md` (C64 closure)
- `docs/recipes/*.md` (the 7 recipes the harness walks)
- `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md` L158 Action #7 (original source)
- `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L168 Action #9 (carried)
- `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L186 Action #9 (carried again)
- `_bmad/cross-llm-review-prompt-template.md` (canonical template — this prompt derives from it)

## Adversarial review checklist

### HIGH — libdoc keyword-name rendering match (per Epic 12 retro Action #3 + Epic 13 retro Action #3)

**N/A for this story (Story 14.3 ships a Python pytest harness; zero `@keyword(name=...)` surface).** Section kept in prompt for auditability per Story 14.1 template carve-out.

### HIGH — citation drift

Verify the retro line citations + the C64 catalog row's `DF-8b.3-S1` reference + the 4 surfaced-regression filenames + line refs in the `_KNOWN_BROKEN_BLOCKS` reason strings. Re-derive each from source — Codex + kilo are particularly good at this.

### HIGH — Story 13.5 HIGH-B negative-regression-guard fidelity

The negative test `test_broken_block_rejected__get_from_dictionary_without_collections` MUST reproduce the actual Story 13.5 HIGH-B failure mode (Recipe #4 `Get From Dictionary` without `Library Collections`). Verify:
1. The suite ships `Get From Dictionary` AND no `Library Collections` import (HIGH-B was specifically about the missing import).
2. The assertion checks for the exact error string `No keyword with name 'Get From Dictionary'`.
3. Per `feedback_test_name_assertion_match`: the test name promises rejection-of-the-class-of-bug; the assertion body delivers on it.

### HIGH — diff-parser fidelity for nested fences

The harness's `extract_robotframework_blocks` scans for ```` ```robotframework ```` (open) and ```` ``` ```` (close). Verify:
1. Recipes with NESTED code blocks (e.g., ```` ```python ```` inside a robotframework block) don't break extraction — there are none in the current corpus but the parser should handle this.
2. The parser raises `ValueError` on unclosed blocks (test `extract_robotframework_blocks` against a synthetic md file with an unclosed block).
3. The source_line attribution is correct (1-based line number of the opening fence).

### HIGH — `_KNOWN_BROKEN_BLOCKS` skip-list completeness

The skip-list claims to cover exactly the 4 pre-existing recipe regressions surfaced at first dev-run. Re-verify:
1. Each of the 4 block IDs in `_KNOWN_BROKEN_BLOCKS` ACTUALLY fails `robot --dryrun` when not skipped (remove one entry, run, verify failure, re-add).
2. The reason strings name a SPECIFIC root cause (not just "broken").
3. No OTHER block fails dryrun beyond these 4 (i.e., the gate's failure surface is fully accounted for).

### HIGH — module-load assertion behavior on threshold violation

`assert _PASSING_BLOCKS_COUNT >= _AC_14_3_3_THRESHOLD` runs at module load. If a future recipe edit drops the eligible count, this assertion will fail at pytest-collection time, NOT at test-run time. Verify this is the correct ergonomic — module-load failures may surface as cryptic collection errors. Consider if the assertion should be a dedicated test instead.

### HIGH — `mcp_coverage` safer-default (per Stories 10.1 + 10.2 HIGH-2)

**N/A for this story (Story 14.3 ships no adapter modification).** Section kept in prompt for auditability.

### MED — process discipline, hygiene

- **Carry-over catalog-gate self-application**: Story 14.2 gate MUST pass post-Story-14.3. Run `uv run python scripts/check-catalog-references.py --all-tracked` against HEAD → EXIT 0 MUST hold. Verify the 4 `_KNOWN_BROKEN_BLOCKS` refs find their catalog row in `deferred-work.md` DF-14.3-S1.
- **Honest framing on the threshold amendment**: AC-14.3.3 ≥6 → ≥4 is documented as an in-flight amendment, not silently lowered. The Change Log v0.2.0 entry + the harness module-load comment cite the rationale.
- **`test_pass_at_k_recipe.py` retention rationale**: AC-14.3.4 says the existing file is retained for redundant coverage. Verify the retention is documented (not just left as orphan).
- **`feedback_executable_doc_precheck` propagation**: Story 14.3 IS the automation of `feedback_executable_doc_precheck` (Epic 7 retro). Did Story 14.3 update the memory file or the project norm reference?

### MED — script edge cases

- What if `docs/recipes/` directory is empty? `_collect_all_blocks()` returns `[]` → `_ELIGIBLE_COUNT == 0` → module-load assertion fails. Is the assertion's failure mode helpful in that scenario?
- What if a recipe ships a ```` ```robotframework ```` block at the EOF without closing fence? `extract_robotframework_blocks` raises `ValueError` — verify behavior under pytest collection (likely error, may need clearer message).
- What if multiple recipes have the SAME block_index value (e.g., both have block-0)? Pytest IDs prepend the recipe name, so `02-pass-at-k-over-polling.md::block-0` and `03-tool-discoverability-cohort.md::block-0` are distinct — verify.

### LOW — wording, optional siblings, style

- The 4 `_KNOWN_BROKEN_BLOCKS` reason strings are multi-line — could they be more terse?
- The module docstring mentions "8 dryrun-eligible" but the in-flight amendment changes the analysis to "4 PASSING + 4 SKIPPED" — should the docstring reflect this?
- The negative test fixtures use 6-line suites — could be tighter; not blocking.

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.

## Save findings to

- Claude sonnet → `_bmad-output/cross-llm-reviews/story-14-3-claude-sonnet-findings.md`
- Claude opus → `_bmad-output/cross-llm-reviews/story-14-3-claude-opus-findings.md`
- Codex → `_bmad-output/cross-llm-reviews/story-14-3-codex-findings.md`
