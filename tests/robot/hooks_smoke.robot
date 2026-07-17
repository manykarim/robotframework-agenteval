*** Settings ***
Documentation     Tier-1 smoke suite for HooksLibrary. Proves the library loads
...               and its deterministic keywords run end-to-end as a real RF
...               library - no LLM, no subprocess execution.
Library           HooksLibrary

*** Variables ***
${SETTINGS}       ${CURDIR}/fixtures/settings.json

*** Test Cases ***
Get Config Parses The Nested Hook Schema
    ${config}=    Hook.Get Config    ${SETTINGS}
    Length Should Be              ${config}[PreToolUse]    1
    Should Be Equal As Strings   ${config}[PreToolUse][0][type]       command
    Should Be Equal As Strings   ${config}[PreToolUse][0][command]    echo hi

Get Hooks For Event Statically Resolves The Matcher
    ${config}=    Hook.Get Config    ${SETTINGS}
    ${hooks}=     Hook.Get Hooks For Event    ${config}    PreToolUse    tool_name=Bash
    Length Should Be    ${hooks}    1
    ${none}=      Hook.Get Hooks For Event    ${config}    PreToolUse    tool_name=Read
    Length Should Be    ${none}     0

Validate Matcher Syntax Accepts A Valid Matcher
    ${valid}=      Hook.Validate Matcher Syntax    Bash|Edit
    Should Be True    ${valid}
    ${matches}=    Hook.Validate Matcher Syntax    Bash|Edit    subject=Edit
    Should Be True    ${matches}
