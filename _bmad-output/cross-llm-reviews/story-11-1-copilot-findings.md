# Story 11.1 — CodexCLIAdapter — Adversarial Review Findings (Copilot / Claude Sonnet 4.6)

**Review date:** 2026-05-26  
**Reviewer:** GitHub Copilot CLI (claude-sonnet-4.6)  
**Scope:** `src/AgentEval/coding_agent/codex_cli.py`, `tests/unit/coding_agent/test_codex_cli.py`,
fixtures, conftest, pyproject.toml, docs carry-overs, ADR citations  
**Test run:** 33/33 passed (5.25 s)

---

## HIGH findings

**None.** All load-bearing correctness checks pass:

- **D-1 (Story 4.2 HIGH-A)** ✅ — `_spawn` passes prompt as the last positional argv element
  (`cmd[-1] == prompt`). `test_spawn_passes_prompt_as_positional_argv` asserts this explicitly.
- **D-2 (Story 4.2 HIGH-B)** ✅ — `stderr=subprocess.STDOUT` set in `_spawn`. Confirmed by
  `test_spawn_uses_stderr_stdout_multiplex`.
- **D-3 (Story 4.2 MED-3)** ✅ — `_finalize` emits `[SUBPROCESS_NONZERO_EXIT exit_code=<N>]`
  exactly when `not response_text and exit_code != 0 and terminal is None`. Three-condition guard
  is correct and the `nonzero_exit.jsonl` fixture exercises the positive path.
- **D-7 (Epic 10 HIGH-2)** ✅ — Non-empty `mcp_servers` → `"external_mixed"` via
  `_detect_mcp_coverage`. `test_run_with_unverified_mcp_marks_external_mixed` confirms the end-
  to-end path through `run()` → `_finalize` → `_detect_mcp_coverage`.
- **`_finalize` projection** ✅ — Traced end-to-end against `/tmp/codex_probe.jsonl` and
  `/tmp/codex_tool_probe.jsonl`:
  - `simple_prompt.jsonl`: `response_text="Hi"`, `usage.input_tokens=23160`,
    `completeness="complete"`, `cost_usd=0.0` — all match test assertions.
  - `tool_use.jsonl`: narration + answer concatenated via `\n`, one `ToolCallTrace` with
    `name="command_execution"`, `args={"command": "/bin/bash -lc 'echo hello'"}`,
    `result="hello\n"`, `error=None` — all match test assertions. `item.started` events
    correctly skipped by `command_execution_payload` (checks `event_type == "item.completed"`).
  - `truncated.jsonl`: no terminal → `completeness="truncated"`, zero usage fallback.
  - `nonzero_exit.jsonl`: empty events + exit_code=2 → diagnostic emitted.
- **D-4 (conftest autouse)** ✅ — `mock_codex_version` is in
  `tests/unit/coding_agent/conftest.py` as an `autouse=True` fixture from the start, matching the
  Story 4.2 Edge-cases MED-1 lesson.
- **D-5 (ADR citations)** ✅ — `codex_cli.py` cites ADR-002 (Tier-1 Adapter Ceiling Rule),
  NOT ADR-005 (Conformance Suite Fidelity Oracles). Confirmed against ADR files.
- **Empirical probe accuracy** ✅ — All 4 fixtures (`simple_prompt.jsonl`, `tool_use.jsonl`,
  `truncated.jsonl`, `nonzero_exit.jsonl`) match the documented JSONL schema and probe files.
- **D-9 (cost_usd + DF-11.1-S2)** ✅ — `cost_usd=0.0` placeholder present; C74 entry in
  `docs/phase-1-5-carry-overs.md` covers `DF-11.1-S2`.
- **D-6 (ADR-A6 renumbering)** ✅ — No references to `ADR-A6` exist in the new files; all
  citations correctly use `ADR-016`.

---

## MED findings

### MED-1 — `_VERSION_RE` dead code + contradictory module-level docstring
**File:** `src/AgentEval/coding_agent/codex_cli.py`, lines 32 and 118  
**Severity:** MED (misleading documentation + story-spec compliance gap)

The module docstring (line 32) states:
> "the regex `_VERSION_RE` accounts for the ``codex-cli `` prefix"

`_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")` is declared at line 118 but is
**never called anywhere**. The constructor comment at lines 202-205 correctly explains why:

> "The default `_SEMVER_RE.search()` in the base helper extracts `0.133.0` from `codex-cli 0.133.0`
> via substring search — no override needed (D-10 prefix is a documentation note only, not a code
> requirement)."

These two statements are contradictory. Furthermore, story spec D-10 explicitly said:
> "**Decision:** `_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")` — match Story 4.2's
> `_VERSION_RE` pattern but with prefix change."

The story spec decision implies `_VERSION_RE` would be used, yet the implementation doesn't use it.
`_SEMVER_RE.search("codex-cli 0.133.0")` works correctly (extracts `0.133.0`), so there is
**no functional regression** — but the module docstring misrepresents what the code does.

**Concrete fix:**  
Option A (preferred — remove dead code): Delete `_VERSION_RE` at line 118 and update
module docstring line 32 to: "Note the `codex --version` output format is ``codex-cli <semver>``
— the base `_SEMVER_RE.search()` extracts the semver substring correctly without a prefix override."

Option B (keep if intended as future override hook): Add a comment after `_VERSION_RE`:
```python
# Declared for future `_assert_binary_version` override if the base search order changes.
# Currently the base `_SEMVER_RE.search()` correctly extracts "0.133.0" from
# "codex-cli 0.133.0" via substring search — no override needed (D-10).
```
AND update the module docstring line 32 to avoid claiming `_VERSION_RE` is "used".

---

### MED-2 — ADR-016 L59 citation points to the Alternatives section, not the Decision section
**File:** `src/AgentEval/coding_agent/codex_cli.py`, lines 55, 73, 85, 444, 449  
**Severity:** MED (citation accuracy; story-spec D-6 mandated this citation)

The code cites "ADR-016 §Detection contract L59" and "ADR-016 L59 safer-default rule" in five
places. Actual content at ADR-016 line 59:

> "— *Default `"library_only"` (the original proposed default value) on detection failure* —
>   rejected: silent partial truth; violates AC-MCP-OBSERVE-01's 'loud refusal beats silent
>   half-truth.' **The ratified default-on-failure is `external_mixed`.**"

This line is in the `## Alternatives` section (which starts at line 56), not the `## Decision`
section. The primary contract rule for `external_mixed` as the catch-all safe default is at
**line 33** in the Decision section:

> "2. No instrumented servers were attached during the run (catch-all safe default)."

Story spec D-6 mandated the L59 citation (over the obsolete ADR-A6 L384), so the intent is
understood. But L59 is an Alternatives entry citing a rejected option — it mentions the ratified
default as a side-note, not as the contract. This is the kind of citation drift that could become
stale if the Alternatives section is ever rewritten.

**Concrete fix:** Replace "ADR-016 L59 safer-default rule" with "ADR-016 §Decision L33 (catch-all
safe default: no instrumented servers attached)" across lines 55, 73, 85, 444, and 449.
Also update `docs/phase-1-5-carry-overs.md` C73 at line 98 which also cites "ADR-016 L59".

---

### MED-3 — `_last_mcp_servers` concurrency invariant undocumented at class level
**File:** `src/AgentEval/coding_agent/codex_cli.py`, lines 212-213 and class docstring (~line 190)  
**Severity:** MED (Phase-1 scope, but invariant not visible to subclassers or adapter users)

The `_last_mcp_servers` stash pattern is explained in the `run()` docstring but NOT in the
`CodexCLIAdapter` class docstring. A user who calls `run()` concurrently from two threads on the
same adapter instance will silently corrupt `mcp_coverage` (the second thread's `_last_mcp_servers`
overwrites the first's before `_finalize` reads it). The `SubprocessAdapter` base class docstring
also doesn't warn about thread-safety of `run()`.

**Concrete fix:** Add to the `CodexCLIAdapter` class docstring:
```
Thread safety: **not concurrent-safe**. ``run()`` uses ``self._last_mcp_servers``
instance state to thread ``mcp_servers`` through to ``_finalize`` (Phase-1 single-
threaded per-instance design; see DF-11.1-S1 for the Phase-2 observer-based path
that eliminates this limitation). Do not call ``run()`` concurrently on the same
``CodexCLIAdapter`` instance.
```

---

### MED-4 — Missing negative-path tests for D-3 diagnostic gating
**File:** `tests/unit/coding_agent/test_codex_cli.py`  
**Severity:** MED (regression risk if `_finalize` condition is refactored)

`test_finalize_nonzero_exit_with_no_message_emits_diagnostic` tests the positive case (all three
conditions true). But the three-condition guard:
```python
if not response_text and exit_code != 0 and terminal is None:
```
has no tests for cases where the diagnostic should NOT fire:
- `exit_code != 0` but `response_text` is non-empty → diagnostic should be suppressed.
- `exit_code != 0` but `terminal` event present → diagnostic should be suppressed.

If a future refactor changes the condition (e.g., drops the `terminal is None` guard), no existing
test would catch the regression.

**Concrete fix:** Add two tests:
```python
def test_finalize_nonzero_exit_with_response_text_does_not_emit_diagnostic() -> None:
    events = _events_from_fixture("simple_prompt.jsonl")  # has agent_message "Hi"
    result = CodexCLIAdapter()._finalize(events, exit_code=1)
    assert result.response_text == "Hi"  # response_text wins; no diagnostic appended
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text

def test_finalize_nonzero_exit_with_terminal_does_not_emit_diagnostic() -> None:
    events = _events_from_fixture("simple_prompt.jsonl")  # has turn.completed terminal
    result = CodexCLIAdapter()._finalize(events, exit_code=1)
    assert "[SUBPROCESS_NONZERO_EXIT" not in result.response_text
```

---

## LOW findings

### LOW-1 — `test_parse_event_returns_none_on_unknown_type` test name vs body mismatch
**File:** `tests/unit/coding_agent/test_codex_cli.py`, lines 204-209  
**Severity:** LOW (`feedback_test_name_assertion_match` norm)

The test name says "unknown_type" but the body tests two semantically different cases:
1. `'{"type":42}'` — non-string type discriminator (correct match to "unknown type")
2. `"[1, 2, 3]"` — non-dict JSON (this is not an "unknown type"; it's an invalid JSON shape)

The second assertion is testing a different code path than the test name promises.

**Concrete fix:** Split into two tests or rename to `test_parse_event_returns_none_on_invalid_json_shapes`.

---

### LOW-2 — `codex = []` extra comment could mention npm install command
**File:** `pyproject.toml`, lines 79-84  
**Severity:** LOW (DX)

The comment on line 79 says "The `codex` binary must be on `$PATH` (npm install -g @openai/codex)"
but the exact npm package name might change as the project is still pre-1.0. The comment is a
best-effort pointer; no fix required unless the spec mandates a specific install path.

---

### LOW-3 — `record_active_run_metadata` not called on `super().run()` exception
**File:** `src/AgentEval/coding_agent/codex_cli.py`, lines 241-255  
**Severity:** LOW (intentional by design, but worth flagging)

If `super().run()` raises (e.g., subprocess spawn error or `_finalize` error), the `finally` block
resets `_last_mcp_servers = None` and then the exception propagates — `record_active_run_metadata`
is NOT called. This mirrors the `claude_code_cli.py` pattern and is presumably intentional (failed
runs don't emit telemetry). No functional bug, but the behavior is undocumented in the `run()`
docstring.

**Concrete fix (optional):** Add one sentence to the `run()` docstring: "If `super().run()` raises,
`record_active_run_metadata` is not called (failed runs emit no telemetry metadata)."

---

## Summary table

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| MED-1 | MED | `codex_cli.py` L32+L118 | `_VERSION_RE` dead code + contradictory docstring |
| MED-2 | MED | `codex_cli.py` L55/73/85/444/449 | ADR-016 L59 citation in Alternatives section, not Decision section |
| MED-3 | MED | `codex_cli.py` class docstring | `_last_mcp_servers` concurrency invariant not documented at class level |
| MED-4 | MED | `test_codex_cli.py` | Missing negative-path tests for D-3 diagnostic gating |
| LOW-1 | LOW | `test_codex_cli.py` L204-209 | Test name vs body mismatch on `_returns_none_on_unknown_type` |
| LOW-2 | LOW | `pyproject.toml` L79 | npm install command comment may become stale |
| LOW-3 | LOW | `codex_cli.py` `run()` | Exception path skips telemetry — undocumented |

---

## D-# lessons verification matrix

| D-# | Expected | Verified | Notes |
|-----|----------|----------|-------|
| D-1 | Prompt as positional argv | ✅ PASS | `cmd[-1] == prompt`; test asserts this |
| D-2 | `stderr=subprocess.STDOUT` | ✅ PASS | `test_spawn_uses_stderr_stdout_multiplex` |
| D-3 | Nonzero-exit diagnostic emitted | ✅ PASS | 3-condition guard correct; positive case tested |
| D-4 | `mock_codex_version` in conftest autouse | ✅ PASS | Present in `conftest.py` from the start |
| D-5 | ADR-002 not ADR-005 | ✅ PASS | Confirmed against ADR README index |
| D-6 | ADR-016 not ADR-A6 L384 | ✅ PASS (with note) | Correctly uses ADR-016; L59 citation is in Alternatives section (MED-2) |
| D-7 | non-empty MCP → `external_mixed` | ✅ PASS | `_detect_mcp_coverage` correct; e2e test via `run()` |
| D-9 | `cost_usd=0.0` + DF-11.1-S2 in carry-overs | ✅ PASS | C74 in `phase-1-5-carry-overs.md` |
| D-10 | `codex-cli ` prefix handled | ✅ PASS (with note) | Base `_SEMVER_RE` handles it; `_VERSION_RE` dead code (MED-1) |
