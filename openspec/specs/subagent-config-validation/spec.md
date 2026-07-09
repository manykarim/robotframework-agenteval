# subagent-config-validation Specification

## Purpose
TBD - created by archiving change add-subagent-delegation-testing. Update Purpose after archive.
## Requirements
### Requirement: Frontmatter parser type-checks the optional skills field

The subagent frontmatter validation SHALL type-check an optional `skills`
field when present (in
`AgentEval.subagents._parser.validate_subagent_structure`, surfaced through
`Get Frontmatter`): it MUST be a list of non-empty strings, mirroring the
existing `tools` field treatment. A malformed `skills` field SHALL raise
`InvalidSubagentDefinitionError` with `field_name="skills"` and a
`fix_suggestion`. The PRD FR3 required-field set (`name`, `description`) and
all existing validation behavior MUST remain unchanged.

#### Scenario: Valid skills list is returned in the frontmatter dict
- **WHEN** `Get Frontmatter` parses a subagent `.md` whose frontmatter includes
  `skills: [pdf-tools, web-search]`
- **THEN** the returned dict SHALL contain `skills` as that list of strings and
  no error SHALL be raised

#### Scenario: Non-list skills field fails loud
- **WHEN** the frontmatter declares `skills: pdf-tools` (a bare string) or a
  list containing a non-string entry
- **THEN** `Get Frontmatter` SHALL raise `InvalidSubagentDefinitionError`
  identifying the `skills` field

#### Scenario: Absent skills field remains valid at parse time
- **WHEN** the frontmatter has no `skills` key but valid `name` and
  `description`
- **THEN** `Get Frontmatter` SHALL succeed (the drift check below, not the
  parser, enforces explicit declaration)

### Requirement: Explicit skills declaration is assertable (config-drift check)

The system SHALL provide a Tier-1 keyword `Subagent.Should Declare Skills`
taking a subagent `.md` path and one or more skill names, passing only when
the frontmatter contains an explicit `skills:` list that includes every named
skill. Because subagents do NOT inherit the parent agent's skills, an absent
or empty `skills:` field SHALL fail the assertion — not vacuously pass.
Failures raise `SubagentConfigDriftError` naming the missing skill(s), the
file path, and a `fix_suggestion` explaining that skills must be explicitly
preloaded in subagent frontmatter.

#### Scenario: All required skills are declared
- **WHEN** `Subagent.Should Declare Skills    agents/researcher.md    pdf-tools
  web-search` is called on a file declaring
  `skills: [pdf-tools, web-search, citations]`
- **THEN** the keyword SHALL return without raising

#### Scenario: Missing skill fails with the drift diagnostic
- **WHEN** the same call is made on a file declaring only
  `skills: [pdf-tools]`
- **THEN** it SHALL raise `SubagentConfigDriftError` naming `web-search` as
  missing, with a `fix_suggestion` referencing explicit frontmatter preloading

#### Scenario: Absent skills field fails rather than vacuously passing
- **WHEN** the call is made on a subagent file with no `skills:` key at all
- **THEN** it SHALL raise `SubagentConfigDriftError` stating that no skills are
  declared and that subagents do not inherit parent skills

#### Scenario: Unparseable subagent file propagates the definition error
- **WHEN** the given path does not parse as a valid subagent definition
- **THEN** the keyword SHALL raise `InvalidSubagentDefinitionError` (not
  `SubagentConfigDriftError`)

### Requirement: Tools allowlist is assertable with a fail-loud inherit-all default

The system SHALL provide a Tier-1 keyword `Subagent.Tools Should Be Subset Of`
taking a subagent `.md` path and an allowlist of tool names, passing only when
the frontmatter declares a `tools:` list whose every entry is in the
allowlist. Because an absent `tools` field means the subagent inherits the
full parent tool set, a missing or empty `tools:` field SHALL fail the
assertion. Failures raise `SubagentConfigDriftError` listing the offending
tools (or the absence of a declaration), the file path, and a
`fix_suggestion`.

#### Scenario: Declared tools within the allowlist pass
- **WHEN** `Subagent.Tools Should Be Subset Of    agents/reviewer.md    Read
  Grep    Bash` is called on a file declaring `tools: [Read, Grep]`
- **THEN** the keyword SHALL return without raising

#### Scenario: Tool outside the allowlist fails naming the offender
- **WHEN** the file declares `tools: [Read, WebFetch]` and the allowlist is
  `Read, Grep, Bash`
- **THEN** it SHALL raise `SubagentConfigDriftError` naming `WebFetch` as
  outside the allowlist

#### Scenario: Absent tools field fails loud as inherit-everything
- **WHEN** the file declares no `tools:` field
- **THEN** it SHALL raise `SubagentConfigDriftError` explaining that omitting
  `tools` inherits the full parent tool set and suggesting an explicit
  `tools:` declaration

