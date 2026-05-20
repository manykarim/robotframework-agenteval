*** Settings ***
Documentation    Story 6.4 dogfood — exercises agenteval's Story 6.2 `AssertionsLibrary`
...              surface against `AgentRunResult` fixtures parallel-derived from
...              `robotframework-agentskills`' scoring-test domain.
...
...              Coverage: 5 assertion keywords × 4 trajectory modes + dict-subset
...              tool-call matching + 3 response variants + FR37 IncompleteTraceError
...              gate empirical verification.
...
...              Run locally:
...                  uv run robot tests/dogfood/agentskills/test_assertions_parity.robot

Library    AgentEval    WITH NAME    AgentEval
Library    ${CURDIR}/fixtures/agentskills_sessions.py

Force Tags    slow    dogfood    epic-6

*** Test Cases ***

Trajectory Should Match exact mode passes for matching single-call session
    [Documentation]    FR23a — `mode=exact` ordered list equality.
    ${run}=    Get Successful Search Run
    AgentEval.Trajectory Should Match    ${run}    expected=${{["search"]}}    mode=exact

Trajectory Should Match exact mode fails for wrong-order trajectory
    [Documentation]    FR23a — order matters in exact mode.
    ${run}=    Get Unnecessary Tool Call Run
    Run Keyword And Expect Error    *Trajectory mismatch*
    ...    AgentEval.Trajectory Should Match    ${run}    expected=${{["delete", "search"]}}    mode=exact

Trajectory Should Match subsequence mode allows extras between expected
    [Documentation]    FR23a — `mode=subsequence` permits extras between matches.
    ${run}=    Get Unnecessary Tool Call Run
    AgentEval.Trajectory Should Match    ${run}    expected=${{["search"]}}    mode=subsequence

Trajectory Should Match set mode is unordered
    [Documentation]    FR23a — `mode=set` compares set-equality of names.
    ${run}=    Get Unnecessary Tool Call Run
    AgentEval.Trajectory Should Match    ${run}    expected=${{["delete", "search"]}}    mode=set

Tool Call Should Have Occurred matches name only
    [Documentation]    FR24 — name-only match (no args specified).
    ${run}=    Get Successful Search Run
    AgentEval.Tool Call Should Have Occurred    ${run}    tool=search

Tool Call Should Have Occurred dict-subset matches partial args
    [Documentation]    FR24 — dict-subset semantics: {"query": "paris"} ⊆ {"query": "paris", "limit": 3}.
    ${run}=    Get Successful Search Run
    AgentEval.Tool Call Should Have Occurred    ${run}    tool=search    args=${{{"query": "paris"}}}

Tool Call Should Have Occurred raises on missing tool
    [Documentation]    Missing tool → AssertionError per FR24.
    ${run}=    Get Successful Search Run
    Run Keyword And Expect Error    *No tool call matched*
    ...    AgentEval.Tool Call Should Have Occurred    ${run}    tool=nonexistent

Agent Response Should Contain matches substring in happy-path session
    [Documentation]    FR25 — substring match against `result.response_text`.
    ${run}=    Get Successful Search Run
    AgentEval.Agent Response Should Contain    ${run}    paris

Agent Response Should Match Regex matches case-sensitive pattern
    [Documentation]    FR25 — `re.search` match against response_text.
    ${run}=    Get Successful Search Run
    AgentEval.Agent Response Should Match Regex    ${run}    Found \\d+ results

Trajectory Should Match raises IncompleteTraceError on external_mixed by default
    [Documentation]    FR37 — gate fires by default on `mcp_coverage="external_mixed"`.
    ${run}=    Get External Mixed Coverage Run
    Run Keyword And Expect Error    IncompleteTraceError: *
    ...    AgentEval.Trajectory Should Match    ${run}    expected=${{["search"]}}

Tool Call Should Have Occurred raises IncompleteTraceError on external_mixed by default
    [Documentation]    FR37 — gate also fires for the tool-call assertion path.
    ${run}=    Get External Mixed Coverage Run
    Run Keyword And Expect Error    IncompleteTraceError: *
    ...    AgentEval.Tool Call Should Have Occurred    ${run}    tool=search

Trajectory Should Match regex mode matches name+args concatenation per FR23b
    [Documentation]    FR23b verbatim — `mode=regex` matches `re.fullmatch(pattern, f"{name}:{json.dumps(args, sort_keys=True, default=str)}")`.
    ...                Story 6.4 code-review HIGH-β fix 2026-05-20 (Edge HIGH-3 + Auditor HIGH-2):
    ...                pre-edit assertions suite missed the regex mode despite AC-6.4.3 verbatim
    ...                "4-mode coverage (exact / subsequence / set / regex)". Story 6.2 HIGH-γ
    ...                `default=str` fix is exercised here because the fixture's `args={"query": "paris", "limit": 3}`
    ...                round-trips through `json.dumps(..., sort_keys=True)`.
    ${run}=    Get Successful Search Run
    AgentEval.Trajectory Should Match    ${run}    expected=${{["search:\\{\"limit\": 3, \"query\": \"paris\"\\}"]}}    mode=regex

Agent Response Should Match Schema validates JSON response against schema dict
    [Documentation]    FR25 — `Agent Response Should Match Schema` exercises the 5th Story 6.2 assertion keyword.
    ...                Story 6.4 code-review HIGH-β fix 2026-05-20 (Edge HIGH-2 + Auditor HIGH-2): pre-edit
    ...                assertions suite missed schema-mode despite AC-6.4.3 verbatim "3 `Agent Response Should *`".
    ...                Story 6.2 HIGH-β `_resolve_schema` tightening fix is exercised here.
    ${run}=    Build Json Response Run
    AgentEval.Agent Response Should Match Schema    ${run}    schema=${{{"type": "object", "required": ["name"]}}}
