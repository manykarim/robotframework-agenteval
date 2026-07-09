# opencode-cli-adapter Specification

## Purpose

The OpenCode CLI adapter integrates the `opencode` coding agent into AgentEval
by subclassing `SubprocessAdapter` and conforming to the `CodingAgentAdapter`
Protocol, normalizing opencode's non-interactive output into a canonical
`AgentRunResult`.

## Requirements

### Requirement: OpenCode CLI adapter conforms to the CodingAgentAdapter Protocol

The system SHALL provide an `OpenCodeCLIAdapter` that subclasses
`SubprocessAdapter` (ADR-003) and conforms to the `CodingAgentAdapter` Protocol,
exposing a single `run(prompt, tools=None, mcp_servers=None, **kwargs)` entry
point returning a normalized `AgentRunResult`. The adapter MUST implement the
three template-method hooks `_spawn`, `_parse_event`, and `_finalize`, and MUST
NOT add a fourth abstract hook.

#### Scenario: Adapter is Protocol-conformant
- **WHEN** `OpenCodeCLIAdapter` is checked against the runtime-checkable
  `CodingAgentAdapter` Protocol
- **THEN** the check SHALL pass and `adapter.run("prompt")` SHALL return an
  `AgentRunResult` instance

#### Scenario: Adapter exposes a stable name and version
- **WHEN** the adapter's `name` property is read
- **THEN** it SHALL return `"opencode-cli"`, and the `version` property SHALL
  resolve the installed `robotframework-agenteval` distribution version (or
  `"unknown"` on metadata-resolution failure)

### Requirement: Adapter invokes opencode in non-interactive mode

The adapter SHALL launch the `opencode` binary in its non-interactive run mode
(`opencode run`) with the prompt passed as an argument/flag, and SHALL pass the
configured model through when one is provided. The subprocess MUST be spawned
with `stdout=subprocess.PIPE`, `stderr` multiplexed into stdout, `text=True`,
and `start_new_session=True` so the base class process-group cleanup works.

#### Scenario: Prompt and model are forwarded to the CLI
- **WHEN** `run("Fix the bug")` is called on an adapter constructed with
  `model="anthropic/claude-opus-4-8"`
- **THEN** the spawned command line SHALL include the non-interactive `run`
  invocation, the prompt text, and the selected model

#### Scenario: stderr is multiplexed to avoid pipe-buffer deadlock
- **WHEN** the opencode subprocess writes verbose diagnostics to stderr
- **THEN** the adapter SHALL not deadlock, because stderr is redirected into the
  stdout pipe that `run()` drains

### Requirement: Adapter normalizes opencode output into AgentRunResult

The adapter SHALL parse opencode's non-interactive output into a concrete
intermediate event type (`OpenCodeEvent`) and fold it into an `AgentRunResult`
populating `response_text`, `tool_calls` (`ToolCallTrace[]`), `usage` (`Usage`),
and `metadata.completeness`. Token/cost/latency fields not exposed by opencode
MAY be Phase-1 placeholders, each documented with a carry-over marker.

#### Scenario: Successful run produces response text and tool traces
- **WHEN** opencode completes a run that emitted assistant text and at least one
  tool invocation
- **THEN** `result.response_text` SHALL contain the assistant text and
  `result.tool_calls` SHALL contain one `ToolCallTrace` per tool invocation with
  `name` and `args` populated

#### Scenario: Non-zero exit with no output surfaces a fail-loud diagnostic
- **WHEN** the opencode subprocess exits non-zero and produced no parseable
  assistant text and no terminal event
- **THEN** `result.response_text` SHALL contain a
  `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic marker and
  `metadata.completeness` SHALL be `"truncated"`

#### Scenario: Successful terminal run is marked complete
- **WHEN** the run reaches a terminal/end event and the subprocess exits zero
- **THEN** `metadata.completeness` SHALL be `"complete"`

### Requirement: Adapter pins the opencode binary version and wires drift warning

The adapter SHALL validate the detected `opencode` binary version against a
pinned `[MIN_VERSION, MAX_VERSION)` range at construction via
`_assert_binary_version` (FR47), raising `UnsupportedBinaryVersionError` when out
of range. It SHALL also invoke the shared FR60 drift helper
(`emit_adapter_version_drift_warning_if_applicable`) with its `_TESTED_UP_TO`
value so an `AdapterVersionDriftWarning` is emitted when the detected binary is
significantly behind tested (≥2 minor versions, or on a previous major).

#### Scenario: Out-of-range binary is rejected at construction
- **WHEN** the installed `opencode` reports a version below `MIN_VERSION` or at/above `MAX_VERSION`
- **THEN** constructing `OpenCodeCLIAdapter` SHALL raise
  `UnsupportedBinaryVersionError` with the FR47 message format
  `"opencode version <X> outside tested range >=<min>, <<max>"`

#### Scenario: In-range binary constructs without a spurious drift warning
- **WHEN** the installed `opencode` version is within range and at/near `_TESTED_UP_TO`
- **THEN** the adapter SHALL construct successfully and SHALL NOT emit an
  `AdapterVersionDriftWarning`

#### Scenario: Missing binary is reported clearly
- **WHEN** the `opencode` binary is not found on `PATH`
- **THEN** construction SHALL raise `UnsupportedBinaryVersionError` referencing
  an unavailable detected version

### Requirement: Adapter applies the mcp_coverage detection contract

The adapter SHALL set `metadata.mcp_coverage` per the ADR-016 §Decision L33
safer-default rule: when `mcp_servers` is empty/`None` it SHALL be
`"hosted_in_process"`; when non-empty and hosted attachment is not yet verified
it SHALL be `"external_mixed"`.

#### Scenario: No MCP servers requested
- **WHEN** `run(prompt)` is called with `mcp_servers=None` or `{}`
- **THEN** `result.metadata.mcp_coverage` SHALL be `"hosted_in_process"`

#### Scenario: MCP servers requested without verified hosting
- **WHEN** `run(prompt, mcp_servers={...})` is called with one or more servers
- **THEN** `result.metadata.mcp_coverage` SHALL be `"external_mixed"`

### Requirement: Adapter is discoverable and importable

The adapter SHALL be registered under the stable name `opencode-cli` in the
`agenteval.coding_agents` entry-points group so it is resolvable through
`_kernel/discovery.py`, and SHALL be importable from its module
`AgentEval.coding_agent.opencode_cli`.

#### Scenario: Adapter resolves by registered name
- **WHEN** the `agenteval.coding_agents` entry-points group is queried for `"opencode-cli"`
- **THEN** it SHALL load and return the `OpenCodeCLIAdapter` class

#### Scenario: Adapter is importable from its submodule
- **WHEN** `from AgentEval.coding_agent.opencode_cli import OpenCodeCLIAdapter` is executed
- **THEN** the import SHALL succeed
