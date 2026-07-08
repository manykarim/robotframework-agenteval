# Proposal: accept-real-claude-hook-config

## Why

`HooksLibrary.Get Config` — the headline (and only) hooks keyword — hard-fails with
`InvalidHookConfigError` when fed a real, current Claude Code `settings.json`
(findings dossier E2, empirically reproduced). The parser expects flat entries
`{"command", "args", "timeout", "matcher"}`, but Claude Code has used a nested
matcher-group format for a long time:
`{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "..."}]}]}}`.
The most obvious real-world input for the keyword is rejected, and no documentation
warns of the divergence. The sibling change `add-hooks-execution-testing` (hooks
EXECUTION testing, the top market-differentiation item in dossier E6) builds on this
parser, so the accepted schema must be fixed first.

## What Changes

- Teach `AgentEval.hooks._parser.parse_hook_config` to accept the real nested
  Claude Code format: event → list of matcher groups → inner `hooks` list of typed
  hook definitions (`type: "command" | "http" | "mcp_tool" | "prompt" | "agent"`),
  verified against the official docs (https://code.claude.com/docs/en/hooks,
  fetched 2026-07-08; details in design.md).
- Keep accepting the legacy flat entry form (`{"command", ...}` directly in the
  event list) with a `DeprecationWarning`; both forms normalize into ONE canonical
  returned entry shape so `.robot` assertions are format-independent.
- **BREAKING**: replace the odd flattened string-key return shape
  (`config["hooks.PreToolUse"]`) with plain event-name keys
  (`config["PreToolUse"]`). Every returned entry carries a normalized shape with
  `type` always present and the group `matcher` copied onto each entry.
- Error messages / RFC 6901 `field_name` pointers extended to the nested locations
  (e.g. `/hooks/PreToolUse/0/hooks/1/command`); fix suggestions rewritten to name
  the real Claude Code schema instead of the invented flat one.
- Update `tests/fixtures/hooks/` to the real nested format (keeping one legacy-flat
  fixture for the deprecation path), update libdoc docstrings on
  `HooksLibrary.Get Config`, and document the accepted schema.
- Inline-skill-frontmatter extraction (`inline_skill`) is preserved and applied to
  `command`-type hook definitions in both formats.

Out of scope: hook EXECUTION testing (sibling change `add-hooks-execution-testing`
depends on this change), README-wide documentation fixes (`fix-first-run-experience`).

## Capabilities

### New Capabilities

- `hook-config-parsing`: parsing + validation of Claude Code `settings.json` hook
  configurations into a normalized, format-independent structure consumable from
  Robot Framework — real nested format as primary, legacy flat format as deprecated
  alias, typed errors with RFC 6901 pointers, inline-skill frontmatter surfacing.

### Modified Capabilities

<!-- none — no existing spec in openspec/specs/ covers hooks; this change creates
     the first spec for the hooks surface -->

## Impact

- **Code**: `src/AgentEval/hooks/_parser.py` (main rewrite),
  `src/AgentEval/hooks/library.py` (docstring + return-shape docs). No new error
  classes (reuses `InvalidHookConfigError`; `errors.py` is already oversized per
  dossier E5).
- **Return-shape consumers (BREAKING migration)**: `tests/unit/hooks/test_library.py`,
  `tests/unit/hooks/test_robot_integration.robot`,
  `tests/conformance/test_tier1_byte_identical_run.py`,
  `tests/conformance/test_ac_static_inspection_fixtures.py`,
  `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`,
  `tests/integration/static_inspection/test_real_world_samples.py`, and the
  `Get Config` example in `README.md` (only the hooks snippet — README-wide fixes
  stay in `fix-first-run-experience`).
- **Fixtures**: `tests/fixtures/hooks/*.json` rewritten to real format + one new
  legacy-flat fixture + one real-world-verbatim fixture.
- **Docs**: `HooksLibrary` libdoc docstrings; accepted-schema documentation.
- **Dependents**: `add-hooks-execution-testing` consumes the normalized entry shape
  produced here and MUST be implemented after this change.
- **PRD note**: PRD FR4 describes the flat shape; the spec-vs-ratified-doc drift is
  resolved in favor of empirical reality (the real Claude Code schema) — see
  design.md.
