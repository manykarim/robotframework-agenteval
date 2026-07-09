# Recipe 4: Stacked Skill Validation Pattern

**Use case:** validate a skill `.md` file with a stacked three-tier pattern — a static frontmatter check, LLM-judge scoring, and cohort activation reliability.

## Listener invocation (REQUIRED)

```bash
robot --listener AgentEval.telemetry.listener.Listener \
      --xunit junit.xml \
      tests/
```

Use the **explicit `Module.Class` listener path**. The shorter
`--listener AgentEval.telemetry.listener` (module-path-only) form is
accepted by RF 7.x but the `Listener` class hooks do NOT fire. The listener
is required for trace capture +
xunit enrichment — see Recipes #1 + #8.

## Overview

Validate a skill `.md` file using a three-tier stacked pattern:

| Tier | Keyword | Notes |
|------|---------|-------|
| 1 — Static | `Skill.Should Be Valid Frontmatter` | Deterministic; no LLM call |
| 2 — Judge | `Judge.Get Score` | Phase 2 — LLM-deterministic at `seed + temperature=0`; rubric ratifies pass/fail at threshold |
| 3 — Cohort | `Skill.Get Discoverability` | 10 trials/task; assert Pass@k ≥ 0.8 |
| 3 — Spot | `Skill.Should Activate For` | Single-prompt assertion |
| Stat | `Stat.Run N Times` + `Stat.Get Pass At K` | Composition with Tier-3 |
| Calibration | `Judge.Calibrate Rubric` | Pre-deployment — verify Cohen's κ ≥ 0.7 against human labels before relying on Tier-2 |

## Robot Framework Example

```robotframework
*** Settings ***
Library    AgentEval

*** Variables ***
${SKILL_PATH}     skills/my-search-skill.md
${TASKS_PATH}     tests/discoverability/my-skill-tasks.yaml
${RUBRIC_PATH}    tests/rubrics/skill-quality.md
${ADAPTER}        generic
${JUDGE_MODEL}    anthropic/claude-sonnet-4-6
${REPRESENTATIVE_PROMPT}    Search for Python tutorials on the web

*** Test Cases ***
Skill Passes Stacked Three-Tier Validation
    # ── Tier 1: Static frontmatter validation (deterministic, fast) ──
    ${fm}=    Skill.Get Frontmatter    ${SKILL_PATH}
    Skill.Should Be Valid Frontmatter    ${fm}

    # ── Tier 2: LLM-judge scoring at seed + temperature=0 ──
    # Run the agent once against a representative prompt, then judge the
    # response against the rubric. Tier-2 is a SEPARATE LLM call from any
    # Tier-3 cohort run — you pay for it explicitly. Calibrate the rubric
    # first via `Judge.Calibrate Rubric` — see docs/recipes/judge-calibration.md.
    ${run}=    Send Prompt    prompt=${REPRESENTATIVE_PROMPT}    adapter=${ADAPTER}
    ${score}=    Judge.Get Score
    ...    result=${run}
    ...    rubric=${RUBRIC_PATH}
    ...    judge_adapter=${ADAPTER}
    ...    judge_model=${JUDGE_MODEL}
    ...    temperature=0.0
    ...    seed=42
    Should Be True    ${score.pass_threshold_met}
    ...    msg=Judge score ${score.numeric_score} below rubric threshold; review reasoning: ${score.reasoning}

    # ── Tier 3: Cohort discoverability (10 trials per task) ──
    ${result}=    Skill.Get Discoverability
    ...    skill=${SKILL_PATH}
    ...    tasks=${TASKS_PATH}
    ...    adapter=${ADAPTER}
    ...    trials_per_task=10
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be True    ${task_result.pass_at_k} >= 0.8
            ...    msg=Task '${task_result.task_id}' pass_at_k < 0.8
        END
    END

    # ── Stat.* composition: Run N times + Pass@5 ──
    # NOTE: Must use custom predicate here
    # (ActivationDecision has no metadata.completeness → default predicate fails)
    ${kwargs}=    Create Dictionary
    ...    skill=${SKILL_PATH}
    ...    prompt=Search for Python tutorials on the web
    ...    adapter=${ADAPTER}
    ${runs}=    Stat.Run N Times
    ...    n=10
    ...    keyword=Skill.Get Activation Decision
    ...    keyword_args=${kwargs}
    ${pass_at_5}=    Stat.Get Pass At K
    ...    runs=${runs}
    ...    k=5
    ...    predicate=${{lambda r: r.result.activated}}
    Should Be True    ${pass_at_5} >= 0.8

    # ── Spot-check: single-prompt activation assertion ──
    Skill.Should Activate For
    ...    prompt=Search for Python tutorials on the web
    ...    skill=${SKILL_PATH}
    ...    adapter=${ADAPTER}
```

## Phase 2 Status

As of Phase 2, the full three-tier stacked validation flow is shipping and is
end-to-end exercisable:

- **Tier 1 + Tier 3** ship in Phase 1.
- **Tier 2** ships in Phase 2.

Operators may opt out of Tier-2 by leaving the section commented out; Tier-1 +
Tier-3 remain the Phase-1 ceiling for budget-constrained users. Tier-2 adds one
LLM call per representative prompt — calibrate the rubric first via
`Judge.Calibrate Rubric` and gate CI on Cohen's kappa ≥ 0.7.

## Phase 2 cross-adapter Skill Discoverability

As of Phase 2, you can compare skill activation
across multiple Tier-1 adapters in a single call to claim "skill X is reliably
activated by Claude AND GPT AND Copilot" with empirical evidence — symmetric to
cross-adapter Tool Discoverability.

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Skill X Is Reliably Activated Across Claude And OpenAI
    ${comparison}=    Skill.Compare Discoverability
    ...    skill=${CURDIR}/skills/web-search.md
    ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
    ...    adapters=${{['claude_code_cli', 'codex_cli']}}
    ...    trials_per_task=5
    ...    max_cost_usd=10.00
    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['codex_cli']} >= 0.7
    # Cross-adapter significance — was the skill consistently triggered
    # OR did one adapter wildly outperform the other? (Extended-variable
    # indexing per RF7 — no `Library Collections` import required.)
    Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3
```

Behind the `[agenteval-advanced]` optional extra (scipy + numpy
for Mann-Whitney U significance). The keyword returns a
`SkillDiscoverabilityComparisonResult` with per-adapter `SkillDiscoverabilityResult`
+ cross-adapter Pass@k differential + per-adapter false-activation /
missed-activation rate comparison + multi-column `CohortHeatmap` (which can
render to HTML via `as_html()` for stakeholder sharing).

**Phase-1.5 dogfood deferral:** the
`robotframework-agentskills` downstream repo will adopt the cross-adapter suite
in its CI matrix (Mock provider for routine CI; a separate
`weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a
budget). Tracked as a Phase-1.5 carry-over.

## Tier 4 — Does the skill actually earn its context window? (A/B benchmark)

Discoverability answers *"does the agent trigger the skill?"* — but not *"does
the skill make the output better?"* `Skill.Compare Against Baseline` runs your
task cohort in two arms (candidate skill vs. a no-skill baseline, or v1 vs. v2)
and reports per-arm pass rate / tokens / time plus cross-arm significance and a
first-class **skill-obsolescence verdict**:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Web Search Skill Earns Its Context Window
    ${bench}=    Skill.Compare Against Baseline
    ...    skill=${CURDIR}/skills/web-search.md
    ...    tasks=${CURDIR}/benchmark/web-search-tasks.yaml
    ...    baseline=none
    ...    trials=5
    ...    max_cost_usd=20.00
    # verdict is one of: skill_improves / skill_unnecessary /
    # skill_regresses / no_significant_difference
    Should Be Equal    ${bench.verdict}    skill_improves
    Should Be True     ${bench.pass_rate_delta} > 0.0
    Log    Candidate pass rate: ${bench.candidate.pass_rate} (${bench.candidate.total_tokens} tokens)
    Log    Baseline  pass rate: ${bench.baseline.pass_rate} (${bench.baseline.total_tokens} tokens)
```

Each benchmark task carries a `prompt` plus exactly one grading mode —
`expected_content: [<substr>, ...]` (deterministic) or `rubric: <path.md>`
(LLM-judge graded, **blind**: the judge never sees which arm produced an
output). Behind the `[agenteval-advanced]` extra (Mann-Whitney U + Cliff's
delta + bootstrap CI, all reused from `AgentEval.stats`).

**Honesty (design D2):** Phase-1 delivers the skill by **prompt-context
injection** — the result carries `skill_delivery="prompt_injected"` to state
plainly this is not native skill installation. When the no-skill baseline
already passes at/above the obsolescence threshold with no significant candidate
gain, the verdict is `skill_unnecessary` — the strongest possible
remove-the-skill signal.

## See Also

- `Skill.Compare Against Baseline` — two-arm A/B outcome benchmark (this recipe, Tier 4)
- `Skill.Get Activation Decision` — single-prompt activation query
- `Skill.Get Discoverability` + `Skill.Should Activate For`
- `Stat.Run N Times` + `Stat.Get Pass At K`
- `Judge.Get Score` — Tier-2 LLM-judge keyword
- `Judge.Calibrate Rubric` + `docs/recipes/judge-calibration.md` — calibrate rubrics against human labels
- `tests/integration/skills/test_devon_three_tier_complete.py` — Python pytest example
- `tests/integration/skills/test_devon_stacked_validation.py` — Tier-1 + Tier-3 subset
