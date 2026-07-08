# Story 14.3 — Cross-LLM 3-Tier Review: Synthesis & Triage Record

**Date:** 2026-06-04
**Story:** 14.3 — Recipe CI Extraction (`tests/integration/recipes/test_all_recipes_dryrun.py`)
**Synthesizer:** Claude Opus 4.8 (in-session, cross-LLM review v2)

This is the capstone audit-trail record (CLAUDE.md §"How to invoke the chain" step 6)
consolidating all four reviewer tiers + the triage/resolution of every finding.

## Chain status (all tiers landed)

| Tier | Reviewer | Status | Output |
| --- | --- | --- | --- |
| 1a | Claude CLI sonnet | LANDED | `story-14-3-claude-sonnet-findings.md` — 0 HIGH, 3 MED, 2 LOW |
| 1b | Claude CLI opus (background) | DEGRADED (0 bytes) → substituted | `story-14-3-claude-opus-findings.md` (summary) |
| 1b' | In-session Opus (empirical) | LANDED | `story-14-3-opus-inline-findings.md` — 3 HIGH, 3 MED, 3 LOW |
| 2 | Codex CLI | LANDED | `story-14-3-codex-findings.md` — 0 HIGH, 3 MED, 1 LOW (+ earlier pass: HIGH-A nested fence) |
| 3 | kilo / minimax-M2.7 | LANDED CLEAN | `story-14-3-kilo-findings.md` — NONE (post-v2 confirmation) |

The CLI background tiers partially degraded (sonnet/opus 0 bytes at first check —
they were mid-write and completed afterward; opus CLI stayed empty). Per the
degraded-chain protocol, the in-session Opus served as the substantive Opus tier
and Tier-3 kilo was invoked. Every HIGH was independently re-verified by
grep / `robot --dryrun` probe before patching.

## HIGH findings (3) — all applied

| ID | Source | Finding | Resolution |
| --- | --- | --- | --- |
| HIGH-1 | Opus | The 3 retro actions + C64 set a **≥6-blocks-PASSING** bar; only 4 pass. Marked fully closed/DONE. | Reframed to **PARTIAL** in spec retro-debt section, Completion Notes, C64 row, Change Log v0.3.0. Full closure blocked on DF-14.3-S1. |
| HIGH-2 | Opus | AC-14.3.3 measures **eligible** blocks (8 ≥ 6, already met); the "≥6→≥4 amendment" silently switched to *passing* (4) — spurious. | Amendment **RETRACTED**. AC-14.3.3 eligible bar restored; passing count tracked as a separate `_DF_14_3_S1_PASSING_FLOOR` regression-guard (code already split by prior pass; spec narrative corrected). |
| HIGH-3 | Opus | Spec cites "Epic 11 retro L158 Action #7"; L158 = Action #8, Action #7 is at **L157**. | Corrected L158 → L157 in all 4 spec references. |
| HIGH-A | Codex (earlier pass) | `extract_robotframework_blocks` closed on any bare fence → nested ```` ```python ```` inside a robot block would truncate extraction. | Parser switched to CommonMark fence-length tracking; `test_…__nested_inner_fence_preserved` added (applied in v0.4.0). |

## MED findings — triage

| ID | Source | Finding | Decision |
| --- | --- | --- | --- |
| MED (unclosed-block test) | Opus MED-1 / Sonnet MED-A | No test for the `extract` unclosed-block `ValueError` path. | APPLIED — `test_…__raises_value_error_on_unclosed_block` (v0.4.0). |
| MED (count drift) | Opus MED-2 / Sonnet MED-C | "13 parametrized / 33 / 10 helper" contradictory. | APPLIED — re-derived to 20 block cases + 2 negative + 15 helper/unit = **37 collected (21 passed / 16 skipped)**; full suite **1985 passed + 32 skipped**. |
| MED (memory annotation) | Opus MED-3 / Sonnet MED-B | `feedback_executable_doc_precheck` not annotated as CI-enforced. | APPLIED — memory file updated with Story 14.3 CI-enforcement note. |
| MED-1 (grep parity) | Codex | `counts_match_grep` used literal 3-backtick grep; parser accepts 3+. | APPLIED — grep widened to `^\`{3,}robotframework[[:space:]]*$`. |
| MED-2 (skip-list audit) | Codex | No test proving the skip-list == the actual failing set. | APPLIED — `test_known_broken_blocks__matches_actual_failing_set` added; PASSES (skip-list empirically exact). |
| MED-3 (stale README) | Codex | `docs/recipes/README.md` described the harness as an unshipped Phase-1.5 work-item + hardcoded "71 entries". | APPLIED — validation section rewritten; count de-hardcoded. |
| MED (robot-module preflight) | Codex / Opus | `FileNotFoundError` skip path effectively unreachable. | APPLIED — `_robot_module_available()` preflight via `importlib.util.find_spec` (v0.4.0). |

## LOW findings — triage

| ID | Source | Finding | Decision |
| --- | --- | --- | --- |
| LOW-1 (C64 line) | Codex | Spec cites C64 at L91; actual row at L88. | APPLIED — L91 → L88 in all spec references. |
| LOW (docstring split) | Opus / Sonnet | Module docstring said "8 eligible" without the 4/4 pass/skip split. | Addressed by the docstring + `_KNOWN_BROKEN_BLOCKS` comments (prior pass). |
| LOW (nested-fence caveat) | Opus | Parser fragility on nested fences. | Resolved by HIGH-A parser rewrite (no longer a fragility). |

## Verified CLEAN (empirically probed, no finding)

- **Skip-list completeness** — the new MED-2 audit test PASSES: the 4 eligible blocks
  that fail `robot --dryrun` are exactly `_KNOWN_BROKEN_BLOCKS` (recipe-3 block-0,
  recipe-5 block-0, recipe-5 block-1, recipe-7 block-0); 4 others pass; zero
  unaccounted failures, zero stale entries.
- **Negative-guard fidelity** — both negative tests pass; `Get From Dictionary`
  suite ships no `Library Collections` and asserts `No keyword with name
  'Get From Dictionary'`.
- **Catalog gate** — `scripts/check-catalog-references.py --all-tracked` EXIT 0.
- **Fence counts** — 20 total / 8 eligible, matches grep.
- **Self-recursion** — harness globs `docs/recipes/*.md` only.

## Final gate state

- `uv run pytest tests/` → **1985 passed + 32 skipped** (full-run verified 2026-06-04).
- Harness alone → 21 passed + 16 skipped.
- ruff + mypy (src) clean; Story 14.2 catalog-gate hook EXIT 0.

## Honest-framing bottom line

The harness machinery is empirically sound. The substantive findings were **framing /
citation / count drift**, not code-correctness defects — exactly the drift class the
3-tier chain targets. The single load-bearing correction: Story 14.3 **PARTIALLY**
advances Epic 11 #7 / Epic 12 #9 / Epic 13 #9 / C64 (mechanism ships + CI-active), but
the **≥6-passing** half of each criterion is NOT met (4/8 pass) and is deferred to
**DF-14.3-S1** (fix-recipe-rot). Full closure is conditional on that follow-up.
