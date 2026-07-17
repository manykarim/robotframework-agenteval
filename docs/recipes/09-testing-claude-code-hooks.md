# Recipe 4: Testing Claude Code hooks

**I want to** verify my Claude Code `settings.json` hooks fire on the right tool
calls and make the right block/allow decision — *before* I trust them in a live
agent session.

Hooks are deterministic local programs speaking a documented
stdin/stdout/exit-code protocol. So `HooksLibrary` can fire a synthetic event at
them and assert on the outcome with **zero API keys** — every keyword here is
Tier 1. There is no LLM or agent mode for hooks, and we won't pretend there is:
a deterministic script gets a deterministic test.

> **Security — these keywords execute your hook scripts locally.**
> `Hook.Fire Hook Event` runs each configured `type: "command"` hook as a
> subprocess with your privileges. The runner sanitizes the environment
> (default-deny allowlist, no parent-secret inheritance), enforces a hard
> timeout, and kills the process group on timeout — but this **limits leakage,
> it is not a sandbox**. Only fire configs whose commands you trust to run on
> your machine.

## The keywords

| Keyword | Role |
| --- | --- |
| `Hook.Get Config` | Parse `settings.json` into normalized per-event entries |
| `Hook.Get Hooks For Event` | Static "which hooks fire for tool X?" — no execution |
| `Hook.Command Should Exist` | Pre-flight: every hook command resolves on disk |
| `Hook.Validate Matcher Syntax` | A matcher compiles (Python `re`) and optionally matches a subject |
| `Hook.Fire Hook Event` | Synthesize the stdin payload and execute matching command hooks |
| `Hook.Decision Should Be` | Assert the normalized `block`/`allow`/`ask`/`none` decision |
| `Hook.Exit Code Should Be` | Assert the raw subprocess exit code |
| `Hook.Output Field Should Be` | Assert a dotted field in the parsed stdout JSON |

## The decision protocol in one table

| Hook behavior | Normalized decision |
| --- | --- |
| exit code `2` (stderr is the message; stdout JSON **ignored**) | `block` |
| exit `0` + `hookSpecificOutput.permissionDecision: "deny"` | `block` |
| exit `0` + `permissionDecision: "allow"` / `"ask"` | `allow` / `ask` |
| exit `0` + top-level `decision: "block"` | `block` |
| exit `0`, no decision JSON | `none` |

`Hook.Decision Should Be` accepts `deny` as an alias of `block`.

## The suite

```robotframework
*** Settings ***
Library    HooksLibrary

*** Variables ***
${SETTINGS}    ${CURDIR}/.claude/settings.json

*** Test Cases ***
Dangerous Bash Is Blocked
    [Documentation]    A PreToolUse hook must BLOCK `rm -rf` and ALLOW safe commands.
    ${config}=    Hook.Get Config    ${SETTINGS}

    # Static pre-flight — no scripts run yet.
    Hook.Command Should Exist    ${config}    event=PreToolUse
    ${firing}=    Hook.Get Hooks For Event    ${config}    PreToolUse    tool_name=Bash
    Length Should Be    ${firing}    1

    # Fire a dangerous command -> BLOCK (exit 2).
    ${blocked}=    Hook.Fire Hook Event    ${config}    PreToolUse
    ...    tool_name=Bash    tool_input=${{ {'command': 'rm -rf /'} }}
    Hook.Decision Should Be    ${blocked}    block
    Hook.Exit Code Should Be    ${blocked}    2

    # Fire a safe command -> no block.
    ${safe}=    Hook.Fire Hook Event    ${config}    PreToolUse
    ...    tool_name=Bash    tool_input=${{ {'command': 'ls -la'} }}
    Hook.Decision Should Be    ${safe}    none

Matcher Syntax Is Valid
    [Documentation]    Validate a regex matcher before relying on it (Python `re`, not JS RegExp).
    ${matches}=    Hook.Validate Matcher Syntax    mcp__.*    subject=mcp__github__create_issue
    Should Be True    ${matches}
```

## Notes

- `Hook.Get Hooks For Event` and `Hook.Fire Hook Event` share one matcher
  engine, so the static simulation and the live execution can never disagree
  about which hooks fire.
- Fire against a *programmatically built or filtered* config too — the keyword
  takes the parsed dict, not a path, so you can test one hook in isolation.
- A per-hook `timeout` in the config is honored; otherwise the keyword-level
  `default_timeout` (30 s) keeps a runaway hook from hanging the suite.
- Matchers use Python `re` semantics, not JavaScript RegExp — validate them
  with `Hook.Validate Matcher Syntax` before you rely on one.

## See also

- [Recipe 6](./08-ci-integration.md) — run this suite in CI (it needs no secrets).
- [`HooksLibrary` keyword reference](../keywords/HooksLibrary.html).
