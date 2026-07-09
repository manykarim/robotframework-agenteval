*** Settings ***
Documentation    Example: run an agent prompt against the Mock provider.
...              The Mock provider needs no API keys, so this test runs
...              anywhere out of the box.
Library    AgentEval

*** Test Cases ***
Mock Provider Returns A Response
    [Documentation]    Drives `Send Prompt` against the Mock provider and
    ...                checks the returned result.
    ${result}=    Send Prompt    adapter=generic    prompt=Say hello    provider=mock
    Should Not Be Empty    ${result.response_text}
    Should Be Equal As Strings    ${result.metadata.completeness}    complete
