# Story 14-6 — `_HostBudgetPlumbing` Mixin (C20+C26+C89+C95 closure) — Cross-LLM Adversarial Review Prompt

## Context

Story 14.6 ships the **unified `_HostBudgetPlumbing` mixin** — FULL mechanism closure of Epic 11 retro Action #2 + Epic 12 retro Action #3 + Epic 13 retro Action #6 + 4 catalog rows (C20+C26+C89+C95 = 7 closures total, biggest Epic 14 blast radius). **Final Epic 14 story.**

Per CLAUDE.md ratified 3-tier cross-LLM review chain:
- **Tier 1a: Claude CLI sonnet** (`claude -p --dangerously-skip-permissions --model sonnet "<prompt>"`)
- **Tier 1b: Claude CLI opus** (`claude -p --dangerously-skip-permissions --model opus "<prompt>"`)
- **Tier 2: Codex CLI** (`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"`)
- Tier 3 (fallback): kilo/minimax-M2.7 — reserved.

## What Story 14.6 ships

- **NEW file:** `src/AgentEval/_kernel/host_budget_plumbing.py` (100+L, Apache 2.0). `_HostBudgetPlumbing` mixin with keyword-only `max_cost_usd` + `max_runtime_seconds` kwargs + cooperative `super().__init__(**kwargs)` forwarding.
- **MCPLibrary(_HostBudgetPlumbing)** inheritance + `@guarded_fanout()` added to `get_tool_discoverability` (closes C20) + `get_tool_discoverability_comparison` (closes C89).
- **SkillsLibrary(_HostBudgetPlumbing)** inheritance (closes C95; existing `@guarded_fanout()` on 2 discoverability keywords now reads real budget attrs).
- **OrchestrationLibrary(_HostBudgetPlumbing)** + cooperative ctor refactor preserving Story 4.3's `default_provider` precedent (closes C26).
- **AgentEval._build_components** passes `max_cost_usd` + `max_runtime_seconds` to OrchestrationLibrary (mirrors Stats + Judge patterns).
- **"tracked NOT enforced" carve-out docstring lines REMOVED** from `MCP.Compare Tool Discoverability` + `Skill.Compare Discoverability` — replaced with positive-framing closure notes.
- **NEW file:** `tests/unit/kernel/test_host_budget_plumbing.py` (12 tests = 4 mixin behavior + 3 subclass smoke + 4 integration contract + 1 estimator-driven pre-flight refusal stub).
- **3 libdoc HTMLs regenerated** (MCPLibrary + SkillsLibrary + OrchestrationLibrary).
- **Stability surface section** added.
- **4 catalog rows** (C20, C26, C89, C95) closed.
- **DF-14.6-S1** filed in `deferred-work.md` for Layer 1/2 live-keyword evidence work (in-flight D-6 amendment).

**1 in-flight spec amendment:** AC-14.6.8 reframed — Layer 1 pre-flight refusal via `__agenteval_test_budget__=(0.0, None)` sentinel does NOT fire without an `estimator=` callable on `@guarded_fanout()`. AC-14.6.6 only ADDS the decorator (no estimator). 4 E2E tests reframed as integration-contract tests. Live pre-flight refusal deferred to DF-14.6-S1.

## What's load-bearing — read the story spec first

| D-/L-# | Claim | What to verify |
| --- | --- | --- |
| D-1 | MCPLibrary + SkillsLibrary not in `_SUB_LIBRARIES`; operators pass budgets at RF Library import time | `grep -nE "_SUB_LIBRARIES" src/AgentEval/__init__.py` shows the exclusion. Mixin's kwargs are RF-Library-import-compatible. |
| D-2 | `@guarded_fanout` already reads via `getattr` so mixin only PROVIDES the attrs | `grep -nE 'getattr.self.*_max_cost_usd' src/AgentEval/_kernel/guardrails.py` confirms the read. No `guardrails.py` changes shipped. |
| D-3 | Keyword-only args via `*` separator | `grep -nE "def __init__.*\\*," src/AgentEval/_kernel/host_budget_plumbing.py` confirms. |
| D-4 | 2 MCP keywords got `@guarded_fanout()` added; 2 Skill + Orch keywords already had it | `grep -nE "@guarded_fanout" src/AgentEval/{mcp,skills,orchestration}/library.py` confirms 5 occurrences after Story 14.6. |
| D-5 | "tracked NOT enforced" carve-out lines removed | `grep -nE "tracked NOT enforced" src/AgentEval/` returns 0 hits post-Story-14.6. |
| D-6 (amendment) | Layer 1 pre-flight needs estimator — DF-14.6-S1 deferral | DF-14.6-S1 row exists in `deferred-work.md`; AC-14.6.8 4 E2E tests are integration-contract not pre-flight. |
| D-7 | `_SUB_LIBRARIES` exclusion preserved | `git diff HEAD~1 src/AgentEval/__init__.py` shows zero changes to `_SUB_LIBRARIES` tuple. |

## Source files to verify against

- `_bmad-output/implementation-artifacts/14-6-unified-host-instance-budget-plumbing-c20-c26-c89-c95-close.md` (story spec)
- `src/AgentEval/_kernel/host_budget_plumbing.py` (NEW mixin)
- `src/AgentEval/_kernel/guardrails.py:265-266` (the host-attr read via getattr)
- `src/AgentEval/mcp/library.py:106` (MCPLibrary inheritance + 2 `@guarded_fanout()` additions)
- `src/AgentEval/skills/library.py:100` (SkillsLibrary inheritance)
- `src/AgentEval/orchestration/library.py:111` (OrchestrationLibrary inheritance + cooperative ctor)
- `src/AgentEval/__init__.py:347-358` (`_build_components` OrchestrationLibrary branch)
- `tests/unit/kernel/test_host_budget_plumbing.py` (12 new tests)
- `docs/contracts/stability-surface.md` (NEW section)
- `docs/phase-1-5-carry-overs.md` (C20, C26, C89, C95 rows closed)
- `_bmad-output/implementation-artifacts/deferred-work.md` (DF-14.6-S1 row)
- `_bmad-output/implementation-artifacts/epic-11-retro-2026-05-27.md` L153 Action #2
- `_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md` L162 Action #3
- `_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md` L183 Action #6

## Adversarial review checklist

### HIGH — libdoc keyword-name rendering match (per Story 14.1 norm)

Story 14.6 modifies 3 libraries — re-render libdoc + verify no rendering regressions on any modified `@keyword(name=...)` surface (MCPLibrary + SkillsLibrary + OrchestrationLibrary). All `@keyword(name=...)` decorators were UNCHANGED; only inheritance + non-keyword methods changed. So libdoc smoke is expected to pass trivially.

### HIGH — cooperative-multiple-inheritance correctness

The mixin uses `super().__init__(**kwargs)` for cooperative MRO. Verify:
1. `MCPLibrary().__init__()` works (no args).
2. `MCPLibrary(max_cost_usd=10.0).__init__(max_cost_usd=10.0)` works.
3. `OrchestrationLibrary(default_provider="mock", max_cost_usd=5.0).__init__(...)` works — both args flow correctly.
4. MRO at runtime: `MCPLibrary.__mro__` shows `[MCPLibrary, _HostBudgetPlumbing, object]`.
5. Passing positional args to subclasses raises TypeError (keyword-only enforced).

### HIGH — `_max_cost_usd` + `_max_runtime_seconds` are NEW attrs on MCPLibrary + SkillsLibrary

Before Story 14.6: MCPLibrary + SkillsLibrary had NO `_max_cost_usd` attr; `@guarded_fanout`'s `getattr(self, "_max_cost_usd", None)` always fell back to None. Verify:
1. Post-Story-14.6: instantiating each library with kwargs sets the attrs.
2. Instantiating with no kwargs sets them to None (backwards-compat).
3. `@guarded_fanout` decorator on existing SkillsLibrary discoverability keywords now actually has non-None budgets if operator passes them.

### HIGH — `@guarded_fanout` decoration on MCPLibrary keywords

AC-14.6.6 adds `@guarded_fanout()` to 2 MCPLibrary keywords. Verify:
1. `grep -nE "@guarded_fanout" src/AgentEval/mcp/library.py` returns 2 occurrences.
2. Decorator ordering: `@keyword → @tier(3) → @guarded_fanout()` (matches SkillsLibrary precedent).
3. Both methods can still be called without raising on import.

### HIGH — `_build_components` OrchestrationLibrary branch correctness

The `__init__.py` change at L347-358 passes 3 args to OrchestrationLibrary. Verify:
1. The ctor accepts `default_provider`, `max_cost_usd`, `max_runtime_seconds` as keyword-only (per cooperative refactor).
2. `AgentEval(provider="mock", max_cost_usd=10.0)` propagates `max_cost_usd=10.0` to OrchestrationLibrary's mixin attrs.
3. Pre-Story-14.6 callers passing only `default_provider` still work (existing test surface).

### HIGH — citation drift

Every `Epic <N> retro Action #<M>`, `L<N>` line-range, `Story <X.Y>` reference, and `DF-/C` ID in the spec + docstrings + stability surface + catalog rows + deferred-work row MUST point to a real, current target.

- Epic 11 retro L153 Action #2 — verify.
- Epic 12 retro L162 Action #3 — verify.
- Epic 13 retro L183 Action #6 — verify.
- `_kernel/guardrails.py:265-266` — verify the `getattr` lines are at those line numbers.
- `_kernel/guardrails.py:282-285` — verify the Layer 1 estimator-gate is at those line numbers.

### HIGH — in-flight spec amendment honesty (D-6)

The D-6 in-flight amendment reframes AC-14.6.8 because Layer 1 pre-flight requires estimator. Verify:
1. The spec acknowledges the original AC wording was wrong about Layer 1 firing without estimator.
2. DF-14.6-S1 in `deferred-work.md` explicitly documents the gap.
3. The Change Log v0.2.0 calls out this 1 in-flight amendment.
4. The closure is correctly framed as "FULL mechanism, DF-14.6-S1 evidence pending" — NOT silently claimed as FULL evidence closure.

### MED — process discipline, hygiene

- **Carry-over catalog-gate self-application**: `uv run python scripts/check-catalog-references.py --all-tracked` → EXIT 0. DF-14.6-S1 ref in spec + deferred-work allowed because catalogued UPSTREAM.
- **Stability-surface registration**: complete with mixin + 3 library inheritance + constructor contract + honest-framing constraints.
- **All 5 fan-out keywords have `@guarded_fanout` post-Story-14.6**: `grep -nE "@guarded_fanout" src/AgentEval/{mcp,skills,orchestration}/library.py | wc -l` returns ≥5.
- **Cooperative MRO doesn't break existing tests**: `tests/unit/orchestration/` + `tests/unit/skills/` + `tests/unit/mcp/` all pass.

### MED — test coverage gaps

- The 4 "integration contract" tests verify host attrs are readable via `getattr` — they do NOT verify decorator actually invokes `getattr` at runtime. Verify via a deeper test that the @guarded_fanout wrapper code path is exercised.
- The 1 estimator-driven pre-flight test uses a stub host — verify the stub correctly inherits the mixin + exercises the budget read path.
- Mid-run Layer 2 cost meter coverage is intentionally absent (DF-14.6-S1 deferral) — confirm DF-14.6-S1 lists this as the gap.

### LOW — wording, optional siblings, style

- The mixin's docstring is verbose — 50+ lines for a 10-line class. Could be tighter.
- The `OrchestrationLibrary` ctor docstring repeats Story 4.3 history at length — could be condensed.
- The stability surface section's honest-framing constraint note is the longest in the file — proportional to the architectural complexity but could be trimmed.

## Output format

For each finding cite **file + line + concrete fix**. Group as HIGH / MED / LOW.

## Save findings to

- Claude sonnet → `_bmad-output/cross-llm-reviews/story-14-6-claude-sonnet-findings.md`
- Claude opus → `_bmad-output/cross-llm-reviews/story-14-6-claude-opus-findings.md`
- Codex → `_bmad-output/cross-llm-reviews/story-14-6-codex-findings.md`
