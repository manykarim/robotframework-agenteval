# Tasks: accept-real-claude-hook-config

## 1. Fixtures (write the target inputs first)

- [x] 1.1 Copy current `tests/fixtures/hooks/settings-valid.json` to new
      `tests/fixtures/hooks/settings-legacy-flat.json` (pins the deprecation path)
- [x] 1.2 Rewrite `tests/fixtures/hooks/settings-valid.json` to the real nested
      format: `PreToolUse` group with `matcher` + 2 typed definitions,
      `PostToolUse` group, matcher-less `Stop` group (design D5)
- [x] 1.3 Rewrite `tests/fixtures/hooks/settings-missing-command.json` so the
      failure is a real-format `type: "command"` definition missing `command`
      inside a matcher group (exercises 5-segment pointer)
- [x] 1.4 Add `tests/fixtures/hooks/settings-real-world.json` mirroring the
      official docs example: command + http + prompt hook types, `Edit|Write`
      and `mcp__memory__.*` matchers, `SessionStart` event, extra fields
      (`async`, `statusMessage`, `if`) for passthrough coverage

## 2. Parser rewrite (`src/AgentEval/hooks/_parser.py`)

- [x] 2.1 Add per-item format classification in `parse_hook_config`: matcher
      group (`hooks` list present) vs legacy flat (`command` present, no
      `hooks`) vs ambiguous/neither → `InvalidHookConfigError` with item pointer
      + real-schema fix suggestion (design D1)
- [x] 2.2 Implement matcher-group handling: validate group `matcher` is str
      when present, group `hooks` is a list; flatten definitions into entries
      with group `matcher` copied on, preserving order (design D2)
- [x] 2.3 Implement per-type definition validation: `type` non-empty str when
      present; required fields `command`/`url`/`server`+`tool`/`prompt` per
      type; `timeout` int-not-bool everywhere; type-less-with-`command`
      grandfathered to `type: "command"`; unknown types passed through
      (design D3)
- [x] 2.4 Normalize legacy flat entries through the existing command-entry
      validation and stamp `"type": "command"`; emit exactly ONE
      `DeprecationWarning` per parse call when any legacy entry was seen,
      naming the file + real schema (design D1)
- [x] 2.5 Change return keys from `f"hooks.{event}"` to plain `event` (design
      D2, BREAKING)
- [x] 2.6 Extend `inline_skill` extraction + reserved-key rejection to
      real-format command definitions with 5-segment pointers; keep unknown
      entry fields passing through onto returned entries
- [x] 2.7 Rewrite every fix suggestion that teaches the flat shape to quote the
      real nested schema (design D4); update the module docstring's format
      description
- [x] 2.8 Run 5-nullish-variant checks on new required fields (`type`, `url`,
      `server`, `tool`, `prompt`): `None`, `""`, `False`, `0`, missing-key
      (per `feedback_nullish_input_fuzz_checklist`)

## 3. Library surface (`src/AgentEval/hooks/library.py`)

- [x] 3.1 Update the `Get Config` docstring: real nested input schema as
      primary, deprecated legacy flat input, normalized return shape with
      plain event keys, `${config}[PreToolUse]` examples (spec: keyword
      documentation requirement)
- [x] 3.2 Update the module docstring usage block (`${config["hooks.PreToolUse"]}`
      → `${config}[PreToolUse]`)
- [x] 3.3 Smoke-verify docstring examples via the existing docstring-example
      dryrun conventions tests (`tests/unit/conventions/`) + libdoc render
      check (per `feedback_executable_doc_precheck`)

## 4. Test migration + new coverage

- [x] 4.1 Migrate `tests/unit/hooks/test_library.py` off `"hooks.<event>"`
      keys; update pointer assertions to nested pointers where fixtures moved
- [x] 4.2 Add unit tests for every spec scenario: real-format parse, matcher
      copy + ordering, matcher-less group, unknown event, unknown type
      passthrough, unknown field passthrough, per-type required-field failures
      (http/mcp_tool/prompt/agent), type-less grandfathering, ambiguous item
      rejection, legacy parse + `type` stamp, single-DeprecationWarning
      (`pytest.warns` + count), nested `inline_skill` extraction + reserved-key
      rejection, absent-`hooks` → `{}`
- [x] 4.3 Migrate `tests/unit/hooks/test_robot_integration.robot` to
      `${config}[PreToolUse]` access
- [x] 4.4 Migrate conformance consumers:
      `tests/conformance/test_tier1_byte_identical_run.py`,
      `tests/conformance/test_ac_static_inspection_fixtures.py`,
      `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`
- [x] 4.5 Migrate `tests/integration/static_inspection/test_real_world_samples.py`
      + add a case parsing `settings-real-world.json` asserting all events and
      non-command types survive normalization
- [x] 4.6 Full gate: `uv run pytest tests/` green; `uv run ruff check src/ tests/`;
      `uv run mypy src/`

## 5. Docs + drift closure

- [x] 5.1 Update the README `Get Config` snippet to the new access shape (ONLY
      the hooks snippet — README-wide fixes belong to `fix-first-run-experience`)
- [x] 5.2 Annotate PRD FR4 drift per design D6: note in
      `_bmad-output/planning-artifacts/prd.md` (or the project's drift log if
      PRD is frozen) that the ratified hook schema is now
      `openspec/specs/hook-config-parsing/spec.md`
- [x] 5.3 Grep new/changed files for `DF-X-SY` markers and verify each is in
      `docs/phase-1-5-carry-overs.md` (per `feedback_carry_over_catalog_gate`,
      BEFORE review)
- [x] 5.4 Note in `openspec/changes/add-hooks-execution-testing/` (when drafted)
      that it consumes the normalized entry shape from this change and must be
      implemented after it
