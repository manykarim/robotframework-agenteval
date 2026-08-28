## Context

`Hook.Command Should Exist` resolves the interpreter on PATH, then looks for a
"target script" argument to existence-check on disk. Confirmed against
`src/HooksLibrary/__init__.py`:

- `command_should_exist` (def L466) splits the command into `interpreter` + `rest`:
  exec form → `interpreter=command`, `rest=args`; shell form → `split =
  shlex.split(command)` (L522), `interpreter=split[0]`, `rest=split[1:]`.
- `_find_script_token(rest, project_dir)` (L592-606) skips `-`-prefixed tokens, then
  returns the first `rest` token whose env-expanded value contains `/` or `os.sep`.
- `_resolve_command_problem` (def L539) calls it at L551 and, if a token is returned,
  fails when `Path(script_expanded).exists()` is False (message at L560).

The bug: the token *following* an inline-source flag (`node -e <src>`, `python -c
<src>`) is not skipped, so inline program text containing a slash is returned as a
"script." There is no interpreter special-casing anywhere (grep across
`_parser.py`/`_runner.py` finds none), so `python -c` misfires identically to
`node -e`; the fix must *introduce* interpreter awareness. `_runner.py::run_command_hook`
runs bare command strings through the shell, so the shell handles `-e`/`-c` there — no
other site reproduces the buggy rule; the fix is confined to `__init__.py`.

## Goals / Non-Goals

**Goals:**

- Inline-source hooks (`-e`/`-c`/`-Command`, `deno eval`, `node -p`) are not
  misreported as a missing target script.
- A genuine missing/real script argument after a *script-consuming* interpreter is
  still detected and existence-checked (fail-loud preserved).
- The fix is localized to `__init__.py` and changes no keyword signature.

**Non-Goals:**

- An interpreter-agnostic path heuristic (rejected — see D1).
- Full general execution-mode modeling for every possible interpreter (over-scope) —
  the table covers the documented interpreters and the common forms; the SHALL is
  scoped to those, not to "all equivalents."

## Decisions

### D1 — Per-interpreter inline-source recognition, then STOP scanning (chosen)

`_find_script_token` gains an `interpreter` parameter. It normalizes the interpreter
basename (strip directory prefix, strip a trailing version suffix so `python3.11` →
`python`, lowercase) and recognizes **inline-source execution modes**:

| interpreter            | inline-source form(s)                                   |
| ---------------------- | ------------------------------------------------------- |
| `node`                 | `-e`, `--eval`, `-p`, `--print`                          |
| `deno`                 | the `eval` **subcommand** (`deno eval CODE`)            |
| `python`, `python3`    | `-c`                                                    |
| `sh`, `bash`, `zsh`    | `-c` (including inside an option **cluster**, e.g. `-ec`, `-lc`) |
| `pwsh`, `powershell`   | `-c`, `-Command`, `-EncodedCommand` (case-insensitive)  |
| `ruby`, `perl`         | `-e`                                                    |

When an inline-source mode is recognized, the scanner consumes the flag and its source
token and then **STOPS** target-script detection for that whole invocation — it does
**not** continue scanning later tokens. This is the load-bearing correction: after
`python -c CODE arg1 arg2`, `node -e CODE arg`, or `bash -c CODE $0 $1`, the remaining
tokens are **arguments to the inline program** (or `$0`/positionals for `sh -c`), not
alternate script files. Continuing to scan them would re-introduce the same false
positive for `python -c 'f(sys.argv[1])' /tmp/not-created-yet`.

For interpreters/commands with **no** recognized inline-source mode, the existing path
test (`/` or `os.sep` after env expansion) runs over `rest` unchanged, so a real script
argument (`bash ./scripts/foo.sh`, `npx tsx ./script.ts`, `node "${CLAUDE_PLUGIN_ROOT}/x.mjs"`)
is still detected and existence-checked, and unset-`${VAR}` surfacing still fires.

Clustered short flags (`sh -ec CODE`) are handled by checking whether a token that
starts with a single `-` and contains no `=` includes a command flag character (`c` for
the shells); PowerShell parameter names are matched case-folded. The `deno eval`
subcommand is matched positionally (first non-flag token == `eval`), not as a flag.

**Why the table, not a heuristic.** The alternative — "only treat a token as a path if
it has no whitespace/shell-metacharacters and looks path-like" — is interpreter-free but
introduces a **false negative**: a legitimate path with a space (`node "/my dir/x.mjs"`)
would be silently skipped, so the existence check no-ops. This keyword exists precisely
to fail loud before a hook silently no-ops; a false negative is strictly worse than the
current false positive. The table only suppresses detection where an inline-source mode
is *known* present, preserving detection of every real path shape. Its cost is a small,
well-known table (chosen over an unknown-interpreter heuristic backstop, which is
deferred).

### D2 — Reuse the already-expanded interpreter

`_resolve_command_problem` already env-expands the interpreter (`interp_expanded` at
L545). Pass that value in and derive the basename from it, so
`${CLAUDE_PLUGIN_ROOT}/bin/node -e ...` still resolves the interpreter correctly.

### D3 — Spec anchoring, scoped honestly

`hook-testing/spec.md` is silent on the target-script-detection algorithm (it does not
encode the buggy rule), so a code-only fix is valid, but the new guarantee is added as a
scenario-backed requirement. The requirement text is **scoped to the documented
interpreters/forms** above — it does not claim to cover "all equivalents," so an
unlisted interpreter's inline mode remains a known, bounded gap rather than an implied
guarantee.

## Risks / Trade-offs

- **Result change on a shipped keyword:** an inline hook that false-failed now passes.
  Intended; note in `CHANGELOG.md`.
- **Table incompleteness:** an unlisted interpreter/mode can still misfire (D1/D3 scope).
  Mitigation: cover the documented interpreters; the table is trivially extensible; the
  SHALL is scoped so this is honest, not a broken promise.
- **Over-suppression:** if a mode were wrongly recognized, a genuine missing script would
  be skipped. Mitigation: recognize only well-known inline-source modes; stop-scanning is
  correct precisely *because* post-source tokens are never script paths.

## Migration Plan

Additive/behavioral-fix, no API change (`_find_script_token` is private). Inline
`-e`/`-c`/`-p`/`eval` hooks that false-failed now pass; script-consuming invocations are
unchanged. Rollback is a revert.

## Open Questions

- **OQ1:** Should an unknown-interpreter conservative backstop (skip a token that is
  clearly inline code — embedded whitespace + shell metacharacters) be added as a
  *supplement* (never sole rule) for interpreters outside the table? Deferred; the table
  + scoped SHALL is the v1.
- **OQ2:** `sh -c '<src>' <arg0> <realscript.sh>` — POSIX passes trailing args as
  `$0`/`$1`; with stop-scanning we intentionally do **not** existence-check a positional
  after the source (it is `$0`, not a script the shell runs as a file). Confirmed as the
  desired behavior; noted here so it is explicit.
