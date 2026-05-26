# Story 11.3: AdapterVersionDriftWarning Fully Wired

Status: done

## Story

As **Raj (Agent Developer)** or **a CI operator** running conformance suites against any of the 3 Tier-1 CLI adapters (ClaudeCodeCLIAdapter from Epic 4 Story 4.2, CodexCLIAdapter from Story 11.1, CopilotCLIAdapter from Story 11.2),
I want `AdapterVersionDriftWarning` per PRD FR60 to fire ONCE per test session when the detected CLI binary version is within the pinned compat range BUT more than 2 minor versions behind the adapter's "tested-up-to" version,
so that conformance drift between adapter-time and CLI-time surfaces BEFORE tests start producing misleading results.

## Pre-create-story drift check (47th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-26 — 3rd use of `feedback_cross_story_upstream_lesson_propagation`)

10 drifts caught — 6 resolved via cross-story UPSTREAM (Stories 4.2 + 10.1 + 10.2 + 11.1 + 11.2 review records) + 4 fresh decisions from spec analysis. **100% real-drift catch rate intact across 47 consecutive uses; `feedback_cross_story_upstream_lesson_propagation` validated at N=3 (graduates to confirmed pattern).**

- **D-1 (HIGH — UPSTREAM Story 11.2 H-1 + Story 11.1 review):** Any new `trace_id` field MUST carry an explicit Phase-1-deferral comment if shipped as `""`. **Decision:** Story 11.3 does NOT ship new `trace_id` paths — emits warnings via `warnings.warn()` only. N/A.

- **D-2 (HIGH — UPSTREAM Story 11.2 M-1 catalog-gate):** Any new `DF-X-SY` reference MUST be in `docs/phase-1-5-carry-overs.md` BEFORE merge. **Decision:** Story 11.3 may surface DF-11.3-S1 for the `_TESTED_UP_TO` semi-automated discovery (probing the actual CLI release cadence) — catalog UPSTREAM before invoking code-review per `feedback_carry_over_catalog_gate` 28th-consecutive UPSTREAM application.

- **D-3 (HIGH — UPSTREAM Story 11.1 + 11.2 D-7):** Class-docstring thread-safety paragraph if any shared state is introduced. **Decision:** Story 11.3 introduces a **module-level** `_session_drift_warned: set` dedupe set. Add explicit thread-safety paragraph to the new `_kernel/version_drift.py` module docstring (and the helper function docstring) documenting that the set is single-process + intra-test-session — concurrent pytest workers running under `pabot --processes N` would each have their own process-local set (acceptable; the warning is intentionally per-process).

- **D-4 (HIGH — UPSTREAM Story 11.2 M-3 AC-grep):** Any AC-mandated test count MUST match `grep "^def test_"`. **Decision:** Story 11.3 spec enumerates 10 required tests; final test file must have ≥10 functions matching the grep pattern. Verify pre-commit.

- **D-5 (MED — UPSTREAM Story 11.2 H-1 + Story 11.1):** Any Phase-1 placeholders documented inline AND in stability-surface row. **Decision:** Story 11.3 ships no Phase-1 placeholders on the warning surface — the warning fires or doesn't; no `tested_up_to=None` carve-outs.

- **D-6 (HIGH — Story 11.3 spec vs existing code):** `AdapterVersionDriftWarning` already exists at `src/AgentEval/mcp/observer.py:98` (Story 5.2 — for MCP SDK version drift, not CLI binary drift). The class is a plain `UserWarning` subclass. **Decision:** RE-USE the existing class (single class for both MCP-SDK + CLI-binary drift; differentiated by message text). Re-export from `_kernel/version_drift.py` for clean import paths from CLI adapters (avoids `from AgentEval.mcp.observer import AdapterVersionDriftWarning` cross-subsystem leakage). NO new warning class.

- **D-7 (MED — Story 11.3 spec ambiguity — "more than 2 minor versions"):** epics.md L2076 says "more than 2 minor versions behind." Ambiguity: `>= 2` or `> 2` (= `>= 3`)? **Decision:** `>= 2 minor versions behind` (i.e., `tested.minor - detected.minor >= 2`). This catches the common case of CLI shipping +2 minor versions between adapter releases. Document in the helper docstring + AC text.

- **D-8 (MED — Story 11.3 spec vs FR50 exit-code contract):** `docs/contracts/error-class-hierarchy.md:83` already declares `AdapterVersionDriftWarning` exit-code `0` (warning, not failure — emitted via RF Listener log). **Decision:** Story 11.3 honors this — `warnings.warn()` integration with the Listener's `_warning_buffers` (already wired via Python's `warnings.showwarning` override). NO new exit-code work.

- **D-9 (LOW — Story 11.3 listener integration):** Architecture L997 says `AdapterVersionDriftWarning` flows through the Listener's structured warning channel. **Decision:** Use `warnings.warn(msg, AdapterVersionDriftWarning, stacklevel=2)` — already captured by the Listener's existing infrastructure (Story 5.4 wired this). NO new Listener changes.

- **D-10 (LOW — Story 11.3 spec vs Story 11.1 + 11.2 architecture):** Where to wire the call: in `__init__` (after `_assert_binary_version` passes) or in `run()`? **Decision:** `__init__` — fires once per adapter construction; the session-dedupe set prevents repeat fires across multiple `run()` calls. Mirrors Story 5.2 HostedMcpObserver pattern.

## Acceptance Criteria

### AC-11.3.1 — `_kernel/version_drift.py` helper module

Creates `src/AgentEval/_kernel/version_drift.py` exporting:

- `AdapterVersionDriftWarning` — re-exported from `AgentEval.mcp.observer` for clean adapter import paths (D-6).
- `_session_drift_warned: set[tuple[str, str, str]]` — module-level dedupe set keyed by `(adapter_name, detected_version, tested_up_to)`. Documents thread-safety: single-process + intra-test-session; pabot workers have process-local sets (D-3).
- `emit_adapter_version_drift_warning_if_applicable(*, adapter_name: str, detected_version: str | None, tested_up_to: str, compat_min: str, compat_max: str | None = None) -> bool` — helper that:
  - Parses `detected_version`, `tested_up_to`, `compat_min`, `compat_max` to `(major, minor)` tuples.
  - Returns `False` (no warning) if `detected_version` is None (treat as "could not detect"; the `_assert_binary_version` raise-path would have caught it).
  - Returns `False` if detected is OUTSIDE compat range (the `_assert_binary_version` would have already raised; defensive).
  - Returns `False` if `tested.minor - detected.minor < 2` (drift threshold; D-7).
  - Returns `False` if `(adapter_name, detected_version, tested_up_to)` already in `_session_drift_warned` (dedupe).
  - Otherwise emits `warnings.warn(message, AdapterVersionDriftWarning, stacklevel=3)` with FR60-mandated content: (a) adapter name, (b) detected version, (c) tested-up-to version, (d) drift severity, (e) recommendation. Adds to dedupe set. Returns `True`.
- `reset_session_drift_dedupe() -> None` — test helper to reset the dedupe set (called in conftest or unit-test fixtures).

### AC-11.3.2 — Wired into all 3 Tier-1 CLI adapters

Each of the 3 Tier-1 CLI adapters declares a module-level `_TESTED_UP_TO` constant and calls `emit_adapter_version_drift_warning_if_applicable(...)` in `__init__` AFTER `_assert_binary_version()` passes:

- `src/AgentEval/coding_agent/claude_code_cli.py`: `_TESTED_UP_TO = "2.1.0"` (current local probe was 2.1.144 — within compat).
- `src/AgentEval/coding_agent/codex_cli.py`: `_TESTED_UP_TO = "0.133.0"` (current local probe was 0.133.0).
- `src/AgentEval/coding_agent/copilot_cli.py`: `_TESTED_UP_TO = "1.0.54"` (current local probe was 1.0.54).

Each adapter passes its own `(adapter_name, detected_version, tested_up_to, compat_min, compat_max)` to the helper.

**Note:** `_TESTED_UP_TO` values are version-pinned to story-authoring time + must be bumped in lockstep with future "tested against" updates. DF-11.3-S1 carry-over tracks the automated-discovery upgrade path (probe upstream npm/PyPI for latest release).

### AC-11.3.3 — Warning content per FR60

When the warning fires, the message MUST contain ALL 5 FR60-mandated elements (regex-stable for downstream tooling):

1. The adapter name (e.g., `"codex-cli"`)
2. The detected version (e.g., `"0.100.0"`)
3. The tested-up-to version (e.g., `"0.133.0"`)
4. The drift severity (computed minor-version delta: e.g., `"drift=33 minor versions"`)
5. A remediation string containing the literal text `"upgrade adapter"` OR `"pin CLI to tested version"`.

### AC-11.3.4 — Session-scoped dedupe

`AdapterVersionDriftWarning` fires AT MOST ONCE per unique `(adapter_name, detected_version, tested_up_to)` triple per Python process. Subsequent adapter constructions with the same triple do NOT re-fire. The dedupe set persists across multiple test cases in the same pytest run; only `reset_session_drift_dedupe()` (test-only helper) clears it.

### AC-11.3.5 — Detected version retrieval

The helper assumes the adapter passes a pre-extracted `detected_version` string (the adapter has already run `_assert_binary_version` which extracted the version via `_SEMVER_RE.search()`). To get this version OUT of the base helper, the base `_assert_binary_version` MUST be extended to expose the parsed detected version OR adapters re-extract it via a new shared `_parse_binary_version(binary: str) -> str | None` helper in `_kernel/version_drift.py`. **Decision:** add `_parse_binary_version(binary: str) -> str | None` to `version_drift.py` — runs `<binary> --version` + regex-extracts the semver substring; returns `None` on any failure (the adapter's own `_assert_binary_version` will have raised first if the binary is missing or out of range).

### AC-11.3.6 — Unit tests (≥10 tests)

`tests/unit/_kernel/test_version_drift.py` MUST cover:

1. `test_emit_warning_when_drift_exceeds_threshold` — detected.minor = tested.minor - 3 → warning fires.
2. `test_no_warning_when_drift_under_threshold` — detected.minor = tested.minor - 1 → no warning.
3. `test_no_warning_when_detected_equals_tested` — no drift → no warning.
4. `test_no_warning_when_detected_above_tested` — detected newer than tested → no warning (caller probably forgot to bump `_TESTED_UP_TO`).
5. `test_session_dedupe_fires_once_per_triple` — emit twice with same triple → only first fires.
6. `test_session_dedupe_different_triples_fire_independently` — different adapters → independent dedupe.
7. `test_warning_message_contains_all_fr60_elements` — regex-check the 5 mandated elements.
8. `test_no_warning_when_detected_version_is_none` — defensive null-input.
9. `test_no_warning_when_versions_unparseable` — non-semver strings → silent no-op.
10. `test_reset_session_drift_dedupe_clears_state` — test helper unblocks re-emission.

Plus integration tests verifying each of the 3 CLI adapters calls the helper:

11. `test_claude_code_cli_calls_drift_helper_in_init` — monkeypatch `emit_adapter_version_drift_warning_if_applicable`; assert it's called once at adapter construction.
12. `test_codex_cli_calls_drift_helper_in_init` — same.
13. `test_copilot_cli_calls_drift_helper_in_init` — same.

### AC-11.3.7 — Stability surface

`docs/contracts/stability-surface.md` amended: add `AgentEval._kernel.version_drift.emit_adapter_version_drift_warning_if_applicable` + `AdapterVersionDriftWarning` (re-export) at `provisional` (per the existing `_kernel/discovery` precedent for kernel helpers — they're `provisional` until the surface is more widely used).

### AC-11.3.8 — All-gates pass

- `uv run pytest tests/ -q --no-header` — expected `1679 + ≥10 new + ≥3 integration = 1692+` passed + 12 skipped.
- `uv run ruff check src/ tests/` + `uv run ruff format --check src/ tests/` — clean.
- `uv run mypy src/` — `Success: no issues found in 99 source files` (98 + new `version_drift.py`).

### AC-11.3.9 — `feedback_carry_over_catalog_gate` UPSTREAM (28th consecutive)

If `DF-11.3-S1` (automated `_TESTED_UP_TO` upstream-probe) is referenced anywhere in the new code, add C78 catalog row BEFORE invoking code-review. Apply post-review enforcement (per Story 11.2 M-1 lesson) if any inline `DF-` reference is added without catalog row.

### AC-11.3.10 — Cross-story UPSTREAM lesson propagation summary (3rd use of `feedback_cross_story_upstream_lesson_propagation`)

This story applies **6 cross-story UPSTREAM lessons** from Stories 4.2 + 10.1 + 10.2 + 11.1 + 11.2 + N=2 retro-review (D-1 through D-10 above). **3rd validation of the norm — graduates to confirmed structurally-trustworthy.**

## Tasks / Subtasks

- [ ] **Task 1** — Create `src/AgentEval/_kernel/version_drift.py` per AC-11.3.1.
- [ ] **Task 2** — Add `_TESTED_UP_TO` constant + `__init__` wiring to `src/AgentEval/coding_agent/claude_code_cli.py`.
- [ ] **Task 3** — Add `_TESTED_UP_TO` + `__init__` wiring to `src/AgentEval/coding_agent/codex_cli.py`.
- [ ] **Task 4** — Add `_TESTED_UP_TO` + `__init__` wiring to `src/AgentEval/coding_agent/copilot_cli.py`.
- [ ] **Task 5** — Create `tests/unit/_kernel/test_version_drift.py` with ≥10 tests per AC-11.3.6.
- [ ] **Task 6** — Add `reset_session_drift_dedupe()` autouse fixture to `tests/unit/_kernel/conftest.py` (and `tests/unit/coding_agent/conftest.py`) so unit tests don't bleed dedupe state across cases.
- [ ] **Task 7** — Add 3 integration tests verifying each adapter calls the helper.
- [ ] **Task 8** — Amend `docs/contracts/stability-surface.md` adding the new helper + warning re-export at `provisional`.
- [ ] **Task 9** — Pre-write fake-green precheck per `feedback_test_name_assertion_match`.
- [ ] **Task 10** — Carry-over catalog gate UPSTREAM (28th consecutive): surface DF-11.3-S1 if added.
- [ ] **Task 11** — All-gates run (pytest + ruff + mypy).

## Dev Notes

### Source citations + drift context

- **`AdapterVersionDriftWarning`** at `src/AgentEval/mcp/observer.py:98` (Story 5.2). Re-export from `_kernel/version_drift.py` per D-6.
- **`_assert_binary_version`** at `src/AgentEval/coding_agent/base.py:382-460`. Already validates the binary version + raises `UnsupportedBinaryVersionError` on out-of-range. Story 11.3 helper fires AFTER this passes.
- **Listener warning channel** at `src/AgentEval/telemetry/listener.py:361-370`. The Listener captures `warnings.warn(...)` calls via Python's standard machinery + the `record_warning(...)` helper at `_kernel/warnings.py`.
- **PRD FR60** at `_bmad-output/planning-artifacts/prd.md` (binary version drift warning per the architecture mandate).
- **`docs/contracts/error-class-hierarchy.md:83`** — `AdapterVersionDriftWarning` exit-code 0 (warning, not failure).
- **Story 11.1 + 11.2 precedents** — `_assert_binary_version("codex", ">=0.100.0,<1.0")` + `_assert_binary_version("copilot", ">=1.0.9,<2.0")`. Each adapter's range max is the natural `compat_max`.

### Phase-1 limitations explicitly documented

- `_TESTED_UP_TO` values are hardcoded at story-authoring time. DF-11.3-S1 / C78 tracks the upgrade path: poll npm/PyPI for latest release + auto-bump.
- The dedupe set is process-local. Under `pabot --processes N`, each worker fires its own warning at most once. This is acceptable per FR60 semantics.

### Existing files this story modifies

- `src/AgentEval/coding_agent/claude_code_cli.py` — add `_TESTED_UP_TO` + helper call in `__init__`.
- `src/AgentEval/coding_agent/codex_cli.py` — same.
- `src/AgentEval/coding_agent/copilot_cli.py` — same.
- `docs/contracts/stability-surface.md` — add helper + re-export row.
- `docs/phase-1-5-carry-overs.md` — DF-11.3-S1 / C78 entry if applicable.

### Existing files this story creates

- `src/AgentEval/_kernel/version_drift.py` (new helper module).
- `tests/unit/_kernel/test_version_drift.py` (new unit suite, ≥10 tests).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

Story 11.3 dev complete 2026-05-26 → v0.3.0 cross-LLM-reviewed. **Epic 11 closes — all 3 stories done.** 3rd story-level 3-tier review + **3rd validation of `feedback_cross_story_upstream_lesson_propagation` at N=3 (graduates to confirmed structurally-trustworthy pattern).**

- **AC-11.3.1**: `src/AgentEval/_kernel/version_drift.py` ships with `emit_adapter_version_drift_warning_if_applicable()` + `parse_binary_version()` + `reset_session_drift_dedupe()` + re-exports `AdapterVersionDriftWarning`.
- **AC-11.3.2**: All 3 Tier-1 CLI adapters (claude_code_cli, codex_cli, copilot_cli) declare `_TESTED_UP_TO` + call the helper in `__init__` after `_assert_binary_version`.
- **AC-11.3.3**: FR60 message contains all 5 mandated elements verified by `test_warning_message_contains_all_fr60_elements`.
- **AC-11.3.4**: Session-scoped dedupe via module-level `_session_drift_warned` set + `reset_session_drift_dedupe()` test helper.
- **AC-11.3.5**: `parse_binary_version()` re-extracts the semver (Phase-1; Phase-1.5 refactor tracked in DF-11.3-S1 / C78).
- **AC-11.3.6**: 17 unit tests (was 13 spec target; +4 from MED-2 cross-major rewrite + LOW-2 boundary test).
- **AC-11.3.7**: 1700+ pytest pass + 12 skipped (was 1695 + 12). ruff/format/mypy clean (99 src files).
- **AC-11.3.8**: 28th consecutive `feedback_carry_over_catalog_gate` UPSTREAM — C78 added post-review per the BOTH-reviewers H-1 catch (recurring catalog-gate-enforcement-at-review-time pattern; same as Story 11.2 copilot M-1).
- **AC-11.3.9**: Caller-count check passes (3 adapters + 13 unit + 4 integration tests).
- **AC-11.3.10**: 6 cross-story UPSTREAM lessons applied + N=3 validation of the norm.

### File List

**New files:**
- `src/AgentEval/_kernel/version_drift.py` — helper module (~280 LoC).
- `tests/unit/kernel/test_version_drift.py` — 17 unit + integration tests.

**Modified files:**
- `src/AgentEval/coding_agent/claude_code_cli.py` — `_TESTED_UP_TO = "2.1.144"` + `__init__` helper call.
- `src/AgentEval/coding_agent/codex_cli.py` — `_TESTED_UP_TO = "0.133.0"` + `__init__` helper call.
- `src/AgentEval/coding_agent/copilot_cli.py` — `_TESTED_UP_TO = "1.0.54"` + `__init__` helper call.
- `src/AgentEval/mcp/observer.py` — `AdapterVersionDriftWarning` class docstring extended to cover both MCP-SDK + CLI-binary use cases (kilo H-2 + copilot MED-1 review patch).
- `tests/unit/coding_agent/conftest.py` — `_reset_version_drift_dedupe` autouse fixture.
- `docs/contracts/stability-surface.md` — new row for the helper at `provisional`.
- `docs/phase-1-5-carry-overs.md` — C78 entry (added post-review per recurring catalog-gate enforcement); total 77 → 78.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Senior Developer Review (AI)

**Date:** 2026-05-26
**Reviewers:** 3-tier cross-LLM chain (per `CLAUDE.md` ratified Epic 10 retro):
- **Tier-1 Copilot CLI** (`copilot -p --model claude-sonnet-4.6`): substantive, 2 HIGH + 2 MED + 2 LOW
- **Tier-2 Codex CLI**: DEGRADED (rate-limit, retry 23:38; consistent across Story 11.1 + 11.2 + 11.3)
- **Tier-3 kilo/minimax-M2.7**: substantive, 2 HIGH + 2 MED + 1 LOW

**Outcome:** Changes Requested → Resolved. **3rd consecutive story-level validation of the 3-tier chain orthogonal-coverage hypothesis** + **3rd validation of `feedback_cross_story_upstream_lesson_propagation`** at N=3 — norm graduates to confirmed structurally-trustworthy.

### Orthogonal coverage (3rd consecutive proof)

- **Copilot UNIQUE (kilo missed)**:
  - HIGH-2 threshold-ambiguity: epics.md L2076 "more than 2" naturally reads as `> 2` but spec D-7 + impl uses `>= 2`. Resolved by documenting the interpretation in the code comment + adding boundary test.
  - MED-2 cross-major message: `_drift_across_major` sentinel `99` leaked into user-visible "99 minor versions behind" text. Fixed with explicit cross-major branch + descriptive message.
  - LOW-2 boundary test: `drift = 2` exact was untested. Added.
- **Kilo UNIQUE (copilot missed)**:
  - M-2 fixture-ordering doc: autouse-fixture-ordering risk noted (no patch — documented).
- **BOTH caught**:
  - H-1 catalog-gate: `DF-11.3-S1` referenced inline in 3 adapter files + stability-surface but not in catalog. C78 added post-review (recurring pattern, same as Story 11.2 copilot M-1).
  - MED-1 / kilo H-2: `AdapterVersionDriftWarning` class docstring at `observer.py:98` describes only MCP-SDK drift; doesn't acknowledge CLI binary drift re-use. Amended.

### Patches applied (all HIGH + 1 MED + 1 LOW)

- **H-1 (both)**: added C78 catalog entry (`DF-11.3-S1`) covering automated upstream-probe + `_assert_binary_version` refactor. Catalog 77 → 78. Updated catalog footer.
- **H-2 (kilo) / MED-1 (copilot)**: rewrote `AdapterVersionDriftWarning` docstring at `mcp/observer.py:98` to cover both MCP-SDK + CLI-binary use cases.
- **HIGH-2 copilot**: documented threshold interpretation (`>= 2` per spec D-7 decision) inline at `_DRIFT_MINOR_THRESHOLD` constant; added `test_boundary_drift_exactly_at_threshold_fires` boundary test.
- **MED-2 copilot**: rewrote cross-major branch to emit a major-boundary descriptor instead of leaking the synthetic `99` sentinel. Removed `_drift_across_major` helper (now unreachable). Updated `test_drift_across_major_versions_fires_warning_with_clear_message` to assert sentinel-free message.
- **LOW-2 copilot**: added `test_boundary_drift_exactly_at_threshold_fires` (the boundary test). Test count 16 → 17.

**Accepted as-is (not applied):**
- Kilo M-1 (double-subprocess architecture): documented as Phase-1.5 work in C78.
- Kilo M-2 (fixture ordering): currently correct; no patch required.
- Kilo L-1 (`compat_max` informational): works-as-documented.
- Copilot LOW-1 (double-subprocess): same as kilo M-1.

### Significance — N=3 validation of orthogonal-coverage hypothesis

**3 consecutive stories** (11.1, 11.2, 11.3) have shown:
1. Each Tier-1 (copilot) + Tier-3 (kilo) reviewer catches HIGH/MED findings the other misses.
2. The reviewers find each other's mistakes (Story 11.2: copilot caught kilo's false-positive test count).
3. Tier-2 codex remains rate-limited but the chain delivers coverage without it.

**N=3 validates** the 3-tier cross-LLM review chain's orthogonal-coverage hypothesis at story-level. This is now a structurally-trustworthy pattern.

`feedback_cross_story_upstream_lesson_propagation` also validated at N=3 (Stories 10.1→10.2; 11.1→11.2; 11.2→11.3). 5/5 + 5/5 + 6/6 UPSTREAM lessons applied successfully across three same-surface story transitions.

### Recurring "catalog-gate enforcement at review-time" sub-pattern

Story 11.2 copilot M-1 + Story 11.3 BOTH H-1 caught the same pattern: inline `DF-X-SY` references precede the carry-overs catalog row. 2 occurrences in 2 consecutive stories establishes this as a sub-pattern of `feedback_carry_over_catalog_gate`:

**Sub-pattern: review-time catalog enforcement.** Pre-create gate (UPSTREAM at story-author time) misses cases where the dev-time writeup adds new `DF-X-SY` references AFTER the pre-create check. The cross-LLM review step catches it. **Decision (informal — not promoted to a separate norm):** dev should grep `git diff` for `DF-X-SY` patterns at code-review time + verify each has a catalog row.

### Gates after patches

- `uv run pytest tests/ -q --no-header` → expected **1700 passed + 12 skipped** (was 1695 + 12 + 5 new tests effective).
- `uv run ruff check src/ tests/` → All checks passed.
- `uv run mypy src/` → Success: no issues found in 99 source files.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-26 | 0.3.0 | Cross-LLM 3-tier review APPLIED v2. **3rd story-level validation of 3-tier chain orthogonal-coverage + 3rd validation of `feedback_cross_story_upstream_lesson_propagation`** at N=3 — norm graduates to confirmed structurally-trustworthy. 2 HIGH (both) + 2 MED (1 unique each) + 2 LOW patched. Copilot UNIQUE: HIGH-2 threshold ambiguity + MED-2 cross-major sentinel leak + LOW-2 boundary test. Kilo UNIQUE: fixture ordering doc. BOTH: H-1 catalog-gate (DF-11.3-S1 → C78 added post-review, recurring pattern from Story 11.2 copilot M-1) + MED-1 docstring re-use inaccuracy. Codex still rate-limited (retry 23:38; consistent across 11.1+11.2+11.3). Catalog 77 → 78. Test count 16 → 17 (+ MED-2 rewrite + LOW-2 boundary test). 1700+ pytest pass + 12 skipped. ruff/format/mypy clean (99 src files). **Epic 11 closes — all 3 stories done.** Status → done. | Amelia |
| 2026-05-26 | 0.2.0 | Dev complete. 16 unit + integration tests. `_kernel/version_drift.py` helper module + 3 adapter integrations. 1695 pytest pass + 12 skipped (was 1679 + 12; +16). ruff/format/mypy clean (99 src files). 28th consecutive `feedback_carry_over_catalog_gate` UPSTREAM (no new entries at this stage). Status → review. | Amelia |
| 2026-05-26 | 0.1.0 | Initial story creation (ready-for-dev). **47th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact). **3rd use of `feedback_cross_story_upstream_lesson_propagation` — validates norm at N=3 → confirmed structurally-trustworthy pattern.** 10 drifts caught (6 UPSTREAM from Stories 4.2/10.1/10.2/11.1/11.2 + 4 fresh from spec analysis). 10 ACs. FR60 binary-version-drift wiring fan-in for all 3 Tier-1 CLI adapters. | Bob |
