# Story 11.3 — AdapterVersionDriftWarning Fully Wired — Cross-LLM Adversarial Review Prompt

## Context

Story 11.3 (Epic 11) wires PRD FR60 `AdapterVersionDriftWarning` across
all 3 Tier-1 CLI adapters (`claude_code_cli`, `codex_cli`, `copilot_cli`)
via a new shared helper module `src/AgentEval/_kernel/version_drift.py`.

**Third per-story 3-tier cross-LLM review** per `CLAUDE.md` (Epic 10
retro 2026-05-26 ratification) + **3rd use of
`feedback_cross_story_upstream_lesson_propagation`** (graduates to
confirmed structurally-trustworthy pattern at N=3).

## What Story 11.3 ships

- **New helper module:** `src/AgentEval/_kernel/version_drift.py` —
  `emit_adapter_version_drift_warning_if_applicable()` + `parse_binary_version()`
  + `reset_session_drift_dedupe()` (test helper) + re-exports
  `AdapterVersionDriftWarning` from `mcp/observer.py` (D-6 decision:
  re-use Story 5.2's class).
- **3 adapter integrations** (claude_code_cli + codex_cli + copilot_cli):
  add `_TESTED_UP_TO` constant + call the helper in `__init__` after
  `_assert_binary_version()` passes.
- **New unit test suite:** `tests/unit/kernel/test_version_drift.py` (16 tests).
- **`tests/unit/coding_agent/conftest.py`:** new `_reset_version_drift_dedupe`
  autouse fixture so dedupe state doesn't bleed across adapter tests.
- **`docs/contracts/stability-surface.md`:** new row at `provisional` for
  the helper.

The diff is at `_bmad-output/cross-llm-reviews/story-11-3-diff.patch`.

## What's load-bearing — the key UPSTREAM lessons applied

Stories 11.1 + 11.2 review records yielded these UPSTREAM-seed items
for Story 11.3 (per D-1 through D-10 in the spec drift check). Verify
each is correctly applied:

| D-# | Lesson source | What to verify |
| --- | --- | --- |
| D-2 | Story 11.2 M-1 catalog-gate | Any `DF-X-SY` references in new code MUST be in `docs/phase-1-5-carry-overs.md`. |
| D-3 | Stories 11.1+11.2 thread-safety | The module-level `_session_drift_warned` set MUST have a thread-safety paragraph in the module docstring. |
| D-4 | Story 11.2 M-3 AC-grep | The AC says "≥10 tests"; final file must match `grep "^def test_"`. |
| D-6 | Story 11.3-specific | `AdapterVersionDriftWarning` is RE-USED (not duplicated) from `mcp/observer.py`. |
| D-7 | Story 11.3-specific | Drift threshold = `tested.minor - detected.minor >= 2` (epics.md L2076 "more than 2 minor versions behind"). |
| D-10 | Story 11.3-specific | Helper call is in `__init__` AFTER `_assert_binary_version` passes. |

## Source files to verify against

- `src/AgentEval/_kernel/version_drift.py` (new module)
- `src/AgentEval/mcp/observer.py:98` (`AdapterVersionDriftWarning` class — re-export source)
- `src/AgentEval/coding_agent/{claude_code_cli,codex_cli,copilot_cli}.py` (3 integration points)
- `tests/unit/kernel/test_version_drift.py` (new unit suite, 16 tests)
- `_bmad-output/implementation-artifacts/11-3-adapterversiondriftwarning-fully-wired.md` (Story 11.3 spec)
- `_bmad-output/planning-artifacts/epics.md:2067-2079` (Story 11.3 epic-level spec)
- `docs/contracts/error-class-hierarchy.md:83` (`AdapterVersionDriftWarning` exit-code 0)
- `docs/contracts/stability-surface.md` (new row at provisional)

## Adversarial review checklist

### HIGH — correctness, regression risk, FR60 compliance

1. **Drift threshold logic**: trace `_drift_across_major()` for ALL the
   edge cases — detected newer (major+1, same minor), detected on a
   previous major (major-1, very high minor), same major (the common
   case). Are the returned drift values sensible? Could the
   `_drift_across_major` ever produce a false-positive (e.g., detected
   on a NEWER patch but lower minor of the same major)?

2. **`parse_binary_version` race**: the helper invokes
   `<binary> --version` AGAIN even though `_assert_binary_version` just
   ran the same command. Two subprocess calls per adapter construction.
   Is this OK? Could the version change between the two calls? (Almost
   certainly no in practice, but flag if there's a cleaner
   architecture.)

3. **Re-use of `AdapterVersionDriftWarning` (D-6)**: Story 5.2's class
   is documented for MCP SDK drift. Story 11.3 re-uses it for CLI binary
   drift. Is the docstring on the class still accurate after re-use? Or
   does the docstring need amendment to cover both surfaces?

4. **FR60 message-content regex stability**: AC-11.3.3 mandates 5
   message elements. Trace the format-string in
   `emit_adapter_version_drift_warning_if_applicable` and verify each
   element is present + would survive a Python-formatting bug.

5. **`compat_max` unused**: AC-11.3.1 receives `compat_max` but the
   helper logic never actually checks it. Is this a real gap (the
   warning should suppress when detected is ALREADY out of compat
   range — but `_assert_binary_version` would have raised already, so
   maybe defensive) OR dead-param-bloat?

### MED — process discipline, hygiene

- **Conftest autouse fixture ordering**: Story 11.3 adds a third autouse
  fixture (`_reset_version_drift_dedupe`) to `tests/unit/coding_agent/conftest.py`
  on top of `mock_claude_version`, `mock_codex_version`, `mock_copilot_version`.
  Pytest applies autouse fixtures in declaration order. Is there an
  ordering dependency (e.g., dedupe-reset must happen BEFORE the
  version mocks)? Spot check.
- **Tests count vs grep**: AC-11.3.6 says "≥10 tests" + the spec also
  enumerates "11-13 integration tests for the 3 adapters" = at least
  13 expected. The actual file has 16. AC met. But: are all 5 spec-
  enumerated FR60 elements covered by a test? Audit the
  `test_warning_message_contains_all_fr60_elements` test against
  AC-11.3.3.

### LOW — wording, style

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.

CRITICAL: when finished, write the findings to:
`_bmad-output/cross-llm-reviews/story-11-3-{tool}-findings.md`
(replace `{tool}` with `copilot`, `codex`, or `kilo`).

If the file isn't written, the review is invalid.
