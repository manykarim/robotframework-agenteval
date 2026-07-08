## ADDED Requirements

### Requirement: Get Conversation Results extracts the per-turn result list

The system SHALL provide `Get Conversation Results    <conv-or-transcript>`
returning the ordered `list[AgentRunResult]` of agent turns, so every existing
metrics keyword that accepts `AgentRunResult | list[AgentRunResult]`
(`Get Cost Total`, `Get Latency`, `Get Latency P95`, `Get Token Usage`,
`Get Tool Call Count`, `Get Tool Call Names`, etc.) aggregates over a
conversation with no new per-metric code. The keyword SHALL be Tier-1 (pure
extraction) and SHALL accept both a live `ConversationHandle` and a frozen
`ConversationTranscript`.

#### Scenario: Existing aggregation keywords work over a conversation
- **WHEN** `${results} =    Get Conversation Results    ${conv}` is followed by
  `${cost} =    Get Cost Total    ${results}` and
  `${p95} =    Get Latency P95    ${results}`
- **THEN** the cost SHALL equal the sum of the agent turns' `cost_usd` values
  and the latency percentile SHALL be computed over the per-turn
  `latency_seconds` values

#### Scenario: Order matches turn order
- **WHEN** results are extracted from a 3-agent-turn conversation
- **THEN** the list SHALL have length 3 with element i corresponding to the
  i-th agent turn chronologically

### Requirement: Get Turn Count reports conversation length

The system SHALL provide `Get Turn Count    <conv-or-transcript>` returning
the number of agent turns (an integer; one "turn" = one user→agent exchange).
It SHALL be Tier-1.

#### Scenario: Turn count after a scripted exchange
- **WHEN** two `Send Message` calls have completed on a handle
- **THEN** `Get Turn Count    ${conv}` SHALL return `2`

#### Scenario: Turn count bounds a simulation
- **WHEN** a `Simulate User` run with `max_turns=5` returns transcript `${t}`
- **THEN** `${count} =    Get Turn Count    ${t}` combined with
  `Should Be True    ${count} <= 5` SHALL pass

### Requirement: Metric keywords document conversation usage with determinism tiers

The new keywords' docstrings SHALL follow the Browser-Library table style used
across the codebase, carry explicit determinism-tier annotations
(`[Tier 1 — Deterministic]`), and show a conversation-aggregation example so
libdoc renders a self-contained recipe for per-turn cost/latency analysis.

#### Scenario: Libdoc carries a conversation aggregation example
- **WHEN** libdoc is generated for the library
- **THEN** `Get Conversation Results` documentation SHALL include an example
  chaining into at least one existing aggregation keyword
