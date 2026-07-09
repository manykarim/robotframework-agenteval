## 1. Package scaffold & models

- [x] 1.1 Create `src/AgentEval/baseline/` package (`__init__.py`, `models.py`, `schema.py`, `comparison.py`, `library.py`) with Apache license headers and module docstrings citing the design decisions
- [x] 1.2 Define frozen dataclasses in `models.py`: `ProportionEvidence` (successes, trials, value), `ContinuousEvidence` (samples, value points: total/mean/p50/p95, samples_truncated), `RunContext` (model, adapter_name, adapter_version, library_version, timestamp, git_sha, git_dirty), `MetricsBaseline` (schema_version, metrics, extra_metrics, run_context), `MetricComparison` (metric, direction, baseline/current points + CIs, tolerance applied + semantics, comparison_mode, verdict, reason), `RegressionReport` (comparisons, run_context pair, `.as_dict()`), `TrendPoint` + `TrendSeries` (`.as_dict()`, `.values()`)
- [x] 1.3 Implement `schema.py`: `SCHEMA_VERSION = 1`, deterministic serializer (indent=2, sort_keys, trailing newline) through `redact_dict`, loader with `schema_version` + required-field validation
- [x] 1.4 Add structured errors to `AgentEval/errors.py` idiom (in `baseline/` or errors.py per existing convention): `BaselineWriteError`, `BaselineNotFoundError` (save-then-commit fix suggestion), `BaselineSchemaError`; warning classes `PossibleRegressionWarning`, `UnderpoweredComparisonWarning`, `DegradedComparisonWarning`
- [x] 1.5 Implement best-effort git capture helper: `git rev-parse HEAD` + `git status --porcelain` via `subprocess.run` with timeout, `GITHUB_SHA`-style env fallback, `None`/`None` on any failure — never raises

## 2. Metric extraction (snapshot path)

- [x] 2.1 Implement results-union extraction: `list[KeywordRun]` (default predicate `completeness == "complete"`, `predicate=` override; latency from `latency_seconds`; unwrap `r.result` when it is an `AgentRunResult`) and `list[AgentRunResult]` (reuse `metrics/_internal` aggregation helpers)
- [x] 2.2 Compute proportion evidence: `pass_rate` (successes/trials), `pass_at_k` for the requested `k=` list (default k=1) via `stats/_internal._compute_pass_at_k`, `tool_hit_rate` only when `expected_tools=` provided
- [x] 2.3 Compute continuous evidence: per-trial `cost_usd` and `latency_ms` sample lists + derived total/mean/p50/p95; omit (and log) metric families whose evidence is unavailable — never zero-fill
- [x] 2.4 Implement `Save Metrics Baseline` keyword (`@keyword` + `@tier(1)`) with `results`, `path=`, optional `history=`, `predicate=`, `k=`, `expected_tools=`, `extra_metrics=`; write baseline JSON (raise `BaselineWriteError` on failure) and append one compact JSONL line when `history=` given (create-if-absent, never truncate)

## 3. Comparison engine

- [x] 3.1 Implement direction registry (higher-is-better: pass_rate/pass_at_k/tool_hit_rate; lower-is-better: cost/latency) with per-metric override
- [x] 3.2 Implement tolerance parsing (`"5%"` / float) with dual semantics: absolute percentage points for proportions, relative-to-baseline for continuous; `tolerances=` per-metric override map
- [x] 3.3 Implement proportion rule: FAIL iff tolerance breach AND Wilson CIs disjoint (recomputed from stored successes/trials at `confidence=`, via `stats/wilson.py`); breach-with-overlap → PASS + `PossibleRegressionWarning` quoting both points, CIs, and Ns
- [x] 3.4 Implement underpower check: Wilson half-width vs tolerance → `UnderpoweredComparisonWarning` with approximate n required
- [x] 3.5 Implement continuous rule: relative-tolerance breach + one-sided Mann-Whitney U (`alpha=0.05`) when both sample sets present AND `[advanced]` importable; else point-only + `DegradedComparisonWarning` naming what was skipped and why; record `comparison_mode`
- [x] 3.6 Handle asymmetric metric sets: baseline-only or current-only metrics → `skipped` verdict with reason in the report, never auto-fail, never silent-drop; `extra_metrics` compared point-only
- [x] 3.7 Implement `Metrics Should Not Regress` keyword (`@keyword` + `@tier(1)`) with `results`, `baseline=`, `tolerance=5%`, `tolerances=`, `confidence=0.95`, `predicate=`, `expected_tools=`; failure message quotes per-metric numeric bars (both points, both CIs, tolerance semantics restated numerically, trial counts); run-context mismatch logged side-by-side, never gated; returns `RegressionReport`

## 4. Trend surface

- [x] 4.1 Implement history reader: parse JSONL snapshots (skip+warn on corrupt lines), time-ordered
- [x] 4.2 Implement `Get Metric Trend` keyword (`@keyword` + `@tier(1)`) with `metric=`, `history=`; returns `TrendSeries` with per-point value + Wilson CI recomputed from stored evidence (else `None`), n_trials, git_sha, model; missing-in-snapshot → missing point, not zero
- [x] 4.3 Extract the shared cell-grid ASCII renderer from `_heatmap/models.py` into a `_heatmap`-internal helper consumed by both `CohortHeatmap` and a new `TrendGrid` (`.as_ascii()`/`.as_dict()`, em-dash missing-cell sentinel); existing `Get Cohort Heatmap` tests must pass unchanged
- [x] 4.4 Wire the optional trend-grid rendering onto the trend surface (metrics rows × snapshot columns)

## 5. Contracts, docs & recipe

- [x] 5.1 Publish `docs/contracts/metrics-baseline-schema.json` (JSON Schema for schema_version 1) and add a unit test validating real emitter output against it
- [x] 5.2 Write the CI-gate recipe under `docs/recipes/` (PR fails when metrics regress vs committed `baselines/main.json`; documents the re-snapshot-and-commit workflow for intentional updates, "raise n not tolerance" flakiness guidance, and the false-negative trade-off); run the executable-doc smoke check (`robot --dryrun` per code block)
- [x] 5.3 Add keywords + `BaselineLibrary` + public dataclasses to `docs/contracts/stability-surface.md`; update README keyword table + `docs/index.md` counts (note dossier E3 drift — fix counts against `grep`-derived reality, not prior claims)
- [x] 5.4 Browser-Library-style keyword docstrings with Arguments tables + runnable examples; libdoc-render smoke check (keyword names are unprefixed, so the namespace multi-word libdoc norm is N/A — verify anyway)

## 6. Tests

- [x] 6.1 Unit tests `tests/unit/baseline/test_models.py` + `test_schema.py`: deterministic serialization (byte-identical modulo timestamp/git fields), redaction at write boundary, schema round-trip, future `schema_version` → `BaselineSchemaError`, missing file → `BaselineNotFoundError` with fix text
- [x] 6.2 Unit tests extraction: KeywordRun default predicate + override, AgentRunResult list path, omission (not zero-fill) when evidence unavailable, `tool_hit_rate` only with `expected_tools=`
- [x] 6.3 Unit tests comparison: genuine regression (45/50 → 5/50, tol 5%) fails with numeric message; noisy drop (9/10 → 7/10) passes + `PossibleRegressionWarning`; within-tolerance clean pass; improvement never fails; continuous fail with Mann-Whitney (advanced installed); point-only fallback + `DegradedComparisonWarning` (advanced absent — simulate via import guard); underpowered → `UnderpoweredComparisonWarning` with n estimate; skipped metrics; context-mismatch reported-not-gated
- [x] 6.4 Unit tests trend: 3-snapshot history → 3 ordered points with recomputed CIs; append never truncates; corrupt line skip+warn; missing metric → missing point; `TrendGrid.as_ascii()` em-dash sentinel; `CohortHeatmap` regression guard after renderer extraction
- [x] 6.5 Nullish-input fuzz per `feedback_nullish_input_fuzz_checklist`: baseline JSON fields as `None`/`""`/`False`/`0`/missing-key through the loader
- [x] 6.6 RF-level dogfood suite under `tests/dogfood/` exercising save → regress-check → trend end-to-end with the mock provider (include VALIDATION-CEILING line in the parity checklist; run the dogfood fake-green precheck)
- [x] 6.7 `Get Keyword Tier` reports 1 for all three keywords; standalone `Library    AgentEval.baseline.library.BaselineLibrary` import smoke; keyword-name collision check vs all existing libraries

## 7. Quality gates & review

- [x] 7.1 `uv run ruff check src/ tests/` clean
- [x] 7.2 `uv run mypy src/` clean
- [x] 7.3 `uv run pytest tests/` green (no regressions vs the 1605-passed HEAD bar)
- [x] 7.4 Carry-over catalog gate: grep new files for `DF-X-SY` markers and verify each is in `docs/phase-1-5-carry-overs.md` (expected: exact-proportion test Phase-2, sample cap, first-class judge/activation metric families, multiple-comparison correction)
- [ ] 7.5 Run the cross-LLM review chain (Tiers 1+2 in parallel, Tier 3 on degradation) per CLAUDE.md; apply HIGH findings inline before marking done
