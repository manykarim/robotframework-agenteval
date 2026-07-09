# conversation-lifecycle Specification

## Purpose
TBD - created by archiving change add-multi-turn-conversation-testing. Update Purpose after archive.
## Requirements
### Requirement: Conversation lifecycle keywords manage a test-owned handle

The system SHALL provide a `ConversationLibrary` sub-library, composed into the
top-level `AgentEval` library (no separate `Library` import required), exposing
`Start Conversation`, `Send Message`, `Get Conversation Transcript`, and
`End Conversation` keywords. `Start Conversation` SHALL return a
`ConversationHandle` owned by the calling test (no library-global "current
conversation" state), constructed with an adapter name plus adapter/run kwargs
resolved via the same discovery + kwarg-splitting rules as `Send Prompt`.
`Start Conversation` SHALL be Tier-1 (no LLM call is made until the first
`Send Message`).

#### Scenario: Keywords are available from the top-level library import
- **WHEN** a `.robot` file imports only `Library    AgentEval`
- **THEN** `Start Conversation`, `Send Message`, `Get Conversation Transcript`,
  and `End Conversation` SHALL be resolvable keywords

#### Scenario: Starting a conversation returns a reusable handle without an LLM call
- **WHEN** `${conv} =    Start Conversation    adapter=generic    model=mock/mock-model`
  is executed
- **THEN** a `ConversationHandle` SHALL be returned with zero turns, and no
  adapter `run()` invocation SHALL have occurred

#### Scenario: Adapter instance is reused across turns
- **WHEN** two `Send Message` calls are made on the same handle
- **THEN** both SHALL execute against the same adapter instance constructed at
  `Start Conversation` time (session affinity), unlike `Send Prompt`'s
  per-call construction

### Requirement: Send Message executes one threaded turn and returns AgentRunResult

`Send Message    ${conv}    <text>    **kwargs` SHALL append a user turn and an
agent turn to the handle and return the agent turn's `AgentRunResult`
(unchanged shape — `response_text`, `tool_calls`, `usage`, `metadata`,
`cost_usd`, `latency_seconds`, `trace_id`), so all existing single-result
assertion and metric keywords apply to a turn without adaptation.
`Send Message` SHALL be annotated Tier-2 (stochastic single-shot).

#### Scenario: A scripted conversation is a plain keyword sequence
- **WHEN** a test executes `Send Message    ${conv}    Book a flight to Oslo`
  followed by `Send Message    ${conv}    Actually make it business class`
- **THEN** each call SHALL return an `AgentRunResult` for that turn, and the
  handle SHALL contain 4 turns (2 user, 2 agent) in chronological order

#### Scenario: Later turns see earlier turns
- **WHEN** the second `Send Message` on a handle executes
- **THEN** the underlying agent invocation SHALL include the prior turns'
  content (natively or via replay per the continuation contract), not just the
  new message

### Requirement: Conversation turns and transcripts are shared immutable types

The system SHALL define `ConversationTurn` and `ConversationTranscript` in
`AgentEval/types.py` (the cross-sub-library shared-types module).
`ConversationTurn` SHALL carry `index`, `role` (`"user"` or `"agent"`),
`content`, `result` (the turn's `AgentRunResult` for agent turns; `None` for
user turns), and `continuation` (agent turns). `Get Conversation Transcript`
SHALL return a frozen `ConversationTranscript` snapshot carrying the ordered
turns plus aggregates: `turn_count` (agent turns), `total_cost_usd`,
`total_latency_seconds`, and `continuation_mode`. Snapshots SHALL NOT mutate
when the conversation continues afterward.

#### Scenario: Transcript is a stable snapshot
- **WHEN** `${t1} =    Get Conversation Transcript    ${conv}` is taken after 2
  turns and a third `Send Message` then executes
- **THEN** `${t1}` SHALL still report the 2-turn state while a fresh
  `Get Conversation Transcript` reports 3 agent turns

#### Scenario: Aggregates reconcile with per-turn results
- **WHEN** a transcript is taken over N agent turns
- **THEN** `total_cost_usd` SHALL equal the sum of the agent turns'
  `result.cost_usd` values (plus any recorded simulator costs, when the
  conversation was driven by `Simulate User`)

### Requirement: Adapter continuation is optional, probed, and honestly reported

Conversation threading SHALL NOT modify the `CodingAgentAdapter` Protocol
(single `run()` per FR12). An adapter MAY implement an optional duck-typed
`run_turn(prompt, *, conversation_state, **kwargs) -> AgentRunResult` method;
when present, turns after the first SHALL use it (`native_session` mode). When
absent, the conversation layer SHALL fall back to composing prior turns into a
delimited history preamble passed to the adapter's ordinary `run()`
(`replayed_history` mode). Every agent turn SHALL record its threading mode in
the turn's `continuation` field with value `"initial"` (first turn),
`"native_session"`, or `"replayed_history"` — the same honest-degradation
philosophy as the ADR-016 `mcp_coverage` field. In this change the `generic`
adapter SHALL implement `run_turn` via full message-history construction, and
the `claude-code-cli` adapter SHALL implement `run_turn` via session resume
(session id captured from its stream-json init event), finalized only after an
empirical CLI probe. Other adapters SHALL degrade to `replayed_history` with
documented follow-up markers.

#### Scenario: Generic adapter threads natively
- **WHEN** a conversation runs on `adapter=generic` with the mock provider and
  two messages are sent
- **THEN** turn 1's agent turn SHALL record `continuation="initial"` and turn
  2's SHALL record `continuation="native_session"`, with the provider invoked
  with the full multi-message history on turn 2

#### Scenario: Adapter without run_turn degrades honestly
- **WHEN** a conversation runs on an adapter that does not implement `run_turn`
  and a second message is sent
- **THEN** the second agent turn SHALL record `continuation="replayed_history"`
  and the prompt passed to `run()` SHALL contain the rendered prior turns

#### Scenario: require_native fails fast on replay-only adapters
- **WHEN** `Start Conversation    adapter=<replay-only>    require_native=True`
  is executed
- **THEN** the keyword SHALL raise `ConversationContinuationUnsupportedError`
  naming the adapter and suggesting the fallback (omit `require_native`) in
  its fix suggestion, before any LLM call is made

### Requirement: Closed conversations reject further sends

`End Conversation    ${conv}` SHALL mark the handle closed and release any
native session resources. `Send Message` (and `Simulate User`) against a
closed handle SHALL raise `ConversationClosedError`. `Get Conversation
Transcript` SHALL remain readable after close.

#### Scenario: Send after close raises a typed error
- **WHEN** `End Conversation    ${conv}` has executed and a subsequent
  `Send Message    ${conv}    hello` is attempted
- **THEN** `ConversationClosedError` SHALL be raised

#### Scenario: Transcript survives close
- **WHEN** a conversation with 2 turns is ended
- **THEN** `Get Conversation Transcript    ${conv}` SHALL still return the
  2-turn transcript

### Requirement: Transcript content assertion keyword

The system SHALL provide `Transcript Should Contain    <conv-or-transcript>
<text>    role=any    as_regex=False`, failing the test when no turn of the
selected role contains the text (substring by default, regex when
`as_regex=True`). It SHALL be Tier-1 (pure inspection).

#### Scenario: Role-filtered containment passes
- **WHEN** an agent turn contains "booking confirmed" and
  `Transcript Should Contain    ${conv}    booking confirmed    role=agent`
  is executed
- **THEN** the keyword SHALL pass

#### Scenario: Missing content fails with turn context
- **WHEN** no turn contains "refund" and
  `Transcript Should Contain    ${conv}    refund` is executed
- **THEN** the keyword SHALL fail with a message reporting the searched text,
  role filter, and the number of turns inspected

