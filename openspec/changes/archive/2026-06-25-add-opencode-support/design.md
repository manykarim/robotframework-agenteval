## Context

`AgentEval` evaluates AI coding agents via a `CodingAgentAdapter` Protocol with
two base classes (ADR-003): `InProcessAdapter` (SDK-driven, direct `run()`
override) and `SubprocessAdapter` (CLI-driven, 3-hook template method). Existing
CLI adapters — `ClaudeCodeCLIAdapter` (Story 4.2), `CodexCLIAdapter` (Story
11.1), `CopilotCLIAdapter` (Story 11.2) — establish a stable shape: pin the
binary version (FR47), emit `AdapterVersionDriftWarning` (FR60), declare a
per-adapter intermediate event type, project the run into `AgentRunResult`, and
apply the ADR-016 §Decision L33 `mcp_coverage` safer default.

opencode is the open-source SST terminal coding agent. It exposes a
non-interactive entry point (`opencode run "<message>"`) and is
provider-agnostic (model selected as `provider/model`). It is a new vendor, so
ADR-005's "≤2 adapters per vendor" ceiling is not a constraint here.

This adapter slots into all existing contracts without changing them. The single
real unknown is opencode's machine-readable output format in non-interactive
mode, which dictates whether the adapter can reuse the base streaming `run()`
(like Codex) or must override `run()` for a post-hoc file read (like Copilot).

## Goals / Non-Goals

**Goals:**
- Ship `OpenCodeCLIAdapter(SubprocessAdapter)` conforming to ADR-003's 3-hook
  contract, registered as `opencode-cli` and re-exported from
  `AgentEval.coding_agent`.
- Reuse the ratified version-pin (FR47) + drift-warning (FR60) + `mcp_coverage`
  (ADR-016 L33) machinery verbatim from the Codex/Copilot adapters.
- Normalize response text, tool calls, usage, and completeness into
  `AgentRunResult`, with documented carry-overs for any field opencode does not
  expose.
- Fixture-driven unit tests + one gated live integration smoke test.

**Non-Goals:**
- MCP hosted-attachment verification (stays at the `external_mixed` safer
  default; the `HostedMcpObserver` upgrade path is a Phase-2 carry-over).
- Interactive/TUI or server-mode integration — only the non-interactive `run`
  path is in scope.
- Sandbox integration (out of scope for adapters per architecture L1523).
- Cost/latency accounting beyond what opencode emits natively.

## Decisions

### Decision 1: Subclass `SubprocessAdapter`, not `InProcessAdapter`
opencode is driven through a CLI binary, not an in-process SDK, so
`SubprocessAdapter` (ADR-003 L24-29) is the correct base. This matches the three
existing CLI adapters and gives us `_assert_binary_version` and process-group
cleanup for free. *Alternative considered:* wrapping opencode's HTTP server mode
via an `InProcessAdapter` — rejected as higher-complexity and outside the
non-interactive scope.

### Decision 2: Event-source strategy chosen by empirical probe, not assumption
Per `feedback_listener_hook_api_surface_empirical_check`, before finalizing
`_parse_event`/`run()` we MUST probe opencode's actual non-interactive output:
- **Case A — JSONL streamed to stdout** (Codex-like): keep the base
  `SubprocessAdapter.run()` template; `_parse_event` parses each line into an
  `OpenCodeEvent`; `_finalize` folds the list. This is preferred — least code,
  fully reuses the base orchestration.
- **Case B — output written to a session/state file** (Copilot-like): override
  `run()` to snapshot the state directory before spawn, drain stdout to avoid
  deadlock, then read the new session file post-exit and fold it. Carries the
  same documented thread-safety + newest-dir-race invariants as Copilot.

The spec is written to be satisfiable under either case; the probe selects the
implementation. *Alternative considered:* hard-coding Case A — rejected because a
wrong guess produces a silently-empty result the type system cannot catch (the
exact failure class the norm exists to prevent).

### Decision 3: Reuse the version-pin + drift machinery verbatim
Construct-time `_assert_binary_version("opencode", MIN_VERSION, MAX_VERSION)`
plus `emit_adapter_version_drift_warning_if_applicable(...)` with `_TESTED_UP_TO`
set to the locally probed version, exactly as `copilot_cli.py` does. The default
`_SEMVER_RE` substring extraction handles `opencode --version` output; if
opencode's version string is non-standard, override `_assert_binary_version`
(documented escape hatch). MIN/MAX bounds are pinned to the probed range at
implementation time. *Alternative considered:* no version pin — rejected;
violates FR47 and the project's pinned-binary norm.

### Decision 4: `mcp_coverage` uses the ADR-016 L33 safer default
Empty/`None` `mcp_servers` → `hosted_in_process`; non-empty → `external_mixed`.
Identical to Codex/Copilot. Real hosted-attachment detection is deferred to the
observer-wiring carry-over.

### Decision 5: Carry-over markers for unexposed fields
Any of `cost_usd`, `latency_seconds`, `input_tokens`, `trace_id` that opencode
does not surface are set to documented placeholders (`0.0`/`0`/`""`) with a
`DF-<story>-S<N>` carry-over entry, following the Copilot precedent
(`DF-11.2-S2`). The carry-over catalog gate (`feedback_carry_over_catalog_gate`)
applies at implementation time.

## Risks / Trade-offs

- **opencode output format is version-volatile** → Decision 2's probe is run at
  implementation time and the captured fixture is committed under
  `tests/fixtures/opencode_cli/`; `_TESTED_UP_TO` + the version pin bound the
  supported range, and the drift warning surfaces newer untested versions.
- **Case B introduces a session-dir race** (concurrent runs against one state
  dir) → mirror Copilot's documented thread-safety invariant ("one adapter
  instance per concurrent run") and pick the newest-by-mtime new directory; track
  a carry-over if a real consumer hits it.
- **Live integration test depends on the binary + provider credentials** → the
  live test is gated behind an env flag (matching
  `test_codex_cli_live.py`/`test_copilot_cli_live.py`) and reads credentials via
  an `os.environ.get` helper, never RF `Get Environment Variable`, to keep keys
  out of `log.html`.
- **Empty-output failure mode** (opencode prints nothing on some prompts) →
  the fail-loud `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic + `truncated`
  completeness make it observable rather than a silent empty `AgentRunResult`.

## Migration Plan

Purely additive; no migration or rollback of existing behavior. Deploy by
merging the new module, its entry-point registration, and tests (no package
`__init__` re-export — see the apply-time amendment in the spec). Rollback =
remove the module + its `pyproject.toml` entry-point line; no other adapter
depends on it. The full run
is gated by `uv run pytest tests/`, `uv run ruff check`, and `uv run mypy src/`.

## Open Questions (RESOLVED at implementation — probe 2026-06-25, `opencode 1.15.12`)

- ~~Which event-source case (A vs. B)?~~ **RESOLVED: Case A** — `opencode run
  --format json` streams JSONL events to stdout (`step_start` / `text` /
  `tool_use` / `step_finish`). The base `SubprocessAdapter.run()` is reused; no
  Copilot-style file-read override needed.
- ~~Exact machine-readable + model-selection flags?~~ **RESOLVED:** `--format
  json` for raw events, `--model provider/model` for model, and
  `--dangerously-skip-permissions` for autonomous non-interactive tool use. A
  `--` end-of-options sentinel precedes the positional prompt (probe-verified to
  guard leading-dash prompts — added per Claude cross-LLM MED-4).
- ~~Final pin values?~~ **RESOLVED:** `MIN_VERSION=1.15.0`, `MAX_VERSION=2.0.0`,
  `_TESTED_UP_TO=1.15.12`. Note (honest-framing): because MIN and `_TESTED_UP_TO`
  share minor 15, the FR60 within-range drift window is empty until
  `_TESTED_UP_TO` advances ≥2 minors — the helper is wired but a no-op at these
  pins (tracked DF-OPENCODE-S3 / C101).
- **New finding:** unlike Codex, opencode surfaces per-step `cost` in
  `step_finish`, so `cost_usd` is populated (sum of per-step costs); token usage
  is summed across per-step `step_finish.tokens` (per-step, not cumulative —
  cross-check tracked DF-OPENCODE-S2 / C100).
