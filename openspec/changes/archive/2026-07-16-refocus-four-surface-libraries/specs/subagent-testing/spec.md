## ADDED Requirements

### Requirement: SubagentsLibrary inspects frontmatter and config drift deterministically

`SubagentsLibrary` SHALL parse a subagent definition's frontmatter and provide Tier-1 assertions for config drift: that a subagent explicitly declares the skills it needs (subagents do not inherit parent skills), and that its declared tools are a subset of an expected allowlist with a fail-loud inherit-all default.

#### Scenario: Missing skill declaration is caught

- **WHEN** a user calls `Subagent.Should Declare Skills    review-checklist` on a subagent whose frontmatter omits it
- **THEN** the assertion fails, surfacing the config-drift gap

#### Scenario: Tool allowlist is enforced

- **WHEN** a user calls `Subagent.Tools Should Be Subset Of` with an allowlist the subagent exceeds
- **THEN** the assertion fails and names the disallowed tools

### Requirement: Delegations are extractable and assertable from a run result

`SubagentsLibrary` SHALL extract the set of subagent delegations from an `AgentRunResult` and provide assertions that a delegation to a named subagent did or did not occur, operating on an already-obtained result.

#### Scenario: Delegation occurrence

- **WHEN** a run result contains a Task-tool invocation to the `docs-writer` subagent
- **THEN** `Subagent.Should Have Delegated To    docs-writer` passes

#### Scenario: Delegation absence

- **WHEN** a run result contains no delegation to `db-admin`
- **THEN** `Subagent.Should Not Have Delegated    db-admin` passes

### Requirement: Routing is testable in agent mode with pass@k

`SubagentsLibrary` SHALL provide an agent-mode routing probe that runs a prompt through the adapter and asserts the chosen subagent, a decision getter that composes with the stats fan-out, and a routing pass@k plus a routing-accuracy cohort evaluation over a tasks file. These keywords SHALL be Tier-3 and SHALL resolve their adapter through the shared spine.

#### Scenario: Single routing probe

- **WHEN** a user runs `Subagent.Should Delegate To    test-writer` with a prompt that should route there
- **THEN** the keyword drives the agent once and passes only if the agent delegated to `test-writer`

#### Scenario: Routing accuracy over a cohort

- **WHEN** a user runs `Subagent.Get Routing Accuracy` over a tasks file of prompt/expected-subagent pairs
- **THEN** the keyword reports the fraction routed correctly with a confidence interval
