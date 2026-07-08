# Design: accept-real-claude-hook-config

## Context

`src/AgentEval/hooks/_parser.py::parse_hook_config` (Story 2.2) validates a shape
that Claude Code does not produce. It requires each item of an event array to be a
flat object with a required `command` string and optional `args` / `timeout` /
`matcher`, and returns `{"hooks.<event>": [entries]}` (a flattened string key,
`library.py` L93 / `_parser.py` L195).

The real Claude Code format nests one extra level (matcher groups) and types the
inner hook definitions. **Verified against the official docs on 2026-07-08 via
WebFetch of https://code.claude.com/docs/en/hooks** — what was verified:

- Structure is 3-level: `hooks` → event name → list of *matcher groups*
  (`{"matcher": "<pattern>", "hooks": [<hook defs>]}`) → inner `hooks` list of
  hook definitions.
- Five hook definition types exist: `command`, `http`, `mcp_tool`, `prompt`,
  `agent`. `type` is documented as required on every definition. Common optional
  fields: `if`, `timeout` (seconds), `statusMessage`, `once`.
- `command`-type fields: `command` (required), `args`, `async`, `asyncRewake`,
  `shell`. `http`: `url` (required), `headers`, `allowedEnvVars`. `mcp_tool`:
  `server` + `tool` (required), `input`. `prompt` / `agent`: `prompt` (required),
  `model`.
- 31 event names exist today (far beyond the PRD-pinned PreToolUse / PostToolUse /
  Stop); some events support `matcher`, some don't (matcher-less events still use
  the group wrapper, with `matcher` omitted).
- Matcher values are regex-ish tool/source patterns (`Bash`, `Edit|Write`,
  `mcp__memory__.*`), and `"*"` / omitted both mean match-all.

Empirical failure (findings dossier E2): feeding a real config raises
`InvalidHookConfigError` ("missing `command`") because the matcher group has no
`command` — its `hooks` key holds the definitions.

Constraint from the repo: `errors.py` is 1,064 LOC / 30 classes with ~15 ever
raised (dossier E5) — do not add new error classes. The sibling change
`add-hooks-execution-testing` will consume this parser's output to fire synthetic
hook events, so the normalized entry shape designed here is a contract for that
change too.

## Goals / Non-Goals

**Goals:**

- A real, current Claude Code `settings.json` parses successfully out of the box.
- One canonical, format-independent returned shape that `.robot` assertions and
  `add-hooks-execution-testing` can rely on.
- Legacy flat configs (our own historical invented shape) keep working, loudly
  deprecated.
- Errors keep the File/Line/Field/Fix format and RFC 6901 pointers, now pointing
  into the real nested locations.
- Docstrings + fixtures + schema documentation match the implementation.

**Non-Goals:**

- Executing hooks or asserting on hook decisions (`add-hooks-execution-testing`).
- README-wide doc repair beyond the one `Get Config` snippet
  (`fix-first-run-experience`).
- Modeling all 31 events with per-event matcher-support validation — we validate
  shape, not event semantics.
- `${CLAUDE_PROJECT_DIR}`-style placeholder expansion (execution-time concern).

## Decisions

### D1 — Accept BOTH formats, auto-detected per event-array item

Each item in an event array is classified:

- **Matcher group** (real format): the item has a `hooks` key whose value is a
  list. `matcher` is optional (matcher-less events / match-all).
- **Legacy flat entry**: the item has a `command` key and NO `hooks` key.
- Anything else (both keys, neither key, `hooks` not a list) → typed error with a
  pointer to the item and a fix suggestion quoting the real schema.

*Why not nested-only?* Our own fixtures, scaffold output, and any early adopter
configs use the flat form; a silent hard break of the form we invented and
documented would be hostile. *Why not keep flat as the primary?* It matches no
real tool — the keyword's stated purpose is parsing Claude Code configs.

Legacy items trigger a single `DeprecationWarning` per parse call (Python
`warnings.warn`, message naming the file and the real schema). No new warning
class in `errors.py` (E5 constraint); RF surfaces Python warnings in logs.

### D2 — Normalize both formats into ONE canonical entry shape; return plain event-name keys (BREAKING)

Return type stays `dict[str, list[dict[str, Any]]]`, but:

- **Keys are plain event names** (`"PreToolUse"`), replacing the flattened
  `"hooks.PreToolUse"` string keys. The old shape forced
  `${config}[hooks.PreToolUse]` — a magic composite string that looks like
  attribute access but isn't, confuses RF users, and was flagged while touching
  this surface (task scope). Since D1 already changes what inputs mean, this is
  the one release-window to fix the key shape too. All in-repo consumers (6 test
  files + README snippet) migrate in this change.
- **Matcher groups are flattened**: each inner hook definition becomes one entry
  in the event's list, with the group's `matcher` copied onto it. Rationale: the
  wrapper carries exactly one datum (`matcher`); assertions and the execution
  change both want per-hook entries ("does a Bash-matched command hook exist?"),
  not group traversal. Order is preserved (groups in order, definitions in order
  within each group).
- **Every entry carries `type`** — from the real format verbatim; legacy flat
  entries are stamped `"type": "command"` (that is semantically what they were).
- **Unknown keys pass through** (`if`, `async`, `statusMessage`, `once`, `url`,
  `headers`, `server`, `tool`, `input`, `prompt`, `model`, future fields...).
  The parser validates what it knows and preserves what it doesn't — same
  forward-compat posture the parser already ratified for unknown events.
- `inline_skill` extraction unchanged: applied to `command`-type entries whose
  `command` starts with a canonical YAML frontmatter block; `inline_skill`
  remains a reserved output key (existing Blind-MED-1 rule kept, pointer updated).

Alternative considered: keep the group structure in the return value
(`[{"matcher": ..., "hooks": [...]}]`). Rejected — pushes nesting-traversal into
every `.robot` file and into `add-hooks-execution-testing`, for zero information
gain over the copied-`matcher` flattening.

### D3 — Per-type validation depth: strict on `command`, required-field-only on the other four, permissive on unknown types

- `type` must be a non-empty string when present. In REAL-format definitions a
  missing `type` is an error (docs say required)… with one pragmatic exception:
  a definition with `command` present and `type` absent is accepted and stamped
  `command` (older real-world configs predate strict typing; hard-failing on
  them re-creates the exact E2 problem one level down).
- `type: "command"` → existing validation preserved: `command` required non-empty
  str, `args` list[str], `timeout` int-not-bool, plus inline-skill extraction.
- `http` → `url` required non-empty str. `mcp_tool` → `server` + `tool` required
  non-empty str. `prompt` / `agent` → `prompt` required non-empty str. `timeout`
  int-not-bool wherever present. No deeper validation (headers shapes etc.) —
  that is execution-scope.
- Unknown `type` values → accepted, passed through unvalidated. Claude Code adds
  types faster than we release; failing closed would rot.
- `matcher` on a group must be a str when present (existing rule, moved to the
  group level). SUPPORTED_EVENTS stays as the PRD-pinned trio for documentation
  purposes; all events get identical shape validation (status quo).

### D4 — Error pointers extend into the nest; messages name the real schema

`field_name` pointers gain the inner segment where applicable:
`/hooks/PreToolUse/0/hooks/1/command`, `/hooks/PreToolUse/0/matcher`,
`/hooks/PreToolUse/0/hooks` (group's `hooks` not a list). Legacy flat entries
keep 3-segment pointers (`/hooks/PreToolUse/0/command`) since that is where the
data physically is. `_build_pointer` already handles arbitrary segments — no
change. Every fix suggestion that today teaches the invented flat shape is
rewritten to quote the real nested shape.

### D5 — Fixtures: real format primary, legacy + verbatim-real added

`tests/fixtures/hooks/` becomes:

- `settings-valid.json` — rewritten to the real nested format (multiple events,
  matcher groups incl. a matcher-less one, multiple hook types).
- `settings-missing-command.json` — rewritten so the failure is a real-format
  `command`-type definition missing `command` (nested pointer exercised).
- `settings-malformed-json.json` — unchanged (JSON-level failure is
  format-independent).
- `settings-legacy-flat.json` — NEW: the current `settings-valid.json` content,
  preserved to pin the deprecation path.
- `settings-real-world.json` — NEW: verbatim-shaped sample matching the official
  docs example (command + http + prompt types, `mcp__.*` matcher, SessionStart),
  pinning "the real thing parses" as a regression test.

Consumers under `tests/conformance/test_ac_static_inspection_fixtures.py` and
`tests/integration/static_inspection/test_real_world_samples.py` migrate with the
fixtures.

### D6 — PRD FR4 drift resolved toward reality

PRD FR4 describes the flat shape. Per `feedback_spec_vs_ratified_doc_precheck`
("fix-the-losing-source-NOW"), the losing source is the PRD: it documented an
assumed format that empirically diverges from the tool it names. The spec written
by this change (`specs/hook-config-parsing/spec.md`) becomes the ratified schema
description; the implementation task list includes a PRD-drift annotation task
rather than silently leaving FR4 contradicted.

## Risks / Trade-offs

- [BREAKING return-shape change breaks external early adopters' `.robot` files]
  → Pre-1.0 library; the old shape was already unusable against real configs
  (E2), so real-world usage of the old key shape against real settings.json is
  approximately zero. Deprecation note + libdoc docstring + error-free legacy
  *input* acceptance soften the input side; the output side is a clean one-time
  break called out as **BREAKING** in the proposal.
- [Claude Code schema keeps evolving (31 events today, 5 types today)] →
  Permissive passthrough of unknown events, unknown types, unknown fields;
  validation is anchored only on documented-required fields. The
  `settings-real-world.json` fixture pins today's snapshot.
- [Flattening matcher groups loses group identity] → No known consumer needs
  group identity; if `add-hooks-execution-testing` later needs it, an optional
  `_group_index` passthrough can be added additively without breaking the shape.
- [Missing-`type` exception (D3) could mask genuinely malformed definitions] →
  Exception is narrow: only when `command` is present; everything else about the
  definition is still validated as a command hook.
- [Single `DeprecationWarning` per parse may be missed in RF logs] → Also
  documented in the keyword docstring's Notes section; the execution-testing
  change will only document the real format, shrinking legacy exposure.

## Migration Plan

1. Land parser + library docstring + fixtures + all in-repo consumer migrations
   in one commit (the repo's tests are the only known consumers).
2. `README.md` hooks snippet updated to the new access shape
   (`${config}[PreToolUse]`) in the same commit — a stale snippet would be a
   fresh E3-class drift.
3. Rollback: revert the commit; fixtures and consumers travel together.

## Open Questions

- None blocking. (Whether `SUPPORTED_EVENTS` should grow beyond the PRD trio is
  deliberately deferred — it is documentation-only today and expanding it has no
  behavioral effect.)

## Dependency note

`add-hooks-execution-testing` MUST build on the normalized entry shape defined
here (plain event keys; flat entries with `type` + copied `matcher`). It should
not start implementation before this change is applied.
