# Proposal: add-hooks-execution-testing

## Why

Hooks are billed as a first-class eval target, but the shipped surface is one parse-only keyword (`Get Config`) — all four independent fresh-user CLI trials flagged the expectation mismatch (findings dossier E4), and E6 ranks hooks execution testing as the highest differentiation-per-effort gap on the roadmap. `docs/ai-testing-tools-landscape.md` §6 confirms no dedicated framework exists anywhere for testing agent hooks: "an RF library firing synthetic hook events and asserting on decisions … would be novel in this space." Hooks are deterministic scripts with a documented stdin/stdout/exit-code protocol, so AgentEval can own this category with Tier-1 keywords that need no API keys and have no market competitor.

## What Changes

- **Hook event execution**: a `Fire Hook Event` keyword that takes a parsed hook config plus an event name (`PreToolUse`, `PostToolUse`, `Stop`, and other Claude Code events) and synthesizes the real Claude Code stdin JSON payload (common fields `session_id` / `transcript_path` / `cwd` / `hook_event_name` plus event-specific fields such as `tool_name` / `tool_input`), then executes every configured `type: "command"` hook whose matcher matches — capturing exit code, stdout, stderr, parsed stdout JSON, and duration per hook.
- **Decision assertions**: keywords asserting on the normalized block/allow decision derived from the real protocol semantics — exit code `2` = block (stderr is the message, stdout JSON ignored); exit `0` + stdout JSON `hookSpecificOutput.permissionDecision` (`allow`/`deny`/`ask`) or top-level `decision: "block"` (PostToolUse/Stop family); exit `0` with no decision JSON = no opinion. Plus exit-code and stdout-JSON field assertions.
- **Matcher simulation (static)**: `Get Hooks For Event` answers "given this tool name, which configured hooks would fire?" without executing anything; `Validate Matcher Syntax` checks a matcher compiles and optionally matches a given tool name (exact / `|`-list / regex / `*` / empty-string semantics per the real protocol).
- **Config sanity checks**: `Hook Command Should Exist` verifies each configured hook command resolves to an executable on disk before any live session depends on it.
- **Subprocess safety**: per-hook timeout honored (config `timeout` field, with a keyword-level default far below Claude Code's 600 s so test suites cannot hang); hook subprocesses run with a sanitized environment (explicit allowlist + `CLAUDE_PROJECT_DIR`, no silent inheritance of parent secrets). Documentation states plainly that these keywords execute user-authored hook scripts locally.
- **Tiering**: every keyword is `@tier(1)` — hook scripts are deterministic programs; executing them involves no LLM. This follows the ratified tier taxonomy (`src/AgentEval/_kernel/tier.py`).

**Dependency (explicit)**: this change depends on the sibling change `accept-real-claude-hook-config` landing first — the parser must understand the real nested Claude Code `settings.json` shape (`{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "..."}]}]}}`) before execution keywords can consume real configs. Today `Get Config` hard-fails on that shape (findings dossier E2). This change consumes the parsed representation that sibling produces; the parsing-format change itself is NOT in scope here.

**Not in scope**: end-to-end headless `claude -p` integration runs (documented in the design as a possible later Tier-2 extension); non-`command` hook types (`http`, `mcp_tool`, `prompt`, `agent`) beyond reporting them as skipped; any change to the settings.json parsing format (sibling change).

## Capabilities

### New Capabilities

- `hook-execution`: firing synthetic Claude Code hook events against configured command hooks — payload synthesis per event type, subprocess execution with timeout and env sanitization, per-hook result capture, and decision/exit-code/output assertion keywords.
- `hook-config-simulation`: static (no-execution) hook config analysis — matcher-based "which hooks would fire" simulation, matcher syntax validation, and command-resolves-on-disk checks.

### Modified Capabilities

_None — `openspec/specs/` currently contains only `opencode-cli-adapter`, which is untouched. The hook config parsing contract is owned by the sibling change `accept-real-claude-hook-config`._

## Impact

- **Code**: `src/AgentEval/hooks/` gains execution + matcher modules (e.g. `_runner.py`, `_matcher.py`); `HooksLibrary` (`src/AgentEval/hooks/library.py`) gains the new keywords alongside the existing `Get Config`; at most one new error class in `src/AgentEval/errors.py` (per findings dossier E5, errors.py is already 30 classes — reuse `InvalidHookConfigError` for config-shape failures).
- **Tests**: new unit tests under `tests/unit/hooks/` with committed fixture hook scripts (deterministic, exit-0/exit-2/JSON-emitting/slow/missing variants) under `tests/fixtures/hooks/`; conventions tests (docstring style, tier annotation) pick the new keywords up automatically.
- **Docs**: README keyword table + a hooks-testing recipe; explicit local-script-execution security note.
- **Dependencies**: no new third-party dependencies (stdlib `subprocess`, `shlex`, `shutil`, `re`, `json`).
- **Sibling changes**: hard dependency on `accept-real-claude-hook-config` (see above); complements `fix-first-run-experience` (which documents the currently-accepted input schema).
