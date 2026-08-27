## 1. Introduce interpreter-aware inline-source handling

- [x] 1.1 Add an `interpreter` parameter to `_find_script_token` (`src/HooksLibrary/__init__.py`, def L592) and update its one caller `_resolve_command_problem` (def L539; call site L551) to pass the already-expanded interpreter value it already holds (`interp_expanded`, L545).
- [x] 1.2 Add a basename-normalization helper: strip directory prefix, strip a trailing version suffix (`python3.11` → `python`), lowercase.
- [x] 1.3 Recognize inline-source execution modes per interpreter: `node` → `{-e, --eval, -p, --print}`; `deno` → the `eval` **subcommand** (first non-flag token == `eval`); `python`/`python3` → `{-c}`; `sh`/`bash`/`zsh` → `-c` **including in an option cluster** (`-ec`, `-lc`); `pwsh`/`powershell` → `{-c, -Command, -EncodedCommand}` **case-insensitive**; `ruby`/`perl` → `{-e}`.
- [x] 1.4 When an inline-source mode is recognized, consume the flag + its source token and **STOP** target-script detection for that invocation — do NOT continue scanning later tokens (they are arguments to the inline program / `$0`+positionals for `sh -c`, not script paths).
- [x] 1.5 For commands with no recognized inline-source mode, keep the existing `/`-or-`os.sep` path test over `rest` (so real paths + unset-`${VAR}` surfacing still work). Apply the same interpreter-derivation + recognition to the exec form (`interpreter=command`, `rest=args`), not only the `shlex.split` shell form.

## 2. Tests (`tests/surfaces/hooks/test_hooks_library.py`)

- [x] 2.1 Unit-test token classification directly on `_find_script_token` (no interpreter installs needed) plus a `command_should_exist` node case with `_command_resolves` mocked: inline cases that must NOT flag — `node -e`, `node -p`, `python -c`, `sh -c`, `bash -c`, `bash -ec`, `pwsh -Command`, `deno eval`, `ruby -e`, `perl -e`, each with a `/` in the inline source.
- [x] 2.2 Exec-form + version-normalized cases covered (`/usr/bin/python3.11 -c ...` normalizes to `python`).
- [x] 2.3 **Post-source argument** cases (the stop-scanning correction): `python -c 'f(sys.argv[1])' /tmp/not-created` and `bash -c 'cmd' /tmp/nope.sh` must NOT flag the trailing token (both unit + `command_should_exist` integration).
- [x] 2.4 Regression: `bash ./scripts/foo.sh`, `npx tsx ./script.ts`, `deno run ./server.ts` detect the real path; missing real script still fails; `${CLAUDE_PLUGIN_ROOT}/x.mjs` resolves/surfaces (existing L449/L462 green).
- [x] 2.5 Real-binary cases use `sys.executable`; node case mocks `_command_resolves` so the matrix needs no `pwsh`/`ruby`/`zsh` on CI.

## 3. Docs + close out

- [x] 3.1 Note the behavior change in `CHANGELOG.md` (inline `-e`/`-c`/`-p`/`eval` hooks that previously false-failed now pass).
- [x] 3.2 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest). Robot dogfood is a separate live-LLM smoke, unaffected by this Tier-1 change.
- [x] 3.3 `openspec validate fix-hook-inline-script --strict`; archive after implementation lands + gates green.
