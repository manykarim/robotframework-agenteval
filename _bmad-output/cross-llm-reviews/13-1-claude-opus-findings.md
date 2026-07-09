I've verified the load-bearing facts against source. Here are my findings.

---

### [HIGH]-1: `Stat.Bootstrap Confidence Interval` is `@tier(1)` but `seed=None` default violates the FR31a bit-identical guarantee

**File:** `src/AgentEval/stats/library.py:~560` (decorator) + `bootstrap.py:79` (RNG seeding)
**Issue:** FR31a (quoted verbatim in `tests/conformance/test_tier1_byte_identical_run.py:17-20`) states: *"Library guarantees bit-identical output across runs of any Tier-1 keyword given identical inputs."* `compute_bootstrap_ci` is decorated `@tier(1)` with `seed: int | None = None`. With the default `seed=None`, two invocations with **identical inputs** produce **different** CIs because `numpy.random.default_rng(None)` draws OS entropy. This is a direct violation of the Tier-1 contract, not a closed-form computation. The Story 6.3 precedent cited in D-9 (`Get Pass At K Confidence Interval` = Wilson) does **not** support this — Wilson is closed-form and genuinely deterministic; Bootstrap is RNG-driven. The determinism-contract.md amendment the dev wrote even hedges with "seed-deterministic," which is precisely *not* true under the default.

The conformance harness fails to catch this only because it skips any Tier-1 keyword with required params (`test_tier1_byte_identical_run.py:111` — `if required_params: continue`), and `runs_a`/`runs_b`/`samples` are required-positional.

**Evidence:**
```python
# library.py
@keyword(name="Stat.Bootstrap Confidence Interval")
@tier(1)
def compute_bootstrap_ci(self, samples, ..., seed: int | None = None) -> tuple[float, float]:
# bootstrap.py:79
    rng = _np.random.default_rng(seed)   # seed=None → OS entropy → non-bit-identical
```
**Fix:** Pick one: (a) default `seed=0` (or another fixed int) so the keyword is bit-identical by default and `seed` overrides for variation; OR (b) make `seed` required (no default) and document that omitting it is a usage error for a Tier-1 keyword; OR (c) if a non-reproducible default is genuinely intended, reclassify the keyword out of Tier-1 (and amend the determinism contract + stability-surface accordingly). Option (a) best matches the "Tier-1 = bit-identical given identical inputs" contract while preserving the reproducibility-via-seed story.

---

### [MED]-1: `MannWhitneyResult.u_statistic` docstring falsely claims it "matches scipy default"; contradicts `mannwhitney.py`

**File:** `src/AgentEval/stats/types.py:54-56` + `library.py` keyword docstring
**Issue:** `scipy.stats.mannwhitneyu(...).statistic` is **U1** (the U corresponding to the *first* sample), per scipy's own docs. The code returns `u_smaller = min(U1, U2)` (`mannwhitney.py:87`). For any case where samples_a tends larger (U1 > U2), `min(U1,U2) ≠ scipy.statistic`. So the types.py claim "The smaller of U1, U2 (matches `scipy.stats.mannwhitneyu` default…)" is factually wrong, and it **contradicts** `mannwhitney.py`'s own (correct) docstring: *"scipy reports U1 corresponding to the first input by default … We return the smaller of the two."* The keyword docstring repeats the same conflation ("u_statistic is the smaller of U1, U2 (canonical form)" alongside "Math reference: scipy.stats.mannwhitneyu"). A consumer who tries to recover `effect_size_r` from the returned `u_statistic` via `2*u/(n_a·n_b)−1` gets the wrong sign/value when U1 > U2, since `effect_size_r` is correctly computed from U1, not from the returned smaller-U.

**Evidence:**
```python
# types.py
u_statistic: The smaller of U1, U2 (matches
    ``scipy.stats.mannwhitneyu`` default — ...).   # FALSE: scipy returns U1
# mannwhitney.py:85-87
u1 = float(result.statistic)
u2 = float(n_a * n_b - u1)
u_smaller = min(u1, u2)
```
**Fix:** Correct the types.py + keyword docstrings to: "the smaller of U1, U2 (canonical reporting form); note this differs from `scipy.stats.mannwhitneyu`, which returns U1 for the first sample. `effect_size_r` is derived from U1, not from this field." Keeps the math, removes the false equivalence.

---

### [MED]-2: No `scipy.stats.bootstrap` reference test for Bootstrap CI, despite D-8 + Dev Notes + epic L2155 mandate

**File:** `tests/unit/stats/test_advanced.py` (Bootstrap CI section, lines ~270-330)
**Issue:** Epic L2155 mandates *"unit tests verify math against scipy reference implementations,"* and the dev's own **D-8** and Dev Notes explicitly commit to *"compare against `scipy.stats.bootstrap` with `confidence_level=0.95, method='percentile'`."* No test imports or calls `scipy.stats.bootstrap` — the Bootstrap tests only check self-consistency (brackets-truth, seed-reproducibility, alpha-ordering, error paths). Mann-Whitney is cross-checked against scipy; Bootstrap is not. Separately, the AC-13.1.6-specified test *"n_resamples=100 vs 10_000 consistency direction (wider with fewer resamples)"* is also absent (replaced by `invalid_alpha` / `too_few_resamples`). The math-equivalence claim in the story is therefore only half-delivered. (The AC-13.1.6 completion note is honestly worded — it does not claim scipy-bootstrap parity — but D-8/Dev Notes do.)

**Evidence:** `grep "scipy" tests/unit/stats/test_advanced.py` → only `mannwhitneyu` reference appears; no `bootstrap` reference. AC-13.1.6 spec line "n_resamples=100 vs 10_000 consistency direction" has no corresponding test function.
**Fix:** Add a test comparing `compute_bootstrap_ci(..., method percentile)` against `scipy.stats.bootstrap(data, statistic, n_resamples=N, confidence_level=1-alpha, method="percentile", random_state=seed)` to within a tolerance for a fixed seed/distribution, OR amend D-8/Dev Notes to state the scipy-bootstrap cross-check was intentionally deferred (and why exact percentile parity is hard given separate RNG streams). Add the missing n_resamples-direction test.

---

### [LOW]-1: Test-count claims overstate actuals (honest-framing)

**File:** story Dev Agent Record / Completion Notes
**Issue:** The story repeatedly claims "31 unit tests" and "34 new Story 13.1 tests." The file defines 28 unit test functions; one is parametrized ×3 → **30 collected unit items**. With 3 integration smokes that's **33 new tests**, not 34. Minor, but the project's `feedback_honest_framing` norm requires numeric bars to match `wc`/collection reality.
**Evidence:** `tests/unit/stats/test_advanced.py`: 28 `def test_*` (one `@pytest.mark.parametrize(... [(42,10),(123,30),(7,100)])`) ⇒ 30 items. `tests/integration/stats/test_advanced_keywords.py`: 3.
**Fix:** Update the story to "30 unit + 3 integration = 33 new tests" (or rerun `pytest --collect-only -q tests/unit/stats/test_advanced.py | tail` and quote the count).

---

### [LOW]-2: Bootstrap CI raw-float branch silently drops `KeywordRun` elements in mixed lists

**File:** `src/AgentEval/stats/library.py` (Bootstrap CI body, the `else` branch)
**Issue:** Branch selection keys only off `samples[0]`. In the `list[float]` branch, `float_samples = [s for s in samples if not isinstance(s, KeywordRun)]` silently *filters out* any `KeywordRun` present in a mixed list rather than raising. A caller passing a heterogeneous list gets a silently-shortened sample with no error — a fake-green hazard for an off-by-some CI.
**Evidence:**
```python
else:
    float_samples: list[float] = [s for s in samples if not isinstance(s, KeywordRun)]
    numeric_samples = [float(s) for s in float_samples]
```
**Fix:** Either `float(s)` over all elements directly (letting a stray `KeywordRun` raise a `TypeError`), or explicitly `raise ValueError` on mixed-type input. Don't silently drop.

---

### [LOW]-3: Import gate probes top-level `scipy`, but helper imports `scipy.stats`

**File:** `src/AgentEval/stats/library.py` (`_ADVANCED_AVAILABLE` gate) vs `mannwhitney.py:38`
**Issue:** The gate succeeds on `import scipy`, but `mannwhitney.py` does `import scipy.stats`. A broken/partial scipy install where the top-level package imports but `scipy.stats` does not would pass the gate and then raise a raw `ImportError` from the helper — bypassing the canonical `[agenteval-advanced]` message. Low likelihood, but the gate and the actual dependency aren't the same symbol.
**Fix:** Probe `import scipy.stats` (and the specific numpy surface used) in the gate so the canonical message covers the real import the helpers perform.

---

**Total: 1 HIGH + 2 MED + 3 LOW**

The HIGH (Tier-1 / `seed=None` determinism violation) is the load-bearing finding: it's a genuine FR31a contract breach that the conformance harness structurally cannot catch (required-param skip), and the story's D-9 rationalization is directly contradicted by the verbatim FR31a text. MED-1 and MED-2 are real but bounded (a false doc claim and a half-met math-reference mandate). The implementation is otherwise correct — sign convention (Probe 1: −1.0 ✓), tie handling (Probe 3 ✓), predicate asymmetry (Probe 7 ✓), and `__post_init__` validators (Probe 8 ✓) all check out against source.
