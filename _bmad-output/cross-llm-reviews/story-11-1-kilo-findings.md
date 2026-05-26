# Story 11.1 — kilo/minimax-M2.7 Adversarial Review Findings

**Reviewer:** kilo/minimax-M2.7 (Tier 3 — canonical fallback per `feedback_third_llm_family_fallback`)
**Date:** 2026-05-26
**Diff:** `_bmad-output/cross-llm-reviews/story-11-1-diff.patch`
**Source files verified against:** `codex_cli.py`, `test_codex_cli.py`, `base.py`, `types.py`, `simple_prompt.jsonl`, `tool_use.jsonl`, `stability-surface.md`, `phase-1-5-carry-overs.md`

---

## HIGH — correctness, citation drift, regression risk

### H-1: `terminal_usage` silently drops `reasoning_output_tokens` (data-loss bug)

**File:** `src/AgentEval/coding_agent/codex_cli.py:183-187`

**Finding:** The `terminal_usage` property extracts only 3 of the 4 fields from `turn.completed.usage`. The Codex JSONL schema (per empirical probe at `simple_prompt.jsonl` line 4 + `tool_use.jsonl` line 7) always carries `reasoning_output_tokens`:

```json
{"type":"turn.completed","usage":{"input_tokens":23160,"cached_input_tokens":4480,"output_tokens":5,"reasoning_output_tokens":0}}
```

The `Usage` dataclass at `types.py:149-151` has 3 fields:
```python
input_tokens: int
output_tokens: int
cached_input_tokens: int = 0
```

`terminal_usage` passes only these 3. `reasoning_output_tokens` is accepted by `Usage.__init__` as an unknown kwarg and discarded — no error, no warning, no field.

**Impact:** Any downstream consumer (cost calculator, token accounting, audit trail) calling `result.usage.reasoning_output_tokens` gets `AttributeError` — or if they wrote defensive code, they get `0` silently instead of the real value. DF-11.1-S2 (cost-catalog integration) explicitly plans to use all 4 token fields, so this bug will block the carry-over's core purpose.

**Re-derive from source:** `simple_prompt.jsonl` line 4 confirms `"reasoning_output_tokens":0` is always present in real `turn.completed` events. `tool_use.jsonl` line 7 confirms `"reasoning_output_tokens":43` with a non-zero value. The `Usage` dataclass has no field for it.

**Fix:** Either (a) add `reasoning_output_tokens: int = 0` to the `Usage` dataclass (requires checking all callers + Story 10.1/10.2 adapter compatibility), or (b) store the raw value in a wrapper/projection on `CodexCLIAdapter` side before calling `Usage()`, or (c) at minimum, document the field is dropped and that Phase-1.5 cost-catalog integration (C74) must handle the projection.

---

### H-2: Citation drift — "ADR-A6 L384" is cited as current but is the old/pre-renumbered reference

**File:** `src/AgentEval/coding_agent/codex_cli.py:86-87`

**Finding:** The docstring says:
> ADR-016 §Detection contract L59 (ratifies ``external_mixed`` default / on detection failure; **supersedes the pre-renumbered ADR-A6 L384 per Epic 10 Story 10.1 kilo MED-2 catch**).

The phrasing "supersedes ADR-A6 L384" is correct about the renumbering history, but the embedded parenthetical makes the citation chain confusing to re-derive. More importantly, the `story 11.1 spec` itself states D-6 as:
> Story 10.1 kilo MED-2 caught that `ADR-A6 L384` is renumbered to `ADR-016 L59`.

And the spec's AC-11.1.2 says:
> Docstring MUST document the 2-branch detection contract inline, **citing ADR-016 L59 verbatim** (NOT `ADR-A6`).

The actual code at `codex_cli.py:385` cites `ADR-016 L59` correctly in the References section. But the inline docstring at lines 84-87 embeds the renumbering history inline in a way that makes it appear "ADR-A6 L384" is still a valid reference to track. Per the adversarial review mandate: **re-derive each cited fact from source**.

The re-derivation: ADR-016 L59 is the ratified text. The `story 11.1 spec` D-6 correctly documents the renumbering. But the parenthetical in the docstring creates a second-order citation risk — future readers might cite "ADR-A6 L384" believing it is still valid.

**Fix:** Remove the parenthetical renumbering history from the inline docstring; keep it only in the spec's D-6 section. The inline docstring should cite `ADR-016 L59` cleanly. The References section (line 385) already does this correctly.

---

## MED — process discipline, hygiene

### M-1: `_VERSION_RE` module-level constant is unused (dead code)

**File:** `src/AgentEval/coding_agent/codex_cli.py:118`

```python
_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")
```

This constant is declared at module scope but is never referenced in the running code. The base `_assert_binary_version` helper at `base.py:438` uses its own `_SEMVER_RE` (`r"(\d+\.\d+(?:\.\d+)?)"`) which correctly extracts `0.133.0` from `codex-cli 0.133.0` via substring search. The adapter's `__init__` at line 206 calls:
```python
self._assert_binary_version(CODEX_BINARY, min=MIN_VERSION, max=MAX_VERSION)
```

with no override, confirming the default regex handles the `codex-cli ` prefix.

The `codex_cli.py` docstring at lines 31-32 explains:
> the regex `_VERSION_RE` accounts for the ``codex-cli `` prefix.

But this is documentation-only; the constant is not wired to anything. The story spec AC-11.1.3 says the `_VERSION_RE` is "per D-10" but D-10 is a documentation note, not a code requirement (per spec: "no override needed (D-10 prefix is a documentation note only, not a code requirement)").

**Fix:** Remove `_VERSION_RE` from module scope, or document it is reserved for a future `_assert_binary_version` override (and add a `skip` annotation so it doesn't appear as dead code).

---

### M-2: `_last_mcp_servers` race — single-threaded assumption not advertised

**File:** `src/AgentEval/coding_agent/codex_cli.py:208-213` + `codex_cli.py:428`

The `run()` override stashes `mcp_servers` on `self._last_mcp_servers` (line 240) before calling `super().run()`, then nulls it in `finally` (line 244). `_finalize` reads it at line 428 via `getattr(self, "_last_mcp_servers", None)`.

The docstring at line 208-212 explicitly calls out "Phase-1 single-threaded per-instance" — this is good hygiene. However:

1. The stash-on-instance pattern is documented but not enforced. A concurrent caller sharing the same `CodexCLIAdapter` instance could overwrite `_last_mcp_servers` mid-run.
2. The `finally` block nulls it, but only on the outer `run()` path — if an exception occurs before `super().run()` is called, `_last_mcp_servers` may retain stale state.
3. The `getattr(self, "_last_mcp_servers", None)` fallback to `None` when attribute doesn't exist is safe but masks the fact that `_finalize` can be called in contexts where `run()` was never called (e.g., direct `_finalize` call in tests).

The story spec correctly documents this as Phase-1 carve-out. But there's no advertising of the thread-safety invariant beyond "Phase-1 single-threaded". If Phase-2 needs thread-safe reuse of a `CodexCLIAdapter` instance, this pattern will silently produce wrong `mcp_coverage` values.

**Fix (MED):** Add a `# Thread-safety: Phase-1 single-instance` comment on `_last_mcp_servers` and on the `run()` override. The spec's Phase-1 carve-out documentation is sufficient for now — this is MED not HIGH because the invariant is documented and the Phase-1 scope is clearly labeled.

---

### M-3: `_SEMVER_RE` vs `_VERSION_RE` — two version regexes for the same binary

**File:** `src/AgentEval/coding_agent/base.py:438` (default) vs `codex_cli.py:118` (unused)

The base `_assert_binary_version` uses `_SEMVER_RE = r"(\d+\.\d+(?:\.\d+)?)"`. The adapter declares `_VERSION_RE = re.compile(r"^codex-cli\s+(\d+\.\d+\.\d+)")`. The base regex handles the prefix correctly because it does substring search (not anchored). The adapter's regex is unused but documented as though it's load-bearing.

This creates a maintenance risk: future developers may see `_VERSION_RE` and assume they need to wire it to `_assert_binary_version` override, adding unnecessary complexity.

**Fix:** Same as M-1 — remove the dead `_VERSION_RE` constant.

---

### M-4: Carry-over catalog C73/C74 — `reasoning_output_tokens` gap not noted

**File:** `docs/phase-1-5-carry-overs.md:98-99`

C74 says: "compute `cost_usd` from `(input_tokens, output_tokens, reasoning_output_tokens, cached_input_tokens)`" — explicitly listing `reasoning_output_tokens` as a required field. But the `Usage` dataclass doesn't have this field (H-1 above). This means C74's implementation note cannot be fulfilled without first fixing H-1.

**Fix:** C74 should note the dependency on `Usage` having `reasoning_output_tokens` before the cost computation can be implemented. This is a MED finding because C74 is correctly documenting the empirical schema (Codex events carry it), but the `Usage` dataclass gap means the carry-over needs a prerequisite fix.

---

### M-5: `stability-surface.md` line 113 — `reasoning_output_tokens` not mentioned

**File:** `docs/contracts/stability-surface.md:113`

The row for `CodexCLIAdapter` says:
> Reads `usage` from `turn.completed.usage` (**4-field shape**: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`)

This correctly identifies the 4-field shape. But the `Usage` dataclass only has 3 fields. The stability-surface doc correctly describes the source schema but doesn't flag that the `Usage` dataclass is currently lossy (drops `reasoning_output_tokens`).

**Fix:** Add a parenthetical "Phase-1: `Usage` dataclass has 3 fields; `reasoning_output_tokens` dropped — tracked in C74 carry-over" to the stability-surface row, so consumers know the Phase-1 limitation.

---

## LOW — wording, optional siblings

### L-1: `run()` override nulls `_last_mcp_servers` in `finally` but the `finally` only wraps `super().run()`, not the full method

**File:** `codex_cli.py:241-244`

```python
self._last_mcp_servers = mcp_servers
try:
    result = super().run(prompt, tools=tools, mcp_servers=mcp_servers, **kwargs)
finally:
    self._last_mcp_servers = None
```

The `finally` correctly nulls on both normal and exception paths from `super().run()`. However, `record_active_run_metadata` is called AFTER the `try/finally` block (line 244-253), which means if `super().run()` raises, `_last_mcp_servers` is already nulled when `record_active_run_metadata` is called (though it only reads `result.cost_usd`, `result.metadata.completeness`, `result.metadata.mcp_coverage` — not `_last_mcp_servers`). This is safe but the sequencing is worth noting for future maintainers.

**No fix required.** This is safe.

---

### L-2: `test_codex_cli.py:182` — `test_parse_event_turn_completed_usage` only asserts 3 fields

**File:** `tests/unit/coding_agent/test_codex_cli.py:182-194`

The test parses a `turn.completed` event with `reasoning_output_tokens` but only asserts `input_tokens`, `output_tokens`, `cached_input_tokens`. Since H-1 is a real bug (data loss), this test is currently passing with false confidence — it doesn't verify the 4th field is preserved.

**Fix:** Add `assert usage.reasoning_output_tokens == 5` to the test once H-1 is fixed. This test should be the regression guard for H-1.

---

## Summary

| Finding | Severity | File:Line | Concrete Fix |
|---------|----------|-----------|-------------|
| H-1: `terminal_usage` drops `reasoning_output_tokens` | HIGH | `codex_cli.py:183-187` | Add `reasoning_output_tokens` to `Usage` dataclass OR project it on adapter side before calling `Usage()` |
| H-2: ADR-A6 L384 citation is pre-renumbered reference | HIGH | `codex_cli.py:86-87` | Remove parenthetical renumbering history from inline docstring; cite ADR-016 L59 cleanly |
| M-1: `_VERSION_RE` unused constant | MED | `codex_cli.py:118` | Remove or mark as reserved-for-future-override |
| M-2: `_last_mcp_servers` thread-safety not enforced | MED | `codex_cli.py:208-213` | Add thread-safety comment; Phase-1 documented but not enforced |
| M-3: Two version regexes (one unused) | MED | `codex_cli.py:118` vs `base.py:438` | Same as M-1 |
| M-4: C74 carry-over needs `Usage` field first | MED | `phase-1-5-carry-overs.md:99` | Add prerequisite note linking C74 to H-1 resolution |
| M-5: stability-surface doesn't flag Usage dropping field | MED | `stability-surface.md:113` | Add Phase-1 limitation note to row |
| L-1: `finally` sequencing is safe | LOW | `codex_cli.py:241-244` | No fix required |
| L-2: Test only checks 3 of 4 usage fields | LOW | `test_codex_cli.py:182-194` | Add `reasoning_output_tokens` assertion once H-1 is fixed |

**H-1 is the most critical** — it is a silent data-loss bug that will block DF-11.1-S2 (C74 cost-catalog integration) and any downstream consumer expecting `reasoning_output_tokens` from Codex adapter results.