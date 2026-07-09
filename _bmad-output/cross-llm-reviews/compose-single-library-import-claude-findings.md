# Cross-LLM adversarial review — `compose-single-library-import`

- **Reviewer:** Claude (Tier 1, `claude-opus-4-8`), adversarial code-review pass
- **Date:** 2026-07-08
- **Branch:** `implement-explore-findings` (uncommitted working tree)
- **Scope:** BREAKING refactor — 19 keyword renames to namespace-prefixed forms,
  composition of Skills/Subagents/MCP into `Library AgentEval` via `_SUB_LIBRARIES`,
  Stats/Judge subclassing `_HostBudgetPlumbing`, repo-wide call-site sweep.

## Verdict

**No HIGH or MED correctness/regression findings.** The refactor is unusually
clean and thoroughly self-tested. One LOW test-coverage observation below. I
actively tried to break it (empirical import, libdoc render, budget forwarding
probe, negative greps, `robot --dryrun` of every resolvable `.robot` suite,
recipe-dryrun + scaffold-e2e integration tests) and could not surface a real
defect. Per project honest-framing norm, I am not inflating LOW/nit items into
findings.

## What I verified empirically (not just by reading)

### 1. The 19 renames — libdoc auto-split rule + no collisions ✅
`uv run python -c "from AgentEval import AgentEval; ..."` → composed library exposes
**56 keywords**, **31 namespaced**, **zero** names containing `. ` (dot-space
auto-split signature). Every renamed post-dot portion is multi-word:
`MCP.Get Server Config`, `MCP.Start Server`, `Skill.Get Frontmatter`,
`Subagent.Get Frontmatter`, `Hook.Get Config`, etc. Import raises **no**
`RuntimeError` from the collision detector → no two components share a
`robot_name`. `Skill.Get Discoverability` vs `MCP.Get Tool Discoverability`,
`Skill.Compare Discoverability` vs `MCP.Compare Tool Discoverability` are
distinct. libdoc HTML (`docs/keywords/*.html`, regenerated today 2026-07-08)
contains the new prefixed names and **zero** stale bare `"name": "Get Server Config"`/
`"name": "Get Frontmatter"` JSON entries; `AgentEval.html` now carries the
composed `MCP.*`/`Skill.*`/`Subagent.*`/`Hook.*` keyword blobs.

### 2. Composition = exact union, no shadowing, correct owner ✅
Collision detector (`__init__.py:398`) runs over the full 11-component set and
passes. `test_full_registry_constructs_without_collision` asserts 11 components;
`test_agenteval_exposes_{mcp,skills}_library_via_dynamic_core` assert the
prefixed names are present and the bare names are gone. Because all names are
globally unique, no keyword resolves to the wrong component. `Get Keyword Tier`
(`__init__.py:462`) resolves by verbatim RF name against the live DynamicCore
registry (`self.keywords`) — rename-safe by construction, no hardcoded name
table. Grep found **no** `Get Keyword Tier <old-name>` or `keyword=<old-name>`
call sites.

### 3. Budget forwarding — no drop, no double-apply ✅
Probed `_build_components()` under `AgentEval(max_cost_usd=1.0, max_runtime_seconds=60)`:
- `OrchestrationLibrary` → 1.0/60 (explicit branch, also needs `default_provider`)
- `StatsLibrary`, `JudgeLibrary`, `SkillsLibrary`, `MCPLibrary` → 1.0/60 (unified
  `isinstance(cls, type) and issubclass(cls, _HostBudgetPlumbing)` branch)
- `HooksLibrary`, `TelemetryLibrary`, `MetricsLibrary`, `AssertionsLibrary`,
  `SubagentsLibrary`, `HeatmapLibrary` → no budget attrs

Branch ordering is correct: the `OrchestrationLibrary` / `MetricsLibrary` /
`AssertionsLibrary` explicit branches precede the `_HostBudgetPlumbing` catch-all
(`__init__.py:338-377`), so Orchestration is never mis-handled by the generic
branch. StatsLibrary/JudgeLibrary previously carried their own
positional-or-keyword `__init__(max_cost_usd, max_runtime_seconds)`; they now
inherit the mixin's **keyword-only** `__init__(*, max_cost_usd=None,
max_runtime_seconds=None, **kwargs)`. I grepped every construction site
(`StatsLibrary(`/`JudgeLibrary(`/`SkillsLibrary(`/`MCPLibrary(`) across `src/` +
`tests/` — **none** pass args positionally (all are `()` or `key=val`), so the
keyword-only tightening breaks nothing. `super().__init__(**kwargs)` terminates
cleanly at `object` for the single-mixin classes. C55 is genuinely closed:
`test_c55_skill_activation_decision_enforces_composed_budget` drives
`AgentEval(max_cost_usd=0.0)` → `Skill.Get Activation Decision` → `CostExceededError`
through the composed path (passes).

### 4. Missed call sites — none ✅
Comprehensive negative grep of the 19 old names as **indented RF keyword calls**
across `tests/**/*.robot` + `src/AgentEval/_init/` returned only test-case titles,
`[Documentation]` lines, and `...` continuation prose — **zero** actual call
sites. `robot --dryrun` of all resolvable `.robot` suites resolves every keyword:
- Scaffold templates `example_mcp_runtime.robot` + `example_skill_validation.robot` → PASS
- Unit `test_robot_integration.robot` (skills/subagents/hooks/mcp) → all keywords
  resolve (the single dryrun FAIL in the MCP suite is the pre-existing
  `transport=websocket` enum-negative test, a dryrun arg-conversion artifact, not
  a resolution failure — `MCP.Start Server` resolved).
- Dogfood parity suites (`test_stats_parity`, `test_assertions_parity`,
  `test_metrics_parity`, `test_skill_discoverability`) → 40/40 dryrun PASS.
- `tests/integration/recipes/test_all_recipes_dryrun.py` + scaffold e2e
  (`test_init_5min_path.py`, `test_init_scaffold_e2e.py`) → 29 passed / 12 skipped.

Remaining `WITH NAME` usages are all correct-by-design: `AgentEval WITH NAME
AgentEval` (self-alias) and `MetricsLibrary ... WITH NAME Metrics` (Metrics is an
unprefixed core-loop library, so it legitimately needs the alias to namespace its
calls as `Metrics.*`). `test_metrics_e2e_smoke.robot` imports `MCPLibrary` by
module path with no `WITH NAME` and calls `MCP.*` — resolves via baked prefix.

### 5. Collision detector + lazy-import tolerance over 11 components ✅
`test_registers_two_stub_components_with_same_robot_name` (dup `Dup.Keyword Name`
across two stubs) → `RuntimeError` naming the keyword + both classes.
`test_missing_module_is_skipped_silently` (ghost module) and
`test_constructor_failure_propagates` (`ValueError` from a stub `__init__`) both
pass — partial-install `ImportError`/`AttributeError` swallow retained, real
constructor bugs still propagate.

### 6. Scaffold + recipe breakage — none ✅
Scaffolds now import plain `Library AgentEval` and resolve `MCP.*`/`Skill.*`
under dryrun. Recipes 03/04/05/07 dropped `WITH NAME` module-path imports for the
single `Library AgentEval` and pass the recipe-dryrun gate.

### 7. Gates ✅
`uv run ruff check src/ tests/` clean · `uv run mypy src/` clean (109 files) ·
`scripts/check_doc_keyword_count.py` → "56 keywords across 11 libraries (README +
docs/index.md agree)" · unit conventions/mcp/skills/subagents/hooks/stats/tier-acl
+ composition = 805 passed · conformance + discoverability = 149 passed / 8 skipped.

## Findings

### LOW-1 — `test_foreign_prefix_trips_the_rule` is a tautology, not a real failing-case
- **File:** `tests/unit/conventions/test_keyword_namespace_prefix.py:147-158`
- **Category:** test-coverage
- **What:** Change task 2.2 asks for "a failing-case assertion (or fixture)
  demonstrating a namespaced library keyword lacking/using a foreign prefix trips
  the test with the offending name + expected prefix." The shipped test instead
  asserts a bare string fact — `assert not "MCP.Do Thing".startswith("Skill.")` —
  which never routes a synthetic offending keyword through the actual enforcement
  logic (`test_namespaced_libraries_prefix_every_keyword`). If someone weakened
  the real check's `startswith` predicate, this test would still pass, so it adds
  no regression protection.
- **Failure scenario:** No runtime failure. It's a coverage gap: the enforcement
  function is only ever exercised against the (currently-clean) real libraries,
  never against a known-bad input, so a regression in the checker itself is
  undetected by this "failing-case" test.
- **Severity rationale:** LOW — the *real* enforcement
  (`test_namespaced_libraries_prefix_every_keyword` + `test_prefixed_names_are_multiword_after_dot`
  + `test_every_library_class_is_categorized`) is correct and would catch an
  actual mis-prefixed keyword; the import-time collision detector is the
  load-bearing guard regardless. Non-blocking. **Suggested fix:** build a throwaway
  class with `@keyword(name="MCP.Do Thing")`, feed its `robot_name` list through
  the same `startswith(prefix)` predicate under a `SkillsLibrary` token, and
  assert the violation string is produced.

## Non-findings I explicitly checked and cleared
- Branch-ordering hazard (Orchestration mis-forwarded by the generic mixin
  branch) — cleared; explicit branch precedes catch-all.
- Positional-arg construction breaking on the keyword-only mixin `__init__` —
  cleared; no positional call sites exist.
- `@library(scope="GLOBAL")` on Judge interacting with mixin inheritance — no
  change from pre-refactor behavior (Judge was already composed).
- Double-registration ambiguity from importing composed **and** standalone in one
  RF suite — not present in any suite; the portability tests (5.3) run at the
  Python level, not by co-importing into one suite.
- Stale bare names in regenerated libdoc HTML / README tables / docs/index.md /
  stability-surface — all updated; doc-count gate agrees at 56/11.

## Pre-existing (out of scope, not introduced here)
- `docs/phase-1-5-carry-overs.md` has a blank line between the C55 and C56 table
  rows that terminates the Markdown table early. Present before this change; flag
  only for eventual cleanup.
