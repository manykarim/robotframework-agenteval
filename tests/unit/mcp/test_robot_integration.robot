*** Settings ***
Documentation    Story 2.3 RF integration test — imports the `MCP`
...              sub-library directly + verifies the 3 Tier-1
...              static-inspection keywords work end-to-end inside
...              an RF execution context.

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
