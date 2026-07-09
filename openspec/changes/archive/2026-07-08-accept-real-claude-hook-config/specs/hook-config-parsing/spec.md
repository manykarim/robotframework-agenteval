# hook-config-parsing — Delta Specification

## ADDED Requirements

### Requirement: Parser accepts the real nested Claude Code hooks format

`parse_hook_config` (surfaced as `HooksLibrary.Get Config`) SHALL accept the real
Claude Code `settings.json` hooks structure: a top-level `hooks` mapping from
event name to a list of matcher groups, where each matcher group is an object
with an optional `matcher` string and a required `hooks` list of typed hook
definitions (verified against https://code.claude.com/docs/en/hooks, 2026-07-08).
The parser SHALL accept any event name (unknown events receive identical shape
validation) and SHALL accept matcher groups without a `matcher` key (matcher-less
events and match-all groups).

#### Scenario: Real-world settings.json parses without error
- **WHEN** `Get Config` is called on a file containing
  `{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}}`
- **THEN** the call SHALL return successfully (no `InvalidHookConfigError`) and
  the result SHALL contain one `PreToolUse` entry with `command == "echo hi"`

#### Scenario: Matcher-less group is accepted
- **WHEN** a matcher group under an event has no `matcher` key but has a valid
  `hooks` list
- **THEN** the group's hook definitions SHALL be returned as entries for that
  event, without a `matcher` field forced onto them

#### Scenario: Unknown event names pass through
- **WHEN** the config declares an event name outside `PreToolUse` /
  `PostToolUse` / `Stop` (e.g. `SessionStart`) with valid matcher groups
- **THEN** the event SHALL appear in the returned mapping with its validated
  entries

### Requirement: Both input formats normalize into one canonical entry shape

The parser SHALL return `dict[str, list[dict]]` keyed by PLAIN event name (e.g.
`"PreToolUse"`, replacing the former flattened `"hooks.PreToolUse"` string keys).
Matcher groups SHALL be flattened: each inner hook definition becomes one entry
in the event's list with the group's `matcher` (when present) copied onto it,
preserving source order (groups in order, definitions in order within each
group). Every returned entry SHALL carry a `type` field. Keys not validated by
the parser (e.g. `if`, `async`, `statusMessage`, `once`, `url`, `headers`,
`server`, `tool`, `input`, `prompt`, `model`, and future fields) SHALL pass
through onto the returned entry unmodified.

#### Scenario: Plain event-name keys
- **WHEN** a valid config declaring `PreToolUse` hooks is parsed
- **THEN** the result SHALL expose the entries under key `"PreToolUse"` and
  SHALL NOT contain a `"hooks.PreToolUse"` key

#### Scenario: Group matcher is copied onto each flattened entry
- **WHEN** one matcher group with `"matcher": "Edit|Write"` contains two hook
  definitions
- **THEN** the event's list SHALL contain two entries, each with
  `matcher == "Edit|Write"`, in the definitions' source order

#### Scenario: Unknown fields pass through
- **WHEN** a `command`-type definition carries extra fields such as
  `"async": true` and `"statusMessage": "linting..."`
- **THEN** the returned entry SHALL include those fields with their original
  values

### Requirement: Legacy flat entries remain accepted with a deprecation warning

An event-array item that has a `command` key and no `hooks` key SHALL be treated
as a legacy flat entry (the pre-change invented shape), validated under the
existing `command`-entry rules, normalized with `"type": "command"` stamped onto
it, and returned in the same canonical shape as real-format entries. When at
least one legacy flat entry is encountered, the parser SHALL emit exactly one
`DeprecationWarning` per parse call, naming the file and pointing at the real
Claude Code schema. No new warning or error class SHALL be added to
`AgentEval.errors`.

#### Scenario: Legacy flat config still parses
- **WHEN** `Get Config` is called on the legacy-flat fixture
  (`{"hooks": {"PreToolUse": [{"command": "echo x", "matcher": "*"}]}}`)
- **THEN** the result SHALL contain a `PreToolUse` entry with
  `command == "echo x"`, `matcher == "*"`, and `type == "command"`

#### Scenario: Deprecation warning emitted once per parse
- **WHEN** a config containing two legacy flat entries is parsed
- **THEN** exactly one `DeprecationWarning` SHALL be emitted for the call

#### Scenario: Ambiguous item is rejected
- **WHEN** an event-array item contains BOTH a `command` key and a `hooks` key,
  or NEITHER
- **THEN** the parser SHALL raise `InvalidHookConfigError` with a `field_name`
  pointer to that item and a fix suggestion quoting the real nested schema

### Requirement: Typed hook definitions are validated by type

For real-format hook definitions the parser SHALL validate: `type` is a
non-empty string when present; `type: "command"` requires a non-empty string
`command` (with existing `args` list-of-str and `timeout` int-not-bool rules);
`type: "http"` requires a non-empty string `url`; `type: "mcp_tool"` requires
non-empty strings `server` and `tool`; `type: "prompt"` and `type: "agent"`
require a non-empty string `prompt`; `timeout` when present on any definition
MUST be an int and not a bool. A definition with `command` present but `type`
absent SHALL be accepted and normalized to `type: "command"`. Definitions with
an unknown `type` string SHALL be accepted and passed through without per-type
field validation. Group-level `matcher`, when present, MUST be a string.

#### Scenario: Command definition missing command fails with nested pointer
- **WHEN** a `PreToolUse` matcher group's second hook definition has
  `"type": "command"` but no `command`
- **THEN** the parser SHALL raise `InvalidHookConfigError` whose `field_name` is
  `/hooks/PreToolUse/0/hooks/1/command`

#### Scenario: Non-command types validate their required field
- **WHEN** an `http`-type definition omits `url` (or an `mcp_tool` omits
  `server`/`tool`, or a `prompt`/`agent` omits `prompt`)
- **THEN** the parser SHALL raise `InvalidHookConfigError` pointing at the
  missing required field of that definition

#### Scenario: Type-less definition with command is grandfathered
- **WHEN** a real-format hook definition has `command` but no `type`
- **THEN** it SHALL be validated as a command hook and returned with
  `type == "command"`

#### Scenario: Unknown type passes through
- **WHEN** a definition has `"type": "some_future_type"` and arbitrary fields
- **THEN** the entry SHALL be returned as-is (plus copied group `matcher`)
  without an error

### Requirement: Errors keep the FR59 format with pointers into the real nesting

All structural failures SHALL continue to raise `InvalidHookConfigError` with
the File/Line/Field/Fix message format, where `field_name` carries an RFC 6901
JSON Pointer into the offending location of the SOURCE document — 5-segment
pointers for real-format definition fields
(`/hooks/<event>/<group_index>/hooks/<def_index>/<field>`), 4-segment for group
fields (`/hooks/<event>/<group_index>/matcher`), and 3-segment for legacy flat
entry fields. Fix suggestions SHALL describe the real Claude Code schema, not
the legacy flat shape. Existing file-level failure behavior (missing file,
non-`.json` extension, malformed JSON with `line_number`, non-object top level,
non-mapping `hooks`, absent `hooks` key returning `{}`) SHALL be preserved.

#### Scenario: Group hooks value not a list
- **WHEN** a matcher group's `hooks` value is a string
- **THEN** the parser SHALL raise `InvalidHookConfigError` with `field_name`
  `/hooks/<event>/<group_index>/hooks` and a fix suggestion describing a JSON
  array of typed hook definitions

#### Scenario: Absent hooks key still returns empty mapping
- **WHEN** the settings file is a valid JSON object without a `hooks` key
- **THEN** `Get Config` SHALL return `{}` without raising

### Requirement: Inline-skill frontmatter extraction is preserved on command entries

The parser SHALL surface inline-skill YAML frontmatter on every normalized
entry with `type == "command"`, from either input format: when the `command`
string begins with a column-0 YAML frontmatter block whose mapping contains
BOTH `name` and `description`, the parsed mapping SHALL appear as an
`inline_skill` dict on the returned entry. `inline_skill` SHALL
remain a reserved output key: a source entry or hook definition supplying its
own `inline_skill` field SHALL raise `InvalidHookConfigError` with a pointer to
that field.

#### Scenario: Inline skill extracted from a real-format command hook
- **WHEN** a real-format `command`-type definition's command starts with
  `---\nname: guard\ndescription: blocks rm\n---\n...`
- **THEN** the returned entry SHALL include
  `inline_skill == {"name": "guard", "description": "blocks rm"}`

#### Scenario: Reserved key collision rejected in nested location
- **WHEN** a real-format hook definition contains an `inline_skill` field
- **THEN** the parser SHALL raise `InvalidHookConfigError` with `field_name`
  `/hooks/<event>/<group_index>/hooks/<def_index>/inline_skill`

### Requirement: Keyword documentation and fixtures describe the accepted schema

The `HooksLibrary.Get Config` libdoc docstring SHALL document: the real nested
input schema as primary, the deprecated legacy flat input, the normalized
returned entry shape with plain event-name keys, and examples using
`${config}[PreToolUse]` access. Test fixtures under `tests/fixtures/hooks/`
SHALL include a real-nested valid config, a real-format missing-command config,
a legacy-flat config, and a verbatim real-world sample mirroring the official
docs example (multiple hook types and a matcher-less event group). The README
`Get Config` snippet SHALL use the new access shape.

#### Scenario: Docstring examples match the new return shape
- **WHEN** the `Get Config` docstring examples are dryrun-checked by the
  existing docstring-example conventions tests
- **THEN** they SHALL reference `${config}[PreToolUse]`-style keys and pass

#### Scenario: Real-world fixture parses in integration tests
- **WHEN** the static-inspection integration suite parses
  `tests/fixtures/hooks/settings-real-world.json`
- **THEN** parsing SHALL succeed and yield entries for every event in the
  fixture, including non-command hook types

## REMOVED Requirements

### Requirement: Flattened `hooks.<event>` return keys
**Reason**: The `"hooks.PreToolUse"` composite string keys were an invented
shape — awkward in Robot Framework item access and misleading (looks like
attribute traversal). Replaced by plain event-name keys as part of the one-time
format-correction break.
**Migration**: Replace `${config}[hooks.PreToolUse]` with
`${config}[PreToolUse]` (Python: `config["hooks.PreToolUse"]` →
`config["PreToolUse"]`). Entry fields `command` / `args` / `timeout` /
`matcher` are unchanged; entries additionally always carry `type`.
