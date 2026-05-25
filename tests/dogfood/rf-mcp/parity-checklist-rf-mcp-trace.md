# `rf-mcp` Trace Observability Dogfood — Parity Checklist

**VALIDATION-CEILING (added 2026-05-25 per Epic 7 retro `feedback_dogfood_validation_ceiling` norm):** this dogfood VERIFIES that the Epic 5 trace-observability surface (OTel spans, `mcp_coverage` 3-state enum per ADR-016, `DegradedTraceWarning` Story 5.4, RunManifest sidecar) wires through a real production stdio MCP server (rf-mcp's robotmcp); does NOT VERIFY full agent-driven multi-turn loop integration (Phase-1 ships observer + coverage pipeline only; agent loop is DF-5.5-DOGFOOD-1 / C43 Phase-2), nor adapter span instrumentation (DF-5.5-DOGFOOD-2 / C44 Phase-1.5), nor cross-version observer compatibility (single MCP SDK pin). Parallel-derived rather than 1:1 ported — `rf-mcp` had NO upstream trace-observability tests because the observability surface didn't exist there pre-agenteval.

**Story:** 5.5 — Interleaved Dogfood: Trace Observability Against `rf-mcp`
**Date:** 2026-05-20
**Companion:** [`parity-checklist-rf-mcp-mcp-surface.md`](./parity-checklist-rf-mcp-mcp-surface.md) (Story 3.3 MCP-surface dogfood).

## Honest scope correction (D-3 drift fix per `feedback_spec_vs_ratified_doc_precheck` 26th use)

The original Story 5.5 epic draft framed this work as **"port `rf-mcp`'s existing trace-observability tests to `.robot`"**. Empirical verification disproved that premise:

```
$ grep -l "trace\|span\|tool_call\|warning\|observabl" \
    /home/many/workspace/rf-mcp/tests/test_mcp_simple.py \
    /home/many/workspace/rf-mcp/tests/test_mcp_comprehensive.py \
    /home/many/workspace/rf-mcp/tests/test_mcp_error_scenarios.py
# (no output — no matches)
```

`rf-mcp`'s pytest corpus tests the **MCP-server surface** (call_tool, list_tools, error scenarios). It does NOT test agent-side trace observability against rf-mcp. There were no tests to port.

**The honest framing this dogfood suite implements:** Story 5.5 is the FIRST place rf-mcp's `robotmcp` server is exercised through agenteval's Epic 5 observability layer (hosted-MCP observer, RunManifest sidecar, `DegradedTraceWarning` collector, `Get Last Warnings` keyword surface). The dogfood validates agenteval's pipeline AGAINST rf-mcp as the MCP-under-test — NOT the other way around.

This is a more accurate statement of what was actually load-bearing in the epic-level intent: agenteval's trace pipeline needs to survive contact with a real third-party MCP server.

## What `rf-mcp`'s pytest corpus actually covers

| Source file | Tests | Coverage scope |
| --- | --- | --- |
| `tests/test_mcp_simple.py` | 3 | MCP-surface: `execute_step` happy path, `analyze_scenario`, `find_keywords` happy paths. NOT trace-observability. |
| `tests/test_mcp_comprehensive.py` | ~10 | MCP-surface comprehensive: find_keywords strategies, schema introspection, response shape. NOT trace-observability. |
| `tests/test_mcp_error_scenarios.py` | ~5 | MCP-error-paths: invalid keyword, unknown tool, malformed args. NOT trace-observability. |

Story 3.3 ported a representative subset of the above to [`test_mcp_surface_parity.robot`](./test_mcp_surface_parity.robot) (1128-LoC pytest corpus → 15 `.robot` tests; full 1:1 parity reserved for Story 9.1).

## What this `.robot` suite NEWLY covers

`tests/dogfood/rf-mcp/test_trace_observability_parity.robot` validates the agenteval-side observability surface against rf-mcp as the MCP under test:

| `.robot` test | Validates | agenteval source-of-truth |
| --- | --- | --- |
| `Rfmcp Vendored Config Parses Cleanly` | Story 3.3 vendored `.mcp.json` remains valid input to Story 2.3's `MCP.Get Server Config` | Story 3.3 + AC-2.3.x |
| `Get Spans Returns Empty List For Test With No Spans` | Story 5.5 `Get Spans` keyword wraps `_kernel/trace_store.get_run_spans` correctly + empty-list-on-no-spans contract holds | Story 5.5 AC-5.5.1 |
| `Get Tool Calls Returns Empty List For Test With No Tool Calls` | Story 5.5 `Get Tool Calls` keyword wraps `_kernel/trace_store.get_tool_calls` correctly | Story 5.5 AC-5.5.1 |
| `Rfmcp Stdio Handle Through Generic Adapter Yields External Mixed Coverage` | Story 5.2 DF-5.2-S3 honest-degradation contract: stdio MCP → `mark_external_mixed` → `mcp_coverage="external_mixed"`; AC-5.4.3 gating (no warning when no prior observation) | Story 5.2 AC-5.2.6 + Story 5.4 AC-5.4.3 + ADR-016 D1 |
| `Bundled In Memory Echo Through Generic Adapter Wires Hosted Observer` | ADR-016 D1 trust-floor: successful `observer.attach()` adds `"hosted_in_process"` to `observation_paths` → `compute_coverage()` reports `hosted_in_process` (DOGFOOD-FINDING DF-5.5-DOGFOOD-3 corrected the spec's pre-edit pessimistic assumption that no-tool-dispatch would degrade to external_mixed; successful attach IS the trust signal per observer.py:217 + ADR-016 D1) | ADR-016 D1 + Story 5.2 AC-5.2.6 + DF-5.5-DOGFOOD-3 |
| `Forced Mark External Mixed After Prior Observation Fires Degraded Warning` | Story 5.4 AC-5.4.3 canonical FR61 trigger: prior observation + `mark_external_mixed` → both Python warning channel + structured `WarningRecord` fire + `Get Last Warnings` surfaces the record + ADR-016 D1 coverage transition | Story 5.4 AC-5.4.3 + AC-5.4.5 |
| `Run Manifest Schema Available At Documented Path` | Story 5.3 v1.0 + Story 5.4 v1.1 JSON Schema published at `docs/contracts/run-manifest-schema.json` with v1.1 description + warnings-property object-with-5-fields shape | Story 5.3 AC-5.3.x + Story 5.4 AC-5.4.9 |

## Local invocation

```bash
RF_MCP_REPO_ROOT=/path/to/rf-mcp uv run robot \
    tests/dogfood/rf-mcp/test_trace_observability_parity.robot
```

All tests carry `[Tags] slow` and are excluded from the standard `uv run pytest` regression sweep. `RF_MCP_REPO_ROOT` defaults to `/home/many/workspace/rf-mcp` (Many's workstation); operators on other machines must override.

## CI wiring status

**Deferred to Story 9.1 / Story 9.2 per Phase-1 norm.** The repo's
[`dogfood-integration.yml`](../../../.github/workflows/dogfood-integration.yml) workflow is **install-smoke-only by design** — see the workflow header L13-21 documenting the Story 1a.2 HIGH-1 fake-green lesson 2026-05-17: cross-repo test execution against the wheel is fake-green CI until rf-mcp + robotframework-agentskills actually adopt agenteval as a dependency (which closes in Story 9.1 + 9.2). Until then, install-smoke is the truthful Phase-1 baseline; Story 5.5's `.robot` suite is **locally-runnable only**.

## Dogfood findings filed

Story 5.5 surfaces 4 actionable agenteval improvements (per AC-5.5.5 `AC-DOGFOOD-01` ≥1 requirement):

- **DF-5.5-DOGFOOD-1** — Multi-turn agent loop required for full agent-driven dogfood. Phase-1's `GenericAdapter.run()` ships ONLY observer attachment + mcp_coverage resolution. A real agent-driven scenario (model returns tool_calls → adapter dispatches via observer-wrapped MCP → result fed back to model → next turn) requires the loop deferred per DF-5.2-S3. Story 5.5 validates the OBSERVER + COVERAGE pipeline against rf-mcp, NOT the agent-loop integration. Phase-2 closes the gap. Catalogued as C43.

- **DF-5.5-DOGFOOD-2** — Adapter doesn't emit `chat_span` / `execute_tool_span`; spans only come from manual `telemetry.spans.invoke_agent_span(...)` context-manager use today. The `telemetry/spans.py` module ships the context-manager helpers but no adapter / provider calls them in `run()`. As a result, `Get Spans` returns `[]` for any Phase-1 test that doesn't explicitly wrap its work in a span context. Phase-2 wires adapter-level instrumentation. Catalogued as C44.

- **DF-5.5-DOGFOOD-3** — ADR-016 D1 trust-floor: attach IS the signal, NOT dispatch. Story 5.5 dogfood empirically corrected the spec's pre-edit assumption that no-tool-dispatch would degrade to `"external_mixed"`. Successful `observer.attach()` is sufficient to credit `"hosted_in_process"` per the ratified ADR. Documentation-only — no catalog entry (contract clarification reflected in `errors.py` docstring + parity-checklist row).

- **DF-5.5-DOGFOOD-4** — `Get Last Warnings test_id="current"` resolves via Listener-bound context. `.robot` suites invoked without `--listener AgentEval.telemetry.listener` route records to the `__suite__` sentinel which `"all"` lookup excluded per AC-5.4.5. **STATUS 2026-05-20**: CLOSED by Story 5.5 code-review HIGH-C fix — `Get Last Warnings test_id="__suite__"` lookup-mode added so Listener-less consumers can read the sentinel via the public RF surface. Originally catalogued as C45; closure note added in same PR.

All four findings are catalogued in `_bmad-output/implementation-artifacts/deferred-work.md` + `docs/phase-1-5-carry-overs.md` per `feedback_carry_over_catalog_gate`.

## Acknowledgements

- **Story 3.3 dogfood pattern (`test_mcp_surface_parity.robot`)** is the format precedent. Suite Setup + Teardown + `RF_MCP_REPO_ROOT` env override + `--directory` workaround for DOGFOOD-FINDING-A are re-used verbatim. The DOGFOOD-FINDING-A real fix is still tracked as `DF-3.3-S1`.
- **Story 5.2 ADR-016 D1 ratification** is the source-of-truth for the 3-state `mcp_coverage` value space + detection-failure default. The dogfood validates the ratified semantic against a real stdio MCP server.
- **`feedback_spec_vs_ratified_doc_precheck`** caught the D-3 framing drift in the pre-create-story drift check (26th consecutive use, 100% real-drift catch rate intact).
