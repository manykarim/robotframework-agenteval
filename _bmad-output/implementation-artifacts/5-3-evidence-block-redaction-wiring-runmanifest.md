# Story 5.3: Evidence Block + Redaction Wiring + RunManifest

Status: done

## Story

As **Raj (Agent Developer)** auditing a test run,
I want the **AC-SIMPLICITY-01 evidence-block format** applied automatically to RF output (per-test trace summary with prompt, response, tool calls, cost, coverage, completeness), **credential redaction wired into the listener pipeline** (so traces NEVER contain raw API keys even on listener failure paths), and a **`RunManifest` JSON sidecar** produced per test capturing the full run metadata (FR39),
So that test reports are auditable + safe for sharing externally — no credential leaks, no missing run context.

## Pre-create-story drift check (24th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

3 drifts caught + resolved pre-authoring (per fix-the-losing-source-NOW pattern):

- **(D-1 MED)** epics.md L1494 cites "visual contract from `docs/contracts/otel-trace-visual.md` (Story 8b authors this contract; Story 5.3 implements the format)". Actual `otel-trace-visual.md` Phase-1 skeleton is owned by **Phase 2** (renderer visualization), NOT Story 8b. The Phase-1 contract Story 5.3 fills is `docs/contracts/evidence-block-format.md` (Phase-1 skeleton owned by Epic 5 per architecture L1419-1428). Story 5.3 fills `evidence-block-format.md`; `otel-trace-visual.md` stays a Phase-2 skeleton.

- **(D-2 HIGH)** Three-way drift on `RunManifest` field set:
  - **epics.md L1502 AC-3** lists ~14 fields: `test_id, suite_id, started_at, completed_at, library_version, adapter (name+version), model, mcp_servers, trace_backend, total_cost_usd, completeness, mcp_coverage, warnings, seed`.
  - **architecture L896** ratifies 7 fields: `library_version, test_id, suite_id, redaction_policy_hash, started_at, ended_at, agenteval_tier_breakdown` (already shipped in `src/AgentEval/types.py:165` as `@dataclass(frozen=True)`).
  - **PRD FR39** lists: `seeds, adapter versions, MCP server versions/SHAs, prompt hashes, library version, redaction-policy hash, test_id, ISO 8601 timestamp`.

  Per fix-the-losing-source-NOW: extend the ratified `RunManifest` dataclass to a **union** of all three sources with `Optional[…] = None` defaults for the new fields. Existing callers + 7-field projection from `_kernel/trace_store.get_run_manifest()` keep working; new fields populated by Story 5.3's manifest-emit path (`telemetry/run_manifest.py`). Also amend epics.md L1502 `completed_at` → `ended_at` to match architecture L896 + the existing dataclass (architecture/dataclass wins for naming consistency).

- **(D-3 MED)** epics.md L1502 RunManifest JSON sidecar path is `<output_dir>/run-manifest-<test_id>.json`; Story 5.1's JSONL backend already uses `<output_dir>/agenteval/trace__<suite>__<test>.jsonl`. For path-shape consistency + co-location with the trace artifact, Story 5.3 uses `<output_dir>/agenteval/run-manifest__<suite>__<test>.json` (same `agenteval/` subdirectory + `__<suite>__<test>` segment pattern). Sanitization helper from `telemetry/backends.py:_sanitize_path_segment` is reused.

## Acceptance Criteria

### AC-5.3.1 — Extended `RunManifest` dataclass (FR39 union shape)

**Given** the existing `RunManifest` at `src/AgentEval/types.py:165` (7 fields per architecture L896) + the FR39 PRD list + the epics.md L1502 operational fields,
**When** Story 5.3 extends the dataclass,
**Then** `RunManifest` carries (existing 7 fields preserved verbatim + new fields added with `Optional[...] = None` defaults so the projection accessor at `_kernel/trace_store.get_run_manifest()` keeps building backward-compatible manifests):
- **Existing (ratified)**: `library_version`, `test_id`, `suite_id`, `redaction_policy_hash`, `started_at: datetime`, `ended_at: datetime`, `agenteval_tier_breakdown: Mapping[int, int]`.
- **New (Story 5.3)**: `adapter_name: str | None = None`, `adapter_version: str | None = None`, `model: str | None = None`, `mcp_servers: list[dict[str, str]] = field(default_factory=list)` (each entry `{name, transport, version_or_sha}`), `trace_backend: Literal["memory", "jsonl"] | None = None`, `total_cost_usd: float | None = None`, `completeness: Literal["complete", "truncated", "partial"] | None = None`, `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"] | None = None`, `warnings: list[str] = field(default_factory=list)` (Story 5.4 populates), `seed: int | None = None`, `prompt_hashes: list[str] = field(default_factory=list)` (SHA-256 of each prompt the agent saw — per FR39).
- `frozen=True` preserved + `__post_init__` defensive-copies the list/dict fields per Story 1b.2 M_R6 pattern.

### AC-5.3.2 — `src/AgentEval/telemetry/run_manifest.py` JSON sidecar emitter

**Given** the extended `RunManifest` dataclass + the Listener's `end_test` hook,
**When** Story 5.3 implements the manifest emitter,
**Then**:
- `RunManifestEmitter` class with `emit(manifest, output_dir, suite_id, test_id)` method writes JSON to `<output_dir>/agenteval/run-manifest__<safe_suite>__<safe_test>.json` (using `telemetry/backends._sanitize_path_segment` for path-traversal safety).
- JSON serialization via `dataclasses.asdict()` + `json.dumps(default=str)` for `datetime` fields.
- On write failure: emits `UserWarning` (DF-5.3-S1 forward-ref: replace with `DegradedTraceWarning` once Story 5.4 lands) + does NOT raise (consistent with `telemetry/backends.JSONLBackend.flush_test` failure pattern).
- Skip phantom 0-byte files when `manifest is None` (consistent with Story 5.2 Codex HIGH-J fix).

### AC-5.3.3 — Listener wires manifest emission on `end_test`

**Given** Story 5.1's `Listener.end_test` hook,
**When** Story 5.3 adds manifest emission,
**Then**:
- `Listener.end_test` calls `RunManifestEmitter.emit(...)` AFTER `trace_store.clear_spans(test_id)` (existing order) BUT before `_kernel_context.unbind_context()`. The manifest is built from a combination of `_kernel/trace_store.get_run_manifest(test_id)` (the 7 ratified fields) + accumulated operational state (the Listener tracks `_current_run_metadata: dict[str, Any]` set by adapters via a `Listener.record_run_metadata(adapter_name, adapter_version, model, mcp_servers, total_cost_usd, completeness, mcp_coverage, seed, prompt_hashes)` API call from the adapter's `run()` post-completion).
- When NO adapter recorded metadata (e.g., a test that didn't call `Send Prompt` / `Run Scenario`), the emitter still writes the manifest with the 7 ratified fields populated (`started_at`, `ended_at`, etc. from span resource attributes) + the new fields as `None` / empty.

### AC-5.3.4 — Adapter `record_run_metadata` integration

**Given** the Generic adapter (Story 4.1) + Claude Code CLI adapter (Story 4.2),
**When** Story 5.3 wires the adapter side of `record_run_metadata`,
**Then** each adapter's `run()`, after building `AgentRunResult`, calls `telemetry.listener.record_active_run_metadata(...)` (a module-level helper paralleling `register_active_observer` from Story 5.2 code-review HIGH-C fix). The helper finds all active listeners + calls `listener.record_run_metadata(...)` on each. Adapter passes:
- `adapter_name = self.name`
- `adapter_version = self.version`
- `model = self._model` (Generic) / `<resolved from claude --version output>` (Claude Code CLI)
- `mcp_servers = [{"name": name, "transport": h.transport, "version_or_sha": "<TBD Phase-1.5>"} for name, h in (mcp_servers or {}).items()]`
- `total_cost_usd = result.cost_usd`
- `completeness = result.metadata.completeness`
- `mcp_coverage = result.metadata.mcp_coverage`
- `prompt_hashes = [sha256(prompt.encode("utf-8")).hexdigest()]`

### AC-5.3.5-DEFERRED — AC-SIMPLICITY-01 `threshold` + `observed_value` fields

**Story 5.3 code-review 1-way Auditor HIGH-F fix 2026-05-20**: PRD L88-92
AC-SIMPLICITY-01 verbatim mandates `(a) exact threshold compared, (b)
observed value, (c) raw agent artifact` for every assertion keyword in
the core library. Story 5.3's `EvidenceBlock` dataclass + contract ship
(c) via `prompt/response/tool_calls` but NOT (a) `threshold` nor (b)
`observed_value`. Phase-1 trace-based family doesn't have a natural
threshold-vs-observed shape (trace-based assertions are pass/fail-by-
existence, not threshold comparisons), but AC-SIMPLICITY-01's "every
assertion keyword" wording doesn't permit a trace-only family that
drops (a)+(b). **Resolution**: deferred to Story 6.x (when Phase-1
ships metric-based assertion keywords like `Get Tool Call Count` +
threshold comparisons). At that point `threshold: str | None` +
`observed_value: str | None` are added to `EvidenceBlock` as Optional
fields populated only by metric-based + judge-based families. Phase-1
trace-based family leaves them None (the trace-based outcome IS the
threshold check); AC-SIMPLICITY-01 is satisfied at PRD-amendment level
via a clarifying note that trace-based assertions implicitly satisfy
(a)+(b) via outcome+tool_calls. Carry-over **DF-5.3-S6** added.

### AC-5.3.5 — `docs/contracts/evidence-block-format.md` Contract section filled

**Given** the Phase-1 skeleton at `docs/contracts/evidence-block-format.md`,
**When** Story 5.3 fills the Contract section,
**Then** the contract documents:
- Field-level JSON schema with required + optional fields per assertion family (trace-based, metric-based, judge-based — though Phase-1 only ships trace-based).
- Required Phase-1 fields per AC-SIMPLICITY-01: `evidence_id` (UUID4), `assertion_name` (RF keyword), `outcome` (pass/fail/skip/degraded), `prompt`, `response`, `tool_calls` (list of `ToolCallTrace` records), `cost_usd`, `coverage` (=mcp_coverage), `completeness`, `redaction_report` (list of `[REDACTED:<pattern_name>]` substitutions per FR38a), `traces`, `metadata` (=AgentRunMetadata).
- 80-char line-width visual format for human-readable rendering (per AC-SIMPLICITY-01 "legibility = simplicity codified as a contract"). Phase-1 ships the field-level schema + a basic visual format; richer rendering is Phase-2 per `otel-trace-visual.md`.
- Stability label assignment for each field (`stable` / `provisional` / `experimental`).

### AC-5.3.6 — `src/AgentEval/telemetry/evidence_block.py` emitter

**Given** the Evidence Block contract,
**When** Story 5.3 implements the emitter,
**Then**:
- `EvidenceBlock` frozen dataclass per AC-5.3.5 field schema.
- `EvidenceBlockEmitter.emit(result, assertion_name, outcome)` builds an `EvidenceBlock` from an `AgentRunResult` + assertion context.
- `EvidenceBlock.to_markdown()` returns a human-readable 80-char-wide block per AC-SIMPLICITY-01.
- `EvidenceBlock.to_dict()` returns the JSON-serializable form per AC-5.3.5.
- Both forms apply `redact_dict` from `_kernel/redaction` before emission (defense-in-depth — even though the `RedactionProcessor` already scrubs span attributes, the evidence block builds from `AgentRunResult` fields not span attributes).

### AC-5.3.7 — Redaction wired end-to-end through evidence block

**Given** `_kernel/redaction.py`'s `redact_dict` + `RedactionProcessor`,
**When** Story 5.3 wires redaction through the evidence block + RunManifest paths,
**Then**:
- `EvidenceBlock.to_dict()` runs every text field through `redact()` before emission.
- `EvidenceBlock.to_markdown()` runs the rendered text through `redact()` before returning.
- `RunManifestEmitter.emit()` runs each text field of the manifest dict through `redact()` (`adapter_name` + `model` are unlikely to contain credentials but defense-in-depth).
- Unit test verifies: an `EvidenceBlock` constructed with `response = "API key sk-1234567890abcdef"` renders as `[REDACTED:openai_api_key]` in both `to_dict()` and `to_markdown()` outputs (assuming the default OPENAI_API_KEY pattern matches).

### AC-5.3.8 — `docs/contracts/run-manifest-schema.json` published

**And** a JSON Schema describing the extended `RunManifest` shape is published at `docs/contracts/run-manifest-schema.json`. Story 5.3's tests validate the emitted JSON sidecar against this schema using `jsonschema.validate()`. Schema is `$schema: "http://json-schema.org/draft-07/schema#"`. Phase-1 stability label: `provisional` (Phase-2 additions are minor-bump safe).

### AC-5.3.9 — Unit tests + integration tests

**And** unit tests at `tests/unit/telemetry/test_evidence_block.py` + `test_redaction_wiring.py` + `test_run_manifest.py` cover:
- `EvidenceBlock.to_dict()` + `to_markdown()` round-trip with all fields populated.
- Redaction integration: response containing `sk-...` API key surfaces as `[REDACTED:openai_api_key]` in evidence block output.
- `RunManifest` extended fields default to `None` / empty list when not populated.
- `RunManifestEmitter.emit()` writes JSON at the canonical path + schema-validates.
- `RunManifestEmitter.emit()` write-failure path emits `UserWarning` + does NOT raise.
- `Listener.record_run_metadata` accumulates per-call data + emits on `end_test`.
- Adapter integration: `GenericAdapter.run()` calls `record_active_run_metadata()` with the correct field set.

### AC-5.3.10 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean.
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance tests/integration -q` regression-clean (978 Story 5.2 close baseline; +30-40 new from this story expected).

### AC-5.3.11 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (26th consecutive use).
- `feedback_n_way_agreement_weight` extended triage table applied.
- `feedback_test_name_assertion_match` applied to all new tests.
- `feedback_codex_sandbox_bypass_operational` for Codex CLI review.
- `feedback_carry_over_catalog_gate` at story-close: grep for `DF-5.3-S<N>` patterns; verify in `docs/phase-1-5-carry-overs.md` AND `_bmad-output/implementation-artifacts/deferred-work.md`.

## Tasks / Subtasks

- [x] **Task 1: Pre-authoring drift fixes applied** (D-1 + D-2 + D-3 above) — DONE during pre-create-story.
- [x] **Task 2: Extend `RunManifest` dataclass** — added 11 new Optional fields (adapter_name, adapter_version, model, mcp_servers, trace_backend, total_cost_usd, completeness, mcp_coverage, warnings, seed, prompt_hashes) with safe defaults; `__post_init__` extended to defensive-copy the 3 new mutable fields per M_R6.
- [x] **Task 3: `src/AgentEval/telemetry/run_manifest.py`** — `RunManifestEmitter` ships sidecar at `<output_dir>/agenteval/run-manifest__<suite>__<test>.json` with skip-on-None + path-sanitization + widened-except + redaction at emit boundary.
- [x] **Task 4: `docs/contracts/run-manifest-schema.json`** — Draft-07 JSON Schema with 7 required + 11 optional fields published.
- [x] **Task 5: `Listener.record_run_metadata` API + `end_test` manifest emission** — `_current_run_metadata` accumulator + `_emit_run_manifest_sidecar` helper called BEFORE `trace_store.clear_spans` (Story 5.2 HIGH-F clear-order pattern preserved).
- [x] **Task 6: Adapter integration** — module-level `record_active_run_metadata()` helper added to `telemetry/listener.py`; Generic + Claude Code CLI adapters call it from `run()` post-completion with adapter_name + version + model + mcp_servers + cost + completeness + mcp_coverage + prompt_hashes.
- [x] **Task 7: `docs/contracts/evidence-block-format.md`** Contract section filled per AC-5.3.5 (field-level JSON schema + 80-char-wide markdown rendering + redaction integration + per-family required-fields table).
- [x] **Task 8: `src/AgentEval/telemetry/evidence_block.py`** — `EvidenceBlock` frozen dataclass + `EvidenceBlockEmitter` with `to_dict()` + `to_markdown()` + redaction integration at emit time.
- [x] **Task 9: Unit + integration tests** — 22 new tests at `tests/unit/telemetry/test_evidence_block.py` (10) + `test_redaction_wiring.py` (4) + `test_run_manifest.py` (8). JSON schema validation included.
- [x] **Task 10: All-gates pass.** ruff/format/mypy clean (66 src files), license headers PASS, **1000 unit+conformance+integration / 8 skipped** (was 978 at Story 5.2 close; +22 net).
- [x] **Task 11: 4-reviewer cross-LLM code review with extended N-way agreement triage table + carry-over catalog gate.** Completed 2026-05-20 — 12 HIGH findings surfaced (1 4-way + 1 3-way + 2 2-way + 8 1-way); 8 code patches applied (HIGH-A/B/D/E/I/J/K/L) + 4 deferred-via-catalog (HIGH-F/G/H + DF catalog entries C36/C37/C38); 27th consecutive cross-LLM STAR catch streak preserved. See Change Log v0.3.0 for the full triage record.

## Dev Notes

### Architecture compliance

- **PRD FR38a + FR38b** (credential redaction): wired through both `EvidenceBlock` + `RunManifestEmitter` emission paths.
- **PRD FR39 (RunManifest)**: extended dataclass covers all FR39-listed fields; JSON sidecar emitted on `end_test`.
- **PRD AC-SIMPLICITY-01** (evidence-block legibility): formal schema documented in `evidence-block-format.md` + `EvidenceBlock` dataclass implements it.
- **NFR-SEC-01** (no credential persistence): redaction at evidence block + manifest emission boundaries.
- **architecture L896** RunManifest dataclass shape: extended (not replaced) — backward compat preserved.
- **Story 1b.2** `_kernel/redaction` + `_kernel/trace_store.get_run_manifest` projection accessor: reused intact.

### Phase-1 limitations explicitly documented

- **mcp_servers version_or_sha**: PRD FR39 lists "MCP server versions/SHAs" but Phase-1 has no canonical way to introspect a third-party MCP server's version. Phase-1 emits placeholder `"<TBD Phase-1.5>"`. DF-5.3-S2 carry-over.
- **prompt_hashes**: Phase-1 hashes the user-prompt input only. Multi-turn conversations (when DF-5.2-S3 lands) will need to hash the full turn sequence — DF-5.3-S3 carry-over.
- **Visual rendering**: `EvidenceBlock.to_markdown()` ships a basic 80-char wrap. Rich visualization (color, syntax highlighting, link previews) is Phase-2 per `docs/contracts/otel-trace-visual.md`.
- **`warnings` field**: populated by Story 5.4's `DegradedTraceWarning` collector; Phase-1 ships empty list default.

## Dev Agent Record

### Completion Notes

- **Extended RunManifest dataclass** at `src/AgentEval/types.py` with 11 new Optional fields (adapter_name, adapter_version, model, mcp_servers, trace_backend, total_cost_usd, completeness, mcp_coverage, warnings, seed, prompt_hashes). All defaults are safe (None / empty list) so the 7-field projection from `_kernel/trace_store.get_run_manifest()` keeps working backward-compatibly. `__post_init__` extended to defensive-copy mcp_servers + warnings + prompt_hashes per M_R6 pattern.
- **JSON Schema** at `docs/contracts/run-manifest-schema.json` (Draft-07) ratifies the extended shape with type constraints (pattern for SHA-256 hashes; enum for transport / coverage / completeness; format: date-time for timestamps).
- **`telemetry/run_manifest.py` `RunManifestEmitter`** writes sidecar at `<output_dir>/agenteval/run-manifest__<safe_suite>__<safe_test>.json` (using `_sanitize_path_segment` for path-traversal safety). Failure pattern matches Story 5.1 JSONLBackend: widened-except (OSError, ValueError, TypeError, RecursionError), UserWarning + None return (DF-5.3-S1 forward-ref to DegradedTraceWarning). Skip-on-None pattern matches Story 5.2 Codex HIGH-J fix.
- **`telemetry/listener.py` extensions**: `_current_run_metadata` dict accumulator + `record_run_metadata(**kwargs)` instance API + module-level `record_active_run_metadata(**kwargs)` helper paralleling `register_active_observer` from Story 5.2. List-valued fields (mcp_servers, prompt_hashes, warnings) accumulate via concat; scalar fields use last-wins. `_emit_run_manifest_sidecar` helper runs in `end_test` BEFORE `trace_store.clear_spans` so the projection accessor can still read the spans. Wrapped in `contextlib.suppress(Exception)` so sidecar-emit failure doesn't mask test outcomes.
- **Adapter integration**: `GenericAdapter.run()` + `ClaudeCodeCLIAdapter.run()` both call `record_active_run_metadata()` post-completion with the operational fields. The 3 helpers (`_hash_prompt`, `_manifest_entries_from_servers`, `_record_run_metadata`) live in `generic.py` + are re-imported by `claude_code_cli.py` to avoid duplication. DF-5.3-S2 carve-out: `mcp_servers[*].version_or_sha` is `"<TBD Phase-1.5>"` (no canonical SDK introspection path today).
- **`docs/contracts/evidence-block-format.md`** Contract section ratified: field-level schema (11 fields with stability labels) + 80-char-wide markdown rendering format + redaction integration (defense-in-depth at emit time since AgentRunResult fields aren't span attributes the OTel RedactionProcessor scrubs).
- **`telemetry/evidence_block.py` `EvidenceBlock` dataclass + `EvidenceBlockEmitter`**: frozen + M_R6 defensive copies; `to_dict()` walks all string fields through `redact()` recursively; `to_markdown()` applies `redact()` to prompt + response before wrapping; `_detect_applied_redactions()` populates the `redaction_report` field via a raw-vs-redacted comparison (DF-5.3-S4 carry-over: per-pattern attribution requires richer `RedactionReport` type from `_kernel/redaction`).
- **3 Phase-1.5 carry-overs identified**: DF-5.3-S1 (UserWarning → DegradedTraceWarning upgrade once Story 5.4 lands); DF-5.3-S2 (`version_or_sha` Phase-1.5 introspection); DF-5.3-S3 (multi-turn prompt_hashes); DF-5.3-S4 (per-pattern RedactionReport attribution). All 4 will be added to `docs/phase-1-5-carry-overs.md` + `deferred-work.md` at story-close per `feedback_carry_over_catalog_gate`.
- **22 new tests pass**; **1000 unit+conformance+integration total** (was 978 at Story 5.2 close); ruff/format/mypy clean (66 src files); license headers PASS.

## File List

**New files:**
- `src/AgentEval/telemetry/evidence_block.py`
- `src/AgentEval/telemetry/run_manifest.py`
- `docs/contracts/run-manifest-schema.json`
- `tests/unit/telemetry/test_evidence_block.py`
- `tests/unit/telemetry/test_redaction_wiring.py`
- `tests/unit/telemetry/test_run_manifest.py`

**Modified files:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 5.3 status transitions.
- `docs/contracts/evidence-block-format.md` — Phase-1 skeleton → ratified Contract section.
- `src/AgentEval/types.py` — `RunManifest` extended with 11 Optional fields.
- `src/AgentEval/telemetry/listener.py` — `record_run_metadata` API + `_emit_run_manifest_sidecar` helper + module-level `record_active_run_metadata`.
- `src/AgentEval/coding_agent/generic.py` — `_record_run_metadata` call + 3 helper functions (`_hash_prompt`, `_manifest_entries_from_servers`, `_record_run_metadata`).
- `src/AgentEval/coding_agent/claude_code_cli.py` — `record_active_run_metadata` call in `run()` post-completion.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (24th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 3 drifts: D-1 MED `otel-trace-visual.md` ownership (Phase-2 not Story 8b) → fills `evidence-block-format.md` instead; D-2 HIGH three-way RunManifest field set drift (epics ~14 / architecture 7 / FR39 different) → extend dataclass with Optional fields + amend `completed_at` → `ended_at`; D-3 MED manifest JSON sidecar path → `<output_dir>/agenteval/run-manifest__<suite>__<test>.json` for Story-5.1-JSONL-parity. | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code review). 3 new telemetry modules (evidence_block.py + run_manifest.py + extended types.RunManifest); 2 new docs/contracts (evidence-block-format.md Contract filled + run-manifest-schema.json Draft-07); Listener `record_run_metadata` API + `_emit_run_manifest_sidecar` helper; both adapters wire `record_active_run_metadata` from `run()` post-completion. 22 new tests (10 evidence_block + 4 redaction_wiring + 8 run_manifest). 4 new Phase-1.5 carry-overs identified (DF-5.3-S1/S2/S3/S4) — to be catalogued at story-close per `feedback_carry_over_catalog_gate`. All gates green: ruff/format/mypy clean (66 src files); **1000 unit+conformance+integration** (was 978 at Story 5.2 close; +22 net) / 8 skipped; license-headers PASS. | Amelia |
| 2026-05-20 | 0.3.0   | **Status → done.** 4-reviewer cross-LLM code-review surfaced **12 HIGH findings** (Blind H1/H4/H5/H6 + Edge-cases E1/E2/E3 + Auditor H5/H6/H7/H8 + Codex H1 + cross-reviewer overlap). N-way agreement triage (`feedback_n_way_agreement_weight` extended Epic 4 retro): **HIGH-A 4-way** carry-over catalog gate (Blind H3 + Auditor H5 + Codex H1 + Edge-cases implicit — DF-5.3-S1/S2/S3/S4 missing from `docs/phase-1-5-carry-overs.md` + `deferred-work.md`; SAME pattern caught Stories 5.1 + 5.2 — `feedback_carry_over_catalog_gate` now **load-bearing across 4 consecutive stories**); **HIGH-B 3-way** JSONL backend silently skipping manifest (Codex empirical `memory exists True; jsonl exists False` + Edge-cases E2 + Blind MED-2 — listener.end_test treated `JSONLBackend.flush_test() is None` as failure + early-returned BEFORE sidecar emit, but None is ALSO legitimate "no spans captured" path); **HIGH-C 2-way** no E2E integration test for full `start_test → adapter.run() → record_active_run_metadata → end_test → sidecar` flow (Edge-cases H3 + Codex MED); **HIGH-D 2-way** multi-adapter `record_run_metadata` last-wins clobbered adapter_name + model when second adapter passed None (Blind H4 + Codex empirical); **HIGH-E Auditor 1-way** PRD FR39 path drift (`run-manifest__` vs PRD L1558 mandated `manifest__`) — Auditor 1-way HIGHs on PRD/ADR re-derivation now **9+ consecutive TPs across 6 epics**; **HIGH-F Auditor 1-way** AC-SIMPLICITY-01 missing `threshold` + `observed_value` fields (deferred to Story 6.x via DF-5.3-S6); **HIGH-G Auditor 1-way** FR34b verbatim box-drawing visual format drift (deferred Phase-2 via DF-5.3-S7); **HIGH-H Auditor 1-way** FR38b `Get Effective Config` redaction unwired (deferred Phase-1.5 via DF-5.3-S8); **HIGH-I Blind 1-way** false-negative redaction when response arrives ALREADY redacted (fixed: upstream `[REDACTED]` marker = positive signal); **HIGH-J Blind 1-way** Decimal flows through `dataclasses.replace` (fixed: coerce to float/int before replace); **HIGH-K Blind 1-way** 80-char overflow in `_wrap_80` (fixed: width=69 + 11-space indent); **HIGH-L Edge-cases 1-way** None latency crash (fixed: `(tc.get('latency_ms') or 0)` coercion). 8 code patches applied + 4 deferred-via-catalog (C36/C37/C38 in `docs/phase-1-5-carry-overs.md`; DF-5.3-S6/S7/S8 in `deferred-work.md` Story 5.3 section) + 3 new regression tests (HIGH-K, HIGH-L, HIGH-I in `test_evidence_block.py`) + 1 NEW integration module (`tests/integration/telemetry/test_run_manifest_listener_e2e.py` — 3 tests covering HIGH-B + HIGH-C + HIGH-D regressions). Catalog total: 31 → 38 (was 35 in pre-edit). All gates green: ruff/format/mypy clean (66 src files); **1005 unit+conformance+integration** (was 1000 at v0.2.0 close; +5 net regression tests for HIGH-B/C/D/I/K/L) / 8 skipped; license-headers PASS. 27th consecutive cross-LLM STAR catch streak preserved. | Amelia |
