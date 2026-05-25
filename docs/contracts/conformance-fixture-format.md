# Conformance Fixture Format

**Status:** Phase-1 stable (Story 1b.5 filled the contract 2026-05-19; per-fixture allowable-variation evidence semantics promoted to `stable` per `stability-surface.md`).
**Owning epic:** Epic 1b Story 1b.5
**Related ADRs:** ADR-005 (Conformance Suite Includes Fidelity Oracles), ADR-017 (Conformance Suite Organization — per-AC test files + per-adapter parametrize)
**Related FRs:** FR45 (Conformance suite), AC-CONFORMANCE-01 (Fidelity oracles), AC-CONFORMANCE-02 (Completeness oracle)

## Purpose

Governs the **schema + authoring guide for golden-trace fixtures** at `tests/conformance/fixtures/<adapter_name>/<scenario_name>.json`. Each fixture captures the canonical `AgentRunResult` an adapter MUST produce when run against a fixed scenario from the deterministic mock harness. Community adapter authors author their own fixtures locally + submit alongside their adapter PR.

## Scope

### In-scope

- JSON schema of the fixture file (top-level keys, types, optionality).
- The "strict-match" vs "constraint-match" rules per field (e.g., `latency_ms` is `>0` constraint; `metadata.completeness` is exact-match).
- Mock-agent + fixed-scenario fixture catalog (what the 6 Phase-1 reference fixtures cover).
- Adapter-authoring workflow: how a contributor authors a new fixture (run the mock harness against their adapter, capture output, hand-tune allowable variations).
- Test-suite consumption: how `tests/conformance/test_ac_*.py` files load + assert against fixtures via the `adapter_registry` fixture.

### Out-of-scope

- The mock agent's internal implementation (`tests/conformance/harness.py`) — that's libdoc + ADR-017.
- Per-adapter `AgentRunResult` schema — that's `evidence-block-format.md` + ADR-006/007.

## Contract

### Schema

The canonical JSON schema lives at `tests/conformance/fixture-schema.json` (validated by `tests/conformance/loader.py:load_fixture(path) -> ConformanceFixture` via stdlib `jsonschema`). Top-level shape:

```json
{
  "_schema_version": "1.0.0",          // semver MAJOR.MINOR.PATCH
  "adapter_name": "generic",            // matches fixture dir under fixtures/
  "scenario_name": "echo_simple",       // matches fixture filename without .json
  "agent_run_result": { ... },          // ToolCallTrace + Usage + AgentRunMetadata shape per FR12/FR36a/b
  "expected_tool_calls": [ ... ],       // sequence of ExpectedToolCallRecord with allowable-variation pins
  "expected_errors": [ ... ],           // structured {class_name, error_code, message_contains?} per Decision-4
  "reproducibility_footer": { ... }     // library_version, redaction_policy_hash, started_at, ended_at (FR39)
}
```

All objects use `additionalProperties: false` per Story 1b.5 code-review fix; the `ToolCallRecord` + `ExpectedToolCallRecord` + `ExpectedError` shapes are extracted as `$defs` and referenced from both `agent_run_result.tool_calls` and `expected_tool_calls`.

### Per-field strict-match vs constraint-match rules (ADR-005 L19-22)

| Field | Match type | Notes |
|---|---|---|
| `agent_run_result.response_text` | strict | exact match required |
| `agent_run_result.tool_calls[*].name` | strict | per ADR-005 L19 |
| `agent_run_result.tool_calls[*].args` | strict | dict-equality |
| `agent_run_result.tool_calls[*].source` | strict | `"adapter"` or `"hosted_mcp"` |
| `agent_run_result.tool_calls[*].latency_ms` | **constraint** `> 0` | ADR-005 L20 — strict-positive, NOT exact |
| `agent_run_result.tool_calls[*].sequence_index` | strict monotonic | per FR35 + AC-CONFORMANCE-01 ("hallucinated sequence_index fails the suite") |
| `agent_run_result.usage.{input,output,cached_input}_tokens` | strict | non-negative integers |
| `agent_run_result.metadata.completeness` | **strict (truncation injection)** | ADR-006 + AC-CONFORMANCE-02 |
| `agent_run_result.metadata.mcp_coverage` | strict | 3-state Literal per ADR-016 |
| `agent_run_result.cost_usd` | strict non-negative | |
| `agent_run_result.latency_seconds` | strict non-negative | |
| `agent_run_result.trace_id` | strict (any non-empty string) | UUID hex Phase-1; Phase-2 may pin OTel 32-char format |
| `expected_tool_calls[*].latency_ms` | constraint (lower bound) | harness asserts observed latency > this value |
| `expected_errors[*].{class_name, error_code}` | strict | per Decision-4 verbatim |
| `expected_errors[*].message_contains` | optional substring | None means "any error message accepted" |
| `reproducibility_footer.library_version` | strict | matches `pyproject.toml` version at fixture-recording time |
| `reproducibility_footer.{started_at, ended_at}` | ISO-8601 pattern | enforced via regex (jsonschema `format: date-time` only activates when rfc3339-validator dep is installed; Phase-1 uses pattern-match) |

### 6 Phase-1 reference fixtures

Per architecture L738-739, Story 1b.5 ships:

| Adapter | Scenario | AC coverage |
|---|---|---|
| `generic` | `echo_simple` | AC-CONFORMANCE-01 + AC-MCP-OBSERVE-01 (`hosted_in_process`) |
| `generic` | `echo_truncated` | AC-CONFORMANCE-02 + FR36a (`completeness="truncated"`) |
| `generic` | `echo_external_mcp` | AC-MCP-OBSERVE-01 (`external_mixed`) + FR37 (`IncompleteTraceError`) |
| `claude_code_cli` | `echo_simple` | same as generic equivalent |
| `claude_code_cli` | `echo_truncated` | same |
| `claude_code_cli` | `echo_external_mcp` | same |

**Phase-1 limitation:** No concrete adapter exists at end-of-Story-1b.5; Generic LiteLLM lands Story 4.1, Claude Code CLI lands Story 4.2. The 6 fixtures publish the contract; nothing exercises them yet. `reproducibility_footer.library_version = "0.0.1"` + `redaction_policy_hash = "sha256:placeholder-phase1"` are synthetic placeholders pending Epic 4 regeneration from real recorded runs.

### Adapter-authoring workflow (5-step checklist)

1. **Implement the adapter.** Subclass `InProcessAdapter` or `SubprocessAdapter` per ADR-003 + Story 1b.4 `coding_agent/base.py`. Pass `assert_adapter_signature(YourAdapter)` from `tests/conformance/harness.py`.
2. **Register the adapter.** Add a `[project.entry-points."agenteval.coding_agents"]` table entry in your `pyproject.toml` keyed by `adapter_name`. Story 1b.3's `_kernel/discovery.discover_adapters()` auto-picks it up.
3. **Author fixture JSON files.** Place at `tests/conformance/fixtures/<your_adapter_name>/<scenario_name>.json` for each scenario you want to assert. Use the schema at `tests/conformance/fixture-schema.json`; `load_fixture(path)` schema-validates.
4. **Record reproducibility footer values.** Set `library_version` to your installed `agenteval` version, `redaction_policy_hash` to the actual hash from `_kernel/redaction.py`, and `started_at`/`ended_at` to ISO-8601 timestamps from the actual run.
5. **Wire to per-AC test files.** Use the `adapter_registry` pytest fixture from `tests/conformance/harness.py` to parametrize over your adapter alongside existing adapters. Replace the `pytest.skip("Owning epic N not yet shipped")` marker with the real assertion body when your epic's keyword infrastructure lands.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. Story 1b.5 (2026-05-19) promoted the fixture-schema field set + the `ToolCallRecord` / `ExpectedToolCallRecord` / `ExpectedError` `$defs` to `stable`. Adding fields with optional default is minor-version-bump safe; removing a field requires major-version bump (breaks existing fixtures). `_schema_version` is bumped per change:
- **PATCH** (1.0.0 → 1.0.1): typo fixes, doc clarifications, no behavior change.
- **MINOR** (1.0.0 → 1.1.0): new optional fields, new `$defs` keys, new `expected_errors[].class_name` values consumers must tolerate.
- **MAJOR** (1.0.0 → 2.0.0): removed/renamed fields, changed match-type for an existing field (strict ↔ constraint), changed Literal enum value spaces.

Phase-2 pre-release semver tags (e.g., `2.0.0-rc1`) are NOT yet supported by the schema's `_schema_version` regex per Story 1b.5 code-review finding F11; tracked as DF-1b.5-S1 in `deferred-work.md`.

## Conformance Report Schema (Phase-1.5)

**Added by Story 8a.2 (2026-05-25)** per PRD FR57. Schema for the report
artifacts emitted by `python -m AgentEval.conformance --adapter <name>
--output-dir <dir>`.

### `<output_dir>/conformance-report.json`

```json
{
  "agenteval_version": "<semver>",
  "adapter": "<adapter-name>",
  "executed_at": "<ISO 8601 UTC, seconds precision>",
  "summary": {
    "total": <integer>,
    "passed": <integer>,
    "failed": <integer>,
    "errored": <integer>,
    "skipped": <integer>
  },
  "fixtures": [
    {
      "fixture_id": "<string>",
      "fixture_path": "<repo-relative path>",
      "status": "passed" | "failed" | "errored" | "skipped",
      "duration_seconds": <float>,
      "oracle_evidence": { /* fixture-specific */ },
      "error": null | {"type": "<exception class name>", "message": "<one-line>"}
    }
  ]
}
```

All keys are REQUIRED. `fixtures[]` is permitted to be empty (e.g., when
fixture discovery finds nothing); `summary.total` equals
`len(fixtures)`.

### `<output_dir>/conformance-report.md`

```markdown
# Conformance Report — <adapter> @ <executed_at>

agenteval version: `<semver>`

## Summary

| Total | Passed | Failed | Errored | Skipped |
| --- | --- | --- | --- | --- |
| N | N | N | N | N |

## First 5 failures   <!-- only present if total failures > 0 -->

- **<fixture_id>** (`<fixture_path>`) — `<status>`: <truncated error message ≤200 chars>
```

### Stability surface

Per FR64. The 4 required top-level keys + 5 summary keys + per-fixture key
set are `stable` from Phase-1.5 onward. Adding new top-level keys (e.g., a
future `environment` block recording git SHA / runner OS) is minor-version
safe; removing or renaming any field requires major-version bump + a
documented migration path for CI consumers.

The 4 `status` values (`passed` / `failed` / `errored` / `skipped`) form a
closed Literal — new values require ADR amendment.

### Phase-1 Limitations (DF-8a.2-S1 / C63)

- Phase-1 fixture execution records every fixture as `status="skipped"`
  with a deferral rationale. Per-adapter fixture dispatch wires in
  Phase-1.5 via the Story 1b.5 harness.
- The listener-variable trigger path (`robot --listener ... --variable
  conformance_report:json+human tests/` per epics.md Story 8a.2 L1862) is
  deferred to Phase-1.5; Phase-1 ships the standalone CLI only.

## References

- ADR-005: Conformance Suite Includes Fidelity Oracles
- ADR-017: Conformance Suite Organization
- Story 1a.2 `conformance.yml` workflow runs these fixtures per release
- Story 8a.2: Conformance Report schema authoring
- FR45 + AC-CONFORMANCE-01/02 (PRD)
- FR57 (PRD): Conformance report shape
