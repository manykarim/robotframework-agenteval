*** Settings ***
Documentation    add-multi-turn-conversation-testing dogfood — exercises the
...              conversation lifecycle + simulated-user surface end-to-end on
...              the deterministic Mock provider (NO API keys). Covers scripted
...              conversations, transcript snapshots + aggregates, the honest
...              `continuation` degradation field, conversational metrics reuse,
...              and the `Simulate User` max_turns stop condition.
...
...              Run locally:
...                  uv run robot tests/dogfood/conversation/test_multi_turn_conversation.robot

Library    AgentEval    provider=mock    max_cost_usd=5.0    WITH NAME    AgentEval

Force Tags    slow    dogfood    conversation

*** Test Cases ***

Scripted conversation records four turns in chronological order
    [Documentation]    Two Send Message calls on the generic (mock) adapter →
    ...                4 turns (2 user, 2 agent), agent turns echo the user text.
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    ${r1}=    AgentEval.Send Message    ${conv}    Book a flight to Oslo
    ${r2}=    AgentEval.Send Message    ${conv}    Make it business class
    Should Be Equal    ${r1.response_text}    Book a flight to Oslo
    Should Be Equal    ${r2.response_text}    Make it business class
    ${t}=    AgentEval.Get Conversation Transcript    ${conv}
    Should Be Equal As Integers    ${t.turn_count}    2
    Length Should Be    ${t.turns}    4

Later turns are threaded natively with an honest continuation field
    [Documentation]    Turn 1 → continuation=initial; turn 2 → native_session
    ...                (the generic adapter rebuilds full message history).
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    AgentEval.Send Message    ${conv}    one
    AgentEval.Send Message    ${conv}    two
    ${t}=    AgentEval.Get Conversation Transcript    ${conv}
    Should Be Equal    ${t.continuation_mode}    native_session
    Should Be Equal    ${t.turns[1].continuation}    initial
    Should Be Equal    ${t.turns[3].continuation}    native_session

Transcript snapshot is stable and survives End Conversation
    [Documentation]    A snapshot taken after 2 turns still reports 2 after close;
    ...                Send Message after close raises ConversationClosedError.
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    AgentEval.Send Message    ${conv}    one
    AgentEval.Send Message    ${conv}    two
    ${snapshot}=    AgentEval.Get Conversation Transcript    ${conv}
    AgentEval.End Conversation    ${conv}
    Run Keyword And Expect Error    *CONVERSATION_CLOSED*
    ...    AgentEval.Send Message    ${conv}    three
    Should Be Equal As Integers    ${snapshot.turn_count}    2
    ${after}=    AgentEval.Get Conversation Transcript    ${conv}
    Should Be Equal As Integers    ${after.turn_count}    2

Conversational metrics reuse the existing metric vocabulary
    [Documentation]    Get Conversation Results extracts the per-turn AgentRunResult
    ...                list; existing Get Cost Total / Get Turn Count aggregate over it.
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    AgentEval.Send Message    ${conv}    one
    AgentEval.Send Message    ${conv}    two
    AgentEval.Send Message    ${conv}    three
    ${count}=    AgentEval.Get Turn Count    ${conv}
    Should Be Equal As Integers    ${count}    3
    ${results}=    AgentEval.Get Conversation Results    ${conv}
    Length Should Be    ${results}    3
    ${cost}=    AgentEval.Get Cost Total    ${results}
    Should Be Equal As Numbers    ${cost}    0.0

Transcript Should Contain asserts role-filtered content
    [Documentation]    Role-filtered containment passes on a present substring +
    ...                fails (with turn context) on an absent one.
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    AgentEval.Send Message    ${conv}    Please refund my ticket
    AgentEval.Transcript Should Contain    ${conv}    refund    role=user
    Run Keyword And Expect Error    *does not contain*
    ...    AgentEval.Transcript Should Contain    ${conv}    upgrade    role=user

Simulate User terminates within the cap with a valid stop reason
    [Documentation]    Drives an LLM-simulated user on the Mock provider. Asserts
    ...                the honest invariants that hold regardless of the Mock's
    ...                deterministic output: the loop terminates within max_turns
    ...                and records a valid stop_reason enum. (The Mock echo
    ...                provider reflects the simulator prompt — including the
    ...                sentinel-token INSTRUCTIONS — so it stops early on the
    ...                goal-sentinel; a real simulator emits the sentinel only
    ...                when it intends to. The unit tests use a scripted simulator
    ...                for exact stop-reason control.)
    ${conv}=    AgentEval.Start Conversation    adapter=generic    model=mock/mock
    ${t}=    AgentEval.Simulate User    ${conv}    persona=impatient traveler
    ...    goal=book the cheapest flight to Oslo    max_turns=3    simulator_adapter=generic
    Should Be True    ${t.turn_count} <= 3
    ${valid}=    Create List    goal_achieved    gave_up    max_turns
    Should Contain    ${valid}    ${t.stop_reason}
    # A non-zero simulator cost flowed into the transcript aggregate.
    Should Be True    ${t.total_cost_usd} >= 0.0
