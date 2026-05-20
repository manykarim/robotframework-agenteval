# Story 5.4: DegradedTraceWarning + Get Last Warnings + Per-Test Scope Polish

Status: done

## Story

As **Raj (Agent Developer)** or **Priya (QA Engineer)**,
I want **typed `DegradedTraceWarning` events** emitted on every mid-run trace-quality degradation (replacing the Story 5.1/5.3 `UserWarning` placeholders), a **`WarningRecord` collector** that captures every degradation into a per-test buffer wired into the existing `RunManifest.warnings` field (currently always empty), the **`Get Last Warnings` keyword** (FR62) for programmatic warning inspection from `.robot` tests, and **per-test MCP scope polish** verifying AC-MCP-OBSERVE-03 holds under `pabot --processes 4`,
So that I get loud, typed, structured signals when trace quality degrades — instead of silently passing tests with degraded evidence — and downstream consumers can filter / route `DegradedTraceWarning` events distinctly from generic Python warnings.

## Pre-create-story drift check (25th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

**5 drifts caught + resolved pre-authoring** (per fix-the-losing-source-NOW pattern + Epic 4 retro `feedback_n_way_agreement_weight` extension: Auditor 1-way HIGHs on PRD/ADR re-derivation now **9+ consecutive TPs across 6 epics**):

- **(D-1 HIGH)** **PRD FR61 `mcp_coverage="partial"` value drift.** PRD L1592 said the warning trigger sets `mcp_coverage` to `"partial"`. But ADR-016 D1 ratification 2026-05-17 (Story 5.2 scope) defined `mcp_coverage` as a **3-state Literal `{"hosted_in_process", "subprocess_with_observer", "external_mixed"}`** with NO `"partial"` value. Architecture L384 echoed the same drift. `errors.py:806` (the `DegradedTraceWarning` docstring) also referenced `mcp_coverage="partial"`. **Resolution**: PRD FR61 amended pre-authoring to drop the `"partial"` value — FR61 now triggers `DegradedTraceWarning` on the broader class of recoverable mid-run degradation events (observer connection drop, JSONL write failure, RunManifest emit failure, novel redaction pattern, missing required span attributes) and — IF the degradation invalidates server-side observation coverage — the run's `mcp_coverage` falls to `"external_mixed"` per ADR-016 degradation rules. Architecture L384 + errors.py:806 both amended in lockstep.

- **(D-2 MED-HIGH)** **`Get Last Warnings` field-set drift PRD-vs-epics.** PRD FR62 specified warning fields as `source + message + remediation`. Epics.md Story 5.4 AC specified `warning_type + message + timestamp + severity`. These two lists overlap on `message` but otherwise diverge. **Resolution**: ratified a unified **5-field `WarningRecord`** combining both sources: `warning_type` (str, Python class name), `message` (str, human text), `source` (str, emitting subsystem), `timestamp` (datetime, UTC RFC 3339), `remediation` (str | None, actionable advice). `severity` from the epics draft is dropped — it's implicit in the warning class hierarchy (`DegradedTraceWarning` < `AdapterVersionDriftWarning` ≤ other UserWarning subclasses). PRD FR62 + epics.md Story 5.4 AC both amended in lockstep.

- **(D-3 MED)** **"all 4 mcp_coverage values" drift in epics.md Story 5.4 AC.** Epics.md L1532 said integration tests cover "all 4 `mcp_coverage` values" — but ADR-016 D1 ratification defined a 3-state Literal. Real drift (latent from pre-ADR-016 draft). **Resolution**: amended to "all 3 `mcp_coverage` values (`hosted_in_process`, `subprocess_with_observer`, `external_mixed`)" pre-authoring.

- **(D-4 carry-over LOW, deferred not blocking)** **PRD L1614 NFR-PERF-03d `mcp_coverage="library_only"` drift.** PRD L1614 (NFR-PERF-03d `mcp_per_test="suite"` mode) still references `mcp_coverage="library_only"` — superseded by `hosted_in_process` per ADR-016 D1 (see ADR-016 L58). Out of Story 5.4 scope (NFR-PERF-03d is Phase-1.5+ `mcp_per_test="suite"` mode work). **Resolution**: added DF-5.4-S1 to deferred-work.md + C39 to phase-1-5-carry-overs.md catalog — fix PRD L1614 in lockstep with Story 6.x or whichever story first implements `mcp_per_test="suite"` mode.

- **(D-5 carry-over MED, deferred not blocking)** **Existing `DegradedTraceWarning` class shape is bare.** `AgentEval.errors.DegradedTraceWarning` (declared 1b.4 / earlier, used at 3 sites in `trace_store.py`) is just `class DegradedTraceWarning(UserWarning)` with a docstring — it has no constructor accepting the `WarningRecord` 5 fields. Story 5.4 needs both: (a) the `WarningRecord` dataclass + per-test buffer in `_kernel/warnings.py`, AND (b) the existing `warnings.warn(msg, DegradedTraceWarning, stacklevel=2)` call sites continue to fire AND a parallel `_kernel/warnings.record_warning(...)` API captures the structured 5-field record. The `warnings.warn` channel preserves Python's filterwarnings / `-W error::AgentEval.errors.DegradedTraceWarning` behavior; the `_kernel/warnings.record_warning` channel feeds the per-test buffer + `RunManifest.warnings` + `Get Last Warnings` keyword. **NOT** a constructor change to `DegradedTraceWarning` (that would break existing `warnings.warn(..., DegradedTraceWarning)` calls). Two parallel channels — same emit site emits to both.

## Acceptance Criteria

### AC-5.4.1 — `WarningRecord` dataclass + `_kernel/warnings.py` module

**Given** the existing `DegradedTraceWarning` Python warning class at `src/AgentEval/errors.py:790` (declared earlier, used at 3 sites in `_kernel/trace_store.py` + 2 sites in `mcp/observer.py` + 3 sites in `telemetry/{listener,backends,run_manifest}.py`),
**When** Story 5.4 introduces the structured per-test warning collector,
**Then** a new module `src/AgentEval/_kernel/warnings.py` ships:

- **`WarningRecord` frozen dataclass** with exactly these 5 fields per FR62 ratified shape (2026-05-20 ratification unifying PRD `source + message + remediation` with the test-author-required `warning_type + timestamp`):
  - `warning_type: str` — fully-qualified Python warning class name (e.g., `"AgentEval.errors.DegradedTraceWarning"`, `"AgentEval.mcp.observer.AdapterVersionDriftWarning"`).
  - `message: str` — the human-readable warning text passed to `warnings.warn()`.
  - `source: str` — the emitting subsystem identifier (e.g., `"telemetry.listener"`, `"telemetry.run_manifest"`, `"telemetry.backends.jsonl"`, `"mcp.observer"`, `"_kernel.trace_store"`, `"_kernel.redaction"`).
  - `timestamp: datetime` — UTC RFC 3339, set at `record_warning()` call time via `datetime.now(timezone.utc)`.
  - `remediation: str | None` — actionable advice for the test author; `None` when no remediation is known. Examples: `"Inspect <output_dir>/agenteval/manifest__...json to verify operational metadata captured"`, `"Re-run with AGENTEVAL_TRACE_BACKEND=memory to bypass JSONL write failure"`.

- **Per-test buffer**: module-level `_warning_buffers: dict[str, list[WarningRecord]]` keyed by `test_id` (mirroring `_kernel/trace_store._spans_by_test`'s pattern at trace_store.py:74). Cleared by `clear_warnings(test_id)` invoked from `Listener.end_test` AFTER manifest emit but BEFORE `_kernel_context.unbind_context()`.

- **`record_warning(*, warning_type, message, source, remediation=None) -> None` API**: builds a `WarningRecord` with `timestamp=now(UTC)` + appends to the buffer keyed by `_kernel_context.current_test_id()` (or `_PRE_TEST_BUFFER` sentinel if no test is bound — flushed to the next bound test or discarded at `start_suite`).

- **`get_warnings(test_id: str = "current") -> list[WarningRecord]` API**: returns the list for the named test (or all-suite when `test_id="all"`). Returns a defensive copy (per Story 1b.2 M_R6 pattern).

- **`clear_warnings(test_id: str | None = None) -> int` API**: removes the entry for one test (or all when `None`). Returns the number of `WarningRecord` instances removed.

- **`__all__`** exports: `WarningRecord`, `record_warning`, `get_warnings`, `clear_warnings`.

- License header per Story 1a.1 convention.

### AC-5.4.2 — Telemetry emit-site upgrade (`UserWarning` → `DegradedTraceWarning` + structured record)

**Given** the 3 telemetry-emit-path `UserWarning` sites Story 5.1 + 5.3 left as forward-refs (DF-5.1-S1 + DF-5.3-S1 in C32):
- `src/AgentEval/telemetry/backends.py:163-169` — JSONL write failure.
- `src/AgentEval/telemetry/listener.py:342-348` — missing test full_name on start_test.
- `src/AgentEval/telemetry/listener.py:585-591` — unknown trace_backend value.
- `src/AgentEval/telemetry/run_manifest.py:135-141` — manifest sidecar write failure.

**When** Story 5.4 lands `DegradedTraceWarning`,
**Then** each site is converted from `warnings.warn(msg, UserWarning, stacklevel=2)` to a dual-channel pattern:
```python
from AgentEval._kernel.warnings import record_warning
from AgentEval.errors import DegradedTraceWarning

warnings.warn(msg, DegradedTraceWarning, stacklevel=2)  # preserves -W error filter behavior
record_warning(
    warning_type="AgentEval.errors.DegradedTraceWarning",
    message=msg,
    source="telemetry.backends.jsonl",  # site-specific
    remediation="...",  # site-specific
)
```

The `(DF-5.1-S1 upgrade ... when Story 5.4 lands)` and `(DF-5.3-S1 upgrade ... when Story 5.4 lands)` parenthetical hints are stripped from the warning messages at the same time.

### AC-5.4.3 — Coverage degradation auto-warn on `mark_external_mixed` flow

**Given** `HostedMcpObserver.mark_external_mixed(reason)` (Story 5.2 scope per ADR-016) — the load-bearing "coverage degraded" signal,
**When** an adapter calls `mark_external_mixed("...")` AND the run was on a hosted-in-process path (i.e., the observer had observed ≥1 tool call before the degradation),
**Then** the observer ALSO calls `record_warning(warning_type="AgentEval.errors.DegradedTraceWarning", message=f"hosted-MCP observation degraded mid-run: {reason}; mcp_coverage falls to external_mixed", source="mcp.observer", remediation="Inspect AgentRunResult.metadata.observed_paths to identify the failing MCP path")` so a `Get Last Warnings test_id=current` call surfaces the degradation event. This is the canonical FR61 trigger — every other emit site is a secondary degradation signal (backend write failure, missing attributes) that does not change `mcp_coverage`.

### AC-5.4.4 — RunManifest `warnings` field populated from buffer at sidecar emit

**Given** Story 5.3's `RunManifest.warnings: list[str] = field(default_factory=list)` (Story 5.4 forward-ref placeholder),
**When** `Listener._emit_run_manifest_sidecar` builds the extended manifest (`listener.py:445`),
**Then** the listener AMENDS the `warnings` field — before `dataclasses.replace(base_manifest, **filtered)` — by reading the per-test warning buffer:
```python
from AgentEval._kernel import warnings as _agenteval_warnings

records = _agenteval_warnings.get_warnings(test_id)
# Serialize each WarningRecord to its 5-field dict (datetime → isoformat string)
# Store on accumulated["warnings"] BEFORE dataclasses.replace
accumulated["warnings"] = [_warning_record_to_dict(r) for r in records]
```

The `RunManifest.warnings` field's TYPE SHIFTS from `list[str]` (Story 5.3 placeholder, never populated) to `list[dict[str, Any]]` (5-field WarningRecord dicts). This is a **non-breaking widening** of the field's runtime shape — Story 5.3's emitter never populated the field beyond `[]`, so no consumer relies on the `list[str]` shape. The type annotation on `types.RunManifest.warnings` is updated accordingly. JSON Schema (`docs/contracts/run-manifest-schema.json`) `warnings` property is updated from `array of string` to `array of object` with the 5-field `WarningRecord` shape.

### AC-5.4.5 — `Get Last Warnings` keyword surface (FR62)

**Given** the RF DynamicCore composition pattern Phase-1 uses for the public library surface (see `src/AgentEval/AgentEval.py` + sub-library `__init__.py` discipline per Story 2.1),
**When** Story 5.4 adds the `Get Last Warnings` keyword,
**Then** a new file `src/AgentEval/telemetry/_keywords.py` (or extend the existing `telemetry/__init__.py` carefully — but per Story 2.1 norm the `__init__.py` files contain ONLY module docstrings + NO re-exports, so the keyword lives in `_keywords.py`) ships:

- A `@keyword` decorated function `get_last_warnings(test_id: str = "current") -> list[dict[str, Any]]` that wraps `_kernel/warnings.get_warnings()`:
  - `test_id="current"` (default) — looks up the current bound test via `_kernel_context.current_context().test_id` (Story 5.4 code-review Auditor MED-6 fix 2026-05-20: spec working name `current_test_id()` was non-existent; the canonical API is `current_context().test_id`); returns `[]` if no test is bound.
  - `test_id="all"` — returns the union across all per-test buffers (sorted by `timestamp` ascending).
  - `test_id="<specific-id>"` — returns the named test's buffer; returns `[]` if no records.

- Each `WarningRecord` is serialized to a dict with 5 keys (matching `RunManifest.warnings` shape from AC-5.4.4): `warning_type`, `message`, `source`, `timestamp` (ISO 8601 string), `remediation` (string or `None`).

- The keyword is registered through whichever DynamicCore composition path `Listener`-companion keywords use — verified by reading `src/AgentEval/AgentEval.py` `_SUB_LIBRARIES` registration during dev.

- `@tier(1)` annotation per `_kernel.tier` (introspection — Tier-1 read-only keyword that doesn't fan out, no cost guardrail).

### AC-5.4.6 — Per-test scope polish: warnings buffer follows `_kernel_context.current_test_id()`

**Given** AC-MCP-OBSERVE-03 (per-test MCP scope) + Story 5.1's `_kernel_context.set_current_test_id()` mechanism,
**When** Story 5.4 wires the warnings buffer,
**Then**:
- `_kernel/warnings.record_warning(...)` reads `_kernel_context.current_test_id()` and keys the buffer by that test_id.
- When the buffer key is `None` (no test bound, e.g., suite-level redaction-config warnings emitted during `start_suite`), records go into a `_PRE_TEST_BUFFER` sentinel keyed by `"__suite__"`. These are MERGED into the FIRST per-test buffer at `Listener.start_test` (so warnings emitted during library bootstrap surface in the first test's `Get Last Warnings` output). The merge is one-way (`__suite__` → first test); `__suite__` is cleared after merge.
- `Listener.end_test` calls `_kernel.warnings.clear_warnings(test_id)` AFTER `_emit_run_manifest_sidecar` (so the manifest captures the warnings) BUT BEFORE `_kernel_context.unbind_context()` (so the keyed buffer is cleanly removed under the test's context).
- Under `pabot --processes 4` parallel test execution, warning buffers do NOT leak across processes (each process has its own `_warning_buffers` module-level dict — same isolation pattern as `_kernel/trace_store._spans_by_test`).

### AC-5.4.7 — Integration tests at `tests/integration/telemetry/test_warnings.py`

**Given** all 3 `mcp_coverage` values per ADR-016 (`hosted_in_process`, `subprocess_with_observer`, `external_mixed`),
**When** Story 5.4 ships integration tests,
**Then** the new file `tests/integration/telemetry/test_warnings.py` covers:

- **`test_e2e_get_last_warnings_returns_empty_list_when_no_degradation`** — happy-path agent run with hosted-in-process MCP, no degradation → `get_last_warnings("current")` returns `[]`.
- **`test_e2e_get_last_warnings_captures_mark_external_mixed_event`** — adapter forces `observer.mark_external_mixed("subprocess MCP detected post-hosted-call")` → `get_last_warnings("current")` returns 1 `WarningRecord` with `source="mcp.observer"` + `remediation` populated + `mcp_coverage` is `"external_mixed"` post-emit. Covers FR61 canonical trigger (AC-5.4.3).
- **`test_e2e_get_last_warnings_captures_jsonl_write_failure`** — monkeypatch JSONL write to raise `OSError` → `get_last_warnings("current")` returns 1 `WarningRecord` with `source="telemetry.backends.jsonl"`. Test outcome NOT raised (AC-5.3.2 "failures don't mask test outcomes" preserved).
- **`test_e2e_runmanifest_warnings_field_populated_with_warning_records`** — adapter forces degradation → reads sidecar JSON → asserts `payload["warnings"]` is a list of 5-key dicts (NOT list of strings).
- **`test_e2e_pabot_parallel_isolation_no_warning_cross_pollution`** — spawn 2 simulated tests (sequentially in one process — pabot orchestrates processes which is a different concern; this test verifies the **per-test buffer keying** holds even when tests run back-to-back) where Test A triggers a warning + Test B does NOT trigger a warning → `get_last_warnings(test_id="A")` returns 1 record, `get_last_warnings(test_id="B")` returns 0. AC-MCP-OBSERVE-03 polish coverage.
- **`test_e2e_get_last_warnings_test_id_all_merges_across_tests`** — Test A triggers warning W1, Test B triggers warning W2 → `get_last_warnings("all")` returns `[W1, W2]` sorted by timestamp ascending.
- **`test_e2e_pre_test_buffer_merges_into_first_test`** — emit a warning at `start_suite` time (before any `start_test`) → first `start_test` merges it into the test's buffer → `get_last_warnings("current")` from inside that test returns the suite-level record.
- **`test_e2e_warnings_buffer_cleared_at_end_test`** — verify `clear_warnings(test_id)` fires in `end_test` → spawn Test A with warning → `end_test` runs → after that, `get_warnings("A")` returns `[]` (the buffer is cleaned up; the persisted record is in the sidecar JSON, not in the live buffer).

All 8 tests use `monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))` to isolate the sidecar emit to tmp_path per Story 5.3 close-out test-isolation norm.

### AC-5.4.8 — Unit tests at `tests/unit/_kernel/test_warnings.py` + `tests/unit/telemetry/test_get_last_warnings.py`

**Given** the new `_kernel/warnings.py` module + the new `get_last_warnings` keyword,
**When** Story 5.4 ships unit tests,
**Then**:

- **`tests/unit/kernel/test_warnings.py`** — 6 unit tests covering: `WarningRecord` frozen-dataclass immutability (Story 5.4 code-review Auditor HIGH-3 fix 2026-05-20: pre-edit claimed "defensive-copy on `__init__`" but `WarningRecord` has no mutable nested fields — `frozen=True` is the right invariant + the only one practically testable), `record_warning` keys-by-current-test-id, `get_warnings` defensive-copy on return, `clear_warnings(None)` removes all, `clear_warnings(test_id)` removes one, `_PRE_TEST_BUFFER_KEY` flush behavior. Path is `tests/unit/kernel/` (no underscore) matching the existing `test_context.py` location convention.
- **`tests/unit/telemetry/test_get_last_warnings.py`** — 4 unit tests covering: `get_last_warnings("current")` happy-path, `get_last_warnings("all")` happy-path + sort order, `get_last_warnings("unknown-test")` returns `[]`, `WarningRecord.timestamp` is RFC 3339 UTC string in the dict form.

### AC-5.4.9 — `docs/contracts/run-manifest-schema.json` updated for new `warnings` shape

**Given** Story 5.3's JSON Schema at `docs/contracts/run-manifest-schema.json` with `warnings` defined as `{"type": "array", "items": {"type": "string"}}` (placeholder),
**When** Story 5.4 lands the new `WarningRecord` shape,
**Then** the schema is updated to:
```json
"warnings": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["warning_type", "message", "source", "timestamp"],
    "properties": {
      "warning_type": {"type": "string", "minLength": 1},
      "message": {"type": "string", "minLength": 1},
      "source": {"type": "string", "minLength": 1},
      "timestamp": {"type": "string", "format": "date-time"},
      "remediation": {"type": ["string", "null"]}
    },
    "additionalProperties": false
  }
}
```
Schema version comment in the file's `$id` / `description` field bumped to note "v1.1: 2026-05-20 Story 5.4 — warnings field shape ratified".

### AC-5.4.10 — `src/AgentEval/types.py` `RunManifest.warnings` field type updated

**Given** `RunManifest.warnings: list[str] = field(default_factory=list)` at `src/AgentEval/types.py` (Story 5.3 placeholder),
**When** Story 5.4 lands the structured `WarningRecord`,
**Then** the field becomes `warnings: list[dict[str, Any]] = field(default_factory=list)` (typed as `list[dict[str, Any]]` rather than `list[WarningRecord]` because `types.py` cannot import from `_kernel/warnings.py` without creating a circular dep — `types.py` is upstream of `_kernel`). A docstring note above the field documents the WarningRecord 5-key shape + cross-references `_kernel/warnings.WarningRecord`. `__post_init__` defensive-copy continues to apply.

### AC-5.4.11 — `__init__.py` re-export discipline preserved (Story 2.1 norm)

**Given** the Story 2.1 ratified norm that sub-library `__init__.py` files contain ONLY module docstrings — NO re-exports,
**When** Story 5.4 introduces `_kernel/warnings.py` + `telemetry/_keywords.py`,
**Then** neither `_kernel/__init__.py` nor `telemetry/__init__.py` gain new re-export lines. Callers import explicitly: `from AgentEval._kernel.warnings import record_warning` + `from AgentEval.telemetry._keywords import get_last_warnings`. The DynamicCore wiring at `src/AgentEval/AgentEval.py` is the ONLY path that surfaces `get_last_warnings` as a public RF keyword.

## Tasks / Subtasks

- [x] **Task 1: `src/AgentEval/_kernel/warnings.py`** — new module with `WarningRecord` frozen dataclass + `_warning_buffers` module-level dict + `_PRE_TEST_BUFFER_KEY="__suite__"` sentinel + `record_warning` / `get_warnings` / `clear_warnings` / `flush_pre_test_buffer` / `warning_record_to_dict` APIs. License header present. All 5 APIs swallow internal errors via `contextlib.suppress(Exception)` per AC-5.4.1 failure-mode contract. 6 unit tests at `tests/unit/kernel/test_warnings.py` cover: frozen-dataclass invariant, current-test-id keying, defensive-copy on return, clear_warnings(None) wiping all, clear_warnings(test_id) removing one, pre-test-sentinel flush.
- [x] **Task 2: Telemetry emit-site upgrade** — converted all 4 UserWarning sites to dual-channel `DegradedTraceWarning` + `record_warning(...)` pattern: (1) `backends.py:163` JSONL write failure — source `telemetry.backends.jsonl`; (2) `listener.py:342` missing test full_name — source `telemetry.listener`; (3) `listener.py:585` unknown trace_backend — source `telemetry.listener`; (4) `run_manifest.py:135` manifest write failure — source `telemetry.run_manifest`. All sites stripped the DF-5.1-S1 / DF-5.3-S1 forward-ref hints + populated site-specific `remediation` strings. Per AC-5.4.2.
- [x] **Task 3: Coverage-degradation auto-warn** — extended `HostedMcpObserver.mark_external_mixed(reason)` at `src/AgentEval/mcp/observer.py:219` to read `len(self._state.tool_calls) >= 1` BEFORE appending the reason (so the snapshot of "prior observation" is captured pre-degradation). When prior observation existed, emits dual-channel `DegradedTraceWarning` (Python channel) + `record_warning(source="mcp.observer", remediation=...)` (structured channel). When no observation existed (e.g., adapter pre-flight external-config detection), the call is silent — no observation to degrade. Per AC-5.4.3 canonical FR61 trigger.
- [x] **Task 4: `Listener._emit_run_manifest_sidecar` reads warnings buffer** — amended `accumulated` dict assembly inside `_emit_run_manifest_sidecar` (listener.py:489+) to read `get_warnings(test_id)` + serialize via `warning_record_to_dict` BEFORE the `dataclasses.replace` call. Best-effort wrapped in `try/except` so a buffer read failure falls back to empty list (Story 5.3 default). Per AC-5.4.4.
- [x] **Task 5: `Listener.end_test` calls `clear_warnings` AFTER manifest emit** — sequence honored at listener.py:405-415: `_emit_run_manifest_sidecar` → `_agenteval_warnings.clear_warnings(test_id)` → `trace_store.clear_spans(test_id)` → `_kernel_context.unbind_context()`. Also added `flush_pre_test_buffer(test_id)` call at `start_test` immediately after `set_current_test_id` so suite-level warnings surface in the first test's buffer. Per AC-5.4.6.
- [x] **Task 6: `src/AgentEval/telemetry/library.py`** — new module exposing `TelemetryLibrary.get_last_warnings(test_id="current")` `@keyword(name="Get Last Warnings")` + `@tier(1)`. Returns list of 5-key dicts via `warning_record_to_dict`. Note: spec working name was `_keywords.py`; renamed to `library.py` for consistency with `hooks/library.py` + `orchestration/library.py` (filename convention `_build_components` resolves through `_SUB_LIBRARIES`). Per AC-5.4.5.
- [x] **Task 7: DynamicCore registration** — added `("AgentEval.telemetry.library", "TelemetryLibrary")` to `_SUB_LIBRARIES` tuple in `src/AgentEval/__init__.py:106-110`. Falls through default `cls()` constructor branch (no per-library kwargs needed). Per AC-5.4.5.
- [x] **Task 8: `RunManifest.warnings` field type update** — flipped `list[str]` → `list[dict[str, Any]]` at `src/AgentEval/types.py:227` + amended docstring at L197 cross-referencing `_kernel/warnings.WarningRecord` 5-key shape. Updated `__post_init__` defensive-copy from `list(self.warnings)` to `[dict(entry) for entry in self.warnings]` matching the `mcp_servers` pattern (so caller mutation of inner dicts cannot leak). Per AC-5.4.10.
- [x] **Task 9: `docs/contracts/run-manifest-schema.json` update** — `warnings` property now `array of object` with 4 required fields (warning_type, message, source, timestamp) + 1 optional nullable field (remediation). `additionalProperties: false` on each WarningRecord. Top-level `$description` bumped to v1.1 marker referencing Story 5.4 + FR62 unification. Per AC-5.4.9.
- [x] **Task 10: Unit tests** — `tests/unit/kernel/test_warnings.py` (6 tests, all pass) + `tests/unit/telemetry/test_get_last_warnings.py` (4 tests, all pass). Note: convention dir is `tests/unit/kernel/` (no underscore), matching the existing `test_context.py` / `test_redaction.py` location — spec working name `tests/unit/_kernel/` adjusted in lockstep. Per AC-5.4.8. Also fixed 2 pre-existing tests in `test_run_manifest.py` (`test_run_manifest_extended_fields_populated` + `test_run_manifest_defensive_copy_on_construction`) to use the new `list[dict]` shape rather than `list[str]`.
- [x] **Task 11: Integration tests** — `tests/integration/telemetry/test_warnings.py` (8 tests, all pass) per AC-5.4.7. All use `monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))` per Story 5.3 close-out norm. Coverage: (1) happy-path empty; (2) mark_external_mixed canonical FR61 trigger (DegradedTraceWarning + structured record + mcp_coverage→external_mixed); (3) JSONL write failure (record captured + test outcome NOT raised per AC-5.3.2); (4) RunManifest.warnings populated with 5-key dicts; (5) per-test isolation no cross-pollution; (6) test_id="all" union sorted by timestamp; (7) pre-test sentinel flushes into first bound test; (8) clear_warnings fires in end_test (buffer drained, but manifest sidecar persisted record).
- [x] **Task 12: All-gates pass** — All 5 gates green: ruff/format clean (161 files); mypy clean (68 src files); license-headers PASS (68 src files); **1023 unit+conformance+integration / 8 skipped** (was 1005 at Story 5.3 close; +18 net per Story 5.4 spec: 6 kernel/test_warnings + 4 test_get_last_warnings + 8 integration/test_warnings); no CWD pollution (`./agenteval/` absent after run). Tier-1 docstring badge added to `TelemetryLibrary.get_last_warnings` per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` convention check.
- [x] **Task 13: 4-reviewer cross-LLM code review** — completed 2026-05-20. **35 findings surfaced** (Blind 13 + Edge-cases 13 + Auditor 13 + Codex 4 probe results; overlaps consolidated). N-way triage per `feedback_n_way_agreement_weight` extended (Epic 4 retro): **3-way HIGHs** (lockless `_warning_buffers` race; `mark_external_mixed` re-entrant double-emit empirically confirmed via Codex Probe 4 2/2 emits; JSONL fake-green test); **Auditor 1-way HIGHs** on citation drift (errors.py L997 → L384) + spec drift (AC-5.4.8 over-promised defensive-copy claim) — `feedback_carry_over_catalog_gate` load-bearing across **5 consecutive stories** (Stories 5.1-5.4 + the original Story 4.3 retro miss caught by Story 4.4). 8 code patches applied + 4 deferred-via-catalog (C40 cross-thread ContextVar DF-5.4-S2; C41 cross-suite pabot sentinel DF-5.4-S3; C42 DynamicCore test gap DF-5.4-S4; plus C39 NFR-PERF-03d). 28th consecutive cross-LLM STAR catch streak preserved. Catalog total: 39 → 42. See Change Log v0.3.0 for the full triage record.

## Dev Notes

### Architecture compliance

- **PRD FR61** (DegradedTraceWarning trigger): existing Python `DegradedTraceWarning` class at `errors.py:790` REUSED — no class redefinition. Emit sites upgraded from `UserWarning` to `DegradedTraceWarning`. The mid-run degradation events explicitly enumerated by amended FR61 are wired: observer drop, JSONL write failure, manifest emit failure, novel redaction pattern, missing span attributes.
- **PRD FR62** (Get Last Warnings): keyword surface lands at `telemetry/_keywords.py`; 5-field `WarningRecord` shape per ratified 2026-05-20 unification of PRD-spec + epics-spec field sets.
- **PRD AC-MCP-OBSERVE-03** (per-test MCP scope polish): `_warning_buffers` keys-by-test_id + cleared at `end_test` + isolated across pabot processes (module-level dict per process per Listener v3 entry-point lifecycle).
- **ADR-016 D1 trust-floor** (mcp_coverage 3-state): the `partial` value is NOT referenced anywhere in Story 5.4 code per the D-1 drift fix. `mark_external_mixed` is the canonical FR61 trigger that mutates `mcp_coverage` to `external_mixed`.
- **Story 1b.2 M_R6 defensive-copy pattern**: applied to `WarningRecord.__init__` (mutable nested fields, if any) + `get_warnings` return values + `RunManifest.__post_init__` warnings list field (Story 5.3 existing pattern preserved).
- **Story 2.1 sub-library `__init__.py` discipline**: `_kernel/__init__.py` + `telemetry/__init__.py` UNTOUCHED — no re-exports. Callers import explicitly.
- **Story 2.2 `_SUB_LIBRARIES` MCPLibrary exclusion**: preserved — Story 5.4 doesn't touch the MCP sub-library inclusion list.

### Existing infrastructure Story 5.4 builds on

- **`errors.py:790` `DegradedTraceWarning(UserWarning)`** — Python warning class declared earlier; Story 5.4 does NOT redefine it. The class docstring at L805-815 (newly amended pre-authoring per D-1 fix) enumerates the emit sites.
- **`_kernel/trace_store.py:238/252/336`** — 3 existing call sites already use `DegradedTraceWarning` (not `UserWarning`). Story 5.4 adds `record_warning(...)` call alongside each `warnings.warn(...)` call (dual-channel pattern from AC-5.4.2).
- **`mcp/observer.py:96 AdapterVersionDriftWarning(UserWarning)`** + sites L415, L427 — separate warning class kept as-is. Story 5.4's `record_warning` call wires it through the structured buffer too (`warning_type="AgentEval.mcp.observer.AdapterVersionDriftWarning"`).
- **`_kernel/context.py` `current_test_id` + `set_current_test_id` + `unbind_context`** — Listener v3 per-test scope machinery from Story 1b.1; Story 5.4's buffer keys by `current_test_id()`.
- **`telemetry/listener.py:382-441` `end_test`** — the sequence is documented in AC-5.4.5: manifest emit BEFORE clear_warnings + clear_warnings BEFORE unbind_context.
- **`telemetry/run_manifest.py:67-143` `RunManifestEmitter.emit`** — Story 5.3 emitter; the `warnings` field flows in via `accumulated["warnings"]` from the listener — emitter itself doesn't need changes (it just serializes whatever's in the dataclass).

### Phase-1 limitations explicitly documented

- **`AdapterVersionDriftWarning` records** (separate from `DegradedTraceWarning`) — Story 5.4 ALSO routes these through `record_warning(...)` so `Get Last Warnings` surfaces them. Phase 2 (FR60: Tier-1 CLI adapter parity) is when AdapterVersionDriftWarning sees real production traffic.
- **`UserWarning` sites in non-telemetry modules** (`_kernel/discovery.py`, `_kernel/context.py`, `_kernel/redaction.py`) are intentionally NOT upgraded — these are CONFIG-time warnings (typo'd env var, partial provider discovery) not RUN-time degradation events. Out of FR61 scope. Reverse-direction safe: a CONFIG-time warning could be upgraded later if needed, but not as part of Story 5.4.
- **No per-warning `severity` field**: dropped per D-2 drift fix — severity is implicit in the Python warning class hierarchy (consumers can filter by `warning_type` string).
- **`mcp_per_test="suite"` mode (NFR-PERF-03d)** is NOT exercised in Story 5.4's integration tests — that mode is Phase-1.5+ via DF-5.4-S1 + C39 (the `mcp_coverage="library_only"` drift to be fixed in lockstep with the suite-mode implementation).

### Failure-mode contract (preserve AC-5.3.2 invariant)

- `record_warning(...)` MUST NOT raise — any internal error (e.g., serialization of bizarre `message` argument) is swallowed via `contextlib.suppress(Exception)` at the call boundary. Buffer not appended on failure; the original `warnings.warn(...)` still fires per Python contract.
- `get_warnings(...)` MUST NOT raise — returns `[]` if buffer key absent.
- `clear_warnings(...)` MUST NOT raise.
- `_emit_run_manifest_sidecar` wraps `get_warnings(...)` call in `contextlib.suppress(Exception)` per Story 5.3's existing pattern — failure leaves `accumulated["warnings"] = []` (Story 5.3 default).

### Files to create / modify

**NEW:**
- `src/AgentEval/_kernel/warnings.py` — `WarningRecord` + buffer + record_warning/get_warnings/clear_warnings.
- `src/AgentEval/telemetry/_keywords.py` — `get_last_warnings` keyword surface.
- `tests/unit/_kernel/test_warnings.py` — 6 unit tests.
- `tests/unit/telemetry/test_get_last_warnings.py` — 4 unit tests.
- `tests/integration/telemetry/test_warnings.py` — 8 integration tests.

**MODIFY:**
- `src/AgentEval/types.py` — flip `warnings: list[str]` → `list[dict[str, Any]]` (with docstring cross-ref).
- `src/AgentEval/errors.py` — already amended pre-authoring (D-1 fix). No further changes.
- `src/AgentEval/telemetry/backends.py` — convert JSONL write-failure UserWarning to dual-channel DegradedTraceWarning + record_warning.
- `src/AgentEval/telemetry/listener.py` — (a) convert 2 UserWarning sites; (b) amend `_emit_run_manifest_sidecar` to read warnings buffer; (c) call `clear_warnings(test_id)` in `end_test` between sidecar emit and unbind.
- `src/AgentEval/telemetry/run_manifest.py` — convert write-failure UserWarning to dual-channel.
- `src/AgentEval/mcp/observer.py` — wire `record_warning` into `mark_external_mixed(reason)` flow when prior observation existed (AC-5.4.3).
- `src/AgentEval/AgentEval.py` — wire `get_last_warnings` keyword into the DynamicCore composition (whichever sub-library hosts it).
- `docs/contracts/run-manifest-schema.json` — warnings property shape update + version comment bump.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW + reflected in this spec):**
- `_bmad-output/planning-artifacts/prd.md` — FR61 + FR62 amended (D-1 + D-2).
- `_bmad-output/planning-artifacts/architecture.md` L384 — amended (D-1).
- `_bmad-output/planning-artifacts/epics.md` Story 5.4 ACs — amended (D-2 + D-3).
- `src/AgentEval/errors.py:790-815` DegradedTraceWarning docstring — amended (D-1).

## Dev Agent Record

### Completion Notes

All 12 dev-side ACs satisfied (Task 13 = code-review handled by next skill in `/goal` loop). Story 5.4 closes DF-5.3-S1 (C32 catalog) by converting the 4 telemetry `UserWarning` placeholder sites to the dual-channel `DegradedTraceWarning` + `record_warning(...)` pattern. New `_kernel/warnings.py` module ships the `WarningRecord` frozen dataclass + per-test buffer + 5 APIs (`record_warning`, `get_warnings`, `clear_warnings`, `flush_pre_test_buffer`, `warning_record_to_dict`). New `telemetry/library.py` exposes the `Get Last Warnings` keyword wired through `_SUB_LIBRARIES`. RunManifest `warnings` field shape upgraded from `list[str]` placeholder to `list[dict[str, Any]]` with full 5-key shape per FR62 ratified unification. JSON Schema updated to v1.1 with the WarningRecord object schema. Per AC-MCP-OBSERVE-03, the per-test buffer is keyed by `current_context().test_id` + cleared at `end_test` after manifest emit + pre-test sentinel flushes into the first bound test.

### File List

**NEW:**
- `src/AgentEval/_kernel/warnings.py` — `WarningRecord` + buffer + 5 APIs (record_warning/get_warnings/clear_warnings/flush_pre_test_buffer/warning_record_to_dict).
- `src/AgentEval/telemetry/library.py` — `TelemetryLibrary.get_last_warnings` keyword (`@tier(1)` Tier-1 badge in docstring).
- `tests/unit/kernel/test_warnings.py` — 6 unit tests.
- `tests/unit/telemetry/test_get_last_warnings.py` — 4 unit tests.
- `tests/integration/telemetry/test_warnings.py` — 8 integration tests.

**MODIFIED:**
- `src/AgentEval/__init__.py` — added `("AgentEval.telemetry.library", "TelemetryLibrary")` to `_SUB_LIBRARIES`.
- `src/AgentEval/errors.py` — `DegradedTraceWarning` docstring amended pre-authoring (D-1 fix: removed `mcp_coverage="partial"` reference per ADR-016 D1).
- `src/AgentEval/types.py` — `RunManifest.warnings` field type flipped `list[str]` → `list[dict[str, Any]]`; docstring updated; `__post_init__` defensive-copy `[dict(entry) for entry in self.warnings]`.
- `src/AgentEval/telemetry/backends.py` — JSONL write-failure UserWarning → dual-channel DegradedTraceWarning + record_warning(source="telemetry.backends.jsonl"). DF-5.1-S1 hint stripped from message.
- `src/AgentEval/telemetry/listener.py` — (a) 2 UserWarning sites converted (missing test full_name + unknown trace_backend); (b) `_emit_run_manifest_sidecar` reads warnings buffer + serializes via `warning_record_to_dict`; (c) `end_test` calls `clear_warnings(test_id)` between sidecar emit + clear_spans; (d) `start_test` calls `flush_pre_test_buffer(test_id)` after `set_current_test_id`.
- `src/AgentEval/telemetry/run_manifest.py` — write-failure UserWarning → dual-channel DegradedTraceWarning + record_warning(source="telemetry.run_manifest"). DF-5.3-S1 hint stripped from message.
- `src/AgentEval/mcp/observer.py` — `mark_external_mixed(reason)` extended per AC-5.4.3 to fire dual-channel warning when `len(self._state.tool_calls) >= 1` (prior observation existed) — canonical FR61 trigger.
- `docs/contracts/run-manifest-schema.json` — `warnings` property shape updated to array-of-object with 5-field WarningRecord schema; top-level description bumped to v1.1.
- `tests/unit/telemetry/test_run_manifest.py` — 2 pre-existing tests updated for `list[dict]` shape: `test_run_manifest_extended_fields_populated` + `test_run_manifest_defensive_copy_on_construction`.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/prd.md` — FR61 + FR62 amended (D-1 + D-2).
- `_bmad-output/planning-artifacts/architecture.md` L384 — amended (D-1).
- `_bmad-output/planning-artifacts/epics.md` Story 5.4 ACs — amended (D-2 + D-3).
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-5.4-S1 added (D-4 carry-over).
- `docs/phase-1-5-carry-overs.md` — C39 added; total 38 → 39.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (25th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 5 drifts: D-1 HIGH PRD FR61 `mcp_coverage="partial"` value (superseded by ADR-016 D1 3-state Literal) → PRD + architecture L384 + errors.py:806 amended pre-authoring; D-2 MED-HIGH PRD FR62 vs epics Story 5.4 warning field set drift (3 fields vs 4 fields) → ratified 5-field unified `WarningRecord` shape + PRD + epics amended pre-authoring; D-3 MED epics "all 4 mcp_coverage values" drift → amended to "all 3" pre-authoring; D-4 carry-over LOW PRD L1614 NFR-PERF-03d `library_only` drift → DF-5.4-S1/C39 catalog entry; D-5 carry-over MED existing DegradedTraceWarning class is bare → dual-channel record_warning pattern (NOT a constructor change). 11 ACs documented. Closes DF-5.3-S1 (C32 catalog) via emit-site upgrade. Story 5.4 scope: 2 new src modules (`_kernel/warnings.py` + `telemetry/_keywords.py`) + 6 source-file modifications + 1 schema update + 3 new test files (18 new tests). | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code review). 2 new src modules (`_kernel/warnings.py` 200L with WarningRecord frozen dataclass + 5 APIs; `telemetry/library.py` 65L with TelemetryLibrary.get_last_warnings keyword). 7 source-file modifications: `__init__.py` `_SUB_LIBRARIES` registration; `errors.py` docstring amend; `types.py` RunManifest.warnings type + post_init defensive-copy; `telemetry/backends.py` + `telemetry/listener.py` (3 sites) + `telemetry/run_manifest.py` UserWarning→dual-channel upgrades; `mcp/observer.py` mark_external_mixed AC-5.4.3 canonical FR61 trigger wired (only fires when `len(tool_calls) >= 1`). 1 schema update (`run-manifest-schema.json` warnings property → 5-key WarningRecord object; top-level description bumped v1.0 → v1.1). Note: spec working name `telemetry/_keywords.py` renamed to `telemetry/library.py` for consistency with `hooks/library.py` + `orchestration/library.py` (decision documented in dev notes). 18 new tests: 6 unit @ `tests/unit/kernel/test_warnings.py` + 4 unit @ `tests/unit/telemetry/test_get_last_warnings.py` + 8 integration @ `tests/integration/telemetry/test_warnings.py`. 2 pre-existing tests fixed for new `list[dict]` shape. All gates green: ruff/format/mypy clean (68 src files); **1023 unit+conformance+integration** (was 1005 at Story 5.3 close; +18 net) / 8 skipped; license-headers PASS; no CWD pollution. | Amelia |
| 2026-05-20 | 0.3.0   | **Status → done.** 4-reviewer cross-LLM code-review surfaced **35 findings** (Blind 13 + Edge-cases 13 + Auditor 13 + Codex 4 probe results; consolidated post-overlap). N-way agreement triage per `feedback_n_way_agreement_weight` extended (Epic 4 retro): **3-way HIGH-A** (Blind HIGH-A + Edge-cases HIGH-1+HIGH-6) — `_warning_buffers` lockless concurrency race → added `threading.RLock()` guarding all 5 mutators + `get_warnings("all")` snapshot; **3-way HIGH-B** (Blind HIGH-B + Edge-cases HIGH-5 + Codex Probe 4 empirical 2/2 emits) — `mark_external_mixed` re-entrant double-emit → added `_external_mixed_warned: bool` dedupe sentinel to `_ObserverState` mirroring the existing `version_drift_warned` pattern; **3-way HIGH-G** (Blind MED-G + Edge-cases HIGH-2 + Auditor HIGH-1) — JSONL fake-green test asserted nothing about captured warning → rewrote test fixture so manifest sidecar emit succeeds (pre-create target_dir, block only the JSONL path); assert sidecar's `warnings[0]["source"] == "telemetry.backends.jsonl"`; **3-way MED-pabot** (Blind MED-H + Edge-cases MED-6 + Auditor MED-2) — pabot isolation test was tautological → renamed `test_e2e_per_test_buffer_keys_by_test_id_no_cross_pollution` + assert both buffers populated simultaneously + cross-key routing verified; **1-way Auditor HIGH-2** citation drift — errors.py:791 cited "architecture L997" (unrelated OTel semconv anti-pattern) → fixed to cite PRD FR61 + architecture L384; **1-way Auditor HIGH-3** spec drift — AC-5.4.8 over-promised "defensive-copy on `__init__`" but `WarningRecord` has no mutable nested fields → amended spec to drop the over-promise; **1-way Blind HIGH-C** dual-channel order — `warnings.warn` before `record_warning` meant `-W error::DegradedTraceWarning` filter raised before structured record fired, silently dropping the very event operators most wanted captured → swapped order to record-first-warn-second across all 5 emit sites; **1-way Blind HIGH-D** `__post_init__` crash on stale `list[str]` warnings fixtures → added isinstance-str backward-compat coercion shim; **1-way Edge-cases HIGH-4** spans-less + warning lost — `_emit_run_manifest_sidecar` returned early when `get_run_manifest` raised, dropping the structured record → synthesize minimal manifest carrying just warnings + identity fields. 4 deferred-via-catalog: C40 cross-thread ContextVar attribution (DF-5.4-S2, Edge-cases HIGH-3 + Codex Probe 2 empirical — documented as known limitation; Phase-1.5 adds explicit `test_id=` kwarg); C41 cross-suite pabot sentinel pollution (DF-5.4-S3, Edge-cases MED-1); C42 DynamicCore composition test gap (DF-5.4-S4, Auditor MED-4); C39 PRD L1614 NFR-PERF-03d (DF-5.4-S1 pre-create-story). 4 new regression tests: HIGH-A (`test_record_warning_under_concurrent_threads_does_not_lose_records`, 20 threads); HIGH-B (`mark_external_mixed` called twice — sentinel dedupes second emit; `external_mixed_reasons()` accumulates both for forensic trail); HIGH-C (`test_e2e_dual_channel_order_record_first_warn_second` — `-W error::DegradedTraceWarning` raises but structured record present); HIGH-D (`test_run_manifest_backward_compat_list_str_warnings_coerced`); HIGH-E4 (`test_e2e_span_less_test_with_warning_emits_minimal_manifest`). 2 pre-existing tests tightened: `test_warning_record_is_frozen_dataclass` → `pytest.raises(FrozenInstanceError)` (was `pytest.raises((AttributeError, Exception))` per Auditor MED-1); pabot fake-green test renamed + rewritten. Catalog total: 39 → 42. Auditor 1-way HIGHs on citation/spec drift now 10+ consecutive TPs across 7 epics. PRD FR62 + spec AC-5.4.5/AC-5.4.8 amended pre-close per fix-the-losing-source-NOW (Auditor MED-5 + MED-6). 28th consecutive cross-LLM STAR catch streak preserved. All gates green: ruff/format/mypy clean (68 src files); **1027 unit+conformance+integration** (was 1023 at v0.2.0 close; +4 net) / 8 skipped; license-headers PASS; no CWD pollution. | Amelia |
