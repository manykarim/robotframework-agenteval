# coding-agent-cli-adapters Specification

## Purpose
TBD - created by archiving change add-e2e-agent-metrics-and-cli-adapters. Update Purpose after archive.
## Requirements
### Requirement: SubprocessCLIAdapter base implements the Adapter protocol via subprocess

The system SHALL provide a `SubprocessCLIAdapter` base class that implements the `Adapter` `run(prompt) -> AgentRunResult` protocol by shelling out to an externally-installed coding-agent CLI binary. The base SHALL define a `build_argv(prompt)` step that concrete adapters override to produce the command line, invoke it via `subprocess.run` with an enforced timeout and `start_new_session`, and define a `parse_output(stdout, stderr, exit_code, session_file)` step that concrete adapters override to normalize the CLI result. Secrets required by the CLI SHALL be sourced from `os.environ` and MUST NOT be written to any log, RF output, or the returned `AgentRunResult`. When the target binary is missing, the adapter MUST fail loud with an error message that names the binary and gives install guidance rather than returning an empty or fake-green result.

#### Scenario: run() invokes the CLI with a timeout and returns an AgentRunResult

- **WHEN** a concrete `SubprocessCLIAdapter` subclass has its `run(prompt)` called with the target binary installed and credentials present
- **THEN** the adapter builds argv via `build_argv(prompt)`, runs the subprocess with the configured timeout and `start_new_session=True`, and returns an `AgentRunResult` produced by `parse_output`

#### Scenario: missing binary fails loud with install guidance

- **WHEN** `run(prompt)` is called but the target CLI binary is not found on `PATH`
- **THEN** the adapter raises an error whose message names the missing binary and includes install guidance, and does not return a populated or empty `AgentRunResult`

#### Scenario: secrets from the environment are never logged

- **WHEN** the adapter sources an API key or token from `os.environ` to invoke the CLI
- **THEN** the secret value does not appear in adapter logs, subprocess-command logs, RF output, or any field of the returned `AgentRunResult`

#### Scenario: subprocess timeout is enforced

- **WHEN** the underlying CLI does not return within the configured timeout
- **THEN** the subprocess is terminated and the adapter surfaces a timeout error rather than hanging indefinitely

### Requirement: Concrete FULL/PARTIAL adapters normalize CLI output into AgentRunResult

The system SHALL provide concrete adapters for `claude-code`, `gemini`, `codex`, and `opencode` that each normalize their CLI output into an `AgentRunResult` carrying `tool_calls` (as `ToolCallTrace` records), token `usage`, `cost_usd`, and `latency_seconds`. Each adapter SHALL read structured JSON from stdout when present and fall back to the newest on-disk session/rollout transcript (for example `~/.claude/projects/…`, `~/.codex/sessions/…`) when stdout is thin. Cost SHALL follow the precedence native → `litellm.completion_cost`, and the adapter SHALL record on `AgentRunMetadata` whether cost/token numbers are native or derived.

#### Scenario: stdout JSON is normalized into AgentRunResult

- **WHEN** a FULL/PARTIAL adapter runs and its CLI emits structured JSON on stdout
- **THEN** the adapter parses that JSON into an `AgentRunResult` with `tool_calls` populated as `ToolCallTrace` records plus token usage, cost, and latency

#### Scenario: on-disk session transcript fallback when stdout is thin

- **WHEN** the CLI stdout lacks the structured tool-call/usage data
- **THEN** the adapter reads the newest on-disk session/rollout transcript for that run and normalizes it into the same `AgentRunResult` shape

#### Scenario: derived cost is flagged in metadata

- **WHEN** an adapter cannot obtain a native cost and computes it via `litellm.completion_cost`
- **THEN** the resulting `AgentRunResult` records on `AgentRunMetadata` that the cost/token numbers are derived rather than native

### Requirement: DEGRADED adapters carry a VALIDATION-CEILING marker

The system SHALL provide best-effort `kilo` and `copilot` adapters at fidelity tier DEGRADED. Each DEGRADED adapter SHALL rely on a session-log/transcript fallback where stdout JSON is unavailable and MUST carry a VALIDATION-CEILING marker stating what it cannot reliably report (for example: tool calls only probed, tokens estimated, cost from premium-request counters). The DEGRADED status and the VALIDATION-CEILING marker MUST be surfaced so downstream metrics never read a degraded run as complete.

#### Scenario: DEGRADED adapter surfaces its VALIDATION-CEILING

- **WHEN** the `kilo` or `copilot` adapter produces an `AgentRunResult`
- **THEN** the result is marked fidelity tier DEGRADED and carries a VALIDATION-CEILING marker naming the metrics it cannot reliably report

#### Scenario: copilot falls back to session log when no JSON stdout is available

- **WHEN** the `copilot` adapter runs and the CLI emits no structured JSON on stdout
- **THEN** the adapter reads the on-disk session log to populate what it can and marks the run DEGRADED with its VALIDATION-CEILING

### Requirement: Each adapter records a fidelity tier so degraded metrics never read as complete

Every CLI adapter SHALL record a fidelity tier of FULL, PARTIAL, or DEGRADED on its `AgentRunResult`. The recorded tier MUST match the adapter's documented capability (`claude-code`/`gemini` FULL; `codex`/`opencode` PARTIAL; `kilo`/`copilot` DEGRADED) so that metrics computed over the run cannot present incomplete data as complete.

#### Scenario: fidelity tier is present on every run result

- **WHEN** any CLI adapter returns an `AgentRunResult`
- **THEN** the result records a fidelity tier of exactly one of FULL, PARTIAL, or DEGRADED matching that adapter's documented capability

### Requirement: Each adapter probes --version and raises AdapterVersionDriftWarning outside a pinned range

Each CLI adapter SHALL probe the CLI's `--version` and record it on `AgentRunMetadata`. When the detected version falls outside the adapter's pinned tested range, the adapter SHALL raise `AdapterVersionDriftWarning` so that parse logic is not silently applied to an untested CLI version.

#### Scenario: version is recorded on metadata

- **WHEN** an adapter runs against an installed CLI whose version is within the pinned range
- **THEN** the detected `--version` string is recorded on `AgentRunMetadata` and no warning is raised

#### Scenario: out-of-range version raises AdapterVersionDriftWarning

- **WHEN** an adapter detects a CLI `--version` outside its pinned tested range
- **THEN** the adapter raises `AdapterVersionDriftWarning`

### Requirement: Each adapter ships a live E2E smoke gated on binary and credentials

Each CLI adapter SHALL ship a live end-to-end smoke test that runs a real prompt through the CLI as the empirical-truth check. Each smoke SHALL be gated on both the target binary being present and the required credentials being available, and MUST skip (not fail) when either is missing so the deterministic CI gate is unaffected.

#### Scenario: smoke runs when binary and credentials are present

- **WHEN** the adapter's live E2E smoke runs with the target binary installed and required credentials set
- **THEN** the smoke drives a real prompt through the CLI and asserts a normalized `AgentRunResult` is produced

#### Scenario: smoke skips when binary or credentials are missing

- **WHEN** the adapter's live E2E smoke runs but the binary is absent or credentials are unset
- **THEN** the smoke is skipped rather than failed, leaving the default deterministic gate green

### Requirement: A failed CLI invocation fails loud, never a silent-empty result

When a CLI adapter's subprocess exits non-zero and yields no usable output (empty or
unparseable stdout and no recoverable session transcript), the adapter SHALL raise
`AdapterError` that names the CLI and surfaces the CLI's stderr, rather than
returning an empty or degraded `AgentRunResult`. This extends the existing
fail-loud, no-fake-green guarantee from the missing-binary case to the
failed-invocation case, so a misconfigured or refused run cannot be read downstream
as a (thin) successful run.

#### Scenario: Non-zero exit with no output raises with the CLI's stderr

- **WHEN** a CLI adapter runs and the subprocess exits non-zero producing no parseable
  stdout and no usable session transcript
- **THEN** the adapter raises `AdapterError` naming the CLI and including its stderr,
  instead of returning an `AgentRunResult` with empty response and zero usage

#### Scenario: A partial-but-usable run is still returned

- **WHEN** a CLI run exits non-zero but still emitted parseable output or a usable
  transcript
- **THEN** the adapter returns an `AgentRunResult` marked not-complete (e.g.
  `completeness` other than `complete`) rather than raising, so recoverable partial
  data is preserved

### Requirement: The codex adapter drives codex exec non-interactively for its supported version

The `codex` adapter SHALL build a `codex exec` command line that runs
non-interactively on its supported codex version — including `--json`,
`--skip-git-repo-check`, and a bounded execution mode sufficient for a measurement
run. The adapter SHALL NOT bake a fully-approval-and-sandbox-bypassing mode in as a
silent default; any such dangerous mode SHALL be an explicit, documented opt-in. The
adapter SHALL keep its parse logic aligned to the codex output schema of its pinned
version and SHALL raise `AdapterVersionDriftWarning` for a codex version outside that
range.

#### Scenario: codex runs non-interactively and returns a populated result

- **WHEN** the codex adapter runs against an installed, supported codex against a
  simple prompt
- **THEN** codex executes without waiting for interactive approval and the adapter
  returns an `AgentRunResult` whose response text and token usage reflect the run

#### Scenario: A dangerous full-bypass mode is opt-in, not default

- **WHEN** the codex adapter is used with default settings
- **THEN** it does not silently pass a flag that disables all approvals and
  sandboxing; enabling that behavior requires an explicit, documented option

