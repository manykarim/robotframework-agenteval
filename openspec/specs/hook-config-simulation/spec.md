# hook-config-simulation Specification

## Purpose
TBD - created by archiving change add-hooks-execution-testing. Update Purpose after archive.
## Requirements
### Requirement: Static "which hooks would fire" simulation

The system SHALL provide a `Get Hooks For Event` keyword that answers, for a
given parsed hook config, event name, and matcher subject (for example a tool
name), which configured hooks would fire — WITHOUT executing anything. The
simulation SHALL use the same matcher engine as `Fire Hook Event`, so static
simulation and live execution can never disagree about which hooks match.

#### Scenario: Simulation lists matching hooks without execution
- **WHEN** `Get Hooks For Event` is called with a config, `PreToolUse`, and
  `tool_name=Bash`
- **THEN** it SHALL return the configured hooks whose matcher matches `Bash` and
  SHALL NOT spawn any subprocess

#### Scenario: Simulation and execution agree on matches
- **WHEN** the same config, event, and subject are passed to both
  `Get Hooks For Event` and `Fire Hook Event`
- **THEN** the set of hooks reported by the simulation SHALL equal the set of
  hooks the execution attempts to run

### Requirement: Matcher engine follows the protocol character-class dispatch

The matcher engine SHALL implement the documented Claude Code dispatch: a
matcher of `*`, empty string, or omitted matches all; a matcher containing only
letters, digits, `_`, `-`, spaces, `,`, and `|` is treated as an exact match or
a `|`/`,`-separated list of exact matches; any other matcher is compiled with
Python `re` and matched unanchored via `re.search`. The divergence between
Python `re` and JavaScript RegExp SHALL be documented on the validation keyword.

#### Scenario: Wildcard and empty matchers match all
- **WHEN** a hook's matcher is `*`, an empty string, or omitted
- **THEN** the hook SHALL be reported as matching for any subject

#### Scenario: Pipe list matches any listed exact name
- **WHEN** a hook's matcher is `Bash|Edit`
- **THEN** the hook SHALL match subject `Bash` and subject `Edit` but not
  subject `Read`

#### Scenario: Non-simple matcher is treated as a regex
- **WHEN** a hook's matcher contains characters outside the simple class (for
  example `mcp__.*`)
- **THEN** it SHALL be compiled with Python `re` and matched unanchored against
  the subject

### Requirement: Matcher syntax validation

The system SHALL provide a `Validate Matcher Syntax` keyword that checks a
matcher compiles under the engine's dispatch rules and, when a subject is
supplied, optionally reports whether it matches that subject. Compile failures
SHALL be reported with the offending pattern, and the Python-`re`-vs-JS-RegExp
divergence SHALL be documented on the keyword so users have a deterministic
pre-flight for regex matchers.

#### Scenario: Invalid regex reports the offending pattern
- **WHEN** `Validate Matcher Syntax` is called with a matcher that is not a
  simple list and fails to compile as a Python regex
- **THEN** the keyword SHALL fail with a message naming the offending pattern

#### Scenario: Optional subject match check
- **WHEN** `Validate Matcher Syntax` is called with a valid matcher and a
  subject
- **THEN** it SHALL report whether the matcher matches that subject

### Requirement: Command-resolves-on-disk sanity check

The system SHALL provide a `Hook Command Should Exist` keyword that, for each
configured hook command, takes the first `shlex`-split token (or the `command`
itself in exec form), expands a literal `$CLAUDE_PROJECT_DIR` or
`${CLAUDE_PROJECT_DIR}` prefix against a `project_dir` argument, and resolves it
via `shutil.which` or a path-existence-plus-executable-bit check. The docstring
SHALL state that this is a heuristic pre-flight checking the first token only,
not a full shell parse.

#### Scenario: Resolvable command passes
- **WHEN** a hook command's first token resolves to an executable on `PATH` or
  on disk
- **THEN** `Hook Command Should Exist` SHALL pass for that hook

#### Scenario: Missing command fails before any live session depends on it
- **WHEN** a hook command's first token cannot be resolved to an executable
- **THEN** `Hook Command Should Exist` SHALL fail, naming the unresolved command

### Requirement: All hook-config-simulation keywords are Tier-1

Every keyword added by this capability SHALL be annotated `@tier(1)`, since
matcher simulation, syntax validation, and command-resolution checks are static
analyses that execute no hook scripts and require no API keys.

#### Scenario: Simulation keywords carry the Tier-1 annotation
- **WHEN** the conventions test suite inspects the new simulation keywords
- **THEN** each SHALL be annotated `@tier(1)`

