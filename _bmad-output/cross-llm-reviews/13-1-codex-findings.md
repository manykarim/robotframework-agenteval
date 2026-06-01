OpenAI Codex v0.133.0
--------
workdir: /home/many/workspace/robotframework-agenteval
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019e82a3-826f-7160-85ed-9f806960aff2
--------
user
# Adversarial Code Review — Story 13.1: Advanced Statistical Primitives (PRD FR29a/b/c)

You are a SENIOR REVIEWER for the robotframework-agenteval project. Your job is to find REAL bugs, REAL drift, REAL spec-vs-implementation mismatches in Story 13.1's implementation. Do NOT pad output with nitpicks. Be ADVERSARIAL but HONEST.

## Project context

- robotframework-agenteval: open-source Robot Framework library evaluating AI coding agents. Python 3.12+, RF 7.x.
- Story 13.1 ships the Phase-2 `[agenteval-advanced]` stats keyword surface (FR29a Mann-Whitney U, FR29b Cliff's delta, FR29c Bootstrap CI). scipy + numpy gated behind the optional extra.
- The story file with full ACs, drift table (12 D-N items), tasks, and dev-record is at:
  `_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md`
- Phase-1 `StatsLibrary` precedent for return-type discipline (scalar `float` for AssertionEngine compatibility) lives at `src/AgentEval/stats/library.py`.

## Review prompt (re-derive cited facts from source per `feedback_citation_drift_first_class`)

For every claim the dev made in the story file's Completion Notes / D-N drift section / AC body, re-derive it from the source files (PRD: `_bmad-output/planning-artifacts/prd.md` L1537-1539 for FR29; architecture: `_bmad-output/planning-artifacts/architecture.md` L1306-1310; epics: `_bmad-output/planning-artifacts/epics.md` L2141-2156). Flag any drift between cited facts and source as a HIGH finding.

## Specific behavioral probes (per `feedback_codex_probe_fitness`)

1. **Sign convention.** For samples_a = [1..8], samples_b = [100..107], does `compute_mann_whitney_u(samples_a, samples_b).effect_size_r` equal a value near -1.0? Why must this be negative? Verify against the dev's "signed rank-biserial r = 2*U1/(n_a*n_b) - 1" formula.
2. **U-statistic convention.** scipy.stats.mannwhitneyu's `.statistic` is U1 (corresponding to samples_a). The dev computes `u_smaller = min(U1, U2)` and returns that as `u_statistic`. Is this consistent with the docstring claim "smaller of U1, U2 (canonical form across literature)"? Empirical check: for samples_a=[1..8], samples_b=[100..107], what's U1? What's U2? What does the code return?
3. **Ties handling in Cliff's delta.** The dev's brute-force implementation has `elif a < b: less += 1`, treating ties as 0 contribution. Is this the Cliff 1993 convention? Or are ties supposed to contribute 0.5/0.5?
4. **Bootstrap CI seed reproducibility.** The dev uses `numpy.random.default_rng(seed)`. Is this deterministic across numpy versions? Could the percentile bootstrap CI shift between numpy 2.0 and numpy 2.4?
5. **ImportError gate.** When `_ADVANCED_AVAILABLE = False`, all 3 keywords raise via `_raise_advanced_extra_missing(keyword_name)`. Does the message exactly match epics.md L2153 verbatim mandate ("install via: uv pip install robotframework-agenteval[agenteval-advanced]")?
6. **mypy.ini scipy ignore.** The dev added `[mypy-scipy.*] ignore_missing_imports = True`. Is this consistent with the existing claude-agent-sdk / openai-agents pattern? Are there any scipy.stats imports that should be tighter-typed but aren't?
7. **Predicate signature.** The dev requires `predicate: Callable[[KeywordRun], float]` (value-extractor, NOT boolean). Cliff's delta uses raw floats. Does the predicate semantic correctly distinguish from `Stat.Get Pass At K`'s boolean predicate? Document the asymmetry.
8. **Cross-story upstream lesson application.** Story 12.1 ships JudgeScore as a dataclass with `__post_init__` validators. Story 13.1 ships MannWhitneyResult similarly. Did the dev apply the Story 12.1 D-4 lesson about defensive boundary checks in `__post_init__`?

## Categorization

- **HIGH**: Real bug, real spec drift, real correctness defect. Would fail in production or violate the spec.
- **MED**: Significant quality issue. Test coverage gap on a load-bearing branch, missing edge case, suboptimal naming.
- **LOW**: Minor improvement opportunity. Style, docstring polish, idiom hint.

## Output format

For each finding, use this format:

```
### [HIGH/MED/LOW]-N: <one-line title>

**File:** `<path>:<line>`
**Issue:** <2-3 sentences>
**Evidence:** <verbatim code excerpt or test output>
**Fix:** <concrete patch suggestion>
```

End with a summary line: `**Total: X HIGH + Y MED + Z LOW**`.

## Story diff

The full diff being reviewed (1750 lines, 1520 inserted) is at `/tmp/story-13-1-review.diff`. Read it and analyze.

---

## Diff to review:

```diff
diff --git a/_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md b/_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md
new file mode 100644
index 0000000..86ed2ba
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md
@@ -0,0 +1,348 @@
+# Story 13.1: Advanced Statistical Primitives Behind `[agenteval-advanced]` Extra
+
+Status: review
+
+## Story
+
+As **Raj (Agent Developer)** doing multi-model statistical comparison,
+I want `Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap CI` keywords behind the `[agenteval-advanced]` optional extra (Phase-2 — FR29a/b/c),
+So that I can statistically compare two non-deterministic agent flows with proper effect-size + significance metrics — the killer Raj Phase-2 surface that Pass@k alone cannot deliver.
+
+## Pre-create-story drift check (51st use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+12 drifts caught — 6 fresh decisions from spec analysis + 6 UPSTREAM from Epic 12 review records (general patterns applicable to any new keyword surface, especially Story 12.1's `JudgeLibrary` precedent which is the most recent new-sub-library landing). **100% real-drift catch rate maintained through Epic 12 close (50 prior uses).** First Epic 13 story — no immediately-prior same-surface story for `feedback_cross_story_upstream_lesson_propagation` direct N+1 propagation (Story 12.3 was Tier-2 LLM-judge integration; Story 13.1 is Tier-1 stats keywords behind an opt-in extra — different surface). UPSTREAM lessons applied from Epic 12 cross-surface generic patterns.
+
+- **D-1 (HIGH — return-type drift PRD vs epic vs architecture; PRIMARY drift):** **3-way contradiction on FR29 return types.**
+  - **PRD L1537-1539 (canonical):** FR29a returns `MannWhitneyResult(u_statistic, p_value, effect_size_r)`; FR29b returns `float ∈ [-1, 1]` (scalar); FR29c returns `(lo, hi)` tuple.
+  - **Architecture L1537-1539:** echoes PRD verbatim.
+  - **Epics.md L2151 (Story 13.1 spec):** `MannWhitneyResult` with `u_statistic, p_value, n_a, n_b` (NO `effect_size_r`); "analogous for Cliff Delta (effect size) and Bootstrap CI (confidence interval on any predicate)" — IMPLIES dataclasses for all three (no scalar / no tuple).
+  - **Decision (fix-the-losing-source-NOW — PRD wins, EXTENDS):** the dev SHIPS PRD-conforming return types:
+    - `MannWhitneyResult(u_statistic: float, p_value: float, effect_size_r: float, n_a: int, n_b: int)` — UNION of PRD's `effect_size_r` + epic's `n_a, n_b` so both sources are satisfied (epic's `n_a, n_b` are useful sample-size context; PRD's `effect_size_r` is the rank-biserial effect size r = `1 - 2*U/(n_a*n_b)`).
+    - `Stat.Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b verbatim (NOT a dataclass).
+    - `Stat.Bootstrap Confidence Interval` returns `tuple[float, float]` per PRD FR29c verbatim (NOT a dataclass).
+    - **Same-commit fix:** amend epics.md L2151 to read: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]`; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29b/c."
+  - Aligns with **Story 6.3 D-1 resolution precedent**: `Get Pass At K` returns scalar `float` (NOT a dataclass) to preserve AssertionEngine `>=` / `<=` matcher compatibility; CI is a separate paired getter (`Get Pass At K Confidence Interval`). The Cliff Delta / Bootstrap CI scalar-or-tuple returns inherit this discipline.
+
+- **D-2 (HIGH — extras name drift PRD/architecture/epic vs ADR-001):** **2-vs-1 majority on the extras name.**
+  - **PRD L1255 / L1537 / architecture L1306 / epic L2153:** consistently `[agenteval-advanced]` — the literal pip install command is `uv pip install robotframework-agenteval[agenteval-advanced]`.
+  - **ADR-001 L70:** `agenteval[advanced]` extra (drift — missing the `agenteval-` prefix).
+  - Existing extras in `pyproject.toml` L66-90 use unprefixed names: `claude-code`, `claude-sdk`, `openai-agents`, `codex`, `copilot`.
+  - **Decision (fix-the-losing-source-NOW — PRD+architecture+epic majority wins):** extra IS named `agenteval-advanced` (literal, per PRD/architecture/epic). Same-commit amendment: ADR-001 L70 `agenteval[advanced]` → `agenteval[agenteval-advanced]` (or `robotframework-agenteval[agenteval-advanced]` for full clarity). Naming-convention divergence vs other extras is intentional per PRD wording — surfaces the agenteval-specific Stats opt-in.
+
+- **D-3 (HIGH — ImportError UX message contract, PRD-mandated):** epics.md L2153 mandates "ImportError on import without the extra has a clear message recommending `uv pip install robotframework-agenteval[agenteval-advanced]`." **Decision:** when scipy/numpy are unavailable, the `Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` keyword methods raise `ImportError` with the verbatim string `"Stat.<Keyword>: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`. Pre-import probe: a module-level `try: import scipy, numpy except ImportError as e: _ADVANCED_AVAILABLE = False, _ADVANCED_IMPORT_ERROR = e`. The `StatsLibrary` itself MUST remain importable WITHOUT the extra (core Phase-1 keywords stay functional); only the 3 Phase-2 keyword methods raise when invoked. UNIT tests verify both paths.
+
+- **D-4 (HIGH — predicate signature parity with Story 6.3 `Get Pass At K`):** Epic AC L2150 example uses `predicate=lambda r: r.cost_usd` (a value-extractor, NOT a boolean predicate). The Phase-1 `Stat.Get Pass At K` predicate is `Callable[[KeywordRun], bool]` (per `src/AgentEval/stats/library.py:176`). **Decision:** Mann-Whitney U / Cliff Delta / Bootstrap CI accept a `predicate: Callable[[KeywordRun], float]` — a **value-extractor** producing the numeric quantity to compare (e.g., `lambda r: r.latency_seconds`, `lambda r: r.result.cost_usd`). This is correctly DISTINCT from `Get Pass At K`'s boolean predicate because the underlying statistical tests need numeric samples, not pass/fail labels. Document the asymmetry in the keyword docstring. Default `predicate` is `None` → raise `ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")` — there is no sensible default numeric metric across all `KeywordRun` shapes.
+
+- **D-5 (MED — module file homes per architecture L1306-1308):** architecture pre-allocated:
+  - `src/AgentEval/stats/mannwhitney.py` — Phase 2 (in `[agenteval-advanced]` extra).
+  - `src/AgentEval/stats/cliffs_delta.py` — Phase 2.
+  - `src/AgentEval/stats/bootstrap.py` — Phase 2 (CI for binomial proportions; Wilson CI in Phase 1).
+  - **Decision:** ship at these exact paths (NOT in a single `advanced.py` file, NOT folded into `_internal.py`). Each module exports `compute_<name>(...)` pure helper + the result-type construction. The `StatsLibrary` keyword methods at `stats/library.py` delegate to the helpers. Mirrors Story 12.1's `judge/rubric.py` decision (architecture-pre-allocated file homes are honored verbatim).
+
+- **D-6 (MED — `[project.optional-dependencies]` advanced entry):** `pyproject.toml` L53-90 currently has NO `agenteval-advanced` entry. **Decision:** add `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]` to `[project.optional-dependencies]`. Floors: scipy 1.11+ has Python 3.12 wheels + the stable `scipy.stats.mannwhitneyu` (used as reference); numpy 2.x permitted (scipy 1.11+ supports). Per project pin-discipline (pyproject.toml L25-30 + epic L1629 precedent), the dep add is justified by direct AC-mandated need (epic L2153 verbatim). Per `bmad-dev-story` HALT: this is the pre-approved exception via epic L2153 ("scipy + numpy" mandated).
+
+- **D-7 (MED — Phase-1 baseline integration tests must remain green WITHOUT the extra):** Existing test suite at HEAD: 1605 passed + 10 skipped. The 3 new Phase-2 keywords MUST be importable WITHOUT scipy/numpy installed (i.e., the `StatsLibrary` class itself MUST NOT fail to import). **Decision:** unit tests at `tests/unit/stats/test_advanced.py` cover (a) WITH-extra happy paths + (b) WITHOUT-extra `ImportError` paths via `sys.modules` monkeypatching (`monkeypatch.setitem(sys.modules, "scipy", None)`); the `monkeypatch` setting `scipy=None` triggers `ImportError` on `import scipy.stats`. Verifies `_ADVANCED_AVAILABLE = False` branch. Phase-1 CI gate (without `[agenteval-advanced]` extra) MUST still pass — i.e., the `tests/unit/stats/test_advanced.py` test that exercises the `ImportError` branch must run cleanly in BOTH environments. The `pytest.importorskip("scipy")` idiom gates the WITH-extra tests.
+
+- **D-8 (MED — math verification against scipy reference, epic-AC-mandated):** epics.md L2155 mandates "unit tests verify math against scipy reference implementations." **Decision:** for `Stat.Mann Whitney U`, compare against `scipy.stats.mannwhitneyu` (use_continuity=False, alternative="two-sided" — the standard form). The `effect_size_r` rank-biserial correlation is computed as `r = 1 - 2*U/(n_a*n_b)` where U is the smaller of `U1, U2` per Glass-Hopkins-Jackson (1996). For `Stat.Cliff Delta`, compare against a hand-computed reference (Cliff 1993 brute-force formula `δ = (#a>b - #a<b) / (n_a * n_b)`) — scipy does NOT ship Cliff's delta directly. For `Stat.Bootstrap CI`, compare against `scipy.stats.bootstrap` with `confidence_level=0.95, method='percentile'`.
+
+- **D-9 (MED — `@tier` annotation: Tier-1 deterministic by inputs, not by call-cost):** **Stat.Mann Whitney U / Cliff Delta / Bootstrap CI are deterministic given fixed input sample lists.** They do NOT invoke LLM providers, do NOT fan out, do NOT mutate state. Compare to `Stat.Get Pass At K` which is `@tier(1)` per `library.py:171`. **Decision:** all 3 keywords are `@tier(1)` per the determinism contract (`docs/contracts/determinism-contract.md` L29 lists "Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap)" as the Tier-1 surface). Bootstrap CI's **seed-driven resampling** is internally deterministic given a fixed `seed: int | None = None` parameter — when seed is None, OS-entropy → non-deterministic but `@tier(1)` is preserved because the underlying computation is closed-form once samples are fixed (the seed parameter exists for reproducibility, not because the keyword is stochastic at the FR layer). Per Story 6.3 precedent (`Stat.Run N Times` is Tier-3 due to fan-out semantics; `Stat.Get Pass At K` is Tier-1 because it's a closed-form computation given fixed inputs).
+
+- **D-10 (LOW — `@guarded_fanout` non-application):** Tier-1 keywords are NEVER decorated with `@guarded_fanout` per Story 6.3 / `src/AgentEval/stats/library.py:170-176` precedent (`@guarded_fanout` is for Tier-3 fan-out only). **Decision:** no `@guarded_fanout` on Mann-Whitney U / Cliff Delta / Bootstrap CI. No `host_instance` budget propagation needed.
+
+- **D-11 (LOW — UPSTREAM from Story 12.1 D-9 / 11.1 trace_id placeholder discipline):** Mann-Whitney U / Cliff Delta / Bootstrap CI consume `list[KeywordRun]` samples; they DON'T produce new traces. **Decision:** no `trace_id` placeholder concern. The keywords are pure transformations on input samples.
+
+- **D-12 (LOW — carry-over catalog gate UPSTREAM Epic 12, 32nd consecutive):** Anticipated Phase-1.5 / Phase-2 carry-overs for Story 13.1:
+  - **DF-13.1-S1 (Phase-2):** `Stat.Mann Whitney U` `alternative="greater" / "less"` one-sided variants (Phase-1 ships two-sided only).
+  - **DF-13.1-S2 (Phase-2):** Bootstrap CI methods beyond percentile (BCa, BC-corrected). Phase-1 ships percentile only.
+  - **DF-13.1-S3 (Phase-2):** `MannWhitneyResult` add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` per Cohen's conventions.
+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-05-27): catalogue C83 + C84 + C85 in BOTH `phase-1-5-carry-overs.md` + `deferred-work.md` BEFORE invoking `/bmad-code-review` (Action #2 sub-pattern).
+
+## Acceptance Criteria
+
+### AC-13.1.1 — `StatsLibrary` 3 new Phase-2 keyword methods (FR29a/b/c)
+
+`src/AgentEval/stats/library.py` extends `StatsLibrary` with 3 new `@keyword`-decorated methods (added after `assert_run_determinism`, before the module footer):
+
+- `Stat.Mann Whitney U(runs_a: list[KeywordRun], runs_b: list[KeywordRun], *, predicate: Callable[[KeywordRun], float] | None = None) -> MannWhitneyResult` — `@tier(1)`. FR29a.
+- `Stat.Cliff Delta(runs_a: list[KeywordRun], runs_b: list[KeywordRun], *, predicate: Callable[[KeywordRun], float] | None = None) -> float` — `@tier(1)`. FR29b.
+- `Stat.Bootstrap Confidence Interval(samples: list[KeywordRun] | list[float], *, statistic: Callable[[list[float]], float] | None = None, predicate: Callable[[KeywordRun], float] | None = None, alpha: float = 0.05, n_resamples: int = 10_000, seed: int | None = None) -> tuple[float, float]` — `@tier(1)`. FR29c.
+
+Each keyword:
+- Probes `_ADVANCED_AVAILABLE` at the method body's first line; raises `ImportError` with the verbatim message in D-3 if False.
+- Delegates the math to `stats/mannwhitney.py` / `stats/cliffs_delta.py` / `stats/bootstrap.py` (per D-5).
+- Carries the Browser-Library-style `| =Arguments= | =Description= |` docstring + `[Tier 1 — Deterministic]` badge per `feedback_full_surface_retro_review` convention.
+
+`Stat.Mann Whitney U` semantics: two-sided alternative (Phase-1 ceiling per D-12 DF-13.1-S1); `use_continuity=False`; computes both U-statistics and returns the smaller one as the canonical `u_statistic` field (matches `scipy.stats.mannwhitneyu` default).
+
+`Stat.Cliff Delta` semantics: pure-Python brute-force computation per Cliff 1993 (`(#a>b - #a<b) / (n_a * n_b)`); pure-Python ≤ O(n_a * n_b) is fine for typical n ≤ 100 trials (the n=20 + n=50 cohorts are the Raj target). For n_a + n_b > 1000, document a Phase-2 algorithm-improvement carve-out.
+
+`Stat.Bootstrap Confidence Interval` semantics: percentile method (Phase-1 ceiling per D-12 DF-13.1-S2); `n_resamples=10_000` default; `seed` parameter for reproducibility (default `None` → OS entropy). The `statistic` parameter is `Callable[[list[float]], float]` (the function whose CI we want — e.g., `statistics.mean`, `statistics.median`). The `predicate` parameter extracts floats from `KeywordRun` inputs when `samples` is `list[KeywordRun]`; if `samples` is already `list[float]`, predicate is ignored. Default `statistic` is `statistics.mean`.
+
+### AC-13.1.2 — `MannWhitneyResult` dataclass (D-1 resolution)
+
+`src/AgentEval/stats/types.py` adds a new frozen dataclass after `KeywordRun`:
+
+```python
+@dataclass(frozen=True, slots=True)
+class MannWhitneyResult:
+    """Mann-Whitney U test result (PRD FR29a; Story 13.1).
+
+    Fields:
+        u_statistic: The smaller of U1, U2 (matches scipy.stats.mannwhitneyu default).
+        p_value: Two-sided p-value (matches scipy.stats.mannwhitneyu default).
+        effect_size_r: Rank-biserial correlation r = 1 - 2*U/(n_a*n_b) per
+            Glass-Hopkins-Jackson (1996). Range: [-1, 1].
+        n_a: Number of samples in the first group (after predicate extraction).
+        n_b: Number of samples in the second group.
+    """
+    u_statistic: float
+    p_value: float
+    effect_size_r: float
+    n_a: int
+    n_b: int
+```
+
+`__post_init__` validates: `n_a >= 1` AND `n_b >= 1` (else `ValueError`); `-1.0 <= effect_size_r <= 1.0` (else `ValueError`); `0.0 <= p_value <= 1.0` (else `ValueError`).
+
+### AC-13.1.3 — `pyproject.toml` `agenteval-advanced` extra
+
+`pyproject.toml` `[project.optional-dependencies]` adds:
+
+```toml
+# Story 13.1 (Epic 13) — Advanced statistical primitives (FR29a/b/c). Phase-2
+# keywords behind the `[agenteval-advanced]` extra: Stat.Mann Whitney U,
+# Stat.Cliff Delta, Stat.Bootstrap Confidence Interval. scipy is the math
+# reference (math-equivalence unit tests); numpy is scipy's transitive dep but
+# pinned here for clarity + override-safety.
+agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]
+```
+
+`uv lock` + `uv sync --extra agenteval-advanced` must succeed (no resolver conflict with the existing hard deps). The base install (`uv sync` without `--extra agenteval-advanced`) MUST NOT pull scipy/numpy.
+
+### AC-13.1.4 — Module file homes per architecture L1306-1308
+
+Each of the 3 new modules is a thin pure-helper module exposing `compute_<name>(...)` functions. The `StatsLibrary` keyword methods delegate to these helpers.
+
+**`src/AgentEval/stats/mannwhitney.py`** (NEW):
+- `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` — pure function using `scipy.stats.mannwhitneyu` for U and p; computes `effect_size_r` locally.
+- Module-level `try: import scipy.stats as _scipy_stats / except ImportError: _scipy_stats = None`; the `compute_*` function raises if `_scipy_stats is None`.
+
+**`src/AgentEval/stats/cliffs_delta.py`** (NEW):
+- `compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float` — pure-Python brute-force formula; no scipy/numpy strictly needed BUT module-level `try: import numpy / except ImportError: ...` still gates per the unified `[agenteval-advanced]` extra contract (consistency with the other 2 modules).
+
+**`src/AgentEval/stats/bootstrap.py`** (NEW):
+- `compute_bootstrap_ci(samples: list[float], statistic: Callable[[list[float]], float], alpha: float, n_resamples: int, seed: int | None) -> tuple[float, float]` — uses `numpy.random.Generator(seed)` for reproducibility; percentile method.
+- Module-level scipy + numpy ImportError gate per the unified contract.
+
+Each module's docstring documents the PRD FR (FR29a/b/c) + the Phase-1.5 carry-over (DF-13.1-S1/S2/S3) + the math reference.
+
+### AC-13.1.5 — `_ADVANCED_AVAILABLE` import gate at `stats/library.py`
+
+`src/AgentEval/stats/library.py` adds at module scope (near the existing `_BROWSER_STYLE_MIGRATED = True` marker):
+
+```python
+try:  # Story 13.1 — Phase-2 [agenteval-advanced] extra gate.
+    import scipy  # noqa: F401  # scipy + numpy required for FR29a/b/c.
+    import numpy  # noqa: F401
+    _ADVANCED_AVAILABLE = True
+    _ADVANCED_IMPORT_ERROR: ImportError | None = None
+except ImportError as _e:  # pragma: no cover  -- exercised via monkeypatch in tests
+    _ADVANCED_AVAILABLE = False
+    _ADVANCED_IMPORT_ERROR = _e
+```
+
+Each Phase-2 keyword method's first line:
+
+```python
+if not _ADVANCED_AVAILABLE:
+    raise ImportError(
+        f"Stat.{<keyword_name>}: scipy + numpy required. "
+        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
+    ) from _ADVANCED_IMPORT_ERROR
+```
+
+The `StatsLibrary` class itself MUST remain importable without scipy/numpy installed — verified by `tests/unit/stats/test_library.py` continuing to pass in the base environment.
+
+### AC-13.1.6 — Unit tests at `tests/unit/stats/test_advanced.py` (≥20 tests)
+
+**`tests/unit/stats/test_advanced.py`** (NEW; gated by `pytest.importorskip("scipy")` for the WITH-extra tests):
+
+- **Mann-Whitney U math (4 tests)**: identical samples → p≈1.0 + effect_size_r≈0; clearly separated samples → p < 0.05 + effect_size_r near ±1; n_a=1 OR n_b=1 edge case (scipy permits but warns); n_a=0 OR n_b=0 → ValueError.
+- **Mann-Whitney U vs scipy reference (3 tests)**: 3 randomly-seeded sample pairs (n=10/30/100); assert `u_statistic` matches `scipy.stats.mannwhitneyu(..., alternative='two-sided', use_continuity=False).statistic` to within 1e-9; assert `p_value` matches to within 1e-9.
+- **Cliff Delta math (5 tests)**: identical samples → δ ≈ 0; strict-dominance (all a > all b) → δ = 1.0; reverse-dominance → δ = -1.0; partial-overlap small → |δ| < 0.5; partial-overlap large → |δ| > 0.7.
+- **Bootstrap CI math (5 tests)**: known-distribution samples (uniform [0,1] n=1000 mean) → CI brackets 0.5 with 95% confidence (seed-reproducible verification); `seed=42` reproducibility (2 invocations identical); `n_resamples=100` vs `10_000` consistency direction (wider with fewer resamples); alpha=0.01 wider than alpha=0.05; empty `samples` → ValueError.
+- **`MannWhitneyResult` dataclass (3 tests)**: in-range fields accepted; `effect_size_r` out of [-1, 1] → ValueError; `p_value` out of [0, 1] → ValueError; frozen (mutation raises).
+- **Predicate value-extraction (2 tests)**: `predicate=lambda r: r.latency_seconds` extracts correctly from `KeywordRun`; `predicate=None` on Mann-Whitney U / Cliff Delta raises `ValueError("predicate is required...")`.
+- **ImportError gate WITHOUT extras (3 tests)**: `monkeypatch.setitem(sys.modules, "scipy", None)` + reload `stats.library` → `_ADVANCED_AVAILABLE = False`; calling `Stat.Mann Whitney U` raises `ImportError` with `"agenteval-advanced"` in the message; calling `Stat.Cliff Delta` likewise; calling `Stat.Bootstrap Confidence Interval` likewise. Use `monkeypatch.setitem(sys.modules, "scipy", None)` to simulate missing scipy without uninstalling.
+
+Plus integration smoke at `tests/integration/stats/test_advanced_keywords.py`: run all 3 keywords through the RF library entry point (via `Library    AgentEval`) with synthetic `KeywordRun` lists; assert returns are well-typed. Single happy-path per keyword (3 tests).
+
+### AC-13.1.7 — `docs/contracts/stability-surface.md` registry
+
+Append a new subsection `### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)`:
+
+- `Stat.Mann Whitney U` RF keyword + Python method `StatsLibrary.mann_whitney_u` — `provisional` label. Signature stable; `effect_size_r` computation may move to Phase-2 if scipy adds a native rank-biserial accessor.
+- `Stat.Cliff Delta` RF keyword + Python method `StatsLibrary.cliff_delta` — `provisional` label.
+- `Stat.Bootstrap Confidence Interval` RF keyword + Python method `StatsLibrary.bootstrap_ci` — `provisional` label. `n_resamples` default (10_000) is `provisional`; may tune in Phase-2.
+- `MannWhitneyResult` dataclass + 5 fields — `provisional` label. Phase-2 may extend with `effect_size_interpretation` (DF-13.1-S3).
+- `[agenteval-advanced]` extra group + `scipy>=1.11,<2.0` + `numpy>=1.26,<3.0` pin — `stable` (the extra name + pin discipline) / `provisional` (the specific pin floors may shift).
+
+### AC-13.1.8 — `docs/contracts/determinism-contract.md` amendment
+
+Append to the existing L29 entry: "(`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` shipped Story 13.1 Phase-2 under `[agenteval-advanced]` extra)." No new Tier classification — Tier-1 per D-9 + Story 6.3 precedent.
+
+### AC-13.1.9 — `docs/adr/ADR-001-architectural-influences-catalog.md` drift fix (D-2)
+
+L70 amended: `agenteval[advanced]` → `agenteval[agenteval-advanced]` (fix-the-losing-source-NOW). Same-commit.
+
+### AC-13.1.10 — Epic.md drift fix (D-1)
+
+L2151 amended in the same commit:
+- Old: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `n_a`, `n_b`; analogous for `Cliff Delta` (effect size) and `Bootstrap CI` (confidence interval on any predicate)."
+- New: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29c (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent)."
+
+### AC-13.1.11 — Phase-1.5 carry-over catalog amendment (UPSTREAM `feedback_carry_over_catalog_gate`, 32nd consecutive)
+
+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` get 3 new rows BEFORE invoking `/bmad-code-review`:
+
+- **C83** `DF-13.1-S1` — Phase-2: `Stat.Mann Whitney U` `alternative="greater" / "less"` one-sided variants.
+- **C84** `DF-13.1-S2` — Phase-2: Bootstrap CI methods beyond percentile (BCa, BC-corrected).
+- **C85** `DF-13.1-S3` — Phase-2: `MannWhitneyResult.effect_size_interpretation` field per Cohen's conventions.
+
+Each row follows the existing carry-over table column shape (ID / Description / Source / Priority / Effort / Owner / Acceptance criteria).
+
+### AC-13.1.12 — All-gates pass
+
+- `uv lock` + `uv sync` (base) succeeds without scipy/numpy in the resolved environment (base install unchanged).
+- `uv sync --extra agenteval-advanced` succeeds (scipy + numpy resolve cleanly).
+- `uv run pytest tests/` reports approximately **1605 + 23 = 1628 passed + 10 skipped** in the base env (the WITHOUT-extras ImportError tests use monkeypatch, so they run in base env; the WITH-extras math tests use `pytest.importorskip("scipy")` and SKIP in base env — count as additional skips).
+- `uv run pytest tests/ --extras agenteval-advanced` (or `uv sync --extra agenteval-advanced` then re-run) reports **all 23 new tests passing** (WITH-extras math tests now run).
+- `uv run ruff check src/ tests/` clean.
+- `uv run ruff format --check src/ tests/` clean.
+- `uv run mypy src/` clean (scoped to src; mypy on the new modules + library.py extension).
+- libdoc regeneration (per Epic 12 retro precedent): `uv run libdoc src/AgentEval/stats/library.py docs/keywords/stats.html` reflects the 3 new keywords with their Browser-Library-style docstrings.
+
+### AC-13.1.13 — Sprint-status
+
+`_bmad-output/implementation-artifacts/sprint-status.yaml` flips:
+- `epic-13: in-progress` (first Epic 13 story; was `backlog`).
+- `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done`.
+- `last_updated: 2026-06-01`.
+
+## Tasks / Subtasks
+
+- [x] **Task 1: Drift fixes (D-1 + D-2; same commit)** — amend `_bmad-output/planning-artifacts/epics.md:2151` per AC-13.1.10 + `docs/adr/ADR-001-architectural-influences-catalog.md:70` per AC-13.1.9.
+- [x] **Task 2: `pyproject.toml` extra add** (AC-13.1.3) — added `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]`. `uv lock` + `uv sync` + `uv sync --extra agenteval-advanced` all clean (scipy 1.17.1 + numpy 2.4.6 resolved).
+- [x] **Task 3: `src/AgentEval/stats/types.py`** (AC-13.1.2) — `MannWhitneyResult` frozen dataclass appended with `__post_init__` validators per D-1.
+- [x] **Task 4: `src/AgentEval/stats/mannwhitney.py`** (AC-13.1.4) — `compute_mann_whitney_u` helper shipped; uses `scipy.stats.mannwhitneyu` for U + p; computes signed rank-biserial `effect_size_r = 2*U1/(n_a*n_b) - 1` locally.
+- [x] **Task 5: `src/AgentEval/stats/cliffs_delta.py`** (AC-13.1.4) — `compute_cliff_delta` shipped via brute-force Cliff 1993 formula.
+- [x] **Task 6: `src/AgentEval/stats/bootstrap.py`** (AC-13.1.4) — `compute_bootstrap_ci` shipped using `numpy.random.Generator(seed)` + percentile method.
+- [x] **Task 7: `src/AgentEval/stats/library.py` extension** (AC-13.1.1 + AC-13.1.5) — module-level `_ADVANCED_AVAILABLE` gate + 3 new `@keyword + @tier(1)`-decorated methods (`compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci` — renamed from `mann_*` / `cliff_*` / `bootstrap_*` per the verb-allowlist convention test).
+- [x] **Task 8: `tests/unit/stats/test_advanced.py`** (AC-13.1.6) — 31 unit tests shipped covering math vs scipy reference + dataclass validators + ImportError gate + predicate value-extraction.
+- [x] **Task 9: `tests/integration/stats/test_advanced_keywords.py`** (AC-13.1.6) — 3 integration smoke tests through `StatsLibrary` surface.
+- [x] **Task 10: `docs/contracts/stability-surface.md`** (AC-13.1.7) — `### Stat. Advanced Surface (Phase-2 — [agenteval-advanced])` subsection registered.
+- [x] **Task 11: `docs/contracts/determinism-contract.md`** (AC-13.1.8) — L29 entry amended per Phase-2 ship.
+- [x] **Task 12: Phase-1.5 carry-over catalog gate UPSTREAM (32nd consecutive)** (AC-13.1.11) — C83 + C84 + C85 added to both `docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md`.
+- [x] **Task 13: All-gates pass** (AC-13.1.12) — ruff/format/mypy/license-headers clean. `uv run pytest tests/` reports **1823 passed + 14 skipped** (was 1605+10 at HEAD; +218 net incl. 34 new Story 13.1 tests + pre-existing telemetry/conformance/etc. tests now executing). mypy clean on 106 src files. No regressions.
+- [x] **Task 14: Sprint-status flip** (AC-13.1.13) — flipped Epic 13 → `in-progress`, Story 13.1 → `review`; `last_updated: 2026-06-01`.
+
+## Dev Notes
+
+Building on the Phase-1 `StatsLibrary` foundation:
+- **Story 6.3** shipped `StatsLibrary` + `Stat.Run N Times` (Tier-3) + `Stat.Get Pass At K` (Tier-1) + `Stat.Get Pass At K Confidence Interval` (Tier-1, Wilson) + `Stat.Assert Run Determinism` (Tier-1). Story 13.1 EXTENDS this surface with 3 new Phase-2 keyword methods.
+- **Story 6.3 D-1 resolution precedent (LOAD-BEARING for D-1 here):** `Get Pass At K` returns scalar `float` (NOT a dataclass) to preserve AssertionEngine matcher compatibility; CI is a separate paired getter. The Cliff Delta / Bootstrap CI scalar-or-tuple returns inherit this discipline. Mann-Whitney U justifies a dataclass return because the 3-tuple `(u_statistic, p_value, effect_size_r)` + sample sizes form a cohesive result the operator typically inspects as a unit.
+- **Story 12.1 precedent for new sub-library file homes:** architecture's pre-allocated file homes (`stats/mannwhitney.py` + `stats/cliffs_delta.py` + `stats/bootstrap.py`) are honored verbatim per Story 12.1's `judge/rubric.py` decision.
+- **Story 12.1 + 11.x precedent for new optional extras:** Story 11.1-11.3 added 3 CLI-adapter extras (`codex`, `copilot`, `claude-code`); Story 10.1+10.2 added 2 SDK extras (`claude-sdk`, `openai-agents`). Story 13.1's `agenteval-advanced` extra follows the same `[project.optional-dependencies]` pattern but uses a longer name per PRD's explicit `[agenteval-advanced]` wording (D-2 resolution).
+
+**Key implementation detail — `_ADVANCED_AVAILABLE` gate placement.** The gate MUST sit at module-import time in `stats/library.py` so the `StatsLibrary` class itself remains importable without scipy/numpy. Each Phase-2 keyword method's body's first line is the per-method `ImportError` raise — this defers the failure to invocation-time, not import-time, preserving Phase-1 functionality. **This is the same pattern used by `scipy.stats` itself** (functions import their dependencies at call time).
+
+**Math reference cross-checking** is the AC-13.1.6 priority (epic L2155 verbatim). Mann-Whitney U: use `scipy.stats.mannwhitneyu(samples_a, samples_b, alternative="two-sided", use_continuity=False)` as the GROUND TRUTH. Document the scipy call signature in `mannwhitney.py`'s docstring so future scipy version changes are auditable. Same for Bootstrap CI: `scipy.stats.bootstrap(data, statistic, n_resamples=10_000, confidence_level=1-alpha, method="percentile", random_state=seed)`.
+
+**UPSTREAM Story 12.1 → Story 13.1 generic lessons (cross-surface, no immediate N+1 propagation):**
+- D-2 (return-type drift): same fix-the-losing-source-NOW pattern that Story 12.1 used for `JudgeScore` shape — PRD wins; epics.md amends in the same commit. Applied here.
+- D-5 (math/scipy reference): same defensive empirical-verification pattern that Story 12.1 used for `JudgeOutputParseError` JSON parse. Applied: scipy-reference-comparison tests per AC-13.1.6.
+- D-12 (carry-over catalog gate UPSTREAM at Task N-1): same 31-consecutive-stories pattern. Applied as Task 12 BEFORE Task 13 (pytest gates).
+
+**No `@guarded_fanout` on Tier-1 keywords (D-10).** Mann-Whitney U / Cliff Delta / Bootstrap CI do NOT invoke LLM providers; they are pure transformations on input samples (which themselves came from prior `Stat.Run N Times` Tier-3 fan-outs that ALREADY enforced budgets). The Phase-2 stats keywords inherit budget protection by composition.
+
+### Project Structure Notes
+
+- Module file homes per architecture L1306-1308: `stats/mannwhitney.py` + `stats/cliffs_delta.py` + `stats/bootstrap.py` are pre-allocated NEW files.
+- `stats/types.py` is EXTENDED (append `MannWhitneyResult` after existing `KeywordRun`).
+- `stats/library.py` is EXTENDED (add 3 new methods + module-level `_ADVANCED_AVAILABLE` gate).
+- `tests/unit/stats/test_advanced.py` is NEW.
+- `tests/integration/stats/test_advanced_keywords.py` is NEW.
+- `pyproject.toml` extends `[project.optional-dependencies]` with `agenteval-advanced`.
+- `docs/contracts/stability-surface.md` + `docs/contracts/determinism-contract.md` are amended (append-only).
+- `docs/adr/ADR-001-architectural-influences-catalog.md` + `_bmad-output/planning-artifacts/epics.md` are amended in the SAME COMMIT per D-1/D-2 fix-the-losing-source-NOW.
+
+### References
+
+- PRD: `_bmad-output/planning-artifacts/prd.md` L1537-1539 (FR29a/b/c canonical signatures + return types).
+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1306-1310 (`stats/{mannwhitney,cliffs_delta,bootstrap,wilson}.py` file homes); L1255 (`[agenteval-advanced]` extra row); L1683 + L1827 (Phase-2 architectural additions including FR29a/b/c).
+- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2141-2156 (Story 13.1 detailed).
+- Prior story: `_bmad-output/implementation-artifacts/6-3-statistical-primitives-tier-acl-determinism-enforcement.md` (Phase-1 `StatsLibrary` foundation; D-1 scalar-return precedent at L100, L103).
+- Prior story: `_bmad-output/implementation-artifacts/12-1-judge-get-score-keyword-basic-rubric-support.md` (new sub-library file home + ImportError discipline; D-3 dataclass + D-7 entry-point declare-only patterns).
+- Contracts: `docs/contracts/determinism-contract.md` L29 (Tier-1 statistical primitives surface); `docs/contracts/stability-surface.md` (label-scheme + registry).
+- ADR-001: `docs/adr/ADR-001-architectural-influences-catalog.md` L70 (agentguard ADR-005 → agenteval Stats adoption with Phase-2 Epic 13 advanced primitives).
+- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (51st use); `feedback_carry_over_catalog_gate.md` UPSTREAM (32nd); `feedback_full_surface_retro_review.md` (Browser-Library-style docstring discipline); `feedback_codex_probe_fitness.md` (empirical scipy reference tests).
+
+## Dev Agent Record
+
+### Agent Model Used
+
+claude-opus-4-7[1m]
+
+### Debug Log References
+
+None. All gates green on first full sweep.
+
+### Completion Notes List
+
+Story 13.1 dev complete — opens Epic 13 (Phase-2 advanced stats surface).
+
+- **AC-13.1.1**: 3 new `@keyword + @tier(1)`-decorated methods on `StatsLibrary` (`compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci`). Methods renamed from `mann_whitney_u` / `cliff_delta` / `bootstrap_ci` to start with `compute` per the verb-allowlist convention test (`tests/unit/conventions/test_keyword_name_idiom.py` + `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`). RF keyword names (`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval`) preserved per PRD/epic verbatim — only the internal Python method names changed.
+- **AC-13.1.2**: `MannWhitneyResult` frozen dataclass at `stats/types.py` with 5 fields per D-1 union resolution (`u_statistic, p_value, effect_size_r, n_a, n_b`). `__post_init__` enforces invariants per D-1 verbatim.
+- **AC-13.1.3**: `pyproject.toml` `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]`. `uv lock` + `uv sync` (base) + `uv sync --extra agenteval-advanced` all clean.
+- **AC-13.1.4**: 3 helper modules at architecture-pre-allocated paths (`stats/mannwhitney.py`, `stats/cliffs_delta.py`, `stats/bootstrap.py`). Each carries the appropriate scipy/numpy imports per the unified extras contract.
+- **AC-13.1.5**: `_ADVANCED_AVAILABLE` module-level gate + `_raise_advanced_extra_missing(keyword_name)` helper. `StatsLibrary` class itself remains importable WITHOUT scipy/numpy (existing 1605 tests still pass).
+- **AC-13.1.6**: 31 unit tests + 3 integration smoke tests at the expected paths. Math correctness for Mann-Whitney U verified against `scipy.stats.mannwhitneyu` within `1e-9` across 3 seeded sample sizes (n=10/30/100). Bootstrap CI seed-reproducibility + α=0.01-wider-than-α=0.05 invariants verified. Cliff delta covers all 4 magnitude bands.
+- **AC-13.1.7**: `### Stat. Advanced Surface (Phase-2)` subsection in `stability-surface.md` with 4 surface registry entries + extras-name + ImportError message format `stable`.
+- **AC-13.1.8**: `determinism-contract.md` L29 amended per Phase-2 ship.
+- **AC-13.1.9 + AC-13.1.10**: D-1 + D-2 drift fixes shipped IN THIS SAME COMMIT: `epics.md` L2151 amended (`MannWhitneyResult` field list + tuple return type for Bootstrap CI per PRD); ADR-001 L70 amended (`agenteval[advanced]` → `[agenteval-advanced]` per PRD majority).
+- **AC-13.1.11**: C83/C84/C85 catalogued UPSTREAM in both `phase-1-5-carry-overs.md` (total 85 items, up from 82) + `deferred-work.md` (3 new entries under new "Deferred from: story-13.1 dev" section). 32nd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use.
+- **AC-13.1.12**: All-gates pass. `uv run pytest tests/`: **1823 passed + 14 skipped** (was 1605+10 baseline; +218 net). ruff/format/mypy/license-headers all clean on Story 13.1's new + modified files. mypy.ini extended with `[mypy-scipy.*]` ignore-missing-imports allowlist per Story 10.1/11.x precedent.
+- **AC-13.1.13**: sprint-status flipped (`epic-13: in-progress`, `13-1-*: review`).
+
+### In-flight spec amendments (per `feedback_in_flight_spec_amendment`)
+
+1. **AC-13.1.1 method-name amendment:** spec originally named the Python methods `mann_whitney_u` / `cliff_delta` / `bootstrap_ci`. Convention test `test_keyword_names_start_with_allowlist_verb` (verb-allowlist gate) rejects `mann` / `cliff` / `bootstrap` as non-allowed first tokens. Amended in-flight per `feedback_in_flight_spec_amendment`: methods renamed to `compute_*` (which IS in the allowlist + matches the helper module-level function naming). RF keyword names (`Stat.Mann Whitney U` etc.) unchanged per PRD/epic — only internal Python method names changed. AC-13.1.1 task box updated to reflect this rename.
+
+2. **AC-13.1.6 ImportError test consolidation:** spec text said "3 keywords × monkeypatch" for the ImportError gate tests. Empirical finding: `sys.modules` reload via `importlib.reload` perturbs the import state across tests; running 3 separate tests left `AgentEval.stats.library` in a partial-import state between tests. Amended in-flight: ImportError gate verified via two consolidated tests — (a) `test_raise_advanced_extra_missing_helper_carries_canonical_message` directly exercises the helper to verify the spec-mandated message format; (b) `test_phase2_keywords_raise_import_error_when_extra_unavailable` monkeypatches `_ADVANCED_AVAILABLE` on the live module and exercises all 3 keyword methods. Coverage equivalent; cross-test pollution eliminated.
+
+### Sign-convention discovery (effect_size_r)
+
+Initial `effect_size_r = 1.0 - 2.0 * u1 / (n_a * n_b)` formula (Glass-Hopkins-Jackson 1996 magnitude convention with min(U)) produced WRONG sign for clearly separated samples_a < samples_b (gave +1.0 instead of -1.0). Empirical test `test_mannwhitney_clearly_separated_samples_p_value_small` caught this immediately. Fixed via the SIGNED rank-biserial convention `r = 2 * U1 / (n_a * n_b) - 1` (where U1 is the scipy default, i.e., the U-statistic for samples_a). This matches Cliff's delta sign convention shipped by `Stat.Cliff Delta` — positive r means samples_a tends to be larger; negative r means samples_b tends to be larger. Docstrings updated across types.py + library.py + mannwhitney.py.
+
+### File List
+
+**New files:**
+- `src/AgentEval/stats/mannwhitney.py` — Mann-Whitney U primitive (FR29a).
+- `src/AgentEval/stats/cliffs_delta.py` — Cliff's delta effect-size primitive (FR29b).
+- `src/AgentEval/stats/bootstrap.py` — Bootstrap CI primitive (FR29c).
+- `tests/unit/stats/test_advanced.py` — 31 unit tests.
+- `tests/integration/stats/__init__.py` — package marker for the new integration test dir.
+- `tests/integration/stats/test_advanced_keywords.py` — 3 integration smoke tests.
+
+**Modified files:**
+- `src/AgentEval/stats/types.py` — appended `MannWhitneyResult` frozen dataclass.
+- `src/AgentEval/stats/library.py` — `_ADVANCED_AVAILABLE` gate + `_raise_advanced_extra_missing` helper + 3 new `@keyword + @tier(1)`-decorated methods.
+- `pyproject.toml` — `agenteval-advanced` optional-dependencies entry.
+- `mypy.ini` — `[mypy-scipy.*] ignore_missing_imports = True` allowlist.
+- `docs/contracts/stability-surface.md` — new `### Stat. Advanced Surface (Phase-2 — [agenteval-advanced])` subsection.
+- `docs/contracts/determinism-contract.md` — L29 amended with Phase-2 stats clause.
+- `docs/adr/ADR-001-architectural-influences-catalog.md` — L70 `agenteval[advanced]` → `[agenteval-advanced]` (D-2 fix-the-losing-source-NOW).
+- `_bmad-output/planning-artifacts/epics.md` — L2151 amended per D-1 (return-type drift fix).
+- `docs/phase-1-5-carry-overs.md` — C83 + C84 + C85 entries + total bumped 82→85.
+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.1 dev" section with 3 entries.
+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — epic-13 → `in-progress`, Story 13.1 → `review`, `last_updated: 2026-06-01`.
diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
index df11950..1c4644c 100644
--- a/_bmad-output/implementation-artifacts/deferred-work.md
+++ b/_bmad-output/implementation-artifacts/deferred-work.md
@@ -366,6 +366,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
 
 - **DF-12.2-S2 (Phase-2 active-learning calibration set curation)** — Story 12.2 D-8 path-of-least-amendment decision 2026-05-27 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Phase-1 ships `load_calibration_set` reading a static human-curated YAML calibration set. Phase-2 work: auto-select diverse calibration examples from the operator's existing trace history (cluster by `cost_usd`/`latency`/`tool_count` distribution, pick representatives from each cluster); semi-supervised labeling UX where the human labels only the highest-uncertainty examples. Catalogued as C82. Effort: L (active-learning calibration set curator + semi-supervised labeling UX + uncertainty-sampling integration test). Phase-2.
 
+## Deferred from: story-13.1 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
+
+- **DF-13.1-S1 (Phase-2 one-sided alternatives for `Stat.Mann Whitney U`)** — Story 13.1 D-12 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Phase-1 ships two-sided Mann-Whitney U only (matches PRD FR29a verbatim signature). Phase-2 work: extend the keyword with an `alternative: Literal["two-sided", "greater", "less"] = "two-sided"` kwarg per `scipy.stats.mannwhitneyu` signature; update `MannWhitneyResult` docstring to clarify which tail the `p_value` corresponds to under each alternative. Catalogued as C83. Effort: S. Phase-2.
+
+- **DF-13.1-S2 (Phase-2 BCa / BC-corrected Bootstrap CI methods)** — Story 13.1 D-12 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Phase-1 ships percentile bootstrap only (`method="percentile"`). Phase-2 work: implement BCa (bias-corrected & accelerated) + BC (bias-corrected) variants per `scipy.stats.bootstrap(method=)` signature; add `method: Literal["percentile", "bca", "bc"] = "percentile"` kwarg to `Stat.Bootstrap Confidence Interval`. Catalogued as C84. Effort: M. Phase-2.
+
+- **DF-13.1-S3 (Phase-2 `MannWhitneyResult.effect_size_interpretation` Cohen-band Literal field)** — Story 13.1 D-12 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Phase-1 ships raw `effect_size_r` only. Phase-2 work: add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` field per Cohen's conventions (negligible: `|r| < 0.1`; small: `0.1 <= |r| < 0.3`; medium: `0.3 <= |r| < 0.5`; large: `|r| >= 0.5`); derive deterministically in `__post_init__`. Catalogued as C85. Effort: XS. Phase-2.
+
 ---
 
 *Update this file as new deferred items emerge from future reviews.*
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index ae99375..f46a742 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -35,7 +35,7 @@
 # - Dev moves story to 'review', then runs code-review (fresh context, different LLM recommended)
 
 generated: 2026-05-17
-last_updated: 2026-05-20
+last_updated: 2026-06-01
 project: robotframework-agenteval
 project_key: NOKEY
 tracking_system: file-system
@@ -150,8 +150,8 @@ development_status:
   12-3-three-tier-stacked-validation-integration-completes-devons-journey-4: done  # Story 12.3 done 2026-05-27. Closes Epic 12 + Devon's Journey 4 Tier-2 slot. Recipe Gallery #4 Tier-2 populated with actual Judge.Get Score invocation; 5 integration tests at test_devon_three_tier_complete.py (Tier-1 + Tier-2 + Tier-3 + coherent-pass + coherent-fail). 2-tier Claude CLI review → 6 findings (2 HIGH + 2 MED + 2 LOW; 1 cross-tier 2-way agreement on recipe imports). All applied: class-path import migration retires SkillsLibrary dryrun-fail framing; full recipe dryrun-clean. Final: 1775 passed + 14 skipped (was 1770 + 14; +5 tests).
   epic-12-retrospective: done  # Epic 12 retro closed 2026-06-01. 3-tier cross-LLM critical review (Claude opus + Codex + Kilo/minimax-M2.7) — first full 3-of-3 retro-on-retro chain since CLAUDE.md ratification. 9 findings applied (7 HIGH + 5 MED + 2 Kilo-MED). 3 cross-tier 2-way HIGH agreements (memory file canonical-source drift, commit range 5-vs-4, ❌ tally 8-vs-7-with-⚠) + 4 reviewer-UNIQUE (Claude HIGH-1, Codex HIGH-4, Kilo MED-1+MED-2). Norms: 1 EXTENDED at N=5 (cross-story upstream — memory file ACTUALLY updated this time per Claude HIGH-1); 4 EXTENDED (spec-precheck 50 uses, catalog-gate 31 stories, monkeypatch-decorator-walk, n-way-agreement intra-family); 1 NEW + CONFIRMED at N=1 (libdoc namespace multi-word convention); 1 RETIRED (retro-debt-block — memory stub created for paper trail per Kilo MED-1).
 
-  epic-13: backlog
-  13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: backlog
+  epic-13: in-progress  # Story 13.1 ready-for-dev 2026-06-01; first Epic 13 story (Advanced Stats Phase-2 surface).
+  13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: review
   13-2-otlp-trace-backend: backlog
   13-3-compare-tool-discoverability-cross-adapter: backlog
   13-4-cohort-heatmap-html-rendering: backlog
diff --git a/_bmad-output/planning-artifacts/epics.md b/_bmad-output/planning-artifacts/epics.md
index 52c6f88..c72ae30 100644
--- a/_bmad-output/planning-artifacts/epics.md
+++ b/_bmad-output/planning-artifacts/epics.md
@@ -2148,7 +2148,7 @@ So that I can statistically compare two non-deterministic agent flows with prope
 
 **Given** two `Stat.Run N Times` result lists,
 **When** I call `${u}=    Stat.Mann Whitney U    ${results_a}    ${results_b}    predicate=lambda r: r.cost_usd`,
-**Then** the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `n_a`, `n_b`; analogous for `Cliff Delta` (effect size) and `Bootstrap CI` (confidence interval on any predicate).
+**Then** the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29c (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent).
 
 **And** all advanced stats keywords are behind `[agenteval-advanced]` extra (requires `scipy + numpy`); ImportError on import without the extra has a clear message recommending `uv pip install robotframework-agenteval[agenteval-advanced]`.
 
diff --git a/docs/adr/ADR-001-architectural-influences-catalog.md b/docs/adr/ADR-001-architectural-influences-catalog.md
index 9881874..46393dc 100644
--- a/docs/adr/ADR-001-architectural-influences-catalog.md
+++ b/docs/adr/ADR-001-architectural-influences-catalog.md
@@ -67,7 +67,7 @@ Source: `/home/many/workspace/robotframework-agentguard/docs/adr/` (22 ADRs revi
 | [agentguard ADR-002 MCP Transport Strategy](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-002-mcp-transport-strategy.md) | MCP transport selection logic (stdio vs streamable HTTP). | `borrow-concept` | agenteval's hosted-MCP universal observation pattern (ADR-004) goes BEYOND transport selection — it imposes a per-test scoping model (ADR-009) and a coverage-detection contract (ADR-016) that have no analog in agentguard. |
 | [agentguard ADR-003 Library Composition](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-003-library-composition.md) | DynamicCore composition with bounded sub-libraries, lazy-loaded. | `adapt` | agenteval also uses DynamicCore composition (16 sub-libraries per architecture.md project tree); the sub-library decomposition differs because agenteval's domain differs (evaluating coding agents vs guardrails). |
 | [agentguard ADR-004 Tool-Call Matching](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-004-tool-call-matching.md) | Heuristics for matching observed tool calls against expected ones. | `adapt` | agenteval's tool-call matching surfaces via `metrics/` keywords (e.g., `Get Tool Hit Rate`); the matching heuristics are reviewed but agenteval applies them to its own per-test scoping. |
-| [agentguard ADR-005 Statistical Assertion API](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-005-statistical-assertion-api.md) | Statistical primitives (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap). | `adapt` | agenteval's `Stat.` sub-library starts from agentguard's primitives; advanced primitives gated behind `agenteval[advanced]` extra (Phase 2 — Epic 13). |
+| [agentguard ADR-005 Statistical Assertion API](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-005-statistical-assertion-api.md) | Statistical primitives (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap). | `adapt` | agenteval's `Stat.` sub-library starts from agentguard's primitives; advanced primitives gated behind `[agenteval-advanced]` extra (Phase 2 — Epic 13; ratified Story 13.1 fix-the-losing-source-NOW amendment 2026-06-01 — drift from PRD/architecture/epic consistent `[agenteval-advanced]` wording). |
 | [agentguard ADR-006 Skill Discovery Default-Deny](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-006-skill-discovery-default-deny.md) | Skills default to disabled; explicit allow-list required. | `explicitly-diverge` | agenteval's `Skill.` keywords *inspect* (static analysis) rather than *enforce* skill activation. Default-deny is the wrong posture for an evaluation framework — evaluators need to observe what skills WOULD activate, not block them. |
 | [agentguard ADR-007 Hook Test Harness](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-007-hook-test-harness.md) | Test harness for agent hooks (pre-tool, post-tool). | `borrow-concept` | agenteval's `hooks/` sub-library has its own static-inspection keywords; the test-harness *concept* (hook-aware testing) is shared but the implementation is independent. |
 | [agentguard ADR-008 Subagent A2A Harness](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-008-subagent-a2a-harness.md) | Agent-to-agent (A2A) communication test harness for subagents. | `borrow-concept` | agenteval's `subagents/` sub-library inspects subagent definitions statically; A2A runtime harness is out of scope for Phase 1 (re-evaluate Phase 2). |
diff --git a/docs/contracts/determinism-contract.md b/docs/contracts/determinism-contract.md
index c9dce02..a9bcd1d 100644
--- a/docs/contracts/determinism-contract.md
+++ b/docs/contracts/determinism-contract.md
@@ -26,7 +26,7 @@ The following single-paragraph summary is **byte-identical** to PRD L1211 per FR
 
 ### Out-of-scope
 
-- Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap) — that's the `Stat.` library docstrings + `stability-surface.md`.
+- Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap) — that's the `Stat.` library docstrings + `stability-surface.md`. (Phase-2: `Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` shipped Story 13.1 under the `[agenteval-advanced]` extra; all Tier-1 per the closed-form / seed-deterministic computation classification.)
 - The specific seed-management strategy for `Stat.Run N Times` — Epic 6 Story 6.x owns the seed contract.
 
 ## Contract
diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
index 7b15c5d..b51529f 100644
--- a/docs/contracts/stability-surface.md
+++ b/docs/contracts/stability-surface.md
@@ -122,6 +122,16 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
 - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 
+### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)
+
+Per Story 13.1 (PRD FR29a/b/c) — Phase-2 advanced statistical primitives gated behind the `[agenteval-advanced]` optional extra (scipy + numpy):
+
+- `Stat.Mann Whitney U` RF keyword + Python method `StatsLibrary.mann_whitney_u` — `provisional` label. Returns `MannWhitneyResult` (two-sided test only — `alternative="greater"`/`"less"` variants Phase-2 / DF-13.1-S1). Signature stable; `effect_size_r` computation is signed rank-biserial (`r = 2 * U1 / (n_a * n_b) - 1`) matching `Stat.Cliff Delta`'s sign convention.
+- `Stat.Cliff Delta` RF keyword + Python method `StatsLibrary.cliff_delta` — `provisional` label. Returns scalar `float ∈ [-1.0, 1.0]` per PRD FR29b (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent).
+- `Stat.Bootstrap Confidence Interval` RF keyword + Python method `StatsLibrary.bootstrap_ci` — `provisional` label. Returns `tuple[float, float]` (lo, hi) percentile bootstrap CI. Percentile method only (BCa + BC-corrected variants Phase-2 / DF-13.1-S2). Default `n_resamples=10_000` is `provisional`. `seed` parameter enables reproducibility.
+- `AgentEval.stats.types.MannWhitneyResult` frozen dataclass — `provisional` label. 5 fields: `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`. `__post_init__` validators (`n_a/n_b >= 1`, `effect_size_r ∈ [-1, 1]`, `p_value ∈ [0, 1]`) are `stable`. Phase-2 may extend with `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` per DF-13.1-S3.
+- `[agenteval-advanced]` optional-dependencies extra (`scipy>=1.11,<2.0` + `numpy>=1.26,<3.0`) — extra NAME (`agenteval-advanced`) is `stable`; the version pins are `provisional` (floors may shift as scipy/numpy 2.x baselines stabilize). The 3 keywords raise `ImportError` with the verbatim message `"Stat.<Keyword>: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"` when invoked without the extra — message format is `stable`.
+
 ### Sandbox Protocol Surface
 
 Per ADR-018 (`adopt` from agentguard ADR-013 with significant divergence — see `docs/adr/ADR-001-architectural-influences-catalog.md` agentguard ADR-013 row):
diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
index 74deca7..ab7ab47 100644
--- a/docs/phase-1-5-carry-overs.md
+++ b/docs/phase-1-5-carry-overs.md
@@ -106,8 +106,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
 | **C73** | **Phase-2: `HostedMcpObserver` wiring for Codex CLI MCP-attachment (`DF-11.1-S1`).** Story 11.1 dev decision 2026-05-26 (parallel to C68 + C69 for Claude+OpenAI SDKs). Codex CLI's `--json` JSONL event surface (`thread.started` / `turn.started` / `item.*` / `turn.completed`) does NOT include any MCP-attachment confirmation event. Until empirical verification of the codex MCP attachment signal (likely via the `codex mcp` subcommand + `~/.codex/config.toml` inspection), non-empty `mcp_servers` falls back to `external_mixed` per ADR-016 §Decision L33. Phase-2: integration test against live binary to discover whether MCP-attachment manifests in stream events + wire `HostedMcpObserver.attach()` per the codex MCP server registration callback (mirrors C68's Claude resolution). | Story 11.1 D-7 decision — Phase-1 detection ceiling | correctness | M | TBD | Live-binary probe + attachment-surface wiring + observer-based detection + promote to `hosted_in_process` only on verified attachment per ADR-016. |
 | **C74** | **Phase-1.5: Codex CLI cost-catalog integration (`DF-11.1-S2`).** Story 11.1 D-9 dev decision 2026-05-26: Codex `turn.completed` events carry usage tokens (`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`) but NO `cost_usd` field — Codex pricing is `gpt-5-codex`-tier which is not in Phase-1 cost catalog. Phase-1 ships `cost_usd=0.0` placeholder. **Prerequisite resolved 2026-05-26 (kilo M-4 catch):** the `Usage` dataclass was extended with `reasoning_output_tokens: int = 0` field at Story 11.1 kilo HIGH-1 fix; all 4 token fields now flow end-to-end. Phase-1.5: extend cost catalog with `gpt-5-codex` pricing rows; compute `cost_usd` from `(input_tokens, output_tokens, reasoning_output_tokens, cached_input_tokens)` per the published OpenAI Codex pricing table. | Story 11.1 D-9 decision — empirical-probe finding | correctness | S | TBD | Cost catalog row added + `_extract_cost` reads from catalog + removes the `0.0` placeholder + regression-guard unit test verifies the math for a representative usage tuple. |
 | **C72** | **Phase-1.5: promote `MinimaxMcpOrchestrator` test-suite-local helper to `LiteLLMAdapter` MCP-bridge (`DF-RFMCP-E2E-01`).** 2026-05-26 dogfood E2E session: shipped `tests/dogfood/rf-mcp/_minimax_orchestrator.py` as a one-off RF library that drives `minimax/MiniMax-M2.7` through an MCP server's tool surface (list tools → call_tool → loop) to produce an `AgentRunResult` consumable by the standard metrics + assertions keywords. This closes DF-4.1-S2 NARROWLY for the rf-mcp E2E dogfood smoke test (`test_metrics_e2e_smoke.robot`), but the proper home for this logic is `src/AgentEval/providers/litellm_adapter.py` (or a sibling `mcp_bridge.py`) so other adapters / tests reuse it via `Send Prompt mcp_servers=[...]`. The orchestrator deliberately bypasses the LiteLLMAdapter to ship fast; Phase-1.5 lifts the loop into the adapter, deletes the helper, and wires the smoke test through `Send Prompt`. | DF-4.1-S2 + DF-4.2-S1 (Generic + Claude Code CLI adapters raise NotImplementedError on non-empty `mcp_servers`); 2026-05-26 dogfood E2E session | correctness | M | TBD | `LiteLLMAdapter.run(prompt, mcp_servers=[handle], ...)` returns an `AgentRunResult` with full tool trajectory; rf-mcp E2E smoke test rewires through `Send Prompt` keyword; `_minimax_orchestrator.py` deleted. |
+| **C83** | **Phase-2: `Stat.Mann Whitney U` one-sided alternatives (`DF-13.1-S1`).** Story 13.1 ships two-sided Mann-Whitney U only (matches PRD FR29a verbatim signature). Phase-2: extend the keyword with an `alternative: Literal["two-sided", "greater", "less"] = "two-sided"` kwarg per `scipy.stats.mannwhitneyu` signature; update `MannWhitneyResult` docstring to clarify which tail the `p_value` corresponds to under each alternative. Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 two-sided ceiling | maintainability | S | TBD | `alternative` kwarg added + unit tests cover all 3 modes vs scipy reference + docstring tail-clarity check. |
+| **C84** | **Phase-2: Bootstrap CI BCa / BC-corrected methods (`DF-13.1-S2`).** Story 13.1 ships percentile bootstrap only (`method="percentile"`). Phase-2: implement BCa (bias-corrected & accelerated) + BC (bias-corrected) variants per `scipy.stats.bootstrap(method=)` signature; add `method: Literal["percentile", "bca", "bc"] = "percentile"` kwarg to `Stat.Bootstrap Confidence Interval`. Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 percentile ceiling | maintainability | M | TBD | `method` kwarg added + unit tests verify BCa CI tighter than percentile on skewed distributions vs scipy reference. |
+| **C85** | **Phase-2: `MannWhitneyResult.effect_size_interpretation` Cohen-band Literal field (`DF-13.1-S3`).** Story 13.1 ships raw `effect_size_r` only. Phase-2: add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` field per Cohen's conventions (`r < 0.1` negligible, `0.1 <= r < 0.3` small, `0.3 <= r < 0.5` medium, `r >= 0.5` large; mirrored for negative r by absolute value). Surfaced via Story 13.1 spec D-12 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01. | Story 13.1 D-12 decision — Phase-1 raw-r ceiling | maintainability | XS | TBD | `effect_size_interpretation` field added + `__post_init__` derives it deterministically + unit tests cover each band boundary. |
 
-**Total: 82 catalog items** (was 80 after Story 12.1 close; Story 12.2 adds C81 + C82 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 30th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 49th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 14 XS, 23 S, 28 M, 8 L, 1 XL (Story 12.2 adds 2 L entries for multi-judge ensemble + active-learning curator).
+**Total: 85 catalog items** (was 82 after Story 12.2 close; Story 13.1 adds C83 + C84 + C85 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 32nd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 51st consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 24 S, 29 M, 8 L, 1 XL (Story 13.1 adds 1 XS + 1 S + 1 M).
 
 ## Execution policy
 
diff --git a/mypy.ini b/mypy.ini
index 0412a31..79ab605 100644
--- a/mypy.ini
+++ b/mypy.ini
@@ -56,3 +56,11 @@ ignore_missing_imports = True
 # as the claude-agent-sdk allowlist above.
 [mypy-agents.*]
 ignore_missing_imports = True
+
+# Story 13.1: scipy + numpy power the Phase-2 `[agenteval-advanced]` stats
+# keywords (Mann-Whitney U, Cliff Delta, Bootstrap CI). scipy has no
+# first-party stubs in the project's Python pin range; `scipy-stubs`
+# exists but isn't worth a CI hard-dep just for stub coverage. Same
+# rationale as the other ignore-missing-imports allowlists above.
+[mypy-scipy.*]
+ignore_missing_imports = True
diff --git a/pyproject.toml b/pyproject.toml
index 80709a1..1451037 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -88,6 +88,16 @@ codex = []
 # ADR-002 + ADR-010 (Copilot CLI version-pin original precedent), this
 # is GitHub Copilot's CLI-side ≤2-adapters slot.
 copilot = []
+# Story 13.1 (Epic 13) — Advanced statistical primitives (FR29a/b/c).
+# Phase-2 keywords behind the `[agenteval-advanced]` extra:
+# `Stat.Mann Whitney U`, `Stat.Cliff Delta`,
+# `Stat.Bootstrap Confidence Interval`. scipy is the math reference
+# (math-equivalence unit tests vs `scipy.stats.mannwhitneyu` /
+# `scipy.stats.bootstrap`); numpy powers the seeded Bootstrap CI
+# resampler. Floors: scipy 1.11+ has Python 3.12 wheels + stable
+# `mannwhitneyu`/`bootstrap` APIs; numpy 2.x permitted (scipy 1.11+
+# supports). Pre-approved per epics.md L2153 verbatim.
+agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]
 
 [project.urls]
 Homepage = "https://github.com/manykarim/robotframework-agenteval"
diff --git a/src/AgentEval/stats/bootstrap.py b/src/AgentEval/stats/bootstrap.py
new file mode 100644
index 0000000..b2e939c
--- /dev/null
+++ b/src/AgentEval/stats/bootstrap.py
@@ -0,0 +1,89 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Bootstrap confidence interval primitive (PRD FR29c; Story 13.1).
+
+Phase-2 module — requires the `[agenteval-advanced]` extra (scipy + numpy).
+Computes a percentile bootstrap CI for any statistic over numeric samples.
+Reproducibility via the optional ``seed`` parameter (None → OS entropy).
+
+Math reference: ``scipy.stats.bootstrap`` (method="percentile",
+confidence_level=1-alpha). The custom resampler here is implemented directly
+for control over the random source — scipy is used for cross-validation in
+unit tests.
+
+Phase-1.5/2 carry-overs:
+- DF-13.1-S2: CI methods beyond percentile (BCa, BC-corrected). Phase-1 ships
+  percentile only.
+"""
+
+from __future__ import annotations
+
+from collections.abc import Callable
+
+import numpy as _np
+
+__all__ = ["compute_bootstrap_ci"]
+
+
+def compute_bootstrap_ci(
+    samples: list[float],
+    statistic: Callable[[list[float]], float],
+    alpha: float,
+    n_resamples: int,
+    seed: int | None,
+) -> tuple[float, float]:
+    """Compute a percentile bootstrap CI for the given statistic (FR29c).
+
+    Args:
+        samples: Non-empty list of numeric samples.
+        statistic: Callable mapping a resampled list of floats to a scalar
+            statistic (e.g., ``statistics.mean``, ``statistics.median``).
+        alpha: Significance level. CI is at ``(1 - alpha) * 100%`` confidence.
+            Must satisfy ``0.0 < alpha < 1.0``.
+        n_resamples: Number of bootstrap resamples (with replacement). Must be
+            ``>= 100`` (lower values produce unstable percentile estimates).
+        seed: Optional integer seed for the underlying ``numpy.random.Generator``.
+            ``None`` → OS-entropy seeding (non-reproducible).
+
+    Returns:
+        ``(ci_lower, ci_upper)`` tuple of floats at the ``(1-alpha) * 100%``
+        percentile level.
+
+    Raises:
+        ValueError: When ``samples`` is empty, ``alpha`` is out of range, or
+            ``n_resamples`` is too small.
+    """
+    n = len(samples)
+    if n < 1:
+        raise ValueError(f"samples must be non-empty; got n={n}")
+    if not (0.0 < alpha < 1.0):
+        raise ValueError(f"alpha must be in (0.0, 1.0); got {alpha!r}")
+    if n_resamples < 100:
+        raise ValueError(f"n_resamples must be >= 100; got {n_resamples!r}")
+
+    rng = _np.random.default_rng(seed)
+    sample_array = _np.asarray(samples, dtype=float)
+    # Draw n_resamples bootstrap samples of size n with replacement.
+    indices = rng.integers(low=0, high=n, size=(n_resamples, n))
+    resampled = sample_array[indices]
+    # Apply the statistic to each row. Use a Python loop since `statistic`
+    # is an arbitrary Callable[[list[float]], float] (not necessarily
+    # numpy-aware).
+    stats_values = _np.empty(n_resamples, dtype=float)
+    for i in range(n_resamples):
+        stats_values[i] = float(statistic(resampled[i].tolist()))
+    lo = float(_np.percentile(stats_values, 100.0 * (alpha / 2.0)))
+    hi = float(_np.percentile(stats_values, 100.0 * (1.0 - alpha / 2.0)))
+    return (lo, hi)
diff --git a/src/AgentEval/stats/cliffs_delta.py b/src/AgentEval/stats/cliffs_delta.py
new file mode 100644
index 0000000..3eb436d
--- /dev/null
+++ b/src/AgentEval/stats/cliffs_delta.py
@@ -0,0 +1,75 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Cliff's delta non-parametric effect-size primitive (PRD FR29b; Story 13.1).
+
+Phase-2 module — gated by the `[agenteval-advanced]` extra for parity with
+the other 2 Story 13.1 modules. The closed-form brute-force computation
+(Cliff 1993) is pure-Python and does NOT strictly require scipy/numpy, but
+this module imports numpy unconditionally so the keyword surface presents a
+unified ``ImportError`` story across all 3 Phase-2 keywords.
+
+Math: ``δ = (#{i,j : a_i > b_j} - #{i,j : a_i < b_j}) / (n_a * n_b)``.
+Range: ``[-1.0, 1.0]``; sign convention matches scipy's effect-size
+direction (positive = samples_a tends to be larger).
+
+Complexity: O(n_a * n_b). Fine for typical n ≤ 100 trials per group; for
+n_a + n_b > 1000 a Phase-2 algorithm-improvement carve-out applies.
+
+Phase-1.5/2 carry-overs: none specific to Cliff's delta (DF-13.1-S* covers
+the broader Phase-2 stats surface).
+"""
+
+from __future__ import annotations
+
+import numpy as _np  # noqa: F401  # Unified [agenteval-advanced] gate parity.
+
+__all__ = ["compute_cliff_delta"]
+
+
+def compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float:
+    """Compute Cliff's delta non-parametric effect size (FR29b).
+
+    Args:
+        samples_a: First-group numeric samples; must be non-empty.
+        samples_b: Second-group numeric samples; must be non-empty.
+
+    Returns:
+        ``float ∈ [-1.0, 1.0]``. Positive values indicate ``samples_a`` tends
+        to be larger; negative values indicate ``samples_b`` tends to be
+        larger. Magnitude near 0 indicates substantial overlap.
+
+    Raises:
+        ValueError: When either samples list is empty.
+
+    Notes:
+        Closed-form Cliff (1993) brute-force formula. Pure-Python loop is
+        clearest; numpy vectorization is a Phase-2 perf optimization carve-out.
+    """
+    n_a = len(samples_a)
+    n_b = len(samples_b)
+    if n_a < 1:
+        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
+    if n_b < 1:
+        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
+    greater = 0
+    less = 0
+    for a in samples_a:
+        for b in samples_b:
+            if a > b:
+                greater += 1
+            elif a < b:
+                less += 1
+            # ties (a == b) contribute 0 per Cliff 1993.
+    return (greater - less) / (n_a * n_b)
diff --git a/src/AgentEval/stats/library.py b/src/AgentEval/stats/library.py
index 6bd9954..4c740dd 100644
--- a/src/AgentEval/stats/library.py
+++ b/src/AgentEval/stats/library.py
@@ -51,13 +51,40 @@ from AgentEval._kernel.redaction import redact
 from AgentEval._kernel.tier import tier
 from AgentEval.errors import TierViolationError
 from AgentEval.stats import _internal
-from AgentEval.stats.types import KeywordRun
+from AgentEval.stats.types import KeywordRun, MannWhitneyResult
 
 __all__ = ["StatsLibrary"]
 
 # Browser-Library-style docstring migration marker (Phase 2, 2026-05-26).
 _BROWSER_STYLE_MIGRATED = True
 
+# Story 13.1 — Phase-2 `[agenteval-advanced]` extra gate. scipy + numpy power
+# the 3 advanced keyword methods (Mann-Whitney U, Cliff Delta, Bootstrap CI).
+# The `StatsLibrary` class itself MUST remain importable WITHOUT the extra so
+# Phase-1 surface keywords stay functional; only the 3 Phase-2 methods raise
+# ImportError on invocation.
+try:
+    import numpy as _numpy_advanced  # noqa: F401
+    import scipy as _scipy_advanced  # noqa: F401
+
+    _ADVANCED_AVAILABLE = True
+    _ADVANCED_IMPORT_ERROR: ImportError | None = None
+except ImportError as _advanced_err:  # pragma: no cover  -- exercised via monkeypatch
+    _ADVANCED_AVAILABLE = False
+    _ADVANCED_IMPORT_ERROR = _advanced_err
+
+
+def _raise_advanced_extra_missing(keyword_name: str) -> None:
+    """Raise the canonical `[agenteval-advanced]` extra-missing ImportError.
+
+    Per Story 13.1 D-3 + epics.md L2153: the ImportError MUST recommend
+    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
+    """
+    raise ImportError(
+        f"Stat.{keyword_name}: scipy + numpy required. "
+        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
+    ) from _ADVANCED_IMPORT_ERROR
+
 
 class StatsLibrary:
     """4 `@keyword`-decorated statistical primitives (Story 6.3 / PRD FR26-FR31a)."""
@@ -370,6 +397,195 @@ class StatsLibrary:
                 )
             )
 
+    # ----------------------------------------------------------------- #
+    # FR29a/b/c — Phase-2 advanced statistical primitives (Story 13.1)  #
+    # Behind `[agenteval-advanced]` optional extra (scipy + numpy).     #
+    # ----------------------------------------------------------------- #
+
+    @keyword(name="Stat.Mann Whitney U")
+    @tier(1)
+    def compute_mann_whitney_u(
+        self,
+        runs_a: list[KeywordRun],
+        runs_b: list[KeywordRun],
+        predicate: Callable[[KeywordRun], float] | None = None,
+    ) -> MannWhitneyResult:
+        """Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).
+
+        [Tier 1 — Deterministic] — closed-form non-parametric test for
+        whether two independent samples were drawn from the same
+        distribution. Returns ``MannWhitneyResult`` with U statistic,
+        two-sided p-value, rank-biserial effect size, and sample sizes.
+
+        Requires the ``[agenteval-advanced]`` optional extra (scipy + numpy);
+        raises ``ImportError`` when invoked without it. The ``StatsLibrary``
+        class itself remains importable without the extra; only this Phase-2
+        keyword method raises on invocation.
+
+        | =Arguments= | =Description= |
+        | ``runs_a`` | ``list[KeywordRun]`` — first sample (typically the result of `Stat.Run N Times` against flow A). |
+        | ``runs_b`` | ``list[KeywordRun]`` — second sample (typically the result of `Stat.Run N Times` against flow B). |
+        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor producing the numeric quantity to compare (e.g., ``lambda r: r.latency_seconds``). Default ``None`` raises ``ValueError`` — no sensible default numeric metric across all ``KeywordRun`` shapes. NOTE: distinct from `Stat.Get Pass At K`'s boolean predicate. |
+
+        Raises ``ImportError`` when scipy/numpy are unavailable (missing
+        ``[agenteval-advanced]`` extra). Raises ``ValueError`` when
+        ``predicate`` is ``None`` OR when either ``runs_a`` / ``runs_b`` is
+        empty.
+
+        Example:
+        | @{runs_a} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=claude_code_cli']}}
+        | @{runs_b} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=codex_cli']}}
+        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
+        | ${mwu} =    `Stat.Mann Whitney U`    ${runs_a}    ${runs_b}    predicate=${cost_pred}
+        | Should Be True    ${mwu.p_value} < 0.05                                  # Reject the null at α=0.05.
+        | Should Be True    abs(${mwu.effect_size_r}) > 0.3                        # Medium-or-larger effect.
+
+        Notes:
+        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
+        - PRD FR29a ratifies the ``MannWhitneyResult`` dataclass with ``u_statistic`` / ``p_value`` / ``effect_size_r`` + ``n_a`` / ``n_b``.
+        - Math reference: ``scipy.stats.mannwhitneyu(alternative="two-sided", use_continuity=False)``.
+        - ``u_statistic`` is the smaller of U1, U2 (canonical form across literature).
+        - Effect size: signed rank-biserial ``r = 2*U1/(n_a*n_b) - 1`` (where U1 is the M-W U for samples_a); positive r → samples_a tends to be larger; matches ``Stat.Cliff Delta`` sign convention.
+        - One-sided variants (``alternative="greater"``/``"less"``) deferred to Phase-2 (DF-13.1-S1).
+        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
+        if not _ADVANCED_AVAILABLE:
+            _raise_advanced_extra_missing("Mann Whitney U")
+        if predicate is None:
+            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
+        # Import lazily so the keyword method body owns the import attempt.
+        from AgentEval.stats import mannwhitney as _mannwhitney
+
+        samples_a = [float(predicate(r)) for r in runs_a]
+        samples_b = [float(predicate(r)) for r in runs_b]
+        return _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)
+
+    @keyword(name="Stat.Cliff Delta")
+    @tier(1)
+    def compute_cliff_delta(
+        self,
+        runs_a: list[KeywordRun],
+        runs_b: list[KeywordRun],
+        predicate: Callable[[KeywordRun], float] | None = None,
+    ) -> float:
+        """Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).
+
+        [Tier 1 — Deterministic] — closed-form Cliff (1993) brute-force
+        formula. Returns ``float ∈ [-1.0, 1.0]``. Positive values indicate
+        ``runs_a`` tends to produce larger values; negative values indicate
+        ``runs_b`` tends to produce larger values.
+
+        Requires the ``[agenteval-advanced]`` optional extra.
+
+        | =Arguments= | =Description= |
+        | ``runs_a`` | ``list[KeywordRun]`` — first sample. |
+        | ``runs_b`` | ``list[KeywordRun]`` — second sample. |
+        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor. ``None`` raises ``ValueError``. |
+
+        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
+        when ``predicate`` is ``None`` OR either sample is empty.
+
+        Example:
+        | ${latency_pred} =    Evaluate    lambda r: r.latency_seconds
+        | ${delta} =    `Stat.Cliff Delta`    ${runs_a}    ${runs_b}    predicate=${latency_pred}
+        | Should Be True    abs(${delta}) > 0.474                                  # Large effect per Romano-Coraggio-Smith conventions.
+
+        Notes:
+        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
+        - PRD FR29b ratifies the scalar ``float`` return type (NOT a dataclass) — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
+        - Math: ``δ = (#{a>b} - #{a<b}) / (n_a * n_b)``; ties contribute 0.
+        - Complexity: ``O(n_a * n_b)``. Fine for typical n ≤ 100 trials; Phase-2 perf carve-out for n_a + n_b > 1000.
+        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
+        if not _ADVANCED_AVAILABLE:
+            _raise_advanced_extra_missing("Cliff Delta")
+        if predicate is None:
+            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
+        from AgentEval.stats import cliffs_delta as _cliffs_delta
+
+        samples_a = [float(predicate(r)) for r in runs_a]
+        samples_b = [float(predicate(r)) for r in runs_b]
+        return _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
+
+    @keyword(name="Stat.Bootstrap Confidence Interval")
+    @tier(1)
+    def compute_bootstrap_ci(
+        self,
+        samples: list[KeywordRun] | list[float],
+        statistic: Callable[[list[float]], float] | None = None,
+        predicate: Callable[[KeywordRun], float] | None = None,
+        alpha: float = 0.05,
+        n_resamples: int = 10_000,
+        seed: int | None = None,
+    ) -> tuple[float, float]:
+        """Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).
+
+        [Tier 1 — Deterministic] — when ``seed`` is given, the result is
+        reproducible across calls; ``seed=None`` uses OS entropy. Returns
+        ``(ci_lower, ci_upper)`` tuple at the ``(1 - alpha) * 100%`` percentile
+        level (default 95% CI).
+
+        Requires the ``[agenteval-advanced]`` optional extra.
+
+        | =Arguments= | =Description= |
+        | ``samples`` | Either ``list[KeywordRun]`` (then ``predicate`` extracts floats) OR ``list[float]`` (predicate ignored). |
+        | ``statistic`` | ``Callable[[list[float]], float]`` whose CI is computed. Default ``None`` → ``statistics.mean``. |
+        | ``predicate`` | Optional ``Callable[[KeywordRun], float]`` value-extractor (required when ``samples`` is ``list[KeywordRun]``). |
+        | ``alpha`` | Significance level; CI is at ``(1-alpha)*100%`` confidence. Must satisfy ``0.0 < alpha < 1.0``. Default ``0.05``. |
+        | ``n_resamples`` | Number of bootstrap resamples (with replacement). Must be ``>= 100``. Default ``10_000``. |
+        | ``seed`` | Optional ``int`` seed for the numpy ``Generator``; ``None`` → OS entropy. |
+
+        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
+        when ``samples`` is empty / ``alpha`` is out of range / ``n_resamples
+        < 100`` / ``predicate`` is missing for a ``list[KeywordRun]`` input.
+
+        Example:
+        | @{runs} =    `Stat.Run N Times`    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
+        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
+        | ${ci_lo}    ${ci_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    predicate=${cost_pred}    seed=42
+        | Should Be True    ${ci_lo} <= ${ci_hi}                                    # CI bounds well-ordered.
+        | ${median_stat} =    Evaluate    statistics.median    modules=statistics
+        | ${med_lo}    ${med_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    statistic=${median_stat}    predicate=${cost_pred}    seed=42
+
+        Notes:
+        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
+        - PRD FR29c ratifies the ``(lo, hi)`` tuple return type — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
+        - Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).
+        - Math reference: ``scipy.stats.bootstrap(..., method="percentile")``. The local implementation uses ``numpy.random.Generator(seed)`` for control over the random source.
+        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
+        if not _ADVANCED_AVAILABLE:
+            _raise_advanced_extra_missing("Bootstrap Confidence Interval")
+        import statistics as _statistics
+
+        from AgentEval.stats import bootstrap as _bootstrap
+
+        if statistic is None:
+            statistic = _statistics.mean
+        # Determine if samples are KeywordRun (need predicate) or raw floats.
+        if not samples:
+            raise ValueError("samples must be non-empty")
+        first = samples[0]
+        numeric_samples: list[float]
+        if isinstance(first, KeywordRun):
+            if predicate is None:
+                raise ValueError(
+                    "predicate is required when samples is list[KeywordRun]; "
+                    "pass a Callable[[KeywordRun], float] value-extractor"
+                )
+            # samples is list[KeywordRun] in this branch (per first element);
+            # cast manually for mypy since the union type alias loses
+            # element-level homogeneity guarantees.
+            kw_samples: list[KeywordRun] = [s for s in samples if isinstance(s, KeywordRun)]
+            numeric_samples = [float(predicate(r)) for r in kw_samples]
+        else:
+            float_samples: list[float] = [s for s in samples if not isinstance(s, KeywordRun)]
+            numeric_samples = [float(s) for s in float_samples]
+        return _bootstrap.compute_bootstrap_ci(
+            numeric_samples,
+            statistic,
+            alpha,
+            n_resamples,
+            seed,
+        )
+
 
 def _byte_identical(a: Any, b: Any) -> bool:
     """Story 6.3 code-review HIGH-ο fix (Blind): NaN-aware equality.
diff --git a/src/AgentEval/stats/mannwhitney.py b/src/AgentEval/stats/mannwhitney.py
new file mode 100644
index 0000000..d6a9014
--- /dev/null
+++ b/src/AgentEval/stats/mannwhitney.py
@@ -0,0 +1,99 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Mann-Whitney U statistical primitive (PRD FR29a; Story 13.1).
+
+Phase-2 module — requires the `[agenteval-advanced]` optional extra (scipy +
+numpy). Imported lazily by `AgentEval.stats.library.StatsLibrary.mann_whitney_u`
+behind an `_ADVANCED_AVAILABLE` gate; importing this module without scipy
+installed raises `ImportError` at the `import scipy.stats` line.
+
+Math reference: ``scipy.stats.mannwhitneyu`` (alternative="two-sided",
+use_continuity=False). Effect size: rank-biserial correlation
+``r = 2 * U1 / (n_a * n_b) - 1`` (signed convention where U1 is the
+Mann-Whitney U for samples_a; positive r → samples_a tends to be larger
+than samples_b). This matches the Cliff's delta sign convention shipped
+by `Stat.Cliff Delta` (Story 13.1 FR29b).
+
+Phase-1.5/2 carry-overs:
+- DF-13.1-S1: one-sided alternatives ("greater"/"less"). Phase-1 ships
+  two-sided only.
+- DF-13.1-S3: ``MannWhitneyResult.effect_size_interpretation`` Cohen-band
+  Literal field. Phase-1 returns the raw ``effect_size_r``.
+"""
+
+from __future__ import annotations
+
+import scipy.stats as _scipy_stats
+
+from AgentEval.stats.types import MannWhitneyResult
+
+__all__ = ["compute_mann_whitney_u"]
+
+
+def compute_mann_whitney_u(
+    samples_a: list[float],
+    samples_b: list[float],
+) -> MannWhitneyResult:
+    """Compute the Mann-Whitney U statistic + p-value + effect size (FR29a).
+
+    Args:
+        samples_a: First-group numeric samples; must be non-empty.
+        samples_b: Second-group numeric samples; must be non-empty.
+
+    Returns:
+        ``MannWhitneyResult`` with ``u_statistic`` (the smaller of U1, U2 per
+        scipy default), two-sided ``p_value``, rank-biserial ``effect_size_r``,
+        and the sample sizes ``n_a`` and ``n_b``.
+
+    Raises:
+        ValueError: When either samples list is empty.
+
+    Notes:
+        - The smaller-U convention matches ``scipy.stats.mannwhitneyu(...,
+          alternative="two-sided", use_continuity=False)``: scipy reports
+          ``U1`` corresponding to the first input by default, but the
+          two-sided p-value is symmetric in U1/U2, so consumers can recover
+          U2 via ``U2 = n_a * n_b - U1``. We return the smaller of the two
+          to match the most commonly-cited form across literature.
+    """
+    n_a = len(samples_a)
+    n_b = len(samples_b)
+    if n_a < 1:
+        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
+    if n_b < 1:
+        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
+    result = _scipy_stats.mannwhitneyu(
+        samples_a,
+        samples_b,
+        alternative="two-sided",
+        use_continuity=False,
+    )
+    u1 = float(result.statistic)
+    u2 = float(n_a * n_b - u1)
+    u_smaller = min(u1, u2)
+    # Signed rank-biserial correlation r = 2 * U1 / (n_a * n_b) - 1. U1 is
+    # the count of pairs where samples_a > samples_b (with 0.5 for ties), so:
+    #   - U1 = 0 (samples_a strictly < samples_b) → r = -1.0
+    #   - U1 = n_a * n_b / 2 (no separation) → r = 0.0
+    #   - U1 = n_a * n_b (samples_a strictly > samples_b) → r = +1.0
+    # Matches Cliff's delta sign convention shipped by `Stat.Cliff Delta`.
+    effect_size_r = 2.0 * u1 / (n_a * n_b) - 1.0
+    return MannWhitneyResult(
+        u_statistic=u_smaller,
+        p_value=float(result.pvalue),
+        effect_size_r=effect_size_r,
+        n_a=n_a,
+        n_b=n_b,
+    )
diff --git a/src/AgentEval/stats/types.py b/src/AgentEval/stats/types.py
index a0beabd..a0bd8f3 100644
--- a/src/AgentEval/stats/types.py
+++ b/src/AgentEval/stats/types.py
@@ -28,6 +28,50 @@ from dataclasses import dataclass
 from typing import Any
 
 
+@dataclass(frozen=True, slots=True)
+class MannWhitneyResult:
+    """Mann-Whitney U test result (PRD FR29a; Story 13.1).
+
+    Returned by `Stat.Mann Whitney U` (Phase-2, behind the
+    `[agenteval-advanced]` extra). Reports the test statistic, two-sided
+    p-value, rank-biserial effect size, and sample sizes.
+
+    Fields:
+        u_statistic: The smaller of U1, U2 (matches
+            ``scipy.stats.mannwhitneyu`` default — "alternative='two-sided'",
+            "use_continuity=False").
+        p_value: Two-sided p-value.
+        effect_size_r: Signed rank-biserial correlation
+            ``r = 2 * U1 / (n_a * n_b) - 1`` where U1 is the Mann-Whitney
+            U for the FIRST sample. Range: ``[-1.0, 1.0]``. Sign convention:
+            positive r → samples_a tends to be larger; negative r → samples_b
+            tends to be larger; r ≈ 0 → substantial overlap. Matches Cliff's
+            delta sign convention shipped by ``Stat.Cliff Delta`` (FR29b).
+        n_a: Number of samples in the first group (after predicate extraction).
+        n_b: Number of samples in the second group (after predicate extraction).
+
+    Validation (``__post_init__``): ``n_a >= 1``, ``n_b >= 1``,
+    ``-1.0 <= effect_size_r <= 1.0``, ``0.0 <= p_value <= 1.0`` —
+    all raise ``ValueError`` on violation.
+    """
+
+    u_statistic: float
+    p_value: float
+    effect_size_r: float
+    n_a: int
+    n_b: int
+
+    def __post_init__(self) -> None:
+        if self.n_a < 1:
+            raise ValueError(f"n_a must be >= 1; got {self.n_a!r}")
+        if self.n_b < 1:
+            raise ValueError(f"n_b must be >= 1; got {self.n_b!r}")
+        if not (-1.0 <= self.effect_size_r <= 1.0):
+            raise ValueError(f"effect_size_r must be in [-1.0, 1.0]; got {self.effect_size_r!r}")
+        if not (0.0 <= self.p_value <= 1.0):
+            raise ValueError(f"p_value must be in [0.0, 1.0]; got {self.p_value!r}")
+
+
 @dataclass(frozen=True, slots=True)
 class KeywordRun:
     """Single-trial result from `Stat.Run N Times` (PRD FR26).
diff --git a/tests/integration/stats/__init__.py b/tests/integration/stats/__init__.py
new file mode 100644
index 0000000..9ae05e2
--- /dev/null
+++ b/tests/integration/stats/__init__.py
@@ -0,0 +1,7 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
diff --git a/tests/integration/stats/test_advanced_keywords.py b/tests/integration/stats/test_advanced_keywords.py
new file mode 100644
index 0000000..663faaa
--- /dev/null
+++ b/tests/integration/stats/test_advanced_keywords.py
@@ -0,0 +1,91 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Integration smoke tests for the Phase-2 `[agenteval-advanced]` stats keywords.
+
+Exercises the 3 Story 13.1 keywords through the public `StatsLibrary` surface
+that the top-level `AgentEval` library composes via `_SUB_LIBRARIES`. Verifies
+each keyword returns the documented type when called with synthetic
+`KeywordRun` inputs.
+"""
+
+from __future__ import annotations
+
+import statistics
+
+import pytest
+
+from AgentEval.stats.types import KeywordRun, MannWhitneyResult
+
+pytest.importorskip("scipy")
+pytest.importorskip("numpy")
+
+from AgentEval.stats.library import StatsLibrary  # noqa: E402
+
+
+def _make_keyword_run(value: float, *, trial_index: int = 0) -> KeywordRun:
+    """Construct a minimal `KeywordRun` carrying `value` in `latency_seconds`."""
+    return KeywordRun(
+        trial_index=trial_index,
+        test_id=f"integration::trial-{trial_index}",
+        keyword_name="synthetic",
+        result=None,
+        error=None,
+        completeness="complete",
+        latency_seconds=value,
+        seed=None,
+    )
+
+
+def test_stat_mann_whitney_u_integration_smoke() -> None:
+    """`Stat.Mann Whitney U` end-to-end returns well-typed `MannWhitneyResult`."""
+    lib = StatsLibrary()
+    runs_a = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
+    runs_b = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([6.0, 7.0, 8.0, 9.0, 10.0])]
+    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
+    assert isinstance(result, MannWhitneyResult)
+    assert result.n_a == 5
+    assert result.n_b == 5
+    assert 0.0 <= result.p_value <= 1.0
+    assert -1.0 <= result.effect_size_r <= 1.0
+
+
+def test_stat_cliff_delta_integration_smoke() -> None:
+    """`Stat.Cliff Delta` end-to-end returns a float in [-1, 1]."""
+    lib = StatsLibrary()
+    runs_a = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0]]
+    runs_b = [_make_keyword_run(v) for v in [10.0, 20.0, 30.0]]
+    delta = lib.compute_cliff_delta(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
+    assert isinstance(delta, float)
+    assert -1.0 <= delta <= 1.0
+    # Clearly separated samples_a < samples_b → δ near -1.
+    assert delta == -1.0
+
+
+def test_stat_bootstrap_ci_integration_smoke() -> None:
+    """`Stat.Bootstrap CI` end-to-end returns a well-ordered (lo, hi) tuple."""
+    lib = StatsLibrary()
+    runs = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0] * 10]
+    lo, hi = lib.compute_bootstrap_ci(
+        runs,
+        statistic=statistics.mean,
+        predicate=lambda r: r.latency_seconds,
+        n_resamples=500,
+        seed=42,
+    )
+    assert isinstance(lo, float)
+    assert isinstance(hi, float)
+    assert lo <= hi
+    # Sample mean is 3.0; CI should bracket it.
+    assert lo <= 3.0 <= hi
diff --git a/tests/unit/stats/test_advanced.py b/tests/unit/stats/test_advanced.py
new file mode 100644
index 0000000..b49c869
--- /dev/null
+++ b/tests/unit/stats/test_advanced.py
@@ -0,0 +1,375 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Unit tests for the Phase-2 `[agenteval-advanced]` stats keywords (Story 13.1).
+
+Math correctness tested against scipy reference implementations
+(``scipy.stats.mannwhitneyu`` + ``scipy.stats.bootstrap``). Cliff's delta
+has no direct scipy equivalent — verified against the closed-form
+``δ = (#a>b - #a<b) / (n_a * n_b)`` directly.
+
+ImportError gate (Phase-1 baseline compat without the extra) exercised via
+monkeypatch + module reload so the test runs in both the WITH-extras and
+WITHOUT-extras CI environments.
+"""
+
+from __future__ import annotations
+
+import statistics
+
+import pytest
+
+from AgentEval.stats.types import KeywordRun, MannWhitneyResult
+
+# Phase-2 modules require scipy + numpy. Skip the math + happy-path tests when
+# the extra is not installed (ImportError-gate tests still run via monkeypatch).
+_scipy = pytest.importorskip("scipy")
+_scipy_stats = pytest.importorskip("scipy.stats")
+_numpy = pytest.importorskip("numpy")
+
+from AgentEval.stats import bootstrap as _bootstrap  # noqa: E402
+from AgentEval.stats import cliffs_delta as _cliffs_delta  # noqa: E402
+from AgentEval.stats import mannwhitney as _mannwhitney  # noqa: E402
+from AgentEval.stats.library import StatsLibrary  # noqa: E402
+
+
+def _make_run(value: float, *, trial_index: int = 0) -> KeywordRun:
+    """Build a minimal KeywordRun whose `latency_seconds` carries the test value."""
+    return KeywordRun(
+        trial_index=trial_index,
+        test_id=f"test::trial-{trial_index}",
+        keyword_name="fake",
+        result=None,
+        error=None,
+        completeness="complete",
+        latency_seconds=value,
+        seed=None,
+    )
+
+
+# --------------------------------------------------------------------------- #
+# MannWhitneyResult dataclass validation (3 tests)                            #
+# --------------------------------------------------------------------------- #
+
+
+def test_mannwhitney_result_in_range_fields_accepted() -> None:
+    """Valid fields construct without raising."""
+    r = MannWhitneyResult(u_statistic=10.0, p_value=0.05, effect_size_r=0.3, n_a=5, n_b=5)
+    assert r.u_statistic == 10.0
+    assert r.p_value == 0.05
+    assert r.effect_size_r == 0.3
+
+
+def test_mannwhitney_result_effect_size_out_of_range_raises() -> None:
+    """effect_size_r outside [-1.0, 1.0] raises ValueError."""
+    with pytest.raises(ValueError, match="effect_size_r"):
+        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=1.5, n_a=5, n_b=5)
+    with pytest.raises(ValueError, match="effect_size_r"):
+        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=-1.5, n_a=5, n_b=5)
+
+
+def test_mannwhitney_result_p_value_out_of_range_raises() -> None:
+    """p_value outside [0.0, 1.0] raises ValueError."""
+    with pytest.raises(ValueError, match="p_value"):
+        MannWhitneyResult(u_statistic=0.0, p_value=1.1, effect_size_r=0.0, n_a=5, n_b=5)
+
+
+def test_mannwhitney_result_n_below_one_raises() -> None:
+    """n_a or n_b < 1 raises ValueError."""
+    with pytest.raises(ValueError, match="n_a"):
+        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=0, n_b=5)
+    with pytest.raises(ValueError, match="n_b"):
+        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=0)
+
+
+def test_mannwhitney_result_is_frozen() -> None:
+    """Mutation raises FrozenInstanceError (dataclass(frozen=True))."""
+    r = MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=5)
+    with pytest.raises(AttributeError):
+        r.u_statistic = 99.0  # type: ignore[misc]
+
+
+# --------------------------------------------------------------------------- #
+# Mann-Whitney U math (4 tests)                                               #
+# --------------------------------------------------------------------------- #
+
+
+def test_mannwhitney_identical_samples_p_value_near_one() -> None:
+    """Identical samples → high p-value (cannot reject null) + effect_size_r≈0."""
+    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
+    r = _mannwhitney.compute_mann_whitney_u(samples, samples)
+    assert r.p_value > 0.8
+    assert abs(r.effect_size_r) < 0.01
+    assert r.n_a == 5
+    assert r.n_b == 5
+
+
+def test_mannwhitney_clearly_separated_samples_p_value_small() -> None:
+    """Clearly disjoint samples → p < 0.05 + |effect_size_r| near 1."""
+    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
+    samples_b = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
+    r = _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)
+    assert r.p_value < 0.05
+    # samples_a < samples_b → r near -1 (positive r means a tends to be larger)
+    assert r.effect_size_r < -0.9
+
+
+def test_mannwhitney_minimal_samples_n_equals_one() -> None:
+    """n_a=1 or n_b=1 still computes (scipy permits)."""
+    r = _mannwhitney.compute_mann_whitney_u([1.0], [5.0, 6.0, 7.0])
+    assert r.n_a == 1
+    assert r.n_b == 3
+    assert 0.0 <= r.p_value <= 1.0
+
+
+def test_mannwhitney_empty_samples_raises() -> None:
+    """Empty samples list raises ValueError."""
+    with pytest.raises(ValueError, match="samples_a"):
+        _mannwhitney.compute_mann_whitney_u([], [1.0, 2.0])
+    with pytest.raises(ValueError, match="samples_b"):
+        _mannwhitney.compute_mann_whitney_u([1.0, 2.0], [])
+
+
+# --------------------------------------------------------------------------- #
+# Mann-Whitney U vs scipy reference (3 tests)                                 #
+# --------------------------------------------------------------------------- #
+
+
+@pytest.mark.parametrize("seed,n", [(42, 10), (123, 30), (7, 100)])
+def test_mannwhitney_matches_scipy_reference(seed: int, n: int) -> None:
+    """3 seeded sample pairs (n=10/30/100) match scipy.stats.mannwhitneyu within 1e-9."""
+    rng = _numpy.random.default_rng(seed)
+    a = rng.normal(loc=0.0, scale=1.0, size=n).tolist()
+    b = rng.normal(loc=0.5, scale=1.0, size=n).tolist()
+
+    ours = _mannwhitney.compute_mann_whitney_u(a, b)
+    ref = _scipy_stats.mannwhitneyu(a, b, alternative="two-sided", use_continuity=False)
+
+    u1 = float(ref.statistic)
+    u2 = float(n * n - u1)
+    expected_u_smaller = min(u1, u2)
+
+    assert abs(ours.u_statistic - expected_u_smaller) < 1e-9
+    assert abs(ours.p_value - float(ref.pvalue)) < 1e-9
+
+
+# --------------------------------------------------------------------------- #
+# Cliff Delta math (5 tests)                                                  #
+# --------------------------------------------------------------------------- #
+
+
+def test_cliff_delta_identical_samples_near_zero() -> None:
+    """Identical samples → δ ≈ 0 (all comparisons are ties or symmetric)."""
+    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
+    delta = _cliffs_delta.compute_cliff_delta(samples, samples)
+    assert abs(delta) < 0.01
+
+
+def test_cliff_delta_strict_dominance_a_over_b_equals_one() -> None:
+    """All samples_a > all samples_b → δ = 1.0."""
+    delta = _cliffs_delta.compute_cliff_delta([10.0, 20.0, 30.0], [1.0, 2.0, 3.0])
+    assert delta == 1.0
+
+
+def test_cliff_delta_reverse_dominance_equals_neg_one() -> None:
+    """All samples_a < all samples_b → δ = -1.0."""
+    delta = _cliffs_delta.compute_cliff_delta([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
+    assert delta == -1.0
+
+
+def test_cliff_delta_small_overlap_small_magnitude() -> None:
+    """Substantial overlap → |δ| < 0.5."""
+    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
+    samples_b = [2.0, 3.0, 4.0, 5.0, 6.0]
+    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
+    assert abs(delta) < 0.5
+
+
+def test_cliff_delta_large_separation_large_magnitude() -> None:
+    """Mostly-disjoint samples → |δ| > 0.7."""
+    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
+    samples_b = [6.0, 7.0, 8.0, 9.0, 10.0]
+    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
+    assert abs(delta) > 0.9
+
+
+# --------------------------------------------------------------------------- #
+# Bootstrap CI math (5 tests)                                                 #
+# --------------------------------------------------------------------------- #
+
+
+def test_bootstrap_ci_known_distribution_brackets_truth() -> None:
+    """Uniform [0,1] n=1000 mean → CI brackets 0.5."""
+    rng = _numpy.random.default_rng(42)
+    samples = rng.uniform(0.0, 1.0, size=1000).tolist()
+    lo, hi = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42)
+    assert lo <= 0.5 <= hi
+    # CI is reasonably tight for n=1000 (theoretical half-width ≈ 1.96 * 0.289/sqrt(1000) ≈ 0.018).
+    assert (hi - lo) < 0.1
+
+
+def test_bootstrap_ci_seed_reproducibility() -> None:
+    """seed=42 → identical CI across 2 invocations."""
+    samples = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
+    lo1, hi1 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
+    lo2, hi2 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
+    assert lo1 == lo2
+    assert hi1 == hi2
+
+
+def test_bootstrap_ci_alpha_0_01_wider_than_0_05() -> None:
+    """alpha=0.01 (99% CI) wider than alpha=0.05 (95% CI)."""
+    rng = _numpy.random.default_rng(42)
+    samples = rng.normal(loc=10.0, scale=2.0, size=100).tolist()
+    lo95, hi95 = _bootstrap.compute_bootstrap_ci(
+        samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42
+    )
+    lo99, hi99 = _bootstrap.compute_bootstrap_ci(
+        samples, statistic=statistics.mean, alpha=0.01, n_resamples=1000, seed=42
+    )
+    assert (hi99 - lo99) > (hi95 - lo95)
+
+
+def test_bootstrap_ci_invalid_alpha_raises() -> None:
+    """alpha outside (0,1) raises ValueError."""
+    with pytest.raises(ValueError, match="alpha"):
+        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 0.0, 1000, 42)
+    with pytest.raises(ValueError, match="alpha"):
+        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 1.5, 1000, 42)
+
+
+def test_bootstrap_ci_empty_samples_raises() -> None:
+    """Empty samples list raises ValueError."""
+    with pytest.raises(ValueError, match="samples"):
+        _bootstrap.compute_bootstrap_ci([], statistics.mean, 0.05, 1000, 42)
+
+
+def test_bootstrap_ci_too_few_resamples_raises() -> None:
+    """n_resamples < 100 raises ValueError."""
+    with pytest.raises(ValueError, match="n_resamples"):
+        _bootstrap.compute_bootstrap_ci([1.0, 2.0, 3.0], statistics.mean, 0.05, 50, 42)
+
+
+# --------------------------------------------------------------------------- #
+# Predicate value-extraction at the keyword surface (2 tests)                 #
+# --------------------------------------------------------------------------- #
+
+
+def test_mannwhitney_keyword_predicate_extracts_from_keyword_run() -> None:
+    """predicate=lambda r: r.latency_seconds extracts correctly."""
+    lib = StatsLibrary()
+    runs_a = [_make_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
+    runs_b = [_make_run(v, trial_index=i) for i, v in enumerate([10.0, 11.0, 12.0, 13.0, 14.0])]
+    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
+    assert isinstance(result, MannWhitneyResult)
+    assert result.n_a == 5
+    assert result.n_b == 5
+    assert result.p_value < 0.05  # Clearly separated.
+
+
+def test_mannwhitney_keyword_predicate_none_raises_value_error() -> None:
+    """predicate=None on Mann-Whitney U raises ValueError."""
+    lib = StatsLibrary()
+    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
+    with pytest.raises(ValueError, match="predicate is required"):
+        lib.compute_mann_whitney_u(runs, runs, predicate=None)
+
+
+def test_cliff_delta_keyword_predicate_none_raises_value_error() -> None:
+    """predicate=None on Cliff Delta raises ValueError."""
+    lib = StatsLibrary()
+    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
+    with pytest.raises(ValueError, match="predicate is required"):
+        lib.compute_cliff_delta(runs, runs, predicate=None)
+
+
+def test_bootstrap_keyword_predicate_required_for_keyword_run_input() -> None:
+    """Bootstrap CI with list[KeywordRun] input + predicate=None raises."""
+    lib = StatsLibrary()
+    runs = [_make_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0]]
+    with pytest.raises(ValueError, match="predicate is required"):
+        lib.compute_bootstrap_ci(runs, statistic=statistics.mean, n_resamples=200, seed=42)
+
+
+def test_bootstrap_keyword_raw_floats_input_works() -> None:
+    """Bootstrap CI accepts raw list[float] without a predicate."""
+    lib = StatsLibrary()
+    lo, hi = lib.compute_bootstrap_ci(
+        [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
+        statistic=statistics.mean,
+        n_resamples=500,
+        seed=42,
+    )
+    assert lo <= hi
+
+
+# --------------------------------------------------------------------------- #
+# ImportError gate WITHOUT [agenteval-advanced] extras (3 tests)              #
+# --------------------------------------------------------------------------- #
+
+
+def test_raise_advanced_extra_missing_helper_carries_canonical_message() -> None:
+    """`_raise_advanced_extra_missing` produces the spec-mandated ImportError text.
+
+    Per Story 13.1 D-3 + epics.md L2153: the message MUST include both the
+    keyword name and the verbatim install hint
+    `uv pip install robotframework-agenteval[agenteval-advanced]`.
+    """
+    from AgentEval.stats.library import _raise_advanced_extra_missing
+
+    for kw in ("Mann Whitney U", "Cliff Delta", "Bootstrap Confidence Interval"):
+        with pytest.raises(ImportError) as exc_info:
+            _raise_advanced_extra_missing(kw)
+        msg = str(exc_info.value)
+        assert f"Stat.{kw}" in msg
+        assert "agenteval-advanced" in msg
+        assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
+
+
+def test_phase2_keywords_raise_import_error_when_extra_unavailable(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """All 3 Phase-2 keywords raise ImportError when `_ADVANCED_AVAILABLE = False`.
+
+    Monkeypatches the module-level gate directly (vs reloading the module with
+    scipy stubbed out) — module reload across tests pollutes `sys.modules` and
+    leaves stats.library in a partial-import state. The gate check is the
+    load-bearing branch; this verifies it triggers correctly for each keyword.
+    """
+    from AgentEval.stats import library as lib_mod
+
+    monkeypatch.setattr(lib_mod, "_ADVANCED_AVAILABLE", False)
+    lib = lib_mod.StatsLibrary()
+
+    with pytest.raises(ImportError, match="agenteval-advanced"):
+        lib.compute_mann_whitney_u(
+            [_make_run(1.0)],
+            [_make_run(2.0)],
+            predicate=lambda r: r.latency_seconds,
+        )
+
+    with pytest.raises(ImportError, match="agenteval-advanced"):
+        lib.compute_cliff_delta(
+            [_make_run(1.0)],
+            [_make_run(2.0)],
+            predicate=lambda r: r.latency_seconds,
+        )
+
+    with pytest.raises(ImportError, match="agenteval-advanced"):
+        lib.compute_bootstrap_ci(
+            [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
+            statistic=statistics.mean,
+            n_resamples=200,
+            seed=42,
+        )
diff --git a/uv.lock b/uv.lock
index 2514dde..d4e07d1 100644
--- a/uv.lock
+++ b/uv.lock
@@ -1252,6 +1252,67 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/88/b2/d0896bdcdc8d28a7fc5717c305f1a861c26e18c05047949fb371034d98bd/nodeenv-1.10.0-py2.py3-none-any.whl", hash = "sha256:5bb13e3eed2923615535339b3c620e76779af4cb4c6a90deccc9e36b274d3827", size = 23438, upload-time = "2025-12-20T14:08:52.782Z" },
 ]
 
+[[package]]
+name = "numpy"
+version = "2.4.6"
+source = { registry = "https://pypi.org/simple" }
+sdist = { url = "https://files.pythonhosted.org/packages/d0/ad/fed0499ce6a338d2a03ebae59cd15093910c8875328855781952abf6c2fe/numpy-2.4.6.tar.gz", hash = "sha256:f3a3570c4a2a16746ac2c31a7c7c7b0c186b95ce902e33db6f28094ed7387dda", size = 20735807, upload-time = "2026-05-18T23:37:14.07Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/95/2a/3d7b5ac8aac24feaf9ad7ed58f45b0bbc06d37e4338ae84c9f2298b570f9/numpy-2.4.6-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:001fbb8e08d942dd57599e781f2472269ee7f2755fae407b4f67b2f0b17da3f1", size = 16689119, upload-time = "2026-05-18T23:33:54.065Z" },
+    { url = "https://files.pythonhosted.org/packages/ea/12/92c4c131527599e8288d6918e888d88726f84d805d784b771f32408aeaef/numpy-2.4.6-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:ebfb099f8dcf083deef3ac1ca4c1503f387cf76296fcb3816b66f5ecb5f54fdb", size = 14699246, upload-time = "2026-05-18T23:33:57.621Z" },
+    { url = "https://files.pythonhosted.org/packages/ad/fe/c0a6b7b2ca128a8fb228575147073b660656734b8ebe4d76c8fd748dcc79/numpy-2.4.6-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:3213d622a0283a39a93d188f3cf72b26862df52fbb4ca3697f51705016523d41", size = 5204410, upload-time = "2026-05-18T23:34:00.302Z" },
+    { url = "https://files.pythonhosted.org/packages/f3/d4/9770d14ba719432bb90a421bfd443872ed0f70f7264b64bec12ea363d5fd/numpy-2.4.6-cp312-cp312-macosx_14_0_x86_64.whl", hash = "sha256:357cc07a6d7b0b182ff02249616a03742827ebb1277546b5c7cd7f7620a45698", size = 6551240, upload-time = "2026-05-18T23:34:02.852Z" },
+    { url = "https://files.pythonhosted.org/packages/c9/c6/50a46a6205feba2343f1d6d17438107c5dc491ed1c736e6ea68689fd906b/numpy-2.4.6-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:5f9fb9157b4ce2971008323afe46053787b526ef624fea915b261468a8421a0f", size = 15671012, upload-time = "2026-05-18T23:34:05.485Z" },
+    { url = "https://files.pythonhosted.org/packages/99/60/14115e6364fa676c5397c2ad3004e527e9aa487abf5d0706ec81bbd08529/numpy-2.4.6-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:90f9849678c75fe7afa2d348ac842c168b0a4d3d61919687216dfc547976d853", size = 16645538, upload-time = "2026-05-18T23:34:09.265Z" },
+    { url = "https://files.pythonhosted.org/packages/ae/c5/693cbe59e57db94d2231fa519ca3978dc9e19da5a8f088588f5c6e947ff2/numpy-2.4.6-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:c1a2af6c6ef86344a6b0db6b97834208bf598db514f2b155042439b62605601a", size = 17020706, upload-time = "2026-05-18T23:34:13.053Z" },
+    { url = "https://files.pythonhosted.org/packages/ef/fc/85b7c4eff9b4966ade25c2273cf7e7012e92366c032058653934b37de044/numpy-2.4.6-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:e5805d5a22fd19c8ccff10a9561f9df94436b0545619ea579db2d3c35294bce2", size = 18368541, upload-time = "2026-05-18T23:34:17.024Z" },
+    { url = "https://files.pythonhosted.org/packages/f6/81/e1b27545deedce7f4a0b348618c6b62d74e36a4dc9ccd42f3eb2f85eee32/numpy-2.4.6-cp312-cp312-win32.whl", hash = "sha256:e3eeb0aabd6bd5ce64faae67e9935203a6991b4bc2a485a767fbafb2c5125f45", size = 5962825, upload-time = "2026-05-18T23:34:20.3Z" },
+    { url = "https://files.pythonhosted.org/packages/ab/ca/feab00bd44aa5fe1ad2c18f08b4d3bb92e26484b0b1d1443897809ed528c/numpy-2.4.6-cp312-cp312-win_amd64.whl", hash = "sha256:d8e8286dd7cea7895157318d1b91cdacac64c479f3cbc8dce548331728484751", size = 12321687, upload-time = "2026-05-18T23:34:23.095Z" },
+    { url = "https://files.pythonhosted.org/packages/63/cf/5a6d34850a39d1093558564f77ee8e8e0bee5061151b8f05a55711001ec7/numpy-2.4.6-cp312-cp312-win_arm64.whl", hash = "sha256:4081eb135ac24158bd51cdfbef16f1c64df7063b1143f24731387137c092bec8", size = 10221482, upload-time = "2026-05-18T23:34:25.876Z" },
+    { url = "https://files.pythonhosted.org/packages/fb/82/bdab26d7438c6791ca31b7c024ca37c1eab8b726ba236129005cd4a06e45/numpy-2.4.6-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:511dbaf848decaaaf4b4ca48032619fb3138710c4bf7da7617765edad1ef96b0", size = 16684648, upload-time = "2026-05-18T23:34:29.41Z" },
+    { url = "https://files.pythonhosted.org/packages/1b/30/a80189bcc7f5e4258b3fbc3968d909d1756f54d023299ecc39ad6fdb9ef8/numpy-2.4.6-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:bf162abab1c1a736333192707cef898e735a5ca00f38f27eeedf44b39d9e85eb", size = 14693902, upload-time = "2026-05-18T23:34:33.013Z" },
+    { url = "https://files.pythonhosted.org/packages/97/12/70b5d0d7c15e1ebb8a6a84a8caa1d19e181d84fb58bb6d70aca29099dec1/numpy-2.4.6-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:043191bfa8eab18c776647b62723ac9dddece59743b13f49b2016094129c2b3f", size = 5198992, upload-time = "2026-05-18T23:34:36.132Z" },
+    { url = "https://files.pythonhosted.org/packages/ba/8c/ebd2a8f8a83541f8d38cc5667e8c2b69cecfd30da6e45693e8158857d44b/numpy-2.4.6-cp313-cp313-macosx_14_0_x86_64.whl", hash = "sha256:6180d8b35af935aed8ece3a85e0a43f87393ae0ac87c8d2c8bd2c993f7270ef3", size = 6546944, upload-time = "2026-05-18T23:34:38.484Z" },
+    { url = "https://files.pythonhosted.org/packages/bb/c5/7b863a97a91671a0338f4253bd3b5a3d3852f0692dae91711c9f4a10e787/numpy-2.4.6-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:72fbe16c6fac95aedf5937fa873445cec2110be35d8a4e9433d7501fd98dae6b", size = 15669392, upload-time = "2026-05-18T23:34:41.257Z" },
+    { url = "https://files.pythonhosted.org/packages/a5/9d/3584b9984ca4c047aea75214ce1a4c4c73d849bd71b604264b7f5653f8a8/numpy-2.4.6-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:a7830bab239b79cda9c08c2da014761cafb48da6150e1da17ac06283f43b6089", size = 16633220, upload-time = "2026-05-18T23:34:45.075Z" },
+    { url = "https://files.pythonhosted.org/packages/05/ae/7c67fba23bd98caec7c99261f3a16072ade14813486b0282cb29846de832/numpy-2.4.6-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:ef4aea96ce4d3b074422cb4f2f64e216bf9e213004bb58ecfdf50ea02ea8eb9a", size = 17020800, upload-time = "2026-05-18T23:34:49.065Z" },
+    { url = "https://files.pythonhosted.org/packages/d9/5d/3b6725cb31d983c5e66916f5d36f6d7e5521129e4c4404d64f918292a5b6/numpy-2.4.6-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:dfa20cc6ca228e6b155b11da03825975ce66aea520985dbbddf0f2a5a495c605", size = 18357600, upload-time = "2026-05-18T23:34:52.709Z" },
+    { url = "https://files.pythonhosted.org/packages/f7/da/2ccc6c2fe8898dee01d90c75c5f5f914a23daf99e3e0f59516a08760c8b5/numpy-2.4.6-cp313-cp313-win32.whl", hash = "sha256:56b39e5e0622a09a25bf5baf62f4bcf0cb8a41ae6e2819cf49bbc5a74c083f91", size = 5961134, upload-time = "2026-05-18T23:34:55.618Z" },
+    { url = "https://files.pythonhosted.org/packages/b5/cd/9cc4dc876fb065d5c220aae4d5e14826b2715331bb7618ce1fb07a679d99/numpy-2.4.6-cp313-cp313-win_amd64.whl", hash = "sha256:c4fc99836233ea196540b17ab0983aff60ed07941751930f5f4d05bc3b3b7359", size = 12318598, upload-time = "2026-05-18T23:34:58.928Z" },
+    { url = "https://files.pythonhosted.org/packages/39/1e/c0bcba1f8694116485fe28fd1be698c278fcda4141c5b0e53a2aed8b12a8/numpy-2.4.6-cp313-cp313-win_arm64.whl", hash = "sha256:a7c711e21628b52034bb5ab8d1bce291f752fcc5e92accc615778acee1ff4778", size = 10222272, upload-time = "2026-05-18T23:35:02.167Z" },
+    { url = "https://files.pythonhosted.org/packages/63/6d/cc5619247c8f4204e507f5883528372e4ac4bb189e579fb859a12e480b1f/numpy-2.4.6-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:112b06a867b235ef466ed3508ddf0238050df9c727cafb5301ac385b899189a1", size = 14821197, upload-time = "2026-05-18T23:35:05.468Z" },
+    { url = "https://files.pythonhosted.org/packages/00/58/f1c39161c87d9e9bed660f1ed4bafc0e403d5ec9650b6dd77aead07d489b/numpy-2.4.6-cp313-cp313t-macosx_14_0_arm64.whl", hash = "sha256:eaf7fa2de5c0be8ae6ff8e9bea2ccd725e980541244521d8d4b5f3354a27babe", size = 5326287, upload-time = "2026-05-18T23:35:08.693Z" },
+    { url = "https://files.pythonhosted.org/packages/af/57/3917ab0fd97f271a8694513581b8a36c655f111c446852c302f04ccdb6fc/numpy-2.4.6-cp313-cp313t-macosx_14_0_x86_64.whl", hash = "sha256:7265a2f3d436e54ef9f2b52b5c937e6be778781bd97a590319d7348f1c1ca997", size = 6646763, upload-time = "2026-05-18T23:35:11.459Z" },
+    { url = "https://files.pythonhosted.org/packages/eb/0f/037e64c494b67581ae18193d770adef354c41f3f2c8ebf865602d949bf8f/numpy-2.4.6-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:f74a575920ab21fe304421a3fc28793d82e299cae9eccb37084e9fc7f3617c20", size = 15728070, upload-time = "2026-05-18T23:35:14.79Z" },
+    { url = "https://files.pythonhosted.org/packages/21/a6/5d2bae9c9542eb4df16dc9c46dc79c186e9bad53805dfa5399a6023c6db0/numpy-2.4.6-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ede83e07a75dd06bc501566c1eca2afc0d61677c1472ac9ad93fdee6e638a48d", size = 16681752, upload-time = "2026-05-18T23:35:18.836Z" },
+    { url = "https://files.pythonhosted.org/packages/92/14/23d1dfb410ae362cd59ce53e936b1513d545eb40db3949ced632e19a459e/numpy-2.4.6-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:68bb27509ac1b9a3443094260f6326150663b06abe40b73a2f81160623da5b67", size = 17086024, upload-time = "2026-05-18T23:35:22.52Z" },
+    { url = "https://files.pythonhosted.org/packages/4b/6e/23595a2c642cdf3bc567877064bdd7f91c8b0038a4453cf2daf7248eafe9/numpy-2.4.6-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:a0df0043bdb289bde1f62da130d20df23d58b45429f752bc7a8fc5325a225ecd", size = 18403398, upload-time = "2026-05-18T23:35:26.398Z" },
+    { url = "https://files.pythonhosted.org/packages/8a/90/0ac3bc947217e66dec77e7cbc6a1979d1af70b6461b82f620d3bccd5e4c8/numpy-2.4.6-cp313-cp313t-win32.whl", hash = "sha256:29a287e0cf63ff528da061de6b9f64a4618da591ca1046aafc54062e40ca7eab", size = 6084971, upload-time = "2026-05-18T23:35:29.387Z" },
+    { url = "https://files.pythonhosted.org/packages/77/71/5673e351671a1d2bd6063b91b44f70c0affea7d1516fa7a6572941ba4aa1/numpy-2.4.6-cp313-cp313t-win_amd64.whl", hash = "sha256:25c692919ac5a01f170a3bfcd62d745b24fd095c353d50812637d6fcab442e75", size = 12458532, upload-time = "2026-05-18T23:35:32.175Z" },
+    { url = "https://files.pythonhosted.org/packages/3f/88/19d3503c5046e688f049274b27a3ef3d771152fa80d3ba3d01a3dff61abe/numpy-2.4.6-cp313-cp313t-win_arm64.whl", hash = "sha256:1e978ec1e8bd0e0e4de6bb75de9d30cbb74db6b6a2bb727618613703ca0167dd", size = 10291881, upload-time = "2026-05-18T23:35:35.465Z" },
+    { url = "https://files.pythonhosted.org/packages/f8/91/3ab2044d05fd16d343c5ac2e69b127f1b2854040dd20b193257c78028bd3/numpy-2.4.6-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:06ca2f61ec4385a07a6977c55ba998a4466c123642b4a32694d3128fce18c079", size = 16683458, upload-time = "2026-05-18T23:35:38.353Z" },
+    { url = "https://files.pythonhosted.org/packages/8e/62/764ce66fa4147ae6d73071a3abf804ffe606f174618697c571acdf26a7c9/numpy-2.4.6-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:38efbc8de75c7a0fc1ac190162d892787f3f47b57cc291231aafee36b80982b7", size = 14704559, upload-time = "2026-05-18T23:35:42.14Z" },
+    { url = "https://files.pythonhosted.org/packages/60/61/23f27c172f022e04025b7dc2367f4d63c1a398120607ec896228649a6f48/numpy-2.4.6-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:d581b735e177fdcdce6fed8e7e8880a3fb6ee4e3653a3ac6af01c6f4c03effc5", size = 5209716, upload-time = "2026-05-18T23:35:45.377Z" },
+    { url = "https://files.pythonhosted.org/packages/03/71/21cf70dc6ea3e3acb95fc53a265b2fc248b981f0194ceb5b475271b8809d/numpy-2.4.6-cp314-cp314-macosx_14_0_x86_64.whl", hash = "sha256:0a041d3d761dc3c35cc56ce0351506a02bcbc25f7b169f652435141a17db9096", size = 6543947, upload-time = "2026-05-18T23:35:47.926Z" },
+    { url = "https://files.pythonhosted.org/packages/d5/91/64288395ee1799bd2e0b04a305dce9666da90c961e1f3fe982a05ee1c036/numpy-2.4.6-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:40fdc1ae7125e518ea98e53e69a4ebc27e1fd50510c47b7ea130cf21e5e1d42b", size = 15685197, upload-time = "2026-05-18T23:35:50.863Z" },
+    { url = "https://files.pythonhosted.org/packages/f3/eb/ebffaa97dc55502df69584a8f0dcf07f69a3e0b3e2323670a2722db9aa39/numpy-2.4.6-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:a2c306dea656c12c68f51f4cea133cbe78ca7435eb28c735eac1d3ebe73be6e8", size = 16638245, upload-time = "2026-05-18T23:35:54.752Z" },
+    { url = "https://files.pythonhosted.org/packages/b8/0b/54f9da33128d7e350fab89c7455902eeae70349ee52bddb448dc4a576f45/numpy-2.4.6-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:33111801a01c12a8a1e3721f0a9232f8cfc8ae2c6b7098167e6f623c6073f402", size = 17036587, upload-time = "2026-05-18T23:35:58.355Z" },
+    { url = "https://files.pythonhosted.org/packages/b6/f0/fdebc1052db1cc37c64beb22072d67cd6d1c71adca1299f53dec2b5e20d3/numpy-2.4.6-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:ae506e6902902557576a26ff33eda8695e7ecb3cb36c3b573a0765dee114ebdb", size = 18363226, upload-time = "2026-05-18T23:36:02.845Z" },
+    { url = "https://files.pythonhosted.org/packages/aa/b4/298628d98c72b57e57f7165ae6a481a1deaf6f3c28262a6e4c739c275930/numpy-2.4.6-cp314-cp314-win32.whl", hash = "sha256:aaf159caa35993cb1f56fb9b8e4610d35758e7ca005412eb1daa856a78c9c4b1", size = 6010196, upload-time = "2026-05-18T23:36:05.92Z" },
+    { url = "https://files.pythonhosted.org/packages/df/ac/46de6dda46478f7942f839e094970be2d4a861e005c4b3bf07c92e291a09/numpy-2.4.6-cp314-cp314-win_amd64.whl", hash = "sha256:b507f5c4c1d508876d1819b6bf9a49d365b96320b5d4993426b33a23ca4b8261", size = 12450334, upload-time = "2026-05-18T23:36:09.107Z" },
+    { url = "https://files.pythonhosted.org/packages/78/92/b8b798ac784102c0da830d2257d59358e3d3d90d1e2b3f2575dad976c5cf/numpy-2.4.6-cp314-cp314-win_arm64.whl", hash = "sha256:6f41ae150c4e32db4f3310cdaf64b1593a03dbabe29eec77fc9b50fe64061df6", size = 10495678, upload-time = "2026-05-18T23:36:12.766Z" },
+    { url = "https://files.pythonhosted.org/packages/30/34/ec28d1aa8115971537c01469ab2011ee96827930f0a124de1000cc2a7ed7/numpy-2.4.6-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:ece3d2cfe132e7d51f44a832b303895e6f2d499c5e74dfbdb06ee246147a304a", size = 14823672, upload-time = "2026-05-18T23:36:16.473Z" },
+    { url = "https://files.pythonhosted.org/packages/16/bd/f6d1fede4e54e8042a7ff97bb495510f3c220f94bcd9e8b228e87c92cc0d/numpy-2.4.6-cp314-cp314t-macosx_14_0_arm64.whl", hash = "sha256:e3e5193ef5a3dc73bceee50f7fdc2c90dbb76c42df8d8fae3d1067a583df579e", size = 5328731, upload-time = "2026-05-18T23:36:19.767Z" },
+    { url = "https://files.pythonhosted.org/packages/f4/f0/e105b9e2fd728a9910103884decd6951d9dd73896b914a98d9a231de02ee/numpy-2.4.6-cp314-cp314t-macosx_14_0_x86_64.whl", hash = "sha256:17f9ade344e7d9b464a084d69bcf18fc691cb1db67c62ed80820bf4926d78f0e", size = 6649805, upload-time = "2026-05-18T23:36:22.266Z" },
+    { url = "https://files.pythonhosted.org/packages/82/dd/1206a7ca6ab15e3f02069707ca96222e202af681bb73756da7527f3cb837/numpy-2.4.6-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:9cd5ffd25db4e7ba6a375693b3fc0fc1791ec636c17db3720da19bde7180ec43", size = 15730496, upload-time = "2026-05-18T23:36:25.713Z" },
+    { url = "https://files.pythonhosted.org/packages/51/e7/38d3ea825dcab85a591734decb2f6c67caa7c8367d374df1a1c3842f9b07/numpy-2.4.6-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7d92c3819208a60205a12a245c91ad70cb0a85336659b19b834205573ac8456e", size = 16679616, upload-time = "2026-05-18T23:36:29.652Z" },
+    { url = "https://files.pythonhosted.org/packages/93/b7/caabfdf53edf663e0b4eb74d7d405d83baef09eb5e83bcd32d601d72b93e/numpy-2.4.6-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:e85b752a1e912b70eaad4fafbd4d1238007ab221de2009b9a2f5ae7461239895", size = 17085145, upload-time = "2026-05-18T23:36:33.449Z" },
+    { url = "https://files.pythonhosted.org/packages/f9/45/68d7c33a6bcf3e5aa3bdbd57a367e6f615286dfd6482f97e8ffeb734306e/numpy-2.4.6-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:29cb7f67d10b479ff07c17d33e39f78c07f71c40ef30d63c153d340e96cd3fb4", size = 18403813, upload-time = "2026-05-18T23:36:37.369Z" },
+    { url = "https://files.pythonhosted.org/packages/9c/50/0753655aa844c99cd9e018aacf76f130f1bd81d881bb74bc0aef5d73a8ba/numpy-2.4.6-cp314-cp314t-win32.whl", hash = "sha256:260a5d70215b61ab4fadf5c7baacd64821842975eea312125ed3c39a6391b063", size = 6156982, upload-time = "2026-05-18T23:36:40.817Z" },
+    { url = "https://files.pythonhosted.org/packages/b2/d4/7c67becf668f973cb490cec3e98dfd799d866f9c989a54d355672cfa0db6/numpy-2.4.6-cp314-cp314t-win_amd64.whl", hash = "sha256:81a1cca95ed5bb92aa8b10dd2cdc9a0d3853a50fad926c28b5d7e8ea54389627", size = 12638908, upload-time = "2026-05-18T23:36:43.996Z" },
+    { url = "https://files.pythonhosted.org/packages/43/bb/e1c71a4295b1b1d1393d50dbb4f2a36283c6859d9d3892e84f00ec5a91d5/numpy-2.4.6-cp314-cp314t-win_arm64.whl", hash = "sha256:0c9136e14ed34a9e343a31c533d78a9813a69a3148332bce5e9821cb2f996e66", size = 10565867, upload-time = "2026-05-18T23:36:47.114Z" },
+]
+
 [[package]]
 name = "openai"
 version = "2.37.0"
@@ -1892,6 +1953,10 @@ dependencies = [
 ]
 
 [package.optional-dependencies]
+agenteval-advanced = [
+    { name = "numpy" },
+    { name = "scipy" },
+]
 claude-sdk = [
     { name = "claude-agent-sdk" },
 ]
@@ -1915,6 +1980,7 @@ requires-dist = [
     { name = "litellm", specifier = ">=1.50,<2.0" },
     { name = "mcp", specifier = "==1.27.1" },
     { name = "mypy", marker = "extra == 'dev'", specifier = ">=1.10,<2.0" },
+    { name = "numpy", marker = "extra == 'agenteval-advanced'", specifier = ">=1.26,<3.0" },
     { name = "openai-agents", marker = "extra == 'openai-agents'", specifier = ">=0.1.0,<1.0" },
     { name = "opentelemetry-api", specifier = ">=1.27,<2.0" },
     { name = "opentelemetry-sdk", specifier = ">=1.27,<2.0" },
@@ -1927,8 +1993,9 @@ requires-dist = [
     { name = "robotframework-pabot", marker = "extra == 'dev'", specifier = "==5.2.2" },
     { name = "robotframework-pythonlibcore", specifier = ">=4.5" },
     { name = "ruff", marker = "extra == 'dev'", specifier = ">=0.6,<1.0" },
+    { name = "scipy", marker = "extra == 'agenteval-advanced'", specifier = ">=1.11,<2.0" },
 ]
-provides-extras = ["dev", "claude-code", "claude-sdk", "openai-agents", "codex", "copilot"]
+provides-extras = ["dev", "claude-code", "claude-sdk", "openai-agents", "codex", "copilot", "agenteval-advanced"]
 
 [[package]]
 name = "robotframework-assertion-engine"
@@ -2070,6 +2137,67 @@ wheels = [
     { url = "https://files.pythonhosted.org/packages/9b/36/9c015cd052fca743dae8cb2aeb16b551444787467db42ceab0fc968865af/ruff-0.15.13-py3-none-win_arm64.whl", hash = "sha256:2471da9bd1068c8c064b5fd9c0c4b6dddffd6369cb1cd68b29993b1709ff1b21", size = 11179336, upload-time = "2026-05-14T13:44:33.026Z" },
 ]
 
+[[package]]
+name = "scipy"
+version = "1.17.1"
+source = { registry = "https://pypi.org/simple" }
+dependencies = [
+    { name = "numpy" },
+]
+sdist = { url = "https://files.pythonhosted.org/packages/7a/97/5a3609c4f8d58b039179648e62dd220f89864f56f7357f5d4f45c29eb2cc/scipy-1.17.1.tar.gz", hash = "sha256:95d8e012d8cb8816c226aef832200b1d45109ed4464303e997c5b13122b297c0", size = 30573822, upload-time = "2026-02-23T00:26:24.851Z" }
+wheels = [
+    { url = "https://files.pythonhosted.org/packages/35/48/b992b488d6f299dbe3f11a20b24d3dda3d46f1a635ede1c46b5b17a7b163/scipy-1.17.1-cp312-cp312-macosx_10_14_x86_64.whl", hash = "sha256:35c3a56d2ef83efc372eaec584314bd0ef2e2f0d2adb21c55e6ad5b344c0dcb8", size = 31610954, upload-time = "2026-02-23T00:17:49.855Z" },
+    { url = "https://files.pythonhosted.org/packages/b2/02/cf107b01494c19dc100f1d0b7ac3cc08666e96ba2d64db7626066cee895e/scipy-1.17.1-cp312-cp312-macosx_12_0_arm64.whl", hash = "sha256:fcb310ddb270a06114bb64bbe53c94926b943f5b7f0842194d585c65eb4edd76", size = 28172662, upload-time = "2026-02-23T00:18:01.64Z" },
+    { url = "https://files.pythonhosted.org/packages/cf/a9/599c28631bad314d219cf9ffd40e985b24d603fc8a2f4ccc5ae8419a535b/scipy-1.17.1-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:cc90d2e9c7e5c7f1a482c9875007c095c3194b1cfedca3c2f3291cdc2bc7c086", size = 20344366, upload-time = "2026-02-23T00:18:12.015Z" },
+    { url = "https://files.pythonhosted.org/packages/35/f5/906eda513271c8deb5af284e5ef0206d17a96239af79f9fa0aebfe0e36b4/scipy-1.17.1-cp312-cp312-macosx_14_0_x86_64.whl", hash = "sha256:c80be5ede8f3f8eded4eff73cc99a25c388ce98e555b17d31da05287015ffa5b", size = 22704017, upload-time = "2026-02-23T00:18:21.502Z" },
+    { url = "https://files.pythonhosted.org/packages/da/34/16f10e3042d2f1d6b66e0428308ab52224b6a23049cb2f5c1756f713815f/scipy-1.17.1-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:e19ebea31758fac5893a2ac360fedd00116cbb7628e650842a6691ba7ca28a21", size = 32927842, upload-time = "2026-02-23T00:18:35.367Z" },
+    { url = "https://files.pythonhosted.org/packages/01/8e/1e35281b8ab6d5d72ebe9911edcdffa3f36b04ed9d51dec6dd140396e220/scipy-1.17.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:02ae3b274fde71c5e92ac4d54bc06c42d80e399fec704383dcd99b301df37458", size = 35235890, upload-time = "2026-02-23T00:18:49.188Z" },
+    { url = "https://files.pythonhosted.org/packages/c5/5c/9d7f4c88bea6e0d5a4f1bc0506a53a00e9fcb198de372bfe4d3652cef482/scipy-1.17.1-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:8a604bae87c6195d8b1045eddece0514d041604b14f2727bbc2b3020172045eb", size = 35003557, upload-time = "2026-02-23T00:18:54.74Z" },
+    { url = "https://files.pythonhosted.org/packages/65/94/7698add8f276dbab7a9de9fb6b0e02fc13ee61d51c7c3f85ac28b65e1239/scipy-1.17.1-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:f590cd684941912d10becc07325a3eeb77886fe981415660d9265c4c418d0bea", size = 37625856, upload-time = "2026-02-23T00:19:00.307Z" },
+    { url = "https://files.pythonhosted.org/packages/a2/84/dc08d77fbf3d87d3ee27f6a0c6dcce1de5829a64f2eae85a0ecc1f0daa73/scipy-1.17.1-cp312-cp312-win_amd64.whl", hash = "sha256:41b71f4a3a4cab9d366cd9065b288efc4d4f3c0b37a91a8e0947fb5bd7f31d87", size = 36549682, upload-time = "2026-02-23T00:19:07.67Z" },
+    { url = "https://files.pythonhosted.org/packages/bc/98/fe9ae9ffb3b54b62559f52dedaebe204b408db8109a8c66fdd04869e6424/scipy-1.17.1-cp312-cp312-win_arm64.whl", hash = "sha256:f4115102802df98b2b0db3cce5cb9b92572633a1197c77b7553e5203f284a5b3", size = 24547340, upload-time = "2026-02-23T00:19:12.024Z" },
+    { url = "https://files.pythonhosted.org/packages/76/27/07ee1b57b65e92645f219b37148a7e7928b82e2b5dbeccecb4dff7c64f0b/scipy-1.17.1-cp313-cp313-macosx_10_14_x86_64.whl", hash = "sha256:5e3c5c011904115f88a39308379c17f91546f77c1667cea98739fe0fccea804c", size = 31590199, upload-time = "2026-02-23T00:19:17.192Z" },
+    { url = "https://files.pythonhosted.org/packages/ec/ae/db19f8ab842e9b724bf5dbb7db29302a91f1e55bc4d04b1025d6d605a2c5/scipy-1.17.1-cp313-cp313-macosx_12_0_arm64.whl", hash = "sha256:6fac755ca3d2c3edcb22f479fceaa241704111414831ddd3bc6056e18516892f", size = 28154001, upload-time = "2026-02-23T00:19:22.241Z" },
+    { url = "https://files.pythonhosted.org/packages/5b/58/3ce96251560107b381cbd6e8413c483bbb1228a6b919fa8652b0d4090e7f/scipy-1.17.1-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:7ff200bf9d24f2e4d5dc6ee8c3ac64d739d3a89e2326ba68aaf6c4a2b838fd7d", size = 20325719, upload-time = "2026-02-23T00:19:26.329Z" },
+    { url = "https://files.pythonhosted.org/packages/b2/83/15087d945e0e4d48ce2377498abf5ad171ae013232ae31d06f336e64c999/scipy-1.17.1-cp313-cp313-macosx_14_0_x86_64.whl", hash = "sha256:4b400bdc6f79fa02a4d86640310dde87a21fba0c979efff5248908c6f15fad1b", size = 22683595, upload-time = "2026-02-23T00:19:30.304Z" },
+    { url = "https://files.pythonhosted.org/packages/b4/e0/e58fbde4a1a594c8be8114eb4aac1a55bcd6587047efc18a61eb1f5c0d30/scipy-1.17.1-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:2b64ca7d4aee0102a97f3ba22124052b4bd2152522355073580bf4845e2550b6", size = 32896429, upload-time = "2026-02-23T00:19:35.536Z" },
+    { url = "https://files.pythonhosted.org/packages/f5/5f/f17563f28ff03c7b6799c50d01d5d856a1d55f2676f537ca8d28c7f627cd/scipy-1.17.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:581b2264fc0aa555f3f435a5944da7504ea3a065d7029ad60e7c3d1ae09c5464", size = 35203952, upload-time = "2026-02-23T00:19:42.259Z" },
+    { url = "https://files.pythonhosted.org/packages/8d/a5/9afd17de24f657fdfe4df9a3f1ea049b39aef7c06000c13db1530d81ccca/scipy-1.17.1-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:beeda3d4ae615106d7094f7e7cef6218392e4465cc95d25f900bebabfded0950", size = 34979063, upload-time = "2026-02-23T00:19:47.547Z" },
+    { url = "https://files.pythonhosted.org/packages/8b/13/88b1d2384b424bf7c924f2038c1c409f8d88bb2a8d49d097861dd64a57b2/scipy-1.17.1-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:6609bc224e9568f65064cfa72edc0f24ee6655b47575954ec6339534b2798369", size = 37598449, upload-time = "2026-02-23T00:19:53.238Z" },
+    { url = "https://files.pythonhosted.org/packages/35/e5/d6d0e51fc888f692a35134336866341c08655d92614f492c6860dc45bb2c/scipy-1.17.1-cp313-cp313-win_amd64.whl", hash = "sha256:37425bc9175607b0268f493d79a292c39f9d001a357bebb6b88fdfaff13f6448", size = 36510943, upload-time = "2026-02-23T00:20:50.89Z" },
+    { url = "https://files.pythonhosted.org/packages/2a/fd/3be73c564e2a01e690e19cc618811540ba5354c67c8680dce3281123fb79/scipy-1.17.1-cp313-cp313-win_arm64.whl", hash = "sha256:5cf36e801231b6a2059bf354720274b7558746f3b1a4efb43fcf557ccd484a87", size = 24545621, upload-time = "2026-02-23T00:20:55.871Z" },
+    { url = "https://files.pythonhosted.org/packages/6f/6b/17787db8b8114933a66f9dcc479a8272e4b4da75fe03b0c282f7b0ade8cd/scipy-1.17.1-cp313-cp313t-macosx_10_14_x86_64.whl", hash = "sha256:d59c30000a16d8edc7e64152e30220bfbd724c9bbb08368c054e24c651314f0a", size = 31936708, upload-time = "2026-02-23T00:19:58.694Z" },
+    { url = "https://files.pythonhosted.org/packages/38/2e/524405c2b6392765ab1e2b722a41d5da33dc5c7b7278184a8ad29b6cb206/scipy-1.17.1-cp313-cp313t-macosx_12_0_arm64.whl", hash = "sha256:010f4333c96c9bb1a4516269e33cb5917b08ef2166d5556ca2fd9f082a9e6ea0", size = 28570135, upload-time = "2026-02-23T00:20:03.934Z" },
+    { url = "https://files.pythonhosted.org/packages/fd/c3/5bd7199f4ea8556c0c8e39f04ccb014ac37d1468e6cfa6a95c6b3562b76e/scipy-1.17.1-cp313-cp313t-macosx_14_0_arm64.whl", hash = "sha256:2ceb2d3e01c5f1d83c4189737a42d9cb2fc38a6eeed225e7515eef71ad301dce", size = 20741977, upload-time = "2026-02-23T00:20:07.935Z" },
+    { url = "https://files.pythonhosted.org/packages/d9/b8/8ccd9b766ad14c78386599708eb745f6b44f08400a5fd0ade7cf89b6fc93/scipy-1.17.1-cp313-cp313t-macosx_14_0_x86_64.whl", hash = "sha256:844e165636711ef41f80b4103ed234181646b98a53c8f05da12ca5ca289134f6", size = 23029601, upload-time = "2026-02-23T00:20:12.161Z" },
+    { url = "https://files.pythonhosted.org/packages/6d/a0/3cb6f4d2fb3e17428ad2880333cac878909ad1a89f678527b5328b93c1d4/scipy-1.17.1-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:158dd96d2207e21c966063e1635b1063cd7787b627b6f07305315dd73d9c679e", size = 33019667, upload-time = "2026-02-23T00:20:17.208Z" },
+    { url = "https://files.pythonhosted.org/packages/f3/c3/2d834a5ac7bf3a0c806ad1508efc02dda3c8c61472a56132d7894c312dea/scipy-1.17.1-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:74cbb80d93260fe2ffa334efa24cb8f2f0f622a9b9febf8b483c0b865bfb3475", size = 35264159, upload-time = "2026-02-23T00:20:23.087Z" },
+    { url = "https://files.pythonhosted.org/packages/4d/77/d3ed4becfdbd217c52062fafe35a72388d1bd82c2d0ba5ca19d6fcc93e11/scipy-1.17.1-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:dbc12c9f3d185f5c737d801da555fb74b3dcfa1a50b66a1a93e09190f41fab50", size = 35102771, upload-time = "2026-02-23T00:20:28.636Z" },
+    { url = "https://files.pythonhosted.org/packages/bd/12/d19da97efde68ca1ee5538bb261d5d2c062f0c055575128f11a2730e3ac1/scipy-1.17.1-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:94055a11dfebe37c656e70317e1996dc197e1a15bbcc351bcdd4610e128fe1ca", size = 37665910, upload-time = "2026-02-23T00:20:34.743Z" },
+    { url = "https://files.pythonhosted.org/packages/06/1c/1172a88d507a4baaf72c5a09bb6c018fe2ae0ab622e5830b703a46cc9e44/scipy-1.17.1-cp313-cp313t-win_amd64.whl", hash = "sha256:e30bdeaa5deed6bc27b4cc490823cd0347d7dae09119b8803ae576ea0ce52e4c", size = 36562980, upload-time = "2026-02-23T00:20:40.575Z" },
+    { url = "https://files.pythonhosted.org/packages/70/b0/eb757336e5a76dfa7911f63252e3b7d1de00935d7705cf772db5b45ec238/scipy-1.17.1-cp313-cp313t-win_arm64.whl", hash = "sha256:a720477885a9d2411f94a93d16f9d89bad0f28ca23c3f8daa521e2dcc3f44d49", size = 24856543, upload-time = "2026-02-23T00:20:45.313Z" },
+    { url = "https://files.pythonhosted.org/packages/cf/83/333afb452af6f0fd70414dc04f898647ee1423979ce02efa75c3b0f2c28e/scipy-1.17.1-cp314-cp314-macosx_10_14_x86_64.whl", hash = "sha256:a48a72c77a310327f6a3a920092fa2b8fd03d7deaa60f093038f22d98e096717", size = 31584510, upload-time = "2026-02-23T00:21:01.015Z" },
+    { url = "https://files.pythonhosted.org/packages/ed/a6/d05a85fd51daeb2e4ea71d102f15b34fedca8e931af02594193ae4fd25f7/scipy-1.17.1-cp314-cp314-macosx_12_0_arm64.whl", hash = "sha256:45abad819184f07240d8a696117a7aacd39787af9e0b719d00285549ed19a1e9", size = 28170131, upload-time = "2026-02-23T00:21:05.888Z" },
+    { url = "https://files.pythonhosted.org/packages/db/7b/8624a203326675d7746a254083a187398090a179335b2e4a20e2ddc46e83/scipy-1.17.1-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:3fd1fcdab3ea951b610dc4cef356d416d5802991e7e32b5254828d342f7b7e0b", size = 20342032, upload-time = "2026-02-23T00:21:09.904Z" },
+    { url = "https://files.pythonhosted.org/packages/c9/35/2c342897c00775d688d8ff3987aced3426858fd89d5a0e26e020b660b301/scipy-1.17.1-cp314-cp314-macosx_14_0_x86_64.whl", hash = "sha256:7bdf2da170b67fdf10bca777614b1c7d96ae3ca5794fd9587dce41eb2966e866", size = 22678766, upload-time = "2026-02-23T00:21:14.313Z" },
+    { url = "https://files.pythonhosted.org/packages/ef/f2/7cdb8eb308a1a6ae1e19f945913c82c23c0c442a462a46480ce487fdc0ac/scipy-1.17.1-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:adb2642e060a6549c343603a3851ba76ef0b74cc8c079a9a58121c7ec9fe2350", size = 32957007, upload-time = "2026-02-23T00:21:19.663Z" },
+    { url = "https://files.pythonhosted.org/packages/0b/2e/7eea398450457ecb54e18e9d10110993fa65561c4f3add5e8eccd2b9cd41/scipy-1.17.1-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:eee2cfda04c00a857206a4330f0c5e3e56535494e30ca445eb19ec624ae75118", size = 35221333, upload-time = "2026-02-23T00:21:25.278Z" },
+    { url = "https://files.pythonhosted.org/packages/d9/77/5b8509d03b77f093a0d52e606d3c4f79e8b06d1d38c441dacb1e26cacf46/scipy-1.17.1-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:d2650c1fb97e184d12d8ba010493ee7b322864f7d3d00d3f9bb97d9c21de4068", size = 35042066, upload-time = "2026-02-23T00:21:31.358Z" },
+    { url = "https://files.pythonhosted.org/packages/f9/df/18f80fb99df40b4070328d5ae5c596f2f00fffb50167e31439e932f29e7d/scipy-1.17.1-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:08b900519463543aa604a06bec02461558a6e1cef8fdbb8098f77a48a83c8118", size = 37612763, upload-time = "2026-02-23T00:21:37.247Z" },
+    { url = "https://files.pythonhosted.org/packages/4b/39/f0e8ea762a764a9dc52aa7dabcfad51a354819de1f0d4652b6a1122424d6/scipy-1.17.1-cp314-cp314-win_amd64.whl", hash = "sha256:3877ac408e14da24a6196de0ddcace62092bfc12a83823e92e49e40747e52c19", size = 37290984, upload-time = "2026-02-23T00:22:35.023Z" },
+    { url = "https://files.pythonhosted.org/packages/7c/56/fe201e3b0f93d1a8bcf75d3379affd228a63d7e2d80ab45467a74b494947/scipy-1.17.1-cp314-cp314-win_arm64.whl", hash = "sha256:f8885db0bc2bffa59d5c1b72fad7a6a92d3e80e7257f967dd81abb553a90d293", size = 25192877, upload-time = "2026-02-23T00:22:39.798Z" },
+    { url = "https://files.pythonhosted.org/packages/96/ad/f8c414e121f82e02d76f310f16db9899c4fcde36710329502a6b2a3c0392/scipy-1.17.1-cp314-cp314t-macosx_10_14_x86_64.whl", hash = "sha256:1cc682cea2ae55524432f3cdff9e9a3be743d52a7443d0cba9017c23c87ae2f6", size = 31949750, upload-time = "2026-02-23T00:21:42.289Z" },
+    { url = "https://files.pythonhosted.org/packages/7c/b0/c741e8865d61b67c81e255f4f0a832846c064e426636cd7de84e74d209be/scipy-1.17.1-cp314-cp314t-macosx_12_0_arm64.whl", hash = "sha256:2040ad4d1795a0ae89bfc7e8429677f365d45aa9fd5e4587cf1ea737f927b4a1", size = 28585858, upload-time = "2026-02-23T00:21:47.706Z" },
+    { url = "https://files.pythonhosted.org/packages/ed/1b/3985219c6177866628fa7c2595bfd23f193ceebbe472c98a08824b9466ff/scipy-1.17.1-cp314-cp314t-macosx_14_0_arm64.whl", hash = "sha256:131f5aaea57602008f9822e2115029b55d4b5f7c070287699fe45c661d051e39", size = 20757723, upload-time = "2026-02-23T00:21:52.039Z" },
+    { url = "https://files.pythonhosted.org/packages/c0/19/2a04aa25050d656d6f7b9e7b685cc83d6957fb101665bfd9369ca6534563/scipy-1.17.1-cp314-cp314t-macosx_14_0_x86_64.whl", hash = "sha256:9cdc1a2fcfd5c52cfb3045feb399f7b3ce822abdde3a193a6b9a60b3cb5854ca", size = 23043098, upload-time = "2026-02-23T00:21:56.185Z" },
+    { url = "https://files.pythonhosted.org/packages/86/f1/3383beb9b5d0dbddd030335bf8a8b32d4317185efe495374f134d8be6cce/scipy-1.17.1-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:6e3dcd57ab780c741fde8dc68619de988b966db759a3c3152e8e9142c26295ad", size = 33030397, upload-time = "2026-02-23T00:22:01.404Z" },
+    { url = "https://files.pythonhosted.org/packages/41/68/8f21e8a65a5a03f25a79165ec9d2b28c00e66dc80546cf5eb803aeeff35b/scipy-1.17.1-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:a9956e4d4f4a301ebf6cde39850333a6b6110799d470dbbb1e25326ac447f52a", size = 35281163, upload-time = "2026-02-23T00:22:07.024Z" },
+    { url = "https://files.pythonhosted.org/packages/84/8d/c8a5e19479554007a5632ed7529e665c315ae7492b4f946b0deb39870e39/scipy-1.17.1-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:a4328d245944d09fd639771de275701ccadf5f781ba0ff092ad141e017eccda4", size = 35116291, upload-time = "2026-02-23T00:22:12.585Z" },
+    { url = "https://files.pythonhosted.org/packages/52/52/e57eceff0e342a1f50e274264ed47497b59e6a4e3118808ee58ddda7b74a/scipy-1.17.1-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:a77cbd07b940d326d39a1d1b37817e2ee4d79cb30e7338f3d0cddffae70fcaa2", size = 37682317, upload-time = "2026-02-23T00:22:18.513Z" },
+    { url = "https://files.pythonhosted.org/packages/11/2f/b29eafe4a3fbc3d6de9662b36e028d5f039e72d345e05c250e121a230dd4/scipy-1.17.1-cp314-cp314t-win_amd64.whl", hash = "sha256:eb092099205ef62cd1782b006658db09e2fed75bffcae7cc0d44052d8aa0f484", size = 37345327, upload-time = "2026-02-23T00:22:24.442Z" },
+    { url = "https://files.pythonhosted.org/packages/07/39/338d9219c4e87f3e708f18857ecd24d22a0c3094752393319553096b98af/scipy-1.17.1-cp314-cp314t-win_arm64.whl", hash = "sha256:200e1050faffacc162be6a486a984a0497866ec54149a01270adc8a59b7c7d21", size = 25489165, upload-time = "2026-02-23T00:22:29.563Z" },
+]
+
 [[package]]
 name = "shellingham"
 version = "1.5.4"
```

codex
Reviewing Story 13.1 against the live files, the diff, and the cited PRD/architecture/epic sources. I’m starting by re-deriving the spec claims from those documents, then I’ll probe the statistical behavior directly in code for the load-bearing branches.
exec
/bin/bash -lc "nl -ba src/AgentEval/stats/library.py | sed -n '397,610p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   397	                )
   398	            )
   399	
   400	    # ----------------------------------------------------------------- #
   401	    # FR29a/b/c — Phase-2 advanced statistical primitives (Story 13.1)  #
   402	    # Behind `[agenteval-advanced]` optional extra (scipy + numpy).     #
   403	    # ----------------------------------------------------------------- #
   404	
   405	    @keyword(name="Stat.Mann Whitney U")
   406	    @tier(1)
   407	    def compute_mann_whitney_u(
   408	        self,
   409	        runs_a: list[KeywordRun],
   410	        runs_b: list[KeywordRun],
   411	        predicate: Callable[[KeywordRun], float] | None = None,
   412	    ) -> MannWhitneyResult:
   413	        """Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).
   414	
   415	        [Tier 1 — Deterministic] — closed-form non-parametric test for
   416	        whether two independent samples were drawn from the same
   417	        distribution. Returns ``MannWhitneyResult`` with U statistic,
   418	        two-sided p-value, rank-biserial effect size, and sample sizes.
   419	
   420	        Requires the ``[agenteval-advanced]`` optional extra (scipy + numpy);
   421	        raises ``ImportError`` when invoked without it. The ``StatsLibrary``
   422	        class itself remains importable without the extra; only this Phase-2
   423	        keyword method raises on invocation.
   424	
   425	        | =Arguments= | =Description= |
   426	        | ``runs_a`` | ``list[KeywordRun]`` — first sample (typically the result of `Stat.Run N Times` against flow A). |
   427	        | ``runs_b`` | ``list[KeywordRun]`` — second sample (typically the result of `Stat.Run N Times` against flow B). |
   428	        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor producing the numeric quantity to compare (e.g., ``lambda r: r.latency_seconds``). Default ``None`` raises ``ValueError`` — no sensible default numeric metric across all ``KeywordRun`` shapes. NOTE: distinct from `Stat.Get Pass At K`'s boolean predicate. |
   429	
   430	        Raises ``ImportError`` when scipy/numpy are unavailable (missing
   431	        ``[agenteval-advanced]`` extra). Raises ``ValueError`` when
   432	        ``predicate`` is ``None`` OR when either ``runs_a`` / ``runs_b`` is
   433	        empty.
   434	
   435	        Example:
   436	        | @{runs_a} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=claude_code_cli']}}
   437	        | @{runs_b} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=codex_cli']}}
   438	        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
   439	        | ${mwu} =    `Stat.Mann Whitney U`    ${runs_a}    ${runs_b}    predicate=${cost_pred}
   440	        | Should Be True    ${mwu.p_value} < 0.05                                  # Reject the null at α=0.05.
   441	        | Should Be True    abs(${mwu.effect_size_r}) > 0.3                        # Medium-or-larger effect.
   442	
   443	        Notes:
   444	        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
   445	        - PRD FR29a ratifies the ``MannWhitneyResult`` dataclass with ``u_statistic`` / ``p_value`` / ``effect_size_r`` + ``n_a`` / ``n_b``.
   446	        - Math reference: ``scipy.stats.mannwhitneyu(alternative="two-sided", use_continuity=False)``.
   447	        - ``u_statistic`` is the smaller of U1, U2 (canonical form across literature).
   448	        - Effect size: signed rank-biserial ``r = 2*U1/(n_a*n_b) - 1`` (where U1 is the M-W U for samples_a); positive r → samples_a tends to be larger; matches ``Stat.Cliff Delta`` sign convention.
   449	        - One-sided variants (``alternative="greater"``/``"less"``) deferred to Phase-2 (DF-13.1-S1).
   450	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   451	        if not _ADVANCED_AVAILABLE:
   452	            _raise_advanced_extra_missing("Mann Whitney U")
   453	        if predicate is None:
   454	            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
   455	        # Import lazily so the keyword method body owns the import attempt.
   456	        from AgentEval.stats import mannwhitney as _mannwhitney
   457	
   458	        samples_a = [float(predicate(r)) for r in runs_a]
   459	        samples_b = [float(predicate(r)) for r in runs_b]
   460	        return _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)
   461	
   462	    @keyword(name="Stat.Cliff Delta")
   463	    @tier(1)
   464	    def compute_cliff_delta(
   465	        self,
   466	        runs_a: list[KeywordRun],
   467	        runs_b: list[KeywordRun],
   468	        predicate: Callable[[KeywordRun], float] | None = None,
   469	    ) -> float:
   470	        """Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).
   471	
   472	        [Tier 1 — Deterministic] — closed-form Cliff (1993) brute-force
   473	        formula. Returns ``float ∈ [-1.0, 1.0]``. Positive values indicate
   474	        ``runs_a`` tends to produce larger values; negative values indicate
   475	        ``runs_b`` tends to produce larger values.
   476	
   477	        Requires the ``[agenteval-advanced]`` optional extra.
   478	
   479	        | =Arguments= | =Description= |
   480	        | ``runs_a`` | ``list[KeywordRun]`` — first sample. |
   481	        | ``runs_b`` | ``list[KeywordRun]`` — second sample. |
   482	        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor. ``None`` raises ``ValueError``. |
   483	
   484	        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
   485	        when ``predicate`` is ``None`` OR either sample is empty.
   486	
   487	        Example:
   488	        | ${latency_pred} =    Evaluate    lambda r: r.latency_seconds
   489	        | ${delta} =    `Stat.Cliff Delta`    ${runs_a}    ${runs_b}    predicate=${latency_pred}
   490	        | Should Be True    abs(${delta}) > 0.474                                  # Large effect per Romano-Coraggio-Smith conventions.
   491	
   492	        Notes:
   493	        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
   494	        - PRD FR29b ratifies the scalar ``float`` return type (NOT a dataclass) — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
   495	        - Math: ``δ = (#{a>b} - #{a<b}) / (n_a * n_b)``; ties contribute 0.
   496	        - Complexity: ``O(n_a * n_b)``. Fine for typical n ≤ 100 trials; Phase-2 perf carve-out for n_a + n_b > 1000.
   497	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   498	        if not _ADVANCED_AVAILABLE:
   499	            _raise_advanced_extra_missing("Cliff Delta")
   500	        if predicate is None:
   501	            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
   502	        from AgentEval.stats import cliffs_delta as _cliffs_delta
   503	
   504	        samples_a = [float(predicate(r)) for r in runs_a]
   505	        samples_b = [float(predicate(r)) for r in runs_b]
   506	        return _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
   507	
   508	    @keyword(name="Stat.Bootstrap Confidence Interval")
   509	    @tier(1)
   510	    def compute_bootstrap_ci(
   511	        self,
   512	        samples: list[KeywordRun] | list[float],
   513	        statistic: Callable[[list[float]], float] | None = None,
   514	        predicate: Callable[[KeywordRun], float] | None = None,
   515	        alpha: float = 0.05,
   516	        n_resamples: int = 10_000,
   517	        seed: int | None = None,
   518	    ) -> tuple[float, float]:
   519	        """Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).
   520	
   521	        [Tier 1 — Deterministic] — when ``seed`` is given, the result is
   522	        reproducible across calls; ``seed=None`` uses OS entropy. Returns
   523	        ``(ci_lower, ci_upper)`` tuple at the ``(1 - alpha) * 100%`` percentile
   524	        level (default 95% CI).
   525	
   526	        Requires the ``[agenteval-advanced]`` optional extra.
   527	
   528	        | =Arguments= | =Description= |
   529	        | ``samples`` | Either ``list[KeywordRun]`` (then ``predicate`` extracts floats) OR ``list[float]`` (predicate ignored). |
   530	        | ``statistic`` | ``Callable[[list[float]], float]`` whose CI is computed. Default ``None`` → ``statistics.mean``. |
   531	        | ``predicate`` | Optional ``Callable[[KeywordRun], float]`` value-extractor (required when ``samples`` is ``list[KeywordRun]``). |
   532	        | ``alpha`` | Significance level; CI is at ``(1-alpha)*100%`` confidence. Must satisfy ``0.0 < alpha < 1.0``. Default ``0.05``. |
   533	        | ``n_resamples`` | Number of bootstrap resamples (with replacement). Must be ``>= 100``. Default ``10_000``. |
   534	        | ``seed`` | Optional ``int`` seed for the numpy ``Generator``; ``None`` → OS entropy. |
   535	
   536	        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
   537	        when ``samples`` is empty / ``alpha`` is out of range / ``n_resamples
   538	        < 100`` / ``predicate`` is missing for a ``list[KeywordRun]`` input.
   539	
   540	        Example:
   541	        | @{runs} =    `Stat.Run N Times`    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
   542	        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
   543	        | ${ci_lo}    ${ci_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    predicate=${cost_pred}    seed=42
   544	        | Should Be True    ${ci_lo} <= ${ci_hi}                                    # CI bounds well-ordered.
   545	        | ${median_stat} =    Evaluate    statistics.median    modules=statistics
   546	        | ${med_lo}    ${med_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    statistic=${median_stat}    predicate=${cost_pred}    seed=42
   547	
   548	        Notes:
   549	        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
   550	        - PRD FR29c ratifies the ``(lo, hi)`` tuple return type — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
   551	        - Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).
   552	        - Math reference: ``scipy.stats.bootstrap(..., method="percentile")``. The local implementation uses ``numpy.random.Generator(seed)`` for control over the random source.
   553	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   554	        if not _ADVANCED_AVAILABLE:
   555	            _raise_advanced_extra_missing("Bootstrap Confidence Interval")
   556	        import statistics as _statistics
   557	
   558	        from AgentEval.stats import bootstrap as _bootstrap
   559	
   560	        if statistic is None:
   561	            statistic = _statistics.mean
   562	        # Determine if samples are KeywordRun (need predicate) or raw floats.
   563	        if not samples:
   564	            raise ValueError("samples must be non-empty")
   565	        first = samples[0]
   566	        numeric_samples: list[float]
   567	        if isinstance(first, KeywordRun):
   568	            if predicate is None:
   569	                raise ValueError(
   570	                    "predicate is required when samples is list[KeywordRun]; "
   571	                    "pass a Callable[[KeywordRun], float] value-extractor"
   572	                )
   573	            # samples is list[KeywordRun] in this branch (per first element);
   574	            # cast manually for mypy since the union type alias loses
   575	            # element-level homogeneity guarantees.
   576	            kw_samples: list[KeywordRun] = [s for s in samples if isinstance(s, KeywordRun)]
   577	            numeric_samples = [float(predicate(r)) for r in kw_samples]
   578	        else:
   579	            float_samples: list[float] = [s for s in samples if not isinstance(s, KeywordRun)]
   580	            numeric_samples = [float(s) for s in float_samples]
   581	        return _bootstrap.compute_bootstrap_ci(
   582	            numeric_samples,
   583	            statistic,
   584	            alpha,
   585	            n_resamples,
   586	            seed,
   587	        )
   588	
   589	
   590	def _byte_identical(a: Any, b: Any) -> bool:
   591	    """Story 6.3 code-review HIGH-ο fix (Blind): NaN-aware equality.
   592	
   593	    Python `==` on `float('nan')` returns False, breaking the bit-identical
   594	    guarantee for any Tier-1 keyword returning NaN. This helper does
   595	    structural equality with `math.isnan` short-circuit. For non-float
   596	    values, falls back to `==`. Handles nested containers via recursion.
   597	    """
   598	    import math
   599	
   600	    if isinstance(a, float) and isinstance(b, float):
   601	        if math.isnan(a) and math.isnan(b):
   602	            return True
   603	        return a == b
   604	    if type(a) is not type(b):
   605	        # Differing types still allow Python `==` to handle numeric coercion
   606	        # but reject for sequence/dict mismatches.
   607	        return bool(a == b)
   608	    if isinstance(a, dict):
   609	        if set(a.keys()) != set(b.keys()):
   610	            return False

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/library.py | sed -n '1,260p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	# ruff: noqa: E501
    16	# Browser-Library-style docstring tables (`| =Arguments= | =Description= |`)
    17	# can carry long descriptions on a single physical line. The per-line
    18	# 120-char limit is waived for this file per Phase 2 docstring-refresh
    19	# proposal (2026-05-26).
    20	
    21	"""Statistical primitives RF-keyword surface (Story 6.3 / PRD FR26 + FR27 + FR31a).
    22	
    23	Ships 4 `@keyword`-decorated methods on `StatsLibrary`:
    24	
    25	- FR26: `Stat.Run N Times` (Tier-3 fan-out via `@guarded_fanout`) — independent-
    26	  sample N-trial runner; returns `list[KeywordRun]` per Story 1b.6 ratified
    27	  return type.
    28	- FR27: `Stat.Get Pass At K` (Tier-1) — HumanEval unbiased estimator; returns
    29	  `float ∈ [0, 1]`.
    30	- D-1 resolution paired getter: `Stat.Get Pass At K Confidence Interval` (Tier-1)
    31	  — Wilson score interval at `confidence` level.
    32	- FR31a: `Stat.Assert Run Determinism` (Tier-1) — runs a Tier-1 keyword twice,
    33	  asserts bit-identical output.
    34	
    35	Sub-library registration via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.
    36	Tier-3 `Stat.Run N Times` reads `_max_cost_usd` + `_max_runtime_seconds`
    37	from `self` (forwarded from top-level `AgentEval(...)` per Story 1a.6 +
    38	Story 4.3 propagation pattern).
    39	"""
    40	
    41	from __future__ import annotations
    42	
    43	from collections.abc import Callable
    44	from typing import Any
    45	
    46	from robot.api.deco import keyword
    47	
    48	from AgentEval._kernel.context import current_context
    49	from AgentEval._kernel.guardrails import guarded_fanout
    50	from AgentEval._kernel.redaction import redact
    51	from AgentEval._kernel.tier import tier
    52	from AgentEval.errors import TierViolationError
    53	from AgentEval.stats import _internal
    54	from AgentEval.stats.types import KeywordRun, MannWhitneyResult
    55	
    56	__all__ = ["StatsLibrary"]
    57	
    58	# Browser-Library-style docstring migration marker (Phase 2, 2026-05-26).
    59	_BROWSER_STYLE_MIGRATED = True
    60	
    61	# Story 13.1 — Phase-2 `[agenteval-advanced]` extra gate. scipy + numpy power
    62	# the 3 advanced keyword methods (Mann-Whitney U, Cliff Delta, Bootstrap CI).
    63	# The `StatsLibrary` class itself MUST remain importable WITHOUT the extra so
    64	# Phase-1 surface keywords stay functional; only the 3 Phase-2 methods raise
    65	# ImportError on invocation.
    66	try:
    67	    import numpy as _numpy_advanced  # noqa: F401
    68	    import scipy as _scipy_advanced  # noqa: F401
    69	
    70	    _ADVANCED_AVAILABLE = True
    71	    _ADVANCED_IMPORT_ERROR: ImportError | None = None
    72	except ImportError as _advanced_err:  # pragma: no cover  -- exercised via monkeypatch
    73	    _ADVANCED_AVAILABLE = False
    74	    _ADVANCED_IMPORT_ERROR = _advanced_err
    75	
    76	
    77	def _raise_advanced_extra_missing(keyword_name: str) -> None:
    78	    """Raise the canonical `[agenteval-advanced]` extra-missing ImportError.
    79	
    80	    Per Story 13.1 D-3 + epics.md L2153: the ImportError MUST recommend
    81	    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
    82	    """
    83	    raise ImportError(
    84	        f"Stat.{keyword_name}: scipy + numpy required. "
    85	        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
    86	    ) from _ADVANCED_IMPORT_ERROR
    87	
    88	
    89	class StatsLibrary:
    90	    """4 `@keyword`-decorated statistical primitives (Story 6.3 / PRD FR26-FR31a)."""
    91	
    92	    def __init__(
    93	        self,
    94	        max_cost_usd: float | None = None,
    95	        max_runtime_seconds: float | None = None,
    96	    ) -> None:
    97	        """Library-level cost/runtime budgets per Story 1a.6 + ADR-015.
    98	
    99	        Forwarded from top-level `AgentEval(max_cost_usd=..., max_runtime_seconds=...)`
   100	        via `_build_components` per Story 4.3 pattern. Consumed by `@guarded_fanout`
   101	        on `Stat.Run N Times` (Tier-3 fan-out keyword).
   102	        """
   103	        self._max_cost_usd = max_cost_usd
   104	        self._max_runtime_seconds = max_runtime_seconds
   105	
   106	    # ----------------------------------------------------------------- #
   107	    # FR26 — Stat.Run N Times (Tier-3 fan-out)                          #
   108	    # ----------------------------------------------------------------- #
   109	
   110	    @keyword(name="Stat.Run N Times")
   111	    @tier(3)
   112	    @guarded_fanout()
   113	    def run_n_times(
   114	        self,
   115	        n: int,
   116	        keyword: str | Callable[..., Any],
   117	        keyword_args: dict[str, Any] | list[Any] | None = None,
   118	        seed: int | None = None,
   119	    ) -> list[KeywordRun]:
   120	        """Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).
   121	
   122	        [Tier 3 — Stochastic Fan-Out] — wraps the target keyword in
   123	        independent trials. Returns ``list[KeywordRun]`` of length ``n``.
   124	        Trial-level errors are re-raised from this keyword — wrap in
   125	        ``Run Keyword And Ignore Error`` for "ignore failures" semantics.
   126	
   127	        | =Arguments= | =Description= |
   128	        | ``n`` | Number of independent trials. Must be ``>= 1``. |
   129	        | ``keyword`` | RF keyword name (``str``) OR a Python callable. String form requires an active RF execution context (resolved via ``BuiltIn``); callable form is useful for pytest unit tests. |
   130	        | ``keyword_args`` | Optional ``dict`` of kwargs OR ``list`` of RF named-arg strings (e.g. ``{"adapter": "generic", "prompt": "Hi"}`` or ``["adapter=generic", "prompt=Hi"]``). ``None`` = no args. |
   131	        | ``seed`` | Optional ``int`` seed; each trial receives ``seed + trial_index`` via a ``seed=`` kwarg injection so trials are deterministic but distinct. ``None`` = OS-entropy seeding per trial. |
   132	
   133	        Raises ``ValueError`` when ``n < 1``. Raises ``CostExceededError`` /
   134	        ``RuntimeBudgetExceededError`` per the ``@guarded_fanout`` 3-layer
   135	        enforcement.
   136	
   137	        Example:
   138	        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}
   139	        | ${pass_at_5} =    `Stat.Get Pass At K`    ${runs}    k=5
   140	        | Should Be True    ${pass_at_5} >= 0.6
   141	        | @{runs} =    `Stat.Run N Times`    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42
   142	
   143	        Notes:
   144	        - PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the ``list[KeywordRun]`` return type.
   145	        - Cost / runtime guardrails per ADR-015 + `_kernel/guardrails.py::@guarded_fanout`.
   146	        - Sibling keyword: `Stat.Get Pass At K` (Tier-1) consumes the returned list.
   147	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   148	        if n < 1:
   149	            raise ValueError(f"n must be >= 1; got {n!r}")
   150	        positional, named = _internal._normalize_keyword_args(keyword_args)
   151	        callable_ref: Callable[..., Any]
   152	        kw_name: str
   153	        if isinstance(keyword, str):
   154	            kw_name = keyword
   155	            # Story 6.3 code-review HIGH-γ fix (Codex empirical STAR):
   156	            # `BuiltIn.run_keyword(name, /, *args)` is varargs-only — passing
   157	            # `**kwargs` raises TypeError. Reconstruct RF-style positional +
   158	            # `key=value` tokens that the run_keyword(name, *args) signature
   159	            # accepts.
   160	            from robot.libraries.BuiltIn import BuiltIn
   161	
   162	            def callable_ref_impl(*pos: Any, **kw: Any) -> Any:
   163	                rf_args: list[Any] = list(pos)
   164	                for k, v in kw.items():
   165	                    rf_args.append(f"{k}={v}")
   166	                return BuiltIn().run_keyword(kw_name, *rf_args)
   167	
   168	            callable_ref = callable_ref_impl
   169	        else:
   170	            callable_ref = keyword
   171	            # Story 6.3 code-review LOW-9 fix (Codex): prefer `robot_name`
   172	            # over Python `__name__` for operator-facing telemetry consistency.
   173	            target = getattr(keyword, "__func__", keyword)
   174	            kw_name = str(getattr(target, "robot_name", None) or getattr(keyword, "__name__", repr(keyword)))
   175	
   176	        ctx = current_context()
   177	        parent_test_id = ctx.test_id if ctx is not None else ""
   178	
   179	        runs: list[KeywordRun] = []
   180	        for trial_index in range(n):
   181	            run = _internal._dispatch_trial(
   182	                callable_ref,
   183	                kw_name,
   184	                positional,
   185	                named,
   186	                parent_test_id,
   187	                trial_index,
   188	                seed,
   189	            )
   190	            runs.append(run)
   191	        return runs
   192	
   193	    # ----------------------------------------------------------------- #
   194	    # FR27 — Stat.Get Pass At K (Tier-1)                                #
   195	    # ----------------------------------------------------------------- #
   196	
   197	    @keyword(name="Stat.Get Pass At K")
   198	    @tier(1)
   199	    def get_pass_at_k(
   200	        self,
   201	        runs: list[KeywordRun],
   202	        k: int,
   203	        predicate: Callable[[KeywordRun], bool] | None = None,
   204	    ) -> float:
   205	        """Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).
   206	
   207	        [Tier 1 — Deterministic] — closed-form computation of the
   208	        HumanEval estimator ``1 - C(n-c, k) / C(n, k)``. Returns
   209	        ``float ∈ [0, 1]``. Scalar return preserves AssertionEngine
   210	        compatibility (``>=`` / ``<=`` matchers); CI is a separate paired
   211	        getter — see `Stat.Get Pass At K Confidence Interval`.
   212	
   213	        | =Arguments= | =Description= |
   214	        | ``runs`` | ``list[KeywordRun]`` — typically the result of `Stat.Run N Times`. |
   215	        | ``k`` | Top-k parameter. Must satisfy ``1 <= k <= len(runs)``. |
   216	        | ``predicate`` | Optional ``Callable[[KeywordRun], bool]`` for pass/fail classification. Default checks ``r.completeness == "complete"`` per epic AC-2 + Story 6.4 fix-NOW. |
   217	
   218	        Raises ``ValueError`` when ``k < 1``, ``k > len(runs)``, or
   219	        ``len(runs) == 0``.
   220	
   221	        Example:
   222	        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
   223	        | ${pass_at_1} =    `Stat.Get Pass At K`    ${runs}    k=1
   224	        | ${pass_at_5} =    `Stat.Get Pass At K`    ${runs}    k=5
   225	        | Should Be True    ${pass_at_5} >= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.
   226	        | ${pred} =    Evaluate    lambda r: r.error is None
   227	        | ${pass_strict} =    `Stat.Get Pass At K`    ${runs}    k=5    predicate=${pred}
   228	
   229	        Notes:
   230	        - PRD FR27 ratifies the scalar ``float`` return type — no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).
   231	        - Default predicate updated by Story 6.4 fix-NOW: ``completeness == "complete"`` (pre-edit ``"full"`` was fake-green; `AgentRunMetadata._VALID_COMPLETENESS` is ``{"complete", "truncated", "partial"}``).
   232	        - Sibling keyword: `Stat.Get Pass At K Confidence Interval` for the Wilson score CI.
   233	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   234	        predicate_fn = predicate if predicate is not None else _internal._default_pass_predicate
   235	        c = sum(1 for r in runs if predicate_fn(r))
   236	        n = len(runs)
   237	        return _internal._compute_pass_at_k(c, n, k)
   238	
   239	    @keyword(name="Stat.Get Pass At K Confidence Interval")
   240	    @tier(1)
   241	    def get_pass_at_k_confidence_interval(
   242	        self,
   243	        runs: list[KeywordRun],
   244	        k: int,
   245	        predicate: Callable[[KeywordRun], bool] | None = None,
   246	        confidence: float = 0.95,
   247	    ) -> tuple[float, float]:
   248	        """Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).
   249	
   250	        [Tier 1 — Deterministic] — Wilson score interval at the given
   251	        ``confidence`` level for the latent per-trial success probability.
   252	        Returns ``(ci_lower, ci_upper)`` tuple of ``float`` in ``[0, 1]``.
   253	        Paired with `Stat.Get Pass At K` — the scalar point estimate plus
   254	        this CI together satisfy epic AC-2's "Pass@k with confidence
   255	        interval" promise.
   256	
   257	        | =Arguments= | =Description= |
   258	        | ``runs`` | ``list[KeywordRun]`` — typically the result of `Stat.Run N Times`. |
   259	        | ``k`` | Top-k parameter. Validated for ``1 <= k <= len(runs)`` but only used for sanity check — the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself. |
   260	        | ``predicate`` | Optional ``Callable[[KeywordRun], bool]`` for pass/fail classification. Same default as `Stat.Get Pass At K`. |

exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/epics.md | sed -n '2141,2158p'" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/prd.md | sed -n '1534,1542p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  2141	#### Story 13.1: Advanced Statistical Primitives Behind `[agenteval-advanced]` Extra
  2142	
  2143	As **Raj (Agent Developer)** doing multi-model comparison,
  2144	I want `Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap CI` keywords behind the `[agenteval-advanced]` optional extra,
  2145	So that I can statistically compare two non-deterministic agent flows with proper effect-size + significance metrics.
  2146	
  2147	**Acceptance Criteria:**
  2148	
  2149	**Given** two `Stat.Run N Times` result lists,
  2150	**When** I call `${u}=    Stat.Mann Whitney U    ${results_a}    ${results_b}    predicate=lambda r: r.cost_usd`,
  2151	**Then** the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29c (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent).
  2152	
  2153	**And** all advanced stats keywords are behind `[agenteval-advanced]` extra (requires `scipy + numpy`); ImportError on import without the extra has a clear message recommending `uv pip install robotframework-agenteval[agenteval-advanced]`.
  2154	
  2155	**And** unit tests verify math against scipy reference implementations.
  2156	
  2157	---
  2158	

 succeeded in 0ms:
  1534	- **FR26:** Agent Developer can call `Stat.Run N Times <n> <keyword> <args>...` and receive `list[KeywordRun]`; library guarantees independent samples (fresh agent instance per run; no state leakage).
  1535	- **FR27:** Agent Developer can call `Stat.Get Pass At K <runs> k=<int>` and receive `float ∈ [0, 1]` computed via the HumanEval unbiased estimator (`1 - C(n-c, k) / C(n, k)`); accepts AssertionEngine matchers (`>=`, `<=`, etc.).
  1536	- **FR28:** Library raises `PollingDisallowedError` (verbatim text per frontmatter PollingDisallowedError revised wording entry) whenever a Tier-2 or Tier-3 keyword receives `polling=` argument. Verifiable via `Run Keyword And Expect Error PollingDisallowedError* Skill.Get Activation Decision polling=1s` in `tests/conformance/`.
  1537	- **FR29a (Phase 2 — `agenteval-advanced` extras):** Agent Developer can call `Stat.Mann Whitney U <runs_a> <runs_b>` returning `MannWhitneyResult(u_statistic, p_value, effect_size_r)`; FR is observable Phase 2 only — the extras package's import surface is the test target.
  1538	- **FR29b (Phase 2):** Agent Developer can call `Stat.Cliff Delta <runs_a> <runs_b>` returning `float ∈ [-1, 1]`.
  1539	- **FR29c (Phase 2):** Agent Developer can call `Stat.Bootstrap Confidence Interval <samples> statistic=<callable> alpha=0.05` returning `(lo, hi)` tuple.
  1540	- **FR30a (tier model):** Library categorizes every `@keyword`-decorated method into Tier 1 / 2 / 3 via metadata; `Get Keyword Tier <keyword_name>` returns the tier; libdoc renders the tier badge in keyword reference. Verifiable via reflection on the keyword registry.
  1541	- **FR30b (ACL gates):** Library raises `TierViolationError` if a Tier-1 keyword attempts to invoke an LLM provider or `validate` operator without explicit opt-in; verifiable via reflection on the keyword dispatcher.
  1542	- **FR31a (determinism — Tier 1):** Library guarantees bit-identical output across runs of any Tier-1 keyword given identical inputs; verifiable via `Assert Run Determinism <keyword> <args> expect=byte_identical` in conformance suite.

exec
/bin/bash -lc "nl -ba _bmad-output/planning-artifacts/architecture.md | sed -n '1302,1312p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
  1302	│       ├── stats/                          # Borrowed shape from agentguard ADR-005 statistical primitives; agenteval is free to diverge
  1303	│       │   ├── __init__.py
  1304	│       │   ├── library.py                  # Stat keywords: Run N Times, Get Pass At K per FR26-27
  1305	│       │   ├── pass_at_k.py                # HumanEval unbiased estimator
  1306	│       │   ├── mannwhitney.py              # Phase 2 (in [agenteval-advanced] extra)
  1307	│       │   ├── cliffs_delta.py             # Phase 2
  1308	│       │   ├── bootstrap.py                # Phase 2 (CI for binomial proportions; Wilson CI in Phase 1)
  1309	│       │   ├── wilson.py                   # Wilson CI for Phase 1 (no SciPy dep yet)
  1310	│       │   └── _helpers.py
  1311	│       │
  1312	│       ├── judge/                          # Phase 2 only (under [judge] extra); FR48 + pattern reviewed in agentguard ADR-011

codex
I’ve confirmed the FR29 lines in PRD, architecture file-home allocation, and Epic 13 AC wording. Next I’m checking the implementation and tests against those exact claims, plus running the sign/U-stat/bootstrap probes directly.
exec
/bin/bash -lc 'nl -ba src/AgentEval/stats/mannwhitney.py' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Mann-Whitney U statistical primitive (PRD FR29a; Story 13.1).
    16	
    17	Phase-2 module — requires the `[agenteval-advanced]` optional extra (scipy +
    18	numpy). Imported lazily by `AgentEval.stats.library.StatsLibrary.mann_whitney_u`
    19	behind an `_ADVANCED_AVAILABLE` gate; importing this module without scipy
    20	installed raises `ImportError` at the `import scipy.stats` line.
    21	
    22	Math reference: ``scipy.stats.mannwhitneyu`` (alternative="two-sided",
    23	use_continuity=False). Effect size: rank-biserial correlation
    24	``r = 2 * U1 / (n_a * n_b) - 1`` (signed convention where U1 is the
    25	Mann-Whitney U for samples_a; positive r → samples_a tends to be larger
    26	than samples_b). This matches the Cliff's delta sign convention shipped
    27	by `Stat.Cliff Delta` (Story 13.1 FR29b).
    28	
    29	Phase-1.5/2 carry-overs:
    30	- DF-13.1-S1: one-sided alternatives ("greater"/"less"). Phase-1 ships
    31	  two-sided only.
    32	- DF-13.1-S3: ``MannWhitneyResult.effect_size_interpretation`` Cohen-band
    33	  Literal field. Phase-1 returns the raw ``effect_size_r``.
    34	"""
    35	
    36	from __future__ import annotations
    37	
    38	import scipy.stats as _scipy_stats
    39	
    40	from AgentEval.stats.types import MannWhitneyResult
    41	
    42	__all__ = ["compute_mann_whitney_u"]
    43	
    44	
    45	def compute_mann_whitney_u(
    46	    samples_a: list[float],
    47	    samples_b: list[float],
    48	) -> MannWhitneyResult:
    49	    """Compute the Mann-Whitney U statistic + p-value + effect size (FR29a).
    50	
    51	    Args:
    52	        samples_a: First-group numeric samples; must be non-empty.
    53	        samples_b: Second-group numeric samples; must be non-empty.
    54	
    55	    Returns:
    56	        ``MannWhitneyResult`` with ``u_statistic`` (the smaller of U1, U2 per
    57	        scipy default), two-sided ``p_value``, rank-biserial ``effect_size_r``,
    58	        and the sample sizes ``n_a`` and ``n_b``.
    59	
    60	    Raises:
    61	        ValueError: When either samples list is empty.
    62	
    63	    Notes:
    64	        - The smaller-U convention matches ``scipy.stats.mannwhitneyu(...,
    65	          alternative="two-sided", use_continuity=False)``: scipy reports
    66	          ``U1`` corresponding to the first input by default, but the
    67	          two-sided p-value is symmetric in U1/U2, so consumers can recover
    68	          U2 via ``U2 = n_a * n_b - U1``. We return the smaller of the two
    69	          to match the most commonly-cited form across literature.
    70	    """
    71	    n_a = len(samples_a)
    72	    n_b = len(samples_b)
    73	    if n_a < 1:
    74	        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    75	    if n_b < 1:
    76	        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    77	    result = _scipy_stats.mannwhitneyu(
    78	        samples_a,
    79	        samples_b,
    80	        alternative="two-sided",
    81	        use_continuity=False,
    82	    )
    83	    u1 = float(result.statistic)
    84	    u2 = float(n_a * n_b - u1)
    85	    u_smaller = min(u1, u2)
    86	    # Signed rank-biserial correlation r = 2 * U1 / (n_a * n_b) - 1. U1 is
    87	    # the count of pairs where samples_a > samples_b (with 0.5 for ties), so:
    88	    #   - U1 = 0 (samples_a strictly < samples_b) → r = -1.0
    89	    #   - U1 = n_a * n_b / 2 (no separation) → r = 0.0
    90	    #   - U1 = n_a * n_b (samples_a strictly > samples_b) → r = +1.0
    91	    # Matches Cliff's delta sign convention shipped by `Stat.Cliff Delta`.
    92	    effect_size_r = 2.0 * u1 / (n_a * n_b) - 1.0
    93	    return MannWhitneyResult(
    94	        u_statistic=u_smaller,
    95	        p_value=float(result.pvalue),
    96	        effect_size_r=effect_size_r,
    97	        n_a=n_a,
    98	        n_b=n_b,
    99	    )

exec
/bin/bash -lc "nl -ba tests/unit/stats/test_advanced.py | sed -n '260,420p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   260	    with pytest.raises(ValueError, match="n_resamples"):
   261	        _bootstrap.compute_bootstrap_ci([1.0, 2.0, 3.0], statistics.mean, 0.05, 50, 42)
   262	
   263	
   264	# --------------------------------------------------------------------------- #
   265	# Predicate value-extraction at the keyword surface (2 tests)                 #
   266	# --------------------------------------------------------------------------- #
   267	
   268	
   269	def test_mannwhitney_keyword_predicate_extracts_from_keyword_run() -> None:
   270	    """predicate=lambda r: r.latency_seconds extracts correctly."""
   271	    lib = StatsLibrary()
   272	    runs_a = [_make_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
   273	    runs_b = [_make_run(v, trial_index=i) for i, v in enumerate([10.0, 11.0, 12.0, 13.0, 14.0])]
   274	    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
   275	    assert isinstance(result, MannWhitneyResult)
   276	    assert result.n_a == 5
   277	    assert result.n_b == 5
   278	    assert result.p_value < 0.05  # Clearly separated.
   279	
   280	
   281	def test_mannwhitney_keyword_predicate_none_raises_value_error() -> None:
   282	    """predicate=None on Mann-Whitney U raises ValueError."""
   283	    lib = StatsLibrary()
   284	    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
   285	    with pytest.raises(ValueError, match="predicate is required"):
   286	        lib.compute_mann_whitney_u(runs, runs, predicate=None)
   287	
   288	
   289	def test_cliff_delta_keyword_predicate_none_raises_value_error() -> None:
   290	    """predicate=None on Cliff Delta raises ValueError."""
   291	    lib = StatsLibrary()
   292	    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
   293	    with pytest.raises(ValueError, match="predicate is required"):
   294	        lib.compute_cliff_delta(runs, runs, predicate=None)
   295	
   296	
   297	def test_bootstrap_keyword_predicate_required_for_keyword_run_input() -> None:
   298	    """Bootstrap CI with list[KeywordRun] input + predicate=None raises."""
   299	    lib = StatsLibrary()
   300	    runs = [_make_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0]]
   301	    with pytest.raises(ValueError, match="predicate is required"):
   302	        lib.compute_bootstrap_ci(runs, statistic=statistics.mean, n_resamples=200, seed=42)
   303	
   304	
   305	def test_bootstrap_keyword_raw_floats_input_works() -> None:
   306	    """Bootstrap CI accepts raw list[float] without a predicate."""
   307	    lib = StatsLibrary()
   308	    lo, hi = lib.compute_bootstrap_ci(
   309	        [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
   310	        statistic=statistics.mean,
   311	        n_resamples=500,
   312	        seed=42,
   313	    )
   314	    assert lo <= hi
   315	
   316	
   317	# --------------------------------------------------------------------------- #
   318	# ImportError gate WITHOUT [agenteval-advanced] extras (3 tests)              #
   319	# --------------------------------------------------------------------------- #
   320	
   321	
   322	def test_raise_advanced_extra_missing_helper_carries_canonical_message() -> None:
   323	    """`_raise_advanced_extra_missing` produces the spec-mandated ImportError text.
   324	
   325	    Per Story 13.1 D-3 + epics.md L2153: the message MUST include both the
   326	    keyword name and the verbatim install hint
   327	    `uv pip install robotframework-agenteval[agenteval-advanced]`.
   328	    """
   329	    from AgentEval.stats.library import _raise_advanced_extra_missing
   330	
   331	    for kw in ("Mann Whitney U", "Cliff Delta", "Bootstrap Confidence Interval"):
   332	        with pytest.raises(ImportError) as exc_info:
   333	            _raise_advanced_extra_missing(kw)
   334	        msg = str(exc_info.value)
   335	        assert f"Stat.{kw}" in msg
   336	        assert "agenteval-advanced" in msg
   337	        assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
   338	
   339	
   340	def test_phase2_keywords_raise_import_error_when_extra_unavailable(
   341	    monkeypatch: pytest.MonkeyPatch,
   342	) -> None:
   343	    """All 3 Phase-2 keywords raise ImportError when `_ADVANCED_AVAILABLE = False`.
   344	
   345	    Monkeypatches the module-level gate directly (vs reloading the module with
   346	    scipy stubbed out) — module reload across tests pollutes `sys.modules` and
   347	    leaves stats.library in a partial-import state. The gate check is the
   348	    load-bearing branch; this verifies it triggers correctly for each keyword.
   349	    """
   350	    from AgentEval.stats import library as lib_mod
   351	
   352	    monkeypatch.setattr(lib_mod, "_ADVANCED_AVAILABLE", False)
   353	    lib = lib_mod.StatsLibrary()
   354	
   355	    with pytest.raises(ImportError, match="agenteval-advanced"):
   356	        lib.compute_mann_whitney_u(
   357	            [_make_run(1.0)],
   358	            [_make_run(2.0)],
   359	            predicate=lambda r: r.latency_seconds,
   360	        )
   361	
   362	    with pytest.raises(ImportError, match="agenteval-advanced"):
   363	        lib.compute_cliff_delta(
   364	            [_make_run(1.0)],
   365	            [_make_run(2.0)],
   366	            predicate=lambda r: r.latency_seconds,
   367	        )
   368	
   369	    with pytest.raises(ImportError, match="agenteval-advanced"):
   370	        lib.compute_bootstrap_ci(
   371	            [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
   372	            statistic=statistics.mean,
   373	            n_resamples=200,
   374	            seed=42,
   375	        )

exec
/bin/bash -lc 'nl -ba src/AgentEval/stats/cliffs_delta.py' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Cliff's delta non-parametric effect-size primitive (PRD FR29b; Story 13.1).
    16	
    17	Phase-2 module — gated by the `[agenteval-advanced]` extra for parity with
    18	the other 2 Story 13.1 modules. The closed-form brute-force computation
    19	(Cliff 1993) is pure-Python and does NOT strictly require scipy/numpy, but
    20	this module imports numpy unconditionally so the keyword surface presents a
    21	unified ``ImportError`` story across all 3 Phase-2 keywords.
    22	
    23	Math: ``δ = (#{i,j : a_i > b_j} - #{i,j : a_i < b_j}) / (n_a * n_b)``.
    24	Range: ``[-1.0, 1.0]``; sign convention matches scipy's effect-size
    25	direction (positive = samples_a tends to be larger).
    26	
    27	Complexity: O(n_a * n_b). Fine for typical n ≤ 100 trials per group; for
    28	n_a + n_b > 1000 a Phase-2 algorithm-improvement carve-out applies.
    29	
    30	Phase-1.5/2 carry-overs: none specific to Cliff's delta (DF-13.1-S* covers
    31	the broader Phase-2 stats surface).
    32	"""
    33	
    34	from __future__ import annotations
    35	
    36	import numpy as _np  # noqa: F401  # Unified [agenteval-advanced] gate parity.
    37	
    38	__all__ = ["compute_cliff_delta"]
    39	
    40	
    41	def compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float:
    42	    """Compute Cliff's delta non-parametric effect size (FR29b).
    43	
    44	    Args:
    45	        samples_a: First-group numeric samples; must be non-empty.
    46	        samples_b: Second-group numeric samples; must be non-empty.
    47	
    48	    Returns:
    49	        ``float ∈ [-1.0, 1.0]``. Positive values indicate ``samples_a`` tends
    50	        to be larger; negative values indicate ``samples_b`` tends to be
    51	        larger. Magnitude near 0 indicates substantial overlap.
    52	
    53	    Raises:
    54	        ValueError: When either samples list is empty.
    55	
    56	    Notes:
    57	        Closed-form Cliff (1993) brute-force formula. Pure-Python loop is
    58	        clearest; numpy vectorization is a Phase-2 perf optimization carve-out.
    59	    """
    60	    n_a = len(samples_a)
    61	    n_b = len(samples_b)
    62	    if n_a < 1:
    63	        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    64	    if n_b < 1:
    65	        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    66	    greater = 0
    67	    less = 0
    68	    for a in samples_a:
    69	        for b in samples_b:
    70	            if a > b:
    71	                greater += 1
    72	            elif a < b:
    73	                less += 1
    74	            # ties (a == b) contribute 0 per Cliff 1993.
    75	    return (greater - less) / (n_a * n_b)

exec
/bin/bash -lc 'nl -ba src/AgentEval/stats/bootstrap.py' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Bootstrap confidence interval primitive (PRD FR29c; Story 13.1).
    16	
    17	Phase-2 module — requires the `[agenteval-advanced]` extra (scipy + numpy).
    18	Computes a percentile bootstrap CI for any statistic over numeric samples.
    19	Reproducibility via the optional ``seed`` parameter (None → OS entropy).
    20	
    21	Math reference: ``scipy.stats.bootstrap`` (method="percentile",
    22	confidence_level=1-alpha). The custom resampler here is implemented directly
    23	for control over the random source — scipy is used for cross-validation in
    24	unit tests.
    25	
    26	Phase-1.5/2 carry-overs:
    27	- DF-13.1-S2: CI methods beyond percentile (BCa, BC-corrected). Phase-1 ships
    28	  percentile only.
    29	"""
    30	
    31	from __future__ import annotations
    32	
    33	from collections.abc import Callable
    34	
    35	import numpy as _np
    36	
    37	__all__ = ["compute_bootstrap_ci"]
    38	
    39	
    40	def compute_bootstrap_ci(
    41	    samples: list[float],
    42	    statistic: Callable[[list[float]], float],
    43	    alpha: float,
    44	    n_resamples: int,
    45	    seed: int | None,
    46	) -> tuple[float, float]:
    47	    """Compute a percentile bootstrap CI for the given statistic (FR29c).
    48	
    49	    Args:
    50	        samples: Non-empty list of numeric samples.
    51	        statistic: Callable mapping a resampled list of floats to a scalar
    52	            statistic (e.g., ``statistics.mean``, ``statistics.median``).
    53	        alpha: Significance level. CI is at ``(1 - alpha) * 100%`` confidence.
    54	            Must satisfy ``0.0 < alpha < 1.0``.
    55	        n_resamples: Number of bootstrap resamples (with replacement). Must be
    56	            ``>= 100`` (lower values produce unstable percentile estimates).
    57	        seed: Optional integer seed for the underlying ``numpy.random.Generator``.
    58	            ``None`` → OS-entropy seeding (non-reproducible).
    59	
    60	    Returns:
    61	        ``(ci_lower, ci_upper)`` tuple of floats at the ``(1-alpha) * 100%``
    62	        percentile level.
    63	
    64	    Raises:
    65	        ValueError: When ``samples`` is empty, ``alpha`` is out of range, or
    66	            ``n_resamples`` is too small.
    67	    """
    68	    n = len(samples)
    69	    if n < 1:
    70	        raise ValueError(f"samples must be non-empty; got n={n}")
    71	    if not (0.0 < alpha < 1.0):
    72	        raise ValueError(f"alpha must be in (0.0, 1.0); got {alpha!r}")
    73	    if n_resamples < 100:
    74	        raise ValueError(f"n_resamples must be >= 100; got {n_resamples!r}")
    75	
    76	    rng = _np.random.default_rng(seed)
    77	    sample_array = _np.asarray(samples, dtype=float)
    78	    # Draw n_resamples bootstrap samples of size n with replacement.
    79	    indices = rng.integers(low=0, high=n, size=(n_resamples, n))
    80	    resampled = sample_array[indices]
    81	    # Apply the statistic to each row. Use a Python loop since `statistic`
    82	    # is an arbitrary Callable[[list[float]], float] (not necessarily
    83	    # numpy-aware).
    84	    stats_values = _np.empty(n_resamples, dtype=float)
    85	    for i in range(n_resamples):
    86	        stats_values[i] = float(statistic(resampled[i].tolist()))
    87	    lo = float(_np.percentile(stats_values, 100.0 * (alpha / 2.0)))
    88	    hi = float(_np.percentile(stats_values, 100.0 * (1.0 - alpha / 2.0)))
    89	    return (lo, hi)

exec
/bin/bash -lc "nl -ba mypy.ini | sed -n '45,80p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
    45	ignore_missing_imports = True
    46	
    47	# Story 10.1: `claude-agent-sdk` PyPI package is an optional extra under
    48	# `[claude-sdk]`. Adapter at `coding_agent/claude_agent_sdk.py` lazy-imports
    49	# it; type stubs aren't shipped (pre-1.0 SDK). Allow missing imports so
    50	# default mypy runs pass without the extra installed.
    51	[mypy-claude_agent_sdk.*]
    52	ignore_missing_imports = True
    53	
    54	# Story 10.2: `openai-agents` PyPI package imports as `agents` (NOT
    55	# `openai_agents`). Optional extra under `[openai-agents]`. Same rationale
    56	# as the claude-agent-sdk allowlist above.
    57	[mypy-agents.*]
    58	ignore_missing_imports = True
    59	
    60	# Story 13.1: scipy + numpy power the Phase-2 `[agenteval-advanced]` stats
    61	# keywords (Mann-Whitney U, Cliff Delta, Bootstrap CI). scipy has no
    62	# first-party stubs in the project's Python pin range; `scipy-stubs`
    63	# exists but isn't worth a CI hard-dep just for stub coverage. Same
    64	# rationale as the other ignore-missing-imports allowlists above.
    65	[mypy-scipy.*]
    66	ignore_missing_imports = True

exec
/bin/bash -lc "nl -ba tests/unit/stats/test_advanced.py | sed -n '1,260p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Unit tests for the Phase-2 `[agenteval-advanced]` stats keywords (Story 13.1).
    16	
    17	Math correctness tested against scipy reference implementations
    18	(``scipy.stats.mannwhitneyu`` + ``scipy.stats.bootstrap``). Cliff's delta
    19	has no direct scipy equivalent — verified against the closed-form
    20	``δ = (#a>b - #a<b) / (n_a * n_b)`` directly.
    21	
    22	ImportError gate (Phase-1 baseline compat without the extra) exercised via
    23	monkeypatch + module reload so the test runs in both the WITH-extras and
    24	WITHOUT-extras CI environments.
    25	"""
    26	
    27	from __future__ import annotations
    28	
    29	import statistics
    30	
    31	import pytest
    32	
    33	from AgentEval.stats.types import KeywordRun, MannWhitneyResult
    34	
    35	# Phase-2 modules require scipy + numpy. Skip the math + happy-path tests when
    36	# the extra is not installed (ImportError-gate tests still run via monkeypatch).
    37	_scipy = pytest.importorskip("scipy")
    38	_scipy_stats = pytest.importorskip("scipy.stats")
    39	_numpy = pytest.importorskip("numpy")
    40	
    41	from AgentEval.stats import bootstrap as _bootstrap  # noqa: E402
    42	from AgentEval.stats import cliffs_delta as _cliffs_delta  # noqa: E402
    43	from AgentEval.stats import mannwhitney as _mannwhitney  # noqa: E402
    44	from AgentEval.stats.library import StatsLibrary  # noqa: E402
    45	
    46	
    47	def _make_run(value: float, *, trial_index: int = 0) -> KeywordRun:
    48	    """Build a minimal KeywordRun whose `latency_seconds` carries the test value."""
    49	    return KeywordRun(
    50	        trial_index=trial_index,
    51	        test_id=f"test::trial-{trial_index}",
    52	        keyword_name="fake",
    53	        result=None,
    54	        error=None,
    55	        completeness="complete",
    56	        latency_seconds=value,
    57	        seed=None,
    58	    )
    59	
    60	
    61	# --------------------------------------------------------------------------- #
    62	# MannWhitneyResult dataclass validation (3 tests)                            #
    63	# --------------------------------------------------------------------------- #
    64	
    65	
    66	def test_mannwhitney_result_in_range_fields_accepted() -> None:
    67	    """Valid fields construct without raising."""
    68	    r = MannWhitneyResult(u_statistic=10.0, p_value=0.05, effect_size_r=0.3, n_a=5, n_b=5)
    69	    assert r.u_statistic == 10.0
    70	    assert r.p_value == 0.05
    71	    assert r.effect_size_r == 0.3
    72	
    73	
    74	def test_mannwhitney_result_effect_size_out_of_range_raises() -> None:
    75	    """effect_size_r outside [-1.0, 1.0] raises ValueError."""
    76	    with pytest.raises(ValueError, match="effect_size_r"):
    77	        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=1.5, n_a=5, n_b=5)
    78	    with pytest.raises(ValueError, match="effect_size_r"):
    79	        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=-1.5, n_a=5, n_b=5)
    80	
    81	
    82	def test_mannwhitney_result_p_value_out_of_range_raises() -> None:
    83	    """p_value outside [0.0, 1.0] raises ValueError."""
    84	    with pytest.raises(ValueError, match="p_value"):
    85	        MannWhitneyResult(u_statistic=0.0, p_value=1.1, effect_size_r=0.0, n_a=5, n_b=5)
    86	
    87	
    88	def test_mannwhitney_result_n_below_one_raises() -> None:
    89	    """n_a or n_b < 1 raises ValueError."""
    90	    with pytest.raises(ValueError, match="n_a"):
    91	        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=0, n_b=5)
    92	    with pytest.raises(ValueError, match="n_b"):
    93	        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=0)
    94	
    95	
    96	def test_mannwhitney_result_is_frozen() -> None:
    97	    """Mutation raises FrozenInstanceError (dataclass(frozen=True))."""
    98	    r = MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=5)
    99	    with pytest.raises(AttributeError):
   100	        r.u_statistic = 99.0  # type: ignore[misc]
   101	
   102	
   103	# --------------------------------------------------------------------------- #
   104	# Mann-Whitney U math (4 tests)                                               #
   105	# --------------------------------------------------------------------------- #
   106	
   107	
   108	def test_mannwhitney_identical_samples_p_value_near_one() -> None:
   109	    """Identical samples → high p-value (cannot reject null) + effect_size_r≈0."""
   110	    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
   111	    r = _mannwhitney.compute_mann_whitney_u(samples, samples)
   112	    assert r.p_value > 0.8
   113	    assert abs(r.effect_size_r) < 0.01
   114	    assert r.n_a == 5
   115	    assert r.n_b == 5
   116	
   117	
   118	def test_mannwhitney_clearly_separated_samples_p_value_small() -> None:
   119	    """Clearly disjoint samples → p < 0.05 + |effect_size_r| near 1."""
   120	    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
   121	    samples_b = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
   122	    r = _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)
   123	    assert r.p_value < 0.05
   124	    # samples_a < samples_b → r near -1 (positive r means a tends to be larger)
   125	    assert r.effect_size_r < -0.9
   126	
   127	
   128	def test_mannwhitney_minimal_samples_n_equals_one() -> None:
   129	    """n_a=1 or n_b=1 still computes (scipy permits)."""
   130	    r = _mannwhitney.compute_mann_whitney_u([1.0], [5.0, 6.0, 7.0])
   131	    assert r.n_a == 1
   132	    assert r.n_b == 3
   133	    assert 0.0 <= r.p_value <= 1.0
   134	
   135	
   136	def test_mannwhitney_empty_samples_raises() -> None:
   137	    """Empty samples list raises ValueError."""
   138	    with pytest.raises(ValueError, match="samples_a"):
   139	        _mannwhitney.compute_mann_whitney_u([], [1.0, 2.0])
   140	    with pytest.raises(ValueError, match="samples_b"):
   141	        _mannwhitney.compute_mann_whitney_u([1.0, 2.0], [])
   142	
   143	
   144	# --------------------------------------------------------------------------- #
   145	# Mann-Whitney U vs scipy reference (3 tests)                                 #
   146	# --------------------------------------------------------------------------- #
   147	
   148	
   149	@pytest.mark.parametrize("seed,n", [(42, 10), (123, 30), (7, 100)])
   150	def test_mannwhitney_matches_scipy_reference(seed: int, n: int) -> None:
   151	    """3 seeded sample pairs (n=10/30/100) match scipy.stats.mannwhitneyu within 1e-9."""
   152	    rng = _numpy.random.default_rng(seed)
   153	    a = rng.normal(loc=0.0, scale=1.0, size=n).tolist()
   154	    b = rng.normal(loc=0.5, scale=1.0, size=n).tolist()
   155	
   156	    ours = _mannwhitney.compute_mann_whitney_u(a, b)
   157	    ref = _scipy_stats.mannwhitneyu(a, b, alternative="two-sided", use_continuity=False)
   158	
   159	    u1 = float(ref.statistic)
   160	    u2 = float(n * n - u1)
   161	    expected_u_smaller = min(u1, u2)
   162	
   163	    assert abs(ours.u_statistic - expected_u_smaller) < 1e-9
   164	    assert abs(ours.p_value - float(ref.pvalue)) < 1e-9
   165	
   166	
   167	# --------------------------------------------------------------------------- #
   168	# Cliff Delta math (5 tests)                                                  #
   169	# --------------------------------------------------------------------------- #
   170	
   171	
   172	def test_cliff_delta_identical_samples_near_zero() -> None:
   173	    """Identical samples → δ ≈ 0 (all comparisons are ties or symmetric)."""
   174	    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
   175	    delta = _cliffs_delta.compute_cliff_delta(samples, samples)
   176	    assert abs(delta) < 0.01
   177	
   178	
   179	def test_cliff_delta_strict_dominance_a_over_b_equals_one() -> None:
   180	    """All samples_a > all samples_b → δ = 1.0."""
   181	    delta = _cliffs_delta.compute_cliff_delta([10.0, 20.0, 30.0], [1.0, 2.0, 3.0])
   182	    assert delta == 1.0
   183	
   184	
   185	def test_cliff_delta_reverse_dominance_equals_neg_one() -> None:
   186	    """All samples_a < all samples_b → δ = -1.0."""
   187	    delta = _cliffs_delta.compute_cliff_delta([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
   188	    assert delta == -1.0
   189	
   190	
   191	def test_cliff_delta_small_overlap_small_magnitude() -> None:
   192	    """Substantial overlap → |δ| < 0.5."""
   193	    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
   194	    samples_b = [2.0, 3.0, 4.0, 5.0, 6.0]
   195	    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
   196	    assert abs(delta) < 0.5
   197	
   198	
   199	def test_cliff_delta_large_separation_large_magnitude() -> None:
   200	    """Mostly-disjoint samples → |δ| > 0.7."""
   201	    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
   202	    samples_b = [6.0, 7.0, 8.0, 9.0, 10.0]
   203	    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
   204	    assert abs(delta) > 0.9
   205	
   206	
   207	# --------------------------------------------------------------------------- #
   208	# Bootstrap CI math (5 tests)                                                 #
   209	# --------------------------------------------------------------------------- #
   210	
   211	
   212	def test_bootstrap_ci_known_distribution_brackets_truth() -> None:
   213	    """Uniform [0,1] n=1000 mean → CI brackets 0.5."""
   214	    rng = _numpy.random.default_rng(42)
   215	    samples = rng.uniform(0.0, 1.0, size=1000).tolist()
   216	    lo, hi = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42)
   217	    assert lo <= 0.5 <= hi
   218	    # CI is reasonably tight for n=1000 (theoretical half-width ≈ 1.96 * 0.289/sqrt(1000) ≈ 0.018).
   219	    assert (hi - lo) < 0.1
   220	
   221	
   222	def test_bootstrap_ci_seed_reproducibility() -> None:
   223	    """seed=42 → identical CI across 2 invocations."""
   224	    samples = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
   225	    lo1, hi1 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
   226	    lo2, hi2 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
   227	    assert lo1 == lo2
   228	    assert hi1 == hi2
   229	
   230	
   231	def test_bootstrap_ci_alpha_0_01_wider_than_0_05() -> None:
   232	    """alpha=0.01 (99% CI) wider than alpha=0.05 (95% CI)."""
   233	    rng = _numpy.random.default_rng(42)
   234	    samples = rng.normal(loc=10.0, scale=2.0, size=100).tolist()
   235	    lo95, hi95 = _bootstrap.compute_bootstrap_ci(
   236	        samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42
   237	    )
   238	    lo99, hi99 = _bootstrap.compute_bootstrap_ci(
   239	        samples, statistic=statistics.mean, alpha=0.01, n_resamples=1000, seed=42
   240	    )
   241	    assert (hi99 - lo99) > (hi95 - lo95)
   242	
   243	
   244	def test_bootstrap_ci_invalid_alpha_raises() -> None:
   245	    """alpha outside (0,1) raises ValueError."""
   246	    with pytest.raises(ValueError, match="alpha"):
   247	        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 0.0, 1000, 42)
   248	    with pytest.raises(ValueError, match="alpha"):
   249	        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 1.5, 1000, 42)
   250	
   251	
   252	def test_bootstrap_ci_empty_samples_raises() -> None:
   253	    """Empty samples list raises ValueError."""
   254	    with pytest.raises(ValueError, match="samples"):
   255	        _bootstrap.compute_bootstrap_ci([], statistics.mean, 0.05, 1000, 42)
   256	
   257	
   258	def test_bootstrap_ci_too_few_resamples_raises() -> None:
   259	    """n_resamples < 100 raises ValueError."""
   260	    with pytest.raises(ValueError, match="n_resamples"):

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/types.py | sed -n '1,120p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Statistical primitives — public types (Story 6.3 AC-6.3.2).
    16	
    17	`KeywordRun` is the PRD FR26 verbatim return-type element for
    18	`Stat.Run N Times` (per `docs/contracts/determinism-contract.md:55`
    19	ratified by Story 1b.6 Codex STAR catch: `KeywordRun`, NOT
    20	`AgentRunResult`). Each trial of a Tier-3 fan-out produces one
    21	`KeywordRun`; `Stat.Get Pass At K` consumes `list[KeywordRun]` and
    22	applies a predicate to compute the unbiased Pass@k estimate per FR27.
    23	"""
    24	
    25	from __future__ import annotations
    26	
    27	from dataclasses import dataclass
    28	from typing import Any
    29	
    30	
    31	@dataclass(frozen=True, slots=True)
    32	class MannWhitneyResult:
    33	    """Mann-Whitney U test result (PRD FR29a; Story 13.1).
    34	
    35	    Returned by `Stat.Mann Whitney U` (Phase-2, behind the
    36	    `[agenteval-advanced]` extra). Reports the test statistic, two-sided
    37	    p-value, rank-biserial effect size, and sample sizes.
    38	
    39	    Fields:
    40	        u_statistic: The smaller of U1, U2 (matches
    41	            ``scipy.stats.mannwhitneyu`` default — "alternative='two-sided'",
    42	            "use_continuity=False").
    43	        p_value: Two-sided p-value.
    44	        effect_size_r: Signed rank-biserial correlation
    45	            ``r = 2 * U1 / (n_a * n_b) - 1`` where U1 is the Mann-Whitney
    46	            U for the FIRST sample. Range: ``[-1.0, 1.0]``. Sign convention:
    47	            positive r → samples_a tends to be larger; negative r → samples_b
    48	            tends to be larger; r ≈ 0 → substantial overlap. Matches Cliff's
    49	            delta sign convention shipped by ``Stat.Cliff Delta`` (FR29b).
    50	        n_a: Number of samples in the first group (after predicate extraction).
    51	        n_b: Number of samples in the second group (after predicate extraction).
    52	
    53	    Validation (``__post_init__``): ``n_a >= 1``, ``n_b >= 1``,
    54	    ``-1.0 <= effect_size_r <= 1.0``, ``0.0 <= p_value <= 1.0`` —
    55	    all raise ``ValueError`` on violation.
    56	    """
    57	
    58	    u_statistic: float
    59	    p_value: float
    60	    effect_size_r: float
    61	    n_a: int
    62	    n_b: int
    63	
    64	    def __post_init__(self) -> None:
    65	        if self.n_a < 1:
    66	            raise ValueError(f"n_a must be >= 1; got {self.n_a!r}")
    67	        if self.n_b < 1:
    68	            raise ValueError(f"n_b must be >= 1; got {self.n_b!r}")
    69	        if not (-1.0 <= self.effect_size_r <= 1.0):
    70	            raise ValueError(f"effect_size_r must be in [-1.0, 1.0]; got {self.effect_size_r!r}")
    71	        if not (0.0 <= self.p_value <= 1.0):
    72	            raise ValueError(f"p_value must be in [0.0, 1.0]; got {self.p_value!r}")
    73	
    74	
    75	@dataclass(frozen=True, slots=True)
    76	class KeywordRun:
    77	    """Single-trial result from `Stat.Run N Times` (PRD FR26).
    78	
    79	    Fields:
    80	        trial_index: 0-indexed trial number within the parent `Stat.Run N Times` call.
    81	        test_id: ContextVar-bound sub-scope id, formatted as
    82	            `{parent_test_id}::trial-{trial_index}` (per Story 4.3 ContextVar precedent).
    83	        keyword_name: RF name of the wrapped keyword (e.g., `Send Prompt`).
    84	        result: Raw return value from the wrapped keyword (commonly an
    85	            `AgentRunResult`, but any return type is preserved).
    86	        error: Exception instance if the trial raised; `None` on success.
    87	            Trial-level errors bubble up to the caller; this field is for
    88	            post-mortem analysis when callers wrap in `Run Keyword And Ignore Error`.
    89	        completeness: Mirrors `result.metadata.completeness` if `result` is an
    90	            `AgentRunResult`; otherwise `"n/a"`. Operator-facing pass-predicate
    91	            convenience (default predicate matches `completeness == "complete"`
    92	            — amended 2026-05-26 per kilo/minimax cross-LLM review FINDING-1;
    93	            pre-Story-6.4 docstring incorrectly cited `"full"`, but the
    94	            `AgentRunMetadata._VALID_COMPLETENESS` literal set is
    95	            `{"complete", "truncated", "partial"}` and Story 6.4 fix-NOW at
    96	            `stats/_internal.py:250` flipped the default predicate to match).
    97	        latency_seconds: Wall-clock duration for this single trial.
    98	        seed: The `int` seed value forwarded to the trial (or `None` if
    99	            OS-entropy seeding was requested).
   100	    """
   101	
   102	    trial_index: int
   103	    test_id: str
   104	    keyword_name: str
   105	    result: Any
   106	    error: BaseException | None
   107	    completeness: str
   108	    latency_seconds: float
   109	    seed: int | None

exec
/bin/bash -lc "nl -ba docs/contracts/stability-surface.md | sed -n '124,136p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   124	
   125	### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)
   126	
   127	Per Story 13.1 (PRD FR29a/b/c) — Phase-2 advanced statistical primitives gated behind the `[agenteval-advanced]` optional extra (scipy + numpy):
   128	
   129	- `Stat.Mann Whitney U` RF keyword + Python method `StatsLibrary.mann_whitney_u` — `provisional` label. Returns `MannWhitneyResult` (two-sided test only — `alternative="greater"`/`"less"` variants Phase-2 / DF-13.1-S1). Signature stable; `effect_size_r` computation is signed rank-biserial (`r = 2 * U1 / (n_a * n_b) - 1`) matching `Stat.Cliff Delta`'s sign convention.
   130	- `Stat.Cliff Delta` RF keyword + Python method `StatsLibrary.cliff_delta` — `provisional` label. Returns scalar `float ∈ [-1.0, 1.0]` per PRD FR29b (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent).
   131	- `Stat.Bootstrap Confidence Interval` RF keyword + Python method `StatsLibrary.bootstrap_ci` — `provisional` label. Returns `tuple[float, float]` (lo, hi) percentile bootstrap CI. Percentile method only (BCa + BC-corrected variants Phase-2 / DF-13.1-S2). Default `n_resamples=10_000` is `provisional`. `seed` parameter enables reproducibility.
   132	- `AgentEval.stats.types.MannWhitneyResult` frozen dataclass — `provisional` label. 5 fields: `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`. `__post_init__` validators (`n_a/n_b >= 1`, `effect_size_r ∈ [-1, 1]`, `p_value ∈ [0, 1]`) are `stable`. Phase-2 may extend with `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` per DF-13.1-S3.
   133	- `[agenteval-advanced]` optional-dependencies extra (`scipy>=1.11,<2.0` + `numpy>=1.26,<3.0`) — extra NAME (`agenteval-advanced`) is `stable`; the version pins are `provisional` (floors may shift as scipy/numpy 2.x baselines stabilize). The 3 keywords raise `ImportError` with the verbatim message `"Stat.<Keyword>: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"` when invoked without the extra — message format is `stable`.
   134	
   135	### Sandbox Protocol Surface
   136	

codex
The main implementation is loaded. I’ve already found one load-bearing test-story mismatch in the import-gate coverage, and I’m validating whether the statistical claims themselves hold empirically before I write findings.
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.library import StatsLibrary
from AgentEval.stats.types import KeywordRun

def run(v):
    return KeywordRun(trial_index=0,test_id='t',keyword_name='k',result=None,error=None,completeness='complete',latency_seconds=v,seed=None)
lib=StatsLibrary()
res=lib.compute_bootstrap_ci([run(1.0), run(2.0), run(3.0)], predicate=lambda r:r.latency_seconds, seed=42, n_resamples=200)
print(res)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.mannwhitney import compute_mann_whitney_u
import scipy.stats as st

a=list(range(1,9))
b=list(range(100,108))
r=compute_mann_whitney_u(a,b)
ref=st.mannwhitneyu(a,b,alternative='two-sided',use_continuity=False)
print('u1', float(ref.statistic))
print('u2', len(a)*len(b)-float(ref.statistic))
print('u_smaller', r.u_statistic)
print('p', r.p_value)
print('r', r.effect_size_r)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.library import StatsLibrary
from AgentEval.stats.types import KeywordRun

def run(v):
    return KeywordRun(trial_index=0,test_id='t',keyword_name='k',result=None,error=None,completeness='complete',latency_seconds=v,seed=None)
lib=StatsLibrary()
# mixed list first float then KeywordRun
lo_hi = lib.compute_bootstrap_ci([1.0, 2.0, run(100.0)], seed=42, n_resamples=200)
print(lo_hi)
# mixed list first KeywordRun then float
lo_hi2 = lib.compute_bootstrap_ci([run(1.0), 2.0, 3.0], predicate=lambda r:r.latency_seconds, seed=42, n_resamples=200)
print(lo_hi2)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.bootstrap import compute_bootstrap_ci
import statistics
samples=[1.0,2.0,3.0,4.0,5.0]*20
print(compute_bootstrap_ci(samples, statistics.mean, 0.05, 500, 42))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 795ms:
(1.0, 2.6750000000000016)

 succeeded in 824ms:
(1.0, 2.0)
(1.0, 1.0)

 succeeded in 832ms:
(2.70475, 3.2552499999999998)

 succeeded in 1905ms:
u1 0.0
u2 64.0
u_smaller 0.0
p 0.0001554001554001554
r -1.0

codex
One of the key drifts is now clear: the implementation intentionally normalizes `u_statistic` to `min(U1, U2)`, but several docs still claim that this “matches scipy default,” which is false because SciPy returns `U1` for the first sample. I’m running one more empirical case where `U1 != min(U1, U2)` so the mismatch is explicit rather than theoretical.
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.mannwhitney import compute_mann_whitney_u
import scipy.stats as st

a=list(range(100,108))
b=list(range(1,9))
r=compute_mann_whitney_u(a,b)
ref=st.mannwhitneyu(a,b,alternative='two-sided',use_continuity=False)
print('u1', float(ref.statistic))
print('u2', len(a)*len(b)-float(ref.statistic))
print('returned', r.u_statistic)
print('effect', r.effect_size_r)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
import scipy, numpy
print('scipy', scipy.__version__)
print('numpy', numpy.__version__)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.stats.bootstrap import compute_bootstrap_ci
import numpy as np, statistics
from scipy.stats import bootstrap
samples=np.array([1.0,2.0,3.0,4.0,5.0]*20)
ours=compute_bootstrap_ci(samples.tolist(), statistics.mean, 0.05, 500, 42)
ref=bootstrap((samples,), np.mean, n_resamples=500, confidence_level=0.95, method='percentile', random_state=42)
print('ours', ours)
print('scipy', (float(ref.confidence_interval.low), float(ref.confidence_interval.high)))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 264ms:
scipy 1.17.1
numpy 2.4.6

 succeeded in 1895ms:
u1 64.0
u2 0.0
returned 0.0
effect 1.0

 succeeded in 1861ms:
ours (2.70475, 3.2552499999999998)
scipy (2.7195, 3.24525)

codex
The bootstrap path is weaker than the story says. The source claims SciPy is the reference, but the tests never assert against `scipy.stats.bootstrap`, and the local implementation already gives different bounds than SciPy for the same sample and seed under the locked versions. I’m checking whether that’s just `random_state` semantics or a deeper algorithm mismatch.
exec
/bin/bash -lc "python - <<'PY'
import inspect
from scipy.stats import bootstrap
sig = inspect.signature(bootstrap)
print(sig)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
import numpy as np
from scipy.stats import bootstrap
samples=np.array([1.0,2.0,3.0,4.0,5.0]*20)
for label, kwargs in [
    ('random_state=42', {'random_state':42}),
    ('rng=default_rng(42)', {'rng':np.random.default_rng(42)}),
    ('random_state=default_rng(42)', {'random_state':np.random.default_rng(42)}),
]:
    try:
        ref=bootstrap((samples,), np.mean, n_resamples=500, confidence_level=0.95, method='percentile', **kwargs)
        print(label, float(ref.confidence_interval.low), float(ref.confidence_interval.high))
    except Exception as e:
        print(label, type(e).__name__, e)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 1528ms:
(data, statistic, *, n_resamples=9999, batch=None, vectorized=None, paired=False, axis=0, confidence_level=0.95, alternative='two-sided', method='BCa', bootstrap_result=None, rng=None, random_state=None)

 succeeded in 1541ms:
random_state=42 2.7195 3.24525
rng=default_rng(42) 2.70475 3.2552499999999998
random_state=default_rng(42) 2.70475 3.2552499999999998

codex
I’ve got enough context to isolate the real issues. I’m pulling the exact line numbers from the story artifact and related contract docs now so the findings tie the false claims back to the concrete source that disproves them.
exec
/bin/bash -lc "nl -ba _bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md | sed -n '120,230p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   120	`uv lock` + `uv sync --extra agenteval-advanced` must succeed (no resolver conflict with the existing hard deps). The base install (`uv sync` without `--extra agenteval-advanced`) MUST NOT pull scipy/numpy.
   121	
   122	### AC-13.1.4 — Module file homes per architecture L1306-1308
   123	
   124	Each of the 3 new modules is a thin pure-helper module exposing `compute_<name>(...)` functions. The `StatsLibrary` keyword methods delegate to these helpers.
   125	
   126	**`src/AgentEval/stats/mannwhitney.py`** (NEW):
   127	- `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` — pure function using `scipy.stats.mannwhitneyu` for U and p; computes `effect_size_r` locally.
   128	- Module-level `try: import scipy.stats as _scipy_stats / except ImportError: _scipy_stats = None`; the `compute_*` function raises if `_scipy_stats is None`.
   129	
   130	**`src/AgentEval/stats/cliffs_delta.py`** (NEW):
   131	- `compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float` — pure-Python brute-force formula; no scipy/numpy strictly needed BUT module-level `try: import numpy / except ImportError: ...` still gates per the unified `[agenteval-advanced]` extra contract (consistency with the other 2 modules).
   132	
   133	**`src/AgentEval/stats/bootstrap.py`** (NEW):
   134	- `compute_bootstrap_ci(samples: list[float], statistic: Callable[[list[float]], float], alpha: float, n_resamples: int, seed: int | None) -> tuple[float, float]` — uses `numpy.random.Generator(seed)` for reproducibility; percentile method.
   135	- Module-level scipy + numpy ImportError gate per the unified contract.
   136	
   137	Each module's docstring documents the PRD FR (FR29a/b/c) + the Phase-1.5 carry-over (DF-13.1-S1/S2/S3) + the math reference.
   138	
   139	### AC-13.1.5 — `_ADVANCED_AVAILABLE` import gate at `stats/library.py`
   140	
   141	`src/AgentEval/stats/library.py` adds at module scope (near the existing `_BROWSER_STYLE_MIGRATED = True` marker):
   142	
   143	```python
   144	try:  # Story 13.1 — Phase-2 [agenteval-advanced] extra gate.
   145	    import scipy  # noqa: F401  # scipy + numpy required for FR29a/b/c.
   146	    import numpy  # noqa: F401
   147	    _ADVANCED_AVAILABLE = True
   148	    _ADVANCED_IMPORT_ERROR: ImportError | None = None
   149	except ImportError as _e:  # pragma: no cover  -- exercised via monkeypatch in tests
   150	    _ADVANCED_AVAILABLE = False
   151	    _ADVANCED_IMPORT_ERROR = _e
   152	```
   153	
   154	Each Phase-2 keyword method's first line:
   155	
   156	```python
   157	if not _ADVANCED_AVAILABLE:
   158	    raise ImportError(
   159	        f"Stat.{<keyword_name>}: scipy + numpy required. "
   160	        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
   161	    ) from _ADVANCED_IMPORT_ERROR
   162	```
   163	
   164	The `StatsLibrary` class itself MUST remain importable without scipy/numpy installed — verified by `tests/unit/stats/test_library.py` continuing to pass in the base environment.
   165	
   166	### AC-13.1.6 — Unit tests at `tests/unit/stats/test_advanced.py` (≥20 tests)
   167	
   168	**`tests/unit/stats/test_advanced.py`** (NEW; gated by `pytest.importorskip("scipy")` for the WITH-extra tests):
   169	
   170	- **Mann-Whitney U math (4 tests)**: identical samples → p≈1.0 + effect_size_r≈0; clearly separated samples → p < 0.05 + effect_size_r near ±1; n_a=1 OR n_b=1 edge case (scipy permits but warns); n_a=0 OR n_b=0 → ValueError.
   171	- **Mann-Whitney U vs scipy reference (3 tests)**: 3 randomly-seeded sample pairs (n=10/30/100); assert `u_statistic` matches `scipy.stats.mannwhitneyu(..., alternative='two-sided', use_continuity=False).statistic` to within 1e-9; assert `p_value` matches to within 1e-9.
   172	- **Cliff Delta math (5 tests)**: identical samples → δ ≈ 0; strict-dominance (all a > all b) → δ = 1.0; reverse-dominance → δ = -1.0; partial-overlap small → |δ| < 0.5; partial-overlap large → |δ| > 0.7.
   173	- **Bootstrap CI math (5 tests)**: known-distribution samples (uniform [0,1] n=1000 mean) → CI brackets 0.5 with 95% confidence (seed-reproducible verification); `seed=42` reproducibility (2 invocations identical); `n_resamples=100` vs `10_000` consistency direction (wider with fewer resamples); alpha=0.01 wider than alpha=0.05; empty `samples` → ValueError.
   174	- **`MannWhitneyResult` dataclass (3 tests)**: in-range fields accepted; `effect_size_r` out of [-1, 1] → ValueError; `p_value` out of [0, 1] → ValueError; frozen (mutation raises).
   175	- **Predicate value-extraction (2 tests)**: `predicate=lambda r: r.latency_seconds` extracts correctly from `KeywordRun`; `predicate=None` on Mann-Whitney U / Cliff Delta raises `ValueError("predicate is required...")`.
   176	- **ImportError gate WITHOUT extras (3 tests)**: `monkeypatch.setitem(sys.modules, "scipy", None)` + reload `stats.library` → `_ADVANCED_AVAILABLE = False`; calling `Stat.Mann Whitney U` raises `ImportError` with `"agenteval-advanced"` in the message; calling `Stat.Cliff Delta` likewise; calling `Stat.Bootstrap Confidence Interval` likewise. Use `monkeypatch.setitem(sys.modules, "scipy", None)` to simulate missing scipy without uninstalling.
   177	
   178	Plus integration smoke at `tests/integration/stats/test_advanced_keywords.py`: run all 3 keywords through the RF library entry point (via `Library    AgentEval`) with synthetic `KeywordRun` lists; assert returns are well-typed. Single happy-path per keyword (3 tests).
   179	
   180	### AC-13.1.7 — `docs/contracts/stability-surface.md` registry
   181	
   182	Append a new subsection `### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)`:
   183	
   184	- `Stat.Mann Whitney U` RF keyword + Python method `StatsLibrary.mann_whitney_u` — `provisional` label. Signature stable; `effect_size_r` computation may move to Phase-2 if scipy adds a native rank-biserial accessor.
   185	- `Stat.Cliff Delta` RF keyword + Python method `StatsLibrary.cliff_delta` — `provisional` label.
   186	- `Stat.Bootstrap Confidence Interval` RF keyword + Python method `StatsLibrary.bootstrap_ci` — `provisional` label. `n_resamples` default (10_000) is `provisional`; may tune in Phase-2.
   187	- `MannWhitneyResult` dataclass + 5 fields — `provisional` label. Phase-2 may extend with `effect_size_interpretation` (DF-13.1-S3).
   188	- `[agenteval-advanced]` extra group + `scipy>=1.11,<2.0` + `numpy>=1.26,<3.0` pin — `stable` (the extra name + pin discipline) / `provisional` (the specific pin floors may shift).
   189	
   190	### AC-13.1.8 — `docs/contracts/determinism-contract.md` amendment
   191	
   192	Append to the existing L29 entry: "(`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` shipped Story 13.1 Phase-2 under `[agenteval-advanced]` extra)." No new Tier classification — Tier-1 per D-9 + Story 6.3 precedent.
   193	
   194	### AC-13.1.9 — `docs/adr/ADR-001-architectural-influences-catalog.md` drift fix (D-2)
   195	
   196	L70 amended: `agenteval[advanced]` → `agenteval[agenteval-advanced]` (fix-the-losing-source-NOW). Same-commit.
   197	
   198	### AC-13.1.10 — Epic.md drift fix (D-1)
   199	
   200	L2151 amended in the same commit:
   201	- Old: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `n_a`, `n_b`; analogous for `Cliff Delta` (effect size) and `Bootstrap CI` (confidence interval on any predicate)."
   202	- New: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29c (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent)."
   203	
   204	### AC-13.1.11 — Phase-1.5 carry-over catalog amendment (UPSTREAM `feedback_carry_over_catalog_gate`, 32nd consecutive)
   205	
   206	`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` get 3 new rows BEFORE invoking `/bmad-code-review`:
   207	
   208	- **C83** `DF-13.1-S1` — Phase-2: `Stat.Mann Whitney U` `alternative="greater" / "less"` one-sided variants.
   209	- **C84** `DF-13.1-S2` — Phase-2: Bootstrap CI methods beyond percentile (BCa, BC-corrected).
   210	- **C85** `DF-13.1-S3` — Phase-2: `MannWhitneyResult.effect_size_interpretation` field per Cohen's conventions.
   211	
   212	Each row follows the existing carry-over table column shape (ID / Description / Source / Priority / Effort / Owner / Acceptance criteria).
   213	
   214	### AC-13.1.12 — All-gates pass
   215	
   216	- `uv lock` + `uv sync` (base) succeeds without scipy/numpy in the resolved environment (base install unchanged).
   217	- `uv sync --extra agenteval-advanced` succeeds (scipy + numpy resolve cleanly).
   218	- `uv run pytest tests/` reports approximately **1605 + 23 = 1628 passed + 10 skipped** in the base env (the WITHOUT-extras ImportError tests use monkeypatch, so they run in base env; the WITH-extras math tests use `pytest.importorskip("scipy")` and SKIP in base env — count as additional skips).
   219	- `uv run pytest tests/ --extras agenteval-advanced` (or `uv sync --extra agenteval-advanced` then re-run) reports **all 23 new tests passing** (WITH-extras math tests now run).
   220	- `uv run ruff check src/ tests/` clean.
   221	- `uv run ruff format --check src/ tests/` clean.
   222	- `uv run mypy src/` clean (scoped to src; mypy on the new modules + library.py extension).
   223	- libdoc regeneration (per Epic 12 retro precedent): `uv run libdoc src/AgentEval/stats/library.py docs/keywords/stats.html` reflects the 3 new keywords with their Browser-Library-style docstrings.
   224	
   225	### AC-13.1.13 — Sprint-status
   226	
   227	`_bmad-output/implementation-artifacts/sprint-status.yaml` flips:
   228	- `epic-13: in-progress` (first Epic 13 story; was `backlog`).
   229	- `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done`.
   230	- `last_updated: 2026-06-01`.

exec
/bin/bash -lc "nl -ba _bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md | sed -n '290,348p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   290	## Dev Agent Record
   291	
   292	### Agent Model Used
   293	
   294	claude-opus-4-7[1m]
   295	
   296	### Debug Log References
   297	
   298	None. All gates green on first full sweep.
   299	
   300	### Completion Notes List
   301	
   302	Story 13.1 dev complete — opens Epic 13 (Phase-2 advanced stats surface).
   303	
   304	- **AC-13.1.1**: 3 new `@keyword + @tier(1)`-decorated methods on `StatsLibrary` (`compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci`). Methods renamed from `mann_whitney_u` / `cliff_delta` / `bootstrap_ci` to start with `compute` per the verb-allowlist convention test (`tests/unit/conventions/test_keyword_name_idiom.py` + `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`). RF keyword names (`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval`) preserved per PRD/epic verbatim — only the internal Python method names changed.
   305	- **AC-13.1.2**: `MannWhitneyResult` frozen dataclass at `stats/types.py` with 5 fields per D-1 union resolution (`u_statistic, p_value, effect_size_r, n_a, n_b`). `__post_init__` enforces invariants per D-1 verbatim.
   306	- **AC-13.1.3**: `pyproject.toml` `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]`. `uv lock` + `uv sync` (base) + `uv sync --extra agenteval-advanced` all clean.
   307	- **AC-13.1.4**: 3 helper modules at architecture-pre-allocated paths (`stats/mannwhitney.py`, `stats/cliffs_delta.py`, `stats/bootstrap.py`). Each carries the appropriate scipy/numpy imports per the unified extras contract.
   308	- **AC-13.1.5**: `_ADVANCED_AVAILABLE` module-level gate + `_raise_advanced_extra_missing(keyword_name)` helper. `StatsLibrary` class itself remains importable WITHOUT scipy/numpy (existing 1605 tests still pass).
   309	- **AC-13.1.6**: 31 unit tests + 3 integration smoke tests at the expected paths. Math correctness for Mann-Whitney U verified against `scipy.stats.mannwhitneyu` within `1e-9` across 3 seeded sample sizes (n=10/30/100). Bootstrap CI seed-reproducibility + α=0.01-wider-than-α=0.05 invariants verified. Cliff delta covers all 4 magnitude bands.
   310	- **AC-13.1.7**: `### Stat. Advanced Surface (Phase-2)` subsection in `stability-surface.md` with 4 surface registry entries + extras-name + ImportError message format `stable`.
   311	- **AC-13.1.8**: `determinism-contract.md` L29 amended per Phase-2 ship.
   312	- **AC-13.1.9 + AC-13.1.10**: D-1 + D-2 drift fixes shipped IN THIS SAME COMMIT: `epics.md` L2151 amended (`MannWhitneyResult` field list + tuple return type for Bootstrap CI per PRD); ADR-001 L70 amended (`agenteval[advanced]` → `[agenteval-advanced]` per PRD majority).
   313	- **AC-13.1.11**: C83/C84/C85 catalogued UPSTREAM in both `phase-1-5-carry-overs.md` (total 85 items, up from 82) + `deferred-work.md` (3 new entries under new "Deferred from: story-13.1 dev" section). 32nd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use.
   314	- **AC-13.1.12**: All-gates pass. `uv run pytest tests/`: **1823 passed + 14 skipped** (was 1605+10 baseline; +218 net). ruff/format/mypy/license-headers all clean on Story 13.1's new + modified files. mypy.ini extended with `[mypy-scipy.*]` ignore-missing-imports allowlist per Story 10.1/11.x precedent.
   315	- **AC-13.1.13**: sprint-status flipped (`epic-13: in-progress`, `13-1-*: review`).
   316	
   317	### In-flight spec amendments (per `feedback_in_flight_spec_amendment`)
   318	
   319	1. **AC-13.1.1 method-name amendment:** spec originally named the Python methods `mann_whitney_u` / `cliff_delta` / `bootstrap_ci`. Convention test `test_keyword_names_start_with_allowlist_verb` (verb-allowlist gate) rejects `mann` / `cliff` / `bootstrap` as non-allowed first tokens. Amended in-flight per `feedback_in_flight_spec_amendment`: methods renamed to `compute_*` (which IS in the allowlist + matches the helper module-level function naming). RF keyword names (`Stat.Mann Whitney U` etc.) unchanged per PRD/epic — only internal Python method names changed. AC-13.1.1 task box updated to reflect this rename.
   320	
   321	2. **AC-13.1.6 ImportError test consolidation:** spec text said "3 keywords × monkeypatch" for the ImportError gate tests. Empirical finding: `sys.modules` reload via `importlib.reload` perturbs the import state across tests; running 3 separate tests left `AgentEval.stats.library` in a partial-import state between tests. Amended in-flight: ImportError gate verified via two consolidated tests — (a) `test_raise_advanced_extra_missing_helper_carries_canonical_message` directly exercises the helper to verify the spec-mandated message format; (b) `test_phase2_keywords_raise_import_error_when_extra_unavailable` monkeypatches `_ADVANCED_AVAILABLE` on the live module and exercises all 3 keyword methods. Coverage equivalent; cross-test pollution eliminated.
   322	
   323	### Sign-convention discovery (effect_size_r)
   324	
   325	Initial `effect_size_r = 1.0 - 2.0 * u1 / (n_a * n_b)` formula (Glass-Hopkins-Jackson 1996 magnitude convention with min(U)) produced WRONG sign for clearly separated samples_a < samples_b (gave +1.0 instead of -1.0). Empirical test `test_mannwhitney_clearly_separated_samples_p_value_small` caught this immediately. Fixed via the SIGNED rank-biserial convention `r = 2 * U1 / (n_a * n_b) - 1` (where U1 is the scipy default, i.e., the U-statistic for samples_a). This matches Cliff's delta sign convention shipped by `Stat.Cliff Delta` — positive r means samples_a tends to be larger; negative r means samples_b tends to be larger. Docstrings updated across types.py + library.py + mannwhitney.py.
   326	
   327	### File List
   328	
   329	**New files:**
   330	- `src/AgentEval/stats/mannwhitney.py` — Mann-Whitney U primitive (FR29a).
   331	- `src/AgentEval/stats/cliffs_delta.py` — Cliff's delta effect-size primitive (FR29b).
   332	- `src/AgentEval/stats/bootstrap.py` — Bootstrap CI primitive (FR29c).
   333	- `tests/unit/stats/test_advanced.py` — 31 unit tests.
   334	- `tests/integration/stats/__init__.py` — package marker for the new integration test dir.
   335	- `tests/integration/stats/test_advanced_keywords.py` — 3 integration smoke tests.
   336	
   337	**Modified files:**
   338	- `src/AgentEval/stats/types.py` — appended `MannWhitneyResult` frozen dataclass.
   339	- `src/AgentEval/stats/library.py` — `_ADVANCED_AVAILABLE` gate + `_raise_advanced_extra_missing` helper + 3 new `@keyword + @tier(1)`-decorated methods.
   340	- `pyproject.toml` — `agenteval-advanced` optional-dependencies entry.
   341	- `mypy.ini` — `[mypy-scipy.*] ignore_missing_imports = True` allowlist.
   342	- `docs/contracts/stability-surface.md` — new `### Stat. Advanced Surface (Phase-2 — [agenteval-advanced])` subsection.
   343	- `docs/contracts/determinism-contract.md` — L29 amended with Phase-2 stats clause.
   344	- `docs/adr/ADR-001-architectural-influences-catalog.md` — L70 `agenteval[advanced]` → `[agenteval-advanced]` (D-2 fix-the-losing-source-NOW).
   345	- `_bmad-output/planning-artifacts/epics.md` — L2151 amended per D-1 (return-type drift fix).
   346	- `docs/phase-1-5-carry-overs.md` — C83 + C84 + C85 entries + total bumped 82→85.
   347	- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.1 dev" section with 3 entries.
   348	- `_bmad-output/implementation-artifacts/sprint-status.yaml` — epic-13 → `in-progress`, Story 13.1 → `review`, `last_updated: 2026-06-01`.

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/library.py | sed -n '508,585p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   508	    @keyword(name="Stat.Bootstrap Confidence Interval")
   509	    @tier(1)
   510	    def compute_bootstrap_ci(
   511	        self,
   512	        samples: list[KeywordRun] | list[float],
   513	        statistic: Callable[[list[float]], float] | None = None,
   514	        predicate: Callable[[KeywordRun], float] | None = None,
   515	        alpha: float = 0.05,
   516	        n_resamples: int = 10_000,
   517	        seed: int | None = None,
   518	    ) -> tuple[float, float]:
   519	        """Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).
   520	
   521	        [Tier 1 — Deterministic] — when ``seed`` is given, the result is
   522	        reproducible across calls; ``seed=None`` uses OS entropy. Returns
   523	        ``(ci_lower, ci_upper)`` tuple at the ``(1 - alpha) * 100%`` percentile
   524	        level (default 95% CI).
   525	
   526	        Requires the ``[agenteval-advanced]`` optional extra.
   527	
   528	        | =Arguments= | =Description= |
   529	        | ``samples`` | Either ``list[KeywordRun]`` (then ``predicate`` extracts floats) OR ``list[float]`` (predicate ignored). |
   530	        | ``statistic`` | ``Callable[[list[float]], float]`` whose CI is computed. Default ``None`` → ``statistics.mean``. |
   531	        | ``predicate`` | Optional ``Callable[[KeywordRun], float]`` value-extractor (required when ``samples`` is ``list[KeywordRun]``). |
   532	        | ``alpha`` | Significance level; CI is at ``(1-alpha)*100%`` confidence. Must satisfy ``0.0 < alpha < 1.0``. Default ``0.05``. |
   533	        | ``n_resamples`` | Number of bootstrap resamples (with replacement). Must be ``>= 100``. Default ``10_000``. |
   534	        | ``seed`` | Optional ``int`` seed for the numpy ``Generator``; ``None`` → OS entropy. |
   535	
   536	        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
   537	        when ``samples`` is empty / ``alpha`` is out of range / ``n_resamples
   538	        < 100`` / ``predicate`` is missing for a ``list[KeywordRun]`` input.
   539	
   540	        Example:
   541	        | @{runs} =    `Stat.Run N Times`    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
   542	        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
   543	        | ${ci_lo}    ${ci_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    predicate=${cost_pred}    seed=42
   544	        | Should Be True    ${ci_lo} <= ${ci_hi}                                    # CI bounds well-ordered.
   545	        | ${median_stat} =    Evaluate    statistics.median    modules=statistics
   546	        | ${med_lo}    ${med_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    statistic=${median_stat}    predicate=${cost_pred}    seed=42
   547	
   548	        Notes:
   549	        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
   550	        - PRD FR29c ratifies the ``(lo, hi)`` tuple return type — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
   551	        - Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).
   552	        - Math reference: ``scipy.stats.bootstrap(..., method="percentile")``. The local implementation uses ``numpy.random.Generator(seed)`` for control over the random source.
   553	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   554	        if not _ADVANCED_AVAILABLE:
   555	            _raise_advanced_extra_missing("Bootstrap Confidence Interval")
   556	        import statistics as _statistics
   557	
   558	        from AgentEval.stats import bootstrap as _bootstrap
   559	
   560	        if statistic is None:
   561	            statistic = _statistics.mean
   562	        # Determine if samples are KeywordRun (need predicate) or raw floats.
   563	        if not samples:
   564	            raise ValueError("samples must be non-empty")
   565	        first = samples[0]
   566	        numeric_samples: list[float]
   567	        if isinstance(first, KeywordRun):
   568	            if predicate is None:
   569	                raise ValueError(
   570	                    "predicate is required when samples is list[KeywordRun]; "
   571	                    "pass a Callable[[KeywordRun], float] value-extractor"
   572	                )
   573	            # samples is list[KeywordRun] in this branch (per first element);
   574	            # cast manually for mypy since the union type alias loses
   575	            # element-level homogeneity guarantees.
   576	            kw_samples: list[KeywordRun] = [s for s in samples if isinstance(s, KeywordRun)]
   577	            numeric_samples = [float(predicate(r)) for r in kw_samples]
   578	        else:
   579	            float_samples: list[float] = [s for s in samples if not isinstance(s, KeywordRun)]
   580	            numeric_samples = [float(s) for s in float_samples]
   581	        return _bootstrap.compute_bootstrap_ci(
   582	            numeric_samples,
   583	            statistic,
   584	            alpha,
   585	            n_resamples,

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/mannwhitney.py | sed -n '50,95p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
    50	
    51	    Args:
    52	        samples_a: First-group numeric samples; must be non-empty.
    53	        samples_b: Second-group numeric samples; must be non-empty.
    54	
    55	    Returns:
    56	        ``MannWhitneyResult`` with ``u_statistic`` (the smaller of U1, U2 per
    57	        scipy default), two-sided ``p_value``, rank-biserial ``effect_size_r``,
    58	        and the sample sizes ``n_a`` and ``n_b``.
    59	
    60	    Raises:
    61	        ValueError: When either samples list is empty.
    62	
    63	    Notes:
    64	        - The smaller-U convention matches ``scipy.stats.mannwhitneyu(...,
    65	          alternative="two-sided", use_continuity=False)``: scipy reports
    66	          ``U1`` corresponding to the first input by default, but the
    67	          two-sided p-value is symmetric in U1/U2, so consumers can recover
    68	          U2 via ``U2 = n_a * n_b - U1``. We return the smaller of the two
    69	          to match the most commonly-cited form across literature.
    70	    """
    71	    n_a = len(samples_a)
    72	    n_b = len(samples_b)
    73	    if n_a < 1:
    74	        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    75	    if n_b < 1:
    76	        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    77	    result = _scipy_stats.mannwhitneyu(
    78	        samples_a,
    79	        samples_b,
    80	        alternative="two-sided",
    81	        use_continuity=False,
    82	    )
    83	    u1 = float(result.statistic)
    84	    u2 = float(n_a * n_b - u1)
    85	    u_smaller = min(u1, u2)
    86	    # Signed rank-biserial correlation r = 2 * U1 / (n_a * n_b) - 1. U1 is
    87	    # the count of pairs where samples_a > samples_b (with 0.5 for ties), so:
    88	    #   - U1 = 0 (samples_a strictly < samples_b) → r = -1.0
    89	    #   - U1 = n_a * n_b / 2 (no separation) → r = 0.0
    90	    #   - U1 = n_a * n_b (samples_a strictly > samples_b) → r = +1.0
    91	    # Matches Cliff's delta sign convention shipped by `Stat.Cliff Delta`.
    92	    effect_size_r = 2.0 * u1 / (n_a * n_b) - 1.0
    93	    return MannWhitneyResult(
    94	        u_statistic=u_smaller,
    95	        p_value=float(result.pvalue),

exec
/bin/bash -lc "nl -ba tests/integration/stats/test_advanced_keywords.py | sed -n '1,120p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Integration smoke tests for the Phase-2 `[agenteval-advanced]` stats keywords.
    16	
    17	Exercises the 3 Story 13.1 keywords through the public `StatsLibrary` surface
    18	that the top-level `AgentEval` library composes via `_SUB_LIBRARIES`. Verifies
    19	each keyword returns the documented type when called with synthetic
    20	`KeywordRun` inputs.
    21	"""
    22	
    23	from __future__ import annotations
    24	
    25	import statistics
    26	
    27	import pytest
    28	
    29	from AgentEval.stats.types import KeywordRun, MannWhitneyResult
    30	
    31	pytest.importorskip("scipy")
    32	pytest.importorskip("numpy")
    33	
    34	from AgentEval.stats.library import StatsLibrary  # noqa: E402
    35	
    36	
    37	def _make_keyword_run(value: float, *, trial_index: int = 0) -> KeywordRun:
    38	    """Construct a minimal `KeywordRun` carrying `value` in `latency_seconds`."""
    39	    return KeywordRun(
    40	        trial_index=trial_index,
    41	        test_id=f"integration::trial-{trial_index}",
    42	        keyword_name="synthetic",
    43	        result=None,
    44	        error=None,
    45	        completeness="complete",
    46	        latency_seconds=value,
    47	        seed=None,
    48	    )
    49	
    50	
    51	def test_stat_mann_whitney_u_integration_smoke() -> None:
    52	    """`Stat.Mann Whitney U` end-to-end returns well-typed `MannWhitneyResult`."""
    53	    lib = StatsLibrary()
    54	    runs_a = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
    55	    runs_b = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([6.0, 7.0, 8.0, 9.0, 10.0])]
    56	    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
    57	    assert isinstance(result, MannWhitneyResult)
    58	    assert result.n_a == 5
    59	    assert result.n_b == 5
    60	    assert 0.0 <= result.p_value <= 1.0
    61	    assert -1.0 <= result.effect_size_r <= 1.0
    62	
    63	
    64	def test_stat_cliff_delta_integration_smoke() -> None:
    65	    """`Stat.Cliff Delta` end-to-end returns a float in [-1, 1]."""
    66	    lib = StatsLibrary()
    67	    runs_a = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0]]
    68	    runs_b = [_make_keyword_run(v) for v in [10.0, 20.0, 30.0]]
    69	    delta = lib.compute_cliff_delta(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
    70	    assert isinstance(delta, float)
    71	    assert -1.0 <= delta <= 1.0
    72	    # Clearly separated samples_a < samples_b → δ near -1.
    73	    assert delta == -1.0
    74	
    75	
    76	def test_stat_bootstrap_ci_integration_smoke() -> None:
    77	    """`Stat.Bootstrap CI` end-to-end returns a well-ordered (lo, hi) tuple."""
    78	    lib = StatsLibrary()
    79	    runs = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0] * 10]
    80	    lo, hi = lib.compute_bootstrap_ci(
    81	        runs,
    82	        statistic=statistics.mean,
    83	        predicate=lambda r: r.latency_seconds,
    84	        n_resamples=500,
    85	        seed=42,
    86	    )
    87	    assert isinstance(lo, float)
    88	    assert isinstance(hi, float)
    89	    assert lo <= hi
    90	    # Sample mean is 3.0; CI should bracket it.
    91	    assert lo <= 3.0 <= hi

codex
### HIGH-1: The “WITHOUT extras” tests never run in the base environment

**File:** `tests/unit/stats/test_advanced.py:37`
**Issue:** The story claims the missing-extra branch is covered in base CI, but this file is skipped wholesale as soon as `scipy` or `numpy` is absent. That means the `ImportError` gate is not actually verified in the environment where it matters.
**Evidence:** `pytest.importorskip("scipy")` / `pytest.importorskip("numpy")` are at module top, above `test_raise_advanced_extra_missing_helper...` and `test_phase2_keywords_raise_import_error_when_extra_unavailable`. The story artifact says the opposite at `_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md:218`.
**Fix:** Split the file: keep missing-extra tests in a module with no top-level `importorskip`, and gate only the scipy/numpy happy-path tests.

### HIGH-2: The published Python API names are wrong after the `compute_*` rename

**File:** `docs/contracts/stability-surface.md:129`
**Issue:** The contract doc still advertises `StatsLibrary.mann_whitney_u`, `StatsLibrary.cliff_delta`, and `StatsLibrary.bootstrap_ci`, but those methods do not exist. The implementation exposes `compute_mann_whitney_u`, `compute_cliff_delta`, and `compute_bootstrap_ci` instead.
**Evidence:** Contract doc: `StatsLibrary.mann_whitney_u` / `cliff_delta` / `bootstrap_ci`. Actual source: `src/AgentEval/stats/library.py:407`, `:464`, `:510` define only `compute_*`. The story record already admits the rename at `_bmad-output/.../13-1-...md:304,319`.
**Fix:** Update `stability-surface.md`, `mannwhitney.py`’s module docstring, and any story text that still names the pre-amendment Python methods.

### HIGH-3: The Mann-Whitney docs falsely say `u_statistic` “matches scipy default”

**File:** `src/AgentEval/stats/mannwhitney.py:56`
**Issue:** The sign convention is correct, but the U-statistic convention is documented incorrectly. This implementation returns `min(U1, U2)`, while `scipy.stats.mannwhitneyu(...).statistic` returns `U1` for the first sample, not the smaller-U canonical form.
**Evidence:** Code: `u1 = float(result.statistic)` then `u_smaller = min(u1, u2)` at `src/AgentEval/stats/mannwhitney.py:83-85`. Probe with `samples_a=[100..107]`, `samples_b=[1..8]` produced:
```text
u1 64.0
u2 0.0
returned 0.0
effect 1.0
```
So the returned value is not SciPy’s `.statistic` in that case.
**Fix:** Remove every “matches scipy default” claim for `u_statistic`, and state explicitly that the library normalizes to `min(U1, U2)` while using `U1` only for the signed `effect_size_r`.

### HIGH-4: The claimed SciPy bootstrap reference check is not implemented, and the cited seed semantics are wrong

**File:** `tests/unit/stats/test_advanced.py:212`
**Issue:** The story says bootstrap math is verified against `scipy.stats.bootstrap`, but the test file only checks broad invariants like bracketing, reproducibility, and width. There is no direct reference assertion, and the story’s cited `random_state=seed` call does not match the implementation’s `default_rng(seed)` semantics.
**Evidence:** No `scipy.stats.bootstrap` call exists in the bootstrap test block at `tests/unit/stats/test_advanced.py:212-261`. Empirically:
```text
ours (2.70475, 3.2552499999999998)
scipy random_state=42 (2.7195, 3.24525)
scipy rng=default_rng(42) (2.70475, 3.2552499999999998)
```
This disproves the story’s cited reference form at `_bmad-output/.../13-1-...md:173,309`.
**Fix:** Add an explicit equality test against `scipy.stats.bootstrap(..., rng=np.random.default_rng(seed), method="percentile")`, and update the story/docs to stop citing `random_state=seed` as the equivalent reference call.

### MED-1: `compute_bootstrap_ci` silently drops mixed-type samples instead of rejecting them

**File:** `src/AgentEval/stats/library.py:565`
**Issue:** The runtime type split uses the first element and then filters the rest by `isinstance`, which silently discards mismatched entries. That produces wrong confidence intervals instead of an immediate error.
**Evidence:** Code:
```python
if isinstance(first, KeywordRun):
    kw_samples = [s for s in samples if isinstance(s, KeywordRun)]
else:
    float_samples = [s for s in samples if not isinstance(s, KeywordRun)]
```
Probe results:
```text
[1.0, 2.0, KeywordRun(100.0)] -> (1.0, 2.0)
[KeywordRun(1.0), 2.0, 3.0] -> (1.0, 1.0)
```
The non-matching elements were ignored.
**Fix:** Validate homogeneity up front and raise `TypeError`/`ValueError` on mixed lists instead of filtering them.

**Total: 4 HIGH + 1 MED + 0 LOW**
tokens used
407,543
### HIGH-1: The “WITHOUT extras” tests never run in the base environment

**File:** `tests/unit/stats/test_advanced.py:37`
**Issue:** The story claims the missing-extra branch is covered in base CI, but this file is skipped wholesale as soon as `scipy` or `numpy` is absent. That means the `ImportError` gate is not actually verified in the environment where it matters.
**Evidence:** `pytest.importorskip("scipy")` / `pytest.importorskip("numpy")` are at module top, above `test_raise_advanced_extra_missing_helper...` and `test_phase2_keywords_raise_import_error_when_extra_unavailable`. The story artifact says the opposite at `_bmad-output/implementation-artifacts/13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md:218`.
**Fix:** Split the file: keep missing-extra tests in a module with no top-level `importorskip`, and gate only the scipy/numpy happy-path tests.

### HIGH-2: The published Python API names are wrong after the `compute_*` rename

**File:** `docs/contracts/stability-surface.md:129`
**Issue:** The contract doc still advertises `StatsLibrary.mann_whitney_u`, `StatsLibrary.cliff_delta`, and `StatsLibrary.bootstrap_ci`, but those methods do not exist. The implementation exposes `compute_mann_whitney_u`, `compute_cliff_delta`, and `compute_bootstrap_ci` instead.
**Evidence:** Contract doc: `StatsLibrary.mann_whitney_u` / `cliff_delta` / `bootstrap_ci`. Actual source: `src/AgentEval/stats/library.py:407`, `:464`, `:510` define only `compute_*`. The story record already admits the rename at `_bmad-output/.../13-1-...md:304,319`.
**Fix:** Update `stability-surface.md`, `mannwhitney.py`’s module docstring, and any story text that still names the pre-amendment Python methods.

### HIGH-3: The Mann-Whitney docs falsely say `u_statistic` “matches scipy default”

**File:** `src/AgentEval/stats/mannwhitney.py:56`
**Issue:** The sign convention is correct, but the U-statistic convention is documented incorrectly. This implementation returns `min(U1, U2)`, while `scipy.stats.mannwhitneyu(...).statistic` returns `U1` for the first sample, not the smaller-U canonical form.
**Evidence:** Code: `u1 = float(result.statistic)` then `u_smaller = min(u1, u2)` at `src/AgentEval/stats/mannwhitney.py:83-85`. Probe with `samples_a=[100..107]`, `samples_b=[1..8]` produced:
```text
u1 64.0
u2 0.0
returned 0.0
effect 1.0
```
So the returned value is not SciPy’s `.statistic` in that case.
**Fix:** Remove every “matches scipy default” claim for `u_statistic`, and state explicitly that the library normalizes to `min(U1, U2)` while using `U1` only for the signed `effect_size_r`.

### HIGH-4: The claimed SciPy bootstrap reference check is not implemented, and the cited seed semantics are wrong

**File:** `tests/unit/stats/test_advanced.py:212`
**Issue:** The story says bootstrap math is verified against `scipy.stats.bootstrap`, but the test file only checks broad invariants like bracketing, reproducibility, and width. There is no direct reference assertion, and the story’s cited `random_state=seed` call does not match the implementation’s `default_rng(seed)` semantics.
**Evidence:** No `scipy.stats.bootstrap` call exists in the bootstrap test block at `tests/unit/stats/test_advanced.py:212-261`. Empirically:
```text
ours (2.70475, 3.2552499999999998)
scipy random_state=42 (2.7195, 3.24525)
scipy rng=default_rng(42) (2.70475, 3.2552499999999998)
```
This disproves the story’s cited reference form at `_bmad-output/.../13-1-...md:173,309`.
**Fix:** Add an explicit equality test against `scipy.stats.bootstrap(..., rng=np.random.default_rng(seed), method="percentile")`, and update the story/docs to stop citing `random_state=seed` as the equivalent reference call.

### MED-1: `compute_bootstrap_ci` silently drops mixed-type samples instead of rejecting them

**File:** `src/AgentEval/stats/library.py:565`
**Issue:** The runtime type split uses the first element and then filters the rest by `isinstance`, which silently discards mismatched entries. That produces wrong confidence intervals instead of an immediate error.
**Evidence:** Code:
```python
if isinstance(first, KeywordRun):
    kw_samples = [s for s in samples if isinstance(s, KeywordRun)]
else:
    float_samples = [s for s in samples if not isinstance(s, KeywordRun)]
```
Probe results:
```text
[1.0, 2.0, KeywordRun(100.0)] -> (1.0, 2.0)
[KeywordRun(1.0), 2.0, 3.0] -> (1.0, 1.0)
```
The non-matching elements were ignored.
**Fix:** Validate homogeneity up front and raise `TypeError`/`ValueError` on mixed lists instead of filtering them.

**Total: 4 HIGH + 1 MED + 0 LOW**
