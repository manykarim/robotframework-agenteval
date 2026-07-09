# regression-baseline-tracking Specification

## Purpose
TBD - created by archiving change add-regression-baseline-tracking. Update Purpose after archive.
## Requirements
### Requirement: Save Metrics Baseline persists an evidence-bearing snapshot

The system SHALL provide a Tier-1 keyword `Save Metrics Baseline` on a new
`BaselineLibrary` (`AgentEval.baseline.library.BaselineLibrary`) that accepts
`results` as `list[KeywordRun]` (from `Stat.Run N Times`) or
`list[AgentRunResult]` and writes a schema-versioned JSON baseline to the
given `path=`. The snapshot MUST store, per metric family, the underlying
evidence — `successes` + `trials` for proportion metrics (`pass_rate`,
`pass_at_k`, and `tool_hit_rate` when `expected_tools=` is provided) and the
raw per-trial sample lists for continuous metrics (`cost_usd`,
`latency_ms` mean/p50/p95) — alongside the derived point values, so that
confidence intervals and rank tests are recomputable at compare time.

#### Scenario: Snapshot from Stat.Run N Times trials
- **WHEN** `Save Metrics Baseline    ${runs}    path=baselines/main.json` is
  called with `${runs}` being 20 `KeywordRun` trials
- **THEN** the file at `baselines/main.json` SHALL contain
  `schema_version: 1`, a `metrics` object whose `pass_rate` entry carries
  `successes`, `trials`, and the point `value`, and continuous entries
  carrying the raw per-trial sample list

#### Scenario: Pass/fail classification uses the ratified default predicate
- **WHEN** a snapshot is computed from `KeywordRun` trials without an explicit
  `predicate=`
- **THEN** a trial SHALL count as a success iff `completeness == "complete"`,
  matching the `Stat.Get Pass At K` default

#### Scenario: Unavailable metrics are omitted, never zero-filled
- **WHEN** the input runs carry no `AgentRunResult` payloads (so cost and
  tool metrics cannot be derived), or `expected_tools=` is not provided
- **THEN** the corresponding metric entries SHALL be absent from the snapshot
  and the omission SHALL be logged; no metric SHALL be written as `0.0` for
  missing evidence

### Requirement: Baseline file is versionable, deterministic, and redacted

The baseline JSON SHALL be designed for committing to a git repository: it
MUST be serialized deterministically (`indent=2`, sorted keys, trailing
newline) so re-snapshots produce reviewable diffs, MUST carry a top-level
integer `schema_version`, MUST carry a `run_context` object with `model`,
`adapter_name`, `adapter_version`, `library_version`, RFC 3339 `timestamp`,
`git_sha`, and `git_dirty`, and MUST pass through the kernel redaction layer
(`redact_dict`) at the write boundary. Git metadata capture MUST be
best-effort: any git failure yields `null` fields and never fails the
keyword. Write failures SHALL raise a structured `BaselineWriteError` (not
warn-and-continue), because a silently missing baseline would fake-green the
CI gate built on it.

#### Scenario: Deterministic re-serialization
- **WHEN** the same results are snapshotted twice to two paths
- **THEN** the two files SHALL be byte-identical except for the
  `run_context.timestamp` (and `git_*`) fields

#### Scenario: Git metadata absent outside a repository
- **WHEN** `Save Metrics Baseline` runs in a directory that is not a git
  repository
- **THEN** the snapshot SHALL be written successfully with
  `git_sha: null` and `git_dirty: null`

#### Scenario: Unwritable path fails loud
- **WHEN** `path=` points into a directory that cannot be created or written
- **THEN** the keyword SHALL raise `BaselineWriteError` with the
  File/Line/Field/Fix structured message format

### Requirement: Metrics Should Not Regress performs tolerance- and CI-aware comparison

The system SHALL provide a Tier-1 keyword `Metrics Should Not Regress` that
loads a baseline file (`baseline=`), computes the same metric set from the
supplied `results`, and applies a per-metric, direction-aware decision rule.
For proportion metrics the keyword SHALL fail only when the direction-aware
point delta exceeds `tolerance=` (absolute percentage points) AND the Wilson
score confidence intervals of baseline and current (default
`confidence=0.95`, recomputed from stored `successes`/`trials`) are disjoint
in the regressing direction. For continuous metrics (lower-is-better by
default) the point delta SHALL be measured against a tolerance relative to
the baseline value, and when raw samples are available on both sides and the
`[advanced]` extra is installed a one-sided Mann-Whitney U test at
`alpha=0.05` MUST also reject before the keyword fails. Per-metric tolerance
overrides SHALL be accepted via a `tolerances=` mapping. The keyword SHALL
return a `RegressionReport` whose per-metric entries record both points, both
CIs, the tolerance applied, the comparison mode, and the verdict.

#### Scenario: Genuine regression fails with numeric evidence
- **WHEN** the baseline stores `pass_rate` 45/50 (0.90) and the current run
  yields 5/50 (0.10) with `tolerance=5%`
- **THEN** the keyword SHALL fail, and the failure message SHALL quote the
  baseline point and CI, the current point and CI, the absolute-points
  tolerance semantics, and both trial counts

#### Scenario: Small noisy drop passes with PossibleRegressionWarning
- **WHEN** the baseline stores 9/10 (0.90) and the current run yields 7/10
  (0.70) with `tolerance=5%` (tolerance breached but the Wilson CIs overlap)
- **THEN** the keyword SHALL pass and emit `PossibleRegressionWarning`
  quoting both points, both overlapping CIs, and the trial counts

#### Scenario: Within-tolerance change passes clean
- **WHEN** every compared metric's direction-aware delta is within its
  tolerance
- **THEN** the keyword SHALL pass without regression warnings and the
  returned `RegressionReport` SHALL mark every metric `pass`

#### Scenario: Improvement never fails
- **WHEN** the current run's higher-is-better metrics exceed the baseline and
  lower-is-better metrics are below it
- **THEN** the keyword SHALL pass regardless of the magnitude of the change

#### Scenario: Continuous regression uses relative tolerance and rank test
- **WHEN** baseline and current snapshots both carry raw latency samples, the
  `[advanced]` extra is installed, and current p95 latency exceeds baseline
  by more than the relative tolerance with a significant one-sided
  Mann-Whitney U result
- **THEN** the keyword SHALL fail naming `latency_p95_ms`, both values, the
  relative-tolerance semantics, and the test statistic

### Requirement: Statistical degradation and underpower are loud, never silent

Comparisons that cannot apply their full statistical machinery SHALL degrade
loudly. When continuous-sample inference is unavailable (missing raw samples
on either side, or `[advanced]` extra not installed) the keyword SHALL fall
back to tolerance-only comparison and emit `DegradedComparisonWarning` naming
what was skipped and why, recording `comparison_mode: "point_only"` in the
report. When the minimum detectable difference at the compared sample sizes
exceeds the requested tolerance for a proportion metric, the keyword SHALL
emit `UnderpoweredComparisonWarning` stating the approximate trial count
required. Metrics present in the baseline but absent from the current results
(or vice versa) SHALL be reported as `skipped` with the reason, never
auto-failed and never dropped silently.

#### Scenario: Point-only fallback without the advanced extra
- **WHEN** `Metrics Should Not Regress` compares continuous metrics and the
  `[advanced]` extra is not installed
- **THEN** the comparison SHALL proceed tolerance-only and emit
  `DegradedComparisonWarning` naming the missing extra, and the report SHALL
  record `comparison_mode: "point_only"` for those metrics

#### Scenario: Underpowered proportion comparison is flagged
- **WHEN** a proportion metric is compared with `tolerance=5%` and trial
  counts so small that the Wilson CI half-width exceeds the tolerance
- **THEN** the keyword SHALL emit `UnderpoweredComparisonWarning` including
  the approximate `n` needed to detect a 5-point drop

#### Scenario: Metric missing on one side is skipped with reason
- **WHEN** the baseline contains `tool_hit_rate` but the current invocation
  provides no `expected_tools=`
- **THEN** the report SHALL list `tool_hit_rate` as `skipped` with the
  reason, and the keyword outcome SHALL not depend on it

### Requirement: Run-context mismatch is reported, not gated

`Metrics Should Not Regress` SHALL compare the baseline's `run_context`
(model, adapter name/version, library version, trial counts) against the
current run's context and include both side by side in the report and log.
A mismatch MUST NOT by itself fail the keyword — comparing across a model or
adapter update is the primary use case.

#### Scenario: Model changed between baseline and current run
- **WHEN** the baseline was captured with `model=claude-sonnet-4-6` and the
  current run uses `model=claude-sonnet-4-7`
- **THEN** the comparison SHALL proceed, and the report/log SHALL state both
  model identifiers side by side

### Requirement: Baseline loading fails structurally on missing or drifted files

Baseline reads SHALL raise structured errors following the project's
File/Line/Field/Fix message design: `BaselineNotFoundError` when `baseline=`
does not exist (with the fix suggestion to run `Save Metrics Baseline` and
commit the file), and `BaselineSchemaError` when the JSON is unparseable,
`schema_version` is unsupported, or a required field is missing/of the wrong
shape (naming the offending field).

#### Scenario: Missing baseline file
- **WHEN** `Metrics Should Not Regress` is called with a `baseline=` path
  that does not exist
- **THEN** the keyword SHALL raise `BaselineNotFoundError` whose message
  includes the resolved path and the save-then-commit fix suggestion

#### Scenario: Schema version from a future release
- **WHEN** the baseline file carries `schema_version: 99`
- **THEN** the keyword SHALL raise `BaselineSchemaError` naming the found and
  supported versions

### Requirement: Append-mode history and Get Metric Trend

`Save Metrics Baseline` SHALL accept an optional `history=` path and, when
given, append the snapshot as one compact JSON line to that JSONL file
(creating it if absent, never truncating existing lines). The system SHALL
provide a Tier-1 keyword `Get Metric Trend` that reads a history file and
returns a `TrendSeries` for a named metric: time-ordered points each carrying
`timestamp`, `git_sha`, `value`, `ci_lower`/`ci_upper` (recomputed from
stored evidence where available, else `None`), `n_trials`, and `model`, with
`.as_dict()` and `.values()` accessors usable from Robot Framework
assertions. Snapshots in the history that lack the requested metric SHALL be
represented as missing points, not zeros.

#### Scenario: History accumulates across snapshots
- **WHEN** `Save Metrics Baseline` is called three times with
  `history=baselines/history.jsonl`
- **THEN** the history file SHALL contain exactly three lines, each a
  self-contained JSON snapshot, in append order

#### Scenario: Trend series for a proportion metric
- **WHEN** `Get Metric Trend    metric=pass_at_1    history=baselines/history.jsonl`
  is called against a 3-snapshot history
- **THEN** the returned series SHALL contain 3 ordered points with `value`
  and Wilson `ci_lower`/`ci_upper` recomputed from each snapshot's stored
  `successes`/`trials`

#### Scenario: Metric absent from one snapshot
- **WHEN** the requested metric exists in only 2 of 3 history snapshots
- **THEN** the series SHALL surface the gap as a missing point (not `0.0`),
  consistent with the `_heatmap` missing-cell honesty sentinel

### Requirement: Optional trend grid rendering reuses the heatmap idiom

The trend surface SHALL offer, via the `TrendSeries`/`TrendGrid` returned by
`Get Metric Trend`, an ASCII box-drawing grid rendering and a nested-dict
rendering of metrics-over-snapshots, with the same `.as_ascii()`/`.as_dict()` method
surface as `CohortHeatmap` and the em-dash sentinel for missing cells. The
implementation SHALL reuse the `_heatmap` grid-rendering internals rather
than duplicating a second ASCII renderer; `CohortHeatmap`'s public behavior
MUST remain unchanged.

#### Scenario: ASCII trend grid renders with missing-cell sentinel
- **WHEN** a trend grid is rendered over a history where one snapshot lacks
  `cost_usd`
- **THEN** `.as_ascii()` SHALL return a box-drawing grid whose missing cell
  renders the em-dash sentinel, and `.as_dict()` SHALL omit or `None` the
  missing cell rather than reporting `0.0`

#### Scenario: CohortHeatmap regression guard
- **WHEN** the existing `Get Cohort Heatmap` unit tests run after the
  renderer extraction
- **THEN** they SHALL pass unchanged

### Requirement: Library surface, tiering, and documentation contracts

All three keywords SHALL be `@tier(1)`-decorated (deterministic, no LLM
calls, no polling). `BaselineLibrary` SHALL be importable standalone
(`Library    AgentEval.baseline.library.BaselineLibrary`) with keyword names
that collide with no existing AgentEval keyword. The baseline file format
SHALL be published as `docs/contracts/metrics-baseline-schema.json` and
validated in unit tests against real emitter output. A CI recipe SHALL be
added under `docs/recipes/` showing a PR gate that runs the suite against the
committed `baselines/main.json`, fails on regression beyond tolerance, and
documents the deliberate re-snapshot-and-commit workflow for intentional
baseline updates; its code blocks MUST pass the executable-doc smoke check
(`robot --dryrun` / `python -c`).

#### Scenario: Keywords report Tier 1
- **WHEN** `Get Keyword Tier` is queried for each of the three new keywords
- **THEN** each SHALL report tier 1

#### Scenario: Emitted baseline validates against the published schema
- **WHEN** a baseline produced by `Save Metrics Baseline` is validated
  against `docs/contracts/metrics-baseline-schema.json`
- **THEN** validation SHALL pass

#### Scenario: CI recipe dryrun-clean
- **WHEN** the recipe's Robot Framework code blocks are executed with
  `robot --dryrun`
- **THEN** they SHALL parse and resolve all keywords without error

