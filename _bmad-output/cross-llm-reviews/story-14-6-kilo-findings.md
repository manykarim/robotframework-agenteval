# Story 14.6 Cross-LLM Review — Kilo/MiniMax-M2.7 Findings
**Artifact:** `_bmad-output/implementation-artifacts/14-6-unified-host-instance-budget-plumbing-c20-c26-c89-c95-close.md`
**Reviewer:** kilo/minimax-M2.7 (Tier 3 fallback per CLAUDE.md)
**Date:** 2026-06-04
**Scope:** Full adversarial review of Story 14.6 `_HostBudgetPlumbing` mixin (C20+C26+C89+C95 closure)

---

## Verification Commands Run

| Check | Command | Result |
|---|---|---|
| MRO verification | Python `inspect` of `MCPLibrary.__mro__`, `SkillsLibrary.__mro__`, `OrchestrationLibrary.__mro__` | VERIFIED — all 3 show `[_HostBudgetPlumbing, object]` in MRO |
| Keyword-only args | Python `inspect.signature(OrchestrationLibrary.__init__)` | VERIFIED — `default_provider`, `max_cost_usd`, `max_runtime_seconds` all `KEYWORD_ONLY` |
| Positional arg rejection | `OrchestrationLibrary('mock')` → `TypeError` | VERIFIED — "takes 1 positional argument but 2 were given" |
| `@guarded_fanout` count | `grep -nE "@guarded_fanout" src/AgentEval/{mcp,skills,orchestration}/library.py \| wc -l` | 5 occurrences (MCPLibrary ×2, SkillsLibrary ×3) |
| `_build_components` diff | `git diff HEAD~1 src/AgentEval/__init__.py` | VERIFIED — only budget args added to OrchestrationLibrary branch |
| `tracked NOT enforced` in src | `grep -rn "tracked NOT enforced" src/AgentEval/` | **2 hits** in `mcp/library.py:460` + `mcp/library.py:602` |
| Test suite | `uv run pytest tests/unit/kernel/test_host_budget_plumbing.py -v` | 12 passed in 1.05s |
| DF-14.6-S1 existence | `grep "DF-14.6-S1" _bmad-output/implementation-artifacts/deferred-work.md` | VERIFIED — row exists at line 421 |

---

## HIGH Findings

### HIGH-1: AC-14.6.7 NOT SATISFIED — "tracked NOT enforced" phrases STILL present in MCPLibrary docstrings

**Severity:** HIGH
**AC:** AC-14.6.7
**Spec claim:** `"tracked NOT enforced" carve-out docstring lines REMOVED from `MCP.Compare Tool Discoverability` + `Skill.Compare Discoverability`, replaced with positive-framing closure notes.`
**Actual state:**
```
$ grep -n "tracked NOT enforced" src/AgentEval/mcp/library.py
460:        | ``max_cost_usd`` | Budget cap. Phase-1: tracked, NOT enforced (DF-4.4-S1 carry-over). Defaults to ``5.00``.
602:        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2186 ... Phase-1: tracked, NOT enforced.
```

The spec's D-5 decision states: "grep + remove `"tracked NOT enforced"` + `"DF-4.4-S1"` + `"DF-13.3-S1"` + `"DF-13.5-S1"` carve-out references in src/ docstrings + remove them. Libdoc regen reflects the new contract."

Both MCPLibrary keywords (`Get Tool Discoverability` at L460 and `MCP.Compare Tool Discoverability` at L602) still carry "Phase-1: tracked, NOT enforced" in their docstrings. This directly violates AC-14.6.7. The SkillsLibrary docstring for `Skill.Compare Discoverability` also needs verification — the grep hit at `skills/library.py:560` suggests similar residual language.

**Citation:** `src/AgentEval/mcp/library.py:460` (Get Tool Discoverability), `src/AgentEval/mcp/library.py:602` (Compare Tool Discoverability).

**Fix:** Replace "Phase-1: tracked, NOT enforced" with "Enforced via `@guarded_fanout()` per Story 14.6 (C20/C89 closure) — budgets passed at RF `Library` import time are honored end-to-end." in both docstrings. Replace DF-4.4-S1 / DF-13.3-S1 carry-over references with the closure note. Regenerate MCPLibrary libdoc.

---

### HIGH-2: SkillsLibrary `Skill.Compare Discoverability` docstring also needs verification

**Severity:** HIGH (dependent on HIGH-1 scope determination)
**Spec claim:** AC-14.6.7 removes "tracked NOT enforced" from `Skill.Compare Discoverability` too.
**Actual state:** `skills/library.py:560` shows `"tracked NOT enforced"` residual reference in the SkillsLibrary docstring for `Skill.Compare Discoverability`. The grep output shows the SkillsLibrary phrase at `skills/library.py:560`: `| ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2218 ... Phase-1 carve-out DF-13.5-S1 / C95: tracked NOT enforced (same SkillsLibrary architectural gap as DF-4.4-S1 / C20 and DF-13.3-S1).`

**Citation:** `src/AgentEval/skills/library.py:560`
**Fix:** Same pattern as HIGH-1 — replace "tracked NOT enforced" + DF-13.5-S1 carry-over with closure note. Regenerate SkillsLibrary libdoc.

---

## MED Findings

### MED-1: AC-14.6.6 decorator ordering — `@guarded_fanout` on `run_scenario` not verified

**Severity:** MED
**AC:** AC-14.6.6
**Spec claim:** `@guarded_fanout()` added to `get_tool_discoverability` + `get_tool_discoverability_comparison` (2 MCP keywords). "2 Skill + Orch keywords already had it" per D-4.
**Verification:** `grep -nE "@guarded_fanout|@keyword.*Run Scenario" src/AgentEval/orchestration/library.py` — the `run_scenario` method at L239-241 only shows `@keyword` + `@tier(3)` decorators. There is NO `@guarded_fanout()` on `OrchestrationLibrary.run_scenario`.

The spec D-4 says: "OrchestrationLibrary.run_scenario (`orchestration/library.py`): `@tier(3)`; needs verification of current decorator state." The D-4 inventory lists "2 Skill + Orch keywords already have it" — but the OrchestrationLibrary's `run_scenario` is NOT decorated with `@guarded_fanout()` in the current ship.

**Citation:** `src/AgentEval/orchestration/library.py:239-244`
**Fix:** If C26 closure requires `@guarded_fanout()` on `run_scenario`, the decorator must be added. If the cooperative MRO + mixin attrs are sufficient (per D-2: decorator reads `getattr(self, "_max_cost_usd", None)` and now the attrs exist), then the spec's D-4 inventory is incorrect about the Orch keyword already having the decorator. This needs resolution — either add the decorator to `run_scenario` or amend the spec's D-4 inventory to reflect the actual state.

---

### MED-2: `get_tool_discoverability` docstring DF-4.4-S1 carry-over reference NOT updated

**Severity:** MED
**AC:** AC-14.6.7
**Actual state:** `mcp/library.py:464-471` still reads:
```
Phase-1 carve-out (DF-4.4-S1): ``@guarded_fanout`` enforcement
of ``max_cost_usd`` + ``max_runtime_seconds`` is DEFERRED —
same architectural gap as Story 4.3 DF-4.3-S6 (MCPLibrary is
excluded from ``_SUB_LIBRARIES`` per Story 2.2 norm; no clean
path to inject library-level budgets without architectural
change). The kwargs are accepted + tracked on the result but
NOT enforced.
```

This entire paragraph is a "tracked NOT enforced" carve-out that should have been replaced with the closure note per AC-14.6.7.

**Citation:** `src/AgentEval/mcp/library.py:464-471`
**Fix:** Replace the Phase-1 carve-out paragraph with closure note: "Budget enforcement via `@guarded_fanout()` (Story 14.6 / C20 closure) — `MCPLibrary` inherits `_HostBudgetPlumbing` so budgets passed at RF `Library` import time are honored end-to-end."

---

## Verified Correct Items

The following items were verified as correct:

| Item | Evidence |
|---|---|
| `_HostBudgetPlumbing` mixin exists at `_kernel/host_budget_plumbing.py` | 97-line file with `__init__` accepting keyword-only `max_cost_usd` + `max_runtime_seconds` + `**kwargs` forwarding |
| MCPLibrary inherits `_HostBudgetPlumbing` | `mcp/library.py:108`: `class MCPLibrary(_HostBudgetPlumbing):` |
| SkillsLibrary inherits `_HostBudgetPlumbing` | `skills/library.py:101`: `class SkillsLibrary(_HostBudgetPlumbing):` |
| OrchestrationLibrary inherits `_HostBudgetPlumbing` + cooperative ctor | `orchestration/library.py:112` + `__init__` at L123-149 properly forwards via `super().__init__(max_cost_usd=..., max_runtime_seconds=..., **kwargs)` |
| `_build_components` passes budgets to OrchestrationLibrary | `__init__.py:347-358`: adds `max_cost_usd=self._max_cost_usd, max_runtime_seconds=self._runtime_seconds` to `cls(default_provider=..., ...)` call |
| `@guarded_fanout()` added to `get_tool_discoverability` | `mcp/library.py:436` shows `@guarded_fanout()` on the method at line 436 |
| `@guarded_fanout()` added to `get_tool_discoverability_comparison` | `mcp/library.py:569` shows `@guarded_fanout()` on the method |
| `_kernel/guardrails.py:265-266` reads attrs via `getattr` | Confirmed: `max_cost_usd = getattr(self, "_max_cost_usd", None)` at L265 |
| 12 unit tests pass | `pytest tests/unit/kernel/test_host_budget_plumbing.py -v` → 12 passed |
| MRO correct for all 3 libraries | Verified via `MCPLibrary.__mro__` = `[MCPLibrary, _HostBudgetPlumbing, object]` |
| OrchestrationLibrary keyword-only args enforced | `OrchestrationLibrary('mock')` raises `TypeError` |
| C20 catalog row closed | `docs/phase-1-5-carry-overs.md:43` row shows "Story 14.6 (closed 2026-06-04, FULL via `_HostBudgetPlumbing` mixin + `@guarded_fanout()` decorator added)" |
| C26 catalog row closed | `docs/phase-1-5-carry-overs.md:49` row shows "Story 14.6 (closed 2026-06-04, FULL)" |
| C89 catalog row closed | `docs/phase-1-5-carry-overs.md:115` row shows closure with Story 14.6 |
| C95 catalog row closed | `docs/phase-1-5-carry-overs.md:123` row shows "Story 14.6 (closed 2026-06-04, FULL)" |
| DF-14.6-S1 filed in deferred-work.md | Row exists at `deferred-work.md:421` |
| Epic 11 retro L153 Action #2 reference | Verified in `epic-11-retro-2026-05-27.md:153` — action item exists |
| Epic 12 retro L162 Action #3 reference | Verified in `epic-12-retro-2026-06-01.md:162` — action item exists |
| Epic 13 retro L183 Action #6 reference | Verified in `epic-13-retro-2026-06-03.md:183` — action item exists |
| `_build_components` diff shows zero changes to `_SUB_LIBRARIES` | Confirmed via `git diff HEAD~1` — only OrchestrationLibrary branch changed |
| `test_decorator_reads_attrs_via_getattr_with_estimator_pre_flight` stub test | Verifies that with `estimator=callable`, the mixin attrs correctly drive `CostExceededError` pre-flight |

---

## LOW Findings

### LOW-1: Test coverage gap — 4 integration-contract tests don't exercise decorator path end-to-end

**Severity:** LOW (per spec's own D-6 amendment framing)
**Spec framing:** Per D-6, the 4 "integration contract" tests (`test_mcp_get_tool_discoverability_reads_budget_from_host_instance`, etc.) verify that host attrs are readable via `getattr`, NOT that the decorator actually fires. The spec acknowledges this and files DF-14.6-S1.
**Kilo note:** The 4 tests do `assert getattr(lib, "_max_cost_usd", None) == 10.0` — they verify the mixin provides the attrs. But they do NOT call the actual keyword through the `@guarded_fanout` wrapper. The `test_decorator_reads_attrs_via_getattr_with_estimator_pre_flight` test at L174-192 does exercise a full decorator-with-estimator path on a stub host, which is good. But the 4 integration-contract tests on the real libraries only verify attr presence, not decorator invocation.
**No fix required** — this is the documented D-6 scope split. DF-14.6-S1 tracks the live-keyword evidence work.

---

### LOW-2: OrchestrationLibrary docstring verbose historical reference

**Severity:** LOW
**Citation:** `orchestration/library.py:131-143` — the `__init__` docstring repeats the full Story 4.3 history at length.
**No fix required** — proportional to the architectural significance of the cooperative refactor.

---

## Summary

| Category | Count |
|---|---|
| HIGH findings | 2 |
| MED findings | 2 |
| LOW findings | 2 |
| Verified correct | 22 |

**AC-14.6.7 is NOT satisfied** — the "tracked NOT enforced" carve-out language remains in `mcp/library.py:460` (Get Tool Discoverability), `mcp/library.py:464-471` (Phase-1 carve-out paragraph), and `mcp/library.py:602` (Compare Tool Discoverability), and `skills/library.py:560` (Skill.Compare Discoverability). The libdoc regeneration step (AC-14.6.14) likely regenerated with the old content still in place.

**MED-1 (OrchestrationLibrary.run_scenario `@guarded_fanout` decorator)** — the spec says "2 Skill + Orch keywords already had it" but the OrchestrationLibrary `run_scenario` does not carry the decorator. This needs resolution: either the spec's D-4 inventory is wrong, or the decorator needs to be added to close C26 properly.

All other claims verified against source. The architectural plumbing (mixin + library inheritance + `_build_components` injection) is correct and fully tested.