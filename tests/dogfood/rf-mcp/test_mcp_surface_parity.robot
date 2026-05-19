*** Settings ***
Documentation    Story 3.3 dogfood parity suite — ports a REPRESENTATIVE
...              subset of rf-mcp's custom Python MCP-surface tests
...              (`test_mcp_simple.py` + `test_mcp_comprehensive.py` +
...              `test_mcp_error_scenarios.py`) to `.robot` using
...              `robotframework-agenteval` Epic 2 (static inspection)
...              + Epic 3 (lifecycle + tool inspection) keywords.
...
...              Source SHA: rf-mcp 235d679785fd4e5f647e9e760ec7da2a3d09b7ef.
...              Parity scope: see `parity-checklist-rf-mcp-mcp-surface.md`.
...              Full 1:1 parity for the 1128-LoC pytest corpus is Story 9.1.
...
...              Execution: `uv run robot tests/dogfood/rf-mcp/test_mcp_surface_parity.robot`.
...              Requires rf-mcp environment at /home/many/workspace/rf-mcp/
...              with `uv sync` already run (robotmcp server must be
...              uv-runnable). The suite reads the vendored .mcp.json +
...              cd's into the rf-mcp directory at lifecycle setup so
...              `uv run -m robotmcp.server` resolves correctly.

Library          AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
Library          OperatingSystem
Library          Collections

Suite Setup      Set Suite-Wide Server Handle
Suite Teardown   Stop Suite Server

*** Variables ***
${VENDORED_MCP_JSON}        ${CURDIR}/.mcp.json
# Story 3.3 code-review 4-way HIGH-A fix 2026-05-19 (Blind HIGH-1 + Edge-cases M2
# + Codex Probe 5): default to Many's workstation but allow override via env var
# so other operators (and Story 9.1 CI) can run the suite without forking. RF's
# `%{VAR=default}` syntax does environment lookup with fallback.
${RF_MCP_REPO_ROOT}         %{RF_MCP_REPO_ROOT=/home/many/workspace/rf-mcp}
${ROBOTMCP_SERVER_NAME}     robotmcp

*** Keywords ***
Set Suite-Wide Server Handle
    [Documentation]    Suite-scoped MCP handle. Per Story 3.3 code-review MED-A
    ...                fix 2026-05-19 (Blind MED-2 + Edge-cases M5):
    ...                `MCP.Start Server` is pure handle construction at this
    ...                layer; each `MCP.Call Tool` / `MCP.List Tools` invocation
    ...                STILL opens its own subprocess via the Phase-1 per-call-
    ...                session pattern (Story 3.1 design at `lifecycle.py:_open_session`).
    ...                The Suite Setup pattern here MIMICS suite-scoped reuse at
    ...                the .robot level (one handle stored as ${HANDLE}; shared
    ...                across all 15 tests), but the architectural `mcp_per_test`
    ...                kwarg on `AgentEval.AgentEval(...)` + `_resolve_scope` is
    ...                NOT exercised — that wiring lives at the top-level Library
    ...                init + the `MCPLifecycleManager` (Phase-1.5+).
    ...
    ...                Initialize ${HANDLE} to ${NONE} FIRST (Story 3.3
    ...                code-review Edge-cases H2 fix) so Suite Teardown can
    ...                guard cleanly even when subsequent setup steps fail.
    Set Suite Variable    ${HANDLE}    ${NONE}
    Directory Should Exist    ${RF_MCP_REPO_ROOT}    rf-mcp repo not found at ${RF_MCP_REPO_ROOT}; set RF_MCP_REPO_ROOT env var or clone rf-mcp there
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    ${entry}=    Set Variable    ${servers["${ROBOTMCP_SERVER_NAME}"]}
    # Story 3.3 dogfood DOGFOOD-FINDING-A workaround: agenteval's `MCP.Start Server`
    # lacks a `cwd=` parameter. `uv run -m robotmcp.server` only resolves when
    # invoked from rf-mcp's project root → inject `--directory ${RF_MCP_REPO_ROOT}`
    # as the first uv flag. Real fix tracked DF-3.3-S1.
    ${args}=    Evaluate    ['--directory', $RF_MCP_REPO_ROOT] + list($entry["args"])
    ${handle}=    MCP.Start Server
    ...    name=${ROBOTMCP_SERVER_NAME}
    ...    transport=stdio
    ...    command=${entry["command"]}
    ...    args=${args}
    ...    env=${entry["env"]}
    Set Suite Variable    ${HANDLE}    ${handle}

Stop Suite Server
    [Documentation]    Story 3.3 code-review Edge-cases H2 fix 2026-05-19:
    ...                guard against ${HANDLE}=${NONE} (Suite Setup failed
    ...                pre-handle-construction) so Teardown doesn't mask the
    ...                real setup failure with a confusing "Variable not found".
    Run Keyword If    "${HANDLE}" != "${NONE}"    MCP.Stop Server    ${HANDLE}

Call Robotmcp Tool
    [Documentation]    Wrapper for `MCP.Call Tool` against the suite-handle.
    [Arguments]    ${tool_name}    ${arguments}
    ${result}=    MCP.Call Tool    ${HANDLE}    ${tool_name}    ${arguments}
    RETURN    ${result}

*** Test Cases ***

# --- Static-inspection parity (AC-3.3.2) — Epic 2 Story 2.3 keywords ----------

Rfmcp Config Parses And Declares Robotmcp Server
    [Documentation]    Mirrors the implicit "the config is valid" assumption
    ...                rf-mcp's pytest fixtures hold (they import `Client(mcp)`
    ...                in-process — there's no separate config parse). This is
    ...                an AGENTEVAL-NATIVE assertion the pytest suite doesn't
    ...                expose because pytest tests the in-process surface, not
    ...                the .mcp.json declaration.
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    Should Contain    ${servers}    robotmcp
    Should Be Equal    ${servers["robotmcp"]["command"]}    uv
    Should Contain    ${servers["robotmcp"]["args"]}    run
    Should Contain    ${servers["robotmcp"]["args"]}    -m
    Should Contain    ${servers["robotmcp"]["args"]}    robotmcp.server

Rfmcp Config Preserves Env Block Subset
    [Documentation]    Verifies the env passthrough across `Get Server Config`.
    ...                rf-mcp's robotmcp depends on ROBOTMCP_* vars
    ...                (functionally required per rf-mcp's server.py defaults).
    ...                Story 3.3 code-review HIGH-A fix 2026-05-19 (4-way:
    ...                Blind HIGH-1 + Edge-cases M3 + Codex HIGH-2 + Codex
    ...                Probe 5): the pre-edit assertion pinned `PYTHONPATH`
    ...                which is Many-workstation-specific (points at
    ...                /home/many/workspace/robotframework-PlatynUI/...).
    ...                Removed PYTHONPATH pin so the test stays portable.
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    ${env}=    Set Variable    ${servers["robotmcp"]["env"]}
    Should Contain    ${env}    ROBOTMCP_INSTRUCTIONS
    Should Contain    ${env}    ROBOTMCP_ATTACH_HOST
    Should Contain    ${env}    ROBOTMCP_TOKENIZER

Rfmcp Config Declares Multiple Servers
    [Documentation]    rf-mcp's real .mcp.json declares 2 servers (robotmcp +
    ...                claude-flow). Verifies multi-server configs parse cleanly.
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    Length Should Be    ${servers}    2
    Should Contain    ${servers}    robotmcp
    Should Contain    ${servers}    claude-flow

# --- Lifecycle parity (AC-3.3.3) — Epic 3 Story 3.1 keywords -------------------

Robotmcp Server Handle Constructs Without Spawning
    [Documentation]    Phase-1 per-call-session pattern means `Start Server`
    ...                is pure handle construction; no subprocess spawn until
    ...                the first tool call. Suite Setup already constructed.
    Should Not Be Equal    ${HANDLE}    ${NONE}
    Should Be Equal    ${HANDLE.name}    robotmcp
    Should Be Equal    ${HANDLE.transport}    stdio

Robotmcp Server Connects And Negotiates Protocol Version
    [Documentation]    Mirrors rf-mcp's implicit "the client connects" assumption.
    ...                The pytest fixture uses in-process FastMCP; here we drive
    ...                the SAME rf-mcp server via stdio subprocess + verify the
    ...                MCP spec handshake succeeds against agenteval's version
    ...                gate (NFR-COMPAT-04 mcp>=1.0,<2.0).
    [Tags]    slow
    ${session}=    MCP.Connect To Server    ${HANDLE}
    Should Be Equal    ${session.name}    robotmcp
    Should Be Equal    ${session.transport}    stdio
    Should Not Be Empty    ${session.protocol_version}

# --- Tool inventory parity (AC-3.3.4) — Epic 3 Story 3.2 keywords -------------

Robotmcp List Tools Includes Execute Step
    [Documentation]    Mirrors rf-mcp `test_simple_log_execution` implicit
    ...                "execute_step tool exists" assumption.
    [Tags]    slow
    ${tools}=    MCP.List Tools    ${HANDLE}
    ${names}=    Evaluate    [t.name for t in $tools]
    Should Contain    ${names}    execute_step

Robotmcp List Tools Includes Analyze Scenario
    [Documentation]    Mirrors rf-mcp `test_analyze_scenario_structure`.
    [Tags]    slow
    ${tools}=    MCP.List Tools    ${HANDLE}
    ${names}=    Evaluate    [t.name for t in $tools]
    Should Contain    ${names}    analyze_scenario

Robotmcp List Tools Includes Find Keywords
    [Documentation]    Mirrors rf-mcp `test_find_keywords_structure`.
    [Tags]    slow
    ${tools}=    MCP.List Tools    ${HANDLE}
    ${names}=    Evaluate    [t.name for t in $tools]
    Should Contain    ${names}    find_keywords

Robotmcp Execute Step Tool Has Input Schema With Keyword Field
    [Documentation]    Validates the tool's input_schema declares the required
    ...                `keyword` field. Story 3.3 code-review MED-B fix 2026-05-19
    ...                (2-way Blind LOW-1 + Edge-cases M1): the pre-edit body
    ...                only asserted `input_schema.type == "object"` which passes
    ...                for any tool with any object schema. Now also asserts the
    ...                `keyword` property is declared per the test name's claim.
    [Tags]    slow
    ${tools}=    MCP.List Tools    ${HANDLE}
    ${execute_step}=    Evaluate    next(t for t in $tools if t.name == "execute_step")
    Should Be Equal    ${execute_step.input_schema.get("type")}    object
    ${properties}=    Set Variable    ${execute_step.input_schema.get("properties", {})}
    Should Contain    ${properties}    keyword

# --- Tool-call parity (AC-3.3.5) — Epic 3 Story 3.2 keywords -------------------

Robotmcp Execute Step Calls Log Keyword Successfully
    [Documentation]    Direct port of rf-mcp `test_simple_log_execution`
    ...                (test_mcp_simple.py L23-43): call execute_step with a
    ...                Log keyword + assert is_error=False + content shape.
    [Tags]    slow
    ${args}=    Create Dictionary    keyword=Log    arguments=${{['Hello World']}}    session_id=parity_test
    ${result}=    Call Robotmcp Tool    execute_step    ${args}
    Should Not Be True    ${result.is_error}
    Should Be True    ${result.latency_ms} > 0
    Should Be True    len($result.content) > 0

Robotmcp Analyze Scenario Returns Success
    [Documentation]    Direct port of rf-mcp `test_analyze_scenario_structure`
    ...                (test_mcp_simple.py L46-58).
    [Tags]    slow
    ${args}=    Create Dictionary    scenario=Test login functionality    context=web
    ${result}=    Call Robotmcp Tool    analyze_scenario    ${args}
    Should Not Be True    ${result.is_error}

Robotmcp Find Keywords Returns Results
    [Documentation]    Direct port of rf-mcp `test_find_keywords_structure`
    ...                + `test_find_keywords_strategies` (test_mcp_comprehensive.py L68-79).
    [Tags]    slow
    ${args}=    Create Dictionary    query=Log    strategy=pattern    limit=${3}
    ${result}=    Call Robotmcp Tool    find_keywords    ${args}
    Should Not Be True    ${result.is_error}

# --- Error-path parity (AC-3.3.5 + AC-3.2.5) — first-class is_error data -----

Robotmcp Execute Step With Invalid Keyword Yields Is Error
    [Documentation]    Mirrors rf-mcp `test_execute_step_invalid_keyword`
    ...                (test_mcp_error_scenarios.py): invalid keyword name must
    ...                surface as `MCPToolResult(is_error=True, ...)` per FR9b
    ...                first-class-data semantics. NOT an exception.
    ...
    ...                Story 3.3 code-review 2-way HIGH-B fix 2026-05-19 (Blind
    ...                HIGH-2 + Edge-cases H3): the pre-edit body only asserted
    ...                `latency_ms > 0` (the comment's disjunction was prose,
    ...                not an assertion) — fake-green: ANY successful round-trip
    ...                passed. rf-mcp's error surface varies by code path:
    ...                either `is_error=True` (MCP spec form) OR `is_error=False`
    ...                with `content[].data["success"]=False` (rf-mcp pattern).
    ...                Either is acceptable; assert at least ONE of the two is
    ...                present so a future rf-mcp silent-swallow regression
    ...                fails the test.
    [Tags]    slow
    ${args}=    Create Dictionary
    ...    keyword=ThisKeywordDoesNotExist
    ...    arguments=${{[]}}
    ...    session_id=parity_test_err
    ${result}=    Call Robotmcp Tool    execute_step    ${args}
    Should Be True    ${result.latency_ms} > 0
    ${success_in_content}=    Evaluate    any((b.get('data') or {}).get('success') is False for b in $result.content if isinstance(b, dict))
    ${error_surfaced}=    Evaluate    bool($result.is_error) or bool($success_in_content)
    Should Be True    ${error_surfaced}    rf-mcp returned neither is_error=True nor content[].data["success"]=False; the invalid-keyword error contract has regressed

Robotmcp Call Unknown Tool Yields Is Error
    [Documentation]    Mirrors agenteval's own AC-3.2.5 + the underlying MCP
    ...                spec contract: unknown tool name surfaces as a server
    ...                error response, NOT as a transport failure.
    [Tags]    slow
    ${empty_args}=    Create Dictionary
    ${result}=    Call Robotmcp Tool    this_tool_does_not_exist    ${empty_args}
    Should Be True    ${result.is_error}
    Should Not Be Equal    ${result.error_message}    ${NONE}

# --- Latency + correlation_id sanity (FR9b ratification) ---------------------

Robotmcp Call Tool Reports Per-Call Correlation Id
    [Documentation]    Verifies the correlation_id Phase-1 placeholder is
    ...                a non-empty uuid4-shaped hex string per call.
    [Tags]    slow
    ${args}=    Create Dictionary    keyword=Log    arguments=${{['cid-test']}}    session_id=parity_cid
    ${result}=    Call Robotmcp Tool    execute_step    ${args}
    Length Should Be    ${result.correlation_id}    32
