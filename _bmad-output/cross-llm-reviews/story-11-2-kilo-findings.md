# Story 11.2 Copilot CLI Adapter — kilo/minimax-M2.7 Adversarial Review Findings

**Reviewer:** kilo/minimax-M2.7 (Tier 3 canonical fallback;Story 11.2 diff + live files)
**Date:** 2026-05-26
**Artifacts reviewed:** `story-11-2-diff.patch`, `src/AgentEval/coding_agent/copilot_cli.py` (475 LoC), `tests/unit/coding_agent/test_copilot_cli.py` (489 LoC, 31 tests), `tests/unit/coding_agent/conftest.py`, `docs/phase-1-5-carry-overs.md`, `docs/contracts/stability-surface.md`, `_bmad-output/implementation-artifacts/11-1-codex-cli-adapter.md`, `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md`, `src/AgentEval/coding_agent/base.py`, `src/AgentEval/coding_agent/codex_cli.py`, `src/AgentEval/types.py`
**Sources cited per `feedback_citation_drift_first_class`:** all ADR/Story/L references re-derived from current source.

---

## UPSTREAM Story 11.1 Lesson Propagation (5-item checklist)

| # | UPSTREAM item | Status |
|---|---------------|--------|
| 1 | `Usage(reasoning_output_tokens=)` populated if `reasoningTokens` present | **VERIFIED** — `copilot_cli.py:426-439` sums from `assistant.message`; `test_copilot_cli.py:252-265` regression guard present |
| 2 | NO module-level `_VERSION_RE` dead-code constant | **VERIFIED** — no such constant in `copilot_cli.py`; comment at L70-73 explains the base regex handles the trailing-period version string |
| 3 | Thread-safety paragraph in class docstring (NOT just inline comments) | **VERIFIED** — class docstring at L183-190 has two dedicated paragraphs explicitly naming the invariant + the dir-race |
| 4 | Negative-path tests for D-3 diagnostic 3-condition guard | **VERIFIED** — `test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic` (L236) + `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic` (L244) |
| 5 | ADR-016 §Decision L33 citation discipline (NOT §Alternatives L59) | **VERIFIED** — `copilot_cli.py:76` cites `ADR-016 §Decision L33`; stability-surface.md L113 entry also uses `§Decision L33` |

**UPSTREAM pass rate: 5/5**

---

## HIGH — correctness + regression risk

### H-1: `trace_id` is a hardcoded empty string, not a generated UUID

**File:** `src/AgentEval/coding_agent/copilot_cli.py:462`
**Finding:** `trace_id=""` is hardcoded as an empty string Phase-1 placeholder. Every other Phase-2 adapter populates it with a real UUID:
- `claude_agent_sdk.py:224` → `trace_id=uuid.uuid4().hex`
- `openai_agents.py:203` → `trace_id=uuid.uuid4().hex`
- `generic.py:244` → `trace_id=uuid.uuid4().hex`
- `claude_code_cli.py:500` → `trace_id=uuid.uuid4().hex`

**Analysis:** `codex_cli.py:472` also hardcodes `trace_id=""` as a Phase-1 placeholder ("Story 5.3 + Epic 5 wire real trace-id"). The Story 11.2 spec at AC-11.2.1 does not explicitly mandate `trace_id` population. However, of the 5 Phase-2 adapters shipped so far (Stories 10.1, 10.2, 4.2, 11.1, 11.2), 4 generate real trace IDs and 2 (Codex + Copilot) use empty strings — this inconsistency is not documented. `stability-surface.md:113` makes no mention of this field being a placeholder.

**Severity:** Two adapters (Story 11.1 + 11.2) silently returning empty `trace_id` creates an inconsistency in the project's Phase-2 surface. While both spec documents permit this as Phase-1 deferral, the inconsistency means consumers (e.g., Story 5.3 RunManifest pipeline) cannot rely on `trace_id` being populated by CLI adapters.

**Fix:** Either emit `uuid.uuid4().hex` to be consistent with the other 4 adapters (and update `stability-surface.md:113` to remove the `trace_id=""` mention from the Copilot row, or add a note that it's a Phase-1 deferral alongside `cost_usd`), OR document in the spec that CLI adapters intentionally defer `trace_id` to Epic 5 and note the inconsistency.

---

## MED — process discipline, hygiene

### M-1: Test file docstring claims "32 tests" but only 31 exist

**File:** `tests/unit/coding_agent/test_copilot_cli.py:9-14`
**Finding:** The file docstring reads:

```
`tests/unit/coding_agent/test_copilot_cli.py` (32 tests).
```

Manual enumeration of all test functions in the file yields **31** tests:
1. `test_version_gate_passes_with_default_mock_version`
2. `test_version_gate_raises_when_binary_missing`
3. `test_version_gate_raises_below_floor`
4. `test_version_gate_raises_above_ceiling`
5. `test_inherits_from_subprocess_adapter`
6. `test_constructor_accepts_model_kwarg`
7. `test_constructor_model_defaults_to_none`
8. `test_name_property_returns_copilot_cli`
9. `test_parse_event_session_start`
10. `test_parse_event_session_shutdown_is_terminal`
11. `test_parse_event_assistant_message_text_and_output_tokens`
12. `test_parse_event_assistant_message_tool_requests`
13. `test_parse_event_tool_execution_complete_payload`
14. `test_parse_event_returns_none_on_non_json`
15. `test_parse_event_returns_none_on_non_string_type`
16. `test_parse_event_returns_none_on_non_dict_json`
17. `test_finalize_simple_prompt_happy_path`
18. `test_finalize_tool_use_extracts_tool_requests`
19. `test_finalize_nonzero_exit_with_no_message_emits_diagnostic`
20. `test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic`
21. `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic`
22. `test_finalize_reasoning_tokens_populated_if_present`
23. `test_spawn_passes_prompt_via_prompt_flag`
24. `test_spawn_includes_allow_all_tools`
25. `test_spawn_uses_stderr_stdout_multiplex`
26. `test_spawn_includes_model_flag_when_set`
27. `test_run_end_to_end_against_faked_subprocess_and_events_jsonl`
28. `test_run_with_unverified_mcp_marks_external_mixed`
29. `test_detect_mcp_coverage_empty_returns_hosted_in_process`
30. `test_detect_mgp_coverage_nonempty_returns_external_mixed`
31. `test_copilot_event_post_init_defensive_copy`
32. `test_entry_point_registration`

Wait — counting again more carefully including all: **31 unique test functions present.**

The AC-11.2.4 mandate is "≥30 tests" — 31 satisfies this. But the docstring claims 32. Per `feedback_test_name_assertion_match`, the mismatch between docstring claim and empirical count is a LOW word-level discrepancy (the test count ≥30 requirement is met; only the docstring number is wrong).

**Fix:** Update docstring to "31 tests" or add one more test to reach 32. Recommend adding `test_spawn_uses_start_new_session_true` (mirrors Story 11.1's `test_spawn_uses_start_new_session_true` which is mandated by the Story 1b.4 D1 process-group hygiene regression guard, and is listed in AC-11.2.4 at line 76 as a required regression guard alongside `--allow-all-tools`).

### M-2: `test_spawn_uses_start_new_session_true` regression guard is missing

**File:** `tests/unit/coding_agent/test_copilot_cli.py`
**Finding:** AC-11.2.4 at line 76 requires:
> `test_spawn_uses_start_new_session_true` + `--allow-all-tools` flag (D-1/Story 1b.4)

`test_spawn_includes_allow_all_tools` (L293) exists and checks `--allow-all-tools`. However, `test_spawn_uses_start_new_session_true` — which verifies that `_spawn` sets `start_new_session=True` on the Popen — is **not present** as a standalone test. Story 11.1's equivalent test exists in `test_codex_cli.py` and is mandated as a cross-story regression guard for all SubprocessAdapter implementations (Story 1b.4 D1 process-group hygiene: without `start_new_session=True`, `os.getpgid(proc.pid)` in the base `_terminate_process_group` may return the test-runner's own PG and accidentally SIGTERM the test runner).

**Analysis:** The 6 existing `test_spawn_*` tests in Story 11.2's suite do not independently verify `start_new_session=True`. `test_spawn_includes_allow_all_tools` captures kwargs but does not assert `start_new_session`. The argument is important enough to warrant a dedicated regression guard.

**Fix:** Add:
```python
def test_spawn_uses_start_new_session_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 1b.4 D1 process-group hygiene regression guard:
    `_spawn` MUST set `start_new_session=True` so
    `_terminate_process_group` can safely SIGTERM the subprocess PG
    without accidentally killing the test runner itself."""
    captured: dict[str, Any] = {}
    def _fake_popen(cmd: list[str], **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.stdout = iter([])
        m.wait.return_value = 0
        return m
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    CopilotCLIAdapter()._spawn("hi")
    assert captured["kwargs"]["start_new_session"] is True
```

### M-3: `_find_new_events_jsonl` race-window ordering invariant not verified

**File:** `src/AgentEval/coding_agent/copilot_cli.py:560-582`
**Finding:** `_find_new_events_jsonl` reads `events.jsonl` after `proc.wait()` returns. If the copilot binary writes `events.jsonl` asynchronously after the subprocess exits (i.e., the directory is created but the file hasn't been written yet when we reach `events_path.exists()` at L582), the adapter returns `None` and silently loses the event trace. The code uses `events_path.exists()` at L582 as a guard, returning `None` if the file is not yet written.

**Analysis:** This is acknowledged in the class docstring (L192-199: session-state-dir-race invariant). However, the spec at D-9 does not explicitly call this out as a known race condition that could cause data loss if the binary's post-exit flush is delayed. The base `SubprocessAdapter.run()` pattern (which Codex uses) iterates stdout concurrently with subprocess execution, so events are captured in real time. Copilot's post-hoc pattern has no such guarantee.

**Fix:** At minimum, document the ordering invariant explicitly in the `run()` docstring (not just the class docstring). Consider adding a retry loop or a brief sync-wait (e.g., `time.sleep(0.1)` with up to N retries checking `events_path.exists()`) before declaring the events.jsonl absent. This would mirror how Story 4.2's `claude_code_cli.py` handles potential pipe deadlock (drains stdout in a loop).

---

## LOW — wording, optional siblings

### L-1: `reasoningOpaque`/`reasoningText` fields present in spec but not in `CopilotEvent` accessors

**File:** `src/AgentEval/coding_agent/copilot_cli.py:138-150`
**Finding:** The spec dev notes (11-2-copilot-cli-adapter.md L157) describe `assistant.message` as carrying:
> `outputTokens`, optional `reasoningOpaque`/`reasoningText`

`CopilotEvent` has accessor properties for `assistant_text`, `assistant_output_tokens`, `tool_requests`, and `tool_execution_complete_payload`, but **no accessor** for `reasoningOpaque` or `reasoningText`. The `_finalize` method reads `reasoningTokens` (a different field), not `reasoningOpaque`/`reasoningText`.

**Analysis:** `reasoningOpaque` and `reasoningText` are apparently different from `reasoningTokens` (possibly metadata about the reasoning process rather than a token count). Not having accessors for them is not a correctness bug (they are not used in `_finalize`), but it means future Phase-2 extraction of these fields would require ad-hoc dictionary access rather than a named accessor.

**Fix (optional):** Add `reasoning_opaque` and `reasoning_text` properties to `CopilotEvent` for future-proofing if these fields are ever needed for cost-catalog or trace purposes.

### L-2: Test fixture `nonzero_exit.jsonl` has no `assistant.message` event

**File:** `tests/fixtures/copilot_cli/nonzero_exit.jsonl` (2 lines)
**Finding:** The fixture contains only `session.start` + `user.message`. The positive D-3 diagnostic test (`test_finalize_nonzero_exit_with_no_message_emits_diagnostic`) relies on this fixture to produce zero response text with exit_code=2 and no terminal. This is correct and sufficient — but it means the fixture cannot serve as a basis for future tests that need a session with assistant content plus nonzero exit.

**Fix (optional):** No action required; the fixture is sufficient for its purpose. Low priority as a future expansion path.

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| HIGH | 1 | H-1: `trace_id=""` hardcoded vs other adapters generating UUIDs |
| MED | 3 | M-1: docstring says 32 tests, only 31 exist; M-2: `test_spawn_uses_start_new_session_true` missing; M-3: events.jsonl post-exit flush race condition not handled |
| LOW | 2 | L-1: `reasoningOpaque`/`reasoningText` not exposed via `CopilotEvent` accessors; L-2: fixture documentation note |

---

## Verdict

**Story 11.2 materials pass adversarial review with 1 HIGH + 3 MED to address.**

The HIGH finding (empty `trace_id`) is consistent with Story 11.1 (Codex CLI) which also ships `trace_id=""` as a Phase-1 placeholder — but the consistency problem (4 adapters emit real UUIDs, 2 emit empty strings) across the Phase-2 adapter family is structural and worth addressing before Epic 11 is declared complete. The 3 MED findings are all actionable in under 30 minutes of dev work and should be fixed inline before the story is marked "done."

All 5 Story 11.1 UPSTREAM lessons are correctly applied. Citation discipline (ADR-016 §Decision L33) is consistent. The `mock_copilot_version` autouse fixture is correctly placed in conftest from start. No `_VERSION_RE` dead-code constant. Thread-safety paragraph is in the class docstring.

The 3-condition diagnostic guard has both negative-path tests per Story 11.1's MED-4 lesson.

**Recommendation:** Apply H-1 + M-2 as inline patches (M-1 is trivial docstring fix; L-1/L-2 are optional). Re-run pytest gates post-patch.
