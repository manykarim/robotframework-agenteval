# Story 3.1: MCP Server Lifecycle Keywords — Start + Connect + Stop + Spec Version Gate

Status: ready-for-dev

## Story

As **Mei (Agent Surface Author — MCP author mode)** or **Priya (QA Engineer)**,
I want **`MCP.Start Server`, `MCP.Connect To Server`, `MCP.Stop Server` keywords (PRD FR7 + FR8) supporting `stdio` + `in_memory` transports in Phase-1 (streamable_http via SDK passthrough; full integration deferred), with MCP spec version validated at connect time per FR46 + AC-MCP-OBSERVE-02 + per-test scope cleanup honored under `pabot` via Story 1b.1's `MCPLifecycleManager`**,
So that I can lifecycle MCP servers in a `.robot` test using the cleanup strategy chosen by the consumer (`True / False / "suite"` per ADR-009 + Story 1a.6), and unsupported MCP spec versions fail loudly with `UnsupportedMCPVersionError` (4th `AgentEvalCompatError` family leaf — first IMPLEMENTED Compat leaf with a real runtime raise site).

## Pre-create-story drift check (15th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19)

5 drifts caught + resolved pre-authoring:

- **(D-A MED)** epics.md L1232 said `MCP.Connect`; PRD FR8 verbatim says `MCP.Connect To Server`. epics.md L1232 amended.
- **(D-B HIGH)** epics.md L1253 said `[Tier 2 — LLM-Deterministic]` libdoc badge. This badge does NOT exist in `src/AgentEval/_kernel/tier.py` (the 3 ratified badges are `[Tier 1 — Deterministic]`, `[Tier 2 — Stochastic Single-Shot]`, `[Tier 3 — Stochastic Fan-Out]`). MCP lifecycle keywords are Tier 1 (deterministic given same env + server binary; I/O latency variance is captured separately via NFR-PERF metrics, NOT via tier badge). Polling is ALLOWED for Tier 1 (e.g., "wait for server ready"). epics.md L1253 amended.
- **(D-C HIGH)** `UnsupportedMCPVersionError` inherits `AgentEvalCompatError` directly (Epic 2 retro Action #3 ratified 2026-05-19 by Many). Follows `UnsupportedBinaryVersionError` precedent (Story 1b.4 D6/D7): domain-specific `__str__` override; NO `_FR59Tier1SetupFailureError` intermediate (the FR59 5-line layout doesn't fit "MCP server reported spec_version=X, expected Y-Z" runtime context).
- **(D-D MED)** epics.md L1241 said `mcp_per_test="test"` — invalid 4th mode. ADR-009 + Story 1a.6 baseline pin 3 modes: `True / False / "suite"`. `True` is the default per-test scope. epics.md L1241 amended.
- **(D-E MED)** Per-sub-library CI step assertion (Epic 2 retro Action #1). Story 3.1 introduces new module paths (`mcp/transport.py`, `mcp/version_gate.py`, `mcp/bundled/echo.py`, `tests/unit/mcp/test_transport.py`, `tests/unit/mcp/test_version_gate.py`). The CI workflow `.github/workflows/ci.yml` already runs `pytest tests/unit -q` which picks up `tests/unit/mcp/`; no new step needed. **BUT** the conformance step from Story 2.4 might not pick up `tests/unit/mcp/*.py` if they get a new subdirectory — verify with the loaded gate.

Pre-authoring fixes: `_bmad-output/planning-artifacts/epics.md` L1232 + L1241 + L1253 amended.

## Phase-1 scope clarification

Per the Phase-1 ship-then-extend pattern (proven across Stories 1b.2 → 1b.4 → 2.1 → 2.2 → 2.3 → 2.4):

- **In scope:** `stdio` transport (subprocess lifecycle via `MCPLifecycleManager`); `in_memory` transport (in-process FastMCP-style echo); spec version gate via MCP SDK's `initialize` handshake; `UnsupportedMCPVersionError` raise site; `mcp_per_test=True|False|"suite"` cleanup; bundled echo MCP server at `src/AgentEval/mcp/bundled/echo.py`.
- **Phase-1 carve-out:** `streamable_http` transport is registered + the MCP SDK's `streamablehttp_client` is exposed via the transport layer, but full integration testing (httpx-backed echo server, real round-trip) is deferred to **Phase-1.5 OR Epic 3 Story 3.2** at the spec author's discretion. The Phase-1 contract is "transport enum accepted; stdio + in_memory are smoke-tested; streamable_http is a documented passthrough surface".
- **Out of scope:** Tool LISTING + tool CALL (those are Story 3.2). This story is server LIFECYCLE only.

## Acceptance Criteria

### AC-3.1.1 — `UnsupportedMCPVersionError` class (4th Compat-family leaf, first IMPLEMENTED)

**Given** the 16-leaf catalog at `docs/contracts/error-class-hierarchy.md` L80,
**When** Story 3.1 implements `class UnsupportedMCPVersionError(AgentEvalCompatError)` at `src/AgentEval/errors.py`,
**Then** the class has:
- `error_code: ClassVar[str] = "UNSUPPORTED_MCP_VERSION"` matching the catalog L80 row.
- `__init__(message, *, server_version: str | None = None, supported_range: str | None = None)` exposing structured attrs (parallel to `UnsupportedBinaryVersionError` Story 1b.4 D7).
- `__str__` override emitting the FR46-shaped message: `"MCP server version <X> outside library tested range <range>"` (FR8 wording verbatim).
- The intermediate `_FR59Tier1SetupFailureError` is NOT inherited — this is a RUNTIME error, not a setup-failure (Many ratified Epic 2 retro Action #3).
- Added to `__all__`.

### AC-3.1.2 — `MCP.Start Server` keyword (PRD FR7)

**Given** the `MCPLifecycleManager` from Story 1b.1 + the `ServerSpec` dataclass,
**When** I call `${handle}=    MCP.Start Server    name=echo    transport=stdio    command=python    args=[-m, AgentEval.mcp.bundled.echo]` in a `.robot` test,
**Then** the keyword spawns the subprocess via `MCPLifecycleManager.acquire(test_id=...)` + returns a `MCPServerHandle` dataclass (name, transport, pid for stdio, internal handle for in_memory). The handle is consumable by `MCP.Connect To Server`. No spec-version validation happens here (that's `MCP.Connect To Server`'s job).

### AC-3.1.3 — `MCP.Connect To Server` keyword (PRD FR8) + spec version gate (FR46 + AC-MCP-OBSERVE-02)

**Given** a handle returned by `MCP.Start Server`,
**When** I call `${session}=    MCP.Connect To Server    ${handle}` in a `.robot` test,
**Then** the keyword:
1. Establishes the MCP client session via the transport-appropriate SDK constructor (`mcp.client.stdio.stdio_client` for stdio; in-process `ClientSession` for in_memory).
2. Calls `session.initialize()` which negotiates the MCP spec version.
3. Reads the negotiated version from the `InitializeResult.protocolVersion`.
4. If the version is OUTSIDE the supported range (`mcp>=1.0,<2.0` per NFR-COMPAT-04 + ADR-008), raises `UnsupportedMCPVersionError` with `server_version` + `supported_range` attrs populated.
5. Otherwise returns a `MCPSession` handle wrapping the SDK's `ClientSession`.

### AC-3.1.4 — `MCP.Stop Server` keyword

**Given** a handle returned by `MCP.Start Server`,
**When** I call `MCP.Stop Server    ${handle}` in a `.robot` test,
**Then** the keyword:
1. Closes the SDK `ClientSession` (if connected).
2. Calls `MCPLifecycleManager.release_test(test_id=...)` OR `release_suite(suite_id=...)` based on the cleanup mode (per Story 1a.6 baseline + ADR-009).
3. Verifies via `MCPLifecycleManager`'s post-kill liveness check that the subprocess is reaped (per Story 0.2 spike findings).

### AC-3.1.5 — Transport coverage: stdio + in_memory smoke-tested; streamable_http passthrough

**Given** the FR7 transport enum (`stdio | streamable_http | in_memory`),
**When** I exercise each via `MCP.Start Server` + `MCP.Connect To Server` in unit tests at `tests/unit/mcp/test_transport.py`,
**Then**:
- `stdio`: bundled echo subprocess starts, connects, initialize() succeeds, `Stop Server` reaps cleanly. Verified with a real subprocess.
- `in_memory`: in-process FastMCP-style echo runs in same Python process, connects via the MCP SDK's in-process transport, initialize() succeeds, `Stop Server` returns instantly.
- `streamable_http`: ONLY the transport-selection path is unit-tested (assert the SDK's `streamablehttp_client` is invoked); full HTTP round-trip is deferred per Phase-1 carve-out.

### AC-3.1.6 — `pabot --processes 8` integration test

**Given** the same lifecycle calls under `pabot --processes 8` with `mcp_per_test=True` mode (default per ADR-009),
**When** the test suite completes,
**Then** no MCP server processes leak. Verified by a `tests/integration/mcp/test_pabot_cleanup.py` that:
1. Captures `/proc` PID inventory before suite start.
2. Runs 8 parallel pabot processes each starting + stopping a bundled echo server.
3. Captures PID inventory after suite end.
4. Asserts diff in MCP-server PIDs == 0.

Cleanup overhead matches the Story 0.2 measurement table within ±10%.

### AC-3.1.7 — `MCPLibrary` extends with 3 keywords (DynamicCore exclusion preserved)

**And** `MCPLibrary` (Story 2.3) gains 3 new `@keyword`-decorated methods: `start_server`, `connect_to_server`, `stop_server`. `MCPLibrary` REMAINS excluded from `_SUB_LIBRARIES` per Story 2.2 + 2.3 + 2.4 collision-prevention norm. Users access via `Library AgentEval.mcp.library.MCPLibrary WITH NAME MCP`.

### AC-3.1.8 — Conventions tests pass on 3 new keywords + new error class

**And** all 5 Story 1b.6 conventions tests pass:
- `test_tier_annotation_present.py`: each new method has `_agenteval_tier = 1` via `@tier(1)`.
- `test_error_class_hierarchy.py`: `UnsupportedMCPVersionError` inherits `AgentEvalCompatError` (no leaf bypasses a sub-base).
- `test_no_bare_async_keywords.py`: no `async def` (MCP SDK calls are wrapped via `_kernel.run_async`).
- `test_keyword_name_idiom.py`: all 3 method names snake_case + verb-allowlist (`start` + `connect` + `stop` all already in allowlist).
- `test_docstring_libdoc_badge_alignment.py`: each docstring contains `[Tier 1 — Deterministic]`.

### AC-3.1.9 — Unit tests + RF integration

**And** unit tests cover:
- `tests/unit/mcp/test_transport.py` (~15 tests): each transport's selection logic + invocation; spec-version gate happy + error paths.
- `tests/unit/mcp/test_version_gate.py` (~10 tests): version-parse + range-check + edge cases (pre-release, post-release, malformed strings).
- `tests/unit/mcp/test_lifecycle_keywords.py` (~20 tests): `MCP.Start Server` + `MCP.Connect To Server` + `MCP.Stop Server` keyword behaviors against mock SDK + real bundled echo.
- `tests/unit/mcp/test_robot_integration.robot` extended with 3 new RF cases exercising stdio + in_memory.

Plus `tests/integration/mcp/test_pabot_cleanup.py` (AC-3.1.6).

### AC-3.1.10 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (39 src files → ~43 after Story 3.1: `mcp/transport.py`, `mcp/version_gate.py`, `mcp/bundled/__init__.py`, `mcp/bundled/echo.py`).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q` — was 494; +45 from Story 3.1 = 539+ pass.
- `uv run pytest tests/conformance -q` — 57+ passed + 9 skipped (was 10; AC-MCP-OBSERVE-02 conformance test un-skipped — see AC-3.1.11).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed (regression).
- `uv run robot tests/acceptance/smoke + 5 RF integration suites` — 13 → 16 passed (3 new MCP RF cases).
- `uv run pytest tests/integration/mcp -q` — new pabot cleanup integration test passes.

### AC-3.1.11 — AC-MCP-OBSERVE-02 conformance test un-skipped

**And** `tests/conformance/test_ac_mcp_observe_02_version_gate.py` un-skips (was `pytest.skip("Owning epic ... not yet shipped")` per Story 1b.5 skeleton). The test injects a mock MCP server negotiating spec version `2.5.0` + asserts `UnsupportedMCPVersionError` fires.

### AC-3.1.12 — Project norms applied

**And**:
- Code-review uses 4-reviewer cross-LLM pair per `feedback_review_methodology_norms` (16th consecutive use).
- Codex review prompt MUST direct behavioral probes per `feedback_codex_probe_fitness` (Epic 2 retro Action #5; ratified 2026-05-19): spawn a real MCP server, call `initialize`, assert protocolVersion AND assert UnsupportedMCPVersionError fires on injected spec-2.5.0 server. NOT pure introspection.
- Auditor review prompt MUST re-derive every citation from source per `feedback_citation_drift_first_class` (17+ STAR-catch streak ongoing).
- Honest framing: (1) `streamable_http` transport is Phase-1 passthrough only (full integration deferred); (2) `UnsupportedMCPVersionError` is the first IMPLEMENTED Compat-family runtime leaf — sets the pattern for future Compat leaves; (3) `MCPLibrary` remains excluded from DynamicCore composition per Story 2.2 norm.

## Tasks / Subtasks

- [ ] **Task 1: Add `UnsupportedMCPVersionError` class** to `src/AgentEval/errors.py` (inherits `AgentEvalCompatError` directly; structured `__init__`; `__str__` override per FR8). Extend `__all__`.
- [ ] **Task 2: Author `src/AgentEval/mcp/version_gate.py`** with `parse_version()` + `is_supported(version, range_str="mcp>=1.0,<2.0")` + raise-on-out-of-range helper.
- [ ] **Task 3: Author `src/AgentEval/mcp/transport.py`** — transport-selector with 3 enum values. `stdio` wraps MCP SDK `stdio_client`; `in_memory` wraps in-process `ClientSession`; `streamable_http` documented passthrough.
- [ ] **Task 4: Author `src/AgentEval/mcp/bundled/__init__.py` + `bundled/echo.py`** — minimal FastMCP-style echo server. Exposes `echo_back(text: str) -> str` tool. Used by Phase-1 integration tests.
- [ ] **Task 5: Author `src/AgentEval/mcp/lifecycle.py`** — `MCPServerHandle` + `MCPSession` dataclasses + the keyword-impl bodies for `start_server`, `connect_to_server`, `stop_server`. Wraps Story 1b.1 `MCPLifecycleManager.acquire / release_test / release_suite`.
- [ ] **Task 6: Extend `src/AgentEval/mcp/library.py:MCPLibrary`** with 3 new `@keyword`-decorated methods (`start_server`, `connect_to_server`, `stop_server`) each delegating to `lifecycle.py` + `@tier(1)`-annotated.
- [ ] **Task 7: Author `tests/unit/mcp/test_version_gate.py`** — ~10 tests for version parsing + range checks.
- [ ] **Task 8: Author `tests/unit/mcp/test_transport.py`** — ~15 tests for transport selection + happy/error paths per transport.
- [ ] **Task 9: Author `tests/unit/mcp/test_lifecycle_keywords.py`** — ~20 tests for the 3 keyword surfaces, mocking the SDK + exercising the bundled echo.
- [ ] **Task 10: Extend `tests/unit/mcp/test_robot_integration.robot`** with 3 new RF cases (stdio start+connect+stop; in_memory start+connect+stop; version-gate raises on spec 2.5.0).
- [ ] **Task 11: Author `tests/integration/mcp/test_pabot_cleanup.py`** — 8-process pabot integration test asserting PID-diff == 0 + cleanup overhead within ±10% of Story 0.2 baseline.
- [ ] **Task 12: Un-skip `tests/conformance/test_ac_mcp_observe_02_version_gate.py`** — populate the test with the mock-server-spec-2.5.0 scenario.
- [ ] **Task 13: Update `.github/workflows/ci.yml`** — add `pytest tests/integration/mcp -q` step (parallel to Story 2.4's static-inspection integration step).
- [ ] **Task 14: All-gates pass.**
- [ ] **Task 15: Apply project norms — 4-reviewer cross-LLM code review.**

## Dev Notes

### Architecture compliance

- PRD FR7 + FR8 + FR40 + FR46 + AC-MCP-OBSERVE-02 + NFR-COMPAT-04.
- ADR-008 (MCP spec range `mcp>=1.0,<2.0`).
- ADR-009 (`mcp_per_test=True | False | "suite"` 3-mode).
- ADR-011 (loud-refusal on spec version mismatch).
- Architecture L299/L354/L573 — `MCPLibrary` excluded from `_SUB_LIBRARIES` (Story 2.2 collision-prevention norm); standalone WITH-NAME pattern.
- ADR-014 — `UnsupportedMCPVersionError` is the 4th Compat-family leaf; inherits `AgentEvalCompatError` directly (Many ratified Epic 2 retro Action #3).
- Story 0.2 spike findings — `MCPLifecycleManager.acquire / release_test / release_suite / shutdown_all` semantics already-validated.
- Story 1b.1 — `MCPLifecycleManager` + `ServerSpec` + scope translation (`_resolve_scope`) available.
- Inherits Stories 2.1-2.4 patterns: deviation-tracker docstrings, behavioral-probe review prompts, JSON-Pointer (N/A here), `_kernel.run_async` for SDK calls (avoid bare `async def @keyword`).

### Phase-1 limitations explicitly documented

- `streamable_http` is Phase-1 passthrough only (full HTTP round-trip deferred to Phase-1.5 OR Epic 3 Story 3.2).
- `UnsupportedMCPVersionError` is RUNTIME error, NOT setup-failure (no FR59 5-line layout).
- Cleanup overhead ±10% of Story 0.2 baseline; broader profiling at Epic 5+ when telemetry stack matures.

## Dev Agent Record

### Context Reference / Agent Model Used / Debug Log References / Completion Notes List

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (15th use) caught 5 drifts: D-A `MCP.Connect` → `MCP.Connect To Server`; D-B "Tier 2 — LLM-Deterministic" badge non-existent → Tier 1; D-C `UnsupportedMCPVersionError` inherits `AgentEvalCompatError` directly per Epic 2 retro Action #3; D-D `mcp_per_test="test"` invalid → True/False/"suite"; D-E CI step verification for new tests/unit/mcp/* modules. Phase-1 scope clarified: stdio + in_memory full; streamable_http passthrough only. | Bob |
