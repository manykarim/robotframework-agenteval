## Why

`Hook.Command Should Exist` false-fails on a valid, working hook whose command is an
inline interpreter script (`node -e "..."`, `python -c "..."`, `sh -c "..."`, ...)
whenever the inline source text contains a `/` — which any inline script that touches
the filesystem (`require('path')`, a relative-path literal, `os.stat('/etc/...')`)
essentially always does.

Root cause confirmed in `src/HooksLibrary/__init__.py`. `_find_script_token`
(L592-606) skips tokens starting with `-` (treating them as flags) and then returns
the **first remaining token containing `/`** as the hook's "target script":

```
600  for token in rest:
601      if token.startswith("-"):
602          continue
603      expanded, _ = cls._expand_env_vars(token, project_dir)
604      if "/" in expanded or os.sep in expanded:
605          return token
606  return None
```

For `node -e "<source>"`, `shlex.split` yields `["-e", "<source>"]`; `-e` is skipped
as a flag, and `<source>` — the inline program, not a path — is returned because it
contains `/`. The caller `_resolve_command_problem` (defined L539; it calls
`_find_script_token` at L551 and existence-checks the returned token at L560) then
asserts the entire inline script string must exist on disk and fails.
The interpreter itself resolves fine on PATH; only the bogus target-script check
fails.

Inline `-e`/`-c` hooks are a common, documented Claude Code hook pattern (one-liners
that avoid shipping a separate script file). This check is otherwise exactly right —
verifying a hook won't silently no-op before a live session depends on it is squarely
this project's philosophy — it just misfires on the single most common way to write a
short hook.

**Refuted:** the issue speculated `python -c` "may currently be special-cased as
consuming source." It is **not** — `_find_script_token` is fully interpreter-agnostic
(grep across `_parser.py`/`_runner.py` finds no interpreter handling); `python -c`
misfires identically to `node -e`. The fix must therefore *introduce* interpreter
awareness, not adjust an existing special case.

## What Changes

- **Teach `_find_script_token` which interpreter modes carry inline source, not a
  path.** Pass the resolved `interpreter` into `_find_script_token`, normalize its
  basename (strip path prefix + version suffix: `/usr/bin/python3.11` → `python`), and
  recognize the documented inline-source modes: `node -e`/`--eval`/`-p`/`--print`, the
  `deno eval` subcommand, `python -c`, `sh`/`bash`/`zsh -c` (including in an option
  cluster like `-ec`/`-lc`), `pwsh -c`/`-Command`/`-EncodedCommand` (case-insensitive),
  `ruby -e`, `perl -e`. When an inline-source mode is recognized, consume the flag + its
  source token and **stop** target-script detection for that invocation — the remaining
  tokens are arguments to the inline program (or `$0`/positionals for `sh -c`), never
  script files, so scanning them would re-create the false positive. This applies to
  both the shell form (`shlex.split`) and the exec form (`command` + `args`).
- **Preserve genuine target-script detection.** A real path argument after a real
  interpreter (`bash ./scripts/foo.sh`, `npx tsx ./script.ts`,
  `node "${CLAUDE_PLUGIN_ROOT}/x.mjs"`) is still detected and existence-checked; a
  genuinely missing script still fails loud; unset-`${VAR}` surfacing is unchanged.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `hook-testing`: ADD a requirement that the hook-command existence check recognizes
  inline interpreter scripts (`-e`/`-c`/`-p`/`-Command`/`deno eval` source) for the
  documented interpreters and does not misreport them — or their trailing arguments —
  as a missing target script, while still detecting a genuine missing script argument
  after a script-consuming interpreter.

## Impact

- **Code:** `src/HooksLibrary/__init__.py` — `_find_script_token` (add an
  `interpreter` parameter + the inline-source-flag table) and its caller
  `_resolve_command_problem` (pass the already-expanded interpreter). Localized;
  `_find_script_token` is a private classmethod with no external callers.
- **Tests:** `tests/surfaces/hooks/test_hooks_library.py` (the `command_should_exist`
  block, L399-470) — add inline-mode cases per interpreter that must **pass** (with
  `_command_resolves`/`shutil.which` **mocked** so the matrix doesn't require
  `pwsh`/`ruby`/`zsh` on CI), a post-source-argument case
  (`python -c 'f(sys.argv[1])' /tmp/nope`), and keep the existing missing-script /
  plugin-root cases green using portable binaries.
- **Docs:** `CHANGELOG.md` — note the behavior change (inline `-e`/`-c`/`-p`/`eval`
  hooks that previously false-failed now pass).
- **Out of scope:** an interpreter-agnostic path heuristic (rejected — a legitimate
  path containing a space would silently skip the existence check, a false negative
  that defeats this keyword's fail-loud purpose); a conservative unknown-interpreter
  backstop (deferred, design OQ1); and an interpreter outside the documented table
  (bounded known gap, per the scoped SHALL).
