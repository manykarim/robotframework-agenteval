## Why

AgentEval can measure an agent run (pass rate, Pass@k, cost, latency, tool hit
rate) and already emits a per-run reproducibility record (`RunManifest`, FR39),
but **nothing compares run N to run N-1**: a model update, adapter bump, or
prompt tweak that silently drops Pass@k from 0.9 to 0.6 is invisible until a
human eyeballs two reports. Competing tools treat this as table stakes — MCPJam
tracks accuracy over time, DeepEval gates CI on metric regression, and
skill-creator's benchmark mode exists specifically to detect regression after
model updates (findings dossier E6 MAJOR). AgentEval has every ingredient
(metrics getters, `Stat.Run N Times` trials, Wilson CI + bootstrap machinery,
JSONL append idiom, `_heatmap` renderers) but no baseline snapshot, no
comparison keyword, and no trend surface.

For stochastic agent metrics a naive point-compare would be dishonest: a
2-point Pass@k drop over 10 trials is usually noise. The comparison must be
CI-overlap-aware — the project's honest-framing brand applied to trend
tracking.

## What Changes

- Add a new Tier-1 `BaselineLibrary` (package `src/AgentEval/baseline/`) with
  three keywords:
  - `Save Metrics Baseline    ${results}    path=baselines/main.json` —
    computes the standard named metrics (pass rate, Pass@k, total cost,
    latency percentiles, optional tool hit rate) from `Stat.Run N Times`
    trials or `AgentRunResult` lists, and persists them **with the raw
    per-trial samples and counts** (so CI-aware comparison is possible later)
    plus run metadata (model, adapter name/version, library version,
    timestamp, git SHA) in a deterministic, diff-friendly, schema-versioned
    JSON file designed for committing to the repo.
  - `Metrics Should Not Regress    ${results}    baseline=baselines/main.json    tolerance=5%` —
    per-metric comparison with configurable tolerance and per-metric
    direction (higher-is-better vs lower-is-better). Statistically honest:
    proportion metrics regress only when the drop exceeds tolerance AND the
    Wilson confidence intervals do not overlap; continuous metrics use the
    stored raw samples with the existing bootstrap/Mann-Whitney primitives.
    Underpowered comparisons (N too small to detect the tolerance) emit an
    explicit warning instead of a fake-green pass.
  - `Get Metric Trend    metric=pass_at_1    history=baselines/history.jsonl` —
    returns the time-ordered series of a named metric (value + CI + run
    metadata per point) from an append-mode JSONL history file, with an
    optional trend-grid rendering reusing the `_heatmap` ASCII/dict idiom.
- Add append-mode history: `Save Metrics Baseline` optionally appends the
  snapshot as one JSONL line to a history file (JSONL is the established
  project append idiom, telemetry `JSONLBackend`).
- Publish the baseline JSON schema as a contract doc
  (`docs/contracts/metrics-baseline-schema.json`) alongside the existing
  `run-manifest-schema.json`.
- Add a CI recipe (`docs/recipes/`) that fails a PR when metrics regress
  beyond tolerance vs the committed `baselines/main.json`, including the
  update-the-baseline workflow for intentional changes.
- Structured errors for missing/corrupt/incompatible baselines following the
  `errors.py` File/Line/Field/Fix message design.

Purely additive — no existing keyword, metric getter, or manifest field
changes.

## Capabilities

### New Capabilities

- `regression-baseline-tracking`: Snapshot named metric values + run metadata
  to a versionable baseline JSON, compare a new run against a committed
  baseline with tolerance- and CI-aware per-metric regression detection, and
  expose metric history as an append-mode JSONL trend series with ASCII/dict
  rendering.

### Modified Capabilities

None. `openspec/specs/` contains only `opencode-cli-adapter`, which is
untouched. This change consumes existing surfaces (metrics getters, stats
primitives, `RunManifest`, `_heatmap` renderers) without altering their
requirements.

## Impact

- **New code**: `src/AgentEval/baseline/` (`library.py`, `models.py`,
  `comparison.py`, `schema.py`), `tests/unit/baseline/`,
  `docs/contracts/metrics-baseline-schema.json`, one CI-gate recipe under
  `docs/recipes/`, dogfood coverage under `tests/dogfood/`.
- **Modified code**: none required in existing runtime modules. Keyword-count
  surfaces (README table, `docs/index.md`) and
  `docs/contracts/stability-surface.md` gain the three new keywords.
- **Dependencies**: none new. Proportion CIs reuse the pure-stdlib
  `stats/wilson.py`; continuous-metric comparison reuses
  `stats/bootstrap.py`/`stats/mannwhitney.py` (already `[advanced]`-extra
  guarded) with a documented stdlib fallback. Git SHA capture is a
  best-effort `git rev-parse HEAD` subprocess — absence of git never fails a
  run.
- **APIs**: adds one public library class (`BaselineLibrary`), three keywords,
  and three public dataclasses (`MetricsBaseline`, `MetricComparison`,
  `RegressionReport`) to the stability surface.
- **Out of scope** (explicit): hosted dashboards (PRD non-goal), HTML trend
  UI (ASCII/dict + JSON is the project idiom), and A/B skill comparison
  (sibling change `add-skill-ab-benchmark`).
