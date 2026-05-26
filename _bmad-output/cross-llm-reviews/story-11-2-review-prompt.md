# Story 11.2 — Copilot CLI Adapter — Cross-LLM Adversarial Review Prompt

## Context

Story 11.2 (Epic 11) ships `CopilotCLIAdapter(SubprocessAdapter)` — Phase-2
adapter for the `copilot` CLI binary. **Second per-story 3-tier cross-LLM
review** per `CLAUDE.md` (Epic 10 retro 2026-05-26 ratification).

**Key architectural wrinkle:** copilot writes events to disk
(`~/.copilot/session-state/{uuid}/events.jsonl`) — NOT to stdout. The adapter
overrides `SubprocessAdapter.run()` to do post-hoc events.jsonl reading
(D-9 in the drift check). This is the FIRST adapter in the project that
needs a post-hoc disk-trace read pattern.

Story 11.2 is also **the second use of `feedback_cross_story_upstream_lesson_propagation`** — it explicitly
applies the lessons from Story 11.1's review record (the UPSTREAM-seed
paragraph at the end of Story 11.1's Senior Developer Review).

## Story 11.1 lessons applied UPSTREAM

Story 11.1's review record listed these UPSTREAM-seed items for Story 11.2:

1. `Usage(reasoning_output_tokens=)` field populated if Copilot's events.jsonl carries an analogous field (D-8)
2. NO module-level `_VERSION_RE` dead-code constant (D-11)
3. Thread-safety invariant MUST be in the class docstring, not just inline comments (D-12)
4. Negative-path tests for the 3-condition diagnostic guard (AC-11.2.4)
5. Citation drift discipline: cite ADR-016 §Decision L33 (NOT §Alternatives L59) (D-6)

Verify each is correctly applied + flag any that are missing or mis-applied.

## What Story 11.2 ships

- **New source:** `src/AgentEval/coding_agent/copilot_cli.py` (~360 LoC) —
  `CopilotCLIAdapter(SubprocessAdapter)` with the 3 abstract hooks + `run()` override.
- **New unit test suite:** `tests/unit/coding_agent/test_copilot_cli.py` (32 tests).
- **New env-gated integration test:** `tests/integration/test_copilot_cli_live.py`.
- **3 new JSONL fixtures** under `tests/fixtures/copilot_cli/`.
- **Modified:** `pyproject.toml` (new `[copilot]` extra + `copilot-cli` entry-point),
  `tests/unit/coding_agent/conftest.py` (new `mock_copilot_version` autouse),
  `docs/contracts/stability-surface.md`, `docs/phase-1-5-carry-overs.md` (C75 + C76).

The diff is at `_bmad-output/cross-llm-reviews/story-11-2-diff.patch`.

## Verify against these source files

- `src/AgentEval/coding_agent/base.py` (SubprocessAdapter ABC)
- `src/AgentEval/coding_agent/codex_cli.py` (Story 11.1 precedent — same vendor, same family)
- `_bmad-output/implementation-artifacts/11-1-codex-cli-adapter.md` (Story 11.1 review record — UPSTREAM source)
- `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md` (Story 11.2 spec)
- `docs/contracts/stability-surface.md`
- `docs/phase-1-5-carry-overs.md`
- Sample empirical events.jsonl: `~/.copilot/session-state/391978f9-2453-418e-b611-4ab2bf354316/events.jsonl`

## Adversarial review checklist

### HIGH — correctness + regression risk

1. **`run()` override correctness (D-9 architectural decision)**:
   - Pre-spawn snapshot identifies "old" session dirs
   - Post-`proc.wait()`, find newest dir NOT in snapshot
   - Race-condition risk: what if copilot writes the events.jsonl AFTER the directory is created but BEFORE we read it? Check the file-existence guard + ordering invariants.
   - Race-condition risk: what if concurrent copilot sessions create dirs during the run window? The "newest dir not in pre_existing" might pick the wrong one.

2. **`_finalize` tool-call pairing**: tool calls are projected from
   `assistant.message.toolRequests[]` + matched by `toolCallId` to
   `tool.execution_complete` payloads. Trace this end-to-end. What
   happens if a `toolCallId` has multiple completions? What if the
   completion comes BEFORE the assistant.message that requested it
   (shouldn't, but verify the projection doesn't assume strict order)?

3. **D-8 reasoning_output_tokens**: the `Usage` dataclass extension
   from Story 11.1 kilo HIGH-1 was the prerequisite. Verify
   `_finalize` populates `reasoning_output_tokens` correctly if
   `assistant.message.reasoningTokens` is present. The empirical probe
   didn't show this field — is the test fixture realistic or
   synthetic-only?

4. **Citation drift**: every `ADR-XX` / `FR-XX` / `Story X.Y` / `DF-X.Y` / `L<N>` reference must resolve to a real current target. Per `feedback_citation_drift_first_class`, re-derive each from source.

5. **`Usage(input_tokens=0)` honesty**: Copilot's events.jsonl
   doesn't seem to expose input tokens. Is `input_tokens=0` a silent
   data-loss bug (like Story 11.1 kilo HIGH-1's `reasoning_output_tokens`
   drop) OR is it honestly Phase-1's surface limit? The C76 carry-over
   should document this — verify.

### MED — process discipline, hygiene

- `_last_mcp_servers` thread-safety (already documented from start per UPSTREAM lesson — verify)
- `mock_copilot_version` autouse fixture in conftest from start (verify)
- No `_VERSION_RE` dead-code constant (verify)
- Negative-path tests for nonzero-exit diagnostic (verify present)
- ADR-016 §Decision L33 citation (NOT L59 or A6) (verify)
- The session-state-dir-race invariant — is the thread-safety paragraph honest about it?

### LOW — wording, optional siblings

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.

CRITICAL: when finished, write the findings to:
`_bmad-output/cross-llm-reviews/story-11-2-{tool}-findings.md`
(replace `{tool}` with `copilot`, `codex`, or `kilo`).

If the file isn't written, the review is invalid.
