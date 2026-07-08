# Story 14.6 — Cross-LLM 3-tier review synthesis

**Date:** 2026-06-04
**Artifact:** Story 14.6 (`_HostBudgetPlumbing` mixin — C20+C26+C89+C95 closure)

## Tier status

| Tier | Reviewer | Outcome |
| --- | --- | --- |
| 1a | Claude CLI sonnet | **DEGRADED — 0-byte output** (`story-14-6-claude-sonnet-findings.md` empty) |
| 1b | Claude CLI opus | **DEGRADED — 0-byte output** (`story-14-6-claude-opus-findings.md` empty) |
| 2 | Codex CLI | **DEGRADED — prompt+diff echoed back**, no structured findings; only a trailing libdoc `grep` confirmation block (`story-14-6-codex-findings.md`, 2856L, low-signal) |
| in-session | Opus 4.8 (this session) | **Served the degraded CLI tiers** per `feedback_third_llm_family_fallback` / `feedback_integration_test_forcing_function` — all empirical claims re-derived from source. |

Per CLAUDE.md "When ALL 3 tiers degrade": end-to-end empirical verification substitutes as the truth check. Every finding below was confirmed by running the code / grepping source — not by reading the diff.

## Findings (HIGH → applied inline as v0.3.0)

### HIGH-1 — C26 is a FALSE closure: `OrchestrationLibrary.run_scenario` has NO `@guarded_fanout` (budget never enforced)

`orchestration/library.py:239-241` — decorator stack is `@keyword(name="Run Scenario")` + `@tier(3)` only. `guarded_fanout` is **not imported** in the module. Empirical:

```
$ grep -cE "^\s*@guarded_fanout" src/AgentEval/orchestration/library.py      → 0
$ grep -nE "import.*guarded_fanout" src/AgentEval/orchestration/library.py   → NOT IMPORTED
>>> hasattr(OrchestrationLibrary.run_scenario, "__wrapped__")                → False
>>> hasattr(MCPLibrary.get_tool_discoverability, "__wrapped__")              → True   # MCP is genuinely wrapped
```

The mixin gives `OrchestrationLibrary` the `_max_cost_usd` / `_max_runtime_seconds` attrs, but with no decorator reading them on `run_scenario`, **nothing enforces the budget.** C26's "FULL closure — `Run Scenario` enforces budgets via `@guarded_fanout`" is materially false. The spec premise (D-4: "OrchestrationLibrary.run_scenario already carrying `@guarded_fanout()`") and the stability-surface claim (`stability-surface.md:142`: "OrchestrationLibrary.run_scenario already had the decorator pre-Story-14.6") are both factually wrong — it never had it. The unit test `test_orchestration_run_scenario_reads_budget_from_host_instance` is fake-green: it asserts `getattr(lib, "_max_cost_usd")` + `hasattr(lib, "run_scenario")`, neither of which detects the missing decorator.

**Fix (applied):** import `guarded_fanout`; add bare `@guarded_fanout()` under `@tier(3)` on `run_scenario` (symmetric with the MCP keywords, which carry no estimator). Strengthen the test to assert `hasattr(OrchestrationLibrary.run_scenario, "__wrapped__")`.

### HIGH-2 — C20/C89 docstring contradiction: `Get Tool Discoverability` still documents "tracked, NOT enforced … DEFERRED" after being decorated + closed

`mcp/library.py` `get_tool_discoverability` now carries `@guarded_fanout()` (line 436) and C20 is claimed FULL-closed, yet its docstring still reads:

- L460 `max_cost_usd | Budget cap. Phase-1: tracked, NOT enforced (DF-4.4-S1 carry-over).`
- L461 `max_runtime_seconds | Runtime cap. Phase-1: tracked, NOT enforced.`
- L464-471 `Phase-1 carve-out (DF-4.4-S1): @guarded_fanout enforcement … is DEFERRED … accepted + tracked … but NOT enforced.`
- L511 `Tier-3 stochastic; budgets tracked but NOT enforced in Phase-1 (DF-4.4-S1).`
- L636 (`get_tool_discoverability_comparison` Notes): `Phase-1 carve-out DF-13.3-S1: @guarded_fanout enforcement DEFERRED.`

Root cause: AC-14.6.7's grep used the exact string `"tracked NOT enforced"`; the docstrings say `"tracked, NOT enforced"` (with a comma), so the grep returned 0 hits and the carve-out was declared removed. The dev only updated the *Compare* keywords' argument-table rows (L601) and left both keywords' carve-out prose + the single-keyword's entire DEFERRED block intact. **The regenerated `MCPLibrary.html` ships the contradiction** (`Get Tool Discoverability` arg table still says "tracked, NOT enforced (DF-4.4-S1 carry-over)"). A `done` C20/C89 closure whose own keyword docs say enforcement is DEFERRED is a fake-green-by-imprecise-grep.

**Fix (applied):** rewrite the residual carve-out prose on both MCP discoverability keywords to the positive closure note (mirroring the wording already used on the Compare arg-table rows); regenerate the 3 libdoc HTMLs.

### HIGH-3 — Citation drift (regresses Story 14.4's own correction)

The story cites the source retro actions as `Epic 11 retro Action #2 (L153)` and `Epic 12 retro Action #3 (L162)`. Re-derived from source:

- **Epic 11 retro L153 = Action #3** (not #2). Content matches (the @guarded_fanout MCPLibrary carve-out). → number wrong.
- **Epic 12 retro L162 Action #3 = "Add libdoc-rendering smoke step to cross-LLM review prompt template"** — a different topic. The @guarded_fanout MCPLibrary carve-out in Epic 12 is **Action #7 at L166**. → both line and number wrong; the quoted text the story attributes to Epic 12 Action #3 does not appear there.
- Epic 13 retro L183 Action #6 — **correct.** ✓

This regresses a sibling story: Story 14.4's `DF-14.4-S1` note (in this same diff) already established via "Codex HIGH-1" that *"Action #3 at Epic 11 L153 is the @guarded_fanout MCPLibrary carve-out."* Story 14.6 then cited it as Action #2 — violating both `feedback_citation_drift_first_class` and `feedback_cross_story_upstream_lesson_propagation`.

**Fix (applied):** correct citations to `Epic 11 Action #3 (L153)` and `Epic 12 Action #7 (L166)` across the spec retro-debt mini-pass, References section, and stability-surface section.

## MED (documented, not all blocking)

- **MED-1 — test suite never exercises a real guarded keyword body.** The 4 "integration-contract" tests assert `getattr`/`hasattr` only; the 1 estimator test uses a synthetic `_HostWithEstimator` (which is the *only* reason a `CostExceededError` is raised anywhere — no shipped keyword carries an estimator). So no test would have caught HIGH-1 (missing decorator) or detects that the live keywords don't pre-flight-refuse. Partially mitigated by the HIGH-1 `__wrapped__` assertion added; full Layer-2 mid-run breach tests remain `DF-14.6-S1`.
- **MED-2 — "honored end-to-end" overstates enforcement.** With bare `@guarded_fanout()` (no estimator) Layer 1 pre-flight never fires, and Layer 2 mid-run needs the real cost tracker (`DF-14.6-S1`). The arg-table wording "budgets … are honored end-to-end" is stronger than the `DF-14.6-S1` admission. Left as-is for consistency with the shipped Compare wording, but flagged for honest-framing.
- **MED-3 — `default_provider` positional break.** `OrchestrationLibrary("mock")` now raises `TypeError` (keyword-only). No positional callers exist in `src/` or `tests/` (verified), so non-blocking; the change is intended per D-3.

## LOW

- Mixin docstring is ~50 lines for a 10-line class (per prompt LOW); acceptable given the architectural blast radius.
- Estimator-gate citation `guardrails.py:282-285` lands inside the gate block (actual CostExceeded gate ~279-284) — close enough, not drift.
