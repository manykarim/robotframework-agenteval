# multi-turn-scenario-yaml Specification

## Purpose
TBD - created by archiving change add-multi-turn-conversation-testing. Update Purpose after archive.
## Requirements
### Requirement: Scenario evals accept turns as an alternative to prompt (BREAKING)

The scenario YAML schema (`ScenarioEval`) SHALL gain an optional
`turns: list[str]` field — an ordered list of user messages executed as ONE
threaded conversation. Validation SHALL require **exactly one of** `prompt` |
`turns` per eval (**BREAKING** pre-1.0 change: `prompt` was previously
REQUIRED; existing single-`prompt` YAML files remain valid). Violations
(both present, neither present, empty `turns`, or non-string turn entries)
SHALL raise `InvalidScenarioYAMLError` with a JSON-Pointer `field_name`, per
the existing loader convention.

#### Scenario: Existing single-prompt YAML still loads
- **WHEN** a pre-existing scenario file with only `evals: [{prompt: ...}]` is
  passed to `Load Scenario`
- **THEN** it SHALL load and validate exactly as before

#### Scenario: Turns-based eval loads
- **WHEN** an eval declares `turns: ["Book a flight to Oslo", "Make it business class"]`
  and no `prompt`
- **THEN** `Load Scenario` SHALL return a `ScenarioEval` with the two turns in
  order and `prompt` unset

#### Scenario: Both prompt and turns is rejected
- **WHEN** an eval declares both `prompt:` and `turns:`
- **THEN** `Load Scenario` SHALL raise `InvalidScenarioYAMLError` whose
  `field_name` points at the offending eval and whose message states the
  exactly-one-of rule

#### Scenario: Neither prompt nor turns is rejected
- **WHEN** an eval declares neither `prompt:` nor `turns:`
- **THEN** `Load Scenario` SHALL raise `InvalidScenarioYAMLError`

### Requirement: Run Scenario executes turns as one threaded conversation

For a `turns:` eval, `Run Scenario` SHALL start a conversation against the
resolved adapter (same adapter/model/provider precedence rules as today:
explicit kwarg > scenario YAML > library default), send each turn
sequentially through the conversation-continuation machinery, and end the
conversation. `repeat: N` SHALL repeat the WHOLE conversation N times with a
fresh handle each repetition. The keyword SHALL keep returning a flat
`list[AgentRunResult]` in stable order — each multi-turn eval contributing
one result per turn per repetition, interleaved in execution order — so
existing index-based consumers keep working.

#### Scenario: Flat results preserve per-turn granularity
- **WHEN** a scenario has one eval with 3 turns and `repeat: 2`
- **THEN** `Run Scenario` SHALL return 6 `AgentRunResult` items, ordered
  turn-1..3 of repetition 1 followed by turn-1..3 of repetition 2

#### Scenario: Fresh conversation per repetition
- **WHEN** `repeat: 2` executes a turns eval
- **THEN** repetition 2's first turn SHALL NOT see repetition 1's history

#### Scenario: Mixed suites execute coherently
- **WHEN** a scenario mixes a single-`prompt` eval and a `turns:` eval
- **THEN** the prompt eval SHALL execute as an independent single-shot run and
  the turns eval as one conversation, results concatenated in eval order

### Requirement: Adapter capability differences degrade honestly in YAML runs

Turns-based scenario execution SHALL use the same optional-`run_turn`
continuation contract as the keyword surface: adapters with native support
thread natively; adapters without it fall back to history-replay prompting.
Each returned `AgentRunResult`'s turn-threading mode SHALL be inspectable via
the recorded per-turn `continuation` value (`"initial"`,
`"native_session"`, or `"replayed_history"`) so YAML-driven cross-adapter
comparisons carry the degradation signal in-band — the same honesty-field
philosophy as `mcp_coverage` (ADR-016). No adapter SHALL hard-fail a `turns:`
eval solely for lacking native continuation.

#### Scenario: Replay-only adapter completes a turns eval with honest marking
- **WHEN** a `turns:` eval runs against an adapter without `run_turn`
- **THEN** all turns SHALL complete via history replay and turns after the
  first SHALL carry `continuation="replayed_history"`

#### Scenario: Native adapter marks native threading
- **WHEN** the same eval runs against the `generic` adapter
- **THEN** turns after the first SHALL carry `continuation="native_session"`

### Requirement: Multi-turn Run Scenario stays Tier-3 budget-guarded

Turns-based execution SHALL run inside the existing `@guarded_fanout()` on
`Run Scenario`, so `max_cost_usd` / `max_runtime_seconds` budgets cover the
sum of all conversation turns across all evals and repetitions.

#### Scenario: Budget covers the whole multi-turn fan-out
- **WHEN** accumulated cost across a scenario's conversation turns exceeds the
  configured `max_cost_usd`
- **THEN** the existing cost-budget error SHALL abort the run without
  starting further turns

