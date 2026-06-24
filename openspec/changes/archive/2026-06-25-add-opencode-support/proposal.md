## Why

`AgentEval` ships CLI adapters for Claude Code, Codex, and Copilot but has no
adapter for **opencode** (the open-source SST terminal coding agent, invoked as
`opencode run "<prompt>"`). opencode is a fast-growing, provider-agnostic OSS
agent that users want to benchmark on the same scenarios/metrics as the existing
adapters. Adding it widens the matrix of evaluable agents and exercises the
`SubprocessAdapter` template-method contract against a fourth, independently
designed CLI — a useful stress test of the abstraction (ADR-003).

## What Changes

- Add a new `OpenCodeCLIAdapter(SubprocessAdapter)` at
  `src/AgentEval/coding_agent/opencode_cli.py` implementing the 3-hook
  template-method pattern (`_spawn` / `_parse_event` / `_finalize`) per ADR-003.
- Spawn the binary in non-interactive mode (`opencode run`) with prompt, model,
  and (where supported) machine-readable output passed via flags; multiplex
  `stderr` into `stdout` per the ratified Story 4.2/11.1 lessons.
- Declare a per-adapter concrete intermediate event type (`OpenCodeEvent`)
  mirroring `CodexEvent` / `CopilotEvent`, projecting the agent's run output into
  a normalized `AgentRunResult` (response text, `ToolCallTrace[]`, `Usage`,
  `completeness`, `mcp_coverage`).
- Pin the `opencode` binary version range (FR47) via `_assert_binary_version`,
  and wire `AdapterVersionDriftWarning` emission (FR60) with a `_TESTED_UP_TO`
  constant, matching the Copilot/Codex adapters.
- Apply the ADR-016 §Decision L33 safer-default `mcp_coverage` contract (empty
  `mcp_servers` → `hosted_in_process`; non-empty → `external_mixed` until
  observer wiring lands).
- Register the adapter under a stable name (`opencode-cli`) so it is discoverable
  via `_kernel/discovery.py`, and re-export it from
  `src/AgentEval/coding_agent/__init__.py`.
- Add unit tests (fixture-driven, fake CLI output) plus a gated live integration
  smoke test mirroring `tests/integration/test_codex_cli_live.py`.

No behavior of existing adapters changes; this is purely additive.

## Capabilities

### New Capabilities
- `opencode-cli-adapter`: A `SubprocessAdapter` that wraps the `opencode run`
  CLI, validates its binary version, parses its run output into a normalized
  `AgentRunResult`, applies the project's `mcp_coverage` detection contract, and
  registers under the stable adapter name `opencode-cli`.

### Modified Capabilities
<!-- None. openspec/specs/ is empty; this change introduces no requirement
     changes to existing capabilities. The adapter slots into existing ADR-003 /
     FR12 / FR47 / FR60 contracts without altering them. -->

## Impact

- **New code**: `src/AgentEval/coding_agent/opencode_cli.py`,
  `tests/unit/coding_agent/test_opencode_cli.py`,
  `tests/integration/test_opencode_cli_live.py`,
  `tests/fixtures/opencode_cli/` (captured sample output).
- **Modified code**: `src/AgentEval/coding_agent/__init__.py` (re-export);
  adapter registration in `_kernel/discovery.py` (or its registration site);
  `docs/contracts/stability-surface.md` (list the new public adapter).
- **External dependency (runtime, optional)**: the `opencode` binary must be on
  `PATH` for live runs; unit tests use captured fixtures and do not require it.
- **APIs**: adds one public adapter class to the stability surface; the
  `CodingAgentAdapter` Protocol, `AgentRunResult`, and `SubprocessAdapter` base
  are unchanged.
- **Empirical-probe dependency**: opencode's exact non-interactive output format
  (streamed JSONL on stdout vs. written to a session/state file) MUST be probed
  before `_parse_event`/`run()` are finalized, per
  `feedback_listener_hook_api_surface_empirical_check`.
