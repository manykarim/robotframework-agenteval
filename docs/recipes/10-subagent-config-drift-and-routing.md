# Recipe 5: SubAgent config drift and delegation routing

**I want to** keep my SubAgents honest — their config shouldn't quietly drift
into over-broad permissions, and the orchestrator should actually delegate the
right work to the right agent.

`SubagentsLibrary` splits this into two jobs. Config-drift checks are **Tier 1**
— deterministic, keyless, CI-cheap. Routing checks are **Tier 3** — they drive a
real agent to see where it delegates.

```robotframework
*** Settings ***
Library    SubagentsLibrary
```

## The SubAgent under test

Save this as `agents/code-reviewer.md`:

```markdown
---
name: code-reviewer
description: Reviews pull requests for correctness and style. Read-only.
tools: [Read, Grep, Bash]
skills: [static-analysis]
---

# Code Reviewer

Review the diff. Report issues. Never edit files.
```

## Tier 1 — config drift (keyless, instant)

SubAgents do **not** inherit the parent's skills, and an absent `tools:` field
silently grants the *full* parent tool set. Both are easy to get wrong, so both
checks **fail loud** on the dangerous default rather than passing vacuously.

```robotframework
*** Settings ***
Library    SubagentsLibrary

*** Variables ***
${AGENT}    ${CURDIR}/agents/code-reviewer.md

*** Test Cases ***
Reviewer Frontmatter Is Well-Formed
    ${fm}=    Subagent.Get Frontmatter    ${AGENT}
    Should Be Equal    ${fm}[name]    code-reviewer

Reviewer Stays Within Its Tool Allowlist
    # An absent `tools:` would inherit everything — that FAILS here.
    Subagent.Tools Should Be Subset Of    ${AGENT}    Read    Grep    Bash

Reviewer Preloads The Skills It Needs
    # Subagents don't inherit parent skills, so this must be explicit.
    Subagent.Should Declare Skills    ${AGENT}    static-analysis
```

Point these at every SubAgent `.md` in your repo and a pull request that widens
a tool allowlist or drops a required skill fails before it merges.

## Tier 1 — delegations from a captured run

Already have an `AgentRunResult` from an orchestrator run? `SubagentsLibrary`
projects the delegations straight out of it — no re-run, no model call:

- `Subagent.Get Delegations` — every orchestrator→subagent handoff, in order.
- `Subagent.Should Have Delegated To` — assert a specific subagent was used.
- `Subagent.Should Not Have Delegated` — assert one was avoided (or none happened).

These read `result.tool_calls`, matching the `Task` tool by default. Use them
when your suite already holds a run result and you want to assert on the routing
after the fact.

## Tier 3 — routing (drives a real agent)

The routing keywords need the `[llm]` extra and a model:

```bash
pip install 'robotframework-agenteval[llm]'
```

A single routing assertion — did the orchestrator hand this prompt to the right
agent?

```robotframework
*** Settings ***
Library    SubagentsLibrary

*** Variables ***
${MODEL}    anthropic/claude-sonnet-4-6

*** Test Cases ***
PR Review Routes To The Reviewer
    Subagent.Should Delegate To    Review my open pull request    code-reviewer
    ...    model=${MODEL}
```

## Tier 3 — routing accuracy across a cohort

One prompt could route right by luck. `Subagent.Get Routing Accuracy` runs a
set of tasks several times each and reports the fraction routed correctly, with
a Wilson confidence band.

Tasks live in a YAML file (`tasks: [{id, prompt, expected_subagent}]`):

```yaml
tasks:
  - id: review-pr
    prompt: Review my open pull request for issues.
    expected_subagent: code-reviewer
  - id: run-migration
    prompt: Apply the pending database migration.
    expected_subagent: db-admin
```

```robotframework
*** Settings ***
Library    SubagentsLibrary

*** Variables ***
${TASKS}    ${CURDIR}/tasks/routing.yaml
${MODEL}    anthropic/claude-sonnet-4-6

*** Test Cases ***
Orchestrator Routes Reliably
    ${result}=    Subagent.Get Routing Accuracy    ${TASKS}
    ...    model=${MODEL}    trials_per_task=5
    Should Be True    ${result.summary.routing_accuracy} >= 0.8
    ...    msg=Routing accuracy ${result.summary.routing_accuracy} below 0.8
    Log    95% CI: ${result.summary.ci_lower} .. ${result.summary.ci_upper}
```

## The split, and why it matters

- **Config drift is Tier 1.** It's a property of the `.md` file, so check it on
  every commit for free. This is where over-broad tool grants and missing skills
  get caught.
- **Routing is Tier 3.** Whether the orchestrator *chooses* the right agent is a
  behavior, not a config fact — it takes a real run to observe. Save it for a
  schedule or a pre-release gate.

## See also

- [Recipe 4](./09-testing-claude-code-hooks.md) — the other all-deterministic surface.
- [`SubagentsLibrary` keyword reference](../keywords/SubagentsLibrary.html).
