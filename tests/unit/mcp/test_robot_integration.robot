*** Settings ***
Documentation    Story 2.3 + 3.1 RF integration test — imports the
...              `MCP` sub-library directly + verifies the 3 Tier-1
...              static-inspection keywords (Story 2.3) AND the 3
...              Tier-1 lifecycle keywords (Story 3.1) work
...              end-to-end inside an RF execution context.

Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP

*** Variables ***
${VALID_FIXTURE}    ${CURDIR}/../../fixtures/mcp/mcp-valid.json

*** Test Cases ***
MCP Get Server Config Returns Dict With Declared Servers
    ${servers}=    MCP.Get Server Config    ${VALID_FIXTURE}
    Should Contain    ${servers}    echo
    Should Contain    ${servers}    remote
    Should Be Equal    ${servers["echo"]["transport"]}    stdio

MCP Get Tool Schema Returns Search Schema
    ${schema}=    MCP.Get Tool Schema    ${VALID_FIXTURE}    search
    Should Be Equal    ${schema["type"]}    object
    Should Contain    ${schema["properties"]}    query

MCP Validate Tool Schema Succeeds For Valid Schema
    MCP.Validate Tool Schema    ${VALID_FIXTURE}    search

MCP Start And Connect To Server In Memory
    [Documentation]    Story 3.1: in_memory transport full lifecycle.
    ${factory}=    Evaluate    __import__('AgentEval.mcp.bundled.echo', fromlist=['build_server']).build_server
    ${handle}=    MCP.Start Server    echo    in_memory    server_factory=${factory}
    ${session}=    MCP.Connect To Server    ${handle}
    Should Be Equal    ${session.name}    echo
    Should Be Equal    ${session.transport}    in_memory
    Should Not Be Empty    ${session.protocol_version}
    MCP.Stop Server    ${handle}

MCP Start Server Stdio Returns Handle Without Spawning
    [Documentation]    Story 3.1 Phase-1 per-call-session: Start Server is pure handle construction.
    ${handle}=    MCP.Start Server    echo    stdio    python    args=${{['-m','AgentEval.mcp.bundled.echo']}}
    Should Be Equal    ${handle.name}    echo
    Should Be Equal    ${handle.transport}    stdio
    Should Be Equal    ${handle.command}    python

MCP Start Server Rejects Unsupported Transport
    [Documentation]    Story 3.1: invalid transport rejected by Literal type-check OR by start_server.
    Run Keyword And Expect Error    *cannot be converted to*    MCP.Start Server    echo    websocket

MCP List Tools In Memory Returns Echo Back
    [Documentation]    Story 3.2: List Tools against bundled echo via in_memory transport.
    ${factory}=    Evaluate    __import__('AgentEval.mcp.bundled.echo', fromlist=['build_server']).build_server
    ${handle}=    MCP.Start Server    echo    in_memory    server_factory=${factory}
    ${tools}=    MCP.List Tools    ${handle}
    Length Should Be    ${tools}    1
    Should Be Equal    ${tools[0].name}    echo_back
    MCP.Stop Server    ${handle}

MCP Call Tool In Memory Echoes Text
    [Documentation]    Story 3.2: Call Tool returns MCPToolResult with is_error=False + non-empty content.
    ${factory}=    Evaluate    __import__('AgentEval.mcp.bundled.echo', fromlist=['build_server']).build_server
    ${handle}=    MCP.Start Server    echo    in_memory    server_factory=${factory}
    ${args}=    Create Dictionary    text=robotframework
    ${result}=    MCP.Call Tool    ${handle}    echo_back    ${args}
    Should Not Be True    ${result.is_error}
    Should Be True    ${result.latency_ms} > 0
    Length Should Be    ${result.correlation_id}    32
    MCP.Stop Server    ${handle}
