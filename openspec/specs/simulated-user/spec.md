# simulated-user Specification

## Purpose
TBD - created by archiving change add-multi-turn-conversation-testing. Update Purpose after archive.
## Requirements
### Requirement: Simulate User drives a conversation with an LLM user simulator

The system SHALL provide a `Simulate User    ${conv}    persona=<text>
goal=<text>    max_turns=5` keyword that repeatedly (a) generates the next
user message from a simulator LLM prompted with the persona, the goal, and the
rendered transcript so far, then (b) sends it via the same turn machinery as
`Send Message`, until a stop condition is reached. It SHALL return the final
`ConversationTranscript`. The simulator adapter/model SHALL be configurable
via `simulator_adapter=` (default `"generic"`) and `simulator_model=`,
mirroring the `judge_adapter`/`judge_model` naming convention. Scripted
conversations (plain `Send Message` sequences) SHALL remain the co-equal,
documented alternative style, including mixing scripted opening turns with a
subsequent `Simulate User` on the same handle.

#### Scenario: Simulation produces alternating turns up to the cap
- **WHEN** `Simulate User    ${conv}    persona=impatient traveler
  goal=book the cheapest flight to Oslo    max_turns=3` runs against the mock
  provider and no stop sentinel is emitted
- **THEN** the conversation SHALL gain at most 3 simulated user turns with an
  agent turn after each, and the returned transcript SHALL record
  `stop_reason="max_turns"`

#### Scenario: Mixed scripted-then-simulated style works on one handle
- **WHEN** a test sends 2 scripted `Send Message` turns and then invokes
  `Simulate User` on the same handle
- **THEN** the simulator's first generated message SHALL be conditioned on the
  scripted turns already in the transcript

### Requirement: Simulation stop conditions are explicit and inspectable

The simulator prompt SHALL instruct the simulator to emit a goal-achieved or
giving-up sentinel when the goal is met or unmeetable; the loop SHALL stop on
either sentinel or on reaching `max_turns`. Sentinel text SHALL be stripped
from the recorded user turns. The returned transcript SHALL record
`stop_reason` with value `"goal_achieved"`, `"gave_up"`, or `"max_turns"` so
tests can assert HOW the conversation ended, not just that it ended.

#### Scenario: Goal achievement stops the loop early
- **WHEN** the simulator emits the goal-achieved sentinel on turn 2 of a
  `max_turns=5` simulation
- **THEN** the loop SHALL stop after that turn and the transcript SHALL record
  `stop_reason="goal_achieved"` with the sentinel absent from the turn content

#### Scenario: Tests can require genuine goal completion
- **WHEN** a test asserts `Should Be Equal    ${transcript.stop_reason}    goal_achieved`
  after a simulation that hit the turn cap
- **THEN** the assertion SHALL fail (the transcript honestly reports
  `max_turns`)

### Requirement: Simulate User is Tier-3 and budget-guarded

`Simulate User` SHALL be annotated `@tier(3)` and wrapped in
`@guarded_fanout()` so the existing library-level `max_cost_usd` and
`max_runtime_seconds` budgets (ADR-015 / `_HostBudgetPlumbing`) govern the
whole simulation loop — refusing entry or aborting mid-loop exactly as
existing Tier-3 fan-out keywords do. Simulator-call costs SHALL be included in
the transcript's `total_cost_usd` alongside agent-turn costs.

#### Scenario: Budget breach aborts the simulation
- **WHEN** a simulation's accumulated cost exceeds the configured
  `max_cost_usd` mid-loop
- **THEN** the guardrail SHALL raise the existing cost-budget error and no
  further simulator or agent calls SHALL be made

#### Scenario: Simulator costs are not hidden
- **WHEN** a simulation completes N turns with a non-zero-cost simulator
- **THEN** `total_cost_usd` on the transcript SHALL include both agent-turn
  and simulator-call costs

### Requirement: cache_key makes simulations repeatable

The simulator SHALL cache each generated user message on disk when
`cache_key=<string>` is provided (under the run's output directory, keyed by a
hash of the cache key, the turn index, and the transcript-so-far) and SHALL
reuse cached messages on subsequent runs, so re-runs replay identical user messages while agent-side
behavior remains subject to its own determinism tier. The transcript SHALL
record per-simulated-turn cache status (`"hit"`, `"miss"`, or `"disabled"`
when no `cache_key` was given). A changed agent reply mid-conversation SHALL
invalidate subsequent cached turns naturally (the transcript hash diverges).

#### Scenario: Second run replays cached user messages
- **WHEN** the same simulation runs twice with `cache_key=booking-v1` and the
  agent replies identically both times
- **THEN** the second run SHALL issue zero simulator LLM calls and its
  simulated user messages SHALL be byte-identical to the first run's

#### Scenario: Diverging agent replies fall back to live generation
- **WHEN** a cached simulation re-runs and the agent's turn-1 reply differs
  from the cached run
- **THEN** turn-2-and-later simulator messages SHALL be regenerated live
  (cache miss) rather than replaying now-incoherent cached messages

### Requirement: Simulated turns are foundation-grade for sibling changes

Simulated user turns SHALL flow through the standard turn machinery
(`ConversationTurn` with role `"user"`, agent turns carrying full
`AgentRunResult`), so downstream consumers — judge, metrics, and the sibling
`add-red-team-probes` change (which may build Crescendo-style multi-turn
attack loops on this keyword surface) — need no simulation-specific types.

#### Scenario: Judge and metrics consume simulated conversations unchanged
- **WHEN** a simulation completes and the test calls
  `Get Conversation Results` and `Judge.Get Score` on its turns
- **THEN** both SHALL work identically to a scripted conversation of the same
  shape

