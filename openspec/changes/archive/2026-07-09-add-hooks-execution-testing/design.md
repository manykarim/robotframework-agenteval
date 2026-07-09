# Design: add-hooks-execution-testing

## Context

`HooksLibrary` today ships exactly one keyword, `Get Config`
(`src/AgentEval/hooks/library.py`), which statically parses a hook
`settings.json`. Nothing in the library — or, per
`docs/ai-testing-tools-landscape.md` §6, anywhere in the market — can *execute*
a configured hook against a synthetic event and assert on its decision. Hooks
are the ideal AgentEval surface: they are deterministic local programs speaking
a documented protocol, so the whole capability is Tier-1 with zero API keys.

The real Claude Code hook protocol (researched from
https://code.claude.com/docs/en/hooks, 2026-07-08):

- **stdin**: one JSON object per event. Common fields: `session_id`,
  `transcript_path`, `cwd`, `hook_event_name`, `permission_mode`. Event-specific
  fields: `tool_name` + `tool_input` (PreToolUse family), plus `tool_response`
  (PostToolUse), `prompt` (UserPromptSubmit), `last_assistant_message`
  (Stop/SubagentStop), etc.
- **exit codes**: `0` = success, stdout parsed as JSON if valid; `2` = blocking
  error — stdout/JSON *ignored*, stderr is the message; any other code =
  non-blocking error.
- **stdout JSON**: universal fields (`continue`, `stopReason`,
  `suppressOutput`, `systemMessage`, `additionalContext`) plus
  `hookSpecificOutput` with `hookEventName` and per-event fields —
  `permissionDecision` (`allow`/`deny`/`ask`/`defer`) +
  `permissionDecisionReason` + `updatedInput` for PreToolUse; top-level
  `decision: "block"` + `reason` for the PostToolUse/Stop/UserPromptSubmit
  family.
- **matchers**: `*` / `""` / omitted = match-all; strings containing only
  letters, digits, `_`, `-`, spaces, `,`, `|` = exact match or `|`/`,`-separated
  list; anything else = an unanchored JS RegExp against the tool name (or the
  event's matcher subject — session source, agent type, etc.).
- **timeouts**: command hooks default to 600 s, per-entry `timeout` (seconds)
  overrides.
- **entries**: matcher groups `{"matcher": ..., "hooks": [{"type": "command",
  "command": ..., "args": [...], "timeout": N}, ...]}`; hook types include
  `command`, `http`, `mcp_tool`, `prompt`, `agent` — only `command` is a local
  deterministic program.
- **env**: Claude Code exposes `CLAUDE_PROJECT_DIR` (and plugin/remote
  variables) to hook processes.

**Hard dependency**: the sibling change `accept-real-claude-hook-config` must
land first — today's parser (`src/AgentEval/hooks/_parser.py`) rejects the real
nested matcher-group shape (findings dossier E2). This design consumes the
parsed config that sibling produces and does not restate the parsing contract.

## Goals / Non-Goals

**Goals:**
- Execute configured `type: "command"` hooks against synthetic, protocol-correct
  stdin payloads and capture exit code / stdout / stderr / parsed JSON /
  duration per hook.
- Normalize the protocol's three decision channels (exit code, PreToolUse
  `permissionDecision`, PostToolUse/Stop `decision`) into one assertable
  vocabulary.
- Static matcher simulation ("which hooks would fire for tool X?") and config
  sanity checks (matcher compiles; command resolves on disk) with no execution.
- Subprocess safety: hard timeouts far below Claude Code's 600 s default,
  sanitized environment, process-group kill.
- All keywords `@tier(1)`; no LLM anywhere in the loop.

**Non-Goals:**
- Parsing-format work (owned by `accept-real-claude-hook-config`).
- Executing `http` / `mcp_tool` / `prompt` / `agent` hook types — they require a
  network endpoint or an LLM. They are *reported* (skipped with a reason), never
  silently dropped.
- End-to-end headless `claude -p` integration runs asserting that Claude Code
  itself honors the hook decision. That is a possible later Tier-2 extension
  (single live agent round-trip) and is deliberately excluded so this capability
  stays deterministic and key-free.
- Reproducing Claude Code's *reaction* to a decision (e.g. that a blocked tool
  call never runs) — we assert on what the hook said, not on the host's
  enforcement.

## Decisions

### Decision 1: Execute from the parsed config object, not from a file path

`Fire Hook Event` takes the dict returned by `Get Config` (post-sibling: real
nested format normalized to flat entries with `type`/`command`/`args`/
`timeout`/`matcher`), not a `settings.json` path. *Alternative considered:*
accepting a path and re-parsing internally — rejected: it duplicates parsing,
hides the dependency on the sibling change, and prevents users from firing
against a programmatically built/filtered config (useful for testing one hook
in isolation). A path convenience can be added later without breaking anything.

### Decision 2: Schema-aware payload synthesis with full-override escape hatch

The runner builds the stdin JSON: common fields (`session_id` — synthetic
constant, `transcript_path` — path under a temp dir, `cwd`, `hook_event_name`,
`permission_mode: "default"`) merged with event-specific fields from keyword
kwargs (`tool_name=Bash`, `tool_input=${dict}`, `prompt=...`,
`tool_response=${dict}`, ...). Unknown events are allowed: common fields +
kwargs pass through verbatim (forward-compat with Claude Code's growing event
list, mirroring the parser's permissive stance on non-PRD events). A
`payload=${dict}` kwarg replaces the synthesized event-specific fields wholesale
(synthesized common fields still fill gaps, explicit keys win). *Alternative
considered:* strict per-event schemas for all ~30 documented events — rejected:
the protocol is version-volatile; we pin exact synthesis only for the PRD FR4
events (PreToolUse / PostToolUse / Stop) and stay permissive elsewhere.

### Decision 3: One normalized decision vocabulary — `block` / `allow` / `ask` / `none`

Derivation, in protocol-faithful precedence order:

1. exit code `2` → `block` (stdout JSON ignored, per protocol).
2. exit `0` + stdout JSON `hookSpecificOutput.permissionDecision`:
   `"deny"` → `block`; `"allow"` → `allow`; `"ask"` → `ask`; `"defer"` → `none`.
3. exit `0` + top-level `decision: "block"` → `block`.
4. exit `0` with no decision-bearing JSON → `none` (no opinion; host default
   flow applies).
5. any other exit code → `none` with `status="nonblocking_error"` recorded.

`Hook Decision Should Be` accepts `deny` as an alias of `block` so users can
assert in either the protocol's PreToolUse vocabulary or the exit-code
vocabulary. Raw `exit_code`, `stdout`, `stderr`, and parsed `stdout_json` stay
on the result object for precise assertions (e.g.
`permissionDecisionReason`). *Alternative considered:* exposing only raw fields
and no normalization — rejected: every user would re-implement the same
three-channel precedence logic, and getting the "exit 2 ignores stdout" rule
wrong is exactly the class of bug this library should encapsulate.

### Decision 4: Per-hook result records; never raise mid-fire; fail-loud on zero matches

`Fire Hook Event` returns a report containing one frozen-dataclass record per
configured hook for the event: matched hooks carry
`status="completed" | "timed_out" | "spawn_failed"` plus captures; non-matching
hooks are omitted; matching non-`command` hooks carry `status="skipped"` +
`skip_reason` (e.g. `type=http not locally executable`). Execution failures
(missing binary, timeout) are *recorded*, not raised, so a multi-hook event
reports every hook; decision/exit-code assertions on a non-`completed` record
fail loud with the status in the message. Exception: zero matching hooks raises
`HookExecutionError` immediately (fix_suggestion pointing at
`Get Hooks For Event`) — returning an empty report would let
`Hook Decision Should Be` never run and produce a fake-green
(`feedback_dogfood_fake_green_precheck` class). *Alternative considered:*
raising on first hook failure — rejected: hides sibling hooks' behavior and
makes negative tests ("the hook times out") awkward.

### Decision 5: Matcher engine — protocol character-class rule, Python `re` for the regex path

Implement the documented dispatch: `*`/empty/omitted → match-all; matcher
containing only `[A-Za-z0-9_\- ,|]` → exact or `|`/`,`-separated exact list;
otherwise compile with Python `re` and match unanchored (`re.search`). Python
`re` is not JS RegExp; the divergence (e.g. lookbehind flavor, `\u{...}`) is
documented on `Validate Matcher Syntax`, which reports compile failures with
the offending pattern. This is the same engine for `Get Hooks For Event`
(static) and `Fire Hook Event` (execution), so simulation and execution can
never disagree. *Alternative considered:* embedding a JS engine for fidelity —
rejected: a heavyweight dependency for an edge users can avoid by testing their
matcher with `Validate Matcher Syntax`.

### Decision 6: Sanitized subprocess environment, default-deny

Hook subprocesses get an explicit allowlist env (`PATH`, `HOME`, `LANG`,
`LC_*`, `TMPDIR`, `USER`, `SHELL`) plus `CLAUDE_PROJECT_DIR` (keyword arg
`project_dir=`, default: the test's cwd) and an optional user-supplied
`extra_env=${dict}`. The parent process environment is NOT inherited by default
— the RF test process routinely holds provider API keys, and handing them to a
user-authored (possibly third-party) hook script under test violates the
project's key-hygiene norm (CLAUDE.md hard rules). `inherit_env=True` is an
explicit opt-in for hooks that genuinely need it. Docs state plainly:
**these keywords execute user-authored hook scripts locally with the invoking
user's privileges** — sanitization limits leakage, it is not a sandbox.
*Alternative considered:* full inheritance like Claude Code itself does —
rejected: Claude Code runs hooks the user installed for themselves; a test
harness runs hooks *under test*, a lower-trust position.

### Decision 7: Timeout — honor per-entry `timeout`, default far below 600 s

Effective timeout = entry `timeout` if set, else keyword `default_timeout=`
(default 30 s — deliberately not Claude Code's 600 s, which would hang a test
suite; documented divergence). Spawn with `start_new_session=True`; on timeout
kill the process group (mirrors `SubprocessAdapter`'s cleanup pattern) and
record `status="timed_out"`. Command strings run through the shell (protocol:
commands are shell commands); an entry with an `args` array uses exec form
(command + args, no shell), mirroring the real protocol's exec-form trigger.

### Decision 8: Minimal error-surface growth — exactly one new error class

`HookExecutionError` (subclassing the FR59 Tier-1 base like
`InvalidHookConfigError`) for zero-match and misuse failures. Config-shape
problems keep raising `InvalidHookConfigError`; assertion keywords fail via
standard RF assertion failures. Findings dossier E5 flags `errors.py` at 30
classes with ~15 ever raised — this change adds one, not a per-failure-mode
hierarchy.

### Decision 9: Command-resolution check via `shlex` + `which`

`Hook Command Should Exist` takes the first `shlex`-split token of each
`command` (or the `command` itself in exec form), expands a literal
`$CLAUDE_PROJECT_DIR`/`${CLAUDE_PROJECT_DIR}` prefix against `project_dir=`,
and resolves via `shutil.which` / path existence + executable bit. Shell
builtins and inline compound commands (`jq ... | grep ...` resolves `jq`) are
handled by checking the first token only; the docstring states this is a
heuristic pre-flight, not a shell parse.

## Risks / Trade-offs

- **[Protocol drift — Claude Code adds/changes events and fields]** → strict
  synthesis only for the 3 PRD-pinned events; permissive passthrough elsewhere;
  the docstring records the documented-protocol snapshot date. A later
  `AdapterVersionDriftWarning`-style check is possible but out of scope.
- **[Python `re` vs JS RegExp divergence in matcher simulation]** → documented
  limitation + `Validate Matcher Syntax` gives users a deterministic pre-flight;
  simulation and execution share one engine so they cannot disagree with each
  other.
- **[Executing user-authored scripts locally is inherently unsandboxed]** →
  default-deny env, no parent-secret inheritance, prominent docs. We do NOT
  claim sandboxing (the dead `security/` package stays dead per findings
  dossier E5).
- **[Windows shell semantics differ (protocol's `shell: powershell`)]** →
  Phase-1 executes via the POSIX default shell for string commands and exec
  form for `args` entries; `shell` field is recorded but not honored — carry-over
  documented with a `DF-X-SY` marker per `feedback_carry_over_catalog_gate`.
- **[Sibling-change coupling — normalized entry shape may shift]** → tasks
  gate implementation on the sibling landing; the runner consumes only
  `type`/`command`/`args`/`timeout`/`matcher`, the minimal stable subset.
- **[Fixture hook scripts can rot / be platform-dependent]** → fixtures are
  tiny `python3 -c`-style or `#!/usr/bin/env python3` scripts (not bash) for
  portability, committed under `tests/fixtures/hooks/exec/`.

## Migration Plan

Purely additive: new keywords on `HooksLibrary`, new private modules, one new
error class. No existing keyword changes; rollback = remove the new modules and
keywords. Gated by `uv run pytest tests/`, `uv run ruff check src/ tests/`,
`uv run mypy src/`, and the conventions suites (docstring style, tier
annotation, libdoc render) which pick up new keywords automatically.

## Open Questions

- Exact normalized entry shape produced by `accept-real-claude-hook-config`
  (field name for hook `type`; whether matcher-group nesting is flattened) —
  resolve when the sibling lands; Task 1 re-checks this before implementation.
  - **RESOLVED (sibling landed 2026-07-08):** `Get Config` returns
    `dict[str, list[dict]]` keyed by PLAIN event name (e.g. `config["PreToolUse"]`).
    Matcher groups are FLATTENED — each entry is one hook definition with a
    `type` field always present and the group's `matcher` copied on when present.
    This change consumes that flattened per-entry shape and MUST be implemented
    only after `accept-real-claude-hook-config` is applied.
- Whether v1 should ship convenience assertions for `updatedInput` /
  `additionalContext` (PreToolUse input-rewriting hooks) — deferred; raw
  `stdout_json` access covers it, and demand should drive the sugar.
