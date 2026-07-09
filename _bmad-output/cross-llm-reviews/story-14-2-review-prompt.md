# Story 14-2 — Pre-Commit Catalog-Gate Hook — Cross-LLM Adversarial Review Prompt

## Context

Story 14.2 ships the **pre-commit catalog-gate hook** (Epic 11 retro Action #2 + Epic 12 retro Action #6 + Epic 13 retro Action #7 — 3 epics carryover chain). First exercise of the Story 14.1 META mechanisms (retro-debt mini-pass + canonical review-prompt template). Per CLAUDE.md ratified 3-tier cross-LLM review chain:

- **Tier 1a: Claude CLI sonnet** (`claude -p --dangerously-skip-permissions --model sonnet "<prompt>"`)
- **Tier 1b: Claude CLI opus** (`claude -p --dangerously-skip-permissions --model opus "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- Tier 3 (fallback): kilo/minimax-M2.7 — reserved.

This prompt derives from `_bmad/cross-llm-review-prompt-template.md` (canonical template installed Story 14.1, exercised on itself + this story).

## What Story 14.2 ships

- **NEW file:** `scripts/check-catalog-references.py` (200+ LoC, Apache 2.0 header). Mode A (default; `git diff --cached` for pre-commit) + Mode B (`--all-tracked` for CI). Recognizes BOTH catalog formats: backticked (`` `DF-X.Y-SZ` ``) in `docs/phase-1-5-carry-overs.md` + bold-row (`**DF-X.Y-SZ (...)**`) in `_bmad-output/implementation-artifacts/deferred-work.md`. `EXCLUDED_PATH_PREFIXES` for `_bmad/`, `_bmad-output/`, `docs/keywords/`, `CHANGELOG.md` (audit surfaces legitimately discuss DF refs).
- **NEW file:** `tests/unit/scripts/test_check_catalog_references.py` (18 unit tests). Coverage: regex extraction (standard + Epic-1b `DF-1b.4-S1` alphanumeric + multi-per-line), catalog row formats (backticked + bold-row + union), find_missing logic, error message format, Mode A monkeypatched, Mode B with `--catalog` override, edge cases (catalog-self-exclusion via `_parse_unified_diff`, prose mentions not counted), live-repo sanity assertion.
- **NEW file:** `tests/unit/scripts/__init__.py` (empty package init).
- **Modified:** `.pre-commit-config.yaml` (+7 lines: `catalog-references` hook entry; `repo: local` + `uv run python scripts/check-catalog-references.py` + `pass_filenames: false` + `require_serial: true`).
- **Modified:** `.github/workflows/ci.yml` (+6 lines: `Catalog references check (Phase-1.5)` step after `License headers check (Apache 2.0)` at L73-74).
- **Modified:** `_bmad-output/implementation-artifacts/deferred-work.md` (+2 rows: retroactive backfill of DF-5.3-S5 + DF-13.3-S4 — the 2 violations the script surfaced on HEAD at first all-tracked run, attributed as "catalogued retroactively per Story 14.2 catalog-gate enforcement").
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml` (`14-2-*: backlog → review`).

The story spec at `_bmad-output/implementation-artifacts/14-2-pre-commit-catalog-gate-hook.md` documents 5 drift D-N entries + 2 cross-story upstream lessons + 3 in-flight spec amendments.

**Zero `src/AgentEval/` modifications. Zero new `@keyword(name=...)` surface.**

## What's load-bearing — read the story spec first

Verify whether each is correctly applied:

| D-/L-# | Claim | What to verify |
| --- | --- | --- |
| D-1 | Script path: `scripts/check-catalog-references.py` (kebab-case per Story 1a.5) | File exists at exactly that path; `entry: uv run python scripts/check-catalog-references.py` matches `scripts/check-license-headers.py` precedent. |
| D-2 | Regex MUST cover Epic-1b alphanumeric story numbering | `DF_REFERENCE_RE = re.compile(r"DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+")` matches `DF-1b.4-S1`. Test `test_regex_extracts_epic_1b_alphanumeric_story_prefix` verifies. |
| D-3 | Catalog row verification handles both formats | `catalog_rows()` recognizes backticked + bold-row. Tests `test_catalog_rows_only_match_backticked_references` + `test_catalog_rows_bold_row_format_deferred_work` + `test_all_catalog_rows_unions_both_formats`. |
| D-4 | CI parity needs `--all-tracked` mode | `.github/workflows/ci.yml` runs with `--all-tracked`; pre-commit defaults to Mode A. |
| D-5 | Exit code + error message format pinned | `format_error_message()` per AC-14.2.1 D-5; test `test_format_error_message_lists_missing_refs`. |
| L-1 | Re-derive every line-number-style anchor from source | Script docstring + spec citations re-derived (Epic 13 retro L184 verified, Epic 12 retro L96 verified). |
| L-2 | Mini-pass example chain converges on Story 14.2 deliverable | CLAUDE.md mini-pass's `grep -lE "AGENTEVAL_INTEGRATION_TESTS"` example is the style-template Story 14.2 automates. |
| In-flight #1 | EXCLUDED_PATH_PREFIXES scope expansion | `is_self_excluded` covers `_bmad/`, `_bmad-output/`, `docs/keywords/`, `CHANGELOG.md`. |
| In-flight #2 | Multi-catalog support | `--catalog` accepts multiple paths; default unions both. |
| In-flight #3 | Retroactive backfill of 2 HEAD violations | `DF-5.3-S5` + `DF-13.3-S4` added to `deferred-work.md` with retroactive attribution. |

## Source files to verify against

- `_bmad-output/implementation-artifacts/14-2-pre-commit-catalog-gate-hook.md` (story spec)
- `scripts/check-catalog-references.py` (NEW 200+ LoC script)
- `tests/unit/scripts/test_check_catalog_references.py` (NEW 18 unit tests)
- `.pre-commit-config.yaml` (+1 hook entry)
- `.github/workflows/ci.yml` (+1 CI step)
- `_bmad-output/implementation-artifacts/deferred-work.md` (+2 retroactive rows)
- `scripts/check-license-headers.py` (Story 1a.5 structural template)
- `_bmad/cross-llm-review-prompt-template.md` (canonical template Story 14.2 derives from)
- `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md` L152 Action #2 (original source)
- `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L165 Action #6 (carried)
- `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L184 Action #7 (carried again)

## Adversarial review checklist

### HIGH — libdoc keyword-name rendering match (per Epic 12 retro Action #3 + Epic 13 retro Action #3)

**N/A for this story (Story 14.2 ships a Python script + pre-commit hook + CI step; zero `@keyword(name=...)` surface).** Per D-5 carve-out from Story 14.1 + AC-14.2.8. Section kept in prompt for auditability per Story 14.1 AC-14.1.5.

### HIGH — citation drift (per `feedback_citation_drift_first_class`)

Every `Epic <N> retro Action #<M>`, `L<N>` line-range, file path, and date in the spec + script docstring + the modified deferred-work.md rows MUST point to a real, current target. Re-derive each cited fact from source:
- Epic 11 retro L152 Action #2 — verify (original source).
- Epic 12 retro L165 Action #6 — verify.
- Epic 13 retro L184 Action #7 — verify.
- Epic 12 retro L96 (catalog-gate sub-pattern note) — verify content.
- `src/AgentEval/mcp/library.py:591` (DF-13.3-S4 surface) — verify the line.
- `src/AgentEval/telemetry/listener.py:859` (DF-5.3-S5 surface) — verify the line.

### HIGH — regex correctness against actual catalog corpus

Probe the live catalog corpus to verify the regex catches what it should:
1. `grep -oE 'DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+' docs/phase-1-5-carry-overs.md | sort -u` — should produce ≥10 unique refs.
2. `grep -oE 'DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+' _bmad-output/implementation-artifacts/deferred-work.md | sort -u` — should include `DF-1b.X-SY` patterns from Epic 1b.
3. Run the script: `uv run python scripts/check-catalog-references.py --all-tracked` → MUST exit 0.

If the regex is wrong, the gate is fake-green (false negatives).

### HIGH — Mode A diff-parser correctness

The `_parse_unified_diff` function tracks (file, line_in_new_file, line_text) across multiple files. Verify:
- A diff adding a line to `src/AgentEval/foo.py` at line 11 produces `(src/AgentEval/foo.py, 11, "...")`.
- A diff modifying `docs/phase-1-5-carry-overs.md` (self-excluded) produces `[]`.
- A diff with multiple hunks tracks line numbers correctly across hunks.

Per `feedback_test_name_assertion_match`: verify the 4 diff-parser tests actually probe what their names promise.

### HIGH — empirical-SDK-probe accuracy (per `feedback_codex_probe_fitness`)

Story 14.2 doesn't ship adapters; this section probes the script's behavior against real Git invocations. Run:
- `git diff --cached` inside the repo with no staged changes → script's `staged_diff_lines` returns `[]` → main returns 0.
- `git ls-files | wc -l` against this repo → should be ~700+ tracked files; `all_tracked_files` should filter to ~600+ matching SCANNED_EXTENSIONS after EXCLUDED_PATH_PREFIXES.

### HIGH — `mcp_coverage` safer-default (per Stories 10.1 + 10.2 HIGH-2 cross-story lesson)

**N/A for this story (Story 14.2 ships no adapter modification).** Section kept in prompt for auditability per Story 14.1 template carve-out.

### MED — process discipline, hygiene

- **Carry-over catalog-gate self-application**: Story 14.2 builds the gate AND its own dev surface should pass it. Run `uv run python scripts/check-catalog-references.py --all-tracked` against the post-Story-14.2 HEAD → EXIT 0 MUST hold. Verify.
- **Stability-surface registration**: N/A (script lives in `scripts/`, not project public API).
- **Executable-doc precheck**: N/A (no fenced robotframework blocks added).
- **Mid-dev decision documentation**: 3 in-flight spec amendments are documented in the Dev Notes Debug Log + Change Log v0.2.0 narrative. Verify the narrative honestly records the surface-area expansion (single-catalog → multi-catalog; narrow regex → wider regex; etc.).
- **Honest framing for the gate's value claim**: spec AC-14.2.9 + script docstring cite Stories 11.2 + 11.3 + 7.4 D-2 as past-incident evidence. Verify those incidents actually fit the gate's mandate (inline DF refs added without catalog rows).

### MED — script edge cases

- What happens if the script is run OUTSIDE a git repo? (`subprocess.run` returncode != 0 → returns empty list → exits 0; verify this is intended behavior, not silent-fail.)
- What happens if a tracked file is unreadable (permission error)? (`except OSError: continue`; verify the script doesn't crash.)
- What happens if a SCANNED file is binary? (`encoding="utf-8", errors="replace"`; verify the script doesn't false-positive on binary content masquerading as DF refs.)
- Mode B against a fresh-clone repo with no `git history`: should still work via `git ls-files`.

### LOW — wording, optional siblings, style

- Script docstring length + structure — does it match `scripts/check-license-headers.py`'s pattern?
- Test file naming — does `test_check_catalog_references.py` mirror the script's name?
- Comment quality in the new `.pre-commit-config.yaml` hook entry — is it as clean as the existing `license-headers` entry?
- `EXCLUDED_PATH_PREFIXES` is a `tuple` — could be a `frozenset` for cleaner intent; trade-off worth noting?

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW. Use the project's standard finding-codename format: `HIGH-A`, `HIGH-B`, ... per reviewer; `MED-1`, `MED-2`, ...; `LOW-1`, `LOW-2`, ...

## Save findings to

- Claude sonnet → `_bmad-output/cross-llm-reviews/story-14-2-claude-sonnet-findings.md`
- Claude opus → `_bmad-output/cross-llm-reviews/story-14-2-claude-opus-findings.md`
- Codex → `_bmad-output/cross-llm-reviews/story-14-2-codex-findings.md`
