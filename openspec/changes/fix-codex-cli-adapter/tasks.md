## 1. Determine the correct codex invocation (empirical)

- [x] 1.1 Against installed codex 0.144.4 in a trusted git dir, find the least-privilege `codex exec` flags that run non-interactively and emit JSONL: start from `--json --skip-git-repo-check -s <mode>` (try `read-only`, then `workspace-write`); capture a real successful run's stdout for the parse work. Record whether a bounded sandbox mode suffices or an approval-policy `-c` is also needed.
- [x] 1.2 Capture the real 0.144.4 JSONL event `type` values, the assistant-text key, and the usage/cost keys, to validate/repair the extractors.

## 2. Fix `build_argv` (`src/AgentEval/_core/cli_adapters/codex.py`)

- [x] 2.1 Update `build_argv` to the invocation from 1.1 (adds `--skip-git-repo-check` + a bounded execution mode). Do NOT default-enable `--dangerously-bypass-approvals-and-sandbox`.
- [x] 2.2 Add an explicit, documented opt-in (constructor/run kwarg, default off) for the dangerous full-bypass mode, for users who run in an externally-sandboxed environment.

## 3. Fail loud on a failed invocation

- [x] 3.1 When `exit_code != 0` AND the parse yields nothing usable (no response text, no tool calls, no usable transcript), raise `AdapterError` naming the CLI + surfacing (truncated) stderr — instead of an empty `AgentRunResult`. Prefer placing the check in the `SubprocessCLIAdapter` base so every adapter is covered; else scope to codex.
- [x] 3.2 Preserve a partial-but-usable run: if parseable output/transcript is present, still return a result marked not-`complete` (do not raise).

## 4. Reconcile schema + version

- [x] 4.1 Update codex's `_ASSISTANT_ITEM_TYPES` / text + usage extractors if the 1.2 capture shows drift; keep the VALIDATION-CEILING note accurate.
- [x] 4.2 Reconcile the codex pinned version range so 0.144.4 is in-range (or intentionally raises `AdapterVersionDriftWarning`).

## 5. Tests

- [x] 5.1 `codex build_argv` unit test pinning the flags (incl. `--skip-git-repo-check`, the bounded mode, and NO dangerous bypass by default; bypass appears only when the opt-in is set).
- [x] 5.2 Fail-loud unit test: a fake CLI run with `exit_code=1` + empty stdout → `AdapterError` whose message includes the stderr; and a partial-but-usable run → returned, marked not-`complete`.
- [x] 5.3 codex JSONL parse test over the captured 0.144.4 stdout (from 1.2) → populated response/usage.
- [x] 5.4 Env/binary-gated live smoke: `Agent.Run Agent codex "..."` (or the adapter directly) returns a non-empty `AgentRunResult` when codex is installed + a trusted dir + creds; skips cleanly otherwise.

## 6. Docs + close out

- [x] 6.1 Update the codex row/caveats in `docs/running-against-a-real-model.md` (and the CLI recipe) if the invocation or its opt-in caveat changed; note the behavior change (failed run now raises) in `CHANGELOG.md`.
- [x] 6.2 Full local gate (ruff/format/mypy/license/contract/doc-count/doc-render/keyword-examples/pytest/robot).
- [ ] 6.3 `openspec validate fix-codex-cli-adapter --strict`; archive after implementation lands + gates green + codex live-confirmed.
