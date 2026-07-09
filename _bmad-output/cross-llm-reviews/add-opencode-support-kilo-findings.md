# Kilo Adversarial Review: add-opencode-support (OpenCodeCLIAdapter)

**Reviewer:** kilo/minimax-M2.7
**Date:** 2026-06-25
**Files reviewed:**
- `src/AgentEval/coding_agent/opencode_cli.py`
- `tests/unit/coding_agent/test_opencode_cli.py`
- `tests/fixtures/opencode_cli/*.jsonl` (5 files)
- `src/AgentEval/coding_agent/codex_cli.py` (sibling precedent)
- `src/AgentEval/_kernel/version_drift.py`

**Empirical ground truth (opencode 1.15.12, `opencode run --format json`):**
Each stdout line is JSON `{type, timestamp, sessionID, part}`.
Types: `step_start`; `text` (`part.text`); `tool_use` (`part.tool`, `part.callID`, `part.state{status, input, output, metadata{exit}}`); `step_finish` (`part.reason` "tool-calls"|"stop"; `part.tokens{input, output, reasoning, cache{read}}` **PER-STEP not cumulative**; `part.cost` per-step).

---

## Category: Framing / Process Drift

### HIGH-1 — `step_tokens` docstring over-claims `total` field
**File:** `opencode_cli.py:55-56`

**What is wrong:**
The docstring claims `part.tokens` carries `{total, input, output, reasoning, cache{write, read}}`. The empirical schema (confirmed by fixture data) has no `total` in `part.tokens`, and the `cache` object only has `{read, write}`, not nested `{write, read}`. More critically, `total` is present in the fixture (`"total":17328`) but **is never extracted or used anywhere in the code** — `_finalize` at lines 417-421 only reads `input`, `output`, `reasoning`, and `cache.read`. The docstring falsely implies `total` is part of the accessible surface.

**Concrete fix:**
Update line 55-56 to match the actual extracted fields:
```
  ``part.tokens`` carries ``{input, output, reasoning,
  cache{read, write}}`` PER STEP (NOT cumulative — verified across a
  2-step tool-use run); ``part.cost`` carries per-step ``cost_usd``.
```
And add `total` to the "Phase-1 placeholder / not surfaced" list, or remove the claim entirely.

---

### MED-1 — `tool_payload` docstring misrepresents field hierarchy
**File:** `opencode_cli.py:169-173`

**What is wrong:**
The docstring says the returned dict carries `tool` (name), `callID`, and `state` (`{...}`) — implying `callID` lives inside `state`. In the empirical schema (and fixture), `callID` is a **top-level sibling** of `state` inside `part`, not nested inside it. The code correctly extracts it as `payload.get("callID")` (line 398), but the docstring misleads about the schema shape.

**Concrete fix:**
Update lines 171-172:
```
  The returned dict carries ``tool`` (name), ``callID`` (top-level
  in ``part``), and ``state`` (``{status, input, output,
  metadata{exit}, ...}``).
```

---

### MED-2 — `step_finish` docstring lists `total` in `part.tokens` dict signature
**File:** `opencode_cli.py:55`

**What is wrong:**
Same issue as HIGH-1 but scoped to the docstring at line 55's inline type signature. The `{total, input, output, reasoning, cache{write, read}}` signature is inaccurate — `total` is not in `part.tokens` in the accessible interface; only `input/output/reasoning/cache{read,write}` are extracted.

**Concrete fix:**
Correct the inline signature at line 55 to `{input, output, reasoning, cache{read, write}}`.

---

## Category: Citation Drift

### LOW-1 — `step_start` event docstring says `part.type == "step-start"`
**File:** `opencode_cli.py:46`

**What is wrong:**
The docstring claims `step_start` events have `part.type == "step-start"`. In the empirical schema, the discriminator is the **top-level** `type` field (`"step_start"`), not `part.type`. The `part.type` sub-field does exist and equals `"step-start"` (confirmed in fixture), but the docstring phrasing `part.type == "step-start"` as the discriminator is misleading — the actual discriminator is the outer `type` field. The code (line 346) correctly uses `parsed.get("type")`.

**Concrete fix:**
Change line 46 to:
```
- ``step_start`` — a step-boundary marker; the inner ``part.type``
  sub-field equals ``"step-start"``.
```

---

### LOW-2 — `step_finish` `part.cost` docstring doesn't specify type
**File:** `opencode_cli.py:57`

**What is wrong:**
The docstring says `part.cost` carries per-step `cost_usd`. The fixture shows `cost: 0` (integer). The code (line 192) does `float(self._part.get("cost") or 0.0)` which handles both int and float. The claim is directionally correct but doesn't specify that `cost` can be `0` for free models or absent entirely. No functional bug; minor doc hygiene.

**Concrete fix:**
Add `(absent/zero for free models)` to line 57.

---

## Category: Completeness Logic

### MED-3 — `is_terminal` ignores error state; a failed tool call followed by `reason=stop` is marked "complete"
**File:** `opencode_cli.py:156-158` + `_finalize:435-437`

**What is wrong:**
`is_terminal` only checks `finish_reason == "stop"`. It does **not** consider whether a preceding `tool_use` event had `state.status == "error"`. In `tool_error.jsonl`, a tool fails (`status: "error"`) but the subsequent `step_finish` has `reason: "stop"`. The adapter would mark this run as `completeness="complete"` even though the tool execution error means the agent did not successfully complete its task.

The empirical schema says `step_finish` carries `part.reason` ("tool-calls"|"stop") and `part.tokens` — there is no `part.success` or similar field. So the adapter cannot detect error-from-terminal-event alone; it must correlate tool errors from the `tool_use` events themselves.

**Concrete fix:**
In `_finalize`, before setting `completeness`, check whether any `tool_use` event has an error marker set:
```python
tool_errors = [tc.error for tc in tool_calls if tc.error]
has_tool_error = any(tool_errors)
completeness = "complete" if terminal is not None and exit_code == 0 and not has_tool_error else "truncated"
```
Or alternatively, surface `has_tool_error` as a separate flag in `AgentRunMetadata`.

---

## Category: Per-Step Token Summing

### CLEAN — Token summing is correct
The `_finalize` token accumulation (lines 408-422) correctly sums `input`, `output`, `reasoning`, and `cache.read` from each `step_finish` event. The test at lines 285-288 explicitly verifies per-step summing (37+234, 63+3, etc.) against `tool_use.jsonl`. The empirical claim that tokens are PER-STEP not cumulative is verified by the fixture: step1 tokens ≠ step2 tokens.

---

## Category: Fail-Loud Diagnostic Guard

### MED-4 — Diagnostic condition is more restrictive than docstring claims
**File:** `opencode_cli.py:369`

**What is wrong:**
The docstring at lines 354-360 says the diagnostic fires when `exit_code != 0` AND no terminal step_finish AND "no assistant text". The actual condition is:
```python
if not response_text and exit_code != 0 and terminal is None:
```
This requires `response_text` to be empty (no text events **or** all text events produced empty strings). The docstring implies the trigger is "no assistant text produced" which could be satisfied by text events that exist but are empty. The condition is **more** restrictive than described.

**Concrete fix:**
Update docstring at lines 354-355 to accurately describe the condition:
```
when ``exit_code != 0`` AND no terminal ``step_finish`` event
AND no response text was produced (i.e., ``response_text`` is empty).
```

---

## Category: MCP Coverage Contract

### CLEAN — `mcp_coverage` detection is correct
`_detect_mcp_coverage` (lines 458-472) correctly returns `"hosted_in_process"` for empty `mcp_servers` and `"external_mixed"` for non-empty, matching ADR-016 §Decision L33. The docstring accurately describes this. Tests at lines 480-488 verify both paths.

---

## Category: Version Pin / Drift Wiring Honesty

### MED-5 — `self.version` in `run()` docstring is ambiguous
**File:** `opencode_cli.py:274`

**What is wrong:**
The docstring at line 274 says `adapter_version=self.version` is recorded. `self.version` comes from the parent `SubprocessAdapter` class and is the **distribution/package version** of `AgentEval` (e.g., "1.0.0"), not the binary version (e.g., "1.15.12"). The `_TESTED_UP_TO = "1.15.12"` constant is the binary pin. These are different values for different purposes. The docstring should clarify this to avoid future confusion when a developer sees a package version in the manifest instead of the binary version.

**Concrete fix:**
Update line 274 comment:
```
# `self.version` is the AgentEval distribution version (package metadata),
# NOT the `opencode` binary version. Binary version is tracked via
# `_TESTED_UP_TO` + `emit_adapter_version_drift_warning_if_applicable`.
```

---

## Category: `codex_cli.py` Sibling Precedent Cross-Check

### CLEAN — Adapter correctly diverges from Codex where empirical schema differs
Key differences correctly handled:
1. **Token source**: Codex uses terminal `turn.completed.usage` (cumulative); opencode uses per-step `step_finish.tokens` (summed). The adapter correctly sums per-step.
2. **Cost**: Codex has no cost field (`cost_usd=0.0` placeholder); opencode has `part.cost` per step and the adapter sums it.
3. **Terminal event**: Codex uses `turn.completed`; opencode uses `step_finish` with `reason="stop"`.
4. **`mcp_coverage`**: Both correctly use `external_mixed` for non-empty servers per ADR-016.

---

## Summary Table

| SEVERITY | file:line | what is wrong | concrete fix |
|----------|-----------|---------------|--------------|
| HIGH-1 | `opencode_cli.py:55-56` | `step_tokens` docstring lists `total` in `part.tokens` and `cache{write,read}` — neither is accurate; `total` is not extracted by code | Correct docstring to `{input, output, reasoning, cache{read, write}}`; mark `total` as not surfaced |
| MED-1 | `opencode_cli.py:169-173` | `tool_payload` docstring implies `callID` is inside `state`; it is a top-level sibling in `part` | Fix field hierarchy description |
| MED-2 | `opencode_cli.py:55` | Inline type signature `{total, input, ...}` is inaccurate | Correct to `{input, output, reasoning, cache{read, write}}` |
| MED-3 | `opencode_cli.py:156-158,435-437` | `is_terminal` + completeness ignores tool error; failed tool + `reason=stop` → "complete" | Check for tool errors before setting completeness="complete" |
| MED-4 | `opencode_cli.py:369` | Fail-loud condition requires empty `response_text`, not just "no assistant text" | Update docstring to accurately describe the `response_text` empty condition |
| MED-5 | `opencode_cli.py:274` | `self.version` in `run()` docstring is ambiguous (package vs binary version) | Clarify that `self.version` is distribution version, not binary pin |
| LOW-1 | `opencode_cli.py:46` | `step_start` docstring says `part.type == "step-start"` as discriminator; actual discriminator is top-level `type` | Clarify that `part.type` is a sub-field, not the event discriminator |
| LOW-2 | `opencode_cli.py:57` | `part.cost` docstring doesn't note it can be absent/zero for free models | Add note about absent/zero for free models |

**Clean categories:** Per-step token summing (verified correct), MCP coverage contract (verified correct), version drift wiring (correct), Codex sibling divergence (correctly handled).
