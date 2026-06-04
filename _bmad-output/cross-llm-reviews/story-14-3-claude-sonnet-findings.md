# Story 14.3 — Claude Sonnet 4.6 (Tier-1a) adversarial review findings — v3 (current-state pass)

**Reviewer:** Claude Sonnet 4.6, in-session (Tier-1a substitute, second pass).
**Date:** 2026-06-04.
**Context:** Background `claude -p --model sonnet` CLI returned 0 bytes (documented empty-output failure
mode). This is the **second** in-session Sonnet pass; the prior pass findings are in the same file
(now superseded below). The prior pass found 7 HIGHs; the Opus/Kilo/v0.3.0 patch cycle addressed them.
This pass reviews the **current post-v0.3.0 state** for what remains open.

**Method:** read all 12 source files; executed the negative-guard fixture under robot; re-derived retro
citations by grep; reviewed diff between prior-pass findings and current harness state.

**Applies to version:** `test_all_recipes_dryrun.py` post-v0.3.0 (untracked in `tests/integration/recipes/`).

---

## Status of prior-pass HIGH findings (all patched in v0.3.0)

| Prior HIGH | Fix applied | Verified |
| --- | --- | --- |
| HIGH-1 (`FileNotFoundError` dead code for robot-absent skip) | `_robot_module_available()` added at L251; `except FileNotFoundError` removed from `test_recipe_block_dryruns` | ✓ L309 uses preflight |
| HIGH-2 (retro closure overclaimed) | C64 row in carry-overs.md → PARTIAL; spec Change Log → PARTIAL framing | ✓ `carry-overs.md:88` reads "PARTIAL 2026-06-04" |
| HIGH-3 (AC-14.3.3 eligible-vs-passing conflation) | `_AC_14_3_3_THRESHOLD` → `_DF_14_3_S1_PASSING_FLOOR`; v2 correction comment L229-236 | ✓ L237 |
| HIGH-4 (C64 docstring cites L91) | `test_all_recipes_dryrun.py:25` → L88 | ✓ L25 reads L88 |
| HIGH-5 (Epic 11 L158 → L157 in spec) | All 4 spec references corrected | ✓ spec L23, L68, L204, L206 read L157 |
| HIGH-6 (no unclosed-block ValueError test) | Test added at L474-490 | ✓ `pytest.raises(ValueError, match="Unclosed")` |
| HIGH-7 (module-load assert masks all tests) | Renamed to `_DF_14_3_S1_PASSING_FLOOR`; message improved | ⚠️ Assert still at L239; see LOW-4 below |

---

## HIGH

**No new HIGH findings.** All prior HIGH findings are patched. Independent re-verification of the
three retro citations:

- Epic 11 retro `L157` Action #7: re-derived → C64 recipe CI extraction. ✓ (L158 = Action #8.)
- Epic 12 retro `L168` Action #9: re-derived → "C64 recipe CI extraction (carried)." ✓
- Epic 13 retro `L186` Action #9: re-derived → "C64 recipe CI extraction (Action #9 carried)." ✓
- C64 row in `docs/phase-1-5-carry-overs.md` at **L88**: re-derived → C64 "PARTIAL 2026-06-04." ✓

---

## MED

### MED-1 — `test_extract_robotframework_blocks__nested_inner_fence_preserved` assertion body does not verify content preservation (`feedback_test_name_assertion_match`)

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:493–513`
**Finding type:** New (not in prior Sonnet pass or Opus/Codex/Kilo findings).

The test name promises the inner fence is "preserved" in the extracted block. The body only checks:

```python
blocks = extract_robotframework_blocks(md)
assert len(blocks) == 1
```

A parser that returned 1 block with content TRUNCATED at the inner `` ``` `` close-line would pass
this test — `len(blocks) == 1` is true whether the raw content includes `Log    after` or not.

The test's synthetic recipe writes:
```
```robotframework
*** Test Cases ***
Outer Test
    Log    before
    ```python
    print('this is documentation inside a robot block')
    ```
    Log    after
```
```
If the inner `` ``` `` (at column 4, stripped: `    ````) had triggered the outer close, the block would
contain everything up to `    ``` ` but NOT `Log    after`. `len(blocks)` would still be 1.

Per `feedback_test_name_assertion_match` (ratified Epic 3 retro): "the assertion body must deliver on
the test name's promise." The name says "preserved"; the body checks count.

**Fix (concrete):** add content assertions after `len(blocks) == 1`:

```python
assert len(blocks) == 1
assert "```python" in blocks[0].raw, "inner open-fence missing — inner content not preserved"
assert "print(" in blocks[0].raw, "inner body missing"
assert "Log    after" in blocks[0].raw, "content AFTER inner close-fence missing — outer block was truncated"
```

The third assertion is the load-bearing one: it fails if and only if the inner `` ``` `` prematurely
closed the outer block.

---

### MED-2 — grep-parity test uses 3-backtick pattern; parser now accepts 3+ via `_ROBOT_FENCE_OPEN_RE` (Codex MED-1, still open)

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:406–423`

`_ROBOT_FENCE_OPEN_RE = re.compile(r"^(?P<fence>`{3,})robotframework\s*$")` (L83) accepts 3 OR MORE
backtick fences. But `test_extract_robotframework_blocks__counts_match_grep` shells out to
`grep -cE "^```robotframework"` which matches EXACTLY 3 backticks.

For the current 7-recipe corpus all fences use exactly 3 backticks → test passes today. But if a future
recipe used a 4-backtick outer fence (valid GFM when a block embeds a 3-backtick inner example), the
parser would extract 1 block and grep would count 0 → parity assertion fails spuriously.

This is not hypothetical: `test_extract_robotframework_blocks__nested_inner_fence_preserved` was added
precisely because the parser now supports multi-length fences. A recipe that actually uses that feature
would break the parity test.

**Fix (concrete):** replace the shell grep with a Python-only count using the same regex:

```python
_PARITY_RE = re.compile(r"^`{3,}robotframework\s*$", re.MULTILINE)
for md_path in sorted(RECIPES_DIR.glob("*.md")):
    blocks = extract_robotframework_blocks(md_path)
    python_count = len(_PARITY_RE.findall(md_path.read_text(encoding="utf-8")))
    assert len(blocks) == python_count, (
        f"{md_path.name}: extracted {len(blocks)} blocks, regex-count {python_count}."
    )
```

This eliminates both the system-binary coupling and the 3-vs-3+ backtick mismatch.

---

### MED-3 — `_KNOWN_BROKEN_BLOCKS` skip-list not audited against actual failing-block set (Codex MED-2, still open)

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:191–212, 307–308`

`_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT - len(_KNOWN_BROKEN_BLOCKS)` and `test_recipe_block_dryruns`
unconditionally skip any `test_id` in `_KNOWN_BROKEN_BLOCKS`. No test verifies:

1. Every entry in `_KNOWN_BROKEN_BLOCKS` STILL fails dryrun today (stale-skip risk).
2. No OTHER eligible block fails beyond those listed (new-failure blindspot).

The Codex and Opus independent dryrun probes verified the 4/4 split at review time, but this is a
snapshot check — no code enforces it going forward. If recipe-3 block-0 is fixed but the skip entry
stays, the harness silently under-tests (the block is skipped even though it would pass), and
`_PASSING_BLOCKS_COUNT` becomes wrong.

**Fix (concrete):** add an audit test that dryruns every eligible block directly:

```python
def test_known_broken_blocks_exact_match(tmp_path: Path) -> None:
    """Audit: _KNOWN_BROKEN_BLOCKS must exactly equal the set that actually fails dryrun."""
    if not _robot_module_available():
        pytest.skip("robot unavailable")
    actually_failing: set[str] = set()
    for block in _ELIGIBLE_BLOCKS:
        suite = wrap_block_for_dryrun(block)
        suite_name = f"audit_{block.recipe.replace('.md', '')}_{block.block_index}.robot"
        result = _run_robot_dryrun(suite, tmp_path / f"audit_{block.block_index}", suite_name)
        if result.returncode != 0:
            actually_failing.add(block.test_id)
    assert actually_failing == set(_KNOWN_BROKEN_BLOCKS), (
        f"Skip-list drift.\nActually failing: {sorted(actually_failing)}\n"
        f"Skip-listed:      {sorted(_KNOWN_BROKEN_BLOCKS)}"
    )
```

This test is expensive (runs 8 dryruns) and could be marked `@pytest.mark.slow` or gated behind an
env var, but it is the only test that would catch a recipe-rot fix without a matching skip-list removal.

---

### MED-4 — VALIDATION-CEILING line absent from module docstring (Opus MED-3, still open)

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:15–47`

The ratified norm `feedback_dogfood_validation_ceiling` (Epic 7 retro) requires a top-of-file
`VALIDATION-CEILING:` statement on any validation harness specifying what it DOES and DOES NOT verify.
The module docstring (L15-47) describes block classification, wrapping, and closure items but never
frames the ceiling.

The ceiling is non-obvious: `robot --dryrun` verifies keyword-name resolution + argument-arity parsing
ONLY. It does NOT verify: runtime values, network calls, actual adapter behavior, or whether the
recipe's own `Library` import line is correct. Specifically, `06-custom-protocol-adapter.md::block-0`
is test-cases-only and is wrapped with a synthetic `Library AgentEval` — if that recipe's documented
import line were wrong, the dryrun would still pass because the synthetic import masks the recipe prose.

**Fix:** add a `VALIDATION-CEILING` paragraph at the end of the module docstring:

```
VALIDATION-CEILING: ``robot --dryrun`` verifies keyword-name resolution and argument-arity
parsing only — never runtime values, network calls, or actual adapter behavior.
Test-cases-only blocks (e.g., recipe-6 block-0) are validated against a *synthetic*
``Library AgentEval`` wrapper; a wrong import in the recipe's prose is out of scope.
```

---

### MED-5 — Numeric drift: spec says "13 parametrized tests" / "10 helper tests"; actual counts are 20 / 11 (Opus MED-2, still open)

**File:** `_bmad-output/implementation-artifacts/14-3-recipe-ci-extraction-test-all-recipes-dryrun.md`
Task 5 (L164), File List (L258), Change Log v0.2.0 (L274).

Empirical `pytest --collect-only`: **33** tests total = **20** parametrized `test_recipe_block_dryruns`
IDs (one per block in `_ALL_BLOCKS`) + **2** negative + **11** helper (verified: `grep -cE '^def test_'`
= 14 = 1 parametrized def + 2 negative + 11 helper).

The spec says "13 parametrized tests" (self-contradicts Task 1's own "33 parametrizations covering all
20 blocks" — one per block IS 20, not 13). The v0.3.0 Change Log entry does not correct these numbers.

**Fix:** standardize spec to "20 parametrized block IDs + 2 negative + 11 helper = 33 total" in all
three locations (Task 5 body, File List, and Change Log v0.2.0 parenthetical).

---

## LOW

### LOW-1 — Module docstring L21 "Closes 3 retro action items" inconsistent with PARTIAL framing

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:21`
**Finding type:** New (not in prior passes).

Line 21 says: `"Closes 3 retro action items (3 epics carryover chain) + 1 catalog row:"`

The Opus HIGH-1 patch updated the story spec and carry-overs.md to say "PARTIAL" (harness ships;
≥6-passing bar deferred to DF-14.3-S1). The test file's own module docstring still says "Closes"
unconditionally — a framing inconsistency in shipped code.

**Fix:** change L21 to:
```
Partially closes 3 retro action items (mechanism delivered; ≥6-passing bar deferred to DF-14.3-S1):
```

---

### LOW-2 — `feedback_executable_doc_precheck` memory file not annotated as CI-automated (Opus MED-4, still open)

**File:** `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_executable_doc_precheck.md`

Story 14.3 IS the CI automation of this Epic-7 norm for `docs/recipes/*` RF blocks. Future sessions
will continue instructing operators to manually smoke-execute recipe RF blocks that the CI gate now
covers. One-line append: "CI-enforced as of Story 14.3 via `tests/integration/recipes/test_all_recipes_dryrun.py`
for `docs/recipes/*` robotframework blocks; manual precheck remains the first-line authoring guard."

---

### LOW-3 — Local `import subprocess as _sp` inside test function is redundant

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:408`

`test_extract_robotframework_blocks__counts_match_grep` does `import subprocess as _sp` locally
"to avoid polluting module scope." `subprocess` is already imported at L53. The local import is
misleading (implies `subprocess` is otherwise absent) and should be deleted; use the module-level
import directly.

---

### LOW-4 — Module-load assert ergonomic: still fires as collection error (prior HIGH-7, partially addressed)

**File:** `tests/integration/recipes/test_all_recipes_dryrun.py:239–248`

The rename from `_AC_14_3_3_THRESHOLD` to `_DF_14_3_S1_PASSING_FLOOR` and the improved message
in v0.3.0 substantially mitigate the "cryptic" concern — the error message is now:
`"DF-14.3-S1 passing-floor regression: N dryrun-eligible blocks are PASSABLE in CI …"`
This is informative, not cryptic.

However: if it fires, ALL 33 test results from this file disappear from the pytest report (collection
error). The dedicated test `test_collect_passable_blocks_meets_amended_ac_14_3_3_threshold` covers the
same condition with a clean `FAILED` for one named test. Having both is redundant.

**Fix (optional):** remove the module-load assert; keep only the dedicated test. Or keep both but document
the ergonomic: the module-load assert is intentional early-fail for corpus-empty protection; the test
provides the same check with better UX.

---

## Verified CLEAN (independently probed)

- **Skip-list completeness (HIGH §`_KNOWN_BROKEN_BLOCKS`):** bash-executed `robot --dryrun` against the
  `_BROKEN_GET_FROM_DICTIONARY_SUITE` fixture → `returncode=1`, output contains
  `"No keyword with name 'Get From Dictionary' found."` Negative guard fidelity ✓
- **Fence counts (D-1):** `grep -cE '^```robotframework' docs/recipes/*.md` → 20 total (recipe-2=5,
  recipe-3=3, recipe-4=2, recipe-5=2, recipe-6=1, recipe-7=5, recipe-8=2, others=0). Matches
  `_ALL_BLOCKS=20` from kilo probe. ✓
- **`_robot_module_available()` correctness (HIGH-1 fix):** uses `importlib.util.find_spec("robot")`
  (L260); `importlib.util` is imported at L51. Correctly handles the case where robot module is absent
  vs Python executable missing. ✓
- **Nested-fence close-fence semantics:** `stripped = line.rstrip()` + `stripped == open_fence`
  (same-length match) correctly handles indented inner `` ``` `` lines (4-space indented
  `"    ```"` stripped-right = `"    ```"` ≠ `"```"`). ✓ (MED-1 flags the missing CONTENT assertion.)
- **Citation re-derivation:** Epic 11 L157, Epic 12 L168, Epic 13 L186, C64 at L88 all confirmed. ✓
- **Unclosed-block test (HIGH-6 fix):** test at L474–490 writes a dangling `` ```robotframework `` to
  `tmp_path` and asserts `pytest.raises(ValueError, match="Unclosed")`. ✓
- **Catalog gate (AC-14.3.9):** DF-14.3-S1 row present in `deferred-work.md:415`; 4 inline refs in
  `_KNOWN_BROKEN_BLOCKS` resolve to it. ✓
- **Self-recursion guard (L-2):** harness globs `docs/recipes/*.md` only, never `tests/`. ✓
- **`docs/recipes/README.md` stale content (Codex MED-3):** README:37 now describes the CI harness,
  4-pass/4-skipped reality, and DF-14.3-S1 correctly. CLOSED ✓

---

## Triage summary

| ID | Severity | Status | Priority |
| --- | --- | --- | --- |
| MED-1 | MED | New finding | Apply before `done` — 3 lines, closes `feedback_test_name_assertion_match` violation |
| MED-2 | MED | Codex open | Apply before `done` — future-proofing; current corpus passes |
| MED-3 | MED | Codex open | Apply at convenience — expensive audit test; MED not blocking |
| MED-4 | MED | Opus open | Apply before `done` — one docstring paragraph; norm compliance |
| MED-5 | MED | Opus open | Apply before `done` — spec-only number correction |
| LOW-1 | LOW | New finding | Cheap one-word fix; framing consistency |
| LOW-2 | LOW | Opus open | One-line memory file update |
| LOW-3 | LOW | Style | Delete 1 line |
| LOW-4 | LOW | Prior HIGH-7 partial | Optional cleanup |

**No code-correctness defect in extraction/classification/wrap/dryrun machinery.** The harness is
empirically sound. All 7 prior HIGH findings are patched. Remaining findings are test-coverage gaps,
documentation hygiene, and minor framing inconsistencies.
