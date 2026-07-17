# Recipe 3: Stacked skill validation across all three tiers

**I want to** validate a Skill from cheap to thorough — a static frontmatter
check first, then an LLM judge, then a real agent cohort — so I only pay for the
expensive checks once the cheap ones pass.

This is the natural shape of a good skill test: fail fast on the free stuff,
climb the tiers only when it's worth it.

| Tier | Keyword | Costs |
| --- | --- | --- |
| 1 — static | `Skill.Should Be Valid Frontmatter` | nothing, instant |
| 2 — judge | `Skill.Get Judge Activation Decision` | one judge call |
| 3 — spot check | `Skill.Should Activate For` | one agent call |
| 3 — cohort | `Skill.Get Discoverability` | `trials_per_task` agent calls per task |

Tiers 2 and 3 need the `[llm]` extra and a model:

```bash
pip install 'robotframework-agenteval[llm]'
```

## Tier 1 — static frontmatter (keyless, instant)

Runs on the base install. Catch a broken skill before spending a cent.

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Variables ***
${SKILL}    ${CURDIR}/skills/web-search.md

*** Test Cases ***
Skill Frontmatter Is Valid
    ${fm}=    Skill.Get Frontmatter    ${SKILL}
    Skill.Should Be Valid Frontmatter    ${fm}
    Should Not Be Empty    ${fm}[description]
```

## Tier 2 — does the response actually apply the skill?

The judge reads a response for *meaning*, not a substring. Give it a response
your agent produced and the skill, and it scores whether the guidance was
actually applied.

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Variables ***
${SKILL}    ${CURDIR}/skills/web-search.md
${MODEL}    anthropic/claude-sonnet-4-6

*** Test Cases ***
Response Reflects The Skill Guidance
    ${response}=    Set Variable
    ...    I searched the web and found three sources; here they are, each cited.
    ${decision}=    Skill.Get Judge Activation Decision    ${response}    ${SKILL}
    ...    model=${MODEL}    threshold=7.0
    Should Be True    ${decision.activated}
    ...    msg=Judge scored ${decision.numeric_score}/10: ${decision.justification}
```

## Tier 3 — drive a real agent

A single spot check — did the skill fire for a prompt it should own?

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Variables ***
${SKILL}    ${CURDIR}/skills/web-search.md
${MODEL}    anthropic/claude-sonnet-4-6

*** Test Cases ***
Skill Activates For A Representative Prompt
    Skill.Should Activate For    Find recent news about Robot Framework    ${SKILL}
    ...    model=${MODEL}
```

## Tier 3 — the cohort (reliability, not luck)

One activation could be a fluke. `Skill.Get Discoverability` runs a set of
tasks — both should-activate prompts and decoys — several times each, and
reports how reliably the skill fires when it should and stays quiet when it
shouldn't.

Tasks live in a YAML file (`tasks: [{id, prompt, should_activate}]`):

```yaml
tasks:
  - id: news-query
    prompt: What's the latest release of Robot Framework?
    should_activate: true
  - id: refactor-request
    prompt: Rename this local variable across the file.
    should_activate: false
```

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Variables ***
${SKILL}    ${CURDIR}/skills/web-search.md
${TASKS}    ${CURDIR}/tasks/web-search-tasks.yaml
${MODEL}    anthropic/claude-sonnet-4-6

*** Test Cases ***
Skill Is Reliably Discoverable
    ${result}=    Skill.Get Discoverability    ${SKILL}    ${TASKS}
    ...    model=${MODEL}    trials_per_task=5
    Should Be True    ${result.summary.activation_accuracy} >= 0.8
    ...    msg=Activation accuracy ${result.summary.activation_accuracy} below 0.8
    Should Be True    ${result.summary.false_activation_rate} <= 0.2

    FOR    ${task}    IN    @{result.per_task_results}
        Log    ${task.task_id}: ${task.activations_observed}/${task.trials_run} (pass@k ${task.pass_at_k})
    END
```

The summary carries `activation_accuracy`, `false_activation_rate`, and
`missed_activation_rate` — the two failure directions split out, so you can tell
a skill that never fires from one that fires on everything.

## The point of the ladder

Each tier answers a sharper question at a higher price:

- **Tier 1** — is the skill file even well-formed?
- **Tier 2** — when applied, does the guidance land?
- **Tier 3 spot** — does the skill fire at all?
- **Tier 3 cohort** — does it fire *reliably*, and not on decoys?

Gate CI on Tier 1 for every commit; run Tiers 2 and 3 on a schedule or before a
release, where the cost buys you real confidence.

## See also

- [Recipe 1](./01-first-eval-in-five-minutes.md) — the Tier-1 starting point.
- [`SkillsLibrary` keyword reference](../keywords/SkillsLibrary.html).
