# Recipe #3: Tool Discoverability cohort

**Persona:** Mei (MCP Tool Author) — anyone shipping an MCP server who wants evidence that the agent reliably picks the right tool for a representative task distribution.
**FR coverage:** FR10a (MVP Tool Discoverability), FR55-ASCII + dict (cohort heatmap).

## TL;DR

Run a task-cohort against your MCP tools + visualize the Pass@k matrix:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Echo Tool Cohort Discoverability
    ${result}=    MCP.Get Tool Discoverability
    ...    mcp_config=${CURDIR}/fixtures/.mcp.json
    ...    tasks=${CURDIR}/fixtures/echo-tasks.yaml
    ...    adapter=generic    provider=mock    trials_per_task=5
    ...    max_cost_usd=5.0
    ${heatmap}=    Get Cohort Heatmap    ${result}
    Log    ${heatmap.as_ascii()}
    # Assert minimum cohort-level pass rate.
    Should Be True    ${result.summary.overall_pass_rate} >= 0.7
```

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
  expected_tools: []  # decoy — agent should NOT call echo here
```

### 2. Run the cohort

`MCP.Get Tool Discoverability` is Tier-3 (`@guarded_fanout`) — protected by
`max_cost_usd` + `max_runtime_seconds` budgets from your `agenteval.yaml`.

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

Feed `as_dict()` output to a downstream renderer (HTML / Grafana / Allure)
or pin specific cells in assertions.

## Phase-1 limitations

Single-model heatmap (one column per `Get Cohort Heatmap` call). Multi-model
comparison (rows=tasks, columns=models) is Phase-2 / Epic 13.

## Cross-references

- Recipe #2 (Pass@k over polling) — the per-task Pass@k math.
- [`docs/contracts/conformance-fixture-format.md`](../contracts/conformance-fixture-format.md)
  — task-YAML schema.
- Story 4.4 sprint-status line — MVP Tool Discoverability ratification.
