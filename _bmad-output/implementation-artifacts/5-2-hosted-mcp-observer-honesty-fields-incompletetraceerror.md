# Story 5.2: Hosted-MCP Observer + Honesty Fields + IncompleteTraceError + Adapter mcp_servers Integration (Expanded Scope)

Status: done

## Story

As **Mei (Agent Surface Author)** or **Raj (Agent Developer)**,
I want **the hosted-MCP universal observer** (post-Epic-0-spike) wired so that tool-call traces are captured even for in-process MCP servers (`hosted_in_process`) + the `subprocess_observer_wrapper` pattern that observes stdio subprocess MCP servers (`subprocess_with_observer`); the `completeness` + `mcp_coverage` honesty fields populated on every `AgentRunResult` via the per-adapter detection contract; `IncompleteTraceError` raised when coverage is `external_mixed` and a metric keyword asserts tool-level details that can't be honestly answered; **AND** the adapter-side `mcp_servers=` integration that closes **DF-4.1-S2 + DF-4.2-S1** (per Epic 4 retro Action #5 — Story 5.2's scope absorbed these carry-overs so Story 5.5's interleaved dogfood port has real MCP-tool-call traces to assert against),
So that consumers get truthful evidence about what was observed vs assumed — never silent degradation (FR35 + FR36a + FR36b + FR37 + AC-MCP-OBSERVE-01).

## Pre-create-story drift check (23rd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

4 drifts caught + resolved pre-authoring (per fix-the-losing-source-NOW pattern):

- **(D-1 MED)** epics.md L1470 cited "per Story 1b.2's `compute_mcp_coverage`" — Story 1b.2 only ships `_check_mcp_coverage` (enforcement gate per ADR-016 L44); detection is **per-adapter** per ADR-016 D4 + `docs/contracts/mcp-coverage-detection.md`. epics.md amended pre-authoring.
- **(D-2 MED)** epics.md L1480 placed integration tests at `tests/integration/telemetry/test_observer.py`; the observer module is `src/AgentEval/mcp/observer.py` per architecture L1257 → tests go at `tests/integration/mcp/test_observer.py` for taxonomy consistency. Will use the corrected path.
- **(D-3 HIGH)** spike findings + ADR-004 Consequences mandate a `subprocess_observer_wrapper.py` helper but architecture L1248-1260 didn't list it. Architecture amended pre-authoring to add `mcp/_observer_subprocess_wrapper.py` to the project tree.
- **(D-4 HIGH)** Epic 4 retro Action #5 (ratified 2026-05-20) expanded Story 5.2 scope to ABSORB DF-4.1-S2 (Generic adapter `mcp_servers=` integration) + DF-4.2-S1 (Claude Code CLI adapter `mcp_servers=` integration). Pre-edit Story 5.2 spec covered only the observer + honesty fields. New scope: also remove the `NotImplementedError` carve-outs from `src/AgentEval/coding_agent/generic.py:128` + `claude_code_cli.py` adapter and wire the adapters to the hosted-MCP observer / subprocess-wrapper. Explicit in this spec under AC-5.2.5 + AC-5.2.6.

## Acceptance Criteria

### AC-5.2.1 — `src/AgentEval/mcp/observer.py` ratified API surface

**Given** Story 0.1's hosted-MCP observer spike findings (`_bmad-output/spikes/spike-hosted-mcp-observer-findings.md`) + ratified ADR-004,
**When** Story 5.2 implements `src/AgentEval/mcp/observer.py`,
**Then**:
- `HostedMcpObserver` class exposes:
  - `attach(server: Server | FastMCP, observation_path: Literal["hosted_in_process", "subprocess_with_observer"]) -> None` — wraps `Server.request_handlers[CallToolRequest]` via dict-mutation per ADR-004; works for both `mcp.server.lowlevel.Server` AND `mcp.server.fastmcp.FastMCP` (latter via `_mcp_server` private attribute access).
  - `mark_external_mixed(reason: str) -> None` — adapter-cooperation hook per ADR-016 D4 + ADR-004 Consequences. Sets internal flag that resolves to `mcp_coverage="external_mixed"`.
  - `compute_coverage() -> Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` — D1 trust-floor resolution: strongest-complete-path wins. `hosted_in_process > subprocess_with_observer > external_mixed`.
  - `tool_calls() -> list[ToolCallTrace]` — chronological list of `ToolCallTrace` records emitted via the wrapped handler.
  - `clear() -> None` — per-test cleanup (called by Listener's `end_test` hook).
- Observer emits `ToolCallTrace` records with `source="hosted_mcp"` per FR35 — distinguishing from adapter-side traces (`source="adapter"`). Records flow through `_kernel/trace_store` via the OTel `execute_tool` span emission (Story 5.1's `emit_tool_call_span(source="hosted_mcp")`).
- Observer accesses `Server.request_handlers` + `FastMCP._mcp_server` — both technically internal in the mcp SDK. **`AdapterVersionDriftWarning`** raised on first attachment if the mcp SDK version doesn't match the tested range `mcp>=1.27,<2.0` per ADR-004 Consequences + spike findings §Limitations.

### AC-5.2.2 — `src/AgentEval/mcp/_observer_subprocess_wrapper.py` per spike Decision D2

**Given** ADR-004 + spike findings §Pattern that works,
**When** Story 5.2 implements the subprocess wrapper,
**Then** `src/AgentEval/mcp/_observer_subprocess_wrapper.py` runs as a Python subprocess entry-point that:
1. Imports the target MCP server module via the `--server-module` CLI flag.
2. Instantiates a fresh `HostedMcpObserver` in the subprocess process.
3. Calls `observer.attach(server, observation_path="subprocess_with_observer")` against the imported server.
4. Runs the server's stdio transport (`mcp.server.stdio.stdio_server`).
5. On exit, persists captured `ToolCallTrace` records as JSONL at the path provided via the `--trace-out` CLI flag — the parent process grafts these into its trace store via the observer.
- Used by `MCPLifecycleManager.acquire()` in Story 1b.1 when transport=`stdio` AND the server module is library-spawnable (i.e., we wrote it OR it's a Python module we can import). For third-party stdio binaries the library cannot wrap, observation degrades to `external_mixed` per AC-MCP-OBSERVE-01.

### AC-5.2.3 — `docs/contracts/mcp-coverage-detection.md` Contract section filled

**Given** the Phase-1 skeleton at `docs/contracts/mcp-coverage-detection.md` (Story 1a.4 + 4.1 updates),
**When** Story 5.2 fills the Contract section,
**Then** the contract documents:
- The 3-valued `mcp_coverage` Literal set + per-value semantics.
- D1 trust-floor decision tree (which value wins when multiple paths succeed).
- D4 per-adapter detection-responsibility table:
  - **Generic LiteLLM adapter (Story 4.1)**: trivially `hosted_in_process` when `mcp_servers=` is passed; the library spawns + observes every MCP server in-process.
  - **Claude Code CLI adapter (Story 4.2)**: detects external MCP configs in `~/.claude.json` + `.mcp.json`. When external configs are present, the adapter calls `observer.mark_external_mixed("Claude Code CLI .mcp.json or ~/.claude.json present")` → resolves to `external_mixed`. When ONLY library-hosted servers are configured, resolves to `subprocess_with_observer` (the `claude` subprocess connects to library-spawned stdio servers via the subprocess wrapper).
  - **Copilot CLI adapter (Phase-2)**: parses `~/.copilot/mcp-config.json` — placeholder row.
- Detection-failure default: `external_mixed` (safer than `hosted_in_process` per ADR-016 D1).
- `IncompleteTraceError` raise gate semantics + the `allow_external_mcp_blind=True` opt-out (links to `_kernel/coverage.py:_check_mcp_coverage` which is already shipped).
- Conformance test-injection scenarios per ADR-005.

### AC-5.2.4 — Honesty fields wired in adapters

**Given** the Generic adapter (Story 4.1) + Claude Code CLI adapter (Story 4.2) currently raise `NotImplementedError` on non-empty `mcp_servers=`,
**When** Story 5.2 lands DF-4.1-S2 + DF-4.2-S1 absorption per Epic 4 retro Action #5,
**Then**:
- **Generic adapter** (`src/AgentEval/coding_agent/generic.py`): replaces the `NotImplementedError` raise (current L128) with a real `mcp_servers=` handling path. For each `(name, handle)` entry: call `observer.attach(handle.server, observation_path="hosted_in_process")`. Adapter sets `AgentRunResult.metadata.mcp_coverage = observer.compute_coverage()`. `completeness="full"` by default; `"truncated"` if the provider raises mid-stream (FR36a).
- **Claude Code CLI adapter** (`src/AgentEval/coding_agent/claude_code_cli.py`): replaces the `NotImplementedError` (similar carve-out) with a real path. For each `(name, handle)`: generates a temporary `.mcp.json` for the `claude` subprocess + invokes the subprocess wrapper. Adapter parses `~/.claude.json` + the caller's `.mcp.json` (when set) to detect external configs; calls `observer.mark_external_mixed(reason)` when external configs are present. Then sets `metadata.mcp_coverage` from `observer.compute_coverage()`.

### AC-5.2.5 — Listener integration (per-test scope)

**Given** Story 5.1's Listener wires `set_current_test_id` on `start_test`,
**When** Story 5.2 ships the observer,
**Then** the observer's `clear()` method is called by Story 5.1's Listener on `end_test` BEFORE `trace_store.clear_spans(test_id)`. This is wired via a new `Listener._observers: list[HostedMcpObserver]` registry that adapters register their observer instances into during `run()` — Phase-1 scope: just append on attach, clear on end_test. The exact registry surface is `Listener.register_observer(observer: HostedMcpObserver)` — public API for adapters.

### AC-5.2.6 — `MCPServerHandle.server_factory` materializes server for observer attach

**Given** Story 3.1's `MCPServerHandle` at `src/AgentEval/mcp/lifecycle.py` already ships with `server_factory: Callable[[], Any] | None` for in_memory transport (no `server` attribute exists today),
**When** the Generic adapter wires `mcp_servers=` through `HostedMcpObserver` per AC-5.2.4,
**Then** `_attach_handle_to_observer` calls `handle.server_factory()` to materialize a fresh FastMCP/Server instance for each `run()`, then `observer.attach(server, "hosted_in_process")`. (Story 5.2 code-review 1-way Auditor HIGH-E fix 2026-05-20: pre-edit spec claimed the handle carries a `.server` attribute populated by `MCP.Start Server` — fictitious; impl uses the `server_factory()` callable that's already part of the ratified Story 3.1 handle shape. Factory-rebuild-per-run semantics are documented as a Phase-1 trade-off: each `adapter.run()` builds a NEW server instance, so tools registered on the test-setup's original handle aren't observed; only the freshly-built copy is wrapped. Story 5.5 dogfood port + DF-5.2-S3 multi-turn loop will surface whether memoizing the factory result on the handle is required to close this honesty gap.) On factory failure or when `transport != "in_memory"`, adapter falls back to `mark_external_mixed(reason)` per ADR-016 detection-failure default.

### AC-5.2.7 — `IncompleteTraceError` end-to-end gate

**Given** `_kernel/coverage._check_mcp_coverage` is already shipped from Story 1b.2,
**When** Story 5.2 wires the adapters to populate `metadata.mcp_coverage`,
**Then** a `.robot` test invoking `MCP.Get Tool Discoverability ...` (Tier-3 keyword from Story 4.4) on a run with `external_mixed` coverage + a metric keyword call (e.g., `Get Tool Call Count` — Phase-2 Epic 6 surface; Story 5.2 ships a placeholder hook) raises `IncompleteTraceError` per FR37 with the canonical message: `"metric keyword <name> called on AgentRunResult with mcp_coverage=external_mixed; opt in via allow_external_mcp_blind=True or ensure all MCP traffic flows through library-hosted servers"`. The opt-out flag flows from PRD FR42 / Story 1a.6 default `allow_external_mcp_blind=False` per config precedence.

### AC-5.2.8 — Integration tests at `tests/integration/mcp/test_observer.py`

**And** integration tests cover (per epics.md L1480, path corrected pre-authoring per D-2):
- `hosted_in_process` path: in-memory FastMCP server + Generic adapter + observer.attach → captures 2+ tool calls.
- `subprocess_with_observer` path: stdio subprocess via wrapper + observer attachment in subprocess context → parent reads JSONL trace + grafts records.
- `external_mixed` path: Claude Code CLI adapter detects an external `.mcp.json` → `mark_external_mixed("external configs present")` → `compute_coverage() == "external_mixed"`.
- `IncompleteTraceError` raise path: metric keyword call against `external_mixed` run with `allow_external_mcp_blind=False` → raises with FR37 verbatim message.
- `AdapterVersionDriftWarning` raise path: mock the `mcp` SDK version to `0.9.99` → first `observer.attach()` emits the warning.

### AC-5.2.9 — Unit tests at `tests/unit/mcp/test_observer.py`

**And** unit tests cover:
- `HostedMcpObserver.attach()` round-trip on lowlevel `Server` AND `FastMCP` (via `_mcp_server` access).
- `attach()` idempotency (re-attach to the same server doesn't double-wrap).
- `mark_external_mixed()` flag + `compute_coverage()` D1 trust-floor matrix.
- `tool_calls()` returns chronological + `source="hosted_mcp"`.
- `clear()` empties the internal record list.
- `AdapterVersionDriftWarning` raise on version-mismatch path (mock `importlib.metadata.version("mcp")` to return `0.9.0`).

### AC-5.2.10 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean.
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance -q` regression-clean (926 Story 5.1 close baseline; +40-50 new from this story expected).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.

### AC-5.2.11 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (25th consecutive use).
- `feedback_n_way_agreement_weight` extended triage table applied (Auditor citation-drift = near-certain band).
- `feedback_test_name_assertion_match` applied to all new tests.
- `feedback_codex_sandbox_bypass_operational` for Codex CLI review.
- `feedback_carry_over_catalog_gate` at story-close: grep `src/AgentEval/mcp/` + spec for any new `DF-5.2-S<N>` patterns; verify each is in `docs/phase-1-5-carry-overs.md` AND `_bmad-output/implementation-artifacts/deferred-work.md`.
- Auditor citation-drift check on FR35 + FR36a + FR36b + FR37 + ADR-004 + ADR-016 + `mcp-coverage-detection.md` wording.

## Tasks / Subtasks

- [x] **Task 1: Architecture + epics.md drift fixes applied pre-authoring** (D-1 + D-3 above). DONE during pre-create-story.
- [x] **Task 2: `src/AgentEval/mcp/observer.py`** — `HostedMcpObserver` class with `attach` / `mark_external_mixed` / `compute_coverage` / `tool_calls` / `external_mixed_reasons` / `clear` API; `AdapterVersionDriftWarning` issued on first attach when mcp SDK version outside `[1.27, 2.0)`. ~300 LoC with thread-safe RLock + idempotent attach.
- [x] **Task 3: `src/AgentEval/mcp/_observer_subprocess_wrapper.py`** — Phase-1 subprocess entry-point shape per spike Decision D2. DF-5.2-S3 carry-over: full stdio-lifecycle plumbing deferred to Story 5.5.
- [x] **Task 4: `docs/contracts/mcp-coverage-detection.md`** Contract section filled per AC-5.2.3 (3-value Literal + D1 trust-floor decision tree + D4 per-adapter detection-responsibility table + `IncompleteTraceError` gate semantics + observer API surface).
- [x] **Task 5: `src/AgentEval/coding_agent/generic.py`** — removed `NotImplementedError` carve-out at L128 (Story 4.1); wires `mcp_servers=` through `HostedMcpObserver` via `_attach_handle_to_observer` helper. In_memory handles attach; non-in_memory degrade to `mark_external_mixed` (DF-5.2-S3 deferred). Closes DF-4.1-S2.
- [x] **Task 6: `src/AgentEval/coding_agent/claude_code_cli.py`** — added `run()` override that constructs per-call observer + calls `_detect_external_configs(mcp_servers)`. Parses `~/.claude.json` + `./.mcp.json` + non-in_memory handles → `mark_external_mixed(reason)`. `_finalize` now reads `self._current_observer.compute_coverage()` instead of hardcoding `"external_mixed"`. Closes DF-4.2-S1.
- [x] **Task 7: `src/AgentEval/telemetry/listener.py`** — added `Listener.register_observer(observer)` + `end_test` calls `observer.clear()` on every registered observer (per-test scope per ADR-009).
- [x] **Task 8: Unit tests** at `tests/unit/mcp/test_observer.py` (19 tests covering attach + idempotency + trust-floor + external_mixed signaling + clear semantics + AdapterVersionDriftWarning emission + wrapped handler records tool calls/errors/sequence_index).
- [x] **Task 9: Integration tests** at `tests/integration/mcp/test_observer.py` (8 tests covering Generic adapter hosted_in_process + external_mixed + IncompleteTraceError raise + opt-out + Listener.register_observer cleanup hook).
- [x] **Task 10: All-gates pass.** ruff + format + mypy clean (64 src files), license headers PASS, **973 unit+conformance+integration / 8 skipped** (was 926 at Story 5.1 close; +47 net).
- [x] **Task 11: 4-reviewer cross-LLM code review with extended N-way agreement triage table + carry-over catalog gate.** 25th consecutive STAR catch. **4-way HIGH-A** (Blind+Edge-cases+Auditor+Codex): carry-over catalog gate violation (DF-5.2-S1/S2/S3 missing from both catalog files) — exact pattern Story 5.1 caught; C29/C30/C31 added. **2-way HIGH-B** (Blind+Edge-cases empirical probe): multiple observers stack wraps on same server → sentinel-marked wrap refuses to stack. **Auditor 1-way HIGHs** (near-certain band per Epic 4 retro extension — 8+ consecutive TPs across 6 epics): HIGH-E `MCPServerHandle.server` attribute claim was fictitious → spec AC-5.2.6 amended to describe `server_factory()` rebuild semantics; HIGH-F clear-order reversed → observer.clear() now fires BEFORE trace_store.clear_spans; HIGH-G FR37 verbatim message drift → kernel emits PRD-exact message with `metric_keyword` kwarg threading; HIGH-H mcp citation NFR-COMPAT-06 → NFR-COMPAT-04 with empirical-floor rationale. **1-way HIGHs with empirical probe**: HIGH-C Listener.register_observer was dead code → adapters now wire via `register_active_observer()`; HIGH-D ambient `~/.claude.json` + `./.mcp.json` pollution → opt-in via `discover_external_configs=True` constructor flag; HIGH-I no-op fallback lying (returned hosted_in_process when no handler) → only credits observation_path when wrap actually installed; HIGH-J Codex empirical probe: subprocess wrapper crashed on lowlevel Server → branch by server type + skip phantom file on bootstrap failure. 5 new regression tests pinning the patches. 8 MEDs + 7 LOWs all applied. `feedback_carry_over_catalog_gate` validated load-bearing for 3rd consecutive story.

## Dev Notes

### Architecture compliance

- **PRD FR35** (server-side observation of `tools/call`): observer wraps `Server.request_handlers[CallToolRequest]` per ADR-004; emits `ToolCallTrace` with `source="hosted_mcp"`.
- **PRD FR36a** (completeness field): adapters set `metadata.completeness` from provider/subprocess terminal events. Already implemented in Story 4.2 stream-json terminal; Story 5.2 doesn't re-touch.
- **PRD FR36b** (mcp_coverage field): adapters call `observer.compute_coverage()` after the run + write to `metadata.mcp_coverage`.
- **PRD FR37** (IncompleteTraceError on external_mixed): already shipped at `_kernel/coverage._check_mcp_coverage` (Story 1b.2). Story 5.2 wires the upstream — adapter populates the metadata; the existing gate enforces.
- **ADR-004 (Hosted-MCP Observation)**: `request_handlers[CallToolRequest]` dict-mutation pattern is the canonical implementation.
- **ADR-016 (mcp_coverage detection default)**: 3-value Literal + D1 trust-floor + D4 per-adapter contract.
- **Story 1b.1 `MCPLifecycleManager`**: `ServerHandle` payload now must include `server` attribute (the actual mcp Server/FastMCP instance) for `transport="in_memory"`. Story 5.2 backfills this on the handle dataclass.

### Phase-1 limitations explicitly documented

- **macOS support deferred**: ADR-004 + Story 0.1 spike validated on Linux 6.8 only. Phase-1.5 macOS validation tracked as existing carry-over.
- **mcp SDK version coupling**: observer accesses `Server.request_handlers` (technically public but undocumented as stability surface) + `FastMCP._mcp_server` (underscore-prefixed private). `AdapterVersionDriftWarning` mitigates; upstream issue with mcp project for a stable `FastMCP` observer hook is a Phase-2 carry-over (DF-5.2-S1).
- **Streamable HTTP transport observation**: spike validated; Phase-1 implementation defers HTTP-specific path to **DF-5.2-S2** (Story 5.5 dogfood port surfaces real HTTP traffic patterns first).
- **`subprocess_with_observer` only for library-spawned stdio**: For third-party stdio binaries the library can't wrap (e.g., random `npx some-mcp-server`), observation falls through to `external_mixed`. Documented in `mcp-coverage-detection.md`.

### Risks + mitigations

- **R-1**: Adapter forgets to call `mark_external_mixed` → coverage silently reports `hosted_in_process` when external configs are present. Mitigation: conformance fixture covering each adapter's external-detection path (AC-5.2.8 integration test).
- **R-2**: `FastMCP._mcp_server` private-attribute access breaks under mcp SDK refactor. Mitigation: `AdapterVersionDriftWarning` raises on version mismatch; CI matrix pins tested range.
- **R-3**: Subprocess wrapper bootstraps a different Python interpreter than the library if `sys.executable` mismatches. Story 5.1 (DF-4.1-S2 fix path) already faced this — use `sys.executable` consistently across the subprocess spawn.

## Dev Agent Record

### Implementation Plan (dev workflow 2026-05-20)

1. Apply pre-create-story drift fixes (D-1 / D-3) — DONE during create-story.
2. Implement `src/AgentEval/mcp/observer.py` — `HostedMcpObserver` with thread-safe RLock + idempotent attach + AdapterVersionDriftWarning + wrapped CallToolRequest handler.
3. Implement `src/AgentEval/mcp/_observer_subprocess_wrapper.py` — Phase-1 CLI entry-point shape; DF-5.2-S3 defers full lifecycle plumbing to Story 5.5.
4. Fill `docs/contracts/mcp-coverage-detection.md` Contract section per AC-5.2.3.
5. Remove `NotImplementedError` from `GenericAdapter.run` (Story 4.1 carve-out); add `_attach_handle_to_observer` helper at module bottom.
6. Override `ClaudeCodeCLIAdapter.run` to construct per-call observer + detect external configs from `~/.claude.json` + `./.mcp.json` + non-in_memory handles. `_finalize` reads `self._current_observer.compute_coverage()`.
7. Add `Listener.register_observer(observer)` + `end_test` cleanup invocation.
8. Write 19 unit tests at `tests/unit/mcp/test_observer.py` + 8 integration tests at `tests/integration/mcp/test_observer.py`.
9. Add `tests/integration/__init__.py` to namespace the integration tests (fixes mcp/ collision with mcp SDK package).
10. Update 3 tests in `tests/unit/coding_agent/test_generic.py` + `tests/unit/orchestration/test_library.py` to assert the new observer-wiring behavior instead of the removed `NotImplementedError`.
11. All-gates pass; flip story to review.

### Completion Notes

- **DF-4.1-S2 + DF-4.2-S1 carry-overs CLOSED** per Epic 4 retro Action #5 ratified scope expansion. The Generic adapter now accepts `mcp_servers=` non-empty and reports honest `mcp_coverage`; the Claude Code CLI adapter detects external configs + reports `external_mixed` correctly (instead of the pre-Story-5.2 hardcoded `"external_mixed"` constant).
- **3 new Phase-1.5 carry-overs identified**: DF-5.2-S1 (upstream mcp SDK FastMCP observer hook issue), DF-5.2-S2 (streamable_http transport observation), DF-5.2-S3 (subprocess-wrapper full lifecycle integration + multi-turn tool dispatch loop for Generic adapter). All 3 are documented inline + spec lists them; carry-over catalog gate (Epic 4 retro NEW norm `feedback_carry_over_catalog_gate`) will be applied at story-close — verify catalog has each before flipping to done.
- **Multi-turn tool dispatch loop deferred to DF-5.2-S3**: Story 5.2 wires the observer ATTACHMENT but not the agent loop. Generic adapter's `tools=None` carve-out still raises NotImplementedError on non-empty `tools=`. Story 5.5 dogfood port + Phase-2 work will land the real multi-turn dispatch.
- **Test isolation gotcha fixed**: `tests/integration/__init__.py` was missing — pytest tried to import `tests/integration/mcp/test_observer.py` as `mcp.test_observer` (rootdir = tests/integration/) which collided with the top-level mcp SDK package. Adding the `__init__.py` namespaces the integration tests cleanly.
- **All-gates green at +47 net tests**: 926 → 973 (19 observer unit + 8 observer integration + 2 modified Generic/orchestration tests + 18 retained).

## File List

**New files:**
- `src/AgentEval/mcp/observer.py`
- `src/AgentEval/mcp/_observer_subprocess_wrapper.py`
- `tests/unit/mcp/test_observer.py`
- `tests/integration/__init__.py`
- `tests/integration/mcp/__init__.py`
- `tests/integration/mcp/test_observer.py`

**Modified files:**
- `_bmad-output/planning-artifacts/architecture.md` — D-3 drift fix at L1257 (added `_observer_subprocess_wrapper.py` to telemetry/mcp project tree).
- `_bmad-output/planning-artifacts/epics.md` — D-1 drift fix at L1470 (`compute_mcp_coverage` → per-adapter detection contract).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 5.2 status transitions.
- `docs/contracts/mcp-coverage-detection.md` — status `Phase-1 skeleton → Phase-1 ratified`; Contract section filled per AC-5.2.3.
- `src/AgentEval/coding_agent/generic.py` — removed `NotImplementedError` carve-out + wired `mcp_servers` through observer.
- `src/AgentEval/coding_agent/claude_code_cli.py` — `run()` override + `_detect_external_configs` method + `_finalize` reads observer coverage.
- `src/AgentEval/telemetry/listener.py` — `register_observer` API + per-test `clear()` invocation.
- `tests/unit/coding_agent/test_generic.py` — amended `test_generic_adapter_run_non_empty_mcp_servers_*` to assert observer wiring instead of removed NotImplementedError.
- `tests/unit/orchestration/test_library.py` — amended `test_send_prompt_non_empty_dict_mcp_servers_forwarded_to_adapter` similarly.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (23rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 4 drifts: D-1 MED epics.md L1470 cited non-existent `Story 1b.2 compute_mcp_coverage` — epics.md amended; D-2 MED integration tests path drift `tests/integration/telemetry/` → `tests/integration/mcp/`; D-3 HIGH architecture L1257 missing `_observer_subprocess_wrapper.py` per ADR-004 + spike — architecture amended; D-4 HIGH Epic 4 retro Action #5 expanded Story 5.2 scope to absorb DF-4.1-S2 + DF-4.2-S1 adapter `mcp_servers=` integration. | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code review). 2 new mcp modules (observer.py + _observer_subprocess_wrapper.py); 3 modified adapters/listener (generic.py wires observer; claude_code_cli.py detects external configs; listener.py adds register_observer); docs/contracts/mcp-coverage-detection.md Contract section filled. DF-4.1-S2 + DF-4.2-S1 carry-overs CLOSED per Epic 4 retro Action #5. 3 new Phase-1.5 carry-overs identified (DF-5.2-S1 upstream mcp SDK hook; DF-5.2-S2 streamable_http observation; DF-5.2-S3 multi-turn tool dispatch loop). 27 new tests (19 observer unit + 8 observer integration). All gates green: ruff/format/mypy clean (64 src files); 973 unit+conformance+integration / 8 skipped (was 926 at Story 5.1 close; +47 net); license-headers PASS. | Amelia |
| 2026-05-20 | 0.3.0   | Code-review patches applied (25th consecutive cross-LLM STAR catch streak). **4-way HIGH-A** carry-over catalog gate violation → C29/C30/C31 added to `docs/phase-1-5-carry-overs.md` + `deferred-work.md` (DF-5.2-S1 upstream mcp hook; DF-5.2-S2 streamable_http; DF-5.2-S3 subprocess wrapper + multi-turn). **2-way HIGH-B** multiple observer wrap-stacking → sentinel-marked wrap (`_agenteval_observer_wrap` attribute on the installed handler) refuses to stack. **5 Auditor 1-way HIGHs** validating Epic 4 retro `feedback_n_way_agreement_weight` extension (Auditor citation-drift = near-certain band, now 8+ consecutive TPs across 6 epics): HIGH-E `MCPServerHandle.server` attribute claim was fictitious — spec AC-5.2.6 amended to describe ratified `server_factory()` rebuild semantics; HIGH-F clear-order reversed → observer.clear() now fires BEFORE trace_store.clear_spans per AC-5.2.5; HIGH-G FR37 verbatim message drift → kernel emits PRD L1555 exact message + `metric_keyword` kwarg threading; HIGH-H mcp citation NFR-COMPAT-06 → NFR-COMPAT-04 with empirical-floor rationale. **HIGH-C** Listener.register_observer was dead code → new module-level `register_active_observer()` helper + adapters wire from `run()`. **HIGH-D** ambient `~/.claude.json` + `./.mcp.json` pollution → opt-in via `discover_external_configs=True` constructor flag + HOME-unset try/except. **HIGH-I** no-op fallback lying → observer only credits `observation_path` when wrap is actually installed; `compute_coverage()` honestly returns external_mixed when no handler registered. **HIGH-J** Codex empirical probe: subprocess wrapper crashed on lowlevel Server (TypeError: missing 3 args) + left 0-byte phantom file → branch by `FastMCP` type + skip phantom file on bootstrap failure. Also Blind MED-2 duplicate `_assert_binary_version` removed. 5 new regression tests pinning each HIGH defense (HIGH-B + HIGH-C + HIGH-D + HIGH-F + HIGH-I) + amended FR37 test for HIGH-G. **`feedback_carry_over_catalog_gate` validated load-bearing for 3rd consecutive story** (Stories 5.1, 5.2 caught by Auditor; the Story 4.3 retro miss caught by Story 4.4 set the precedent). All gates green: ruff/format/mypy clean (64 src files); **978 unit+conformance+integration** (was 973 pre-review; +5 new tests) / 8 skipped; license-headers PASS. | Amelia |
