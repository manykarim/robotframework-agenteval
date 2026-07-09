All the probes are now verified. Let me compile the review.

---

## Story 13.5 Adversarial Code Review

### Probe-by-probe verdicts

1. **Helper extraction parity** — 20 Story 7.2 tests pass unchanged. ✓
2. **`@guarded_fanout()` posture** — `guardrails.py:265` confirms `getattr(self, "_max_cost_usd", None)` graceful fallback. ✓ (but see HIGH-2 below)
3. **N=2/N=3 pairwise ordering** — `itertools.combinations(["a","b","c"], 2)` → `a_vs_b, a_vs_c, b_vs_c`. ✓
4. **Delta direction convention** — integration test asserts `delta_a_vs_c.false_activation_rate_delta > 0` and `delta_b_vs_c.missed_activation_rate_delta > 0`; math checked (a.false−c.false = 1.0−0.0 = +1.0; b.missed−c.missed = 1.0−0.0 = +1.0). ✓
5. **Comparison-level wall-clock** — `compare_t_start = time.perf_counter()` is captured before the per-adapter loop; `total_runtime = time.perf_counter() - compare_t_start`. ✓
6. **Pre-flight extras gate ordering** — polling check → arg validation → extras gate → parse → fan-out. ✓
7. **4-way cross-consistency validator** — all four `__post_init__` checks confirmed in `types.py:305-325`. ✓
8. **L-7 cells-as-omission** — cells generator never emits explicit `None`; all adapters run the same tasks so no structural gap. ✓
9. **Recipe `robot --dryrun` claim** — **FAILS empirically** (see HIGH-1).
10. **C95-C98 carry-over completeness** — `grep -c "^| \*\*C"` → 98; each row has 7 columns. ✓

---

### HIGH-1: Recipe `robot --dryrun` claim false — `Get From Dictionary` not in scope

**File:** `docs/recipes/04-skill-author-stacked-validation.md:147`

**Issue:** The recipe snippet uses `Get From Dictionary` (RF Collections library keyword) but the `*** Settings ***` section only imports `AgentEval.skills.library.SkillsLibrary`. Running `robot --dryrun` on the verbatim snippet fails with `No keyword with name 'Get From Dictionary' found.` AC-13.5.8 explicitly states "`robot --dryrun` smoke verified clean" — this claim is false.

**Evidence:**
```
$ robot --dryrun /tmp/recipe_dryrun_test.robot
Skill X Is Reliably Activated Across Claude And OpenAI  | FAIL |
No keyword with name 'Get From Dictionary' found.
1 test, 0 passed, 1 failed
```

**Fix:** Either add `Library    Collections` to the snippet's `*** Settings ***` section, or replace `Get From Dictionary` with RF7 inline variable syntax (no extra import required):
```robot
Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3
```

---

### HIGH-2: `max_cost_usd` / `max_runtime_seconds` are declared, documented, and silently ignored

**File:** `src/AgentEval/skills/library.py:448-453`

**Issue:** `Skill.Compare Discoverability` declares `max_cost_usd: float = 20.00` and `max_runtime_seconds: float | None = None` with docstring text "Budget cap. Defaults to 20.00" / "Runtime cap." — both imply active enforcement. But `@guarded_fanout()` resolves its budget via `getattr(self, "_max_cost_usd", None)` (guardrails.py:265), and `SkillsLibrary` has no `_max_cost_usd` attribute (no `__init__`, no class-level assignment). The method body also never references either parameter. A caller passing `max_cost_usd=5.0` gets zero budget enforcement — the guard operates with `None` for both fields, skipping all three cost/runtime layers entirely. `Skill.Get Discoverability` (Story 7.2) does NOT have `max_cost_usd` in its signature, so this is a new false-promise introduced by Story 13.5.

**Evidence:**
```
# guardrails.py:265 — decorator NEVER reads the method kwarg:
max_cost_usd = getattr(self, "_max_cost_usd", None)  # → None (always)

# skills/library.py — grep of body after signature:
$ grep "max_cost_usd\|max_runtime" src/AgentEval/skills/library.py
# → appears only in the signature and docstring, never in the body
```

**Fix:** Add a one-line note to the docstring alongside both parameters stating budget enforcement is deferred to Phase-2.5 (C95), e.g.:
```
| ``max_cost_usd`` | Accepted for API-shape forward-compatibility; budget enforcement
                    deferred to Phase-2.5 (C95 / DF-13.5-S1). Not currently enforced. |
```
Alternatively, wire `max_cost_usd` as the `__agenteval_test_budget__` override or call `object.__setattr__(self, "_max_cost_usd", max_cost_usd)` at the top of the function body before `@guarded_fanout()` executes its wrapper logic.

---

**Total: 2 HIGH + 0 MED + 0 LOW**

The two findings are orthogonal: HIGH-1 is a doc/test validity failure (broken dryrun claim); HIGH-2 is a silent API contract violation (budget parameter that does nothing). All other probes are clean — pairwise math, wall-clock semantics, extras-gate ordering, 4-way cross-consistency, and carry-over catalog are all correct.
