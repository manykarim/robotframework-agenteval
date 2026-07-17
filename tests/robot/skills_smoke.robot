*** Settings ***
Documentation     Tier-1 smoke suite for SkillsLibrary. Proves the library loads
...               and its deterministic frontmatter keywords run end-to-end as a
...               real RF library - no LLM.
Library           SkillsLibrary

*** Variables ***
${SKILL}          ${CURDIR}/fixtures/skills/example.md

*** Test Cases ***
Get Frontmatter Parses The YAML Block
    ${fm}=    Skill.Get Frontmatter    ${SKILL}
    Should Be Equal As Strings    ${fm}[name]    example-skill

Should Be Valid Frontmatter Enforces The Contract
    ${fm}=    Skill.Get Frontmatter    ${SKILL}
    Skill.Should Be Valid Frontmatter    ${fm}

Get Allowed Tools Returns The Declared List
    ${tools}=    Skill.Get Allowed Tools    ${SKILL}
    Length Should Be    ${tools}    2
    Should Contain      ${tools}    Read
    Should Contain      ${tools}    Grep
