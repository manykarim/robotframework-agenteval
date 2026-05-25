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
    # MCP.Start Server signature (mcp/library.py:195): keyword-only-style positional
    # args mapped to (name, transport, command, args). Robot's keyword binding
    # accepts either positional or `name=` form. The 2-step `Get Server Config`
    # then `Start Server` was the original intent — corrected per Story 8b.1 v0.2.0
    # kilo/minimax cross-LLM review FINDING-1 (the previous form passed the
    # config path as `name` and "bundled-echo" as `transport`, which is not a
    # valid Transport literal).
    ${HANDLE}=    MCP.Start Server    bundled-echo    stdio    python    args=${{['-m','AgentEval.mcp.bundled.echo']}}
    Set Suite Variable    ${HANDLE}

Teardown Bundled Echo
    Run Keyword If    $HANDLE is not None    MCP.Stop Server    ${HANDLE}
