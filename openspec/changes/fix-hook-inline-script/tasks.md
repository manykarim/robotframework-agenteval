## 1. Introduce interpreter-aware inline-source handling

- [ ] 1.1 Add an `interpreter` parameter to `_find_script_token` (`src/HooksLibrary/__init__.py`, def L592) and update its one caller `_resolve_command_problem` (def L539; call site L551) to pass the already-expanded interpreter value it already holds (`interp_expanded`, L545).
- [ ] 1.2 Add a basename-normalization helper: strip directory prefix, strip a trailing version suffix (`python3.11` → `python`), lowercase.
- [ ] 1.3 Recognize inline-source execution modes per interpreter: `node` → `{-e, --eval, -p, --print}`; `deno` → the `eval` **subcommand** (first non-flag token == `eval`); `python`/`python3` → `{-c}`; `sh`/`bash`/`zsh` → `-c` **including in an option cluster** (`-ec`, `-lc` — a single-`-` token with no `=` that contains `c`); `pwsh`/`powershell` → `{-c, -Command, -EncodedCommand}` **case-insensitive**; `ruby`/`perl` → `{-e}`.
- [ ] 1.4 When an inline-source mode is recognized, consume the flag + its source token and **STOP** target-script detection for that invocation — do NOT continue scanning later tokens (they are arguments to the inline program / `$0`+positionals for `sh -c`, not script paths).
- [ ] 1.5 For commands with no recognized inline-source mode, keep the existing `/`-or-`os.sep` path test over `rest` (so real paths + unset-`${VAR}` surfacing still work). Apply the same interpreter-derivation + recognition to the exec form (`interpreter=command`, `rest=args`), not only the `shlex.split` shell form.

## 2. Tests (`tests/surfaces/hooks/test_hooks_library.py`, ~L399-470)

- [ ] 2.1 Unit-test token classification with `_command_resolves`/`shutil.which` **mocked** (so the matrix does not require `pwsh`/`ruby`/`zsh` on the CI image): inline cases that must NOT flag — `node -e`, `node -p`, `python -c`, `sh -c`, `bash -c`, `bash -ec`, `pwsh -Command`, `deno eval`, `ruby -e`, `perl -e`, each with a `/` in the inline source.
- [ ] 2.2 Exec-form case: `command=node, args=['-e', "<source with />"]` must NOT flag.
- [ ] 2.3 **Post-source argument** cases (the stop-scanning correction): `python -c 'f(sys.argv[1])' /tmp/not-created` and `bash -c 'cmd' /tmp/nope.sh` must NOT flag the trailing token.
- [ ] 2.4 Regression, using `sys.executable`-style known-present binaries where a real path is needed (must STILL detect/verify): `bash ./scripts/foo.sh` and `npx tsx ./script.ts` detect the real path; a missing real script still fails with "does not exist"; `node "${CLAUDE_PLUGIN_ROOT}/x.mjs"` resolves when set and still names `$CLAUDE_PLUGIN_ROOT` when unset (keep L449/L462 green).
- [ ] 2.5 Version-normalization case: `/usr/bin/python3.11 -c "...import os.path..."` normalizes to `python` and is not flagged. Gate any test that needs a real non-portable binary (`pwsh`, `zsh`) behind availability, keeping one portable `sys.executable` integration case.

## 3. Docs + close out

- [ ] 3.1 Note the behavior change in `CHANGELOG.md` (inline `-e`/`-c`/`-p`/`eval` hooks that previously false-failed now pass).
- [ ] 3.2 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest / robot).
- [ ] 3.3 `openspec validate fix-hook-inline-script --strict`; archive after implementation lands + gates green.
