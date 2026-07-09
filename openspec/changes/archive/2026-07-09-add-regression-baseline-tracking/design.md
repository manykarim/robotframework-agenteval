## Context

AgentEval already produces everything a regression gate needs, in pieces:

- **Metrics getters** (`src/AgentEval/metrics/library.py`): `Get Tool Hit
  Rate`, `Get Tool Success Rate`, `Get Latency`, `Get Latency P95`, `Get Cost
  Total`, `Get Token Usage` — all accept `AgentRunResult | list[AgentRunResult]`.
- **Trial machinery** (`src/AgentEval/stats/`): `Stat.Run N Times` returns
  `list[KeywordRun]` (each carrying `completeness`, `latency_seconds`,
  `result`, `error`, `seed`); `Stat.Get Pass At K` computes the HumanEval
  estimator; `Stat.Get Pass At K Confidence Interval` wraps the pure-stdlib
  Wilson score interval (`stats/wilson.py`); `stats/bootstrap.py` and
  `stats/mannwhitney.py` provide continuous-sample inference behind the
  `[advanced]` extra.
- **Run metadata** (`src/AgentEval/telemetry/run_manifest.py`, FR39):
  per-test `RunManifest` with `library_version`, `adapter_name`,
  `adapter_version`, `model`, `total_cost_usd`, timestamps — plus the `Get Run
  Manifest` keyword.
- **Append idiom** (`telemetry/backends.py::JSONLBackend`): one JSON object
  per line under `<output_dir>/agenteval/`.
- **Grid rendering** (`src/AgentEval/_heatmap/`): `CohortHeatmap` with
  `.as_ascii()` (box-drawing) + `.as_dict()` renderers and the em-dash
  missing-cell honesty sentinel (Story 10.1).

What is missing is the connective tissue: persist a named-metric snapshot,
compare a new run against it without lying about noise, and expose the series
over time. Constraints: RF 7.x keyword surface, Tier-1 determinism (no LLM
calls), pure-stdlib default path (`[advanced]` extra optional), honest-framing
norms (numeric bars, no fake-green), files designed to be committed to git.

## Goals / Non-Goals

**Goals:**
- One new Tier-1 library (`BaselineLibrary`) with three keywords: `Save
  Metrics Baseline`, `Metrics Should Not Regress`, `Get Metric Trend`.
- Baseline JSON that is diff-friendly, schema-versioned, redacted, and stores
  **sufficient statistics + raw per-trial samples** so compare-time inference
  is possible (not just point estimates).
- CI-overlap-aware regression decisions for proportion metrics; rank-based /
  tolerance comparison for continuous metrics; explicit warnings when a
  comparison is statistically underpowered or degraded.
- Append-mode JSONL history + trend series + ASCII/dict trend grid.
- A CI recipe gating PRs on the committed `baselines/main.json`.

**Non-Goals:**
- Hosted dashboards or HTML trend UI (PRD non-goal; ASCII/dict + JSON is the
  project idiom).
- A/B skill comparison (sibling change `add-skill-ab-benchmark`).
- Automatic baseline refresh/ratcheting (the update is a deliberate,
  human-reviewed commit — that is the point of a committed baseline).
- Sequential-testing / multiple-comparison correction across many metrics
  (documented as a Phase-2 carry-over; per-metric alpha is fixed and named in
  the report).
- New runtime dependencies.

## Decisions

### Decision 1: Store evidence, not verdicts — baselines carry counts + raw samples

A baseline that stores only `pass_rate: 0.9` cannot support an honest
comparison later. `MetricsBaseline` therefore persists, per metric family:

- **Proportions** (`pass_rate`, `pass_at_k`, `tool_hit_rate`): `successes` +
  `trials` (ints), alongside the derived point value. Wilson CIs for both
  sides are then recomputable at compare time at any confidence level, and
  Pass@k is recomputable for any k ≤ trials.
- **Continuous** (`cost_usd`, `latency_ms` family): the raw per-trial sample
  list (floats), alongside derived `total`/`mean`/`p50`/`p95` points. This is
  what makes Mann-Whitney U / bootstrap comparison possible run-over-run.

Sample lists are small in practice (N = trials, typically 5-50); no cap is
imposed in Phase 1 but the schema reserves a `samples_truncated: bool` field
so a future cap is non-breaking. *Alternative considered:* store point
estimates + precomputed CI only — rejected because the CI of a difference
cannot be derived from two marginal CIs, and it freezes the confidence level
at snapshot time.

### Decision 2: Regression rule = tolerance breach AND CI-disjoint (proportions)

For a higher-is-better proportion metric, `Metrics Should Not Regress` FAILS
only when **both** hold:

1. `baseline_point − current_point > tolerance` (tolerance breach), and
2. the Wilson CIs (default `confidence=0.95`, configurable) are **disjoint**
   in the regressing direction (`current_ci_upper < baseline_ci_lower`).

Outcomes are three-valued and always numerically reported:

- **FAIL** — breach + disjoint CIs: the drop is larger than tolerated and
  unlikely to be noise.
- **PASS-with-WARNING** (`PossibleRegressionWarning`) — tolerance breached
  but CIs overlap: "a 2-point Pass@k drop over 10 trials may be noise" lands
  here; the warning quotes both points, both CIs, and N so the human can
  raise trials rather than chase ghosts.
- **PASS** — within tolerance.

Additionally, when the minimum detectable difference at the current sample
sizes exceeds the requested tolerance (approximated from the Wilson
half-widths), the keyword emits `UnderpoweredComparisonWarning` stating the N
required — the gate never silently pretends it could have caught what it
mathematically cannot. *Alternative considered:* two-proportion z-test /
Fisher exact — rejected for Phase 1 because CI-overlap on the already-shipped
Wilson machinery is dependency-free, conservative (overlap ⇒ don't fail),
and directly explainable in the failure message; an exact test is a Phase-2
carry-over.

### Decision 3: Continuous metrics — direction-aware tolerance + rank test when possible

`cost_usd` and `latency_*` are lower-is-better (direction registry per metric
name, overridable). Decision rule:

1. Tolerance breach: `current − baseline > tolerance` (relative tolerance,
   see Decision 4).
2. Noise guard: when **both** snapshots carry raw samples **and** the
   `[advanced]` extra is installed, a one-sided Mann-Whitney U
   (`stats/mannwhitney.py`) at `alpha=0.05` must also reject before FAILing;
   otherwise the comparison degrades to tolerance-only and emits
   `DegradedComparisonWarning` naming exactly what was skipped and why
   (missing samples vs missing extra). Degraded ≠ silent: the report records
   `comparison_mode: "point_only"`.

*Alternative considered:* bootstrap CI on the difference — viable but also
`[advanced]`-gated and slower; Mann-Whitney is the already-ratified two-sample
primitive. Point-only as the universal rule was rejected: it is exactly the
naive compare the proposal forbids for stochastic metrics.

### Decision 4: Tolerance semantics — absolute points for proportions, relative for continuous

`tolerance=5%` means: **5 percentage points absolute** for proportion metrics
(0.05 on the [0,1] scale — "Pass@1 may drop from 0.90 to 0.85") and **5%
relative to the baseline value** for continuous metrics ("cost may grow
5%"). Mixed semantics on one flag are justified because relative tolerance on
proportions misbehaves near 0/1, and absolute tolerance on cost is
meaningless across scenarios of different sizes. A per-metric override map
(`tolerances={"cost_usd": "10%"}`) covers the exceptions; both semantics are
stated in the keyword doc table and in every failure message (numeric bars,
per `feedback_honest_framing`). *Alternative considered:* single relative
semantics — rejected (0% baseline ⇒ division by zero; 90%→85.5% relative-5%
reads as arbitrary).

### Decision 5: Input shape — `list[KeywordRun]` canonical, `list[AgentRunResult]` accepted

`Save Metrics Baseline` and `Metrics Should Not Regress` accept the same
`results` union as the ecosystem produces:

- `list[KeywordRun]` (from `Stat.Run N Times`): pass/fail derives from the
  ratified default predicate (`completeness == "complete"`, overridable via
  `predicate=`); latency from `latency_seconds`; cost/tool metrics extracted
  from `r.result` when it is an `AgentRunResult` (else those metrics are
  omitted from the snapshot, and the omission is listed in the keyword's
  return/log — never zero-filled, per the `_heatmap` em-dash honesty
  precedent).
- `list[AgentRunResult]` (from repeated `Send Prompt` / `Run Scenario`):
  reuses the same internal extraction the metrics getters use.

`tool_hit_rate` requires `expected_tools=`; it is included only when the
caller provides them. *Alternative considered:* accept a prebuilt
`dict[str, float]` of metrics — deferred; it bypasses evidence capture
(Decision 1) and invites point-only baselines. The schema keeps an
`extra_metrics` object for user-supplied named scalars, which are compared
point-only with `comparison_mode: "point_only"` recorded.

### Decision 6: File formats — deterministic pretty JSON baseline, JSONL history

- **Baseline** (`baselines/main.json`): `json.dump(..., indent=2,
  sort_keys=True)` + trailing newline — stable diffs for PR review. Top-level
  `schema_version: 1`, `metrics: {...}`, `run_context: {...}` (model,
  adapter_name, adapter_version, library_version, timestamp RFC 3339,
  git_sha, git_dirty), `extra_metrics: {...}`. Payload passes through
  `redact_dict` at the write boundary (same defense-in-depth as
  `RunManifestEmitter`) — a committed file must never carry a credential.
- **History** (`history=baselines/history.jsonl`): optional `history=` param
  on `Save Metrics Baseline` appends the same snapshot as **one compact JSON
  line** (the `JSONLBackend` idiom). Append-only; `Get Metric Trend` is the
  reader.
- **Write failures RAISE** (structured `BaselineWriteError`). This is the
  opposite of the telemetry-sidecar warn-don't-raise contract, deliberately:
  a sidecar is passive hygiene, but the user explicitly asked to persist a
  baseline — silently continuing would fake-green the very artifact CI gates
  on. Read failures raise structured errors with the File/Line/Field/Fix
  message design (`BaselineNotFoundError` with the "run `Save Metrics
  Baseline` first, then commit the file" fix suggestion;
  `BaselineSchemaError` on `schema_version` mismatch or shape drift).

### Decision 7: Run context is informational, never a gate

`run_context` mismatches between baseline and current run (different `model`,
`adapter_version`, trial count) are **logged in the comparison report, never
auto-failed**. Rationale: the headline use case is exactly a cross-context
comparison — "did the model update regress my metrics?" (skill-creator
benchmark-mode idiom, dossier E6). The report always prints both contexts
side by side so an apples-to-oranges comparison is visible, not blocked.
Trial-count asymmetry (baseline N=50 vs current N=10) is handled by the CI
machinery itself — Wilson widths reflect each side's own N.

### Decision 8: Trend surface — `TrendSeries` + grid render reusing `_heatmap`

`Get Metric Trend    metric=pass_at_1    history=...` returns a `TrendSeries`
dataclass: ordered `points` (each `{timestamp, git_sha, value, ci_lower,
ci_upper, n_trials, model}`), plus `.as_dict()` and `.values()` accessors —
RF-assertable and JSON-dumpable. An optional grid rendering (rows = metrics,
columns = snapshots, cells = values with the em-dash sentinel for
missing-in-that-snapshot) reuses the `_heatmap` box-drawing renderer: the
shared cell-grid formatting is extracted into `_heatmap` internals (private
package, internal move — `CohortHeatmap` public behavior unchanged) and
consumed by a `TrendGrid` model with the same `.as_ascii()`/`.as_dict()`
method surface. *Alternative considered:* duplicate a small renderer inside
`baseline/` — rejected; two ASCII grid renderers is exactly the
`wilson_ci.py`-duplication complexity smell the audit (dossier E5) flagged.

### Decision 9: Keyword naming, tier, and import shape

- Names are unprefixed — `Save Metrics Baseline`, `Metrics Should Not
  Regress`, `Get Metric Trend` — matching the metrics-library idiom and the
  scope's literal surface; no collision with any of the 56 existing keyword
  names, so the library stays composition-safe for the
  `compose-single-library-import` sibling change.
- All three keywords are `@tier(1)` (deterministic file IO + arithmetic; no
  LLM, no polling).
- Library lives at `AgentEval.baseline.library.BaselineLibrary` (public
  package, no underscore — the models are part of the stability surface),
  documented for standalone import `WITH NAME Baseline`.

### Decision 10: Git SHA capture — best-effort subprocess, never fatal

`git rev-parse HEAD` + `git status --porcelain` (dirty flag) via
`subprocess.run` with a short timeout; any failure (no git, not a repo,
timeout) yields `git_sha: null, git_dirty: null`. A missing SHA never blocks
a snapshot — CI environments without `.git` (shallow artifacts) must still be
able to compare. *Alternative considered:* `GITHUB_SHA`-style env fallback —
accepted as a secondary source when the subprocess fails, since the CI recipe
is a primary consumer.

## Risks / Trade-offs

- **[Flaky CI gate erodes trust]** → The AND-rule (Decision 2) makes overlap
  ⇒ no-fail, biasing toward false negatives, and the
  `PossibleRegressionWarning` + `UnderpoweredComparisonWarning` channel makes
  the residual uncertainty visible instead of silent. The CI recipe documents
  "raise `n` in `Stat.Run N Times`" as the flakiness fix, not "raise
  tolerance".
- **[False negatives by design]** → Conservative gating means small real
  regressions can pass for a while; the trend surface (`Get Metric Trend`)
  exists precisely to catch slow drift that any single gate misses. Named
  explicitly in the recipe.
- **[Baseline schema drift over releases]** → `schema_version` int +
  `BaselineSchemaError` with Fix block; the published contract schema
  (`docs/contracts/metrics-baseline-schema.json`) is validated in unit tests
  against real emitter output (contract-doc smoke-test norm).
- **[Raw samples bloat committed files]** → Bounded by trial counts (tens,
  not thousands) in real usage; `samples_truncated` reserved for a future
  cap. Baselines are one file per suite, not per test, by default path
  convention.
- **[Mixed tolerance semantics confuse users]** → Every failure/warning
  message restates the semantics numerically ("tolerance 5% = 0.05 absolute
  on pass_at_1"; "= $0.012 on cost_usd baseline $0.24"), per
  `feedback_honest_framing`.
- **[`[advanced]`-extra split creates two behaviors]** → The degradation is
  loud (`DegradedComparisonWarning` + `comparison_mode` recorded in the
  report), and proportion metrics — the headline gate — are full-strength on
  pure stdlib.
- **[Comparing across models flagged as apples-to-oranges]** → Deliberate
  (Decision 7): context mismatch is reported, not blocked; that comparison is
  the feature's primary use case after a model update.

## Open Questions

- Default path convention: `baselines/main.json` (repo-root relative, as in
  the scope's invocation) is the documented convention, but the keyword takes
  an explicit `path=` — should a future `agenteval init` scaffold a
  `baselines/` dir? Deferred to the `fix-first-run-experience` sibling.
- Multi-metric family growth (judge scores from Epic 12, activation Pass@k
  from Skill keywords): the `extra_metrics` point-only channel accepts them
  today; first-class evidence-bearing entries are a Phase-2 carry-over to be
  cataloged at implementation time (`DF-*` marker).
