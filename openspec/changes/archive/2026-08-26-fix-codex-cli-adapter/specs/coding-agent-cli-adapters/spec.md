## ADDED Requirements

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
