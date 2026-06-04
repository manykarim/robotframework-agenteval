# Story 14.2 — Claude Opus (Tier 1b) cross-LLM adversarial findings

**Reviewer:** Claude Opus 4.8 (`claude-opus-4-8`), performed **inline by the
orchestrating session** — the `claude -p --model opus` CLI invocation returned
**0 bytes** (empty-output failure mode; stderr: `no stdin data received in 3s`
— the prompt was piped via stdin which arrived empty). Per CLAUDE.md, Claude
CLI is therefore degraded for this story; this file is the Opus-tier review
produced directly with full repo access. Tier 3 (kilo/minimax) fired in
parallel per the degraded-Claude branch of the chain.

**Date:** 2026-06-03
**Scope:** `scripts/check-catalog-references.py`,
`tests/unit/scripts/test_check_catalog_references.py`, `.pre-commit-config.yaml`,
`.github/workflows/ci.yml`, `deferred-work.md` (+2 rows), story spec.

---

## HIGH

### HIGH-A — The catalog-gate blocks its own commit and turns CI permanently red (self-defeating gate) — BLOCKING, reproduced

**Files:** `scripts/check-catalog-references.py:41`,
`tests/unit/scripts/test_check_catalog_references.py` (lines 5, 47, 52, 75, 82,
84, 89, 91, 100, 108, 113, 164, 165, 169, 174, 177, 194, 224, 229, 244, 254,
269, 276).

The gate's own two new files contain literal `DF-X.Y-SZ` strings that match
`DF_REFERENCE_RE` and are NOT catalogued:

- `scripts/check-catalog-references.py:41` — docstring example `` `DF-1b.4-S1` ``.
- the test file — `DF-1b.4-S1` (many) and the forged fixture ref `DF-99.99-S99`
  (many).

Neither `DF-1b.4-S1` nor `DF-99.99-S99` has a catalog row (verified:
`grep 'DF-1b\.4-S1' docs/phase-1-5-carry-overs.md deferred-work.md` -> no match;
same for `DF-99.99-S99`). `DF-99.99-S99` is an intentional *forged* test ref and
MUST NEVER be catalogued; `DF-1b.4-S1` is an Epic-1b extraction example.

Both files live under `scripts/` and `tests/` — neither is in
`EXCLUDED_PATH_PREFIXES` nor `SELF_EXCLUDED_FILES`, and both match
`SCANNED_EXTENSIONS` (`.py`). Therefore:

- **Mode A (pre-commit):** the commit that introduces Story 14.2 stages these
  files; `git diff --cached` shows the refs as added lines -> gate exits 1 ->
  the pre-commit hook blocks its own commit. Reproduced:

  ```
  $ git add scripts/check-catalog-references.py tests/unit/scripts/...
  $ uv run python scripts/check-catalog-references.py
  ERROR: pre-commit catalog-gate found 25 inline DF-X.Y-SZ reference(s) without catalog rows ...
    - DF-1b.4-S1 in scripts/check-catalog-references.py:41 ...
    - DF-99.99-S99 in tests/unit/scripts/test_check_catalog_references.py:164 ...
  MODE_A_EXIT=1
  ```

- **Mode B (CI `--all-tracked`):** once the files are committed/tracked,
  `git ls-files` returns them, so CI exits 1 on every run -> CI goes permanently
  red. Reproduced (with files staged): `MODE_B_EXIT=1`, same 25 refs.

**Why dev saw a false EXIT 0:** during development the files are still untracked
(`git status` shows `??`). `all_tracked_files()` is built from `git ls-files`,
which excludes untracked files, so the dev-time `--all-tracked` run never scanned
the gate's own files. The green is an artifact of "not yet committed" and
evaporates the instant the story is committed. This is precisely the
fake-green-gate failure mode the review prompt's HIGH sections warn about.

**Concrete fix** — exclude the gate's own machinery (the canonical "file that
legitimately contains DF refs" — the gate's own tests/fixtures). In
`EXCLUDED_PATH_PREFIXES`:

```python
EXCLUDED_PATH_PREFIXES = (
    "_bmad/",
    "_bmad-output/",
    "docs/keywords/",
    "CHANGELOG.md",
    "scripts/check-catalog-references.py",  # this gate's own example refs
    "tests/unit/scripts/",                  # this gate's own forged fixtures
)
```

Keep the exclusion surgical (these two paths only) — do NOT exclude all of
`scripts/` or `tests/`, or you reopen a real coverage hole. After the fix, both
modes must exit 0 with the files staged. (Verified the rest of the tracked tree
is already clean, so these two paths are the only blockers.)

### HIGH-B — `test_main_passes_against_current_repo_state` is fake-green (per `feedback_test_name_assertion_match` + `feedback_dogfood_fake_green_precheck`)

**File:** `tests/unit/scripts/test_check_catalog_references.py:279-292`.

The test asserts `main(["--all-tracked"]) == 0` "against the live catalog." It
passes today only because the script + test file are untracked (HIGH-A root
cause). The moment Story 14.2 is committed, this test will assert-fail in CI
(`exit_code == 1`), and its own failure message ("the script surfaced a real
catalog-gate violation") will be misleading — the "violation" is the gate's own
fixtures, not a real carry-over. After the HIGH-A fix it will correctly stay
green. **Fix:** ship HIGH-A's exclusion; this test then verifies what its name
promises (clean tracked tree) rather than passing on an untracked-file artifact.

---

## MED

### MED-1 — `catalog_rows()` counts *any* backticked/bold occurrence, not actual table rows (docstring over-claims)

**File:** `scripts/check-catalog-references.py:91-114`.

`backticked_re` matches any backticked occurrence anywhere in the catalog file —
including prose mentions, "see also" cross-refs, or a reference cited in a
*different* row's narrative. The docstring says it returns refs "that have a row
in the catalog," and `test_catalog_rows_only_match_backticked_references`
reinforces "requires backtick wrapping." But a ref merely name-dropped in
backticks in `phase-1-5-carry-overs.md` would satisfy the gate without an actual
row. This is a real (if narrow) false-negative path. **Fix:** either (a) tighten
the docstring to say "any backticked/bold occurrence in a catalog file counts"
(honest framing — the check is occurrence-based, not row-structured), or (b)
anchor the regex to table-row / list-item start (`^\s*[|\-]`). Option (a) is the
lower-risk fix; document the looseness.

### MED-2 — `--unified=0` diff parser mis-increments line numbers on non-content markers

**File:** `scripts/check-catalog-references.py:150-180`.

The `elif not line.startswith("-")` branch treats every non-`+`/non-`-` line as a
context line and increments `current_lineno`. With `--unified=0` there are no
real context lines, but `\ No newline at end of file` markers hit this branch and
bump the counter. Impact is bounded — it only skews the reported line number of
refs that follow a `\ No newline` marker within the same hunk, never detection —
so MED-low. **Fix:** explicitly `continue` on lines starting with `\ `, `diff `,
or `index ` rather than letting them fall through to the increment branch.

---

## LOW

### LOW-1 — `EXCLUDED_PATH_PREFIXES` / `SELF_EXCLUDED_FILES` could be `frozenset`

`scripts/check-catalog-references.py:65-81`. Membership is tested via
`startswith`/`endswith` over the whole tuple, so `frozenset` wouldn't speed it
up, but signals "unordered membership set" intent more clearly. Trivial/optional.

### LOW-2 — pre-commit hook lacks a `files:` filter (runs on every commit)

`.pre-commit-config.yaml:48-53`. Unlike the `license-headers` precedent
(`files: ^src/AgentEval/.*\.py$`), the `catalog-references` hook has no `files:`
filter. This is correct by design (the script reads `git diff --cached` itself
and must see the whole staged set), but worth a one-line comment so a future
reader doesn't add a filter that would blind the gate.

---

## Verified clean (no finding)

- **Citations:** Epic 11 retro L152 = Action #2 (build pre-commit catalog-gate
  hook); Epic 12 retro L165 = Action #6; Epic 13 retro L184 = Action #7;
  `src/AgentEval/mcp/library.py:591` = DF-13.3-S4 model kwarg;
  `src/AgentEval/telemetry/listener.py:859` = DF-5.3-S5 identity provenance. No
  citation drift.
- **D-2 regex breadth:** `DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+` correctly matches
  Epic-1b `DF-1b.4-S1`; live corpus 83 (docs) / 106 (deferred-work) unique refs
  including `DF-1b.*`.
- **In-flight #3 backfill:** `DF-5.3-S5` (deferred-work.md:255) + `DF-13.3-S4`
  (deferred-work.md:395) present with honest retroactive attribution.
- **Test count:** 18 test functions, matches the claim (18 passed locally).
- **Self-exclusion of the two catalog files** works as designed.
- **Rest of the tracked tree** is catalog-clean.

---

## Verdict

**2 HIGH (1 blocking, reproduced) + 2 MED + 2 LOW.** HIGH-A is a release-blocker:
the story cannot be committed with its own hook enabled, and CI would go red on
the first post-merge run. HIGH-A + HIGH-B share one root cause and one fix
(surgical exclusion of the gate's own machinery files). Ratify HIGH-A/HIGH-B
inline before flipping `14-2-*` to `done`; MED-1 + MED-2 are cheap same-commit
follow-ons.
