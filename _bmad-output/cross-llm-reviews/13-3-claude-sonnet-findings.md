Here is the full adversarial review of Story 13.3.

---

## Adversarial Code Review — Story 13.3: MCP.Compare Tool Discoverability

**Verification baseline:** 1874 passed + 16 skipped (no regressions). All 23 new Story 13.3 tests pass. Ruff and mypy clean. Story 4.4's 50+ existing tests pass unchanged (helper extraction verified). No HIGH findings.

---

### MED-1: Dead code + factually wrong comment — outer `t_start` is captured but never used

**File:** `src/AgentEval/mcp/library.py:628` and `:761-763`

**Issue:** `t_start = time.monotonic()` is captured before arg validation (the correct anchor per single-adapter semantics), but the compare keyword passes a fresh `time.monotonic()` **per adapter** (after `load_discoverability_tasks()`), so the outer `t_start` is silently discarded via `_ = t_start`. The comment on that line states it "contributes to the per-adapter timers we MAX'd above" — this is factually false. The per-adapter timers are independent, post-YAML-load anchors that never see the outer `t_start`.

**Evidence:**
```python
t_start = time.monotonic()         # line 628 — never forwarded to anything
# ...
task_list = load_discoverability_tasks(tasks)   # YAML load at line 674
for adapter_name in adapters:
    ...run_single_adapter_discoverability(
        ...,
        t_start=time.monotonic(),  # line 699 — fresh per-adapter, post-YAML-load
    )
# ...
_ = t_start  # line 763 — "contributes to per-adapter timers" — FALSE
```

**Fix:** Either (a) pass the outer `t_start` to each per-adapter call so timers include YAML load time and match the single-adapter semantics, or (b) delete the outer `t_start = time.monotonic()` capture (line 628) and remove the misleading `_ = t_start` + comment. Option (b) is simplest and consistent with the "parallel model" intent where individual per-adapter times are what matters.

---

### MED-2: `_internal.py` `t_start` docstring claims a contract the compare caller violates

**File:** `src/AgentEval/discoverability/_internal.py:84-87`

**Issue:** The `t_start` parameter docstring reads: *"Lets compare-multi-adapter measure end-to-end across all adapters from a single anchor."* Both claims are false in compare mode: the compare keyword fires a **new** `time.monotonic()` **per adapter**, **after** `load_discoverability_tasks()` — not before YAML load and not from a single shared origin. This creates a semantic inconsistency: per-adapter `summary.total_runtime_seconds` inside `per_adapter_results` **excludes YAML load time** and uses different origins, while the standalone `MCP.Get Tool Discoverability` path **includes** YAML load time (because `t_start` is captured at library.py:512 before the YAML load at line 530).

**Evidence:** Single-adapter: `t_start` captured at line 512 → `load_discoverability_tasks` at line 530 → `run_single_adapter_discoverability(t_start=t_start)`. Compare: `load_discoverability_tasks` at line 674 → loop with `t_start=time.monotonic()` at line 699.

**Fix:** Correct the docstring to say the per-adapter `t_start` is a fresh anchor fired **after YAML load**, and that the "single anchor" claim is aspirational (Phase-2.5 parallel fan-out). Also note the `total_runtime_seconds` field inside `per_adapter_results` will be slightly shorter than if called via `Get Tool Discoverability` on the same adapter, because YAML load is amortized in compare mode.

---

### LOW-1: Missing test for `worst_adapter` unknown-key validator

**File:** `tests/unit/discoverability/test_comparison.py` (missing)

**Issue:** AC-13.3.2 explicitly specs validating both `best_adapter` AND `worst_adapter` are in `pass_rate_per_adapter`. `test_comparison_summary_rejects_unknown_best_adapter` covers `best_adapter` only. No symmetric test for `worst_adapter` exists.

**Fix:** Add `test_comparison_summary_rejects_unknown_worst_adapter` passing `best_adapter="a", worst_adapter="unknown"` and asserting `pytest.raises(ValueError, match="worst_adapter")`.

---

### LOW-2: L-5 docstring anchor test specified but not implemented

**File:** `tests/unit/discoverability/test_comparison.py` (missing)

**Issue:** Cross-story lesson L-5 (applied per the story's completion notes) explicitly requires a Browser-Library-convention test that asserts `"Mann-Whitney U"` + `"Story 13.1"` + `"FR10b"` + `"Phase-2"` appear in the keyword docstring. All four phrases exist in the docstring (confirmed), but the test itself was never written. The 16 unit tests in `test_comparison.py` include no docstring anchor test.

**Fix:** Add `test_compare_keyword_docstring_anchors` that reads `MCPLibrary.get_tool_discoverability_comparison.__doc__` and asserts each of the four phrases is present. Mirrors the existing `test_keyword_has_robot_marker` / `test_keyword_has_tier_3_annotation` pattern in `tests/unit/discoverability/test_keyword.py`.

---

### LOW-3: No adapter registry cleanup fixture in `test_comparison.py`

**File:** `tests/unit/discoverability/test_comparison.py:350-441`

**Issue:** Five unit test functions call `register_adapter()` without an autouse teardown fixture. The integration test (`test_compare_e2e.py:57-65`) correctly has `_restore_adapter_registry`. Without it, 11 stub adapter names leak into the process-wide `_registered_adapters` dict for the pytest session duration. No functional bug today (all names are unique), but the next story that registers a colliding stub name will get a silent overwrite.

**Fix:** Add the same `_restore_adapter_registry` autouse fixture (verbatim from `test_compare_e2e.py`) at module level in `test_comparison.py`.

---

**Total: 0 HIGH + 2 MED + 3 LOW**
