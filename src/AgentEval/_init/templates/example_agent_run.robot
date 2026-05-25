*** Settings ***
Documentation    Example: run an agent prompt via the Mock provider (Epic 4 / Story 8b.1).
Library    AgentEval

*** Test Cases ***
Mock Provider Returns A Response
    [Documentation]    Drives `Send Prompt` against the Mock provider — no real
    ...                API keys needed; verifies the AgentRunResult contract.
    ${result}=    Send Prompt    adapter=generic    prompt=Say hello    provider=mock
    Should Not Be Empty    ${result.response_text}
    Should Be Equal As Strings    ${result.metadata.completeness}    complete
