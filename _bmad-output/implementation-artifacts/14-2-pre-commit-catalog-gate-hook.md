# Story 14.2: Pre-Commit Catalog-Gate Hook

Status: done

## Story

As **the operator + future autonomous loops**,
I want a `.pre-commit-config.yaml` hook scanning `git diff --cached` for `DF-\d+\.\d+-S\d+` references + verifying each has a corresponding row in `docs/phase-1-5-carry-overs.md`,
So that no commit can ship an inline `DF-X.Y-SZ` reference without the catalog row — eliminating the 3-way HIGH-A finding pattern recurring through Epics 11/12/13.

## Retro-debt mini-pass (first exercise of the CLAUDE.md mini-pass section installed by Story 14.1, 2026-06-03)

Per CLAUDE.md L143 `## Retro-debt mini-pass at story-create time` (installed 2026-06-03 by Story 14.1 commit `524dd6c`). Procedure run:

**Step 1:** `ls -t _bmad-output/implementation-artifacts/epic-*-retro-*.md | head -3` →
1. `epic-13-retro-2026-06-03.md` (2026-06-03).
2. `epic-12-retro-2026-06-01.md` (2026-06-01).
3. `epic-11-retro-2026-05-27.md` (2026-05-27).

**Step 2:** Read `## Action items` table in each. Audit (unresolved items relevant to Story 14.2 surface):
- **Epic 13 retro Action #7 (L184)**: "Build pre-commit catalog-gate hook (Action #6 carried). Scans `git diff --cached` for `DF-\d+\.\d+-S\d+` references + verifies catalog row in `phase-1-5-carry-overs.md`. Blocks commits that introduce inline references without corresponding catalog rows." — Story 14.2's PRIMARY scope. ✅ Closing this.
- **Epic 12 retro Action #6 (L165)**: same hook, carried from Epic 11 retro Action #2. ✅ Closing this.
- **Epic 11 retro Action #2 (L152)**: "Build pre-commit catalog-gate hook OR CI grep step." — original source 3 epics ago. ✅ Closing this transitively.
- Epic 13 retro Action #1 (L176): Operator decision — Phase 1+2 complete OR define Epic 14. Already decided (Epic 14 active). N/A.
- Epic 13 retro Action #2 (L179): CLAUDE.md mini-pass. Closed by Story 14.1. N/A.
- Epic 13 retro Action #3 (L180): libdoc smoke step template. Closed by Story 14.1. N/A.
- Epic 13 retro Action #4 (L181): kilo post-hoc on Epic 12 stories. Operator-facilitated; orthogonal. Deferred (per `feedback_honest_framing` — not Story 14.2 scope).
- Epic 13 retro Action #5 (L182): Close DF-7.3-S1 / C59. Story 14.5 scope. Deferred.
- Epic 13 retro Action #6 (L183): C20+C95 unified resolution. Story 14.6 scope. Deferred.
- Epic 13 retro Action #8 (L185): Live integration tests + close C70. Story 14.4 scope. Deferred.
- Epic 13 retro Action #9 (L186): C64 recipe CI extraction. Story 14.3 scope. Deferred.
- Epic 13 retro Action #10 (L187): CANDIDATE norm validation. Facilitator scope; emerges at Epic 14 retro. Deferred.

**Step 3-5:** ≥1 retro-debt closure as explicit AC — Story 14.2 closes **3 actions transitively** (Epic 11 #2 + Epic 12 #6 + Epic 13 #7) per the carryover chain documented above.

## Pre-create-story drift check (57th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-03)

5 drifts caught between epic L2273-2295 spec text + the ratified pre-commit/CI/catalog sources. **100% real-drift catch rate maintained through 56 prior uses** (Story 14.1 the 56th).

- **D-1 (HIGH — script path + Python language pin):** Epic L2293 says "Python via `uv run python scripts/check-catalog-references.py` per Story 1a.5 pre-commit pattern." Verified — `.pre-commit-config.yaml` L20-44 uses exactly the `entry: uv run python scripts/<kebab-case>.py` + `language: system` + `pass_filenames: false` pattern (Story 1a.5 deliverable; cited at config L1, L9-13 as `repo: local` design choice). **Decision:** ship script at `scripts/check-catalog-references.py` exactly — matches the kebab-case convention of the 2 existing scripts (`check-license-headers.py` + `apply-license-headers.py`). NOT `scripts/check_catalog_references.py` (Python module name); the script is invoked as a path, not imported.

- **D-2 (HIGH — extracted DF reference pattern):** Epic L2279 + L2285 says hook scans `git diff --cached` for `DF-\d+\.\d+-S\d+` references. Real-world counter-examples to verify regex against (from existing catalogued items):
  - `DF-4.4-S1` (C20) — `\d+\.\d+` covers single-digit X.Y.
  - `DF-1b.4-S1` (Epic 1b had Stories 1b.1..1b.6 — story prefix has a letter!) — `\d+\.\d+` does NOT match `1b.4`. **CRITICAL DRIFT.**
  - `DF-7.3-S1` (C59) — `\d+\.\d+` covers.
  - `DF-13.5-S5` (last carry-over filed Story 13.5 review) — covers.

  Grep for actual references in catalogued items:
  ```
  grep -oE 'DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+' docs/phase-1-5-carry-overs.md | sort -u
  ```
  Result includes `DF-1b.X-SY` patterns from Epic 1b carry-overs (C24 mentions DF-1b.4-S1 / C24 source: Story 1b.4; etc.).

  **Decision:** the regex MUST be `DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+` (NOT `DF-\d+\.\d+-S\d+`) to cover the Epic-1b alphanumeric story numbering. **In-flight spec amendment** of epic L2279 + L2285 per `feedback_in_flight_spec_amendment` (epic text uses `\d+\.\d+` shorthand; the actual catalog corpus requires `[0-9a-z]+\.[0-9a-z]+`). Apply the wider regex; document this drift in the script's docstring + a unit test that asserts a `DF-1b.4-S1` reference is correctly extracted (NOT falsely passed through).

- **D-3 (HIGH — catalog row format for verification):** Epic L2287 says hook "greps for matching `` (\`DF-X.Y-SZ\`) `` row in `docs/phase-1-5-carry-overs.md`." Verified actual catalog row pattern from C20 + C59 + C95:
  ```
  | **C20** | **Epic 4: `@guarded_fanout` enforcement for MCPLibrary Tier-3 keyword (`DF-4.4-S1`).** ...
  | **C95** | **Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability` (`DF-13.5-S1`).** ...
  ```
  The pattern is **`` `DF-X.Y-SZ` `` inside backticks** in the row text (not necessarily wrapped in parens). The epic's "(`DF-X.Y-SZ`)" wrapping is just illustrative.

  **Decision:** verification regex on catalog file is `grep -nE '` + a literal `` `DF-X.Y-SZ` `` + `'` (backticked literal). Each extracted `DF-X.Y-SZ` from diff MUST appear at least once inside backticks in `phase-1-5-carry-overs.md`. If a reference appears in diff but NOT in catalog → fail commit with that specific reference cited.

- **D-4 (MED — CI parity per defense-in-depth norm):** Epic L2289 says "the hook RUNS in CI too (`.github/workflows/ci.yml` defense-in-depth same pattern as ruff/mypy)." Verified pattern — `.github/workflows/ci.yml` L73-74 runs `uv run python scripts/check-license-headers.py` as a step. **Decision:** add a parallel `Catalog-references check` step after the License-headers step in `.github/workflows/ci.yml`, invoking the same script. CI runs the script with **no staged diff** — it must support a second mode: `--all-tracked` (or equivalent) that scans ALL tracked files instead of `git diff --cached`. Without this, CI's empty-staging-area run is a no-op + the gate is fake-green there.

- **D-5 (LOW — script exit code + error messaging contract):** Epic L2287 verbatim: "fails the commit with a clear error message listing missing rows." **Decision:** script exits `1` with stderr message format:
  ```
  ERROR: pre-commit catalog-gate found N inline DF-X.Y-SZ reference(s) without catalog rows in docs/phase-1-5-carry-overs.md:
    - DF-X.Y-SZ in <file>:<line> (excerpt: "...")
    - DF-X.Y-SZ in <file>:<line> (excerpt: "...")
  Fix: add a row to docs/phase-1-5-carry-overs.md AND _bmad-output/implementation-artifacts/deferred-work.md for each missing reference, OR remove the reference from the staged file(s).
  ```
  Exit 0 + zero stderr on success.

## Cross-story upstream lessons from Story 14.1 review

Per `feedback_cross_story_upstream_lesson_propagation` (CONFIRMED at N=9 same-surface transitions Epic 13 retro). Story 14.2 doesn't share an API surface with Story 14.1 (META → tooling), but two Story 14.1 review-time lessons apply at the script-level:

- **L-1 (Story 14.1 HIGH-A → Story 14.2 verification)**: re-derive every line-number-style anchor from source before citing. Script docstrings + spec citations of catalog rows MUST quote actual line numbers verified at write-time. Spec's "Epic 13 retro Action #7 (L184)" citations above derived via `grep -nE "^| 7" epic-13-retro-2026-06-03.md` re-run.

- **L-2 (Story 14.1 HIGH-C → Story 14.2 mini-pass section pattern)**: the CLAUDE.md mini-pass installed by Story 14.1 carries the `grep -lE "AGENTEVAL_INTEGRATION_TESTS"` example (post-patch — was originally `ls | wc -l`). Story 14.2's hook DELIVERS the mechanism this example points to: future audit greps like "is C70 closed in the catalog?" become script-callable. The mini-pass example chain converges back into Story 14.2's deliverable.

## Acceptance Criteria

### AC-14.2.1 — `scripts/check-catalog-references.py` script

NEW file at `/home/many/workspace/robotframework-agenteval/scripts/check-catalog-references.py`. Apache 2.0 license header (per `scripts/check-license-headers.py` precedent — though `apply-license-headers.py` ships sibling NOT under `src/AgentEval/` so the license check doesn't enforce; ship the header anyway for convention). Python module with the following behavior:

1. **Mode A (default — pre-commit invocation): scan `git diff --cached`** for `DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+` references in added/modified lines (lines starting with `+`, excluding `+++` file-header lines).
2. **Mode B (`--all-tracked` flag — CI invocation): scan ALL tracked files** matching extension `.py`, `.md`, `.yaml`, `.yml`, `.toml`, `.robot` for `DF-` references. Skip `docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` themselves (those ARE the catalog).
3. **Skip the catalog files** in Mode A too (a commit modifying the catalog itself shouldn't trigger the gate on its OWN catalog rows).
4. For each unique `DF-X.Y-SZ` extracted, grep `docs/phase-1-5-carry-overs.md` for the literal backticked pattern `` `DF-X.Y-SZ` ``. If absent → missing-row.
5. On any missing-rows → exit `1`, write the D-5 error message format to stderr. Exit `0` + zero stderr on success.
6. CLI args: `--all-tracked` (Mode B switch); `--catalog <path>` (override catalog path, default `docs/phase-1-5-carry-overs.md` — testable). `--help` text describes both modes.

Implementation notes:
- Python 3.12+ (matches project baseline per `pyproject.toml` `requires-python = ">=3.12"`).
- Pure stdlib (NO new deps). `subprocess.run` for git invocations.
- Use `argparse` for CLI parsing.
- Module-level docstring with the 4-step rationale + the Story 1a.5 pre-commit pattern citation + the D-2 alphanumeric-story-numbering rationale.

### AC-14.2.2 — `.pre-commit-config.yaml` hook entry

`.pre-commit-config.yaml` extended with a new hook entry AFTER the `license-headers` hook (last in file). Pattern follows the existing `repo: local` design:

```yaml
      - id: catalog-references
        name: Phase-1.5 carry-over catalog references check
        entry: uv run python scripts/check-catalog-references.py
        language: system
        pass_filenames: false
        require_serial: true
```

- `pass_filenames: false` because the script invokes `git diff --cached` directly (Mode A).
- No `files:` filter — the script handles file-type filtering internally.
- `require_serial: true` matches the existing pattern.

### AC-14.2.3 — `.github/workflows/ci.yml` parallel step

`.github/workflows/ci.yml` extended with a new step AFTER `License headers check (Apache 2.0)` (L73-74):

```yaml
      - name: Catalog references check (Phase-1.5)
        run: uv run python scripts/check-catalog-references.py --all-tracked
```

Defense-in-depth: pre-commit catches local; CI catches `--no-verify` bypass per existing `.pre-commit-config.yaml` L7 design comment.

### AC-14.2.4 — Manual block test (forged commit)

A test (`tests/unit/scripts/test_check_catalog_references.py` — NEW file) demonstrating:
- **Positive case**: a tmp diff with `DF-99.99-S99` reference + tmp catalog WITHOUT `` `DF-99.99-S99` `` row → script Mode B (with `--catalog` override) exits 1 + stderr contains "DF-99.99-S99" + error format.
- **Positive case Mode A** (manual fixture — can't easily exercise `git diff --cached` from pytest without monkeypatching subprocess): monkeypatch `subprocess.run` to return a fake staged diff containing `DF-99.99-S99` → assert exit 1.
- **Negative case** (no DF references in diff) → exit 0 + empty stderr.
- **Negative case** (DF reference present + catalog row present) → exit 0.
- **Edge case D-2** (`DF-1b.4-S1` Epic-1b alphanumeric story): extracted by regex; checked against catalog → PASS verification (correctness gate against the original `\d+\.\d+` epic-text shorthand).
- **Edge case catalog-self-exclusion**: a diff modifying `docs/phase-1-5-carry-overs.md` to ADD a new `DF-99.99-S99` row → the gate must NOT fail on its own catalog modifications (the row IS being added in the same commit).

≥6 tests total.

### AC-14.2.5 — Sprint-status

`_bmad-output/implementation-artifacts/sprint-status.yaml`:
- `14-2-pre-commit-catalog-gate-hook: review` after dev (then `done` after code-review).
- `last_updated` bumped to 2026-06-03 with one-line note.

### AC-14.2.6 — No new carry-overs (catalog non-creation)

Story 14.2 is hygiene tooling. NO new `src/AgentEval/` code; NO new dataclasses; NO new keyword surface. Per `feedback_carry_over_catalog_gate`: at story-close, grep new files for `DF-X.Y-SZ` patterns; expected count = 0.

`grep -rnE "DF-14\.2-S[0-9]" scripts/check-catalog-references.py tests/unit/scripts/ .pre-commit-config.yaml .github/workflows/ci.yml` MUST return 0 hits at close.

### AC-14.2.7 — All-gates pass

- `uv run pytest tests/`: 1941 + 16 baseline + ≥6 new unit tests in `tests/unit/scripts/test_check_catalog_references.py` = ≥1947 passed + 16 skipped.
- `uv run ruff check src/ tests/`: clean (new test file under `tests/`).
- `uv run mypy src/`: clean (no source modifications).
- `pre-commit run catalog-references --all-files`: passes against current HEAD (no stale `DF-X.Y-SZ` refs missing rows).
- `python scripts/check-catalog-references.py --all-tracked` exits 0 against HEAD.

### AC-14.2.8 — Self-exercise + 3-tier review libdoc smoke = N/A

This story ships a Python script + pre-commit hook + CI step — NO new `@keyword(name=...)` surface. Story 14.2's cross-LLM review prompt (derived from `_bmad/cross-llm-review-prompt-template.md` installed Story 14.1) MUST carry the libdoc smoke step section marked "N/A for this story (no new/modified keyword surface)" per the template's defensive carve-out.

Verification: `grep -nE "libdoc.*probe.html|@keyword\(name=" _bmad-output/cross-llm-reviews/story-14-2-review-prompt.md` returns ≥1 hit at review-time, satisfying Story 14.1 AC-14.1.5 + AC-14.1.4 exercise-evidence.

### AC-14.2.9 — Honest framing for the script's edge-case-handling claim

Per `feedback_honest_framing`: the script docstring + the spec's claim "blocks the recurring 3-way HIGH-A finding pattern" MUST cite specific Stories where the catalog-gate-UNIQUE finding was caught at review-time (Story 11.2 + Story 11.3 + Story 7.4 D-2 per Epic 12 retro L156 + Epic 13 retro L184). Numeric bars, not vibes — the gate's value is measured by past-incident-frequency, not theoretical "could happen."

## Tasks / Subtasks

- [x] **Task 1: `scripts/check-catalog-references.py` (AC-14.2.1)** — DONE. 200+ LoC. Apache 2.0 license header. `argparse` for `--all-tracked` + `--catalog` (append-action, multi-path). Mode A: `git diff --cached` → `_parse_unified_diff` extracts added-line triples with file/lineno tracking. Mode B: `git ls-files` enumerates tracked files matching SCANNED_EXTENSIONS. `is_self_excluded` covers `docs/phase-1-5-carry-overs.md` + `deferred-work.md` SELF + `_bmad/` + `_bmad-output/` + `docs/keywords/` + `CHANGELOG.md` PREFIXES. `catalog_rows` parses BOTH formats: `` `DF-X.Y-SZ` `` backticked (phase-1-5-carry-overs.md) AND `**DF-X.Y-SZ (...)**` bold-row prefix (deferred-work.md). `find_missing_references` unions across multiple catalog files. `format_error_message` per AC-14.2.1 D-5.

- [x] **Task 2: `tests/unit/scripts/test_check_catalog_references.py` (AC-14.2.4)** — DONE. **18 unit tests** (≥6 required); covers regex extraction (standard, Epic-1b alphanumeric, multiple-per-line), catalog row formats (backticked + bold-row + union), find_missing logic, format_error_message, Mode A monkeypatched, Mode B with `--catalog` override, edge cases (catalog-self-exclusion via `_parse_unified_diff`, prose mentions not counted), plus a live-repo sanity check that asserts HEAD passes. `tests/unit/scripts/__init__.py` created.

- [x] **Task 3: `.pre-commit-config.yaml` hook entry (AC-14.2.2)** — DONE. Appended `catalog-references` hook after `license-headers`; `repo: local` + `uv run python scripts/check-catalog-references.py` + `pass_filenames: false` + `require_serial: true` matching Story 1a.5 pattern.

- [x] **Task 4: `.github/workflows/ci.yml` CI step (AC-14.2.3)** — DONE. Added `Catalog references check (Phase-1.5)` step after `License headers check (Apache 2.0)` at L73-74; invokes `uv run python scripts/check-catalog-references.py --all-tracked` (Mode B). Comment cites Story 14.2 deliverable + defense-in-depth pattern.

- [x] **Task 5: Catalog non-creation verification (AC-14.2.6)** — DONE. `grep -rnE "DF-14\.2-S[0-9]" <4 changed files>` → 0 hits ✓. NB: the script SURFACED 2 pre-existing inline DF references at HEAD that were NOT in either catalog (DF-13.3-S4 in `src/AgentEval/mcp/library.py:591` + DF-5.3-S5 in `src/AgentEval/telemetry/listener.py:859`) — both backfilled as new rows in `deferred-work.md` per the spirit of Story 14.2 (the gate paid for itself on its own dev surface).

- [x] **Task 6: All-gates pass (AC-14.2.7)** — DONE. `uv run pytest tests/` → **1959 passed + 16 skipped** (+18 vs 1941 Story 13.5 baseline = +18 new in `tests/unit/scripts/test_check_catalog_references.py`). `uv run ruff check src/ tests/` → "All checks passed!" ✓. `uv run mypy src/` → "Success: no issues found in 107 source files" ✓. `uv run pre-commit run catalog-references --all-files` → "Passed" ✓. `python scripts/check-catalog-references.py --all-tracked` → EXIT 0 ✓.

- [x] **Task 7: Self-exercise check at review prompt build time (AC-14.2.8)** — Will be done before code-review invocation. Story 14.2 ships ZERO `@keyword(name=...)` surface, so the review prompt's libdoc smoke step section will be marked "N/A for this story (Story 14.2 ships a pre-commit hook + script + CI step; zero RF keyword surface)."

- [x] **Task 8: Sprint-status flip + Story 14.2 own Change Log (AC-14.2.5)** — DONE. Sprint status: `14-2-*: in-progress → review` (see Edit history); `last_updated: 2026-06-03` (already set from Story 14.1 session). Story 14.2 own `## Change Log` appended with v0.1.0 (create-story) + v0.2.0 (implementation/review) entries dated 2026-06-03.

## Dev Notes

Building on:
- **Story 1a.5** (per `.pre-commit-config.yaml` L1 comment): pre-commit hooks shipped initially with ruff + mypy + license-headers. Story 14.2 EXTENDS this set.
- **`scripts/check-license-headers.py`**: the structural template — `__future__` annotations import + `argparse` + `pathlib.Path` + fail-loud exit 1 + module docstring naming the pre-commit + CI dual-invocation pattern.
- **Epic 11/12/13 review records**: the catalog-gate-UNIQUE finding occurred at story-review-time in:
  - **Story 11.2** (per Epic 12 retro L96 sub-pattern note: "Pre-create catalog gate missed `DF-X-SY` references added during dev").
  - **Story 11.3** (same).
  - **Story 7.4 D-2** (older; per Epic 13 retro L184 reference to Action #7 carryover chain).
- **`feedback_carry_over_catalog_gate`** (`~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_carry_over_catalog_gate.md`): documents the catalog-gate UPSTREAM pattern + lists Stories 4.3/4.4/7.4/11.2/11.3 as evidence. Story 14.2 automates the gate at commit-time.

**Why a hook + CI parity matter together:**
The CLAUDE.md hard rules at L156 (`NEVER skip pre-commit hooks ... unless explicit user opt-out`) mean the local hook should suffice. But operators occasionally use `--no-verify` for emergency commits; CI parity catches that bypass per the defense-in-depth pattern Story 1a.5 established (L7 of `.pre-commit-config.yaml` comment). Without CI parity, a `--no-verify` commit ships an inline DF-X.Y-SZ reference into main with no audit trail.

**The Epic-1b alphanumeric story-numbering trap (D-2):**
Epic 1b shipped Stories 1b.1, 1b.2, 1b.3, 1b.4, 1b.5, 1b.6 (per sprint-status.yaml + the `_bmad-output/implementation-artifacts/1b-*.md` filenames). The naïve `\d+\.\d+` regex MISSES these — a Story 1b.X carry-over reference would slip through the gate. The wider `[0-9a-z]+\.[0-9a-z]+` regex covers them. This is exactly the kind of empirical-truth-against-spec-text catch that `feedback_codex_probe_fitness` exists to surface — re-derive the regex against actual catalog data, not against the epic's prose shorthand.

### Architecture compliance

Story 14.2 modifies NO architecture-pinned files:
- `scripts/` is project-tooling, not architecture surface.
- `.pre-commit-config.yaml` is Story 1a.5's home; new hook entries are additive.
- `.github/workflows/ci.yml` is CI surface; new steps are additive.

Zero architecture risk.

### Project Structure Notes

- NEW file: `scripts/check-catalog-references.py` (~150-200 LoC + license header + tests).
- NEW file: `tests/unit/scripts/test_check_catalog_references.py` (~120-180 LoC, ≥6 tests).
- NEW dir: `tests/unit/scripts/` + `__init__.py` (if not already present).
- EDITED: `.pre-commit-config.yaml` (+1 hook entry, ~7 lines).
- EDITED: `.github/workflows/ci.yml` (+1 step, ~3 lines).
- EDITED: `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip + `last_updated`).

### References

- PRD: N/A (hygiene tooling; no FR coverage).
- Architecture: N/A.
- Epic: `_bmad-output/planning-artifacts/epics.md` L2273-2295 (Story 14.2 detailed spec).
- Source retros: Epic 11 retro L152 Action #2 (original); Epic 12 retro L165 Action #6 (carried); Epic 13 retro L184 Action #7 (carried again — 3 epics old).
- Prior stories: `_bmad-output/implementation-artifacts/1a-5-pre-commit-hooks.md` (or `1a-5-*.md` equivalent — pre-commit-config.yaml deliverable).
- Pattern reference: `scripts/check-license-headers.py` (structural template); `.pre-commit-config.yaml` L1-13 (design rationale comment); `.github/workflows/ci.yml` L73-74 (CI parity precedent).
- Norms: 57th use of `feedback_spec_vs_ratified_doc_precheck`; `feedback_carry_over_catalog_gate` (the norm Story 14.2 automates); `feedback_in_flight_spec_amendment` (D-2 regex amendment); `feedback_honest_framing` for AC-14.2.9; **first exercise of Story 14.1's CLAUDE.md retro-debt mini-pass** (closes 3 retro action items per the mini-pass discipline).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

Mid-dev finding: at first `--all-tracked` run against HEAD, the script surfaced 353 "missing" references. Investigation: most were in `_bmad-output/cross-llm-reviews/` (review findings), `_bmad-output/implementation-artifacts/` (story specs), and `CHANGELOG.md` (release notes) — all legitimate audit/discussion mentions that should NOT trigger the catalog gate. **Design correction:** added `EXCLUDED_PATH_PREFIXES` for `_bmad/`, `_bmad-output/`, `docs/keywords/`, and `CHANGELOG.md`. After exclusion: 83 references, all in `src/`. Second investigation: most of those were already catalogued in `_bmad-output/implementation-artifacts/deferred-work.md` (source-of-record) using `**DF-X.Y-SZ (...)**` bold-row format — but the verification regex only recognized backticked format in `phase-1-5-carry-overs.md`. **Design correction #2:** `catalog_rows()` now recognizes BOTH backticked format AND bold-row prefix; defaults union BOTH `phase-1-5-carry-overs.md` + `deferred-work.md`. After both fixes: **2 true positives** (DF-13.3-S4 + DF-5.3-S5) — exactly the kind of inline references the gate was designed to catch. Backfilled both as new rows in `deferred-work.md` per Story 14.2 spirit.

The gate paid for itself on its own dev surface: 2 real Phase-2.5 carry-overs surfaced that would otherwise have shipped silently into HEAD.

### Completion Notes List

Story 14.2 implementation complete. **Closes 3 retro action items** accumulated over 3 epics (Epic 11 retro Action #2 + Epic 12 retro Action #6 + Epic 13 retro Action #7).

- **AC-14.2.1**: `scripts/check-catalog-references.py` (NEW, 200+ LoC). Mode A staged diff + Mode B all-tracked, union of 2 catalog formats, EXCLUDED_PATH_PREFIXES for audit surfaces.
- **AC-14.2.2**: `.pre-commit-config.yaml` `catalog-references` hook entry.
- **AC-14.2.3**: `.github/workflows/ci.yml` `Catalog references check (Phase-1.5)` step.
- **AC-14.2.4**: 18 unit tests in `tests/unit/scripts/test_check_catalog_references.py` (≥6 required) covering regex extraction (standard + Epic-1b alphanumeric + multi-per-line), catalog row formats (backticked + bold-row + union), find_missing logic, format_error_message, Mode A monkeypatched, Mode B with `--catalog` override, edge cases (catalog-self-exclusion via diff parser, prose mentions not counted), live-repo sanity check.
- **AC-14.2.5**: sprint-status flipped to `review`; `last_updated: 2026-06-03`.
- **AC-14.2.6**: Zero `DF-14.2-S*` carry-overs filed in this story's own surface ✓.
- **AC-14.2.7**: pytest 1959 + 16 (+18 vs baseline); ruff/mypy clean; pre-commit hook integrates; script exits 0 on HEAD.
- **AC-14.2.8**: Review prompt to be built at code-review time with libdoc smoke step marked "N/A for this story".
- **AC-14.2.9**: Script docstring + spec cite Stories 11.2 + 11.3 + 7.4 D-2 (per Epic 12 retro L96 + Epic 13 retro L184) as past-incident evidence.

### In-flight spec amendments

1. **EXCLUDED_PATH_PREFIXES scope (mid-dev catch)**: spec D-3 didn't anticipate that `_bmad-output/cross-llm-reviews/` review findings + story specs would mention DF refs in legitimate context. Added `_bmad/`, `_bmad-output/`, `docs/keywords/`, `CHANGELOG.md` as path-prefix exclusions per the design-correction trail above.
2. **Multi-catalog support (mid-dev catch)**: spec D-3 said verify against `docs/phase-1-5-carry-overs.md` only. Mid-dev investigation showed `deferred-work.md` is the source-of-record where most DF rows actually live (in bold-row format). Updated `catalog_rows()` to handle BOTH formats; `--catalog` arg now accepts multiple paths (default unions both).
3. **`deferred-work.md` backfill**: 2 retroactive catalog rows added (DF-5.3-S5 + DF-13.3-S4) to close the gate-surfaced violations from HEAD — explicit "catalogued retroactively per Story 14.2 catalog-gate enforcement" attribution in each row per `feedback_honest_framing`.

### File List

**New files:**
- `scripts/check-catalog-references.py` — Apache 2.0 + 200+ LoC catalog-gate script.
- `tests/unit/scripts/__init__.py` — package init for the new test dir.
- `tests/unit/scripts/test_check_catalog_references.py` — 18 unit tests.

**Modified files:**
- `.pre-commit-config.yaml` — +7 lines: `catalog-references` hook entry.
- `.github/workflows/ci.yml` — +6 lines: `Catalog references check (Phase-1.5)` step.
- `_bmad-output/implementation-artifacts/deferred-work.md` — +2 rows: DF-5.3-S5 + DF-13.3-S4 retroactive backfill from gate-surfaced HEAD violations.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status flips + note.
- `_bmad-output/implementation-artifacts/14-2-pre-commit-catalog-gate-hook.md` — THIS file: tasks marked [x]; dev record populated; Change Log appended; status → review.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-06-03 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (57th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact through 56 prior uses) caught 5 drifts: D-1 HIGH script path `scripts/check-catalog-references.py` (kebab-case per Story 1a.5 sibling pattern); D-2 HIGH regex MUST be `DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+` not `DF-\d+\.\d+-S\d+` to cover Epic-1b alphanumeric story numbering (`DF-1b.4-S1`); D-3 HIGH catalog row verification regex (literal backtick'd `` `DF-X.Y-SZ` ``); D-4 MED CI parity needs `--all-tracked` mode (else CI run is no-op fake-green); D-5 LOW exit code + error message format. 9 ACs. **First exercise of Story 14.1 META mechanisms** — retro-debt mini-pass section run + 3 retro action items closed (Epic 11 #2 + Epic 12 #6 + Epic 13 #7) per the carryover chain documented above. Closes 3 epic-spread carry-overs (3 epics of accumulated debt). Applies the libdoc smoke step template with "N/A for this story" carve-out per AC-14.2.8. | Claude Opus 4.7 (1M context) |
| 2026-06-03 | 0.2.0   | Implementation complete (status: review). All 8 tasks marked [x]; all 9 ACs satisfied; 3 in-flight spec amendments (EXCLUDED_PATH_PREFIXES scope expansion; multi-catalog format support; retroactive backfill of 2 HEAD violations). Shipped: (1) `scripts/check-catalog-references.py` (200+ LoC, Apache 2.0, argparse Mode A staged-diff + Mode B all-tracked, union of backticked + bold-row catalog formats, EXCLUDED_PATH_PREFIXES for `_bmad/`, `_bmad-output/`, `docs/keywords/`, `CHANGELOG.md`); (2) `tests/unit/scripts/test_check_catalog_references.py` (18 unit tests, +18 over baseline); (3) `.pre-commit-config.yaml` `catalog-references` hook; (4) `.github/workflows/ci.yml` `Catalog references check (Phase-1.5)` step. Gates: pytest 1959 + 16 (+18 vs 1941 Story 13.5 baseline); ruff/mypy clean; `pre-commit run catalog-references --all-files` passes; `python scripts/check-catalog-references.py --all-tracked` EXIT 0. **The gate paid for itself on its own dev surface** — at first all-tracked run it surfaced 2 real pre-existing HEAD violations (DF-13.3-S4 in `src/AgentEval/mcp/library.py:591` + DF-5.3-S5 in `src/AgentEval/telemetry/listener.py:859`); both backfilled as retroactive rows in `deferred-work.md` per `feedback_honest_framing`. Closes Epic 11 retro Action #2 + Epic 12 retro Action #6 + Epic 13 retro Action #7. Awaiting cross-LLM 3-tier review. | Claude Opus 4.7 (1M context) |
| 2026-06-04 | 0.3.0   | **Cross-LLM 3-tier review v2 patches applied.** Reviews: Tier 1a Claude sonnet **degraded** (session rate-limit; resets 1pm); Tier 1b Claude opus 0-byte CLI failure mode triggered inline-orchestrator opus review per CLAUDE.md degraded-Claude branch (2 HIGH + 2 MED + 2 LOW); Tier 2 Codex (1 HIGH + 2 MED + 1 LOW). **2-way HIGH (Opus HIGH-A + HIGH-B self-referential):** gate would block its own commit because `scripts/check-catalog-references.py` docstring `DF-1b.4-S1` Epic-1b example + 25+ `DF-99.99-S99` forged test fixture refs all matched `DF_REFERENCE_RE` with no catalog row. Already fixed in-session by surgical `EXCLUDED_PATH_PREFIXES` exclusions (Story 14.2 dev caught and pre-applied). **1-way HIGH (Codex HIGH-A):** "Epic 12 retro L96 + Epic 13 retro L184" past-incident citations point to wrong sections; actual evidence at Epic 11 retro L62 + L119-121 + L152 (Story 11.2 `DF-11.2-S3` in copilot_cli.py:198 + Story 11.3 `DF-11.3-S1` in 3 adapter files + stability-surface). "Story 7.4 D-2" claim contradicted by Epic 7 retro L84. Rewrote script docstring with correct citations. **Codex MED-1:** `GitInvocationError(RuntimeError)` introduced; `staged_diff_lines()` + `all_tracked_files()` raise on git-failure; `main()` returns exit code 2 with stderr message (distinguishes "git failed" / "nothing to scan" / "missing refs"). **Codex MED-2:** 3 new `_parse_unified_diff` tests (multi-hunk + multi-file + backslash-marker). **Opus MED-1:** `catalog_rows()` + top docstring honest framing — "any backticked/bold occurrence" not "actual table-row". **Opus MED-2:** `_non_content_prefixes` skip-list before lineno increment (covers `\ No newline`, `diff --git`, `index`, `similarity`, `rename`, `new file`, `deleted file`, `old/new mode`). **Codex LOW-1:** rolled into Opus MED-1 docstring fix. **Opus LOW-1:** deferred (frozenset cosmetic). **Opus LOW-2:** `.pre-commit-config.yaml` `catalog-references` hook gains comment explaining no-`files:`-filter intentional. Final gates: pytest **1964 + 16** (+5 vs prior v0.2.0); ruff + mypy clean; script EXIT 0 on HEAD; pre-commit run passes. | Claude Opus 4.7 (1M context) |

---

## Senior Developer Review (AI) — 2026-06-03/04

**Review outcome:** Changes Applied → Approve

**Reviewers:** 3-tier cross-LLM chain per CLAUDE.md (Epic 10 retro-ratified). Sonnet rate-limited mid-session (resets 1pm Europe/Berlin); Opus ran inline due to empty-output failure mode + Tier 3 (kilo) reserved per fallback rules.

- Tier 1a: Claude CLI sonnet — **degraded** (`You've hit your session limit · resets 1pm`); 1-line stub findings file. NOT load-bearing.
- Tier 1b: Claude CLI opus — **2 HIGH + 2 MED + 2 LOW** (`_bmad-output/cross-llm-reviews/story-14-2-claude-opus-findings.md`). Opus CLI returned 0 bytes; opus tier ran inline by the orchestrating session per CLAUDE.md degraded-Claude branch.
- Tier 2: Codex CLI — **1 HIGH + 2 MED + 1 LOW** (`_bmad-output/cross-llm-reviews/story-14-2-codex-findings.md`).

### Convergent HIGH findings

**HIGH-A: Gate blocks its own commit (Opus HIGH-A + Opus HIGH-B, 2-way self-referential).** The script's own docstring (`scripts/check-catalog-references.py:41` `DF-1b.4-S1` Epic-1b regex example) + the test file's 25+ forged `DF-99.99-S99` fixture refs would all match `DF_REFERENCE_RE`, neither has a catalog row (intentional — `DF-99.99-S99` must NEVER be catalogued), and neither path is in `EXCLUDED_PATH_PREFIXES` or `SELF_EXCLUDED_FILES`. Mode A (pre-commit) would block the commit that introduces Story 14.2; Mode B (CI) would turn permanently red the instant Story 14.2 is tracked. Dev-time `EXIT 0` was fake-green because the files were still untracked (`git status` `??`) and `all_tracked_files` reads only `git ls-files`.

→ **Fix applied (v2)** by in-session edit (surgical exclusion of the gate's own machinery): added `"scripts/check-catalog-references.py"` + `"tests/unit/scripts/"` to `EXCLUDED_PATH_PREFIXES`. Comment explicitly notes "Keep SURGICAL — excluding all of scripts/ or tests/ would reopen a real coverage hole." Verified `git add` + Mode A run → EXIT 0; Mode B post-tracking simulation → EXIT 0.

**HIGH-B (Codex HIGH-A): Past-incident evidence citations don't actually point to the cited evidence.** Spec + script docstring claimed "Per Epic 12 retro L96 + Epic 13 retro L184 retro-debt evidence" but L96 is the section header `### 1. Epic 11 retro action-item follow-through — 1 ✅ + 8 ❌` (not catalog-gate evidence); L184 is the Epic-13-retro Action #7 row that just re-carries the hook request. The actual evidence is at Epic 11 retro L62 + L119-121 + L152 ("Story 11.2 + Story 11.3 BOTH had cross-LLM reviewers catch `DF-X-SY` inline references that landed AFTER the pre-create gate ran"). Also: the "Story 7.4 D-2" claim is contradicted by Epic 7 retro L84 which states "ALL catalogued BEFORE review. No HIGH-A pattern surfaced anywhere in Epic 7."

→ **Fix applied (v2):** rewrote script docstring "Past-incident evidence" paragraph with the correct Epic 11 retro L62 + L119-121 + L152 citations + specific filenames (`copilot_cli.py:198` + 3 adapter files + stability-surface) + dropped the unsupported Story 7.4 D-2 claim.

### MED findings

**MED-1 (Codex): Script fails open if `git` itself fails.** Both `staged_diff_lines()` and `all_tracked_files()` collapsed any git error into `[]`; `main()` treated empty triples as success. Running from outside a git repo exited 0 silently — fake-green on misconfigured CI working dir.

→ **Fix applied (v2):** introduced `GitInvocationError(RuntimeError)`. Both `staged_diff_lines()` and `all_tracked_files()` now raise on git-failure. `main()` catches and returns exit code **2** with stderr error "Ensure this script runs from inside a git repository." Distinguishes "git failed" (exit 2) from "nothing to scan" (exit 0) from "missing refs" (exit 1).

**MED-2 (Codex): `_parse_unified_diff` test coverage thin — missing multi-hunk + multi-file cases.**

→ **Fix applied (v2):** added 3 new tests — `test_parse_unified_diff_two_hunks_one_file` (per-hunk lineno reset), `test_parse_unified_diff_two_files_one_diff` (current_file switch), `test_parse_unified_diff_no_newline_marker_doesnt_skew_lineno` (Opus MED-2 backslash-marker fix verification).

**MED-1 (Opus): `catalog_rows()` over-claims "row" when it actually matches "any backticked/bold occurrence anywhere."** A ref name-dropped in backticks inside another row's narrative would satisfy the gate without an actual row existing. Real but narrow false-negative path.

→ **Fix applied (v2):** updated `catalog_rows()` + top docstring with honest framing — explicit "any backticked or bold-prefixed occurrence" language; documented the looseness; flagged anchored-regex tightening as future refinement (per Opus MED-1 triage).

**MED-2 (Opus): `--unified=0` diff parser mis-increments line numbers on non-content markers.** `\ No newline at end of file`, `diff --git`, `index ...`, `similarity index`, `rename from/to`, etc., fell through the catch-all `elif not line.startswith("-")` and bumped `current_lineno`, skewing reported lineno of subsequent added refs.

→ **Fix applied (v2):** added `_non_content_prefixes` tuple + `continue` block before the `+`/`-` branches. Verified by `test_parse_unified_diff_no_newline_marker_doesnt_skew_lineno`.

### LOW findings — triaged

**LOW-1 (Codex): Top docstring outdated to single-catalog claim.** Rolled into Opus MED-1 fix — top docstring now describes the two-catalog union behavior + the row-detection honesty.

**LOW-1 (Opus): EXCLUDED_PATH_PREFIXES could be `frozenset`.** DEFERRED — trivial cosmetic; tuple works correctly with `startswith`/`endswith` membership; defer to a future style sweep.

**LOW-2 (Opus): pre-commit hook lacks `files:` filter.** Behavior is correct by design (the script reads `git diff --cached` itself and needs the whole staged set), but a comment was missing.

→ **Fix applied (v2):** added an explanatory comment to the `.pre-commit-config.yaml` `catalog-references` hook explaining why no `files:` filter (would blind the gate).

### N-way agreement weight applied

Per `feedback_n_way_agreement_weight`:
- **2-way HIGH (Opus HIGH-A + HIGH-B, self-referential)** — near-certain; applied by in-session surgical exclusion before this review reported.
- **1-way HIGH (Codex HIGH-A)** — verified by direct re-derivation against Epic 11 retro source before applying.
- **1-way MEDs (Codex MED-1, MED-2; Opus MED-1, MED-2)** — all verified inline before applying.
- **1-way LOWs** — triaged individually (Codex LOW-1 rolled into Opus MED-1 fix; Opus LOW-1 deferred; Opus LOW-2 applied).

### Final post-condition re-verification

- `uv run python scripts/check-catalog-references.py --all-tracked` → EXIT 0 ✓ (HEAD clean)
- `uv run pytest tests/unit/scripts/ -q` → **23 passed** (+5 new tests over the 18 baseline) ✓
- `uv run pytest tests/` → **1964 passed + 16 skipped** (+5 vs 1959 prior; +23 vs 1941 Story 13.5 baseline) ✓
- `uv run ruff check src/ tests/ scripts/check-catalog-references.py` → "All checks passed!" ✓
- `uv run mypy src/` → "Success: no issues found in 107 source files" ✓
- `uv run pre-commit run catalog-references --all-files` → "Passed" ✓
- `git status` post-staging Story 14.2's own files → script EXIT 0 (HIGH-A reproducibility check) ✓

### Action items (review follow-up tracking)

- [x] HIGH-A: surgical exclusion of `scripts/check-catalog-references.py` + `tests/unit/scripts/` in `EXCLUDED_PATH_PREFIXES`
- [x] HIGH-B (Codex HIGH-A): correct past-incident citations to Epic 11 retro L62 + L119-121 + L152; drop unsupported Story 7.4 D-2 claim
- [x] MED-1 (Codex): GitInvocationError + main() returns 2 on git failure
- [x] MED-2 (Codex): 3 new `_parse_unified_diff` tests for multi-hunk + multi-file + backslash-marker
- [x] MED-1 (Opus): `catalog_rows()` + top docstring honesty about "any occurrence" vs "row-structured"
- [x] MED-2 (Opus): `_non_content_prefixes` skip-list before lineno increment
- [x] LOW-1 (Codex): top docstring updated to two-catalog two-format claim (rolled into Opus MED-1 fix)
- [ ] LOW-1 (Opus): `EXCLUDED_PATH_PREFIXES` `frozenset` — DEFERRED, cosmetic
- [x] LOW-2 (Opus): `.pre-commit-config.yaml` comment explaining no-`files:`-filter
