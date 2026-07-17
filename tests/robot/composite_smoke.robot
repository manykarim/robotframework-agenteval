*** Settings ***
Documentation     Composite smoke suite. Imports the single ``AgentEval``
...               library and calls one Tier-1 keyword from each of the four
...               surfaces, proving the one-import composite works end-to-end.
Library           AgentEval

*** Variables ***
${SETTINGS}       ${CURDIR}/fixtures/settings.json
${SKILL}          ${CURDIR}/fixtures/skills/example.md
${AGENT}          ${CURDIR}/fixtures/agents/researcher.md
${MCP_CONFIG}     ${CURDIR}/fixtures/.mcp.json

*** Test Cases ***
Composite Exposes One Keyword From Every Surface
    # Hooks surface
    ${config}=    Hook.Get Config    ${SETTINGS}
    Length Should Be    ${config}[PreToolUse]    1
    # Skills surface
    ${fm}=    Skill.Get Frontmatter    ${SKILL}
    Should Be Equal As Strings    ${fm}[name]    example-skill
    # Subagents surface
    Subagent.Should Declare Skills    ${AGENT}    example-skill
    # MCP surface
    ${schema}=    MCP.Get Tool Schema    ${MCP_CONFIG}    search
    Should Be Equal As Strings    ${schema}[type]    object
