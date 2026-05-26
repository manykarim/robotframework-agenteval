# Story 11.2 Copilot CLI Adapter — GitHub Copilot CLI Adversarial Review Findings

**Reviewer:** GitHub Copilot CLI (Claude Sonnet 4.6 — claude-sonnet-4.6)
**Date:** 2026-05-26
**Artifacts reviewed:**
- `src/AgentEval/coding_agent/copilot_cli.py` (475 LoC)
- `tests/unit/coding_agent/test_copilot_cli.py` (32 tests — confirmed by `grep -n "^def test_"`)
- `tests/unit/coding_agent/conftest.py`
- `tests/fixtures/copilot_cli/` (3 JSONL fixtures)
- `docs/phase-1-5-carry-overs.md`
- `docs/contracts/stability-surface.md`
- `docs/adr/ADR-016-mcp-coverage-detection-default.md`
- `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md`
- `src/AgentEval/coding_agent/base.py`, `codex_cli.py`, `generic.py`, `claude_code_cli.py`
- `src/AgentEval/types.py`
- `_bmad-output/cross-llm-reviews/story-11-2-kilo-findings.md` (kilo Tier 3 review for zero-overlap targeting)
**Sources cited per `feedback_citation_drift_first_class`:** all ADR/Story/L references re-derived from current source files.

---

## UPSTREAM Story 11.1 Lesson Propagation (5-item checklist)

| # | UPSTREAM item | Status |
|---|---------------|--------|
| 1 | `Usage(reasoning_output_tokens=)` populated if `reasoningTokens` present | **VERIFIED** — `copilot_cli.py:426-438` sums `data.get("reasoningTokens")` from `assistant.message` events; `isinstance(rt, int)` guard handles missing field defensively; `test_finalize_reasoning_tokens_populated_if_present` (L252-265) regression guard present |
| 2 | NO module-level `_VERSION_RE` dead-code constant | **VERIFIED** — no such constant found; comment at L105-108 explains base `_SEMVER_RE.search()` handles the `GitHub Copilot CLI 1.0.54.` trailing-period format via substring search |
| 3 | Thread-safety paragraph in class docstring (NOT just inline comments) | **VERIFIED** — class docstring at L183-199 has two dedicated paragraphs: the `_last_mcp_servers` stash thread-safety invariant AND the session-state-dir-race invariant, both in the class docstring as required |
| 4 | Negative-path tests for D-3 diagnostic 3-condition guard | **VERIFIED** — `test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic` (L236) covers "has response text" path; `test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic` (L244) covers "has terminal event" path |
| 5 | ADR-016 §Decision L33 citation discipline (NOT §Alternatives L59) | **VERIFIED** — `copilot_cli.py:76` cites `ADR-016 §Decision L33` verbatim; `_detect_mcp_coverage` docstring (L466-471) also cites `ADR-016 §Decision L33`; stability-surface.md L113 entry uses `§Decision L33`; ADR-016 file confirmed at `docs/adr/ADR-016-mcp-coverage-detection-default.md` L33 = degradation rule #2 "No instrumented servers were attached during the run (catch-all safe default)" |

**UPSTREAM pass rate: 5/5** ✓

---

## HIGH — correctness + regression risk

### H-1: `trace_id=""` hardcoded — no inline placeholder comment, inconsistent with 5 of 7 adapters

**File:** `src/AgentEval/coding_agent/copilot_cli.py:462`

**Finding:**
```python
trace_id="",
```
This is a bare empty string with no inline explanation. Cross-checking all 7 adapter `trace_id` usages in the project:

| Adapter | `trace_id` value | Comment? |
|---------|-----------------|----------|
| `claude_agent_sdk.py:224` | `uuid.uuid4().hex` | no comment needed |
| `claude_code_cli.py:500` | `uuid.uuid4().hex` | no comment needed |
| `generic.py:244` | `uuid.uuid4().hex` | no comment needed |
| `openai_agents.py:203` | `uuid.uuid4().hex` | no comment needed |
| `codex_cli.py:472` | `""` | **"Story 5.3 + Epic 5 wire real trace-id"** |
| `copilot_cli.py:462` | `""` | **NONE** |

`codex_cli.py` (Story 11.1 precedent) explicitly documents the empty-string as a Phase-1 placeholder. `copilot_cli.py` drops the comment, leaving `trace_id=""` with no explanation. The stability-surface.md L113 entry for `CopilotCLIAdapter` does NOT mention `trace_id` as a placeholder, while the codex entry also omits it. Base PRD FR51 mandates `trace_id=<uuid>` for RF-report-line traceability.

**Severity:** HIGH — the Story 5.3 RunManifest pipeline cannot reliably correlate CLI-adapter runs. The asymmetry between codex (documented placeholder) and copilot (undocumented) violates the cross-story consistency norm. The underlying deferral is legitimate but must be documented.

**Concrete fix:**
```python
trace_id="",  # Phase-1 placeholder; Story 5.3 / Epic 5 wires real trace-id (mirrors codex_cli.py).
```
Additionally: update `stability-surface.md:113` CopilotCLIAdapter row to add "`trace_id=''` Phase-1 placeholder per codex precedent (DF-11.2-S3-adjacent; Story 5.3 wires real UUID)."

---

## MED — process discipline, hygiene

### M-1: `DF-11.2-S3` referenced in class docstring but has NO catalog entry (carry-over catalog gate violation)

**File:** `src/AgentEval/coding_agent/copilot_cli.py:197-199` (class docstring)

**Finding:** The class docstring says:
> "concurrent runs against the same `~/.copilot/session-state/` parent would race for the 'newest directory' pick. Documented; tracked DF-11.2-S3 carry-over if a real consumer hits this."

`DF-11.2-S3` is referenced as a tracked carry-over, but **`docs/phase-1-5-carry-overs.md` has NO corresponding entry**. The catalog ends at C76 (Story 11.2 adds C75 + C76). The `feedback_carry_over_catalog_gate` norm — applied 27 consecutive times per the catalog footer — requires ALL `DF-X-SY` patterns to have a corresponding catalog row. `grep -rn "DF-11.2-S3"` returns exactly ONE non-binary hit: `copilot_cli.py:198`. No catalog row, no spec decision referencing it, no Task in the story tasks list.

**This was NOT caught by kilo/minimax M2.7 — unique finding.**

**Severity:** MED — the `feedback_carry_over_catalog_gate` norm exists precisely to prevent carry-overs from being dropped. The session-state-dir-race is a real correctness concern (documented by the class docstring itself) that has no Phase-2 tracking.

**Concrete fix:** Add to `docs/phase-1-5-carry-overs.md` after C76:

```markdown
| **C77** | **Phase-2: session-state-dir race for concurrent Copilot CLI runs (`DF-11.2-S3`).** Story 11.2 class docstring 2026-05-26: `run()` identifies the new session-state directory by selecting the newest dir not in the pre-spawn snapshot. Concurrent Copilot runs against the same `~/.copilot/session-state/` parent race for this "newest dir" pick — the wrong session's events.jsonl could be read. Phase-1: single-instance-per-run mitigation documented in class docstring. Phase-2: if a real consumer hits this, add a sessionId-based lookup (read the `session.start` event's `sessionId` from stdout stream pre-`proc.wait()`, then match against directory names OR use the `sessionId` to find the correct dir). | Story 11.2 class docstring invariant — Phase-1 concurrency gap | correctness | S | TBD | Live-binary probe confirms `session.start.sessionId` is the UUID used for the session-state directory name; `run()` reads sessionId from stdout to identify the correct directory instead of mtime heuristic. |
```

Update catalog total: **77 catalog items**.

---

### M-2: `test_spawn_uses_start_new_session_true` as standalone test is absent; assertion is embedded in a multi-assertion test

**File:** `tests/unit/coding_agent/test_copilot_cli.py:310-326`

**Finding:** AC-11.2.4 at line 76 specifies:
> `test_spawn_uses_start_new_session_true` + `--allow-all-tools` flag (D-1/Story 1b.4)

`test_spawn_uses_start_new_session_true` is not present as a standalone function. The `start_new_session=True` assertion EXISTS at L324 inside `test_spawn_uses_stderr_stdout_multiplex`, which bundles 4 assertions (stderr, start_new_session, text, stdout). This is not a dedicated regression guard per the AC's intent.

The importance is not trivial: the Story 1b.4 process-group hygiene invariant (`start_new_session=True` prevents `_terminate_process_group` from accidentally SIGTERMing the test runner's process group) is load-bearing enough to warrant its own test name and docstring. If a future refactor splits `test_spawn_uses_stderr_stdout_multiplex` into separate tests, the `start_new_session` guard might be silently dropped.

**Note on kilo M-1 (test count claim):** kilo claimed 31 tests vs docstring's 32. This reviewer's independent `grep -n "^def test_"` count returns **32 unique test functions**. Kilo's M-1 finding is a **false positive** — the docstring claim of "32 tests" is correct.

**Severity:** MED — AC requirement not met as specified; the regression guard exists but is not independently navigable.

**Concrete fix:**
```python
def test_spawn_uses_start_new_session_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 1b.4 D1 process-group hygiene regression guard:
    `_spawn` MUST set `start_new_session=True` so
    `_terminate_process_group` can safely SIGTERM the subprocess PG
    without accidentally killing the test runner itself.

    AC-11.2.4 mandated standalone test (mirrors Story 11.1's equivalent)."""
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
This raises the test count to 33 and satisfies AC-11.2.4 line 76.

---

### M-3: `_parse_event` coverage for 5 event types mandated by AC-11.2.4 is absent

**File:** `tests/unit/coding_agent/test_copilot_cli.py`

**Finding:** AC-11.2.4 at `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md:71` says:
> "`_parse_event` per event type (`session.start`, `session.model_change`, `session.shutdown`, `user.message`, `assistant.turn_start`, `assistant.turn_end`, `assistant.message`, `tool.execution_start`, `tool.execution_complete`, `None` on non-JSON, `None` on unknown type)."

Existing tests cover: `session.start`, `session.shutdown`, `assistant.message` (text+tokens), `assistant.message` (tool_requests), `tool.execution_complete`, `None` on non-JSON, `None` on non-string type, `None` on non-dict JSON.

**Missing 5 event type tests:** `session.model_change`, `user.message`, `assistant.turn_start`, `assistant.turn_end`, `tool.execution_start`.

For each missing type, `_parse_event` simply creates a `CopilotEvent(event_type=<type>, raw=<dict>)` — the behavior is trivially correct. However, AC says "MUST cover" with the word "MUST" and enumerates all 10 types. The absence means the test suite doesn't document/verify that these 5 types are handled (even trivially).

**Severity:** MED — AC not fully satisfied; the implementation is correct but the test coverage gap violates the explicit "MUST" in the AC.

**Concrete fix:** Add 5 one-liner tests, e.g.:
```python
def test_parse_event_session_model_change() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"session.model_change","data":{"newModel":"gpt-5"}}')
    assert event is not None
    assert event.event_type == "session.model_change"

def test_parse_event_user_message() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"user.message","data":{"content":"hi"}}')
    assert event is not None
    assert event.event_type == "user.message"

def test_parse_event_assistant_turn_start() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"assistant.turn_start","data":{"turnId":"0"}}')
    assert event is not None
    assert event.event_type == "assistant.turn_start"

def test_parse_event_assistant_turn_end() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"assistant.turn_end","data":{"turnId":"0"}}')
    assert event is not None
    assert event.event_type == "assistant.turn_end"

def test_parse_event_tool_execution_start() -> None:
    event = CopilotCLIAdapter()._parse_event('{"type":"tool.execution_start","data":{"toolCallId":"c1","toolName":"shell"}}')
    assert event is not None
    assert event.event_type == "tool.execution_start"
```

---

## LOW — wording, optional siblings

### L-1: `reasoningOpaque`/`reasoningText` fields present in empirical probe spec but no `CopilotEvent` accessor (kilo L-1 confirmed)

**File:** `src/AgentEval/coding_agent/copilot_cli.py:122-171` / `_bmad-output/implementation-artifacts/11-2-copilot-cli-adapter.md:157`

**Finding (confirms kilo L-1 with source citation):** The spec dev notes describe `assistant.message` as carrying `optional reasoningOpaque`/`reasoningText`. The empirical probe that drove D-8 observed these fields in the real copilot events.jsonl (per the spec author's dev notes at `11-2-copilot-cli-adapter.md:157`). `_finalize` reads `reasoningTokens` (a speculative integer-count field, NOT observed in the probe) while `reasoningOpaque`/`reasoningText` have no accessor and are silently discarded.

The `test_finalize_reasoning_tokens_populated_if_present` test uses a **fully synthetic fixture** — `{"reasoningTokens": 5}` — which does not correspond to any field confirmed in the empirical probe. The docstring's "if present" framing is honest, but the field name `reasoningTokens` appears to have been inferred from the Codex `turn.completed.usage.reasoning_output_tokens` analogy rather than from the actual Copilot events.jsonl schema. If Copilot surfaces reasoning data via `reasoningOpaque` (content, not count), the `reasoning_output_tokens` field would remain 0 even when reasoning occurred.

**Severity:** LOW — the code is defensively correct (won't crash, won't fabricate tokens). The probe couldn't be read in this session (permission denied to `~/.copilot/session-state/391978f9.../events.jsonl`). The correctness risk is deferred behind C76.

**Fix (optional):** Add a comment in the `reasoning_tokens` loop explaining that `reasoningTokens` is a speculative field name; document the empirically observed alternatives `reasoningOpaque`/`reasoningText` so a Phase-2 probe can confirm which field name Copilot actually uses.

---

### L-2: `nonzero_exit.jsonl` fixture is documentation-only minimal (kilo L-2 confirmed)

**File:** `tests/fixtures/copilot_cli/nonzero_exit.jsonl`

**Finding (confirms kilo L-2):** 2-line fixture (`session.start` + `user.message`) is sufficient for its current test purpose but cannot serve future tests that need assistant content + nonzero exit.

**Severity:** LOW — no action required; future tests can create inline events.

---

### L-3: kilo M-1 is a false positive (test count is correct)

**Finding:** kilo/minimax M2.7 (Tier 3) enumerated 31 tests and flagged the docstring's "32 tests" claim as wrong. Independent verification via `grep -n "^def test_" tests/unit/coding_agent/test_copilot_cli.py | wc -l` returns **32**. The 32nd test (`test_detect_mcp_coverage_nonempty_returns_external_mixed`) was miscounted by kilo (possibly confused by the `mgp` vs `mcp` pattern in the kilo enumeration). The docstring claim is **correct**. No fix needed for M-1.

---

## ADR-016 §Decision L33 Citation Integrity Check

Per `feedback_citation_drift_first_class`, re-derived from source:

`docs/adr/ADR-016-mcp-coverage-detection-default.md` line 33 (numbered from the view output) = **"2. No instrumented servers were attached during the run (catch-all safe default)."**

The adapter cites this as justification for returning `external_mixed` when no instrumented servers are attached (non-empty `mcp_servers` case). The adapter also returns `hosted_in_process` for empty `mcp_servers` — this maps to the ADR's logic that if no MCP servers were configured, the run is trivially fully observable. **Citation is semantically correct; L33 is in the §Decision section (NOT §Alternatives at L56-63).** The UPSTREAM lesson is correctly applied.

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| HIGH | 1 | H-1: `trace_id=""` with no placeholder comment (undocumented deferral vs. codex_cli precedent) |
| MED | 3 | M-1: `DF-11.2-S3` carry-over not cataloged (catalog gate violation); M-2: `test_spawn_uses_start_new_session_true` standalone absent; M-3: 5 of 11 AC-required `_parse_event` event-type tests missing |
| LOW | 3 | L-1: `reasoningOpaque`/`reasoningText` not in CopilotEvent accessors; L-2: fixture minimal; L-3: kilo M-1 is a false positive (32 tests confirmed) |

---

## Verdict

**Story 11.2 materials pass adversarial review with 1 HIGH + 3 MED to address.**

All 5 Story 11.1 UPSTREAM lessons correctly applied (5/5). Citation discipline (ADR-016 §Decision L33) is consistent across source, stability-surface, and docstrings. The `mock_copilot_version` autouse fixture is correctly placed in conftest. No `_VERSION_RE` dead-code constant. Thread-safety + dir-race invariant is in the class docstring as mandated.

The **unique finding not in kilo's review** is M-1: `DF-11.2-S3` is referenced in the class docstring as a tracked carry-over but has no C77 catalog entry. The `feedback_carry_over_catalog_gate` norm (27th consecutive application) is violated. This is actionable in under 10 minutes (one catalog row addition).

H-1 (`trace_id=""` with no comment) mirrors `codex_cli.py`'s documented-placeholder pattern but was not applied consistently. The fix is a one-line comment addition + stability-surface.md amendment.

**Recommended order of fixes before marking done:**
1. Add C77 catalog row for DF-11.2-S3 in `docs/phase-1-5-carry-overs.md` (M-1 — catalog gate violation)
2. Add inline placeholder comment to `copilot_cli.py:462` (H-1 — consistency with codex precedent)
3. Add standalone `test_spawn_uses_start_new_session_true` test (M-2 — AC requirement)
4. Add 5 trivial `_parse_event` event-type tests (M-3 — AC requirement)
