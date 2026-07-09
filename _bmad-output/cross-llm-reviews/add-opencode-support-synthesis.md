# Cross-LLM Review Synthesis — `add-opencode-support` (OpenCodeCLIAdapter)

**Date:** 2026-06-25
**Artifact under review:** `src/AgentEval/coding_agent/opencode_cli.py` + tests + fixtures (OpenSpec change `add-opencode-support`)

## Tier outcomes (3-tier chain per CLAUDE.md)

| Tier | Reviewer | Status | Output |
| --- | --- | --- | --- |
| 1 | Claude CLI (`--model opus`) | ✅ succeeded | 3 MED + 3 LOW (9.3 KB) |
| 2 | Codex CLI | ❌ degraded — hung on `Reading additional input from stdin...`, 0 bytes after several minutes; killed | none |
| 3 | kilo / minimax-M2.7 | ✅ succeeded | 1 HIGH(false) + 5 MED + 2 LOW (11 KB) |

Per CLAUDE.md: Tier 1 alone produced ≥2 MED (the ratify bar). Tier 2 degraded →
Tier 3 invoked per the fallback rule. The two successful reviewers produced
**orthogonal** finding classes (Claude: test-coverage + argv-safety semantics;
kilo: docstring/framing/schema-citation drift) — consistent with the
project's documented zero-overlap pattern.

## Findings applied (inline, v2)

### Tier 1 (Claude)
- **MED-1 (test-name vs assertion-body):** `test_finalize_nonzero_exit_with_text_does_not_emit_diagnostic` couldn't isolate the `not response_text` clause (its fixture also had a terminal). **Applied:** added `test_finalize_nonzero_exit_with_text_but_no_terminal_isolates_not_response_text_clause` (text + no terminal + nonzero exit).
- **MED-2 (tool-error coverage gap):** the `metadata.exit != 0` elif arm was never exercised (`tool_error.jsonl` fires the `status` arm first). **Applied:** added `test_finalize_completed_tool_with_nonzero_command_exit_marks_error` (status="completed", exit=1 → `error="exit_code=1"`).
- **MED-4 (argv injection):** prompt appended with no `--` sentinel → a leading-dash prompt parses as a flag. **Applied:** probe-verified `opencode run ... -- "<prompt>"` honors the sentinel and guards a leading-dash prompt; `_spawn` now inserts `--` before the prompt; added `test_spawn_inserts_end_of_options_sentinel_before_prompt`.
- **LOW-5 (stdin hygiene):** child inherited parent stdin. **Applied:** `stdin=subprocess.DEVNULL` + asserted in `test_spawn_uses_stderr_stdout_multiplex_and_pgroup`.
- **LOW-3 (single-emission tool assumption):** documented inline with a `DF-OPENCODE-S1 / C99` pointer (no behavior change; observer wiring is the upgrade path).
- **LOW-6 (drift window empty):** already documented + tested; no change.

### Tier 3 (kilo) — doc-accuracy fixes (all doc-only, no behavior change)
- **MED-4 (kilo):** fail-loud docstring said "no assistant text"; precise trigger is empty `response_text`. **Applied:** docstring corrected.
- **MED-5 (kilo):** `self.version` is the distribution version, not the binary version. **Applied:** clarifying comment at `record_active_run_metadata`.
- **LOW-1 (kilo):** event discriminator is the top-level `type`, not `part.type`. **Applied:** module-docstring schema section clarified.
- **LOW-2 (kilo):** `part.cost` can be absent/zero for free models. **Applied:** noted.
- **MED-1 (kilo, partial):** `callID` is a top-level sibling of `state`. **Applied:** clarified in module + `tool_payload` docstrings (the original wording was already correct but ambiguous).

## Findings rejected (with rationale, per `feedback_honest_framing`)

- **kilo HIGH-1 + MED-2 — FALSE POSITIVE (probe-verified).** kilo claimed `total` is not in `part.tokens` and proposed removing it from the docstring. Bash probe against `simple_prompt.jsonl` shows `part.tokens` keys = `['total','input','output','reasoning','cache']` (`total=17328`) and `cache` keys = `['write','read']`. The module docstring's `{total, input, output, reasoning, cache{write, read}}` is **accurate to the wire format**. Removing `total` would make the docstring *wrong*. **Resolution:** kept the accurate wire schema; added a clarifying note that `_finalize` extracts only the subset it folds into `Usage` (`total`/`cache.write` intentionally not used) — addresses kilo's underlying reader-confusion concern without introducing a falsehood.
- **kilo MED-3 — REJECTED (semantic + cross-adapter consistency).** kilo proposed downgrading `completeness` to `"truncated"` when any `tool_call.error` is set. `completeness` means "did the agent reach its terminal turn vs get cut off", not "did every tool succeed"; a tool erroring while the agent still reaches `reason=stop` is normal and is faithfully surfaced on `ToolCallTrace.error`. Conflating the two would also diverge from the codex/copilot sibling precedent (both gate on terminal+exit_code only). **Resolution:** rejection rationale documented inline at the completeness line.

## Net

- 3 new regression tests added (43 opencode unit tests total, was 40).
- All accepted code changes: `--` argv sentinel + `stdin=DEVNULL` in `_spawn` (functional hardening); the rest are doc-accuracy. No functional logic changed by the doc fixes.
- Gates after v2: `ruff` clean, `mypy` clean, opencode suite green; full-suite regression re-run clean.
