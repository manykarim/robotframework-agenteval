# Recipe 4: Devon's Stacked Skill Validation Pattern

**Persona:** Devon (Agent Surface Author)
**Epic:** Epic 7 — Skill Author Validation Flow + Skill Discoverability
**Status:** Stub — drafted Story 7.3; content polish deferred to Epic 8b.

## Overview

Devon validates a skill `.md` file using a three-tier stacked pattern:

| Tier | Keyword | Story | Notes |
|------|---------|-------|-------|
| 1 — Static | `Skill.Should Be Valid Frontmatter` | 2.1 | Deterministic; no LLM call |
| 2 — Judge | `Judge.Get Score` | Epic 12.3 | **Phase 2 only** — see TODO below |
| 3 — Cohort | `Skill.Get Discoverability` | 7.2 | 10 trials/task; assert Pass@k ≥ 0.8 |
| 3 — Spot | `Skill.Should Activate For` | 7.2 | Single-prompt assertion |
| Stat | `Stat.Run N Times` + `Stat.Get Pass At K` | 6.3 | Composition with Tier-3 |

## Robot Framework Example

```robotframework
*** Settings ***
Library    AgentEval.skills.library    WITH NAME    Skill
Library    AgentEval.stats.library     WITH NAME    Stat

*** Variables ***
${SKILL_PATH}     skills/my-search-skill.md
${TASKS_PATH}     tests/discoverability/my-skill-tasks.yaml
${ADAPTER}        generic

*** Test Cases ***
Devon Validates Skill: Stacked Three-Tier Pattern
    # ── Tier 1: Static frontmatter validation (deterministic, fast) ──
    ${fm}=    Skill.Get Frontmatter    ${SKILL_PATH}
    Skill.Should Be Valid Frontmatter    ${fm}

    # ── Tier 2 (Phase 2 only — placeholder) ──
    # TODO Phase 2: Judge.Get Score here (Epic 12 Story 12.3)
    # ${score}=    Judge.Get Score    ${SKILL_PATH}    prompt=${REPRESENTATIVE_PROMPT}
    # Should Be True    ${score} >= 0.8

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

## See Also

- Story 7.1: `Skill.Get Activation Decision` — single-prompt activation query
- Story 7.2: `Skill.Get Discoverability` + `Skill.Should Activate For`
- Story 6.3: `Stat.Run N Times` + `Stat.Get Pass At K`
- Epic 12 Story 12.3: `Judge.Get Score` (Phase 2 — Tier-2 LLM judge)
- `tests/integration/skills/test_devon_stacked_validation.py` — Python pytest example
