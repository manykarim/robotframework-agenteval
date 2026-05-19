*** Settings ***
Documentation    Story 2.1 RF integration test — imports the `Skill`
...              sub-library directly + verifies the 5 Tier-1 static-
...              inspection keywords work end-to-end inside a real
...              Robot Framework execution context (not just unit-test
...              Python calls). Complements
...              tests/unit/skills/test_library.py.

Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill

*** Variables ***
${VALID_FIXTURE}    tests/fixtures/skills/example-valid.md

*** Test Cases ***
Skill Get Frontmatter Returns Dict With Required Fields
    ${frontmatter}=    Skill.Get Frontmatter    ${VALID_FIXTURE}
    Should Be Equal    ${frontmatter["name"]}    example-valid-skill
    Should Contain    ${frontmatter["description"]}    canonical valid skill
    Length Should Be    ${frontmatter["allowed-tools"]}    4
    Should Be Equal    ${frontmatter["disable-model-invocation"]}    ${False}

Skill Get Description Returns Configured String
    ${description}=    Skill.Get Description    ${VALID_FIXTURE}
    Should Start With    ${description}    A canonical valid skill

Skill Get Allowed Tools Returns Configured List
    ${tools}=    Skill.Get Allowed Tools    ${VALID_FIXTURE}
    Should Contain    ${tools}    read_file
    Should Contain    ${tools}    write_file
    Should Contain    ${tools}    search_database
    Should Contain    ${tools}    run_tests

Skill Get Disable Model Invocation Returns Bool
    ${value}=    Skill.Get Disable Model Invocation    ${VALID_FIXTURE}
    Should Be Equal    ${value}    ${False}

Skill Should Be Valid Frontmatter Passes On Complete Dict
    ${frontmatter}=    Skill.Get Frontmatter    ${VALID_FIXTURE}
    Skill.Should Be Valid Frontmatter    ${frontmatter}
