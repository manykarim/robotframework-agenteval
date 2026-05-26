# Story 11.1: Codex CLI Adapter

Status: done

## Story

As **Raj (Agent Developer)** working with OpenAI's coding agent ecosystem,
I want a `CodexCLIAdapter(SubprocessAdapter)` invoking the `codex` CLI binary via its non-interactive `codex exec --json` JSONL surface,
so that I can run Codex CLI agent workflows under the same unified `CodingAgentAdapter` Protocol that powers the Claude Code CLI adapter (Story 4.2) — and start the Epic 11 fan-in toward the FR60 `AdapterVersionDriftWarning` ratification (Story 11.3).

## Pre-create-story drift check (45th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-26)

11 drifts caught — 9 resolved via cross-story-upstream-lesson-propagation (1st use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification) + 2 fresh decisions from empirical probe. **100% real-drift catch rate intact across 45 consecutive uses.**

- **D-1 (HIGH — cross-story UPSTREAM from Story 4.2 HIGH-A):** Spec implies the adapter must pipe the user prompt into the codex subprocess but `epics.md` L2041 is silent on prompt-delivery mechanism. Story 4.2 review HIGH-A (3-way: Blind H1 + Edge-cases H1 + Codex Probe 5) caught the prompt-never-fed-to-stdin bug. **Decision:** pass `prompt` as positional argv after end-of-options sentinel — per `codex exec --help` "Initial instructions for the agent. If not provided as an argument (or if `-` is used), instructions are read from stdin." Positional argv is the safer wiring (matches Story 4.2 resolution). AC-11.1.4 mandates a `test_spawn_passes_prompt_as_positional_argv` regression-guard mirroring Story 4.2's analogous test.

- **D-2 (HIGH — cross-story UPSTREAM from Story 4.2 HIGH-B):** Spec L2041 silent on stderr handling. Story 4.2 review HIGH-B (2-way: Edge-cases H2 + Codex independent flag) caught a stderr pipe deadlock where `stderr=subprocess.PIPE` + base `run()` only draining stdout → stderr-full child blocks → parent wedges. **Decision:** `stderr=subprocess.STDOUT` multiplex into stdout; `_parse_event` returns `None` on non-JSON lines so diagnostics are cleanly skipped. AC-11.1.4 mandates `test_spawn_uses_stderr_stdout_multiplex` regression-guard.

- **D-3 (HIGH — cross-story UPSTREAM from Story 4.2 MED-3):** Spec L2041 silent on non-zero exit handling. Story 4.2 review MED-3 (Codex independent finding) caught that silent return of `response_text=""` on subprocess non-zero exit indistinguishably masks "agent declined to respond" from "binary refused to run." **Decision:** `_finalize` surfaces a `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic marker when there's no terminal event AND no assistant text. M_R11 fail-loud applied. AC-11.1.4 mandates `test_finalize_nonzero_exit_with_no_message_emits_diagnostic`.

- **D-4 (HIGH — cross-story UPSTREAM from Story 4.2 MED-1 — autouse fixture hoist):** Story 4.2 review MED-1 (Edge-cases MED-1) moved the `mock_claude_version` autouse fixture from `test_claude_code_cli.py` to `tests/unit/coding_agent/conftest.py` so future cross-module tests inherit the mock automatically. **Decision:** new `mock_codex_version` autouse fixture goes DIRECTLY into `tests/unit/coding_agent/conftest.py` from the start — NO test-file-local autouse. Eliminates the CI fake-green class for Story 11.1 + Story 11.2's `mock_copilot_version` (same conftest).

- **D-5 (HIGH — cross-story UPSTREAM from Story 4.2 Auditor HIGH-1):** Spec L2041 cites "FR47 binary check" — Story 4.2 review confirmed the per-CLI binary-version-pinning pattern is ADR-002 (Tier-1 Adapter Ceiling Rule), NOT ADR-005 (which actually ratifies conformance-suite fidelity oracles). **Decision:** all references in the new adapter file + this story spec cite **ADR-002** + **ADR-010 precedent** (the original per-CLI version-pinning ADR cited by Story 4.2). Inline citation hygiene from the start.

- **D-6 (HIGH — cross-story UPSTREAM from Epic 10 ADR-A6 renumbering):** Story 10.1 kilo MED-2 caught that `ADR-A6 L384` is renumbered to `ADR-016 §Decision L33`. **Decision:** all `mcp_coverage` references in this adapter cite **ADR-016 §Decision L33** verbatim (NOT `ADR-A6`); same applies to docstring + carry-over entries Story 11.1 creates.

- **D-7 (MED — cross-story UPSTREAM from Story 10.1 HIGH-2 + Story 10.2 D-4):** Spec implies `mcp_coverage="hosted_in_process"` for Codex MCP integration but ADR-016 §Decision L33 mandates `external_mixed` on detection failure (safer-default rule). **Decision:** mirror the Stories 10.1 + 10.2 post-HIGH-2 contract — empty `mcp_servers` → `hosted_in_process` (trivially honest); non-empty `mcp_servers` → `external_mixed` until proper `HostedMcpObserver` wiring lands (DF-11.1-S1 carry-over). Codex JSONL events do NOT surface MCP-attachment confirmation in the empirical probe (`thread.started` / `turn.started` / `item.completed` / `turn.completed` only), so detection-failure path is the only honest default.

- **D-8 (MED — empirical probe finding):** Spec L2041 cites generic "Codex's output format" but `codex exec --json` emits a **specific 4-event schema** confirmed empirically 2026-05-26: `thread.started` (carries `thread_id`); `turn.started` (no payload); `item.started` / `item.completed` (carries `item: {id, type, text|command|aggregated_output|exit_code|status}` — `type` ∈ `{"agent_message", "command_execution"}`); `turn.completed` (carries `usage: {input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}`). **Decision:** Phase-1 `CodexEvent` dataclass mirrors the 4 event types verbatim; `_parse_event` returns `None` on unknown types (forward-compat); fixtures capture the empirical probe output verbatim.

- **D-9 (MED — empirical probe finding):** `turn.completed.usage` has NO `cost_usd` field (unlike Claude Code's `total_cost_usd`). Codex pricing is `gpt-5-codex`-tier (not in Phase-1 cost catalog). **Decision:** Phase-1 ships `cost_usd=0.0` placeholder with explicit docstring note + DF-11.1-S2 carry-over for cost-catalog integration. Mirrors Story 4.2's Phase-1 placeholder pattern.

- **D-10 (LOW — empirical probe finding):** `codex --version` outputs `codex-cli 0.133.0` (note the `codex-cli` prefix, NOT bare `codex`). FR47 binary-version-gate regex must account for the `codex-cli ` prefix. **Decision:** `_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")` — match Story 4.2's `_VERSION_RE` pattern but with prefix change.

- **D-11 (LOW — pin range decision):** Spec L2043 says "version pinned via FR47 binary check" but doesn't pin a range. **Decision:** `[codex] = []` optional-extras (no Python deps; `codex` binary must be on `$PATH` per Story 4.2 precedent); compat range `>=0.100.0,<1.0` (current local `0.133.0` is in range; allows minor bumps until 1.0). Below `0.100.0` predates the documented `--json` stream-output flag.

## Acceptance Criteria

### AC-11.1.1 — Adapter implementation

`src/AgentEval/coding_agent/codex_cli.py` implements `CodexCLIAdapter(SubprocessAdapter)` per `src/AgentEval/coding_agent/base.py:229` (ADR-003 L24-29). Implements EXACTLY the 3 abstract hooks:

- **`_spawn(prompt: str, **kwargs) -> subprocess.Popen[str]`** — launches `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json` with prompt as positional argv (D-1), `stderr=subprocess.STDOUT` multiplex (D-2), `stdout=subprocess.PIPE`, `text=True`, `start_new_session=True` (per Story 1b.4 D1 process-group hygiene).
- **`_parse_event(line: str) -> CodexEvent | None`** — parses one stdout JSONL line into a `CodexEvent` dataclass; returns `None` on non-JSON / empty / non-event-type lines (forward-compat).
- **`_finalize(events: list[CodexEvent], exit_code: int) -> AgentRunResult`** — folds the chronological event stream into `AgentRunResult` with: `response_text` (concatenation of `item.completed` events where `item.type == "agent_message"`), `tool_calls` (list of `ToolCallTrace` projected from `item.completed` where `item.type == "command_execution"`; Phase-1 placeholders `result=aggregated_output`, `error=None` on `exit_code=0` else `f"exit_code={exit_code}"`, `latency_ms=0.0`, `source="adapter"`), `usage` (from final `turn.completed.usage`), `cost_usd=0.0` (D-9), `metadata.completeness` (`"complete"` on `turn.completed` present + `exit_code=0`; `"truncated"` otherwise), `metadata.mcp_coverage` per AC-11.1.2.

### AC-11.1.2 — `mcp_coverage` honesty per ADR-016 §Decision L33 (D-7)

- `mcp_servers` is `None` or empty: `mcp_coverage = "hosted_in_process"` (trivially honest — nothing to cover).
- `mcp_servers` is non-empty AND no verified hosted-attachment signal exists in the JSONL event stream: `mcp_coverage = "external_mixed"` per ADR-016 §Decision L33 safer-default rule.
- The `HostedMcpObserver` wiring that would upgrade non-empty MCP to `hosted_in_process` empirically is **DF-11.1-S1 carry-over** (mirrors Story 10.2's DF-10.2-S1).

Docstring MUST document the 2-branch detection contract inline, citing ADR-016 §Decision L33 verbatim (NOT ADR-A6).

### AC-11.1.3 — Entry-point + pyproject extra + version gate

`pyproject.toml` amended:

- `[project.optional-dependencies]` entry: `codex = []` (no Python deps; binary on `$PATH` — mirrors Story 4.2's `claude-code = []`).
- `[project.entry-points."agenteval.coding_agents"]` entry: `codex-cli = "AgentEval.coding_agent.codex_cli:CodexCLIAdapter"`.

`__init__` calls `_assert_binary_version("codex", ">=0.100.0,<1.0")` via the existing `SubprocessAdapter._assert_binary_version` helper (Story 1b.4) using regex `_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")` (D-10). Raises `UnsupportedBinaryVersionError` (already declared in `errors.py`) when out of range or missing.

### AC-11.1.4 — Unit tests (mirror Story 4.2 + cross-story regression guards)

`tests/unit/coding_agent/test_codex_cli.py` MUST cover (minimum 25 tests):

- Construction + 4 version-gate tests (missing-binary + below-floor + above-ceiling + in-range) — via `mock_codex_version` autouse fixture in `tests/unit/coding_agent/conftest.py` (D-4).
- `_parse_event` per event type (`thread.started`, `turn.started`, `item.started`, `item.completed:agent_message`, `item.completed:command_execution`, `turn.completed`, `None` on non-JSON, `None` on unknown type).
- `_finalize` against 4 fixtures: `simple_prompt.jsonl` (happy path), `tool_use.jsonl` (command_execution), `truncated.jsonl` (missing terminal), `nonzero_exit.jsonl` (subprocess exit_code != 0).
- **Cross-story UPSTREAM regression guards** (per `feedback_cross_story_upstream_lesson_propagation` first application):
  - `test_spawn_passes_prompt_as_positional_argv` (D-1 — Story 4.2 HIGH-A mirror)
  - `test_spawn_uses_stderr_stdout_multiplex` (D-2 — Story 4.2 HIGH-B mirror)
  - `test_spawn_uses_start_new_session_true` (Story 1b.4 D1 process-group hygiene mirror)
  - `test_finalize_nonzero_exit_with_no_message_emits_diagnostic` (D-3 — Story 4.2 MED-3 mirror)
  - `test_run_end_to_end_against_faked_subprocess` — drives the full template-method `run()` chain end-to-end with a faked Popen replaying `simple_prompt.jsonl` (Story 4.2 Blind H2 closure mirror).
  - `test_run_with_unverified_mcp_marks_external_mixed` (D-7 — Story 10.1 HIGH-2 + Story 10.2 D-4 mirror).
- Entry-point registration test via `importlib.metadata.entry_points`.

### AC-11.1.5 — Integration test gated behind env flag

`tests/integration/test_codex_cli_live.py` skipped unless `os.environ.get("AGENTEVAL_INTEGRATION_TESTS") == "1"` AND `codex` binary is on `$PATH` AND a valid Codex login session exists. The live test runs `codex exec --json "Say hi"` against the real binary + asserts `response_text` non-empty + `usage.output_tokens > 0` + `mcp_coverage="hosted_in_process"` (empty `mcp_servers` path).

### AC-11.1.6 — Conformance + stability surface

- Conformance smoke: `test_entry_point_registration` in the unit suite (verifies `importlib.metadata.entry_points` returns `CodexCLIAdapter` under `agenteval.coding_agents`). Mirrors Story 10.1's reframed AC-10.1.6 (no `tests/conformance/test_adapter_conformance.py` file invented; in-suite smoke is the conformance check).
- `docs/contracts/stability-surface.md` amended: add `CodexCLIAdapter` row at `experimental` (per Epic 9 retro Action #3 — Phase-2 adapters land at `experimental`; may promote to `stable` after 3-month no-break window).

### AC-11.1.7 — All-gates pass

- `uv run pytest tests/ -q --no-header` — expected `1605 + new tests` pass + 10 skipped (current HEAD at this story's start: 1605 + 10).
- `uv run ruff check src/ tests/` + `uv run ruff format --check src/ tests/` — clean.
- `uv run mypy src/` — `Success: no issues found in 97 source files` (96 + new `codex_cli.py`).

### AC-11.1.8 — `feedback_carry_over_catalog_gate` UPSTREAM (24th consecutive)

Surface DF-11.1-S1 (`HostedMcpObserver` wiring for Codex MCP) + DF-11.1-S2 (cost-catalog integration for Codex pricing) entries in `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review per the UPSTREAM gate. Catalog total after this story: 72 → 74.

### AC-11.1.9 — Caller-count check

The new public surface (`CodexCLIAdapter`) has callers via the conformance smoke + unit-test suite + entry-point smoke + integration test. Zero 0-caller helpers added.

### AC-11.1.10 — Cross-story UPSTREAM lesson propagation summary (first use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification)

This story applies **9 cross-story UPSTREAM lessons** (D-1 through D-7 above + the `mock_codex_version` conftest placement + the ADR-A6 → ADR-016 citation discipline) from Stories 4.2 + 10.1 + 10.2. Each is folded into the AC text above as an explicit requirement, NOT as a "nice to have." Per `feedback_cross_story_upstream_lesson_propagation` operational trigger: at `/bmad-create-story` time, grep prior same-surface story for `^### HIGH` + `^### MED` headings; fold each as AC requirement. Verified via `grep -E "^### HIGH|^### MED|^- \*\*HIGH" _bmad-output/implementation-artifacts/4-2-claude-code-cli-adapter.md` → all caught lessons are in AC text above.

## Tasks / Subtasks

- [ ] **Task 1** — Add `[codex] = []` extra to `pyproject.toml` + `codex-cli = "AgentEval.coding_agent.codex_cli:CodexCLIAdapter"` entry-point under `[project.entry-points."agenteval.coding_agents"]`. Preserve existing `claude-code` + `generic` + `claude-code-cli` + `claude-sdk` + `openai-agents` entries.
- [ ] **Task 2** — Implement `src/AgentEval/coding_agent/codex_cli.py`:
  - [ ] `CodexEvent` frozen dataclass mirroring the 4-event schema (D-8 empirical probe).
  - [ ] `CodexCLIAdapter(SubprocessAdapter)` with `__init__(*, model=None, **kwargs)` → calls `_assert_binary_version("codex", ">=0.100.0,<1.0")` with `_VERSION_RE` per D-10.
  - [ ] `_spawn(prompt, tools=None, mcp_servers=None, **kwargs)` per AC-11.1.1 + D-1 + D-2.
  - [ ] `_parse_event(line)` per AC-11.1.1 (returns `CodexEvent | None`).
  - [ ] `_finalize(events, exit_code)` per AC-11.1.1 + D-3 + D-9 (cost-zero placeholder).
  - [ ] `_detect_mcp_coverage(mcp_servers)` per AC-11.1.2 + D-7 (ADR-016 §Decision L33).
  - [ ] `_record_run_metadata` invoked at end of `run()` (lazy-import from `coding_agent/generic.py`; mirrors Story 10.1 HIGH-4 + Story 10.2 D-6 UPSTREAM).
  - [ ] Docstring documents D-1..D-11 resolutions inline (so future readers know why the adapter has the regression-guard tests).
- [ ] **Task 3** — Add `mock_codex_version` autouse fixture to `tests/unit/coding_agent/conftest.py` (D-4 — UPSTREAM from start).
- [ ] **Task 4** — Create 4 fixtures under `tests/fixtures/codex_cli/` (`simple_prompt.jsonl` from `/tmp/codex_probe.jsonl` empirical capture; `tool_use.jsonl` from `/tmp/codex_tool_probe.jsonl`; `truncated.jsonl` synthetic; `nonzero_exit.jsonl` synthetic).
- [ ] **Task 5** — Implement `tests/unit/coding_agent/test_codex_cli.py` per AC-11.1.4 (≥25 tests).
- [ ] **Task 6** — Implement `tests/integration/test_codex_cli_live.py` per AC-11.1.5 (env-gated).
- [ ] **Task 7** — Amend `docs/contracts/stability-surface.md` adding `CodexCLIAdapter` at `experimental`.
- [ ] **Task 8** — Pre-write fake-green precheck per `feedback_test_name_assertion_match` — every test's assertion body MUST deliver on the test name's promise.
- [ ] **Task 9** — Carry-over catalog gate UPSTREAM (24th consecutive): surface DF-11.1-S1 + DF-11.1-S2 entries in `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review. Catalog total 72 → 74.
- [ ] **Task 10** — All-gates run (pytest + ruff + format + mypy).

## Dev Notes

### Source citations + drift context

- **`SubprocessAdapter` ABC**: `src/AgentEval/coding_agent/base.py:229-340` — abstract template-method pattern per ADR-003 L24-29. Exactly 3 abstract hooks: `_spawn`, `_parse_event`, `_finalize`. Process-group cleanup-on-exception per Story 1b.4 D1.
- **`_assert_binary_version` helper**: `src/AgentEval/coding_agent/base.py` (Story 1b.4) — raises `UnsupportedBinaryVersionError` on out-of-range.
- **`UnsupportedBinaryVersionError`**: declared in `src/AgentEval/errors.py` (Story 1b.3).
- **`AgentRunResult` + `AgentRunMetadata` + `ToolCallTrace` + `Usage`**: `src/AgentEval/types.py` — frozen dataclass shapes per Story 1b.4.
- **`enforce_tier1_no_llm`**: `src/AgentEval/_kernel/tier_acl.py`. NOT called by SubprocessAdapter `run()` (subprocess adapters are out-of-process by design; Tier-1 enforcement is the caller's responsibility per ADR-019). Story 4.2 + 11.1 do NOT call this in adapter code.
- **Story 4.2 ClaudeCodeCLIAdapter precedent**: `src/AgentEval/coding_agent/claude_code_cli.py:183` — canonical SubprocessAdapter implementation. ALL pattern decisions (regex, hooks, `_record_run_metadata` wiring, fixture organization) mirror this file.
- **Codex CLI binary**: `codex-cli` v0.133.0 (empirical probe 2026-05-26). `--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json "<prompt>"` is the canonical non-interactive invocation. Pin range `>=0.100.0,<1.0`.
- **Empirical event schema** (`/tmp/codex_probe.jsonl` + `/tmp/codex_tool_probe.jsonl` 2026-05-26):
  ```jsonl
  {"type":"thread.started","thread_id":"019e6580-..."}
  {"type":"turn.started"}
  {"type":"item.started","item":{"id":"item_0","type":"command_execution","command":"/bin/bash -lc 'echo hello'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
  {"type":"item.completed","item":{"id":"item_0","type":"command_execution","command":"/bin/bash -lc 'echo hello'","aggregated_output":"hello\n","exit_code":0,"status":"completed"}}
  {"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"`echo hello` produced..."}}
  {"type":"turn.completed","usage":{"input_tokens":...,"cached_input_tokens":...,"output_tokens":...,"reasoning_output_tokens":...}}
  ```

### Phase-1 limitations explicitly documented (mirror Story 4.2 pattern)

- Stream-json schema is CLI-tool-internal; version-pinning + fixture-driven tests are the stability gates.
- `tool_calls: list[ToolCallTrace]` synthesized from `command_execution` items; full OTel-span correlation lands in Epic 5 hosted-MCP observer (DF-11.1-S1).
- `[codex]` optional-extras group ships empty (no Python deps); doc note about needing `codex` CLI on `$PATH` + a valid Codex login session.
- `cost_usd=0.0` placeholder per D-9; DF-11.1-S2 carry-over for cost-catalog integration.
- `mcp_coverage="external_mixed"` for non-empty `mcp_servers` per D-7 + ADR-016 §Decision L33; observer wiring deferred to DF-11.1-S1.

### Existing files this story modifies

- `pyproject.toml` — add `[codex]` extra + `codex-cli` entry-point.
- `mypy.ini` — NO new entry needed (`codex` is a binary, not a Python package).
- `docs/contracts/stability-surface.md` — add `CodexCLIAdapter` at `experimental`.
- `docs/phase-1-5-carry-overs.md` — add DF-11.1-S1 + DF-11.1-S2 entries.
- `tests/unit/coding_agent/conftest.py` — add `mock_codex_version` autouse fixture (D-4).

### Existing files this story creates

- `src/AgentEval/coding_agent/codex_cli.py` (new adapter).
- `tests/unit/coding_agent/test_codex_cli.py` (new unit suite, ≥25 tests).
- `tests/integration/test_codex_cli_live.py` (new env-gated integration).
- `tests/fixtures/codex_cli/{simple_prompt,tool_use,truncated,nonzero_exit}.jsonl` (4 new fixtures).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Completion Notes List

Story 11.1 dev complete 2026-05-26. All 10 ACs + 10 Tasks satisfied. **First use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification: 9 cross-story UPSTREAM lessons APPLIED FROM THE START** — no fake-test-masked HIGH-1 regression class, no stderr deadlock, no missing nonzero-exit diagnostic, no observer optimism, no autouse-fixture-test-local fake-green class.

- **AC-11.1.1**: `CodexCLIAdapter(SubprocessAdapter)` at `src/AgentEval/coding_agent/codex_cli.py`. Overrides `_spawn` + `_parse_event` + `_finalize` per ADR-003. Uses `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json "<prompt>"` invocation. `_record_run_metadata` wired UPSTREAM per Story 10.1 HIGH-4 + Story 10.2 D-6 lesson.
- **AC-11.1.2**: `_detect_mcp_coverage` mirrors Stories 10.1 + 10.2 patched 2-branch ADR-016-L59-honest contract from the start: empty → `hosted_in_process`; non-empty → `external_mixed` until C73 (`DF-11.1-S1`) lands.
- **AC-11.1.3**: `[codex]` extra + `codex-cli = "AgentEval.coding_agent.codex_cli:CodexCLIAdapter"` entry-point. Version gate via base `_assert_binary_version("codex", ">=0.100.0,<1.0")` — default `_SEMVER_RE.search()` extracts `0.133.0` from `codex-cli 0.133.0` substring (no override needed).
- **AC-11.1.4**: 33 unit tests at `tests/unit/coding_agent/test_codex_cli.py`. All cross-story UPSTREAM regression guards pass: `test_spawn_passes_prompt_as_positional_argv` (D-1) + `test_spawn_uses_stderr_stdout_multiplex` (D-2) + `test_spawn_uses_start_new_session_true` + `test_finalize_nonzero_exit_with_no_message_emits_diagnostic` (D-3) + `test_run_end_to_end_against_faked_subprocess` + `test_run_with_unverified_mcp_marks_external_mixed` (D-7).
- **AC-11.1.5**: env-gated integration test at `tests/integration/test_codex_cli_live.py` (skipped in CI).
- **AC-11.1.6**: conformance smoke via `test_entry_point_registration` in unit suite (mirrors Story 10.1's reframed AC-10.1.6).
- **AC-11.1.7**: 1638 pytest pass + 11 skipped (was 1605 + 10; +33 new + 1 env-gated). ruff/format/mypy clean (97 source files; was 96 + new `codex_cli.py`).
- **AC-11.1.8**: Carry-over catalog gate UPSTREAM (26th consecutive): added C73 (HostedMcpObserver wiring) + C74 (cost-catalog integration). Catalog total 72 → 74.
- **AC-11.1.9**: Caller-count check: `CodexCLIAdapter` has callers via unit suite (33 tests) + entry-point smoke + env-gated integration. Zero 0-caller helpers.
- **AC-11.1.10**: 9 cross-story UPSTREAM lessons applied from Stories 4.2 + 10.1 + 10.2. Pattern proven on first application — caught zero regressions because lessons were folded into AC text upstream.

### File List

**New files:**

- `src/AgentEval/coding_agent/codex_cli.py` — `CodexCLIAdapter(SubprocessAdapter)` + `CodexEvent` dataclass + 3 hook implementations + version-gate call in `__init__` (~340 LoC).
- `tests/unit/coding_agent/test_codex_cli.py` — 33 unit tests with fake-Popen + monkeypatched `subprocess.run`.
- `tests/integration/test_codex_cli_live.py` — env-gated live integration test (1 test, skipped in CI).
- `tests/fixtures/codex_cli/simple_prompt.jsonl` — 4-event happy-path fixture from empirical probe.
- `tests/fixtures/codex_cli/tool_use.jsonl` — 7-event command_execution fixture from empirical probe.
- `tests/fixtures/codex_cli/truncated.jsonl` — 3-event missing-terminal fixture (synthetic).
- `tests/fixtures/codex_cli/nonzero_exit.jsonl` — 2-event subprocess-nonzero-exit fixture (synthetic).

**Modified files:**

- `pyproject.toml` — `[codex]` extra (L80-84) + `codex-cli` entry-point (L123-124).
- `tests/unit/coding_agent/conftest.py` — `mock_codex_version` autouse fixture (D-4 UPSTREAM).
- `docs/contracts/stability-surface.md` — `CodexCLIAdapter` at `experimental`.
- `docs/phase-1-5-carry-overs.md` — C73 + C74 entries; catalog total 72 → 74.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `epic-11` → in-progress; `11-1-codex-cli-adapter` → review.

## Senior Developer Review (AI)

**Date:** 2026-05-26
**Reviewers:** 3-tier cross-LLM review chain (per `CLAUDE.md` ratified Epic 10 retro 2026-05-26):
- **Tier 1 Copilot CLI** (`copilot -p --model claude-sonnet-4.6 --allow-all-tools`) — substantive, 0 HIGH + 4 MED + 3 LOW
- **Tier 2 Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox`) — DEGRADED (usage limit; retry at 23:38)
- **Tier 3 kilo/minimax-M2.7** (`~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7`) — substantive, 2 HIGH + 5 MED + 2 LOW

**Outcome:** Changes Requested → Resolved (all HIGH + most MED + LOW-1 applied).

### Reviewer participation + ORTHOGONAL coverage proof

The 2 available reviewers caught **DIFFERENT classes of drift with minimal overlap** — the strongest single-story evidence of the 3-tier chain's orthogonal-coverage hypothesis since Epic 10 retro-on-retro:

- **Kilo caught H-1**: silent data-loss bug — `Usage` dataclass dropped `reasoning_output_tokens` because the 4th Codex token field had no corresponding dataclass slot. Copilot MISSED this (focused on contract-text + tests, not dataclass shape coverage).
- **Copilot caught MED-2**: ADR-016 L59 citation pointed to the §Alternatives section (rejected option), NOT §Decision L33 (ratified contract). Kilo MISSED this nuance (verified L59 mentions external_mixed but didn't re-derive that L59 is in §Alternatives, not §Decision).
- **Copilot caught MED-4 + LOW-1**: missing negative-path tests for the D-3 diagnostic 3-condition guard + `test_parse_event_returns_none_on_unknown_type` bundled two semantically-distinct failure modes. Kilo MISSED both.
- **Both caught**: `_VERSION_RE` dead-code module-level constant + `_last_mcp_servers` thread-safety invariant not advertised at class docstring level.

This orthogonality validates the 3-tier review chain's coverage-is-multiplicative claim at story-level (not just retro-level as Epic 10 retro-on-retro demonstrated).

### Patches applied (priority order)

- [x] **[HIGH-1 kilo] [src/AgentEval/types.py:147-167 + src/AgentEval/coding_agent/codex_cli.py:terminal_usage]** Silent data-loss: `Usage` dataclass had 3 fields but Codex `turn.completed.usage` emits 4 (`reasoning_output_tokens` was silently dropped). **Patch:** extended `Usage` with `reasoning_output_tokens: int = 0` (backward-compatible default; non-negative validation extended); updated `CodexEvent.terminal_usage` to pass the 4th field; updated `test_parse_event_turn_completed_usage` to assert the 4th field as regression-guard. Without this fix, DF-11.1-S2 / C74 cost-catalog integration would have shipped on lossy data.
- [x] **[HIGH-2 kilo] [src/AgentEval/coding_agent/codex_cli.py:90-92]** Citation history inlined in References section created second-order citation risk. **Patch:** rewrote the References ADR-016 entry to lead with §Decision L33 (the ratified contract) and footnote the renumbering history clearly.
- [x] **[MED-1 both / kilo M-1 / copilot MED-1] [src/AgentEval/coding_agent/codex_cli.py]** `_VERSION_RE` declared at module scope but unused (dead code; module docstring falsely claimed it was "used"). **Patch:** removed the constant + `re` import; rewrote module docstring to honestly state the base helper's default regex handles the `codex-cli ` prefix via substring search.
- [x] **[MED-2 copilot] [src/AgentEval/coding_agent/codex_cli.py + docs/phase-1-5-carry-overs.md + Story 11.1 spec]** "ADR-016 L59" citation pointed to the rejected-alternatives section; the ratified contract is at §Decision L33. **Patch:** replaced all 14 `ADR-016 L59` references across `codex_cli.py` (4) + `phase-1-5-carry-overs.md` (3) + Story 11.1 spec (7) with `ADR-016 §Decision L33`.
- [x] **[MED-3 both / kilo M-2 / copilot MED-3] [src/AgentEval/coding_agent/codex_cli.py:CodexCLIAdapter class docstring]** `_last_mcp_servers` concurrency invariant was only commented inline, not advertised at class level. **Patch:** added a "Thread safety: NOT concurrent-safe" paragraph to the class docstring + a parallel note to `stability-surface.md`.
- [x] **[MED-4 copilot] [tests/unit/coding_agent/test_codex_cli.py]** Only the positive case of the D-3 3-condition diagnostic gate was tested. **Patch:** added 2 negative-path tests (`test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic` + `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic`) covering the suppression branches.
- [x] **[LOW-1 copilot] [tests/unit/coding_agent/test_codex_cli.py:202-209]** `test_parse_event_returns_none_on_unknown_type` bundled non-string-type + non-dict-JSON cases per `feedback_test_name_assertion_match`. **Patch:** split into `test_parse_event_returns_none_on_non_string_type` + `test_parse_event_returns_none_on_non_dict_json` (now 3 input variants on the non-dict branch).
- [x] **[Kilo M-4 + M-5]** C74 carry-over + stability-surface row updated to reflect resolved `Usage` field extension.

**Accepted as-is (not applied):**

- Kilo L-1 (finally-block sequencing): kilo's own assessment is "no fix required" — safe.
- Copilot LOW-2 (`@openai/codex` npm install command may become stale): minor DX wording; comment is intentionally a best-effort pointer.
- Copilot LOW-3 (`record_active_run_metadata` not called on exception path): intentional Phase-1 design mirroring `claude_code_cli.py`. Behavior matches the existing precedent.

### Significance

**First story to ship under the newly-ratified 3-tier cross-LLM review chain (CLAUDE.md ratified Epic 10 retro 2026-05-26).** Tier-2 codex was degraded (rate-limit) but the chain's degradation-handling worked exactly as designed — Tiers 1 (copilot) + 3 (kilo) covered the gap with substantive orthogonal findings. **This is the 1st validation of the chain at the per-story code-review level** (prior validations were at retro-level + 7 retroactive-batch level).

**First use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification:** 9 cross-story UPSTREAM lessons applied (D-1 through D-11). The reviewers verified ALL 9 lessons were correctly applied — `feedback_cross_story_upstream_lesson_propagation` operational trigger works. No fake-test-masked regressions; no observer optimism; no autouse-fixture-test-local fake-green class.

### Gates after patches

- `uv run pytest tests/ -q --no-header` → **1641 passed + 11 skipped** (was 1605 + 10; +36 new + 1 env-gated).
- `uv run ruff check src/ tests/` → All checks passed.
- `uv run mypy src/` → Success: no issues found in 97 source files (was 96 + new `codex_cli.py`).

### Cross-story propagation lessons for Story 11.2 + 11.3 (UPSTREAM seed)

For `/bmad-create-story 11.2` (Copilot CLI Adapter) — same `SubprocessAdapter` ABC, same subprocess-spawn shape — apply ALL of the following from Story 11.1's review record:

- D-1 (prompt-as-positional-argv) + D-2 (stderr multiplex) + D-3 (nonzero-exit diagnostic) + D-4 (`mock_copilot_version` conftest hoist from start) + D-5 (ADR-002 cite) + D-6 (ADR-016 §Decision L33, not L59 or A6) + D-7 (mcp_coverage external_mixed default).
- **NEW for 11.2 (from this review):** `Usage(reasoning_output_tokens=)` field MUST be populated if Copilot's events.jsonl carries an analogous token field. Empirical probe pre-write.
- **NEW for 11.2 (from this review):** NO module-level `_VERSION_RE` dead-code constant. Document that the base `_SEMVER_RE.search()` handles any version-string prefix.
- **NEW for 11.2 (from this review):** Thread-safety invariant MUST be in the class docstring, not just inline comments.
- **NEW for 11.2 (from this review):** Negative-path tests for the 3-condition diagnostic guard (both "response_text wins" + "terminal present wins" suppression branches).
- **NEW for 11.2 (from this review):** Citation drift discipline: cite ADR-016 §Decision L33 (NOT §Alternatives L59); re-derive each cited fact's section context before pasting.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-05-26 | 0.3.0 | Cross-LLM 3-tier review APPLIED v2. 2 HIGH (kilo) + 6 MED (5 unique) + 2 LOW (copilot LOW-1) patches applied. **First story under the ratified 3-tier chain (CLAUDE.md Epic 10 retro 2026-05-26).** Tier-2 codex rate-limited; Tiers 1 (copilot) + 3 (kilo) delivered ORTHOGONAL coverage — codex MISSED Usage data-loss + thread-safety; kilo MISSED L59-vs-L33 + negative-path-tests + test-name-mismatch. 1641 pytest pass + 11 skipped (was 1605 + 10; +36 + 1). ruff/format/mypy clean (97 src files). `Usage` dataclass extended with 4th field `reasoning_output_tokens` (backward-compatible default). Status → done. | Amelia |
| 2026-05-26 | 0.2.0 | Dev complete. 33 unit tests + 1 env-gated integration test. 1638 pytest pass + 11 skipped (was 1605 + 10; +33 + 1). ruff/format/mypy clean (97 src files). 26th consecutive `feedback_carry_over_catalog_gate` UPSTREAM (added C73 + C74; catalog 72 → 74). Status → review. | Amelia |
| 2026-05-26 | 0.1.0 | Initial story creation (ready-for-dev). **45th use of `feedback_spec_vs_ratified_doc_precheck`** (100% catch rate intact across 45 consecutive uses). **First use of `feedback_cross_story_upstream_lesson_propagation` post-Epic-10 ratification** — 9 cross-story UPSTREAM lessons applied from Stories 4.2 + 10.1 + 10.2 (D-1 prompt-as-argv; D-2 stderr multiplex; D-3 nonzero-exit diagnostic; D-4 conftest autouse hoist; D-5 ADR-002 not ADR-005; D-6 ADR-A6 → ADR-016; D-7 mcp_coverage external_mixed default; D-9 cost-zero placeholder; D-10 `codex-cli ` prefix regex). 11 drifts total caught (9 UPSTREAM + 2 fresh from empirical probe). 10 ACs. Epic 11 first story; epic-11 status → in-progress. Empirical codex JSONL schema probed pre-write — 4-event surface captured at `/tmp/codex_probe.jsonl` + `/tmp/codex_tool_probe.jsonl`. | Bob |
