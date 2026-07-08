# Recipe #3: Tool Discoverability cohort

**Use case:** you ship an MCP server and want evidence that an agent reliably
picks the right tool across a representative set of tasks.

## TL;DR

Run a task cohort against your MCP tools and visualize the Pass@k matrix:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Echo Tool Cohort Discoverability
    ${result}=    MCP.Get Tool Discoverability
    ...    mcp_server=bundled-echo
    ...    tasks=${CURDIR}/fixtures/echo-tasks.yaml
    ...    adapter=generic    provider=mock    trials_per_task=5
    ...    max_cost_usd=5.0
    ${heatmap}=    Get Cohort Heatmap    ${result}
    Log    ${heatmap.as_ascii()}
    # Assert a minimum cohort-level pass rate.
    Should Be True    ${result.summary.overall_pass_rate} >= 0.7
```

`MCP.Get Tool Discoverability` lives in `MCPLibrary`, so import it with a
prefix; `Get Cohort Heatmap` comes from the top-level `AgentEval` library.

## Step-by-step

### 1. Author a task YAML

Define a cohort of representative prompts:

```yaml
# tests/fixtures/echo-tasks.yaml
- id: task-1
  prompt: Echo back the word hello
  expected_tools: [echo]
- id: task-2
  prompt: Repeat my message verbatim
  expected_tools: [echo]
- id: task-3
  prompt: What is 2+2?
  expected_tools: []  # decoy — the agent should NOT call echo here
```

### 2. Run the cohort

`MCP.Get Tool Discoverability` is a Tier-3 (stochastic fan-out) keyword,
protected by the `max_cost_usd` and `max_runtime_seconds` budgets you set in
`agenteval.yaml`.

### 3. Render the heatmap

```robotframework
${heatmap}=    Get Cohort Heatmap    ${result}
${ascii}=    Set Variable    ${heatmap.as_ascii()}
Log    ${ascii}
```

Renders a box-drawing table:

```
┌──────────┬───────────┐
│ Task     │ default   │
├──────────┼───────────┤
│ task-1   │ 1.00      │
│ task-2   │ 0.80      │
│ task-3   │ 0.00      │
└──────────┴───────────┘
```

### 4. Programmatic consumption

```robotframework
${data}=    Set Variable    ${heatmap.as_dict()}
# {"task-1": {"default": 1.0}, "task-2": {"default": 0.8}, "task-3": {"default": 0.0}}
```

Feed the `as_dict()` output to a downstream renderer (HTML / Grafana / Allure)
or pin specific cells in assertions.

## Comparing multiple adapters

`MCP.Get Tool Discoverability` produces a single-column heatmap. To compare
several coding agents on the same task set with statistical significance, use
`MCP.Compare Tool Discoverability` (requires the `[agenteval-advanced]` extra).

## Cross-references

- Recipe #2 (Pass@k over polling) — the per-task Pass@k math.
- [`docs/contracts/conformance-fixture-format.md`](../contracts/conformance-fixture-format.md)
  — the task-YAML schema.
