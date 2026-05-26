# Story 11.2: Copilot CLI Adapter

Status: done

## Story

As **Raj (Agent Developer)** working with the GitHub Copilot ecosystem,
I want a `CopilotCLIAdapter(SubprocessAdapter)` invoking the `copilot` binary in non-interactive autopilot mode + parsing the `~/.copilot/session-state/{uuid}/events.jsonl` trace post-hoc,
so that I can run Copilot CLI agent workflows under the unified `CodingAgentAdapter` Protocol — completing the Epic 11 CLI-adapter triad before the Story 11.3 `AdapterVersionDriftWarning` fan-in.

## Pre-create-story drift check (46th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-26 — 2nd use of `feedback_cross_story_upstream_lesson_propagation`)

12 drifts caught — 11 resolved via cross-story-upstream-lesson-propagation (Story 11.1 + Story 4.2 + Epic 10 lessons) + 1 fresh decision from empirical events.jsonl probe. **100% real-drift catch rate intact across 46 consecutive uses; `feedback_cross_story_upstream_lesson_propagation` validated 2nd-application UPSTREAM.**

- **D-1 (HIGH — UPSTREAM Story 11.1 D-1 / Story 4.2 HIGH-A):** Spec L2059 silent on prompt-delivery mechanism. **Decision:** pass `prompt` to `copilot -p "<prompt>"` as the `-p`/`--prompt` flag argument (per `copilot --help`: "Execute a prompt in non-interactive mode"). Add `test_spawn_passes_prompt_via_prompt_flag` regression-guard.

- **D-2 (HIGH — UPSTREAM Story 11.1 D-2 / Story 4.2 HIGH-B):** Spec L2059 silent on stderr handling. **Decision:** `stderr=subprocess.STDOUT` multiplex into stdout. `_parse_event` returns `None` on non-JSON lines.

- **D-3 (HIGH — UPSTREAM Story 11.1 D-3 / Story 4.2 MED-3):** Spec silent on subprocess non-zero exit handling. **Decision:** `_finalize` surfaces `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic when no terminal event AND no assistant text. M_R11 fail-loud.

- **D-4 (HIGH — UPSTREAM Story 11.1 D-4 / Story 4.2 MED-1):** **Decision:** `mock_copilot_version` autouse fixture goes DIRECTLY into `tests/unit/coding_agent/conftest.py` from the start (mirrors `mock_codex_version` from Story 11.1).

- **D-5 (HIGH — UPSTREAM Story 11.1 D-5 / Story 4.2 Auditor HIGH-1):** **Decision:** all ADR citations are ADR-002 (Tier-1 Adapter Ceiling Rule) + ADR-010 (Copilot CLI version-pinning precedent — original per-CLI pin source for the project). Inline citation hygiene from the start.

- **D-6 (HIGH — UPSTREAM Epic 10 + Story 11.1 D-6 / kilo MED-2):** **Decision:** all `mcp_coverage` citations cite **ADR-016 §Decision L33** verbatim (NOT `ADR-A6 L384`, NOT `ADR-016 L59`). Inline citation discipline matching Story 11.1 post-copilot-MED-2 fix.

- **D-7 (MED — UPSTREAM Story 11.1 D-7 / Stories 10.1 + 10.2 HIGH-2):** **Decision:** non-empty `mcp_servers` returns `mcp_coverage="external_mixed"` per ADR-016 §Decision L33. Observer wiring deferred to DF-11.2-S1 carry-over (mirrors C73).

- **D-8 (HIGH — fresh from Story 11.1 kilo HIGH-1 lesson):** Copilot `assistant.message` events carry `outputTokens`; `session.shutdown` carries aggregate usage data. Empirical probe at `~/.copilot/session-state/391978f9-2453-418e-b611-4ab2bf354316/events.jsonl` confirmed. **Decision:** `Usage` dataclass already has `reasoning_output_tokens: int = 0` field (added Story 11.1 kilo HIGH-1 fix); if Copilot exposes a `reasoningTokens` field in `session.shutdown` or `assistant.message`, populate it. NO field drop. Pre-write empirical probe required per `feedback_listener_hook_api_surface_empirical_check`.

- **D-9 (HIGH — Copilot-specific architectural decision):** Spec L2059-2060 says "parses `~/.copilot/session-state/{uuid}/events.jsonl` for trace data." Copilot CLI does NOT stream events to stdout — events are written to disk only. **Decision:** override `SubprocessAdapter.run()` to do `spawn → proc.wait() → read events.jsonl post-hoc → call _finalize(events, exit_code)`. The `_parse_event(line)` hook is still used for per-line parsing, but iteration happens AFTER subprocess exit (not on proc.stdout). Capture the session UUID from stdout (first `session.start` event written gives it) OR by globbing for the newest session-state directory created during the run window. Mirrors Story 4.2's `run()` override precedent. Document inline.

- **D-10 (MED — fresh empirical probe):** Spec L2057 pins copilot binary at `v1.0.9+` (likely from the original epics.md L2057 ACR). Local probe at story-authoring: `GitHub Copilot CLI 1.0.54`. **Decision:** pin range `>=1.0.9,<2.0` (matches ADR-010 precedent + epics.md L2057). Below `1.0.9` predates the documented autopilot mode + events.jsonl trace format.

- **D-11 (MED — UPSTREAM Story 11.1 MED-1):** **Decision:** NO module-level `_VERSION_RE` dead-code constant. The base `_assert_binary_version`'s default `_SEMVER_RE.search()` extracts `1.0.54` from `GitHub Copilot CLI 1.0.54.` (note trailing period after the version — the base regex `(\d+\.\d+(?:\.\d+)?)` handles it via substring search).

- **D-12 (MED — UPSTREAM Story 11.1 MED-3):** **Decision:** add "Thread safety: NOT concurrent-safe" paragraph to `CopilotCLIAdapter` class docstring from the start. Same `_last_mcp_servers` stash pattern as Story 11.1.

## Acceptance Criteria

### AC-11.2.1 — Adapter implementation

`src/AgentEval/coding_agent/copilot_cli.py` implements `CopilotCLIAdapter(SubprocessAdapter)` per `src/AgentEval/coding_agent/base.py:229` (ADR-003 L24-29). Implements EXACTLY the 3 abstract hooks PLUS overrides `run()` per D-9:

- **`_spawn(prompt: str, **kwargs) -> subprocess.Popen[str]`** — launches `copilot --allow-all-tools -p "<prompt>"` (model defaults to copilot's selection) with `stderr=subprocess.STDOUT` multiplex (D-2), `stdout=subprocess.PIPE`, `text=True`, `start_new_session=True`.
- **`_parse_event(line: str) -> CopilotEvent | None`** — parses one JSONL line into a `CopilotEvent` dataclass; returns `None` on non-JSON / empty / non-event-type lines.
- **`_finalize(events: list[CopilotEvent], exit_code: int) -> AgentRunResult`** — folds events into `AgentRunResult` with: `response_text` (concatenation of `assistant.message.content` from non-`tool_request` events), `tool_calls` (projected from `assistant.message.toolRequests[]` + matching `tool.execution_complete` results), `usage` (Story 11.1 D-8 lesson: read from `session.shutdown` if present, else sum `assistant.message.outputTokens`), `cost_usd=0.0` (Copilot CLI doesn't surface cost in events — DF-11.2-S2 carry-over), `metadata.completeness` (`"complete"` on `session.shutdown` event present + `exit_code=0`), `metadata.mcp_coverage` per AC-11.2.2.
- **`run(prompt, tools, mcp_servers, **kwargs) -> AgentRunResult`** — overrides base per D-9 (post-hoc events.jsonl parse): spawns subprocess + waits + locates new `~/.copilot/session-state/{uuid}/events.jsonl` (created during the run window) + reads lines through `_parse_event` + calls `_finalize`. Wires `_record_run_metadata` per Story 10.1 HIGH-4 lesson UPSTREAM.

### AC-11.2.2 — `mcp_coverage` honesty per ADR-016 §Decision L33 (D-7)

- Empty / `None` `mcp_servers`: `mcp_coverage = "hosted_in_process"`.
- Non-empty `mcp_servers` without verified hosted-attachment: `mcp_coverage = "external_mixed"` per ADR-016 §Decision L33 safer-default rule.
- `HostedMcpObserver` wiring is DF-11.2-S1 carry-over (mirrors Story 11.1's C73 + Story 10.1's C68 + Story 10.2's C69).

Docstring documents the 2-branch detection contract inline, citing ADR-016 §Decision L33 verbatim.

### AC-11.2.3 — Entry-point + pyproject extra + version gate

`pyproject.toml` amended:
- `[project.optional-dependencies]` entry: `copilot = []` (no Python deps; binary on `$PATH` — mirrors Story 4.2 + 11.1 pattern).
- `[project.entry-points."agenteval.coding_agents"]` entry: `copilot-cli = "AgentEval.coding_agent.copilot_cli:CopilotCLIAdapter"`.

`__init__` calls `_assert_binary_version("copilot", ">=1.0.9,<2.0")` via the existing helper. Raises `UnsupportedBinaryVersionError` when out of range or missing.

### AC-11.2.4 — Unit tests (≥30 tests; mirror Story 11.1 patterns)

`tests/unit/coding_agent/test_copilot_cli.py` MUST cover:

- Construction + 4 version-gate tests (missing-binary + below-floor + above-ceiling + in-range) — via `mock_copilot_version` autouse fixture in `tests/unit/coding_agent/conftest.py` (D-4).
- `_parse_event` per event type (`session.start`, `session.model_change`, `session.shutdown`, `user.message`, `assistant.turn_start`, `assistant.turn_end`, `assistant.message`, `tool.execution_start`, `tool.execution_complete`, `None` on non-JSON, `None` on unknown type).
- `_finalize` against 3 fixtures: `simple_prompt.jsonl` (happy path), `tool_use.jsonl` (toolRequests + tool.execution events), `nonzero_exit.jsonl` (subprocess exit_code != 0).
- **Cross-story UPSTREAM regression guards** (per `feedback_cross_story_upstream_lesson_propagation` 2nd application):
  - `test_spawn_passes_prompt_via_prompt_flag` (D-1)
  - `test_spawn_uses_stderr_stdout_multiplex` (D-2)
  - `test_spawn_uses_start_new_session_true` + `--allow-all-tools` flag (D-1/Story 1b.4)
  - `test_finalize_nonzero_exit_with_no_message_emits_diagnostic` (D-3)
  - `test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic` (Story 11.1 copilot MED-4 lesson — negative-path).
  - `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic` (same).
  - `test_run_end_to_end_against_faked_subprocess` — drives the full `run()` template-method chain end-to-end with a faked Popen + monkeypatched events.jsonl path.
  - `test_run_with_unverified_mcp_marks_external_mixed` (D-7).
  - `test_extract_usage_includes_reasoning_output_tokens` if Copilot surfaces a reasoning-tokens field anywhere in events (Story 11.1 kilo HIGH-1 lesson — empirical probe required).
- Entry-point registration test.

### AC-11.2.5 — Integration test gated behind env flag

`tests/integration/test_copilot_cli_live.py` skipped unless `os.environ.get("AGENTEVAL_INTEGRATION_TESTS") == "1"` AND `copilot` binary is on `$PATH` AND a valid Copilot login session exists.

### AC-11.2.6 — Conformance + stability surface

- Conformance smoke via `test_entry_point_registration` in the unit suite.
- `docs/contracts/stability-surface.md` amended: add `CopilotCLIAdapter` row at `experimental`.

### AC-11.2.7 — All-gates pass

- `uv run pytest tests/ -q --no-header` — expected `1641 + new tests` pass + 11 skipped (current HEAD: 1641 + 11).
- `uv run ruff check src/ tests/` + `uv run ruff format --check src/ tests/` — clean.
- `uv run mypy src/` — `Success: no issues found in 98 source files` (97 + new `copilot_cli.py`).

### AC-11.2.8 — `feedback_carry_over_catalog_gate` UPSTREAM (27th consecutive)

Surface DF-11.2-S1 (`HostedMcpObserver` wiring for Copilot MCP) + DF-11.2-S2 (cost-catalog integration for Copilot pricing) entries in `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review. Catalog total after this story: 74 → 76.

### AC-11.2.9 — Caller-count check

The new public surface (`CopilotCLIAdapter`) has callers via the conformance smoke + unit-test suite + entry-point smoke + integration test. Zero 0-caller helpers added.

### AC-11.2.10 — Cross-story UPSTREAM lesson propagation summary (2nd use of `feedback_cross_story_upstream_lesson_propagation`)

This story applies **12 cross-story UPSTREAM lessons** (D-1 through D-12 above) from Stories 4.2 + 10.1 + 10.2 + **11.1 (NEW source — 1st N+1 follow-up story validating the norm)**:

From Story 11.1 review record specifically (the UPSTREAM seed paragraph in 11.1's Senior Developer Review):
- `Usage(reasoning_output_tokens=)` field populated if applicable (D-8 + Story 11.1 kilo HIGH-1)
- NO module-level `_VERSION_RE` dead-code constant (D-11 + Story 11.1 MED-1)
- Class-docstring thread-safety paragraph from start (D-12 + Story 11.1 MED-3)
- Negative-path tests for diagnostic gate (AC-11.2.4 + Story 11.1 copilot MED-4)
- ADR-016 §Decision L33 citation discipline (D-6 + Story 11.1 copilot MED-2)

Per `feedback_cross_story_upstream_lesson_propagation` operational trigger: at `/bmad-create-story` time, grep prior same-surface story for `^### HIGH` + `^### MED` headings; fold each as AC requirement.

## Tasks / Subtasks

- [ ] **Task 1** — Add `[copilot] = []` extra + `copilot-cli` entry-point to `pyproject.toml`.
- [ ] **Task 2** — Implement `src/AgentEval/coding_agent/copilot_cli.py`:
  - [ ] `CopilotEvent` frozen dataclass mirroring the 10-event schema (D-8 empirical probe).
  - [ ] `CopilotCLIAdapter(SubprocessAdapter)` with `__init__(*, model=None, **kwargs)` → `_assert_binary_version("copilot", ">=1.0.9,<2.0")`.
  - [ ] `_spawn(prompt, tools, mcp_servers, **kwargs)` per AC-11.2.1 + D-1 + D-2.
  - [ ] `_parse_event(line)` per AC-11.2.1.
  - [ ] `_finalize(events, exit_code)` per AC-11.2.1 + D-3 + D-8 (reasoning_output_tokens populated if present).
  - [ ] `_detect_mcp_coverage(mcp_servers)` per AC-11.2.2 + D-7.
  - [ ] `run()` OVERRIDE per D-9 — post-hoc events.jsonl read.
  - [ ] `_record_run_metadata` wiring per Story 10.1 HIGH-4 UPSTREAM.
  - [ ] Class docstring includes "Thread safety: NOT concurrent-safe" paragraph from start (D-12).
- [ ] **Task 3** — Add `mock_copilot_version` autouse fixture to `tests/unit/coding_agent/conftest.py` (D-4).
- [ ] **Task 4** — Create 3 fixtures under `tests/fixtures/copilot_cli/` (`simple_prompt.jsonl`, `tool_use.jsonl`, `nonzero_exit.jsonl`).
- [ ] **Task 5** — Implement `tests/unit/coding_agent/test_copilot_cli.py` per AC-11.2.4 (≥30 tests including all Story 11.1 cross-story regression guards).
- [ ] **Task 6** — Implement `tests/integration/test_copilot_cli_live.py` per AC-11.2.5.
- [ ] **Task 7** — Amend `docs/contracts/stability-surface.md` adding `CopilotCLIAdapter` at `experimental`.
- [ ] **Task 8** — Pre-write fake-green precheck per `feedback_test_name_assertion_match`.
- [ ] **Task 9** — Carry-over catalog gate UPSTREAM (27th consecutive): surface DF-11.2-S1 + DF-11.2-S2 in `docs/phase-1-5-carry-overs.md`.
- [ ] **Task 10** — All-gates run.

## Dev Notes

### Empirical events.jsonl schema (probe 2026-05-26)

Captured via behavioral probe BEFORE writing this adapter per
`feedback_listener_hook_api_surface_empirical_check`. The 10 event types
(probe at `~/.copilot/session-state/391978f9-2453-418e-b611-4ab2bf354316/events.jsonl`):

- `session.start` — carries `sessionId`, `copilotVersion`, `context.cwd`, etc.
- `session.model_change` — carries `newModel`.
- `session.shutdown` — terminal event; carries aggregate usage if any.
- `user.message` — carries `content`.
- `assistant.turn_start` — carries `turnId`, `interactionId`.
- `assistant.turn_end` — turn boundary.
- `assistant.message` — model output; carries `content`, `toolRequests[]` (with `toolCallId`, `name`, `arguments`, `mcpServerName`, `mcpToolName`), `outputTokens`, optional `reasoningOpaque`/`reasoningText`.
- `tool.execution_start` — carries `toolCallId`, `toolName`, `arguments`, optional `mcpServerName`/`mcpToolName`.
- `tool.execution_complete` — carries `toolCallId`, `success`, `result`, `model`.

### Story 11.1 lessons applied UPSTREAM (the explicit goal of `feedback_cross_story_upstream_lesson_propagation` 2nd use)

This is the **2nd story to apply the UPSTREAM-lesson-propagation norm** (Story 11.1 was the first; this is the next same-surface SubprocessAdapter transition). All Story 11.1 patches are folded into Story 11.2's AC text BEFORE any code is written — see drift check D-8 through D-12 + AC-11.2.4 mandates.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

Story 11.2 dev complete 2026-05-26 → v0.3.0 cross-LLM-reviewed. **2nd story under the ratified 3-tier cross-LLM review chain + 2nd validation of `feedback_cross_story_upstream_lesson_propagation`.**

- **AC-11.2.1**: `CopilotCLIAdapter(SubprocessAdapter)` at `src/AgentEval/coding_agent/copilot_cli.py` with `run()` OVERRIDE for post-hoc events.jsonl parsing (D-9; first adapter to need this pattern).
- **AC-11.2.2**: ADR-016 §Decision L33 honest 2-branch contract.
- **AC-11.2.3**: `[copilot] = []` extra + `copilot-cli` entry-point + base `_assert_binary_version` handles `GitHub Copilot CLI 1.0.54.` trailing-period format via substring search.
- **AC-11.2.4**: 38 unit tests (was 32; +5 _parse_event coverage per copilot M-3 + 1 standalone start_new_session per copilot+kilo M-2).
- **AC-11.2.5**: env-gated integration test.
- **AC-11.2.6**: conformance smoke via `test_entry_point_registration`.
- **AC-11.2.7**: 1673 pytest pass + 12 skipped (was 1641 + 11; +32 + 1 env-gated; further +6 post-review). ruff/format/mypy clean (98 src files).
- **AC-11.2.8**: 27th consecutive `feedback_carry_over_catalog_gate` UPSTREAM; added C75 + C76 + **C77 (added post-review per copilot M-1 catch — DF-11.2-S3 was inline-referenced without catalog row)**.
- **AC-11.2.9**: Caller-count check passes.
- **AC-11.2.10**: 12 cross-story UPSTREAM lessons applied. 5/5 UPSTREAM verified by BOTH reviewers.

### File List

**New files:**
- `src/AgentEval/coding_agent/copilot_cli.py` — `CopilotCLIAdapter(SubprocessAdapter)` + `CopilotEvent` + `run()` override for post-hoc events.jsonl parsing (~360 LoC).
- `tests/unit/coding_agent/test_copilot_cli.py` — 38 unit tests.
- `tests/integration/test_copilot_cli_live.py` — env-gated live integration test.
- `tests/fixtures/copilot_cli/{simple_prompt,tool_use,nonzero_exit}.jsonl` — 3 fixtures.

**Modified files:**
- `pyproject.toml` — `[copilot]` extra + `copilot-cli` entry-point.
- `tests/unit/coding_agent/conftest.py` — `mock_copilot_version` autouse fixture.
- `docs/contracts/stability-surface.md` — `CopilotCLIAdapter` row at `experimental`.
- `docs/phase-1-5-carry-overs.md` — C75 + C76 + C77 entries; total 74 → 77.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Senior Developer Review (AI)

**Date:** 2026-05-26
**Reviewers:** 3-tier cross-LLM chain (per `CLAUDE.md` ratified Epic 10 retro):
- **Tier-1 Copilot CLI** (`copilot -p --model claude-sonnet-4.6`): substantive, 1 HIGH + 3 MED + 3 LOW
- **Tier-2 Codex CLI**: DEGRADED (rate-limit, retry 23:38; same as Story 11.1)
- **Tier-3 kilo/minimax-M2.7**: substantive, 1 HIGH + 3 MED + 2 LOW

**Outcome:** Changes Requested → Resolved. **2nd story-level validation of the 3-tier chain orthogonal-coverage hypothesis** + 2nd validation of `feedback_cross_story_upstream_lesson_propagation` at N=2.

### Orthogonal coverage demonstrated

The 2 available reviewers caught **DIFFERENT classes of drift** + **caught each other's mistakes**:

- **Copilot UNIQUE findings (kilo missed)**: M-1 (DF-11.2-S3 catalog gate violation), M-3 (5 of 11 AC-required `_parse_event` event-type tests missing).
- **Kilo UNIQUE findings (copilot missed)**: M-3 (events.jsonl post-exit flush race window).
- **BOTH caught**: H-1 (`trace_id=""` inconsistency vs codex precedent), M-2 (standalone `test_spawn_uses_start_new_session_true` missing).
- **Cross-check (copilot caught kilo's mistake)**: kilo's M-1 ("31 tests, docstring says 32") was a **false positive** — copilot's independent grep confirmed 32 tests; kilo's enumeration mis-counted by 1.

### Patches applied (all HIGH + all real MED)

- **H-1 (both)**: Added inline placeholder comment to `copilot_cli.py:462` mirroring `codex_cli.py:472` documented-placeholder pattern + amended stability-surface.md row with Phase-1 placeholders enumerated.
- **M-1 copilot (UNIQUE)**: Added C77 entry to `docs/phase-1-5-carry-overs.md` for `DF-11.2-S3` (session-state-dir race + events.jsonl post-exit flush race). Catalog 76 → 77. Verified gate-violation correction: 27th UPSTREAM gate now passes with full catalog coverage of every `DF-X-SY` reference in the codebase.
- **M-2 (both)**: Added standalone `test_spawn_uses_start_new_session_true` with explicit Story 1b.4 D1 process-group hygiene regression-guard docstring. Test count 32 → 33 unit tests + 5 = 38.
- **M-3 copilot (UNIQUE)**: Added 5 trivial `_parse_event` tests for `session.model_change`, `user.message`, `assistant.turn_start`, `assistant.turn_end`, `tool.execution_start` per AC-11.2.4 "MUST cover" mandate. Test count → 38.
- **M-3 kilo (UNIQUE)**: Documented in C77 carry-over (above) — events.jsonl post-exit flush race is the Phase-2 robustness path.

**Accepted as-is (LOW):**
- L-1 (both): `reasoningOpaque`/`reasoningText` not exposed via accessors — Phase-2 if real consumer hits this.
- L-2 (both): fixture documentation note — no action.
- L-3 (copilot): kilo M-1 false-positive cross-check — recorded; no fix needed.

### Significance

- **2nd story-level validation of the 3-tier orthogonal-coverage hypothesis** (1st = Story 11.1). Two consecutive stories now show: each reviewer catches findings the other misses + at least one catches a counter-finding the other got wrong. The 3-tier chain's value is no longer hypothetical at code-review level.
- **2nd validation of `feedback_cross_story_upstream_lesson_propagation`** at N=2: 5/5 Story 11.1 UPSTREAM lessons were independently verified applied by BOTH reviewers. Promotes the norm from "validated N=1" to "validated N=2" — graduates to a structurally-trustworthy pattern.
- **Codex still rate-limited** across Story 11.1 + 11.2 (retry 23:38). Tiers 1 + 3 carrying full coverage. No degradation in catch quality.

### Gates after patches

- `uv run pytest tests/ -q --no-header` → expected ~**1679 passed + 12 skipped** (was 1673 + 12 + 6 new tests).
- `uv run ruff check src/ tests/` → All checks passed.
- `uv run mypy src/` → Success: no issues found in 98 source files.

### Cross-story UPSTREAM seed for Story 11.3 (AdapterVersionDriftWarning)

Story 11.3 is the FR60 fan-in story that touches all 3 CLI adapters (Story 4.2 + 11.1 + 11.2). Cross-story UPSTREAM-seed items for Story 11.3 pre-create drift check:
- ALL Story 11.1 + 11.2 UPSTREAM lessons (12 + 12 = ~20 unique).
- **NEW from this review:** any new public symbol must be in `docs/phase-1-5-carry-overs.md` BEFORE merge IF it ships a `DF-X-SY` reference (the C77 catch).
- **NEW from this review:** any AC-mandated test list MUST be empirically counted via `grep "^def test_"` AND match the docstring claim (counter-validates the kilo M-1 false-positive class).
- **NEW from this review:** `trace_id=""` placeholders MUST carry the explicit Phase-1-deferral inline comment per the codex_cli.py precedent.
- **NEW from this review:** if any Phase-1 placeholder is added to a new adapter, the stability-surface row MUST enumerate it (mirrors the Story 11.2 stability-surface entry).

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-26 | 0.3.0 | Cross-LLM 3-tier review APPLIED v2. 1 HIGH (both reviewers) + 3 MED (5 unique findings combined) patched + 3 LOW accepted. **2nd story-level validation of 3-tier orthogonal-coverage hypothesis** — copilot UNIQUE catches: M-1 catalog-gate (DF-11.2-S3 → C77) + M-3 5 missing AC-required tests; kilo UNIQUE catch: M-3 events.jsonl post-exit flush race window. Copilot ALSO caught kilo's M-1 as a false positive (independent grep confirms 32 tests). Codex still rate-limited (retry 23:38). Catalog 76 → 77 (added C77 via the copilot M-1 catch). Test count 32 → 38 (+5 _parse_event coverage + 1 standalone start_new_session). **2nd validation of `feedback_cross_story_upstream_lesson_propagation` at N=2** — 5/5 Story 11.1 UPSTREAM lessons independently verified applied by BOTH reviewers. Status → done. | Amelia |
| 2026-05-26 | 0.2.0 | Dev complete. 32 unit tests + 1 env-gated integration test. `run()` override for post-hoc events.jsonl reading (D-9). 1673 pytest pass + 12 skipped (was 1641 + 11; +32 + 1). ruff/format/mypy clean (98 src files). 27th consecutive `feedback_carry_over_catalog_gate` UPSTREAM (added C75 + C76; catalog 74 → 76). Status → review. | Amelia |
| 2026-05-26 | 0.1.0 | Initial story creation (ready-for-dev). **46th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact across 46 consecutive uses). **2nd use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification — validates norm at N=2.** 12 drifts caught (11 UPSTREAM from Stories 4.2 + 10.1 + 10.2 + 11.1 + 1 fresh from empirical events.jsonl probe). 10 ACs. Empirical Copilot events.jsonl 10-event schema probed pre-write at `~/.copilot/session-state/391978f9-*/events.jsonl`. | Bob |
