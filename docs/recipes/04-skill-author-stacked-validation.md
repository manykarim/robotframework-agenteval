# Recipe 4: Devon's Stacked Skill Validation Pattern

**Persona:** Devon (Agent Surface Author)
**Epic:** Epic 7 — Skill Author Validation Flow + Skill Discoverability (Tier-1 + Tier-3); Epic 12 — Tier-2 LLM-Judge completion.
**Status:** Complete — Story 7.3 stub + Story 8b.3 polish + Story 12.3 Tier-2 completion (2026-05-27).

## Listener invocation (REQUIRED)

```bash
robot --listener AgentEval.telemetry.listener.Listener \
      --xunit junit.xml \
      tests/
```

Use the **explicit `Module.Class` listener path**. The shorter
`--listener AgentEval.telemetry.listener` (module-path-only) form is
accepted by RF 7.x but the `Listener` class hooks do NOT fire (Story 8a.2
D-6 empirical finding). The listener is required for trace capture +
xunit enrichment — see Recipes #1 + #8.

## Overview

Devon validates a skill `.md` file using a three-tier stacked pattern:

| Tier | Keyword | Story | Notes |
|------|---------|-------|-------|
| 1 — Static | `Skill.Should Be Valid Frontmatter` | 2.1 | Deterministic; no LLM call |
| 2 — Judge | `Judge.Get Score` | Epic 12.3 | Phase 2 — LLM-deterministic at `seed + temperature=0`; rubric ratifies pass/fail at threshold |
| 3 — Cohort | `Skill.Get Discoverability` | 7.2 | 10 trials/task; assert Pass@k ≥ 0.8 |
| 3 — Spot | `Skill.Should Activate For` | 7.2 | Single-prompt assertion |
| Stat | `Stat.Run N Times` + `Stat.Get Pass At K` | 6.3 | Composition with Tier-3 |
| Calibration | `Judge.Calibrate Rubric` | Epic 12.2 | Pre-deployment — verify Cohen's κ ≥ 0.7 against human labels before relying on Tier-2 |

## Robot Framework Example

```robotframework
*** Settings ***
Library    AgentEval.skills.library.SkillsLibrary                  WITH NAME    Skill
Library    AgentEval.stats.library.StatsLibrary                    WITH NAME    Stat
Library    AgentEval.judge.library.JudgeLibrary                    WITH NAME    Judge
Library    AgentEval.orchestration.library.OrchestrationLibrary

*** Variables ***
${SKILL_PATH}     skills/my-search-skill.md
${TASKS_PATH}     tests/discoverability/my-skill-tasks.yaml
${RUBRIC_PATH}    tests/rubrics/skill-quality.md
${ADAPTER}        generic
${JUDGE_MODEL}    anthropic/claude-sonnet-4-6
${REPRESENTATIVE_PROMPT}    Search for Python tutorials on the web

*** Test Cases ***
Devon Validates Skill: Stacked Three-Tier Pattern
    # ── Tier 1: Static frontmatter validation (deterministic, fast) ──
    ${fm}=    Skill.Get Frontmatter    ${SKILL_PATH}
    Skill.Should Be Valid Frontmatter    ${fm}

    # ── Tier 2: LLM-judge scoring at seed + temperature=0 (Story 12.3) ──
    # Run the agent once against a representative prompt, then judge the
    # response against the rubric. Tier-2 is a SEPARATE LLM call from any
    # Tier-3 cohort run — Devon pays for it explicitly. Calibrate the rubric
    # first via `Judge.Calibrate Rubric` (Story 12.2) — see docs/recipes/judge-calibration.md.
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
    # NOTE: Must use custom predicate — see DF-7.3-S1/C59 in deferred-work.md
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

As of Story 12.3 (Epic 12 — 2026-05-27), the full three-tier stacked validation
flow is shipping. Devon's Journey 4 from PRD L394-401 is end-to-end exercisable:

- **Tier 1 + Tier 3** ship in Phase 1 (Epic 7).
- **Tier 2** ships in Phase 2 (Epic 12 — Stories 12.1 + 12.2 + 12.3).

Operators may opt out of Tier-2 by leaving the section commented out; Tier-1 +
Tier-3 remain the Phase-1 ceiling for budget-constrained users. Tier-2 adds one
LLM call per representative prompt — calibrate the rubric first via
`Judge.Calibrate Rubric` (Story 12.2) and gate CI on Cohen's kappa ≥ 0.7 per
`architecture.md` L199.

## See Also

- Story 7.1: `Skill.Get Activation Decision` — single-prompt activation query
- Story 7.2: `Skill.Get Discoverability` + `Skill.Should Activate For`
- Story 6.3: `Stat.Run N Times` + `Stat.Get Pass At K`
- Story 12.1: `Judge.Get Score` — Tier-2 LLM-judge keyword
- Story 12.2: `Judge.Calibrate Rubric` + `docs/recipes/judge-calibration.md` — calibrate rubrics against human labels
- Story 12.3: `tests/integration/skills/test_devon_three_tier_complete.py` — Python pytest example
- `tests/integration/skills/test_devon_stacked_validation.py` — Tier-1 + Tier-3 subset (Story 7.3)
