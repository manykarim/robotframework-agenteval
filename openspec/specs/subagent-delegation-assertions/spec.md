# subagent-delegation-assertions Specification

## Purpose
TBD - created by archiving change add-subagent-delegation-testing. Update Purpose after archive.
## Requirements
### Requirement: Delegations are extractable from an agent run result

The system SHALL provide a Tier-1 keyword `Subagent.Get Delegations` that,
given an `AgentRunResult`, returns a list of `DelegationRecord` objects — one
per tool invocation in `result.tool_calls` whose tool name is in the
delegation-tool set (default `{"Task"}`, matched case-insensitively;
overridable via a `delegation_tool=` argument). Each `DelegationRecord` MUST
carry the resolved subagent identity (probed from the trace `args` in the
fixed key order `subagent_type` → `agent_type` → `agent` → `name`), the
delegation prompt when present in `args`, the trace `sequence_index`,
`latency_ms`, `error`, and the raw `args` mapping. Records MUST be ordered by
`sequence_index`. The keyword MUST NOT invoke any agent or network call.

#### Scenario: Run with two Task-tool invocations yields two ordered records
- **WHEN** `Subagent.Get Delegations` is called on an `AgentRunResult` whose
  `tool_calls` contain two traces named `Task` with
  `args={"subagent_type": "code-reviewer", "prompt": "review the diff"}` and
  `args={"subagent_type": "test-writer", "prompt": "add tests"}` plus one
  unrelated `Bash` trace
- **THEN** it SHALL return exactly two `DelegationRecord`s, ordered by
  `sequence_index`, with `subagent` values `code-reviewer` and `test-writer`
  and their respective prompts populated

#### Scenario: Run with no delegation-tool invocations yields an empty list
- **WHEN** `Subagent.Get Delegations` is called on a result whose `tool_calls`
  contain only non-delegation tools (e.g. `Read`, `Bash`)
- **THEN** it SHALL return an empty list and SHALL NOT raise

#### Scenario: Custom delegation tool name is honored
- **WHEN** `Subagent.Get Delegations` is called with
  `delegation_tool=dispatch_agent` on a result containing a
  `dispatch_agent` trace with `args={"agent": "docs-writer"}`
- **THEN** it SHALL return one record with `subagent` equal to `docs-writer`
  (resolved via the identity-key probe order)

#### Scenario: Delegation trace without a recognizable identity key degrades visibly
- **WHEN** a delegation-tool trace's `args` contain none of the identity keys
- **THEN** the returned record SHALL have `subagent` equal to the empty string
  and SHALL retain the raw `args` mapping for diagnostics

### Requirement: Delegation-occurrence assertion on an existing result

The system SHALL provide a Tier-1 keyword `Subagent.Should Have Delegated To`
taking an `AgentRunResult` and an expected subagent name, passing when at
least one extracted `DelegationRecord` has a `subagent` exactly equal
(case-sensitive) to the expected name, and otherwise raising
`SubagentDelegationAssertionError` whose diagnostics include the expected
subagent, the list of observed delegations (or an explicit statement that none
occurred), and a `fix_suggestion`.

#### Scenario: Assertion passes when the expected subagent was delegated to
- **WHEN** `Subagent.Should Have Delegated To    ${result}    code-reviewer`
  is called on a result containing a `Task` trace with
  `subagent_type: code-reviewer`
- **THEN** the keyword SHALL return without raising

#### Scenario: Assertion fails listing observed delegations
- **WHEN** the same assertion is called on a result whose only delegation went
  to `test-writer`
- **THEN** it SHALL raise `SubagentDelegationAssertionError` naming
  `code-reviewer` as expected and listing `test-writer` among observed
  delegations, with a non-empty `fix_suggestion`

#### Scenario: Assertion fails when no delegation occurred at all
- **WHEN** the assertion is called on a result with zero delegation-tool traces
- **THEN** it SHALL raise `SubagentDelegationAssertionError` stating that no
  delegations were observed

### Requirement: Delegation-absence assertion on an existing result

The system SHALL provide a Tier-1 keyword `Subagent.Should Not Have Delegated`
taking an `AgentRunResult` and an optional subagent name. With a name, it
SHALL fail if any delegation to that subagent occurred; without a name, it
SHALL fail if ANY delegation occurred. Failures raise
`SubagentDelegationAssertionError` listing the offending delegations.

#### Scenario: No-delegation assertion passes on a delegation-free run
- **WHEN** `Subagent.Should Not Have Delegated    ${result}` is called on a
  result with no delegation-tool traces
- **THEN** the keyword SHALL return without raising

#### Scenario: No-delegation assertion fails when any delegation occurred
- **WHEN** the same call is made on a result containing one `Task` trace
- **THEN** it SHALL raise `SubagentDelegationAssertionError` listing the
  observed delegation(s)

#### Scenario: Targeted absence assertion ignores other subagents
- **WHEN** `Subagent.Should Not Have Delegated    ${result}    deployer` is
  called on a result that delegated only to `code-reviewer`
- **THEN** the keyword SHALL return without raising

### Requirement: Tier-2 routing probe runs a prompt and asserts the chosen subagent

The system SHALL provide a Tier-2 keyword `Subagent.Should Delegate To` that
sends a prompt to a named adapter exactly once (constructed via the same
adapter-discovery path used by `SkillsLibrary`, with `adapter=`, `model=`, and
forwarded `**kwargs`), extracts delegations from the returned
`AgentRunResult`, and asserts the expected subagent is among them. Providing a
`polling` argument MUST raise `PollingDisallowedError` per FR28. On
no-match the keyword MUST raise `SubagentDelegationAssertionError` carrying
the prompt, expected subagent, observed delegations, the run's response text
as reasoning, and a `fix_suggestion`.

#### Scenario: Probe passes when the adapter run delegated to the expected subagent
- **WHEN** `Subagent.Should Delegate To    Review my PR    code-reviewer
  adapter=stub` is called and the stub adapter's result contains a `Task`
  trace with `subagent_type: code-reviewer`
- **THEN** the keyword SHALL return without raising after exactly one adapter
  run

#### Scenario: Probe fails with routing diagnostics
- **WHEN** the adapter run delegated to a different subagent (or none)
- **THEN** it SHALL raise `SubagentDelegationAssertionError` whose diagnostics
  include the prompt, the expected subagent, and the observed delegations

#### Scenario: Polling is rejected
- **WHEN** the keyword is called with `polling=1.0`
- **THEN** it SHALL raise `PollingDisallowedError` without invoking the adapter

### Requirement: Tier-3 delegation-decision getter composes with fan-out statistics

The system SHALL provide a Tier-3 `@guarded_fanout` keyword
`Subagent.Get Delegation Decision` that runs a prompt via a named adapter once
and returns a `DelegationDecision` dataclass with `delegated` (bool — true iff
at least one delegation to the expected subagent occurred), `delegations`
(the extracted `DelegationRecord` list), `reasoning` (the response text),
`cost_usd`, and `latency_seconds`. Providing `polling` MUST raise
`PollingDisallowedError` (FR28). The keyword MUST NOT raise on a routing
miss — it reports the decision so `Stat.Run N Times` cohorts can aggregate it.

#### Scenario: Decision reflects a successful routing
- **WHEN** `Subagent.Get Delegation Decision    Review my PR    code-reviewer
  adapter=stub` runs against a stub whose result delegates to `code-reviewer`
- **THEN** the returned decision SHALL have `delegated == True`, a non-empty
  `delegations` list, and `cost_usd`/`latency_seconds` copied from the run

#### Scenario: Routing miss returns a decision instead of raising
- **WHEN** the stub's result contains no delegation to the expected subagent
- **THEN** the keyword SHALL return a decision with `delegated == False` and
  SHALL NOT raise

### Requirement: Routing Pass@k reuses the existing estimator with a hard-coded predicate

The system SHALL provide a Tier-1 keyword `Subagent.Get Routing Pass At K`
taking a `list[KeywordRun]` (typically from `Stat.Run N Times` wrapping
`Subagent.Get Delegation Decision`) and `k`, returning the HumanEval unbiased
Pass@k estimate computed via the existing
`AgentEval.stats._internal._compute_pass_at_k` helper. The pass-predicate MUST
be hard-coded to `isinstance(run.result, DelegationDecision) and
run.result.delegated`, and the keyword MUST NOT expose a `predicate`
argument. Invalid `k` (`k < 1`, `k > len(runs)`, empty runs) SHALL raise
`ValueError` via the shared helper's validation.

#### Scenario: Pass@k over mixed routing outcomes
- **WHEN** `Subagent.Get Routing Pass At K` is called with 5 runs of which 3
  carry `DelegationDecision(delegated=True)` results and `k=2`
- **THEN** it SHALL return the same value
  `AgentEval.stats._internal._compute_pass_at_k(3, 5, 2)` produces

#### Scenario: Foreign result types count as failures, not crashes
- **WHEN** the runs list contains a `KeywordRun` whose `result` is not a
  `DelegationDecision`
- **THEN** that run SHALL count as a non-pass and the keyword SHALL NOT raise

#### Scenario: Invalid k fails loud
- **WHEN** the keyword is called with `k=0` or `k` greater than the number of runs
- **THEN** it SHALL raise `ValueError`

### Requirement: Routing-accuracy cohort evaluation over a tasks YAML

The system SHALL provide a Tier-3 `@guarded_fanout` keyword
`Subagent.Get Routing Accuracy` that loads a routing-tasks YAML (a `tasks`
list where each entry has `id`, `prompt`, and `expected_subagent`), runs
`trials_per_task` adapter calls per task (default 3), and returns a
`SubagentRoutingResult` with per-task results (task id, expected subagent,
trial outcomes, per-task Pass@k) and a summary including `routing_accuracy`
(fraction of trials whose delegations included the expected subagent).
Structurally invalid tasks YAML SHALL raise
`InvalidSubagentRoutingTasksError`; `trials_per_task < 1` SHALL raise
`ValueError`; providing `polling` SHALL raise `PollingDisallowedError` (FR28).

#### Scenario: Cohort run aggregates per-task routing outcomes
- **WHEN** `Subagent.Get Routing Accuracy` runs a 2-task YAML with
  `trials_per_task=2` against a stub adapter that always delegates to
  `code-reviewer`, where task 1 expects `code-reviewer` and task 2 expects
  `test-writer`
- **THEN** the returned result SHALL contain 2 per-task entries and a summary
  with `routing_accuracy == 0.5`

#### Scenario: Malformed tasks YAML fails loud
- **WHEN** the tasks YAML is missing the `expected_subagent` field on an entry
  (or `tasks` is not a list)
- **THEN** the keyword SHALL raise `InvalidSubagentRoutingTasksError` with the
  offending file path in its diagnostics

#### Scenario: Polling and invalid trial counts are rejected
- **WHEN** the keyword is called with `polling=2.0` or with `trials_per_task=0`
- **THEN** it SHALL raise `PollingDisallowedError` or `ValueError`
  respectively, without invoking the adapter

