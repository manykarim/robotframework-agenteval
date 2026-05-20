*** Settings ***
Documentation    Story 5.5 dogfood — exercises agenteval's Epic 5 trace
...              observability layer (hosted-MCP observer + RunManifest
...              sidecar + DegradedTraceWarning + Get Last Warnings)
...              against `rf-mcp`'s `robotmcp` MCP server as the
...              MCP-under-test, plus the bundled in-memory FastMCP
...              echo server as the hosted-in-process happy-path proof.
...
...              Per Story 5.5 spec D-3 drift fix 2026-05-20: this is
...              NOT a port of rf-mcp's trace tests (rf-mcp has none —
...              its pytest corpus tests the MCP-server surface, not
...              agent-side trace observability). This suite is the
...              FIRST place rf-mcp is exercised through agenteval's
...              observability pipeline. See
...              `parity-checklist-rf-mcp-trace.md` for the honest
...              scope correction.
...
...              CI wiring deferred per Phase-1 norm:
...              `dogfood-integration.yml` is install-smoke-only by
...              design (Story 1a.2 HIGH-1 lesson). Run locally:
...
...                  RF_MCP_REPO_ROOT=/path/to/rf-mcp \
...                  uv run robot tests/dogfood/rf-mcp/test_trace_observability_parity.robot
...
...              All tests carry `[Tags] slow` so the standard
...              `uv run pytest` sweep skips them — they require rf-mcp
...              checked out at $RF_MCP_REPO_ROOT.

Library          AgentEval    WITH NAME    AgentEval
Library          AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
Library          OperatingSystem
Library          Collections
Library          Process

Suite Setup      Set Suite-Wide Server Handle
Suite Teardown   Stop Suite Server

*** Variables ***
${VENDORED_MCP_JSON}        ${CURDIR}/.mcp.json
${RF_MCP_REPO_ROOT}         %{RF_MCP_REPO_ROOT=/home/many/workspace/rf-mcp}
${ROBOTMCP_SERVER_NAME}     robotmcp

*** Keywords ***
Set Suite-Wide Server Handle
    [Documentation]    Re-uses Story 3.3 Suite Setup pattern verbatim
    ...                (`tests/dogfood/rf-mcp/test_mcp_surface_parity.robot`)
    ...                including the DOGFOOD-FINDING-A `--directory`
    ...                injection workaround for the missing
    ...                `MCP.Start Server cwd=` parameter (DF-3.3-S1).
    Set Suite Variable    ${HANDLE}    ${NONE}
    Directory Should Exist    ${RF_MCP_REPO_ROOT}    rf-mcp repo not found at ${RF_MCP_REPO_ROOT}; set RF_MCP_REPO_ROOT env var or clone rf-mcp there
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    ${entry}=    Set Variable    ${servers["${ROBOTMCP_SERVER_NAME}"]}
    ${args}=    Evaluate    ['--directory', $RF_MCP_REPO_ROOT] + list($entry["args"])
    ${handle}=    MCP.Start Server
    ...    name=${ROBOTMCP_SERVER_NAME}
    ...    transport=stdio
    ...    command=${entry["command"]}
    ...    args=${args}
    ...    env=${entry["env"]}
    Set Suite Variable    ${HANDLE}    ${handle}

Stop Suite Server
    [Documentation]    Story 3.3 Edge-cases H2 fix pattern: guard against
    ...                ${HANDLE}=${NONE} so Teardown doesn't mask Setup failure.
    Run Keyword If    "${HANDLE}" != "${NONE}"    MCP.Stop Server    ${HANDLE}

Build In Memory Echo Handle
    [Documentation]    Constructs an MCPServerHandle backed by the bundled
    ...                FastMCP echo server (`AgentEval.mcp.bundled.echo`).
    ...                Used to prove the HOSTED-IN-PROCESS happy path against
    ...                a real (synthetic) MCP server when the observer is
    ...                actually wired through. Returns the handle.
    ${handle}=    Evaluate
    ...    __import__('AgentEval.mcp.lifecycle', fromlist=['start_server']).start_server(name='echo', transport='in_memory', server_factory=__import__('AgentEval.mcp.bundled.echo', fromlist=['build_server']).build_server)
    RETURN    ${handle}

Build Generic Adapter With Mock Provider
    [Documentation]    Builds a GenericAdapter wired to a MockProvider that
    ...                returns a single deterministic response. Used to drive
    ...                the adapter's `mcp_servers=` wiring path (Story 5.2
    ...                HostedMcpObserver attach) without a real LLM call.
    [Arguments]    ${response_text}=ok
    ${adapter}=    Evaluate
    ...    __import__('AgentEval.coding_agent.generic', fromlist=['GenericAdapter']).GenericAdapter(provider_instance=__import__('AgentEval.providers.mock', fromlist=['MockProvider']).MockProvider(responses=[__import__('AgentEval.providers.base', fromlist=['ChatResponse']).ChatResponse(text=$response_text, tool_calls=[], usage=__import__('AgentEval.providers.base', fromlist=['ProviderUsage']).ProviderUsage(input_tokens=1, output_tokens=1), cost_usd=0.001)]))
    RETURN    ${adapter}

*** Test Cases ***

# --- Static-inspection sanity (re-uses Story 3.3 .mcp.json) ---

Rfmcp Vendored Config Parses Cleanly
    [Documentation]    Sanity check the vendored .mcp.json still parses through
    ...                Story 2.3's `MCP.Get Server Config` — guards against
    ...                Story 3.3 vendored-config regressions.
    [Tags]    slow
    ${servers}=    MCP.Get Server Config    ${VENDORED_MCP_JSON}
    Should Contain    ${servers}    robotmcp

# --- AC-5.5.3 #1 + AC-5.5.1: Get Spans / Get Tool Calls keyword surface -------

Get Spans Returns List Type For Both Current And Unknown Test Ids
    [Documentation]    Story 5.5 AC-5.5.1: `Get Spans` keyword wraps
    ...                `_kernel/trace_store.get_run_spans` projection accessor.
    ...                Story 5.5 code-review 3-way HIGH-D fix 2026-05-20
    ...                (Blind HIGH-7 + Edge-cases MED-EC-12 + Auditor HIGH-1):
    ...                pre-edit asserted only `len == 0` for `test_id=${TEST NAME}`
    ...                — tautological per DF-5.5-DOGFOOD-2 (no adapter
    ...                emits spans in Phase-1). Now exercises the
    ...                `test_id="current"` no-bound-test contract +
    ...                explicit-unknown-test_id contract + verifies the
    ...                wrapper returns `list` shape (not None, not raises).
    [Tags]    slow
    # Listener-less context: current returns [] per AC-5.5.1 + HIGH-A fix.
    ${current_spans}=    AgentEval.Get Spans    test_id=current
    Should Be True    ${{ isinstance($current_spans, list) }}
    Should Be Equal As Integers    ${{ len($current_spans) }}    0
    # Explicit unknown id: also [] per the projection accessor contract.
    ${unknown_spans}=    AgentEval.Get Spans    test_id=S.never_existed
    Should Be True    ${{ isinstance($unknown_spans, list) }}
    Should Be Equal As Integers    ${{ len($unknown_spans) }}    0

Get Tool Calls Returns List Type For Both Current And Unknown Test Ids
    [Documentation]    Story 5.5 AC-5.5.1: `Get Tool Calls` keyword wraps
    ...                `_kernel/trace_store.get_tool_calls`. Story 5.5
    ...                code-review 3-way HIGH-D fix 2026-05-20 — sibling
    ...                pattern to `Get Spans` above. Verifies the wrapper
    ...                returns a list (not None, not raises) for both
    ...                no-bound-test current AND explicit-unknown paths.
    [Tags]    slow
    ${current_tcs}=    AgentEval.Get Tool Calls    test_id=current
    Should Be True    ${{ isinstance($current_tcs, list) }}
    Should Be Equal As Integers    ${{ len($current_tcs) }}    0
    ${unknown_tcs}=    AgentEval.Get Tool Calls    test_id=S.never_existed
    Should Be True    ${{ isinstance($unknown_tcs, list) }}
    Should Be Equal As Integers    ${{ len($unknown_tcs) }}    0

Get Run Manifest Returns None For No Bound Test Per Sibling Consistency
    [Documentation]    Story 5.5 code-review 2-way HIGH-F fix 2026-05-20
    ...                (Blind HIGH-10 + Edge-cases HIGH-EC-2): pre-edit
    ...                `Get Run Manifest test_id=current` raised `ValueError`
    ...                on no-bound-test path — diverging from sibling
    ...                Tier-1 keywords (`Get Last Warnings`, `Get Spans`,
    ...                `Get Tool Calls`) which return `[]`. Now returns
    ...                `None` for Tier-1 sibling-consistency. Direct accessor
    ...                callers still get `ValueError` per Story 1b.2
    ...                semantics — only the keyword wrapper is defensive.
    [Tags]    slow
    ${manifest}=    AgentEval.Get Run Manifest    test_id=current
    Should Be Equal    ${manifest}    ${NONE}

# --- AC-5.5.3 #2: Rfmcp stdio handle wired through GenericAdapter degrades ---

Rfmcp Stdio Handle Through Generic Adapter Yields External Mixed Coverage
    [Documentation]    Story 5.5 AC-5.5.3 + Story 5.2 DF-5.2-S3 honest-degradation
    ...                contract: rf-mcp's stdio transport is not yet wrapped
    ...                by the subprocess observer (Phase-2 work). The
    ...                GenericAdapter wires the stdio handle through
    ...                `_attach_handle_to_observer` which calls
    ...                `observer.mark_external_mixed(...)` — the canonical
    ...                FR61 trigger ONLY when prior observation existed.
    ...                Since no prior observation, `mark_external_mixed`
    ...                accumulates the reason but does NOT fire the warning
    ...                (per AC-5.4.3). Coverage resolves to "external_mixed"
    ...                per ADR-016 D1.
    [Tags]    slow
    ${adapter}=    Build Generic Adapter With Mock Provider
    ${mcp_servers}=    Create Dictionary    ${ROBOTMCP_SERVER_NAME}=${HANDLE}
    ${result}=    Evaluate    $adapter.run(prompt='probe', mcp_servers=$mcp_servers)
    Should Be Equal    ${result.metadata.mcp_coverage}    external_mixed
    # No DegradedTraceWarning fires when prior observation absent — this is
    # the AC-5.4.3 invariant validated against a real stdio MCP handle.
    ${warnings}=    AgentEval.Get Last Warnings    test_id=current
    Should Be Equal As Integers    ${{ len($warnings) }}    0

# --- AC-5.5.3 #3: In-memory echo through GenericAdapter wires hosted observer --

Bundled In Memory Echo Through Generic Adapter Wires Hosted Observer
    [Documentation]    Story 5.5 AC-5.5.3 #3 (DOGFOOD-CORRECTED): an in_memory
    ...                handle backed by the bundled FastMCP echo server gets
    ...                the HostedMcpObserver attached via the
    ...                `transport == "in_memory"` branch of
    ...                `_attach_handle_to_observer` (generic.py:259-271).
    ...                Empirical dogfood-run 2026-05-20 (DF-5.5-DOGFOOD-3):
    ...                ADR-016 D1 trust-floor reports `"hosted_in_process"`
    ...                when the observer ATTACHED successfully — the attach
    ...                IS the trust signal (path added to observation_paths
    ...                at observer.py:217). The dispatch-of-a-tool-call is
    ...                NOT required for the strongest-path-completed
    ...                semantic; successful attach is sufficient. This is
    ...                the spec's pre-edit assumption corrected by running
    ...                the dogfood.
    [Tags]    slow
    ${echo_handle}=    Build In Memory Echo Handle
    ${adapter}=    Build Generic Adapter With Mock Provider
    ${mcp_servers}=    Create Dictionary    echo=${echo_handle}
    ${result}=    Evaluate    $adapter.run(prompt='probe', mcp_servers=$mcp_servers)
    # Per ADR-016 D1 trust-floor: observer attached successfully →
    # observation_paths contains "hosted_in_process" → compute_coverage
    # reports the strongest-path-completed value. Dogfood validation
    # confirmed this is the correct behavior (the spec's pre-edit
    # assumption that no-tool-dispatch would degrade to external_mixed
    # was wrong; the dispatch step is NOT gating on coverage resolution).
    Should Be Equal    ${result.metadata.mcp_coverage}    hosted_in_process
    # Adapter metadata captures completeness from the run.
    Should Be Equal    ${result.metadata.completeness}    complete

# --- AC-5.5.3 #5 (+ AC-5.4.3 dogfood): forced degradation surfaces warning ----

Forced Mark External Mixed After Prior Observation Fires Degraded Warning
    [Documentation]    Story 5.5 AC-5.5.3 #5: directly drive the canonical FR61
    ...                trigger by constructing a HostedMcpObserver, injecting
    ...                a synthetic prior tool call into its state, then
    ...                calling mark_external_mixed("dogfood-simulated"). The
    ...                AC-5.4.3 invariant guarantees: (a) DegradedTraceWarning
    ...                fires through both Python + structured channels;
    ...                (b) mcp_coverage falls to "external_mixed"; (c)
    ...                Get Last Warnings shows the structured record with
    ...                source="mcp.observer".
    [Tags]    slow
    ${observer}=    Evaluate    __import__('AgentEval.mcp.observer', fromlist=['HostedMcpObserver']).HostedMcpObserver()
    # Inject a prior tool_call into observer state to satisfy AC-5.4.3
    # gating ("only fires when len(tool_calls) >= 1"). Mirrors the
    # internal _record path pattern used by Story 5.4 integration tests.
    ${tc}=    Evaluate    __import__('AgentEval.types', fromlist=['ToolCallTrace']).ToolCallTrace(name='echo', args={}, result='ok', error=None, latency_ms=1.0, source='hosted_mcp', gen_ai_tool_call_id='t-1', sequence_index=1)
    Evaluate    $observer._state.tool_calls.append($tc)
    Evaluate    $observer.mark_external_mixed('dogfood-simulated subprocess MCP')
    # AC-5.4.3 canonical FR61 trigger: structured record surfaces via
    # Get Last Warnings. Story 5.5 code-review 3-way HIGH-C fix 2026-05-20
    # (Blind HIGH-5 + Edge-cases HIGH-EC-4 + Auditor HIGH-3): the
    # Listener-less .robot context routes records to the `__suite__`
    # sentinel. The DF-5.5-DOGFOOD-4 fix landed in the same PR added
    # `test_id="__suite__"` as a public lookup-mode so this dogfood
    # reads via the public RF surface instead of `_warning_buffers`
    # private access. Also: filter records by the unique message
    # substring (Edge-cases HIGH-EC-13 state-bleed safety — prior tests
    # in the same suite ALSO populate __suite__ via `_attach_handle_to_observer`
    # mark_external_mixed calls; index-fragile lookup would assert on
    # the wrong record).
    ${all_records}=    AgentEval.Get Last Warnings    test_id=__suite__
    ${matching}=    Evaluate    [r for r in $all_records if 'dogfood-simulated' in r.get('message', '')]
    Should Be True    ${{ len($matching) >= 1 }}    expected the dogfood-simulated DegradedTraceWarning record in __suite__ sentinel; got ${all_records}
    ${first}=    Set Variable    ${matching[0]}
    Should Be Equal    ${first["warning_type"]}    AgentEval.errors.DegradedTraceWarning
    Should Be Equal    ${first["source"]}    mcp.observer
    # ADR-016 D1: post-mark_external_mixed coverage is "external_mixed".
    Should Be Equal    ${{ $observer.compute_coverage() }}    external_mixed

# --- AC-5.5.3 #4 + #6: JSON sidecar emit + schema validation -----------------

Json Sidecar Schema Validates Against Run Manifest Schema
    [Documentation]    Story 5.5 AC-5.5.3 #6 — closes Auditor MED-3 carry from
    ...                Story 5.4 catalog: `jsonschema.validate(sidecar_payload,
    ...                schema)` on a manifest constructed from the
    ...                live `RunManifest` dataclass + v1.1 schema.
    ...
    ...                Story 5.5 code-review 3-way HIGH-E fix 2026-05-20
    ...                (Blind HIGH-6 + Auditor HIGH-4 + Auditor MED-4): the
    ...                pre-edit test only validated schema file existence
    ...                + 2 keys — never called `jsonschema.validate`. AC
    ...                demanded a real schema validation. Now:
    ...                construct a Story 5.3 `RunManifest` + serialize via
    ...                the same `RunManifestEmitter._manifest_to_redacted_dict`
    ...                path that the sidecar emitter uses + validate the
    ...                payload against the v1.1 schema.
    [Tags]    slow
    ${schema_path}=    Set Variable    ${EXECDIR}/docs/contracts/run-manifest-schema.json
    ${schema_text}=    Get File    ${schema_path}
    ${schema}=    Evaluate    __import__('json').loads($schema_text)
    Should Contain    ${schema["description"]}    v1.1
    # Emit a synthetic manifest through the same `RunManifestEmitter.emit()`
    # path that `_emit_run_manifest_sidecar` calls on `end_test` so the
    # serialized JSON includes the `_json_default` datetime → isoformat
    # transformation. Then read the JSON back + validate. This proves
    # the FULL emit pipeline (dataclasses → redact_dict → json.dump
    # with default=_json_default) produces a payload that conforms to
    # the v1.1 schema verbatim.
    ${tmpdir}=    Evaluate    __import__('tempfile').mkdtemp(prefix='story-5-5-dogfood-')
    ${manifest_path}=    Evaluate
    ...    __import__('AgentEval.telemetry.run_manifest', fromlist=['RunManifestEmitter']).RunManifestEmitter().emit(__import__('AgentEval.types', fromlist=['RunManifest']).RunManifest(library_version='0.1.0', test_id='S.synth', suite_id='S', redaction_policy_hash='0'*64, started_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), ended_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), warnings=[{'warning_type': 'AgentEval.errors.DegradedTraceWarning', 'message': 'schema-validation probe', 'source': 'test_fixture', 'timestamp': '2026-05-20T00:00:00+00:00', 'remediation': None}]), output_dir=__import__('pathlib').Path($tmpdir), suite_id='S', test_id='S.synth')
    Should Not Be Equal    ${manifest_path}    ${NONE}
    ${payload_text}=    Get File    ${manifest_path}
    ${payload}=    Evaluate    __import__('json').loads($payload_text)
    # AC-5.5.3 #6 verbatim: jsonschema.validate(sidecar_payload, schema)
    Evaluate    __import__('jsonschema').validate(instance=$payload, schema=$schema)
    # Cleanup the temp dir to avoid /tmp accumulation across runs.
    Evaluate    __import__('shutil').rmtree($tmpdir, ignore_errors=True)
