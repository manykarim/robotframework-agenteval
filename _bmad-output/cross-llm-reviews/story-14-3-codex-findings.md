## HIGH

No HIGH findings.

## MED

### MED-1 — The grep-parity helper no longer matches the parser it is supposed to validate

- **File:** `tests/integration/recipes/test_all_recipes_dryrun.py:83`, `tests/integration/recipes/test_all_recipes_dryrun.py:406`
- **Why it matters:** `extract_robotframework_blocks()` now intentionally accepts ```` ```robotframework ```` fences of length `>= 3` via `_ROBOT_FENCE_OPEN_RE`, but `test_extract_robotframework_blocks__counts_match_grep()` still counts only the literal triple-backtick opener with `grep -cE '^```robotframework'`. A future recipe that uses a 4-backtick outer fence to embed an inner ```python example will be parsed correctly by the helper and then falsely fail the parity test.
- **Concrete fix:** Replace the `grep` count with the same regex the parser uses, or widen the shell matcher to the 3+-backtick form so the test and implementation share one definition of “open robot fence.”

### MED-2 — The known-broken skip-list is not verified against the actual failing block set

- **File:** `tests/integration/recipes/test_all_recipes_dryrun.py:206`, `tests/integration/recipes/test_all_recipes_dryrun.py:238`, `tests/integration/recipes/test_all_recipes_dryrun.py:307`
- **Why it matters:** The passing-floor logic is derived from `len(_KNOWN_BROKEN_BLOCKS)`, and the parametrized test unconditionally skips any matching `test_id`. There is no regression guard that proves those four IDs are still the only failing eligible blocks. If one recipe gets fixed and nobody removes its skip entry, the harness will keep under-testing silently; if a new eligible block starts failing, the floor math still looks “correct” until a human notices.
- **Concrete fix:** Add one audit test that dryruns every eligible block without consulting `_KNOWN_BROKEN_BLOCKS` and asserts `actual_failing_ids == set(_KNOWN_BROKEN_BLOCKS)`. That pins both halves of the claim: every listed block still fails, and no unlisted eligible block fails.

### MED-3 — The recipe-gallery README still describes the pre-Story-14.3 validation model

- **File:** `docs/recipes/README.md:36`, `docs/recipes/README.md:37`, `docs/recipes/README.md:44`
- **Why it matters:** The README still says every fenced `robotframework` block runs through `robot --dryrun` before shipment, that the all-recipes harness is only a Phase-1.5 work item, and that the carry-over catalog is at 71 rows. None of those are true at HEAD: Story 14.3 has shipped the harness, 12 blocks are intentionally classified out of dryrun, 4 eligible blocks are skip-listed under `DF-14.3-S1`, and the catalog row count is now higher.
- **Concrete fix:** Rewrite the validation section to reflect the shipped harness honestly: all fenced blocks are extracted, only dryrun-eligible blocks are executed, the four known-broken eligible blocks are catalogued under `DF-14.3-S1`, and the catalog-reference line should stop hard-coding the stale row count.

## LOW

### LOW-1 — The story spec still cites the C64 catalog row at the wrong line number

- **File:** `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md:24`, `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md:68`, `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md:205`
- **Why it matters:** The spec says C64 lives at `docs/phase-1-5-carry-overs.md` line 91, but the current row is at `docs/phase-1-5-carry-overs.md:88`. This is straightforward citation drift in a story that explicitly calls out source-line re-derivation as load-bearing.
- **Concrete fix:** Update the three `L91` references to `L88`, or better, drop the fragile line-number citation and point to `C64 / DF-8b.3-S1` by stable row ID instead.

## Verification Notes

- `uv run pytest tests/integration/recipes/test_all_recipes_dryrun.py -q` → `17 passed, 16 skipped`
- `uv run python scripts/check-catalog-references.py --all-tracked` → exit `0`
- Direct dryrun audit of all 8 eligible blocks confirmed the current failing set is exactly:
  - `03-tool-discoverability-cohort.md::block-0`
  - `05-dogfood-replacing-custom-tests.md::block-0`
  - `05-dogfood-replacing-custom-tests.md::block-1`
  - `07-first-mcp-server-test-tier-1.md::block-0`
