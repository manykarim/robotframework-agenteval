# Design — Skill A/B Benchmark Mode

## Context

The skills surface today measures *trigger behavior* (does the agent activate
the skill?) but not *outcome value* (does the skill make the agent's output
better, cheaper, or faster?). Anthropic's skill-creator centers a benchmark
mode: run the same task set with and without the skill (or v1 vs. v2), grade
outputs blind, and report pass rate / tokens / time per arm. The building
blocks already exist in this repo:

- **Cohort execution pattern**: `Skill.Get Discoverability`
  (`src/AgentEval/skills/library.py`) + the extracted
  `run_single_adapter_skill_discoverability` helper
  (`src/AgentEval/skills/_internal.py`) — task YAML loader with RFC-6901
  error pointers, N tasks × M trials loop, adapter-per-trial construction,
  per-task cost accumulation, summary dataclass, wall-clock anchor at keyword
  entry (Story 13.3 HIGH-A precedent).
- **Cross-cohort comparison pattern**: `Skill.Compare Discoverability` —
  ≥2-cohort fan-out, Mann-Whitney U over per-task distributions, extras-gate
  fail-fast BEFORE fan-out, `max_cost_usd` default sized to the fan-out
  multiple, multi-column `CohortHeatmap`.
- **Statistics**: `AgentEval.stats` pure helpers `compute_mann_whitney_u`,
  `cliffs_delta`, `compute_bootstrap_ci` (Epic 13; behind
  `[agenteval-advanced]`).
- **Grading**: `AgentEval.judge` (`Judge.Get Score` — rubric load, prompt
  composition, JSON parse into `JudgeScore` with `numeric_score`,
  `pass_threshold_met`, `reasoning`, `cost_usd`).
- **Metrics carriers**: every adapter returns `AgentRunResult` with `usage`
  (tokens), `cost_usd`, `latency_seconds` (`src/AgentEval/types.py:346`).
- **Guardrails**: `@tier(3)` + `@guarded_fanout()` + `_HostBudgetPlumbing`
  (Story 14.6) enforce `max_cost_usd` end-to-end.

Constraints: FR28 polling ban; frozen/`asdict()`-serializable result
dataclasses; structured errors with File/Line/Field/Fix; keyword name must be
namespace-prefixed multi-word (`Skill.Compare Against Baseline` — post-dot
portion is multi-word, satisfying
`feedback_libdoc_namespace_keyword_must_be_multiword`); honesty-field
philosophy (state what was and was not verified, cf. `mcp_coverage` /
`adapter_coverage`).

## Goals / Non-Goals

**Goals:**

- One keyword that answers "does this skill earn its context window?" with
  per-arm pass rate + tokens + elapsed time + cost and cross-arm statistical
  significance.
- Blind grading: the grader can never condition on which arm produced an
  output.
- Skill obsolescence ("base model passes without the skill") as a first-class
  machine-readable verdict, not something the user derives by eyeballing two
  numbers.
- Evidence-bearing results: every pass/fail verdict is traceable to the trial
  output, the grading mode, and (for judged trials) the judge's reasoning.
- Reuse, not reinvention: stats, judge, heatmap, budget machinery are
  composed as-is.

**Non-Goals:**

- Trigger-precision / activation measurement (existing keywords own it).
- Regression tracking across runs over time (sibling change
  `add-regression-baseline-tracking` owns run-N-vs-run-N-1).
- N>2 arm tournaments (two arms per invocation; callers can chain
  invocations; a multi-arm mode can layer on later without breaking the
  two-arm contract).
- A new grading DSL: grading is either deterministic content checks or the
  existing judge rubric format.

## Decisions

### D1 — Two fixed arms: `candidate` and `baseline`; `baseline=none` means no-skill

`Skill.Compare Against Baseline` always runs exactly two arms over the SAME
task cohort:

- `candidate` arm: the skill at `skill=`.
- `baseline` arm: `baseline=none` (literal string, default) → the agent runs
  WITHOUT any skill (skill-vs-no-skill mode); `baseline=<path>` → the agent
  runs with the other skill (v1-vs-v2 mode).

*Why*: the skill-creator idiom is pairwise; every downstream statistic
(Mann-Whitney U, Cliff's delta, bootstrap CI on the delta) is defined for two
samples; and `Skill.Compare Discoverability` already establishes "N result
columns + pairwise deltas" for the N-way case if it's ever needed.
*Alternative considered*: `arms=[...]` list like `adapters=` — rejected;
C(N,2) significance output complicates the obsolescence verdict, which is
inherently about ONE candidate vs. ONE baseline.

### D2 — Skill delivery: Phase-1 prompt-context injection + `skill_delivery` honesty field

The existing discoverability keywords never install the skill anywhere — they
assume the agent environment already has it and only inspect `response_text`.
An A/B benchmark cannot assume that: the two arms MUST differ only in skill
availability, under the library's control.

Phase-1 mechanism: for a skill arm, the trial prompt is composed as skill
content (frontmatter + body) prepended to the task prompt inside a clearly
delimited block ("You have the following skill available: ..."); the no-skill
arm sends the bare task prompt. The result carries
`skill_delivery: "prompt_injected"` — an honesty field (closed value space,
runtime-validated in `__post_init__` like `AgentRunMetadata.mcp_coverage`)
that states this is context-injection, NOT native skill installation.
Phase-2 can add `"workspace_installed"` (CLI adapters writing the skill file
into the agent's skills directory) without a breaking change.

*Why*: adapters expose no uniform skill-installation API; prompt injection is
the only mechanism that works across all 6 adapters today; and per the
honesty-field philosophy we say so in the data rather than imply parity with
native installation. *Alternative considered*: per-adapter installers now —
rejected as a 6-adapter matrix of filesystem conventions that would dwarf the
benchmark logic; deferred behind the honesty field.

### D3 — Benchmark task cohort YAML: sibling schema with grading spec

New loader `load_skill_benchmark_tasks` (sibling of
`load_skill_discoverability_tasks`, same error discipline:
`InvalidSkillBenchmarkTasksError` with RFC-6901 `field_name` pointers +
`fix_suggestion`). Discoverability tasks (`should_activate`) are about
triggering; benchmark tasks are about outcomes, so each task needs a grading
spec. Schema per task:

- `id` (str, unique, required), `prompt` (str, required)
- exactly ONE grading mode:
  - `expected_content: [<substr>, ...]` — deterministic: trial passes when
    ALL listed substrings appear (case-insensitive) in `response_text`; or
  - `rubric: <path.md>` — judge-graded via the Epic-12 judge; trial passes
    when `JudgeScore.pass_threshold_met` is true.
- File-level optional defaults block: `defaults: {rubric: <path>}` so a
  cohort can share one rubric without repeating it per task.

*Why not reuse the discoverability YAML*: `should_activate` is meaningless
here and grading specs are meaningless there; a shared schema would make both
loaders validate fields the other keyword ignores. The two loaders share
low-level YAML/IO error handling via a small extracted helper if convenient
(implementation detail).

### D4 — Blind grading protocol (skill-creator idiom)

When a task uses judge grading:

1. **Zero arm metadata in the judge prompt**: the composed judge prompt
   contains ONLY the rubric + the task prompt + the trial's `response_text`.
   No skill name, no skill content, no arm label, no "with/without skill"
   wording. The judge grades each output independently against the rubric
   (absolute grading, not pairwise ranking).
2. **Blinded grading ids + seed-shuffled order**: each trial output gets an
   opaque grading id (`g-<seed-derived-hex>`); the grading queue interleaves
   both arms in a seed-shuffled order so systematic drift in a stateful judge
   backend cannot correlate with arm.
3. **Auditable unblinding**: the evidence output records, per trial, the
   blinded grading id AND the true arm/task/trial coordinates, plus a
   top-level `blinding: {"mode": "arm_label_blind", "seed": <int>}` record —
   so a reviewer can verify after the fact that grading inputs carried no arm
   information.

*Why absolute-per-output instead of pairwise A/B ranking*: pairwise ranking
prompts are more sample-efficient but position-biased and can't produce
per-arm pass RATES (needed for the obsolescence verdict and for
Mann-Whitney over per-task distributions); absolute grading reuses
`Judge.Get Score` composition unchanged. Deterministic `expected_content`
grading is trivially blind (no LLM sees anything).

*Guard*: skill-vs-no-skill outputs can self-identify (the candidate arm's
output may mention the skill by name). We cannot scrub model outputs without
destroying evidence; the blinding contract is therefore about what the
*harness* adds — nothing arm-identifying — and this limitation is documented
in the keyword docs (honesty over false comfort).

### D5 — Statistics: reuse Epic-13 primitives; extras-gate fail-fast; mandatory seed

- **Pass-rate significance**: Mann-Whitney U (`compute_mann_whitney_u`) over
  the two arms' per-task pass-rate distributions (task-level pairing, same
  granularity as `Skill.Compare Discoverability` uses for `pass_at_k`).
- **Effect size**: Cliff's delta (`cliffs_delta`) over the same samples.
- **Uncertainty on the headline number**: percentile bootstrap CI
  (`compute_bootstrap_ci`) on the pass-rate delta (candidate − baseline),
  seeded.
- The keyword takes `seed: int` (default `42`) — it feeds BOTH the bootstrap
  resampler and the blind-grading shuffle, keeping the whole benchmark
  reproducible at Tier-3-stochastic-modulo-provider level.
- Statistical fields require `[agenteval-advanced]`; the keyword raises
  `ImportError` BEFORE any adapter fan-out (mirrors
  `Skill.Compare Discoverability` — operators must not pay 2-arm trial cost
  to discover a missing extra).

*Alternative considered*: making stats optional (populate `None` without the
extra) — rejected; a benchmark whose significance fields silently vanish
invites vibes-based conclusions, against `feedback_honest_framing`.

### D6 — Skill-obsolescence verdict: closed set, first-class field

`verdict` is a closed, runtime-validated value space:

- `skill_improves` — candidate beats baseline, p < alpha.
- `skill_unnecessary` — the OBSOLESCENCE signal: baseline (no-skill) pass
  rate ≥ `obsolescence_threshold` (keyword arg, default `0.9`) AND no
  significant candidate improvement. The base model already does the job;
  the skill adds nothing but tokens. Only emitted in `baseline=none` mode —
  in v1-vs-v2 mode the corresponding outcome is `no_significant_difference`.
- `skill_regresses` — candidate significantly WORSE than baseline.
- `no_significant_difference` — everything else.

The verdict is computed by the library (single documented rule, `alpha`
keyword arg, default `0.05`), not left for users to derive — per landscape §4
this dimension ("base model passes without skill") deserves a first-class
outcome, and per-user re-derivation would fork the rule. Token/time deltas do
NOT affect the verdict (they're reported alongside); a skill that only costs
tokens while `skill_unnecessary` is already the strongest possible removal
signal.

### D7 — Result shape: frozen dataclasses, per-arm metrics, evidence list

New frozen dataclasses in `src/AgentEval/skills/types.py` (all
`asdict()`-serializable, defensive copies per the M_R6 pattern):

- `SkillBenchmarkTrialEvidence` — task_id, arm, trial_index, blinded
  grading id, passed, grading_mode (`"expected_content" | "judge"`),
  judge_score + judge_reasoning (judge mode only), response_excerpt
  (truncated, redaction-pass applied), tokens (input/output), cost_usd,
  latency_seconds.
- `SkillBenchmarkArmSummary` — arm name, skill path (or `None`), pass_rate,
  per-task pass rates, total/mean tokens, total elapsed seconds, total
  cost_usd, trials_run.
- `SkillBenchmarkComparisonResult` — `candidate: SkillBenchmarkArmSummary`,
  `baseline: SkillBenchmarkArmSummary`, `pass_rate_delta`,
  `mann_whitney: MannWhitneyResult`, `cliffs_delta: float`,
  `bootstrap_ci: tuple[float, float]`, `verdict`, `skill_delivery`,
  `blinding` record, `evidence: list[SkillBenchmarkTrialEvidence]`,
  `heatmap: CohortHeatmap`, `total_runtime_seconds`, `total_cost_usd`
  (adapter + judge cost combined, judge cost also broken out).

### D8 — Heatmap + budget integration

- **Heatmap**: a `CohortHeatmap.from_skill_benchmark(...)` constructor
  (sibling of `from_skill_comparison`, `src/AgentEval/_heatmap/models.py`)
  with rows = task ids, columns = the two arms (`candidate` /
  `baseline`), cells = per-task pass rate. ASCII/dict/HTML renderers come
  free.
- **Budget/tier**: the keyword is `@tier(3)` + `@guarded_fanout()`;
  `max_cost_usd` defaults to `20.00` (2 arms × trials, consistent with
  `Skill.Compare Discoverability`'s fan-out-sized default);
  `SkillsLibrary` already inherits `_HostBudgetPlumbing` so import-time
  budgets are honored. Judge grading calls run INSIDE the same guarded scope
  so grading cost counts against the same `max_cost_usd` — a benchmark's
  grading bill is part of the benchmark. `max_runtime_seconds` tracked
  (Phase-1: not enforced, same as the sibling keyword). `polling=` raises
  `PollingDisallowedError` per FR28.

## Risks / Trade-offs

- [Prompt-injection delivery ≠ native skill loading — absolute pass rates may
  differ from production skill behavior] → `skill_delivery` honesty field +
  keyword docs state the limitation; the RELATIVE arm comparison (same
  delivery both arms in v1-vs-v2; delta interpretation in no-skill mode) is
  the supported claim. Phase-2 `workspace_installed` closes the gap.
- [Candidate outputs may self-identify the skill, weakening blinding] →
  documented contract: the harness adds no arm metadata; output
  self-identification is recorded evidence, not scrubbed (D4 guard).
- [Judge grading doubles LLM spend and adds judge noise] → judge calls share
  the `max_cost_usd` budget (D8); `expected_content` mode is available for
  deterministic tasks; judge noise affects both arms symmetrically under
  blinding, and rubric calibration (`Judge.Calibrate Rubric`, κ≥0.7 gate)
  is the existing project answer to judge quality.
- [Small cohorts → underpowered Mann-Whitney; users may over-read
  `no_significant_difference`] → result carries n per arm + bootstrap CI so
  width is visible; keyword docs recommend ≥10 tasks × ≥3 trials; verdict
  rule uses significance, never raw deltas.
- [Two-arm limit forces multiple invocations for skill tournaments] →
  accepted (Non-Goal); pairwise chaining preserves the verdict semantics.
- [Per-trial adapter construction (inherited pattern from
  `run_single_adapter_skill_discoverability`) may be slow for heavy CLI
  adapters] → consistent with the existing cohort keywords; optimizing
  adapter reuse is orthogonal and out of scope.

## Migration Plan

Purely additive: new keyword + new dataclasses + new loader + one new heatmap
constructor. No existing API changes, no data migration. Rollback = remove
the new module/keyword. Ships behind nothing (statistics already gated by the
existing `[agenteval-advanced]` extra).

## Open Questions

- Phase-2 `workspace_installed` delivery: which adapters expose a stable
  skills directory contract (Claude Code `.claude/skills/` is known; codex /
  copilot / opencode need empirical probes per
  `feedback_listener_hook_api_surface_empirical_check`). Tracked as a
  carry-over, not blocking.
- Whether `Skill.Compare Against Baseline` should later accept a pre-loaded
  cohort object (for cohort reuse across sibling keywords) — deferred until a
  second caller exists (`feedback_caller_count_check`).
