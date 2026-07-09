*** Settings ***
Documentation    Example: validate a skill file's frontmatter.
...              This is a static check — it reads the skill Markdown and
...              inspects its YAML frontmatter, so it needs no API keys.
Library    AgentEval

*** Test Cases ***
Example Skill Has Valid Frontmatter
    [Documentation]    Reads tests/fixtures/example-skill.md and asserts its
    ...                frontmatter is valid (has the four required fields with
    ...                the correct types).
    ${frontmatter}=    Skill.Get Frontmatter    ${CURDIR}/fixtures/example-skill.md
    Skill.Should Be Valid Frontmatter    ${frontmatter}
    Should Be Equal As Strings    ${frontmatter}[name]    example-search
