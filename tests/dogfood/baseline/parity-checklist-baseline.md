# Parity Checklist: Regression Baseline Tracking (OpenSpec `add-regression-baseline-tracking`)

**VALIDATION-CEILING (per `feedback_dogfood_validation_ceiling` norm):** this
dogfood VERIFIES that the `BaselineLibrary` keyword surface (`Save Metrics
Baseline` / `Metrics Should Not Regress` / `Get Metric Trend`) drives
end-to-end through the composed `Library    AgentEval` import on the
deterministic Mock provider (NO API keys) — snapshot → regression-gate → trend,
plus the three-valued statistical bands (FAIL / PASS-with-`PossibleRegression`
/ within-tolerance PASS), deterministic redacted JSON, and structured
`BaselineNotFoundError`. It does **NOT** VERIFY: (1) live LLM-driven metric
collection — the Mock provider always returns `completeness="complete"`, so the
FAIL and PASS-with-warning bands are driven through **controlled `KeywordRun`
fixtures** (`Make Keyword Runs`), not mock output; (2) the continuous-metric
Mann-Whitney U path against real cost/latency variance (Mock cost is `0.0`) —
that path is covered in `tests/unit/baseline/test_comparison.py`; (3) the
`git_sha`/`git_dirty` capture across non-repo / shallow-clone CI environments
(unit-covered via the best-effort helper). The exhaustive statistical-rule
matrix lives in the unit suite; this dogfood is the composed-surface
integration proof.

## Coverage

| Behavior | Robot test | Band |
| --- | --- | --- |
| Real Mock fan-out → save → regress(PASS) → trend | `Mock run round-trips through save -> regress -> trend` | live mock provider |
| Deterministic + schema-versioned JSON | `Baseline JSON is deterministic and schema-versioned` | fixture |
| Real regression beyond tolerance FAILS (CIs disjoint) | `Real regression beyond tolerance fails the gate` | fixture |
| Within-CI-overlap drop PASSES + `PossibleRegressionWarning` | `Within-CI-overlap drop passes with a PossibleRegressionWarning` | fixture |
| Missing baseline → structured `BaselineNotFoundError` | `Missing baseline raises a structured BaselineNotFoundError` | fixture |
| Trend series + ASCII grid (reuses `_heatmap` renderer) | `Trend series exposes an ASCII trend grid` | fixture |

**Run locally:**

```
uv run robot tests/dogfood/baseline/test_regression_baseline.robot
```

## Fake-green precheck (per `feedback_dogfood_fake_green_precheck`)

- Every assertion body checks a load-bearing value (trial count, file
  contents, `report.regressed`, series length, grid content), not just that a
  keyword returned.
- The FAIL band uses `Run Keyword And Expect Error    *regressed*` — it asserts
  the gate actually raises, not that it silently passed.
- The missing-baseline test asserts the `*BASELINE_NOT_FOUND*` error code, not
  a generic failure.
- Suite executed green at authoring time: `6 tests, 6 passed, 0 failed`.
