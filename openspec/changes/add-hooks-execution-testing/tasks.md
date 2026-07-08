## 1. Preconditions and dependency gate

- [ ] 1.1 Confirm the sibling change `accept-real-claude-hook-config` has landed and `Get Config` returns the normalized nested-matcher-group representation; re-check the exact normalized entry shape (field name for hook `type`; whether matcher-group nesting is flattened) per design Open Questions before writing the runner
- [ ] 1.2 Record the consumed stable subset of the parsed config (`type` / `command` / `args` / `timeout` / `matcher`) so the runner depends only on that subset
- [ ] 1.3 Confirm no new third-party dependency is required (stdlib `subprocess`, `shlex`, `shutil`, `re`, `json` only)

## 2. Matcher engine (shared by simulation and execution)

- [ ] 2.1 Add `src/AgentEval/hooks/_matcher.py` implementing the protocol character-class dispatch: `*`/empty/omitted match-all; simple class (`[A-Za-z0-9_\- ,|]`) exact or `|`/`,`-separated list; otherwise Python `re` unanchored `re.search`
- [ ] 2.2 Expose a compile/validate entry point that reports compile failures with the offending pattern; document the Python-`re`-vs-JS-RegExp divergence
- [ ] 2.3 Unit tests under `tests/unit/hooks/` covering wildcard/empty/omitted, exact, pipe/comma lists, regex path, and invalid-regex failure

## 3. Payload synthesis

- [ ] 3.1 Add stdin JSON synthesis: common fields (`session_id` synthetic constant, `transcript_path` under temp dir, `cwd`, `hook_event_name`, `permission_mode: "default"`) merged with event-specific kwargs
- [ ] 3.2 Pin exact event-specific synthesis for the three PRD FR4 events (`PreToolUse`, `PostToolUse`, `Stop`); pass common fields plus kwargs through verbatim for any other event name
- [ ] 3.3 Implement the `payload=${dict}` full-override escape hatch (synthesized common fields fill gaps, explicit keys win)
- [ ] 3.4 Unit tests: PreToolUse carries `tool_name`/`tool_input`; unknown event passes through permissively; `payload` override replaces event-specific fields

## 4. Subprocess runner and result records

- [ ] 4.1 Add `src/AgentEval/hooks/_runner.py` executing each matching `type: "command"` hook; string `command` via shell, `command`+`args` in exec form
- [ ] 4.2 Implement default-deny sanitized env (allowlist `PATH`/`HOME`/`LANG`/`LC_*`/`TMPDIR`/`USER`/`SHELL` + `CLAUDE_PROJECT_DIR` from `project_dir=` + optional `extra_env=`); `inherit_env=True` explicit opt-in
- [ ] 4.3 Implement effective timeout (entry `timeout` else `default_timeout=30`), `start_new_session=True`, process-group kill on timeout, `status="timed_out"`
- [ ] 4.4 Define frozen-dataclass per-hook result record capturing `exit_code`/`stdout`/`stderr`/`stdout_json`/`duration`/`status`/`skip_reason`; record execution failures (`spawn_failed`, `timed_out`) instead of raising mid-fire
- [ ] 4.5 Record matching non-`command` hooks as `status="skipped"` with a `skip_reason`; never silently drop
- [ ] 4.6 Record `shell` field for `args`-less entries but do not honor Windows/powershell `shell`; add a `DF-X-SY` carry-over marker per `feedback_carry_over_catalog_gate`

## 5. Decision normalization

- [ ] 5.1 Implement the three-channel precedence: exit `2` → `block` (ignore stdout JSON); exit `0` + `hookSpecificOutput.permissionDecision` (`deny`→`block`, `allow`→`allow`, `ask`→`ask`, `defer`→`none`); exit `0` + top-level `decision: "block"` → `block`; exit `0` no decision JSON → `none`; other exit → `none` + `nonblocking_error` status
- [ ] 5.2 Unit tests covering each precedence branch, especially "exit 2 ignores an allow stdout"

## 6. HooksLibrary keywords

- [ ] 6.1 Add `Fire Hook Event` (parsed config + event + kwargs → per-hook report); raise `HookExecutionError` immediately on zero matches with `fix_suggestion` pointing at `Get Hooks For Event`
- [ ] 6.2 Add `Hook Decision Should Be` asserting the normalized decision; accept `deny` as an alias of `block`; fail loud when the target record status is not `completed`
- [ ] 6.3 Add exit-code and stdout-JSON field assertion keywords over the raw record fields
- [ ] 6.4 Add `Get Hooks For Event` (static, no execution) using the shared matcher engine
- [ ] 6.5 Add `Validate Matcher Syntax` (compile check + optional subject match) reporting the offending pattern and the regex-flavor divergence
- [ ] 6.6 Add `Hook Command Should Exist` (first `shlex` token, `$CLAUDE_PROJECT_DIR` expansion, `shutil.which`/exec-bit resolution; heuristic pre-flight docstring)
- [ ] 6.7 Annotate every new keyword `@tier(1)`

## 7. Errors

- [ ] 7.1 Add exactly one new error class `HookExecutionError` (subclassing the FR59 Tier-1 base like `InvalidHookConfigError`) for zero-match and misuse failures; keep config-shape failures on `InvalidHookConfigError`

## 8. Fixtures and tests

- [ ] 8.1 Commit deterministic fixture hook scripts under `tests/fixtures/hooks/exec/` (`#!/usr/bin/env python3` or `python3 -c` style, not bash): exit-0, exit-2, JSON-emitting (`permissionDecision`), top-level `decision: "block"`, slow (timeout), and missing-binary variants
- [ ] 8.2 Unit tests for `Fire Hook Event`: matching hook executes and captures fields; zero-match raises `HookExecutionError`; multi-hook event reports a timed-out and a completed sibling; non-command hook recorded skipped; assertion on non-completed record fails loud
- [ ] 8.3 Unit tests for env sanitization: injected parent secret is absent from the hook env by default; `inherit_env=True` opt-in restores it
- [ ] 8.4 Run the dogfood fake-green precheck on any new `.robot` dogfood asset before flipping to review (`feedback_dogfood_fake_green_precheck`)

## 9. Docs and quality gates

- [ ] 9.1 Add the new keywords to the README keyword table and add a hooks-testing recipe with the prominent local-script-execution security note; smoke-execute recipe code blocks per `feedback_executable_doc_precheck`
- [ ] 9.2 Verify `DF-X-SY` carry-over markers (Windows `shell`, any caller-gap) are present in `docs/phase-1-5-carry-overs.md` per the carry-over catalog gate (Task N-1 UPSTREAM)
- [ ] 9.3 Green gates: `uv run pytest tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`, and the conventions suites (docstring style, tier annotation, libdoc render) which pick up the new keywords automatically
