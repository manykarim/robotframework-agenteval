# Add Skill A/B Benchmark Mode (`Skill.Compare Against Baseline`)

## Why

AgentEval has the strongest cross-adapter skill-testing surface in the market
(`Skill.Get Discoverability`, `Skill.Compare Discoverability`, `Skill.Get
Activation Pass At K`) but cannot answer the single most important skill
question: **does this skill actually improve agent outcomes?** Anthropic's own
skill-creator tooling centers exactly this — a benchmark mode reporting pass
rate / tokens / time per arm, with blind A/B comparator agents (skill vs.
no-skill, skill-v1 vs. skill-v2) — and `docs/ai-testing-tools-landscape.md` §4
names "skill obsolescence (base model passes without skill)" as a distinct test
dimension AgentEval does not cover (exploration finding E6 MAJOR). Meanwhile
the statistical machinery this mode needs (Mann-Whitney U, Cliff's delta,
bootstrap CI) shipped in Epic 13 and is underused: closing the gap is mostly
composition of existing primitives, not new math.

## What Changes

- Add one new Tier-3 keyword to `SkillsLibrary`:
  `Skill.Compare Against Baseline    skill=${path}    tasks=${cohort_yaml}
  baseline=none|${other_skill_path}    trials=N` — runs the task cohort in two
  arms (candidate skill vs. no-skill baseline, OR skill-v1 vs. skill-v2) and
  returns a frozen result dataclass with per-arm pass rate, token usage,
  elapsed time, and cost, plus cross-arm statistical significance
  (Mann-Whitney U p-value, Cliff's delta effect size, bootstrap CI on the
  pass-rate delta — all reused from `AgentEval.stats`).
- Add a benchmark task-cohort YAML schema + loader (sibling of
  `load_skill_discoverability_tasks`): each task carries a prompt plus a
  grading spec (deterministic expected-content check OR judge-rubric grading
  via the Epic-12 `judge/` machinery).
- **Blind grading** (skill-creator idiom): when a judge grades trial outputs,
  the judge prompt carries zero arm metadata — no skill name, no arm label, no
  "with/without skill" wording — and grading order is seed-shuffled. The
  blinding map is recorded in the evidence output for post-hoc audit.
- **Skill-obsolescence signal as a first-class outcome**: a closed verdict set
  including `skill_unnecessary` — when the no-skill baseline arm already passes
  at/above an obsolescence threshold and the skill shows no significant
  improvement, the result flags it (the skill adds nothing), per landscape §4.
- **Evidence-bearing output** following the project's honesty-field philosophy:
  per-task-per-trial grading evidence (verdict, grading mode, judge reasoning,
  cost/tokens/latency, blinded grading id) plus a `skill_delivery` honesty
  field stating HOW the skill was made available to the agent in the with-skill
  arm (Phase-1: prompt-context injection).
- Integrate with existing machinery: multi-column `CohortHeatmap` (arms as
  columns, tasks as rows), `@tier(3)` + `@guarded_fanout()` budget enforcement
  (`max_cost_usd`, `_HostBudgetPlumbing`), FR28 polling ban, and the
  `[agenteval-advanced]` extras gate (fail-fast BEFORE fan-out, mirroring
  `Skill.Compare Discoverability`).

Purely additive — no existing keyword's behavior changes.

**NOT in scope**: trigger-precision testing (covered by the existing
activation/discoverability keywords) and regression-over-time tracking
(sibling change `add-regression-baseline-tracking`).

## Capabilities

### New Capabilities
- `skill-ab-benchmark`: The `Skill.Compare Against Baseline` keyword surface —
  two-arm benchmark execution over a task cohort YAML, per-arm outcome metrics
  (pass rate / tokens / time / cost), cross-arm statistical significance via
  the Epic-13 stats primitives, blind judge grading, first-class
  skill-obsolescence verdict, evidence-bearing results, and integration with
  the cohort heatmap + tier/budget machinery.

### Modified Capabilities
<!-- None. The only existing spec in openspec/specs/ is opencode-cli-adapter,
     whose requirements are untouched. This change composes existing runtime
     contracts (FR12 AgentRunResult, FR28 polling ban, ADR-015 guardrails,
     FR29a/b/c stats keywords, FR48 judge) without altering them. -->

## Impact

- **New code**: benchmark task loader + arm-runner + verdict logic in
  `src/AgentEval/skills/` (internal module alongside `_internal.py`); result
  dataclasses in `src/AgentEval/skills/types.py`; one new `@keyword` method on
  `SkillsLibrary` (`src/AgentEval/skills/library.py`); a heatmap constructor
  for two-arm benchmark results (`src/AgentEval/_heatmap/models.py`).
- **Reused, unmodified**: `AgentEval.stats` (`mannwhitney.py`,
  `cliffs_delta.py`, `bootstrap.py`), `AgentEval.judge` (`Judge.Get Score`
  internals / `load_rubric` + `_compose_judge_prompt`-style composition),
  `_kernel` tier + `@guarded_fanout` + `_HostBudgetPlumbing`, adapter
  discovery, `AgentRunResult.usage/cost_usd/latency_seconds`.
- **Tests**: unit tests (mock adapter + canned judge responses) under
  `tests/unit/skills/`; conventions tests pick up the new keyword
  automatically; dogfood recipe deferred to a follow-up story.
- **Dependencies**: statistical fields require the existing
  `[agenteval-advanced]` optional extra (scipy/numpy) — no new dependency.
- **Docs**: README keyword table + a recipe are follow-up work items listed in
  tasks.md (README is already drift-flagged by finding E3; this change must
  not worsen it).
