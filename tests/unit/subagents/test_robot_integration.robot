*** Settings ***
Documentation    Story 2.2 RF integration test — imports the `Subagent`
...              sub-library directly + verifies `Get Frontmatter`
...              works end-to-end inside an RF execution context. Extended by
...              add-subagent-delegation-testing with delegation-routing +
...              config-drift keyword cases.

Library    AgentEval

*** Variables ***
${VALID_FIXTURE}    ${CURDIR}/../../fixtures/subagents/example-valid.md
${SKILLS_FIXTURE}    ${CURDIR}/../../fixtures/subagents/example-with-skills.md

*** Test Cases ***
Subagent Get Frontmatter Returns Dict With Required Fields
    ${def}=    Subagent.Get Frontmatter    ${VALID_FIXTURE}
    Should Be Equal    ${def["name"]}    example-valid-subagent
    Should Contain    ${def["description"]}    canonical valid sub-agent
    Length Should Be    ${def["tools"]}    2

Subagent Get Frontmatter Includes Optional Model Field
    ${def}=    Subagent.Get Frontmatter    ${VALID_FIXTURE}
    Should Be Equal    ${def["model"]}    claude-sonnet-4-6

Subagent Get Delegations Extracts Task Tool Invocations
    ${result}=    Build Delegation Result    code-reviewer    review the diff
    ${dels}=    Subagent.Get Delegations    ${result}
    Length Should Be    ${dels}    1
    Should Be Equal    ${dels[0].subagent}    code-reviewer

Subagent Should Have Delegated To Passes
    ${result}=    Build Delegation Result    code-reviewer    review the diff
    Subagent.Should Have Delegated To    ${result}    code-reviewer

Subagent Should Not Have Delegated Fails On Delegation
    ${result}=    Build Delegation Result    code-reviewer    review the diff
    Run Keyword And Expect Error    SubagentDelegationAssertionError*
    ...    Subagent.Should Not Have Delegated    ${result}

Subagent Should Declare Skills Passes When Declared
    Subagent.Should Declare Skills    ${SKILLS_FIXTURE}    pdf-tools    web-search

Subagent Should Declare Skills Fails When Absent
    Run Keyword And Expect Error    SubagentConfigDriftError*
    ...    Subagent.Should Declare Skills    ${VALID_FIXTURE}    pdf-tools

Subagent Tools Should Be Subset Of Passes
    Subagent.Tools Should Be Subset Of    ${SKILLS_FIXTURE}    Read    Grep    Bash

Subagent Tools Should Be Subset Of Fails On Offender
    Run Keyword And Expect Error    SubagentConfigDriftError*
    ...    Subagent.Tools Should Be Subset Of    ${SKILLS_FIXTURE}    Read

*** Keywords ***
Build Delegation Result
    [Documentation]    Construct an AgentRunResult carrying one Task-tool
    ...                delegation trace, for the Tier-1 delegation keywords.
    [Arguments]    ${subagent}    ${prompt}
    ${result}=    Evaluate
    ...    __import__('AgentEval.types', fromlist=['AgentRunResult']).AgentRunResult(response_text='ok', tool_calls=[__import__('AgentEval.types', fromlist=['ToolCallTrace']).ToolCallTrace(name='Task', args={'subagent_type': '${subagent}', 'prompt': '${prompt}'}, result=None, error=None, latency_ms=0.0, source='adapter', gen_ai_tool_call_id='i0', sequence_index=0)], usage=__import__('AgentEval.types', fromlist=['Usage']).Usage(input_tokens=1, output_tokens=1), metadata=__import__('AgentEval.types', fromlist=['AgentRunMetadata']).AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='t'*32)
    RETURN    ${result}
