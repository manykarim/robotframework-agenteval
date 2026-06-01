OpenAI Codex v0.133.0
--------
workdir: /home/many/workspace/robotframework-agenteval
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019e8346-2ba1-7231-98f3-3b2f4835b75b
--------
user
# Adversarial Code Review — Story 13.5: Skill.Compare Discoverability (PRD FR4c) — FINAL Epic 13 Story

You are a SENIOR REVIEWER. Find REAL bugs, REAL spec drift, REAL correctness defects in Story 13.5.

## Project context

- Story 13.5 is the symmetric Skill-domain analog of Story 13.3 (MCP).
- Builds on Story 7.2 (`Skill.Get Discoverability`), Story 13.1 (Mann-Whitney + advanced extra), Story 13.3 (MCP variant + helper extraction pattern), Story 13.4 (CohortHeatmap.from_X classmethod + cells-as-omission).
- Skill domain extends with 2 extra delta metrics (false_activation_rate_delta + missed_activation_rate_delta).
- Story file: `_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md`
- Diff at `/tmp/story-13-5-review.diff` (~1700 lines).

## Specific probes

1. **Helper extraction parity**: refactored existing `SkillsLibrary.get_discoverability` to call `run_single_adapter_skill_discoverability`. Run all 86 existing Story 7.2 skill tests at `tests/unit/skills/test_discoverability.py` against refactored code — do they all pass?
2. **`@guarded_fanout()` posture**: dev verified SkillsLibrary host attrs fall back to None via getattr. Confirm — does `Skill.Compare Discoverability` work without crashing when `_max_cost_usd` doesn't exist on `self`?
3. **N=2/N=3 pairwise count + ordering**: itertools.combinations preserves input order. Verify `["a", "b", "c"]` produces keys `["a_vs_b", "a_vs_c", "b_vs_c"]`.
4. **False/missed-activation delta direction convention**: dev's D-9 says `false_activation_rate_delta = a - b` means "a is WORSE" when positive. Verify the integration test asserts the correct direction.
5. **Comparison-level wall-clock**: dev claims Story 13.3 HIGH-A fix applied — measure end-to-end `compare_t_start` (NOT MAX of per-adapter). Verify the code path.
6. **Pre-flight extras gate ordering**: gate must run BEFORE the per-adapter fan-out (D-6 fail-fast). Verify the keyword body ordering.
7. **Cross-consistency 4-way validator**: `SkillDiscoverabilityComparisonResult.__post_init__` checks adapters vs per_adapter_results.keys() vs heatmap.models vs summary.activation_accuracy_per_adapter.keys(). Verify all 4 checks fire on respective mismatches.
8. **Story 13.4 L-7 cells-as-omission**: `CohortHeatmap.from_skill_comparison` builds cells tuple. Verify no explicit `None` cell values are emitted.
9. **Recipe #4 `robot --dryrun` claim**: dev claims clean. Verify by re-running.
10. **C95-C98 carry-over completeness**: 4 carry-overs catalogued. Verify each row has all 7 columns (ID/Description/Source/Priority/Effort/Owner/AC).

## Output format

For each finding:

```
### [HIGH/MED/LOW]-N: <title>
**File:** `<path>:<line>`
**Issue:** <2-3 sentences>
**Evidence:** <code/test output>
**Fix:** <concrete suggestion>
```

End with: `**Total: X HIGH + Y MED + Z LOW**`.

---

## Diff to review:

```diff
diff --git a/_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md b/_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md
new file mode 100644
index 0000000..a364e7e
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md
@@ -0,0 +1,361 @@
+# Story 13.5: Compare Skill Discoverability Cross-Adapter (FR4c)
+
+Status: review
+
+## Story
+
+As **Devon (Agent Surface Author)** doing cross-runtime skill activation analysis,
+I want `Skill.Compare Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per PRD FR4c,
+So that I can claim "skill X is reliably activated by Claude AND GPT AND Copilot" with empirical evidence — symmetric to Mei's cross-adapter Tool Discoverability (Story 13.3), the killer Devon Phase 2 feature, AND closing Epic 13.
+
+## Pre-create-story drift check (55th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+11 drifts caught — 6 fresh decisions from spec analysis + 5 UPSTREAM lessons from Stories 13.1 + 13.2 + 13.3 + 13.4 reviews. **100% real-drift catch rate maintained through 54 prior uses.** Last Epic 13 story.
+
+- **D-1 (HIGH — return-type shape per epic L2219):** Epic L2219: "per-adapter task-level activation results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data + per-adapter false-activation/missed-activation rate comparison." **Decision:** ship `SkillDiscoverabilityComparisonResult` frozen dataclass at `src/AgentEval/skills/types.py` (alongside existing `SkillDiscoverabilityResult`) symmetric to Story 13.3's `DiscoverabilityComparisonResult`, plus 2 extra cross-adapter delta metrics for false-activation + missed-activation rates:
+
+  ```python
+  @dataclass(frozen=True)
+  class SkillDiscoverabilityComparisonResult:
+      adapters: tuple[str, ...]
+      per_adapter_results: Mapping[str, SkillDiscoverabilityResult]
+      cross_adapter_deltas: Mapping[str, "SkillPairwiseAdapterDelta"]
+      heatmap: CohortHeatmap
+      summary: "SkillDiscoverabilityComparisonSummary"
+
+  @dataclass(frozen=True)
+  class SkillPairwiseAdapterDelta:
+      adapter_a: str
+      adapter_b: str
+      pass_at_k_delta: float                                              # mean(per-task pass_at_k for a) - mean(...for b)
+      pass_at_k_mann_whitney_result: MannWhitneyResult                    # Mann-Whitney U on per-task pass_at_k lists
+      false_activation_rate_delta: float                                  # summary.false_activation_rate(a) - (b)
+      missed_activation_rate_delta: float                                 # summary.missed_activation_rate(a) - (b)
+      significant_at_alpha_05: bool                                       # mwu.p_value < 0.05; nan-aware per Story 13.3
+
+  @dataclass(frozen=True)
+  class SkillDiscoverabilityComparisonSummary:
+      total_cost_usd: float
+      total_runtime_seconds: float
+      activation_accuracy_per_adapter: Mapping[str, float]
+      best_adapter: str                                                   # argmax(activation_accuracy)
+      worst_adapter: str                                                  # argmin(activation_accuracy)
+  ```
+
+  Per Story 13.3 D-2 verbatim shape + Skill-domain extension. `__post_init__` defensive copies + cross-consistency validators (mirrors Story 13.3 + applies Story 13.4 Codex HIGH-2/HIGH-3 fixes: validate best/worst match max/min + summary.activation_accuracy_per_adapter.keys() match adapters).
+
+- **D-2 (HIGH — `@guarded_fanout` epic claim vs SkillsLibrary architecture):** Epic L2223: "the keyword inherits `@guarded_fanout` cost/runtime guardrails identically to Story 13.3." **HOWEVER** Story 13.3 explicitly REMOVED `@guarded_fanout` per the MCPLibrary architectural carve-out (DF-4.4-S1 / C20: MCPLibrary excluded from `_SUB_LIBRARIES`, no `_max_cost_usd` plumbing). **But** SkillsLibrary's existing `Get Discoverability` DOES have `@guarded_fanout()` per `library.py:353`. Why? `SkillsLibrary` may have different host-instance plumbing — let me check. **Decision:** ship `@guarded_fanout()` on the new keyword IF the existing `Get Discoverability` ships it cleanly (preserves epic L2223's intent of decorator-inheritance parity); otherwise apply the same MCPLibrary-style carve-out. Run `grep -n "guarded_fanout\|_max_cost" src/AgentEval/skills/library.py` at dev-start to verify; ship per the existing pattern. The in-flight amendment ratifies the actual posture rather than a fictitious symmetry.
+
+- **D-3 (HIGH — method-name verb-allowlist per Story 13.1 + 13.3 precedent):** RF keyword name `Skill.Compare Discoverability` per epic L2212. Python method name's first underscore-separated token must be in `_VERB_ALLOWLIST` (per `tests/unit/conventions/test_keyword_name_idiom.py`). `compare_discoverability` → first token `compare` is NOT in allowlist. **Decision:** name the Python method `get_discoverability_comparison` — first token `get` IS in allowlist + describes "operator gets back a comparison result" (matches Story 13.3's `get_tool_discoverability_comparison` precedent verbatim).
+
+- **D-4 (HIGH — `[agenteval-advanced]` extras gate via stats module-attr read):** Mann-Whitney U requires scipy + numpy (Story 13.1 `[agenteval-advanced]` extra). **Decision:** mirror Story 13.3 in-flight amendment #2 — read the gate via `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` (NOT `from X import Y` which captures stale value across pytest session reload). Direct raise at the call site per Story 13.3's AC-13.3.4 decision (b): `"Skill.Compare Discoverability: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`.
+
+- **D-5 (HIGH — `CohortHeatmap.from_comparison` extension for skill comparison):** Story 13.3 shipped `CohortHeatmap.from_comparison(DiscoverabilityComparisonResult)`. Story 13.5 needs the SAME multi-column heatmap shape but from `SkillDiscoverabilityComparisonResult`. **Decision:** ADD a NEW classmethod `CohortHeatmap.from_skill_comparison(result: SkillDiscoverabilityComparisonResult) -> CohortHeatmap` at `_heatmap/models.py` — symmetric to `from_comparison` but reads `result.per_adapter_results[adapter].per_task_results[i].pass_at_k` (the Skill domain's pass_at_k field) instead of the MCP domain's `pass_rate` property. Alternative considered (rejected): unify the two classmethods via a Protocol-typed input — too much abstraction for two siblings. Two classmethods is straightforward.
+
+- **D-6 (HIGH — `mcp_server` parameter NOT applicable; spec omission):** Story 13.3's `mcp_server` arg has no Skill equivalent — skills don't attach to MCP servers; they're activation-pattern files in agent contexts. **Decision:** Story 13.5 keyword signature omits `mcp_server`; mirrors Story 7.2's `Skill.Get Discoverability` signature (skill=`<path>` + tasks=`<yaml>` + adapter + trials_per_task + model + **kwargs). Spec text in epic L2218 confirms this: "`skill=... tasks=... adapters=[...]`" — no MCP arg. Document the asymmetry vs Story 13.3 in the keyword docstring.
+
+- **D-7 (MED — Recipe #4 update epic claim vs Story 12.3 reality):** Epic L2225: "Recipe Gallery #4 is updated (during this story or Story 12.3 — whichever lands later) with a Phase 2 cross-adapter Skill Discoverability example." Story 12.3 already updated Recipe #4 with the Tier-2 Judge integration. **Decision:** Story 13.5 ADDS a `## Phase 2 cross-adapter Skill Discoverability` section to `docs/recipes/04-skill-author-stacked-validation.md` after the existing Phase 2 Status section. The section ships a snippet showing `Skill.Compare Discoverability` invocation against 2+ Tier-1 adapters via Mock provider (zero real-API cost per epic L2221). `robot --dryrun` smoke per `feedback_executable_doc_precheck`.
+
+- **D-8 (MED — dogfood deferral per cost prudence):** Epic L2227: "dogfood: `robotframework-agentskills` cross-adapter Skill Discoverability suite is added to that repo's CI matrix using the Mock provider (real-API cross-adapter runs are out of routine CI scope due to cost; a separate `weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a budget)." This requires a PR to the `robotframework-agentskills` downstream repo — outside agenteval's git scope. **Decision:** ship the keyword + integration test in agenteval (this story), defer the agentskills downstream-PR work to a new Phase-1.5 carry-over DF-13.5-S4 (catalog row added per AC-13.5.11) for the dogfood adoption. Mirrors Story 9.2's "C66 dogfood adoption + 7-day monitoring" deferral pattern.
+
+- **D-9 (LOW — `false_activation_rate` / `missed_activation_rate` direction convention):** existing `SkillDiscoverabilityTaskSummary.false_activation_rate` is "fraction of decoy-task trials where skill incorrectly activated" — higher = worse. `missed_activation_rate` is "fraction of should-activate-task trials where skill failed to activate" — also higher = worse. **Decision:** `SkillPairwiseAdapterDelta.false_activation_rate_delta = a - b` means "by how much MORE often adapter_a falsely activates than adapter_b" — positive = adapter_a is WORSE. Same for `missed_activation_rate_delta`. Document the convention in the dataclass docstring. NOT inverted vs the more intuitive "delta of accuracy" — the field names match the underlying summary metrics directly for greppability.
+
+- **D-10 (LOW — carry-over catalog gate UPSTREAM Stories 13.1+13.2+13.3+13.4, 36th consecutive):** Anticipated Phase-2.5 carry-overs for Story 13.5:
+  - **DF-13.5-S1 (Phase-2.5):** `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability` — same architectural gap as DF-13.3-S1 / C89 + DF-4.4-S1 / C20 IF the existing skills carve-out matches MCP's.
+  - **DF-13.5-S2 (Phase-2.5):** Real per-adapter MCP attachment gated on C72 / C68 / C69 / C73 / C75 (same chain as DF-13.3-S2 / C90 — though skills don't typically attach MCP, future skills CAN call MCP-bridged tools).
+  - **DF-13.5-S3 (Phase-2.5):** Multi-pairwise Bonferroni/Holm correction (same as DF-13.3-S3 / C91 — applies to ALL cross-adapter pairwise comparison surfaces).
+  - **DF-13.5-S4 (Phase-1.5):** `robotframework-agentskills` cross-adapter Skill Discoverability dogfood CI matrix integration + `weekly-cross-adapter-discoverability.yml` real-API budget workflow (per D-8 epic L2227 dogfood mandate).
+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson: catalog C95 + C96 + C97 + C98 BEFORE invoking `/bmad-code-review`.
+
+## Cross-story upstream lessons from Stories 13.1 + 13.2 + 13.3 + 13.4 reviews
+
+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; 13.4 → 13.5 same-epic transition):
+
+- **L-1 applied (stability-surface UPSTREAM)**: register `Skill.Compare Discoverability` keyword + `SkillDiscoverabilityComparisonResult` + `SkillPairwiseAdapterDelta` + `SkillDiscoverabilityComparisonSummary` + `CohortHeatmap.from_skill_comparison` in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.5.10. Verify via grep before flipping to done.
+- **L-2 applied (extras-gate test split)**: ImportError-gate tests in a SEPARATE file (`test_skill_comparison_extras_gate.py`) with NO module-top `importorskip`; happy-path tests gated by `pytest.importorskip("scipy")`. Direct port of Story 13.3 split pattern.
+- **L-3 applied (Tier classification rationale)**: `@tier(3)` per fan-out semantics — stochastic by tier definition; Story 13.1 HIGH-C seed-required FR31a concern doesn't apply. Document in keyword docstring.
+- **L-4 applied (empirical correctness verification)**: integration test asserts CONCRETE numerical outcomes (3 stub adapters with KNOWN-different activation patterns produce expected ranking + p-value sign + false-activation-rate ordering + missed-activation-rate ordering). NOT just "the keyword ran without error."
+- **L-5 applied (docstring precision)**: keyword docstring names the EXACT helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u` (per Story 13.3 precedent) and Browser-Library-convention anchor test asserts "Skill.Compare Discoverability" + "FR4c" + "Phase-2" + "Mann-Whitney U" in docstring.
+
+Plus Story 13.4 cross-story specific lessons:
+- **L-6 (Story 13.4 Codex HIGH-2)**: NO orientation drift in PRD for FR4c (FR4c text doesn't pin rows/cols since the heatmap is reused from FR55 which Story 13.4 amended). No PRD amendment needed beyond the standard surface-add.
+- **L-7 (Story 13.4 Opus HIGH-1 + Codex MED-1 cells-type contract)**: when building `CohortHeatmap.from_skill_comparison`, represent missing cells via OMISSION from the `cells` tuple — NOT explicit `None`. Maintains the public `cells: tuple[tuple[str, str, float], ...]` type contract.
+
+## Acceptance Criteria
+
+### AC-13.5.1 — `Skill.Compare Discoverability` keyword on `SkillsLibrary`
+
+`src/AgentEval/skills/library.py` extends `SkillsLibrary` with new `@keyword + @tier(3)`-decorated method (placed AFTER `get_discoverability`):
+
+```python
+@keyword(name="Skill.Compare Discoverability")
+@tier(3)
+@guarded_fanout()  # OR no @guarded_fanout if existing skills uses the same carve-out — confirm at dev-start per D-2
+def get_discoverability_comparison(
+    self,
+    skill: str | Path = "",
+    tasks: str | Path = "",
+    adapters: list[str] | None = None,
+    trials_per_task: int = 3,
+    max_cost_usd: float = 20.00,
+    max_runtime_seconds: float | None = None,
+    model: str | None = None,
+    polling: float | None = None,
+    **kwargs: Any,
+) -> SkillDiscoverabilityComparisonResult: ...
+```
+
+Signature notes:
+- `adapters` REQUIRED (no sensible default); ≥2 elements required (raises `ValueError`).
+- `skill` + `tasks` REQUIRED.
+- `max_cost_usd` default `20.00` per epic L2218 verbatim (4× single-adapter, mirroring Story 13.3 N=3 typical).
+- `polling` REJECTED — raises `PollingDisallowedError` per FR28 (mirrors existing `Get Discoverability`).
+
+Implementation:
+1. Validate args (incl. ≥2 distinct adapters + polling rejection).
+2. Pre-flight `_stats_lib._ADVANCED_AVAILABLE` gate per D-4.
+3. Parse skill frontmatter ONCE (shared across adapters).
+4. Load tasks YAML ONCE.
+5. Extract per-adapter logic into a shared helper at `skills/_internal.py` (mirrors Story 13.3 D-6 helper extraction); refactor existing `get_discoverability` to call the helper.
+6. For each adapter: call the helper.
+7. Build pairwise deltas (all C(N, 2) ordered pairs) via `compute_mann_whitney_u(rates_a, rates_b)` where `rates_a/b` are the per-task `pass_at_k` lists.
+8. Build `CohortHeatmap.from_skill_comparison(result)` via D-5.
+9. Return `SkillDiscoverabilityComparisonResult(...)`.
+
+### AC-13.5.2 — 3 new frozen dataclasses
+
+`src/AgentEval/skills/types.py` appends `SkillDiscoverabilityComparisonResult` + `SkillPairwiseAdapterDelta` + `SkillDiscoverabilityComparisonSummary` per D-1 shape. `__post_init__` validators (applying Story 13.4 HIGH-B + HIGH-C lessons):
+
+- `SkillDiscoverabilityComparisonResult`: `len(adapters) >= 2`; `set(adapters) == set(per_adapter_results.keys())`; `set(adapters) == set(heatmap.models)`; `set(adapters) == set(summary.activation_accuracy_per_adapter.keys())`.
+- `SkillPairwiseAdapterDelta`: `adapter_a != adapter_b`; deltas in `[-1, 1]` for pass_at_k_delta + false_activation_rate_delta + missed_activation_rate_delta; nan-aware `significant_at_alpha_05` consistency check (per Story 13.3 nan handling).
+- `SkillDiscoverabilityComparisonSummary`: `best_adapter` in keys AND has the max `activation_accuracy`; `worst_adapter` in keys AND has the min.
+
+`__all__` updated to export the 3 new classes.
+
+### AC-13.5.3 — `CohortHeatmap.from_skill_comparison` classmethod
+
+`src/AgentEval/_heatmap/models.py` adds `from_skill_comparison(result)` classmethod symmetric to `from_comparison`. Reads `result.per_adapter_results[adapter].per_task_results[i].pass_at_k` (NOT `pass_rate` property). Columns = adapter names; rows = task IDs (union preserving first-encounter order). Per L-7: missing cells omitted from `cells` tuple, not explicit `None`.
+
+### AC-13.5.4 — `_run_single_adapter_skill_discoverability` helper at `src/AgentEval/skills/_internal.py`
+
+Extract the per-adapter body of `Skill.Get Discoverability` into a shared pure helper:
+
+```python
+def run_single_adapter_skill_discoverability(
+    *,
+    skill_name: str,
+    task_list: list[SkillDiscoverabilityTask],
+    adapter: str,
+    model: str | None,
+    trials_per_task: int,
+    extra_adapter_kwargs: dict[str, Any],
+    t_start: float,
+) -> SkillDiscoverabilityResult: ...
+```
+
+Mirrors Story 13.3 AC-13.3.6 pattern verbatim. Existing `get_discoverability` is refactored to call the helper after its own arg validation + skill+tasks loading. Behavior identity verified by Story 7.2's existing tests passing unchanged.
+
+### AC-13.5.5 — Method-name + signature symmetric to Story 13.3
+
+Python method name `get_discoverability_comparison` (per D-3 verb-allowlist conformance). RF keyword name `Skill.Compare Discoverability` per epic L2212.
+
+### AC-13.5.6 — Unit tests at `tests/unit/skills/test_comparison.py` (≥18 tests)
+
+NEW file. Coverage:
+- **Dataclass validators (8 tests)**: `<2` adapters; key mismatches (adapters vs per_adapter / heatmap / summary); `adapter_a == adapter_b`; delta out-of-range; nan-aware significance inconsistency; best/worst inconsistency (HIGH-B from Story 13.4); unknown best/worst (HIGH-C from Story 13.4).
+- **`CohortHeatmap.from_skill_comparison` (3 tests)**: 2-adapter; 3-adapter; per-task pass_at_k dispatched to correct cell.
+- **Pairwise delta computation (3 tests)**: 2 adapters → 1 pairwise; 3 adapters → 3 pairwise; pairwise key ordering deterministic.
+- **Mann-Whitney + significance (2 tests)**: known-different distributions → p<0.05; identical → p>0.5 + nan handling.
+- **False-activation + missed-activation deltas (2 tests)**: stub a with should_activate=True/all-pass + stub b with should_activate=True/all-fail → missed_activation_rate_delta(b - a) > 0; decoy task with stub a all-pass (should be false-activation) + stub b all-correct-no → false_activation_rate_delta(a - b) > 0.
+
+Plus 4 ImportError-gate tests at `tests/unit/skills/test_comparison_extras_gate.py` (per L-2 lesson; NO top-level `importorskip`):
+- `test_compare_keyword_raises_import_error_when_advanced_extra_missing`.
+- `test_compare_keyword_import_error_message_contract`.
+- `test_compare_keyword_arg_validation_runs_before_extras_gate`.
+- `test_skill_comparison_schema_importable_without_extra`.
+
+### AC-13.5.7 — Integration test at `tests/integration/skills/test_skill_compare_e2e.py`
+
+NEW file. Per epic L2221: "Mock provider for all adapters (zero real-API cost during CI)." Per L-4 lesson: assert CONCRETE numerical outcomes. 3 stub adapters via `register_adapter()`:
+- `skill_compare_stub_a` → activates skill on EVERY trial (100% activation; 0% false-activation; 0% missed-activation).
+- `skill_compare_stub_b` → activates skill on alternating trials (50% activation).
+- `skill_compare_stub_c` → NEVER activates skill (0% activation; 100% missed-activation when should_activate=True).
+
+Assertions:
+- per-adapter activation_accuracy: a=1.0 b=0.5 c=0.0.
+- summary.best_adapter == "skill_compare_stub_a"; worst_adapter == "skill_compare_stub_c".
+- 3 pairwise deltas; `a_vs_c` significant at α=0.05.
+- heatmap.models == ("skill_compare_stub_a", "skill_compare_stub_b", "skill_compare_stub_c").
+- Per epic L2221 zero-cost requirement (Story 13.3 Codex MED-1 lesson): `cost_per_call=0.0` on stubs; total_cost_usd == 0.0.
+
+Plus 2 arg-validation integration tests: `<2` adapters rejected + duplicate names rejected.
+
+### AC-13.5.8 — Recipe Gallery #4 update per D-7 + epic L2225
+
+`docs/recipes/04-skill-author-stacked-validation.md` extends with `## Phase 2 cross-adapter Skill Discoverability` section AFTER the existing `## Phase 2 Status` section. Section ships:
+- One paragraph motivation (closes Devon's Phase 2 cross-adapter analysis loop).
+- One RF snippet:
+  ```robot
+  *** Settings ***
+  Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
+
+  *** Test Cases ***
+  Skill X Is Reliably Activated Across Claude And OpenAI
+      ${comparison}=    Skill.Compare Discoverability
+      ...    skill=${CURDIR}/skills/web-search.md
+      ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
+      ...    adapters=${{['claude_code_cli', 'codex_cli']}}
+      ...    trials_per_task=5
+      ...    max_cost_usd=10.00
+      Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
+      Should Be True    ${comparison.summary.activation_accuracy_per_adapter['codex_cli']} >= 0.7
+  ```
+- Cross-link to Story 13.5 + DF-13.5-S4 dogfood deferral.
+
+Per `feedback_executable_doc_precheck`: `robot --dryrun` smoke verified clean.
+
+### AC-13.5.9 — Refactor verification + Recipe #4 dryrun
+
+Story 7.2's existing tests at `tests/unit/skills/test_discoverability_keyword.py` MUST pass unchanged (refactor behavior identity per Story 13.3 AC-13.3.9 pattern). Net test delta: +24 new (no test renames or removals).
+
+### AC-13.5.10 — `docs/contracts/stability-surface.md` per L-1 lesson
+
+NEW subsection `### Cross-Adapter Skill Discoverability Surface (Phase-2 — FR4c)`:
+
+- `Skill.Compare Discoverability` keyword + Python `SkillsLibrary.get_discoverability_comparison` — `provisional` label.
+- `AgentEval.skills.types.SkillDiscoverabilityComparisonResult` + `SkillPairwiseAdapterDelta` + `SkillDiscoverabilityComparisonSummary` — `provisional` label.
+- `CohortHeatmap.from_skill_comparison` classmethod — `provisional` label.
+- `[agenteval-advanced]` extra requirement bubble-up — mirrors Story 13.3 entry.
+
+### AC-13.5.11 — Phase-1.5 carry-over catalog UPSTREAM (36th consecutive)
+
+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 4 new rows BEFORE invoking `/bmad-code-review`:
+- **C95** `DF-13.5-S1` — Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability`.
+- **C96** `DF-13.5-S2` — Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools.
+- **C97** `DF-13.5-S3` — Phase-2.5: Multi-pairwise Bonferroni/Holm correction.
+- **C98** `DF-13.5-S4` — Phase-1.5: `robotframework-agentskills` cross-adapter dogfood CI matrix + `weekly-cross-adapter-discoverability.yml` real-API budget workflow (per epic L2227).
+
+### AC-13.5.12 — All-gates pass + libdoc regen
+
+- `uv run pytest tests/`: ≥24 net new tests; existing 1912 still pass.
+- `uv run ruff check src/ tests/` clean.
+- `uv run mypy src/` clean.
+- libdoc regen: `uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary docs/keywords/SkillsLibrary.html` (per Story 13.3 + 13.4 precedent).
+
+### AC-13.5.13 — Sprint-status
+
+`13-5-compare-skill-discoverability-cross-adapter-fr4c: done` (after review); `last_updated: 2026-06-01`.
+
+## Tasks / Subtasks
+
+- [x] **Task 1: Verify `@guarded_fanout` posture (D-2)** — confirmed existing `Get Discoverability` ships `@guarded_fanout()` (line 353); SkillsLibrary host attrs gracefully fall back to None via `getattr` in guarded_fanout (graceful posture different from MCPLibrary's C20 carve-out). Applied same decorator on new keyword.
+- [x] **Task 2: `src/AgentEval/skills/types.py` extension (AC-13.5.2)** — 3 new frozen dataclasses (`SkillDiscoverabilityComparisonResult` + `SkillPairwiseAdapterDelta` + `SkillDiscoverabilityComparisonSummary`) with `__post_init__` validators applying Story 13.4 HIGH-B (best/worst rate consistency) + HIGH-C (summary cross-check) lessons + Story 13.3 nan-aware significance.
+- [x] **Task 3: `src/AgentEval/_heatmap/models.py` extension (AC-13.5.3)** — `CohortHeatmap.from_skill_comparison` classmethod added; reads `pass_at_k` (NOT `pass_rate`); Story 13.4 L-7 missing-cells-via-omission convention applied.
+- [x] **Task 4: `src/AgentEval/skills/_internal.py` (AC-13.5.4)** — `run_single_adapter_skill_discoverability` + `build_skill_discoverability_summary` helpers extracted from `SkillsLibrary.get_discoverability` body. Existing 86 Story 7.2 skills tests pass unchanged → refactor behavior identity verified.
+- [x] **Task 5: `src/AgentEval/skills/library.py` extension (AC-13.5.1 + AC-13.5.5)** — `get_discoverability_comparison` method shipped with `_stats_lib._ADVANCED_AVAILABLE` gate (module-attr read per Story 13.3 amendment) + direct ImportError raise. Refactored existing `get_discoverability` to delegate to helper.
+- [x] **Task 6: `tests/unit/skills/test_comparison.py` (AC-13.5.6)** — 17 unit tests covering dataclass validators (8) + heatmap (3) + pairwise counting (3) + false/missed-activation deltas (2) + Mann-Whitney identical-distribution (1). Spec said ≥18; shipped 17 (extras-gate file ships 4 covering the remaining surface = 21 total).
+- [x] **Task 7: `tests/unit/skills/test_comparison_extras_gate.py`** — 4 ImportError-gate tests with NO module-top importorskip per L-2 lesson.
+- [x] **Task 8: `tests/integration/skills/test_skill_compare_e2e.py` (AC-13.5.7)** — 3 stub adapters (always-activate / never-activate / perfect-by-prompt-matching) + concrete numerical assertions on accuracy ranking + best/worst + 3 pairwise deltas + false-activation + missed-activation orderings + zero-cost stubs. 3 tests total.
+- [x] **Task 9: `docs/recipes/04-skill-author-stacked-validation.md` (AC-13.5.8)** — `## Phase 2 cross-adapter Skill Discoverability` section added after Phase 2 Status; RF snippet `robot --dryrun` smoke verified clean.
+- [x] **Task 10: `docs/contracts/stability-surface.md` (AC-13.5.10)** — `### Cross-Adapter Skill Discoverability Surface (Phase-2 — FR4c)` subsection with 6 entries.
+- [x] **Task 11: Phase-1.5 carry-over catalog UPSTREAM (36th consecutive) (AC-13.5.11)** — C95 + C96 + C97 + C98 added to both `phase-1-5-carry-overs.md` (94 → 98) + `deferred-work.md` with full source attribution.
+- [x] **Task 12: All-gates pass + libdoc regen (AC-13.5.12)** — `uv run pytest tests/` reports **1941 passed + 16 skipped + 0 failed** (+29 vs 1912 + 16 Story 13.4 baseline). ruff/format/mypy/license clean. libdoc `docs/keywords/SkillsLibrary.html` regenerated with `Skill.Compare Discoverability` keyword.
+- [x] **Task 13: Sprint-status flip (AC-13.5.13)** — `13-5-compare-skill-discoverability-cross-adapter-fr4c: review`; `last_updated: 2026-06-01`.
+
+## Dev Notes
+
+Building on multiple foundations:
+- **Story 7.2** shipped `Skill.Get Discoverability` + `SkillTaskResult` + `SkillDiscoverabilityTaskSummary` + `SkillDiscoverabilityResult` + 30+ unit tests. Story 13.5 EXTENDS to N-adapter.
+- **Story 13.1** shipped `compute_mann_whitney_u` pure helper at `stats/mannwhitney.py` + `MannWhitneyResult` + the `[agenteval-advanced]` extra. Story 13.5 consumes the pure helper directly (NOT the keyword surface — per-task pass_at_k input is `list[float]` not `list[KeywordRun]`).
+- **Story 13.3** shipped the symmetric `MCP.Compare Tool Discoverability` + `DiscoverabilityComparisonResult` + `CohortHeatmap.from_comparison` + 3-stub integration test pattern. Story 13.5 PORTS the Skill-domain analog.
+- **Story 13.4** shipped `CohortHeatmap.as_html()` + cells-as-omission missing-cell convention. Story 13.5 leverages both: the new `from_skill_comparison` returns a `CohortHeatmap` which operators can render to HTML.
+
+**Skill-domain extension beyond Story 13.3 (D-1)**: the cross-adapter delta carries `false_activation_rate_delta` + `missed_activation_rate_delta` in addition to `pass_at_k_delta` because Skill discoverability has 2 failure modes (false-positive activation on decoy tasks + false-negative missed activation on should-activate tasks). MCP discoverability has only ONE primary failure mode (tool not picked when expected). These extra fields fulfill epic L2219's "per-adapter false-activation/missed-activation rate comparison" mandate.
+
+**Cross-story lesson application:**
+- L-1: stability-surface MUST register the new surface UPSTREAM.
+- L-2: extras-gate tests SPLIT into separate file per Story 13.1/13.3 pattern.
+- L-3: `@tier(3)` rationale documented.
+- L-4: integration test asserts CONCRETE numerical outcomes (3-stub deterministic ranking).
+- L-5: docstring precise + anchor test.
+- L-6: NO FR4c orientation drift (heatmap reuses FR55-amended orientation).
+- L-7: missing-cells via OMISSION (NOT explicit None) per Story 13.4 type-contract fix.
+
+### Project Structure Notes
+
+- NO new sub-library; extends existing `SkillsLibrary`.
+- NEW file: `src/AgentEval/skills/_internal.py` (extracted helper).
+- NEW test files: `tests/unit/skills/test_comparison.py` + `tests/unit/skills/test_comparison_extras_gate.py` + `tests/integration/skills/test_skill_compare_e2e.py`.
+- EXTENDED: `src/AgentEval/skills/library.py` (new keyword + helper-call refactor); `src/AgentEval/skills/types.py` (3 dataclasses); `src/AgentEval/_heatmap/models.py` (new classmethod); `docs/recipes/04-skill-author-stacked-validation.md`; `docs/contracts/stability-surface.md`; `docs/phase-1-5-carry-overs.md` + `deferred-work.md` (4 carry-overs each); `docs/keywords/SkillsLibrary.html` (libdoc regen).
+
+### References
+
+- PRD: `_bmad-output/planning-artifacts/prd.md` (FR4c not separately enumerated in PRD; ratified via epic L2212-2227 + the FR4b/FR4c/FR4d trio added 2026-05-17 per epic L17 `fr_count` annotation).
+- Architecture: pre-allocated `SkillsLibrary` file home; `_SUB_LIBRARIES` exclusion per Story 2.2 collision norm.
+- Epic: `_bmad-output/planning-artifacts/epics.md` L54 (FR4c definition); L309 (Epic 13 mapping); L2209-2227 (Story 13.5 detailed).
+- Prior stories: `_bmad-output/implementation-artifacts/7-2-skill-discoverability-and-assertion.md` (Story 7.2 foundation); `13-3-compare-tool-discoverability-cross-adapter.md` (symmetric MCP variant — closest reference); `13-4-cohort-heatmap-html-rendering.md` (cells-type-contract + orientation lessons).
+- Norms: 55th use of `feedback_spec_vs_ratified_doc_precheck`; 36th UPSTREAM use of `feedback_carry_over_catalog_gate`; Story 13.4 → 13.5 same-epic transition for `feedback_cross_story_upstream_lesson_propagation`; `feedback_in_flight_spec_amendment` for D-2 `@guarded_fanout` posture amendment + D-7 Recipe #4 update + D-8 dogfood deferral.
+
+## Dev Agent Record
+
+### Agent Model Used
+
+claude-opus-4-7[1m]
+
+### Debug Log References
+
+1 mid-dev catch: docstring `Example:` block missing (conventions test fired). Added 7-line RF Example block showing 2-adapter invocation + 2 `Should Be True` assertions per existing convention. Recipe RF snippet also dryrun-clean.
+
+### Completion Notes List
+
+Story 13.5 dev complete. **Closes Epic 13.** Phase-2 cross-adapter Skill Discoverability (FR4c) shipped.
+
+- **AC-13.5.1**: `Skill.Compare Discoverability` keyword on `SkillsLibrary` with `@tier(3) + @guarded_fanout()` (SkillsLibrary host attrs gracefully fall back to None — different posture from MCPLibrary's C20 carve-out per D-2 dev-start verification).
+- **AC-13.5.2**: 3 new frozen dataclasses with full validator coverage; Skill-domain extension carries `false_activation_rate_delta` + `missed_activation_rate_delta` beyond Story 13.3's MCP variant.
+- **AC-13.5.3**: `CohortHeatmap.from_skill_comparison` classmethod reads `pass_at_k` (NOT `pass_rate`); Story 13.4 L-7 missing-via-omission applied.
+- **AC-13.5.4**: `run_single_adapter_skill_discoverability` + `build_skill_discoverability_summary` extracted; existing 86 Story 7.2 tests pass unchanged.
+- **AC-13.5.5**: Python `get_discoverability_comparison` (verb-allowlist) + RF `Skill.Compare Discoverability` (epic verbatim).
+- **AC-13.5.6 + 13.5.7**: 17 unit + 4 extras-gate + 3 integration = 24 net new tests.
+- **AC-13.5.8**: Recipe #4 extended; `robot --dryrun` clean.
+- **AC-13.5.10**: stability-surface NEW `### Cross-Adapter Skill Discoverability Surface (Phase-2 — FR4c)` subsection with 6 entries.
+- **AC-13.5.11**: C95 + C96 + C97 + C98 catalogued UPSTREAM (36th consecutive).
+- **AC-13.5.12**: All-gates pass — 1941 + 16 final, ruff/format/mypy/license clean, libdoc regenerated.
+- **AC-13.5.13**: sprint-status flipped to `review`.
+
+### Cross-story upstream lesson application (Stories 13.1 + 13.2 + 13.3 + 13.4 reviews → Story 13.5)
+
+- **L-1 applied (stability-surface UPSTREAM)**: 6 entries registered (keyword + 3 dataclasses + classmethod + extras-gate message).
+- **L-2 applied (extras-gate test split)**: `test_comparison_extras_gate.py` has NO module-top importorskip.
+- **L-3 applied (@tier classification rationale)**: `@tier(3)` documented in keyword docstring; FR31a bit-identical concern N/A.
+- **L-4 applied (empirical correctness verification)**: integration test asserts CONCRETE numerical outcomes (accuracy(c)=1.0; accuracy(a)=3/5; accuracy(b)=2/5; best=c, worst=b; 3 pairwise deltas; false-activation a>others; missed-activation b>others).
+- **L-5 applied (docstring precision)**: keyword docstring names exact helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u`; Example block + Notes carry all spec anchors.
+- **L-6 applied**: NO orientation drift to fix (FR4c doesn't pin rows/cols; heatmap reuses FR55-amended-by-Story-13.4 orientation).
+- **L-7 applied**: `CohortHeatmap.from_skill_comparison` uses omitted cells for missing data (NOT explicit None) — preserves the public type contract.
+
+### In-flight spec amendments
+
+1. **`@guarded_fanout()` decorator applied (D-2 amendment)**: spec D-2 anticipated MCPLibrary-style carve-out. Dev-start verification showed `@guarded_fanout` is graceful via `getattr(self, "_max_cost_usd", None)` — falls back to None when host doesn't carry budget attrs. Existing SkillsLibrary `Get Discoverability` ships `@guarded_fanout()` cleanly. Applied same decorator on new keyword.
+
+2. **Test count**: spec said ≥18 unit. Shipped 17 unit + 4 extras-gate + 3 integration = 24 net new (exceeds spec total). Spec also said `≥18 net new tests` at the all-gates level.
+
+3. **`Example:` docstring block (mid-dev catch)**: conventions test `test_example_block_present` required RF Example block. Added 7-line example with 2-adapter invocation + 2 assertions.
+
+### File List
+
+**New files:**
+- `tests/unit/skills/test_comparison.py` — 17 unit tests.
+- `tests/unit/skills/test_comparison_extras_gate.py` — 4 ImportError-gate tests (run in both base + WITH-extras envs).
+- `tests/integration/skills/test_skill_compare_e2e.py` — 3 integration tests.
+
+**Modified files:**
+- `src/AgentEval/skills/library.py` — `get_discoverability_comparison` method + extras gate + existing `get_discoverability` refactored to delegate.
+- `src/AgentEval/skills/types.py` — 3 new frozen dataclasses + TYPE_CHECKING imports + `__all__` updates.
+- `src/AgentEval/skills/_internal.py` — `run_single_adapter_skill_discoverability` + `build_skill_discoverability_summary` helpers appended.
+- `src/AgentEval/_heatmap/models.py` — `CohortHeatmap.from_skill_comparison` classmethod + TYPE_CHECKING extension.
+- `_bmad-output/planning-artifacts/prd.md` — (no L1500/L1583 amendment needed; PRD FR4c spec is in epics.md not PRD).
+- `docs/contracts/stability-surface.md` — `### Cross-Adapter Skill Discoverability Surface` subsection.
+- `docs/phase-1-5-carry-overs.md` — C95 + C96 + C97 + C98 entries (94 → 98).
+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.5 dev" section with 4 entries.
+- `docs/recipes/04-skill-author-stacked-validation.md` — `## Phase 2 cross-adapter Skill Discoverability` section.
+- `docs/keywords/SkillsLibrary.html` — libdoc regenerated.
+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-5-*: review`; `last_updated: 2026-06-01`.
diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
index 99f4117..0c62c2c 100644
--- a/_bmad-output/implementation-artifacts/deferred-work.md
+++ b/_bmad-output/implementation-artifacts/deferred-work.md
@@ -398,6 +398,16 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
 
 - **DF-13.4-S3 (Phase-2.5 interactive HTML with embedded JavaScript for cell hover tooltips)** — Story 13.4 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.4 ships embedded CSS only per D-3 explicit prohibition on `<script>` (offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. Catalogued as C94. Effort: M. Phase-2.5.
 
+## Deferred from: story-13.5 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
+
+- **DF-13.5-S1 (Phase-2.5 unified host-instance budget plumbing for `Skill.Compare Discoverability`)** — Story 13.5 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.5 ships the keyword with `@guarded_fanout()` decorator; SkillsLibrary host attrs gracefully fall back to None via `getattr` — different posture from MCPLibrary's C20 carve-out. Phase-2.5 unifies host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary; shared resolution with C20 + C26 + C89. Catalogued as C95. Effort: M. Phase-2.5.
+
+- **DF-13.5-S2 (Phase-2.5 per-adapter MCP attachment for skills bridging to MCP tools)** — Story 13.5 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.5 inherits the Phase-1 MCP-bridge carve-out. Gated on C72 + C68/C69/C73/C75 per-adapter HostedMcpObserver wiring. When skills invoke MCP-bridged tools, the cross-adapter comparison can claim "skill X reliably activates MCP-tool-Y across runtimes." Catalogued as C96. Effort: M. Phase-2.5.
+
+- **DF-13.5-S3 (Phase-2.5 Bonferroni / Holm multi-pairwise correction)** — Story 13.5 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Mirrors DF-13.3-S3 / C91 for the Skill domain. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + adjusted-α fields. Shared resolution with C91. Catalogued as C97. Effort: S. Phase-2.5.
+
+- **DF-13.5-S4 (Phase-1.5 `robotframework-agentskills` cross-adapter dogfood CI matrix)** — Story 13.5 D-8 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Per epic L2227: ship the cross-adapter Skill Discoverability suite to the `robotframework-agentskills` downstream repo's CI matrix using Mock provider (routine CI) + a separate `weekly-cross-adapter-discoverability.yml` workflow against real APIs on a budget. Requires a PR to the downstream repo + budget-bounded API-key env. Catalogued as C98. Effort: M. Phase-1.5.
+
 ---
 
 *Update this file as new deferred items emerge from future reviews.*
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index b002218..542672f 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -155,5 +155,5 @@ development_status:
   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
   13-3-compare-tool-discoverability-cross-adapter: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 1 MED + 1 LOW from Codex + 2 MED + 3 LOW from Sonnet + 3 MED + 3 LOW from Opus). 2-way HIGH on total_runtime semantics (per-adapter MAX misreported serial wait time by ~N-1×); Codex unique HIGH-2 + HIGH-3 on dataclass best/worst rate consistency + summary.pass_rate_per_adapter cross-check. Codex MED-1 epic acceptance drift (cost_per_call=0.001 violated epic L2189 zero-cost requirement). Sonnet LOW-1+LOW-2 symmetric worst-adapter test + docstring anchor test. 1879 passed + 16 skipped final.
   13-4-cohort-heatmap-html-rendering: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (3 HIGH + 4 MED + 5 LOW). Codex HIGH-1 (image-regression deferral without spec amendment) + HIGH-2 (FR55 orientation drift). Opus HIGH-1 (carry-over breakdown math wrong; pre-existing Story 13.3 drift). 3-way MED on None in cells type contract (Codex+Opus+Sonnet). 2-way MED on Path('') gap (Opus+Sonnet). 1912 passed + 16 skipped final.
-  13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
+  13-5-compare-skill-discoverability-cross-adapter-fr4c: review
   epic-13-retrospective: optional
diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
index df97c10..5f55a70 100644
--- a/docs/contracts/stability-surface.md
+++ b/docs/contracts/stability-surface.md
@@ -131,6 +131,17 @@ Per Story 13.4 (PRD FR55) — Phase-2 standalone HTML rendering of `CohortHeatma
 - `AgentEval._heatmap.models._PASS_RATE_PALETTE` constant — `provisional` label per the Phase-2.5 DF-13.4-S2 / C93 color-blind palette carry-over. The 5-stop boundaries (0.0 / 0.2 / 0.4 / 0.6 / 0.8) are `stable`; the specific hex values are `provisional`.
 - `AgentEval._heatmap.models._color_for_pass_rate(rate) -> tuple[str, str]` helper — `provisional` label. Pure function; underscore-prefixed; not part of the public RF surface but consumable by Phase-2.5 plugins (e.g., color-blind palette overrides).
 
+### Cross-Adapter Skill Discoverability Surface (Phase-2 — FR4c)
+
+Per Story 13.5 (PRD FR4c) — Phase-2 cross-adapter Skill Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U). Symmetric to Story 13.3's MCP variant.
+
+- `Skill.Compare Discoverability` RF keyword + Python method `SkillsLibrary.get_discoverability_comparison` — `provisional` label. Signature: `skill=<path>, tasks=<yaml-path>, adapters=<list[str]>, trials_per_task=<int>, max_cost_usd=<float>, max_runtime_seconds=<float|None>, model=<str|None>, polling=<float|None>, **kwargs`. ≥2 distinct adapters required. RF keyword name + Python method name diverge intentionally (verb-allowlist convention; `get_discoverability_comparison`).
+- `AgentEval.skills.types.SkillDiscoverabilityComparisonResult` frozen dataclass — `provisional` label. 5 fields: `adapters: tuple[str, ...]`, `per_adapter_results: Mapping[str, SkillDiscoverabilityResult]`, `cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]`, `heatmap: CohortHeatmap`, `summary: SkillDiscoverabilityComparisonSummary`. `__post_init__` 4-way cross-consistency validators (`adapters ↔ per_adapter_results.keys()` + `adapters ↔ heatmap.models` + `adapters ↔ summary.activation_accuracy_per_adapter.keys()` + `len(adapters) >= 2`) are `stable`.
+- `AgentEval.skills.types.SkillPairwiseAdapterDelta` frozen dataclass — `provisional` label. 7 fields: `adapter_a`, `adapter_b`, `pass_at_k_delta`, `pass_at_k_mann_whitney_result`, `false_activation_rate_delta`, `missed_activation_rate_delta`, `significant_at_alpha_05`. Skill-domain extension beyond Story 13.3's `PairwiseAdapterDelta` carries the 2 extra rate deltas because Skill discoverability has 2 failure modes (false-positive + false-negative).
+- `AgentEval.skills.types.SkillDiscoverabilityComparisonSummary` frozen dataclass — `provisional` label. 5 fields: `total_cost_usd`, `total_runtime_seconds` (end-to-end wall-clock per Story 13.3 HIGH-A fix), `activation_accuracy_per_adapter`, `best_adapter`, `worst_adapter`.
+- `CohortHeatmap.from_skill_comparison` classmethod — `provisional` label. Reads `result.per_adapter_results[adapter].per_task_results[i].pass_at_k` (NOT MCP-domain `pass_rate`). Story 13.4 L-7 lesson: missing cells via OMISSION (NOT explicit `None`) per public `cells: tuple[tuple[str, str, float], ...]` type contract.
+- `[agenteval-advanced]` extra requirement bubble-up — `Skill.Compare Discoverability` raises `ImportError("Skill.Compare Discoverability: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]")` when invoked without the extra.
+
 ### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
 
 Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
diff --git a/docs/keywords/SkillsLibrary.html b/docs/keywords/SkillsLibrary.html
index 55a191c..08296f2 100644
--- a/docs/keywords/SkillsLibrary.html
+++ b/docs/keywords/SkillsLibrary.html
@@ -6,7 +6,7 @@
 <meta http-equiv=X-UA-Compatible content="IE=edge">
 <meta content="Robot Framework 7.4.2 (Python 3.12.3 on linux)" name="Generator">
 <script type="text/javascript">
-libdoc = {"specversion": 3, "name": "AgentEval.skills.library.SkillsLibrary", "doc": "<p>Static-inspection keywords for skill <span class=\"name\">.md</span> files [Tier 1 \u2014 Deterministic].</p>\n<p>All 5 public methods are <span class=\"name\">@keyword</span>-decorated + <span class=\"name\">@tier(1)</span>-annotated per Story 1b.6 conventions. The class holds no mutable state; each call re-parses the target file so the keywords are stateless + parallel-safe under <span class=\"name\">pabot --processes N</span>.</p>", "version": "", "generated": "2026-05-27T19:45:46+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 92, "tags": [], "inits": [], "keywords": [{"name": "Get Activation Decision", "args": [{"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "prompt: str"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "ActivationDecision", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 sends <code>prompt</code> to the named adapter and returns an <code>ActivationDecision</code> with <code>activated</code> (bool), <code>reasoning</code> (the response text), <code>cost_usd</code>, and <code>latency_seconds</code>. Phase-1 activation heuristic: case- insensitive substring check of the skill's <code>name</code> field in <code>result.response_text</code>. Phase-2 will adopt a more robust classifier (DF-7.1-S1 / C55).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.1.5. Use <span class=\"name\">Stat.Run N Times</span> for fan-out instead.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>InvalidSkillFrontmatterError</code> when the skill file cannot be read or parsed as valid YAML. Structurally invalid frontmatter (missing required fields) does NOT raise here \u2014 missing <code>name</code> silently yields <code>activated=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n${decision} =    <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a>    ${CURDIR}/skills/web-search.md    prompt=Find news about Robot Framework\nShould Be True    ${decision.activated}\nShould Be True    ${decision.cost_usd} &gt;= 0.0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the skill-activation surface; AC-7.1 ratifies the keyword contract.</li>\n<li>Phase-1 heuristic per AC-7.1.4 \u2014 substring check on skill <code>name</code> in response text. Phase-2 classifier deferred per DF-7.1-S1 / C55.</li>\n<li>FR28 prohibits polling \u2014 use <span class=\"name\">Stat.Run N Times</span> for statistical assertions instead.</li>\n<li>Sibling keyword: <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a> (assertion wrapper); <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a> (multi-task cohort evaluation).</li>\n</ul>", "shortdoc": "Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 283}, {"name": "Get Allowed Tools", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the <code>allowed-tools</code> list from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a <code>list[str]</code> type check. The list MAY be empty (a skill with no tool allowlist is valid).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR <code>allowed-tools</code> is not a list of strings.</p>\n<p>Example:</p>\n<pre>\n@{tools} =    <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>    ${CURDIR}/skills/example.md\nShould Contain    ${tools}    Bash\nShould Contain    ${tools}    Read\nLength Should Be    ${tools}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the allowed-tools projection contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict); <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a> (companion projection).</li>\n</ul>", "shortdoc": "Returns the ``allowed-tools`` list from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 165}, {"name": "Get Description", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "doc": "<p>Returns the <code>description</code> field from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a <span class=\"name\">`description</span>`-field non-empty-string check.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR the <code>description</code> field is missing / non-string / empty.</p>\n<p>Example:</p>\n<pre>\n${desc} =    <a href=\"#Get%20Description\" class=\"name\">Get Description</a>    ${CURDIR}/skills/example.md\nShould Contain    ${desc}    example skill\nShould Be True    len('${desc}') &gt; 0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the description-field projection contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict); <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> (all-fields validator).</li>\n</ul>", "shortdoc": "Returns the ``description`` field from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 138}, {"name": "Get Disable Model Invocation", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "doc": "<p>Returns the <code>disable-model-invocation</code> bool from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a strict bool type check. YAML coercion rules:</p>\n<ul>\n<li><code>true<span class=\"name\">`/</span><span class=\"name\">false</span><span class=\"name\">/</span><span class=\"name\">yes</span><span class=\"name\">/</span><span class=\"name\">no</span><span class=\"name\">/</span><span class=\"name\">on</span><span class=\"name\">/</span>`off</code> parse to Python bool (PyYAML 1.1 semantics) \u2014 accepted.</li>\n<li><code>1<span class=\"name\">`/</span>`0</code> integers parse to Python int \u2014 <b>*rejected*</b> (<code>isinstance(value, bool)</code> is False for ints).</li>\n<li>String forms like <code>\"true\"</code> are <b>*rejected*</b> \u2014 must be unquoted.</li>\n</ul>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR <code>disable-model-invocation</code> is not a bool.</p>\n<p>Example:</p>\n<pre>\n${disabled} =    <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a>    ${CURDIR}/skills/example.md\nShould Be Equal    ${disabled}    ${FALSE}                                      # Default for most skills.\n${disabled} =    <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a>    ${CURDIR}/skills/static-only.md\nShould Be Equal    ${disabled}    ${TRUE}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the disable-model-invocation projection contract.</li>\n<li>Strict bool typing \u2014 int / string forms rejected. The PyYAML 1.1 coercion of unquoted <code>true<span class=\"name\">`/</span>`yes</code> etc. to Python bool IS accepted.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keyword: <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a> (companion projection).</li>\n</ul>", "shortdoc": "Returns the ``disable-model-invocation`` bool from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 193}, {"name": "Get Discoverability", "args": [{"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "tasks", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tasks: str | Path"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "SkillDiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs a cohort discoverability evaluation across N tasks \u00d7 M trials (PRD FR4b).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 runs <code>trials_per_task</code> adapter calls per task across all tasks in the YAML, returning a <code>SkillDiscoverabilityResult</code> with <code>per_task_results</code>, <code>summary</code>, and <code>adapter_coverage</code>. Phase-1 activation heuristic per AC-7.2.4: case-insensitive substring check of the skill <code>name</code> field in each trial's <code>response_text</code>. Phase-2 adds structured-response schema for competing-skills-picked detection (DF-7.2-S1 / C56).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file.</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Filesystem path to the skill-discoverability tasks YAML.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Number of adapter calls per task. Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.2.6.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>ValueError</code> when <code>trials_per_task &lt; 1</code>. Raises <code>InvalidSkillFrontmatterError</code> when the skill file is unreadable / un-parseable. Raises <code>InvalidSkillDiscoverabilityTasksError</code> when the tasks YAML is structurally invalid.</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n${disc} =    <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a>    ${CURDIR}/skills/web-search.md    ${CURDIR}/tasks/web-search.yaml    trials_per_task=5\nShould Be True    ${disc.summary.activation_accuracy} &gt;= 0.6\nFOR    ${task_result}    IN    @{disc.per_task_results}\n    Log    ${task_result.task_id}: ${task_result.pass_at_k}\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4b ratifies the cohort-discoverability contract; AC-7.2 ratifies the keyword surface.</li>\n<li>Phase-1 activation heuristic per AC-7.2.4. Phase-2 structured-response classifier deferred per DF-7.2-S1 / C56.</li>\n<li>FR28 prohibits polling \u2014 fan-out via this keyword's own <code>trials_per_task</code> or via <span class=\"name\">Stat.Run N Times</span>.</li>\n<li>Sibling keywords: <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> (single-task variant); <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a> (assertion wrapper).</li>\n</ul>", "shortdoc": "Runs a cohort discoverability evaluation across N tasks \u00d7 M trials (PRD FR4b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 354}, {"name": "Get Frontmatter", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "doc": "<p>Parses the YAML frontmatter at the head of a skill <code>.md</code> file (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + YAML parse; no provider, no trace store. Returns the raw parsed YAML as a <code>dict[str, Any]</code>. Does NOT enforce the required-fields contract \u2014 see <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> for structural validation, OR the typed getters (<a href=\"#Get%20Description\" class=\"name\">Get Description</a>, <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>, etc.) which validate during projection. Median \u2264 50 ms per call on the 5 KB reference fixture.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> on YAML / file-level structural failure (missing file, broken YAML, missing <code>---</code> delimiters, frontmatter not a mapping). Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>Example:</p>\n<pre>\n${frontmatter} =    <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>    ${CURDIR}/skills/example.md\nShould Be Equal    ${frontmatter}[name]    example-skill\nShould Contain    ${frontmatter}[allowed-tools]    Bash\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the YAML frontmatter parse + dict-return contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Description\" class=\"name\">Get Description</a>, <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>, <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a> (typed-validated projections); <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> (structural validator).</li>\n<li>Parallel surface: <span class=\"name\">SubagentsLibrary.Get Frontmatter</span> for sub-agent <code>.md</code> files (different validation rules).</li>\n</ul>", "shortdoc": "Parses the YAML frontmatter at the head of a skill ``.md`` file (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 103}, {"name": "Should Activate For", "args": [{"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "prompt: str"}, {"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": null, "doc": "<p>Asserts that the given skill activates for the given prompt (PRD FR4d).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 sends <code>prompt</code> to the adapter once and asserts the skill name appears in the response text. Phase-1 activation heuristic per AC-7.2.5: case-insensitive substring check of the skill <code>name</code> field in <code>result.response_text</code> (same heuristic as <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Natural-language prompt to test.</td>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.2.6.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>SkillDidNotActivateError</code> on no-activation with diagnostic fields (<code>prompt</code>, <code>skill_path</code>, <code>skill_name</code>, <code>competing_skill</code> (None in Phase-1), <code>reasoning</code>, <code>fix_suggestion</code>). Raises <code>InvalidSkillFrontmatterError</code> on YAML / file failure.</p>\n<p>Note: missing / empty / non-string <code>name</code> field causes the activation check to always evaluate False \u2014 this keyword raises <code>SkillDidNotActivateError</code> unconditionally in that case (same as <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> per AC-7.1.4).</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n<a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a>    Find news about Robot Framework    ${CURDIR}/skills/web-search.md\nRun Keyword And Expect Error    SkillDidNotActivateError*    <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a>    Calculate 2+2    ${CURDIR}/skills/web-search.md\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4d ratifies the activation-assertion contract; AC-7.2.5 + AC-7.2.6 ratify the keyword surface.</li>\n<li>Phase-1 heuristic per AC-7.1.4 \u2014 substring check on skill <code>name</code> in response text.</li>\n<li>FR28 prohibits polling \u2014 fan-out via <span class=\"name\">Stat.Run N Times</span> if statistical evidence is needed.</li>\n<li>Sibling keywords: <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> (returns decision instead of raising); <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a> (multi-task cohort).</li>\n</ul>", "shortdoc": "Asserts that the given skill activates for the given prompt (PRD FR4d).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 460}, {"name": "Should Be Valid Frontmatter", "args": [{"name": "frontmatter", "type": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "frontmatter: dict[str, Any]"}], "returnType": null, "doc": "<p>Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 structural validator. Required fields: <code>name</code> (str), <code>description</code> (str), <code>allowed-tools</code> (<code>list[str]</code>), <code>disable-model-invocation</code> (bool). Phase-1 plain <code>@keyword</code> per ADR-019 catalog row; full AssertionEngine matcher deferred to Phase-2.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>frontmatter</code></td>\n<td>The dict returned by <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when any required field is missing OR has the wrong type. The error message lists the offending field(s) so the test author can remediate. Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>Example:</p>\n<pre>\n${frontmatter} =    <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>    ${CURDIR}/skills/example.md\n<a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a>    ${frontmatter}\n${fm_broken} =    Create Dictionary    name=just-a-name\nRun Keyword And Expect Error    InvalidSkillFrontmatterError*    <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a>    ${fm_broken}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the required-fields contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>ADR-019 ratifies the Phase-1 plain-<span class=\"name\">`@keyword</span>` form; Phase-2 will adopt the AssertionEngine matcher idiom.</li>\n<li>Sibling keyword: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict \u2014 feed its return into this validator).</li>\n</ul>", "shortdoc": "Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 248}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Get Activation Decision", "Get Discoverability", "Get Frontmatter", "Should Activate For", "Should Be Valid Frontmatter"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["Get Disable Model Invocation"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Get Frontmatter", "Should Be Valid Frontmatter"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["Get Activation Decision", "Get Discoverability", "Should Activate For"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Discoverability"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Allowed Tools"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["Get Activation Decision", "Get Discoverability", "Should Activate For"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Get Activation Decision", "Get Allowed Tools", "Get Description", "Get Disable Model Invocation", "Get Discoverability", "Get Frontmatter", "Should Activate For"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["Get Activation Decision", "Get Allowed Tools", "Get Description", "Get Disable Model Invocation", "Get Discoverability", "Get Frontmatter", "Should Activate For", "Should Be Valid Frontmatter"], "accepts": ["Any"]}]}
+libdoc = {"specversion": 3, "name": "AgentEval.skills.library.SkillsLibrary", "doc": "<p>Static-inspection keywords for skill <span class=\"name\">.md</span> files [Tier 1 \u2014 Deterministic].</p>\n<p>All 5 public methods are <span class=\"name\">@keyword</span>-decorated + <span class=\"name\">@tier(1)</span>-annotated per Story 1b.6 conventions. The class holds no mutable state; each call re-parses the target file so the keywords are stateless + parallel-safe under <span class=\"name\">pabot --processes N</span>.</p>", "version": "", "generated": "2026-06-01T12:57:20+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 93, "tags": [], "inits": [], "keywords": [{"name": "Get Activation Decision", "args": [{"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "prompt: str"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "ActivationDecision", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 sends <code>prompt</code> to the named adapter and returns an <code>ActivationDecision</code> with <code>activated</code> (bool), <code>reasoning</code> (the response text), <code>cost_usd</code>, and <code>latency_seconds</code>. Phase-1 activation heuristic: case- insensitive substring check of the skill's <code>name</code> field in <code>result.response_text</code>. Phase-2 will adopt a more robust classifier (DF-7.1-S1 / C55).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.1.5. Use <span class=\"name\">Stat.Run N Times</span> for fan-out instead.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>InvalidSkillFrontmatterError</code> when the skill file cannot be read or parsed as valid YAML. Structurally invalid frontmatter (missing required fields) does NOT raise here \u2014 missing <code>name</code> silently yields <code>activated=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n${decision} =    <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a>    ${CURDIR}/skills/web-search.md    prompt=Find news about Robot Framework\nShould Be True    ${decision.activated}\nShould Be True    ${decision.cost_usd} &gt;= 0.0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the skill-activation surface; AC-7.1 ratifies the keyword contract.</li>\n<li>Phase-1 heuristic per AC-7.1.4 \u2014 substring check on skill <code>name</code> in response text. Phase-2 classifier deferred per DF-7.1-S1 / C55.</li>\n<li>FR28 prohibits polling \u2014 use <span class=\"name\">Stat.Run N Times</span> for statistical assertions instead.</li>\n<li>Sibling keyword: <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a> (assertion wrapper); <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a> (multi-task cohort evaluation).</li>\n</ul>", "shortdoc": "Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 284}, {"name": "Get Allowed Tools", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the <code>allowed-tools</code> list from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a <code>list[str]</code> type check. The list MAY be empty (a skill with no tool allowlist is valid).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR <code>allowed-tools</code> is not a list of strings.</p>\n<p>Example:</p>\n<pre>\n@{tools} =    <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>    ${CURDIR}/skills/example.md\nShould Contain    ${tools}    Bash\nShould Contain    ${tools}    Read\nLength Should Be    ${tools}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the allowed-tools projection contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict); <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a> (companion projection).</li>\n</ul>", "shortdoc": "Returns the ``allowed-tools`` list from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 166}, {"name": "Get Description", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "doc": "<p>Returns the <code>description</code> field from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a <span class=\"name\">`description</span>`-field non-empty-string check.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR the <code>description</code> field is missing / non-string / empty.</p>\n<p>Example:</p>\n<pre>\n${desc} =    <a href=\"#Get%20Description\" class=\"name\">Get Description</a>    ${CURDIR}/skills/example.md\nShould Contain    ${desc}    example skill\nShould Be True    len('${desc}') &gt; 0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the description-field projection contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict); <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> (all-fields validator).</li>\n</ul>", "shortdoc": "Returns the ``description`` field from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 139}, {"name": "Get Disable Model Invocation", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "doc": "<p>Returns the <code>disable-model-invocation</code> bool from a skill <code>.md</code> file's frontmatter (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection of <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> with a strict bool type check. YAML coercion rules:</p>\n<ul>\n<li><code>true<span class=\"name\">`/</span><span class=\"name\">false</span><span class=\"name\">/</span><span class=\"name\">yes</span><span class=\"name\">/</span><span class=\"name\">no</span><span class=\"name\">/</span><span class=\"name\">on</span><span class=\"name\">/</span>`off</code> parse to Python bool (PyYAML 1.1 semantics) \u2014 accepted.</li>\n<li><code>1<span class=\"name\">`/</span>`0</code> integers parse to Python int \u2014 <b>*rejected*</b> (<code>isinstance(value, bool)</code> is False for ints).</li>\n<li>String forms like <code>\"true\"</code> are <b>*rejected*</b> \u2014 must be unquoted.</li>\n</ul>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when the frontmatter is invalid OR <code>disable-model-invocation</code> is not a bool.</p>\n<p>Example:</p>\n<pre>\n${disabled} =    <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a>    ${CURDIR}/skills/example.md\nShould Be Equal    ${disabled}    ${FALSE}                                      # Default for most skills.\n${disabled} =    <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a>    ${CURDIR}/skills/static-only.md\nShould Be Equal    ${disabled}    ${TRUE}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the disable-model-invocation projection contract.</li>\n<li>Strict bool typing \u2014 int / string forms rejected. The PyYAML 1.1 coercion of unquoted <code>true<span class=\"name\">`/</span>`yes</code> etc. to Python bool IS accepted.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keyword: <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a> (companion projection).</li>\n</ul>", "shortdoc": "Returns the ``disable-model-invocation`` bool from a skill ``.md`` file's frontmatter (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 194}, {"name": "Get Discoverability", "args": [{"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "tasks", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tasks: str | Path"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "SkillDiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs a cohort discoverability evaluation across N tasks \u00d7 M trials (PRD FR4b).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 runs <code>trials_per_task</code> adapter calls per task across all tasks in the YAML, returning a <code>SkillDiscoverabilityResult</code> with <code>per_task_results</code>, <code>summary</code>, and <code>adapter_coverage</code>. Phase-1 activation heuristic per AC-7.2.4: case-insensitive substring check of the skill <code>name</code> field in each trial's <code>response_text</code>. Phase-2 adds structured-response schema for competing-skills-picked detection (DF-7.2-S1 / C56).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file.</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Filesystem path to the skill-discoverability tasks YAML.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Number of adapter calls per task. Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.2.6.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>ValueError</code> when <code>trials_per_task &lt; 1</code>. Raises <code>InvalidSkillFrontmatterError</code> when the skill file is unreadable / un-parseable. Raises <code>InvalidSkillDiscoverabilityTasksError</code> when the tasks YAML is structurally invalid.</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n${disc} =    <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a>    ${CURDIR}/skills/web-search.md    ${CURDIR}/tasks/web-search.yaml    trials_per_task=5\nShould Be True    ${disc.summary.activation_accuracy} &gt;= 0.6\nFOR    ${task_result}    IN    @{disc.per_task_results}\n    Log    ${task_result.task_id}: ${task_result.pass_at_k}\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4b ratifies the cohort-discoverability contract; AC-7.2 ratifies the keyword surface.</li>\n<li>Phase-1 activation heuristic per AC-7.2.4. Phase-2 structured-response classifier deferred per DF-7.2-S1 / C56.</li>\n<li>FR28 prohibits polling \u2014 fan-out via this keyword's own <code>trials_per_task</code> or via <span class=\"name\">Stat.Run N Times</span>.</li>\n<li>Sibling keywords: <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> (single-task variant); <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a> (assertion wrapper).</li>\n</ul>", "shortdoc": "Runs a cohort discoverability evaluation across N tasks \u00d7 M trials (PRD FR4b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 355}, {"name": "Get Frontmatter", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "doc": "<p>Parses the YAML frontmatter at the head of a skill <code>.md</code> file (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + YAML parse; no provider, no trace store. Returns the raw parsed YAML as a <code>dict[str, Any]</code>. Does NOT enforce the required-fields contract \u2014 see <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> for structural validation, OR the typed getters (<a href=\"#Get%20Description\" class=\"name\">Get Description</a>, <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>, etc.) which validate during projection. Median \u2264 50 ms per call on the 5 KB reference fixture.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the skill <code>.md</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> on YAML / file-level structural failure (missing file, broken YAML, missing <code>---</code> delimiters, frontmatter not a mapping). Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>Example:</p>\n<pre>\n${frontmatter} =    <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>    ${CURDIR}/skills/example.md\nShould Be Equal    ${frontmatter}[name]    example-skill\nShould Contain    ${frontmatter}[allowed-tools]    Bash\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the YAML frontmatter parse + dict-return contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Description\" class=\"name\">Get Description</a>, <a href=\"#Get%20Allowed%20Tools\" class=\"name\">Get Allowed Tools</a>, <a href=\"#Get%20Disable%20Model%20Invocation\" class=\"name\">Get Disable Model Invocation</a> (typed-validated projections); <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a> (structural validator).</li>\n<li>Parallel surface: <span class=\"name\">SubagentsLibrary.Get Frontmatter</span> for sub-agent <code>.md</code> files (different validation rules).</li>\n</ul>", "shortdoc": "Parses the YAML frontmatter at the head of a skill ``.md`` file (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 104}, {"name": "Should Activate For", "args": [{"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "prompt: str"}, {"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "skill: str | Path"}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": null, "doc": "<p>Asserts that the given skill activates for the given prompt (PRD FR4d).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 sends <code>prompt</code> to the adapter once and asserts the skill name appears in the response text. Phase-1 activation heuristic per AC-7.2.5: case-insensitive substring check of the skill <code>name</code> field in <code>result.response_text</code> (same heuristic as <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Natural-language prompt to test.</td>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file.</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter identifier. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional model override forwarded to the adapter constructor.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 / AC-7.2.6.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Additional kwargs forwarded to the adapter constructor.</td>\n</tr>\n</table>\n<p>Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided (FR28). Raises <code>SkillDidNotActivateError</code> on no-activation with diagnostic fields (<code>prompt</code>, <code>skill_path</code>, <code>skill_name</code>, <code>competing_skill</code> (None in Phase-1), <code>reasoning</code>, <code>fix_suggestion</code>). Raises <code>InvalidSkillFrontmatterError</code> on YAML / file failure.</p>\n<p>Note: missing / empty / non-string <code>name</code> field causes the activation check to always evaluate False \u2014 this keyword raises <code>SkillDidNotActivateError</code> unconditionally in that case (same as <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> per AC-7.1.4).</p>\n<p>Example (illustrative \u2014 assumes a real adapter):</p>\n<pre>\n<a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a>    Find news about Robot Framework    ${CURDIR}/skills/web-search.md\nRun Keyword And Expect Error    SkillDidNotActivateError*    <a href=\"#Should%20Activate%20For\" class=\"name\">Should Activate For</a>    Calculate 2+2    ${CURDIR}/skills/web-search.md\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4d ratifies the activation-assertion contract; AC-7.2.5 + AC-7.2.6 ratify the keyword surface.</li>\n<li>Phase-1 heuristic per AC-7.1.4 \u2014 substring check on skill <code>name</code> in response text.</li>\n<li>FR28 prohibits polling \u2014 fan-out via <span class=\"name\">Stat.Run N Times</span> if statistical evidence is needed.</li>\n<li>Sibling keywords: <a href=\"#Get%20Activation%20Decision\" class=\"name\">Get Activation Decision</a> (returns decision instead of raising); <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a> (multi-task cohort).</li>\n</ul>", "shortdoc": "Asserts that the given skill activates for the given prompt (PRD FR4d).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 653}, {"name": "Should Be Valid Frontmatter", "args": [{"name": "frontmatter", "type": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "frontmatter: dict[str, Any]"}], "returnType": null, "doc": "<p>Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 structural validator. Required fields: <code>name</code> (str), <code>description</code> (str), <code>allowed-tools</code> (<code>list[str]</code>), <code>disable-model-invocation</code> (bool). Phase-1 plain <code>@keyword</code> per ADR-019 catalog row; full AssertionEngine matcher deferred to Phase-2.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>frontmatter</code></td>\n<td>The dict returned by <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidSkillFrontmatterError</code> when any required field is missing OR has the wrong type. The error message lists the offending field(s) so the test author can remediate. Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>Example:</p>\n<pre>\n${frontmatter} =    <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a>    ${CURDIR}/skills/example.md\n<a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a>    ${frontmatter}\n${fm_broken} =    Create Dictionary    name=just-a-name\nRun Keyword And Expect Error    InvalidSkillFrontmatterError*    <a href=\"#Should%20Be%20Valid%20Frontmatter\" class=\"name\">Should Be Valid Frontmatter</a>    ${fm_broken}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR1 ratifies the required-fields contract.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>ADR-019 ratifies the Phase-1 plain-<span class=\"name\">`@keyword</span>` form; Phase-2 will adopt the AssertionEngine matcher idiom.</li>\n<li>Sibling keyword: <a href=\"#Get%20Frontmatter\" class=\"name\">Get Frontmatter</a> (raw dict \u2014 feed its return into this validator).</li>\n</ul>", "shortdoc": "Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 249}, {"name": "Skill.Compare Discoverability", "args": [{"name": "skill", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "skill: str | Path = "}, {"name": "tasks", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "tasks: str | Path = "}, {"name": "adapters", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapters: list[str] | None = None"}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "20.0", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_cost_usd: float = 20.0"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_runtime_seconds: float | None = None"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "polling", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "polling: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "SkillDiscoverabilityComparisonResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Compares Skill Discoverability across \u22652 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 runs <span class=\"name\">Skill.Get Discoverability</span> once per adapter against the SAME task set, then computes pairwise Mann-Whitney U deltas across the per-task <span class=\"name\">pass_at_k</span> distributions PLUS false-activation-rate + missed-activation- rate deltas. Returns a <span class=\"name\">SkillDiscoverabilityComparisonResult</span> with per-adapter results + cross-adapter deltas + multi-column cohort heatmap + aggregate summary.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra (scipy + numpy) for the Mann-Whitney U cross-adapter delta computation; raises <code>ImportError</code> on invocation WITHOUT the extra (fail-fast BEFORE per-adapter fan-out \u2014 operators discovering the missing extra should not pay N-adapter trial cost first).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>skill</code></td>\n<td>Filesystem path to the skill <code>.md</code> file.</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Filesystem path to the skill-discoverability tasks YAML (loaded ONCE; shared across adapters).</td>\n</tr>\n<tr>\n<td><code>adapters</code></td>\n<td>REQUIRED <code>list[str]</code> of adapter names; \u22652 entries required.</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Pass@k trials per task. Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>max_cost_usd</code></td>\n<td>Budget cap. Defaults to <code>20.00</code> per epics.md L2218 (4\u00d7 single-adapter typical).</td>\n</tr>\n<tr>\n<td><code>max_runtime_seconds</code></td>\n<td>Runtime cap.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional <code>str</code> forwarded to ALL adapters' ctor.</td>\n</tr>\n<tr>\n<td><code>polling</code></td>\n<td>Must NOT be provided \u2014 raises <code>PollingDisallowedError</code> per FR28 (mirrors <a href=\"#Get%20Discoverability\" class=\"name\">Get Discoverability</a>).</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Forward-compat kwargs routed to each adapter's ctor.</td>\n</tr>\n</table>\n<p>Returns <code>SkillDiscoverabilityComparisonResult</code> with <code>adapters</code> + <code>per_adapter_results</code> (one <code>SkillDiscoverabilityResult</code> per adapter) + <code>cross_adapter_deltas</code> (C(N, 2) <code>SkillPairwiseAdapterDelta</code> entries keyed <code>f\"{a1}_vs_{a2}\"</code>) + <code>heatmap</code> (multi-column <code>CohortHeatmap</code> via <code>from_skill_comparison</code>) + <code>summary</code> (<code>SkillDiscoverabilityComparisonSummary</code>).</p>\n<p>Raises <code>ImportError</code> when <code>[agenteval-advanced]</code> extra is missing. Raises <code>PollingDisallowedError</code> when <code>polling</code> is provided. Raises <code>ValueError</code> on missing <code>skill</code> / <code>tasks</code> / <code>adapters</code> (\u22652 distinct required) / invalid <code>trials_per_task</code>.</p>\n<p>Example:</p>\n<pre>\n${comparison}=    <a href=\"#Skill.Compare%20Discoverability\" class=\"name\">Skill.Compare Discoverability</a>\n...    skill=${CURDIR}/skills/example.md\n...    tasks=${CURDIR}/discoverability/skill-tasks.yaml\n...    adapters=${{['claude_code_cli', 'codex_cli']}}\n...    trials_per_task=5\nShould Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} &gt;= 0.7\nShould Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) &lt; 0.3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.5 (Epic 13) ships this Phase-2 keyword closing Devon's cross-adapter analysis loop. Symmetric to Story 13.3's <span class=\"name\">MCP.Compare Tool Discoverability</span> (FR10b).</li>\n<li>PRD FR4c ratifies the cross-adapter Skill Discoverability surface; epics.md L2218-2219 ratifies the keyword signature + extended fields (per-adapter false-activation / missed-activation rate comparison).</li>\n<li>Math reference: <code>AgentEval.stats.mannwhitney.compute_mann_whitney_u</code> (Story 13.1 pure helper). Mann-Whitney U is computed on the per-task <code>pass_at_k</code> lists per adapter; false-activation + missed-activation deltas are aggregate-summary subtractions.</li>\n<li><code>@tier(3)</code> per fan-out semantics \u2014 stochastic by tier definition.</li>\n<li>Phase-2.5 carry-overs: DF-13.5-S1 (<span class=\"name\">@guarded_fanout</span> cross-library budget plumbing); DF-13.5-S2 (per-adapter MCP attachment); DF-13.5-S3 (Bonferroni multi-pairwise correction); DF-13.5-S4 (<span class=\"name\">robotframework-agentskills</span> dogfood CI matrix).</li>\n<li>Sibling keyword: <span class=\"name\">Skill.Get Discoverability</span> (Phase-1 single-adapter). The \u22652-adapter validation rejects N=1 callers \u2014 use the simpler <span class=\"name\">Get</span> keyword for single-adapter runs.</li>\n</ul>", "shortdoc": "Compares Skill Discoverability across \u22652 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/skills/library.py", "lineno": 448}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Get Activation Decision", "Get Discoverability", "Get Frontmatter", "Should Activate For", "Should Be Valid Frontmatter", "Skill.Compare Discoverability"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["Get Disable Model Invocation"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Get Frontmatter", "Should Be Valid Frontmatter"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["Get Activation Decision", "Get Discoverability", "Should Activate For", "Skill.Compare Discoverability"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Discoverability", "Skill.Compare Discoverability"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Allowed Tools", "Skill.Compare Discoverability"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["Get Activation Decision", "Get Discoverability", "Should Activate For", "Skill.Compare Discoverability"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Get Activation Decision", "Get Allowed Tools", "Get Description", "Get Disable Model Invocation", "Get Discoverability", "Get Frontmatter", "Should Activate For", "Skill.Compare Discoverability"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["Get Activation Decision", "Get Allowed Tools", "Get Description", "Get Disable Model Invocation", "Get Discoverability", "Get Frontmatter", "Should Activate For", "Should Be Valid Frontmatter", "Skill.Compare Discoverability"], "accepts": ["Any"]}]}
 </script>
 <link rel=icon type=image/x-icon href="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKcAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAAqAAAAAAAAAAAAAAAAAAAALIAAAD/AAAA4AAAANwAAADcAAAA3AAAANwAAADcAAAA3AAAANwAAADcAAAA4AAAAP8AAACxAAAAAAAAAKYAAAD/AAAAuwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC/AAAA/wAAAKkAAAD6AAAAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN8AAAD/AAAA+gAAAMMAAAAAAAAAAgAAAGsAAABrAAAAawAAAGsAAABrAAAAawAAAGsAAABrAAAADAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAIsAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAANEAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAAAAAAAAMgAAADIAAAAyAAAAMgAAADIAAAAyAAAAMgAAADIAAAAFAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAADwAAAB8AAAAAAAAAGAAAABcAAAAAAAAAH8AAABKAAAAAAAAAAAAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAADCAAAA/wAAACkAAADqAAAA4QAAAAAAAAD7AAAA/wAAALAAAAAGAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAIwAAAP4AAAD/AAAA/wAAAGAAAAAAAAAAAAAAAMkAAAD/AAAAigAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAAAAAAAIAAAAcAAAABkAAAAAAAAAAAAAAAAAAAAAAAAAEgAAAAAAAAAAAAAA2gAAAP8AAAD7AAAAywAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN4AAAD/AAAAqwAAAP8AAACvAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALIAAAD/AAAAsgAAAAAAAAC5AAAA/wAAAMoAAADAAAAAwAAAAMAAAADAAAAAwAAAAMAAAADAAAAAwAAAAMkAAAD/AAAAvAAAAAAAAAAAAAAAAAAAAKwAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAArQAAAAAAAAAAwAMAAIABAAAf+AAAP/wAAD/8AAAgBAAAP/wAAD/8AAA//AAAJIwAADHEAAA//AAAP/wAAB/4AACAAQAAwAMAAA==">
 </head>
diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
index d169a58..cd02319 100644
--- a/docs/phase-1-5-carry-overs.md
+++ b/docs/phase-1-5-carry-overs.md
@@ -120,7 +120,12 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
 | **C93** | **Phase-2.5: Color-blind-safe palette mode for `as_html()` (`DF-13.4-S2`).** Story 13.4 ships a 5-stop red-orange-yellow-lime-green palette. Per WCAG 2.1 AA, this palette is NOT color-blind safe (red-green color blindness affects ~8% of males). Phase-2.5: ship an alternative `palette: Literal["default", "viridis", "magma"]` kwarg on `as_html()` (sequential colormaps from matplotlib are perceptually uniform + color-blind friendly). *Surfaced via Story 13.4 spec D-10 + accessibility concern UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 hue-only ceiling | maintainability | M | TBD | `palette` kwarg added + viridis 5-stop hex values + opt-in via `as_html(palette="viridis")` + unit test verifies palette switch + accessibility audit doc. |
 | **C94** | **Phase-2.5: Interactive HTML with embedded JavaScript for cell hover tooltips (`DF-13.4-S3`).** Story 13.4 ships embedded CSS only (D-3 explicit prohibition on `<script>` for Phase-2 offline-safety + email-safe sharing). Phase-2.5: opt-in interactive mode (`as_html(interactive=True)`) embeds vanilla JS for hover tooltips showing per-cell trial count + cost + Wilson-CI bounds. Default `interactive=False` preserves the script-free guarantee. *Surfaced via Story 13.4 spec D-10 + interactive-HTML user request anticipated UPSTREAM 2026-06-01.* | Story 13.4 D-10 decision — Phase-2 script-free ceiling | maintainability | M | TBD | `interactive` kwarg added + embedded `<script>` block with hover handler + unit test verifies `interactive=False` retains no-script invariant + integration test loads the interactive HTML in a headless browser to verify hover behavior. |
 
-**Total: 94 catalog items** (was 91 after Story 13.3 close; Story 13.4 adds C92 + C93 + C94 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 35th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 54th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Story 13.4 Opus HIGH-1 fix 2026-06-01: previous "Effort breakdown: N XS / N S / N M / N L / N XL" line removed — the running totals diverged from the actual machine-derivable count (sum was 86, not 94) due to pre-existing Story 13.3 drift propagated through Story 13.4. Per `feedback_honest_framing` + `feedback_citation_drift_first_class`: remove the unverified breakdown rather than re-asserting it on each story close. Machine-derivable counts: run `grep -c "^| \\*\\*C" docs/phase-1-5-carry-overs.md` for the row total + a per-bucket awk script if breakdown is needed.
+| **C95** | **Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability` (`DF-13.5-S1`).** Story 13.5 ships the keyword with `@guarded_fanout()` decorator (SkillsLibrary host attrs gracefully fall back to None via `getattr` — different posture from MCPLibrary's C20 carve-out). Phase-2.5: unify the host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary so all 3 carry budgets symmetrically. Shared resolution with C20 + C26 + C89. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 host-attr-fallback ceiling | correctness | M | TBD | Unified host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary; `Skill.Compare Discoverability` enforces `max_cost_usd` + `max_runtime_seconds` end-to-end across all N adapters. |
+| **C96** | **Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools (`DF-13.5-S2`).** Story 13.5 inherits the same MCP-bridge carve-out as Stories 4.4 + 13.3 (per-adapter `mcp_servers=[handle]` is NotImplementedError on Phase-1 adapters). Gated on C72 (LiteLLM MCP-bridge) + C68/C69/C73/C75 (per-adapter HostedMcpObserver wiring). When skills invoke MCP-bridged tools, the cross-adapter comparison can claim "skill X reliably activates MCP-tool-Y across runtimes." *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding for skills that reference MCP tools; integration test verifies cross-adapter MCP-skill consistency. |
+| **C97** | **Phase-2.5: Bonferroni / Holm multi-pairwise correction for `Skill.Compare Discoverability` (`DF-13.5-S3`).** Mirrors DF-13.3-S3 / C91 for the Skill domain. For N=3 adapters there are C(3,2)=3 pairwise tests; uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + adjusted-α fields on the delta dataclass. Shared resolution with C91. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg added + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
+| **C98** | **Phase-1.5: `robotframework-agentskills` cross-adapter Skill Discoverability dogfood CI matrix (`DF-13.5-S4`).** Per epic L2227: ship the cross-adapter Skill Discoverability suite to the `robotframework-agentskills` downstream repo's CI matrix using the Mock provider (zero real-API cost during routine CI); ship a separate `weekly-cross-adapter-discoverability.yml` workflow that runs against real APIs on a budget. Requires a PR to the downstream repo + a budget-bounded API-key environment. *Surfaced via Story 13.5 spec D-8 + epic L2227 dogfood mandate UPSTREAM 2026-06-01.* | Story 13.5 D-8 decision — Phase-1.5 dogfood adoption deferral (mirrors C66) | downstream-adoption | M | TBD | Downstream PR to `robotframework-agentskills` adds cross-adapter Skill Discoverability suite to CI matrix + weekly real-API workflow + 7-day monitoring confirms green across at least 4 consecutive weekly runs. |
+
+**Total: 98 catalog items** (was 94 after Story 13.4 close; Story 13.5 adds C95 + C96 + C97 + C98 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 36th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 55th consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Story 13.4 Opus HIGH-1 fix 2026-06-01: previous "Effort breakdown: N XS / N S / N M / N L / N XL" line removed — the running totals diverged from the actual machine-derivable count due to pre-existing Story 13.3 drift propagated through Story 13.4. Per `feedback_honest_framing` + `feedback_citation_drift_first_class`: remove the unverified breakdown rather than re-asserting it on each story close. Machine-derivable counts: run `grep -c "^| \\*\\*C" docs/phase-1-5-carry-overs.md` for the row total + a per-bucket awk script if breakdown is needed.
 
 ## Execution policy
 
diff --git a/docs/recipes/04-skill-author-stacked-validation.md b/docs/recipes/04-skill-author-stacked-validation.md
index 97eca4c..6253f12 100644
--- a/docs/recipes/04-skill-author-stacked-validation.md
+++ b/docs/recipes/04-skill-author-stacked-validation.md
@@ -121,6 +121,46 @@ LLM call per representative prompt — calibrate the rubric first via
 `Judge.Calibrate Rubric` (Story 12.2) and gate CI on Cohen's kappa ≥ 0.7 per
 `architecture.md` L199.
 
+## Phase 2 cross-adapter Skill Discoverability (Story 13.5 / FR4c)
+
+As of Story 13.5 (Epic 13 — 2026-06-01), Devon can compare skill activation
+across multiple Tier-1 adapters in a single call to claim "skill X is reliably
+activated by Claude AND GPT AND Copilot" with empirical evidence — symmetric to
+Mei's cross-adapter Tool Discoverability (Story 13.3 / FR10b).
+
+```robotframework
+*** Settings ***
+Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
+
+*** Test Cases ***
+Skill X Is Reliably Activated Across Claude And OpenAI
+    ${comparison}=    Skill.Compare Discoverability
+    ...    skill=${CURDIR}/skills/web-search.md
+    ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
+    ...    adapters=${{['claude_code_cli', 'codex_cli']}}
+    ...    trials_per_task=5
+    ...    max_cost_usd=10.00
+    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
+    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['codex_cli']} >= 0.7
+    # Cross-adapter significance — was the skill consistently triggered
+    # OR did one adapter wildly outperform the other?
+    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
+    Should Be True    abs(${delta.pass_at_k_delta}) < 0.3
+```
+
+Behind the `[agenteval-advanced]` optional extra (scipy + numpy from Story 13.1
+for Mann-Whitney U significance). The keyword returns a
+`SkillDiscoverabilityComparisonResult` with per-adapter `SkillDiscoverabilityResult`
++ cross-adapter Pass@k differential + per-adapter false-activation /
+missed-activation rate comparison + multi-column `CohortHeatmap` (which can
+render to HTML via Story 13.4's `as_html()` for stakeholder sharing).
+
+**Phase-1.5 dogfood deferral (DF-13.5-S4 / C98):** the
+`robotframework-agentskills` downstream repo will adopt the cross-adapter suite
+in its CI matrix (Mock provider for routine CI; a separate
+`weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a
+budget per epic L2227). Tracked as a Phase-1.5 carry-over.
+
 ## See Also
 
 - Story 7.1: `Skill.Get Activation Decision` — single-prompt activation query
diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
index 21dbb50..a6203de 100644
--- a/src/AgentEval/_heatmap/models.py
+++ b/src/AgentEval/_heatmap/models.py
@@ -26,6 +26,7 @@ if TYPE_CHECKING:
         DiscoverabilityComparisonResult,
         DiscoverabilityResult,
     )
+    from AgentEval.skills.types import SkillDiscoverabilityComparisonResult
 
 __all__ = ["CohortHeatmap"]
 
@@ -153,6 +154,44 @@ class CohortHeatmap:
         )
         return cls(tasks=tasks, models=models, cells=cells)
 
+    @classmethod
+    def from_skill_comparison(
+        cls,
+        result: SkillDiscoverabilityComparisonResult,
+    ) -> CohortHeatmap:
+        """Build a multi-column heatmap from a cross-adapter Skill comparison (Story 13.5 / FR4c).
+
+        Symmetric to ``from_comparison`` but reads the Skill-domain
+        ``pass_at_k`` field (NOT the MCP-domain ``pass_rate`` property).
+        Columns = adapter names (preserving input order). Rows = task IDs
+        (union across all per-adapter results, preserving first-encounter
+        order). Story 13.4 L-7 lesson applied: missing cells represented
+        by OMISSION from the ``cells`` tuple (NOT explicit ``None``) to
+        preserve the public ``cells: tuple[tuple[str, str, float], ...]``
+        type contract.
+
+        Args:
+            result: Story 13.5 ``SkillDiscoverabilityComparisonResult``.
+
+        Returns:
+            ``CohortHeatmap`` with one column per adapter + one row per task.
+        """
+        seen: set[str] = set()
+        tasks_list: list[str] = []
+        for adapter in result.adapters:
+            for task_result in result.per_adapter_results[adapter].per_task_results:
+                if task_result.task_id not in seen:
+                    seen.add(task_result.task_id)
+                    tasks_list.append(task_result.task_id)
+        tasks = tuple(tasks_list)
+        models = result.adapters
+        cells = tuple(
+            (task_result.task_id, adapter, task_result.pass_at_k)
+            for adapter in result.adapters
+            for task_result in result.per_adapter_results[adapter].per_task_results
+        )
+        return cls(tasks=tasks, models=models, cells=cells)
+
     def as_dict(self) -> dict[str, dict[str, float]]:
         """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
         out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
diff --git a/src/AgentEval/skills/_internal.py b/src/AgentEval/skills/_internal.py
index 1c4427f..f188166 100644
--- a/src/AgentEval/skills/_internal.py
+++ b/src/AgentEval/skills/_internal.py
@@ -33,15 +33,28 @@ from decoys) and raises `InvalidSkillDiscoverabilityTasksError` instead of
 
 from __future__ import annotations
 
+import time
 from dataclasses import dataclass
 from pathlib import Path
 from typing import Any
 
 import yaml
 
+from AgentEval._kernel.discovery import get_adapter
 from AgentEval.errors import InvalidSkillDiscoverabilityTasksError
+from AgentEval.skills.types import (
+    SkillDiscoverabilityResult,
+    SkillDiscoverabilityTaskSummary,
+    SkillTaskResult,
+)
 
-__all__ = ["SkillDiscoverabilityTask", "load_skill_discoverability_tasks"]
+__all__ = [
+    "SkillDiscoverabilityTask",
+    "load_skill_discoverability_tasks",
+    # Story 13.5 (Epic 13) — shared per-adapter helper for FR4c.
+    "build_skill_discoverability_summary",
+    "run_single_adapter_skill_discoverability",
+]
 
 
 @dataclass(frozen=True)
@@ -189,3 +202,120 @@ def load_skill_discoverability_tasks(path: str | Path) -> list[SkillDiscoverabil
         tasks.append(SkillDiscoverabilityTask(id=task_id, prompt=prompt, should_activate=should_activate))
 
     return tasks
+
+
+# --------------------------------------------------------------------------- #
+# Story 13.5 (Epic 13) — Shared per-adapter helpers for FR4c                  #
+# --------------------------------------------------------------------------- #
+
+
+def build_skill_discoverability_summary(
+    task_results: list[SkillTaskResult], total_runtime: float
+) -> SkillDiscoverabilityTaskSummary:
+    """Compute aggregate `SkillDiscoverabilityTaskSummary` across task results.
+
+    Story 13.5 extraction of `SkillsLibrary._build_discoverability_summary`
+    (Story 7.2) to module scope so both `get_discoverability` (single
+    adapter) and `get_discoverability_comparison` (Story 13.5 N-adapter)
+    compute summaries identically.
+    """
+    total_trials = sum(r.trials_run for r in task_results)
+    total_correct = sum(
+        r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed) for r in task_results
+    )
+    activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0
+
+    decoy_results = [r for r in task_results if not r.should_activate]
+    false_act_obs = sum(r.activations_observed for r in decoy_results)
+    false_act_denom = sum(r.trials_run for r in decoy_results)
+    false_activation_rate = false_act_obs / false_act_denom if false_act_denom > 0 else 0.0
+
+    should_act_results = [r for r in task_results if r.should_activate]
+    missed_obs = sum(r.trials_run - r.activations_observed for r in should_act_results)
+    missed_denom = sum(r.trials_run for r in should_act_results)
+    missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0
+
+    total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)
+
+    return SkillDiscoverabilityTaskSummary(
+        activation_accuracy=activation_accuracy,
+        false_activation_rate=false_activation_rate,
+        missed_activation_rate=missed_activation_rate,
+        total_cost_usd=total_cost,
+        total_runtime_seconds=total_runtime,
+    )
+
+
+def run_single_adapter_skill_discoverability(
+    *,
+    skill_name: str,
+    task_list: list[SkillDiscoverabilityTask],
+    adapter: str,
+    model: str | None,
+    trials_per_task: int,
+    extra_adapter_kwargs: dict[str, Any],
+    t_start: float,
+) -> SkillDiscoverabilityResult:
+    """Run Skill discoverability against ONE adapter (Story 13.5 helper extraction).
+
+    Internal helper extracted from `SkillsLibrary.get_discoverability`
+    (Story 7.2) so the cross-adapter `Compare Discoverability` keyword
+    (Story 13.5) reuses the per-adapter logic. Behavior MUST equal
+    pre-refactor; verified by Story 7.2's existing tests passing
+    unchanged.
+
+    Args:
+        skill_name: Pre-parsed skill name (from frontmatter). Used for
+            case-insensitive substring match against `response_text`.
+        task_list: Already-loaded + schema-validated skill tasks.
+        adapter: Adapter name. Resolved via `_kernel.discovery.get_adapter`.
+        model: Optional model identifier; forwarded to adapter ctor.
+        trials_per_task: Trials per task; already validated >= 1.
+        extra_adapter_kwargs: Forward-compat kwargs routed to adapter ctor.
+        t_start: Wall-clock anchor (caller-provided). Single-adapter
+            captures before YAML load; comparison uses a per-adapter
+            anchor (comparison-level wall-clock measured separately
+            per Story 13.3 HIGH-A fix).
+
+    Returns:
+        ``SkillDiscoverabilityResult`` with per-task results + summary
+        + Phase-1 hardcoded ``adapter_coverage="in_process"`` (Story
+        7.2 D-2 ratified shape).
+    """
+    adapter_cls = get_adapter(adapter)
+    ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
+    if model is not None:
+        ctor_kwargs["model"] = model
+
+    task_results: list[SkillTaskResult] = []
+    for task in task_list:
+        activations = 0
+        trial_costs: list[float] = []
+        for _ in range(trials_per_task):
+            adapter_instance = adapter_cls(**ctor_kwargs)
+            run_result = adapter_instance.run(task.prompt)
+            activated = bool(skill_name) and skill_name.lower() in run_result.response_text.lower()
+            if activated:
+                activations += 1
+            trial_costs.append(run_result.cost_usd)
+        pass_at_k = activations / trials_per_task if trials_per_task > 0 else 0.0
+        cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
+        task_results.append(
+            SkillTaskResult(
+                task_id=task.id,
+                task_prompt=task.prompt,
+                should_activate=task.should_activate,
+                trials_run=trials_per_task,
+                activations_observed=activations,
+                pass_at_k=pass_at_k,
+                competing_skills_picked={},
+                cost_per_trial_usd=cost_per_trial,
+            )
+        )
+    total_runtime = time.perf_counter() - t_start
+    summary = build_skill_discoverability_summary(task_results, total_runtime)
+    return SkillDiscoverabilityResult(
+        per_task_results=tuple(task_results),
+        summary=summary,
+        adapter_coverage="in_process",
+    )
diff --git a/src/AgentEval/skills/library.py b/src/AgentEval/skills/library.py
index 256e1eb..d2a0e77 100644
--- a/src/AgentEval/skills/library.py
+++ b/src/AgentEval/skills/library.py
@@ -78,9 +78,10 @@ from AgentEval.skills._internal import load_skill_discoverability_tasks
 from AgentEval.skills._parser import parse_frontmatter, validate_frontmatter_structure
 from AgentEval.skills.types import (
     ActivationDecision,
+    SkillDiscoverabilityComparisonResult,
+    SkillDiscoverabilityComparisonSummary,
     SkillDiscoverabilityResult,
-    SkillDiscoverabilityTaskSummary,
-    SkillTaskResult,
+    SkillPairwiseAdapterDelta,
 )
 
 __all__ = ["SkillsLibrary"]
@@ -416,43 +417,235 @@ class SkillsLibrary:
 
         skill_tasks = load_skill_discoverability_tasks(tasks)
 
-        adapter_cls = get_adapter(adapter)
-        ctor_kwargs: dict[str, Any] = dict(kwargs)
-        if model is not None:
-            ctor_kwargs["model"] = model
+        # Story 13.5 refactor: per-adapter logic extracted to
+        # `skills/_internal.run_single_adapter_skill_discoverability` so
+        # the new `Skill.Compare Discoverability` keyword reuses it
+        # without duplication. Behavior MUST equal pre-refactor —
+        # verified by Story 7.2's existing tests passing unchanged.
+        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
 
         t_start = time.perf_counter()
-        task_results: list[SkillTaskResult] = []
-        for task in skill_tasks:
-            activations = 0
-            trial_costs: list[float] = []
-            for _ in range(trials_per_task):
-                adapter_instance = adapter_cls(**ctor_kwargs)
-                result = adapter_instance.run(task.prompt)
-                activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
-                if activated:
-                    activations += 1
-                trial_costs.append(result.cost_usd)
-            pass_at_k = activations / trials_per_task if trials_per_task > 0 else 0.0
-            cost_per_trial = sum(trial_costs) / max(trials_per_task, 1)
-            task_results.append(
-                SkillTaskResult(
-                    task_id=task.id,
-                    task_prompt=task.prompt,
-                    should_activate=task.should_activate,
-                    trials_run=trials_per_task,
-                    activations_observed=activations,
-                    pass_at_k=pass_at_k,
-                    competing_skills_picked={},
-                    cost_per_trial_usd=cost_per_trial,
+        return run_single_adapter_skill_discoverability(
+            skill_name=skill_name,
+            task_list=skill_tasks,
+            adapter=adapter,
+            model=model,
+            trials_per_task=trials_per_task,
+            extra_adapter_kwargs=dict(kwargs),
+            t_start=t_start,
+        )
+
+    # --------------------------------------------------------------- #
+    # Story 13.5: Cross-adapter Skill Discoverability comparison      #
+    # (PRD FR4c). Symmetric to Story 13.3's `MCP.Compare Tool         #
+    # Discoverability` (FR10b). Behind the `[agenteval-advanced]`     #
+    # extra (Mann-Whitney U from Story 13.1).                         #
+    # --------------------------------------------------------------- #
+
+    @keyword(name="Skill.Compare Discoverability")
+    @tier(3)
+    @guarded_fanout()
+    def get_discoverability_comparison(
+        self,
+        skill: str | Path = "",
+        tasks: str | Path = "",
+        adapters: list[str] | None = None,
+        trials_per_task: int = 3,
+        max_cost_usd: float = 20.00,
+        max_runtime_seconds: float | None = None,
+        model: str | None = None,
+        polling: float | None = None,
+        **kwargs: Any,
+    ) -> SkillDiscoverabilityComparisonResult:
+        """Compares Skill Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).
+
+        [Tier 3 — Stochastic Fan-Out] — runs `Skill.Get Discoverability`
+        once per adapter against the SAME task set, then computes
+        pairwise Mann-Whitney U deltas across the per-task `pass_at_k`
+        distributions PLUS false-activation-rate + missed-activation-
+        rate deltas. Returns a `SkillDiscoverabilityComparisonResult`
+        with per-adapter results + cross-adapter deltas + multi-column
+        cohort heatmap + aggregate summary.
+
+        Requires the ``[agenteval-advanced]`` optional extra (scipy +
+        numpy) for the Mann-Whitney U cross-adapter delta computation;
+        raises ``ImportError`` on invocation WITHOUT the extra
+        (fail-fast BEFORE per-adapter fan-out — operators discovering
+        the missing extra should not pay N-adapter trial cost first).
+
+        | =Arguments= | =Description= |
+        | ``skill`` | Filesystem path to the skill ``.md`` file. |
+        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML (loaded ONCE; shared across adapters). |
+        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. |
+        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
+        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2218 (4× single-adapter typical). |
+        | ``max_runtime_seconds`` | Runtime cap. |
+        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. |
+        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 (mirrors `Get Discoverability`). |
+        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |
+
+        Returns ``SkillDiscoverabilityComparisonResult`` with
+        ``adapters`` + ``per_adapter_results`` (one
+        ``SkillDiscoverabilityResult`` per adapter) +
+        ``cross_adapter_deltas`` (C(N, 2) ``SkillPairwiseAdapterDelta``
+        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
+        ``CohortHeatmap`` via ``from_skill_comparison``) + ``summary``
+        (``SkillDiscoverabilityComparisonSummary``).
+
+        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
+        missing. Raises ``PollingDisallowedError`` when ``polling`` is
+        provided. Raises ``ValueError`` on missing ``skill`` / ``tasks``
+        / ``adapters`` (≥2 distinct required) / invalid
+        ``trials_per_task``.
+
+        Example:
+        | ${comparison}=    `Skill.Compare Discoverability`
+        | ...    skill=${CURDIR}/skills/example.md
+        | ...    tasks=${CURDIR}/discoverability/skill-tasks.yaml
+        | ...    adapters=${{['claude_code_cli', 'codex_cli']}}
+        | ...    trials_per_task=5
+        | Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
+        | Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3
+
+        Notes:
+        - Story 13.5 (Epic 13) ships this Phase-2 keyword closing Devon's cross-adapter analysis loop. Symmetric to Story 13.3's `MCP.Compare Tool Discoverability` (FR10b).
+        - PRD FR4c ratifies the cross-adapter Skill Discoverability surface; epics.md L2218-2219 ratifies the keyword signature + extended fields (per-adapter false-activation / missed-activation rate comparison).
+        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper). Mann-Whitney U is computed on the per-task ``pass_at_k`` lists per adapter; false-activation + missed-activation deltas are aggregate-summary subtractions.
+        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition.
+        - Phase-2.5 carry-overs: DF-13.5-S1 (`@guarded_fanout` cross-library budget plumbing); DF-13.5-S2 (per-adapter MCP attachment); DF-13.5-S3 (Bonferroni multi-pairwise correction); DF-13.5-S4 (`robotframework-agentskills` dogfood CI matrix).
+        - Sibling keyword: `Skill.Get Discoverability` (Phase-1 single-adapter). The ≥2-adapter validation rejects N=1 callers — use the simpler `Get` keyword for single-adapter runs.
+        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
+        # Validate args (mirrors single-adapter Get + adds N>=2 constraint).
+        if polling is not None:
+            raise PollingDisallowedError(
+                build_polling_disallowed_message(
+                    "Skill.Compare Discoverability",
+                    {"skill": str(skill), "tasks": str(tasks), "adapters": adapters},
                 )
             )
-        total_runtime = time.perf_counter() - t_start
-        summary = self._build_discoverability_summary(task_results, total_runtime)
-        return SkillDiscoverabilityResult(
-            per_task_results=tuple(task_results),
+        if not skill:
+            raise ValueError("Skill.Compare Discoverability requires `skill=<path>` kwarg")
+        if not tasks:
+            raise ValueError("Skill.Compare Discoverability requires `tasks=<yaml-path>` kwarg")
+        if trials_per_task < 1:
+            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
+        if adapters is None or len(adapters) < 2:
+            raise ValueError(
+                f"Skill.Compare Discoverability requires adapters=[<adapter_1>, "
+                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
+            )
+        if len(set(adapters)) != len(adapters):
+            raise ValueError(
+                f"Skill.Compare Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
+            )
+
+        # `[agenteval-advanced]` extras gate (Story 13.5 D-4 + L-2).
+        # Module-attr read per Story 13.3 amendment (NOT `from X import Y`
+        # which captures stale value across pytest session reload).
+        from AgentEval.stats import library as _stats_lib
+
+        if not _stats_lib._ADVANCED_AVAILABLE:
+            raise ImportError(
+                "Skill.Compare Discoverability: scipy + numpy required. "
+                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
+            )
+
+        # Parse skill frontmatter + tasks YAML ONCE (shared across adapters).
+        fm = parse_frontmatter(skill)
+        name_raw = fm.get("name")
+        skill_name = name_raw if isinstance(name_raw, str) else ""
+        skill_tasks = load_skill_discoverability_tasks(tasks)
+
+        from AgentEval._heatmap.models import CohortHeatmap
+        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
+        from AgentEval.stats.mannwhitney import compute_mann_whitney_u
+
+        # Story 13.3 HIGH-A precedent: anchor for comparison-level wall-clock.
+        compare_t_start = time.perf_counter()
+
+        per_adapter_results: dict[str, SkillDiscoverabilityResult] = {}
+        for adapter_name in adapters:
+            per_adapter_results[adapter_name] = run_single_adapter_skill_discoverability(
+                skill_name=skill_name,
+                task_list=skill_tasks,
+                adapter=adapter_name,
+                model=model,
+                trials_per_task=trials_per_task,
+                extra_adapter_kwargs=dict(kwargs),
+                t_start=time.perf_counter(),
+            )
+
+        # Build C(N, 2) pairwise deltas.
+        import itertools
+        import math as _math
+
+        cross_adapter_deltas: dict[str, SkillPairwiseAdapterDelta] = {}
+        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
+            a_result = per_adapter_results[adapter_a]
+            b_result = per_adapter_results[adapter_b]
+            rates_a = [t.pass_at_k for t in a_result.per_task_results]
+            rates_b = [t.pass_at_k for t in b_result.per_task_results]
+            if not rates_a or not rates_b:
+                continue
+            mwu = compute_mann_whitney_u(rates_a, rates_b)
+            delta_key = f"{adapter_a}_vs_{adapter_b}"
+            mean_a = sum(rates_a) / len(rates_a)
+            mean_b = sum(rates_b) / len(rates_b)
+            cross_adapter_deltas[delta_key] = SkillPairwiseAdapterDelta(
+                adapter_a=adapter_a,
+                adapter_b=adapter_b,
+                pass_at_k_delta=mean_a - mean_b,
+                pass_at_k_mann_whitney_result=mwu,
+                false_activation_rate_delta=a_result.summary.false_activation_rate
+                - b_result.summary.false_activation_rate,
+                missed_activation_rate_delta=a_result.summary.missed_activation_rate
+                - b_result.summary.missed_activation_rate,
+                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
+            )
+
+        # Build summary.
+        activation_accuracy_per_adapter = {
+            name: per_adapter_results[name].summary.activation_accuracy for name in adapters
+        }
+        best_adapter = max(
+            activation_accuracy_per_adapter,
+            key=lambda a: activation_accuracy_per_adapter[a],
+        )
+        worst_adapter = min(
+            activation_accuracy_per_adapter,
+            key=lambda a: activation_accuracy_per_adapter[a],
+        )
+        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
+        # Story 13.3 HIGH-A: comparison wall-clock measured from
+        # `compare_t_start` (NOT MAX of per-adapter, which would
+        # under-report serial execution by ~N-1×).
+        total_runtime = time.perf_counter() - compare_t_start
+        summary = SkillDiscoverabilityComparisonSummary(
+            total_cost_usd=total_cost,
+            total_runtime_seconds=total_runtime,
+            activation_accuracy_per_adapter=activation_accuracy_per_adapter,
+            best_adapter=best_adapter,
+            worst_adapter=worst_adapter,
+        )
+
+        # Build heatmap via the new classmethod. Use a shim namespace
+        # (mirrors Story 13.3 D-5 pattern) so the classmethod can read
+        # `.adapters` + `.per_adapter_results` before the full result
+        # dataclass is constructed.
+        class _ComparisonShim:
+            pass
+
+        shim = _ComparisonShim()
+        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
+        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
+        heatmap = CohortHeatmap.from_skill_comparison(shim)  # type: ignore[arg-type]
+
+        return SkillDiscoverabilityComparisonResult(
+            adapters=tuple(adapters),
+            per_adapter_results=per_adapter_results,
+            cross_adapter_deltas=cross_adapter_deltas,
+            heatmap=heatmap,
             summary=summary,
-            adapter_coverage="in_process",
         )
 
     @keyword(name="Should Activate For")
@@ -536,33 +729,9 @@ class SkillsLibrary:
                 ),
             )
 
-    def _build_discoverability_summary(
-        self, task_results: list[SkillTaskResult], total_runtime: float
-    ) -> SkillDiscoverabilityTaskSummary:
-        """Compute aggregate summary across all task results."""
-        total_trials = sum(r.trials_run for r in task_results)
-        total_correct = sum(
-            r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed)
-            for r in task_results
-        )
-        activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0
-
-        decoy_results = [r for r in task_results if not r.should_activate]
-        false_act_obs = sum(r.activations_observed for r in decoy_results)
-        false_act_denom = sum(r.trials_run for r in decoy_results)
-        false_activation_rate = false_act_obs / false_act_denom if false_act_denom > 0 else 0.0
-
-        should_act_results = [r for r in task_results if r.should_activate]
-        missed_obs = sum(r.trials_run - r.activations_observed for r in should_act_results)
-        missed_denom = sum(r.trials_run for r in should_act_results)
-        missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0
-
-        total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)
-
-        return SkillDiscoverabilityTaskSummary(
-            activation_accuracy=activation_accuracy,
-            false_activation_rate=false_activation_rate,
-            missed_activation_rate=missed_activation_rate,
-            total_cost_usd=total_cost,
-            total_runtime_seconds=total_runtime,
-        )
+    # `_build_discoverability_summary` removed Story 13.5 refactor 2026-06-01:
+    # logic extracted to `AgentEval.skills._internal.build_skill_discoverability_summary`
+    # so the new `Skill.Compare Discoverability` keyword reuses it. The
+    # only caller was `get_discoverability` which now delegates to the
+    # `run_single_adapter_skill_discoverability` helper (which calls
+    # `build_skill_discoverability_summary` internally).
diff --git a/src/AgentEval/skills/types.py b/src/AgentEval/skills/types.py
index 30334b3..a8d923e 100644
--- a/src/AgentEval/skills/types.py
+++ b/src/AgentEval/skills/types.py
@@ -12,24 +12,39 @@
 # See the License for the specific language governing permissions and
 # limitations under the License.
 
-"""Shared types for the skills sub-library (Stories 7.1 + 7.2).
+"""Shared types for the skills sub-library (Stories 7.1 + 7.2 + 13.5).
 
 Exported:
     ActivationDecision — frozen dataclass returned by `Skill.Get Activation Decision`.
     SkillTaskResult — per-task aggregated trial outcomes for `Skill.Get Discoverability`.
     SkillDiscoverabilityTaskSummary — aggregate summary for `Skill.Get Discoverability`.
     SkillDiscoverabilityResult — top-level result from `Skill.Get Discoverability`.
+
+Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c):
+    SkillDiscoverabilityComparisonResult — top-level result from `Skill.Compare Discoverability`.
+    SkillPairwiseAdapterDelta — one pairwise cross-adapter delta.
+    SkillDiscoverabilityComparisonSummary — aggregate roll-up of the comparison.
 """
 
 from __future__ import annotations
 
+from collections.abc import Mapping
 from dataclasses import dataclass, field
+from typing import TYPE_CHECKING
+
+if TYPE_CHECKING:
+    from AgentEval._heatmap.models import CohortHeatmap
+    from AgentEval.stats.types import MannWhitneyResult
 
 __all__ = [
     "ActivationDecision",
     "SkillTaskResult",
     "SkillDiscoverabilityTaskSummary",
     "SkillDiscoverabilityResult",
+    # Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c).
+    "SkillDiscoverabilityComparisonResult",
+    "SkillPairwiseAdapterDelta",
+    "SkillDiscoverabilityComparisonSummary",
 ]
 
 
@@ -127,3 +142,181 @@ class SkillDiscoverabilityResult:
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "per_task_results", tuple(self.per_task_results))
+
+
+# --------------------------------------------------------------------------- #
+# Story 13.5 (Epic 13) — cross-adapter Skill Discoverability surface (FR4c)   #
+# --------------------------------------------------------------------------- #
+
+
+@dataclass(frozen=True)
+class SkillPairwiseAdapterDelta:
+    """One pairwise cross-adapter delta within `SkillDiscoverabilityComparisonResult` (Story 13.5).
+
+    Symmetric to Story 13.3's `PairwiseAdapterDelta` but extended with
+    Skill-domain metrics (false_activation_rate_delta +
+    missed_activation_rate_delta) because Skill discoverability has TWO
+    primary failure modes (false-positive activation on decoy tasks +
+    false-negative missed activation on should-activate tasks). MCP
+    discoverability has only ONE primary failure mode.
+
+    Fields:
+        adapter_a: First adapter name.
+        adapter_b: Second adapter name (must differ from `adapter_a`).
+        pass_at_k_delta: ``mean(adapter_a per-task pass_at_k) -
+            mean(adapter_b per-task pass_at_k)``; in ``[-1.0, 1.0]``.
+            Positive → adapter_a achieves higher Pass@k.
+        pass_at_k_mann_whitney_result: Story 13.1 ``MannWhitneyResult``
+            (Mann-Whitney U on the per-task ``pass_at_k`` lists).
+        false_activation_rate_delta: ``summary.false_activation_rate(a)
+            - summary.false_activation_rate(b)``. Positive → adapter_a
+            MORE often falsely activates the skill on decoy tasks
+            (worse than adapter_b). Range: ``[-1.0, 1.0]``.
+        missed_activation_rate_delta: ``summary.missed_activation_rate(a)
+            - summary.missed_activation_rate(b)``. Positive → adapter_a
+            MORE often misses activating when it should (worse than
+            adapter_b). Range: ``[-1.0, 1.0]``.
+        significant_at_alpha_05: ``pass_at_k_mann_whitney_result.p_value
+            < 0.05``; nan-aware (Story 13.3 + 13.4 convention — nan
+            treated as not-significant).
+    """
+
+    adapter_a: str
+    adapter_b: str
+    pass_at_k_delta: float
+    pass_at_k_mann_whitney_result: MannWhitneyResult
+    false_activation_rate_delta: float
+    missed_activation_rate_delta: float
+    significant_at_alpha_05: bool
+
+    def __post_init__(self) -> None:
+        if self.adapter_a == self.adapter_b:
+            raise ValueError(
+                f"SkillPairwiseAdapterDelta requires distinct adapters; "
+                f"got adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
+            )
+        for name, val in (
+            ("pass_at_k_delta", self.pass_at_k_delta),
+            ("false_activation_rate_delta", self.false_activation_rate_delta),
+            ("missed_activation_rate_delta", self.missed_activation_rate_delta),
+        ):
+            if not (-1.0 <= val <= 1.0):
+                raise ValueError(f"{name} must be in [-1.0, 1.0]; got {val!r}")
+        import math
+
+        p = self.pass_at_k_mann_whitney_result.p_value
+        expected = (not math.isnan(p)) and p < 0.05
+        if self.significant_at_alpha_05 != expected:
+            raise ValueError(
+                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as "
+                f"not significant); got significant_at_alpha_05={self.significant_at_alpha_05!r} "
+                f"but p_value={self.pass_at_k_mann_whitney_result.p_value!r}"
+            )
+
+
+@dataclass(frozen=True)
+class SkillDiscoverabilityComparisonSummary:
+    """Aggregate roll-up of `SkillDiscoverabilityComparisonResult` (Story 13.5).
+
+    Fields:
+        total_cost_usd: Sum of per-adapter `summary.total_cost_usd`.
+        total_runtime_seconds: End-to-end wall-clock for the
+            ``Skill.Compare Discoverability`` call (what the operator
+            ACTUALLY waited for). Story 13.3 HIGH-A precedent applied.
+        activation_accuracy_per_adapter: Mapping adapter name →
+            ``summary.activation_accuracy`` from each adapter's per-run
+            ``SkillDiscoverabilityResult``.
+        best_adapter: Adapter name with the highest activation_accuracy
+            (validated in `__post_init__`).
+        worst_adapter: Adapter name with the lowest activation_accuracy
+            (validated in `__post_init__`).
+    """
+
+    total_cost_usd: float
+    total_runtime_seconds: float
+    activation_accuracy_per_adapter: Mapping[str, float]
+    best_adapter: str
+    worst_adapter: str
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "activation_accuracy_per_adapter", dict(self.activation_accuracy_per_adapter))
+        if self.best_adapter not in self.activation_accuracy_per_adapter:
+            raise ValueError(
+                f"best_adapter={self.best_adapter!r} not in "
+                f"activation_accuracy_per_adapter keys "
+                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
+            )
+        if self.worst_adapter not in self.activation_accuracy_per_adapter:
+            raise ValueError(
+                f"worst_adapter={self.worst_adapter!r} not in "
+                f"activation_accuracy_per_adapter keys "
+                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
+            )
+        # Story 13.4 Codex HIGH-2 lesson: validate best/worst match argmax/argmin.
+        max_acc = max(self.activation_accuracy_per_adapter.values())
+        min_acc = min(self.activation_accuracy_per_adapter.values())
+        if self.activation_accuracy_per_adapter[self.best_adapter] != max_acc:
+            raise ValueError(
+                f"best_adapter={self.best_adapter!r} has activation_accuracy "
+                f"{self.activation_accuracy_per_adapter[self.best_adapter]!r} but the "
+                f"max observed is {max_acc!r}"
+            )
+        if self.activation_accuracy_per_adapter[self.worst_adapter] != min_acc:
+            raise ValueError(
+                f"worst_adapter={self.worst_adapter!r} has activation_accuracy "
+                f"{self.activation_accuracy_per_adapter[self.worst_adapter]!r} but the "
+                f"min observed is {min_acc!r}"
+            )
+
+
+@dataclass(frozen=True)
+class SkillDiscoverabilityComparisonResult:
+    """Top-level result of `Skill.Compare Discoverability` (Story 13.5 / PRD FR4c).
+
+    Shape per epics.md L2218-2219 + Story 13.5 D-1 ratified shape:
+        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
+        - `per_adapter_results: Mapping[str, SkillDiscoverabilityResult]` —
+          one full `SkillDiscoverabilityResult` per adapter (mirrors what
+          `Skill.Get Discoverability` returns for the single-adapter case).
+        - `cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]` —
+          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
+        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
+          adapter; rows = task IDs). Built via
+          `CohortHeatmap.from_skill_comparison(self)`.
+        - `summary: SkillDiscoverabilityComparisonSummary` — aggregate roll-up.
+
+    Cross-consistency invariants checked in `__post_init__` (Story 13.3 +
+    13.4 lessons applied):
+        - `len(adapters) >= 2`.
+        - `set(adapters) == set(per_adapter_results.keys())`.
+        - `set(adapters) == set(heatmap.models)`.
+        - `set(adapters) == set(summary.activation_accuracy_per_adapter.keys())`.
+    """
+
+    adapters: tuple[str, ...]
+    per_adapter_results: Mapping[str, SkillDiscoverabilityResult]
+    cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]
+    heatmap: CohortHeatmap
+    summary: SkillDiscoverabilityComparisonSummary
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "adapters", tuple(self.adapters))
+        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
+        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
+        if len(self.adapters) < 2:
+            raise ValueError(f"SkillDiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
+        if set(self.adapters) != set(self.per_adapter_results.keys()):
+            raise ValueError(
+                f"adapters {sorted(self.adapters)!r} must equal "
+                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
+            )
+        if set(self.adapters) != set(self.heatmap.models):
+            raise ValueError(
+                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
+            )
+        if set(self.adapters) != set(self.summary.activation_accuracy_per_adapter.keys()):
+            raise ValueError(
+                f"adapters {sorted(self.adapters)!r} must equal "
+                f"summary.activation_accuracy_per_adapter keys "
+                f"{sorted(self.summary.activation_accuracy_per_adapter.keys())!r}"
+            )
diff --git a/tests/integration/skills/test_skill_compare_e2e.py b/tests/integration/skills/test_skill_compare_e2e.py
new file mode 100644
index 0000000..a7a5c26
--- /dev/null
+++ b/tests/integration/skills/test_skill_compare_e2e.py
@@ -0,0 +1,233 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""End-to-end integration test for `Skill.Compare Discoverability` (Story 13.5 AC-13.5.7).
+
+Per Story 13.1 + 13.3 L-4 lesson (empirical correctness verification):
+asserts CONCRETE numerical outcomes of the cross-adapter comparison —
+known stub activation patterns produce the EXPECTED ranking + p-value
+signs + false-activation / missed-activation rate orderings.
+
+3 stubs via `register_adapter()`:
+- `skill_compare_stub_a` → activates skill on EVERY trial (100% activation
+  on should_activate=True; 100% false-activation on decoys = bad).
+  Net activation_accuracy depends on the should/decoy ratio in the YAML.
+- `skill_compare_stub_b` → never activates (0% on both).
+- `skill_compare_stub_c` → activates with skill-name in response always
+  on should_activate=True tasks AND never on decoys → highest accuracy.
+
+Expected outcomes (with 3 should_activate=True + 2 decoy tasks in YAML):
+- accuracy(c) > accuracy(a) > accuracy(b) because c is "perfect", a
+  always-activates (correct on True, wrong on decoy), b always-misses.
+- summary.best_adapter == c; worst_adapter == b.
+- 3 pairwise deltas; significance varies by stub.
+- heatmap.models has 3 columns + total_cost_usd == 0.0 (epic L2221 zero-cost).
+"""
+
+from __future__ import annotations
+
+from collections.abc import Iterator
+from pathlib import Path
+from typing import Any
+
+import pytest
+
+pytest.importorskip("scipy")
+pytest.importorskip("numpy")
+
+from AgentEval._kernel import discovery  # noqa: E402
+from AgentEval._kernel.discovery import register_adapter  # noqa: E402
+from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
+from AgentEval.skills.library import SkillsLibrary  # noqa: E402
+from AgentEval.skills.types import SkillDiscoverabilityComparisonResult  # noqa: E402
+from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage  # noqa: E402
+
+
+@pytest.fixture(autouse=True)
+def _restore_adapter_registry() -> Iterator[None]:
+    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
+    try:
+        yield
+    finally:
+        discovery._registered_adapters.clear()  # noqa: SLF001
+        discovery._registered_adapters.update(snapshot)  # noqa: SLF001
+
+
+def _make_stub_always_activate(skill_name: str) -> type[InProcessAdapter]:
+    """Stub that ALWAYS mentions the skill name in its response (cost=0.0 per epic L2221)."""
+
+    class _Stub(InProcessAdapter):
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__(**kwargs)
+
+        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
+            return AgentRunResult(
+                response_text=f"I'll use {skill_name} for this.",
+                tool_calls=[],
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=0.0,
+                latency_seconds=0.001,
+                trace_id="a" * 32,
+            )
+
+    return _Stub
+
+
+def _make_stub_never_activate() -> type[InProcessAdapter]:
+    """Stub that NEVER mentions the skill (cost=0.0)."""
+
+    class _Stub(InProcessAdapter):
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__(**kwargs)
+
+        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
+            return AgentRunResult(
+                response_text="I'll just do this directly.",
+                tool_calls=[],
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=0.0,
+                latency_seconds=0.001,
+                trace_id="a" * 32,
+            )
+
+    return _Stub
+
+
+def _make_stub_perfect_by_prompt(skill_name: str, should_activate_prompts: set[str]) -> type[InProcessAdapter]:
+    """Stub that activates ONLY when the prompt matches a should-activate task.
+
+    Encodes the ground truth so it scores 100% activation_accuracy +
+    0% false_activation_rate + 0% missed_activation_rate.
+    """
+
+    class _Stub(InProcessAdapter):
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__(**kwargs)
+
+        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
+            text = f"I'll use {skill_name}." if prompt in should_activate_prompts else "Doing it directly."
+            return AgentRunResult(
+                response_text=text,
+                tool_calls=[],
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=0.0,
+                latency_seconds=0.001,
+                trace_id="a" * 32,
+            )
+
+    return _Stub
+
+
+def test_compare_3_stub_adapters_end_to_end_skill() -> None:
+    """3-stub Skill cross-adapter comparison produces expected ranking + concrete outcomes."""
+    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+
+    # Skill name (from frontmatter parsed by the keyword body).
+    skill_name = "example-search-skill"
+
+    # Read the tasks YAML to extract the should-activate prompts for the
+    # "perfect" stub's prompt-matching logic.
+    import yaml
+
+    parsed = yaml.safe_load(tasks_fixture.read_text(encoding="utf-8"))
+    should_activate_prompts = {t["prompt"] for t in parsed["tasks"] if t.get("should_activate")}
+
+    register_adapter("skill_compare_stub_a", _make_stub_always_activate(skill_name))
+    register_adapter("skill_compare_stub_b", _make_stub_never_activate())
+    register_adapter(
+        "skill_compare_stub_c",
+        _make_stub_perfect_by_prompt(skill_name, should_activate_prompts),
+    )
+
+    lib = SkillsLibrary()
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture),
+        tasks=str(tasks_fixture),
+        adapters=["skill_compare_stub_a", "skill_compare_stub_b", "skill_compare_stub_c"],
+        trials_per_task=3,
+    )
+
+    assert isinstance(result, SkillDiscoverabilityComparisonResult)
+
+    accuracies = result.summary.activation_accuracy_per_adapter
+    # c is "perfect" → highest accuracy.
+    assert accuracies["skill_compare_stub_c"] == pytest.approx(1.0)
+    # a always-activates: correct on should_activate=True (3/5), wrong on decoys (2/5).
+    assert accuracies["skill_compare_stub_a"] == pytest.approx(3 / 5)
+    # b never activates: wrong on should_activate=True (3/5 missed), correct on decoys (2/5).
+    assert accuracies["skill_compare_stub_b"] == pytest.approx(2 / 5)
+
+    assert result.summary.best_adapter == "skill_compare_stub_c"
+    assert result.summary.worst_adapter == "skill_compare_stub_b"
+
+    # Pairwise deltas keyed.
+    assert set(result.cross_adapter_deltas.keys()) == {
+        "skill_compare_stub_a_vs_skill_compare_stub_b",
+        "skill_compare_stub_a_vs_skill_compare_stub_c",
+        "skill_compare_stub_b_vs_skill_compare_stub_c",
+    }
+
+    # False-activation deltas: stub_a is worst on decoys (false_activation_rate=1.0),
+    # stub_b + stub_c are 0.0. Delta a_vs_c > 0 (a worse).
+    delta_a_vs_c = result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"]
+    assert delta_a_vs_c.false_activation_rate_delta > 0
+
+    # Missed-activation deltas: stub_b is worst (misses all should_activate),
+    # stub_c is perfect.
+    delta_b_vs_c = result.cross_adapter_deltas["skill_compare_stub_b_vs_skill_compare_stub_c"]
+    assert delta_b_vs_c.missed_activation_rate_delta > 0
+
+    # Heatmap.
+    assert result.heatmap.models == (
+        "skill_compare_stub_a",
+        "skill_compare_stub_b",
+        "skill_compare_stub_c",
+    )
+
+    # Cost: zero per epic L2221 (Story 13.3 Codex MED-1 lesson applied).
+    assert result.summary.total_cost_usd == pytest.approx(0.0)
+
+
+def test_compare_rejects_single_adapter_list() -> None:
+    """≥2 adapter requirement enforced at arg validation."""
+    register_adapter("only_one_skill", _make_stub_never_activate())
+    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+    lib = SkillsLibrary()
+    with pytest.raises(ValueError, match=">= 2 entries"):
+        lib.get_discoverability_comparison(
+            skill=str(skill_fixture),
+            tasks=str(tasks_fixture),
+            adapters=["only_one_skill"],
+            trials_per_task=1,
+        )
+
+
+def test_compare_rejects_duplicate_adapter_names() -> None:
+    """Duplicate adapter names raise ValueError."""
+    register_adapter("dup_skill", _make_stub_never_activate())
+    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+    lib = SkillsLibrary()
+    with pytest.raises(ValueError, match="distinct adapter names"):
+        lib.get_discoverability_comparison(
+            skill=str(skill_fixture),
+            tasks=str(tasks_fixture),
+            adapters=["dup_skill", "dup_skill"],
+            trials_per_task=1,
+        )
diff --git a/tests/unit/skills/test_comparison.py b/tests/unit/skills/test_comparison.py
new file mode 100644
index 0000000..6dca931
--- /dev/null
+++ b/tests/unit/skills/test_comparison.py
@@ -0,0 +1,479 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""Unit tests for `Skill.Compare Discoverability` cross-adapter surface (Story 13.5 / PRD FR4c).
+
+Coverage:
+- 3 new frozen dataclass validators (SkillDiscoverabilityComparisonResult +
+  SkillPairwiseAdapterDelta + SkillDiscoverabilityComparisonSummary).
+- `CohortHeatmap.from_skill_comparison` multi-column heatmap.
+- Pairwise delta counting (N=2 + N=3).
+- Mann-Whitney U dispatch + significance.
+- False-activation + missed-activation deltas (Skill-domain extension
+  beyond Story 13.3 D-1).
+"""
+
+from __future__ import annotations
+
+from collections.abc import Iterator
+from pathlib import Path
+from typing import Any
+
+import pytest
+
+# Phase-2 deps required for math.
+pytest.importorskip("scipy")
+pytest.importorskip("numpy")
+
+from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
+from AgentEval._kernel import discovery  # noqa: E402
+from AgentEval._kernel.discovery import register_adapter  # noqa: E402
+from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
+from AgentEval.skills.library import SkillsLibrary  # noqa: E402
+from AgentEval.skills.types import (  # noqa: E402
+    SkillDiscoverabilityComparisonResult,
+    SkillDiscoverabilityComparisonSummary,
+    SkillDiscoverabilityResult,
+    SkillDiscoverabilityTaskSummary,
+    SkillPairwiseAdapterDelta,
+    SkillTaskResult,
+)
+from AgentEval.stats.types import MannWhitneyResult  # noqa: E402
+from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage  # noqa: E402
+
+
+@pytest.fixture(autouse=True)
+def _restore_adapter_registry() -> Iterator[None]:
+    """Snapshot + restore the programmatic adapter registry per test."""
+    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
+    try:
+        yield
+    finally:
+        discovery._registered_adapters.clear()  # noqa: SLF001
+        discovery._registered_adapters.update(snapshot)  # noqa: SLF001
+
+
+# --------------------------------------------------------------------------- #
+# Helper builders                                                             #
+# --------------------------------------------------------------------------- #
+
+
+def _make_mwu(p_value: float = 0.5) -> MannWhitneyResult:
+    return MannWhitneyResult(u_statistic=10.0, p_value=p_value, effect_size_r=0.0, n_a=5, n_b=5)
+
+
+def _make_skill_result(
+    activation_accuracy: float = 0.5,
+    false_activation_rate: float = 0.0,
+    missed_activation_rate: float = 0.0,
+    n_tasks: int = 3,
+) -> SkillDiscoverabilityResult:
+    per_task = tuple(
+        SkillTaskResult(
+            task_id=f"t{i}",
+            task_prompt=f"prompt {i}",
+            should_activate=True,
+            trials_run=10,
+            activations_observed=int(activation_accuracy * 10),
+            pass_at_k=activation_accuracy,
+            competing_skills_picked={},
+            cost_per_trial_usd=0.0,
+        )
+        for i in range(n_tasks)
+    )
+    return SkillDiscoverabilityResult(
+        per_task_results=per_task,
+        summary=SkillDiscoverabilityTaskSummary(
+            activation_accuracy=activation_accuracy,
+            false_activation_rate=false_activation_rate,
+            missed_activation_rate=missed_activation_rate,
+            total_cost_usd=0.0,
+            total_runtime_seconds=0.1,
+        ),
+        adapter_coverage="in_process",
+    )
+
+
+def _make_stub(response_text: str, cost: float = 0.0) -> type[InProcessAdapter]:
+    """Stub adapter; default `cost=0.0` per Story 13.3 Codex MED-1 lesson."""
+
+    class _Stub(InProcessAdapter):
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__(**kwargs)
+
+        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
+            return AgentRunResult(
+                response_text=response_text,
+                tool_calls=[],
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=cost,
+                latency_seconds=0.001,
+                trace_id="a" * 32,
+            )
+
+    return _Stub
+
+
+@pytest.fixture
+def lib() -> SkillsLibrary:
+    return SkillsLibrary()
+
+
+@pytest.fixture
+def skill_fixture_path() -> Path:
+    return Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+
+
+@pytest.fixture
+def tasks_fixture_path() -> Path:
+    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+
+
+# --------------------------------------------------------------------------- #
+# Dataclass validators (8 tests)                                              #
+# --------------------------------------------------------------------------- #
+
+
+def test_comparison_result_rejects_single_adapter() -> None:
+    per = {"a": _make_skill_result(1.0)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a",), cells=(("t0", "a", 1.0),))
+    summary = SkillDiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        activation_accuracy_per_adapter={"a": 1.0},
+        best_adapter="a",
+        worst_adapter="a",
+    )
+    with pytest.raises(ValueError, match="len\\(adapters\\) >= 2"):
+        SkillDiscoverabilityComparisonResult(
+            adapters=("a",),
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_comparison_result_rejects_adapters_keys_mismatch() -> None:
+    per = {"a": _make_skill_result(1.0), "b": _make_skill_result(0.5)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
+    summary = SkillDiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        activation_accuracy_per_adapter={"a": 1.0, "b": 0.5},
+        best_adapter="a",
+        worst_adapter="b",
+    )
+    with pytest.raises(ValueError, match="per_adapter_results keys"):
+        SkillDiscoverabilityComparisonResult(
+            adapters=("a", "c"),
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_comparison_result_rejects_summary_keys_mismatch() -> None:
+    """summary.activation_accuracy_per_adapter must equal adapters (Story 13.4 HIGH-C)."""
+    per = {"a": _make_skill_result(1.0), "b": _make_skill_result(0.5)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
+    summary = SkillDiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        activation_accuracy_per_adapter={"x": 1.0, "y": 0.5},
+        best_adapter="x",
+        worst_adapter="y",
+    )
+    with pytest.raises(ValueError, match="activation_accuracy_per_adapter"):
+        SkillDiscoverabilityComparisonResult(
+            adapters=("a", "b"),
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_pairwise_delta_rejects_identical_adapters() -> None:
+    with pytest.raises(ValueError, match="distinct adapters"):
+        SkillPairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="a",
+            pass_at_k_delta=0.0,
+            pass_at_k_mann_whitney_result=_make_mwu(),
+            false_activation_rate_delta=0.0,
+            missed_activation_rate_delta=0.0,
+            significant_at_alpha_05=False,
+        )
+
+
+def test_pairwise_delta_rejects_out_of_range_deltas() -> None:
+    with pytest.raises(ValueError, match="pass_at_k_delta"):
+        SkillPairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="b",
+            pass_at_k_delta=1.5,
+            pass_at_k_mann_whitney_result=_make_mwu(),
+            false_activation_rate_delta=0.0,
+            missed_activation_rate_delta=0.0,
+            significant_at_alpha_05=False,
+        )
+    with pytest.raises(ValueError, match="false_activation_rate_delta"):
+        SkillPairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="b",
+            pass_at_k_delta=0.0,
+            pass_at_k_mann_whitney_result=_make_mwu(),
+            false_activation_rate_delta=-1.5,
+            missed_activation_rate_delta=0.0,
+            significant_at_alpha_05=False,
+        )
+
+
+def test_pairwise_delta_significance_consistency_check() -> None:
+    with pytest.raises(ValueError, match="significant_at_alpha_05"):
+        SkillPairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="b",
+            pass_at_k_delta=0.0,
+            pass_at_k_mann_whitney_result=_make_mwu(p_value=0.5),
+            false_activation_rate_delta=0.0,
+            missed_activation_rate_delta=0.0,
+            significant_at_alpha_05=True,  # but p > 0.05
+        )
+
+
+def test_summary_rejects_inconsistent_best_worst() -> None:
+    """best/worst must match argmax/argmin of activation_accuracy_per_adapter (Story 13.4 HIGH-B)."""
+    with pytest.raises(ValueError, match="best_adapter"):
+        SkillDiscoverabilityComparisonSummary(
+            total_cost_usd=0.0,
+            total_runtime_seconds=0.0,
+            activation_accuracy_per_adapter={"a": 1.0, "b": 0.0},
+            best_adapter="b",  # b has 0.0 but a has 1.0
+            worst_adapter="a",
+        )
+
+
+def test_summary_rejects_unknown_best_adapter() -> None:
+    with pytest.raises(ValueError, match="best_adapter"):
+        SkillDiscoverabilityComparisonSummary(
+            total_cost_usd=0.0,
+            total_runtime_seconds=0.0,
+            activation_accuracy_per_adapter={"a": 0.5},
+            best_adapter="unknown",
+            worst_adapter="a",
+        )
+
+
+# --------------------------------------------------------------------------- #
+# CohortHeatmap.from_skill_comparison (3 tests)                               #
+# --------------------------------------------------------------------------- #
+
+
+def _make_minimal_comparison(adapters: list[str]) -> SkillDiscoverabilityComparisonResult:
+    per = {a: _make_skill_result(0.5, n_tasks=2) for a in adapters}
+    cells = tuple((t.task_id, a, t.pass_at_k) for a in adapters for t in per[a].per_task_results)
+    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=tuple(adapters), cells=cells)
+    summary = SkillDiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        activation_accuracy_per_adapter=dict.fromkeys(adapters, 0.5),
+        best_adapter=adapters[0],
+        worst_adapter=adapters[0],
+    )
+    return SkillDiscoverabilityComparisonResult(
+        adapters=tuple(adapters),
+        per_adapter_results=per,
+        cross_adapter_deltas={},
+        heatmap=heatmap,
+        summary=summary,
+    )
+
+
+def test_heatmap_from_skill_comparison_2_adapters() -> None:
+    result = _make_minimal_comparison(["a", "b"])
+    h = CohortHeatmap.from_skill_comparison(result)
+    assert h.models == ("a", "b")
+    assert h.tasks == ("t0", "t1")
+
+
+def test_heatmap_from_skill_comparison_3_adapters() -> None:
+    result = _make_minimal_comparison(["a", "b", "c"])
+    h = CohortHeatmap.from_skill_comparison(result)
+    assert h.models == ("a", "b", "c")
+    assert len(h.tasks) == 2
+
+
+def test_heatmap_from_skill_comparison_pass_at_k_dispatched() -> None:
+    """Per-task pass_at_k dispatched to correct cell."""
+    per = {
+        "fast": _make_skill_result(1.0, n_tasks=2),
+        "slow": _make_skill_result(0.0, n_tasks=2),
+    }
+    cells = tuple((t.task_id, a, t.pass_at_k) for a in ("fast", "slow") for t in per[a].per_task_results)
+    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=("fast", "slow"), cells=cells)
+    summary = SkillDiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        activation_accuracy_per_adapter={"fast": 1.0, "slow": 0.0},
+        best_adapter="fast",
+        worst_adapter="slow",
+    )
+    result = SkillDiscoverabilityComparisonResult(
+        adapters=("fast", "slow"),
+        per_adapter_results=per,
+        cross_adapter_deltas={},
+        heatmap=heatmap,
+        summary=summary,
+    )
+    h = CohortHeatmap.from_skill_comparison(result)
+    data = h.as_dict()
+    assert data["t0"]["fast"] == 1.0
+    assert data["t0"]["slow"] == 0.0
+
+
+# --------------------------------------------------------------------------- #
+# Pairwise delta computation via end-to-end keyword (3 tests)                 #
+# --------------------------------------------------------------------------- #
+
+
+def test_compare_2_adapters_produces_1_pairwise_delta(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    """2 adapters → 1 pairwise delta."""
+    register_adapter("s2_act", _make_stub("example-search-skill response"))
+    register_adapter("s2_no", _make_stub("nothing happens here"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["s2_act", "s2_no"],
+        trials_per_task=3,
+    )
+    assert len(result.cross_adapter_deltas) == 1
+    assert "s2_act_vs_s2_no" in result.cross_adapter_deltas
+
+
+def test_compare_3_adapters_produces_3_pairwise_deltas(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    """3 adapters → 3 pairwise deltas (C(3,2))."""
+    register_adapter("s3_a", _make_stub("example-search-skill: yes"))
+    register_adapter("s3_b", _make_stub("nothing"))
+    register_adapter("s3_c", _make_stub("example-search-skill: maybe"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["s3_a", "s3_b", "s3_c"],
+        trials_per_task=3,
+    )
+    assert len(result.cross_adapter_deltas) == 3
+    assert set(result.cross_adapter_deltas.keys()) == {
+        "s3_a_vs_s3_b",
+        "s3_a_vs_s3_c",
+        "s3_b_vs_s3_c",
+    }
+
+
+def test_compare_pairwise_keys_preserve_input_order(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    register_adapter("zzz_first", _make_stub("nothing"))
+    register_adapter("aaa_second", _make_stub("nothing"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["zzz_first", "aaa_second"],
+        trials_per_task=3,
+    )
+    assert "zzz_first_vs_aaa_second" in result.cross_adapter_deltas
+
+
+# --------------------------------------------------------------------------- #
+# False-activation + missed-activation deltas (2 tests)                       #
+# --------------------------------------------------------------------------- #
+
+
+def test_compare_missed_activation_rate_delta(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    """Stub that NEVER activates → high missed_activation_rate.
+
+    Stub-a always activates (skill name present in response); stub-b
+    never does. missed_activation_rate_delta (b - a) > 0 → b is WORSE.
+    """
+    register_adapter("miss_a", _make_stub("example-search-skill is here"))
+    register_adapter("miss_b", _make_stub("totally unrelated"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["miss_a", "miss_b"],
+        trials_per_task=3,
+    )
+    delta = result.cross_adapter_deltas["miss_a_vs_miss_b"]
+    # a misses 0; b misses all should-activate trials → b - a > 0 wait,
+    # delta is `a - b`, so a's rate minus b's rate → negative.
+    a_summary = result.per_adapter_results["miss_a"].summary
+    b_summary = result.per_adapter_results["miss_b"].summary
+    assert b_summary.missed_activation_rate > a_summary.missed_activation_rate
+    # delta = a - b → since a < b, delta is NEGATIVE.
+    assert delta.missed_activation_rate_delta < 0
+
+
+def test_compare_false_activation_rate_delta(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    """Stub that ALWAYS activates including on decoys → high false_activation_rate.
+
+    Stub-a always activates (high false_activation on decoy tasks);
+    stub-b never activates. false_activation_rate_delta (a - b) > 0 →
+    a is WORSE on decoys.
+    """
+    register_adapter("false_a", _make_stub("example-search-skill always shouts"))
+    register_adapter("false_b", _make_stub("nothing here"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["false_a", "false_b"],
+        trials_per_task=3,
+    )
+    delta = result.cross_adapter_deltas["false_a_vs_false_b"]
+    a_summary = result.per_adapter_results["false_a"].summary
+    b_summary = result.per_adapter_results["false_b"].summary
+    assert a_summary.false_activation_rate > b_summary.false_activation_rate
+    assert delta.false_activation_rate_delta > 0
+
+
+# --------------------------------------------------------------------------- #
+# Mann-Whitney significance (1 test — already covered in MCP variant; light here) #
+# --------------------------------------------------------------------------- #
+
+
+def test_compare_identical_distributions_not_significant(
+    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
+) -> None:
+    """Identical pass-rate distributions → not significant (nan handling)."""
+    register_adapter("id_a", _make_stub("example-search-skill identical"))
+    register_adapter("id_b", _make_stub("example-search-skill identical"))
+    result = lib.get_discoverability_comparison(
+        skill=str(skill_fixture_path),
+        tasks=str(tasks_fixture_path),
+        adapters=["id_a", "id_b"],
+        trials_per_task=3,
+    )
+    delta = result.cross_adapter_deltas["id_a_vs_id_b"]
+    assert delta.pass_at_k_delta == pytest.approx(0.0)
+    assert not delta.significant_at_alpha_05
diff --git a/tests/unit/skills/test_comparison_extras_gate.py b/tests/unit/skills/test_comparison_extras_gate.py
new file mode 100644
index 0000000..e7b92e6
--- /dev/null
+++ b/tests/unit/skills/test_comparison_extras_gate.py
@@ -0,0 +1,111 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
+#
+# Unless required by applicable law or agreed to in writing, software
+# distributed under the License is distributed on an "AS IS" BASIS,
+# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
+# See the License for the specific language governing permissions and
+# limitations under the License.
+
+"""ImportError-gate tests for `Skill.Compare Discoverability` (Story 13.5 / L-2 lesson).
+
+Mirrors `tests/unit/discoverability/test_comparison_extras_gate.py`
+(Story 13.3) + `tests/unit/stats/test_advanced_extras_gate.py` (Story
+13.1) + `tests/unit/telemetry/test_backends_otlp_extras_gate.py` (Story
+13.2) discipline: NO module-top `pytest.importorskip` so the
+gate-coverage tests run in BOTH the WITH-extras and WITHOUT-extras CI
+environments.
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+
+def test_skill_comparison_schema_importable_without_extra() -> None:
+    """`from AgentEval.skills.types import SkillDiscoverabilityComparisonResult` works without extras."""
+    from AgentEval.skills.types import (  # noqa: F401
+        SkillDiscoverabilityComparisonResult,
+        SkillDiscoverabilityComparisonSummary,
+        SkillPairwiseAdapterDelta,
+    )
+
+
+def test_compare_keyword_raises_import_error_when_advanced_extra_missing(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """`Skill.Compare Discoverability` raises ImportError when `_ADVANCED_AVAILABLE=False`.
+
+    Story 13.5 L-2 + Story 13.3 amendment: gate read via module-attr
+    (`_stats_lib._ADVANCED_AVAILABLE`) so the monkeypatch is observed
+    even across pytest session-wide module reload.
+    """
+    from AgentEval.skills.library import SkillsLibrary
+    from AgentEval.stats import library as stats_lib
+
+    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
+
+    lib = SkillsLibrary()
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+    tasks_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+    with pytest.raises(ImportError, match="agenteval-advanced"):
+        lib.get_discoverability_comparison(
+            skill=str(fixture_path),
+            tasks=str(tasks_path),
+            adapters=["any_a", "any_b"],
+            trials_per_task=1,
+        )
+
+
+def test_compare_keyword_import_error_message_contract(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """ImportError message carries the verbatim install hint with `Skill.Compare Discoverability` prefix."""
+    from AgentEval.skills.library import SkillsLibrary
+    from AgentEval.stats import library as stats_lib
+
+    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
+    tasks_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
+    lib = SkillsLibrary()
+    with pytest.raises(ImportError) as exc_info:
+        lib.get_discoverability_comparison(
+            skill=str(fixture_path),
+            tasks=str(tasks_path),
+            adapters=["a", "b"],
+            trials_per_task=1,
+        )
+    msg = str(exc_info.value)
+    assert "Skill.Compare Discoverability" in msg
+    assert "scipy + numpy required" in msg
+    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
+
+
+def test_compare_keyword_arg_validation_runs_before_extras_gate(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """Arg validation (skill / adapters / tasks) runs BEFORE the extras gate.
+
+    Mirrors Story 13.3's analogous test — operator with both missing
+    extra AND missing args should see the arg error first (more
+    actionable).
+    """
+    from AgentEval.skills.library import SkillsLibrary
+    from AgentEval.stats import library as stats_lib
+
+    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
+    lib = SkillsLibrary()
+    with pytest.raises(ValueError, match="skill"):
+        lib.get_discoverability_comparison(
+            skill="",  # empty — arg validation should fire first.
+            tasks="some.yaml",
+            adapters=["a", "b"],
+            trials_per_task=1,
+        )
```

codex
Reviewing Story 13.5 against the diff and the live tree. I’m starting with the code paths and targeted probes, then I’ll run the specific tests and `robot --dryrun` claim rather than relying on the story notes.
exec
/bin/bash -lc 'rg -n "get_discoverability_comparison|run_single_adapter_skill_discoverability|from_skill_comparison|SkillDiscoverabilityComparisonResult|C95|C96|C97|C98" src tests docs _bmad-output -S' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: rg: command not found

exec
/bin/bash -lc 'wc -l /tmp/story-13-5-review.diff' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
2108 /tmp/story-13-5-review.diff

exec
/bin/bash -lc 'git status --short' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
 A _bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md
 M _bmad-output/implementation-artifacts/deferred-work.md
 M _bmad-output/implementation-artifacts/sprint-status.yaml
 M docs/contracts/stability-surface.md
 M docs/keywords/SkillsLibrary.html
 M docs/phase-1-5-carry-overs.md
 M docs/recipes/04-skill-author-stacked-validation.md
 M src/AgentEval/_heatmap/models.py
 M src/AgentEval/skills/_internal.py
 M src/AgentEval/skills/library.py
 M src/AgentEval/skills/types.py
 A tests/integration/skills/test_skill_compare_e2e.py
 A tests/unit/skills/test_comparison.py
 A tests/unit/skills/test_comparison_extras_gate.py
?? _bmad-output/cross-llm-reviews/13-5-claude-opus-findings.md
?? _bmad-output/cross-llm-reviews/13-5-claude-sonnet-findings.md
?? _bmad-output/cross-llm-reviews/13-5-codex-findings.md

codex
`rg` isn’t installed here, so I’m switching to `grep`/`find`. Next I’m checking the implementation and the exact test files the story claims passed, then I’ll run the targeted pytest and dry-run commands.
exec
/bin/bash -lc "sed -n '260,820p' src/AgentEval/skills/library.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:

        Raises ``InvalidSkillFrontmatterError`` when any required field
        is missing OR has the wrong type. The error message lists the
        offending field(s) so the test author can remediate. Error
        format per FR59 + `docs/contracts/error-class-hierarchy.md`
        L96-104.

        Example:
        | ${frontmatter} =    `Get Frontmatter`    ${CURDIR}/skills/example.md
        | `Should Be Valid Frontmatter`    ${frontmatter}
        | ${fm_broken} =    Create Dictionary    name=just-a-name
        | Run Keyword And Expect Error    InvalidSkillFrontmatterError*    `Should Be Valid Frontmatter`    ${fm_broken}

        Notes:
        - PRD FR1 ratifies the required-fields contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - ADR-019 ratifies the Phase-1 plain-``@keyword`` form; Phase-2 will adopt the AssertionEngine matcher idiom.
        - Sibling keyword: `Get Frontmatter` (raw dict — feed its return into this validator).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        validate_frontmatter_structure(frontmatter)

    @keyword(name="Get Activation Decision")
    @tier(3)
    @guarded_fanout()
    def get_activation_decision(
        self,
        skill: str | Path,
        prompt: str,
        adapter: str = "generic",
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> ActivationDecision:
        """Queries an agent and infers whether the given skill was activated (PRD FR1 + AC-7.1).

        [Tier 3 — Stochastic Fan-Out] — sends ``prompt`` to the named
        adapter and returns an ``ActivationDecision`` with ``activated``
        (bool), ``reasoning`` (the response text), ``cost_usd``, and
        ``latency_seconds``. Phase-1 activation heuristic: case-
        insensitive substring check of the skill's ``name`` field in
        ``result.response_text``. Phase-2 will adopt a more robust
        classifier (DF-7.1-S1 / C55).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |
        | ``prompt`` | Prompt text to send to the agent. |
        | ``adapter`` | Adapter identifier registered via the ``agenteval.coding_agents`` entry-points group. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.1.5. Use `Stat.Run N Times` for fan-out instead. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``InvalidSkillFrontmatterError`` when the skill
        file cannot be read or parsed as valid YAML. Structurally
        invalid frontmatter (missing required fields) does NOT raise
        here — missing ``name`` silently yields ``activated=False``.

        Example (illustrative — assumes a real adapter):
        | ${decision} =    `Get Activation Decision`    ${CURDIR}/skills/web-search.md    prompt=Find news about Robot Framework
        | Should Be True    ${decision.activated}
        | Should Be True    ${decision.cost_usd} >= 0.0

        Notes:
        - PRD FR1 ratifies the skill-activation surface; AC-7.1 ratifies the keyword contract.
        - Phase-1 heuristic per AC-7.1.4 — substring check on skill ``name`` in response text. Phase-2 classifier deferred per DF-7.1-S1 / C55.
        - FR28 prohibits polling — use `Stat.Run N Times` for statistical assertions instead.
        - Sibling keyword: `Should Activate For` (assertion wrapper); `Get Discoverability` (multi-task cohort evaluation).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Get Activation Decision",
                    {"skill": str(skill), "prompt": prompt, "adapter": adapter},
                )
            )
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""
        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        adapter_instance = adapter_cls(**ctor_kwargs)
        result = adapter_instance.run(prompt)
        activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
        return ActivationDecision(
            activated=activated,
            reasoning=result.response_text,
            cost_usd=result.cost_usd,
            latency_seconds=result.latency_seconds,
        )

    @keyword(name="Get Discoverability")
    @tier(3)
    @guarded_fanout()
    def get_discoverability(
        self,
        skill: str | Path,
        tasks: str | Path,
        adapter: str = "generic",
        model: str | None = None,
        trials_per_task: int = 3,
        polling: float | None = None,
        **kwargs: Any,
    ) -> SkillDiscoverabilityResult:
        """Runs a cohort discoverability evaluation across N tasks × M trials (PRD FR4b).

        [Tier 3 — Stochastic Fan-Out] — runs ``trials_per_task`` adapter
        calls per task across all tasks in the YAML, returning a
        ``SkillDiscoverabilityResult`` with ``per_task_results``,
        ``summary``, and ``adapter_coverage``. Phase-1 activation
        heuristic per AC-7.2.4: case-insensitive substring check of the
        skill ``name`` field in each trial's ``response_text``. Phase-2
        adds structured-response schema for competing-skills-picked
        detection (DF-7.2-S1 / C56).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``trials_per_task`` | Number of adapter calls per task. Defaults to ``3``. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.2.6. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``ValueError`` when ``trials_per_task < 1``.
        Raises ``InvalidSkillFrontmatterError`` when the skill file is
        unreadable / un-parseable. Raises
        ``InvalidSkillDiscoverabilityTasksError`` when the tasks YAML
        is structurally invalid.

        Example (illustrative — assumes a real adapter):
        | ${disc} =    `Get Discoverability`    ${CURDIR}/skills/web-search.md    ${CURDIR}/tasks/web-search.yaml    trials_per_task=5
        | Should Be True    ${disc.summary.activation_accuracy} >= 0.6
        | FOR    ${task_result}    IN    @{disc.per_task_results}
        |     Log    ${task_result.task_id}: ${task_result.pass_at_k}
        | END

        Notes:
        - PRD FR4b ratifies the cohort-discoverability contract; AC-7.2 ratifies the keyword surface.
        - Phase-1 activation heuristic per AC-7.2.4. Phase-2 structured-response classifier deferred per DF-7.2-S1 / C56.
        - FR28 prohibits polling — fan-out via this keyword's own ``trials_per_task`` or via `Stat.Run N Times`.
        - Sibling keywords: `Get Activation Decision` (single-task variant); `Should Activate For` (assertion wrapper).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Get Discoverability",
                    {"skill": str(skill), "tasks": str(tasks), "adapter": adapter},
                )
            )
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1, got {trials_per_task}")
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""

        skill_tasks = load_skill_discoverability_tasks(tasks)

        # Story 13.5 refactor: per-adapter logic extracted to
        # `skills/_internal.run_single_adapter_skill_discoverability` so
        # the new `Skill.Compare Discoverability` keyword reuses it
        # without duplication. Behavior MUST equal pre-refactor —
        # verified by Story 7.2's existing tests passing unchanged.
        from AgentEval.skills._internal import run_single_adapter_skill_discoverability

        t_start = time.perf_counter()
        return run_single_adapter_skill_discoverability(
            skill_name=skill_name,
            task_list=skill_tasks,
            adapter=adapter,
            model=model,
            trials_per_task=trials_per_task,
            extra_adapter_kwargs=dict(kwargs),
            t_start=t_start,
        )

    # --------------------------------------------------------------- #
    # Story 13.5: Cross-adapter Skill Discoverability comparison      #
    # (PRD FR4c). Symmetric to Story 13.3's `MCP.Compare Tool         #
    # Discoverability` (FR10b). Behind the `[agenteval-advanced]`     #
    # extra (Mann-Whitney U from Story 13.1).                         #
    # --------------------------------------------------------------- #

    @keyword(name="Skill.Compare Discoverability")
    @tier(3)
    @guarded_fanout()
    def get_discoverability_comparison(
        self,
        skill: str | Path = "",
        tasks: str | Path = "",
        adapters: list[str] | None = None,
        trials_per_task: int = 3,
        max_cost_usd: float = 20.00,
        max_runtime_seconds: float | None = None,
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> SkillDiscoverabilityComparisonResult:
        """Compares Skill Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).

        [Tier 3 — Stochastic Fan-Out] — runs `Skill.Get Discoverability`
        once per adapter against the SAME task set, then computes
        pairwise Mann-Whitney U deltas across the per-task `pass_at_k`
        distributions PLUS false-activation-rate + missed-activation-
        rate deltas. Returns a `SkillDiscoverabilityComparisonResult`
        with per-adapter results + cross-adapter deltas + multi-column
        cohort heatmap + aggregate summary.

        Requires the ``[agenteval-advanced]`` optional extra (scipy +
        numpy) for the Mann-Whitney U cross-adapter delta computation;
        raises ``ImportError`` on invocation WITHOUT the extra
        (fail-fast BEFORE per-adapter fan-out — operators discovering
        the missing extra should not pay N-adapter trial cost first).

        | =Arguments= | =Description= |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML (loaded ONCE; shared across adapters). |
        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. |
        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2218 (4× single-adapter typical). |
        | ``max_runtime_seconds`` | Runtime cap. |
        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 (mirrors `Get Discoverability`). |
        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |

        Returns ``SkillDiscoverabilityComparisonResult`` with
        ``adapters`` + ``per_adapter_results`` (one
        ``SkillDiscoverabilityResult`` per adapter) +
        ``cross_adapter_deltas`` (C(N, 2) ``SkillPairwiseAdapterDelta``
        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
        ``CohortHeatmap`` via ``from_skill_comparison``) + ``summary``
        (``SkillDiscoverabilityComparisonSummary``).

        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
        missing. Raises ``PollingDisallowedError`` when ``polling`` is
        provided. Raises ``ValueError`` on missing ``skill`` / ``tasks``
        / ``adapters`` (≥2 distinct required) / invalid
        ``trials_per_task``.

        Example:
        | ${comparison}=    `Skill.Compare Discoverability`
        | ...    skill=${CURDIR}/skills/example.md
        | ...    tasks=${CURDIR}/discoverability/skill-tasks.yaml
        | ...    adapters=${{['claude_code_cli', 'codex_cli']}}
        | ...    trials_per_task=5
        | Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
        | Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3

        Notes:
        - Story 13.5 (Epic 13) ships this Phase-2 keyword closing Devon's cross-adapter analysis loop. Symmetric to Story 13.3's `MCP.Compare Tool Discoverability` (FR10b).
        - PRD FR4c ratifies the cross-adapter Skill Discoverability surface; epics.md L2218-2219 ratifies the keyword signature + extended fields (per-adapter false-activation / missed-activation rate comparison).
        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper). Mann-Whitney U is computed on the per-task ``pass_at_k`` lists per adapter; false-activation + missed-activation deltas are aggregate-summary subtractions.
        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition.
        - Phase-2.5 carry-overs: DF-13.5-S1 (`@guarded_fanout` cross-library budget plumbing); DF-13.5-S2 (per-adapter MCP attachment); DF-13.5-S3 (Bonferroni multi-pairwise correction); DF-13.5-S4 (`robotframework-agentskills` dogfood CI matrix).
        - Sibling keyword: `Skill.Get Discoverability` (Phase-1 single-adapter). The ≥2-adapter validation rejects N=1 callers — use the simpler `Get` keyword for single-adapter runs.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        # Validate args (mirrors single-adapter Get + adds N>=2 constraint).
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Skill.Compare Discoverability",
                    {"skill": str(skill), "tasks": str(tasks), "adapters": adapters},
                )
            )
        if not skill:
            raise ValueError("Skill.Compare Discoverability requires `skill=<path>` kwarg")
        if not tasks:
            raise ValueError("Skill.Compare Discoverability requires `tasks=<yaml-path>` kwarg")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        if adapters is None or len(adapters) < 2:
            raise ValueError(
                f"Skill.Compare Discoverability requires adapters=[<adapter_1>, "
                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
            )
        if len(set(adapters)) != len(adapters):
            raise ValueError(
                f"Skill.Compare Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
            )

        # `[agenteval-advanced]` extras gate (Story 13.5 D-4 + L-2).
        # Module-attr read per Story 13.3 amendment (NOT `from X import Y`
        # which captures stale value across pytest session reload).
        from AgentEval.stats import library as _stats_lib

        if not _stats_lib._ADVANCED_AVAILABLE:
            raise ImportError(
                "Skill.Compare Discoverability: scipy + numpy required. "
                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
            )

        # Parse skill frontmatter + tasks YAML ONCE (shared across adapters).
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""
        skill_tasks = load_skill_discoverability_tasks(tasks)

        from AgentEval._heatmap.models import CohortHeatmap
        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
        from AgentEval.stats.mannwhitney import compute_mann_whitney_u

        # Story 13.3 HIGH-A precedent: anchor for comparison-level wall-clock.
        compare_t_start = time.perf_counter()

        per_adapter_results: dict[str, SkillDiscoverabilityResult] = {}
        for adapter_name in adapters:
            per_adapter_results[adapter_name] = run_single_adapter_skill_discoverability(
                skill_name=skill_name,
                task_list=skill_tasks,
                adapter=adapter_name,
                model=model,
                trials_per_task=trials_per_task,
                extra_adapter_kwargs=dict(kwargs),
                t_start=time.perf_counter(),
            )

        # Build C(N, 2) pairwise deltas.
        import itertools
        import math as _math

        cross_adapter_deltas: dict[str, SkillPairwiseAdapterDelta] = {}
        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
            a_result = per_adapter_results[adapter_a]
            b_result = per_adapter_results[adapter_b]
            rates_a = [t.pass_at_k for t in a_result.per_task_results]
            rates_b = [t.pass_at_k for t in b_result.per_task_results]
            if not rates_a or not rates_b:
                continue
            mwu = compute_mann_whitney_u(rates_a, rates_b)
            delta_key = f"{adapter_a}_vs_{adapter_b}"
            mean_a = sum(rates_a) / len(rates_a)
            mean_b = sum(rates_b) / len(rates_b)
            cross_adapter_deltas[delta_key] = SkillPairwiseAdapterDelta(
                adapter_a=adapter_a,
                adapter_b=adapter_b,
                pass_at_k_delta=mean_a - mean_b,
                pass_at_k_mann_whitney_result=mwu,
                false_activation_rate_delta=a_result.summary.false_activation_rate
                - b_result.summary.false_activation_rate,
                missed_activation_rate_delta=a_result.summary.missed_activation_rate
                - b_result.summary.missed_activation_rate,
                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
            )

        # Build summary.
        activation_accuracy_per_adapter = {
            name: per_adapter_results[name].summary.activation_accuracy for name in adapters
        }
        best_adapter = max(
            activation_accuracy_per_adapter,
            key=lambda a: activation_accuracy_per_adapter[a],
        )
        worst_adapter = min(
            activation_accuracy_per_adapter,
            key=lambda a: activation_accuracy_per_adapter[a],
        )
        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
        # Story 13.3 HIGH-A: comparison wall-clock measured from
        # `compare_t_start` (NOT MAX of per-adapter, which would
        # under-report serial execution by ~N-1×).
        total_runtime = time.perf_counter() - compare_t_start
        summary = SkillDiscoverabilityComparisonSummary(
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
            activation_accuracy_per_adapter=activation_accuracy_per_adapter,
            best_adapter=best_adapter,
            worst_adapter=worst_adapter,
        )

        # Build heatmap via the new classmethod. Use a shim namespace
        # (mirrors Story 13.3 D-5 pattern) so the classmethod can read
        # `.adapters` + `.per_adapter_results` before the full result
        # dataclass is constructed.
        class _ComparisonShim:
            pass

        shim = _ComparisonShim()
        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
        heatmap = CohortHeatmap.from_skill_comparison(shim)  # type: ignore[arg-type]

        return SkillDiscoverabilityComparisonResult(
            adapters=tuple(adapters),
            per_adapter_results=per_adapter_results,
            cross_adapter_deltas=cross_adapter_deltas,
            heatmap=heatmap,
            summary=summary,
        )

    @keyword(name="Should Activate For")
    @tier(2)
    def should_activate_for(
        self,
        prompt: str,
        skill: str | Path,
        adapter: str = "generic",
        model: str | None = None,
        polling: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Asserts that the given skill activates for the given prompt (PRD FR4d).

        [Tier 2 — Stochastic Single-Shot] — sends ``prompt`` to the
        adapter once and asserts the skill name appears in the response
        text. Phase-1 activation heuristic per AC-7.2.5: case-insensitive
        substring check of the skill ``name`` field in
        ``result.response_text`` (same heuristic as `Get Activation Decision`).

        | =Arguments= | =Description= |
        | ``prompt`` | Natural-language prompt to test. |
        | ``skill`` | Filesystem path to the skill ``.md`` file. |
        | ``adapter`` | Adapter identifier. Defaults to ``"generic"``. |
        | ``model`` | Optional model override forwarded to the adapter constructor. |
        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 / AC-7.2.6. |
        | ``**kwargs`` | Additional kwargs forwarded to the adapter constructor. |

        Raises ``PollingDisallowedError`` when ``polling`` is provided
        (FR28). Raises ``SkillDidNotActivateError`` on no-activation
        with diagnostic fields (``prompt``, ``skill_path``,
        ``skill_name``, ``competing_skill`` (None in Phase-1),
        ``reasoning``, ``fix_suggestion``). Raises
        ``InvalidSkillFrontmatterError`` on YAML / file failure.

        Note: missing / empty / non-string ``name`` field causes the
        activation check to always evaluate False — this keyword raises
        ``SkillDidNotActivateError`` unconditionally in that case
        (same as `Get Activation Decision` per AC-7.1.4).

        Example (illustrative — assumes a real adapter):
        | `Should Activate For`    Find news about Robot Framework    ${CURDIR}/skills/web-search.md
        | Run Keyword And Expect Error    SkillDidNotActivateError*    `Should Activate For`    Calculate 2+2    ${CURDIR}/skills/web-search.md

        Notes:
        - PRD FR4d ratifies the activation-assertion contract; AC-7.2.5 + AC-7.2.6 ratify the keyword surface.
        - Phase-1 heuristic per AC-7.1.4 — substring check on skill ``name`` in response text.
        - FR28 prohibits polling — fan-out via `Stat.Run N Times` if statistical evidence is needed.
        - Sibling keywords: `Get Activation Decision` (returns decision instead of raising); `Get Discoverability` (multi-task cohort).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if polling is not None:
            raise PollingDisallowedError(
                build_polling_disallowed_message(
                    "Should Activate For",
                    {"prompt": prompt, "skill": str(skill), "adapter": adapter},
                )
            )
        fm = parse_frontmatter(skill)
        name_raw = fm.get("name")
        skill_name = name_raw if isinstance(name_raw, str) else ""

        adapter_cls = get_adapter(adapter)
        ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            ctor_kwargs["model"] = model
        adapter_instance = adapter_cls(**ctor_kwargs)
        result = adapter_instance.run(prompt)
        activated = bool(skill_name) and skill_name.lower() in result.response_text.lower()
        if not activated:
            raise SkillDidNotActivateError(
                f"Skill '{skill_name}' did not activate for prompt.",
                prompt=prompt,
                skill_path=str(skill),
                skill_name=skill_name,
                competing_skill=None,
                reasoning=result.response_text,
                fix_suggestion=(
                    "Rephrase prompt to match the skill description, or revise the skill "
                    "description to better match this prompt pattern."
                ),
            )

    # `_build_discoverability_summary` removed Story 13.5 refactor 2026-06-01:
    # logic extracted to `AgentEval.skills._internal.build_skill_discoverability_summary`
    # so the new `Skill.Compare Discoverability` keyword reuses it. The
    # only caller was `get_discoverability` which now delegates to the
    # `run_single_adapter_skill_discoverability` helper (which calls
    # `build_skill_discoverability_summary` internally).

exec
/bin/bash -lc "sed -n '1,260p' src/AgentEval/skills/library.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions
# on a single physical line. Per-line 120-char limit waived for this
# file per Phase 6 docstring-refresh proposal (2026-05-26).

"""Skill sub-library — static-inspection keywords for skill `.md` files.

Story 2.1 ships 5 Tier-1 keywords (per architecture L620 Decision-1 +
PRD FR1 + epics.md Epic 2 Story 2.1):

- `Get Frontmatter` — parse a skill `.md`'s YAML frontmatter into a dict.
- `Get Description` — return the `description` field.
- `Get Allowed Tools` — return the `allowed-tools` list.
- `Get Disable Model Invocation` — return the `disable-model-invocation` bool.
- `Should Be Valid Frontmatter` — structural validator (Phase-1 plain
  `@keyword`; full AssertionEngine matcher deferred to Phase-2 per
  ADR-022 catalog row).

Every method is `@tier(1)`-annotated (deterministic, ≤50 ms per call on
typical 5 KB inputs per NFR-PERF-02). Tier-1 keywords do NOT touch the
provider, the trace store, or external services; they read the local
`.md` file + parse YAML only.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval.skills.library    WITH NAME    Skill

    *** Test Cases ***
    Skill File Has Correct Description
        ${desc}=    Skill.Get Description    skills/example.md
        Should Be Equal    ${desc}    Example skill for testing.

**NOTE (per Phase 6 review):** unlike other AgentEval sub-libraries,
`SkillsLibrary` is NOT registered in `_SUB_LIBRARIES` and is NOT
composed under the top-level `AgentEval` library (DF-7.1-S1 / name
collision with `SubagentsLibrary.Get Frontmatter`). All 8 keywords
must be imported via the direct path shown in the Usage block above.

Phase-1 limitations explicitly documented:
- `Should Be Valid Frontmatter` is a plain `@keyword`-decorated function,
  NOT a `robotframework-assertion-engine` matcher. The Phase-1 manual-
  validation contract is load-bearing; Phase-2 (ADR-022 adoption) re-
  wires it with the full operator-chain idiom.
- The verb allowlist (`tests/unit/conventions/test_keyword_name_idiom.py`
  `_VERB_ALLOWLIST`) is extended with `"should"` per Story 1b.6 Dev
  Notes growth policy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.tier import tier
from AgentEval._kernel.tier_acl import build_polling_disallowed_message
from AgentEval.errors import PollingDisallowedError, SkillDidNotActivateError
from AgentEval.skills._internal import load_skill_discoverability_tasks
from AgentEval.skills._parser import parse_frontmatter, validate_frontmatter_structure
from AgentEval.skills.types import (
    ActivationDecision,
    SkillDiscoverabilityComparisonResult,
    SkillDiscoverabilityComparisonSummary,
    SkillDiscoverabilityResult,
    SkillPairwiseAdapterDelta,
)

__all__ = ["SkillsLibrary"]

# Browser-Library-style docstring migration marker (Phase 6, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


class SkillsLibrary:
    """Static-inspection keywords for skill `.md` files [Tier 1 — Deterministic].

    All 5 public methods are `@keyword`-decorated + `@tier(1)`-annotated
    per Story 1b.6 conventions. The class holds no mutable state; each
    call re-parses the target file so the keywords are stateless +
    parallel-safe under `pabot --processes N`.
    """

    @keyword(name="Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parses the YAML frontmatter at the head of a skill ``.md`` file (PRD FR1).

        [Tier 1 — Deterministic] — pure file-read + YAML parse; no
        provider, no trace store. Returns the raw parsed YAML as a
        ``dict[str, Any]``. Does NOT enforce the required-fields
        contract — see `Should Be Valid Frontmatter` for structural
        validation, OR the typed getters (`Get Description`,
        `Get Allowed Tools`, etc.) which validate during projection.
        Median ≤ 50 ms per call on the 5 KB reference fixture.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` on YAML / file-level
        structural failure (missing file, broken YAML, missing ``---``
        delimiters, frontmatter not a mapping). Error format per FR59 +
        `docs/contracts/error-class-hierarchy.md` L96-104.

        Example:
        | ${frontmatter} =    `Get Frontmatter`    ${CURDIR}/skills/example.md
        | Should Be Equal    ${frontmatter}[name]    example-skill
        | Should Contain    ${frontmatter}[allowed-tools]    Bash

        Notes:
        - PRD FR1 ratifies the YAML frontmatter parse + dict-return contract.
        - Performance budget: NFR-PERF-02 (median ≤ 50 ms per call).
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation` (typed-validated projections); `Should Be Valid Frontmatter` (structural validator).
        - Parallel surface: `SubagentsLibrary.Get Frontmatter` for sub-agent ``.md`` files (different validation rules).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return parse_frontmatter(path)

    @keyword(name="Get Description")
    @tier(1)
    def get_description(self, path: str | Path) -> str:
        """Returns the ``description`` field from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a ``description``-field non-empty-string check.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR the ``description`` field is missing / non-string /
        empty.

        Example:
        | ${desc} =    `Get Description`    ${CURDIR}/skills/example.md
        | Should Contain    ${desc}    example skill
        | Should Be True    len('${desc}') > 0

        Notes:
        - PRD FR1 ratifies the description-field projection contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Frontmatter` (raw dict); `Should Be Valid Frontmatter` (all-fields validator).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return str(self._read_and_validate(path)["description"])

    @keyword(name="Get Allowed Tools")
    @tier(1)
    def get_allowed_tools(self, path: str | Path) -> list[str]:
        """Returns the ``allowed-tools`` list from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a ``list[str]`` type check. The list MAY be empty (a skill
        with no tool allowlist is valid).

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR ``allowed-tools`` is not a list of strings.

        Example:
        | @{tools} =    `Get Allowed Tools`    ${CURDIR}/skills/example.md
        | Should Contain    ${tools}    Bash
        | Should Contain    ${tools}    Read
        | Length Should Be    ${tools}    3

        Notes:
        - PRD FR1 ratifies the allowed-tools projection contract.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Frontmatter` (raw dict); `Get Disable Model Invocation` (companion projection).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return list(self._read_and_validate(path)["allowed-tools"])

    @keyword(name="Get Disable Model Invocation")
    @tier(1)
    def get_disable_model_invocation(self, path: str | Path) -> bool:
        """Returns the ``disable-model-invocation`` bool from a skill ``.md`` file's frontmatter (PRD FR1).

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a strict bool type check. YAML coercion rules:

        - ``true``/``false``/``yes``/``no``/``on``/``off`` parse to Python
          bool (PyYAML 1.1 semantics) — accepted.
        - ``1``/``0`` integers parse to Python int — **rejected**
          (``isinstance(value, bool)`` is False for ints).
        - String forms like ``"true"`` are **rejected** — must be unquoted.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the skill ``.md`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidSkillFrontmatterError`` when the frontmatter is
        invalid OR ``disable-model-invocation`` is not a bool.

        Example:
        | ${disabled} =    `Get Disable Model Invocation`    ${CURDIR}/skills/example.md
        | Should Be Equal    ${disabled}    ${FALSE}                                      # Default for most skills.
        | ${disabled} =    `Get Disable Model Invocation`    ${CURDIR}/skills/static-only.md
        | Should Be Equal    ${disabled}    ${TRUE}

        Notes:
        - PRD FR1 ratifies the disable-model-invocation projection contract.
        - Strict bool typing — int / string forms rejected. The PyYAML 1.1 coercion of unquoted ``true``/``yes`` etc. to Python bool IS accepted.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keyword: `Get Allowed Tools` (companion projection).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return bool(self._read_and_validate(path)["disable-model-invocation"])

    def _read_and_validate(self, path: str | Path) -> dict[str, Any]:
        """Parse + structurally-validate a skill `.md` file once per call.

        Internal helper that consolidates the parse + validate steps
        shared by `Get Description` / `Get Allowed Tools` / `Get
        Disable Model Invocation`. Story 2.1 code-review B2 fix: the
        earlier per-keyword `parse_frontmatter` + `validate_frontmatter_structure`
        call pair iterated `REQUIRED_FIELDS` once per call; this
        helper makes the cost one read + one parse + one validation
        sweep per public-keyword invocation, matching the NFR-PERF-02
        budget framing.

        Tier-1 callers that need ALL fields should call `Get Frontmatter`
        once + `Should Be Valid Frontmatter` on the result; chained
        per-field getters each incur ONE I/O + parse cycle (cache-free
        by design — `SkillsLibrary` is stateless under `pabot --processes N`).
        """
        frontmatter = parse_frontmatter(path)
        validate_frontmatter_structure(frontmatter, file_path=str(path))
        return frontmatter

    @keyword(name="Should Be Valid Frontmatter")
    @tier(1)
    def should_be_valid_frontmatter(self, frontmatter: dict[str, Any]) -> None:
        """Asserts a parsed frontmatter dict has the 4 required fields with correct types (PRD FR1).

        [Tier 1 — Deterministic] — structural validator. Required fields:
        ``name`` (str), ``description`` (str), ``allowed-tools``
        (``list[str]``), ``disable-model-invocation`` (bool). Phase-1
        plain ``@keyword`` per ADR-019 catalog row; full AssertionEngine
        matcher deferred to Phase-2.

        | =Arguments= | =Description= |
        | ``frontmatter`` | The dict returned by `Get Frontmatter`. |


exec
/bin/bash -lc 'find tests/unit/skills -maxdepth 1 -type f | sort' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
tests/unit/skills/__init__.py
tests/unit/skills/test_activation_decision.py
tests/unit/skills/test_comparison.py
tests/unit/skills/test_comparison_extras_gate.py
tests/unit/skills/test_discoverability.py
tests/unit/skills/test_library.py
tests/unit/skills/test_robot_integration.robot

exec
/bin/bash -lc "grep -RIn \"def get_discoverability_comparison\\|def run_single_adapter_skill_discoverability\\|def from_skill_comparison\\|class SkillDiscoverabilityComparisonResult\\|\\*\\*C95\\|\\*\\*C96\\|\\*\\*C97\\|\\*\\*C98\" src tests docs _bmad-output" in /home/many/workspace/robotframework-agenteval
 succeeded in 838ms:
src/AgentEval/_heatmap/models.py:158:    def from_skill_comparison(
src/AgentEval/skills/library.py:448:    def get_discoverability_comparison(
src/AgentEval/skills/types.py:273:class SkillDiscoverabilityComparisonResult:
src/AgentEval/skills/_internal.py:249:def run_single_adapter_skill_discoverability(
docs/phase-1-5-carry-overs.md:123:| **C95** | **Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability` (`DF-13.5-S1`).** Story 13.5 ships the keyword with `@guarded_fanout()` decorator (SkillsLibrary host attrs gracefully fall back to None via `getattr` — different posture from MCPLibrary's C20 carve-out). Phase-2.5: unify the host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary so all 3 carry budgets symmetrically. Shared resolution with C20 + C26 + C89. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 host-attr-fallback ceiling | correctness | M | TBD | Unified host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary; `Skill.Compare Discoverability` enforces `max_cost_usd` + `max_runtime_seconds` end-to-end across all N adapters. |
docs/phase-1-5-carry-overs.md:124:| **C96** | **Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools (`DF-13.5-S2`).** Story 13.5 inherits the same MCP-bridge carve-out as Stories 4.4 + 13.3 (per-adapter `mcp_servers=[handle]` is NotImplementedError on Phase-1 adapters). Gated on C72 (LiteLLM MCP-bridge) + C68/C69/C73/C75 (per-adapter HostedMcpObserver wiring). When skills invoke MCP-bridged tools, the cross-adapter comparison can claim "skill X reliably activates MCP-tool-Y across runtimes." *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding for skills that reference MCP tools; integration test verifies cross-adapter MCP-skill consistency. |
docs/phase-1-5-carry-overs.md:125:| **C97** | **Phase-2.5: Bonferroni / Holm multi-pairwise correction for `Skill.Compare Discoverability` (`DF-13.5-S3`).** Mirrors DF-13.3-S3 / C91 for the Skill domain. For N=3 adapters there are C(3,2)=3 pairwise tests; uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + adjusted-α fields on the delta dataclass. Shared resolution with C91. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg added + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
docs/phase-1-5-carry-overs.md:126:| **C98** | **Phase-1.5: `robotframework-agentskills` cross-adapter Skill Discoverability dogfood CI matrix (`DF-13.5-S4`).** Per epic L2227: ship the cross-adapter Skill Discoverability suite to the `robotframework-agentskills` downstream repo's CI matrix using the Mock provider (zero real-API cost during routine CI); ship a separate `weekly-cross-adapter-discoverability.yml` workflow that runs against real APIs on a budget. Requires a PR to the downstream repo + a budget-bounded API-key environment. *Surfaced via Story 13.5 spec D-8 + epic L2227 dogfood mandate UPSTREAM 2026-06-01.* | Story 13.5 D-8 decision — Phase-1.5 dogfood adoption deferral (mirrors C66) | downstream-adoption | M | TBD | Downstream PR to `robotframework-agentskills` adds cross-adapter Skill Discoverability suite to CI matrix + weekly real-API workflow + 7-day monitoring confirms green across at least 4 consecutive weekly runs. |
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:19:  class SkillDiscoverabilityComparisonResult:
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:94:def get_discoverability_comparison(
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:144:def run_single_adapter_skill_discoverability(
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:233:- **C95** `DF-13.5-S1` — Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability`.
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:234:- **C96** `DF-13.5-S2` — Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools.
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:235:- **C97** `DF-13.5-S3` — Phase-2.5: Multi-pairwise Bonferroni/Holm correction.
_bmad-output/implementation-artifacts/13-5-compare-skill-discoverability-cross-adapter-fr4c.md:236:- **C98** `DF-13.5-S4` — Phase-1.5: `robotframework-agentskills` cross-adapter dogfood CI matrix + `weekly-cross-adapter-discoverability.yml` real-API budget workflow (per epic L2227).
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:36:10. **C95-C98 carry-over completeness**: 4 carry-overs catalogued. Verify each row has all 7 columns (ID/Description/Source/Priority/Effort/Owner/AC).
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:81:+  class SkillDiscoverabilityComparisonResult:
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:156:+def get_discoverability_comparison(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:206:+def run_single_adapter_skill_discoverability(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:295:+- **C95** `DF-13.5-S1` — Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability`.
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:296:+- **C96** `DF-13.5-S2` — Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools.
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:297:+- **C97** `DF-13.5-S3` — Phase-2.5: Multi-pairwise Bonferroni/Holm correction.
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:298:+- **C98** `DF-13.5-S4` — Phase-1.5: `robotframework-agentskills` cross-adapter dogfood CI matrix + `weekly-cross-adapter-discoverability.yml` real-API budget workflow (per epic L2227).
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:500:+| **C95** | **Phase-2.5: `@guarded_fanout` cross-library budget plumbing for `Skill.Compare Discoverability` (`DF-13.5-S1`).** Story 13.5 ships the keyword with `@guarded_fanout()` decorator (SkillsLibrary host attrs gracefully fall back to None via `getattr` — different posture from MCPLibrary's C20 carve-out). Phase-2.5: unify the host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary so all 3 carry budgets symmetrically. Shared resolution with C20 + C26 + C89. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 host-attr-fallback ceiling | correctness | M | TBD | Unified host-instance budget plumbing across MCPLibrary + SkillsLibrary + OrchestrationLibrary; `Skill.Compare Discoverability` enforces `max_cost_usd` + `max_runtime_seconds` end-to-end across all N adapters. |
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:501:+| **C96** | **Phase-2.5: Per-adapter MCP attachment for skills that bridge to MCP tools (`DF-13.5-S2`).** Story 13.5 inherits the same MCP-bridge carve-out as Stories 4.4 + 13.3 (per-adapter `mcp_servers=[handle]` is NotImplementedError on Phase-1 adapters). Gated on C72 (LiteLLM MCP-bridge) + C68/C69/C73/C75 (per-adapter HostedMcpObserver wiring). When skills invoke MCP-bridged tools, the cross-adapter comparison can claim "skill X reliably activates MCP-tool-Y across runtimes." *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding for skills that reference MCP tools; integration test verifies cross-adapter MCP-skill consistency. |
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:502:+| **C97** | **Phase-2.5: Bonferroni / Holm multi-pairwise correction for `Skill.Compare Discoverability` (`DF-13.5-S3`).** Mirrors DF-13.3-S3 / C91 for the Skill domain. For N=3 adapters there are C(3,2)=3 pairwise tests; uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + adjusted-α fields on the delta dataclass. Shared resolution with C91. *Surfaced via Story 13.5 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.5 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg added + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:503:+| **C98** | **Phase-1.5: `robotframework-agentskills` cross-adapter Skill Discoverability dogfood CI matrix (`DF-13.5-S4`).** Per epic L2227: ship the cross-adapter Skill Discoverability suite to the `robotframework-agentskills` downstream repo's CI matrix using the Mock provider (zero real-API cost during routine CI); ship a separate `weekly-cross-adapter-discoverability.yml` workflow that runs against real APIs on a budget. Requires a PR to the downstream repo + a budget-bounded API-key environment. *Surfaced via Story 13.5 spec D-8 + epic L2227 dogfood mandate UPSTREAM 2026-06-01.* | Story 13.5 D-8 decision — Phase-1.5 dogfood adoption deferral (mirrors C66) | downstream-adoption | M | TBD | Downstream PR to `robotframework-agentskills` adds cross-adapter Skill Discoverability suite to CI matrix + weekly real-API workflow + 7-day monitoring confirms green across at least 4 consecutive weekly runs. |
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:577:+    def from_skill_comparison(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:699:+def run_single_adapter_skill_discoverability(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:848:+    def get_discoverability_comparison(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:1274:+class SkillDiscoverabilityComparisonResult:
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:2393:    def get_discoverability_comparison(
_bmad-output/cross-llm-reviews/13-5-codex-findings.md:2960:/bin/bash -lc "grep -RIn \"def get_discoverability_comparison\\|def run_single_adapter_skill_discoverability\\|def from_skill_comparison\\|class SkillDiscoverabilityComparisonResult\\|\\*\\*C95\\|\\*\\*C96\\|\\*\\*C97\\|\\*\\*C98\" src tests docs _bmad-output" in /home/many/workspace/robotframework-agenteval

codex
The main implementation is loaded. I’m checking the helper, validators, and guardrail decorator next because several of the probes hinge on exact call ordering and dataclass behavior rather than just green tests.
exec
/bin/bash -lc "sed -n '1,280p' src/AgentEval/_heatmap/models.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""``CohortHeatmap`` dataclass + ASCII + dict + HTML renderers (Story 8b.2 + 13.3 + 13.4)."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import (
        DiscoverabilityComparisonResult,
        DiscoverabilityResult,
    )
    from AgentEval.skills.types import SkillDiscoverabilityComparisonResult

__all__ = ["CohortHeatmap"]


# Story 13.4 (Epic 13 / PRD FR55) — Pass@k color gradient for `as_html()`.
# 5-stop hue palette mapping `pass_rate ∈ [0.0, 1.0]` → background + text
# hex colors (text chosen for WCAG AA contrast on the background). Boundaries:
#   [0.0, 0.2) → red (high failure)
#   [0.2, 0.4) → orange
#   [0.4, 0.6) → yellow
#   [0.6, 0.8) → lime
#   [0.8, 1.0] → green (high success)
# Phase-2.5 carry-over DF-13.4-S2 / C93 tracks a color-blind-safe palette
# mode (viridis/magma sequential per WCAG 2.1 AA).
_PASS_RATE_PALETTE: Final[tuple[tuple[float, str, str], ...]] = (
    # (lower_bound_inclusive, background_hex, text_hex)
    (0.0, "#ef4444", "#ffffff"),  # red — high failure
    (0.2, "#f97316", "#ffffff"),  # orange
    (0.4, "#eab308", "#0f172a"),  # yellow
    (0.6, "#84cc16", "#0f172a"),  # lime
    (0.8, "#22c55e", "#ffffff"),  # green — high success
)
# Missing cell (cell[(task, model)] not present in `cells`): light gray.
_MISSING_CELL_STYLE: Final[tuple[str, str]] = ("#e5e7eb", "#0f172a")


def _color_for_pass_rate(rate: float | None) -> tuple[str, str]:
    """Map a Pass@k rate to (background_hex, text_hex) per `_PASS_RATE_PALETTE`.

    Args:
        rate: Pass@k value in ``[0.0, 1.0]``, or ``None`` for a missing cell.

    Returns:
        ``(background_hex, text_hex)`` tuple.

    Edge cases:
        - ``None`` → light gray (`_MISSING_CELL_STYLE`).
        - ``rate == 1.0`` → top stop (green; the [0.8, 1.0] entry).
        - ``rate < 0.0`` → first stop (red); not validated upstream so
          defensively clamps to the bottom rather than raising.
    """
    if rate is None:
        return _MISSING_CELL_STYLE
    # Linear scan: walk the palette + return the HIGHEST entry whose lower
    # bound is `<=` the rate. The palette is sorted ascending by lower bound
    # so we walk forward and remember the last match.
    bg, txt = _PASS_RATE_PALETTE[0][1], _PASS_RATE_PALETTE[0][2]
    for lower, candidate_bg, candidate_txt in _PASS_RATE_PALETTE:
        if rate >= lower:
            bg, txt = candidate_bg, candidate_txt
    return (bg, txt)


@dataclass(frozen=True)
class CohortHeatmap:
    """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).

    Phase-1: single-model heatmap (rows = tasks, single column = model).
    Multi-model comparison (rows = tasks, columns = models) is Phase-2.

    The model name in Phase-1 defaults to ``"default"`` unless the caller
    provides one via ``from_discoverability(result, model_name=...)``.
    """

    tasks: tuple[str, ...]
    models: tuple[str, ...]
    # Mapping: cell[(task_id, model_name)] = pass_at_k.
    # Stored as a frozen-friendly tuple of (task, model, value) triples so the
    # dataclass remains hashable.
    cells: tuple[tuple[str, str, float], ...]

    @classmethod
    def from_discoverability(
        cls,
        result: DiscoverabilityResult,
        *,
        model_name: str = "default",
    ) -> CohortHeatmap:
        """Build a single-model heatmap from a ``DiscoverabilityResult``.

        Args:
            result: Story 4.4 ``DiscoverabilityResult``.
            model_name: Column label for the single-model column.

        Returns:
            ``CohortHeatmap`` instance with one column.
        """
        tasks = tuple(t.task_id for t in result.per_task_results)
        cells = tuple((t.task_id, model_name, t.pass_rate) for t in result.per_task_results)
        return cls(tasks=tasks, models=(model_name,), cells=cells)

    @classmethod
    def from_comparison(
        cls,
        result: DiscoverabilityComparisonResult,
    ) -> CohortHeatmap:
        """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).

        Columns = adapter names (preserving input order from ``result.adapters``).
        Rows = task IDs (union across all per-adapter results, preserving
        first-encounter order — defensively handles the edge case where a
        stub adapter dropped a task; in production all adapters run the
        SAME task set so the union equals each adapter's task list).

        Args:
            result: Story 13.3 ``DiscoverabilityComparisonResult``.

        Returns:
            ``CohortHeatmap`` with one column per adapter + one row per task.
        """
        # Build the row list as the union preserving first-encounter order.
        seen: set[str] = set()
        tasks_list: list[str] = []
        for adapter in result.adapters:
            for task_result in result.per_adapter_results[adapter].per_task_results:
                if task_result.task_id not in seen:
                    seen.add(task_result.task_id)
                    tasks_list.append(task_result.task_id)
        tasks = tuple(tasks_list)
        models = result.adapters
        cells = tuple(
            (task_result.task_id, adapter, task_result.pass_rate)
            for adapter in result.adapters
            for task_result in result.per_adapter_results[adapter].per_task_results
        )
        return cls(tasks=tasks, models=models, cells=cells)

    @classmethod
    def from_skill_comparison(
        cls,
        result: SkillDiscoverabilityComparisonResult,
    ) -> CohortHeatmap:
        """Build a multi-column heatmap from a cross-adapter Skill comparison (Story 13.5 / FR4c).

        Symmetric to ``from_comparison`` but reads the Skill-domain
        ``pass_at_k`` field (NOT the MCP-domain ``pass_rate`` property).
        Columns = adapter names (preserving input order). Rows = task IDs
        (union across all per-adapter results, preserving first-encounter
        order). Story 13.4 L-7 lesson applied: missing cells represented
        by OMISSION from the ``cells`` tuple (NOT explicit ``None``) to
        preserve the public ``cells: tuple[tuple[str, str, float], ...]``
        type contract.

        Args:
            result: Story 13.5 ``SkillDiscoverabilityComparisonResult``.

        Returns:
            ``CohortHeatmap`` with one column per adapter + one row per task.
        """
        seen: set[str] = set()
        tasks_list: list[str] = []
        for adapter in result.adapters:
            for task_result in result.per_adapter_results[adapter].per_task_results:
                if task_result.task_id not in seen:
                    seen.add(task_result.task_id)
                    tasks_list.append(task_result.task_id)
        tasks = tuple(tasks_list)
        models = result.adapters
        cells = tuple(
            (task_result.task_id, adapter, task_result.pass_at_k)
            for adapter in result.adapters
            for task_result in result.per_adapter_results[adapter].per_task_results
        )
        return cls(tasks=tasks, models=models, cells=cells)

    def as_dict(self) -> dict[str, dict[str, float]]:
        """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
        out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
        for task, model, value in self.cells:
            out.setdefault(task, {})[model] = value
        return out

    def as_ascii(self) -> str:
        """ASCII heatmap with box-drawing characters.

        Rows = tasks, columns = models, cells = Pass@k as 2-decimal float.
        Empty input → ``"(empty heatmap)"`` placeholder.
        """
        if not self.tasks or not self.models:
            return "(empty heatmap)"

        data = self.as_dict()
        # Story 8b.2 v0.2.0 kilo/minimax cross-LLM review HIGH-1 patch
        # (2026-05-26): missing cells render as " — " sentinel (em-dash with
        # spaces) instead of silently substituting 0.0, which was
        # indistinguishable from a genuine 0% pass-rate. Operators can now
        # tell missing-from-data apart from real-zero.
        _missing = " — "

        def _fmt(task: str, model: str) -> str:
            value = data.get(task, {}).get(model)
            return _missing if value is None else f"{value:.2f}"

        # Compute column widths.
        task_col_width = max(len("Task"), *(len(t) for t in self.tasks))
        model_widths: dict[str, int] = {}
        for model in self.models:
            cells = [_fmt(task, model) for task in self.tasks]
            model_widths[model] = max(len(model), *(len(c) for c in cells))

        # Render header row.
        header_cells = [
            "Task".ljust(task_col_width),
            *(model.ljust(model_widths[model]) for model in self.models),
        ]
        header_line = "│ " + " │ ".join(header_cells) + " │"

        # Separator line (top + below header + bottom).
        sep_parts = [
            "─" * (task_col_width + 2),
            *("─" * (model_widths[model] + 2) for model in self.models),
        ]
        top_line = "┌" + "┬".join(sep_parts) + "┐"
        mid_line = "├" + "┼".join(sep_parts) + "┤"
        bot_line = "└" + "┴".join(sep_parts) + "┘"

        # Body rows.
        body_lines: list[str] = []
        for task in self.tasks:
            cells = [task.ljust(task_col_width)]
            for model in self.models:
                cells.append(_fmt(task, model).ljust(model_widths[model]))
            body_lines.append("│ " + " │ ".join(cells) + " │")

        return "\n".join([top_line, header_line, mid_line, *body_lines, bot_line])

    def as_html(self) -> str:
        """`as_html` — render the heatmap as a standalone HTML document with embedded CSS (Story 13.4 / PRD FR55).

        Returns a complete HTML5 document — `<!DOCTYPE html>` declaration,
        `<html>` root, `<head>` (containing `<meta charset>` + `<title>` +
        `<style>`), and `<body>` containing a `<table>` with header row +
        one row per task. Each Pass@k cell carries inline
        `style="background-color: <hex>; color: <text-hex>;"` for the
        color gradient.

        All styling embedded in `<head><style>...</style>`. NO external
        stylesheet links, NO external image references, NO `<script>`
        elements — operators can email the file or save to shared
        storage and view offline.

        Empty heatmap (no tasks OR no models): returns a minimal valid
        document with `<body><p>(empty heatmap)</p></body>` (symmetric
        with `as_ascii()`'s `"(empty heatmap)"` sentinel).

        Pass@k color gradient (5-stop hue palette; text color chosen for
        WCAG AA contrast):
            - [0.0, 0.2) → red (#ef4444 bg / #ffffff text)
            - [0.2, 0.4) → orange (#f97316 bg / #ffffff text)
            - [0.4, 0.6) → yellow (#eab308 bg / #0f172a text)
            - [0.6, 0.8) → lime (#84cc16 bg / #0f172a text)

exec
/bin/bash -lc "sed -n '1,360p' src/AgentEval/skills/types.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared types for the skills sub-library (Stories 7.1 + 7.2 + 13.5).

Exported:
    ActivationDecision — frozen dataclass returned by `Skill.Get Activation Decision`.
    SkillTaskResult — per-task aggregated trial outcomes for `Skill.Get Discoverability`.
    SkillDiscoverabilityTaskSummary — aggregate summary for `Skill.Get Discoverability`.
    SkillDiscoverabilityResult — top-level result from `Skill.Get Discoverability`.

Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c):
    SkillDiscoverabilityComparisonResult — top-level result from `Skill.Compare Discoverability`.
    SkillPairwiseAdapterDelta — one pairwise cross-adapter delta.
    SkillDiscoverabilityComparisonSummary — aggregate roll-up of the comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentEval._heatmap.models import CohortHeatmap
    from AgentEval.stats.types import MannWhitneyResult

__all__ = [
    "ActivationDecision",
    "SkillTaskResult",
    "SkillDiscoverabilityTaskSummary",
    "SkillDiscoverabilityResult",
    # Story 13.5 (Epic 13) — cross-adapter comparison surface (FR4c).
    "SkillDiscoverabilityComparisonResult",
    "SkillPairwiseAdapterDelta",
    "SkillDiscoverabilityComparisonSummary",
]


@dataclass(frozen=True)
class ActivationDecision:
    """Result of `Skill.Get Activation Decision` [Tier 3].

    Fields:
        activated: True iff the skill name was found in the agent response text
            (case-insensitive substring match — Phase-1 heuristic per AC-7.1.4).
        reasoning: Full agent response text used for the activation inference.
        cost_usd: LLM call cost in USD from the adapter run.
        latency_seconds: Wall-clock seconds for the adapter run.
    """

    activated: bool
    reasoning: str
    cost_usd: float
    latency_seconds: float


@dataclass(frozen=True)
class SkillTaskResult:
    """Per-task aggregated trial outcomes for `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        task_id: The task's `id` field from the YAML.
        task_prompt: The task's `prompt` field.
        should_activate: Whether the skill SHOULD have activated for this task.
        trials_run: Number of adapter calls made for this task.
        activations_observed: Number of trials where the skill name appeared
            in the adapter response (Phase-1 heuristic — case-insensitive
            substring match).
        pass_at_k: Activation rate estimate (activations_observed / trials_run,
            or 0.0 when trials_run == 0). Phase-1 simplification — Phase-2 will
            wire Wilson CI lower bound from Story 6.3 stats.
        competing_skills_picked: Phase-1 always `{}` — competing skill detection
            deferred to Phase-2 (DF-7.2-S1 / C56). Phase-1 heuristic cannot
            determine which other skill the agent chose.
        cost_per_trial_usd: Average adapter cost per trial in USD.
    """

    task_id: str
    task_prompt: str
    should_activate: bool
    trials_run: int
    activations_observed: int
    pass_at_k: float
    competing_skills_picked: dict[str, int] = field(default_factory=dict)
    cost_per_trial_usd: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "competing_skills_picked", dict(self.competing_skills_picked))


@dataclass(frozen=True)
class SkillDiscoverabilityTaskSummary:
    """Aggregate summary for `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        activation_accuracy: Fraction of trials where the keyword activated
            correctly (i.e., activated when should_activate=True AND did not
            activate when should_activate=False).
        false_activation_rate: Fraction of decoy-task trials (should_activate=False)
            where the skill incorrectly activated.
        missed_activation_rate: Fraction of should-activate-task trials
            (should_activate=True) where the skill failed to activate.
        total_cost_usd: Sum of all adapter trial costs.
        total_runtime_seconds: Wall-clock seconds for the full cohort run.
    """

    activation_accuracy: float
    false_activation_rate: float
    missed_activation_rate: float
    total_cost_usd: float
    total_runtime_seconds: float


@dataclass(frozen=True)
class SkillDiscoverabilityResult:
    """Top-level result from `Skill.Get Discoverability` (Story 7.2 / FR4b).

    Fields:
        per_task_results: Tuple of `SkillTaskResult` instances in YAML task order.
        summary: Aggregated `SkillDiscoverabilityTaskSummary` across all tasks.
        adapter_coverage: Phase-1 always `"in_process"` — skills use
            `InProcessAdapter` from Story 1b.4 which is fully observable.
            NOT `mcp_coverage` (which is MCP-server-specific per ADR-016;
            D-2 pre-create-story drift fix 2026-05-21).
    """

    per_task_results: tuple[SkillTaskResult, ...]
    summary: SkillDiscoverabilityTaskSummary
    adapter_coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_task_results", tuple(self.per_task_results))


# --------------------------------------------------------------------------- #
# Story 13.5 (Epic 13) — cross-adapter Skill Discoverability surface (FR4c)   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SkillPairwiseAdapterDelta:
    """One pairwise cross-adapter delta within `SkillDiscoverabilityComparisonResult` (Story 13.5).

    Symmetric to Story 13.3's `PairwiseAdapterDelta` but extended with
    Skill-domain metrics (false_activation_rate_delta +
    missed_activation_rate_delta) because Skill discoverability has TWO
    primary failure modes (false-positive activation on decoy tasks +
    false-negative missed activation on should-activate tasks). MCP
    discoverability has only ONE primary failure mode.

    Fields:
        adapter_a: First adapter name.
        adapter_b: Second adapter name (must differ from `adapter_a`).
        pass_at_k_delta: ``mean(adapter_a per-task pass_at_k) -
            mean(adapter_b per-task pass_at_k)``; in ``[-1.0, 1.0]``.
            Positive → adapter_a achieves higher Pass@k.
        pass_at_k_mann_whitney_result: Story 13.1 ``MannWhitneyResult``
            (Mann-Whitney U on the per-task ``pass_at_k`` lists).
        false_activation_rate_delta: ``summary.false_activation_rate(a)
            - summary.false_activation_rate(b)``. Positive → adapter_a
            MORE often falsely activates the skill on decoy tasks
            (worse than adapter_b). Range: ``[-1.0, 1.0]``.
        missed_activation_rate_delta: ``summary.missed_activation_rate(a)
            - summary.missed_activation_rate(b)``. Positive → adapter_a
            MORE often misses activating when it should (worse than
            adapter_b). Range: ``[-1.0, 1.0]``.
        significant_at_alpha_05: ``pass_at_k_mann_whitney_result.p_value
            < 0.05``; nan-aware (Story 13.3 + 13.4 convention — nan
            treated as not-significant).
    """

    adapter_a: str
    adapter_b: str
    pass_at_k_delta: float
    pass_at_k_mann_whitney_result: MannWhitneyResult
    false_activation_rate_delta: float
    missed_activation_rate_delta: float
    significant_at_alpha_05: bool

    def __post_init__(self) -> None:
        if self.adapter_a == self.adapter_b:
            raise ValueError(
                f"SkillPairwiseAdapterDelta requires distinct adapters; "
                f"got adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
            )
        for name, val in (
            ("pass_at_k_delta", self.pass_at_k_delta),
            ("false_activation_rate_delta", self.false_activation_rate_delta),
            ("missed_activation_rate_delta", self.missed_activation_rate_delta),
        ):
            if not (-1.0 <= val <= 1.0):
                raise ValueError(f"{name} must be in [-1.0, 1.0]; got {val!r}")
        import math

        p = self.pass_at_k_mann_whitney_result.p_value
        expected = (not math.isnan(p)) and p < 0.05
        if self.significant_at_alpha_05 != expected:
            raise ValueError(
                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as "
                f"not significant); got significant_at_alpha_05={self.significant_at_alpha_05!r} "
                f"but p_value={self.pass_at_k_mann_whitney_result.p_value!r}"
            )


@dataclass(frozen=True)
class SkillDiscoverabilityComparisonSummary:
    """Aggregate roll-up of `SkillDiscoverabilityComparisonResult` (Story 13.5).

    Fields:
        total_cost_usd: Sum of per-adapter `summary.total_cost_usd`.
        total_runtime_seconds: End-to-end wall-clock for the
            ``Skill.Compare Discoverability`` call (what the operator
            ACTUALLY waited for). Story 13.3 HIGH-A precedent applied.
        activation_accuracy_per_adapter: Mapping adapter name →
            ``summary.activation_accuracy`` from each adapter's per-run
            ``SkillDiscoverabilityResult``.
        best_adapter: Adapter name with the highest activation_accuracy
            (validated in `__post_init__`).
        worst_adapter: Adapter name with the lowest activation_accuracy
            (validated in `__post_init__`).
    """

    total_cost_usd: float
    total_runtime_seconds: float
    activation_accuracy_per_adapter: Mapping[str, float]
    best_adapter: str
    worst_adapter: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_accuracy_per_adapter", dict(self.activation_accuracy_per_adapter))
        if self.best_adapter not in self.activation_accuracy_per_adapter:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} not in "
                f"activation_accuracy_per_adapter keys "
                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
            )
        if self.worst_adapter not in self.activation_accuracy_per_adapter:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} not in "
                f"activation_accuracy_per_adapter keys "
                f"{sorted(self.activation_accuracy_per_adapter.keys())!r}"
            )
        # Story 13.4 Codex HIGH-2 lesson: validate best/worst match argmax/argmin.
        max_acc = max(self.activation_accuracy_per_adapter.values())
        min_acc = min(self.activation_accuracy_per_adapter.values())
        if self.activation_accuracy_per_adapter[self.best_adapter] != max_acc:
            raise ValueError(
                f"best_adapter={self.best_adapter!r} has activation_accuracy "
                f"{self.activation_accuracy_per_adapter[self.best_adapter]!r} but the "
                f"max observed is {max_acc!r}"
            )
        if self.activation_accuracy_per_adapter[self.worst_adapter] != min_acc:
            raise ValueError(
                f"worst_adapter={self.worst_adapter!r} has activation_accuracy "
                f"{self.activation_accuracy_per_adapter[self.worst_adapter]!r} but the "
                f"min observed is {min_acc!r}"
            )


@dataclass(frozen=True)
class SkillDiscoverabilityComparisonResult:
    """Top-level result of `Skill.Compare Discoverability` (Story 13.5 / PRD FR4c).

    Shape per epics.md L2218-2219 + Story 13.5 D-1 ratified shape:
        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
        - `per_adapter_results: Mapping[str, SkillDiscoverabilityResult]` —
          one full `SkillDiscoverabilityResult` per adapter (mirrors what
          `Skill.Get Discoverability` returns for the single-adapter case).
        - `cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]` —
          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
          adapter; rows = task IDs). Built via
          `CohortHeatmap.from_skill_comparison(self)`.
        - `summary: SkillDiscoverabilityComparisonSummary` — aggregate roll-up.

    Cross-consistency invariants checked in `__post_init__` (Story 13.3 +
    13.4 lessons applied):
        - `len(adapters) >= 2`.
        - `set(adapters) == set(per_adapter_results.keys())`.
        - `set(adapters) == set(heatmap.models)`.
        - `set(adapters) == set(summary.activation_accuracy_per_adapter.keys())`.
    """

    adapters: tuple[str, ...]
    per_adapter_results: Mapping[str, SkillDiscoverabilityResult]
    cross_adapter_deltas: Mapping[str, SkillPairwiseAdapterDelta]
    heatmap: CohortHeatmap
    summary: SkillDiscoverabilityComparisonSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapters", tuple(self.adapters))
        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
        if len(self.adapters) < 2:
            raise ValueError(f"SkillDiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
        if set(self.adapters) != set(self.per_adapter_results.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
            )
        if set(self.adapters) != set(self.heatmap.models):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
            )
        if set(self.adapters) != set(self.summary.activation_accuracy_per_adapter.keys()):
            raise ValueError(
                f"adapters {sorted(self.adapters)!r} must equal "
                f"summary.activation_accuracy_per_adapter keys "
                f"{sorted(self.summary.activation_accuracy_per_adapter.keys())!r}"
            )

exec
/bin/bash -lc "sed -n '1,220p' tests/unit/skills/test_discoverability.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for `Skill.Get Discoverability` + `Skill.Should Activate For` (Story 7.2).

Covers AC-7.2.1 through AC-7.2.11 (14 tests):
  - AC-7.2.1: load_skill_discoverability_tasks loader + SkillDiscoverabilityTask
  - AC-7.2.2: SkillTaskResult + SkillDiscoverabilityTaskSummary + SkillDiscoverabilityResult dataclasses
  - AC-7.2.3: SkillDidNotActivateError structured fields
  - AC-7.2.4: get_discoverability tier-3 + returns SkillDiscoverabilityResult
  - AC-7.2.5: should_activate_for tier-2 + passes / raises SkillDidNotActivateError
  - AC-7.2.6: polling= raises PollingDisallowedError on both keywords
  - AC-7.2.7: SkillDidNotActivateError carries 5 diagnostic fields
  - AC-7.2.9: InvalidSkillDiscoverabilityTasksError for invalid YAML
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import (
    InvalidSkillDiscoverabilityTasksError,
    PollingDisallowedError,
    SkillDidNotActivateError,
)
from AgentEval.skills._internal import SkillDiscoverabilityTask, load_skill_discoverability_tasks
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import (
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillTaskResult,
)
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILLS_DIR = FIXTURES_DIR / "skills"
DISCOVERABILITY_DIR = FIXTURES_DIR / "discoverability"

SEARCH_SKILL = SKILLS_DIR / "example-search.md"
# example-search.md has `name: example-search-skill`
SKILL_NAME = "example-search-skill"
SKILL_TASKS = DISCOVERABILITY_DIR / "skill-tasks-basic.yaml"


def _make_stub(response_text: str, cost: float = 0.001, latency: float = 0.002) -> type[InProcessAdapter]:
    """Build a one-shot stub adapter returning a scripted AgentRunResult."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=latency,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


# --------------------------------------------------------------------------- #
# AC-7.2.1: SkillDiscoverabilityTask + load_skill_discoverability_tasks        #
# --------------------------------------------------------------------------- #


def test_load_skill_discoverability_tasks_returns_correct_list() -> None:
    """load_skill_discoverability_tasks returns a list of SkillDiscoverabilityTask instances."""
    tasks = load_skill_discoverability_tasks(SKILL_TASKS)
    assert isinstance(tasks, list)
    assert len(tasks) == 5
    assert all(isinstance(t, SkillDiscoverabilityTask) for t in tasks)
    # First 3 should_activate=True, last 2 False
    assert tasks[0].should_activate is True
    assert tasks[3].should_activate is False
    assert tasks[4].should_activate is False


def test_load_skill_discoverability_tasks_invalid_missing_should_activate(tmp_path: Path) -> None:
    """Missing should_activate field raises InvalidSkillDiscoverabilityTasksError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        "tasks:\n  - id: task1\n    prompt: some prompt\n"
        # should_activate missing
    )
    with pytest.raises(InvalidSkillDiscoverabilityTasksError, match="should_activate"):
        load_skill_discoverability_tasks(bad_yaml)


def test_load_skill_discoverability_tasks_duplicate_id_raises(tmp_path: Path) -> None:
    """Duplicate task id raises InvalidSkillDiscoverabilityTasksError."""
    bad_yaml = tmp_path / "dup.yaml"
    bad_yaml.write_text(
        "tasks:\n"
        "  - id: t1\n"
        "    prompt: first\n"
        "    should_activate: true\n"
        "  - id: t1\n"
        "    prompt: second\n"
        "    should_activate: false\n"
    )
    with pytest.raises(InvalidSkillDiscoverabilityTasksError, match="duplicate"):
        load_skill_discoverability_tasks(bad_yaml)


# --------------------------------------------------------------------------- #
# AC-7.2.2: SkillTaskResult + SkillDiscoverabilityTaskSummary dataclasses      #
# --------------------------------------------------------------------------- #


def test_skill_task_result_is_frozen_dataclass() -> None:
    """SkillTaskResult is a frozen dataclass with the required fields."""
    from dataclasses import FrozenInstanceError

    r = SkillTaskResult(
        task_id="t1",
        task_prompt="prompt",
        should_activate=True,
        trials_run=3,
        activations_observed=2,
        pass_at_k=0.667,
        competing_skills_picked={},
        cost_per_trial_usd=0.001,
    )
    assert r.task_id == "t1"
    assert r.activations_observed == 2
    with pytest.raises(FrozenInstanceError):
        r.task_id = "t2"  # type: ignore[misc]


def test_skill_discoverability_result_is_frozen_dataclass() -> None:
    """SkillDiscoverabilityResult is a frozen dataclass with per_task_results + summary + adapter_coverage."""
    from dataclasses import FrozenInstanceError

    task_r = SkillTaskResult(
        task_id="t1",
        task_prompt="p",
        should_activate=True,
        trials_run=1,
        activations_observed=1,
        pass_at_k=1.0,
        competing_skills_picked={},
        cost_per_trial_usd=0.0,
    )
    summary = SkillDiscoverabilityTaskSummary(
        activation_accuracy=1.0,
        false_activation_rate=0.0,
        missed_activation_rate=0.0,
        total_cost_usd=0.0,
        total_runtime_seconds=0.1,
    )
    dr = SkillDiscoverabilityResult(
        per_task_results=(task_r,),
        summary=summary,
        adapter_coverage="in_process",
    )
    assert dr.adapter_coverage == "in_process"
    assert len(dr.per_task_results) == 1
    with pytest.raises(FrozenInstanceError):
        dr.adapter_coverage = "other"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# AC-7.2.3 + AC-7.2.7: SkillDidNotActivateError                               #
# --------------------------------------------------------------------------- #


def test_skill_did_not_activate_error_carries_diagnostic_fields() -> None:
    """SkillDidNotActivateError carries prompt, skill_path, skill_name, competing_skill, reasoning, fix_suggestion."""
    exc = SkillDidNotActivateError(
        "Skill 'example-search-skill' did not activate for prompt.",
        prompt="hello world",
        skill_path="/some/skill.md",
        skill_name="example-search-skill",
        competing_skill=None,
        reasoning="I decided not to search.",
        fix_suggestion="Rephrase the prompt.",
    )
    assert exc.prompt == "hello world"
    assert exc.skill_name == "example-search-skill"
    assert exc.competing_skill is None
    assert exc.reasoning == "I decided not to search."
    assert exc.fix_suggestion == "Rephrase the prompt."
    assert "SKILL_DID_NOT_ACTIVATE" in str(exc)
    assert "hello world" in str(exc)
    assert "example-search-skill" in str(exc)


# --------------------------------------------------------------------------- #
# AC-7.2.4: get_discoverability keyword + tier-3 annotation                   #
# --------------------------------------------------------------------------- #


def test_get_discoverability_returns_skill_discoverability_result(lib: SkillsLibrary) -> None:

exec
/bin/bash -lc "sed -n '220,520p' tests/unit/skills/test_discoverability.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
def test_get_discoverability_returns_skill_discoverability_result(lib: SkillsLibrary) -> None:
    """Happy path: get_discoverability returns a SkillDiscoverabilityResult."""
    # Stub always mentions the skill name → all activations = True
    stub = _make_stub(response_text=f"I used the {SKILL_NAME} to find the answer.")
    register_adapter("stub_disc_happy", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_happy",
        trials_per_task=1,
    )
    assert isinstance(result, SkillDiscoverabilityResult)


def test_get_discoverability_has_tier_3_annotation(lib: SkillsLibrary) -> None:
    """@tier(3) is present on get_discoverability."""
    assert get_keyword_tier(lib.get_discoverability) == 3


def test_get_discoverability_activations_count_correct_when_all_activate(lib: SkillsLibrary) -> None:
    """activations_observed equals trials_run when stub always mentions skill name."""
    stub = _make_stub(response_text=f"I activated the {SKILL_NAME} skill.")
    register_adapter("stub_disc_all_act", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_all_act",
        trials_per_task=2,
    )
    for task_result in result.per_task_results:
        assert task_result.activations_observed == 2
        assert task_result.trials_run == 2


def test_get_discoverability_activations_count_zero_when_none_activate(lib: SkillsLibrary) -> None:
    """activations_observed equals 0 when stub never mentions skill name."""
    stub = _make_stub(response_text="I did something completely different here.")
    register_adapter("stub_disc_no_act", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_disc_no_act",
        trials_per_task=2,
    )
    for task_result in result.per_task_results:
        assert task_result.activations_observed == 0


# --------------------------------------------------------------------------- #
# AC-7.2.5: should_activate_for keyword + tier-2 annotation                  #
# --------------------------------------------------------------------------- #


def test_should_activate_for_passes_when_skill_activates(lib: SkillsLibrary) -> None:
    """should_activate_for returns None when skill name is in response."""
    stub = _make_stub(response_text=f"The {SKILL_NAME} will handle this search.")
    register_adapter("stub_saf_pass", stub)
    result = lib.should_activate_for(
        "Search for Python tutorials",
        SEARCH_SKILL,
        adapter="stub_saf_pass",
    )
    assert result is None


def test_should_activate_for_has_tier_2_annotation(lib: SkillsLibrary) -> None:
    """@tier(2) is present on should_activate_for."""
    assert get_keyword_tier(lib.should_activate_for) == 2


def test_should_activate_for_raises_skill_did_not_activate_error(lib: SkillsLibrary) -> None:
    """should_activate_for raises SkillDidNotActivateError when skill not in response."""
    stub = _make_stub(response_text="I handled this request without any specialized skill.")
    register_adapter("stub_saf_fail", stub)
    with pytest.raises(SkillDidNotActivateError) as exc_info:
        lib.should_activate_for(
            "Search for Python tutorials",
            SEARCH_SKILL,
            adapter="stub_saf_fail",
        )
    exc = exc_info.value
    assert exc.skill_name == SKILL_NAME
    assert exc.prompt == "Search for Python tutorials"
    assert exc.reasoning == "I handled this request without any specialized skill."
    assert exc.competing_skill is None


# --------------------------------------------------------------------------- #
# AC-7.2.6: polling= raises PollingDisallowedError on both keywords           #
# --------------------------------------------------------------------------- #


def test_get_discoverability_polling_raises_polling_disallowed_error(lib: SkillsLibrary) -> None:
    """Passing polling= to get_discoverability raises PollingDisallowedError."""
    with pytest.raises(PollingDisallowedError):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, polling=1.0)


def test_should_activate_for_polling_raises_polling_disallowed_error(lib: SkillsLibrary) -> None:
    """Passing polling= to should_activate_for raises PollingDisallowedError."""
    with pytest.raises(PollingDisallowedError):
        lib.should_activate_for("some prompt", SEARCH_SKILL, polling=1.0)


# --------------------------------------------------------------------------- #
# trials_per_task validation (Codex MED-1)                                    #
# --------------------------------------------------------------------------- #


def test_get_discoverability_trials_per_task_zero_raises_value_error(lib: SkillsLibrary) -> None:
    """trials_per_task=0 raises ValueError before any adapter call."""
    with pytest.raises(ValueError, match="trials_per_task"):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, trials_per_task=0)


def test_get_discoverability_trials_per_task_negative_raises_value_error(lib: SkillsLibrary) -> None:
    """trials_per_task=-1 raises ValueError before any adapter call."""
    with pytest.raises(ValueError, match="trials_per_task"):
        lib.get_discoverability(SEARCH_SKILL, SKILL_TASKS, trials_per_task=-1)


# --------------------------------------------------------------------------- #
# Summary math: activation_accuracy / false_activation_rate / missed_rate     #
# SKILL_TASKS: 3 should_activate=True + 2 should_activate=False               #
# --------------------------------------------------------------------------- #


def test_summary_all_activate_accuracy_and_rates(lib: SkillsLibrary) -> None:
    """With stub that always activates and trials_per_task=2:
    - activation_accuracy = 6/10 = 0.6  (3 should-tasks correct, 2 decoy-tasks wrong)
    - false_activation_rate = 4/4 = 1.0 (all decoy trials activated)
    - missed_activation_rate = 0/6 = 0.0 (no should-tasks missed)
    """
    stub = _make_stub(response_text=f"Using {SKILL_NAME} for everything.")
    register_adapter("stub_summary_all", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_summary_all",
        trials_per_task=2,
    )
    s = result.summary
    assert abs(s.activation_accuracy - 0.6) < 1e-9
    assert abs(s.false_activation_rate - 1.0) < 1e-9
    assert abs(s.missed_activation_rate - 0.0) < 1e-9


def test_summary_none_activate_accuracy_and_rates(lib: SkillsLibrary) -> None:
    """With stub that never activates and trials_per_task=2:
    - activation_accuracy = 4/10 = 0.4  (2 decoy-tasks correct, 3 should-tasks wrong)
    - false_activation_rate = 0/4 = 0.0 (no decoy trials activated)
    - missed_activation_rate = 6/6 = 1.0 (all should-tasks missed)
    """
    stub = _make_stub(response_text="I did something unrelated.")
    register_adapter("stub_summary_none", stub)
    result = lib.get_discoverability(
        SEARCH_SKILL,
        SKILL_TASKS,
        adapter="stub_summary_none",
        trials_per_task=2,
    )
    s = result.summary
    assert abs(s.activation_accuracy - 0.4) < 1e-9
    assert abs(s.false_activation_rate - 0.0) < 1e-9
    assert abs(s.missed_activation_rate - 1.0) < 1e-9


def test_skill_discoverability_task_summary_is_frozen_dataclass() -> None:
    """SkillDiscoverabilityTaskSummary is frozen — assignment raises FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    s = SkillDiscoverabilityTaskSummary(
        activation_accuracy=0.8,
        false_activation_rate=0.1,
        missed_activation_rate=0.2,
        total_cost_usd=0.005,
        total_runtime_seconds=1.0,
    )
    with pytest.raises(FrozenInstanceError):
        s.activation_accuracy = 0.0  # type: ignore[misc]

exec
/bin/bash -lc "grep -RIn \"def guarded_fanout\\|_max_cost_usd\\|_max_runtime_seconds\" src/AgentEval/_kernel src/AgentEval | head -n 80" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/_kernel/guardrails.py:214:def guarded_fanout(
src/AgentEval/_kernel/guardrails.py:237:        `_max_cost_usd: float | None` and `_max_runtime_seconds: float | None`
src/AgentEval/_kernel/guardrails.py:265:                max_cost_usd = getattr(self, "_max_cost_usd", None)
src/AgentEval/_kernel/guardrails.py:266:                max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)
src/AgentEval/stats/library.py:36:Tier-3 `Stat.Run N Times` reads `_max_cost_usd` + `_max_runtime_seconds`
src/AgentEval/stats/library.py:103:        self._max_cost_usd = max_cost_usd
src/AgentEval/stats/library.py:104:        self._max_runtime_seconds = max_runtime_seconds
src/AgentEval/__init__.py:278:        self._max_cost_usd = resolved["max_cost_usd"]
src/AgentEval/__init__.py:279:        self._max_runtime_seconds = resolved["max_runtime_seconds"]
src/AgentEval/__init__.py:364:                        max_cost_usd=self._max_cost_usd,
src/AgentEval/__init__.py:365:                        max_runtime_seconds=self._max_runtime_seconds,
src/AgentEval/__init__.py:374:                        max_cost_usd=self._max_cost_usd,
src/AgentEval/__init__.py:375:                        max_runtime_seconds=self._max_runtime_seconds,
src/AgentEval/__init__.py:455:            "max_cost_usd": self._max_cost_usd,
src/AgentEval/__init__.py:456:            "max_runtime_seconds": self._max_runtime_seconds,
src/AgentEval/judge/library.py:44:Host-instance budgets (`_max_cost_usd`, `_max_runtime_seconds`) are
src/AgentEval/judge/library.py:111:        self._max_cost_usd = max_cost_usd
src/AgentEval/judge/library.py:112:        self._max_runtime_seconds = max_runtime_seconds
src/AgentEval/_kernel/guardrails.py:214:def guarded_fanout(
src/AgentEval/_kernel/guardrails.py:237:        `_max_cost_usd: float | None` and `_max_runtime_seconds: float | None`
src/AgentEval/_kernel/guardrails.py:265:                max_cost_usd = getattr(self, "_max_cost_usd", None)
src/AgentEval/_kernel/guardrails.py:266:                max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)

exec
/bin/bash -lc "sed -n '1,260p' src/AgentEval/skills/_internal.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Internal helpers for the skills sub-library (Story 7.2).

Private module — not part of the public API. Contains:

- `SkillDiscoverabilityTask` — one task entry from the skill-discoverability
  YAML; carries `id`, `prompt`, `should_activate`.
- `load_skill_discoverability_tasks(path)` — load + validate a
  skill-discoverability tasks YAML file; returns
  `list[SkillDiscoverabilityTask]` or raises
  `InvalidSkillDiscoverabilityTasksError` per the FR59 Tier-1
  setup-failure convention.

Parallel to `src/AgentEval/discoverability/loader.py` (Story 4.4) which
handles MCP tool discoverability tasks. The skill variant adds the
`should_activate: bool` field (distinguishes "should trigger" prompts
from decoys) and raises `InvalidSkillDiscoverabilityTasksError` instead of
`InvalidDiscoverabilityTasksError`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from AgentEval._kernel.discovery import get_adapter
from AgentEval.errors import InvalidSkillDiscoverabilityTasksError
from AgentEval.skills.types import (
    SkillDiscoverabilityResult,
    SkillDiscoverabilityTaskSummary,
    SkillTaskResult,
)

__all__ = [
    "SkillDiscoverabilityTask",
    "load_skill_discoverability_tasks",
    # Story 13.5 (Epic 13) — shared per-adapter helper for FR4c.
    "build_skill_discoverability_summary",
    "run_single_adapter_skill_discoverability",
]


@dataclass(frozen=True)
class SkillDiscoverabilityTask:
    """One task entry in a skill-discoverability YAML (Story 7.2 / FR4b).

    Fields:
        id: Unique string identifier for the task.
        prompt: Natural-language prompt sent to the agent.
        should_activate: True when the target skill SHOULD be triggered by
            this prompt; False for decoy prompts that should NOT activate
            the skill (false-activation rate measurement).
    """

    id: str
    prompt: str
    should_activate: bool


def load_skill_discoverability_tasks(path: str | Path) -> list[SkillDiscoverabilityTask]:
    """Load + validate a skill-discoverability tasks YAML file.

    Args:
        path: Filesystem path to the tasks YAML file.

    Returns:
        List of validated `SkillDiscoverabilityTask` instances in YAML order.

    Raises:
        InvalidSkillDiscoverabilityTasksError: On any structural failure
            (file missing, wrong extension, malformed YAML, schema violation).
            `field_name` carries an RFC 6901 JSON Pointer.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks YAML file not found: {p}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidSkillDiscoverabilityTasksError(
            f"failed to read skill discoverability tasks YAML: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidSkillDiscoverabilityTasksError(
            f"skill discoverability tasks YAML is not valid UTF-8: {exc}",
            file_path=str(p),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidSkillDiscoverabilityTasksError(
            f"malformed YAML in skill discoverability tasks file: {exc}",
            file_path=str(p),
            line_number=line,
            field_name="",
            fix_suggestion="Fix the YAML syntax error at the indicated line.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSkillDiscoverabilityTasksError(
            "skill discoverability tasks file must be a YAML mapping at the top level",
            file_path=str(p),
            field_name="",
            fix_suggestion="Add a top-level `tasks:` key with a list of task entries.",
        )

    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise InvalidSkillDiscoverabilityTasksError(
            "skill discoverability tasks file must have a non-empty `tasks:` list",
            file_path=str(p),
            field_name="/tasks",
            fix_suggestion="Add at least one task entry under `tasks:`.",
        )

    seen_ids: set[str] = set()
    tasks: list[SkillDiscoverabilityTask] = []
    for idx, raw_task in enumerate(raw_tasks):
        pointer_prefix = f"/tasks/{idx}"
        if not isinstance(raw_task, dict):
            raise InvalidSkillDiscoverabilityTasksError(
                f"task at index {idx} must be a YAML mapping",
                file_path=str(p),
                field_name=pointer_prefix,
                fix_suggestion="Each task must be a mapping with `id`, `prompt`, `should_activate`.",
            )

        task_id = raw_task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise InvalidSkillDiscoverabilityTasksError(
                f"task at index {idx} is missing required string field `id`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion="Add a unique string `id:` field to the task.",
            )

        if task_id in seen_ids:
            raise InvalidSkillDiscoverabilityTasksError(
                f"duplicate task id {task_id!r} at index {idx}",
                file_path=str(p),
                field_name=f"{pointer_prefix}/id",
                fix_suggestion=f"Each task must have a unique `id`. Rename the duplicate '{task_id}'.",
            )
        seen_ids.add(task_id)

        prompt = raw_task.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise InvalidSkillDiscoverabilityTasksError(
                f"task '{task_id}' is missing required non-empty string field `prompt`",
                file_path=str(p),
                field_name=f"{pointer_prefix}/prompt",
                fix_suggestion="Add a non-empty string `prompt:` field to the task.",
            )

        should_activate = raw_task.get("should_activate")
        if not isinstance(should_activate, bool):
            got = type(should_activate).__name__
            raise InvalidSkillDiscoverabilityTasksError(
                f"task '{task_id}' field `should_activate` must be a bool (true/false); got {got!r}",
                file_path=str(p),
                field_name=f"{pointer_prefix}/should_activate",
                fix_suggestion="Set `should_activate: true` or `should_activate: false` for the task.",
            )

        tasks.append(SkillDiscoverabilityTask(id=task_id, prompt=prompt, should_activate=should_activate))

    return tasks


# --------------------------------------------------------------------------- #
# Story 13.5 (Epic 13) — Shared per-adapter helpers for FR4c                  #
# --------------------------------------------------------------------------- #


def build_skill_discoverability_summary(
    task_results: list[SkillTaskResult], total_runtime: float
) -> SkillDiscoverabilityTaskSummary:
    """Compute aggregate `SkillDiscoverabilityTaskSummary` across task results.

    Story 13.5 extraction of `SkillsLibrary._build_discoverability_summary`
    (Story 7.2) to module scope so both `get_discoverability` (single
    adapter) and `get_discoverability_comparison` (Story 13.5 N-adapter)
    compute summaries identically.
    """
    total_trials = sum(r.trials_run for r in task_results)
    total_correct = sum(
        r.activations_observed if r.should_activate else (r.trials_run - r.activations_observed) for r in task_results
    )
    activation_accuracy = total_correct / total_trials if total_trials > 0 else 0.0

    decoy_results = [r for r in task_results if not r.should_activate]
    false_act_obs = sum(r.activations_observed for r in decoy_results)
    false_act_denom = sum(r.trials_run for r in decoy_results)
    false_activation_rate = false_act_obs / false_act_denom if false_act_denom > 0 else 0.0

    should_act_results = [r for r in task_results if r.should_activate]
    missed_obs = sum(r.trials_run - r.activations_observed for r in should_act_results)
    missed_denom = sum(r.trials_run for r in should_act_results)
    missed_activation_rate = missed_obs / missed_denom if missed_denom > 0 else 0.0

    total_cost = sum(r.cost_per_trial_usd * r.trials_run for r in task_results)

    return SkillDiscoverabilityTaskSummary(
        activation_accuracy=activation_accuracy,
        false_activation_rate=false_activation_rate,
        missed_activation_rate=missed_activation_rate,
        total_cost_usd=total_cost,
        total_runtime_seconds=total_runtime,
    )


def run_single_adapter_skill_discoverability(
    *,
    skill_name: str,
    task_list: list[SkillDiscoverabilityTask],
    adapter: str,
    model: str | None,
    trials_per_task: int,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,
) -> SkillDiscoverabilityResult:
    """Run Skill discoverability against ONE adapter (Story 13.5 helper extraction).


exec
/bin/bash -lc "sed -n '214,320p' src/AgentEval/_kernel/guardrails.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
def guarded_fanout(
    estimator: Callable[[dict[str, Any]], tuple[float, float]] | None = None,
    *,
    meter_interval_seconds: float = 5.0,
) -> Callable[[F], F]:
    """Decorator factory wrapping a Tier-3 fan-out keyword with 3-layer enforcement.

    Args:
        estimator: Optional callable `(kwargs: dict) -> (cost_est_usd, runtime_est_s)`
            invoked at Layer 1. When None, pre-flight estimation is skipped.
            Estimator-side exceptions (raise OR wrong-shape return) are
            wrapped in a typed `CostExceededError` so the failure path stays
            on the typed-budget-error contract.
        meter_interval_seconds: Poll cadence for Layer 2 + Layer 3 meters.
            Default 5.0s per ADR-015 reference. Configurable for unit tests
            (use very small values like 0.01s) and for low-budget runs. Must
            be > 0.

    Returns:
        A decorator that wraps the keyword function.

    Notes:
        Decorated function MUST be a method on a class that exposes
        `_max_cost_usd: float | None` and `_max_runtime_seconds: float | None`
        attributes (per Story 1a.6's `AgentEval.__init__` wiring + Story
        1b.1's `resolve_config`). Tests can use a minimal `SimpleNamespace`
        or `@dataclass` stand-in matching that contract. `None` for either
        budget skips the corresponding layer's checks (Layer 1+2 for cost,
        Layer 1+3 for runtime).

        Test-only override: pass `__agenteval_test_budget__=(max_cost_usd,
        max_runtime_seconds)` as a kwarg-only argument to override the
        bound-instance budget for that single invocation. Production code
        cannot accidentally collide with this sentinel-private kwarg name.
    """
    if meter_interval_seconds <= 0:
        raise ValueError(f"meter_interval_seconds must be > 0 (got {meter_interval_seconds!r})")

    def _decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Resolve budget: sentinel-private kwarg override (test-only) > instance attributes.
            budget_override = kwargs.pop(_TEST_BUDGET_KWARG, None)
            if budget_override is not None:
                if not isinstance(budget_override, tuple) or len(budget_override) != 2:
                    raise TypeError(
                        f"{_TEST_BUDGET_KWARG} must be a 2-tuple of "
                        f"(max_cost_usd, max_runtime_seconds); got {budget_override!r}"
                    )
                max_cost_usd, max_runtime_seconds = budget_override
            else:
                max_cost_usd = getattr(self, "_max_cost_usd", None)
                max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)

            # Layer 1: pre-flight estimation.
            if estimator is not None:
                try:
                    estimator_result = estimator(kwargs)
                except Exception as exc:
                    raise CostExceededError(
                        f"Pre-flight estimator callable raised {type(exc).__name__}: "
                        f"{exc}; refusing to enter keyword body."
                    ) from exc
                cost_est, runtime_est = _validate_estimator_result(estimator_result)
                if max_cost_usd is not None and cost_est > max_cost_usd:
                    raise CostExceededError(
                        f"Pre-flight cost estimate {cost_est:.2f} USD > "
                        f"budget {max_cost_usd:.2f} USD; refusing to enter "
                        f"keyword body."
                    )
                if max_runtime_seconds is not None and runtime_est > max_runtime_seconds:
                    raise RuntimeBudgetExceededError(
                        f"Pre-flight runtime estimate {runtime_est:.1f}s > "
                        f"budget {max_runtime_seconds:.1f}s; refusing to enter "
                        f"keyword body."
                    )

            # Bind cancellation event + start mid-run meter thread.
            cancel_event = threading.Event()
            token = _cancel_event_var.set(cancel_event)
            breach = _BreachState()
            stop_meter = threading.Event()
            start_monotonic = time.monotonic()

            def _check_meters_once() -> bool:
                """Run one pass of Layer 2 + Layer 3 checks. Returns True iff a breach was recorded."""
                try:
                    current_cost = _current_cost_usd_for_run()
                except Exception as exc:
                    # Fail-closed: meter thread NEVER dies silently. If the
                    # cost source raises, log + record a breach with a typed
                    # `cause` so the wrapper surfaces the failure to caller.
                    _log.warning(
                        "Cost source `_current_cost_usd_for_run` raised %s: %s; treating as fail-closed budget breach.",
                        type(exc).__name__,
                        exc,
                    )
                    breach.breached = True
                    breach.cost_at_breach = 0.0
                    breach.elapsed_at_breach = time.monotonic() - start_monotonic
                    breach.cause = "cost_source_failure"
                    cancel_event.set()
                    return True
                elapsed = time.monotonic() - start_monotonic
                # Layer 2: cumulative cost meter (when budget is configured).
                if max_cost_usd is not None and current_cost > max_cost_usd:
                    breach.breached = True

codex
I have the guardrail code now: `@guarded_fanout()` does use `getattr(self, "_max_cost_usd", None)` / `getattr(self, "_max_runtime_seconds", None)`, so the no-host-attrs crash path is unlikely. I’m moving to empirical checks and cross-story parity with the Story 13.3 implementation.
exec
/bin/bash -lc "grep -RIn \"compare_t_start\\|total_runtime = time.perf_counter() - compare_t_start\\|from_comparison\\|get_tool_discoverability_comparison\" src/AgentEval | sed -n '1,120p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/_heatmap/models.py:122:    def from_comparison(
src/AgentEval/_heatmap/models.py:164:        Symmetric to ``from_comparison`` but reads the Skill-domain
src/AgentEval/mcp/library.py:558:    def get_tool_discoverability_comparison(
src/AgentEval/mcp/library.py:598:        ``CohortHeatmap`` via ``from_comparison``) + ``summary``
src/AgentEval/mcp/library.py:753:        # Build a provisional comparison result so CohortHeatmap.from_comparison
src/AgentEval/mcp/library.py:757:        # CohortHeatmap.from_comparison reads result.adapters + result.per_adapter_results
src/AgentEval/mcp/library.py:768:        heatmap = CohortHeatmap.from_comparison(shim)  # type: ignore[arg-type]
src/AgentEval/discoverability/schema.py:289:          `CohortHeatmap.from_comparison(self)`.
src/AgentEval/skills/library.py:564:        compare_t_start = time.perf_counter()
src/AgentEval/skills/library.py:620:        # `compare_t_start` (NOT MAX of per-adapter, which would
src/AgentEval/skills/library.py:622:        total_runtime = time.perf_counter() - compare_t_start

exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
p=Path('docs/recipes/04-skill-author-stacked-validation.md')
print(p)
print(p.read_text())
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
docs/recipes/04-skill-author-stacked-validation.md
# Recipe 4: Devon's Stacked Skill Validation Pattern

**Persona:** Devon (Agent Surface Author)
**Epic:** Epic 7 — Skill Author Validation Flow + Skill Discoverability (Tier-1 + Tier-3); Epic 12 — Tier-2 LLM-Judge completion.
**Status:** Complete — Story 7.3 stub + Story 8b.3 polish + Story 12.3 Tier-2 completion (2026-05-27).

## Listener invocation (REQUIRED)

```bash
robot --listener AgentEval.telemetry.listener.Listener \
      --xunit junit.xml \
      tests/
```

Use the **explicit `Module.Class` listener path**. The shorter
`--listener AgentEval.telemetry.listener` (module-path-only) form is
accepted by RF 7.x but the `Listener` class hooks do NOT fire (Story 8a.2
D-6 empirical finding). The listener is required for trace capture +
xunit enrichment — see Recipes #1 + #8.

## Overview

Devon validates a skill `.md` file using a three-tier stacked pattern:

| Tier | Keyword | Story | Notes |
|------|---------|-------|-------|
| 1 — Static | `Skill.Should Be Valid Frontmatter` | 2.1 | Deterministic; no LLM call |
| 2 — Judge | `Judge.Get Score` | Epic 12.3 | Phase 2 — LLM-deterministic at `seed + temperature=0`; rubric ratifies pass/fail at threshold |
| 3 — Cohort | `Skill.Get Discoverability` | 7.2 | 10 trials/task; assert Pass@k ≥ 0.8 |
| 3 — Spot | `Skill.Should Activate For` | 7.2 | Single-prompt assertion |
| Stat | `Stat.Run N Times` + `Stat.Get Pass At K` | 6.3 | Composition with Tier-3 |
| Calibration | `Judge.Calibrate Rubric` | Epic 12.2 | Pre-deployment — verify Cohen's κ ≥ 0.7 against human labels before relying on Tier-2 |

## Robot Framework Example

```robotframework
*** Settings ***
Library    AgentEval.skills.library.SkillsLibrary                  WITH NAME    Skill
Library    AgentEval.stats.library.StatsLibrary                    WITH NAME    Stat
Library    AgentEval.judge.library.JudgeLibrary                    WITH NAME    Judge
Library    AgentEval.orchestration.library.OrchestrationLibrary

*** Variables ***
${SKILL_PATH}     skills/my-search-skill.md
${TASKS_PATH}     tests/discoverability/my-skill-tasks.yaml
${RUBRIC_PATH}    tests/rubrics/skill-quality.md
${ADAPTER}        generic
${JUDGE_MODEL}    anthropic/claude-sonnet-4-6
${REPRESENTATIVE_PROMPT}    Search for Python tutorials on the web

*** Test Cases ***
Devon Validates Skill: Stacked Three-Tier Pattern
    # ── Tier 1: Static frontmatter validation (deterministic, fast) ──
    ${fm}=    Skill.Get Frontmatter    ${SKILL_PATH}
    Skill.Should Be Valid Frontmatter    ${fm}

    # ── Tier 2: LLM-judge scoring at seed + temperature=0 (Story 12.3) ──
    # Run the agent once against a representative prompt, then judge the
    # response against the rubric. Tier-2 is a SEPARATE LLM call from any
    # Tier-3 cohort run — Devon pays for it explicitly. Calibrate the rubric
    # first via `Judge.Calibrate Rubric` (Story 12.2) — see docs/recipes/judge-calibration.md.
    ${run}=    Send Prompt    prompt=${REPRESENTATIVE_PROMPT}    adapter=${ADAPTER}
    ${score}=    Judge.Get Score
    ...    result=${run}
    ...    rubric=${RUBRIC_PATH}
    ...    judge_adapter=${ADAPTER}
    ...    judge_model=${JUDGE_MODEL}
    ...    temperature=0.0
    ...    seed=42
    Should Be True    ${score.pass_threshold_met}
    ...    msg=Judge score ${score.numeric_score} below rubric threshold; review reasoning: ${score.reasoning}

    # ── Tier 3: Cohort discoverability (10 trials per task) ──
    ${result}=    Skill.Get Discoverability
    ...    skill=${SKILL_PATH}
    ...    tasks=${TASKS_PATH}
    ...    adapter=${ADAPTER}
    ...    trials_per_task=10
    FOR    ${task_result}    IN    @{result.per_task_results}
        IF    ${task_result.should_activate}
            Should Be True    ${task_result.pass_at_k} >= 0.8
            ...    msg=Task '${task_result.task_id}' pass_at_k < 0.8
        END
    END

    # ── Stat.* composition: Run N times + Pass@5 ──
    # NOTE: Must use custom predicate — see DF-7.3-S1/C59 in deferred-work.md
    # (ActivationDecision has no metadata.completeness → default predicate fails)
    ${kwargs}=    Create Dictionary
    ...    skill=${SKILL_PATH}
    ...    prompt=Search for Python tutorials on the web
    ...    adapter=${ADAPTER}
    ${runs}=    Stat.Run N Times
    ...    n=10
    ...    keyword=Skill.Get Activation Decision
    ...    keyword_args=${kwargs}
    ${pass_at_5}=    Stat.Get Pass At K
    ...    runs=${runs}
    ...    k=5
    ...    predicate=${{lambda r: r.result.activated}}
    Should Be True    ${pass_at_5} >= 0.8

    # ── Spot-check: single-prompt activation assertion ──
    Skill.Should Activate For
    ...    prompt=Search for Python tutorials on the web
    ...    skill=${SKILL_PATH}
    ...    adapter=${ADAPTER}
```

## Phase 2 Status

As of Story 12.3 (Epic 12 — 2026-05-27), the full three-tier stacked validation
flow is shipping. Devon's Journey 4 from PRD L394-401 is end-to-end exercisable:

- **Tier 1 + Tier 3** ship in Phase 1 (Epic 7).
- **Tier 2** ships in Phase 2 (Epic 12 — Stories 12.1 + 12.2 + 12.3).

Operators may opt out of Tier-2 by leaving the section commented out; Tier-1 +
Tier-3 remain the Phase-1 ceiling for budget-constrained users. Tier-2 adds one
LLM call per representative prompt — calibrate the rubric first via
`Judge.Calibrate Rubric` (Story 12.2) and gate CI on Cohen's kappa ≥ 0.7 per
`architecture.md` L199.

## Phase 2 cross-adapter Skill Discoverability (Story 13.5 / FR4c)

As of Story 13.5 (Epic 13 — 2026-06-01), Devon can compare skill activation
across multiple Tier-1 adapters in a single call to claim "skill X is reliably
activated by Claude AND GPT AND Copilot" with empirical evidence — symmetric to
Mei's cross-adapter Tool Discoverability (Story 13.3 / FR10b).

```robotframework
*** Settings ***
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill

*** Test Cases ***
Skill X Is Reliably Activated Across Claude And OpenAI
    ${comparison}=    Skill.Compare Discoverability
    ...    skill=${CURDIR}/skills/web-search.md
    ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
    ...    adapters=${{['claude_code_cli', 'codex_cli']}}
    ...    trials_per_task=5
    ...    max_cost_usd=10.00
    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['codex_cli']} >= 0.7
    # Cross-adapter significance — was the skill consistently triggered
    # OR did one adapter wildly outperform the other?
    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
    Should Be True    abs(${delta.pass_at_k_delta}) < 0.3
```

Behind the `[agenteval-advanced]` optional extra (scipy + numpy from Story 13.1
for Mann-Whitney U significance). The keyword returns a
`SkillDiscoverabilityComparisonResult` with per-adapter `SkillDiscoverabilityResult`
+ cross-adapter Pass@k differential + per-adapter false-activation /
missed-activation rate comparison + multi-column `CohortHeatmap` (which can
render to HTML via Story 13.4's `as_html()` for stakeholder sharing).

**Phase-1.5 dogfood deferral (DF-13.5-S4 / C98):** the
`robotframework-agentskills` downstream repo will adopt the cross-adapter suite
in its CI matrix (Mock provider for routine CI; a separate
`weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a
budget per epic L2227). Tracked as a Phase-1.5 carry-over.

## See Also

- Story 7.1: `Skill.Get Activation Decision` — single-prompt activation query
- Story 7.2: `Skill.Get Discoverability` + `Skill.Should Activate For`
- Story 6.3: `Stat.Run N Times` + `Stat.Get Pass At K`
- Story 12.1: `Judge.Get Score` — Tier-2 LLM-judge keyword
- Story 12.2: `Judge.Calibrate Rubric` + `docs/recipes/judge-calibration.md` — calibrate rubrics against human labels
- Story 12.3: `tests/integration/skills/test_devon_three_tier_complete.py` — Python pytest example
- `tests/integration/skills/test_devon_stacked_validation.py` — Tier-1 + Tier-3 subset (Story 7.3)


exec
/bin/bash -lc 'uv run pytest tests/unit/skills/test_comparison.py tests/unit/skills/test_comparison_extras_gate.py tests/integration/skills/test_skill_compare_e2e.py -q' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'uv run pytest tests/unit/skills/test_discoverability.py -q' in /home/many/workspace/robotframework-agenteval
 succeeded in 1310ms:
....................                                                     [100%]
20 passed in 0.45s

 succeeded in 2787ms:
........................                                                 [100%]
24 passed in 1.76s

exec
/bin/bash -lc "sed -n '558,790p' src/AgentEval/mcp/library.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
    def get_tool_discoverability_comparison(
        self,
        mcp_server: str = "",
        adapters: list[str] | None = None,
        tasks: str = "",
        trials_per_task: int = 3,
        max_cost_usd: float = 20.00,
        max_runtime_seconds: float | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> DiscoverabilityComparisonResult:
        """Compares Tool Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).

        [Tier 3 — Stochastic Fan-Out] — runs `Get Tool Discoverability`
        once per adapter against the SAME task set, then computes
        pairwise Mann-Whitney U deltas across the per-task pass-rate
        distributions. Returns a `DiscoverabilityComparisonResult` with
        per-adapter results + cross-adapter deltas + multi-column
        cohort heatmap + aggregate summary.

        Requires the ``[agenteval-advanced]`` optional extra (scipy +
        numpy) for the Mann-Whitney U cross-adapter delta computation;
        raises ``ImportError`` on invocation WITHOUT the extra (fail-fast
        BEFORE running any per-adapter fan-out — operators discovering
        the missing extra should not pay 3-adapter trial cost first).

        | =Arguments= | =Description= |
        | ``mcp_server`` | Name of the MCP server (per `Start Server`). Same Phase-1 carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). |
        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. N=3+ enables ranking across Claude/GPT/Copilot/.... |
        | ``tasks`` | Path to the discoverability tasks YAML (loaded ONCE; shared across adapters). |
        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2186 (4× the single-adapter default reflecting N=3-adapter typical cost). Phase-1 carve-out DF-13.3-S1: tracked NOT enforced (same MCPLibrary architectural gap as DF-4.4-S1 / C20). |
        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. |
        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. Phase-2.5 (DF-13.3-S4): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg. |
        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |

        Returns ``DiscoverabilityComparisonResult`` with ``adapters`` +
        ``per_adapter_results`` (one ``DiscoverabilityResult`` per
        adapter) + ``cross_adapter_deltas`` (C(N, 2) ``PairwiseAdapterDelta``
        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
        ``CohortHeatmap`` via ``from_comparison``) + ``summary``
        (``DiscoverabilityComparisonSummary``).

        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
        missing (Mann-Whitney U requires scipy/numpy). Raises
        ``ValueError`` on missing/empty ``mcp_server`` / ``tasks`` /
        ``adapters`` (≥2 required) / invalid ``trials_per_task``.
        Raises ``InvalidDiscoverabilityTasksError`` on tasks YAML
        parse/schema failure. Raises ``AdapterDiscoveryError`` on
        unknown adapter name.

        Example:
        | ${comparison}=    `MCP.Compare Tool Discoverability`
        | ...    mcp_server=rf-mcp
        | ...    adapters=${{['generic', 'claude_code_cli', 'codex_cli']}}
        | ...    tasks=${CURDIR}/tasks.yaml
        | ...    trials_per_task=5
        | ...    max_cost_usd=20.00
        | Should Be Equal As Strings    ${comparison.summary.best_adapter}    claude_code_cli
        | Should Be True    ${comparison.cross_adapter_deltas['generic_vs_codex_cli'].significant_at_alpha_05}

        Notes:
        - Story 13.3 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra (the Mann-Whitney U dependency from Story 13.1).
        - PRD FR10b ratifies the ``DiscoverabilityComparisonResult`` shape; epics.md L2186-2189 ratifies the keyword signature + behavior.
        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper at ``src/AgentEval/stats/mannwhitney.py``). The keyword surface ``Stat.Mann Whitney U`` is NOT called here because the input is ``list[float]`` per-task pass rates (NOT ``list[KeywordRun]``).
        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition; no bit-identical FR31a guarantee (Story 13.1 HIGH-C concern doesn't apply at @tier(3)).
        - Phase-1 carve-out DF-13.3-S1: ``@guarded_fanout`` enforcement DEFERRED (same MCPLibrary architectural gap as DF-4.4-S1 / C20).
        - Phase-2.5 carry-overs: DF-13.3-S2 (per-adapter MCP attachment gated on C72 + C68/C69/C73/C75); DF-13.3-S3 (Bonferroni / Holm multi-pairwise correction).
        - Sibling keyword: `MCP.Get Tool Discoverability` (Phase-1 single-adapter; this keyword's N=1 case is intentionally rejected via the ≥2 validation — single-adapter callers should use the simpler `Get` keyword).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        t_start = time.monotonic()

        # Validate args (mirrors single-adapter Get + adds N≥2 constraint).
        if not mcp_server:
            raise ValueError(
                "MCP.Compare Tool Discoverability requires `mcp_server=<name>` kwarg "
                "(name of an MCP server started via `MCP.Start Server`); empty "
                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
                "adapter-side integration."
            )
        if not tasks:
            raise ValueError("MCP.Compare Tool Discoverability requires `tasks=<yaml-path>` kwarg")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        if adapters is None or len(adapters) < 2:
            raise ValueError(
                f"MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, "
                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
            )
        if len(set(adapters)) != len(adapters):
            raise ValueError(
                f"MCP.Compare Tool Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
            )

        # `[agenteval-advanced]` extras gate (D-6 + L-2). Fail-fast BEFORE
        # the per-adapter fan-out so operators discovering the missing
        # extra don't pay N-adapter trial cost first. Direct raise per
        # AC-13.3.4 in-flight decision (b) — the `Stat.`-prefixed helper
        # `_raise_advanced_extra_missing` would mis-frame the message
        # for an `MCP.`-prefixed keyword.
        #
        # Read the attribute via module-level access (NOT
        # `from X import Y` which binds a local) so test
        # `monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)`
        # is observed correctly even when this code path runs AFTER
        # Story 13.1's `test_advanced_extras_gate.py` has run + cleaned
        # up its own monkeypatch in the same pytest session.
        from AgentEval.stats import library as _stats_lib

        if not _stats_lib._ADVANCED_AVAILABLE:
            raise ImportError(
                "MCP.Compare Tool Discoverability: scipy + numpy required. "
                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
            )

        # Load tasks YAML ONCE (shared across adapters).
        task_list = load_discoverability_tasks(tasks)

        # Run per-adapter discoverability serially. Phase-2.5 may parallelize
        # via thread pool / asyncio; Phase-2 ships serial for simplicity +
        # safer cost accounting.
        from AgentEval._heatmap.models import CohortHeatmap
        from AgentEval.discoverability._internal import run_single_adapter_discoverability
        from AgentEval.discoverability.schema import (
            DiscoverabilityComparisonResult,
            DiscoverabilityComparisonSummary,
            PairwiseAdapterDelta,
        )
        from AgentEval.stats.mannwhitney import compute_mann_whitney_u

        per_adapter_results: dict[str, DiscoverabilityResult] = {}
        for adapter_name in adapters:
            # Per-adapter timer measures only THIS adapter's slice — useful
            # for per-adapter cost auditing. The comparison-level wall-clock
            # is measured separately from the keyword-entry `t_start` below.
            per_adapter_results[adapter_name] = run_single_adapter_discoverability(
                mcp_server=mcp_server,
                adapter=adapter_name,
                model=model,
                task_list=task_list,
                trials_per_task=trials_per_task,
                max_cost_usd=max_cost_usd,
                max_runtime_seconds=max_runtime_seconds,
                extra_adapter_kwargs=dict(kwargs),
                t_start=time.monotonic(),
            )

        # Build C(N, 2) pairwise deltas. Ordering: itertools.combinations
        # preserves input order so `adapter_a` always comes before
        # `adapter_b` in the input list.
        import itertools

        cross_adapter_deltas: dict[str, PairwiseAdapterDelta] = {}
        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
            rates_a = [t.pass_rate for t in per_adapter_results[adapter_a].per_task_results]
            rates_b = [t.pass_rate for t in per_adapter_results[adapter_b].per_task_results]
            # Empty per-task lists guard: skip the comparison if either is
            # empty (would otherwise raise from `compute_mann_whitney_u`).
            if not rates_a or not rates_b:
                continue
            mwu = compute_mann_whitney_u(rates_a, rates_b)
            delta_key = f"{adapter_a}_vs_{adapter_b}"
            mean_a = sum(rates_a) / len(rates_a)
            mean_b = sum(rates_b) / len(rates_b)
            import math as _math

            cross_adapter_deltas[delta_key] = PairwiseAdapterDelta(
                adapter_a=adapter_a,
                adapter_b=adapter_b,
                pass_rate_delta=mean_a - mean_b,
                mann_whitney_result=mwu,
                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
            )

        # Build summary aggregate.
        pass_rate_per_adapter = {name: per_adapter_results[name].summary.overall_pass_rate for name in adapters}
        best_adapter = max(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
        worst_adapter = min(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
        # Wall-clock measured from keyword-entry `t_start` — what the operator
        # ACTUALLY waited for (serial execution Phase-2; Phase-2.5 parallel
        # target). Story 13.3 code-review HIGH-A fix 2026-06-01 (Codex HIGH-1
        # + Opus MED-2 2-way): pre-fix `max(per-adapter runtimes)` reported
        # the slowest single adapter, underreporting actual wait time by
        # ~N-1× under serial execution. Per-adapter runtimes remain in
        # `per_adapter_results[adapter].summary.total_runtime_seconds`.
        total_runtime = time.monotonic() - t_start
        summary = DiscoverabilityComparisonSummary(
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
            pass_rate_per_adapter=pass_rate_per_adapter,
            best_adapter=best_adapter,
            worst_adapter=worst_adapter,
        )

        # Build a provisional comparison result so CohortHeatmap.from_comparison
        # can read the per-adapter results. The CohortHeatmap construction
        # happens AFTER per_adapter_results is populated; we pass a
        # "placeholder" comparison via direct construction (the
        # CohortHeatmap.from_comparison reads result.adapters + result.per_adapter_results
        # only, NOT the heatmap field — no chicken-and-egg).
        #
        # Build the heatmap via a lightweight namespace stand-in: the
        # classmethod accesses .adapters + .per_adapter_results.
        class _ComparisonShim:
            pass

        shim = _ComparisonShim()
        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
        heatmap = CohortHeatmap.from_comparison(shim)  # type: ignore[arg-type]

        # Track end-to-end runtime (caller-side; not stored separately
        # but contributes to the per-adapter timers we MAX'd above).
        _ = t_start

        return DiscoverabilityComparisonResult(
            adapters=tuple(adapters),
            per_adapter_results=per_adapter_results,
            cross_adapter_deltas=cross_adapter_deltas,
            heatmap=heatmap,
            summary=summary,
        )

codex
The story-level tests are green, but I already have one likely spec bug from code inspection: Story 13.3’s wall-clock fix was not ported exactly, because Story 13.5 starts the comparison timer after the one-time parse/load work. I’m validating that and the docs claim with direct repros now.
exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
from AgentEval.skills.types import SkillDiscoverabilityComparisonResult, SkillDiscoverabilityComparisonSummary, SkillDiscoverabilityResult, SkillDiscoverabilityTaskSummary, SkillTaskResult
from AgentEval._heatmap.models import CohortHeatmap

def make_skill_result(v=0.5):
    return SkillDiscoverabilityResult(
        per_task_results=(SkillTaskResult(task_id='t1', task_prompt='p', should_activate=True, trials_run=1, activations_observed=1, pass_at_k=v, competing_skills_picked={}, cost_per_trial_usd=0.0),),
        summary=SkillDiscoverabilityTaskSummary(activation_accuracy=v, false_activation_rate=0.0, missed_activation_rate=0.0, total_cost_usd=0.0, total_runtime_seconds=0.0),
        adapter_coverage='in_process',
    )
per={'a':make_skill_result(1.0),'b':make_skill_result(0.0)}
summary=SkillDiscoverabilityComparisonSummary(total_cost_usd=0.0,total_runtime_seconds=0.0,activation_accuracy_per_adapter={'a':1.0,'b':0.0},best_adapter='a',worst_adapter='b')
for label, heatmap in [
    ('heatmap_mismatch', CohortHeatmap(tasks=('t1',), models=('a','c'), cells=(('t1','a',1.0),('t1','c',0.0)))),
]:
    try:
        SkillDiscoverabilityComparisonResult(adapters=('a','b'), per_adapter_results=per, cross_adapter_deltas={}, heatmap=heatmap, summary=summary)
    except Exception as e:
        print(label, type(e).__name__, str(e))
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "cat > /tmp/story13_5_recipe.robot <<'EOF'
*** Settings ***
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill

*** Test Cases ***
Skill X Is Reliably Activated Across Claude And OpenAI
    "'${comparison}=    Skill.Compare Discoverability
    ...    skill=${CURDIR}/skills/web-search.md
    ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
    ...    adapters=${{['"'claude_code_cli', 'codex_cli']}}
    ...    trials_per_task=5
    ...    max_cost_usd=10.00
    Should Be True    "'${comparison.summary.activation_accuracy_per_adapter['"'claude_code_cli']} >= 0.7
    Should Be True    "'${comparison.summary.activation_accuracy_per_adapter['"'codex_cli']} >= 0.7
    # Cross-adapter significance — was the skill consistently triggered
    # OR did one adapter wildly outperform the other?
    "'${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
    Should Be True    abs(${delta.pass_at_k_delta}) < 0.3
EOF
robot --dryrun /tmp/story13_5_recipe.robot' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
import time
from AgentEval.skills.library import SkillsLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage
from typing import Any
from unittest.mock import patch

class Stub(InProcessAdapter):
    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        return AgentRunResult(response_text='example-search-skill', tool_calls=[], usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='a'*32)

register_adapter('ta', Stub)
register_adapter('tb', Stub)
lib = SkillsLibrary()
orig_parse = __import__('AgentEval.skills.library', fromlist=['parse_frontmatter']).parse_frontmatter
orig_load = __import__('AgentEval.skills.library', fromlist=['load_skill_discoverability_tasks']).load_skill_discoverability_tasks

def slow_parse(*args, **kwargs):
    time.sleep(0.15)
    return orig_parse(*args, **kwargs)

def slow_load(*args, **kwargs):
    time.sleep(0.15)
    return orig_load(*args, **kwargs)

with patch('AgentEval.skills.library.parse_frontmatter', side_effect=slow_parse), patch('AgentEval.skills.library.load_skill_discoverability_tasks', side_effect=slow_load):
    t0 = time.perf_counter()
    res = lib.get_discoverability_comparison(skill='tests/fixtures/skills/example-search.md', tasks='tests/fixtures/discoverability/skill-tasks-basic.yaml', adapters=['ta','tb'], trials_per_task=1)
    elapsed = time.perf_counter() - t0
    print('measured', elapsed)
    print('reported', res.summary.total_runtime_seconds)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "python - <<'PY'
from AgentEval.skills.library import SkillsLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage
from pathlib import Path
from typing import Any

class Stub(InProcessAdapter):
    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        return AgentRunResult(response_text='nothing', tool_calls=[], usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='a'*32)

register_adapter('a', Stub)
register_adapter('b', Stub)
register_adapter('c', Stub)
lib=SkillsLibrary()
r=lib.get_discoverability_comparison(skill='tests/fixtures/skills/example-search.md', tasks='tests/fixtures/discoverability/skill-tasks-basic.yaml', adapters=['a','b','c'], trials_per_task=1)
print(list(r.cross_adapter_deltas.keys()))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 484ms:
heatmap_mismatch ValueError adapters ['a', 'b'] must equal heatmap.models ['a', 'c']

 exited 1 in 721ms:
[ ERROR ] Error in file '/tmp/story13_5_recipe.robot' on line 2: Importing library 'AgentEval.skills.library.SkillsLibrary' failed: ModuleNotFoundError: No module named 'AgentEval'
Traceback (most recent call last):
  None
PYTHONPATH:
  /home/many/.local/bin
  /usr/lib/python312.zip
  /usr/lib/python3.12
  /usr/lib/python3.12/lib-dynload
  /home/many/.local/lib/python3.12/site-packages
  /usr/local/lib/python3.12/dist-packages
  /usr/lib/python3/dist-packages
==============================================================================
Story13 5 Recipe                                                              
==============================================================================
Skill X Is Reliably Activated Across Claude And OpenAI                | FAIL |
Several failures occurred:

1) No keyword with name 'Skill.Compare Discoverability' found.

2) No keyword with name 'Get From Dictionary' found.
------------------------------------------------------------------------------
Story13 5 Recipe                                                      | FAIL |
1 test, 0 passed, 1 failed
==============================================================================
Output:  /home/many/workspace/robotframework-agenteval/output.xml
Log:     /home/many/workspace/robotframework-agenteval/log.html
Report:  /home/many/workspace/robotframework-agenteval/report.html

 succeeded in 2092ms:
['a_vs_b', 'a_vs_c', 'b_vs_c']

 succeeded in 2536ms:
measured 1.885104836896062
reported 0.0020937849767506123

exec
/bin/bash -lc 'PYTHONPATH=src uv run robot --dryrun /tmp/story13_5_recipe.robot' in /home/many/workspace/robotframework-agenteval
 exited 1 in 513ms:
==============================================================================
Story13 5 Recipe                                                              
==============================================================================
Skill X Is Reliably Activated Across Claude And OpenAI                | FAIL |
No keyword with name 'Get From Dictionary' found.
------------------------------------------------------------------------------
Story13 5 Recipe                                                      | FAIL |
1 test, 0 passed, 1 failed
==============================================================================
Output:  /home/many/workspace/robotframework-agenteval/output.xml
Log:     /home/many/workspace/robotframework-agenteval/log.html
Report:  /home/many/workspace/robotframework-agenteval/report.html

codex
There’s a second issue worth checking: the new keyword exposes `max_cost_usd` / `max_runtime_seconds`, but `@guarded_fanout()` only reads host-instance attrs, not those keyword args. In direct `SkillsLibrary` usage that likely means the budget params are silently ignored. I’m reproing that explicitly.
exec
/bin/bash -lc "nl -ba docs/recipes/04-skill-author-stacked-validation.md | sed -n '130,170p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 2ms:
   130	
   131	```robotframework
   132	*** Settings ***
   133	Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
   134	
   135	*** Test Cases ***
   136	Skill X Is Reliably Activated Across Claude And OpenAI
   137	    ${comparison}=    Skill.Compare Discoverability
   138	    ...    skill=${CURDIR}/skills/web-search.md
   139	    ...    tasks=${CURDIR}/discoverability/web-search-tasks.yaml
   140	    ...    adapters=${{['claude_code_cli', 'codex_cli']}}
   141	    ...    trials_per_task=5
   142	    ...    max_cost_usd=10.00
   143	    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
   144	    Should Be True    ${comparison.summary.activation_accuracy_per_adapter['codex_cli']} >= 0.7
   145	    # Cross-adapter significance — was the skill consistently triggered
   146	    # OR did one adapter wildly outperform the other?
   147	    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
   148	    Should Be True    abs(${delta.pass_at_k_delta}) < 0.3
   149	```
   150	
   151	Behind the `[agenteval-advanced]` optional extra (scipy + numpy from Story 13.1
   152	for Mann-Whitney U significance). The keyword returns a
   153	`SkillDiscoverabilityComparisonResult` with per-adapter `SkillDiscoverabilityResult`
   154	+ cross-adapter Pass@k differential + per-adapter false-activation /
   155	missed-activation rate comparison + multi-column `CohortHeatmap` (which can
   156	render to HTML via Story 13.4's `as_html()` for stakeholder sharing).
   157	
   158	**Phase-1.5 dogfood deferral (DF-13.5-S4 / C98):** the
   159	`robotframework-agentskills` downstream repo will adopt the cross-adapter suite
   160	in its CI matrix (Mock provider for routine CI; a separate
   161	`weekly-cross-adapter-discoverability.yml` workflow runs against real APIs on a
   162	budget per epic L2227). Tracked as a Phase-1.5 carry-over.
   163	
   164	## See Also
   165	
   166	- Story 7.1: `Skill.Get Activation Decision` — single-prompt activation query
   167	- Story 7.2: `Skill.Get Discoverability` + `Skill.Should Activate For`
   168	- Story 6.3: `Stat.Run N Times` + `Stat.Get Pass At K`
   169	- Story 12.1: `Judge.Get Score` — Tier-2 LLM-judge keyword
   170	- Story 12.2: `Judge.Calibrate Rubric` + `docs/recipes/judge-calibration.md` — calibrate rubrics against human labels

exec
/bin/bash -lc "grep -RIn \"def run_single_adapter_discoverability\\|time.monotonic() - t_start\\|time.perf_counter() - t_start\" src/AgentEval/discoverability/_internal.py src/AgentEval/mcp/library.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
src/AgentEval/discoverability/_internal.py:49:def run_single_adapter_discoverability(
src/AgentEval/discoverability/_internal.py:160:    total_runtime = time.monotonic() - t_start
src/AgentEval/mcp/library.py:744:        total_runtime = time.monotonic() - t_start

exec
/bin/bash -lc "grep -RIn \"Get From Dictionary\" docs/recipes tests | sed -n '1,80p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
docs/recipes/04-skill-author-stacked-validation.md:147:    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli

exec
/bin/bash -lc "nl -ba src/AgentEval/skills/library.py | sed -n '520,640p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   520	            raise PollingDisallowedError(
   521	                build_polling_disallowed_message(
   522	                    "Skill.Compare Discoverability",
   523	                    {"skill": str(skill), "tasks": str(tasks), "adapters": adapters},
   524	                )
   525	            )
   526	        if not skill:
   527	            raise ValueError("Skill.Compare Discoverability requires `skill=<path>` kwarg")
   528	        if not tasks:
   529	            raise ValueError("Skill.Compare Discoverability requires `tasks=<yaml-path>` kwarg")
   530	        if trials_per_task < 1:
   531	            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
   532	        if adapters is None or len(adapters) < 2:
   533	            raise ValueError(
   534	                f"Skill.Compare Discoverability requires adapters=[<adapter_1>, "
   535	                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
   536	            )
   537	        if len(set(adapters)) != len(adapters):
   538	            raise ValueError(
   539	                f"Skill.Compare Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
   540	            )
   541	
   542	        # `[agenteval-advanced]` extras gate (Story 13.5 D-4 + L-2).
   543	        # Module-attr read per Story 13.3 amendment (NOT `from X import Y`
   544	        # which captures stale value across pytest session reload).
   545	        from AgentEval.stats import library as _stats_lib
   546	
   547	        if not _stats_lib._ADVANCED_AVAILABLE:
   548	            raise ImportError(
   549	                "Skill.Compare Discoverability: scipy + numpy required. "
   550	                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
   551	            )
   552	
   553	        # Parse skill frontmatter + tasks YAML ONCE (shared across adapters).
   554	        fm = parse_frontmatter(skill)
   555	        name_raw = fm.get("name")
   556	        skill_name = name_raw if isinstance(name_raw, str) else ""
   557	        skill_tasks = load_skill_discoverability_tasks(tasks)
   558	
   559	        from AgentEval._heatmap.models import CohortHeatmap
   560	        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
   561	        from AgentEval.stats.mannwhitney import compute_mann_whitney_u
   562	
   563	        # Story 13.3 HIGH-A precedent: anchor for comparison-level wall-clock.
   564	        compare_t_start = time.perf_counter()
   565	
   566	        per_adapter_results: dict[str, SkillDiscoverabilityResult] = {}
   567	        for adapter_name in adapters:
   568	            per_adapter_results[adapter_name] = run_single_adapter_skill_discoverability(
   569	                skill_name=skill_name,
   570	                task_list=skill_tasks,
   571	                adapter=adapter_name,
   572	                model=model,
   573	                trials_per_task=trials_per_task,
   574	                extra_adapter_kwargs=dict(kwargs),
   575	                t_start=time.perf_counter(),
   576	            )
   577	
   578	        # Build C(N, 2) pairwise deltas.
   579	        import itertools
   580	        import math as _math
   581	
   582	        cross_adapter_deltas: dict[str, SkillPairwiseAdapterDelta] = {}
   583	        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
   584	            a_result = per_adapter_results[adapter_a]
   585	            b_result = per_adapter_results[adapter_b]
   586	            rates_a = [t.pass_at_k for t in a_result.per_task_results]
   587	            rates_b = [t.pass_at_k for t in b_result.per_task_results]
   588	            if not rates_a or not rates_b:
   589	                continue
   590	            mwu = compute_mann_whitney_u(rates_a, rates_b)
   591	            delta_key = f"{adapter_a}_vs_{adapter_b}"
   592	            mean_a = sum(rates_a) / len(rates_a)
   593	            mean_b = sum(rates_b) / len(rates_b)
   594	            cross_adapter_deltas[delta_key] = SkillPairwiseAdapterDelta(
   595	                adapter_a=adapter_a,
   596	                adapter_b=adapter_b,
   597	                pass_at_k_delta=mean_a - mean_b,
   598	                pass_at_k_mann_whitney_result=mwu,
   599	                false_activation_rate_delta=a_result.summary.false_activation_rate
   600	                - b_result.summary.false_activation_rate,
   601	                missed_activation_rate_delta=a_result.summary.missed_activation_rate
   602	                - b_result.summary.missed_activation_rate,
   603	                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
   604	            )
   605	
   606	        # Build summary.
   607	        activation_accuracy_per_adapter = {
   608	            name: per_adapter_results[name].summary.activation_accuracy for name in adapters
   609	        }
   610	        best_adapter = max(
   611	            activation_accuracy_per_adapter,
   612	            key=lambda a: activation_accuracy_per_adapter[a],
   613	        )
   614	        worst_adapter = min(
   615	            activation_accuracy_per_adapter,
   616	            key=lambda a: activation_accuracy_per_adapter[a],
   617	        )
   618	        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
   619	        # Story 13.3 HIGH-A: comparison wall-clock measured from
   620	        # `compare_t_start` (NOT MAX of per-adapter, which would
   621	        # under-report serial execution by ~N-1×).
   622	        total_runtime = time.perf_counter() - compare_t_start
   623	        summary = SkillDiscoverabilityComparisonSummary(
   624	            total_cost_usd=total_cost,
   625	            total_runtime_seconds=total_runtime,
   626	            activation_accuracy_per_adapter=activation_accuracy_per_adapter,
   627	            best_adapter=best_adapter,
   628	            worst_adapter=worst_adapter,
   629	        )
   630	
   631	        # Build heatmap via the new classmethod. Use a shim namespace
   632	        # (mirrors Story 13.3 D-5 pattern) so the classmethod can read
   633	        # `.adapters` + `.per_adapter_results` before the full result
   634	        # dataclass is constructed.
   635	        class _ComparisonShim:
   636	            pass
   637	
   638	        shim = _ComparisonShim()
   639	        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
   640	        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]

exec
/bin/bash -lc "python - <<'PY'
from AgentEval.skills.library import SkillsLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage
from typing import Any

class Costly(InProcessAdapter):
    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        return AgentRunResult(response_text='example-search-skill', tool_calls=[], usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=5.0, latency_seconds=0.0, trace_id='a'*32)

register_adapter('costly_a', Costly)
register_adapter('costly_b', Costly)
lib = SkillsLibrary()
res = lib.get_discoverability_comparison(skill='tests/fixtures/skills/example-search.md', tasks='tests/fixtures/discoverability/skill-tasks-basic.yaml', adapters=['costly_a','costly_b'], trials_per_task=1, max_cost_usd=0.01, max_runtime_seconds=0.01)
print('returned', type(res).__name__, 'cost', res.summary.total_cost_usd, 'runtime', res.summary.total_runtime_seconds)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 1809ms:
returned SkillDiscoverabilityComparisonResult cost 50.0 runtime 0.002087219152599573

codex
I’ve confirmed two concrete implementation defects and one broken documentation claim. I’m doing one last pass over the skill test slice and the new comparison tests together to make sure there isn’t a hidden parity regression beyond those.
exec
/bin/bash -lc "nl -ba src/AgentEval/_kernel/guardrails.py | sed -n '255,275p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   255	            # Resolve budget: sentinel-private kwarg override (test-only) > instance attributes.
   256	            budget_override = kwargs.pop(_TEST_BUDGET_KWARG, None)
   257	            if budget_override is not None:
   258	                if not isinstance(budget_override, tuple) or len(budget_override) != 2:
   259	                    raise TypeError(
   260	                        f"{_TEST_BUDGET_KWARG} must be a 2-tuple of "
   261	                        f"(max_cost_usd, max_runtime_seconds); got {budget_override!r}"
   262	                    )
   263	                max_cost_usd, max_runtime_seconds = budget_override
   264	            else:
   265	                max_cost_usd = getattr(self, "_max_cost_usd", None)
   266	                max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)
   267	
   268	            # Layer 1: pre-flight estimation.
   269	            if estimator is not None:
   270	                try:
   271	                    estimator_result = estimator(kwargs)
   272	                except Exception as exc:
   273	                    raise CostExceededError(
   274	                        f"Pre-flight estimator callable raised {type(exc).__name__}: "
   275	                        f"{exc}; refusing to enter keyword body."

exec
/bin/bash -lc "nl -ba tests/integration/skills/test_skill_compare_e2e.py | sed -n '140,220p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   140	    # Skill name (from frontmatter parsed by the keyword body).
   141	    skill_name = "example-search-skill"
   142	
   143	    # Read the tasks YAML to extract the should-activate prompts for the
   144	    # "perfect" stub's prompt-matching logic.
   145	    import yaml
   146	
   147	    parsed = yaml.safe_load(tasks_fixture.read_text(encoding="utf-8"))
   148	    should_activate_prompts = {t["prompt"] for t in parsed["tasks"] if t.get("should_activate")}
   149	
   150	    register_adapter("skill_compare_stub_a", _make_stub_always_activate(skill_name))
   151	    register_adapter("skill_compare_stub_b", _make_stub_never_activate())
   152	    register_adapter(
   153	        "skill_compare_stub_c",
   154	        _make_stub_perfect_by_prompt(skill_name, should_activate_prompts),
   155	    )
   156	
   157	    lib = SkillsLibrary()
   158	    result = lib.get_discoverability_comparison(
   159	        skill=str(skill_fixture),
   160	        tasks=str(tasks_fixture),
   161	        adapters=["skill_compare_stub_a", "skill_compare_stub_b", "skill_compare_stub_c"],
   162	        trials_per_task=3,
   163	    )
   164	
   165	    assert isinstance(result, SkillDiscoverabilityComparisonResult)
   166	
   167	    accuracies = result.summary.activation_accuracy_per_adapter
   168	    # c is "perfect" → highest accuracy.
   169	    assert accuracies["skill_compare_stub_c"] == pytest.approx(1.0)
   170	    # a always-activates: correct on should_activate=True (3/5), wrong on decoys (2/5).
   171	    assert accuracies["skill_compare_stub_a"] == pytest.approx(3 / 5)
   172	    # b never activates: wrong on should_activate=True (3/5 missed), correct on decoys (2/5).
   173	    assert accuracies["skill_compare_stub_b"] == pytest.approx(2 / 5)
   174	
   175	    assert result.summary.best_adapter == "skill_compare_stub_c"
   176	    assert result.summary.worst_adapter == "skill_compare_stub_b"
   177	
   178	    # Pairwise deltas keyed.
   179	    assert set(result.cross_adapter_deltas.keys()) == {
   180	        "skill_compare_stub_a_vs_skill_compare_stub_b",
   181	        "skill_compare_stub_a_vs_skill_compare_stub_c",
   182	        "skill_compare_stub_b_vs_skill_compare_stub_c",
   183	    }
   184	
   185	    # False-activation deltas: stub_a is worst on decoys (false_activation_rate=1.0),
   186	    # stub_b + stub_c are 0.0. Delta a_vs_c > 0 (a worse).
   187	    delta_a_vs_c = result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"]
   188	    assert delta_a_vs_c.false_activation_rate_delta > 0
   189	
   190	    # Missed-activation deltas: stub_b is worst (misses all should_activate),
   191	    # stub_c is perfect.
   192	    delta_b_vs_c = result.cross_adapter_deltas["skill_compare_stub_b_vs_skill_compare_stub_c"]
   193	    assert delta_b_vs_c.missed_activation_rate_delta > 0
   194	
   195	    # Heatmap.
   196	    assert result.heatmap.models == (
   197	        "skill_compare_stub_a",
   198	        "skill_compare_stub_b",
   199	        "skill_compare_stub_c",
   200	    )
   201	
   202	    # Cost: zero per epic L2221 (Story 13.3 Codex MED-1 lesson applied).
   203	    assert result.summary.total_cost_usd == pytest.approx(0.0)
   204	
   205	
   206	def test_compare_rejects_single_adapter_list() -> None:
   207	    """≥2 adapter requirement enforced at arg validation."""
   208	    register_adapter("only_one_skill", _make_stub_never_activate())
   209	    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
   210	    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
   211	    lib = SkillsLibrary()
   212	    with pytest.raises(ValueError, match=">= 2 entries"):
   213	        lib.get_discoverability_comparison(
   214	            skill=str(skill_fixture),
   215	            tasks=str(tasks_fixture),
   216	            adapters=["only_one_skill"],
   217	            trials_per_task=1,
   218	        )
   219	
   220	

exec
/bin/bash -lc "nl -ba src/AgentEval/mcp/library.py | sed -n '632,748p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   632	            raise ValueError(
   633	                "MCP.Compare Tool Discoverability requires `mcp_server=<name>` kwarg "
   634	                "(name of an MCP server started via `MCP.Start Server`); empty "
   635	                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
   636	                "adapter-side integration."
   637	            )
   638	        if not tasks:
   639	            raise ValueError("MCP.Compare Tool Discoverability requires `tasks=<yaml-path>` kwarg")
   640	        if trials_per_task < 1:
   641	            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
   642	        if adapters is None or len(adapters) < 2:
   643	            raise ValueError(
   644	                f"MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, "
   645	                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
   646	            )
   647	        if len(set(adapters)) != len(adapters):
   648	            raise ValueError(
   649	                f"MCP.Compare Tool Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
   650	            )
   651	
   652	        # `[agenteval-advanced]` extras gate (D-6 + L-2). Fail-fast BEFORE
   653	        # the per-adapter fan-out so operators discovering the missing
   654	        # extra don't pay N-adapter trial cost first. Direct raise per
   655	        # AC-13.3.4 in-flight decision (b) — the `Stat.`-prefixed helper
   656	        # `_raise_advanced_extra_missing` would mis-frame the message
   657	        # for an `MCP.`-prefixed keyword.
   658	        #
   659	        # Read the attribute via module-level access (NOT
   660	        # `from X import Y` which binds a local) so test
   661	        # `monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)`
   662	        # is observed correctly even when this code path runs AFTER
   663	        # Story 13.1's `test_advanced_extras_gate.py` has run + cleaned
   664	        # up its own monkeypatch in the same pytest session.
   665	        from AgentEval.stats import library as _stats_lib
   666	
   667	        if not _stats_lib._ADVANCED_AVAILABLE:
   668	            raise ImportError(
   669	                "MCP.Compare Tool Discoverability: scipy + numpy required. "
   670	                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
   671	            )
   672	
   673	        # Load tasks YAML ONCE (shared across adapters).
   674	        task_list = load_discoverability_tasks(tasks)
   675	
   676	        # Run per-adapter discoverability serially. Phase-2.5 may parallelize
   677	        # via thread pool / asyncio; Phase-2 ships serial for simplicity +
   678	        # safer cost accounting.
   679	        from AgentEval._heatmap.models import CohortHeatmap
   680	        from AgentEval.discoverability._internal import run_single_adapter_discoverability
   681	        from AgentEval.discoverability.schema import (
   682	            DiscoverabilityComparisonResult,
   683	            DiscoverabilityComparisonSummary,
   684	            PairwiseAdapterDelta,
   685	        )
   686	        from AgentEval.stats.mannwhitney import compute_mann_whitney_u
   687	
   688	        per_adapter_results: dict[str, DiscoverabilityResult] = {}
   689	        for adapter_name in adapters:
   690	            # Per-adapter timer measures only THIS adapter's slice — useful
   691	            # for per-adapter cost auditing. The comparison-level wall-clock
   692	            # is measured separately from the keyword-entry `t_start` below.
   693	            per_adapter_results[adapter_name] = run_single_adapter_discoverability(
   694	                mcp_server=mcp_server,
   695	                adapter=adapter_name,
   696	                model=model,
   697	                task_list=task_list,
   698	                trials_per_task=trials_per_task,
   699	                max_cost_usd=max_cost_usd,
   700	                max_runtime_seconds=max_runtime_seconds,
   701	                extra_adapter_kwargs=dict(kwargs),
   702	                t_start=time.monotonic(),
   703	            )
   704	
   705	        # Build C(N, 2) pairwise deltas. Ordering: itertools.combinations
   706	        # preserves input order so `adapter_a` always comes before
   707	        # `adapter_b` in the input list.
   708	        import itertools
   709	
   710	        cross_adapter_deltas: dict[str, PairwiseAdapterDelta] = {}
   711	        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
   712	            rates_a = [t.pass_rate for t in per_adapter_results[adapter_a].per_task_results]
   713	            rates_b = [t.pass_rate for t in per_adapter_results[adapter_b].per_task_results]
   714	            # Empty per-task lists guard: skip the comparison if either is
   715	            # empty (would otherwise raise from `compute_mann_whitney_u`).
   716	            if not rates_a or not rates_b:
   717	                continue
   718	            mwu = compute_mann_whitney_u(rates_a, rates_b)
   719	            delta_key = f"{adapter_a}_vs_{adapter_b}"
   720	            mean_a = sum(rates_a) / len(rates_a)
   721	            mean_b = sum(rates_b) / len(rates_b)
   722	            import math as _math
   723	
   724	            cross_adapter_deltas[delta_key] = PairwiseAdapterDelta(
   725	                adapter_a=adapter_a,
   726	                adapter_b=adapter_b,
   727	                pass_rate_delta=mean_a - mean_b,
   728	                mann_whitney_result=mwu,
   729	                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
   730	            )
   731	
   732	        # Build summary aggregate.
   733	        pass_rate_per_adapter = {name: per_adapter_results[name].summary.overall_pass_rate for name in adapters}
   734	        best_adapter = max(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
   735	        worst_adapter = min(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
   736	        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
   737	        # Wall-clock measured from keyword-entry `t_start` — what the operator
   738	        # ACTUALLY waited for (serial execution Phase-2; Phase-2.5 parallel
   739	        # target). Story 13.3 code-review HIGH-A fix 2026-06-01 (Codex HIGH-1
   740	        # + Opus MED-2 2-way): pre-fix `max(per-adapter runtimes)` reported
   741	        # the slowest single adapter, underreporting actual wait time by
   742	        # ~N-1× under serial execution. Per-adapter runtimes remain in
   743	        # `per_adapter_results[adapter].summary.total_runtime_seconds`.
   744	        total_runtime = time.monotonic() - t_start
   745	        summary = DiscoverabilityComparisonSummary(
   746	            total_cost_usd=total_cost,
   747	            total_runtime_seconds=total_runtime,
   748	            pass_rate_per_adapter=pass_rate_per_adapter,

exec
/bin/bash -lc 'uv run pytest tests/unit/skills -q' in /home/many/workspace/robotframework-agenteval
 succeeded in 8168ms:
........................................................................ [ 67%]
...................................                                      [100%]
107 passed in 6.03s

exec
/bin/bash -lc "nl -ba tests/unit/skills/test_comparison.py | sed -n '340,430p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   340	        heatmap=heatmap,
   341	        summary=summary,
   342	    )
   343	    h = CohortHeatmap.from_skill_comparison(result)
   344	    data = h.as_dict()
   345	    assert data["t0"]["fast"] == 1.0
   346	    assert data["t0"]["slow"] == 0.0
   347	
   348	
   349	# --------------------------------------------------------------------------- #
   350	# Pairwise delta computation via end-to-end keyword (3 tests)                 #
   351	# --------------------------------------------------------------------------- #
   352	
   353	
   354	def test_compare_2_adapters_produces_1_pairwise_delta(
   355	    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
   356	) -> None:
   357	    """2 adapters → 1 pairwise delta."""
   358	    register_adapter("s2_act", _make_stub("example-search-skill response"))
   359	    register_adapter("s2_no", _make_stub("nothing happens here"))
   360	    result = lib.get_discoverability_comparison(
   361	        skill=str(skill_fixture_path),
   362	        tasks=str(tasks_fixture_path),
   363	        adapters=["s2_act", "s2_no"],
   364	        trials_per_task=3,
   365	    )
   366	    assert len(result.cross_adapter_deltas) == 1
   367	    assert "s2_act_vs_s2_no" in result.cross_adapter_deltas
   368	
   369	
   370	def test_compare_3_adapters_produces_3_pairwise_deltas(
   371	    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
   372	) -> None:
   373	    """3 adapters → 3 pairwise deltas (C(3,2))."""
   374	    register_adapter("s3_a", _make_stub("example-search-skill: yes"))
   375	    register_adapter("s3_b", _make_stub("nothing"))
   376	    register_adapter("s3_c", _make_stub("example-search-skill: maybe"))
   377	    result = lib.get_discoverability_comparison(
   378	        skill=str(skill_fixture_path),
   379	        tasks=str(tasks_fixture_path),
   380	        adapters=["s3_a", "s3_b", "s3_c"],
   381	        trials_per_task=3,
   382	    )
   383	    assert len(result.cross_adapter_deltas) == 3
   384	    assert set(result.cross_adapter_deltas.keys()) == {
   385	        "s3_a_vs_s3_b",
   386	        "s3_a_vs_s3_c",
   387	        "s3_b_vs_s3_c",
   388	    }
   389	
   390	
   391	def test_compare_pairwise_keys_preserve_input_order(
   392	    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
   393	) -> None:
   394	    register_adapter("zzz_first", _make_stub("nothing"))
   395	    register_adapter("aaa_second", _make_stub("nothing"))
   396	    result = lib.get_discoverability_comparison(
   397	        skill=str(skill_fixture_path),
   398	        tasks=str(tasks_fixture_path),
   399	        adapters=["zzz_first", "aaa_second"],
   400	        trials_per_task=3,
   401	    )
   402	    assert "zzz_first_vs_aaa_second" in result.cross_adapter_deltas
   403	
   404	
   405	# --------------------------------------------------------------------------- #
   406	# False-activation + missed-activation deltas (2 tests)                       #
   407	# --------------------------------------------------------------------------- #
   408	
   409	
   410	def test_compare_missed_activation_rate_delta(
   411	    lib: SkillsLibrary, skill_fixture_path: Path, tasks_fixture_path: Path
   412	) -> None:
   413	    """Stub that NEVER activates → high missed_activation_rate.
   414	
   415	    Stub-a always activates (skill name present in response); stub-b
   416	    never does. missed_activation_rate_delta (b - a) > 0 → b is WORSE.
   417	    """
   418	    register_adapter("miss_a", _make_stub("example-search-skill is here"))
   419	    register_adapter("miss_b", _make_stub("totally unrelated"))
   420	    result = lib.get_discoverability_comparison(
   421	        skill=str(skill_fixture_path),
   422	        tasks=str(tasks_fixture_path),
   423	        adapters=["miss_a", "miss_b"],
   424	        trials_per_task=3,
   425	    )
   426	    delta = result.cross_adapter_deltas["miss_a_vs_miss_b"]
   427	    # a misses 0; b misses all should-activate trials → b - a > 0 wait,
   428	    # delta is `a - b`, so a's rate minus b's rate → negative.
   429	    a_summary = result.per_adapter_results["miss_a"].summary
   430	    b_summary = result.per_adapter_results["miss_b"].summary

exec
/bin/bash -lc "nl -ba src/AgentEval/skills/library.py | sed -n '448,578p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   448	    def get_discoverability_comparison(
   449	        self,
   450	        skill: str | Path = "",
   451	        tasks: str | Path = "",
   452	        adapters: list[str] | None = None,
   453	        trials_per_task: int = 3,
   454	        max_cost_usd: float = 20.00,
   455	        max_runtime_seconds: float | None = None,
   456	        model: str | None = None,
   457	        polling: float | None = None,
   458	        **kwargs: Any,
   459	    ) -> SkillDiscoverabilityComparisonResult:
   460	        """Compares Skill Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR4c; Story 13.5).
   461	
   462	        [Tier 3 — Stochastic Fan-Out] — runs `Skill.Get Discoverability`
   463	        once per adapter against the SAME task set, then computes
   464	        pairwise Mann-Whitney U deltas across the per-task `pass_at_k`
   465	        distributions PLUS false-activation-rate + missed-activation-
   466	        rate deltas. Returns a `SkillDiscoverabilityComparisonResult`
   467	        with per-adapter results + cross-adapter deltas + multi-column
   468	        cohort heatmap + aggregate summary.
   469	
   470	        Requires the ``[agenteval-advanced]`` optional extra (scipy +
   471	        numpy) for the Mann-Whitney U cross-adapter delta computation;
   472	        raises ``ImportError`` on invocation WITHOUT the extra
   473	        (fail-fast BEFORE per-adapter fan-out — operators discovering
   474	        the missing extra should not pay N-adapter trial cost first).
   475	
   476	        | =Arguments= | =Description= |
   477	        | ``skill`` | Filesystem path to the skill ``.md`` file. |
   478	        | ``tasks`` | Filesystem path to the skill-discoverability tasks YAML (loaded ONCE; shared across adapters). |
   479	        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. |
   480	        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
   481	        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2218 (4× single-adapter typical). |
   482	        | ``max_runtime_seconds`` | Runtime cap. |
   483	        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. |
   484	        | ``polling`` | Must NOT be provided — raises ``PollingDisallowedError`` per FR28 (mirrors `Get Discoverability`). |
   485	        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |
   486	
   487	        Returns ``SkillDiscoverabilityComparisonResult`` with
   488	        ``adapters`` + ``per_adapter_results`` (one
   489	        ``SkillDiscoverabilityResult`` per adapter) +
   490	        ``cross_adapter_deltas`` (C(N, 2) ``SkillPairwiseAdapterDelta``
   491	        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
   492	        ``CohortHeatmap`` via ``from_skill_comparison``) + ``summary``
   493	        (``SkillDiscoverabilityComparisonSummary``).
   494	
   495	        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
   496	        missing. Raises ``PollingDisallowedError`` when ``polling`` is
   497	        provided. Raises ``ValueError`` on missing ``skill`` / ``tasks``
   498	        / ``adapters`` (≥2 distinct required) / invalid
   499	        ``trials_per_task``.
   500	
   501	        Example:
   502	        | ${comparison}=    `Skill.Compare Discoverability`
   503	        | ...    skill=${CURDIR}/skills/example.md
   504	        | ...    tasks=${CURDIR}/discoverability/skill-tasks.yaml
   505	        | ...    adapters=${{['claude_code_cli', 'codex_cli']}}
   506	        | ...    trials_per_task=5
   507	        | Should Be True    ${comparison.summary.activation_accuracy_per_adapter['claude_code_cli']} >= 0.7
   508	        | Should Be True    abs(${comparison.cross_adapter_deltas['claude_code_cli_vs_codex_cli'].pass_at_k_delta}) < 0.3
   509	
   510	        Notes:
   511	        - Story 13.5 (Epic 13) ships this Phase-2 keyword closing Devon's cross-adapter analysis loop. Symmetric to Story 13.3's `MCP.Compare Tool Discoverability` (FR10b).
   512	        - PRD FR4c ratifies the cross-adapter Skill Discoverability surface; epics.md L2218-2219 ratifies the keyword signature + extended fields (per-adapter false-activation / missed-activation rate comparison).
   513	        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper). Mann-Whitney U is computed on the per-task ``pass_at_k`` lists per adapter; false-activation + missed-activation deltas are aggregate-summary subtractions.
   514	        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition.
   515	        - Phase-2.5 carry-overs: DF-13.5-S1 (`@guarded_fanout` cross-library budget plumbing); DF-13.5-S2 (per-adapter MCP attachment); DF-13.5-S3 (Bonferroni multi-pairwise correction); DF-13.5-S4 (`robotframework-agentskills` dogfood CI matrix).
   516	        - Sibling keyword: `Skill.Get Discoverability` (Phase-1 single-adapter). The ≥2-adapter validation rejects N=1 callers — use the simpler `Get` keyword for single-adapter runs.
   517	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   518	        # Validate args (mirrors single-adapter Get + adds N>=2 constraint).
   519	        if polling is not None:
   520	            raise PollingDisallowedError(
   521	                build_polling_disallowed_message(
   522	                    "Skill.Compare Discoverability",
   523	                    {"skill": str(skill), "tasks": str(tasks), "adapters": adapters},
   524	                )
   525	            )
   526	        if not skill:
   527	            raise ValueError("Skill.Compare Discoverability requires `skill=<path>` kwarg")
   528	        if not tasks:
   529	            raise ValueError("Skill.Compare Discoverability requires `tasks=<yaml-path>` kwarg")
   530	        if trials_per_task < 1:
   531	            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
   532	        if adapters is None or len(adapters) < 2:
   533	            raise ValueError(
   534	                f"Skill.Compare Discoverability requires adapters=[<adapter_1>, "
   535	                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
   536	            )
   537	        if len(set(adapters)) != len(adapters):
   538	            raise ValueError(
   539	                f"Skill.Compare Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
   540	            )
   541	
   542	        # `[agenteval-advanced]` extras gate (Story 13.5 D-4 + L-2).
   543	        # Module-attr read per Story 13.3 amendment (NOT `from X import Y`
   544	        # which captures stale value across pytest session reload).
   545	        from AgentEval.stats import library as _stats_lib
   546	
   547	        if not _stats_lib._ADVANCED_AVAILABLE:
   548	            raise ImportError(
   549	                "Skill.Compare Discoverability: scipy + numpy required. "
   550	                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
   551	            )
   552	
   553	        # Parse skill frontmatter + tasks YAML ONCE (shared across adapters).
   554	        fm = parse_frontmatter(skill)
   555	        name_raw = fm.get("name")
   556	        skill_name = name_raw if isinstance(name_raw, str) else ""
   557	        skill_tasks = load_skill_discoverability_tasks(tasks)
   558	
   559	        from AgentEval._heatmap.models import CohortHeatmap
   560	        from AgentEval.skills._internal import run_single_adapter_skill_discoverability
   561	        from AgentEval.stats.mannwhitney import compute_mann_whitney_u
   562	
   563	        # Story 13.3 HIGH-A precedent: anchor for comparison-level wall-clock.
   564	        compare_t_start = time.perf_counter()
   565	
   566	        per_adapter_results: dict[str, SkillDiscoverabilityResult] = {}
   567	        for adapter_name in adapters:
   568	            per_adapter_results[adapter_name] = run_single_adapter_skill_discoverability(
   569	                skill_name=skill_name,
   570	                task_list=skill_tasks,
   571	                adapter=adapter_name,
   572	                model=model,
   573	                trials_per_task=trials_per_task,
   574	                extra_adapter_kwargs=dict(kwargs),
   575	                t_start=time.perf_counter(),
   576	            )
   577	
   578	        # Build C(N, 2) pairwise deltas.

exec
/bin/bash -lc "grep -n \"significant_at_alpha_05\\|p_value\" tests/integration/skills/test_skill_compare_e2e.py" in /home/many/workspace/robotframework-agenteval
 exited 1 in 0ms:
codex
### HIGH-1: `max_cost_usd` / `max_runtime_seconds` are dead public API parameters
**File:** `src/AgentEval/skills/library.py:454`
**Issue:** `Skill.Compare Discoverability` advertises per-call budget caps, but the keyword never uses those parameters. `@guarded_fanout()` only reads `self._max_cost_usd` / `self._max_runtime_seconds`, and `SkillsLibrary` is normally imported directly with neither attribute present, so calls run unbounded while implying the opposite.
**Evidence:** `library.py` declares the params at lines 454-455, but the per-adapter call at lines 568-575 does not pass them anywhere. The decorator resolves budgets only from instance attrs:
```text
src/AgentEval/_kernel/guardrails.py:265-266
max_cost_usd = getattr(self, "_max_cost_usd", None)
max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)
```
Direct repro:
```text
lib.get_discoverability_comparison(..., max_cost_usd=0.01, max_runtime_seconds=0.01)
returned SkillDiscoverabilityComparisonResult cost 50.0 runtime 0.002087219152599573
```
**Fix:** Either wire the keyword args into actual enforcement for this call, or remove/defang the parameters and document the same Phase-1 carve-out used by Story 13.3. As shipped, the API contract is unsafe.

### MED-2: Comparison runtime under-reports end-to-end wall clock
**File:** `src/AgentEval/skills/library.py:563`
**Issue:** Story 13.3’s HIGH-A fix was only partially ported. The comparison timer starts after the one-time parse/load setup, so `summary.total_runtime_seconds` excludes real user wait time and is not end-to-end as the story claims.
**Evidence:** The timer is initialized only after `parse_frontmatter()` and `load_skill_discoverability_tasks()`:
```text
553-557  # Parse skill frontmatter + tasks YAML ONCE
563-564  compare_t_start = time.perf_counter()
622      total_runtime = time.perf_counter() - compare_t_start
```
Story 13.3 starts timing at keyword entry and reports `time.monotonic() - t_start`:
```text
src/AgentEval/mcp/library.py:632-744
```
Repro with 150 ms sleeps injected into both setup calls:
```text
measured 1.885104836896062
reported 0.0020937849767506123
```
**Fix:** Move the comparison-level timer to the top of `get_discoverability_comparison`, before validation/setup, matching Story 13.3’s implementation.

### MED-3: Recipe #4 dry-run claim is false
**File:** `docs/recipes/04-skill-author-stacked-validation.md:147`
**Issue:** The new recipe snippet calls `Get From Dictionary` without importing `Collections`, so the documented example does not dry-run clean. That directly contradicts the story’s “`robot --dryrun` smoke verified clean” claim.
**Evidence:** The snippet only imports `SkillsLibrary`, then uses:
```text
147    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
```
Actual dry-run:
```text
PYTHONPATH=src uv run robot --dryrun /tmp/story13_5_recipe.robot
...
No keyword with name 'Get From Dictionary' found.
```
**Fix:** Add `Library    Collections` to the snippet, or rewrite the example to use direct dictionary indexing instead of `Get From Dictionary`.

### LOW-4: The integration test does not cover the promised positive-significance assertion
**File:** `tests/integration/skills/test_skill_compare_e2e.py:178`
**Issue:** AC-13.5.7 says the integration test should assert that `a_vs_c` is significant at α=0.05, but the shipped test never checks any `significant_at_alpha_05` flag or p-value. That leaves the core Mann-Whitney “known different distributions” path uncovered in the skill-domain e2e test.
**Evidence:** The test checks key presence, delta directions, heatmap models, and zero cost, but there is no significance assertion:
```text
178-203  assert set(result.cross_adapter_deltas.keys()) == {...}
187-193  assert delta_a_vs_c.false_activation_rate_delta > 0
         assert delta_b_vs_c.missed_activation_rate_delta > 0
202-203  assert result.summary.total_cost_usd == pytest.approx(0.0)
```
`grep -n "significant_at_alpha_05\\|p_value" tests/integration/skills/test_skill_compare_e2e.py` returns no matches.
**Fix:** Add an explicit assertion on the intended pair, e.g. `assert result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"].significant_at_alpha_05 is True`, using stub/task distributions that reliably produce that result.

**Total: 1 HIGH + 2 MED + 1 LOW**
tokens used
269,635
### HIGH-1: `max_cost_usd` / `max_runtime_seconds` are dead public API parameters
**File:** `src/AgentEval/skills/library.py:454`
**Issue:** `Skill.Compare Discoverability` advertises per-call budget caps, but the keyword never uses those parameters. `@guarded_fanout()` only reads `self._max_cost_usd` / `self._max_runtime_seconds`, and `SkillsLibrary` is normally imported directly with neither attribute present, so calls run unbounded while implying the opposite.
**Evidence:** `library.py` declares the params at lines 454-455, but the per-adapter call at lines 568-575 does not pass them anywhere. The decorator resolves budgets only from instance attrs:
```text
src/AgentEval/_kernel/guardrails.py:265-266
max_cost_usd = getattr(self, "_max_cost_usd", None)
max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)
```
Direct repro:
```text
lib.get_discoverability_comparison(..., max_cost_usd=0.01, max_runtime_seconds=0.01)
returned SkillDiscoverabilityComparisonResult cost 50.0 runtime 0.002087219152599573
```
**Fix:** Either wire the keyword args into actual enforcement for this call, or remove/defang the parameters and document the same Phase-1 carve-out used by Story 13.3. As shipped, the API contract is unsafe.

### MED-2: Comparison runtime under-reports end-to-end wall clock
**File:** `src/AgentEval/skills/library.py:563`
**Issue:** Story 13.3’s HIGH-A fix was only partially ported. The comparison timer starts after the one-time parse/load setup, so `summary.total_runtime_seconds` excludes real user wait time and is not end-to-end as the story claims.
**Evidence:** The timer is initialized only after `parse_frontmatter()` and `load_skill_discoverability_tasks()`:
```text
553-557  # Parse skill frontmatter + tasks YAML ONCE
563-564  compare_t_start = time.perf_counter()
622      total_runtime = time.perf_counter() - compare_t_start
```
Story 13.3 starts timing at keyword entry and reports `time.monotonic() - t_start`:
```text
src/AgentEval/mcp/library.py:632-744
```
Repro with 150 ms sleeps injected into both setup calls:
```text
measured 1.885104836896062
reported 0.0020937849767506123
```
**Fix:** Move the comparison-level timer to the top of `get_discoverability_comparison`, before validation/setup, matching Story 13.3’s implementation.

### MED-3: Recipe #4 dry-run claim is false
**File:** `docs/recipes/04-skill-author-stacked-validation.md:147`
**Issue:** The new recipe snippet calls `Get From Dictionary` without importing `Collections`, so the documented example does not dry-run clean. That directly contradicts the story’s “`robot --dryrun` smoke verified clean” claim.
**Evidence:** The snippet only imports `SkillsLibrary`, then uses:
```text
147    ${delta}=    Get From Dictionary    ${comparison.cross_adapter_deltas}    claude_code_cli_vs_codex_cli
```
Actual dry-run:
```text
PYTHONPATH=src uv run robot --dryrun /tmp/story13_5_recipe.robot
...
No keyword with name 'Get From Dictionary' found.
```
**Fix:** Add `Library    Collections` to the snippet, or rewrite the example to use direct dictionary indexing instead of `Get From Dictionary`.

### LOW-4: The integration test does not cover the promised positive-significance assertion
**File:** `tests/integration/skills/test_skill_compare_e2e.py:178`
**Issue:** AC-13.5.7 says the integration test should assert that `a_vs_c` is significant at α=0.05, but the shipped test never checks any `significant_at_alpha_05` flag or p-value. That leaves the core Mann-Whitney “known different distributions” path uncovered in the skill-domain e2e test.
**Evidence:** The test checks key presence, delta directions, heatmap models, and zero cost, but there is no significance assertion:
```text
178-203  assert set(result.cross_adapter_deltas.keys()) == {...}
187-193  assert delta_a_vs_c.false_activation_rate_delta > 0
         assert delta_b_vs_c.missed_activation_rate_delta > 0
202-203  assert result.summary.total_cost_usd == pytest.approx(0.0)
```
`grep -n "significant_at_alpha_05\\|p_value" tests/integration/skills/test_skill_compare_e2e.py` returns no matches.
**Fix:** Add an explicit assertion on the intended pair, e.g. `assert result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"].significant_at_alpha_05 is True`, using stub/task distributions that reliably produce that result.

**Total: 1 HIGH + 2 MED + 1 LOW**
