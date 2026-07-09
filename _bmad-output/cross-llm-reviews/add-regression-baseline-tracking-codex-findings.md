# Adversarial Review: add-regression-baseline-tracking

Reviewer: Codex
Date: 2026-07-09
Repo/branch: `/home/many/workspace/robotframework-agenteval`, `implement-explore-findings`, uncommitted working tree

## Findings

### MED-1: Missing metrics are skipped without any warning, so the keyword can fake-green when evidence disappears

Location: `src/AgentEval/baseline/comparison.py:339`, `src/AgentEval/baseline/comparison.py:384`, `src/AgentEval/baseline/comparison.py:389`, `src/AgentEval/baseline/comparison.py:419`; returned silently by `src/AgentEval/baseline/library.py:318`

The comparison engine returns `verdict="skipped"` for baseline-only/current-only metrics, but `_skipped()` emits no warning and `metrics_should_not_regress()` returns successfully when the only non-pass outcomes are skips. A caller using the keyword as a CI gate can therefore get a green build with no visible warning when the current run stops producing a baseline metric.

Concrete scenario:

```python
base = MetricsBaseline(1, {
    "pass_rate": ProportionEvidence(successes=10, trials=10, value=1.0),
    "cost_usd": ContinuousEvidence(samples=(0.1, 0.1, 0.1), value=0.1, total=0.3, mean=0.1),
}, {}, RunContext())
curr = MetricsBaseline(1, {
    "pass_rate": ProportionEvidence(successes=10, trials=10, value=1.0),
}, {}, RunContext())
report = compare(base, curr, tolerance="5%")
```

Observed: `report.regressed == False`, `cost_usd` is `skipped`, and the only warning is the unrelated `UnderpoweredComparisonWarning` for `pass_rate`. There is no missing-metric warning. This violates the "missing metric ... get WARNED (not silently passed)" honesty bar. It is especially risky for `Metrics Should Not Regress` because current extraction omits `cost_usd` when results no longer unwrap to `AgentRunResult`, making a cost gate disappear while CI still passes.

Suggested fix: add a dedicated warning class or reuse an existing loud warning path for skipped metrics, and emit it for baseline-only, current-only, and evidence-kind mismatch skips. The keyword may still return pass per the spec's "never auto-fail" rule, but the skip must be visible without requiring callers to inspect `report.comparisons`.

### MED-2: History "corrupt line skip+warn" only catches JSON/top-level corruption; malformed metric evidence crashes trend parsing

Location: `src/AgentEval/baseline/schema.py:101`, `src/AgentEval/baseline/library.py:421`, `src/AgentEval/baseline/library.py:453`

`_read_history()` calls `parse_snapshot()`, which validates only JSON parseability, `schema_version`, and top-level `metrics`/`run_context` shape. It does not validate or reconstruct metric evidence. As a result, a history line that is valid JSON with `schema_version: 1` but has malformed metric evidence is accepted as a snapshot, then `get_metric_trend()` crashes later while coercing metric fields instead of skipping the corrupt line with a warning.

Concrete scenario:

```json
{"schema_version":1,"metrics":{"pass_rate":{"kind":"proportion","successes":"oops","trials":10,"value":0.9}},"extra_metrics":{},"run_context":{}}
```

`Get Metric Trend    metric=pass_rate` raises:

```text
ValueError: invalid literal for int() with base 10: 'oops'
```

This contradicts the JSONL history requirement that corrupt lines are skipped with a warning. The same issue applies to other malformed metric fields that pass top-level validation and then fail in `float(value)` or `wilson_score_interval(successes, trials)`.

Suggested fix: have `_read_history()` call the full loader/reconstructor (`load`) and convert back to payload, or strengthen `parse_snapshot()` to validate each metric entry. Keep the `try/except` around the full per-line validation so malformed metric evidence is skipped and logged with the line number.

### LOW-1: Baseline loader leaks `KeyError`/`ValueError` for malformed metric fields instead of `BaselineSchemaError`

Location: `src/AgentEval/baseline/schema.py:169`, especially `src/AgentEval/baseline/schema.py:180`

`load()` promises `BaselineSchemaError` when a required field is missing or has the wrong shape, but `_from_payload()` directly indexes and coerces nested metric fields. A baseline with `{"kind": "proportion", "trials": 10, "value": 0.9}` raises `KeyError: 'successes'`; a baseline with `successes > trials` loads successfully and only fails later when the comparison recomputes Wilson CIs.

This is not a false-green for baselines produced by `Save Metrics Baseline`, but it weakens schema-drift handling for committed files and JSONL history.

Suggested fix: wrap nested evidence reconstruction in field-specific validation that raises `BaselineSchemaError(file_path=..., field_name="metrics.<name>.<field>")`, including numeric constraints like `0 <= successes <= trials`, `0 <= value <= 1` for proportions, and list-of-number checks for continuous samples.

## Checks That Passed

- CI-overlap AND rule: `9/10 -> 7/10` passed with `PossibleRegressionWarning`; `45/50 -> 5/50` failed with `comparison_mode="wilson_ci_disjoint"`.
- Direction registry: `pass_rate`, `pass_at_*`, and `tool_hit_rate` are higher-is-better; `cost_usd` and `latency_*` are lower-is-better. Direct probes confirmed cost/latency increases fail and pass-rate improvements do not fail.
- Continuous Mann-Whitney tail: direct probes with current samples larger than baseline for `cost_usd`/`latency_p95_ms` failed in `mann_whitney` mode; higher-is-better continuous drops also failed in the opposite direction.
- Degraded continuous path: missing samples or simulated missing advanced extra emits `DegradedComparisonWarning` and records `comparison_mode="point_only"`.
- Underpower: Wilson half-width warnings fire and do not mask a real fail.
- Save schema: baseline JSON is deterministic, redacted via `redact_dict`, schema-versioned, and stores evidence (`successes`/`trials` or raw samples), not precomputed pass/fail verdicts.
- Surface checks: all three BaselineLibrary keywords are `@tier(1)`, composed into `AgentEval`, unprefixed by convention, and the count gate expects 98 keywords.

## Commands Run

- `uv run pytest tests/unit/baseline -q`
- `uv run pytest tests/unit/conventions/test_keyword_namespace_prefix.py tests/unit/conventions/test_keyword_name_idiom.py tests/integration/docs/test_keyword_count_drift.py tests/unit/test_composition.py -q`
- Direct `uv run python` probes for the proportion CI-overlap cases, continuous direction/Mann-Whitney cases, missing metric skip behavior, and malformed history/schema inputs.
