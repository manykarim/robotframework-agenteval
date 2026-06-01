I have completed all 10 probes with empirical verification. Here are my findings.

---

## Adversarial Review — Story 13.5: Skill.Compare Discoverability (FR4c)

**Probe results (verified empirically):**
- ✅ Probe 1: All 120 skills unit+integration tests pass; refactor preserves Story 7.2 behavior.
- ✅ Probe 2: `guarded_fanout` reads `getattr(self, "_max_cost_usd", None)` → no crash (but see HIGH-1).
- ✅ Probe 3: `itertools.combinations(["a","b","c"], 2)` → `a_vs_b/a_vs_c/b_vs_c`, order preserved.
- ✅ Probe 4: delta directions correct in integration + unit tests (`a-b`, positive = a worse).
- ✅ Probe 5: comparison-level `compare_t_start` end-to-end wall-clock, not MAX-of-per-adapter.
- ✅ Probe 6: extras gate runs after arg-validation, before fan-out (fail-fast confirmed).
- ✅ Probe 7: all 4 cross-consistency checks present in `__post_init__` (but see LOW-3).
- ✅ Probe 8: `from_skill_comparison` emits no explicit `None` cells.
- ❌ Probe 9: recipe dryrun is **NOT clean** (see MED-1).
- ✅ Probe 10: C95–C98 each have all 7 table columns.

---

### [HIGH]-1: `max_cost_usd`/`max_runtime_seconds` are dead params and the docstring drops the "NOT enforced" caveat the sibling keyword carries

**File:** `src/AgentEval/skills/library.py:454-455,481-482` (+ libdoc)

**Issue:** The new keyword accepts `max_cost_usd=20.00` / `max_runtime_seconds`, but neither value is ever consumed: they appear only in the signature and docstring (`grep` shows no other reference in the body), and `@guarded_fanout()` reads `self._max_cost_usd` — an attribute `SkillsLibrary` never sets (no `__init__`, excluded from `_SUB_LIBRARIES`), so it resolves to `None` and all enforcement layers are skipped. Critically, the docstring labels `max_cost_usd` simply as **"Budget cap. Defaults to 20.00"** with no caveat, whereas the symmetric Story 13.3 keyword explicitly documents **"tracked NOT enforced (DF-4.4-S1 / C20)"**. An operator running a real-API 4× cross-adapter fan-out who sets `max_cost_usd=10.00` to bound spend gets **zero** protection while the docstring tells them it's a cap. This violates `feedback_honest_framing` and diverges from the established 13.3 precedent. 13.5 is actually *worse* than 13.3 here: it ships the `@guarded_fanout()` decorator (so it *looks* enforced) while it is not.

**Evidence:**
```
13.3: max_cost_usd | Budget cap. Defaults to 20.00 ... Phase-1 carve-out DF-13.3-S1: tracked NOT enforced ...
13.5: max_cost_usd | Budget cap. Defaults to 20.00 per epics.md L2218 (4× single-adapter typical).
guardrails.py:265:  max_cost_usd = getattr(self, "_max_cost_usd", None)   # SkillsLibrary has no such attr → None
$ grep -n max_cost_usd src/AgentEval/skills/library.py → only 454 (sig) + 481 (docstring); never in body
```

**Fix:** Append the "Phase-1: tracked, NOT enforced (DF-13.5-S1 / C95)" caveat to the `max_cost_usd` **and** `max_runtime_seconds` docstring rows (verbatim parity with 13.3), and regenerate libdoc. Optionally drop the unused `@guarded_fanout()` decorator since it enforces nothing here, or thread the params through (matching 13.3's `run_single_adapter_*(max_cost_usd=...)` forwarding) so they are at least non-dead.

---

### [MED]-1: Recipe #4 snippet fails `robot --dryrun` — `Get From Dictionary` used without `Library Collections`; dev's "dryrun verified clean" claim is false

**File:** `docs/recipes/04-skill-author-stacked-validation.md:137-141`

**Issue:** The shipped recipe snippet imports only `SkillsLibrary WITH NAME Skill` but calls `Get From Dictionary` — a Collections-library keyword — which is not imported. `robot --dryrun` fails to resolve it. AC-13.5.8, Task 9, and D-7 all assert "`robot --dryrun` smoke verified clean," and the Debug Log says "Recipe RF snippet also dryrun-clean." This is exactly the defect class `feedback_executable_doc_precheck` exists to catch, and the verification claim is demonstrably false. (The docstring/libdoc Example uses extended-variable syntax instead and is fine — only the recipe is broken.)

**Evidence:**
```
$ uv run robot --dryrun <exact recipe snippet>
Skill X Is Reliably Activated Across Claude And OpenAI                | FAIL |
No keyword with name 'Get From Dictionary' found.
1 test, 0 passed, 1 failed
```
(After adding `Library Collections`, the same file dryruns PASS — confirming the missing import is the sole cause.)

**Fix:** Add `Library    Collections` to the snippet's `*** Settings ***`, or replace the `Get From Dictionary` line with extended-variable access: `${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}` (as the docstring Example already does). Then actually re-run `robot --dryrun`.

---

### [LOW]-1: Class docstring + regenerated libdoc still claim "All 5 public methods … `@tier(1)`-annotated"

**File:** `src/AgentEval/skills/library.py:96-97` (propagated into `docs/keywords/SkillsLibrary.html`)

**Issue:** The class docstring states "All 5 public methods are `@keyword`-decorated + `@tier(1)`-annotated." The library now exposes **9** keyword-decorated methods, and the new `Skill.Compare Discoverability` is `@tier(3)` (as are `Get Discoverability`, `Get Activation Decision`). The story regenerated libdoc but did not correct this stale class doc. Pre-existing drift, but worsened and re-published by this story.

**Evidence:** libdoc lists 9 keywords; `Skill.Compare Discoverability` is `@tier(3)`.

**Fix:** Update the class docstring to reflect the actual count and the mixed Tier 1/2/3 surface, then regenerate libdoc.

---

### [LOW]-2: AC-13.5.7's "`a_vs_c` significant at α=0.05" assertion is silently absent from the integration test

**File:** `tests/integration/skills/test_skill_compare_e2e.py:test_compare_3_stub_adapters_end_to_end_skill`

**Issue:** AC-13.5.7 enumerates "3 pairwise deltas; `a_vs_c` significant at α=0.05." The integration test asserts the three delta keys exist and checks false/missed-activation deltas, but makes **no** significance assertion for `a_vs_c`. With `trials_per_task=3` over 5 heavily-tied per-task `pass_at_k` lists (`[1,1,1,1,1]` vs `[1,1,1,0,0]`), Mann-Whitney U almost certainly is *not* significant — likely the real reason it was dropped. Per `feedback_in_flight_spec_amendment`, the AC should have been amended in-commit rather than silently unmet.

**Fix:** Either amend AC-13.5.7 to remove the unachievable significance claim (documenting why tiny tied distributions aren't significant), or add an explicit assertion on `a_vs_c.significant_at_alpha_05` that matches reality.

---

### [LOW]-3: No unit test for the `set(adapters) == set(heatmap.models)` validator branch

**File:** `tests/unit/skills/test_comparison.py`

**Issue:** Probe 7's 4-way validator is fully present in code, and 3 of the 4 branches have dedicated negative tests (single-adapter, per_adapter-keys mismatch, summary-keys mismatch). The `heatmap.models` mismatch branch (`src/AgentEval/skills/types.py`) has no dedicated test — the existing `adapters_keys_mismatch` test trips the `per_adapter_results` check first, so the heatmap branch is never exercised.

**Fix:** Add a test where `adapters` and `per_adapter_results.keys()` agree but `heatmap.models` differs, asserting `ValueError` matching "heatmap.models".

---

**Total: 1 HIGH + 1 MED + 3 LOW**

The HIGH (misleading/dead budget cap on a real-money fan-out keyword) and the MED (broken recipe with a false dryrun-clean claim) are the two that should block `done` until fixed. Note that the existing test suite passes (120/120 skills tests) and the core comparison math, delta directions, wall-clock, and cross-consistency validators are all correct — the defects are in operator-facing surfaces (docstring honesty + executable docs), not the computation.
