# Parity Checklist — rf-mcp MCP-Surface Port (Story 3.3)

**Source corpus:** [rf-mcp](https://github.com/manykarim/rf-mcp) @ SHA `235d679785fd4e5f647e9e760ec7da2a3d09b7ef` (snapshot 2026-05-19).
**Source files covered (representative subset):**
- `tests/test_mcp_simple.py` (133 LoC)
- `tests/test_mcp_comprehensive.py` (237 LoC)
- `tests/test_mcp_error_scenarios.py` (581 LoC)
- `tests/test_plugins_basic.py` (177 LoC)
- **Total source LoC: 1128**

**Story 3.3 scope (drift D-C, ratified 2026-05-19):** REPRESENTATIVE subset — 15 `.robot` test cases covering the MCP-surface assertions (server config, lifecycle, tool inventory, happy-path tool calls, error-response tool calls, latency + correlation_id). Full 1:1 parity for the 1128-LoC pytest corpus is **Story 9.1 + Phase-1.5** scope (when rf-mcp adopts agenteval as a dependency, the .robot suite migrates into rf-mcp itself + the dogfood-integration.yml CI workflow extends to clone-and-run).

**Local execution:** `uv run robot tests/dogfood/rf-mcp/test_mcp_surface_parity.robot` — pass-rate **15/15 (100%)** as of 2026-05-19 against live `robotmcp` server (heavy, ~6s startup amortized via `mcp_per_test="suite"`).

**Performance baseline:** suite wall-clock ~30-60s on dev workstation (Intel i9, 32GB RAM, Linux 6.8); ~2s per tool-call after suite-shared handshake. Epic 8b Recipe Gallery #5 absorption is deferred (drift D-D).

---

## Mapping table

| .robot test name | rf-mcp pytest source | Parity status | Notes |
| --- | --- | --- | --- |
| `Rfmcp Config Parses And Declares Robotmcp Server` | (implicit; pytest tests in-process, never parses .mcp.json) | agenteval-native | Adds a static-inspection assertion the pytest suite doesn't have because pytest's `Client(mcp)` fixture skips the config layer. |
| `Rfmcp Config Preserves Env Block Subset` | (implicit) | agenteval-native | Verifies env passthrough; rf-mcp's robotmcp depends on `ROBOTMCP_*` + `PYTHONPATH`. |
| `Rfmcp Config Declares Multiple Servers` | (implicit) | agenteval-native | rf-mcp's real config has `robotmcp` + `claude-flow`. |
| `Robotmcp Server Handle Constructs Without Spawning` | (implicit; pytest skips lifecycle layer) | agenteval-native | Validates the per-call-session Phase-1 pattern. |
| `Robotmcp Server Connects And Negotiates Protocol Version` | `tests/test_mcp_simple.py` L13-17 (`mcp_client` fixture creates `Client(mcp)`) | representative | rf-mcp uses in-process; agenteval drives stdio subprocess. Same handshake contract. |
| `Robotmcp List Tools Includes Execute Step` | `tests/test_mcp_simple.py:test_simple_log_execution` L23-43 | representative | Pytest indirectly verifies via successful `call_tool("execute_step", ...)`; .robot asserts via explicit `MCP.List Tools`. |
| `Robotmcp List Tools Includes Analyze Scenario` | `tests/test_mcp_simple.py:test_analyze_scenario_structure` L46-58 | representative | Same pattern. |
| `Robotmcp List Tools Includes Find Keywords` | `tests/test_mcp_simple.py:test_find_keywords_structure` L60-65 | representative | Same pattern. |
| `Robotmcp Execute Step Tool Has Input Schema With Keyword Field` | (implicit; pytest doesn't introspect schema) | agenteval-native | Verifies tool input_schema's structural shape via `MCPTool.input_schema`. |
| `Robotmcp Execute Step Calls Log Keyword Successfully` | `tests/test_mcp_simple.py:test_simple_log_execution` L23-43 | full | Direct port; same args + same result-shape assertions. |
| `Robotmcp Analyze Scenario Returns Success` | `tests/test_mcp_simple.py:test_analyze_scenario_structure` L46-58 | full | Direct port. |
| `Robotmcp Find Keywords Returns Results` | `tests/test_mcp_simple.py:test_find_keywords_structure` L60-65 + `tests/test_mcp_comprehensive.py:test_find_keywords_strategies` L68-79 | full | Pattern-strategy variant. |
| `Robotmcp Execute Step With Invalid Keyword Yields Is Error` | `tests/test_mcp_error_scenarios.py:test_execute_step_invalid_keyword` | representative | rf-mcp's error semantics vary by code path; .robot asserts the no-exception invariant + latency_ms. |
| `Robotmcp Call Unknown Tool Yields Is Error` | (mirrors agenteval's AC-3.2.5 + MCP spec) | full | Direct application of FR9b error-response-is-first-class-data. |
| `Robotmcp Call Tool Reports Per-Call Correlation Id` | (implicit; pytest doesn't surface correlation_id) | agenteval-native | Validates Story 3.2 FR9b correlation_id Phase-1 uuid4 placeholder. |

---

## Deferred parity (Story 9.1 + Phase-1.5)

The following rf-mcp test scenarios are NOT ported in Story 3.3 — they remain in the pytest suite as upstream evidence + will migrate when rf-mcp adopts agenteval (Story 9.1):

- `test_mcp_comprehensive.py` — 13 of 14 tests (recommend_libraries modes, manage_library_plugins, manage_session init/import, execute_step variable assignments, execute_flow branches, build_suite, check_library_availability, get_keyword_info modes, set_library_search_order, run_test_suite dry+full, get_locator_guidance, manage_attach_status). All exercise the same `MCP.Call Tool` surface; full port is mechanical once Story 9.1 adopts agenteval.
- `test_mcp_error_scenarios.py` — 25 of 26 tests. Most exercise edge-case argument handling; high-value for full parity but each test adds 1-2s of suite runtime. Phase-1.5 budget decision.
- `test_plugins_basic.py` — 4 tests. Test rf-mcp's plugin registry directly (NOT via MCP). Out of agenteval's MCP-surface scope.
- 100% of asyncio fixture, parametrize, monkeypatch patterns — translatable but RF-syntax-heavy; defer until Story 9.1 + a dedicated parity-pass.

---

## Dogfood findings (AC-3.3.8 — ≥1 actionable improvement required)

Story 3.3 surfaced **2 real load-bearing findings** during the parity port. Both are tracked in `_bmad-output/implementation-artifacts/deferred-work.md` under "Dogfood findings from rf-mcp MCP-surface port (Story 3.3, 2026-05-19)":

### DOGFOOD-FINDING-1 (HIGH, fixed in Story 3.3)

**`io.UnsupportedOperation: fileno` under Robot Framework runtime**: the MCP SDK's `stdio_client(server, errlog=sys.stderr)` default crashes under `robot` execution because RF's listener replaces `sys.stderr` with a non-fd capture buffer AND the SDK calls `.fileno()` on the errlog handle when spawning the subprocess. Story 3.3 dev fixed this by passing `errlog=sys.__stderr__` (the un-wrapped real stderr Python stashes at interpreter startup) explicitly. Without the fix, **11 of 15 parity tests failed** (every stdio-using test). The pre-Story-3.3 transport.py comment claimed "errlog is NOT passed to avoid this" — but the SDK's default WAS `sys.stderr`, so the comment was misleading + the fix was missing. This is exactly the kind of friction `feedback_review_methodology_norms` interleaved-dogfood is designed to catch in week 3 rather than week 10.

### DOGFOOD-FINDING-A (MED, workaround applied; real fix Phase-1.5 DF-3.3-S1)

**`MCP.Start Server` lacks a `cwd=` parameter**: rf-mcp's `.mcp.json` declares `command="uv", args=["run", "-m", "robotmcp.server"]` — `uv run` resolves the project from the cwd, but agenteval's `start_server` doesn't expose a way to set the subprocess cwd. Without a workaround, the robotmcp subprocess exited immediately with `ModuleNotFoundError: No module named 'robotmcp'` (because agenteval's cwd → agenteval's `.venv`, not rf-mcp's). Story 3.3 documented the gap + applied a workaround: inject `--directory ${RF_MCP_REPO_ROOT}` into the args list at suite setup. Real fix is to extend `MCPServerHandle` + `start_server` with a `cwd: str | None = None` field (additive; non-breaking) — tracked as DF-3.3-S1.

**Bonus validation of Story 3.2 patches**: when the robotmcp subprocess immediately exits (before fix-A workaround), the SDK raised `McpError("Connection closed")` — which is now mapped to `MCPConnectionLostError` by the Story 3.2 code-review HIGH-2 fix (Codex Probe 7 widening). Pre-Story-3.2 the operator would have seen a raw `McpError` with no `server_name`/`last_operation`/`fix_suggestion`. Story 3.2's behavioral-probe-driven HIGH catch is validated in production by Story 3.3's dogfood.
