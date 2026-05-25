*** Settings ***
Documentation    Example: drive the bundled echo MCP server (Epic 3 / Story 8b.1).
Library    AgentEval
Suite Setup       Setup Bundled Echo
Suite Teardown    Teardown Bundled Echo

*** Variables ***
${HANDLE}    ${NONE}

*** Test Cases ***
Echo Tool Roundtrips A Message
    [Documentation]    Calls the bundled `echo` tool + asserts the response.
    ${result}=    MCP.Call Tool    ${HANDLE}    echo    message=hello
    Should Be True    ${result.success}    msg=expected echo tool to succeed; got is_error=${result.is_error} (error=${result.error_message})

*** Keywords ***
Setup Bundled Echo
    ${HANDLE}=    MCP.Start Server    ${CURDIR}/fixtures/.mcp.json    bundled-echo
    Set Suite Variable    ${HANDLE}

Teardown Bundled Echo
    Run Keyword If    $HANDLE is not None    MCP.Stop Server    ${HANDLE}
