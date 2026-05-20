*** Settings ***
Documentation    Story 6.4 dogfood — exercises agenteval's Story 6.1 `MetricsLibrary`
...              surface against `AgentRunResult` fixtures parallel-derived from
...              `robotframework-agentskills`' scoring-test domain (per Story 6.4
...              D-2 framing reframe + D-4 fixture-driven scope per C44+C46).
...
...              Per Story 6.4 spec: 9 metric keywords × ≥1 happy + ≥1 empty/edge
...              variant = AC-6.4.2 coverage. Parity-checklist mapping at
...              `parity-checklist-agentskills-metrics.md`.
...
...              CI wiring deferred per Phase-1 norm: `dogfood-integration.yml`
...              is install-smoke-only by design (Story 1a.2 HIGH-1 lesson).
...              Run locally:
...
...                  uv run robot tests/dogfood/agentskills/test_metrics_parity.robot
...
...              All tests carry `[Tags] slow dogfood` so the standard pytest
...              sweep doesn't pick them up.

Library    AgentEval    WITH NAME    AgentEval
Library    ${CURDIR}/fixtures/agentskills_sessions.py

Force Tags    slow    dogfood    epic-6

*** Test Cases ***

Get Tool Call Count returns 1 for single-tool session
    [Documentation]    Story 6.1 FR19 — MetricsLibrary.Get Tool Call Count happy path
    ...                against agentskills-shape successful-search session fixture.
    ${run}=    Get Successful Search Run
    ${count}=    AgentEval.Get Tool Call Count    ${run}
    Should Be Equal As Integers    ${count}    1

Get Tool Call Count returns 2 for unnecessary-tool session
    [Documentation]    Two tool calls (search + delete) in the unnecessary-call fixture.
    ${run}=    Get Unnecessary Tool Call Run
    ${count}=    AgentEval.Get Tool Call Count    ${run}
    Should Be Equal As Integers    ${count}    2

Get Tool Call Names preserves chronological order
    [Documentation]    FR19 — names list preserves chronological order + duplicates
    ...                (agentskills' SessionScorecard.tool_names parity).
    ${run}=    Get Unnecessary Tool Call Run
    ${names}=    AgentEval.Get Tool Call Names    ${run}
    Should Be Equal    ${names}    ${{["search", "delete"]}}

Get Tool Hit Rate computes correctly when expected tools matched
    [Documentation]    FR20 — tool_hit_rate = (expected_tools_observed) / (expected_tools_count).
    ${run}=    Get Successful Search Run
    ${rate}=    AgentEval.Get Tool Hit Rate    ${run}    expected_tools=${{["search"]}}
    Should Be Equal As Numbers    ${rate}    1.0

Get Tool Hit Rate computes partial when expected tools missing
    [Documentation]    expected=["search", "fetch"], observed=["search"] → 0.5.
    ${run}=    Get Successful Search Run
    ${rate}=    AgentEval.Get Tool Hit Rate    ${run}    expected_tools=${{["search", "fetch"]}}
    Should Be Equal As Numbers    ${rate}    0.5

Get Tool Success Rate is 1.0 for happy-path session
    [Documentation]    FR20 — success_rate = (tools without error) / total_tools.
    ${run}=    Get Successful Search Run
    ${rate}=    AgentEval.Get Tool Success Rate    ${run}
    Should Be Equal As Numbers    ${rate}    1.0

Get Tool Success Rate is 0.0 for partial-completeness session with timeout
    [Documentation]    Partial session's tool call has error="timeout" → success_rate=0.
    ${run}=    Get Partial Completeness Run
    ${rate}=    AgentEval.Get Tool Success Rate    ${run}
    Should Be Equal As Numbers    ${rate}    0.0

Get Unnecessary Call Rate is 0.5 when one of two calls is unnecessary
    [Documentation]    FR21 — unnecessary_call_rate = (calls outside expected_tools) / total_calls.
    ...                Unnecessary fixture: ["search", "delete"], expected=["search"] → 0.5.
    ${run}=    Get Unnecessary Tool Call Run
    ${rate}=    AgentEval.Get Unnecessary Call Rate    ${run}    expected_tools=${{["search"]}}
    Should Be Equal As Numbers    ${rate}    0.5

Get Token Usage returns Usage dataclass
    [Documentation]    FR22 — `Get Token Usage` returns Usage(input_tokens, output_tokens, cached_input_tokens).
    ${run}=    Get Successful Search Run
    ${usage}=    AgentEval.Get Token Usage    ${run}
    Should Be Equal As Integers    ${usage.input_tokens}    50
    Should Be Equal As Integers    ${usage.output_tokens}    30

Get Latency returns mean tool-call latency ms
    [Documentation]    FR22 — `Get Latency` is the mean of tool_calls[*].latency_ms.
    ${run}=    Get Successful Search Run
    ${latency}=    AgentEval.Get Latency    ${run}
    Should Be Equal As Numbers    ${latency}    120.5

Get Latency P95 equals max for single-tool runs
    [Documentation]    FR22 — P95 of [x] is x; sanity check for the percentile boundary.
    ${run}=    Get Successful Search Run
    ${p95}=    AgentEval.Get Latency P95    ${run}
    Should Be Equal As Numbers    ${p95}    120.5

Get Cost Total returns the AgentRunResult cost_usd
    [Documentation]    FR22 — `Get Cost Total` returns `result.cost_usd` (USD scalar).
    ${run}=    Get Successful Search Run
    ${cost}=    AgentEval.Get Cost Total    ${run}
    Should Be Equal As Numbers    ${cost}    0.0042
