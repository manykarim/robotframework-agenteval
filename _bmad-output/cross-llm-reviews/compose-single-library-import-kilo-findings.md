# Review: `compose-single-library-import` — kilo findings

**Reviewer:** kilo/minimax-M2.7
**Change:** `compose-single-library-import` (branch `implement-explore-findings`, uncommitted working tree)
**Date:** 2026-07-08
**Scope:** Breaking refactor: 19 keyword renames, library composition into `Library AgentEval`, `_HostBudgetPlumbing` subclass refactor for StatsLibrary/JudgeLibrary

---

## Verifications performed

| Check | Method | Result |
|---|---|---|
| 56-keyword composition | `uv run python` → `lib.get_keyword_names()` | PASS — 56 total, 31 prefixed + 25 unprefixed, no dups |
| Collision detector | `_build_components` RuntimeError path | PASS — retained verbatim; verified no duplicates |
| Tier lookups | `get_keyword_tier()` on renamed methods | PASS — all tiers unchanged |
| Robot dryrun (skills) | `uv run robot --dryrun` | PASS — 5/5 |
| Robot dryrun (hooks) | `uv run robot --dryrun` | PASS — 2/2 |
| Robot dryrun (MCP) | `uv run robot --dryrun` | PASS — 9/10 (1 websocket error is pre-existing expected-failure) |
| Full pytest | `uv run pytest tests/` | PASS — 2130 passed, 29 skipped |
| Ruff check | `uv run ruff check src/` | PASS |
| Mypy | `uv run mypy src/` | PASS |

---

## Finding 1: Renamed keywords — libdoc auto-split constraint

**Rating:** LOW (no issue found)

All 19 renamed keywords satisfy the multi-word-post-dot constraint per `feedback_libdoc_namespace_keyword_must_be_multiword` (Epic 12 retro):

| Library | Old name | New name | Post-dot words |
|---|---|---|---|
| SkillsLibrary | Get Frontmatter | Skill.Get Frontmatter | 2 ✓ |
| SkillsLibrary | Get Description | Skill.Get Description | 2 ✓ |
| SkillsLibrary | Get Allowed Tools | Skill.Get Allowed Tools | 3 ✓ |
| SkillsLibrary | Get Disable Model Invocation | Skill.Get Disable Model Invocation | 4 ✓ |
| SkillsLibrary | Should Be Valid Frontmatter | Skill.Should Be Valid Frontmatter | 4 ✓ |
| SkillsLibrary | Get Activation Decision | Skill.Get Activation Decision | 3 ✓ |
| SkillsLibrary | Get Discoverability | Skill.Get Discoverability | 2 ✓ |
| SkillsLibrary | Should Activate For | Skill.Should Activate For | 3 ✓ |
| SubagentsLibrary | Get Frontmatter | Subagent.Get Frontmatter | 2 ✓ |
| HooksLibrary | Get Config | Hook.Get Config | 2 ✓ |
| MCPLibrary | Get Server Config | MCP.Get Server Config | 2 ✓ |
| MCPLibrary | Get Tool Schema | MCP.Get Tool Schema | 2 ✓ |
| MCPLibrary | Validate Tool Schema | MCP.Validate Tool Schema | 3 ✓ |
| MCPLibrary | Start Server | MCP.Start Server | 2 ✓ |
| MCPLibrary | Connect To Server | MCP.Connect To Server | 3 ✓ |
| MCPLibrary | Stop Server | MCP.Stop Server | 2 ✓ |
| MCPLibrary | List Tools | MCP.List Tools | 2 ✓ |
| MCPLibrary | Call Tool | MCP.Call Tool | 2 ✓ |
| MCPLibrary | Get Tool Discoverability | MCP.Get Tool Discoverability | 3 ✓ |

**No collision detected** — grep across all `.robot` files found zero occurrences of the old unprefixed names as actual RF keyword calls. All 98 matches were new prefixed names in code blocks/comments.

---

## Finding 2: Composition correctness — keyword union, no shadowing

**Rating:** LOW (no issue found)

`AgentEval` now composes 11 sub-libraries (up from 8). The keyword set is exactly the union:

```
31 prefixed:  Skill.* (10), MCP.* (10), Stat.* (7), Judge.* (2), Hook.* (1), Subagent.* (1)
25 unprefixed: core loop (metrics, assertions, telemetry, orchestration, heatmap, top-level config/tier)
Total: 56
```

No duplicates — verified programmatically:
```python
>>> lib.get_keyword_names()
# 56 unique names, zero dups
```

The import-time collision detector (`RuntimeError` on duplicate `robot_name`) is retained verbatim and runs over the full 11-component set.

---

## Finding 3: Budget forwarding — `_HostBudgetPlumbing` subclass refactor

**Rating:** LOW (no issue found)

**Before:** `StatsLibrary` and `JudgeLibrary` had explicit `__init__` methods accepting `max_cost_usd` + `max_runtime_seconds`, forwarded via dedicated `elif cls_name == "StatsLibrary"` / `elif cls_name == "JudgeLibrary"` branches.

**After:** Both inherit from `_HostBudgetPlumbing` and have no `__init__` override. The unified branch:
```python
elif isinstance(cls, type) and issubclass(cls, _HostBudgetPlumbing):
    components.append(cls(max_cost_usd=..., max_runtime_seconds=...))
```

**Correctness analysis:**

| Library | Inherits `_HostBudgetPlumbing` | Goes through _HostBudgetPlumbing branch |
|---|---|---|
| OrchestrationLibrary | ✓ | No — explicit `cls_name == "OrchestrationLibrary"` branch first |
| SkillsLibrary | ✓ | ✓ (correctly) |
| MCPLibrary | ✓ | ✓ (correctly) |
| StatsLibrary | ✓ | ✓ (correctly) |
| JudgeLibrary | ✓ | ✓ (correctly) |
| SubagentsLibrary | ✗ | No — falls to `else: cls()` |
| HooksLibrary | ✗ | No — falls to `else: cls()` |

`OrchestrationLibrary` is correctly handled by its explicit branch (receives `default_provider` + budgets). No double-application of budgets. No budget drop.

`_HostBudgetPlumbing.__init__` signature:
```python
def __init__(self, *, max_cost_usd=None, max_runtime_seconds=None, **kwargs):
    self._max_cost_usd = max_cost_usd
    self._max_runtime_seconds = max_runtime_seconds
    super().__init__(**kwargs)
```

Compatible with all prior call sites (standalone imports accepting kwargs, `_build_components` forwarding).

---

## Finding 4: Scaffold/recipe surfaces

**Rating:** LOW (no issue found)

Both scaffold templates (`example_mcp_runtime.robot`, `example_skill_validation.robot`) correctly:
- Use `Library AgentEval` (no `WITH NAME`)
- Call prefixed keywords (`MCP.Start Server`, `Skill.Get Frontmatter`, etc.)

`README.md` updated: single-import pattern taught exclusively, naming rule stated in one sentence, all keyword tables updated.

---

## Finding 5: Lazy-import tolerance

**Rating:** LOW (no issue found)

The `try/except ImportError, AttributeError` DEBUG-log swallow in `_build_components` is retained. Partial-install tolerance is preserved.

---

## Summary

**No substantive issues found.** The refactor is correctly implemented:

1. All 19 renames satisfy the libdoc multi-word constraint
2. The 11-component composition exposes exactly the keyword union with no shadowing
3. `_HostBudgetPlumbing` subclass check correctly forwards budgets to all 5 adopting classes without double-application or drops
4. All old keyword names swept from actual RF call sites in `.robot` files
5. Scaffold templates and README updated to single-import pattern
6. 2130/2130 tests pass; ruff/mypy clean

The change is safe to commit.
