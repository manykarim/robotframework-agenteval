# hook-execution Specification

## Purpose
TBD - created by archiving change add-hooks-execution-testing. Update Purpose after archive.
## Requirements
### Requirement: Fire a synthetic hook event against a parsed config

The system SHALL provide a `Fire Hook Event` keyword that accepts a parsed hook
config object (the normalized representation produced by `Get Config` after the
sibling `accept-real-claude-hook-config` change) plus an event name, synthesizes
a protocol-correct Claude Code stdin JSON payload, and executes every configured
`type: "command"` hook whose matcher matches the event. The keyword MUST NOT
accept a `settings.json` file path in place of the parsed config, so the
dependency on the parsed representation stays explicit and callers can fire
against a programmatically built or filtered config.

#### Scenario: Matching command hook is executed
- **WHEN** `Fire Hook Event` is called with a parsed config containing a
  `PreToolUse` command hook whose matcher matches `Bash` and the event kwargs
  `tool_name=Bash`
- **THEN** the configured command SHALL be executed as a subprocess and its
  exit code, stdout, stderr, parsed stdout JSON, and duration SHALL be captured
  on a per-hook result record

#### Scenario: Zero matching hooks fails loud
- **WHEN** `Fire Hook Event` is called for an event/tool combination that no
  configured hook matcher matches
- **THEN** the keyword SHALL raise `HookExecutionError` immediately (rather than
  returning an empty report), with a `fix_suggestion` pointing at
  `Get Hooks For Event`

### Requirement: Payload synthesis is schema-aware with a full-override escape hatch

The runner SHALL synthesize the stdin JSON by merging synthetic common fields
(`session_id`, `transcript_path` under a temp dir, `cwd`, `hook_event_name`,
`permission_mode`) with event-specific fields supplied as keyword kwargs. It
SHALL pin exact event-specific synthesis for the three PRD FR4 events
(`PreToolUse`, `PostToolUse`, `Stop`) and pass common fields plus kwargs through
verbatim for any other (including future) event name. A `payload` dict kwarg
SHALL replace the synthesized event-specific fields wholesale, with synthesized
common fields still filling gaps and explicit keys winning.

#### Scenario: PreToolUse payload carries tool fields
- **WHEN** `Fire Hook Event` synthesizes a `PreToolUse` payload with
  `tool_name=Bash` and a `tool_input` dict
- **THEN** the stdin JSON delivered to the hook SHALL contain `hook_event_name`,
  the common fields, `tool_name`, and `tool_input`

#### Scenario: Unknown event name passes through permissively
- **WHEN** `Fire Hook Event` is called with an event name outside the three
  pinned events plus arbitrary kwargs
- **THEN** the stdin JSON SHALL contain the common fields and the kwargs
  verbatim, and no error SHALL be raised solely because the event is unknown

### Requirement: Normalized decision vocabulary

The system SHALL derive one normalized decision from the real protocol's three
channels using this precedence: exit code `2` yields `block` (stdout JSON
ignored, stderr is the message); exit `0` with stdout JSON
`hookSpecificOutput.permissionDecision` maps `deny` to `block`, `allow` to
`allow`, `ask` to `ask`, and `defer` to `none`; exit `0` with top-level
`decision: "block"` yields `block`; exit `0` with no decision-bearing JSON
yields `none`; any other exit code yields `none` recorded with a
non-blocking-error status. A `Hook Decision Should Be` keyword SHALL assert the
normalized decision and MUST accept `deny` as an alias of `block`.

#### Scenario: Exit code 2 blocks and ignores stdout JSON
- **WHEN** a hook exits with code `2` while also printing an `allow` decision on
  stdout
- **THEN** the normalized decision SHALL be `block` and the stdout JSON SHALL
  NOT override it

#### Scenario: PreToolUse deny maps to block alias
- **WHEN** a hook exits `0` with `hookSpecificOutput.permissionDecision: "deny"`
- **THEN** `Hook Decision Should Be    block` and `Hook Decision Should Be
  deny` SHALL both pass for that hook result

#### Scenario: No decision-bearing output yields none
- **WHEN** a hook exits `0` and prints no decision JSON
- **THEN** the normalized decision SHALL be `none`

### Requirement: Per-hook result records; execution failures recorded not raised

`Fire Hook Event` SHALL return a report containing one frozen-dataclass record
per configured hook that matched the event. Each record SHALL carry a status of
`completed`, `timed_out`, `spawn_failed`, or `skipped`. Matching non-`command`
hook types SHALL be recorded with status `skipped` and a `skip_reason` rather
than silently dropped. Execution failures (missing binary, timeout) SHALL be
recorded on the record, not raised mid-fire, so a multi-hook event reports every
hook. Decision, exit-code, and output assertions performed against a record
whose status is not `completed` SHALL fail loud with the status in the message.

#### Scenario: One slow hook does not hide its siblings
- **WHEN** an event fires two matching hooks where the first times out and the
  second completes
- **THEN** the report SHALL contain both records, the first with status
  `timed_out` and the second with status `completed`

#### Scenario: Non-command hook type is reported as skipped
- **WHEN** a matching hook has a type other than `command` (for example `http`)
- **THEN** its record SHALL have status `skipped` and a `skip_reason` naming the
  unsupported type, and SHALL NOT be executed

#### Scenario: Assertion on a non-completed record fails loud
- **WHEN** `Hook Decision Should Be` is called against a record with status
  `spawn_failed`
- **THEN** the assertion SHALL fail with a message naming the `spawn_failed`
  status rather than reporting a misleading decision

### Requirement: Subprocess safety — sanitized environment and enforced timeout

Hook subprocesses SHALL run with a sanitized, default-deny environment: an
explicit allowlist (`PATH`, `HOME`, `LANG`, `LC_*`, `TMPDIR`, `USER`, `SHELL`)
plus `CLAUDE_PROJECT_DIR` (from a `project_dir` kwarg defaulting to the test's
cwd) and an optional `extra_env` dict. The parent process environment MUST NOT
be inherited by default; `inherit_env=True` SHALL be an explicit opt-in. Each
hook SHALL run under an effective timeout equal to its config `timeout` entry
when set, else a keyword-level `default_timeout` (default 30 s, deliberately far
below Claude Code's 600 s). Subprocesses SHALL be spawned with
`start_new_session=True`, and on timeout the process group SHALL be killed and
the record marked `timed_out`. Documentation SHALL state plainly that these
keywords execute user-authored hook scripts locally with the invoking user's
privileges and that sanitization limits leakage rather than sandboxing.

#### Scenario: Parent secrets are not inherited by default
- **WHEN** the RF test process holds a provider API key in its environment and a
  hook is fired without `inherit_env`
- **THEN** the hook subprocess environment SHALL NOT contain that key, only the
  allowlisted variables plus `CLAUDE_PROJECT_DIR` and any `extra_env`

#### Scenario: Timeout kills the process group
- **WHEN** a hook runs longer than its effective timeout
- **THEN** the process group SHALL be killed and the record SHALL be marked
  `timed_out`

### Requirement: Command execution honors shell vs exec form

The runner SHALL execute a hook whose config provides a bare `command` string
through the shell (protocol: hook commands are shell commands), and SHALL
execute a hook that additionally provides an `args` array in exec form (command
plus args, no shell), mirroring the real protocol's exec-form trigger.

#### Scenario: String command runs via shell
- **WHEN** a hook config provides only a `command` string containing a pipe
- **THEN** the command SHALL be executed through the shell so the pipe is
  honored

#### Scenario: Command with args runs in exec form
- **WHEN** a hook config provides a `command` plus an `args` array
- **THEN** the command SHALL be executed in exec form without shell
  interpretation

### Requirement: All hook-execution keywords are Tier-1

Every keyword added by this capability SHALL be annotated `@tier(1)` per the
ratified tier taxonomy, because hook scripts are deterministic local programs
whose execution involves no LLM and requires no API keys.

#### Scenario: Execution keywords carry the Tier-1 annotation
- **WHEN** the conventions test suite inspects the new hook-execution keywords
- **THEN** each SHALL be annotated `@tier(1)`

