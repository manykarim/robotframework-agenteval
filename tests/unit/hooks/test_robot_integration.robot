*** Settings ***
Documentation    Story 2.2 RF integration test — imports the `Hook`
...              sub-library directly + verifies `Get Config` works
...              end-to-end inside an RF execution context.

Library    AgentEval.hooks.library.HooksLibrary    WITH NAME    Hook

*** Variables ***
${VALID_FIXTURE}    ${CURDIR}/../../fixtures/hooks/settings-valid.json

*** Test Cases ***
Hook Get Config Returns Dict With Event Arrays
    ${config}=    Hook.Get Config    ${VALID_FIXTURE}
    Should Contain    ${config}    hooks.PreToolUse
    Should Contain    ${config}    hooks.PostToolUse
    Should Contain    ${config}    hooks.Stop

Hook Entries Preserve Required Command Field
    ${config}=    Hook.Get Config    ${VALID_FIXTURE}
    ${entry}=    Set Variable    ${config["hooks.PreToolUse"][0]}
    Should Be Equal    ${entry["command"]}    echo pre-tool-use
