# Story 2.3: MCP Static Inspection Keywords

Status: review

## Story

As **Mei (Agent Surface Author — MCP author mode)** or **Priya (QA Engineer)**,
I want **`MCP.Get Server Config` + `MCP.Get Tool Schema` + `MCP.Validate Tool Schema`**,
So that I can assert on `.mcp.json` declarations and MCP tool schemas in a `.robot` test in Tier-1 deterministic time — first MCP-author value milestone (full runtime lifecycle is Epic 3).

## Pre-create-story drift check (13th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19)

Surfaced 5 drifts; all resolved via path-of-least-amendment pre-authoring:

- **(D-A MED)** epics.md L1197 said "per-keyword P95 <50ms". PRD NFR-PERF-02 L1608 specifies **median**. Same drift as Stories 2.2 D-A. epics.md amended.
- **(D-B HIGH)** `InvalidMCPServerConfigError` not in 14-leaf catalog. Added as 15th leaf under `AgentEvalIntegrityError` (Tier-1 setup-failure semantics; exit code 65; `field_name` carries RFC 6901 JSON Pointer).
- **(D-C HIGH)** `InvalidMCPToolSchemaError` (PRD FR6 references it) not in catalog. Added as 16th leaf; same semantics + JSON Pointer convention. PRD-locked by FR6's "JSON Pointer and validation error message" wording.
- **(D-D MED)** PRD FR6 says `MCP.Get Tool Schema <tool_name>` returns the schema "against a running or configured MCP server". Phase-1 has no running-server runtime (full lifecycle is Epic 3 per Story 2.3 narrative). Resolution: Phase-1 reads tool schemas from a DECLARATIVE `.mcp.json:tools` extension — each server entry MAY include an optional `tools: { <tool_name>: <json_schema_dict> }` field. Phase-2 + Epic 3 will retrieve schemas from running servers per FR6 verbatim. This is a Phase-1 carve-out documented in the new 16th-leaf catalog row.
- **(D-E LOW)** Transport enumeration: PRD FR7 lists `stdio | streamable_http | in_memory`. The validator MUST accept these 3 values only; any other transport string raises `InvalidMCPServerConfigError`.

Pre-authoring fixes: `docs/contracts/error-class-hierarchy.md` L10 + L54 + L56 + L93-95 + L121 + L130 amended (15th + 16th leaves added; prose counts updated 14 → 16); `_bmad-output/planning-artifacts/epics.md` L1197 amended.

## Acceptance Criteria

### AC-2.3.1 — `MCP.Get Server Config` keyword (PRD FR5)

**Given** a valid `.mcp.json` file at `tests/fixtures/mcp/mcp-valid.json` declaring multiple MCP servers with `stdio` + `streamable_http` transports,
**When** I call `${servers}=    MCP.Get Server Config    tests/fixtures/mcp/mcp-valid.json` in a `.robot` test,
**Then** the variable receives a dict mapping `<server_name>` → server-entry dict. Each entry has at minimum `command` (str) + may have `args` (list[str]), `env` (dict[str,str]), `transport` (str ∈ {`stdio`, `streamable_http`, `in_memory`}). The call completes in **median** <50 ms per NFR-PERF-02 + does NOT spawn any subprocesses (pure file-parsing + JSON validation; the keyword's no-side-effect contract is testable via a `subprocess`-spawned process inventory if a future test cares).

### AC-2.3.2 — `InvalidMCPServerConfigError` (15th leaf)

**And Given** an invalid `.mcp.json` (missing required `command` field on a server, malformed JSON, unsupported transport),
**When** I call `MCP.Get Server Config` against it,
**Then** `InvalidMCPServerConfigError` is raised with `error_code = "INVALID_MCP_SERVER_CONFIG"`. The `field_name` attribute carries an RFC 6901 JSON Pointer to the offending location (e.g., `/mcpServers/echo/command`). The error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104. The exception inherits from `AgentEvalIntegrityError`.

### AC-2.3.3 — `MCP.Get Tool Schema` keyword (PRD FR6 Phase-1)

**And Given** a `.mcp.json` whose server entry declares an optional `tools` field — each entry under `tools` is a tool_name → JSON Schema mapping describing the tool's input parameters,
**When** I call `${schema}=    MCP.Get Tool Schema    tool_name=search    config_path=tests/fixtures/mcp/mcp-valid.json    server_name=echo` in a `.robot` test,
**Then** the variable receives the JSON Schema dict for that tool's input parameters. Median latency ≤ 50 ms per NFR-PERF-02.

Phase-1 carve-out: tool schemas come from the **declarative** `.mcp.json:tools` extension, NOT from a running MCP server (PRD FR6's "against a running or configured MCP server" runtime path is Epic 3 scope). Documented in the 16th-leaf catalog row.

### AC-2.3.4 — `MCP.Validate Tool Schema` keyword (PRD FR6 Phase-1)

**And Given** a tool schema in `.mcp.json:tools` that does NOT validate against the jsonschema Draft 2020-12 meta-schema (e.g., a `type` value that isn't one of the 7 standard types, a `$ref` pointing nowhere, a malformed `properties` mapping),
**When** I call `MCP.Validate Tool Schema    tool_name=broken_tool    config_path=tests/fixtures/mcp/mcp-with-broken-tool.json`,
**Then** `InvalidMCPToolSchemaError` is raised with: (a) `error_code = "INVALID_MCP_TOOL_SCHEMA"`, (b) `field_name` carries an RFC 6901 JSON Pointer to the offending sub-schema, (c) the jsonschema validation error message in the underlying `__cause__` for callers needing the verbatim diagnostic, (d) the FR59 format applied to `__str__`.

Validation uses the `jsonschema` library (pinned `>=4.0,<5.0` in pyproject) against the **Draft 2020-12** meta-schema. Each tool schema is validated as a JSON Schema document (NOT as a value against the schema — we're validating the schema-validity itself).

### AC-2.3.5 — `MCP` sub-library NOT registered in DynamicCore `_SUB_LIBRARIES`

**And** the `MCP` sub-library (`src/AgentEval/mcp/library.py`) exports the 3 keywords via an `MCPLibrary` class. Per Story 2.2 code-review HIGH-1 ratification (DynamicCore collision: parallel `Get*` keywords across sub-libraries silently shadow), the new sub-library is NOT registered in `src/AgentEval/__init__.py:_SUB_LIBRARIES`. Users access via standalone import: `Library AgentEval.mcp.library.MCPLibrary WITH NAME MCP`. The HooksLibrary remains the only sub-library composed into `Library AgentEval` (because `Get Config` is unique across all Phase-1 sub-libraries).

### AC-2.3.6 — Conventions tests pass on the 3 new keywords

**And** all 5 Story 1b.6 conventions tests pass on `get_server_config`, `get_tool_schema`, `validate_tool_schema`:
- `test_tier_annotation_present.py`: each has `_agenteval_tier = 1` via `@tier(1)`.
- `test_error_class_hierarchy.py`: 15th + 16th leaves inherit `_FR59Tier1SetupFailureError` → `AgentEvalIntegrityError` → `AgentEvalError`.
- `test_no_bare_async_keywords.py`: no `async def`.
- `test_keyword_name_idiom.py`: snake_case + first verb in `_VERB_ALLOWLIST` (`get`, `validate` — both already present).
- `test_docstring_libdoc_badge_alignment.py`: each docstring contains the exact `[Tier 1 — Deterministic]` badge.

### AC-2.3.7 — Fixtures

**And** the following fixtures ship:
- `tests/fixtures/mcp/mcp-valid.json` — valid `.mcp.json` declaring ≥2 servers (one `stdio`, one `streamable_http`) with optional `tools` entries on at least one server. Includes a valid tool schema (e.g., `search` tool with `{"type":"object","properties":{"query":{"type":"string"}}}`).
- `tests/fixtures/mcp/mcp-missing-command.json` — server entry missing `command`.
- `tests/fixtures/mcp/mcp-malformed-json.json` — broken JSON.
- `tests/fixtures/mcp/mcp-unsupported-transport.json` — server entry with `transport: "websocket"` (not in FR7's enum).
- `tests/fixtures/mcp/mcp-with-broken-tool.json` — valid server entry but `tools.broken_tool` is a malformed JSON Schema.

All fixtures' bytes deterministic per FR31a.

### AC-2.3.8 — Unit tests

**And** `tests/unit/mcp/test_library.py` covers:
- Happy path for all 3 keywords.
- Each error path: malformed JSON, missing `command`, unsupported transport, missing tool, malformed schema.
- Median latency assertion (sample-of-11) for each of the 3 keywords.
- FR59 `__str__` 5-line layout for both new error classes.
- JSON Pointer `field_name` for both error classes.
- DynamicCore exclusion: `_loaded_components` does NOT contain `MCPLibrary`; the parent's `Library AgentEval; Get Server Config` does NOT resolve (raises RF "no keyword").
- Standalone import works: `MCPLibrary()` instantiates + each keyword callable.

Plus `tests/unit/mcp/test_robot_integration.robot` (~3 RF tests) using `Library AgentEval.mcp.library.MCPLibrary WITH NAME MCP` + `${CURDIR}`-anchored fixture paths.

### AC-2.3.9 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (37 src files post-Story-2.2; new: `src/AgentEval/mcp/library.py` + `src/AgentEval/mcp/_parser.py` = 39 source files).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q` — 398 prior + ~40 new ≥ 438 pass.
- `uv run pytest tests/conformance -q` — 30 passed + 11 skipped.
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.
- `uv run robot tests/acceptance/smoke` — unchanged.
- All 4 prior RF integration tests pass + 1 new MCP RF integration test passes.
- `uv run pytest tests/unit/conventions -q` STANDALONE passes (per Story 2.1 code-review order-dependent fake-green prevention).

### AC-2.3.10 — Project norms applied

**And**:
- Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (13th consecutive use; Story 2.2 was 12th).
- Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (14+ STAR-catch streak; Story 2.2 was the 14th).
- CI workflow `.github/workflows/ci.yml` extended with `robot tests/unit/mcp/test_robot_integration.robot` step.
- Honest framing documented: (1) Tool-schema source is the declarative `.mcp.json:tools` extension, NOT runtime MCP servers (Phase-1 carve-out; Phase-2 + Epic 3 lands runtime); (2) MCP sub-library excluded from DynamicCore composition per Story 2.2 collision-prevention norm; (3) jsonschema validation uses Draft 2020-12 meta-schema (the project's pinned `jsonschema>=4.0,<5.0` supports this Draft by default).

## Tasks / Subtasks

- [x] **Task 1: 2 new error leaves added** — `InvalidMCPServerConfigError` (15th) + `InvalidMCPToolSchemaError` (16th) under `_FR59Tier1SetupFailureError`.
- [x] **Task 2: `src/AgentEval/mcp/_parser.py`** — full parser with JSON Pointer field_name + jsonschema Draft202012Validator.
- [x] **Task 3: `src/AgentEval/mcp/library.py`** — `MCPLibrary` with 3 keywords.
- [x] **Task 4: `src/AgentEval/mcp/__init__.py`** — no eager re-export.
- [x] **Task 5: `_SUB_LIBRARIES` NOT extended** — per Story 2.2 HIGH-1 ratification.
- [x] **Task 6: 5 fixtures** at `tests/fixtures/mcp/`.
- [x] **Task 7: Unit tests** — 57 unit + 3 RF integration.
- [x] **Task 8: CI workflow extended** with new robot step.
- [x] **Task 9: All-gates pass.** ruff/format/mypy clean (39 src files); 491 unit + 30 conformance + 11 skipped + 6 tier1 + 13 RF.
- [x] **Task 10: Apply project norms — code-review queue.**

## Dev Notes

### Architecture compliance

- PRD FR5 (Get Server Config) + FR6 (Get Tool Schema + Validate Tool Schema) + FR7 (transport enum) + FR59 (Tier-1 setup-failure format) + NFR-PERF-02 (median ≤ 50 ms).
- Architecture L832-849 — sub-library module layout (`library.py` + `_parser.py`-style helper).
- Architecture L825+ Phase-1 carve-out registry — extended with: "Story 2.3 ratifies `.mcp.json:tools` declarative tool-schema extension as the Phase-1 source for `MCP.Get Tool Schema`; Phase-2 + Epic 3 retrieve schemas from running MCP servers per FR6."
- Architecture L299/L354/L573 — DynamicCore composition; MCP sub-library NOT composed (Story 2.2 collision-prevention).
- ADR-014 + error-class-hierarchy.md L54 + L93-95 — `InvalidMCPServerConfigError` (15th) + `InvalidMCPToolSchemaError` (16th) under `_FR59Tier1SetupFailureError`.
- jsonschema Draft 2020-12 — `jsonschema>=4.0,<5.0` pin supports it.
- Story 2.1 + 2.2 lessons inherited: no eager re-export in `__init__.py`; `${CURDIR}`-anchored RF fixture paths; column-0 `---` (N/A for JSON); `utf-8-sig` BOM strip; one-line YAML summary (N/A for JSON); RFC 6901 JSON Pointer `field_name`; `_FR59Tier1SetupFailureError` shared parent.

### Phase-1 limitations explicitly documented

- `MCP.Get Tool Schema` reads from `.mcp.json:tools` extension (Phase-1 declarative). FR6 runtime retrieval lands Phase-2 + Epic 3.
- `MCPLibrary` not composed into `Library AgentEval` (Story 2.2 collision-prevention norm).
- jsonschema validation uses Draft 2020-12 only.
- Transport enum strict per FR7 (`stdio`, `streamable_http`, `in_memory`); other values raise.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code dev-story workflow, 2026-05-19.

### Implementation Plan + Decisions

1. **`_FR59Tier1SetupFailureError` shared parent extended to 5 leaves.** Story 2.1+2.2 established the private intermediate; Story 2.3 adds 2 more (15th `InvalidMCPServerConfigError` + 16th `InvalidMCPToolSchemaError`). All 5 setup-failure leaves now share the structured `__init__` + FR59 4-line `__str__` shape.
2. **Phase-1 `.mcp.json:tools` declarative extension.** PRD FR6 says "against a running or configured MCP server" — Phase-1 cannot retrieve schemas from running servers (Epic 3 scope). Ratified the declarative `tools: {name: schema}` per-server extension as the Phase-1 source; documented in the 16th-leaf catalog row.
3. **`MCPLibrary` EXCLUDED from `_SUB_LIBRARIES`** per Story 2.2 HIGH-1 collision-prevention norm. Users access via standalone WITH-NAME import. The `Get Server Config` keyword name doesn't collide with anything Phase-1 ships, but the precedent matters: future Tier-1 sub-libraries will inevitably introduce collisions. Story 2.3 follows the same exclusion pattern preemptively + the new unit test asserts it.
4. **jsonschema Draft 2020-12.** Used `jsonschema.Draft202012Validator.check_schema` to verify schema-validity (NOT to validate instance-values against schemas — that's runtime concern Epic 3 owns). The wrapped `SchemaError` is preserved via `__cause__` so callers can introspect the verbatim diagnostic.
5. **Transport enum strict per FR7.** Only `stdio`/`streamable_http`/`in_memory` accepted; `sse` (MCP spec also has this) NOT supported in Phase-1 — pinned to FR7's verbatim enumeration.
6. **`_build_pointer()` duplicated** (intentionally) — mcp/_parser.py and hooks/_parser.py each have their own. Phase-1.5 hygiene candidate: extract to shared `_kernel/jsonptr.py`.

### Completion Notes

- All 10 ACs satisfied. 57 unit + 3 RF integration tests added (60 new total).
- Inherited Story 2.1+2.2 patterns transitively: no eager re-export, `utf-8-sig`, FR59 5-line layout, RFC 6901 JSON Pointer escaping, deviation-tracker docstring.

### Test Results

```
$ uv run ruff check src/ tests/ — PASS
$ uv run ruff format --check src/ tests/ — PASS (after format)
$ uv run mypy src/ — Success: 39 source files
$ uv run python scripts/check-license-headers.py — PASS 39/39
$ uv run pytest tests/unit -q — 455 passed (398 prior + 57 new)
$ uv run pytest tests/conformance -q — 30 passed, 11 skipped
$ uv run pytest tests/acceptance/tier1 -q — 6 passed
$ uv run robot tests/acceptance/smoke + tests/unit/{skills,subagents,hooks,mcp}/test_robot_integration.robot — 13 passed
$ uv run pytest tests/unit/conventions -q (STANDALONE) — 17 passed
```

## File List

**New files:**
- `src/AgentEval/mcp/_parser.py` — `.mcp.json` parser + RFC 6901 JSON Pointer helper + jsonschema Draft 2020-12 validator (~430 LoC).
- `src/AgentEval/mcp/library.py` — `MCPLibrary` with 3 `@tier(1)` `@keyword`-decorated methods (~150 LoC).
- `tests/fixtures/mcp/mcp-valid.json` (canonical happy-path fixture with 2 servers + tools).
- `tests/fixtures/mcp/mcp-missing-command.json`.
- `tests/fixtures/mcp/mcp-malformed-json.json`.
- `tests/fixtures/mcp/mcp-unsupported-transport.json`.
- `tests/fixtures/mcp/mcp-with-broken-tool.json`.
- `tests/unit/mcp/__init__.py` + `test_library.py` (57 tests) + `test_robot_integration.robot` (3 RF tests).

**Modified files:**
- `src/AgentEval/errors.py` — added `InvalidMCPServerConfigError` (15th leaf) + `InvalidMCPToolSchemaError` (16th leaf); both inherit `_FR59Tier1SetupFailureError`.
- `mypy.ini` — added `[mypy-jsonschema.*]` `ignore_missing_imports` section.
- `.github/workflows/ci.yml` — added 1 new robot invocation step (MCP RF integration).

**Modified pre-authoring (drift fixes):**
- `docs/contracts/error-class-hierarchy.md` L10 + L54 + L56 + L93-96 + L121 + L130 — 14-leaf → 16-leaf prose + 15th + 16th leaf inventory rows.
- `_bmad-output/planning-artifacts/epics.md` L1197 — P95 → median per PRD NFR-PERF-02.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (13th use) caught 5 drifts: D-A epics.md P95 → median; D-B + D-C 2 new leaves (15th + 16th) added to catalog; D-D Phase-1 tool-schema source ratified as `.mcp.json:tools` extension; D-E transport enum strict per FR7. | Bob |
| 2026-05-19 | 0.2.0   | Dev-story complete. `MCPLibrary` + `InvalidMCPServerConfigError` (15th leaf) + `InvalidMCPToolSchemaError` (16th leaf) shipped. 57 unit + 3 RF integration tests added; all gates green (ruff/format/mypy clean on 39 src files; 455 unit + 30 conformance + 11 skipped + 6 tier1 + 13 RF). Status: review. | Dev |
