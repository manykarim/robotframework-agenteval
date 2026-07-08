*** Settings ***
Documentation    Example: call a tool on the bundled echo MCP server.
...              Runs with no API keys — the echo server ships with agenteval
...              and simply returns whatever text you send it.
Library    AgentEval
Suite Setup       Start Bundled Echo Server
Suite Teardown    Stop Bundled Echo Server

*** Variables ***
${HANDLE}    ${NONE}

*** Test Cases ***
Echo Tool Roundtrips A Message
    [Documentation]    Calls the bundled `echo_back` tool and checks the reply.
    ${result}=    MCP.Call Tool    ${HANDLE}    echo_back    text=hello
    Should Be Equal    ${result.is_error}    ${FALSE}
    ...    msg=expected the echo tool to succeed (error=${result.error_message})
    Should Contain    ${result.content}[0][text]    hello

*** Keywords ***
Start Bundled Echo Server
    # The bundled echo server runs as a subprocess over stdio. MCP.Start Server
    # builds the connection handle; each tool call opens and closes its own
    # session. Using the current interpreter keeps the example runnable from
    # any environment where agenteval is installed.
    ${handle}=    MCP.Start Server    bundled-echo    stdio    ${{ __import__('sys').executable }}
    ...    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
    Set Suite Variable    ${HANDLE}

Stop Bundled Echo Server
    Run Keyword If    $HANDLE is not None    MCP.Stop Server    ${HANDLE}
