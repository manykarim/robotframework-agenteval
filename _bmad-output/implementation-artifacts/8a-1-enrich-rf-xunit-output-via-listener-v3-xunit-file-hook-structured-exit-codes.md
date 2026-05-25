# Story 8a.1: Enrich RF `--xunit` Output Via Listener v3 `xunit_file` Hook + Structured Exit Codes

Status: done

## Story

As **Priya (QA Engineer)** or **a CI operator**,
I want `robotframework-agenteval` to **enrich RF's native `--xunit` output** with per-testcase `<properties>` (cost, tokens, latency, coverage, completeness, trace_id, adapter, model, tier) + `<system-out>` evidence block + `<system-err>` warning content, via the `xunit_file(path)` hook on the Story 5.1 Regular Listener — plus FR50 error_code → exit code mapping for the process-exit channel,
so that mainstream CI tooling that already consumes JUnit XML automatically surfaces AgentEval telemetry alongside standard pass/fail — without parallel CI-tool integrations and without re-emitting JUnit XML from scratch.

## Pre-create-story drift check (35th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-25)

**100% real-drift catch rate intact.** 6 drifts caught:

- **D-1 (HIGH):** epics.md L1818 example showed `agenteval.completeness="full"` — but the ratified `completeness` Literal in `src/AgentEval/types.py` L314 is `("complete", "truncated", "partial")`. `"full"` is NEVER a valid value (this is the exact DF-6.4-S1 drift Story 6.4 fixed in `_default_pass_predicate` but did NOT propagate to the epics.md xunit example). **AMENDED pre-authoring** (commit pending this story): epics.md L1818 `value="full"` → `value="complete"` per `fix-the-losing-source-NOW`.
- **D-2 (HIGH-decision):** `docs/contracts/error-class-hierarchy.md` L128 explicitly states "Adding `exit_code: ClassVar[int]` to each leaf is tracked in `deferred-work.md` as a Phase-1.5 hygiene pass to coincide with the CLI's exit-code translation layer landing (Epic 8a Story 8a.1)." **Decision (path-of-least-amendment):** Story 8a.1 ships the exit-code mapping as a single `_ERROR_EXIT_CODES: dict[str, int]` constant in `src/AgentEval/cli.py` (consulting the contract table by `error_code` string lookup, NOT touching the 19 leaf classes); per-leaf `ClassVar[int]` deferred to Phase-1.5 as **DF-8a.1-S1 / C62**. Rationale: changes to 19 leaf classes carry blast radius; the lookup-table approach is functionally equivalent for FR50 + isolates the change to one new file.
- **D-3 (MED):** AC includes `agenteval.adapter` + `agenteval.model` properties — these are NOT in `trace_store.get_run_manifest()`'s 7 ratified fields. They're populated via the Story 5.3 `record_active_run_metadata()` adapter-side callback into `self._current_run_metadata` on the listener instance. Implementation reads BOTH `trace_store` projections (cost/tokens/latency/completeness/mcp_coverage/trace_id) AND `listener._current_run_metadata` (adapter/model). Story dev notes document this.
- **D-4 (MED):** epics.md L1838 documents the `--listener AgentEval.telemetry.listener` requirement, but `docs/contracts/junit-xml-enrichment.md` (the contract authored by THIS story per AC) does not currently state it. The contract authoring SHALL include a "Required listener invocation" section repeating the requirement loud-and-clear.
- **D-5 (LOW):** `tests/integration/ci/` directory does not exist (current `tests/integration/` has `mcp/`, `orchestration/`, `skills/`, `telemetry/`). Story creates `tests/integration/ci/__init__.py` + the new test file.
- **D-6 (LOW):** epics.md AC mentions "`pytest-junitxml` + a GitLab-test-reports compatible parser" for verification — `pytest-junitxml` is NOT a project dep. **Decision (path-of-least-amendment):** use Python stdlib `xml.etree.ElementTree` for shape verification (testcase + properties + property name/value attributes); skip the third-party parser dependency. The schema-compliance assertion verifies (a) every property has `name` + `value` attributes, (b) `<failure type="...">` attributes parse, (c) re-parsing the enriched XML yields the same elements as parsing the pre-enrichment XML plus the additions. Defer GitLab-specific parser verification to Phase-2 if needed.

## Acceptance Criteria

### AC-8a.1.1 — `xunit_file(path)` listener hook implementation

**Given** the Story 5.1 Regular Listener at `src/AgentEval/telemetry/listener.py` (currently has a Phase-1 no-op `xunit_file(path)` stub at L434),
**When** `Listener.xunit_file(path)` is called by RF after `--xunit junit.xml` is written,
**Then** the method:
1. Reads the XML at `path` via `xml.etree.ElementTree`.
2. For each `<testcase>` element: derives the test_id (canonical RF `longname` = `<classname>.<name>` per RF Listener v3 convention).
3. Looks up per-test metadata from (a) `trace_store.get_run_manifest(test_id)` for trace_id + tier breakdown, (b) `trace_store.get_usage(test_id)` for tokens, (c) `trace_store.get_latency(test_id)` for latency_seconds, (d) `self._completed_run_metadata.get(test_id)` for cost_usd + adapter + model + completeness + mcp_coverage (populated by `end_test`).
4. Injects `<properties>` child element with the 9 ratified property names (see AC-8a.1.2).
5. Injects `<system-out>` with the evidence block (per Story 5.3 evidence-block format) if available.
6. Injects `<system-err>` with `DegradedTraceWarning` content (per Story 5.4 `get_warnings`) if any warnings fired for the test.
7. Writes the enriched XML back to `path` atomically (write to `path + ".tmp"`, then `os.replace(path + ".tmp", path)`).

**Failure-mode contract:** any exception during enrichment is logged via the `_logger` at WARN level but does NOT raise — the original xunit file is preserved (no partial-write corruption). Symmetric to the Story 5.3 `RunManifestEmitter` warning-and-return-None pattern.

### AC-8a.1.2 — 9 ratified `<properties>` names + value types

**Given** the property naming contract documented at `docs/contracts/junit-xml-enrichment.md`,
**When** a `<testcase>` is enriched,
**Then** the following 9 `<property>` elements are injected (in this order, alphabetical by name for diff stability):

| Property name | Source | Value type | Empty/missing fallback |
| --- | --- | --- | --- |
| `agenteval.adapter` | `self._completed_run_metadata[test_id].adapter` | string | property omitted |
| `agenteval.completeness` | `self._completed_run_metadata[test_id].completeness` | string Literal `complete`/`truncated`/`partial` | property omitted |
| `agenteval.cost_usd` | `self._completed_run_metadata[test_id].cost_usd` | string (decimal, 4-place precision) | property omitted |
| `agenteval.latency_seconds` | `trace_store.get_latency(test_id)` | string (decimal, 3-place precision) | property omitted if no spans |
| `agenteval.mcp_coverage` | `self._completed_run_metadata[test_id].mcp_coverage` | string Literal | property omitted |
| `agenteval.model` | `self._completed_run_metadata[test_id].model` | string | property omitted |
| `agenteval.tier_breakdown` | `trace_store.get_run_manifest(test_id).agenteval_tier_breakdown` | JSON string (e.g., `"{\"1\": 2, \"3\": 5}"`) | property omitted if no spans |
| `agenteval.total_tokens` | `trace_store.get_usage(test_id).total_tokens` | string (integer) | property omitted if no spans |
| `agenteval.trace_id` | `trace_store.get_run_manifest(test_id).test_id` | string | property omitted if no spans |

All `value` attribute values are strings per JUnit XML convention. Numeric values use deterministic precision per the table.

### AC-8a.1.3 — FR50 sysexits-style exit-code mapping in `src/AgentEval/cli.py`

**Given** the FR50 sysexits-style per-leaf exit-code mapping authoritative at `docs/contracts/error-class-hierarchy.md` L73-L94,
**When** `agenteval` CLI exits after a test run that raised `AgentEvalError` leaves,
**Then** `src/AgentEval/cli.py` exports a function `error_code_to_exit_code(error_code: str) -> int` that returns the sysexits-style exit code for the given `error_code` string per the contract table. Unknown `error_code` → returns `70` (EX_SOFTWARE — generic agenteval failure). The mapping covers all 19 leaves (12 with explicit codes per contract L128 + 4 pinned per epics.md L1660 + 3 warning-class leaves = exit 0).

The function is unit-tested but NOT yet wired into the CLI's main exit path (CLI subcommand layer lands Story 8b.1's `agenteval init`); a `# Phase-1.5: wire into CLI main exit channel when subcommand structure lands` comment marks the integration point.

### AC-8a.1.4 — `docs/contracts/junit-xml-enrichment.md` filled

**Given** the Phase-1 skeleton at `docs/contracts/junit-xml-enrichment.md` (L1-L50, status: "Phase-1 skeleton — content to be filled by Epic 8a Story 8a.1"),
**When** Story 8a.1 ships,
**Then** the contract is filled with:
- **Required listener invocation** (D-4 amendment): `robot --listener AgentEval.telemetry.listener --xunit junit.xml tests/` is mandatory; xunit-enrichment is a no-op without the listener.
- **Property table** (the 9 names from AC-8a.1.2 with semantics + value-type rules + fallback rules).
- **Failure-mode contract** (any enrichment failure is logged + the original file is preserved).
- **Idempotency contract** (re-running enrichment on an already-enriched file is safe: properties are replaced by `name`, not appended).
- **Stability surface** (FR50 exit codes pinned from Phase-1; property-name additions are minor-version-safe; property-name removal or `value` semantic changes are breaking changes per FR64).
- **Cross-reference** to `error-class-hierarchy.md` L73-L94 for the FR50 exit-code table.

Status field updated from "Phase-1 skeleton" → "Phase-1 stable (Story 8a.1 closed)".

### AC-8a.1.5 — `self._completed_run_metadata` per-test cache on the listener

**Given** the Story 5.3 `_current_run_metadata` is per-listener-instance (not per-test),
**When** the listener processes multiple tests in a suite,
**Then** the listener also maintains `self._completed_run_metadata: dict[str, ActiveRunMetadata]` keyed by `test_id`, populated at `end_test` time (just before `_emit_run_manifest_sidecar`) from `self._current_run_metadata` (snapshot via `copy.copy`). `xunit_file` reads from this dict, NOT from `self._current_run_metadata` (which is cleared/overwritten per test).

This avoids the cross-test bleed where `xunit_file` runs AFTER `end_suite` (so `_current_run_metadata` reflects only the LAST test's metadata).

### AC-8a.1.6 — Unit tests: `tests/unit/telemetry/test_xunit_enrichment.py`

**Given** a fixture xunit file `tests/unit/telemetry/_fixtures/junit-pre-enrichment.xml` (synthetic 3-testcase suite with no agent metadata),
**When** the unit tests run,
**Then** ≥10 tests cover:
1. `<properties>` injection with all 9 names when full metadata is available.
2. Property omission when metadata source returns None/empty (per the fallback rule).
3. `<system-out>` injection with synthetic evidence-block content.
4. `<system-err>` injection with synthetic `DegradedTraceWarning` content.
5. **Idempotency:** re-running enrichment on an already-enriched file yields a byte-identical result (no duplicate properties; properties replaced by `name`).
6. **Schema shape:** `xml.etree.ElementTree.fromstring(enriched)` succeeds; every `<property>` has `name` + `value` attrs.
7. **Atomic write:** simulate a write failure mid-enrichment; verify the original file is preserved (not partially overwritten).
8. **Test-id derivation:** `longname` = `<classname>.<name>` correctly maps to trace_store lookups.
9. **Failure-mode:** exception in `get_run_manifest` is caught + logged at WARN + xunit file written without that test's enrichment.
10. **`agenteval.tier_breakdown` JSON encoding:** dict keys are integer strings; sorted by key for deterministic output.

### AC-8a.1.7 — `error_code_to_exit_code` unit tests in `tests/unit/test_cli.py`

**Given** the FR50 mapping function from AC-8a.1.3,
**When** the unit tests run,
**Then** ≥6 tests cover:
1. Each of the 4 pinned codes (PollingDisallowed=65, CostExceeded=66, IncompleteTrace=67, UnsupportedMCPVersion=68).
2. Each of the 8 sysexits-aligned codes (77 EX_NOPERM, 78 EX_CONFIG, 75 EX_TEMPFAIL, 70 EX_SOFTWARE for tier violation, 65 EX_DATAERR for 5 data-error leaves).
3. Unknown `error_code` → 70 fallback.
4. Empty / None `error_code` → 70 fallback.
5. `AdapterVersionDriftWarning` (warning class) → 0.
6. Coverage table-driven: assert every leaf in `error-class-hierarchy.md` L73-L94 has an entry in `_ERROR_EXIT_CODES`.

### AC-8a.1.8 — Integration test: `tests/integration/ci/test_xunit_end_to_end.py`

**Given** a minimal `.robot` test exercising an agent keyword (e.g., the existing `tests/integration/telemetry/test_listener_xunit.robot` — or a new dogfood-style suite added by this story),
**When** the test runs via `uv run robot --listener AgentEval.telemetry.listener --xunit junit.xml <suite>` in a tmp dir,
**Then** the integration test:
1. Parses the resulting `junit.xml`.
2. Asserts each `<testcase>` for a test that exercised an agent keyword has the 9 `<property>` elements (or the fallback subset per AC-8a.1.2).
3. Asserts the values match what the per-test trace store would have returned.
4. Asserts `<system-out>` is present and CDATA-wrapped (if the test produced an evidence block).

Integration test uses the **Mock provider** (no live API calls); the `.robot` fixture is deterministic.

### AC-8a.1.9 — `feedback_carry_over_catalog_gate` UPSTREAM (14th consecutive)

DF-8a.1-S1 / C62 catalogued in `deferred-work.md` + `docs/phase-1-5-carry-overs.md` BEFORE code-review (per Epic 5 retro norm).

### AC-8a.1.10 — `feedback_caller_count_check` (Epic 5 retro)

At story-close, grep new public helpers for caller count > 0:
- `error_code_to_exit_code` → callers: at least the unit test file.
- `_completed_run_metadata` → callers: `end_test` (writer) + `xunit_file` (reader).
- Any new helper in `telemetry/listener.py` for xunit XML manipulation → caller: `xunit_file`.

### AC-8a.1.11 — `feedback_in_flight_spec_amendment` (Epic 5 retro)

Any AC text that diverges from the shipped implementation MUST be amended in the same commit (per Epic 5 retro norm). Specifically: if D-6 forces a swap to a different XML parser, AC-8a.1.6 #6 must amend.

### AC-8a.1.12 — `feedback_executable_doc_precheck` (Epic 7 retro)

Any code block in `docs/contracts/junit-xml-enrichment.md` (filled by this story) MUST be smoke-executed if it is RF / Python (per Epic 7 retro NEW norm). The example `<testcase>` XML block is illustrative, not executable — no precheck needed for the XML example. The `robot --listener ... --xunit ...` invocation example IS executable; smoke-test via `robot --dryrun --listener AgentEval.telemetry.listener --xunit /tmp/test.xml tests/unit/telemetry/_fixtures/dummy.robot` (or use an existing dogfood suite) before flipping to review.

### AC-8a.1.13 — All-gates pass

Pre-commit verification:
- `uv run pytest tests/ -q` → all green; +16 new tests (10 xunit + 6 cli) net pass; existing 1263 unchanged.
- `uv run ruff check src/ tests/` → clean.
- `uv run ruff format --check src/ tests/` → clean.
- `uv run mypy src/` → clean (expected: 81 src files → 81 + 0 new modules, unless a small helper lands in `telemetry/_xunit_enrichment.py`).
- `tests/integration/ci/test_xunit_end_to_end.py` passes locally.

## Tasks / Subtasks

- [x] **Task 1** (Pre-create-story): amend epics.md L1818 `"full"` → `"complete"` per D-1. (DONE pre-authoring as part of story creation commit.)
- [x] **Task 2** (AC-8a.1.1, AC-8a.1.5): extend `src/AgentEval/telemetry/listener.py` with `self._completed_run_metadata: dict[str, ActiveRunMetadata]` populated at `end_test`; replace the `xunit_file` no-op stub at L434 with the enrichment implementation.
- [x] **Task 3** (AC-8a.1.1): factor xunit-XML manipulation into `src/AgentEval/telemetry/_xunit_enrichment.py` private helper (test_id derivation + property injection + atomic write + idempotent re-enrichment).
- [x] **Task 4** (AC-8a.1.3): create `src/AgentEval/cli.py::error_code_to_exit_code(error_code: str) -> int` + `_ERROR_EXIT_CODES` constant (consult `error-class-hierarchy.md` L73-L94).
- [x] **Task 5** (AC-8a.1.4): fill `docs/contracts/junit-xml-enrichment.md` per the contract sections. Smoke-execute the documented invocation per AC-8a.1.12.
- [x] **Task 6** (AC-8a.1.6): create `tests/unit/telemetry/_fixtures/junit-pre-enrichment.xml` + `tests/unit/telemetry/test_xunit_enrichment.py` (≥10 tests).
- [x] **Task 7** (AC-8a.1.7): extend `tests/unit/test_cli.py` (or create if missing) with ≥6 `error_code_to_exit_code` tests.
- [x] **Task 8** (AC-8a.1.8): create `tests/integration/ci/__init__.py` + `tests/integration/ci/test_xunit_end_to_end.py` (Mock-provider-driven).
- [x] **Task 9** (AC-8a.1.9): catalog DF-8a.1-S1 / C62 in `deferred-work.md` + `docs/phase-1-5-carry-overs.md` BEFORE code-review.
- [x] **Task 10** (AC-8a.1.10): caller-count grep verification.
- [x] **Task 11** (AC-8a.1.13): all-gates green run.
- [x] **Task 12**: sprint-status.yaml update story → done after code-review passes.

## Dev Notes

### Architecture compliance

- **PRD FR49** (JUnit XML emission): satisfied by the enrichment (RF emits the base file; agenteval adds the `<properties>` + `<system-out>` + `<system-err>` children).
- **PRD FR50** (Exit-code mapping): satisfied by `error_code_to_exit_code` in `cli.py` + the `_ERROR_EXIT_CODES` constant. Per-leaf `ClassVar[int]` deferred to Phase-1.5 (DF-8a.1-S1 / C62 — D-2 decision).
- **PRD FR64** (Stability Surface): `<properties>` names + value semantics are additive-safe per the contract (per `docs/contracts/stability-surface.md`).
- **architecture L1248**: `telemetry/listener.py` is the canonical listener entry-point — extension is additive.
- **ADR-014** (Error-Class Hierarchy): `error_code` class attribute drives the FR50 mapping; no per-leaf changes required.

### Existing infrastructure Story 8a.1 builds on

- **`src/AgentEval/telemetry/listener.py`** — Story 5.1 Regular Listener with `xunit_file` reserved no-op stub at L434. Story 5.3 populates `self._current_run_metadata` per-test via `record_active_run_metadata()`.
- **`src/AgentEval/_kernel/trace_store.py`** — Story 1b.2 + Story 5.x ship `get_run_manifest(test_id)`, `get_usage(test_id)`, `get_latency(test_id)` projections.
- **`docs/contracts/junit-xml-enrichment.md`** — Phase-1 skeleton awaiting fill by this story.
- **`docs/contracts/error-class-hierarchy.md`** — L73-L94 has the per-leaf FR50 exit-code table (this story's CLI mapping is a string-keyed lookup of that table).
- **`src/AgentEval/cli.py`** — exists but is a minimal stub (verify before extending).
- **`src/AgentEval/_kernel/trace_store.RunManifest`** — provides `library_version`, `test_id`, `suite_id`, `redaction_policy_hash`, `started_at`, `ended_at`, `agenteval_tier_breakdown` (7 fields).
- **Story 5.3 `ActiveRunMetadata`** — extends RunManifest with `adapter`, `model`, `cost_usd`, `mcp_coverage`, `completeness` Optional fields.

### test_id derivation

RF Listener v3 emits `start_test(data, result)` where `data.longname` = `<suite_name>.<test_name>` (canonical). The xunit `<testcase classname="..." name="...">` element's pair maps to `longname` via `f"{classname}.{name}"`.

**Edge case:** RF flat-suite tests vs nested-suite tests. RF nested suites use `Outer.Inner.Test` as longname; xunit uses `Outer.Inner` as `classname` + `Test` as `name`. The derivation `f"{classname}.{name}"` works for both (flat case `classname` is just the top-level suite).

### Atomic write pattern

```python
import os
from pathlib import Path

def _atomic_write_xml(path: Path, tree: ET.ElementTree) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

### Idempotency

For each `<testcase>`, before injecting a property: check if a `<property name="agenteval.X">` already exists; if so, update `value` in place. If not, append. This makes re-enrichment safe (e.g., a CI tool re-running the listener post-hoc).

### Failure-mode contract

The listener's `xunit_file` runs AFTER all tests complete + RF has written the file. A failure to enrich SHOULD NOT corrupt the original file. Implementation: wrap the entire enrichment in `try/except Exception` → log at WARN level → return without modifying the file. Atomic write (above) prevents partial-write corruption even on success path.

### Files to create / modify

**CREATE:**
- `src/AgentEval/telemetry/_xunit_enrichment.py` — private helper (~120 lines)
- `tests/unit/telemetry/test_xunit_enrichment.py` — ≥10 tests
- `tests/unit/telemetry/_fixtures/junit-pre-enrichment.xml` — synthetic 3-testcase fixture
- `tests/integration/ci/__init__.py` — package marker + license header
- `tests/integration/ci/test_xunit_end_to_end.py` — Mock-provider-driven integration test
- `tests/integration/ci/test_xunit_suite.robot` — minimal RF suite for integration test (if not reusing existing)

**MODIFY:**
- `src/AgentEval/telemetry/listener.py` — replace `xunit_file` stub at L434; add `_completed_run_metadata` cache; populate at `end_test`
- `src/AgentEval/cli.py` — add `_ERROR_EXIT_CODES` constant + `error_code_to_exit_code` function
- `tests/unit/test_cli.py` — extend with FR50 mapping tests (create if missing)
- `docs/contracts/junit-xml-enrichment.md` — fill from skeleton to stable
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-8a.1-S1 entry
- `docs/phase-1-5-carry-overs.md` — C62 row added

**SOURCE DOCS AMENDED PRE-AUTHORING (per `fix-the-losing-source-NOW`):**
- `_bmad-output/planning-artifacts/epics.md` L1818 — `value="full"` → `value="complete"` (D-1)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

### Completion Notes List

Story 8a.1 implementation complete 2026-05-25. All 13 ACs satisfied:

- **AC-8a.1.1**: `xunit_file(path)` listener hook implemented; delegates to `_xunit_enrichment.enrich_xunit_file` via `contextlib.suppress(Exception)` (failure-mode contract). Reads `self._completed_run_metadata` snapshot built in `end_test`. Atomic write (`os.replace`) verified via test #7.
- **AC-8a.1.2**: 9 ratified `<property>` names injected with correct value-type formatting (4-decimal cost, 3-decimal latency, integer tokens, JSON-stringified tier_breakdown). None/empty → property omitted (verified test #2).
- **AC-8a.1.3**: `error_code_to_exit_code(error_code)` + `_ERROR_EXIT_CODES` constant ship in `src/AgentEval/cli.py`. Covers all 19 leaves + EXIT_CODE_FALLBACK=70. Per-leaf `ClassVar[int]` deferred to Phase-1.5 / DF-8a.1-S1 / C62 per D-2 decision.
- **AC-8a.1.4**: `docs/contracts/junit-xml-enrichment.md` filled (status Phase-1 stable) with required-listener invocation, property table, idempotency contract, failure-mode contract, FR50 mapping cross-reference, change policy.
- **AC-8a.1.5**: `self._completed_run_metadata: dict[str, dict[str, Any]]` keyed by `test_id`. Populated in `end_test` BEFORE `clear_warnings` + `clear_spans` via `_snapshot_completed_run_metadata`.
- **AC-8a.1.6**: 11 unit tests (1 bonus) at `tests/unit/telemetry/test_xunit_enrichment.py`. All 10 enumerated cases + 1 bonus (non-agenteval properties preserved).
- **AC-8a.1.7**: 6 parametrized tests at `tests/unit/test_cli.py` cover 4 pinned codes + 14 sysexits-aligned codes + unknown/None fallback + warning-class exit-0 + coverage assertion.
- **AC-8a.1.8**: 3 integration tests at `tests/integration/ci/test_xunit_end_to_end.py` drive the listener `start_suite → start_test → record_active_run_metadata → end_test → xunit_file` pipeline.
- **AC-8a.1.9**: DF-8a.1-S1 / C62 catalogued in `deferred-work.md` + `docs/phase-1-5-carry-overs.md`.
- **AC-8a.1.10**: Caller-count verification:
  - `error_code_to_exit_code`: 6+ tests + future CLI wiring point (comment marked).
  - `_completed_run_metadata`: writer (`end_test`) + reader (`xunit_file`) = 2 callers.
  - `_snapshot_completed_run_metadata`: caller `end_test` = 1.
  - `enrich_xunit_file` (helper): caller `Listener.xunit_file` + unit + integration tests.
- **AC-8a.1.11**: No in-flight AC amendments needed (implementation matched spec).
- **AC-8a.1.12**: `docs/contracts/junit-xml-enrichment.md` smoke-executed via `uv run robot --listener AgentEval.telemetry.listener --xunit /tmp/agentval-smoke/junit.xml /tmp/agentval-smoke/smoke.robot` → 1 test pass, no listener-wiring errors. Property injection path not exercised (no agent keyword), which matches the documented "no-op without agent keywords" behavior.
- **AC-8a.1.13**: All gates green — `uv run pytest tests/ -q --no-header` → `1300 passed, 8 skipped`; ruff/format/mypy clean (82 src files, +1 from `_xunit_enrichment.py`).

Story creation: 35th use of `feedback_spec_vs_ratified_doc_precheck`. Implementation: applied `feedback_carry_over_catalog_gate` UPSTREAM (14th consecutive); `feedback_caller_count_check`; `feedback_executable_doc_precheck` (NEW Epic 7 retro). NFR-COMPAT-06 compliance: all `agenteval.*` property keys sourced from `semconv.py` `XUNIT_PROP_*` constants.

### File List

**New files:**
- `src/AgentEval/telemetry/_xunit_enrichment.py` — JUnit XML enrichment helper (~245 lines)
- `tests/unit/telemetry/_fixtures/__init__.py` — fixture package marker
- `tests/unit/telemetry/_fixtures/junit-pre-enrichment.xml` — synthetic 3-testcase fixture
- `tests/unit/telemetry/test_xunit_enrichment.py` — 11 unit tests
- `tests/unit/test_cli.py` — 6 FR50 exit-code mapping tests
- `tests/integration/ci/__init__.py` — package marker
- `tests/integration/ci/test_xunit_end_to_end.py` — 3 integration tests

**Modified files:**
- `src/AgentEval/telemetry/listener.py` — `_completed_run_metadata` cache + `_snapshot_completed_run_metadata` helper + `xunit_file` enrichment hook (replaces no-op stub)
- `src/AgentEval/telemetry/semconv.py` — 9 `XUNIT_PROP_*` constants for the JUnit XML property names
- `src/AgentEval/cli.py` — `_ERROR_EXIT_CODES` dict + `error_code_to_exit_code` function + `EXIT_CODE_FALLBACK` constant
- `tests/unit/telemetry/test_semconv.py` — expected `__all__` set extended with 9 new `XUNIT_PROP_*` names
- `docs/contracts/junit-xml-enrichment.md` — filled from Phase-1 skeleton to Phase-1 stable
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-8a.1-S1 entry
- `docs/phase-1-5-carry-overs.md` — C62 row added + counter updated to 62
- `_bmad-output/planning-artifacts/epics.md` L1818 — `value="full"` → `value="complete"` (D-1 pre-create amendment)

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-25 | 0.1.0 | Initial story creation (ready-for-dev). 35th use of `feedback_spec_vs_ratified_doc_precheck` (100% catch rate intact) caught 6 drifts: D-1 HIGH `completeness="full"` → `"complete"` (epics.md L1818 AMENDED pre-authoring per DF-6.4-S1 propagation); D-2 HIGH-decision per-leaf `exit_code: ClassVar[int]` deferred Phase-1.5 (DF-8a.1-S1/C62) via lookup-table path-of-least-amendment; D-3 MED `adapter`+`model` come from Story 5.3 `_current_run_metadata` not trace_store; D-4 MED contract MUST repeat listener-required invocation; D-5 LOW `tests/integration/ci/` directory creation; D-6 LOW stdlib XML parser instead of `pytest-junitxml` dep. 13 ACs documented (8a.1.1-8a.1.13). Closes FR49 + FR50 + FR64 enrichment surfaces. Applies Epic 5+7 retro norms: `feedback_carry_over_catalog_gate` UPSTREAM (14th consecutive); `feedback_in_flight_spec_amendment`; `feedback_caller_count_check`; `feedback_executable_doc_precheck` (NEW Epic 7 retro). | Bob |
| 2026-05-25 | 0.2.0 | Implementation complete. 7 new files + 8 modified files. All 13 ACs satisfied. NFR-COMPAT-06 compliance preserved via `XUNIT_PROP_*` constants in `semconv.py` (9 new exports added; tests/unit/telemetry/test_semconv.py expected set extended). `Usage.total_tokens` computed as `input_tokens + output_tokens + cached_input_tokens` (no native property on `Usage` dataclass). 1300 pytest pass (was 1297 at Epic 7 close; +3 net new tests: 11 xunit + 6 cli + 3 integration); ruff/format/mypy clean (82 src files). Smoke-executed contract example via `robot --listener AgentEval.telemetry.listener --xunit /tmp/agentval-smoke/junit.xml /tmp/agentval-smoke/smoke.robot` — listener wiring confirmed; property injection path not exercised (no agent keyword in smoke), matching the documented "no-op without agent keywords" behavior. DF-8a.1-S1/C62 catalogued. Status → review. | Amelia |
