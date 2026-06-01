I've empirically verified the implementation end-to-end. Findings below — each is grounded in source/test execution, not just the diff.

---

## Review: Story 13.3 — MCP.Compare Tool Discoverability (FR10b)

**What I verified empirically (to avoid manufacturing findings):**
- All 23 new tests pass; full discoverability unit suite (71, incl. Story 4.4's 50+) passes → **refactor is behavior-preserving (Probe 1 ✓)**.
- `ruff` + `mypy` clean on all changed source.
- Mann-Whitney significance is real for the 3-task fixture: separated dists → `p=0.0253 < 0.05`; identical → `p=nan` (Probes 2/4 ✓).
- `_ComparisonShim` works because `from_comparison` only reads `.adapters` + `.per_adapter_results`, and the resulting `heatmap.models` satisfies the `set(adapters)==set(heatmap.models)` invariant (Probe 7 ✓).
- PRD L1500 amended correctly (Probe 10 ✓); `@guarded_fanout` correctly omitted matching the existing `Get Tool Discoverability` pattern (Probe 5 ✓).

---

### [MED]-1: `summary.pass_rate_per_adapter ↔ adapters` cross-consistency invariant is never enforced

**File:** `src/AgentEval/discoverability/schema.py:236-247` + `DiscoverabilityComparisonResult.__post_init__`
**Issue:** AC-13.3.2 explicitly mandates the summary validator assert `set(pass_rate_per_adapter.keys()) == set(adapters_referenced_in_comparison)`. The shipped `DiscoverabilityComparisonSummary.__post_init__` only checks `best_adapter`/`worst_adapter` membership, and `DiscoverabilityComparisonResult.__post_init__` checks `adapters↔per_adapter_results` and `adapters↔heatmap.models` but **not** `adapters↔summary.pass_rate_per_adapter`. A summary missing/adding an adapter would validate clean. No live bug (the builder is correct), but the AC-promised defensive invariant is absent.
**Evidence:**
```python
def __post_init__(self) -> None:
    object.__setattr__(self, "pass_rate_per_adapter", dict(self.pass_rate_per_adapter))
    if self.best_adapter not in self.pass_rate_per_adapter: ...
    if self.worst_adapter not in self.pass_rate_per_adapter: ...
    # no key-set equality check
```
**Fix:** In `DiscoverabilityComparisonResult.__post_init__`, add `if set(self.adapters) != set(self.summary.pass_rate_per_adapter.keys()): raise ValueError(...)`.

---

### [MED]-2: `total_runtime_seconds` reports a parallel-target MAX on serial execution; method-level `t_start` is dead with a false comment

**File:** `src/AgentEval/mcp/library.py` (comparison method — per-adapter `t_start=time.monotonic()`, summary `max(...)`, and the trailing `_ = t_start`)
**Issue:** Adapters run **serially**, so the real wall-clock is the *sum* of per-adapter runtimes. Cost is summed (correct), but `total_runtime_seconds` is `max()` across adapters ("models eventual parallel target"). For N=3 this under-reports actual elapsed time by up to 3×, and **no field captures the true wall-clock**. Compounding this, the method's top-level `t_start = time.monotonic()` is dead: each adapter is timed with its own fresh `time.monotonic()`, so the trailing comment is factually wrong — exactly the comment-vs-code drift class this project flags (cf. Story 4.4 MED-D).
**Evidence:**
```python
# Track end-to-end runtime (caller-side; not stored separately
# but contributes to the per-adapter timers we MAX'd above).
_ = t_start    # <-- per-adapter timers use their OWN time.monotonic(); t_start contributes to nothing
```
**Fix:** Either delete the dead `t_start` and its false comment, or actually use it to record true end-to-end wall-clock (e.g., a `wall_clock_seconds` field on the summary) and keep MAX as a separate "parallel-target" estimate. At minimum correct the comment.

---

### [MED]-3: `MannWhitneyResult` nan-relaxation changes Story 13.1's shipped `Stat.Mann Whitney U` behavior with no direct regression test

**File:** `src/AgentEval/stats/types.py:67-82`
**Issue:** The validator was relaxed to accept `p_value=nan`. This is the correct scipy convention, but it silently changes the behavior of the **already-shipped** `Stat.Mann Whitney U` keyword (identical samples previously raised `ValueError`; now return `nan`). I confirmed `tests/unit/stats/` (89 tests) has **no** direct coverage of the identical-samples/nan path for `compute_mann_whitney_u` — the only nan tests are for `assert_run_determinism`. The new nan path is exercised only indirectly through the 13.3 comparison test. A behavior change to a Phase-2 stability-surface should carry a direct unit test in the owning module.
**Evidence:** `grep` shows stats nan tests are all `assert_run_determinism`; none assert `compute_mann_whitney_u([1,1,1],[1,1,1]).p_value` is nan.
**Fix:** Add a `tests/unit/stats/test_advanced.py` case asserting identical/zero-variance samples yield `p_value=nan` and construct a valid `MannWhitneyResult` (and that `Stat.Mann Whitney U` no longer raises).

---

### [LOW]-1: Stale `ToolDiscoverabilityResult` type name still present at PRD FR55 (the CohortHeatmap surface this story extends)

**File:** `_bmad-output/planning-artifacts/prd.md:1583`
**Issue:** AC-13.3.12/D-1 claims to correct the stale `ToolDiscoverabilityResult` → `DiscoverabilityResult`. Only the FR10b instance was fixed. FR55 still reads `Metric.Get Cohort Heatmap <ToolDiscoverabilityResult>` — referencing a type that was never shipped (the keyword takes `DiscoverabilityResult`, per the regenerated libdoc). FR55 is the `CohortHeatmap` surface Story 13.3 directly extends with `from_comparison`, so it's squarely adjacent.
**Evidence:** `grep -n ToolDiscoverabilityResult prd.md` → `1583:- **FR55 ...** Metric.Get Cohort Heatmap <ToolDiscoverabilityResult>`.
**Fix:** Same-commit `ToolDiscoverabilityResult` → `DiscoverabilityResult` at L1583, or scope the D-1 claim to FR10b only.

---

### [LOW]-2: Pairwise deltas silently dropped on empty per-task lists (no-silent-caps)

**File:** `src/AgentEval/mcp/library.py` (delta loop: `if not rates_a or not rates_b: continue`)
**Issue:** If any adapter yields zero per-task results, its pairs are skipped, producing a `DiscoverabilityComparisonResult` with fewer than C(N,2) deltas and **no log/warning**. Per the project's no-silent-truncation norm, a dropped comparison should be surfaced. Low impact (the tasks loader rejects empty YAML), but the guard is silent.
**Fix:** `log`/warn the skipped pair, or assert non-empty since upstream validation guarantees it.

---

### [LOW]-3: Redundant local re-import of `DiscoverabilityComparisonResult`

**File:** `src/AgentEval/mcp/library.py` (module-top import + in-method `from ...schema import (DiscoverabilityComparisonResult, ...)`)
**Issue:** `DiscoverabilityComparisonResult` is imported at module top *and* re-imported locally inside the method (shadowing). Harmless and ruff-clean, but the local import only needs `DiscoverabilityComparisonSummary` + `PairwiseAdapterDelta`.
**Fix:** Drop `DiscoverabilityComparisonResult` from the in-method import.

---

**Total: 0 HIGH + 3 MED + 3 LOW**

Honest framing per `feedback_honest_framing`: I found **no HIGH** despite 13.1/13.2 each producing 4–6. This is a genuine negative, not under-review — I empirically confirmed the refactor is behavior-preserving (71 tests), the Mann-Whitney/nan math is correct (verified against scipy directly), gates are clean, and the PRD amendment landed. The MED findings are missing-invariant / metric-honesty / coverage-gap issues, not correctness defects; none block `done`, though MED-1 and MED-3 are worth folding in before close.
