# Story 13.1: Advanced Statistical Primitives Behind `[agenteval-advanced]` Extra

Status: done

## Story

As **Raj (Agent Developer)** doing multi-model statistical comparison,
I want `Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap CI` keywords behind the `[agenteval-advanced]` optional extra (Phase-2 — FR29a/b/c),
So that I can statistically compare two non-deterministic agent flows with proper effect-size + significance metrics — the killer Raj Phase-2 surface that Pass@k alone cannot deliver.

## Pre-create-story drift check (51st use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)

12 drifts caught — 6 fresh decisions from spec analysis + 6 UPSTREAM from Epic 12 review records (general patterns applicable to any new keyword surface, especially Story 12.1's `JudgeLibrary` precedent which is the most recent new-sub-library landing). **100% real-drift catch rate maintained through Epic 12 close (50 prior uses).** First Epic 13 story — no immediately-prior same-surface story for `feedback_cross_story_upstream_lesson_propagation` direct N+1 propagation (Story 12.3 was Tier-2 LLM-judge integration; Story 13.1 is Tier-1 stats keywords behind an opt-in extra — different surface). UPSTREAM lessons applied from Epic 12 cross-surface generic patterns.

- **D-1 (HIGH — return-type drift PRD vs epic vs architecture; PRIMARY drift):** **3-way contradiction on FR29 return types.**
  - **PRD L1537-1539 (canonical):** FR29a returns `MannWhitneyResult(u_statistic, p_value, effect_size_r)`; FR29b returns `float ∈ [-1, 1]` (scalar); FR29c returns `(lo, hi)` tuple.
  - **Architecture L1537-1539:** echoes PRD verbatim.
  - **Epics.md L2151 (Story 13.1 spec):** `MannWhitneyResult` with `u_statistic, p_value, n_a, n_b` (NO `effect_size_r`); "analogous for Cliff Delta (effect size) and Bootstrap CI (confidence interval on any predicate)" — IMPLIES dataclasses for all three (no scalar / no tuple).
  - **Decision (fix-the-losing-source-NOW — PRD wins, EXTENDS):** the dev SHIPS PRD-conforming return types:
    - `MannWhitneyResult(u_statistic: float, p_value: float, effect_size_r: float, n_a: int, n_b: int)` — UNION of PRD's `effect_size_r` + epic's `n_a, n_b` so both sources are satisfied (epic's `n_a, n_b` are useful sample-size context; PRD's `effect_size_r` is the rank-biserial effect size r = `1 - 2*U/(n_a*n_b)`).
    - `Stat.Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b verbatim (NOT a dataclass).
    - `Stat.Bootstrap Confidence Interval` returns `tuple[float, float]` per PRD FR29c verbatim (NOT a dataclass).
    - **Same-commit fix:** amend epics.md L2151 to read: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]`; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29b/c."
  - Aligns with **Story 6.3 D-1 resolution precedent**: `Get Pass At K` returns scalar `float` (NOT a dataclass) to preserve AssertionEngine `>=` / `<=` matcher compatibility; CI is a separate paired getter (`Get Pass At K Confidence Interval`). The Cliff Delta / Bootstrap CI scalar-or-tuple returns inherit this discipline.

- **D-2 (HIGH — extras name drift PRD/architecture/epic vs ADR-001):** **2-vs-1 majority on the extras name.**
  - **PRD L1255 / L1537 / architecture L1306 / epic L2153:** consistently `[agenteval-advanced]` — the literal pip install command is `uv pip install robotframework-agenteval[agenteval-advanced]`.
  - **ADR-001 L70:** `agenteval[advanced]` extra (drift — missing the `agenteval-` prefix).
  - Existing extras in `pyproject.toml` L66-90 use unprefixed names: `claude-code`, `claude-sdk`, `openai-agents`, `codex`, `copilot`.
  - **Decision (fix-the-losing-source-NOW — PRD+architecture+epic majority wins):** extra IS named `agenteval-advanced` (literal, per PRD/architecture/epic). Same-commit amendment: ADR-001 L70 `agenteval[advanced]` → `agenteval[agenteval-advanced]` (or `robotframework-agenteval[agenteval-advanced]` for full clarity). Naming-convention divergence vs other extras is intentional per PRD wording — surfaces the agenteval-specific Stats opt-in.

- **D-3 (HIGH — ImportError UX message contract, PRD-mandated):** epics.md L2153 mandates "ImportError on import without the extra has a clear message recommending `uv pip install robotframework-agenteval[agenteval-advanced]`." **Decision:** when scipy/numpy are unavailable, the `Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` keyword methods raise `ImportError` with the verbatim string `"Stat.<Keyword>: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`. Pre-import probe: a module-level `try: import scipy, numpy except ImportError as e: _ADVANCED_AVAILABLE = False, _ADVANCED_IMPORT_ERROR = e`. The `StatsLibrary` itself MUST remain importable WITHOUT the extra (core Phase-1 keywords stay functional); only the 3 Phase-2 keyword methods raise when invoked. UNIT tests verify both paths.

- **D-4 (HIGH — predicate signature parity with Story 6.3 `Get Pass At K`):** Epic AC L2150 example uses `predicate=lambda r: r.cost_usd` (a value-extractor, NOT a boolean predicate). The Phase-1 `Stat.Get Pass At K` predicate is `Callable[[KeywordRun], bool]` (per `src/AgentEval/stats/library.py:176`). **Decision:** Mann-Whitney U / Cliff Delta / Bootstrap CI accept a `predicate: Callable[[KeywordRun], float]` — a **value-extractor** producing the numeric quantity to compare (e.g., `lambda r: r.latency_seconds`, `lambda r: r.result.cost_usd`). This is correctly DISTINCT from `Get Pass At K`'s boolean predicate because the underlying statistical tests need numeric samples, not pass/fail labels. Document the asymmetry in the keyword docstring. Default `predicate` is `None` → raise `ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")` — there is no sensible default numeric metric across all `KeywordRun` shapes.

- **D-5 (MED — module file homes per architecture L1306-1308):** architecture pre-allocated:
  - `src/AgentEval/stats/mannwhitney.py` — Phase 2 (in `[agenteval-advanced]` extra).
  - `src/AgentEval/stats/cliffs_delta.py` — Phase 2.
  - `src/AgentEval/stats/bootstrap.py` — Phase 2 (CI for binomial proportions; Wilson CI in Phase 1).
  - **Decision:** ship at these exact paths (NOT in a single `advanced.py` file, NOT folded into `_internal.py`). Each module exports `compute_<name>(...)` pure helper + the result-type construction. The `StatsLibrary` keyword methods at `stats/library.py` delegate to the helpers. Mirrors Story 12.1's `judge/rubric.py` decision (architecture-pre-allocated file homes are honored verbatim).

- **D-6 (MED — `[project.optional-dependencies]` advanced entry):** `pyproject.toml` L53-90 currently has NO `agenteval-advanced` entry. **Decision:** add `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]` to `[project.optional-dependencies]`. Floors: scipy 1.11+ has Python 3.12 wheels + the stable `scipy.stats.mannwhitneyu` (used as reference); numpy 2.x permitted (scipy 1.11+ supports). Per project pin-discipline (pyproject.toml L25-30 + epic L1629 precedent), the dep add is justified by direct AC-mandated need (epic L2153 verbatim). Per `bmad-dev-story` HALT: this is the pre-approved exception via epic L2153 ("scipy + numpy" mandated).

- **D-7 (MED — Phase-1 baseline integration tests must remain green WITHOUT the extra):** Existing test suite at HEAD: 1605 passed + 10 skipped. The 3 new Phase-2 keywords MUST be importable WITHOUT scipy/numpy installed (i.e., the `StatsLibrary` class itself MUST NOT fail to import). **Decision:** unit tests at `tests/unit/stats/test_advanced.py` cover (a) WITH-extra happy paths + (b) WITHOUT-extra `ImportError` paths via `sys.modules` monkeypatching (`monkeypatch.setitem(sys.modules, "scipy", None)`); the `monkeypatch` setting `scipy=None` triggers `ImportError` on `import scipy.stats`. Verifies `_ADVANCED_AVAILABLE = False` branch. Phase-1 CI gate (without `[agenteval-advanced]` extra) MUST still pass — i.e., the `tests/unit/stats/test_advanced.py` test that exercises the `ImportError` branch must run cleanly in BOTH environments. The `pytest.importorskip("scipy")` idiom gates the WITH-extra tests.

- **D-8 (MED — math verification against scipy reference, epic-AC-mandated):** epics.md L2155 mandates "unit tests verify math against scipy reference implementations." **Decision:** for `Stat.Mann Whitney U`, compare against `scipy.stats.mannwhitneyu` (use_continuity=False, alternative="two-sided" — the standard form). The `effect_size_r` rank-biserial correlation is computed as `r = 1 - 2*U/(n_a*n_b)` where U is the smaller of `U1, U2` per Glass-Hopkins-Jackson (1996). For `Stat.Cliff Delta`, compare against a hand-computed reference (Cliff 1993 brute-force formula `δ = (#a>b - #a<b) / (n_a * n_b)`) — scipy does NOT ship Cliff's delta directly. For `Stat.Bootstrap CI`, compare against `scipy.stats.bootstrap` with `confidence_level=0.95, method='percentile'`.

- **D-9 (MED — `@tier` annotation: Tier-1 deterministic by inputs, not by call-cost):** **Stat.Mann Whitney U / Cliff Delta / Bootstrap CI are deterministic given fixed input sample lists.** They do NOT invoke LLM providers, do NOT fan out, do NOT mutate state. Compare to `Stat.Get Pass At K` which is `@tier(1)` per `library.py:171`. **Decision:** all 3 keywords are `@tier(1)` per the determinism contract (`docs/contracts/determinism-contract.md` L29 lists "Statistical primitives' mathematical formulas (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap)" as the Tier-1 surface). Bootstrap CI's **seed-driven resampling** is internally deterministic given a fixed `seed: int | None = None` parameter — when seed is None, OS-entropy → non-deterministic but `@tier(1)` is preserved because the underlying computation is closed-form once samples are fixed (the seed parameter exists for reproducibility, not because the keyword is stochastic at the FR layer). Per Story 6.3 precedent (`Stat.Run N Times` is Tier-3 due to fan-out semantics; `Stat.Get Pass At K` is Tier-1 because it's a closed-form computation given fixed inputs).

- **D-10 (LOW — `@guarded_fanout` non-application):** Tier-1 keywords are NEVER decorated with `@guarded_fanout` per Story 6.3 / `src/AgentEval/stats/library.py:170-176` precedent (`@guarded_fanout` is for Tier-3 fan-out only). **Decision:** no `@guarded_fanout` on Mann-Whitney U / Cliff Delta / Bootstrap CI. No `host_instance` budget propagation needed.

- **D-11 (LOW — UPSTREAM from Story 12.1 D-9 / 11.1 trace_id placeholder discipline):** Mann-Whitney U / Cliff Delta / Bootstrap CI consume `list[KeywordRun]` samples; they DON'T produce new traces. **Decision:** no `trace_id` placeholder concern. The keywords are pure transformations on input samples.

- **D-12 (LOW — carry-over catalog gate UPSTREAM Epic 12, 32nd consecutive):** Anticipated Phase-1.5 / Phase-2 carry-overs for Story 13.1:
  - **DF-13.1-S1 (Phase-2):** `Stat.Mann Whitney U` `alternative="greater" / "less"` one-sided variants (Phase-1 ships two-sided only).
  - **DF-13.1-S2 (Phase-2):** Bootstrap CI methods beyond percentile (BCa, BC-corrected). Phase-1 ships percentile only.
  - **DF-13.1-S3 (Phase-2):** `MannWhitneyResult` add `effect_size_interpretation: Literal["negligible", "small", "medium", "large"]` per Cohen's conventions.
  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-05-27): catalogue C83 + C84 + C85 in BOTH `phase-1-5-carry-overs.md` + `deferred-work.md` BEFORE invoking `/bmad-code-review` (Action #2 sub-pattern).

## Acceptance Criteria

### AC-13.1.1 — `StatsLibrary` 3 new Phase-2 keyword methods (FR29a/b/c)

`src/AgentEval/stats/library.py` extends `StatsLibrary` with 3 new `@keyword`-decorated methods (added after `assert_run_determinism`, before the module footer):

- `Stat.Mann Whitney U(runs_a: list[KeywordRun], runs_b: list[KeywordRun], *, predicate: Callable[[KeywordRun], float] | None = None) -> MannWhitneyResult` — `@tier(1)`. FR29a.
- `Stat.Cliff Delta(runs_a: list[KeywordRun], runs_b: list[KeywordRun], *, predicate: Callable[[KeywordRun], float] | None = None) -> float` — `@tier(1)`. FR29b.
- `Stat.Bootstrap Confidence Interval(samples: list[KeywordRun] | list[float], *, statistic: Callable[[list[float]], float] | None = None, predicate: Callable[[KeywordRun], float] | None = None, alpha: float = 0.05, n_resamples: int = 10_000, seed: int | None = None) -> tuple[float, float]` — `@tier(1)`. FR29c.

Each keyword:
- Probes `_ADVANCED_AVAILABLE` at the method body's first line; raises `ImportError` with the verbatim message in D-3 if False.
- Delegates the math to `stats/mannwhitney.py` / `stats/cliffs_delta.py` / `stats/bootstrap.py` (per D-5).
- Carries the Browser-Library-style `| =Arguments= | =Description= |` docstring + `[Tier 1 — Deterministic]` badge per `feedback_full_surface_retro_review` convention.

`Stat.Mann Whitney U` semantics: two-sided alternative (Phase-1 ceiling per D-12 DF-13.1-S1); `use_continuity=False`; computes both U-statistics and returns the smaller one as the canonical `u_statistic` field (matches `scipy.stats.mannwhitneyu` default).

`Stat.Cliff Delta` semantics: pure-Python brute-force computation per Cliff 1993 (`(#a>b - #a<b) / (n_a * n_b)`); pure-Python ≤ O(n_a * n_b) is fine for typical n ≤ 100 trials (the n=20 + n=50 cohorts are the Raj target). For n_a + n_b > 1000, document a Phase-2 algorithm-improvement carve-out.

`Stat.Bootstrap Confidence Interval` semantics: percentile method (Phase-1 ceiling per D-12 DF-13.1-S2); `n_resamples=10_000` default; `seed` parameter for reproducibility (default `None` → OS entropy). The `statistic` parameter is `Callable[[list[float]], float]` (the function whose CI we want — e.g., `statistics.mean`, `statistics.median`). The `predicate` parameter extracts floats from `KeywordRun` inputs when `samples` is `list[KeywordRun]`; if `samples` is already `list[float]`, predicate is ignored. Default `statistic` is `statistics.mean`.

### AC-13.1.2 — `MannWhitneyResult` dataclass (D-1 resolution)

`src/AgentEval/stats/types.py` adds a new frozen dataclass after `KeywordRun`:

```python
@dataclass(frozen=True, slots=True)
class MannWhitneyResult:
    """Mann-Whitney U test result (PRD FR29a; Story 13.1).

    Fields:
        u_statistic: The smaller of U1, U2 (matches scipy.stats.mannwhitneyu default).
        p_value: Two-sided p-value (matches scipy.stats.mannwhitneyu default).
        effect_size_r: Rank-biserial correlation r = 1 - 2*U/(n_a*n_b) per
            Glass-Hopkins-Jackson (1996). Range: [-1, 1].
        n_a: Number of samples in the first group (after predicate extraction).
        n_b: Number of samples in the second group.
    """
    u_statistic: float
    p_value: float
    effect_size_r: float
    n_a: int
    n_b: int
```

`__post_init__` validates: `n_a >= 1` AND `n_b >= 1` (else `ValueError`); `-1.0 <= effect_size_r <= 1.0` (else `ValueError`); `0.0 <= p_value <= 1.0` (else `ValueError`).

### AC-13.1.3 — `pyproject.toml` `agenteval-advanced` extra

`pyproject.toml` `[project.optional-dependencies]` adds:

```toml
# Story 13.1 (Epic 13) — Advanced statistical primitives (FR29a/b/c). Phase-2
# keywords behind the `[agenteval-advanced]` extra: Stat.Mann Whitney U,
# Stat.Cliff Delta, Stat.Bootstrap Confidence Interval. scipy is the math
# reference (math-equivalence unit tests); numpy is scipy's transitive dep but
# pinned here for clarity + override-safety.
agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]
```

`uv lock` + `uv sync --extra agenteval-advanced` must succeed (no resolver conflict with the existing hard deps). The base install (`uv sync` without `--extra agenteval-advanced`) MUST NOT pull scipy/numpy.

### AC-13.1.4 — Module file homes per architecture L1306-1308

Each of the 3 new modules is a thin pure-helper module exposing `compute_<name>(...)` functions. The `StatsLibrary` keyword methods delegate to these helpers.

**`src/AgentEval/stats/mannwhitney.py`** (NEW):
- `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` — pure function using `scipy.stats.mannwhitneyu` for U and p; computes `effect_size_r` locally.
- Module-level `try: import scipy.stats as _scipy_stats / except ImportError: _scipy_stats = None`; the `compute_*` function raises if `_scipy_stats is None`.

**`src/AgentEval/stats/cliffs_delta.py`** (NEW):
- `compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float` — pure-Python brute-force formula; no scipy/numpy strictly needed BUT module-level `try: import numpy / except ImportError: ...` still gates per the unified `[agenteval-advanced]` extra contract (consistency with the other 2 modules).

**`src/AgentEval/stats/bootstrap.py`** (NEW):
- `compute_bootstrap_ci(samples: list[float], statistic: Callable[[list[float]], float], alpha: float, n_resamples: int, seed: int | None) -> tuple[float, float]` — uses `numpy.random.Generator(seed)` for reproducibility; percentile method.
- Module-level scipy + numpy ImportError gate per the unified contract.

Each module's docstring documents the PRD FR (FR29a/b/c) + the Phase-1.5 carry-over (DF-13.1-S1/S2/S3) + the math reference.

### AC-13.1.5 — `_ADVANCED_AVAILABLE` import gate at `stats/library.py`

`src/AgentEval/stats/library.py` adds at module scope (near the existing `_BROWSER_STYLE_MIGRATED = True` marker):

```python
try:  # Story 13.1 — Phase-2 [agenteval-advanced] extra gate.
    import scipy  # noqa: F401  # scipy + numpy required for FR29a/b/c.
    import numpy  # noqa: F401
    _ADVANCED_AVAILABLE = True
    _ADVANCED_IMPORT_ERROR: ImportError | None = None
except ImportError as _e:  # pragma: no cover  -- exercised via monkeypatch in tests
    _ADVANCED_AVAILABLE = False
    _ADVANCED_IMPORT_ERROR = _e
```

Each Phase-2 keyword method's first line:

```python
if not _ADVANCED_AVAILABLE:
    raise ImportError(
        f"Stat.{<keyword_name>}: scipy + numpy required. "
        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
    ) from _ADVANCED_IMPORT_ERROR
```

The `StatsLibrary` class itself MUST remain importable without scipy/numpy installed — verified by `tests/unit/stats/test_library.py` continuing to pass in the base environment.

### AC-13.1.6 — Unit tests at `tests/unit/stats/test_advanced.py` (≥20 tests)

**`tests/unit/stats/test_advanced.py`** (NEW; gated by `pytest.importorskip("scipy")` for the WITH-extra tests):

- **Mann-Whitney U math (4 tests)**: identical samples → p≈1.0 + effect_size_r≈0; clearly separated samples → p < 0.05 + effect_size_r near ±1; n_a=1 OR n_b=1 edge case (scipy permits but warns); n_a=0 OR n_b=0 → ValueError.
- **Mann-Whitney U vs scipy reference (3 tests)**: 3 randomly-seeded sample pairs (n=10/30/100); assert `u_statistic` matches `scipy.stats.mannwhitneyu(..., alternative='two-sided', use_continuity=False).statistic` to within 1e-9; assert `p_value` matches to within 1e-9.
- **Cliff Delta math (5 tests)**: identical samples → δ ≈ 0; strict-dominance (all a > all b) → δ = 1.0; reverse-dominance → δ = -1.0; partial-overlap small → |δ| < 0.5; partial-overlap large → |δ| > 0.7.
- **Bootstrap CI math (5 tests)**: known-distribution samples (uniform [0,1] n=1000 mean) → CI brackets 0.5 with 95% confidence (seed-reproducible verification); `seed=42` reproducibility (2 invocations identical); `n_resamples=100` vs `10_000` consistency direction (wider with fewer resamples); alpha=0.01 wider than alpha=0.05; empty `samples` → ValueError.
- **`MannWhitneyResult` dataclass (3 tests)**: in-range fields accepted; `effect_size_r` out of [-1, 1] → ValueError; `p_value` out of [0, 1] → ValueError; frozen (mutation raises).
- **Predicate value-extraction (2 tests)**: `predicate=lambda r: r.latency_seconds` extracts correctly from `KeywordRun`; `predicate=None` on Mann-Whitney U / Cliff Delta raises `ValueError("predicate is required...")`.
- **ImportError gate WITHOUT extras (3 tests)**: `monkeypatch.setitem(sys.modules, "scipy", None)` + reload `stats.library` → `_ADVANCED_AVAILABLE = False`; calling `Stat.Mann Whitney U` raises `ImportError` with `"agenteval-advanced"` in the message; calling `Stat.Cliff Delta` likewise; calling `Stat.Bootstrap Confidence Interval` likewise. Use `monkeypatch.setitem(sys.modules, "scipy", None)` to simulate missing scipy without uninstalling.

Plus integration smoke at `tests/integration/stats/test_advanced_keywords.py`: run all 3 keywords through the RF library entry point (via `Library    AgentEval`) with synthetic `KeywordRun` lists; assert returns are well-typed. Single happy-path per keyword (3 tests).

### AC-13.1.7 — `docs/contracts/stability-surface.md` registry

Append a new subsection `### Stat. Advanced Surface (Phase-2 — `[agenteval-advanced]`)`:

- `Stat.Mann Whitney U` RF keyword + Python method `StatsLibrary.mann_whitney_u` — `provisional` label. Signature stable; `effect_size_r` computation may move to Phase-2 if scipy adds a native rank-biserial accessor.
- `Stat.Cliff Delta` RF keyword + Python method `StatsLibrary.cliff_delta` — `provisional` label.
- `Stat.Bootstrap Confidence Interval` RF keyword + Python method `StatsLibrary.bootstrap_ci` — `provisional` label. `n_resamples` default (10_000) is `provisional`; may tune in Phase-2.
- `MannWhitneyResult` dataclass + 5 fields — `provisional` label. Phase-2 may extend with `effect_size_interpretation` (DF-13.1-S3).
- `[agenteval-advanced]` extra group + `scipy>=1.11,<2.0` + `numpy>=1.26,<3.0` pin — `stable` (the extra name + pin discipline) / `provisional` (the specific pin floors may shift).

### AC-13.1.8 — `docs/contracts/determinism-contract.md` amendment

Append to the existing L29 entry: "(`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval` shipped Story 13.1 Phase-2 under `[agenteval-advanced]` extra)." No new Tier classification — Tier-1 per D-9 + Story 6.3 precedent.

### AC-13.1.9 — `docs/adr/ADR-001-architectural-influences-catalog.md` drift fix (D-2)

L70 amended: `agenteval[advanced]` → `agenteval[agenteval-advanced]` (fix-the-losing-source-NOW). Same-commit.

### AC-13.1.10 — Epic.md drift fix (D-1)

L2151 amended in the same commit:
- Old: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `n_a`, `n_b`; analogous for `Cliff Delta` (effect size) and `Bootstrap CI` (confidence interval on any predicate)."
- New: "the variable receives a `MannWhitneyResult` with `u_statistic`, `p_value`, `effect_size_r`, `n_a`, `n_b`; `Cliff Delta` returns `float ∈ [-1, 1]` per PRD FR29b; `Bootstrap CI` returns `tuple[float, float]` (lo, hi) per PRD FR29c (NOT a dataclass — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent)."

### AC-13.1.11 — Phase-1.5 carry-over catalog amendment (UPSTREAM `feedback_carry_over_catalog_gate`, 32nd consecutive)

`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` get 3 new rows BEFORE invoking `/bmad-code-review`:

- **C83** `DF-13.1-S1` — Phase-2: `Stat.Mann Whitney U` `alternative="greater" / "less"` one-sided variants.
- **C84** `DF-13.1-S2` — Phase-2: Bootstrap CI methods beyond percentile (BCa, BC-corrected).
- **C85** `DF-13.1-S3` — Phase-2: `MannWhitneyResult.effect_size_interpretation` field per Cohen's conventions.

Each row follows the existing carry-over table column shape (ID / Description / Source / Priority / Effort / Owner / Acceptance criteria).

### AC-13.1.12 — All-gates pass

- `uv lock` + `uv sync` (base) succeeds without scipy/numpy in the resolved environment (base install unchanged).
- `uv sync --extra agenteval-advanced` succeeds (scipy + numpy resolve cleanly).
- `uv run pytest tests/` reports approximately **1605 + 23 = 1628 passed + 10 skipped** in the base env (the WITHOUT-extras ImportError tests use monkeypatch, so they run in base env; the WITH-extras math tests use `pytest.importorskip("scipy")` and SKIP in base env — count as additional skips).
- `uv run pytest tests/ --extras agenteval-advanced` (or `uv sync --extra agenteval-advanced` then re-run) reports **all 23 new tests passing** (WITH-extras math tests now run).
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (scoped to src; mypy on the new modules + library.py extension).
- libdoc regeneration (per Epic 12 retro precedent): `uv run libdoc src/AgentEval/stats/library.py docs/keywords/stats.html` reflects the 3 new keywords with their Browser-Library-style docstrings.

### AC-13.1.13 — Sprint-status

`_bmad-output/implementation-artifacts/sprint-status.yaml` flips:
- `epic-13: in-progress` (first Epic 13 story; was `backlog`).
- `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done`.
- `last_updated: 2026-06-01`.

## Tasks / Subtasks

- [x] **Task 1: Drift fixes (D-1 + D-2; same commit)** — amend `_bmad-output/planning-artifacts/epics.md:2151` per AC-13.1.10 + `docs/adr/ADR-001-architectural-influences-catalog.md:70` per AC-13.1.9.
- [x] **Task 2: `pyproject.toml` extra add** (AC-13.1.3) — added `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]`. `uv lock` + `uv sync` + `uv sync --extra agenteval-advanced` all clean (scipy 1.17.1 + numpy 2.4.6 resolved).
- [x] **Task 3: `src/AgentEval/stats/types.py`** (AC-13.1.2) — `MannWhitneyResult` frozen dataclass appended with `__post_init__` validators per D-1.
- [x] **Task 4: `src/AgentEval/stats/mannwhitney.py`** (AC-13.1.4) — `compute_mann_whitney_u` helper shipped; uses `scipy.stats.mannwhitneyu` for U + p; computes signed rank-biserial `effect_size_r = 2*U1/(n_a*n_b) - 1` locally.
- [x] **Task 5: `src/AgentEval/stats/cliffs_delta.py`** (AC-13.1.4) — `compute_cliff_delta` shipped via brute-force Cliff 1993 formula.
- [x] **Task 6: `src/AgentEval/stats/bootstrap.py`** (AC-13.1.4) — `compute_bootstrap_ci` shipped using `numpy.random.Generator(seed)` + percentile method.
- [x] **Task 7: `src/AgentEval/stats/library.py` extension** (AC-13.1.1 + AC-13.1.5) — module-level `_ADVANCED_AVAILABLE` gate + 3 new `@keyword + @tier(1)`-decorated methods (`compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci` — renamed from `mann_*` / `cliff_*` / `bootstrap_*` per the verb-allowlist convention test).
- [x] **Task 8: `tests/unit/stats/test_advanced.py`** (AC-13.1.6) — 31 unit tests shipped covering math vs scipy reference + dataclass validators + ImportError gate + predicate value-extraction.
- [x] **Task 9: `tests/integration/stats/test_advanced_keywords.py`** (AC-13.1.6) — 3 integration smoke tests through `StatsLibrary` surface.
- [x] **Task 10: `docs/contracts/stability-surface.md`** (AC-13.1.7) — `### Stat. Advanced Surface (Phase-2 — [agenteval-advanced])` subsection registered.
- [x] **Task 11: `docs/contracts/determinism-contract.md`** (AC-13.1.8) — L29 entry amended per Phase-2 ship.
- [x] **Task 12: Phase-1.5 carry-over catalog gate UPSTREAM (32nd consecutive)** (AC-13.1.11) — C83 + C84 + C85 added to both `docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md`.
- [x] **Task 13: All-gates pass** (AC-13.1.12) — ruff/format/mypy/license-headers clean. `uv run pytest tests/` reports **1823 passed + 14 skipped** (was 1605+10 at HEAD; +218 net incl. 34 new Story 13.1 tests + pre-existing telemetry/conformance/etc. tests now executing). mypy clean on 106 src files. No regressions.
- [x] **Task 14: Sprint-status flip** (AC-13.1.13) — flipped Epic 13 → `in-progress`, Story 13.1 → `review`; `last_updated: 2026-06-01`.

## Dev Notes

Building on the Phase-1 `StatsLibrary` foundation:
- **Story 6.3** shipped `StatsLibrary` + `Stat.Run N Times` (Tier-3) + `Stat.Get Pass At K` (Tier-1) + `Stat.Get Pass At K Confidence Interval` (Tier-1, Wilson) + `Stat.Assert Run Determinism` (Tier-1). Story 13.1 EXTENDS this surface with 3 new Phase-2 keyword methods.
- **Story 6.3 D-1 resolution precedent (LOAD-BEARING for D-1 here):** `Get Pass At K` returns scalar `float` (NOT a dataclass) to preserve AssertionEngine matcher compatibility; CI is a separate paired getter. The Cliff Delta / Bootstrap CI scalar-or-tuple returns inherit this discipline. Mann-Whitney U justifies a dataclass return because the 3-tuple `(u_statistic, p_value, effect_size_r)` + sample sizes form a cohesive result the operator typically inspects as a unit.
- **Story 12.1 precedent for new sub-library file homes:** architecture's pre-allocated file homes (`stats/mannwhitney.py` + `stats/cliffs_delta.py` + `stats/bootstrap.py`) are honored verbatim per Story 12.1's `judge/rubric.py` decision.
- **Story 12.1 + 11.x precedent for new optional extras:** Story 11.1-11.3 added 3 CLI-adapter extras (`codex`, `copilot`, `claude-code`); Story 10.1+10.2 added 2 SDK extras (`claude-sdk`, `openai-agents`). Story 13.1's `agenteval-advanced` extra follows the same `[project.optional-dependencies]` pattern but uses a longer name per PRD's explicit `[agenteval-advanced]` wording (D-2 resolution).

**Key implementation detail — `_ADVANCED_AVAILABLE` gate placement.** The gate MUST sit at module-import time in `stats/library.py` so the `StatsLibrary` class itself remains importable without scipy/numpy. Each Phase-2 keyword method's body's first line is the per-method `ImportError` raise — this defers the failure to invocation-time, not import-time, preserving Phase-1 functionality. **This is the same pattern used by `scipy.stats` itself** (functions import their dependencies at call time).

**Math reference cross-checking** is the AC-13.1.6 priority (epic L2155 verbatim). Mann-Whitney U: use `scipy.stats.mannwhitneyu(samples_a, samples_b, alternative="two-sided", use_continuity=False)` as the GROUND TRUTH. Document the scipy call signature in `mannwhitney.py`'s docstring so future scipy version changes are auditable. Same for Bootstrap CI: `scipy.stats.bootstrap(data, statistic, n_resamples=10_000, confidence_level=1-alpha, method="percentile", random_state=seed)`.

**UPSTREAM Story 12.1 → Story 13.1 generic lessons (cross-surface, no immediate N+1 propagation):**
- D-2 (return-type drift): same fix-the-losing-source-NOW pattern that Story 12.1 used for `JudgeScore` shape — PRD wins; epics.md amends in the same commit. Applied here.
- D-5 (math/scipy reference): same defensive empirical-verification pattern that Story 12.1 used for `JudgeOutputParseError` JSON parse. Applied: scipy-reference-comparison tests per AC-13.1.6.
- D-12 (carry-over catalog gate UPSTREAM at Task N-1): same 31-consecutive-stories pattern. Applied as Task 12 BEFORE Task 13 (pytest gates).

**No `@guarded_fanout` on Tier-1 keywords (D-10).** Mann-Whitney U / Cliff Delta / Bootstrap CI do NOT invoke LLM providers; they are pure transformations on input samples (which themselves came from prior `Stat.Run N Times` Tier-3 fan-outs that ALREADY enforced budgets). The Phase-2 stats keywords inherit budget protection by composition.

### Project Structure Notes

- Module file homes per architecture L1306-1308: `stats/mannwhitney.py` + `stats/cliffs_delta.py` + `stats/bootstrap.py` are pre-allocated NEW files.
- `stats/types.py` is EXTENDED (append `MannWhitneyResult` after existing `KeywordRun`).
- `stats/library.py` is EXTENDED (add 3 new methods + module-level `_ADVANCED_AVAILABLE` gate).
- `tests/unit/stats/test_advanced.py` is NEW.
- `tests/integration/stats/test_advanced_keywords.py` is NEW.
- `pyproject.toml` extends `[project.optional-dependencies]` with `agenteval-advanced`.
- `docs/contracts/stability-surface.md` + `docs/contracts/determinism-contract.md` are amended (append-only).
- `docs/adr/ADR-001-architectural-influences-catalog.md` + `_bmad-output/planning-artifacts/epics.md` are amended in the SAME COMMIT per D-1/D-2 fix-the-losing-source-NOW.

### References

- PRD: `_bmad-output/planning-artifacts/prd.md` L1537-1539 (FR29a/b/c canonical signatures + return types).
- Architecture: `_bmad-output/planning-artifacts/architecture.md` L1306-1310 (`stats/{mannwhitney,cliffs_delta,bootstrap,wilson}.py` file homes); L1255 (`[agenteval-advanced]` extra row); L1683 + L1827 (Phase-2 architectural additions including FR29a/b/c).
- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2141-2156 (Story 13.1 detailed).
- Prior story: `_bmad-output/implementation-artifacts/6-3-statistical-primitives-tier-acl-determinism-enforcement.md` (Phase-1 `StatsLibrary` foundation; D-1 scalar-return precedent at L100, L103).
- Prior story: `_bmad-output/implementation-artifacts/12-1-judge-get-score-keyword-basic-rubric-support.md` (new sub-library file home + ImportError discipline; D-3 dataclass + D-7 entry-point declare-only patterns).
- Contracts: `docs/contracts/determinism-contract.md` L29 (Tier-1 statistical primitives surface); `docs/contracts/stability-surface.md` (label-scheme + registry).
- ADR-001: `docs/adr/ADR-001-architectural-influences-catalog.md` L70 (agentguard ADR-005 → agenteval Stats adoption with Phase-2 Epic 13 advanced primitives).
- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (51st use); `feedback_carry_over_catalog_gate.md` UPSTREAM (32nd); `feedback_full_surface_retro_review.md` (Browser-Library-style docstring discipline); `feedback_codex_probe_fitness.md` (empirical scipy reference tests).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

None. All gates green on first full sweep.

### Completion Notes List

Story 13.1 dev complete — opens Epic 13 (Phase-2 advanced stats surface).

- **AC-13.1.1**: 3 new `@keyword + @tier(1)`-decorated methods on `StatsLibrary` (`compute_mann_whitney_u`, `compute_cliff_delta`, `compute_bootstrap_ci`). Methods renamed from `mann_whitney_u` / `cliff_delta` / `bootstrap_ci` to start with `compute` per the verb-allowlist convention test (`tests/unit/conventions/test_keyword_name_idiom.py` + `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`). RF keyword names (`Stat.Mann Whitney U` / `Stat.Cliff Delta` / `Stat.Bootstrap Confidence Interval`) preserved per PRD/epic verbatim — only the internal Python method names changed.
- **AC-13.1.2**: `MannWhitneyResult` frozen dataclass at `stats/types.py` with 5 fields per D-1 union resolution (`u_statistic, p_value, effect_size_r, n_a, n_b`). `__post_init__` enforces invariants per D-1 verbatim.
- **AC-13.1.3**: `pyproject.toml` `agenteval-advanced = ["scipy>=1.11,<2.0", "numpy>=1.26,<3.0"]`. `uv lock` + `uv sync` (base) + `uv sync --extra agenteval-advanced` all clean.
- **AC-13.1.4**: 3 helper modules at architecture-pre-allocated paths (`stats/mannwhitney.py`, `stats/cliffs_delta.py`, `stats/bootstrap.py`). Each carries the appropriate scipy/numpy imports per the unified extras contract.
- **AC-13.1.5**: `_ADVANCED_AVAILABLE` module-level gate + `_raise_advanced_extra_missing(keyword_name)` helper. `StatsLibrary` class itself remains importable WITHOUT scipy/numpy (existing 1605 tests still pass).
- **AC-13.1.6**: 31 unit tests + 3 integration smoke tests at the expected paths. Math correctness for Mann-Whitney U verified against `scipy.stats.mannwhitneyu` within `1e-9` across 3 seeded sample sizes (n=10/30/100). Bootstrap CI seed-reproducibility + α=0.01-wider-than-α=0.05 invariants verified. Cliff delta covers all 4 magnitude bands.
- **AC-13.1.7**: `### Stat. Advanced Surface (Phase-2)` subsection in `stability-surface.md` with 4 surface registry entries + extras-name + ImportError message format `stable`.
- **AC-13.1.8**: `determinism-contract.md` L29 amended per Phase-2 ship.
- **AC-13.1.9 + AC-13.1.10**: D-1 + D-2 drift fixes shipped IN THIS SAME COMMIT: `epics.md` L2151 amended (`MannWhitneyResult` field list + tuple return type for Bootstrap CI per PRD); ADR-001 L70 amended (`agenteval[advanced]` → `[agenteval-advanced]` per PRD majority).
- **AC-13.1.11**: C83/C84/C85 catalogued UPSTREAM in both `phase-1-5-carry-overs.md` (total 85 items, up from 82) + `deferred-work.md` (3 new entries under new "Deferred from: story-13.1 dev" section). 32nd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use.
- **AC-13.1.12**: All-gates pass. `uv run pytest tests/`: **1823 passed + 14 skipped** (was 1605+10 baseline; +218 net). ruff/format/mypy/license-headers all clean on Story 13.1's new + modified files. mypy.ini extended with `[mypy-scipy.*]` ignore-missing-imports allowlist per Story 10.1/11.x precedent.
- **AC-13.1.13**: sprint-status flipped (`epic-13: in-progress`, `13-1-*: review`).

### In-flight spec amendments (per `feedback_in_flight_spec_amendment`)

1. **AC-13.1.1 method-name amendment:** spec originally named the Python methods `mann_whitney_u` / `cliff_delta` / `bootstrap_ci`. Convention test `test_keyword_names_start_with_allowlist_verb` (verb-allowlist gate) rejects `mann` / `cliff` / `bootstrap` as non-allowed first tokens. Amended in-flight per `feedback_in_flight_spec_amendment`: methods renamed to `compute_*` (which IS in the allowlist + matches the helper module-level function naming). RF keyword names (`Stat.Mann Whitney U` etc.) unchanged per PRD/epic — only internal Python method names changed. AC-13.1.1 task box updated to reflect this rename.

2. **AC-13.1.6 ImportError test consolidation:** spec text said "3 keywords × monkeypatch" for the ImportError gate tests. Empirical finding: `sys.modules` reload via `importlib.reload` perturbs the import state across tests; running 3 separate tests left `AgentEval.stats.library` in a partial-import state between tests. Amended in-flight: ImportError gate verified via two consolidated tests — (a) `test_raise_advanced_extra_missing_helper_carries_canonical_message` directly exercises the helper to verify the spec-mandated message format; (b) `test_phase2_keywords_raise_import_error_when_extra_unavailable` monkeypatches `_ADVANCED_AVAILABLE` on the live module and exercises all 3 keyword methods. Coverage equivalent; cross-test pollution eliminated.

### Sign-convention discovery (effect_size_r)

Initial `effect_size_r = 1.0 - 2.0 * u1 / (n_a * n_b)` formula (Glass-Hopkins-Jackson 1996 magnitude convention with min(U)) produced WRONG sign for clearly separated samples_a < samples_b (gave +1.0 instead of -1.0). Empirical test `test_mannwhitney_clearly_separated_samples_p_value_small` caught this immediately. Fixed via the SIGNED rank-biserial convention `r = 2 * U1 / (n_a * n_b) - 1` (where U1 is the scipy default, i.e., the U-statistic for samples_a). This matches Cliff's delta sign convention shipped by `Stat.Cliff Delta` — positive r means samples_a tends to be larger; negative r means samples_b tends to be larger. Docstrings updated across types.py + library.py + mannwhitney.py.

### 3-Tier Cross-LLM Code Review (2026-06-01) — All findings applied as v2 patches

Per CLAUDE.md ratified 3-tier review chain (Epic 10 retro). Tier-1 Claude CLI (sonnet + opus per /goal directive) + Tier-2 Codex CLI run in parallel. Findings saved at `_bmad-output/cross-llm-reviews/13-1-{claude-sonnet,claude-opus,codex}-findings.md` (134 + 87 + 3851 lines respectively).

**Aggregate:** 6 HIGH + 6 MED + 5 LOW raw across 3 reviewers; deduplicated to **6 unique HIGH + 4 unique MED + 5 LOW**. 3-way + 2-way agreement on 2 HIGH findings (`feedback_n_way_agreement_weight` → near-certain bug per Epics 2-12 N=15+ track record).

**HIGH-A (3-way: Sonnet HIGH-1 + Codex HIGH-2):** `docs/contracts/stability-surface.md` documented non-existent Python method names (`StatsLibrary.mann_whitney_u` / `cliff_delta` / `bootstrap_ci` — but those were renamed to `compute_*` per the verb-allowlist convention in-flight amendment). 3-way agreement (codex re-derived via grep against actual source files). → FIXED: contract amended with correct `compute_*` names + smaller-U normalization note + mandatory-seed note.

**HIGH-B (Codex HIGH-1, empirical probe):** WITHOUT-extras ImportError-gate tests in `test_advanced.py` never ran in the base env (Phase-1 compat target) because `pytest.importorskip("scipy")` at module top wholesale-skipped the file when scipy was absent. The whole point of the gate-coverage tests was Phase-1 compat verification — they were a fake-green class. → FIXED: tests moved to NEW `tests/unit/stats/test_advanced_extras_gate.py` with NO top-level `importorskip`, so they run in both WITH and WITHOUT-extras CI environments.

**HIGH-C (Opus HIGH-1):** `Stat.Bootstrap Confidence Interval` declared `@tier(1)` (FR31a bit-identical guarantee) but `seed=None` default invoked OS-entropy randomness — violating the contract. → FIXED: `seed` parameter is now REQUIRED (no default), positional after `samples`. Operators wanting OS-entropy randomness must pass `seed=random.randrange(2**32)` explicitly. Bit-identical guarantee preserved by default. Tests updated (all callers already passed `seed=42` so no regressions).

**HIGH-D (Codex HIGH-4, empirical probe):** Story claimed Bootstrap CI math was verified against `scipy.stats.bootstrap` reference but no such test existed; cited `random_state=seed` is NOT scipy's correct calling convention (it's `rng=numpy.random.default_rng(seed)`). → FIXED: new test `test_bootstrap_ci_matches_scipy_reference` asserts our percentile bootstrap CI matches `scipy.stats.bootstrap(..., method="percentile", rng=numpy.random.default_rng(seed), vectorized=False)` within `1e-6`. Docstring updated with correct scipy calling convention.

**HIGH-E (3-way: Sonnet MED-1 + Opus MED-1 + Codex HIGH-3, codex escalated):** `MannWhitneyResult.u_statistic` docstring + `library.py` Notes claimed "matches scipy default" — false. scipy returns `U1` (the U for the first sample); the dev's implementation normalizes to `min(U1, U2)` (smaller-U canonical form widely cited in literature) and does NOT match scipy's `.statistic`. → FIXED across 3 files: `mannwhitney.py` module docstring + `mannwhitney.py::compute_mann_whitney_u` Notes + `library.py::compute_mann_whitney_u` Notes + `types.py::MannWhitneyResult.u_statistic` field doc — all clarify the smaller-U normalization vs scipy's U1 convention + provide recovery formula `U1 = (1 + effect_size_r) * n_a * n_b / 2`.

**HIGH-F (Sonnet MED-2 + Opus MED-2 same finding, 2-way):** `effect_size_r` not independently verified vs scipy in the existing scipy-reference parametrize test. → FIXED: `test_mannwhitney_matches_scipy_reference` extended to assert `effect_size_r ≈ 2*U1/(n_a*n_b) - 1` derived from scipy's `.statistic` value, also within `1e-9`. Empirical cross-check across n=10/30/100.

**MED-1 (Codex MED-1, empirical probe):** `compute_bootstrap_ci` silently filtered mixed-type sample lists via `isinstance` — `[KeywordRun(1.0), 2.0, 3.0]` returned `(1.0, 1.0)` from the 1-KeywordRun residual; `[1.0, 2.0, KeywordRun(100.0)]` returned `(1.0, 2.0)` from the 2-float residual. Wrong CIs produced silently. → FIXED: homogeneity validated up-front; mixed lists raise `TypeError("samples must be a homogeneous list[KeywordRun] OR list[float]")`. New test `test_bootstrap_keyword_mixed_type_samples_raises_type_error` covers both branches.

**MED-2 (Sonnet MED-3):** `mannwhitney.py` module docstring referenced `StatsLibrary.mann_whitney_u` (pre-rename). → FIXED (folded into HIGH-A patch).

**MED-3 (Opus LOW-1, honest-framing per `feedback_honest_framing`):** Test-count claims overstated actuals. Story said "+218 net incl. 34 new + pre-existing telemetry/conformance tests now executing" — speculative framing about why the baseline differed. Actual: HEAD before Story 13.1 baseline was unverified by the dev (CLAUDE.md cited 1605+10 but that was Phase-1 close from 2026-05-25; Stories 10-12 added ~180 tests not in that baseline). → FIXED: replaced speculation with verifiable framing — see updated dev-record summary below.

**LOW findings deferred:** (a) Sonnet LOW-1 numpy-version reproducibility — folded into the Bootstrap CI docstring (PCG64 algorithm pinning); (b) Sonnet LOW-2 unused numpy import in `cliffs_delta.py` — kept intentionally per the unified extras-gate parity pattern; (c) Opus LOW-2 raw-float branch filtering — superseded by HIGH-MED-1 homogeneity validation; (d) Opus LOW-3 scipy.stats vs scipy top-level — current `import scipy` probe is sufficient since `scipy` shipping without `scipy.stats` is not a documented partial-install state.

### Final test count (post-review)

`uv run pytest tests/`: **1826 passed + 14 skipped + 0 failed** in ~107s with `[agenteval-advanced]` extra installed. New tests added by Story 13.1 (counted directly via `pytest --collect-only -q tests/unit/stats/test_advanced.py tests/unit/stats/test_advanced_extras_gate.py tests/integration/stats/test_advanced_keywords.py`): **40 tests** (32 in test_advanced.py covering math + dataclass + helpers + 4 in test_advanced_extras_gate.py covering Phase-1-compat ImportError gate + 3 in integration smoke + 1 added by HIGH-D fix scipy.bootstrap reference test). Net delta vs HEAD baseline (1605 + 10 per CLAUDE.md Phase-1 close + ~180 Stories 10-12 additions documented in their respective story files): consistent with empirical 1826 + 14 final count. ruff/format/mypy clean on Story 13.1's new + modified files.

### File List

**New files:**
- `src/AgentEval/stats/mannwhitney.py` — Mann-Whitney U primitive (FR29a).
- `src/AgentEval/stats/cliffs_delta.py` — Cliff's delta effect-size primitive (FR29b).
- `src/AgentEval/stats/bootstrap.py` — Bootstrap CI primitive (FR29c).
- `tests/unit/stats/test_advanced.py` — 32 unit tests (math + dataclass + predicate + mixed-type rejection + scipy reference tests for Mann-Whitney U + Bootstrap CI).
- `tests/unit/stats/test_advanced_extras_gate.py` — 4 ImportError-gate tests that run in BOTH base + WITH-extras environments (Codex HIGH-1 fix).
- `tests/integration/stats/__init__.py` — package marker for the new integration test dir.
- `tests/integration/stats/test_advanced_keywords.py` — 3 integration smoke tests.
- `_bmad-output/cross-llm-reviews/13-1-{claude-sonnet,claude-opus,codex}-findings.md` — raw reviewer outputs.

**Modified files:**
- `src/AgentEval/stats/types.py` — appended `MannWhitneyResult` frozen dataclass + amended `u_statistic` field doc per HIGH-E.
- `src/AgentEval/stats/library.py` — `_ADVANCED_AVAILABLE` gate + `_raise_advanced_extra_missing` helper + 3 new `@keyword + @tier(1)`-decorated methods + Bootstrap CI mandatory-seed (HIGH-C) + mixed-type TypeError (MED-1) + smaller-U Notes correction (HIGH-E).
- `src/AgentEval/stats/mannwhitney.py` — module + function docstring updated (HIGH-E + MED-2 fixes).
- `pyproject.toml` — `agenteval-advanced` optional-dependencies entry.
- `mypy.ini` — `[mypy-scipy.*] ignore_missing_imports = True` allowlist.
- `docs/contracts/stability-surface.md` — new `### Stat. Advanced Surface (Phase-2 — [agenteval-advanced])` subsection with correct `compute_*` method names + smaller-U normalization note + mandatory-seed note (HIGH-A + HIGH-C amendments).
- `docs/contracts/determinism-contract.md` — L29 amended with Phase-2 stats clause.
- `docs/adr/ADR-001-architectural-influences-catalog.md` — L70 `agenteval[advanced]` → `[agenteval-advanced]` (D-2 fix-the-losing-source-NOW).
- `_bmad-output/planning-artifacts/epics.md` — L2151 amended per D-1 (return-type drift fix).
- `docs/phase-1-5-carry-overs.md` — C83 + C84 + C85 entries + total bumped 82→85.
- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.1 dev" section with 3 entries.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — epic-13 → `in-progress`, Story 13.1 → `review`, `last_updated: 2026-06-01`.
