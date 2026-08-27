## ADDED Requirements

### Requirement: Command existence checking recognizes inline interpreter scripts

When `Hook.Command Should Exist` checks that a hook command resolves, it SHALL
distinguish an interpreter's **inline source** from a **target-script path argument**
for the documented interpreters and forms: `node -e`/`--eval`/`-p`/`--print`, the
`deno eval` subcommand, `python -c`, `sh`/`bash`/`zsh -c` (including in an option
cluster such as `-ec`/`-lc`), `pwsh -c`/`-Command`/`-EncodedCommand` (case-insensitive),
`ruby -e`, and `perl -e`. When an inline-source mode is recognized, the inline program
text SHALL NOT be treated as a filesystem path — even when it contains a `/` — and the
check SHALL stop looking for a target script for that invocation, because the tokens
following inline source are arguments to the program, not script files. A hook that
resolves its interpreter on PATH and carries only inline source SHALL therefore pass.
For a command with no recognized inline-source mode, the check SHALL still detect and
existence-verify a target-script path argument (e.g. `bash ./scripts/foo.sh`,
`npx tsx ./script.ts`), so a genuinely missing script SHALL still fail loud, and unset
environment placeholders in a path argument SHALL still be surfaced. This behavior SHALL
apply to both the shell-string command form and the exec (command + args) form. The
requirement is scoped to the listed interpreters/forms; an unlisted interpreter's inline
mode is a known, bounded gap rather than a guaranteed case.

#### Scenario: An inline -e/-c hook whose source contains a slash passes

- **WHEN** a user checks a hook whose command is `node -e "...require('./data/x.json')..."`
  (or `python -c "...os.stat('/etc/hosts')..."`) and the interpreter resolves on PATH
- **THEN** `Hook.Command Should Exist` passes and does not report the inline source as a
  missing target script

#### Scenario: Arguments after inline source are not treated as scripts

- **WHEN** a user checks a hook whose command is `python -c 'f(sys.argv[1])' /tmp/not-created`
- **THEN** the check passes and does not report the trailing `/tmp/not-created` argument
  as a missing target script

#### Scenario: A real target-script argument is still verified

- **WHEN** a user checks a hook whose command is `bash ./scripts/foo.sh` and the script
  does not exist on disk
- **THEN** the check still fails, reporting that `./scripts/foo.sh` does not exist

#### Scenario: A resolvable script argument passes

- **WHEN** a user checks a hook whose command references an existing script via a real
  path (including through a set environment placeholder)
- **THEN** the check passes, and if the placeholder's variable is unset the check fails
  naming that variable rather than misreporting the source
