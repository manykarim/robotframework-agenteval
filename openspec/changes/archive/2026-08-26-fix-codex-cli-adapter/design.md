## Context

Live e2e (2026-07-31) through `Agent.Run Agent codex` against installed codex
0.144.4, in a throwaway (non-git) cwd:

- **Symptom:** `AgentRunResult` came back **empty** — no response, 0 tokens,
  `metric_source=none` — with no exception raised.
- **Raw capture:** `codex exec "<prompt>" --json` exited **returncode 1** with
  **empty stdout** and stderr:
  `Reading additional input from stdin...` + `Not inside a trusted directory and
  --skip-git-repo-check was not specified.`
- **With `--skip-git-repo-check`** (in a trusted git dir) codex got past that gate
  but then **hung >220s** — `codex exec` waits for approval without an execution-mode
  flag.
- **`codex exec --help` (0.144.4)** confirms the shape: positional `[PROMPT]` (or
  stdin), `--json` (JSONL to stdout), `--skip-git-repo-check`, `-C/--cd <DIR>`,
  `-s/--sandbox <mode>`, and `--dangerously-bypass-approvals-and-sandbox`
  (documented *"EXTREMELY DANGEROUS … solely for … externally sandboxed"*).

Two independent defects, both in the codex adapter — **not** in `Agent.Run Agent`,
which faithfully returned what the adapter produced:

1. `build_argv` (`codex.py`) omits the flags codex 0.144.4 needs to run
   non-interactively.
2. `parse_output` maps a returncode-1 / empty-stdout run to an empty
   `AgentRunResult` (it sets `completeness="partial"` but discards stderr and returns
   no error) — a silent failure.

codex was never live-confirmed (only claude-code was), and its extractors key on
`ASSUMPTION`-marked version-sensitive JSONL field spellings.

## Goals / Non-Goals

**Goals:**

- codex runs non-interactively on its supported version and returns a real result.
- A failed CLI invocation fails **loud** (raises with stderr), never silent-empty.
- codex's JSONL parse + pinned version are reconfirmed against 0.144.4, with a live
  smoke guarding future drift.

**Non-Goals:**

- No change to `Agent.Run Agent` / the classifier / other adapters' behavior — the
  run keyword is correct; this is a codex-adapter fix.
- No fix for `gemini` (not installed here), `kilo`, or `copilot` — likewise
  unconfirmed, flagged for their own follow-up.
- Do **not** make a fully-approval-and-sandbox-bypassing codex mode the default.

## Decisions

### D1 — codex non-interactive invocation (security-aware)

`build_argv` becomes, for the supported codex version, roughly:
`codex exec "<prompt>" --json --skip-git-repo-check -s <bounded-mode>` — where the
bounded `--sandbox` mode is the least-privilege setting that still lets codex
complete a measurement run without an interactive approval prompt. The exact mode is
determined empirically at implementation time (candidates: `read-only`,
`workspace-write`), because the goal is "runs non-interactively" *without* the
extremely-dangerous full bypass.

- **The dangerous full bypass is opt-in.** `--dangerously-bypass-approvals-and-sandbox`
  (which the project's own `CLAUDE.md` uses for codex *review*) executes shell
  commands with no sandbox — inappropriate as a library default that a user's suite
  would run unknowingly. Expose it only via an explicit, documented option
  (constructor/run kwarg), defaulting off.
- Open question: whether a bounded sandbox mode alone suffices for codex `exec` to
  finish non-interactively for tool-using prompts, or whether an approval policy
  config (`-c`) is also needed. Resolve during apply against the real CLI.

### D2 — fail loud on a failed invocation (shared base or codex)

Currently only a missing binary fails loud. Add: when `exit_code != 0` **and** the
parse yields nothing usable (no response text, no tool calls, no usable transcript),
raise `AdapterError(f"{slug} CLI exited {code}: {stderr[:N]}")` from `parse_output`
(or a shared post-parse check in the base `run`). A partial-but-usable run
(parseable output present) is still returned, marked not-`complete`, so recoverable
data is not thrown away. Placing the check in the base `SubprocessCLIAdapter` fixes
every adapter uniformly; scoping it to codex is the minimal alternative.

### D3 — reconfirm schema + version + live smoke

Once codex runs, capture its real 0.144.4 JSONL and verify `_ASSISTANT_ITEM_TYPES`
and the assistant-text / usage extractors still match; update them if drifted.
Reconcile the pinned version range so 0.144.4 is in-range (or intentionally warns).
Add an env/binary-gated live smoke (per the existing "each adapter ships a live E2E
smoke" requirement) so the next codex drift fails a test, not a user run.

## Risks / Trade-offs

- **A bounded sandbox mode may still not run non-interactively** for tool-using
  prompts → Mitigation: determine empirically; if a safe non-interactive mode does
  not exist, document codex as opt-in-dangerous-only and mark its fidelity/ceiling
  accordingly rather than shipping a false default.
- **Fail-loud in the base could change other adapters' behavior** on their own
  edge cases → Mitigation: gate strictly on "nonzero exit AND nothing usable
  parsed", and cover each adapter's happy path in tests before/after.
- **codex costs + slowness** make the live smoke expensive → Mitigation: env-gated,
  trivial prompt, short timeout; not on per-push CI.

## Migration Plan

Additive/behavioral-fix — no API change. codex starts working where it silently
failed; a genuinely failed CLI run now raises instead of returning empty (arguably a
fix, but note it in the CHANGELOG as a behavior change for any suite that depended on
the empty result). Rollback is a revert.

## Open Questions

- The exact least-privilege codex `--sandbox`/approval configuration that runs
  non-interactively (D1) — pinned at implementation time against codex 0.144.4.
- Whether fail-loud lives in the base (all adapters) or only codex (D2) — lean base,
  decide after checking the other adapters' failed-run behavior.
