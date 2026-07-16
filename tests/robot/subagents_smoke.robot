*** Settings ***
Documentation     Tier-1 smoke suite for SubagentsLibrary. Proves the library
...               loads and its deterministic frontmatter keywords run
...               end-to-end as a real RF library - no LLM.
Library           SubagentsLibrary

*** Variables ***
${AGENT}          ${CURDIR}/fixtures/agents/researcher.md

*** Test Cases ***
Get Frontmatter Parses The YAML Block
    ${fm}=    Subagent.Get Frontmatter    ${AGENT}
    Should Be Equal As Strings    ${fm}[name]    researcher

Should Declare Skills Requires An Explicit Declaration
    Subagent.Should Declare Skills    ${AGENT}    example-skill    web-search

Tools Should Be Subset Of An Allowlist
    Subagent.Tools Should Be Subset Of    ${AGENT}    Read    Grep    Bash
