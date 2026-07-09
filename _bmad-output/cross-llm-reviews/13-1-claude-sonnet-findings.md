I have all the evidence I need. Here is the adversarial review:

---

### [HIGH]-1: `stability-surface.md` documents nonexistent Python method names for all 3 advanced keywords

**File:** `docs/contracts/stability-surface.md:129-131`

**Issue:** The stability contract registers `StatsLibrary.mann_whitney_u`, `StatsLibrary.cliff_delta`, and `StatsLibrary.bootstrap_ci` as the Python method entry points. These methods do not exist. The dev renamed all three to `compute_*` during implementation (in-flight spec amendment per the verb-allowlist convention test) but the rename was not propagated to this contract doc. Calling any of the three names results in `AttributeError`.

**Evidence:**
```
$ python3 -c "from AgentEval.stats.library import StatsLibrary; lib=StatsLibrary(); print(hasattr(lib, 'mann_whitney_u'))"
False
$ python3 -c "from AgentEval.stats.library import StatsLibrary; lib=StatsLibrary(); print(hasattr(lib, 'compute_mann_whitney_u'))"
True
```
Actual methods: `compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci`.

**Fix:** In `stability-surface.md` lines 129–131, replace:
- `StatsLibrary.mann_whitney_u` → `StatsLibrary.compute_mann_whitney_u`
- `StatsLibrary.cliff_delta` → `StatsLibrary.compute_cliff_delta`
- `StatsLibrary.bootstrap_ci` → `StatsLibrary.compute_bootstrap_ci`

---

### [MED]-1: `MannWhitneyResult.u_statistic` docstring falsely claims "matches scipy.stats.mannwhitneyu default"

**File:** `src/AgentEval/stats/types.py:41-43` and `src/AgentEval/stats/mannwhitney.py:56-57`

**Issue:** scipy's `mannwhitneyu` returns **U1** (the U statistic corresponding to the first sample), not `min(U1, U2)`. The docstring assertion "matches `scipy.stats.mannwhitneyu` default" is false whenever samples_a tends to be larger than samples_b: in that regime U1 > U2, scipy returns U1, and the code returns U2. A user who reads the docstring and compares `result.u_statistic` against `scipy.stats.mannwhitneyu(a, b).statistic` will see a mismatch.

**Evidence:**
```
samples_a=[100..107], samples_b=[1..8]:
  scipy statistic (U1) = 64.0   ← scipy's default output
  code's u_statistic  = 0.0     ← min(64, 0) = 0
  scipy.statistic == u_statistic? False
```

**Fix:** Replace the parenthetical in `types.py:41-43` with:
```python
u_statistic: The smaller of U1 and U2 (NOT the same as ``scipy.stats.mannwhitneyu(...).statistic``,
    which returns U1 for the first sample; use ``U2 = n_a * n_b - u_statistic`` to recover U1 when needed).
```
Apply the same correction to `mannwhitney.py:56-57`.

---

### [MED]-2: `effect_size_r` formula not independently verified in the scipy reference test

**File:** `tests/unit/stats/test_advanced.py:149-164`

**Issue:** The three-parametrize scipy reference test (`test_mannwhitney_matches_scipy_reference`) validates `u_statistic` and `p_value` against scipy within 1e-9, but **does not check `effect_size_r`**. The effect size formula (`2*U1/(n_a*n_b) - 1`) was the subject of a sign-convention bug discovered mid-dev (documented in the Sign-convention discovery section). The AC-13.1.6 mandates "unit tests verify math against scipy reference implementations" — `effect_size_r` is part of the math surface and was the most recently broken field. There is no test that numerically verifies the formula against an independent derivation.

**Evidence:** The test body:
```python
assert abs(ours.u_statistic - expected_u_smaller) < 1e-9
assert abs(ours.p_value - float(ref.pvalue)) < 1e-9
# effect_size_r: never checked against reference
```
The behavioral test `test_mannwhitney_clearly_separated_samples_p_value_small` only asserts `< -0.9`, not the exact boundary value (which is -1.0 for 8 vs 8 fully separated samples).

**Fix:** Add to `test_mannwhitney_matches_scipy_reference`:
```python
expected_effect_size_r = 2.0 * u1 / (n * n) - 1.0
assert abs(ours.effect_size_r - expected_effect_size_r) < 1e-9
```
where `u1 = float(ref.statistic)` (already computed in the test body). Additionally, tighten `test_mannwhitney_clearly_separated_samples_p_value_small` to assert `r.effect_size_r == -1.0` (the exact value for fully disjoint samples_a < samples_b with n_a=n_b=8 and U1=0).

---

### [MED]-3: `mannwhitney.py` module docstring references the pre-rename method name

**File:** `src/AgentEval/stats/mannwhitney.py:18-19`

**Issue:** The module docstring says "Imported lazily by `AgentEval.stats.library.StatsLibrary.mann_whitney_u`". The method was renamed to `compute_mann_whitney_u` during the in-flight spec amendment. This stale reference will send readers to a method that doesn't exist when they follow the cross-reference.

**Evidence:**
```python
# mannwhitney.py:18-19
Imported lazily by `AgentEval.stats.library.StatsLibrary.mann_whitney_u`
#                                                                ^^^^^^^^^^^^^^ does not exist
```

**Fix:** Replace with `StatsLibrary.compute_mann_whitney_u`.

---

### [LOW]-1: Bootstrap CI seed reproducibility across numpy major versions is undocumented and untested

**File:** `src/AgentEval/stats/bootstrap.py:76`

**Issue:** `numpy.random.default_rng(seed)` produces reproducible output within a fixed numpy version, but numpy does not guarantee bit-identical output across major releases (e.g., 1.26 → 2.0 → 2.4). The pin range `numpy>=1.26,<3.0` spans two major versions. The test `test_bootstrap_ci_seed_reproducibility` only verifies same-call reproducibility within a single process. No documentation warns users that seeded results may shift after a numpy upgrade within the allowed range.

**Evidence:**
```toml
# pyproject.toml
agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]
```
The bootstrap.py docstring says "Reproducibility via the optional `seed` parameter" with no cross-version caveat.

**Fix:** Add a one-line note to `compute_bootstrap_ci`'s docstring:
```
Note: bit-identical reproducibility is guaranteed only within the same numpy major version.
Upgrading numpy (e.g., 1.26 → 2.x) may produce different values for the same seed.
```
This doesn't require a behavioral change, just documentation honesty. Log as DF-13.1-S4 if the team wants to bound the numpy pin more tightly.

---

### [LOW]-2: `cliffs_delta.py` numpy import is a side-effect-only sentinel with no runtime usage

**File:** `src/AgentEval/stats/cliffs_delta.py:36`

**Issue:** `import numpy as _np  # noqa: F401` is present purely to fail at import time when numpy is absent (gate-parity with `mannwhitney.py`/`bootstrap.py`). `_np` is never referenced in any function body. The `# noqa: F401` comment suppresses the linter, but if a future maintainer cleans up "unused imports" or the `noqa` is removed, the gate silently disappears and `Stat.Cliff Delta` would still work without numpy — violating the unified `[agenteval-advanced]` contract.

**Evidence:**
```python
import numpy as _np  # noqa: F401  # Unified [agenteval-advanced] gate parity.
# ... _np never used anywhere in the module
```

**Fix:** Add a module-level assertion that makes the dependency explicit:
```python
_ = _np.ndarray  # sentinel — ensures numpy is importable; do not remove
```
Alternatively, an explicit `if _np is None: raise ImportError(...)` pattern at the bottom of the module initialization makes the gate intent harder to accidentally delete.

---

**Total: 1 HIGH + 3 MED + 2 LOW**

The implementation is mathematically sound and the test coverage is substantial. The one HIGH is a stability-contract correctness defect (wrong method names in the `provisional` registry — `AttributeError` on first use by any external consumer). The MEDs cluster around docstring drift and a formula-coverage gap in the scipy reference test for the field that had an in-flight sign bug during dev.
