# Recipe 10: Multi-Turn Conversation Testing

**Use case:** test an agent across a *conversation*, not a single prompt —
either as a **scripted** sequence of `Send Message` keywords (an RF test body IS
a readable conversation script) or with a **simulated user** (`Simulate User`)
that drives the conversation from a persona + goal. Judge and metrics work over
a whole conversation with the vocabulary you already know.

## Overview

Two co-equal styles, plus the mix:

| Style | How | Determinism |
|-------|-----|-------------|
| **Scripted** | `Start Conversation` → N × `Send Message` → assertions | You write every user turn — fully reproducible on the mock provider |
| **Simulated** | `Start Conversation` → `Simulate User` (persona/goal/max_turns) | LLM-driven; Tier-3, budget-guarded; `cache_key` makes re-runs replay identical user messages |
| **Mixed** | scripted opening turns, then `Simulate User` on the same handle | The simulator conditions its first message on the scripted turns |

Every agent turn records an honest `continuation` field —
`"initial"` / `"native_session"` / `"replayed_history"` — the same
honesty-field philosophy as `mcp_coverage`. Native adapters (`generic` via
message-history, `claude-code-cli` via `--resume`) thread natively; adapters
without native continuation degrade to history-replay and *say so* in the
transcript rather than silently pretending.

## Style 1 — Scripted conversation

```robotframework
*** Settings ***
Library    AgentEval    provider=mock

*** Test Cases ***
Booking Conversation Is Coherent
    ${conv} =    Start Conversation    adapter=generic    model=mock/mock
    ${r1} =    Send Message    ${conv}    Book a flight to Oslo
    ${r2} =    Send Message    ${conv}    Actually make it business class
    # A turn's result is a plain AgentRunResult — every metric/assertion applies.
    ${cost} =    Get Cost Total    ${r2}
    # The transcript is an immutable snapshot with reconciled aggregates.
    ${t} =    Get Conversation Transcript    ${conv}
    Should Be Equal As Integers    ${t.turn_count}    2
    Should Be Equal    ${t.continuation_mode}    native_session
    Transcript Should Contain    ${conv}    Oslo    role=user
    End Conversation    ${conv}
```

## Style 2 — Simulated user

```robotframework
*** Settings ***
Library    AgentEval    provider=mock    max_cost_usd=1.0

*** Test Cases ***
Simulated Traveler Reaches The Goal
    ${conv} =    Start Conversation    adapter=generic    model=mock/mock
    ${t} =    Simulate User    ${conv}    persona=impatient traveler
    ...    goal=book the cheapest flight to Oslo    max_turns=5
    ...    simulator_adapter=generic    cache_key=booking-v1
    # Assert HOW it ended, not just that it ended.
    Should Be True    ${t.turn_count} <= 5
    # Metrics + judge aggregate over the whole conversation.
    ${results} =    Get Conversation Results    ${conv}
    ${total} =    Get Cost Total    ${results}
```

## Style 3 — Mixed (scripted opening, then simulate to finish)

```robotframework
*** Settings ***
Library    AgentEval    provider=mock    max_cost_usd=1.0

*** Test Cases ***
Scripted Opening Then Simulated Completion
    ${conv} =    Start Conversation    adapter=generic    model=mock/mock
    Send Message    ${conv}    I want to book a flight
    Send Message    ${conv}    From Berlin
    # The simulator's first message is conditioned on the two scripted turns.
    ${t} =    Simulate User    ${conv}    persona=budget-conscious traveler
    ...    goal=finish booking the cheapest option    max_turns=3
    ${count} =    Get Turn Count    ${conv}
```

## Judging a conversation

`Judge.Get Score` already accepts a per-turn `AgentRunResult` (per-turn judging
is free) AND a whole `ConversationTranscript`:

```robotframework
*** Settings ***
Library    AgentEval    provider=mock

*** Test Cases ***
Judge A Turn And A Whole Conversation
    ${conv} =    Start Conversation    adapter=generic    model=mock/mock
    ${r2} =    Send Message    ${conv}    Make it business class
    # Per-turn: the turn's result IS an AgentRunResult.
    ${turn_score} =    Judge.Get Score    result=${r2}    rubric=${CURDIR}/rubrics/upsell.md
    # Whole conversation: pass the transcript.
    ${t} =    Get Conversation Transcript    ${conv}
    ${whole} =    Judge.Get Score    result=${t}    rubric=${CURDIR}/rubrics/goal-completion.md
    # One-line assertion form (fails the test unless the turn passes the rubric).
    Judge Turn Should Pass    ${conv}    ${CURDIR}/rubrics/upsell.md    turn=-1
```

## Scenario YAML `turns:` (declarative multi-turn)

Scenario YAML gains a per-eval `turns:` list executed as ONE threaded
conversation. **Exactly one of `prompt` | `turns`** per eval (this is a
pre-1.0 BREAKING validation change — existing single-`prompt` files remain
valid):

```yaml
# scenarios/booking.yaml
evals:
  - turns:
      - Book a flight to Oslo
      - Actually make it business class
    repeat: 2          # repeats the WHOLE conversation twice (fresh handle each)
  - prompt: Summarize the itinerary   # single-shot evals still work
```

`Run Scenario` keeps returning a flat `list[AgentRunResult]` — each multi-turn
eval contributes one result per turn per repetition, order-stable.

## Honest degradation

An adapter that cannot natively continue a session is never forced to fake it.
Its turns after the first record `continuation="replayed_history"` (the agent
re-reads the history as text; no persistent tool/workspace state across turns).
Pass `Start Conversation    require_native=True` to fail fast up front with
`ConversationContinuationUnsupportedError` for tests where replay semantics
would invalidate the eval.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConversationClosedError` on `Send Message` | The handle was `End Conversation`-ed | Start a fresh conversation; `Get Conversation Transcript` still works on a closed handle |
| `continuation_mode` is `replayed_history` when you expected native | The adapter has no `run_turn` | Use `generic` / `claude-code-cli`, or accept honest replay; `require_native=True` fails fast |
| `stop_reason == "max_turns"` but you expected `goal_achieved` | The simulator never emitted the goal sentinel | Assert `stop_reason` explicitly; raise `max_turns` or tune the persona/goal |
| `Simulate User` raises `CostExceededError` | The Tier-3 budget (`max_cost_usd`) was breached mid-loop | Raise the budget, lower `max_turns`, or add a `cache_key` (re-runs cost ~half) |

## Sibling: red-team multi-turn attacks

Multi-turn attack orchestration (Crescendo-style escalation) is **not** in this
recipe — it is the sibling OpenSpec change `add-red-team-probes`, which builds
its attack loops directly on `ConversationHandle` + `Simulate User`. This
change is deliberately that foundation; the attack layer is a follow-up, not
implemented here.
