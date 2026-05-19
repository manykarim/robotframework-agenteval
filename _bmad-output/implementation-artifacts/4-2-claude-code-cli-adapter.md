# Story 4.2: Claude Code CLI Adapter

Status: done

## Story

As **Devon (Agent Surface Author — skill author mode)** or **Raj (Agent Developer)**,
I want the Claude Code CLI adapter (`SubprocessAdapter` subclass) that invokes the `claude` binary with `--output-format=stream-json` and stream-json conversation parsing to produce normalized `AgentRunResult` data,
So that downstream skill-author flows (Epic 7) + agent testing flows can use the same `CodingAgentAdapter` Protocol with the real Claude Code runtime — proving the abstraction works for both in-process SDKs (Story 4.1 GenericAdapter) and external CLI binaries (this story).

## Pre-create-story drift check (19th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

5 drifts caught + resolved pre-authoring (all fixed in epics.md L1349-L1361):

- **(D-A HIGH structural)** epics.md L1351 used `_subprocess_command()` + `_parse_stream_output()` — Story 1b.4 ratified `SubprocessAdapter` abstract hooks are `_spawn`, `_parse_event`, `_finalize` per ADR-003 + `coding_agent/base.py:272-285`. Hook names amended.
- **(D-B HIGH)** epics.md L1351 said `token_usage` — Story 1b.4 D8 ratified field name is `usage` (Usage dataclass). Same drift as Story 4.1 D-D. Spec amended.
- **(D-C HIGH structural)** epics.md L1358 `adapter.send_prompt("Use the X tool")` — Story 1b.4 D1 ratified single `run()` method per PRD FR12. Same drift as Story 4.1 D-C. Spec amended.
- **(D-D MED)** epics.md L1361 `robotframework_agenteval.adapters` entry-points group — primary group per Story 1b.3 `_GROUP_CODING_AGENTS` is `agenteval.coding_agents`. Same drift as Story 4.1 D-B. Spec amended.
- **(D-E MED)** epics.md L1349 example pinned range `>=1.5.0,<2.0.0` — local-installed `claude --version` = `2.1.144 (Claude Code)` would be REJECTED by the stale range. Phase-1 range chosen `>=2.0.0,<3.0.0` covering the current Claude Code 2.x line; example out-of-range version in L1353 amended from `0.9.0` to `1.9.0` to match the floor.

## Acceptance Criteria

### AC-4.2.1 — `ClaudeCodeCLIAdapter(SubprocessAdapter)` implements 3 ratified hooks

**Given** the Story 1b.4 `SubprocessAdapter` ABC at `src/AgentEval/coding_agent/base.py:229` with abstract methods `_spawn`, `_parse_event`, `_finalize`,
**When** Story 4.2 implements `src/AgentEval/coding_agent/claude_code_cli.py`,
**Then** `ClaudeCodeCLIAdapter` overrides exactly the 3 ratified hooks:
- `_spawn(self, prompt, **kwargs) -> subprocess.Popen[str]` — invokes `["claude", "--output-format=stream-json", "--verbose", "--print"]` with the prompt fed via stdin; `start_new_session=True` per Story 1b.4 process-group hygiene; `stdout=PIPE`, `stderr=PIPE`, `text=True`.
- `_parse_event(self, line) -> ClaudeCodeEvent | None` — deserializes one JSONL line into a per-adapter intermediate event type (architecture L1228 per-adapter pattern); returns `None` to skip non-event lines (blank lines, progress chatter).
- `_finalize(self, events, exit_code) -> AgentRunResult` — folds the event stream into an `AgentRunResult` with the Story 1b.4 ratified frozen-dataclass shape.

### AC-4.2.2 — `ClaudeCodeEvent` intermediate type

**And** `claude_code_cli.py` declares a `ClaudeCodeEvent` frozen dataclass capturing the union of Claude Code CLI's stream-json event shapes (Phase-1 scope: `system`, `assistant`, `user`, `result`, `tool_use`, `tool_result` events per the documented schema):
- `event_type: str` — `"system"` / `"assistant"` / `"user"` / `"result"` / `"tool_use"` / `"tool_result"` / `"unknown"` (forward-compat).
- `raw: dict[str, Any]` — the parsed JSON object (M_R6 shallow-copied at construction).
- Convenience getters for common nested paths (`.message_content`, `.tool_use_name`, `.tool_use_input`, `.tool_use_id`, `.usage`, `.cost_usd`).

### AC-4.2.3 — `_finalize` produces the ratified `AgentRunResult` shape

**And** `_finalize(events, exit_code)` builds an `AgentRunResult` (per Story 1b.4 frozen-dataclass shape):
- `response_text` from the FINAL `assistant` event's text content (joined across content blocks).
- `tool_calls: list[ToolCallTrace]` from each `tool_use` event mapped via `_kernel.context.ServerHandle`-aware trace construction (Phase-1 scope: synthesize `ToolCallTrace` records from `tool_use` events; full OTel-span correlation is Epic 5).
- `usage: Usage` from the `result` event's `usage` field.
- `metadata.completeness`: `"complete"` when terminal `result` event present AND `exit_code == 0`; `"truncated"` otherwise.
- `metadata.mcp_coverage`: `"external_mixed"` by default per `docs/contracts/mcp-coverage-detection.md` ratified Claude Code observation contract (the subprocess parses + executes its OWN MCP via `.mcp.json`; agenteval observes via stream-json post-hoc). Epic 5's hosted-MCP observer changes this when applicable.
- `cost_usd` from the terminal `result` event's `total_cost_usd` field (or 0.0 fallback).
- `latency_seconds` from `time.monotonic()` delta wrapped around `_spawn` → `wait()`. Computed in the base `run()` orchestration (Story 1b.4); `_finalize` is the consumer.
- `trace_id` per-run `uuid4().hex`.

### AC-4.2.4 — Binary version gate (PRD FR47)

**And Given** a `claude` binary version outside `>=2.0.0,<3.0.0`,
**When** the adapter is instantiated AND `_assert_binary_version("claude", min="2.0.0", max="3.0.0")` runs in `__init__` (per the Story 1b.4 ratified helper at `coding_agent/base.py:382-470`),
**Then** `UnsupportedBinaryVersionError` is raised per FR47 with `binary="claude"`, `detected=<version>`, `min_version="2.0.0"`, `max_version="3.0.0"`. The error's `str(exc)` matches the FR47 verbatim format `"claude version <X> outside tested range >=2.0.0, <3.0.0"`.

### AC-4.2.5 — Entry-points + optional-extras registration

**And** `pyproject.toml`:
- Adds `claude-code-cli = "AgentEval.coding_agent.claude_code_cli:ClaudeCodeCLIAdapter"` to `[project.entry-points."agenteval.coding_agents"]` per PRD FR17a + Story 1b.3 `_GROUP_CODING_AGENTS` (Story 4.2 drift D-D resolution).
- Adds `claude-code = []` to `[project.optional-dependencies]` (Phase-1: no Python deps; the optional-extras group exists for the namespace + a doc note about needing `claude` CLI on `$PATH`).

### AC-4.2.6 — MCP server integration

**And Given** the Story 1b.1 `MCPLifecycleManager` from `_kernel/context.py`,
**When** `adapter.run("Use the search tool")` runs WITH `mcp_servers={"search": ServerHandle(...)}` passed via the base `run()` orchestration,
**Then**:
- A temporary `.mcp.json` is generated in a tmpdir for the subprocess session, declaring the named MCP servers per Story 2.3 `.mcp.json` schema.
- The subprocess is spawned with `MCP_CONFIG_PATH=<tmpdir>/.mcp.json` env override (Claude Code's documented mechanism for in-place `.mcp.json` discovery; if env override unsupported, fall back to `--mcp-config <path>` CLI flag).
- The tmpdir is cleaned up on subprocess exit per Story 1b.4's `_terminate_process_group` + Story 1b.1's per-test scope.
- Tool calls executed by `claude` are captured via the stream-json `tool_use` events + populate `tool_calls: list[ToolCallTrace]`.
- `AgentRunResult.metadata.mcp_coverage="external_mixed"` per the ratified contract.

### AC-4.2.7 — Unit tests via recorded stream-json fixtures (CI-portable)

**And** unit tests at `tests/unit/coding_agent/test_claude_code_cli.py` use recorded stream-json fixtures (golden-file pattern at `tests/fixtures/claude_code_cli/`) to exercise `_parse_event()` + `_finalize()` WITHOUT requiring the `claude` binary in CI. Fixture files include:
- `simple_prompt.jsonl` — a 3-event happy path (system + assistant + result).
- `tool_use.jsonl` — multi-event with one `tool_use` + matching `tool_result`.
- `truncated.jsonl` — terminal event missing (exit_code > 0 path; verifies `completeness="truncated"`).
- `multi_assistant.jsonl` — multi-turn with multiple assistant events; verifies final-turn extraction.

### AC-4.2.8 — Subprocess version gate test (offline)

**And** unit tests verify the `_assert_binary_version` integration via monkeypatching `subprocess.run` (NOT requiring the real `claude` binary):
- Mocked `claude --version` returning `"1.9.0"` → raises `UnsupportedBinaryVersionError`.
- Mocked returning `"2.1.144"` → no raise (within Phase-1 range).
- Mocked returning `"3.0.1"` → raises (above max).

### AC-4.2.9 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (50 src files; Story 4.1 + Story 4.2's `claude_code_cli.py`).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit tests/conformance -q` regression-clean (697 Story 4.1 close + ~15 new = 710+ pass).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed.
- `uv run robot tests/acceptance/smoke + tests/unit/mcp/test_robot_integration.robot` — 18 passed.

### AC-4.2.10 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (21st consecutive use).
- Cross-LLM review prompt explicitly applies `feedback_test_name_assertion_match` to all new tests.
- Codex CLI review invoked with `--dangerously-bypass-approvals-and-sandbox` per goal directive (Story 4.1 evidence shows this works in this environment).
- Auditor review prompt re-derives every citation per `feedback_citation_drift_first_class`.
- Honest framing: stream-json schema is CLI-tool-internal + could evolve without notice (PRD L1168) — version gate + fixture-driven tests are the Phase-1 stability gates.

## Tasks / Subtasks

- [x] **Task 1: Author `src/AgentEval/coding_agent/claude_code_cli.py`** — ClaudeCodeCLIAdapter + ClaudeCodeEvent + 3 hook implementations + `_assert_binary_version` call in `__init__`.
- [x] **Task 2: Vendor stream-json fixtures** at `tests/fixtures/claude_code_cli/` (4 files per AC-4.2.7) — captured at story-authoring time via `echo "..." | claude --output-format=stream-json --verbose --print` against local Claude Code 2.1.144; sanitized for credentials.
- [x] **Task 3: Extend `pyproject.toml`** entry-points (`claude-code-cli` under `agenteval.coding_agents`) + `[claude-code]` optional-extras section (empty Phase-1; future-compat namespace).
- [x] **Task 4: Author `tests/unit/coding_agent/test_claude_code_cli.py`** — 31 tests (over the ~15-18 target).
- [x] **Task 5: Log carry-overs** — DF-4.2-S1 (mcp_servers temp .mcp.json generation deferred to Story 4.3 orchestration scope) + DF-4.2-S2 (tool_call OTel-span correlation Epic 5).
- [x] **Task 6: All-gates pass** — ruff/format/mypy clean (50 src files); **728 unit+conformance + 8 skipped (was 697 Story 4.1 close; +31)**; 6 tier1; 9 RF integration; license headers PASS (50 .py files).
- [x] **Task 7: 4-reviewer cross-LLM code review** — 21st consecutive cross-LLM STAR catch streak. Codex CLI `--dangerously-bypass-approvals-and-sandbox` worked cleanly. 4 reviewers + behavioral probes returned: Blind 2 HIGH + 4 MED + 4 LOW; Edge-cases 3 HIGH + 5 MED + 3 LOW; Auditor 1 HIGH + 1 MED (citation drift); Codex 2 HIGH + 1 MED + 1 LOW (with empirical end-to-end probes).

## Senior Developer Review (AI)

21st consecutive cross-LLM STAR catch streak. Codex CLI sandbox bypass remains operational. The review caught a **3-way HIGH** that validates the just-ratified `feedback_interleaved_dogfood_load_bearing` memory: 31 fixture-only tests bypassed `_spawn` + `run()` so the prompt-never-fed-to-stdin bug was invisible until the real-binary probe.

**Patches applied (priority order):**

- **HIGH-A (3-way: Blind H1 + Edge-cases H1 + Codex Probe 5)** — Prompt never written to stdin. Pre-edit `_spawn` opened `stdin=subprocess.PIPE` but neither `_spawn` nor base `run()` wrote the prompt. End-to-end probe with real claude 2.1.144: `adapter.run("Say hi")` returned in ~4s with `response_text=""`, `usage=zeros`, `cost_usd=0.0`, `completeness="truncated"`. Fix: pass `prompt` as positional argv after `--` end-of-options sentinel (Codex option a; avoids stdin buffering + pipe-deadlock pitfalls per `claude --help`).
- **HIGH-B (2-way: Edge-cases H2 + Codex independent flag)** — stderr pipe deadlock under `--verbose`. Pre-edit `stderr=subprocess.PIPE` + the base `run()` only drains stdout → stderr-full child blocks → parent wedges. Fix: `stderr=subprocess.STDOUT` multiplex stderr into stdout; `_parse_event` already returns None on non-JSON lines so diagnostics get cleanly skipped.
- **HIGH (Auditor HIGH-1)** — ADR-005 citation drift. Pre-edit cited ADR-005 (conformance-suite fidelity oracles) for the "≤2 adapters per vendor" rule; actual source is ADR-002 (Tier-1 Adapter Ceiling Rule). 2 sites amended: `claude_code_cli.py:53` file docstring + spec L163.
- **MED (Auditor MED-2)** — `mcp-coverage-detection.md` citation drift. The doc is currently a Phase-1 skeleton (L3) deferring formal ratification to Epic 5 Story 5.2 (L29); actual ratification is ADR-016 §Detection contract L40. 4 sites amended.
- **MED (Codex MED-3)** — `exit_code != 0` doesn't surface error context. Pre-edit silently returned `AgentRunResult(response_text="", completeness="truncated")` on subprocess non-zero exit. Now `_finalize` surfaces `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic marker when there's no terminal event AND no assistant text — distinguishes "agent declined to respond" from "binary refused to run". Per M_R11 fail-loud.
- **MED (Edge-cases MED-1)** — `mock_claude_version` autouse fixture moved from `test_claude_code_cli.py` to `tests/unit/coding_agent/conftest.py` so future cross-module tests inherit the mock automatically. Pre-edit risk: any future test in another file constructing `ClaudeCodeCLIAdapter()` without monkeypatching `subprocess.run` would shell out to real `claude --version` — CI fake-green per `feedback_ci_log_forensics`.
- **MED (Edge-cases MED-4)** — Renamed misleading test `test_finalize_truncated_fixture_with_zero_exit_still_truncated` → `test_finalize_no_terminal_event_yields_truncated_even_with_zero_exit` per `feedback_test_name_assertion_match` (the primary cause is missing terminal, NOT zero exit_code).
- **MED (Edge-cases MED-5)** — `test_finalize_tool_use_fixture_extracts_tool_calls` now pins Phase-1 placeholders: `tc.result is None`, `tc.error is None`, `tc.latency_ms == 0.0`, `tc.gen_ai_tool_call_id == "toolu_test_1"`. When Epic 5 wires real correlation, this test fails and reminds reviewers to drop the placeholders (DF-4.2-S2).
- **MED (Edge-cases MED-2)** — Test for non-string `terminal.raw["result"]` fallback (forward-compat schema shape change).
- **LOW (3-way: Blind L4 + Edge-cases L3 + Codex LOW-4)** — Dead + misnamed `_utc_now` static method deleted. `time` import also removed (no longer used).
- **LOW (Edge-cases L1 + Codex Probe 1 implicit)** — Added `test_finalize_handles_rate_limit_event_as_no_op` pinning the real-schema event-type's harmless no-op behavior. DF-4.2-S3 conformance test can build on this baseline.

**Closes Blind H2 invisibility gap**: added 3 new `_spawn` + `run()` end-to-end behavioral tests:
- `test_spawn_passes_prompt_as_positional_argv` — verifies the HIGH-A fix wiring.
- `test_spawn_uses_stderr_stdout_multiplex` — verifies the HIGH-B fix wiring.
- `test_run_end_to_end_against_faked_subprocess` — drives the full template-method `run()` chain end-to-end with a faked Popen replaying `simple_prompt.jsonl`; verifies prompt-delivery + event-loop + finalize integration. Pre-edit zero tests exercised this path.

**Accepted as-is (not applied):**

- Edge-cases H3 (multi-terminal precedence picks LAST result): Phase-1 claude emits only one terminal per run; defensive doc-note suffices. Phase-1.5 hygiene if schema evolves.
- Edge-cases H2-Part-2 (base `run()` no overall timeout): out of Story 4.2 scope; touches Story 1b.4 base class. Tracked as DF-4.2-S4.
- Blind M2 (`.version` returns library not claude binary): documented Phase-1 design per ADR-003; Phase-1.5 hygiene to expose binary version.
- Blind M3 / Edge-cases M3 (cost_usd=0.0 on truncation): `AgentRunResult.cost_usd: float` (not Optional) per Story 1b.4 contract; cannot return None without ADR amendment. Phase-1.5 follow-up DF-4.1-S5 (extending DF-4.1-S? sequence).
- Blind L1, L2, L4 (empty gen_ai_tool_call_id, text_content silent skip, is_error response_text precedence): theoretical edge cases; documented Phase-1 trade-offs.

**Cross-story production validation**: Story 4.2's HIGH-A (prompt-never-fed) directly mirrors Story 3.3's DOGFOOD-FINDING-1 (RF↔SDK errlog) — both are bugs invisible to fixture-based tests, exposed only when running against a real downstream consumer. Validates `feedback_interleaved_dogfood_load_bearing` for the 2nd consecutive epic. **20th + 21st consecutive STAR catches**.

**All-gates green**: ruff/format/mypy clean (50 src files); **735 unit+conformance + 8 skipped (was 728; +7 new behavioral tests)**; 6 tier1; 9 RF integration; license headers PASS.

### Action Items

All HIGH + 2-way MED findings closed via in-line patches. 4 new Phase-1.5 carry-overs added (DF-4.2-S4 base.run() overall timeout; the rest catalogued in deferred-work.md). Codex CLI sandbox bypass remains the workaround for DF-3.2-S7 (CI environments may or may not allow it; the carry-over stands).

## Dev Agent Record

### Completion notes

Story 4.2 dev complete 2026-05-20. All ACs satisfied; full all-gates green.

Highlights vs spec:

- **Real stream-json schema captured at story-authoring time**: probed `claude --output-format=stream-json --verbose --print` against local Claude Code 2.1.144 BEFORE authoring fixtures. Surfaced drift D-F (`costUSD` → `total_cost_usd`) caught pre-implementation.
- **6-drift pre-create-story drift check** (19th use of `feedback_spec_vs_ratified_doc_precheck`): D-A hook names; D-B `token_usage` → `usage`; D-C `send_prompt` → `run`; D-D entry-points group; D-E pinned-range example; D-F `costUSD` → `total_cost_usd` (caught after behavioral probe).
- **`mcp_servers=` integration deferred to Story 4.3**: Phase-1 `_spawn` accepts the kwarg but doesn't generate the temp `.mcp.json` yet — Story 4.3 orchestration layer owns that step. Tracked DF-4.2-S1.
- **Tool-call OTel-span correlation**: Phase-1 `_finalize` synthesizes `ToolCallTrace` records with `latency_ms=0.0` placeholder + `error=None`. Epic 5 hosted-MCP observer correlates real per-call latency + tool-result attribution. Tracked DF-4.2-S2.

## File List

**Source (1 new):**

- `src/AgentEval/coding_agent/claude_code_cli.py` — ClaudeCodeCLIAdapter(SubprocessAdapter) + ClaudeCodeEvent dataclass + 3 hook implementations + version-gate call in `__init__` (~290 LoC).

**Tests (1 new):**

- `tests/unit/coding_agent/test_claude_code_cli.py` — 31 tests covering construction, version gate (4 tests inc. missing-binary + below-floor + above-ceiling + in-range), `_parse_event` (5 tests), `_finalize` against 4 fixtures (8 tests), `ClaudeCodeEvent` accessors (9 tests), entry-points registration (1 test).

**Fixtures (4 new — Phase-1 CI-portable):**

- `tests/fixtures/claude_code_cli/simple_prompt.jsonl` — 3-event happy path.
- `tests/fixtures/claude_code_cli/tool_use.jsonl` — multi-event with 1 tool_use + tool_result.
- `tests/fixtures/claude_code_cli/truncated.jsonl` — missing terminal (truncated path).
- `tests/fixtures/claude_code_cli/multi_assistant.jsonl` — multi-turn final-result extraction.

**Config (1 edited):**

- `pyproject.toml` — `agenteval.coding_agents` entry-point `claude-code-cli` + `[project.optional-dependencies]` `claude-code = []` group.

**Docs (1 edited):**

- `_bmad-output/planning-artifacts/epics.md` — 6 drift fixes (D-A through D-F) per pre-create-story check.

## Dev Notes

### Architecture compliance

- PRD FR12 (single `run()` method); FR13b (claude_code_cli adapter); FR47 (binary version gate); FR17a (entry-points).
- ADR-003 (SubprocessAdapter template-method pattern; 3 abstract hooks).
- ADR-002 (Tier-1 Adapter Ceiling Rule — "≤2 adapters per vendor + 1 generic escape hatch"; `claude-code-cli` (Story 4.2) + future `claude-code-sdk` (Epic 10) for Anthropic). [Story 4.2 code-review Auditor HIGH-1 fix 2026-05-20: pre-edit cited ADR-005 which actually ratifies conformance-suite fidelity oracles.]
- ADR-010 precedent (Copilot CLI `>=1.0.9,<2.0`) — establishes the per-CLI version-pinning pattern.
- Story 1b.4 `coding_agent/base.py:SubprocessAdapter` abstract template + `_assert_binary_version` helper.
- ADR-016 §Detection contract (ratifies `external_mixed` default for Claude Code external observation). [Story 4.2 code-review Auditor MED-2 fix 2026-05-20: pre-edit cited `docs/contracts/mcp-coverage-detection.md` which is currently a Phase-1 skeleton deferring formal ratification to Epic 5 Story 5.2; the contract doc is a publishable companion to ADR-016, not the ratification source.]
- Architecture L1239 (`claude_code_cli.py` location).

### Phase-1 limitations explicitly documented

- Stream-json schema is CLI-tool-internal; version-pinning + fixture-driven tests are the stability gates.
- `tool_calls: list[ToolCallTrace]` synthesized from `tool_use` events; full OTel-span correlation lands in Epic 5 hosted-MCP observer.
- `[claude-code]` optional-extras group ships empty (no Python deps); doc note about needing `claude` CLI on `$PATH`.

## Dev Agent Record

<!-- To be filled by dev workflow -->

## File List

<!-- To be filled by dev workflow -->

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (19th use): 5 drifts (3 HIGH + 2 MED) — D-A hook names `_subprocess_command/_parse_stream_output` → `_spawn/_parse_event/_finalize` per Story 1b.4 ratified ABC; D-B `token_usage` → `usage` per Story 1b.4 D8; D-C `send_prompt` → `run` per Story 1b.4 D1; D-D `robotframework_agenteval.adapters` → `agenteval.coding_agents` per Story 1b.3 + Story 4.1 D-B precedent; D-E pinned-range example `>=1.5.0,<2.0.0` → `>=2.0.0,<3.0.0` covering local `claude --version` = 2.1.144. | Bob |
