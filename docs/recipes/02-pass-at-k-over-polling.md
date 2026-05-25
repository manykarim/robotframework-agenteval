# Recipe #2: Pass@k over polling

**Persona:** Priya (QA Engineer) — anyone testing a non-deterministic agent.
**FR coverage:** FR26 (statistical primitives), FR28 (polling ban), ADR-019 (AssertionEngine adoption).

## TL;DR

Use `Stat.Run N Times` + `Stat.Get Pass At K` to run a stochastic agent
keyword N times and assert "passes at least k/N times" — instead of the
banned polling-retry anti-pattern.

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Agent Activation Pass At K
    ${runs}=    Stat.Run N Times    n=10    keyword=Send Prompt
    ...    keyword_args=&{KEYWORD_ARGS}
    ${pass_at_5}=    Stat.Get Pass At K    runs=${runs}    k=5
    Should Be True    ${pass_at_5} >= 0.8

*** Variables ***
&{KEYWORD_ARGS}    prompt=Say hello    adapter=generic    provider=mock
```

## Why no polling?

Tier-2 (single-call) + Tier-3 (fan-out) keywords are non-deterministic by
construction (FR28). Retrying the same call until it succeeds masks real
failure modes — a flaky keyword that passes 1 in 10 runs is NOT
"eventually consistent"; it's broken.

`PollingDisallowedError` fires when a Tier-2/3 keyword is called with a
`polling=` kwarg (or the AssertionEngine `validate` operator without
explicit `allow_validate_operator=True` opt-in). See
[`docs/contracts/error-class-hierarchy.md`](../contracts/error-class-hierarchy.md)
FR56 polling-ban regex contract for the message-format pinning.

## Step-by-step

### 1. Wrap the stochastic call in `Stat.Run N Times`

```robotframework
${runs}=    Stat.Run N Times    n=10    keyword=Send Prompt
...    keyword_args=&{KEYWORD_ARGS}
```

`Stat.Run N Times` runs `Send Prompt` 10 times (Tier-3 fan-out — protected
by `@guarded_fanout` for cost + runtime budgets) and returns a
`list[KeywordRun]` with each invocation's result.

### 2. Compute Pass@k

```robotframework
${pass_at_5}=    Stat.Get Pass At K    runs=${runs}    k=5
```

Pass@k = (number of trials that passed) / `trials_run`. By default, the
predicate checks `r.metadata.completeness == "complete"`. Pass a custom
predicate via `predicate=${{lambda r: ...}}` for skill-activation or
custom-success cases.

### 3. Assert against the rate

```robotframework
Should Be True    ${pass_at_5} >= 0.8
```

Pin the threshold based on what you observed historically — Pass@5 ≥ 0.8
says "the agent activates the right skill ≥ 80% of the time across 10
trials, sampling 5 at a time."

## What if the default predicate doesn't fit my keyword?

Some Tier-2/3 keywords (e.g., `Skill.Get Activation Decision`) return
custom dataclasses without a `metadata.completeness` field — the default
predicate would return 0.0 silently. See
[deferred-work `DF-7.3-S1`](../../_bmad-output/implementation-artifacts/deferred-work.md)
for the documented incompatibility.

**Custom predicate workaround:**

```robotframework
${pass}=    Stat.Get Pass At K    runs=${runs}    k=5
...    predicate=${{lambda r: isinstance(r.result, $$ACT) and r.result.activated}}
```

(Where `$$ACT` is `AgentEval.skills.types.ActivationDecision`. Pass via
RF `Set Variable` if needed.)

## Cross-references

- Recipe #4 (Devon's stacked validation) — applies the Pass@k pattern to
  skill activation reliability.
- [`docs/contracts/error-class-hierarchy.md`](../contracts/error-class-hierarchy.md)
  FR56 — polling-ban message contract.
- ADR-019 — AssertionEngine adoption + polling ban + validate disabled by
  default.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Stat.Get Pass At K` returns 0.0 every time | Default predicate doesn't match your keyword's result type. | Pass a custom `predicate=` kwarg. |
| `PollingDisallowedError` fires | You passed `polling=N` to a Tier-2/3 keyword OR used `validate` operator without opt-in. | Wrap in `Stat.Run N Times` instead. |
| `CostExceededError` fires mid-run | The 10-trial cohort exceeds `agenteval.yaml::max_cost_usd`. | Lower N, or raise `max_cost_usd` via CLI / env. |
