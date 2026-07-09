# fanout-guardrails Specification

## Purpose
TBD - created by archiving change remove-dead-machinery. Update Purpose after archive.
## Requirements
### Requirement: No-budget calls skip the metering machinery
When a `@guarded_fanout`-decorated keyword is invoked and BOTH resolved budgets (`max_cost_usd` and `max_runtime_seconds`, after applying the test-only budget-override kwarg and instance-attribute lookup) are `None`, the wrapper SHALL invoke the decorated body directly without spawning a metering thread, without allocating breach state, and without binding a cancellation event.

#### Scenario: No meter thread when nothing to enforce
- **WHEN** a guarded keyword runs on a host library whose `max_cost_usd` and `max_runtime_seconds` are both `None`
- **THEN** no thread named `agenteval-guarded-fanout-meter` is created during the call and the body's return value is passed through unchanged

#### Scenario: Cancel event unbound on the fast path
- **WHEN** the decorated body calls `current_cancel_event()` during a no-budget invocation
- **THEN** it returns `None` (the documented out-of-frame value)

#### Scenario: Exceptions propagate unchanged on the fast path
- **WHEN** the decorated body raises an exception during a no-budget invocation
- **THEN** the original exception propagates to the caller without budget-enforcement wrapping

### Requirement: Budgeted calls keep full 3-layer enforcement
When at least one budget is configured (non-`None` `max_cost_usd` or `max_runtime_seconds`), the wrapper SHALL preserve the existing enforcement path unchanged: Layer-1 pre-flight estimation (when an `estimator` is supplied), a non-daemon background meter thread polling cumulative cost (Layer 2) and wall-clock runtime (Layer 3), fail-closed handling of cost-source failures, and the post-body raise of `CostExceededError` / `RuntimeBudgetExceededError` on breach.

#### Scenario: Meter thread spawned when a budget is set
- **WHEN** a guarded keyword runs with `max_cost_usd` set to a non-`None` value
- **THEN** a non-daemon `agenteval-guarded-fanout-meter` thread is started and joined around the body

#### Scenario: Runtime breach still enforced
- **WHEN** a guarded keyword with `max_runtime_seconds` configured exceeds that wall-clock budget
- **THEN** the call fails with `RuntimeBudgetExceededError`

#### Scenario: Test-only budget override still honored
- **WHEN** a call supplies the test-only budget-override kwarg with a non-`None` budget on a host whose instance attributes carry no budgets
- **THEN** the metering path is taken using the overridden budgets

### Requirement: Estimator surface retained
The `estimator` parameter of `@guarded_fanout` SHALL remain part of the decorator's signature and Layer-1 contract (ADR-015), even though no production decorator site currently supplies one.

#### Scenario: Estimator pre-flight rejection still works
- **WHEN** a guarded call with a configured `max_cost_usd` uses an estimator whose cost estimate exceeds the budget
- **THEN** the call fails with `CostExceededError` before the body executes

