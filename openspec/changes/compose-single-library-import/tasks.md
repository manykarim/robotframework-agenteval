## 1. Naming rule: rename keywords to the uniform prefix (keyword-namespacing)

- [ ] 1.1 Rename the 8 SkillsLibrary `@keyword(name=...)` values in `src/AgentEval/skills/library.py` to their `Skill.` forms (`Skill.Get Frontmatter`, `Skill.Get Description`, `Skill.Get Allowed Tools`, `Skill.Get Disable Model Invocation`, `Skill.Should Be Valid Frontmatter`, `Skill.Get Activation Decision`, `Skill.Get Discoverability`, `Skill.Should Activate For`); leave already-conforming `Skill.Get Activation Pass At K` / `Skill.Compare Discoverability` untouched
- [ ] 1.2 Rename SubagentsLibrary `Get Frontmatter` to `Subagent.Get Frontmatter` in `src/AgentEval/subagents/library.py`
- [ ] 1.3 Rename HooksLibrary `Get Config` to `Hook.Get Config` in `src/AgentEval/hooks/library.py`
- [ ] 1.4 Rename the 9 MCPLibrary `@keyword(name=...)` values in `src/AgentEval/mcp/library.py` to their `MCP.` forms (`MCP.Get Server Config`, `MCP.Get Tool Schema`, `MCP.Validate Tool Schema`, `MCP.Start Server`, `MCP.Connect To Server`, `MCP.Stop Server`, `MCP.List Tools`, `MCP.Call Tool`, `MCP.Get Tool Discoverability`); leave `MCP.Compare Tool Discoverability` untouched
- [ ] 1.5 Verify every renamed name keeps a multi-word post-dot portion (libdoc auto-split constraint) and that keyword bodies, arguments, tier annotations, and return types are otherwise unchanged
- [ ] 1.6 Update `@tier`-registry / `Get Keyword Tier` lookups so the renamed names resolve to the same tier integers they had before

## 2. Conventions test enforcing the rule mechanically

- [ ] 2.1 Add a unit conventions test under `tests/unit/conventions/` asserting every `@keyword` on Skills/Subagents/Hooks/MCP/Stats/Judge libraries starts with its namespace token + dot, and that Orchestration/Telemetry/Metrics/Assertions/Heatmap/top-level `AgentEval` keyword names contain no dot
- [ ] 2.2 Add a failing-case assertion (or fixture) demonstrating a namespaced library keyword lacking/using a foreign prefix trips the test with the offending name + expected prefix
- [ ] 2.3 Add a libdoc-render smoke assertion (Story 14.1 step) that no rendered keyword name contains a dot-followed-by-space (`Judge. Calibrate` auto-split signature)

## 3. Composition: add the three excluded libraries (single-library-import)

- [ ] 3.1 In `src/AgentEval/__init__.py`, add `("AgentEval.skills.library", "SkillsLibrary")`, `("AgentEval.subagents.library", "SubagentsLibrary")`, `("AgentEval.mcp.library", "MCPLibrary")` to `_SUB_LIBRARIES`
- [ ] 3.2 Replace the Story 2.2 carve-out comment block (~L92-120) with a statement of the D1 naming rule and a pointer to the collision detector
- [ ] 3.3 Refactor `_build_components()` budget forwarding to forward `max_cost_usd` + `max_runtime_seconds` to any component class that is a `_HostBudgetPlumbing` subclass (covers Stats/Judge/Skills/MCP and future adopters), keeping the explicit branches for OrchestrationLibrary (provider + budgets) and Metrics/Assertions (`allow_external_mcp_blind`); construct Subagents/Hooks with no kwargs
- [ ] 3.4 Confirm the import-time collision detector (`RuntimeError` naming both owning classes) is retained verbatim and now runs over the full 11-component composition
- [ ] 3.5 Confirm the lazy-import `ImportError`/`AttributeError` DEBUG-log swallow is retained (partial-install tolerance) and that constructor exceptions still propagate

## 4. Composition & budget-forwarding tests

- [ ] 4.1 Add a test importing only `AgentEval` and resolving one keyword from each of the 11 sub-libraries (`Skill.Get Frontmatter`, `Subagent.Get Frontmatter`, `Hook.Get Config`, `MCP.Get Server Config`, `Stat.Get Pass At K`, `Judge.Get Score`, `Send Prompt`, `Get Spans`, `Get Tool Call Count`, `Trajectory Should Match`, `Get Cohort Heatmap`)
- [ ] 4.2 Add a test asserting the composed DynamicCore keyword set equals the union of all sub-libraries' `@keyword` methods plus top-level keywords (no shadowing/dropping)
- [ ] 4.3 Add a test registering two stub components declaring the same `robot_name` and asserting `RuntimeError` names the colliding name + both classes; add a test that the full registry constructs without `RuntimeError`
- [ ] 4.4 Add a C55-closure test: `AgentEval(max_cost_usd=0.0)` → `Skill.Get Activation Decision` with a stubbed nonzero-cost adapter raises the `@guarded_fanout` cost-exceeded error
- [ ] 4.5 Add a test that under `AgentEval(max_cost_usd=1.0, max_runtime_seconds=60)` the composed MCPLibrary component carries `_max_cost_usd == 1.0` and `_max_runtime_seconds == 60.0`, and that a `_HostBudgetPlumbing` subclass is forwarded without a new class-name branch
- [ ] 4.6 Add tests for missing-module-skipped-silently and constructor-failure-propagates paths

## 5. Standalone-import support

- [ ] 5.1 Drop the `WITH NAME Skill` idiom from sub-library module docstrings (`skills/library.py`, `subagents/library.py`, `hooks/library.py`, `mcp/library.py`) and add the short double-prefix-trap warning (`Skill.Skill.Get Frontmatter` — harmless, pointless, don't do it)
- [ ] 5.2 Add a test importing `AgentEval.skills.library.SkillsLibrary max_cost_usd=2.0` (no `WITH NAME`), calling `Skill.Get Frontmatter`, and asserting `_max_cost_usd == 2.0`
- [ ] 5.3 Add a test running the same `MCP.Get Server Config` call body under `Library AgentEval` and `Library AgentEval.mcp.library.MCPLibrary` and asserting identical resolution/results with no call-site edits

## 6. Repo-wide sweep of call sites

- [ ] 6.1 Sweep every `.robot` and pytest file under `tests/` (unit conventions, tier-ACL, dogfood suites under `tests/dogfood/`, integration suites) replacing the 19 old keyword names with their prefixed forms
- [ ] 6.2 Remove any `WITH NAME` imports of AgentEval sub-libraries in tests now that composition/standalone both bake the prefix

## 7. Documentation & scaffold surfaces

- [ ] 7.1 README: replace the `WITH NAME` import blocks (L161/L176/L195 and the L46/L116 import examples) with the single `Library AgentEval` import; update keyword tables to the new prefixed names; add the one-sentence naming rule beside the import example; show module-path standalone import only in the budget-scoping subsection
- [ ] 7.2 `docs/recipes/*.md`: replace `WITH NAME`/old-name occurrences; re-run the dryrun conventions gate (`feedback_executable_doc_precheck`) so recipe code blocks still pass
- [ ] 7.3 Scaffold templates `src/AgentEval/_init/templates/example_mcp_runtime.robot` + `example_skill_validation.robot`: drop the direct-path imports so `MCP.Start Server` etc. resolve under `Library AgentEval`; add a dryrun assertion that scaffold `*** Settings ***` import only `Library AgentEval`
- [ ] 7.4 Regenerate all `docs/keywords/*.html` libdoc and run the Story 14.1 libdoc-render smoke (no auto-split names)
- [ ] 7.5 Update `docs/contracts/stability-surface.md` to the new keyword names and `docs/phase-1-5-carry-overs.md` C55 row to closure evidence
- [ ] 7.6 Add the CHANGELOG-level breaking-rename note within this change

## 8. Negative-grep gate & close-out

- [ ] 8.1 Repo-wide negative grep: zero occurrences of the 19 old keyword names as RF call sites outside git history, CHANGELOG-style notes, and carry-over prose
- [ ] 8.2 Carry-over catalog gate: grep new/changed files for `DF-X-SY` markers and verify each is in `docs/phase-1-5-carry-overs.md`
- [ ] 8.3 Caller-count check: grep any newly public helper for caller count; 0 callers → add a `DF-X-SY` caller-gap entry
- [ ] 8.4 `uv run ruff check src/ tests/`, `uv run mypy src/`, and full `uv run pytest tests/` all green
- [ ] 8.5 Run the cross-LLM review chain (Tiers 1+2, escalate to Tier 3 if degraded) per CLAUDE.md; save findings under `_bmad-output/cross-llm-reviews/`; apply HIGH findings inline before marking done
