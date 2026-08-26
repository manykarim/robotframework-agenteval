## Why

A live end-to-end run (2026-07-31) through `Agent.Run Agent codex` against the
installed `codex` 0.144.4 exposed that the **codex CLI adapter does not work** and
**fails silently**:

- `build_argv` produces `codex exec "<prompt>" --json`, but codex 0.144.4 exits
  **non-zero with empty stdout** and stderr `Not inside a trusted directory and
  --skip-git-repo-check was not specified.` Adding `--skip-git-repo-check` clears
  that gate but codex then **hangs** waiting for approval — `codex exec` is
  non-interactive only with an explicit execution mode.
- `parse_output` turned that failed run (exit code 1, empty stdout) into an
  **empty `AgentRunResult`** — no response, no tokens, and the stderr **discarded**
  — so the failure was invisible. The base spec already says a CLI adapter MUST
  fail loud "rather than returning an empty or fake-green result" for a missing
  binary; a failed *invocation* deserves the same.

codex was never live-confirmed (only `claude-code` was, at v0.2.0), and its parse
keys on `ASSUMPTION`-marked, version-sensitive field spellings — so this is a real,
untested gap, not a regression. `Agent.Run Agent` itself behaved correctly (it
returned exactly what the adapter produced); the defect is entirely in the codex
adapter.

## What Changes

- **Correct the codex non-interactive invocation** for its supported version.
  `codex exec --help` (0.144.4) confirms `--json`, `--skip-git-repo-check`, and an
  execution-mode flag are required. **Security-sensitive:** the mode that fully
  disables prompts (`--dangerously-bypass-approvals-and-sandbox`) is documented
  *"EXTREMELY DANGEROUS"*; the adapter SHALL NOT bake full bypass in as a silent
  default. It SHALL prefer a bounded `--sandbox` mode (e.g. read-only /
  workspace-write) sufficient for a measurement run, and make any dangerous bypass
  an explicit, documented opt-in.
- **Fail loud on a failed subprocess.** When a CLI run exits non-zero with no usable
  output, the adapter SHALL raise `AdapterError` naming the CLI + surfacing its
  stderr (never a silent-empty `AgentRunResult`), extending the existing
  "fail-loud, no fake-green" guarantee from binary-missing to invocation-failure.
- **Reconfirm codex's JSONL schema + version** against 0.144.4 output once it
  actually runs (event `type` values, the assistant-text key, cumulative-token
  handling), and update the pinned version range / drift warning accordingly.
- **A live E2E smoke** for codex (gated on the binary + a trusted dir) so a future
  codex version drift fails a test, not a user's run.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `coding-agent-cli-adapters`: ADD a requirement that a failed CLI subprocess
  (non-zero exit + no usable output) fails loud with the CLI's stderr; and ADD a
  requirement that the codex adapter drives `codex exec` non-interactively for its
  supported version without a silently-dangerous default execution mode.

## Impact

- **Code:** `src/AgentEval/_core/cli_adapters/codex.py` (`build_argv`, and
  `parse_output`'s failed-run handling) and possibly the `SubprocessCLIAdapter`
  base if the fail-loud check is shared across adapters.
- **Tests:** a `codex build_argv` unit test pinning the flags; a fail-loud unit
  test (nonzero exit + empty stdout → `AdapterError` with stderr); a codex JSONL
  parse test against captured 0.144.4 output; an env/binary-gated live smoke.
- **Docs:** `docs/running-against-a-real-model.md` codex row + the CLI recipe, if
  the invocation or its caveats change.
- **Out of scope (related, unconfirmed):** `gemini` (not installed here), `kilo`,
  and `copilot` are likewise only best-effort/unconfirmed — flagged for their own
  follow-up, not fixed here.
