# Story 11.1 — Codex CLI Adapter — Cross-LLM Adversarial Review Prompt

## Context

Story 11.1 (Epic 11) ships `CodexCLIAdapter(SubprocessAdapter)` — a Phase-2
subprocess-based adapter for the OpenAI `codex` CLI binary. **First use of the
project's newly-ratified 3-tier cross-LLM review chain** (per `CLAUDE.md`,
ratified Epic 10 retro 2026-05-26):

- **Tier 1: Copilot CLI** (`copilot -p --model claude-sonnet-4.6 --allow-all-tools "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- **Tier 3: kilo/minimax-M2.7** (`~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "<prompt>"`)

Each reviewer runs INDEPENDENTLY. Coverage is multiplicative, not redundant.

## What Story 11.1 ships

- **New source:** `src/AgentEval/coding_agent/codex_cli.py` (~340 LoC) —
  `CodexCLIAdapter(SubprocessAdapter)` with the 3 abstract hooks (`_spawn`,
  `_parse_event`, `_finalize`) + `CodexEvent` frozen dataclass.
- **New unit test suite:** `tests/unit/coding_agent/test_codex_cli.py` (33 tests).
- **New env-gated integration test:** `tests/integration/test_codex_cli_live.py`.
- **4 new JSONL fixtures** under `tests/fixtures/codex_cli/`.
- **Modified:** `pyproject.toml` (new `[codex]` extra + `codex-cli` entry-point),
  `tests/unit/coding_agent/conftest.py` (new `mock_codex_version` autouse fixture),
  `docs/contracts/stability-surface.md`, `docs/phase-1-5-carry-overs.md` (C73 + C74).

The diff is at `_bmad-output/cross-llm-reviews/story-11-1-diff.patch`.

## What's load-bearing — read the story spec first

The story spec at `_bmad-output/implementation-artifacts/11-1-codex-cli-adapter.md`
documents **9 cross-story UPSTREAM lessons** (D-1 through D-11 in the drift
check) folded into the AC text from Stories 4.2 + 10.1 + 10.2. This is the
**FIRST use of `feedback_cross_story_upstream_lesson_propagation`** (Epic 10
retro NEW norm). Your job is to verify whether each lesson is correctly applied:

| D-# | Lesson source | What to verify |
| --- | --- | --- |
| D-1 | Story 4.2 HIGH-A (prompt-never-fed) | Prompt passed as positional argv to `codex exec`, NOT stdin |
| D-2 | Story 4.2 HIGH-B (stderr pipe deadlock) | `stderr=subprocess.STDOUT` multiplex |
| D-3 | Story 4.2 MED-3 (silent nonzero exit) | `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` diagnostic emitted |
| D-4 | Story 4.2 Edge-cases MED-1 (autouse fixture hoist) | `mock_codex_version` lives in `tests/unit/coding_agent/conftest.py` from the start |
| D-5 | Story 4.2 Auditor HIGH-1 (ADR drift) | Citations are ADR-002 + ADR-010, NOT ADR-005 |
| D-6 | Story 10.1 kilo MED-2 (ADR-A6 renumbering) | Citations are ADR-016 L59, NOT ADR-A6 L384 |
| D-7 | Stories 10.1 + 10.2 HIGH-2 (mcp_coverage optimism) | Non-empty mcp_servers → `external_mixed`, NOT `hosted_in_process` |
| D-9 | Empirical probe | `cost_usd=0.0` placeholder documented; DF-11.1-S2 carry-over present |
| D-10 | Empirical probe | `codex-cli ` prefix in `--version` output handled correctly by base `_SEMVER_RE.search()` |

## Source files to verify against

- `src/AgentEval/coding_agent/base.py` (SubprocessAdapter ABC; `_assert_binary_version` helper)
- `src/AgentEval/coding_agent/claude_code_cli.py` (Story 4.2 reference precedent)
- `_bmad-output/implementation-artifacts/4-2-claude-code-cli-adapter.md` (Story 4.2 review record — the source of UPSTREAM lessons)
- `_bmad-output/implementation-artifacts/10-1-claude-agent-sdk-adapter.md` + `10-2-openai-agents-sdk-adapter.md` (Epic 10 review records — also UPSTREAM source)
- `docs/contracts/stability-surface.md` (where the new adapter is registered)
- `docs/phase-1-5-carry-overs.md` (C73 + C74 entries)
- `pyproject.toml` (entry-point + extra)
- `/tmp/codex_probe.jsonl` + `/tmp/codex_tool_probe.jsonl` (empirical JSONL captures from the codex binary)

## Adversarial review checklist

### HIGH — correctness, citation drift, regression risk

1. **`_finalize` correctness**: trace the codex JSONL → `AgentRunResult` projection
   end-to-end. Verify `response_text`, `tool_calls`, `usage`, `cost_usd`,
   `completeness`, `mcp_coverage`, `latency_seconds` all derive from the
   captured event stream correctly per the empirical schema at
   `/tmp/codex_probe.jsonl` + `/tmp/codex_tool_probe.jsonl`.

2. **D-1 prompt-delivery wiring (Story 4.2 HIGH-A inheritance)**: verify
   `_spawn` passes the prompt as the LAST positional argv element. Probe
   `test_spawn_passes_prompt_as_positional_argv` to confirm.

3. **D-2 stderr multiplex (Story 4.2 HIGH-B inheritance)**: verify
   `_spawn` sets `stderr=subprocess.STDOUT`. Probe
   `test_spawn_uses_stderr_stdout_multiplex` to confirm.

4. **D-3 nonzero-exit diagnostic (Story 4.2 MED-3 inheritance)**: verify
   `_finalize` emits `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]` exactly
   when `exit_code != 0` AND no terminal event AND no agent_message text.
   Probe `test_finalize_nonzero_exit_with_no_message_emits_diagnostic`.

5. **D-7 mcp_coverage safer-default (Epic 10 inheritance)**: verify
   non-empty `mcp_servers` returns `external_mixed` per ADR-016 L59.
   Probe `test_run_with_unverified_mcp_marks_external_mixed`.

6. **Citation drift**: every `ADR-XX`, `FR-XX`, `Story X.Y`, `DF-X.Y`,
   `L<N>` line-range, or filename in the adapter docstring + story spec
   must point to a real, current target. **kilo+codex are PARTICULARLY
   GOOD at this class** — re-derive each cited fact from source.

7. **Test-name vs assertion-body match** (`feedback_test_name_assertion_match`):
   every test name's promise MUST be delivered by its assertion body.

8. **Empirical-probe accuracy**: the 4 fixtures should match the documented
   schema. Re-run `codex exec --json "Say hi in one word, no thinking."`
   if possible to verify the schema hasn't drifted since story-authoring.

### MED — process discipline, hygiene

- **`_VERSION_RE` unused-variable check**: the constant is declared at module
  scope but the actual call uses the base helper's default. Either remove
  the constant OR cite where it would be used (future override hook).
- **`_last_mcp_servers` race**: the stash-on-instance pattern works for
  Phase-1 single-threaded, but flag if there's a concurrency invariant
  the adapter should advertise OR a cleaner pattern that doesn't use
  instance state.
- **Cost surface**: Codex events carry NO `cost_usd`; adapter ships `0.0`.
  Verify DF-11.1-S2 catalog row covers this.
- **MCPLifecycleManager interaction**: this is a SubprocessAdapter; does
  the codex subprocess respect the `MCPLifecycleManager` cleanup on SIGTERM?

### LOW — wording, optional siblings

- Style, ordering, sibling cross-refs.

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.

CRITICAL: when finished, write the findings to:
`_bmad-output/cross-llm-reviews/story-11-1-{tool}-findings.md`
(replace `{tool}` with `copilot`, `codex`, or `kilo` depending on which reviewer you are).

If the file isn't written, the review is invalid.
