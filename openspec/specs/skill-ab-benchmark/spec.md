# skill-ab-benchmark Specification

## Purpose
TBD - created by archiving change add-skill-ab-benchmark. Update Purpose after archive.
## Requirements
### Requirement: Skill.Compare Against Baseline keyword surface

The `SkillsLibrary` SHALL provide a `Skill.Compare Against Baseline` keyword
(`@keyword`-decorated, `@tier(3)`, `@guarded_fanout()`) with the signature
`skill: str|Path`, `tasks: str|Path`, `baseline: str|Path = "none"`,
`trials: int = 3`, `adapter: str = "generic"`, `model: str|None = None`,
`seed: int = 42`, `alpha: float = 0.05`,
`obsolescence_threshold: float = 0.9`, `max_cost_usd: float = 20.00`,
`max_runtime_seconds: float|None = None`, `polling: float|None = None`,
`**kwargs` (forwarded to the adapter constructor). The keyword MUST validate
its inputs before any adapter fan-out: missing `skill`/`tasks` and
`trials < 1` SHALL raise `ValueError`; providing `polling` SHALL raise
`PollingDisallowedError` (FR28); `alpha` outside `(0, 1)` and
`obsolescence_threshold` outside `[0, 1]` SHALL raise `ValueError`. The
post-dot keyword name is multi-word, complying with the ratified libdoc
namespace-keyword norm.

#### Scenario: Valid two-arm invocation returns a benchmark result
- **WHEN** `Skill.Compare Against Baseline` is called with a valid skill
  path, a valid benchmark tasks YAML, `baseline=none`, and `trials=3`
- **THEN** it SHALL return a `SkillBenchmarkComparisonResult` covering both
  arms without raising

#### Scenario: Polling is rejected per FR28
- **WHEN** the keyword is called with `polling=2.0`
- **THEN** it SHALL raise `PollingDisallowedError` before any adapter call

#### Scenario: Invalid trials count is rejected before fan-out
- **WHEN** the keyword is called with `trials=0`
- **THEN** it SHALL raise `ValueError` and no adapter SHALL be constructed

### Requirement: Two-arm execution model with no-skill and skill-vs-skill modes

The keyword SHALL run the SAME task cohort in exactly two arms: a `candidate`
arm using the skill at `skill=`, and a `baseline` arm determined by
`baseline=`: the literal string `"none"` (default) SHALL run the baseline arm
WITHOUT any skill (skill-vs-no-skill mode); a filesystem path SHALL run the
baseline arm with that other skill (v1-vs-v2 mode). Each arm SHALL execute
`trials` runs per task against the same adapter and model, and the two arms
MUST differ only in skill availability.

#### Scenario: baseline=none runs a bare no-skill arm
- **WHEN** the keyword runs with `baseline=none`
- **THEN** every baseline-arm trial SHALL send the task prompt WITHOUT any
  skill content, while every candidate-arm trial includes the candidate skill

#### Scenario: baseline as a path runs v1-vs-v2
- **WHEN** the keyword runs with `baseline=${path_to_v1}` and
  `skill=${path_to_v2}`
- **THEN** the baseline arm SHALL deliver the v1 skill and the candidate arm
  the v2 skill, using the SAME delivery mechanism in both arms

#### Scenario: Both arms share the task cohort
- **WHEN** the tasks YAML defines N tasks
- **THEN** each arm SHALL run all N tasks × `trials` runs (2 × N × trials
  adapter runs total)

### Requirement: Skill delivery honesty field

The result SHALL carry a `skill_delivery` field with a closed, runtime-
validated value space; Phase-1 SHALL emit `"prompt_injected"`, meaning skill
arms receive the skill's frontmatter + body prepended to the task prompt in a
delimited block. Constructing the result with a value outside the closed set
SHALL raise `ValueError` (mirroring the `AgentRunMetadata.mcp_coverage`
runtime closed-set check). The keyword documentation MUST state that
prompt-injection is not native skill installation.

#### Scenario: Phase-1 delivery mode is reported
- **WHEN** a benchmark completes
- **THEN** `result.skill_delivery` SHALL equal `"prompt_injected"`

#### Scenario: Invalid delivery value is rejected at construction
- **WHEN** a `SkillBenchmarkComparisonResult` is constructed with
  `skill_delivery="magic"`
- **THEN** `ValueError` SHALL be raised

### Requirement: Benchmark task cohort YAML schema and loader

The system SHALL provide a benchmark tasks loader (sibling of
`load_skill_discoverability_tasks`) that validates a YAML cohort where each
task carries `id` (unique string), `prompt` (string), and exactly ONE grading
mode: `expected_content` (non-empty list of strings; trial passes when ALL
entries appear case-insensitively in the trial's `response_text`) OR `rubric`
(path to a judge rubric `.md`). A file-level `defaults.rubric` MAY supply the
rubric for tasks that declare no grading mode. Structural failures SHALL
raise a dedicated error type carrying `file_path`, an RFC-6901 JSON-Pointer
`field_name`, and a `fix_suggestion`, consistent with the project error
format.

#### Scenario: Valid cohort loads in YAML order
- **WHEN** a YAML with 3 tasks (2 `expected_content`, 1 `rubric`) is loaded
- **THEN** the loader SHALL return 3 validated tasks in file order

#### Scenario: Task with both grading modes is rejected
- **WHEN** a task declares BOTH `expected_content` and `rubric`
- **THEN** the loader SHALL raise the benchmark-tasks error with a JSON
  Pointer to the offending task and a fix suggestion

#### Scenario: Task with no grading mode and no default is rejected
- **WHEN** a task declares neither grading mode and the file has no
  `defaults.rubric`
- **THEN** the loader SHALL raise the benchmark-tasks error identifying the
  task

#### Scenario: Duplicate task ids are rejected
- **WHEN** two tasks share the same `id`
- **THEN** the loader SHALL raise the benchmark-tasks error naming the
  duplicated id

### Requirement: Per-arm outcome metrics

The result SHALL expose one arm summary per arm (`candidate`, `baseline`)
containing at minimum: `pass_rate` (fraction of passing trials), per-task
pass rates, total and mean token usage (input + output, aggregated from each
trial's `AgentRunResult.usage`), total elapsed seconds (aggregated from
`latency_seconds`), total `cost_usd`, and `trials_run`. The top-level result
SHALL expose `pass_rate_delta` (candidate − baseline), a wall-clock
`total_runtime_seconds` anchored at keyword entry, and `total_cost_usd`
combining adapter and judge spend with judge spend also broken out.

#### Scenario: Arm summaries carry pass rate, tokens, time, cost
- **WHEN** a benchmark completes over 4 tasks × 3 trials per arm
- **THEN** each arm summary SHALL report `trials_run == 12`, a `pass_rate`
  in `[0, 1]`, token totals, elapsed seconds, and cost aggregated from that
  arm's 12 `AgentRunResult`s

#### Scenario: Judge spend counted and broken out
- **WHEN** at least one task uses rubric grading
- **THEN** `total_cost_usd` SHALL include the judge calls' cost and the
  judge-only cost SHALL be separately readable

### Requirement: Statistical significance via existing stats primitives

The result SHALL include: a Mann-Whitney U result
(`AgentEval.stats.mannwhitney.compute_mann_whitney_u`) over the two arms'
per-task pass-rate distributions; Cliff's delta
(`AgentEval.stats.cliffs_delta`) over the same samples; and a seeded
percentile bootstrap confidence interval
(`AgentEval.stats.bootstrap.compute_bootstrap_ci`) on the pass-rate delta.
These SHALL reuse the Epic-13 pure helpers (no reimplementation). The keyword
SHALL raise `ImportError` when the `[agenteval-advanced]` extra is missing,
BEFORE any adapter fan-out.

#### Scenario: Significance fields populated from Epic-13 helpers
- **WHEN** a benchmark completes with the advanced extra installed
- **THEN** the result SHALL carry `mann_whitney` (with `p_value`),
  `cliffs_delta`, and `bootstrap_ci` as a `(lo, hi)` tuple with `lo <= hi`

#### Scenario: Missing extra fails fast before spending
- **WHEN** the keyword is invoked without scipy/numpy available
- **THEN** it SHALL raise `ImportError` and zero adapter runs SHALL occur

#### Scenario: Seed makes bootstrap reproducible
- **WHEN** the same benchmark data is processed twice with `seed=42`
- **THEN** the bootstrap CI bounds SHALL be identical across the two runs

### Requirement: Blind grading of judge-graded trials

For rubric-graded tasks, the composed judge prompt SHALL contain ONLY the
rubric, the task prompt, and the trial's `response_text` — no skill name, no
skill content, no arm label, and no with/without-skill wording added by the
harness. Each trial output SHALL receive an opaque blinded grading id, and
the grading queue SHALL interleave both arms in an order shuffled by `seed`.
The result SHALL carry a blinding record (mode + seed) and the evidence SHALL
map blinded grading ids to true arm/task/trial coordinates for post-hoc
audit. A trial passes judge grading when `JudgeScore.pass_threshold_met` is
true.

#### Scenario: Judge prompt carries no arm metadata
- **WHEN** a candidate-arm trial and a baseline-arm trial of the same task
  are judge-graded
- **THEN** the two composed judge prompts SHALL differ ONLY in the
  `response_text` section (and neither contains the skill name injected by
  the harness or any arm label)

#### Scenario: Grading order is seed-shuffled across arms
- **WHEN** a benchmark with rubric grading runs with `seed=42`
- **THEN** the grading call order SHALL be a deterministic seed-derived
  interleaving of both arms, not arm-A-then-arm-B

#### Scenario: Blinding is auditable after the fact
- **WHEN** a benchmark completes
- **THEN** each evidence entry SHALL expose both its blinded grading id and
  its true arm, and the result SHALL expose the blinding mode + seed

### Requirement: Skill-obsolescence verdict as first-class outcome

The result SHALL carry a `verdict` field with the closed, runtime-validated
value space `{"skill_improves", "skill_unnecessary", "skill_regresses",
"no_significant_difference"}`, computed by the library: `skill_improves` when
the candidate arm is significantly better (Mann-Whitney `p_value < alpha`
with candidate direction favorable); `skill_regresses` when significantly
worse; `skill_unnecessary` ONLY in `baseline=none` mode, when the baseline
pass rate is `>= obsolescence_threshold` AND the candidate shows no
significant improvement; otherwise `no_significant_difference`.

#### Scenario: Base model passing without the skill flags obsolescence
- **WHEN** `baseline=none`, the baseline arm's pass rate is `0.95` with
  `obsolescence_threshold=0.9`, and the candidate shows no significant
  improvement
- **THEN** `result.verdict` SHALL equal `"skill_unnecessary"`

#### Scenario: Obsolescence verdict never emitted in v1-vs-v2 mode
- **WHEN** `baseline` is a skill path and both arms pass at high rates with
  no significant difference
- **THEN** `result.verdict` SHALL equal `"no_significant_difference"`, never
  `"skill_unnecessary"`

#### Scenario: Significant improvement wins over obsolescence
- **WHEN** the baseline pass rate exceeds the obsolescence threshold BUT the
  candidate is significantly better at `alpha`
- **THEN** `result.verdict` SHALL equal `"skill_improves"`

### Requirement: Evidence-bearing output

The result SHALL carry an `evidence` list with one frozen entry per trial per
arm containing at minimum: `task_id`, `arm`, `trial_index`, blinded grading
id, `passed`, `grading_mode` (`"expected_content"` or `"judge"`), judge score
and judge reasoning for judge-graded trials, a truncated response excerpt
(with the project redaction pass applied), token usage, `cost_usd`, and
`latency_seconds`. All result dataclasses SHALL be frozen and serialize
cleanly via `dataclasses.asdict()`.

#### Scenario: Every trial produces an evidence entry
- **WHEN** a benchmark runs 2 arms × 3 tasks × 2 trials
- **THEN** `result.evidence` SHALL contain exactly 12 entries, each naming
  its task, arm, trial index, and pass verdict

#### Scenario: Judge-graded evidence carries reasoning
- **WHEN** a rubric-graded trial is graded
- **THEN** its evidence entry SHALL include the judge's numeric score and
  reasoning text

#### Scenario: Result serializes for trace artifacts
- **WHEN** `dataclasses.asdict()` is applied to the result
- **THEN** it SHALL succeed and round-trip all evidence entries

### Requirement: Cohort heatmap and budget integration

The result SHALL include a `CohortHeatmap` (via a new
`CohortHeatmap.from_skill_benchmark` constructor) with rows = task ids,
columns = the two arms, cells = per-task pass rates, supporting the existing
ASCII/dict/HTML renderers. The keyword SHALL run under `@tier(3)` +
`@guarded_fanout()` with `max_cost_usd` (default `20.00`) enforced across BOTH
arms AND judge grading calls in the same guarded scope, honoring
library-level budgets via the existing `_HostBudgetPlumbing` inheritance;
`max_runtime_seconds` SHALL be tracked (Phase-1: not enforced).

#### Scenario: Heatmap has one column per arm
- **WHEN** a benchmark over 5 tasks completes
- **THEN** `result.heatmap.as_dict()` SHALL expose 5 rows × 2 columns
  (`candidate`, `baseline`) of pass rates and `as_ascii()` SHALL render

#### Scenario: Budget cap covers adapter and judge spend
- **WHEN** accumulated adapter + judge cost would exceed `max_cost_usd`
- **THEN** the `@guarded_fanout` budget enforcement SHALL trip exactly as it
  does for `Skill.Compare Discoverability`, halting further spend

