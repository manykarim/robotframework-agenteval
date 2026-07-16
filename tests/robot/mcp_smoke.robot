*** Settings ***
Documentation     Tier-1 smoke suite for MCPLibrary. Exercises only the
...               deterministic schema path (no live server, no [mcp] extra).
Library           MCPLibrary

*** Variables ***
${MCP_CONFIG}     ${CURDIR}/fixtures/.mcp.json

*** Test Cases ***
Get Tool Schema Returns The Declared Input Schema
    ${schema}=    MCP.Get Tool Schema    ${MCP_CONFIG}    search
    Should Be Equal As Strings    ${schema}[type]    object
    Should Contain                ${schema}[required]    query

Validate Tool Schema Passes On A Well Formed Schema
    MCP.Validate Tool Schema    ${MCP_CONFIG}    search
