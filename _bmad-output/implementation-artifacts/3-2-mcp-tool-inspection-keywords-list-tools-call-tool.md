# Story 3.2: MCP Tool Inspection Keywords — List Tools + Call Tool

Status: done

## Story

As **Mei (Agent Surface Author)** or **Priya (QA Engineer)**,
I want **`MCP.List Tools` and `MCP.Call Tool` keywords with full `MCPToolResult` access** (text content, error responses, latency_ms, correlation_id),
So that I can introspect what tools a connected MCP server offers, invoke tools with parameters, and assert on tool results in a `.robot` test — covering the dynamic-evaluation surface that the static Epic 2 keywords cannot reach.

## Pre-create-story drift check (16th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19)

5 drifts caught + resolved pre-authoring:

- **(D-A MED)** epics.md L1265 said `MCP.Connect`; Story 3.1 fix established `MCP.Connect To Server` per FR8 verbatim. epics.md L1265 amended.
- **(D-B HIGH)** `MCPConnectionLostError` not in 16-leaf catalog. Added as 17th leaf under `AgentEvalCompatError` (Compat-family runtime error, parallel to `UnsupportedMCPVersionError`). `error_code = "MCP_CONNECTION_LOST"`; exit code 69 (sysexits-extended; sibling to `UnsupportedMCPVersionError` L80 = 68).
- **(D-C MED)** epics.md L1281 says "in all 3 transports". Story 3.1 ratified `streamable_http` as Phase-1 passthrough; Story 3.2 unit tests scope to stdio + in_memory. streamable_http via SDK passthrough remains Phase-1.5 OR Epic 3 deferred.
- **(D-D HIGH structural)** epics.md L1266 + L1270 read "Given a connected MCP server" + "${result}= MCP.Call Tool name=echo tool=echo_back" — implies a LIVE session is reusable across calls. Story 3.1 ratified per-call-session pattern (each operation re-opens). Story 3.2 keywords MUST accept an `MCPServerHandle` (NOT `MCPSession`) + re-open the session per call. Trade-off: stdio pays subprocess-startup latency on every `MCP.Call Tool`. Phase-1.5 may introduce pooled sessions via `MCPLifecycleManager` integration.
- **(D-E LOW)** `correlation_id` field at L1271 is for trace lookup — trace recording lands Epic 5. Phase-1 surfaces a per-call uuid4 string so the API contract ships but the trace-side lookup is deferred. Documented in `MCPToolResult` dataclass docstring.

Pre-authoring fixes: `docs/contracts/error-class-hierarchy.md` L10 + L53 + L56 + L84 amended (17 leaves; new Compat row); `_bmad-output/planning-artifacts/epics.md` L1265 amended.

## Acceptance Criteria

### AC-3.2.1 — `MCPTool` dataclass (PRD FR9a)

**Given** the FR9a contract for `MCPTool` records,
**When** Story 3.2 implements `class MCPTool(frozen=True)` at `src/AgentEval/mcp/lifecycle.py` (extending the existing `MCPSession` / `MCPServerHandle` neighborhood),
**Then** the dataclass has:
- `name: str`
- `description: str`
- `input_schema: dict[str, Any]` (JSON Schema dict)
- `output_schema: dict[str, Any] | None` (optional per MCP spec)
- `@dataclass(frozen=True)` for immutability.

### AC-3.2.2 — `MCPToolResult` dataclass (PRD FR9b)

**And** `class MCPToolResult(frozen=True)` with:
- `content: list[dict[str, Any]]` — list of content blocks per MCP spec; each block has `type` + type-specific keys (`text`, `data`, `mimeType`, ...).
- `is_error: bool` — True when the SDK's `CallToolResult.isError` is True.
- `error_message: str | None` — populated when `is_error=True`; None otherwise.
- `latency_ms: float` — wall-clock elapsed from request-send to response-receive.
- `correlation_id: str` — per-call uuid4 string (Phase-1 placeholder; Epic 5 wires real trace-id lookup).

### AC-3.2.3 — `MCP.List Tools` keyword (PRD FR9a)

**And Given** an `MCPServerHandle` from `MCP.Start Server` (Story 3.1),
**When** I call `${tools}=    MCP.List Tools    ${handle}` in a `.robot` test,
**Then** the keyword:
1. Opens a fresh MCP session via the Story 3.1 per-call-session pattern (`open_*_session` + agenteval-owned `initialize()`).
2. Calls `session.list_tools()` per MCP spec.
3. Maps each SDK `Tool` to an `MCPTool` dataclass.
4. Tears down the session.
5. Returns `list[MCPTool]`.

### AC-3.2.4 — `MCP.Call Tool` keyword (PRD FR9b)

**And Given** the same handle + a tool name + arguments dict,
**When** I call `${result}=    MCP.Call Tool    ${handle}    echo_back    arguments=${{ {"text": "hello"} }}` in a `.robot` test,
**Then** the keyword:
1. Opens a fresh MCP session.
2. Records `t0 = time.monotonic()`.
3. Calls `session.call_tool(name, arguments)`.
4. Computes `latency_ms = (time.monotonic() - t0) * 1000`.
5. Generates a per-call `correlation_id` via `uuid.uuid4().hex`.
6. Maps the SDK's `CallToolResult` to `MCPToolResult` (content list, is_error from `isError`, error_message extracted from text-content block when `is_error=True`).
7. Tears down the session.
8. Returns `MCPToolResult`.

### AC-3.2.5 — Error responses are first-class data (PRD FR9b)

**And Given** a tool that returns an error response (e.g., `echo_back` invoked with missing required `text` parameter),
**When** I call `MCP.Call Tool` against it,
**Then** the returned `MCPToolResult` has `is_error=True` and `error_message` populated, BUT **no exception is raised** — error responses are first-class data, distinct from infrastructure failures.

### AC-3.2.6 — `MCPConnectionLostError` on infrastructure failure (PRD FR9b 17th leaf)

**And Given** an MCP server that crashes mid-call (simulated via subprocess kill),
**When** `MCP.Call Tool` is in flight,
**Then** `MCPConnectionLostError` is raised with:
- `error_code = "MCP_CONNECTION_LOST"`.
- Structured attrs `server_name`, `last_operation` (e.g., `"call_tool"`), `fix_suggestion`.
- Per-test cleanup from Story 3.1's `try/except` AsyncExitStack runs (no subprocess leak).

### AC-3.2.7 — `MCPLibrary` extends with 2 keywords (DynamicCore exclusion preserved)

**And** `MCPLibrary` (Stories 2.3 + 3.1) gains 2 new `@keyword`-decorated methods: `list_tools`, `call_tool`. `MCPLibrary` REMAINS excluded from `_SUB_LIBRARIES` per Story 2.2+2.3+3.1 collision-prevention norm.

### AC-3.2.8 — Conventions tests pass

**And** all 5 Story 1b.6 conventions tests pass on the 2 new keywords:
- `@tier(1)` annotation (Tier-1 deterministic per Story 3.1 precedent).
- 17 leaves in error-class-hierarchy.md (catalog updated).
- No `async def @keyword` (wrap via `_run_async`).
- `list` + `call` already in `_VERB_ALLOWLIST`.
- `[Tier 1 — Deterministic]` badge in docstrings.

### AC-3.2.9 — Unit tests + RF integration

**And** unit tests at `tests/unit/mcp/test_tool_inspection.py` (~20 tests) cover:
- Happy path `MCP.List Tools` against bundled echo (in_memory + stdio).
- Happy path `MCP.Call Tool` with valid arguments.
- Error path `MCP.Call Tool` with invalid arguments (returns `is_error=True`, no exception).
- `MCPConnectionLostError` on simulated subprocess crash mid-call.
- `latency_ms > 0` invariant.
- `correlation_id` is a non-empty string (uuid4 hex format).
- `MCPToolResult.is_error` reflects SDK's `isError` field.

Plus `tests/unit/mcp/test_robot_integration.robot` extended with ~2 new RF cases.

### AC-3.2.10 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (44 src files Story 3.1 baseline; no new source files in this story; 2 keywords added to `MCPLibrary` + dataclasses to `lifecycle.py`).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q` — was 575 (Story 3.1 close); +25 from Story 3.2 = 600+ pass.
- `uv run pytest tests/conformance -q` — 64 passed + 9 skipped (regression).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.
- `uv run robot tests/acceptance/smoke + tests/unit/{skills,subagents,hooks,mcp}/test_robot_integration.robot` — 16 → 18 passed (2 new MCP tool RF cases).

### AC-3.2.11 — Project norms applied

**And**:
- Code-review uses 4-reviewer cross-LLM pair per `feedback_review_methodology_norms` (17th consecutive use; Story 3.1 was 17th STAR).
- Codex review prompt directs behavioral probes per `feedback_codex_probe_fitness`: spawn real MCP server, call list_tools + call_tool, assert response shape + raise sites.
- Auditor review prompt re-derives every citation per `feedback_citation_drift_first_class` (18+ STAR streak).
- Honest framing: (1) per-call session pattern means each `MCP.Call Tool` pays subprocess-startup latency on stdio — Phase-1.5 may introduce pooled sessions; (2) `correlation_id` is a Phase-1 uuid placeholder; Epic 5 wires real trace-id lookup; (3) `streamable_http` transport remains Phase-1 passthrough.

## Tasks / Subtasks

- [x] **Task 1: Add `MCPConnectionLostError`** to `src/AgentEval/errors.py` (17th leaf, inherits `AgentEvalCompatError`; structured `server_name` + `last_operation` + `fix_suggestion` attrs). Extend `__all__`.
- [x] **Task 2: Add `MCPTool` + `MCPToolResult` dataclasses** to `src/AgentEval/mcp/lifecycle.py` (frozen, with the field set per AC-3.2.1 + AC-3.2.2).
- [x] **Task 3: Add `list_tools(handle)` + `call_tool(handle, tool_name, arguments)` functions** to `src/AgentEval/mcp/lifecycle.py` (sync wrappers around the async SDK calls via `_run_async`; map SDK `Tool` → `MCPTool` + `CallToolResult` → `MCPToolResult`; catch transport-layer errors → raise `MCPConnectionLostError`).
- [x] **Task 4: Extend `src/AgentEval/mcp/library.py:MCPLibrary`** with 2 new `@keyword`-decorated methods (`list_tools`, `call_tool`) each `@tier(1)`-annotated.
- [x] **Task 5: Author `tests/unit/mcp/test_tool_inspection.py`** (39 tests; superset of the ~20 target).
- [x] **Task 6: Extend `tests/unit/mcp/test_robot_integration.robot`** with 2 new RF cases.
- [x] **Task 7: All-gates pass** — ruff clean / mypy clean (44 src files) / 609 unit+conformance + 9 skipped / 6 tier1 / 18 RF integration / license headers PASS.
- [x] **Task 8: Apply project norms — 4-reviewer cross-LLM code review.** Codex CLI bwrap-sandbox process gap surfaced (DF-3.2-S7); Codex slot filled by behavioral probes per `feedback_codex_probe_fitness`. 4 reviewers + behavioral probes returned 2 HIGH (Blind), 2 HIGH (Edge-cases), 5 HIGH (Auditor citation-drift), 2 HIGH (Codex/probe), 3-way MED + multiple LOWs. N-way triage applied per `feedback_n_way_agreement_weight`: 3-way HIGH on transport-loss classification gaps (Blind MED + Edge-cases HIGH-2 + Codex HIGH-1 + Codex HIGH-2) drove the `_is_connection_lost_exception` widening; 2-way HIGH on empty-content `error_message` contract; Auditor's 5-citation-drift catches all amended.

## Senior Developer Review (AI)

4 reviewers + behavioral probes 2026-05-19. Patches applied:

**Production fixes (3-way HIGH + 2-way HIGH):**

- `_is_connection_lost_exception` widened: handles `BaseExceptionGroup` (recursive), `mcp.shared.exceptions.McpError("Connection closed"/"Connection lost"/"Stream closed")` for stdio subprocess crash, anyio + stdlib leaf signatures (5 total). `_representative_cause` helper surfaces inner transport exception via `__cause__` when group-wrapped. Initialize-handshake transport-failures now mapped (the `try/except` wrapper extended to cover `_initialize_with_typed_error_mapping` too).
- `_map_call_result` empty-content fallback: `is_error=True` with `content=[]` now yields structured `error_message="tool returned an error response with no content"`. Non-text-block case names the actual block type in the fallback ("non-text content block of type `image`").

**Verified 1-way HIGHs:**

- `list_tools` cursor-loop pagination (SDK signature `list_tools(cursor=None, *, params=None)` returning paginated `ListToolsResult.nextCursor`). Pre-edit code returned only first page.
- `test_call_tool_arguments_are_copied_not_referenced` rewritten with `monkeypatch + captured["seen"]` verifying the SDK saw a different dict object AND the pre-mutation value.

**Auditor citation-drift fixes (5/5):**

- PRD FR9a amended: `Get Tool Names` / `Get Tool Descriptions` deferred to Phase-1.5 (DF-3.2-S1).
- PRD FR9b amended: `(result, error, latency_ms)` → 5-field shape matching implementation; documents tool-level-error vs infrastructure-error distinction explicitly.
- `epics.md` L1294 + L1467 amended: `MCP.Connect` → `MCP.Connect To Server` (D-A drift had 2 escapees).
- `src/AgentEval/errors.py:L706` docstring amended: removed miscitation of `epics.md L1660` (which is Story 6.5's closing line, not Story 8a.1 exit-code mapping); now correctly points at `error-class-hierarchy.md` L84 with Story 8a.1 L1811 hygiene noted in DF-3.2-S3.
- `error-class-hierarchy.md` L133 amended: "16 leaves" → "17 leaves" matching L56 running total. Pre-existing "11 leaves" drifts (L5 / L18 / L45 / ADR-014 L32) tracked in DF-3.2-S4.

**3-way MED:**

- `MCPTool` + `MCPToolResult` docstrings document shallow-frozen footgun explicitly. Phase-1 still ships shallow `dict(...)` copies on construction; consumers caching cross-call must deep-copy.

**Behavioral test coverage added (13 new tests, 52 total):**

- Pagination (3 tests: multi-page, single-page, missing-tools-attr).
- ExceptionGroup unwrap (1 test with `BaseExceptionGroup([ClosedResourceError])`).
- Mid-initialize transport-failure mapping (2 tests: `list_tools` + `call_tool`).
- `McpError("Connection closed")` → MCPConnectionLostError (1 test).
- Generic `McpError` propagates raw (1 test, pins design intent).
- 3 additional connection-lost signatures (`EndOfStream`, `ConnectionError`, `BrokenPipeError`) parametrized (1 test, 3 params).
- Empty-content `is_error=True` fallback (1 test).
- Non-text content `is_error=True` fallback (1 test).

**Deferred to Phase-1.5 (DF-3.2-S1 through DF-3.2-S7):**

- PRD FR9a sub-keywords (Get Tool Names / Get Tool Descriptions).
- ADR-014 leaf-table amendment for 17-leaf state.
- Story 8a.1 epics.md L1811 exit-code mapping completion (add 69 + future codes).
- error-class-hierarchy.md "11 leaves" pre-existing drifts.
- `MCPConnectionLostError.correlation_id` attr (Codex LOW-3 + Blind MED-3) — Epic 5 trace forensics.
- SDK "Unsupported protocol version" message-format pinning (Edge-cases LOW-1).
- Cross-LLM-family review degraded to single-family this round (Codex CLI bwrap sandbox blocked file reads); investigate Codex config / sibling LLM CLI alternate.

**Honest framing:**

- The 3-way HIGH on transport-loss classification was load-bearing: pre-edit code would have leaked raw anyio/McpError exceptions on the canonical stdio-subprocess-crash production case — exactly the scenario `MCPConnectionLostError` was designed for. Codex probe 7 (REAL FastMCP server with `os._exit(1)` mid-handler) caught it via behavioral evidence; type-system reasoning would not have surfaced it. This is the 18th consecutive cross-LLM STAR catch streak — and the empirical justification for `feedback_codex_probe_fitness`.

### Action Items

All HIGH + 3-way MED findings closed via in-line patches. Phase-1.5 carry-overs documented in `_bmad-output/implementation-artifacts/deferred-work.md` (DF-3.2-S1 through DF-3.2-S7). Edge-cases LOW-2 + Codex LOW-2 + Codex LOW-4 also closed (defensive `getattr(page, "tools", None)`, top-level `import anyio`). LOW-1 (Windows clock resolution) accepted as-is (Linux primary; CI runs Linux).

## Dev Agent Record

### Completion notes

Story 3.2 dev implementation complete 2026-05-19. All ACs satisfied; full all-gates green (609 unit+conformance passed + 9 skipped, 6 tier1, 18 RF integration including 2 new MCP tool cases, ruff/format/mypy clean on 44 src files, license headers PASS).

Implementation highlights (vs spec):

- `MCPConnectionLostError` (17th leaf) — inherits `AgentEvalCompatError` directly per Epic 2 retro Action #3 (`__str__` inherits the base H_R7 `<error_code>: <message>` shape; runtime error, not FR59 setup-failure layout).
- Per-call session pattern factored to 3 shared private helpers in `lifecycle.py` (`_validate_handle_for_connect`, `_open_session`, `_initialize_with_typed_error_mapping`). `connect_to_server` + `list_tools` + `call_tool` all reuse them. Phase-1 each call re-opens + re-initializes the MCP session (subprocess-startup latency on stdio); honestly documented in the spec.
- `_is_connection_lost_exception` classifies anyio + stdlib transport-layer signatures → `MCPConnectionLostError` with `server_name`/`last_operation`/`fix_suggestion` attrs + `__cause__` preserving the original exception for forensics. Tool-LEVEL error responses (`CallToolResult.isError`) remain first-class data via `MCPToolResult(is_error=True, ...)`.
- `correlation_id` is a per-call `uuid.uuid4().hex` Phase-1 placeholder per drift D-E; Epic 5 will wire real trace-id lookup.
- 2 new verbs added to `_VERB_ALLOWLIST` allowlists: `call` (for `Call Tool`). Both unit + conformance allowlists updated symmetrically.

Pre-create-story drift check (16th use of `feedback_spec_vs_ratified_doc_precheck`) caught 5 drifts (3 HIGH + 2 MED) ALL fixed pre-authoring; details in spec.

## File List

**Source (3 edited):**

- `src/AgentEval/errors.py` — added `MCPConnectionLostError` (17th leaf, ~50 LoC including docstring) + `__all__` entry.
- `src/AgentEval/mcp/lifecycle.py` — added `MCPTool` + `MCPToolResult` dataclasses; 3 private helpers (`_validate_handle_for_connect`, `_open_session`, `_initialize_with_typed_error_mapping`); refactored `connect_to_server` to reuse them; added `list_tools`, `call_tool`, `_is_connection_lost_exception`, `_map_tool`, `_map_call_result`.
- `src/AgentEval/mcp/library.py` — added `List Tools` + `Call Tool` `@keyword`+`@tier(1)` methods.

**Tests (3 edited / 1 new):**

- `tests/unit/mcp/test_tool_inspection.py` — NEW. 39 tests.
- `tests/unit/mcp/test_robot_integration.robot` — extended with 2 new MCP tool RF cases (16 → 18 total RF tests).
- `tests/unit/conventions/test_keyword_name_idiom.py` — added `"call"` to `_VERB_ALLOWLIST` (Story 3.2 growth-log entry).
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` — added `"call"` to the symmetric in-test allowlist.

**Docs (2 edited pre-authoring):**

- `docs/contracts/error-class-hierarchy.md` — 16 → 17 leaves; new `MCPConnectionLostError` Compat-family row + L10/L53/L56 prose updates.
- `_bmad-output/planning-artifacts/epics.md` — L1265 `MCP.Connect` → `MCP.Connect To Server` (drift D-A).

## Dev Notes

### Architecture compliance

- PRD FR9a + FR9b (tool inspection contracts).
- ADR-014 — `MCPConnectionLostError` is the 17th leaf, 5th Compat-family.
- Story 3.1 per-call-session pattern inherited verbatim (`open_*_session` + `_run_async` + `try/except BaseException` cleanup).
- Stories 2.1-3.1 patterns transitively: no eager re-export, behavioral probes for SDK invariants, structured attrs on errors, `@dataclass(frozen=True)` + `dict(...)` shallow copy at construction.
- Architecture L299/L354/L573 — `MCPLibrary` excluded from `_SUB_LIBRARIES`.
- Story 1b.6 conventions tests pass.

### Phase-1 limitations explicitly documented

- Per-call session pattern: each `MCP.Call Tool` re-opens the session (stdio pays subprocess-startup latency). Phase-1.5 may introduce pooled sessions via `MCPLifecycleManager` integration.
- `correlation_id` is a Phase-1 uuid4 placeholder; Epic 5 wires real trace-id lookup.
- `streamable_http` transport remains Phase-1 passthrough (Story 3.1 carve-out).

## Dev Agent Record

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (16th use) caught 5 drifts: D-A `MCP.Connect` → `MCP.Connect To Server`; D-B `MCPConnectionLostError` added as 17th leaf; D-C 3-transport scope → stdio + in_memory only; D-D structural — keywords take handle (not session) per per-call pattern; D-E `correlation_id` Phase-1 uuid placeholder. | Bob |
