*** Settings ***
Documentation    DF-RFMCP-E2E-01 smoke suite — drives minimax M2.7 through
...              rf-mcp's robotmcp MCP server via the test-suite-local
...              `MinimaxMcpOrchestrator` (closes DF-4.1-S2 narrowly for the
...              dogfood path; production wiring lands in Phase-1.5 per
...              `docs/phase-1-5-carry-overs.md`).
...
...              Proves the LLM ↔ rf-mcp ↔ metrics pipeline end-to-end with
...              a single trivial tool-call round-trip. Larger scenarios
...              (TodoMVC) live in separate suites and are gated behind
...              browser-deps availability.
...
...              Execution: ``uv run robot tests/dogfood/rf-mcp/test_metrics_e2e_smoke.robot``
...              from the repo root. The orchestrator is imported by absolute
...              path via ``${CURDIR}`` so no ``--pythonpath`` flag is needed;
...              ``.env`` is auto-loaded by the orchestrator on import.
...
...              Requires:
...              - rf-mcp repo at ``%{RF_MCP_REPO_ROOT=/home/many/workspace/rf-mcp}``
...                with ``uv sync`` already run (robotmcp must be uv-runnable).
...              - ``MINIMAX_API_KEY`` + ``MINIMAX_BASE_URL`` + ``MINIMAX_MODEL``
...                in ``.env`` at repo root (gitignored). When the key is unset
...                the test ``Skip``s cleanly rather than failing.
...
...              Skips cleanly when ``MINIMAX_API_KEY`` is unset so CI runs
...              without credentials don't false-fail.

Library          AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
Library          AgentEval.metrics.library.MetricsLibrary    allow_external_mcp_blind=True    WITH NAME    Metrics
Library          OperatingSystem
Library          Collections
Library          ${CURDIR}/_minimax_orchestrator.py    WITH NAME    Orchestrator

Suite Setup      Set Suite-Wide Server Handle
Suite Teardown   Stop Suite Server
Test Setup       Skip If Credentials Missing

*** Variables ***
${VENDORED_MCP_JSON}        ${CURDIR}/.mcp.json
${RF_MCP_REPO_ROOT}         %{RF_MCP_REPO_ROOT=/home/many/workspace/rf-mcp}
${ROBOTMCP_SERVER_NAME}     robotmcp

*** Keywords ***
Set Suite-Wide Server Handle
    [Documentation]    Mirrors the suite-handle pattern from
    ...                ``test_mcp_surface_parity.robot``. ``cwd=`` workaround
    ...                still applies (DF-3.3-S1).
    Set Suite Variable    ${HANDLE}    ${NONE}
    Directory Should Exist    ${RF_MCP_REPO_ROOT}    rf-mcp repo not found at ${RF_MCP_REPO_ROOT}; set RF_MCP_REPO_ROOT env var or clone rf-mcp there
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    ${entry}=    Set Variable    ${servers["${ROBOTMCP_SERVER_NAME}"]}
    ${args}=    Evaluate    ['--directory', $RF_MCP_REPO_ROOT] + list($entry["args"])
    ${handle}=    MCP.Start Server
    ...    name=${ROBOTMCP_SERVER_NAME}
    ...    transport=stdio
    ...    command=${entry["command"]}
    ...    args=${args}
    ...    env=${entry["env"]}
    Set Suite Variable    ${HANDLE}    ${handle}

Stop Suite Server
    Run Keyword If    "${HANDLE}" != "${NONE}"    MCP.Stop Server    ${HANDLE}

Skip If Credentials Missing
    [Documentation]    Skip cleanly when MINIMAX_API_KEY is absent so the
    ...                suite remains runnable in CI / other-operator contexts
    ...                without forcing every machine to carry the key.
    ...                **Security:** delegates to the orchestrator's Python-
    ...                level env check so the credential value never enters
    ...                RF's variable namespace (would otherwise be logged
    ...                plaintext to ``log.html``).
    Orchestrator.Skip If Minimax Credentials Missing

*** Test Cases ***

Minimax Calls At Least One Rf-mcp Tool Successfully
    [Documentation]    Smoke test — drives minimax through rf-mcp's tool surface
    ...                with a minimal introspection-style prompt that asks the
    ...                model to discover the available tools and call ONE safe
    ...                one. Verifies the LLM ↔ MCP ↔ metrics pipeline shape
    ...                without depending on browser/Playwright deps.
    [Tags]    smoke    e2e    live-llm    rfmcp
    ${prompt}=    Catenate    SEPARATOR=\n
    ...    You have access to MCP tools exposed by the rf-mcp `robotmcp` server.
    ...    Your task: identify ONE safe, side-effect-free tool from the available
    ...    tools (for example, a tool that returns library status, available
    ...    keywords, or session info — NOT one that executes Robot Framework
    ...    code or starts a browser). Call that tool exactly once with sensible
    ...    arguments, then briefly summarize what it returned.
    ${result}=    Orchestrator.Send Prompt With Mcp Tools
    ...    prompt=${prompt}
    ...    handle=${HANDLE}
    ...    max_iterations=4

    # Trajectory shape — at least one tool was called and no errors surfaced.
    ${count}=    Metrics.Get Tool Call Count    ${result}
    Should Be True    ${count} >= 1    Expected ≥1 tool call, got ${count}

    ${success_rate}=    Metrics.Get Tool Success Rate    ${result}
    Should Be Equal As Numbers    ${success_rate}    1.0    Expected 100%% success, got ${success_rate}

    # Token usage was reported (LLM actually ran).
    ${usage}=    Metrics.Get Token Usage    ${result}
    Should Be True    ${usage.input_tokens} > 0    Expected non-zero prompt tokens
    Should Be True    ${usage.output_tokens} > 0    Expected non-zero completion tokens

    # mcp_coverage projection on the result.
    Should Be Equal    ${result.metadata.mcp_coverage}    subprocess_with_observer
    Should Be Equal    ${result.metadata.completeness}    complete

    # Latency was captured.
    Should Be True    ${result.latency_seconds} > 0    Expected positive wall-clock latency

    Log    Trajectory: ${count} call(s), input=${usage.input_tokens} tokens, output=${usage.output_tokens} tokens, latency=${result.latency_seconds}s
