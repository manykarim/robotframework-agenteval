## ADDED Requirements

### Requirement: A library constructs and runs an agent adapter via keywords

The library SHALL provide an `AgentLibrary` (namespace prefix `Agent.`) with a
keyword to construct an adapter and a keyword to run a prompt through it, so a user
can drive an agent and obtain a raw `AgentRunResult` without reaching into internal
modules or `Evaluate`. `Agent.Get Adapter` SHALL accept an adapter slug OR an object
already satisfying the `Adapter` protocol, forward construction configuration as
native Robot Framework arguments, and return an adapter. `Agent.Run Agent` SHALL
accept an adapter (slug or object) and a prompt, forward per-run arguments to the
adapter's `run()`, and return the resulting `AgentRunResult`. Both keyword names
SHALL be multi-word after the namespace dot.

#### Scenario: Construct an adapter and run a prompt

- **WHEN** a user calls `Agent.Get Adapter` with a slug and configuration, then
  `Agent.Run Agent` with that adapter and a prompt
- **THEN** an `AgentRunResult` is returned that the existing metric/trace reader
  keywords consume unchanged

#### Scenario: Run a prompt from a bare slug

- **WHEN** a user calls `Agent.Run Agent` with a slug string (rather than a
  pre-built adapter) and a prompt
- **THEN** the adapter is resolved from the slug and the prompt is run, so
  families that need no construction config (CLI, one-shot generic) need no
  separate construct step

### Requirement: One run path works across all adapter families

`Agent.Run Agent` SHALL drive any adapter that satisfies the `Adapter` protocol —
the in-process pydantic-ai adapter, the generic LiteLLM adapter, and each
coding-agent CLI adapter — through the single `run(prompt) -> AgentRunResult` seam,
without per-family branching in the keyword surface. Per-run arguments that differ
by family (e.g. a CLI `timeout`/`cwd`) SHALL be forwarded as native keyword
arguments to the adapter's `run()`.

#### Scenario: The same keyword drives a CLI adapter and an in-process adapter

- **WHEN** `Agent.Run Agent` is called once with a coding-agent CLI slug and once
  with an in-process adapter object
- **THEN** each returns a normalized `AgentRunResult` and the metric keywords read
  both the same way

### Requirement: Run failures are classified centrally, never fabricated

The library SHALL centralize the transient/budget failure taxonomy in one shared
classifier, keyed on structured exception signals (HTTP status code, exception
`__cause__`, and type) rather than exception-class-name string matching. When
`Agent.Run Agent` catches a run failure it SHALL classify it into one of
`budget_exceeded`, `provider_error`, or `timeout`, or treat it as a genuine fault.
When the classified category is listed in the keyword's `skip_on` argument the
keyword SHALL skip the test (naming the category and adapter); a `budget_exceeded`
failure that is not skipped SHALL be re-raised as the existing `BudgetExceededError`;
an unlisted transient SHALL re-raise the original error; and a genuine
config/auth/harness fault (e.g. missing extra, tier violation, missing binary,
non-retryable HTTP status) SHALL always raise and SHALL NEVER be skipped. The
keyword SHALL NOT fabricate an `AgentRunResult` for a failed run.

#### Scenario: A budget-exceeded run is skipped when opted in

- **WHEN** a run exceeds its request/usage limit and `skip_on` includes
  `budget_exceeded`
- **THEN** the test is skipped with a message naming the category and adapter, and
  no `AgentRunResult` is fabricated

#### Scenario: A non-retryable HTTP fault always raises

- **WHEN** a run fails with a non-retryable HTTP status (e.g. 401/403/404) even if
  `provider_error` is listed in `skip_on`
- **THEN** the keyword raises rather than skipping, so an auth/config bug cannot
  masquerade as a transient skip

#### Scenario: A transient provider error not opted-in re-raises

- **WHEN** a run fails with a classified transient provider error and `skip_on`
  does not list `provider_error`
- **THEN** the original error is raised (the run is not silently turned into a
  passing empty result)

### Requirement: Running an agent enforces the agent tier uniformly

`Agent.Run Agent` SHALL enforce the no-model (deterministic) tier guard before
dispatching to any adapter, so a Tier-3 run inside a deterministic scope is rejected
uniformly regardless of adapter family.

#### Scenario: A run inside a deterministic scope is rejected

- **WHEN** `Agent.Run Agent` is invoked inside a deterministic (Tier-1) scope
- **THEN** it raises a tier-violation error before any adapter call
