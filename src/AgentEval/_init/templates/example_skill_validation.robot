*** Settings ***
Documentation    Example: validate a skill's frontmatter (Epic 2 / Story 8b.1).
Library    Collections
Library    AgentEval
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill

*** Test Cases ***
Example Skill Has Valid Frontmatter
    [Documentation]    Reads tests/fixtures/example-skill.md + asserts the
    ...                frontmatter has the required `name` + `description` fields.
    ...                Uses `Library AgentEval.skills.library.SkillsLibrary WITH NAME Skill`
    ...                because `SkillsLibrary` is excluded from the top-level
    ...                AgentEval DynamicCore composition (Story 2.2 — avoids
    ...                `Get Frontmatter` name collision with `SubagentsLibrary`).
    ${frontmatter}=    Skill.Get Frontmatter    ${CURDIR}/fixtures/example-skill.md
    Dictionary Should Contain Key    ${frontmatter}    name
    Dictionary Should Contain Key    ${frontmatter}    description
    Should Be Equal As Strings    ${frontmatter}[name]    example-search
