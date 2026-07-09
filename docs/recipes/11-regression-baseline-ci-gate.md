# Recipe #11: Gate a PR on metric regression vs a committed baseline

**Use case:** any team that wants CI to fail a pull request when a model
update, adapter bump, or prompt tweak silently drops Pass@k, raises cost, or
slows latency versus a known-good baseline committed to the repo.
**What it covers:** `Save Metrics Baseline`, `Metrics Should Not Regress`,
`Get Metric Trend`, the CI-overlap-aware regression rule, and the deliberate
re-snapshot-and-commit workflow for intentional changes.

## The honest-framing contract (read this first)

Agent metrics are stochastic. A naive point-compare that fails the moment
Pass@1 dips from 0.90 to 0.88 would fail on noise. `Metrics Should Not Regress`
therefore FAILS a proportion metric **only** when the drop exceeds `tolerance`
AND the Wilson confidence intervals are disjoint — a drop inside the CI overlap
PASSES and emits a `PossibleRegressionWarning` instead. Continuous metrics
(cost, latency) use a relative tolerance plus a one-sided Mann-Whitney U noise
guard (with the `[agenteval-advanced]` extra).

**Flaky gate? Raise `n`, not `tolerance`.** If a comparison keeps landing in
the PASS-with-warning band, the fix is more trials in `Stat.Run N Times` (which
tightens the CIs), NOT a looser tolerance (which blinds the gate). When the
sample size is too small to detect the requested tolerance at all, the keyword
emits `UnderpoweredComparisonWarning` naming the `n` you would need.

**Known trade-off (by design):** the AND-rule biases toward false negatives —
small real regressions can pass for a while. The trend surface (`Get Metric
Trend`) exists precisely to catch slow drift that any single gate misses.

## Step 1 — snapshot a baseline and commit it

```robotframework
*** Settings ***
Library    AgentEval    provider=mock

*** Test Cases ***
Snapshot The Main Baseline
    @{runs}=    Stat.Run N Times    n=50    keyword=Send Prompt
    ...    keyword_args=${{ ['adapter=mock', 'prompt=Add a health-check route'] }}
    Save Metrics Baseline    ${runs}    path=baselines/main.json
    ...    history=baselines/history.jsonl    model=claude-sonnet-4-6
```

Commit `baselines/main.json` (and `baselines/history.jsonl`) to the repo. The
JSON is deterministic (`indent=2`, sorted keys, trailing newline) and redacted,
so it produces reviewable diffs and never carries a credential.

## Step 2 — gate every PR against the committed baseline

```robotframework
*** Settings ***
Library    AgentEval    provider=mock

*** Test Cases ***
Metrics Must Not Regress On This PR
    @{runs}=    Stat.Run N Times    n=50    keyword=Send Prompt
    ...    keyword_args=${{ ['adapter=mock', 'prompt=Add a health-check route'] }}
    ${report}=    Metrics Should Not Regress    ${runs}    baseline=baselines/main.json
    ...    tolerance=5%    tolerances=${{ {'cost_usd': '10%'} }}
    Should Be Equal    ${report.regressed}    ${FALSE}
```

`tolerance=5%` means **5 percentage points absolute** for proportion metrics
(Pass@1 may drop from 0.90 to 0.85) and **5% relative** for continuous metrics
(cost may grow 5%). The per-metric `tolerances=` map overrides individual
metrics. On regression the keyword raises `AssertionError` whose message quotes
every number — both points, both CIs, the tolerance semantics restated
numerically, and both trial counts — so the failure is a numeric bar, not a
vibe.

Wire it into GitHub Actions like any other suite:

```yaml
# .github/workflows/regression-gate.yml
jobs:
  regression-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run robot tests/regression_gate.robot
```

A non-zero exit fails the PR. Nothing else to configure — the assertion is the
gate.

## Step 3 — intentionally moving the baseline

When a change legitimately shifts the metrics (a better prompt, an intended
model upgrade), the baseline update is a **deliberate, human-reviewed commit** —
never an automatic ratchet. Re-run Step 1 to regenerate `baselines/main.json`,
inspect the diff in code review, and commit it in the same PR that made the
change. The committed baseline IS the record of "what we decided good looks
like."

## Step 4 — watch the trend for slow drift

```robotframework
*** Settings ***
Library    AgentEval    provider=mock

*** Test Cases ***
Inspect The Pass At 1 Trend
    ${series}=    Get Metric Trend    metric=pass_at_1    history=baselines/history.jsonl
    Log    ${series.grid.as_ascii()}
    Log    ${series.values()}
```

`Get Metric Trend` reads the append-mode JSONL history into a time-ordered
`TrendSeries` (each point carries the value + recomputed Wilson CI + trial
count + git SHA + model) plus a metrics × snapshots `TrendGrid` that renders as
an ASCII box-drawing grid — the same renderer as `Get Cohort Heatmap`, with the
em-dash sentinel for a metric missing from a snapshot.

## References

- `docs/contracts/metrics-baseline-schema.json` — the published baseline schema.
- OpenSpec `add-regression-baseline-tracking` design Decisions 2-4 (the
  statistical rule) + Decision 7 (run-context reported, not gated).
