*** Settings ***
Documentation    Story 2.2 RF integration test — imports the `Subagent`
...              sub-library directly + verifies `Get Frontmatter`
...              works end-to-end inside an RF execution context.

Library    AgentEval.subagents.library.SubagentsLibrary    WITH NAME    Subagent

*** Variables ***
${VALID_FIXTURE}    ${CURDIR}/../../fixtures/subagents/example-valid.md

*** Test Cases ***
Subagent Get Frontmatter Returns Dict With Required Fields
    ${def}=    Subagent.Get Frontmatter    ${VALID_FIXTURE}
    Should Be Equal    ${def["name"]}    example-valid-subagent
    Should Contain    ${def["description"]}    canonical valid sub-agent
    Length Should Be    ${def["tools"]}    2

Subagent Get Frontmatter Includes Optional Model Field
    ${def}=    Subagent.Get Frontmatter    ${VALID_FIXTURE}
    Should Be Equal    ${def["model"]}    claude-sonnet-4-6
