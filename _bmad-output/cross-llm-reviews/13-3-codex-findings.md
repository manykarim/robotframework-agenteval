OpenAI Codex v0.133.0
--------
workdir: /home/many/workspace/robotframework-agenteval
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: high
reasoning summaries: none
session id: 019e8301-f00b-7782-8960-3bfffe65a0c6
--------
user
# Adversarial Code Review — Story 13.3: MCP.Compare Tool Discoverability Cross-Adapter (PRD FR10b)

You are a SENIOR REVIEWER for the robotframework-agenteval project. Find REAL bugs, REAL spec drift, REAL correctness defects in Story 13.3. Be ADVERSARIAL but HONEST.

## Project context

- robotframework-agenteval: open-source Robot Framework library evaluating AI coding agents. Python 3.12+, RF 7.x.
- Story 13.3 ships `MCP.Compare Tool Discoverability adapters=[...]` keyword that fans out per-adapter Tool Discoverability evaluation across N≥2 adapters + computes pairwise Mann-Whitney U cross-adapter deltas + builds multi-column CohortHeatmap.
- Builds on: Story 4.4 (`MCP.Get Tool Discoverability` single-adapter), Story 13.1 (`MannWhitneyResult` + `compute_mann_whitney_u` pure helper at `stats/mannwhitney.py` + `[agenteval-advanced]` extra), Story 8b.2 (`CohortHeatmap` with `from_discoverability`).
- Story file: `_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md`
- Stories 13.1 + 13.2 reviews each produced 4-6 HIGH findings; Story 13.3 should be reviewed at the same rigor.

## Review prompt (re-derive cited facts from source per `feedback_citation_drift_first_class`)

Re-derive every dev claim from source: PRD (`_bmad-output/planning-artifacts/prd.md` L1500 for FR10b - check the AMENDMENT was actually applied), architecture (`_bmad-output/planning-artifacts/architecture.md` L1258 for MCPLibrary file home), epics.md L2177-2189, existing Story 4.4 + Story 13.1 + Story 8b.2 code. Flag any drift as HIGH.

## Specific behavioral probes (per `feedback_codex_probe_fitness`)

1. **Helper extraction behavioral equivalence.** Story 4.4's existing `MCP.Get Tool Discoverability` was refactored to call `run_single_adapter_discoverability`. Does the refactor introduce ANY behavior change? Run the 50+ existing Story 4.4 tests at `tests/unit/discoverability/test_keyword.py` against the refactored code and verify they all pass.
2. **N=2 vs N=3 vs N=4 adapter counts.** The keyword validates `len(adapters) >= 2`. Does it handle exactly N=2 correctly (1 pairwise delta)? N=3 (3 pairs)? N=4 (6 pairs)? Probe via the keyword + verify `len(result.cross_adapter_deltas) == N*(N-1)/2`.
3. **Pairwise delta ordering determinism.** The dev uses `itertools.combinations(adapters, 2)` to generate pairs. Is the output order deterministic? Does swapping the adapters list order change the delta keys? Verify: `adapters=["a", "b", "c"]` produces keys `["a_vs_b", "a_vs_c", "b_vs_c"]`; `adapters=["c", "b", "a"]` produces `["c_vs_b", "c_vs_a", "b_vs_a"]`.
4. **Mann-Whitney U identical-samples nan handling.** When two adapters produce IDENTICAL per-task pass-rate distributions (e.g., both all-pass), scipy returns `p_value=nan`. The dev added nan-tolerance to `MannWhitneyResult.__post_init__` AND to `PairwiseAdapterDelta.significant_at_alpha_05`. Does this propagate correctly all the way to the keyword's `cross_adapter_deltas` mapping?
5. **`@guarded_fanout` decorator omitted.** Spec D-7 said `@tier(3) + @guarded_fanout()`. Dev removed `@guarded_fanout()` per in-flight amendment because MCPLibrary doesn't carry `_max_cost_usd`. Verify this matches the existing `MCP.Get Tool Discoverability` pattern (only `@tier(3)`).
6. **Helper sharing — `_run_single_adapter` cost accounting bug.** The dev passes `t_start=time.monotonic()` PER ADAPTER to the helper. Each adapter's `total_runtime_seconds` measures from its OWN start. Is this the right semantic? Should the runtime be measured end-to-end across all adapters?
7. **CohortHeatmap shim hack.** In `mcp/library.py:compute_tool_discoverability_comparison`, the dev uses a `_ComparisonShim` class to build the heatmap BEFORE the full `DiscoverabilityComparisonResult` exists (chicken-and-egg). Is this hack correct? Does `CohortHeatmap.from_comparison` only read `.adapters + .per_adapter_results`? Verify by reading the implementation.
8. **`_ADVANCED_AVAILABLE` module-attr read amendment.** Dev changed `from AgentEval.stats.library import _ADVANCED_AVAILABLE` to `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` to handle pytest session-wide reload. Is this the right fix? Does it work in production when the gate is ACTUALLY tripped (not just under test)?
9. **Test count claim verification.** Dev claims 22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration). Re-count by running `pytest --collect-only` on each new test file.
10. **PRD amendment was actually applied.** Dev claims PRD L1500 amended per D-1 (N-runtime `adapters=[...]` shape + `DiscoverabilityResult` typo fix). Verify by reading the PRD line.

## Categorization

- **HIGH**: Real bug, real spec drift, real correctness defect.
- **MED**: Significant quality issue / test coverage gap.
- **LOW**: Minor improvement / style / docstring polish.

## Output format

For each finding:

```
### [HIGH/MED/LOW]-N: <one-line title>

**File:** `<path>:<line>`
**Issue:** <2-3 sentences>
**Evidence:** <verbatim code excerpt or test output>
**Fix:** <concrete patch suggestion>
```

End with: `**Total: X HIGH + Y MED + Z LOW**`.

## Story diff

The full diff (~2000+ lines) is at `/tmp/story-13-3-review.diff`. Read it and analyze.

---

## Diff to review:

```diff
diff --git a/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md b/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md
new file mode 100644
index 0000000..7a2f584
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md
@@ -0,0 +1,421 @@
+# Story 13.3: Compare Tool Discoverability Cross-Adapter (FR10b)
+
+Status: review
+
+## Story
+
+As **Mei (Agent Surface Author)** doing cross-runtime MCP analysis,
+I want `MCP.Compare Tool Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per PRD FR10b,
+So that I can claim "tool X is discoverable by Claude AND GPT AND Copilot" with empirical evidence — the killer Mei feature deferred from Phase 1, building on Story 13.1's Mann-Whitney U + Story 8b.2's `CohortHeatmap` + Story 4.4's per-adapter `MCP.Get Tool Discoverability`.
+
+## Pre-create-story drift check (53rd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+11 drifts caught — 6 fresh decisions from spec analysis + 5 UPSTREAM lessons from Stories 13.1 + 13.2 reviews. **100% real-drift catch rate maintained through 52 prior uses.**
+
+- **D-1 (HIGH — runtime-shape drift PRD vs epic, 1-vs-1 NOT resolved by majority — needs Mei intent reading):** **PRD vs epic disagree on the keyword signature.**
+  - **PRD L1500:** `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>` — explicit 2-runtime A/B comparison.
+  - **Epic L2186:** `MCP.Compare Tool Discoverability mcp_server=rf-mcp tasks=... adapters=[generic, claude-agent-sdk, openai-agents-sdk] trials_per_task=5 max_cost_usd=20.00` — N-runtime list (3 adapters in the example).
+  - **Decision (epic wins, generalize-then-PRD-amend):** ship the N-runtime `adapters: list[str]` shape per epic — covers the PRD's 2-runtime A/B case by passing a 2-element list (`adapters=["claude_code_cli", "codex_cli"]`). The N-shape is strictly more general, more aligned with Mei's "claim X across Claude AND GPT AND Copilot" goal (which requires ≥3 adapters), and matches Story 13.5's symmetric Skill version (which also uses `adapters=[...]`). **Same-commit fix:** amend PRD L1500 to read: `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...] (≥2 required)` with note "Backwards-compat: a 2-element list satisfies the original A/B semantic". Per `feedback_in_flight_spec_amendment` + Story 13.1 D-1 fix-the-losing-source-NOW precedent.
+
+- **D-2 (HIGH — return-type shape, no canonical source):** PRD doesn't fully spec `DiscoverabilityComparisonResult`'s field set; epic L2187 enumerates "per-adapter task-level results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data." **Decision:** ship `DiscoverabilityComparisonResult` frozen dataclass at `src/AgentEval/discoverability/schema.py` (alongside existing `DiscoverabilityResult` / `TaskResult` / `DiscoverabilitySummary`) with fields:
+  ```python
+  @dataclass(frozen=True)
+  class DiscoverabilityComparisonResult:
+      adapters: tuple[str, ...]                                                       # adapter names in input order
+      per_adapter_results: Mapping[str, DiscoverabilityResult]                        # {adapter_name: per-adapter result}
+      cross_adapter_deltas: Mapping[str, "PairwiseAdapterDelta"]                      # {f"{a1}_vs_{a2}": delta} for all ordered pairs
+      heatmap: CohortHeatmap                                                          # multi-column heatmap (one column per adapter)
+      summary: "DiscoverabilityComparisonSummary"                                     # aggregate roll-up
+  ```
+  with:
+  ```python
+  @dataclass(frozen=True)
+  class PairwiseAdapterDelta:
+      adapter_a: str
+      adapter_b: str
+      pass_rate_delta: float                                                          # avg(adapter_a per-task pass rate) - avg(adapter_b)
+      mann_whitney_result: MannWhitneyResult                                          # Story 13.1 dataclass; predicate=lambda r: r.pass_rate
+      significant_at_alpha_05: bool                                                   # p_value < 0.05
+
+  @dataclass(frozen=True)
+  class DiscoverabilityComparisonSummary:
+      total_cost_usd: float                                                           # sum across all adapters
+      total_runtime_seconds: float                                                    # max across adapters (parallel; not summed)
+      pass_rate_per_adapter: Mapping[str, float]                                      # adapter_name → overall_pass_rate
+      best_adapter: str                                                               # max(pass_rate_per_adapter)
+      worst_adapter: str                                                              # min(pass_rate_per_adapter)
+  ```
+  Frozen dataclasses with `__post_init__` defensive copy + Mapping → dict cast per Story 1b.2 M_R6 pattern + Story 4.4 frozen-invariant precedent.
+
+- **D-3 (HIGH — file home + sub-library composition, `MCPLibrary` carve-out):** `MCPLibrary` is excluded from `_SUB_LIBRARIES` per Story 2.2 collision norm + Story 4.4 architectural gap (DF-4.4-S1 / C20: `@guarded_fanout` enforcement deferred because `MCPLibrary` constructed via `WITH NAME MCP` not `_SUB_LIBRARIES`). **Decision:** ship `MCP.Compare Tool Discoverability` as a NEW `@keyword`-decorated method on `MCPLibrary` at `src/AgentEval/mcp/library.py` — same parent as `MCP.Get Tool Discoverability`. Same `@guarded_fanout` carve-out applies (kwargs tracked, NOT enforced; DF-4.4-S1 carry-over EXTENDED to cover Compare). NO new sub-library. Per Story 13.1 D-5 + Story 13.2 D-3: honor architecture's pre-allocated file home; don't create new modules.
+
+- **D-4 (HIGH — `mcp_server` arg semantics under N-adapters):** Epic AC L2186 shows ONE `mcp_server=rf-mcp` arg shared across all adapters. The Phase-1 `Get Tool Discoverability` carve-out (DF-4.1-S2 + DF-4.2-S1) means `mcp_server=` is accepted-but-not-forwarded to `adapter.run(mcp_servers=...)` — both Phase-1 adapters raise `NotImplementedError` on non-empty `mcp_servers`. For Phase-2 adapters from Stories 10.1+10.2 (Claude Agent SDK + OpenAI Agents SDK) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge. **Decision:** Cross-adapter `Compare Tool Discoverability` inherits the same carve-out behavior — the `mcp_server` arg is forwarded VERBATIM to each per-adapter `Get Tool Discoverability` call; downstream behavior is identical to single-adapter Phase-1 (accepted, validated non-empty, not forwarded to adapter.run; tests use stub adapters via `register_adapter` per Story 7.3 pattern). Catalog a DF-13.3-S2 carry-over for "Phase-2.5: real per-adapter MCP attachment" gated on C72 + C68 + C69 + C73 + C75 (the existing per-adapter MCP-bridge backlog).
+
+- **D-5 (HIGH — Mann-Whitney U predicate selection):** Story 13.1's `Stat.Mann Whitney U` requires `predicate: Callable[[KeywordRun], float]` value-extractor. But the comparison input is `list[TaskResult]` per adapter, NOT `list[KeywordRun]`. **Decision:** the Mann-Whitney U input is the PER-TASK pass-rate list per adapter:
+  ```python
+  rates_a = [t.pass_rate for t in per_adapter_results["adapter_a"].per_task_results]
+  rates_b = [t.pass_rate for t in per_adapter_results["adapter_b"].per_task_results]
+  ```
+  These are `list[float]` directly. `MannWhitneyResult` consumes these via the lower-level `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` helper at `src/AgentEval/stats/mannwhitney.py` (Story 13.1 module-level pure helper). The keyword surface `Stat.Mann Whitney U` (which takes `list[KeywordRun]` + predicate) does NOT apply at this layer; we call the pure helper directly. Document this dispatch in the dev notes. (`_ADVANCED_AVAILABLE` gate at `stats/library.py` controls availability — same ImportError gate as the keyword surface; OTLPBackend D-5 precedent applies.)
+
+- **D-6 (HIGH — `[agenteval-advanced]` extras dependency + ImportError gate):** Mann-Whitney U requires scipy + numpy via Story 13.1's `[agenteval-advanced]` extra. Story 13.3's `Compare Tool Discoverability` IS-A consumer of that dependency. **Decision:** `MCP.Compare Tool Discoverability` raises the SAME canonical ImportError (`"Stat.Mann Whitney U: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`) when invoked without `[agenteval-advanced]`. Implementation: at the call site, probe `from AgentEval.stats.library import _ADVANCED_AVAILABLE`; if False, raise ImportError BEFORE running any per-adapter fan-out (fail-fast, save cost — operators discovering the missing extra should not pay 3-adapter trial cost first). Per Story 13.2 L-2 lesson: tests split into happy-path + extras-gate files.
+
+- **D-7 (MED — `@tier(3)` + `@guarded_fanout` for the Compare-keyword, UPSTREAM Story 13.1 HIGH-C lesson):** `Compare Tool Discoverability` runs N×M trials (N adapters × M tasks × `trials_per_task` trials). This is Tier-3 fan-out by definition (parallel to `Stat.Run N Times` + `MCP.Get Tool Discoverability`). **Decision:** `@tier(3) + @guarded_fanout()` on the method, mirroring `MCP.Get Tool Discoverability` per Story 4.4 pattern. The `@guarded_fanout` Phase-1 carve-out applies identically (DF-4.4-S1 / C20: kwargs tracked, NOT enforced). Story 13.1 HIGH-C lesson re seed-required-for-FR31a DOESN'T apply here — `@tier(3)` keywords are explicitly stochastic by tier definition; no bit-identical guarantee.
+
+- **D-8 (MED — `CohortHeatmap` multi-adapter extension):** Story 8b.2's `CohortHeatmap` already supports multi-column heatmaps via `tasks: tuple[str, ...]` + `models: tuple[str, ...]` + `cells`. `CohortHeatmap.from_discoverability` is single-model-only (Phase-1 carve-out per `_heatmap/models.py:46`). **Decision:** ADD a NEW classmethod `CohortHeatmap.from_comparison(result: DiscoverabilityComparisonResult) -> CohortHeatmap` at `src/AgentEval/_heatmap/models.py` that builds a multi-column heatmap (columns = adapter names; rows = task IDs; cells = per-adapter per-task pass-rate). The existing single-model classmethod stays unchanged for backward compat. This is the "cohort heatmap data" half of epic AC L2187 ("+ cohort heatmap data").
+
+- **D-9 (MED — integration test stub-adapter pattern per epic L2189):** Epic L2189 mandates "integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero)." Story 12.3 + Story 7.3 established the canonical `register_adapter()` stub pattern (NOT MockProvider at the provider layer — adapter-level stub). **Decision:** use the `register_adapter` 3-stub pattern from Story 12.3 — register 3 stub adapters (`compare_stub_a`, `compare_stub_b`, `compare_stub_c`) returning different per-task pass-rate distributions so Mann-Whitney U produces meaningfully different p-values. The 3rd stub validates ≥2 adapters → N-adapter generalization (per D-1 PRD-amend coverage).
+
+- **D-10 (LOW — carry-over catalog gate UPSTREAM Story 13.1+13.2, 34th consecutive):** Anticipated Phase-1.5 / Phase-2 carry-overs for Story 13.3:
+  - **DF-13.3-S1 (Phase-2.5):** `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` — same architectural gap as DF-4.4-S1 / C20. Cross-adapter fan-out compounds cost N× (N adapters × M tasks × trials). Once Phase-1.5 lands `MCPLibrary` cross-library budget plumbing, this keyword benefits identically.
+  - **DF-13.3-S2 (Phase-2.5):** Real per-adapter MCP-server attachment (gated on C72 LiteLLM MCP-bridge + C68/C69/C73/C75 per-adapter HostedMcpObserver wiring). Phase-2 ships the keyword shape + stub-adapter testing; real cross-adapter MCP coverage flows from upstream MCP-bridge work.
+  - **DF-13.3-S3 (Phase-2.5):** Multi-pairwise correction (Bonferroni / Holm) for the cross-adapter delta significance. Phase-2 ships pairwise comparisons WITHOUT multiple-testing correction — for N=3 adapters there are C(3,2)=3 pairs; Bonferroni-adjusted α=0.0167. Add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` in Phase-2.5.
+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C89 + C90 + C91 BEFORE invoking `/bmad-code-review`.
+
+## Cross-story upstream lessons from Stories 13.1 + 13.2 reviews
+
+Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; this is Story 13.2 → 13.3 same-epic transition):
+
+- **L-1 applied (stability-surface drift UPSTREAM)**: register `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` + `CohortHeatmap.from_comparison` classmethod + the new `MCP.Compare Tool Discoverability` keyword in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.3.10. Verify via grep before flipping to done.
+- **L-2 applied (extras-gate test split)**: ImportError-gate tests (the `[agenteval-advanced]` requirement bubble-up from D-6) sit in a SEPARATE file from happy-path tests — NO `importorskip` at module top so they run in both base + WITH-extras CI envs. Story 13.1's `test_advanced_extras_gate.py` + Story 13.2's `test_backends_otlp_extras_gate.py` are the canonical pattern.
+- **L-3 applied (Tier classification rationale)**: `MCP.Compare Tool Discoverability` is `@tier(3)` per fan-out semantics — the Story 13.1 HIGH-C seed-required-for-bit-identical FR31a concern does NOT apply (`@tier(3)` is explicitly stochastic). Document the @tier rationale in the keyword docstring.
+- **L-4 applied (empirical correctness verification)**: integration test asserts CONCRETE numerical output of the cross-adapter delta — specifically that 3 stub adapters with KNOWN different pass-rate distributions produce the EXPECTED ranking (e.g., stub_a > stub_b > stub_c) + the expected p-value sign (stub_a-vs-stub_c should have p < 0.05). NOT just "the keyword ran without error."
+- **L-5 applied (docstring precision)**: keyword docstring names the EXACT helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u` (Story 13.1 pure helper) and does NOT claim "calls Stat.Mann Whitney U" (which would be misleading since the keyword surface takes `list[KeywordRun]`, not the `list[float]` pass-rate input). Browser-Library-convention anchor test asserts "Mann-Whitney U" + "Story 13.1" + "FR10b" + "Phase-2" appear in the docstring.
+
+## Acceptance Criteria
+
+### AC-13.3.1 — `MCP.Compare Tool Discoverability` keyword on `MCPLibrary`
+
+`src/AgentEval/mcp/library.py` extends `MCPLibrary` with a new `@keyword + @tier(3) + @guarded_fanout()`-decorated method (placed AFTER `get_tool_discoverability`):
+
+```python
+@keyword(name="MCP.Compare Tool Discoverability")
+@tier(3)
+@guarded_fanout()
+def compare_tool_discoverability(
+    self,
+    mcp_server: str = "",
+    adapters: list[str] | None = None,
+    tasks: str = "",
+    trials_per_task: int = 3,
+    max_cost_usd: float = 20.00,
+    max_runtime_seconds: float | None = None,
+    model: str | None = None,
+    **kwargs: Any,
+) -> DiscoverabilityComparisonResult: ...
+```
+
+Signature notes:
+- `adapters` REQUIRED (no sensible default); ≥2 elements required (raises `ValueError("MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, <adapter_2>, ...] with ≥2 entries; got {adapters!r}")` otherwise).
+- `mcp_server` + `tasks` REQUIRED (mirrors `Get Tool Discoverability` validation).
+- `max_cost_usd` default `20.00` per epic L2186 verbatim (4× the single-adapter default of `5.00`, reflecting the N=3-adapter typical cost).
+- `model` optional: when given, forwarded to ALL adapters; when None, each adapter uses its default. Phase-2 carry-over (DF-13.3-S4 Phase-2.5): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg.
+
+Implementation:
+1. Validate args (incl. ≥2 adapters).
+2. Pre-flight `_ADVANCED_AVAILABLE` gate per D-6.
+3. Load tasks YAML once (shared across adapters).
+4. For each adapter in `adapters`: invoke per-adapter discoverability internally (delegating to the same logic as `get_tool_discoverability` but without re-validating + without per-call YAML re-load — extract a private `_run_single_adapter_discoverability` helper for shared logic).
+5. Compute all C(N, 2) pairwise deltas via `compute_mann_whitney_u(rates_a, rates_b)`.
+6. Build the multi-column `CohortHeatmap.from_comparison(result)`.
+7. Build the summary.
+8. Return `DiscoverabilityComparisonResult(...)`.
+
+### AC-13.3.2 — `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` dataclasses
+
+`src/AgentEval/discoverability/schema.py` appends 3 new frozen dataclasses per D-2 verbatim shape. All carry `__post_init__` defensive copies of mutable containers (`Mapping → dict(...)` cast; tuple immutability for `adapters`). Validators:
+
+- `DiscoverabilityComparisonResult.__post_init__`: assert `len(adapters) >= 2`; assert `set(adapters) == set(per_adapter_results.keys())`; assert `set(adapters) == set(heatmap.models)` (cross-consistency).
+- `PairwiseAdapterDelta.__post_init__`: assert `adapter_a != adapter_b`; assert `-1.0 <= pass_rate_delta <= 1.0`; assert `significant_at_alpha_05 == (mann_whitney_result.p_value < 0.05)`.
+- `DiscoverabilityComparisonSummary.__post_init__`: assert `set(pass_rate_per_adapter.keys()) == set(adapters_referenced_in_comparison)`; assert `best_adapter` AND `worst_adapter` ∈ `pass_rate_per_adapter.keys()`; defensive `dict(...)` cast on `pass_rate_per_adapter`.
+
+The 3 new classes added to `__all__`.
+
+### AC-13.3.3 — `CohortHeatmap.from_comparison` classmethod
+
+`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with a new classmethod (placed AFTER `from_discoverability`):
+
+```python
+@classmethod
+def from_comparison(
+    cls,
+    result: DiscoverabilityComparisonResult,
+) -> CohortHeatmap:
+    """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).
+
+    Columns = adapter names (preserving input order). Rows = task IDs
+    (union across all per-adapter results — should be identical since
+    each adapter ran the same task set, but defensively uses the union
+    to handle stub-adapter edge cases).
+    """
+```
+
+Implementation:
+- `tasks = tuple(union of task_ids across all per_adapter_results, preserving first-encounter order)`.
+- `models = result.adapters` (already a tuple).
+- `cells = tuple((task_id, adapter, t.pass_rate) for adapter, ad_result in result.per_adapter_results.items() for t in ad_result.per_task_results)`.
+
+`TYPE_CHECKING` import for `DiscoverabilityComparisonResult` (mirrors existing `DiscoverabilityResult` import pattern).
+
+### AC-13.3.4 — `_advanced_available` gate per D-6 + L-2 lesson
+
+`MCPLibrary.compute_tool_discoverability_comparison` (or whatever the Python method name resolves to per the verb-allowlist) probes the gate AT INVOCATION (NOT at module import — `MCPLibrary` must remain importable without `[agenteval-advanced]`):
+
+```python
+# Inside the keyword method body, FIRST after arg validation:
+from AgentEval.stats.library import _ADVANCED_AVAILABLE, _raise_advanced_extra_missing
+if not _ADVANCED_AVAILABLE:
+    _raise_advanced_extra_missing("Compare Tool Discoverability")
+```
+
+Note: re-uses Story 13.1's `_raise_advanced_extra_missing(keyword_name)` helper but with a different keyword name. **In-flight amendment:** the helper currently formats `f"Stat.{keyword_name}: ..."`. For `MCP.Compare Tool Discoverability` the leading `Stat.` is wrong. Either: (a) generalize the helper to accept a prefix arg; (b) raise the ImportError directly at the MCPLibrary call site with the verbatim spec message. **Decision (b)** — direct raise at the call site:
+```python
+raise ImportError(
+    "MCP.Compare Tool Discoverability: scipy + numpy required. "
+    "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
+)
+```
+The helper stays Stats-prefix-specific; MCP raises directly. Symmetric maintenance.
+
+### AC-13.3.5 — Method-name rename per verb-allowlist
+
+Per Story 13.1 in-flight amendment #1: the Python method name's first token must be in `_VERB_ALLOWLIST`. `compare_tool_discoverability` → first token `compare` is NOT in allowlist (`get` / `set` / `run` / `send` / `assert` / `check` / `validate` / `compute` / `list` / etc. per `tests/unit/conventions/test_keyword_name_idiom.py`).
+
+**Decision:** name the Python method `get_tool_discoverability_comparison` — first token `get` (in allowlist) + describes the operation correctly (operator gets back a comparison result). RF keyword name `MCP.Compare Tool Discoverability` is preserved per epic L2186 verbatim via `@keyword(name="MCP.Compare Tool Discoverability")` (the RF name + Python name diverge intentionally, per Story 13.1's `compute_mann_whitney_u` / `Stat.Mann Whitney U` precedent).
+
+### AC-13.3.6 — Internal helper extraction at `src/AgentEval/discoverability/_internal.py` (NEW or extend existing)
+
+Extract the per-adapter discoverability logic from `MCPLibrary.get_tool_discoverability` into a shared helper that BOTH `get_tool_discoverability` AND `get_tool_discoverability_comparison` call:
+
+```python
+def _run_single_adapter_discoverability(
+    *,
+    mcp_server: str,
+    adapter: str,
+    model: str | None,
+    task_list: list[DiscoverabilityTask],  # pre-loaded; YAML parsed once
+    trials_per_task: int,
+    max_cost_usd: float,
+    max_runtime_seconds: float | None,
+    extra_adapter_kwargs: dict[str, Any],
+    t_start: float,  # caller-provided so the runtime metric covers the whole compare
+) -> DiscoverabilityResult: ...
+```
+
+Mirrors the existing `MCPLibrary.get_tool_discoverability` body but factored for shared use. Existing `get_tool_discoverability` is refactored to call the helper after its own arg validation + YAML load. **No behavior change** for single-adapter callers (verify via the existing 50+ Story 4.4 tests passing unchanged).
+
+Place at `src/AgentEval/discoverability/_internal.py` (NEW file) — mirrors Story 6.3's `stats/_internal.py` pure-helper precedent + architecture's `_internal.py` canonical helper module name.
+
+### AC-13.3.7 — Unit tests at `tests/unit/discoverability/test_comparison.py` (≥15 tests)
+
+NEW file. Coverage:
+
+- **Dataclass validators (6 tests)**: `DiscoverabilityComparisonResult` with `len(adapters) < 2` → ValueError; adapters/per_adapter_results key mismatch → ValueError; adapters/heatmap.models mismatch → ValueError; `PairwiseAdapterDelta` with `adapter_a == adapter_b` → ValueError; `pass_rate_delta` out of [-1, 1] → ValueError; `significant_at_alpha_05` vs p_value consistency mismatch → ValueError.
+- **`CohortHeatmap.from_comparison` (4 tests)**: 2-adapter happy path; 3-adapter (≥3 columns) happy path; per-task-pass-rate dispatched to correct cell; `as_ascii()` produces ≥3 columns when 3 adapters provided.
+- **Pairwise delta computation (3 tests)**: 2 adapters → 1 pairwise delta (key `"<a1>_vs_<a2>"`); 3 adapters → 3 pairwise deltas; pairwise key ordering deterministic.
+- **`compute_mann_whitney_u` dispatch (2 tests)**: 2 adapters with known-different pass-rate distributions → `p_value < 0.05`; 2 adapters with identical distributions → `p_value > 0.5`.
+
+Gated by `pytest.importorskip("opentelemetry")` for the MCPLibrary infrastructure dependency (Story 4.4 precedent) + `pytest.importorskip("scipy")` for the Mann-Whitney U math (Story 13.1 precedent).
+
+Plus 3 ImportError-gate tests at NEW `tests/unit/discoverability/test_comparison_extras_gate.py` (per L-2 lesson; NO `importorskip` at module top):
+- `test_compare_keyword_raises_import_error_when_advanced_extra_missing` — monkeypatch `_ADVANCED_AVAILABLE = False`, assert the spec-mandated ImportError with `"MCP.Compare Tool Discoverability"` + `"agenteval-advanced"` substring.
+- `test_compare_module_importable_without_extra` — `from AgentEval.discoverability.schema import DiscoverabilityComparisonResult` works without scipy/numpy.
+- `test_compare_message_contract` — message contains the verbatim install hint.
+
+### AC-13.3.8 — Integration test with 3 stub adapters at `tests/integration/discoverability/test_compare_e2e.py` (NEW)
+
+Per epic L2189 + L-4 lesson: ship 3 stub adapters via `register_adapter()` (mirrors Story 12.3 + Story 7.3 pattern) returning KNOWN-different per-task pass-rate distributions. Assert CONCRETE numerical outcomes:
+
+```python
+# Stub returns: stub_a → 1.0 success on all tasks; stub_b → 0.5 success; stub_c → 0.0 success.
+result = lib.get_tool_discoverability_comparison(
+    mcp_server="echo",
+    adapters=["compare_stub_a", "compare_stub_b", "compare_stub_c"],
+    tasks=str(TASKS_YAML),
+    trials_per_task=10,  # enough for Mann-Whitney to have power
+    model="stub",
+)
+
+# Per-adapter pass rates.
+assert result.per_adapter_results["compare_stub_a"].summary.overall_pass_rate == pytest.approx(1.0)
+assert result.per_adapter_results["compare_stub_b"].summary.overall_pass_rate == pytest.approx(0.5)
+assert result.per_adapter_results["compare_stub_c"].summary.overall_pass_rate == pytest.approx(0.0)
+
+# Ranking (summary.best_adapter / worst_adapter).
+assert result.summary.best_adapter == "compare_stub_a"
+assert result.summary.worst_adapter == "compare_stub_c"
+
+# Pairwise significance.
+ac_delta = result.cross_adapter_deltas["compare_stub_a_vs_compare_stub_c"]
+assert ac_delta.significant_at_alpha_05  # stub_a (all-pass) vs stub_c (all-fail) is significant.
+
+# Heatmap shape: 3 columns, M rows (M = task count).
+assert result.heatmap.models == ("compare_stub_a", "compare_stub_b", "compare_stub_c")
+assert len(result.heatmap.tasks) == len(YAML_TASKS)
+```
+
+### AC-13.3.9 — `MCP.Get Tool Discoverability` refactor (extract helper)
+
+Per AC-13.3.6 the existing `get_tool_discoverability` is refactored to call `_run_single_adapter_discoverability`. ALL Story 4.4's existing tests (50+ unit + 8 integration per `tests/unit/discoverability/` + `tests/integration/discoverability/`) MUST pass unchanged — proves the refactor is behavior-preserving. Test count delta = +18 new (per AC-13.3.7 + AC-13.3.8), no test renames or removals.
+
+### AC-13.3.10 — `docs/contracts/stability-surface.md` registry per L-1 lesson
+
+NEW subsection `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)`:
+
+- `MCP.Compare Tool Discoverability` RF keyword + Python method `MCPLibrary.get_tool_discoverability_comparison` — `provisional` label. Signature stable (mirrors `Get Tool Discoverability` with `adapters: list[str]` replacing `adapter: str`); the `@guarded_fanout` carve-out (DF-13.3-S1) applies identically to DF-4.4-S1.
+- `AgentEval.discoverability.schema.DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` frozen dataclasses — `provisional` label. Field set may extend in Phase-2.5 (multi-pairwise correction per DF-13.3-S3).
+- `CohortHeatmap.from_comparison` classmethod — `provisional` label. Mirrors `from_discoverability` discipline.
+- `[agenteval-advanced]` extra requirement bubble-up — the `MCP.Compare Tool Discoverability` keyword inherits the same ImportError contract as the Story 13.1 `Stat.Mann Whitney U` keyword. ImportError message format is `stable`.
+
+### AC-13.3.11 — Phase-1.5 carry-over catalog UPSTREAM (34th consecutive)
+
+`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
+- **C89** `DF-13.3-S1` — Phase-2.5: `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` (same MCPLibrary architectural gap as C20).
+- **C90** `DF-13.3-S2` — Phase-2.5: Real per-adapter MCP-server attachment (gated on C72 + C68/C69/C73/C75).
+- **C91** `DF-13.3-S3` — Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance.
+
+### AC-13.3.12 — PRD amendment per D-1 (same-commit, fix-the-losing-source-NOW)
+
+`_bmad-output/planning-artifacts/prd.md` L1500 amended:
+- **Old:** "Agent Surface Author can compare `ToolDiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>`..."
+- **New:** "Agent Surface Author can compare `DiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...]` (≥2 required; N=3+ enables ranking across Claude/GPT/Copilot/...) and receive a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-runtime delta with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data — Phase 2 (Story 13.3; depends on ≥2 fully-shipped Tier-1 runtimes; backwards-compat with the original A/B semantic via a 2-element list)."
+
+Also amend "`ToolDiscoverabilityResult`" typo → "`DiscoverabilityResult`" (the existing FR10a-shipped type; not "Tool" prefix).
+
+### AC-13.3.13 — All-gates pass
+
+- `uv run pytest tests/`: ≥18 new tests + all existing 1846 + 16 pre-existing tests still pass. Net ≥18 added.
+- `uv run ruff check src/ tests/` clean.
+- `uv run ruff format --check src/AgentEval/mcp/ src/AgentEval/discoverability/ src/AgentEval/_heatmap/ tests/unit/discoverability/ tests/integration/discoverability/` clean for Story-13.3 files.
+- `uv run mypy src/` clean (≥106 src files).
+- libdoc regeneration (per Story 13.2 Codex LOW-1 lesson): `uv run python -m robot.libdoc src/AgentEval docs/keywords/AgentEval.html` produces an updated artifact with the new `MCP.Compare Tool Discoverability` keyword.
+
+### AC-13.3.14 — Sprint-status
+
+`13-3-compare-tool-discoverability-cross-adapter: done` (after review); `last_updated: 2026-06-01`.
+
+## Tasks / Subtasks
+
+- [x] **Task 1: PRD amendment (D-1 + AC-13.3.12)** — `_bmad-output/planning-artifacts/prd.md` L1500 amended per the N-runtime `adapters=[...]` wording + `DiscoverabilityResult` typo fix.
+- [x] **Task 2: `src/AgentEval/discoverability/schema.py` extension (AC-13.3.2)** — `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` appended with `__post_init__` validators; nan-tolerant `significant_at_alpha_05` consistency check (per scipy identical-samples convention).
+- [x] **Task 3: `src/AgentEval/_heatmap/models.py` extension (AC-13.3.3)** — `CohortHeatmap.from_comparison` classmethod added with `TYPE_CHECKING` import.
+- [x] **Task 4: `src/AgentEval/discoverability/_internal.py` (AC-13.3.6, NEW)** — `run_single_adapter_discoverability` helper extracted from existing Story 4.4 body; behavior identity verified by Story 4.4's 50+ existing tests passing unchanged.
+- [x] **Task 5: `src/AgentEval/mcp/library.py` extension (AC-13.3.1 + AC-13.3.4 + AC-13.3.5)** — `get_tool_discoverability_comparison` method (Python name `get_*` per verb-allowlist; RF name `MCP.Compare Tool Discoverability` per epic); `_ADVANCED_AVAILABLE` gate via `_stats_lib._ADVANCED_AVAILABLE` module-attr read (NOT `from X import Y` which captures stale value across session-wide monkeypatch); existing `get_tool_discoverability` refactored to delegate to the helper.
+- [x] **Task 6: `tests/unit/discoverability/test_comparison.py` (AC-13.3.7)** — 16 unit tests covering dataclass validators (7) + heatmap multi-column (4) + pairwise counting (3) + Mann-Whitney significance dispatch (2).
+- [x] **Task 7: `tests/unit/discoverability/test_comparison_extras_gate.py` (AC-13.3.7 + L-2)** — 4 ImportError-gate tests, NO module-top `importorskip`; covers schema importability + helper message + keyword raise + arg-validation-precedence.
+- [x] **Task 8: `tests/integration/discoverability/test_compare_e2e.py` (AC-13.3.8)** — 3 stub adapters (100% / 50% / 0% pass rates) + CONCRETE numerical assertions per L-4 (ranking + p < 0.05 for a-vs-c + heatmap shape + cost math); + 2 arg-validation tests.
+- [x] **Task 9: `docs/contracts/stability-surface.md` (AC-13.3.10)** — `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)` subsection with 5 entries.
+- [x] **Task 10: Phase-1.5 carry-over catalog UPSTREAM (34th consecutive)** (AC-13.3.11) — C89 (DF-13.3-S1 @guarded_fanout) + C90 (DF-13.3-S2 per-adapter MCP) + C91 (DF-13.3-S3 Bonferroni correction) added to both `phase-1-5-carry-overs.md` (88 → 91) + `deferred-work.md`.
+- [x] **Task 11: All-gates pass** (AC-13.3.13) — `uv run pytest tests/` reports **1874 passed + 16 skipped + 0 failed** (+28 net vs 1846 + 16 Story 13.2 baseline). 22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration; the +28 includes a couple of side-fix tests). ruff/format/mypy/license clean. libdoc `docs/keywords/MCPLibrary.html` regenerated with `MCP.Compare Tool Discoverability` keyword.
+- [x] **Task 12: Sprint-status flip** (AC-13.3.14) — `13-3-compare-tool-discoverability-cross-adapter: review`; `last_updated: 2026-06-01`.
+
+## Dev Notes
+
+Building on multiple Phase-1 + Phase-2 foundations:
+- **Story 4.4** shipped `MCP.Get Tool Discoverability` + `DiscoverabilityResult` + `TaskResult` + `DiscoverabilitySummary` + 50+ unit tests + 8 integration tests + the loader/schema infrastructure. Story 13.3 builds the N-adapter wrapper.
+- **Story 13.1** shipped `Stat.Mann Whitney U` keyword + `MannWhitneyResult` dataclass + the `compute_mann_whitney_u` pure helper at `stats/mannwhitney.py` + the `[agenteval-advanced]` extra. Story 13.3 consumes the pure helper directly (NOT the keyword surface — different input shape per D-5).
+- **Story 8b.2** shipped `CohortHeatmap` dataclass + `from_discoverability` single-model classmethod + `as_ascii()` / `as_dict()` renderers. Story 13.3 adds the multi-column `from_comparison` classmethod.
+- **Story 7.3** + **Story 12.3** established the `register_adapter` stub pattern for integration tests with multiple per-test adapters. Story 13.3 ships 3 stubs (1 more than Story 12.3's coherent-pass/coherent-fail design) to validate ranking across N≥3.
+
+**Key implementation detail — pure helper dispatch (D-5).** `Stat.Mann Whitney U` is the user-facing keyword; it takes `list[KeywordRun]` + a predicate to extract floats. Story 13.3's per-adapter pass-rate input is ALREADY `list[float]` (one per task per adapter). The pure helper `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` at `stats/mannwhitney.py` is the correct dispatch target — bypasses the predicate machinery. Document this in the keyword docstring so future maintainers don't try to refactor to "consistently call the keyword surface."
+
+**Key implementation detail — helper extraction (AC-13.3.6).** The existing `MCPLibrary.get_tool_discoverability` body is ~150 LoC with significant complexity (adapter resolution + per-trial dispatch + cost/runtime tracking + DiscoverabilityResult assembly). Extracting `_run_single_adapter_discoverability` to a shared helper:
+- Avoids ~150 LoC duplication.
+- Provides a clean per-adapter unit-test surface.
+- Preserves the existing 50+ Story 4.4 tests unchanged (they call the keyword surface, which delegates to the helper).
+- Failure mode: subtle behavior change. **Mitigation:** the existing Story 4.4 tests MUST pass unchanged (verified at AC-13.3.13). If they don't, the refactor introduced a regression and must be fixed BEFORE adding the Compare surface.
+
+**Cross-story lesson application:**
+- L-1: stability-surface MUST register the new surface UPSTREAM (verified at AC-13.3.10).
+- L-2: extras-gate tests split per Story 13.1 / 13.2 pattern.
+- L-3: `@tier(3)` rationale documented (stochastic by tier definition).
+- L-4: integration test asserts CONCRETE numerical correctness — known stub pass-rate distributions produce expected ranking + p-value sign.
+- L-5: docstring names exact helper path; Browser-Library anchor test.
+
+### Project Structure Notes
+
+- **NO new sub-library directory.** `MCP.Compare Tool Discoverability` ships on the existing `MCPLibrary` per architecture's MCP carve-out.
+- **NEW file:** `src/AgentEval/discoverability/_internal.py` (shared helper).
+- **NEW test files:** `tests/unit/discoverability/test_comparison.py` + `tests/unit/discoverability/test_comparison_extras_gate.py` + `tests/integration/discoverability/test_compare_e2e.py`.
+- **EXTENDED files:** `src/AgentEval/mcp/library.py` (new keyword + helper-call refactor); `src/AgentEval/discoverability/schema.py` (3 new dataclasses); `src/AgentEval/_heatmap/models.py` (new classmethod); `docs/contracts/stability-surface.md` (new subsection); `docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` (carry-overs); `_bmad-output/planning-artifacts/prd.md` (FR10b amendment per D-1); `docs/keywords/AgentEval.html` (libdoc regen).
+
+### References
+
+- PRD: `_bmad-output/planning-artifacts/prd.md` L1499 (FR10a — base discoverability shape); L1500 (FR10b — to be amended per D-1 + AC-13.3.12).
+- Architecture: `_bmad-output/planning-artifacts/architecture.md` L737 (FR10b → "Phase 2 cross-adapter comparison"); L1300 (`CohortHeatmap` file home at `metrics/types.py` — but actual shipping location is `_heatmap/models.py` per Story 8b.2 — `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
+- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2177-2189 (Story 13.3 detailed).
+- Prior stories: `_bmad-output/implementation-artifacts/4-4-mvp-tool-discoverability-fr10a-single-runtime-discoverability-check.md` (single-adapter foundation); `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md` (`Stat.Mann Whitney U` + pure helper + `[agenteval-advanced]` extra); `13-2-otlp-trace-backend.md` (immediately-prior cross-story upstream lessons).
+- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry); `src/AgentEval/discoverability/schema.py` (existing `DiscoverabilityResult` + `TaskResult`); `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` shape).
+- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (53rd use); `feedback_carry_over_catalog_gate.md` UPSTREAM (34th); `feedback_cross_story_upstream_lesson_propagation.md` (Story 13.2 → 13.3 same-epic transition); `feedback_listener_hook_api_surface_empirical_check.md` (L-4 empirical numerical verification); `feedback_in_flight_spec_amendment.md` (D-1 PRD amendment in same commit + AC-13.3.5 method-name divergence).
+
+## Dev Agent Record
+
+### Agent Model Used
+
+claude-opus-4-7[1m]
+
+### Debug Log References
+
+3 mid-dev catches:
+1. **`MannWhitneyResult` nan-p-value**: scipy returns `p_value=nan` when both samples have identical rank distributions (no variance → no test possible). Story 13.1's `MannWhitneyResult.__post_init__` rejected nan; relaxed to accept `nan` or `[0, 1]`. Documented as the scipy convention.
+2. **`PairwiseAdapterDelta.significant_at_alpha_05` validator**: `nan < 0.05` evaluates `False` in Python, so the bool field naturally becomes False — but the validator required explicit consistency check. Updated to `(not isnan(p)) and p < 0.05`.
+3. **`_ADVANCED_AVAILABLE` read pattern**: function-local `from AgentEval.stats.library import _ADVANCED_AVAILABLE` captured stale value across pytest session-wide module reload. Fixed by reading via `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` (always reads current module attribute).
+
+### Completion Notes List
+
+Story 13.3 dev complete. Phase-2 cross-adapter Tool Discoverability comparison (FR10b) shipped.
+
+- **AC-13.3.1**: `MCP.Compare Tool Discoverability` ships on `MCPLibrary` (file home preserved per architecture L1258; NO new sub-library). Validates ≥2 distinct adapters; ImportError gate at first body line (fail-fast).
+- **AC-13.3.2**: 3 new frozen dataclasses with `__post_init__` validators. Cross-consistency invariants checked: `adapters ↔ per_adapter_results.keys()` and `adapters ↔ heatmap.models`.
+- **AC-13.3.3**: `CohortHeatmap.from_comparison` builds multi-column heatmap from comparison; supports the multi-column ASCII rendering.
+- **AC-13.3.4**: `_ADVANCED_AVAILABLE` gate at module-attr read (not `from X import Y` to handle session-wide reload). Direct ImportError raise with `MCP.Compare Tool Discoverability:` prefix (per spec decision (b)).
+- **AC-13.3.5**: Python method `get_tool_discoverability_comparison` (verb-allowlist conformant) + RF name `MCP.Compare Tool Discoverability` preserved.
+- **AC-13.3.6**: `run_single_adapter_discoverability` helper extracted to `_internal.py`; existing `get_tool_discoverability` delegates to it. Story 4.4's 50+ existing tests pass unchanged.
+- **AC-13.3.7**: 16 unit tests (test_comparison.py) + 4 ImportError-gate tests (test_comparison_extras_gate.py, NO module-top importorskip per L-2 lesson).
+- **AC-13.3.8**: 3 integration tests at `test_compare_e2e.py`: end-to-end happy path + 2 arg-validation tests. Concrete numerical assertions per L-4 (pass-rate ranking, p_value sign, heatmap shape, cost math).
+- **AC-13.3.9**: refactor verified — Story 4.4's existing tests pass unchanged.
+- **AC-13.3.10**: stability-surface registry NEW `### Cross-Adapter Discoverability Surface` subsection with 5 entries.
+- **AC-13.3.11**: C89 + C90 + C91 catalogued UPSTREAM (34th consecutive).
+- **AC-13.3.12**: PRD L1500 amended per D-1 (N-runtime `adapters=[...]` shape + `DiscoverabilityResult` typo fix).
+- **AC-13.3.13**: All gates pass — 1874+16 final, ruff/format/mypy/license clean, libdoc regen.
+- **AC-13.3.14**: sprint-status flipped to `review`.
+
+### Cross-story upstream lesson application (Stories 13.1 + 13.2 reviews → Story 13.3)
+
+- **L-1 applied (stability-surface UPSTREAM)**: registered all 5 Story 13.3 surface entries before flipping to review; verified via grep.
+- **L-2 applied (extras-gate test split)**: `test_comparison.py` (importorskip) + `test_comparison_extras_gate.py` (NO importorskip) split per canonical pattern.
+- **L-3 applied (@tier classification rationale)**: `@tier(3)` documented in keyword docstring as stochastic-by-tier (no FR31a bit-identical guarantee); Story 13.1 HIGH-C seed-required concern moot.
+- **L-4 applied (empirical numerical verification)**: integration test asserts CONCRETE outcomes (best=stub_a, worst=stub_c, p<0.05 for max-effect pair, heatmap.models exactly the 3 names).
+- **L-5 applied (docstring precision)**: keyword docstring names exact helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u` + explains the predicate-bypass rationale (input is `list[float]` not `list[KeywordRun]`).
+
+### In-flight spec amendments
+
+1. **AC-13.3.1 `@guarded_fanout` removed**: spec D-7 said `@tier(3) + @guarded_fanout()`. Existing `MCP.Get Tool Discoverability` only has `@tier(3)` because MCPLibrary's host-instance plumbing doesn't carry `_max_cost_usd` (DF-4.4-S1 / C20 carve-out). Adding `@guarded_fanout()` would crash on `self._max_cost_usd` access. Amended in-flight: only `@tier(3)`, document the carve-out in docstring (C89 / DF-13.3-S1 tracks the cross-library fix shared with C20).
+
+2. **AC-13.3.4 module-attr gate read**: spec said `from AgentEval.stats.library import _ADVANCED_AVAILABLE`. Empirically the function-local import captured a stale value across pytest session-wide reload (Story 13.1's `test_advanced_extras_gate.py` reloaded `stats.library` earlier in the session). Amended to `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` for always-fresh attribute read.
+
+3. **AC-13.3.2 `PairwiseAdapterDelta.significant_at_alpha_05` nan-tolerance**: spec required `significant_at_alpha_05 == (p_value < 0.05)` strict equality. scipy returns `p_value=nan` for identical-rank samples. Amended to `(not isnan(p)) and p < 0.05` — equivalent semantics (nan is not-significant).
+
+4. **`MannWhitneyResult.p_value` nan-tolerance** (Story 13.1 side-fix): Story 13.1's validator rejected nan. Relaxed to `isnan(p) or 0.0 <= p <= 1.0` per scipy identical-samples convention. Backwards-compat: real p_values still validated.
+
+### File List
+
+**New files:**
+- `src/AgentEval/discoverability/_internal.py` — `run_single_adapter_discoverability` helper.
+- `tests/unit/discoverability/test_comparison.py` — 16 unit tests.
+- `tests/unit/discoverability/test_comparison_extras_gate.py` — 4 ImportError-gate tests (run in both base + WITH-extras).
+- `tests/integration/discoverability/__init__.py` — package marker.
+- `tests/integration/discoverability/test_compare_e2e.py` — 3 integration tests.
+
+**Modified files:**
+- `src/AgentEval/discoverability/schema.py` — 3 new frozen dataclasses (`DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary`) + `TYPE_CHECKING` imports + `__all__` updates.
+- `src/AgentEval/_heatmap/models.py` — `CohortHeatmap.from_comparison` classmethod + extended `TYPE_CHECKING` imports.
+- `src/AgentEval/mcp/library.py` — `get_tool_discoverability_comparison` method + extras gate + existing `get_tool_discoverability` refactored to delegate.
+- `src/AgentEval/stats/types.py` — `MannWhitneyResult.__post_init__` p_value validator relaxed for nan (Story 13.1 side-fix; doc'd as scipy convention).
+- `_bmad-output/planning-artifacts/prd.md` — L1500 FR10b amended per D-1 (N-runtime shape + `DiscoverabilityResult` typo fix).
+- `docs/contracts/stability-surface.md` — `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)` subsection.
+- `docs/phase-1-5-carry-overs.md` — C89 + C90 + C91 entries + total 88 → 91.
+- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.3 dev" section with 3 entries.
+- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-3-compare-tool-discoverability-cross-adapter: review`; `last_updated: 2026-06-01`.
+- `docs/keywords/MCPLibrary.html` — libdoc regenerated with `MCP.Compare Tool Discoverability` keyword.
+- `docs/keywords/AgentEval.html` — libdoc regenerated (no top-level kwarg change but timestamp updated for consistency).
diff --git a/_bmad-output/implementation-artifacts/deferred-work.md b/_bmad-output/implementation-artifacts/deferred-work.md
index ca2c862..2f6c828 100644
--- a/_bmad-output/implementation-artifacts/deferred-work.md
+++ b/_bmad-output/implementation-artifacts/deferred-work.md
@@ -382,6 +382,14 @@ Added by Story 4.3 (Orchestration Keywords — Epic 4 Story 3). Pre-create-story
 
 - **DF-13.2-S3 (Phase-2.5 OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage)** — Story 13.2 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.2 ships `BatchSpanProcessor(OTLPSpanExporter)` with OpenTelemetry SDK built-in retry but NO circuit-breaker for sustained outages — if the collector is unreachable for N consecutive batches, the BatchSpanProcessor queue fills + drops spans silently. Phase-2.5 work: ship an `OTLPCircuitBreakerProcessor` wrapping `BatchSpanProcessor` that falls back to JSONL-on-disk persistence after `failure_threshold` consecutive batch failures + auto-resumes when the collector becomes reachable. Catalogued as C88. Effort: M. Phase-2.5.
 
+## Deferred from: story-13.3 dev (2026-06-01) — UPSTREAM pre-emptive per Epic 11 retro
+
+- **DF-13.3-S1 (Phase-2.5 `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability`)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships the cross-adapter compare keyword WITHOUT `@guarded_fanout` decorator — same MCPLibrary architectural gap as DF-4.4-S1 / C20. Cross-adapter fan-out compounds cost N× (N adapters × M tasks × trials), making this carve-out MORE expensive than the single-adapter case. Catalogued as C89. Effort: M. Shared resolution with C20. Phase-2.5.
+
+- **DF-13.3-S2 (Phase-2.5 real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability`)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Same `mcp_server` accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1); for Phase-2 SDK + CLI adapters gated on C72 + C68/C69/C73/C75 per-adapter HostedMcpObserver wiring. Catalogued as C90. Effort: M. Phase-2.5.
+
+- **DF-13.3-S3 (Phase-2.5 multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance)** — Story 13.3 D-10 path-of-least-amendment decision 2026-06-01 (UPSTREAM pre-emptive catalog enforcement per Epic 11 retro sub-pattern). Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction; for N=3 adapters there are C(3,2)=3 pairs and uncorrected α=0.05 inflates the family-wise error rate. Phase-2.5: add `correction_method: Literal["none", "bonferroni", "holm"]` kwarg + `summary.bonferroni_adjusted_alpha` + `delta.significant_at_corrected_alpha` fields. Catalogued as C91. Effort: S. Phase-2.5.
+
 ---
 
 *Update this file as new deferred items emerge from future reviews.*
diff --git a/_bmad-output/implementation-artifacts/sprint-status.yaml b/_bmad-output/implementation-artifacts/sprint-status.yaml
index 41cbde1..2540487 100644
--- a/_bmad-output/implementation-artifacts/sprint-status.yaml
+++ b/_bmad-output/implementation-artifacts/sprint-status.yaml
@@ -153,7 +153,7 @@ development_status:
   epic-13: in-progress  # Story 13.1 ready-for-dev 2026-06-01; first Epic 13 story (Advanced Stats Phase-2 surface).
   13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches (6 HIGH + 4 MED). 3-way HIGH on stability-surface drift + u_statistic-vs-scipy docstring lie; 2-way HIGH on missing scipy.bootstrap reference test. Codex empirical probes caught: WITHOUT-extras gate tests fake-green via importorskip + Bootstrap CI silent mixed-type filter + mandatory-seed FR31a violation. 1826 passed + 14 skipped final.
   13-2-otlp-trace-backend: done  # 2026-06-01 3-tier cross-LLM review applied v2 patches. 3-way HIGH: service.name=unknown_service (Resource.create({}) latent Story 5.1 bug surfaced by OTLP feature; fixed to "robotframework-agenteval"). Codex empirical HIGH-1+2: OTLP processor persists after backend switch + endpoint changes ignored (NFR-SEC-05 fix: per-endpoint sentinel + processor detach via SDK private API). 2-way MED: insecure= kwarg verified via mock interception. libdoc regenerated. 1846 passed + 16 skipped final.
-  13-3-compare-tool-discoverability-cross-adapter: backlog
+  13-3-compare-tool-discoverability-cross-adapter: review
   13-4-cohort-heatmap-html-rendering: backlog
   13-5-compare-skill-discoverability-cross-adapter-fr4c: backlog
   epic-13-retrospective: optional
diff --git a/_bmad-output/planning-artifacts/prd.md b/_bmad-output/planning-artifacts/prd.md
index 48a9e94..81c4003 100644
--- a/_bmad-output/planning-artifacts/prd.md
+++ b/_bmad-output/planning-artifacts/prd.md
@@ -1497,7 +1497,7 @@ Each FR states the testable, observable capability the library must provide. For
 - **FR9a:** Agent Surface Author can call `MCP.List Tools <handle>` and receive an ordered list of `MCPTool` records (`name`, `description`, `input_schema`, `output_schema`). The field-projection convenience keywords `Get Tool Names` / `Get Tool Descriptions` are deferred to Phase-1.5 (Story 3.2 code-review Auditor HIGH 2026-05-19: PRD originally named both projection keywords inline with FR9a; Story 3.2 implements only `MCP.List Tools` because AssertionEngine + native Python list-comprehension + `${tools[*].name}` index access cover the documented use case without a dedicated keyword. Phase-1.5 may re-introduce as convenience keywords if .robot-test ergonomics warrant — tracked in `deferred-work.md`).
 - **FR9b:** Agent Surface Author can call `MCP.Call Tool <handle> <tool_name> <args_dict>` and receive an `MCPToolResult` (`content` list of MCP content blocks per spec, `is_error` mirroring the SDK's `CallToolResult.isError`, `error_message` extracted from the first text-content block when `is_error=True`, `latency_ms` wall-clock for the SDK round-trip, `correlation_id` per-call uuid4 hex Phase-1 placeholder for Epic 5 trace-id wiring); same call supports AssertionEngine matchers (`Should Contain`, `matches`, `Should Match Schema`) against `content`. (Story 3.2 code-review Auditor HIGH 2026-05-19: amended from pre-edit `(result, error, latency_ms)` shape to match the 5-field implementation that ships in `src/AgentEval/mcp/lifecycle.py:MCPToolResult` — same pattern as Story 3.1's FR8 prefix amendment. Pre-edit shape was too narrow: `content` is a LIST of typed blocks per MCP spec, not a scalar `result`; tool-level error responses surface as `is_error=True` first-class data per FR9b semantic intent, distinct from infrastructure failure which raises `MCPConnectionLostError`; per-call `correlation_id` ships now so Epic 5 trace wiring doesn't require a breaking API change.)
 - **FR10a:** Agent Surface Author can call `MCP.Get Tool Discoverability mcp_server=<name> adapter=<name> model=<id> tasks=<yaml-path> trials_per_task=<n> max_cost_usd=<usd>` (single-runtime + single-model Phase-1 surface; FR10b lifts the per-model cohort restriction in Phase-2) and receive a `DiscoverabilityResult` containing `per_task_results: list[TaskResult]` (each with `task_id`, `task_prompt`, `trials_run`, `success_count` per Pass@k semantics, `tool_calls_per_trial`, `competing_tools_picked`, `cost_per_trial_usd`, `wilson_ci_lower`, `wilson_ci_upper`), `summary` (overall pass-rate, total-cost, total-runtime), `mcp_coverage` per Story 1b.2 `compute_mcp_coverage`. (Story 4.4 pre-create-story drift D-C 2026-05-20: pre-edit FR10a wording named `tool=<name>` `by_models=<list>` `with_tasks=<list>` `k=<n>` — amended to match the ratified operational shape per epics.md L1403 + Story 4.4 implementation. Phase-1 single-runtime is preserved; the `tool=<name>` focus filter becomes an optional task-level field within the YAML per AC-DISCOVER-01 evidence-block design. Wilson-CI cohort table per AC-DISCOVER-01 is computed per-task across `trials_per_task` trials — single-model variant per Phase-1 carve-out.) [Tier 3, Phase 1; single-runtime version. FR10b lifts the single-runtime restriction in Phase 2.]
-- **FR10b:** Agent Surface Author can compare `ToolDiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>` and receive a cross-runtime delta with statistical significance (Mann-Whitney U) — **Phase 2** (depends on ≥2 fully-shipped Tier-1 runtimes; Phase 1 has only Generic + CC CLI where Generic is a thin LiteLLM stub).
+- **FR10b:** Agent Surface Author can compare `DiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...]` (≥2 required; N=3+ enables ranking across Claude/GPT/Copilot/...) and receive a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-runtime delta with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data — **Phase 2** (Story 13.3; depends on ≥2 fully-shipped Tier-1 runtimes; Phase 1 has only Generic + CC CLI where Generic is a thin LiteLLM stub; backwards-compat with the original A/B semantic via a 2-element list). Story 13.3 D-1 fix-the-losing-source-NOW 2026-06-01: amended from earlier `runtime_a=<adapter> runtime_b=<adapter>` 2-runtime A/B wording to the N-runtime `adapters=[...]` shape per epics.md L2186 ratified spec + the symmetric Story 13.5 Skill version; also corrected stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
 - **FR11:** Library raises `CostExceededError("projected $X.XX > max_cost_usd=$5.00; raise limit or reduce task_list")` pre-flight if the projected cost for a fanned-out keyword exceeds `max_cost_usd` (default 5.00 USD); during execution, the cumulative cost meter hard-stops with `CostExceededError("$X.XX exceeded $Y.YY=1.1× max_cost_usd")` at 1.1× the limit. Verifiable via `Stat.Run N Times 10 max_cost_usd=0.01 ...` against a deterministic mock provider.
 - **FR11b (time guardrail — sibling to FR11):** Library exposes `max_runtime_seconds` keyword argument (default `None` — no time cap; opt-in) on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). When set, library performs a pre-flight wall-clock estimate (`mcp_startup_estimate × n_servers × n_trials + agent_runtime_estimate × n_trials`) and raises `RuntimeBudgetExceededError("projected XXs > max_runtime_seconds=YY; reduce trials, use mcp_per_test=suite, or raise limit")` pre-flight; mid-run wall-clock meter hard-stops at 1.1× declared limit. Orthogonal to FR11: cost guard catches token spend; time guard catches latency under heavy MCP servers (e.g., `rf-mcp` / `robotmcp` take several seconds to start; multiplied across trials this can silently blow runtime budgets). Verifiable via `Stat.Run N Times 20 max_runtime_seconds=5 ...` against a deterministic slow-mock provider.
 
diff --git a/docs/contracts/stability-surface.md b/docs/contracts/stability-surface.md
index 6f212a8..051e962 100644
--- a/docs/contracts/stability-surface.md
+++ b/docs/contracts/stability-surface.md
@@ -122,6 +122,17 @@ Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-spli
 - `AgentEval.coding_agent.copilot_cli.CopilotCLIAdapter` (Story 11.2) — `experimental` label. Phase-2 SubprocessAdapter wrapping the GitHub Copilot CLI binary (pin range `>=1.0.9,<2.0`; local probe `GitHub Copilot CLI 1.0.54.`). Architecture wrinkle: `run()` is overridden because copilot writes events to `~/.copilot/session-state/{uuid}/events.jsonl` (NOT stdout) — adapter reads them post-hoc after `proc.wait()`. Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's events.jsonl schema may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `assistant.message.outputTokens` (summed); `input_tokens=0` placeholder pending events.jsonl exposing the field (DF-11.2-S2 carry-over). `reasoning_output_tokens` populated if `assistant.message.reasoningTokens` is present (Story 11.1 kilo HIGH-1 lesson UPSTREAM). `cost_usd=0.0` placeholder per the same carry-over. `mcp_coverage` detection mirrors Stories 10.1/10.2/11.1 post-HIGH-2 contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.2-S1 / C75 HostedMcpObserver wiring). **Thread safety: NOT concurrent-safe** — `_last_mcp_servers` stash + the session-state-dir-race invariant (concurrent runs against the same `~/.copilot/session-state/` parent race for "newest dir" pick; tracked DF-11.2-S3 / C77). Construct one adapter per concurrent run. **Phase-1 placeholders documented inline:** `trace_id=""` (Story 5.3 / Epic 5 wires real UUID — same pattern as `codex_cli.py`), `cost_usd=0.0` + `input_tokens=0` (DF-11.2-S2 / C76). Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 - `AgentEval.coding_agent.codex_cli.CodexCLIAdapter` (Story 11.1) — `experimental` label. Phase-2 SubprocessAdapter wrapping the OpenAI `codex` CLI binary (pin range `>=0.100.0,<1.0`; local probe `codex-cli 0.133.0`). Constructor signature (`model`, `**kwargs`) is `experimental`; pre-1.0 binary's JSONL event surface may force adapter changes. `run()` honors the FR12 signature contract per the `CodingAgentAdapter` Protocol (`stable`). Reads `usage` from `turn.completed.usage` (full 4-field shape: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` — the `Usage` dataclass was extended with `reasoning_output_tokens` at Story 11.1 kilo HIGH-1 catch 2026-05-26 so no field is silently dropped). `cost_usd` returns `0.0` because Codex events carry no cost field (DF-11.1-S2 / C74 tracks cost-catalog integration). `mcp_coverage` detection mirrors Story 10.1/10.2's patched 2-branch contract per ADR-016 §Decision L33 (non-empty MCP → `external_mixed` until DF-11.1-S1 / C73 HostedMcpObserver wiring lands). **Thread safety: NOT concurrent-safe** — instance-state `_last_mcp_servers` stash pattern means concurrent `run()` calls on one adapter instance corrupt `mcp_coverage`; construct one adapter per concurrent run. Promotion to `stable` after the 3-month-no-break window per Epic 9 retro Action #3 + Exit Criterion #4.
 
+### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)
+
+Per Story 13.3 (PRD FR10b) — Phase-2 cross-adapter Tool Discoverability comparison; depends on Story 13.1's `[agenteval-advanced]` extra (Mann-Whitney U):
+
+- `MCP.Compare Tool Discoverability` RF keyword + Python method `MCPLibrary.get_tool_discoverability_comparison` — `provisional` label. Signature: `mcp_server=<str>, adapters=<list[str]>, tasks=<yaml-path>, trials_per_task=<int>, max_cost_usd=<float>, max_runtime_seconds=<float|None>, model=<str|None>, **kwargs`. ≥2 adapters required. RF keyword name + Python method name diverge intentionally (Story 13.1 `Stat.Mann Whitney U` / `compute_mann_whitney_u` precedent) — the Python name starts with `get` per the verb-allowlist convention test. The `@guarded_fanout` carve-out applies identically to `MCP.Get Tool Discoverability` (DF-4.4-S1 / C20 MCPLibrary architectural gap); DF-13.3-S1 / C89 tracks the cross-library budget-plumbing fix.
+- `AgentEval.discoverability.schema.DiscoverabilityComparisonResult` frozen dataclass — `provisional` label. 5 fields: `adapters: tuple[str, ...]`, `per_adapter_results: Mapping[str, DiscoverabilityResult]`, `cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]`, `heatmap: CohortHeatmap`, `summary: DiscoverabilityComparisonSummary`. `__post_init__` cross-consistency validators (`adapters ↔ per_adapter_results.keys()` + `adapters ↔ heatmap.models`) are `stable`.
+- `AgentEval.discoverability.schema.PairwiseAdapterDelta` frozen dataclass — `provisional` label. 5 fields: `adapter_a: str`, `adapter_b: str`, `pass_rate_delta: float`, `mann_whitney_result: MannWhitneyResult`, `significant_at_alpha_05: bool`. `nan` p_value (scipy identical-samples convention) treated as not-significant.
+- `AgentEval.discoverability.schema.DiscoverabilityComparisonSummary` frozen dataclass — `provisional` label. 5 fields: `total_cost_usd: float` (sum across adapters), `total_runtime_seconds: float` (MAX across adapters — models eventual parallel target), `pass_rate_per_adapter: Mapping[str, float]`, `best_adapter: str`, `worst_adapter: str`.
+- `CohortHeatmap.from_comparison(result: DiscoverabilityComparisonResult)` classmethod — `provisional` label. Multi-column heatmap with one column per adapter + one row per task. Mirrors `from_discoverability` discipline.
+- `[agenteval-advanced]` extra requirement bubble-up — `MCP.Compare Tool Discoverability` raises `ImportError("MCP.Compare Tool Discoverability: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]")` when invoked without the extra. Fail-fast BEFORE any per-adapter fan-out. Message format is `stable`.
+
 ### OTLP Trace Backend Surface (Phase-2 — `[otlp]`)
 
 Per Story 13.2 (PRD FR33b) — Phase-2 OTLP trace exporter gated behind the `[otlp]` optional extra (`opentelemetry-exporter-otlp`):
diff --git a/docs/keywords/AgentEval.html b/docs/keywords/AgentEval.html
index 2001b53..3e68c2f 100644
--- a/docs/keywords/AgentEval.html
+++ b/docs/keywords/AgentEval.html
@@ -6,7 +6,7 @@
 <meta http-equiv=X-UA-Compatible content="IE=edge">
 <meta content="Robot Framework 7.4.2 (Python 3.12.3 on linux)" name="Generator">
 <script type="text/javascript">
-libdoc = {"specversion": 3, "name": "AgentEval", "doc": "<p>Robot Framework library for evaluating AI coding agents.</p>\n<p>Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point + the FR41 precedence chain (kwarg \u2192 env-var \u2192 <span class=\"name\">.env</span> \u2192 defaults) via <span class=\"name\">_kernel.context.resolve_config</span> (Story 1b.1). <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> returns the precedence-resolved values.</p>\n<p>Args: provider: Provider plugin name resolved via <span class=\"name\">agenteval.providers</span> entry-points (FR42; ADR-013). Phase 1 ships only the <span class=\"name\">litellm</span> provider; future providers register via <span class=\"name\">[project.entry-points.\"agenteval.providers\"]</span>. telemetry: Enable the OTel listener for trace recording (FR42 + FR44). When False, <span class=\"name\">Get Trace Backend Names</span> returns <span class=\"name\">[]</span> and no OTLP egress occurs (Phase 2). Phase 1 wires the parameter; full listener-disable enforcement lands in Epic 5 Story 5.1. trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports <span class=\"name\">\"memory\"</span> and <span class=\"name\">\"jsonl\"</span>; <span class=\"name\">\"otlp\"</span> is Phase 2. allow_validate_operator: Enable the AssertionEngine <span class=\"name\">validate</span> operator which uses <span class=\"name\">eval()</span> (FR42 + FR43; NFR-SEC-02). Default False \u2014 the safer posture per NFR-SEC-02. Gate enforcement (raising <span class=\"name\">ValidateOperatorDisallowed</span>) lands in Epic 6. default_temperature: Default provider temperature for non-stochastic keywords (FR42). 0.0 enforces deterministic provider calls where the underlying model supports it. mcp_per_test: MCP server scope.</p>\n<ul>\n<li>True (default): per-test isolation; correct under <span class=\"name\">pabot --processes N</span>. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>False: single shared instance across all tests; only correct serial. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>\"suite\": per-suite scope; recipe-5 dogfood-CI ergonomics override. (Architecture L314 + NFR-PERF-03d \u2014 not in ADR-009 proper.) allow_external_mcp_blind: Opt-in to running with <span class=\"name\">mcp_coverage=\"external_mixed\"</span> without <span class=\"name\">IncompleteTraceError</span> (FR42 + ADR-016 D4 adapter contract). Default False enforces loud-refusal posture from ADR-016. max_cost_usd: Cost budget for <span class=\"name\">@guarded_fanout</span>-decorated Tier-3 keywords (FR42 + ADR-015). USD per fan-out invocation. Default 5.00. max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords (FR11b + ADR-015). Default None = no cap (opt-in via explicit value). Sibling to <span class=\"name\">max_cost_usd</span>; catches slow MCP-server startup compounded across trials. otlp_endpoint: OTLP collector endpoint URL (FR33b; Story 13.2). Only consumed when <code>trace_backend=\"otlp\"</code>. URL scheme selects transport: <code>http://</code> / <code>https://</code> \u2192 OTLP HTTP/protobuf exporter (port 4318); <code>grpc://</code> / <code>grpcs://</code> \u2192 OTLP gRPC exporter (port 4317). Default <code>None</code> \u2192 OTLPBackend falls back to <code>http://localhost:4318/v1/traces</code> (local Jaeger HTTP). Requires the <code>[otlp]</code> extra (<code>opentelemetry-exporter-otlp</code>); constructing OTLPBackend without the extra raises <code>ImportError</code>.</li>\n</ul>\n<p>FR41 precedence behavior (Story 1b.1): Each <span class=\"name\">__init__</span> parameter defaults to a private sentinel; if the caller does NOT pass it, the value falls through to <span class=\"name\">AGENTEVAL_*</span> env-vars, then to a <span class=\"name\">.env</span> file in cwd, then to the FR42 + FR11b defaults documented in this docstring. Callers who want to force a value explicitly (even when an env-var is set) pass that value as a kwarg. <span class=\"name\">.env.example</span> documents the canonical <span class=\"name\">AGENTEVAL_*</span> env-var names.</p>\n<p>References:</p>\n<ul>\n<li>PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)</li>\n<li>PRD FR11b (max_runtime_seconds keyword arg sibling)</li>\n<li>PRD FR41 (config precedence)</li>\n<li>ADR-009 (mcp_per_test 3-mode)</li>\n<li>ADR-013 (entry-points discovery for <span class=\"name\">provider</span>)</li>\n<li>ADR-015 (@guarded_fanout for cost + runtime guardrails)</li>\n<li>ADR-016 (mcp_coverage detection + allow_external_mcp_blind)</li>\n<li>docs/contracts/stability-surface.md (Phase-1 stability labels for this class)</li>\n</ul>", "version": "", "generated": "2026-06-01T10:57:00+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 159, "tags": ["agenteval"], "inits": [{"name": "__init__", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "provider", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "provider: str = _UNSET"}, {"name": "telemetry", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "telemetry: bool = _UNSET"}, {"name": "trace_backend", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "trace_backend: str = _UNSET"}, {"name": "allow_validate_operator", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_validate_operator: bool = _UNSET"}, {"name": "default_temperature", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "default_temperature: float = _UNSET"}, {"name": "mcp_per_test", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'suite'", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "mcp_per_test: bool | Literal['suite'] = _UNSET"}, {"name": "allow_external_mcp_blind", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_external_mcp_blind: bool = _UNSET"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_cost_usd: float = _UNSET"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}, {"name": "otlp_endpoint", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "otlp_endpoint: str | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize self.  See help(type(self)) for accurate signature.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 233}], "keywords": [{"name": "Agent Response Should Contain", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "substring", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "substring: str"}], "returnType": null, "doc": "<p>Asserts that <code>substring</code> appears in <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>substring</code></td>\n<td>Literal substring to match. Case-sensitive.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the substring is not found.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    Robot Framework                                          # Mock echoes the prompt.\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    test automation\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 236}, {"name": "Agent Response Should Match Regex", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "pattern", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "pattern: str"}], "returnType": null, "doc": "<p>Asserts a regex pattern matches <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 uses <code>re.search</code> (substring-match by default per FR25's \"match\" terminology). Multi-line text supported via standard <code>re</code> flags in the pattern. NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>pattern</code></td>\n<td>Python <code>re</code> pattern. Use <code>(?i)</code> / <code>(?m)</code> / <code>(?s)</code> inline flags as needed.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the pattern does not match.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Released in 2020 \u2014 Robot Framework 3.x    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    20\\d{2}                          # 4-digit year \u2014 matches the echoed \"2020\".\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the regex assertion; <span class=\"name\">re.search</span> semantics (not <span class=\"name\">re.fullmatch</span>).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts a regex pattern matches ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 268}, {"name": "Agent Response Should Match Schema", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "schema", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "schema: dict[str, Any] | str | Path"}], "returnType": null, "doc": "<p>Asserts <code>response_text</code> parses as JSON + validates against a JSON Schema (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <code>mcp_coverage<span class=\"name\">`-gated. Parses </span>`response_text</code> as JSON, then validates against the schema via <code>jsonschema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code> (expected to be JSON-parsable).</td>\n</tr>\n<tr>\n<td><code>schema</code></td>\n<td>JSON Schema as a <code>dict</code> OR a file path (<code>str</code> / <code>pathlib.Path</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>schema</code> is not a <code>dict<span class=\"name\">`/</span><span class=\"name\">str</span><span class=\"name\">/</span>`Path</code>, or when the file is not a valid JSON schema dict. Raises <code>AssertionError</code> (redacted per FR38a) when <code>response_text</code> is not JSON-parsable. Raises <code>jsonschema.ValidationError</code> when the parsed JSON does not validate against the schema (preserves the jsonschema convention so consumers can catch the specific exception).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt={\"answer\": 42}    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${{ {\"type\": \"object\", \"required\": [\"answer\"]} }}\n# Path form: <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.</li>\n<li>Uses <code>jsonschema</code> package \u2014 the upstream <code>ValidationError</code> is preserved on validation failure (callers can catch specifically).</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex pattern).</li>\n</ul>", "shortdoc": "Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 301}, {"name": "Get Cohort Heatmap", "args": [{"name": "discoverability_result", "type": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "discoverability_result: DiscoverabilityResult"}, {"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "model_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "default", "kind": "NAMED_ONLY", "required": false, "repr": "model_name: str = default"}], "returnType": {"name": "CohortHeatmap", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds a <code>CohortHeatmap</code> from a <code>DiscoverabilityResult</code> (Story 8b.2 / FR55).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection over the result's <code>per_task_results</code>; no LLM calls. Returns a <code>CohortHeatmap</code> instance with <code>.as_ascii()</code> (box-drawing rendered grid) + <code>.as_dict()</code> (nested <code>{task: {model: pass_at_k}}</code> mapping) methods.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>discoverability_result</code></td>\n<td>Result from <span class=\"name\">MCP.Get Tool Discoverability</span> (Story 4.4 / FR10a). Carries <code>per_task_results</code> list of per-task <code>pass_rate</code> values.</td>\n</tr>\n<tr>\n<td><code>model_name</code></td>\n<td>Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to <code>\"default\"</code>.</td>\n</tr>\n</table>\n<p>Phase-1 scope: single-model heatmap (one column). Multi-model comparison (rows = tasks \u00d7 columns = models) is Phase-2 work. Missing cells render as <code>\" \u2014 \"</code> sentinel (em-dash with spaces) rather than silently substituting <code>0.0</code> per the Story 10.1 kilo/minimax review HIGH-1 honesty patch.</p>\n<p>Example:</p>\n<pre>\n${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()\n${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()\n${heatmap} =    <a href=\"#Get%20Cohort%20Heatmap\" class=\"name\">Get Cohort Heatmap</a>    ${disc}    model_name=claude-sonnet-4-5\n${ascii} =    Evaluate    $heatmap.as_ascii()\nLog    ${ascii}                                                                           # Box-drawing render.\n${cells} =    Evaluate    $heatmap.as_dict()\nShould Not Be Empty    ${cells}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 8b.2 ratifies the <code>CohortHeatmap</code> data class + <code>Get Cohort Heatmap</code> keyword surface.</li>\n<li>FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> produces the <code>DiscoverabilityResult</code> input.</li>\n</ul>", "shortdoc": "Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_heatmap/library.py", "lineno": 49}, {"name": "Get Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a Claude Code <code>settings.json</code> hook configuration.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per-entry validation per PRD FR4. Returns a dict mapping <code>hooks.&lt;event&gt;</code> \u2192 list of validated hook entries. Covered events: <code>PreToolUse</code>, <code>PostToolUse</code>, <code>Stop</code>; other events are passed through with the same validation. Median \u2264 50 ms on typical hook configs per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>settings.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Each returned entry has <code>command</code> (required) plus any of the optional fields <code>args</code> / <code>timeout</code> / <code>matcher</code> that were present in the source JSON. Entries whose command contains an inline YAML frontmatter block additionally surface an <code>inline_skill: dict</code> field with the parsed frontmatter.</p>\n<p>Raises <code>InvalidHookConfigError</code> on any structural failure (file not found, malformed JSON, missing <code>command</code>, wrong-type optional field). The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer (e.g. <code>/hooks/PreToolUse/0/command</code>) pinpointing the nested location. Format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>This keyword is re-exported through the top-level <code>AgentEval</code> library, so <code>AgentEval.Get Config</code> and <code>Hook.Get Config</code> (when imported as <code>WITH NAME    Hook</code>) resolve to the same implementation.</p>\n<p>Example:</p>\n<pre>\n${config} =    <a href=\"#Get%20Config\" class=\"name\">Get Config</a>    ${CURDIR}/.claude/settings.json\nLength Should Be    ${config}[hooks.PreToolUse]    1\nShould Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook\nShould Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop). Unknown events are validated with the same shape contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format: FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104. The <code>field_name</code> attribute on raised errors carries an RFC 6901 JSON Pointer.</li>\n<li>Inline-skill-frontmatter hooks are an extension surface \u2014 the inner skill is reachable via <span class=\"name\">SkillsLibrary</span> keywords passed the <code>inline_skill</code> dict directly.</li>\n</ul>", "shortdoc": "Parses a Claude Code ``settings.json`` hook configuration.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/hooks/library.py", "lineno": 66}, {"name": "Get Cost Total", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns total provider-reported USD cost (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (USD). Single run: the run's <code>cost_usd</code>. Multi-trial: sum across trials. Empty list \u2192 <code>0.0</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <code>mcp_coverage<span class=\"name\">`-gated. Returns </span>`0.0</code> on the Mock provider; non-zero on real adapters per Story 8a.1 (real adapters use <code>total_cost_usd</code> not <code>cost_usd</code>).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${cost_usd} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${result}\nShould Be True    ${cost_usd} &lt; 0.10                                      # Single-shot cost cap $0.10.\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${total_cost} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${results}                         # Cohort cost rollup.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the cost metric.</li>\n<li>Mock-provider runs return <code>0.0</code> cost; real adapters surface the provider's reported cost.</li>\n<li>Story 8a.1 v1 HIGH-1 ratified <code>total_cost_usd</code> as the canonical real-adapter key.</li>\n<li>Sibling keywords: <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns total provider-reported USD cost (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 419}, {"name": "Get Effective Config", "args": [{"name": "setting", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "setting: str | None = None"}], "returnType": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "doc": "<p>Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 two-form return: no-arg \u2192 <code>dict[str, Any]</code> of resolved values (Story 1a.6 ratified shape, backwards-compat with tier-1 + smoke tests); <code>setting=&lt;key&gt;</code> \u2192 <code>ConfigValue(value, source)</code> for that single setting (FR41 L1563). <code>source</code> is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>setting</code></td>\n<td>Optional config-key name (e.g., <code>\"max_cost_usd\"</code>). When <code>None</code> (default), returns the full <code>dict[str, Any]</code>. When set, returns the single <code>ConfigValue</code> for that key.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>setting</code> is set but not a known config key (with a sorted list of known keys in the message).</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0    telemetry=False\n${config} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>\nShould Be Equal As Numbers    ${config}[max_cost_usd]    5.0\nShould Be Equal    ${config}[telemetry]    ${FALSE}\n${cost_setting} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>    setting=max_cost_usd\nShould Be Equal As Numbers    ${cost_setting.value}    5.0\nShould Be Equal    ${cost_setting.source}    init_arg\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the ConfigValue surface; FR42 ratifies the 9 settings.</li>\n<li>Story 4.3 DF-4.3-S1 carry-over: full <code>dict[str, ConfigValue]</code> migration of the no-arg form is Phase-1.5.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a> for the FR41-compliant full-surface form.</li>\n</ul>", "shortdoc": "Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 409}, {"name": "Get Effective Config With Provenance", "args": [], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "ConfigValue", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the full settings map with per-key provenance as a <code>dict[str, ConfigValue]</code> (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 FR41-compliant surface. Each <code>ConfigValue</code> carries <code>value</code> + <code>source</code> per FR41 L1563. Source is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td>(none)</td>\n<td>Returns the full settings map; no arguments.</td>\n</tr>\n</table>\n<p>Defensive shallow-copy of the underlying provenance dict \u2014 caller mutations don't propagate to the Library's internal state.</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0\n${settings} =    <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a>\n${cost} =    Set Variable    ${settings}[max_cost_usd]\nShould Be Equal As Numbers    ${cost.value}    5.0\nShould Be Equal    ${cost.source}    init_arg                              # Constructor kwarg won.\n${temp} =    Set Variable    ${settings}[default_temperature]\nShould Be Equal    ${temp.source}    default                               # Not overridden \u2014 uses FR42 default.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the <code>dict[str, ConfigValue]</code> shape.</li>\n<li>This is the FR41-compliant surface DF-4.3-S1 will migrate <code>Get Effective Config</code> (no-arg) to once tier-1 tests update.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> for the simpler <code>dict[str, Any]</code> or per-setting form.</li>\n</ul>", "shortdoc": "Returns the full settings map with per-key provenance as a ``dict[str, ConfigValue]`` (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 529}, {"name": "Get Keyword Tier", "args": [{"name": "keyword", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the determinism-tier annotation for an RF keyword (PRD FR30a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int \u2208 {1, 2, 3}</code>. Walks the composed DynamicCore keyword registry + top-level methods to resolve the verbatim RF name to its <code>_agenteval_tier</code> integer via the <code>@tier(N)</code> decorator chain.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>Verbatim RF keyword name (e.g., <code>\"Send Prompt\"</code>, <code>\"Stat.Run N Times\"</code>, <code>\"Get Effective Config\"</code>).</td>\n</tr>\n</table>\n<p>Returns the wrapper's own tier, not the wrapped keyword's tier \u2014 e.g., <code>Stat.Run N Times</code> returns <code>3</code> (fan-out runner tier) per epic AC-5 + Story 6.3 D-14 amendment. The runner's tier governs the <code>@guarded_fanout</code> enforcement model, independent of the wrapped keyword's own classification.</p>\n<p>Raises <code>ValueError</code> when the keyword is not found in the composed library (with a sorted list of known keywords in the message), OR when the keyword has no <code>@tier(N)</code> annotation, OR when the annotated tier is outside <code>{1, 2, 3}</code> (defensive range check per Story 6.3 code-review HIGH-\u03c0 fix).</p>\n<p>Example:</p>\n<pre>\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Get Tool Call Count\nShould Be Equal As Integers    ${tier}    1                                # Tier-1 deterministic metric.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Send Prompt\nShould Be Equal As Integers    ${tier}    2                                # Tier-2 stochastic single-shot.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Stat.Run N Times\nShould Be Equal As Integers    ${tier}    3                                # Tier-3 fan-out runner.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR30a ratifies the tier-introspection contract; AC-6.3.7 establishes the DynamicCore walk.</li>\n<li>Story 6.3 D-14 amendment: fan-out runner reports its own tier (3), not the wrapped keyword's tier.</li>\n<li>Sibling keywords: every <span class=\"name\">@tier</span>-decorated keyword in the composed library is introspectable here.</li>\n</ul>", "shortdoc": "Returns the determinism-tier annotation for an RF keyword (PRD FR30a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 462}, {"name": "Get Last Warnings", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[dict]</code>. Each record has the FR62 ratified 5-field shape: <code>warning_type</code> (str \u2014 fully-qualified Python warning class), <code>message</code> (str \u2014 human- readable text), <code>source</code> (str \u2014 emitting subsystem), <code>timestamp</code> (str \u2014 UTC RFC 3339), <code>remediation</code> (str | None \u2014 actionable advice).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test via the listener context; returns <code>[]</code> if no test is bound. <code>\"all\"</code> \u2014 union across every per-test buffer in the process, sorted by <code>timestamp</code> ascending. Any other value is treated as a specific test_id (returns the named buffer or <code>[]</code> if absent).</td>\n</tr>\n</table>\n<p>Defensive copy of records. Never raises \u2014 buffer-read failures fall back to <code>[]</code>.</p>\n<p>Example:</p>\n<pre>\n@{warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>\nLength Should Be    ${warnings}    0                                                   # Clean run: zero warnings.\n@{all_warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>    test_id=all\nFOR    ${w}    IN    @{all_warnings}\n    Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR62 ratifies the 5-field <code>WarningRecord</code> shape.</li>\n<li>Story 5.4 ratified the per-test buffer + <code>\"all\"</code> aggregation contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> \u2014 companion trace-store accessors.</li>\n</ul>", "shortdoc": "Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 64}, {"name": "Get Latency", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns mean turn-level latency in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). When the run has no <code>tool_calls</code>, falls back to <code>result.latency_seconds * 1000.0</code>. Multi-trial: union-of- tool-calls mean \u2014 all per-tool-call latencies from all trials are flattened into one list before <code>statistics.mean()</code> is taken. Mean-of-per-run-means is a statistical anti-pattern (under-weights runs with more tool calls); union-then-mean is the operator-intuitive default per Story 6.1 code-review.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${latency_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${result}\nShould Be True    ${latency_ms} &lt; 2000                                    # Mean turn latency under 2 seconds.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the latency metric \u2014 per-tool-call resolution preferred over per-run.</li>\n<li>Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).</li>\n<li>Sibling keyword: <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a> for tail-latency tracking.</li>\n<li>Provider-reported scalar \u2014 observer-independent per AC-6.1.1.</li>\n</ul>", "shortdoc": "Returns mean turn-level latency in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 355}, {"name": "Get Latency P95", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the P95 latency across tool calls in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). AC-6.1.8 boundary conditions: 0 tool_calls \u2192 <code>0.0</code>; 1 tool_call \u2192 that single latency; \u22652 \u2192 <code>statistics.quantiles(n=100)[94]</code>. Multi-trial: P95 across the union of all tool_calls' latencies.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${p95_ms} =    <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>    ${results}\n${mean_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${results}\nShould Be True    ${p95_ms} &gt;= ${mean_ms}                                 # P95 \u2265 mean by definition.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the P95 metric \u2014 tail-latency tracking complements <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> mean.</li>\n<li>AC-6.1.8 boundary conditions cover empty / single-call edge cases.</li>\n<li>Sibling keywords: <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> for mean; <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> to generate multi-trial input.</li>\n</ul>", "shortdoc": "Returns the P95 latency across tool calls in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 389}, {"name": "Get Run Manifest", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "Union", "typedoc": null, "nested": [{"name": "RunManifest", "typedoc": null, "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "doc": "<p>Returns the in-memory 7-field <code>RunManifest</code> for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>RunManifest | None</code>. <code>None</code> when <code>test_id=\"current\"</code> and no test is bound (Tier-1 sibling-consistency with <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> / <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> / <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a> non-raising contracts). The in-memory manifest is the <b>*ratified 7-field shape*</b> (<code>library_version</code>, <code>test_id</code>, <code>suite_id</code>, <code>redaction_policy_hash</code>, <code>started_at</code>, <code>ended_at</code>, <code>agenteval_tier_breakdown</code>) \u2014 NOT the Story-5.3-extended operational metadata dict (which lives in the JSON sidecar at <code>&lt;output_dir&gt;/agenteval/manifest__&lt;suite&gt;__&lt;test&gt;.json</code>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>None</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim \u2014 that accessor's <code>ValueError</code> propagates if the explicit id resolves to None per Story 1b.2 semantics.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n${manifest} =    <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>\nShould Not Be Equal    ${manifest}    ${NONE}\nShould Not Be Empty    ${manifest.library_version}\nLength Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li>7-field shape ratified at Story 1b.2 per FR39.</li>\n<li>Story 5.5 code-review 2-way HIGH-F established the <code>None</code> (not raise) contract on no-bound-test current path.</li>\n<li>For the Story-5.3-extended operational shape, read the JSON sidecar directly.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 178}, {"name": "Get Spans", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ReadableSpan", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ReadableSpan]</code> in chronological order by <code>start_time</code>. Empty list is a valid state (test ran without emitting spans). Thin keyword wrapper around the <code>_kernel/trace_store.get_run_spans</code> projection accessor.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n@{spans} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>\nShould Not Be Empty    ${spans}\nFOR    ${span}    IN    @{spans}\n    ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}\n    Log    ${span.name} took ${duration_ns} ns\nEND\n@{spans_specific} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>    test_id=My Suite.Specific Test\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.</li>\n<li>Story 5.5 code-review 3-way HIGH-A established the no-bound-test \u2192 <code>[]</code> non-raising contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> (projection over execute_tool spans); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> (resource-attribute projection); <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 98}, {"name": "Get Token Usage", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "Usage", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Returns the agent's token usage as a <code>Usage</code> dataclass (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>Usage(input_tokens, output_tokens, cached_input_tokens)</code>. Single run: the run's own usage. Multi-trial: sum per field. Empty list \u2192 <code>Usage(0, 0, 0)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 observer-independent. NOT <span class=\"name\">`mcp_coverage</span>`-gated (PRD FR22 + AC-6.1.1).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${usage} =    <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>    ${result}\nShould Be True    ${usage.input_tokens} &gt; 0\nShould Be True    ${usage.output_tokens} &gt; 0\nLog    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the four usage metrics \u2014 <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>, <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a> \u2014 all observer-independent per AC-6.1.1.</li>\n<li><code>Usage</code> is a frozen dataclass; field validation ensures non-negative counts.</li>\n<li>Sibling keywords: <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 324}, {"name": "Get Tool Call Count", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the number of tool calls made by the agent (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int</code>. Single run: <code>len(result.tool_calls)</code>. Multi-trial: sum across trials.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial sum aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code> (default-deny per FR42).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${count} =    <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a>    ${result}\nShould Be Equal As Integers    ${count}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42 \u2014 opt out via <code>AgentEval(allow_external_mcp_blind=True)</code>.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a> for the ordered names list.</li>\n</ul>", "shortdoc": "Returns the number of tool calls made by the agent (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 92}, {"name": "Get Tool Call Names", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns tool-call names in chronological order (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 duplicates preserved per FR19 verbatim (\"list[str] (preserving order)\"). Single run: chronological list. Multi-trial: union preserving order-of-first-appearance.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial union aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n@{names} =    <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a>    ${result}\nShould Contain    ${names}    web_search\nShould Be Equal    ${names}[0]    web_search                              # First tool called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> for the count; <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> for expected-set comparison.</li>\n</ul>", "shortdoc": "Returns tool-call names in chronological order (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 132}, {"name": "Get Tool Calls", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ToolCallTrace", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns <code>ToolCallTrace</code> records projected from the trace store (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ToolCallTrace]</code>. Thin keyword wrapper around <code>_kernel/trace_store.get_tool_calls</code>. Mirrors the source-filtering semantics of the Story 1b.2 accessor (no per-call source filter exposed at the RF surface; consumers filter the returned list themselves).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Returns <code>list[ToolCallTrace]</code> frozen dataclasses (Story 1b.2 shape): each record carries <code>name</code>, <code>args</code>, <code>result</code>, <code>error</code>, <code>latency_ms</code>, <code>source</code>, <code>gen_ai_tool_call_id</code>, <code>sequence_index</code>.</p>\n<p>Example:</p>\n<pre>\n@{tool_calls} =    <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>\nShould Not Be Empty    ${tool_calls}\nShould Be Equal    ${tool_calls}[0].name    web_search\nShould Be Equal As Integers    ${tool_calls}[0].sequence_index    0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li><span class=\"name\">ToolCallTrace</span> shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> (full span list); <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> (metrics-library count over <span class=\"name\">AgentRunResult</span>); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>.</li>\n</ul>", "shortdoc": "Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 139}, {"name": "Get Tool Hit Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-hit rate <code>|expected \u2229 observed| / |expected|</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Empty <code>expected_tools</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: union-of-observed against expected_tools.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${hit_rate} =    <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a>    ${result}    ${{['web_search', 'fetch']}}\nShould Be True    ${hit_rate} &gt;= 0.5                                      # At least half of expected tools were called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keywords: <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a> (calls NOT in expected set); <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a> (errors / total).</li>\n</ul>", "shortdoc": "Returns the tool-hit rate ``|expected \u2229 observed| / |expected|`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 178}, {"name": "Get Tool Success Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-success rate <code>non-error / total</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: aggregate across all per-trial tool calls.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${success_rate} =    <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a>    ${result}\nShould Be True    ${success_rate} &gt;= 0.8                                  # At least 80% of tool calls succeeded.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Each <code>ToolCallTrace</code> has an <code>error</code> field \u2014 non-None counts as a failure.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (vs expected set); <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>.</li>\n</ul>", "shortdoc": "Returns the tool-success rate ``non-error / total`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 224}, {"name": "Get Unnecessary Call Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the unnecessary-call rate <code>not_in_expected / total</code> (PRD FR21).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${noise} =    <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>    ${result}    ${{['web_search']}}\nShould Be True    ${noise} &lt;= 0.2                                         # At most 20% of calls were off-task.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR21 ratifies the unnecessary-rate formula \u2014 quantifies \"noise\" tool calls beyond the expected set.</li>\n<li>AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls \u2192 0.0).</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (calls that ARE in expected set).</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n</ul>", "shortdoc": "Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 271}, {"name": "Judge.Calibrate Rubric", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "calibration_set", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "calibration_set: str | Path"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "CalibrationReport", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs the judge against a labeled calibration set and returns a <span class=\"name\">CalibrationReport</span> (Story 12.2).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 N single-shot LLM calls (one per calibration row) against the configured <code>judge_adapter</code>. Cohen's kappa over binarized judge-pass / human-pass labels at the rubric's threshold; <code>passes_hard_fail</code> is True iff <code>kappa &gt;= 0.7</code> per <span class=\"name\">architecture.md</span> L199 agentguard-borrowed calibration discipline. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>calibration_set</code></td>\n<td>Path to a YAML calibration set with <span class=\"name\">rows:</span> list of <span class=\"name\">{prompt, response, human_label}</span>.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug; defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier; forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Returns <code>CalibrationReport</code> with: <code>cohen_kappa</code> (float; <code>nan</code> if zero-variance), <code>passes_hard_fail</code> (kappa &gt;= 0.7), <code>threshold_tuning</code> (precision/recall/F1 sweep), <code>recommended_threshold</code> (F1-maximizing), <code>systematic_bias_diagnostics</code> (human-readable bullets), <code>total_cost_usd</code>, <code>total_latency_seconds</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>InvalidCalibrationSetError</code> on calibration set parse failure. Raises <code>JudgeOutputParseError</code> if any per-row judge invocation returns malformed JSON.</p>\n<p>Example:</p>\n<pre>\n${report} =    <a href=\"#Judge.Calibrate%20Rubric\" class=\"name\">Judge.Calibrate Rubric</a>    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${report.passes_hard_fail}\nLog    Cohen's kappa = ${report.cohen_kappa}\nLog    Recommended threshold = ${report.recommended_threshold}\n</pre>\n<p>Notes:</p>\n<ul>\n<li><span class=\"name\">KAPPA_HARD_FAIL_THRESHOLD = 0.7</span> per <span class=\"name\">architecture.md</span> L199.</li>\n<li>Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.</li>\n<li>Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.</li>\n</ul>", "shortdoc": "Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).", "tags": ["agenteval"], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 187}, {"name": "Judge.Get Score", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "result: AgentRunResult"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "JudgeScore", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Evaluates an <span class=\"name\">AgentRunResult</span> against a Markdown rubric using an LLM judge (PRD FR48).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 single-shot LLM call against the configured <span class=\"name\">judge_adapter</span> (default <span class=\"name\">\"generic\"</span> LiteLLM-backed). LLM-deterministic per the determinism-contract.md <span class=\"name\">@tier(2)</span> contract when invoked with <span class=\"name\">seed + temperature=0</span>. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>The <span class=\"name\">AgentRunResult</span> to evaluate. Reads <code>result.response_text</code> for the agent's output.</td>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug to resolve via <span class=\"name\">agenteval.coding_agents</span> entry-points. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier for the judge adapter (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>). Forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs (e.g., <code>temperature=0.0</code>, <code>seed=42</code>).</td>\n</tr>\n</table>\n<p>Returns <code>JudgeScore</code> with: <code>numeric_score</code> (0-10), <code>pass_threshold_met</code> (vs rubric threshold), <code>reasoning</code> (LLM's narrative explanation), <code>criteria_breakdown</code> (per-criterion sub-scores), <code>cost_usd</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>JudgeOutputParseError</code> when the LLM response is not valid JSON OR is missing required fields OR <code>numeric_score</code> is outside <code>[0.0, 10.0]</code>.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6\n${score} =    <a href=\"#Judge.Get%20Score\" class=\"name\">Judge.Get Score</a>    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${score.pass_threshold_met}\nShould Be True    ${score.numeric_score} &gt;= 7.0\nLog    Reasoning: ${score.reasoning}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR48 ratifies the keyword + rubric calibration discipline.</li>\n<li>Tier-2 LLM-deterministic per <span class=\"name\">determinism-contract.md</span>; cost guardrails per ADR-015.</li>\n<li><span class=\"name\">JudgeScore</span> shape ratified Story 12.1 AC-12.1.2 per architecture L1316.</li>\n<li>Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.</li>\n</ul>", "shortdoc": "Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 117}, {"name": "Load Scenario", "args": [{"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "scenario: str"}], "returnType": {"name": "Scenario", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Loads + validates a scenario YAML without executing it.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file read + YAML parse + schema validation. Returns the parsed <code>Scenario</code> dataclass without dispatching to any adapter \u2014 useful for <code>.robot</code> tests that assert on scenario metadata or pre-flight-check scenarios before a <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidScenarioYAMLError</code> on parse failure or schema violation. The error's <code>field_name</code> attribute pinpoints the offending field per FR59.</p>\n<p>Example:</p>\n<pre>\n${scenario} =    <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a>    ${CURDIR}/scenarios/web-search.yaml\nShould Be Equal    ${scenario.agent}    web-search-agent\nShould Be Equal    ${scenario.model}    anthropic/claude-sonnet-4-6\nLength Should Be    ${scenario.evals}    5\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the scenario YAML schema; see <span class=\"name\">Scenario</span> dataclass in <span class=\"name\">scenarios/schema.py</span>.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> (Tier-3) for dispatch + execution.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n</ul>", "shortdoc": "Loads + validates a scenario YAML without executing it.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 330}, {"name": "Run Scenario", "args": [{"name": "adapter", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "_Unset", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str | _Unset = _UNSET"}, {"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "scenario: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Executes a scenario YAML file's <code>evals[]</code> against an adapter (PRD FR15).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 loads the scenario YAML via <code>load_scenario()</code>, validates against the <code>Scenario</code> schema, then dispatches each eval's prompt to <code>adapter.run()</code> <code>repeat</code> times. Returns a flat <code>list[AgentRunResult]</code> of length <code>sum(eval.repeat for eval in scenario.evals)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Per-scenario <code>agent:</code> field in the YAML overrides this kwarg per FR15 (\"scenario YAML specifies agent\" \u2014 YAML beats default but not explicit kwarg).</td>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code>. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are split between adapter constructor + <code>run()</code> per the same signature-introspection rule as <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>. Scenario-YAML <code>model:</code> / <code>provider:</code> fields inject into the merged kwargs unless the caller already passed them.</p>\n<p>Raises <code>InvalidScenarioYAMLError</code> on YAML parse / schema failure, <code>AdapterDiscoveryError</code> on unknown adapter name, and <code>NotImplementedError</code> on non-empty comma-separated <code>mcp_servers</code> (Phase-1 DF-4.3-S2 carve-out).</p>\n<p>Example:</p>\n<pre>\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    scenario=${CURDIR}/scenarios/web-search.yaml\nLength Should Be    ${results}    5\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the multi-eval orchestration contract.</li>\n<li>FR41 precedence resolution: explicit kwarg &gt; scenario YAML &gt; library default.</li>\n<li>Sibling keyword: <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a> (Tier-1) to validate the YAML without executing.</li>\n<li>Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).</li>\n</ul>", "shortdoc": "Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 215}, {"name": "Send Prompt", "args": [{"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "prompt: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Executes a single-shot prompt against a coding-agent adapter (PRD FR14).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 invokes the named adapter's <code>run()</code> method per the <span class=\"name\">CodingAgentAdapter</span> Protocol. Returns an <code>AgentRunResult</code> carrying <code>response_text</code>, <code>tool_calls</code>, <code>usage</code>, <code>metadata</code> (with <code>completeness</code> + <code>mcp_coverage</code>), <code>cost_usd</code>, <code>latency_seconds</code>, and <code>trace_id</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code> (LiteLLM-backed).</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code> of attached MCP servers. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2 \u2014 name resolution to handles deferred).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are forwarded to the adapter \u2014 caller kwargs that match the adapter's <code>__init__</code> signature flow to construction; the rest flow to <code>run()</code>. Useful for <code>model=\"anthropic/claude-sonnet-4-6\"</code>, <code>temperature=0.5</code>, etc.</p>\n<p>Raises <code>AdapterDiscoveryError</code> when the <code>adapter</code> name is not registered. Raises <code>NotImplementedError</code> on comma-separated <code>mcp_servers</code> name strings until DF-4.3-S2 lands the name \u2192 handle resolver (pass <code>mcp_servers={'name': handle}</code> directly to forward Phase-1).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Hello, world.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=claude-code-cli    prompt=Run the build.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR14 ratifies the single-prompt orchestration contract.</li>\n<li>Adapter discovery per Story 1b.3 + ADR-013 entry-points.</li>\n<li><code>cost_usd</code> is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> for multi-eval YAML-driven dispatch (Tier-3).</li>\n</ul>", "shortdoc": "Executes a single-shot prompt against a coding-agent adapter (PRD FR14).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 127}, {"name": "Stat.Assert Run Determinism", "args": [{"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "expect", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "byte_identical", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "expect: str = byte_identical"}], "returnType": null, "doc": "<p>Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 invokes the wrapped keyword twice with identical inputs and compares via deep-equality. The bit-identical guarantee is scoped to Tier-1 keywords only (FR31a contract); the keyword raises <code>TierViolationError</code> if a Tier-2/3 keyword is passed.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR callable. Same dispatch rules as <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> (string form requires active RF context).</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings.</td>\n</tr>\n<tr>\n<td><code>expect</code></td>\n<td>Comparison mode. Phase-1 supports <code>\"byte_identical\"</code> only; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> deferred to Phase-2.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>expect != \"byte_identical\"</code> (Phase-1 scope). Raises <code>TierViolationError</code> when the wrapped keyword is not Tier-1 \u2014 FR31a is scoped to Tier-1 only. Raises <code>AssertionError</code> on output mismatch with a <span class=\"name\">`redact()</span>`-scrubbed diff per FR38a credential-safety contract.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Effective Config\nRun Keyword And Expect Error    TierViolationError*    <a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Send Prompt\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> + <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for statistical assertions instead.</li>\n<li>Diff redaction per FR38a + Story 5.3 \u2014 credentials in args / output don't leak into RF logs.</li>\n<li>Story 6.3 ratifies <code>\"byte_identical\"</code> as the Phase-1 contract; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> are Phase-2 work-items.</li>\n</ul>", "shortdoc": "Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 297}, {"name": "Stat.Bootstrap Confidence Interval", "args": [{"name": "samples", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "samples: list[KeywordRun] | list[float]"}, {"name": "seed", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "seed: int"}, {"name": "statistic", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[list[float]]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "statistic: Callable[[list[float]], float] | None = None"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}, {"name": "alpha", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.05", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "alpha: float = 0.05"}, {"name": "n_resamples", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "10000", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "n_resamples: int = 10000"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 given fixed <code>samples</code> + <code>seed</code>, the result is bit-identical across calls (FR31a guarantee). Returns <code>(ci_lower, ci_upper)</code> tuple at the <code>(1 - alpha) * 100%</code> percentile level (default 95% CI).</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>samples</code></td>\n<td>Either <code>list[KeywordRun]</code> (then <code>predicate</code> extracts floats) OR <code>list[float]</code> (predicate ignored). Mixed-type lists raise <code>TypeError</code> \u2014 homogeneous types required.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>REQUIRED <code>int</code> seed for the numpy <code>Generator</code>. No default \u2014 the <code>@tier(1)</code> bit-identical guarantee (FR31a) requires a fixed seed. Operators wanting OS-entropy randomness must pass an explicit seed (e.g., <code>seed=random.randrange(2**32)</code>).</td>\n</tr>\n<tr>\n<td><code>statistic</code></td>\n<td><code>Callable[[list[float]], float]</code> whose CI is computed. Default <code>None</code> \u2192 <code>statistics.mean</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], float]</code> value-extractor (required when <code>samples</code> is <code>list[KeywordRun]</code>).</td>\n</tr>\n<tr>\n<td><code>alpha</code></td>\n<td>Significance level; CI is at <code>(1-alpha)*100%</code> confidence. Must satisfy <code>0.0 &lt; alpha &lt; 1.0</code>. Default <code>0.05</code>.</td>\n</tr>\n<tr>\n<td><code>n_resamples</code></td>\n<td>Number of bootstrap resamples (with replacement). Must be <code>&gt;= 100</code>. Default <code>10_000</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy unavailable; <code>ValueError</code> when <code>samples</code> is empty / <code>alpha</code> is out of range / <code>n_resamples &lt; 100</code> / <code>predicate</code> is missing for a <code>list[KeywordRun]</code> input. Raises <code>TypeError</code> when <code>samples</code> mixes <code>KeywordRun</code> and raw floats (homogeneous types required).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${cost_pred} =    Evaluate    lambda r: r.result.cost_usd\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Bootstrap%20Confidence%20Interval\" class=\"name\">Stat.Bootstrap Confidence Interval</a>    ${runs}    seed=42    predicate=${cost_pred}\nShould Be True    ${ci_lo} &lt;= ${ci_hi}                                    # CI bounds well-ordered.\n${median_stat} =    Evaluate    statistics.median    modules=statistics\n${med_lo}    ${med_hi} =    <a href=\"#Stat.Bootstrap%20Confidence%20Interval\" class=\"name\">Stat.Bootstrap Confidence Interval</a>    ${runs}    seed=42    statistic=${median_stat}    predicate=${cost_pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29c ratifies the <code>(lo, hi)</code> tuple return type \u2014 preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.</li>\n<li>Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).</li>\n<li>Math reference: <code>scipy.stats.bootstrap(samples, statistic, rng=numpy.random.default_rng(seed), method=\"percentile\")</code>. The local implementation uses the same <code>numpy.random.default_rng(seed)</code> source so reference equivalence is verifiable.</li>\n<li>Mandatory <code>seed</code> preserves the <code>@tier(1)</code> FR31a bit-identical guarantee (Story 13.1 code-review HIGH-C catch, Opus tier review).</li>\n<li>Resampling result determinism is pinned to a single <code>numpy.random.Generator</code> algorithm (PCG64). Major numpy ABI changes that retire PCG64 would shift CI bounds; track via <span class=\"name\">`_TESTED_UP_TO</span>`-style pinning in Phase-2 if numpy 3.x ships a different default generator.</li>\n</ul>", "shortdoc": "Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 509}, {"name": "Stat.Cliff Delta", "args": [{"name": "runs_a", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_a: list[KeywordRun]"}, {"name": "runs_b", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_b: list[KeywordRun]"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form Cliff (1993) brute-force formula. Returns <code>float \u2208 [-1.0, 1.0]</code>. Positive values indicate <code>runs_a</code> tends to produce larger values; negative values indicate <code>runs_b</code> tends to produce larger values.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs_a</code></td>\n<td><code>list[KeywordRun]</code> \u2014 first sample.</td>\n</tr>\n<tr>\n<td><code>runs_b</code></td>\n<td><code>list[KeywordRun]</code> \u2014 second sample.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>REQUIRED <code>Callable[[KeywordRun], float]</code> value-extractor. <code>None</code> raises <code>ValueError</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy unavailable; <code>ValueError</code> when <code>predicate</code> is <code>None</code> OR either sample is empty.</p>\n<p>Example:</p>\n<pre>\n${latency_pred} =    Evaluate    lambda r: r.latency_seconds\n${delta} =    <a href=\"#Stat.Cliff%20Delta\" class=\"name\">Stat.Cliff Delta</a>    ${runs_a}    ${runs_b}    predicate=${latency_pred}\nShould Be True    abs(${delta}) &gt; 0.474                                  # Large effect per Romano-Coraggio-Smith conventions.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29b ratifies the scalar <code>float</code> return type (NOT a dataclass) \u2014 preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.</li>\n<li>Math: <code>\u03b4 = (#{a&gt;b} - #{a&lt;b}) / (n_a * n_b)</code>; ties contribute 0.</li>\n<li>Complexity: <code>O(n_a * n_b)</code>. Fine for typical n \u2264 100 trials; Phase-2 perf carve-out for n_a + n_b &gt; 1000.</li>\n</ul>", "shortdoc": "Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 463}, {"name": "Stat.Get Pass At K", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form computation of the HumanEval estimator <code>1 - C(n-c, k) / C(n, k)</code>. Returns <code>float \u2208 [0, 1]</code>. Scalar return preserves AssertionEngine compatibility (<code>&gt;=</code> / <code>&lt;=</code> matchers); CI is a separate paired getter \u2014 see <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Must satisfy <code>1 &lt;= k &lt;= len(runs)</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Default checks <code>r.completeness == \"complete\"</code> per epic AC-2 + Story 6.4 fix-NOW.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k &lt; 1</code>, <code>k &gt; len(runs)</code>, or <code>len(runs) == 0</code>.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${pass_at_1} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=1\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.\n${pred} =    Evaluate    lambda r: r.error is None\n${pass_strict} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5    predicate=${pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR27 ratifies the scalar <code>float</code> return type \u2014 no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).</li>\n<li>Default predicate updated by Story 6.4 fix-NOW: <code>completeness == \"complete\"</code> (pre-edit <code>\"full\"</code> was fake-green; <span class=\"name\">AgentRunMetadata._VALID_COMPLETENESS</span> is <code>{\"complete\", \"truncated\", \"partial\"}</code>).</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a> for the Wilson score CI.</li>\n</ul>", "shortdoc": "Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 199}, {"name": "Stat.Get Pass At K Confidence Interval", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}, {"name": "confidence", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.95", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "confidence: float = 0.95"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Wilson score interval at the given <code>confidence</code> level for the latent per-trial success probability. Returns <code>(ci_lower, ci_upper)</code> tuple of <code>float</code> in <code>[0, 1]</code>. Paired with <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> \u2014 the scalar point estimate plus this CI together satisfy epic AC-2's \"Pass@k with confidence interval\" promise.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Validated for <code>1 &lt;= k &lt;= len(runs)</code> but only used for sanity check \u2014 the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Same default as <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>.</td>\n</tr>\n<tr>\n<td><code>confidence</code></td>\n<td>Confidence level in <code>(0, 1)</code>. Defaults to <code>0.95</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k</code> is non-positive or <code>k &gt; n</code> (with <code>n &gt; 0</code> \u2014 empty <code>runs</code> is permitted per the Wilson formula).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5\nShould Be True    0.0 &lt;= ${ci_lo} &lt;= ${ci_hi} &lt;= 1.0                      # CI bounds are well-formed probabilities.\n${ci99_lo}    ${ci99_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5    confidence=0.99\nShould Be True    (${ci99_hi} - ${ci99_lo}) &gt;= (${ci_hi} - ${ci_lo})      # Higher confidence \u2192 wider interval.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.</li>\n<li>PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for the scalar point estimate.</li>\n</ul>", "shortdoc": "Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 241}, {"name": "Stat.Mann Whitney U", "args": [{"name": "runs_a", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_a: list[KeywordRun]"}, {"name": "runs_b", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_b: list[KeywordRun]"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}], "returnType": {"name": "MannWhitneyResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form non-parametric test for whether two independent samples were drawn from the same distribution. Returns <code>MannWhitneyResult</code> with U statistic, two-sided p-value, rank-biserial effect size, and sample sizes.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra (scipy + numpy); raises <code>ImportError</code> when invoked without it. The <code>StatsLibrary</code> class itself remains importable without the extra; only this Phase-2 keyword method raises on invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs_a</code></td>\n<td><code>list[KeywordRun]</code> \u2014 first sample (typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> against flow A).</td>\n</tr>\n<tr>\n<td><code>runs_b</code></td>\n<td><code>list[KeywordRun]</code> \u2014 second sample (typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> against flow B).</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>REQUIRED <code>Callable[[KeywordRun], float]</code> value-extractor producing the numeric quantity to compare (e.g., <code>lambda r: r.latency_seconds</code>). Default <code>None</code> raises <code>ValueError</code> \u2014 no sensible default numeric metric across all <code>KeywordRun</code> shapes. NOTE: distinct from <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>'s boolean predicate.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy are unavailable (missing <code>[agenteval-advanced]</code> extra). Raises <code>ValueError</code> when <code>predicate</code> is <code>None</code> OR when either <code>runs_a</code> / <code>runs_b</code> is empty.</p>\n<p>Example:</p>\n<pre>\n@{runs_a} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=claude_code_cli']}}\n@{runs_b} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=codex_cli']}}\n${cost_pred} =    Evaluate    lambda r: r.result.cost_usd\n${mwu} =    <a href=\"#Stat.Mann%20Whitney%20U\" class=\"name\">Stat.Mann Whitney U</a>    ${runs_a}    ${runs_b}    predicate=${cost_pred}\nShould Be True    ${mwu.p_value} &lt; 0.05                                  # Reject the null at \u03b1=0.05.\nShould Be True    abs(${mwu.effect_size_r}) &gt; 0.3                        # Medium-or-larger effect.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29a ratifies the <code>MannWhitneyResult</code> dataclass with <code>u_statistic</code> / <code>p_value</code> / <code>effect_size_r</code> + <code>n_a</code> / <code>n_b</code>.</li>\n<li>Math reference: <code>scipy.stats.mannwhitneyu(alternative=\"two-sided\", use_continuity=False)</code>. The returned <code>p_value</code> matches scipy exactly; the returned <code>u_statistic</code> is normalized to <code>min(U1, U2)</code> (smaller-U canonical form) and does NOT match scipy's <code>.statistic</code> directly \u2014 scipy returns <code>U1</code>. Consumers needing scipy's U1 can recover it via <code>U1 = (1 + effect_size_r) * n_a * n_b / 2</code>.</li>\n<li>Effect size: signed rank-biserial <code>r = 2*U1/(n_a*n_b) - 1</code> (where U1 is the M-W U for samples_a); positive r \u2192 samples_a tends to be larger; matches <code>Stat.Cliff Delta</code> sign convention.</li>\n<li>One-sided variants (<code>alternative=\"greater\"<span class=\"name\">`/</span>`\"less\"</code>) deferred to Phase-2 (DF-13.1-S1).</li>\n</ul>", "shortdoc": "Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 407}, {"name": "Stat.Run N Times", "args": [{"name": "n", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "n: int"}, {"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "seed", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "int", "typedoc": "integer", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "seed: int | None = None"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Runs a keyword <code>n</code> times independently and returns the per-trial results (PRD FR26).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 wraps the target keyword in independent trials. Returns <code>list[KeywordRun]</code> of length <code>n</code>. Trial-level errors are re-raised from this keyword \u2014 wrap in <code>Run Keyword And Ignore Error</code> for \"ignore failures\" semantics.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>n</code></td>\n<td>Number of independent trials. Must be <code>&gt;= 1</code>.</td>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR a Python callable. String form requires an active RF execution context (resolved via <code>BuiltIn</code>); callable form is useful for pytest unit tests.</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings (e.g. <code>{\"adapter\": \"generic\", \"prompt\": \"Hi\"}</code> or <code>[\"adapter=generic\", \"prompt=Hi\"]</code>). <code>None</code> = no args.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>Optional <code>int</code> seed; each trial receives <code>seed + trial_index</code> via a <code>seed=</code> kwarg injection so trials are deterministic but distinct. <code>None</code> = OS-entropy seeding per trial.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>n &lt; 1</code>. Raises <code>CostExceededError</code> / <code>RuntimeBudgetExceededError</code> per the <code>@guarded_fanout</code> 3-layer enforcement.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= 0.6\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the <code>list[KeywordRun]</code> return type.</li>\n<li>Cost / runtime guardrails per ADR-015 + <span class=\"name\">_kernel/guardrails.py::@guarded_fanout</span>.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> (Tier-1) consumes the returned list.</li>\n</ul>", "shortdoc": "Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 113}, {"name": "Tool Call Should Have Occurred", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "tool", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool: str"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: dict[str, Any] | None = None"}, {"name": "match_mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "subset", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "match_mode: str = subset"}], "returnType": null, "doc": "<p>Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 searches all observed <code>tool_calls</code> for one matching <code>tool</code> + (optionally) <code>args</code>. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>tool</code></td>\n<td>Expected tool name (exact-match required).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>Optional dict of expected args. <code>None</code> (default) = name-only match.</td>\n</tr>\n<tr>\n<td><code>match_mode</code></td>\n<td><code>\"subset\"</code> (default \u2014 <code>args</code> is a dict-subset of <code>tc.args</code>; recursive for nested dicts) OR <code>\"exact\"</code> (<code>tc.args == args</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>match_mode</code> is invalid (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> when no tool call matches.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected <code>web_search</code> call):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"agenteval\"} }}\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"x\"} }}    match_mode=exact\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR24 ratifies the name + args + match-mode contract.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a> for ordered-sequence assertions over multiple calls.</li>\n</ul>", "shortdoc": "Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 162}, {"name": "Trajectory Should Match", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "expected", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected: list[str]"}, {"name": "mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "exact", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mode: str = exact"}], "returnType": null, "doc": "<p>Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 four match modes available. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a so credentials in tool args don't leak into RF logs.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>expected</code></td>\n<td>List of expected tool names (or regex patterns when <code>mode=\"regex\"</code>).</td>\n</tr>\n<tr>\n<td><code>mode</code></td>\n<td>Match mode: <code>\"exact\"</code> (ordered equality) / <code>\"subsequence\"</code> (ordered, extras allowed between) / <code>\"set\"</code> (unordered set-equality of distinct names) / <code>\"regex\"</code> (each <code>expected[i]</code> is a <code>re.fullmatch</code> pattern against <code>&lt;tool&gt;:&lt;json.dumps(args, sort_keys=True)&gt;</code>). Default <code>\"exact\"</code>.</td>\n</tr>\n</table>\n<p>Set-mode caveat: duplicate names collapse \u2014 <code>[\"a\", \"a\"]</code> set- equals <code>[\"a\"]</code>. Operators wanting multiset semantics (\"exactly N calls of tool X\") should use <code>mode=\"exact\"</code>.</p>\n<p>Raises <code>ValueError</code> when <code>mode</code> is not one of the 4 documented values (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> on trajectory mismatch.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected 3-call trajectory):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'fetch', 'summarize']}}\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['fetch', 'web_search']}}    mode=set\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR23a + FR23b ratify the 4 match modes.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a> for single-call name+args assertions.</li>\n</ul>", "shortdoc": "Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 86}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config", "Get Last Warnings", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["__init__", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config With Provenance", "Get Last Warnings", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["__init__", "Get Cost Total", "Get Latency", "Get Latency P95", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Keyword Tier", "Get Tool Call Count", "Stat.Bootstrap Confidence Interval", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Config", "Get Cost Total", "Get Last Warnings", "Get Latency", "Get Latency P95", "Get Spans", "Get Token Usage", "Get Tool Call Count", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Run Scenario", "Stat.Assert Run Determinism", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U", "Stat.Run N Times", "Trajectory Should Match"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["__init__"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["__init__", "Get Effective Config", "Get Run Manifest", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Judge.Calibrate Rubric", "Judge.Get Score"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["__init__", "Agent Response Should Contain", "Agent Response Should Match Regex", "Agent Response Should Match Schema", "Get Cohort Heatmap", "Get Config", "Get Effective Config", "Get Effective Config With Provenance", "Get Keyword Tier", "Get Last Warnings", "Get Run Manifest", "Get Spans", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Unnecessary Call Rate", "Judge.Calibrate Rubric", "Judge.Get Score", "Load Scenario", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred", "Trajectory Should Match"], "accepts": ["Any"]}, {"type": "Standard", "name": "tuple", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> or <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible lists converted further to tuples. They can contain any values <code>ast.literal_eval</code> supports, including tuples and other collections.</p>\n<p>If the argument is a tuple, it is used without conversion. Lists and other sequences are converted to tuples.</p>\n<p>If the type has nested types like <code>tuple[str, int, int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>('one', 'two')</code>, <code>(('one', 1), ('two', 2))</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for list literals is new in Robot Framework 7.4.</p>", "usages": ["Stat.Bootstrap Confidence Interval", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Sequence"]}]}
+libdoc = {"specversion": 3, "name": "AgentEval", "doc": "<p>Robot Framework library for evaluating AI coding agents.</p>\n<p>Wires the 9 PRD FR42 + FR11b defaults into a single Library entry point + the FR41 precedence chain (kwarg \u2192 env-var \u2192 <span class=\"name\">.env</span> \u2192 defaults) via <span class=\"name\">_kernel.context.resolve_config</span> (Story 1b.1). <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> returns the precedence-resolved values.</p>\n<p>Args: provider: Provider plugin name resolved via <span class=\"name\">agenteval.providers</span> entry-points (FR42; ADR-013). Phase 1 ships only the <span class=\"name\">litellm</span> provider; future providers register via <span class=\"name\">[project.entry-points.\"agenteval.providers\"]</span>. telemetry: Enable the OTel listener for trace recording (FR42 + FR44). When False, <span class=\"name\">Get Trace Backend Names</span> returns <span class=\"name\">[]</span> and no OTLP egress occurs (Phase 2). Phase 1 wires the parameter; full listener-disable enforcement lands in Epic 5 Story 5.1. trace_backend: Trace store backend (FR42 + FR33b). Phase 1 supports <span class=\"name\">\"memory\"</span> and <span class=\"name\">\"jsonl\"</span>; <span class=\"name\">\"otlp\"</span> is Phase 2. allow_validate_operator: Enable the AssertionEngine <span class=\"name\">validate</span> operator which uses <span class=\"name\">eval()</span> (FR42 + FR43; NFR-SEC-02). Default False \u2014 the safer posture per NFR-SEC-02. Gate enforcement (raising <span class=\"name\">ValidateOperatorDisallowed</span>) lands in Epic 6. default_temperature: Default provider temperature for non-stochastic keywords (FR42). 0.0 enforces deterministic provider calls where the underlying model supports it. mcp_per_test: MCP server scope.</p>\n<ul>\n<li>True (default): per-test isolation; correct under <span class=\"name\">pabot --processes N</span>. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>False: single shared instance across all tests; only correct serial. (ADR-009 \u00a7Decision \u2014 ratified True/False.)</li>\n<li>\"suite\": per-suite scope; recipe-5 dogfood-CI ergonomics override. (Architecture L314 + NFR-PERF-03d \u2014 not in ADR-009 proper.) allow_external_mcp_blind: Opt-in to running with <span class=\"name\">mcp_coverage=\"external_mixed\"</span> without <span class=\"name\">IncompleteTraceError</span> (FR42 + ADR-016 D4 adapter contract). Default False enforces loud-refusal posture from ADR-016. max_cost_usd: Cost budget for <span class=\"name\">@guarded_fanout</span>-decorated Tier-3 keywords (FR42 + ADR-015). USD per fan-out invocation. Default 5.00. max_runtime_seconds: Wall-clock budget for Tier-3 fan-out keywords (FR11b + ADR-015). Default None = no cap (opt-in via explicit value). Sibling to <span class=\"name\">max_cost_usd</span>; catches slow MCP-server startup compounded across trials. otlp_endpoint: OTLP collector endpoint URL (FR33b; Story 13.2). Only consumed when <code>trace_backend=\"otlp\"</code>. URL scheme selects transport: <code>http://</code> / <code>https://</code> \u2192 OTLP HTTP/protobuf exporter (port 4318); <code>grpc://</code> / <code>grpcs://</code> \u2192 OTLP gRPC exporter (port 4317). Default <code>None</code> \u2192 OTLPBackend falls back to <code>http://localhost:4318/v1/traces</code> (local Jaeger HTTP). Requires the <code>[otlp]</code> extra (<code>opentelemetry-exporter-otlp</code>); constructing OTLPBackend without the extra raises <code>ImportError</code>.</li>\n</ul>\n<p>FR41 precedence behavior (Story 1b.1): Each <span class=\"name\">__init__</span> parameter defaults to a private sentinel; if the caller does NOT pass it, the value falls through to <span class=\"name\">AGENTEVAL_*</span> env-vars, then to a <span class=\"name\">.env</span> file in cwd, then to the FR42 + FR11b defaults documented in this docstring. Callers who want to force a value explicitly (even when an env-var is set) pass that value as a kwarg. <span class=\"name\">.env.example</span> documents the canonical <span class=\"name\">AGENTEVAL_*</span> env-var names.</p>\n<p>References:</p>\n<ul>\n<li>PRD FR42 (defaults) + FR43 (validate gate) + FR44 (telemetry disable)</li>\n<li>PRD FR11b (max_runtime_seconds keyword arg sibling)</li>\n<li>PRD FR41 (config precedence)</li>\n<li>ADR-009 (mcp_per_test 3-mode)</li>\n<li>ADR-013 (entry-points discovery for <span class=\"name\">provider</span>)</li>\n<li>ADR-015 (@guarded_fanout for cost + runtime guardrails)</li>\n<li>ADR-016 (mcp_coverage detection + allow_external_mcp_blind)</li>\n<li>docs/contracts/stability-surface.md (Phase-1 stability labels for this class)</li>\n</ul>", "version": "", "generated": "2026-06-01T11:44:27+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 159, "tags": ["agenteval"], "inits": [{"name": "__init__", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "provider", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "provider: str = _UNSET"}, {"name": "telemetry", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "telemetry: bool = _UNSET"}, {"name": "trace_backend", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "trace_backend: str = _UNSET"}, {"name": "allow_validate_operator", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_validate_operator: bool = _UNSET"}, {"name": "default_temperature", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "default_temperature: float = _UNSET"}, {"name": "mcp_per_test", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'suite'", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "mcp_per_test: bool | Literal['suite'] = _UNSET"}, {"name": "allow_external_mcp_blind", "type": {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "allow_external_mcp_blind: bool = _UNSET"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_cost_usd: float = _UNSET"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "max_runtime_seconds: float | None = _UNSET"}, {"name": "otlp_endpoint", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "NAMED_ONLY", "required": false, "repr": "otlp_endpoint: str | None = _UNSET"}], "returnType": null, "doc": "<p>Initialize self.  See help(type(self)) for accurate signature.</p>", "shortdoc": "Initialize self.  See help(type(self)) for accurate signature.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 233}], "keywords": [{"name": "Agent Response Should Contain", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "substring", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "substring: str"}], "returnType": null, "doc": "<p>Asserts that <code>substring</code> appears in <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>substring</code></td>\n<td>Literal substring to match. Case-sensitive.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the substring is not found.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    Robot Framework                                          # Mock echoes the prompt.\n<a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a>    ${result}    test automation\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 236}, {"name": "Agent Response Should Match Regex", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "pattern", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "pattern: str"}], "returnType": null, "doc": "<p>Asserts a regex pattern matches <code>result.response_text</code> (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 uses <code>re.search</code> (substring-match by default per FR25's \"match\" terminology). Multi-line text supported via standard <code>re</code> flags in the pattern. NOT <span class=\"name\">`mcp_coverage</span><span class=\"name\">-gated. Failure messages are </span><span class=\"name\">redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code>.</td>\n</tr>\n<tr>\n<td><code>pattern</code></td>\n<td>Python <code>re</code> pattern. Use <code>(?i)</code> / <code>(?m)</code> / <code>(?s)</code> inline flags as needed.</td>\n</tr>\n</table>\n<p>Raises <code>AssertionError</code> when the pattern does not match.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Released in 2020 \u2014 Robot Framework 3.x    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    20\\d{2}                          # 4-digit year \u2014 matches the echoed \"2020\".\n<a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a>    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the regex assertion; <span class=\"name\">re.search</span> semantics (not <span class=\"name\">re.fullmatch</span>).</li>\n<li>Response text is observer-independent \u2014 no mcp_coverage gate.</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a> (JSON schema).</li>\n</ul>", "shortdoc": "Asserts a regex pattern matches ``result.response_text`` (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 268}, {"name": "Agent Response Should Match Schema", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "schema", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "schema: dict[str, Any] | str | Path"}], "returnType": null, "doc": "<p>Asserts <code>response_text</code> parses as JSON + validates against a JSON Schema (PRD FR25).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 provider-reported scalar; NOT <code>mcp_coverage<span class=\"name\">`-gated. Parses </span>`response_text</code> as JSON, then validates against the schema via <code>jsonschema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying <code>response_text</code> (expected to be JSON-parsable).</td>\n</tr>\n<tr>\n<td><code>schema</code></td>\n<td>JSON Schema as a <code>dict</code> OR a file path (<code>str</code> / <code>pathlib.Path</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>schema</code> is not a <code>dict<span class=\"name\">`/</span><span class=\"name\">str</span><span class=\"name\">/</span>`Path</code>, or when the file is not a valid JSON schema dict. Raises <code>AssertionError</code> (redacted per FR38a) when <code>response_text</code> is not JSON-parsable. Raises <code>jsonschema.ValidationError</code> when the parsed JSON does not validate against the schema (preserves the jsonschema convention so consumers can catch the specific exception).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt={\"answer\": 42}    adapter=generic    provider=mock\n<a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${{ {\"type\": \"object\", \"required\": [\"answer\"]} }}\n# Path form: <a href=\"#Agent%20Response%20Should%20Match%20Schema\" class=\"name\">Agent Response Should Match Schema</a>    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.</li>\n<li>Uses <code>jsonschema</code> package \u2014 the upstream <code>ValidationError</code> is preserved on validation failure (callers can catch specifically).</li>\n<li>Failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keywords: <a href=\"#Agent%20Response%20Should%20Contain\" class=\"name\">Agent Response Should Contain</a> (literal substring), <a href=\"#Agent%20Response%20Should%20Match%20Regex\" class=\"name\">Agent Response Should Match Regex</a> (regex pattern).</li>\n</ul>", "shortdoc": "Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 301}, {"name": "Get Cohort Heatmap", "args": [{"name": "discoverability_result", "type": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "discoverability_result: DiscoverabilityResult"}, {"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "model_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "default", "kind": "NAMED_ONLY", "required": false, "repr": "model_name: str = default"}], "returnType": {"name": "CohortHeatmap", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds a <code>CohortHeatmap</code> from a <code>DiscoverabilityResult</code> (Story 8b.2 / FR55).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure projection over the result's <code>per_task_results</code>; no LLM calls. Returns a <code>CohortHeatmap</code> instance with <code>.as_ascii()</code> (box-drawing rendered grid) + <code>.as_dict()</code> (nested <code>{task: {model: pass_at_k}}</code> mapping) methods.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>discoverability_result</code></td>\n<td>Result from <span class=\"name\">MCP.Get Tool Discoverability</span> (Story 4.4 / FR10a). Carries <code>per_task_results</code> list of per-task <code>pass_rate</code> values.</td>\n</tr>\n<tr>\n<td><code>model_name</code></td>\n<td>Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to <code>\"default\"</code>.</td>\n</tr>\n</table>\n<p>Phase-1 scope: single-model heatmap (one column). Multi-model comparison (rows = tasks \u00d7 columns = models) is Phase-2 work. Missing cells render as <code>\" \u2014 \"</code> sentinel (em-dash with spaces) rather than silently substituting <code>0.0</code> per the Story 10.1 kilo/minimax review HIGH-1 honesty patch.</p>\n<p>Example:</p>\n<pre>\n${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()\n${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()\n${heatmap} =    <a href=\"#Get%20Cohort%20Heatmap\" class=\"name\">Get Cohort Heatmap</a>    ${disc}    model_name=claude-sonnet-4-5\n${ascii} =    Evaluate    $heatmap.as_ascii()\nLog    ${ascii}                                                                           # Box-drawing render.\n${cells} =    Evaluate    $heatmap.as_dict()\nShould Not Be Empty    ${cells}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 8b.2 ratifies the <code>CohortHeatmap</code> data class + <code>Get Cohort Heatmap</code> keyword surface.</li>\n<li>FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> produces the <code>DiscoverabilityResult</code> input.</li>\n</ul>", "shortdoc": "Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_heatmap/library.py", "lineno": 49}, {"name": "Get Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a Claude Code <code>settings.json</code> hook configuration.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per-entry validation per PRD FR4. Returns a dict mapping <code>hooks.&lt;event&gt;</code> \u2192 list of validated hook entries. Covered events: <code>PreToolUse</code>, <code>PostToolUse</code>, <code>Stop</code>; other events are passed through with the same validation. Median \u2264 50 ms on typical hook configs per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>settings.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Each returned entry has <code>command</code> (required) plus any of the optional fields <code>args</code> / <code>timeout</code> / <code>matcher</code> that were present in the source JSON. Entries whose command contains an inline YAML frontmatter block additionally surface an <code>inline_skill: dict</code> field with the parsed frontmatter.</p>\n<p>Raises <code>InvalidHookConfigError</code> on any structural failure (file not found, malformed JSON, missing <code>command</code>, wrong-type optional field). The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer (e.g. <code>/hooks/PreToolUse/0/command</code>) pinpointing the nested location. Format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</p>\n<p>This keyword is re-exported through the top-level <code>AgentEval</code> library, so <code>AgentEval.Get Config</code> and <code>Hook.Get Config</code> (when imported as <code>WITH NAME    Hook</code>) resolve to the same implementation.</p>\n<p>Example:</p>\n<pre>\n${config} =    <a href=\"#Get%20Config\" class=\"name\">Get Config</a>    ${CURDIR}/.claude/settings.json\nLength Should Be    ${config}[hooks.PreToolUse]    1\nShould Be Equal    ${config}[hooks.PreToolUse][0][command]    /usr/local/bin/audit-hook\nShould Be Equal As Integers    ${config}[hooks.PostToolUse][0][timeout]    30\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR4 ratifies the canonical events (PreToolUse / PostToolUse / Stop). Unknown events are validated with the same shape contract.</li>\n<li>Performance budget: NFR-PERF-02 (median \u2264 50 ms per call).</li>\n<li>Error format: FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104. The <code>field_name</code> attribute on raised errors carries an RFC 6901 JSON Pointer.</li>\n<li>Inline-skill-frontmatter hooks are an extension surface \u2014 the inner skill is reachable via <span class=\"name\">SkillsLibrary</span> keywords passed the <code>inline_skill</code> dict directly.</li>\n</ul>", "shortdoc": "Parses a Claude Code ``settings.json`` hook configuration.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/hooks/library.py", "lineno": 66}, {"name": "Get Cost Total", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns total provider-reported USD cost (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (USD). Single run: the run's <code>cost_usd</code>. Multi-trial: sum across trials. Empty list \u2192 <code>0.0</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <code>mcp_coverage<span class=\"name\">`-gated. Returns </span>`0.0</code> on the Mock provider; non-zero on real adapters per Story 8a.1 (real adapters use <code>total_cost_usd</code> not <code>cost_usd</code>).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${cost_usd} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${result}\nShould Be True    ${cost_usd} &lt; 0.10                                      # Single-shot cost cap $0.10.\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${total_cost} =    <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>    ${results}                         # Cohort cost rollup.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the cost metric.</li>\n<li>Mock-provider runs return <code>0.0</code> cost; real adapters surface the provider's reported cost.</li>\n<li>Story 8a.1 v1 HIGH-1 ratified <code>total_cost_usd</code> as the canonical real-adapter key.</li>\n<li>Sibling keywords: <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns total provider-reported USD cost (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 419}, {"name": "Get Effective Config", "args": [{"name": "setting", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "setting: str | None = None"}], "returnType": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "doc": "<p>Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 two-form return: no-arg \u2192 <code>dict[str, Any]</code> of resolved values (Story 1a.6 ratified shape, backwards-compat with tier-1 + smoke tests); <code>setting=&lt;key&gt;</code> \u2192 <code>ConfigValue(value, source)</code> for that single setting (FR41 L1563). <code>source</code> is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>setting</code></td>\n<td>Optional config-key name (e.g., <code>\"max_cost_usd\"</code>). When <code>None</code> (default), returns the full <code>dict[str, Any]</code>. When set, returns the single <code>ConfigValue</code> for that key.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>setting</code> is set but not a known config key (with a sorted list of known keys in the message).</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0    telemetry=False\n${config} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>\nShould Be Equal As Numbers    ${config}[max_cost_usd]    5.0\nShould Be Equal    ${config}[telemetry]    ${FALSE}\n${cost_setting} =    <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a>    setting=max_cost_usd\nShould Be Equal As Numbers    ${cost_setting.value}    5.0\nShould Be Equal    ${cost_setting.source}    init_arg\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the ConfigValue surface; FR42 ratifies the 9 settings.</li>\n<li>Story 4.3 DF-4.3-S1 carry-over: full <code>dict[str, ConfigValue]</code> migration of the no-arg form is Phase-1.5.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a> for the FR41-compliant full-surface form.</li>\n</ul>", "shortdoc": "Returns the resolved AgentEval configuration as a dict OR a single ConfigValue (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 409}, {"name": "Get Effective Config With Provenance", "args": [], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "ConfigValue", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns the full settings map with per-key provenance as a <code>dict[str, ConfigValue]</code> (PRD FR41).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 FR41-compliant surface. Each <code>ConfigValue</code> carries <code>value</code> + <code>source</code> per FR41 L1563. Source is one of <code>\"init_arg\"</code> / <code>\"env\"</code> / <code>\"dotenv\"</code> / <code>\"default\"</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td>(none)</td>\n<td>Returns the full settings map; no arguments.</td>\n</tr>\n</table>\n<p>Defensive shallow-copy of the underlying provenance dict \u2014 caller mutations don't propagate to the Library's internal state.</p>\n<p>Example:</p>\n<pre>\nLibrary    AgentEval    max_cost_usd=5.0\n${settings} =    <a href=\"#Get%20Effective%20Config%20With%20Provenance\" class=\"name\">Get Effective Config With Provenance</a>\n${cost} =    Set Variable    ${settings}[max_cost_usd]\nShould Be Equal As Numbers    ${cost.value}    5.0\nShould Be Equal    ${cost.source}    init_arg                              # Constructor kwarg won.\n${temp} =    Set Variable    ${settings}[default_temperature]\nShould Be Equal    ${temp.source}    default                               # Not overridden \u2014 uses FR42 default.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR41 ratifies the <code>dict[str, ConfigValue]</code> shape.</li>\n<li>This is the FR41-compliant surface DF-4.3-S1 will migrate <code>Get Effective Config</code> (no-arg) to once tier-1 tests update.</li>\n<li>Sibling keyword: <a href=\"#Get%20Effective%20Config\" class=\"name\">Get Effective Config</a> for the simpler <code>dict[str, Any]</code> or per-setting form.</li>\n</ul>", "shortdoc": "Returns the full settings map with per-key provenance as a ``dict[str, ConfigValue]`` (PRD FR41).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 529}, {"name": "Get Keyword Tier", "args": [{"name": "keyword", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the determinism-tier annotation for an RF keyword (PRD FR30a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int \u2208 {1, 2, 3}</code>. Walks the composed DynamicCore keyword registry + top-level methods to resolve the verbatim RF name to its <code>_agenteval_tier</code> integer via the <code>@tier(N)</code> decorator chain.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>Verbatim RF keyword name (e.g., <code>\"Send Prompt\"</code>, <code>\"Stat.Run N Times\"</code>, <code>\"Get Effective Config\"</code>).</td>\n</tr>\n</table>\n<p>Returns the wrapper's own tier, not the wrapped keyword's tier \u2014 e.g., <code>Stat.Run N Times</code> returns <code>3</code> (fan-out runner tier) per epic AC-5 + Story 6.3 D-14 amendment. The runner's tier governs the <code>@guarded_fanout</code> enforcement model, independent of the wrapped keyword's own classification.</p>\n<p>Raises <code>ValueError</code> when the keyword is not found in the composed library (with a sorted list of known keywords in the message), OR when the keyword has no <code>@tier(N)</code> annotation, OR when the annotated tier is outside <code>{1, 2, 3}</code> (defensive range check per Story 6.3 code-review HIGH-\u03c0 fix).</p>\n<p>Example:</p>\n<pre>\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Get Tool Call Count\nShould Be Equal As Integers    ${tier}    1                                # Tier-1 deterministic metric.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Send Prompt\nShould Be Equal As Integers    ${tier}    2                                # Tier-2 stochastic single-shot.\n${tier} =    <a href=\"#Get%20Keyword%20Tier\" class=\"name\">Get Keyword Tier</a>    Stat.Run N Times\nShould Be Equal As Integers    ${tier}    3                                # Tier-3 fan-out runner.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR30a ratifies the tier-introspection contract; AC-6.3.7 establishes the DynamicCore walk.</li>\n<li>Story 6.3 D-14 amendment: fan-out runner reports its own tier (3), not the wrapped keyword's tier.</li>\n<li>Sibling keywords: every <span class=\"name\">@tier</span>-decorated keyword in the composed library is introspectable here.</li>\n</ul>", "shortdoc": "Returns the determinism-tier annotation for an RF keyword (PRD FR30a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/__init__.py", "lineno": 462}, {"name": "Get Last Warnings", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[dict]</code>. Each record has the FR62 ratified 5-field shape: <code>warning_type</code> (str \u2014 fully-qualified Python warning class), <code>message</code> (str \u2014 human- readable text), <code>source</code> (str \u2014 emitting subsystem), <code>timestamp</code> (str \u2014 UTC RFC 3339), <code>remediation</code> (str | None \u2014 actionable advice).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test via the listener context; returns <code>[]</code> if no test is bound. <code>\"all\"</code> \u2014 union across every per-test buffer in the process, sorted by <code>timestamp</code> ascending. Any other value is treated as a specific test_id (returns the named buffer or <code>[]</code> if absent).</td>\n</tr>\n</table>\n<p>Defensive copy of records. Never raises \u2014 buffer-read failures fall back to <code>[]</code>.</p>\n<p>Example:</p>\n<pre>\n@{warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>\nLength Should Be    ${warnings}    0                                                   # Clean run: zero warnings.\n@{all_warnings} =    <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>    test_id=all\nFOR    ${w}    IN    @{all_warnings}\n    Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR62 ratifies the 5-field <code>WarningRecord</code> shape.</li>\n<li>Story 5.4 ratified the per-test buffer + <code>\"all\"</code> aggregation contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> \u2014 companion trace-store accessors.</li>\n</ul>", "shortdoc": "Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 64}, {"name": "Get Latency", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns mean turn-level latency in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). When the run has no <code>tool_calls</code>, falls back to <code>result.latency_seconds * 1000.0</code>. Multi-trial: union-of- tool-calls mean \u2014 all per-tool-call latencies from all trials are flattened into one list before <code>statistics.mean()</code> is taken. Mean-of-per-run-means is a statistical anti-pattern (under-weights runs with more tool calls); union-then-mean is the operator-intuitive default per Story 6.1 code-review.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${latency_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${result}\nShould Be True    ${latency_ms} &lt; 2000                                    # Mean turn latency under 2 seconds.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the latency metric \u2014 per-tool-call resolution preferred over per-run.</li>\n<li>Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).</li>\n<li>Sibling keyword: <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a> for tail-latency tracking.</li>\n<li>Provider-reported scalar \u2014 observer-independent per AC-6.1.1.</li>\n</ul>", "shortdoc": "Returns mean turn-level latency in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 355}, {"name": "Get Latency P95", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the P95 latency across tool calls in milliseconds (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> (ms). AC-6.1.8 boundary conditions: 0 tool_calls \u2192 <code>0.0</code>; 1 tool_call \u2192 that single latency; \u22652 \u2192 <code>statistics.quantiles(n=100)[94]</code>. Multi-trial: P95 across the union of all tool_calls' latencies.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 NOT <span class=\"name\">`mcp_coverage</span>`-gated.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n@{results} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}\n${p95_ms} =    <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>    ${results}\n${mean_ms} =    <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>    ${results}\nShould Be True    ${p95_ms} &gt;= ${mean_ms}                                 # P95 \u2265 mean by definition.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the P95 metric \u2014 tail-latency tracking complements <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> mean.</li>\n<li>AC-6.1.8 boundary conditions cover empty / single-call edge cases.</li>\n<li>Sibling keywords: <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a> for mean; <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> to generate multi-trial input.</li>\n</ul>", "shortdoc": "Returns the P95 latency across tool calls in milliseconds (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 389}, {"name": "Get Run Manifest", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "Union", "typedoc": null, "nested": [{"name": "RunManifest", "typedoc": null, "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "doc": "<p>Returns the in-memory 7-field <code>RunManifest</code> for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>RunManifest | None</code>. <code>None</code> when <code>test_id=\"current\"</code> and no test is bound (Tier-1 sibling-consistency with <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> / <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> / <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a> non-raising contracts). The in-memory manifest is the <b>*ratified 7-field shape*</b> (<code>library_version</code>, <code>test_id</code>, <code>suite_id</code>, <code>redaction_policy_hash</code>, <code>started_at</code>, <code>ended_at</code>, <code>agenteval_tier_breakdown</code>) \u2014 NOT the Story-5.3-extended operational metadata dict (which lives in the JSON sidecar at <code>&lt;output_dir&gt;/agenteval/manifest__&lt;suite&gt;__&lt;test&gt;.json</code>).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>None</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim \u2014 that accessor's <code>ValueError</code> propagates if the explicit id resolves to None per Story 1b.2 semantics.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n${manifest} =    <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>\nShould Not Be Equal    ${manifest}    ${NONE}\nShould Not Be Empty    ${manifest.library_version}\nLength Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li>7-field shape ratified at Story 1b.2 per FR39.</li>\n<li>Story 5.5 code-review 2-way HIGH-F established the <code>None</code> (not raise) contract on no-bound-test current path.</li>\n<li>For the Story-5.3-extended operational shape, read the JSON sidecar directly.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>, <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>, <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 178}, {"name": "Get Spans", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ReadableSpan", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ReadableSpan]</code> in chronological order by <code>start_time</code>. Empty list is a valid state (test ran without emitting spans). Thin keyword wrapper around the <code>_kernel/trace_store.get_run_spans</code> projection accessor.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) \u2014 resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Example:</p>\n<pre>\n@{spans} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>\nShould Not Be Empty    ${spans}\nFOR    ${span}    IN    @{spans}\n    ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}\n    Log    ${span.name} took ${duration_ns} ns\nEND\n@{spans_specific} =    <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a>    test_id=My Suite.Specific Test\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.</li>\n<li>Story 5.5 code-review 3-way HIGH-A established the no-bound-test \u2192 <code>[]</code> non-raising contract.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a> (projection over execute_tool spans); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a> (resource-attribute projection); <a href=\"#Get%20Last%20Warnings\" class=\"name\">Get Last Warnings</a>.</li>\n</ul>", "shortdoc": "Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 98}, {"name": "Get Token Usage", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "Usage", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Returns the agent's token usage as a <code>Usage</code> dataclass (PRD FR22).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>Usage(input_tokens, output_tokens, cached_input_tokens)</code>. Single run: the run's own usage. Multi-trial: sum per field. Empty list \u2192 <code>Usage(0, 0, 0)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Provider-reported scalar \u2014 observer-independent. NOT <span class=\"name\">`mcp_coverage</span>`-gated (PRD FR22 + AC-6.1.1).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${usage} =    <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>    ${result}\nShould Be True    ${usage.input_tokens} &gt; 0\nShould Be True    ${usage.output_tokens} &gt; 0\nLog    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR22 ratifies the four usage metrics \u2014 <a href=\"#Get%20Token%20Usage\" class=\"name\">Get Token Usage</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>, <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a> \u2014 all observer-independent per AC-6.1.1.</li>\n<li><code>Usage</code> is a frozen dataclass; field validation ensures non-negative counts.</li>\n<li>Sibling keywords: <a href=\"#Get%20Cost%20Total\" class=\"name\">Get Cost Total</a>, <a href=\"#Get%20Latency\" class=\"name\">Get Latency</a>, <a href=\"#Get%20Latency%20P95\" class=\"name\">Get Latency P95</a>.</li>\n</ul>", "shortdoc": "Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 324}, {"name": "Get Tool Call Count", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "doc": "<p>Returns the number of tool calls made by the agent (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>int</code>. Single run: <code>len(result.tool_calls)</code>. Multi-trial: sum across trials.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial sum aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code> (default-deny per FR42).</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${count} =    <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a>    ${result}\nShould Be Equal As Integers    ${count}    3\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42 \u2014 opt out via <code>AgentEval(allow_external_mcp_blind=True)</code>.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a> for the ordered names list.</li>\n</ul>", "shortdoc": "Returns the number of tool calls made by the agent (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 92}, {"name": "Get Tool Call Names", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns tool-call names in chronological order (PRD FR19).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 duplicates preserved per FR19 verbatim (\"list[str] (preserving order)\"). Single run: chronological list. Multi-trial: union preserving order-of-first-appearance.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code> for multi-trial union aggregation.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n@{names} =    <a href=\"#Get%20Tool%20Call%20Names\" class=\"name\">Get Tool Call Names</a>    ${result}\nShould Contain    ${names}    web_search\nShould Be Equal    ${names}[0]    web_search                              # First tool called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> for the count; <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> for expected-set comparison.</li>\n</ul>", "shortdoc": "Returns tool-call names in chronological order (PRD FR19).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 132}, {"name": "Get Tool Calls", "args": [{"name": "test_id", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "current", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "test_id: str = current"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "ToolCallTrace", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Returns <code>ToolCallTrace</code> records projected from the trace store (Story 5.5 AC-5.5.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>list[ToolCallTrace]</code>. Thin keyword wrapper around <code>_kernel/trace_store.get_tool_calls</code>. Mirrors the source-filtering semantics of the Story 1b.2 accessor (no per-call source filter exposed at the RF surface; consumers filter the returned list themselves).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>test_id</code></td>\n<td><code>\"current\"</code> (default) resolves to the bound test; returns <code>[]</code> if no test is bound. Any other value is forwarded to the projection accessor verbatim.</td>\n</tr>\n</table>\n<p>Returns <code>list[ToolCallTrace]</code> frozen dataclasses (Story 1b.2 shape): each record carries <code>name</code>, <code>args</code>, <code>result</code>, <code>error</code>, <code>latency_ms</code>, <code>source</code>, <code>gen_ai_tool_call_id</code>, <code>sequence_index</code>.</p>\n<p>Example:</p>\n<pre>\n@{tool_calls} =    <a href=\"#Get%20Tool%20Calls\" class=\"name\">Get Tool Calls</a>\nShould Not Be Empty    ${tool_calls}\nShould Be Equal    ${tool_calls}[0].name    web_search\nShould Be Equal As Integers    ${tool_calls}[0].sequence_index    0\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 5.5 AC-5.5.1 ratifies the keyword wrapper.</li>\n<li><span class=\"name\">ToolCallTrace</span> shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.</li>\n<li>Sibling keywords: <a href=\"#Get%20Spans\" class=\"name\">Get Spans</a> (full span list); <a href=\"#Get%20Tool%20Call%20Count\" class=\"name\">Get Tool Call Count</a> (metrics-library count over <span class=\"name\">AgentRunResult</span>); <a href=\"#Get%20Run%20Manifest\" class=\"name\">Get Run Manifest</a>.</li>\n</ul>", "shortdoc": "Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/telemetry/library.py", "lineno": 139}, {"name": "Get Tool Hit Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-hit rate <code>|expected \u2229 observed| / |expected|</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Empty <code>expected_tools</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: union-of-observed against expected_tools.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${hit_rate} =    <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a>    ${result}    ${{['web_search', 'fetch']}}\nShould Be True    ${hit_rate} &gt;= 0.5                                      # At least half of expected tools were called.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Sibling keywords: <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a> (calls NOT in expected set); <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a> (errors / total).</li>\n</ul>", "shortdoc": "Returns the tool-hit rate ``|expected \u2229 observed| / |expected|`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 178}, {"name": "Get Tool Success Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the tool-success rate <code>non-error / total</code> (PRD FR20).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention. Multi-trial: aggregate across all per-trial tool calls.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${success_rate} =    <a href=\"#Get%20Tool%20Success%20Rate\" class=\"name\">Get Tool Success Rate</a>    ${result}\nShould Be True    ${success_rate} &gt;= 0.8                                  # At least 80% of tool calls succeeded.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n<li>Each <code>ToolCallTrace</code> has an <code>error</code> field \u2014 non-None counts as a failure.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (vs expected set); <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>.</li>\n</ul>", "shortdoc": "Returns the tool-success rate ``non-error / total`` (PRD FR20).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 224}, {"name": "Get Unnecessary Call Rate", "args": [{"name": "result", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult | list[AgentRunResult]"}, {"name": "expected_tools", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected_tools: list[str]"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Returns the unnecessary-call rate <code>not_in_expected / total</code> (PRD FR21).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 returns <code>float</code> in <code>[0, 1]</code>. Zero <code>tool_calls</code> returns <code>0.0</code> per AC-6.1.8 vacuous-truth convention.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>Single <code>AgentRunResult</code> OR <code>list[AgentRunResult]</code>.</td>\n</tr>\n<tr>\n<td><code>expected_tools</code></td>\n<td>List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary.</td>\n</tr>\n</table>\n<p>Raises <code>IncompleteTraceError</code> per FR37 when any input run carries <code>mcp_coverage=\"external_mixed\"</code> AND the Library was constructed with <code>allow_external_mcp_blind=False</code>.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected tool-call surface):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6\n${noise} =    <a href=\"#Get%20Unnecessary%20Call%20Rate\" class=\"name\">Get Unnecessary Call Rate</a>    ${result}    ${{['web_search']}}\nShould Be True    ${noise} &lt;= 0.2                                         # At most 20% of calls were off-task.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR21 ratifies the unnecessary-rate formula \u2014 quantifies \"noise\" tool calls beyond the expected set.</li>\n<li>AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls \u2192 0.0).</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Hit%20Rate\" class=\"name\">Get Tool Hit Rate</a> (calls that ARE in expected set).</li>\n<li>mcp_coverage gating per FR37 + FR42.</li>\n</ul>", "shortdoc": "Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/metrics/library.py", "lineno": 271}, {"name": "Judge.Calibrate Rubric", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "calibration_set", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "calibration_set: str | Path"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "CalibrationReport", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Runs the judge against a labeled calibration set and returns a <span class=\"name\">CalibrationReport</span> (Story 12.2).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 N single-shot LLM calls (one per calibration row) against the configured <code>judge_adapter</code>. Cohen's kappa over binarized judge-pass / human-pass labels at the rubric's threshold; <code>passes_hard_fail</code> is True iff <code>kappa &gt;= 0.7</code> per <span class=\"name\">architecture.md</span> L199 agentguard-borrowed calibration discipline. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>calibration_set</code></td>\n<td>Path to a YAML calibration set with <span class=\"name\">rows:</span> list of <span class=\"name\">{prompt, response, human_label}</span>.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug; defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier; forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Returns <code>CalibrationReport</code> with: <code>cohen_kappa</code> (float; <code>nan</code> if zero-variance), <code>passes_hard_fail</code> (kappa &gt;= 0.7), <code>threshold_tuning</code> (precision/recall/F1 sweep), <code>recommended_threshold</code> (F1-maximizing), <code>systematic_bias_diagnostics</code> (human-readable bullets), <code>total_cost_usd</code>, <code>total_latency_seconds</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>InvalidCalibrationSetError</code> on calibration set parse failure. Raises <code>JudgeOutputParseError</code> if any per-row judge invocation returns malformed JSON.</p>\n<p>Example:</p>\n<pre>\n${report} =    <a href=\"#Judge.Calibrate%20Rubric\" class=\"name\">Judge.Calibrate Rubric</a>    rubric=${CURDIR}/rubrics/skill-quality.md    calibration_set=${CURDIR}/calibration/skill-quality.yaml    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${report.passes_hard_fail}\nLog    Cohen's kappa = ${report.cohen_kappa}\nLog    Recommended threshold = ${report.recommended_threshold}\n</pre>\n<p>Notes:</p>\n<ul>\n<li><span class=\"name\">KAPPA_HARD_FAIL_THRESHOLD = 0.7</span> per <span class=\"name\">architecture.md</span> L199.</li>\n<li>Phase-1: single-shot per row; multi-turn / multi-judge ensemble is DF-12.2-S1 carry-over.</li>\n<li>Phase-1: Cohen's kappa only; Krippendorff's alpha is DF-12.2-S1 carry-over.</li>\n</ul>", "shortdoc": "Runs the judge against a labeled calibration set and returns a `CalibrationReport` (Story 12.2).", "tags": ["agenteval"], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 187}, {"name": "Judge.Get Score", "args": [{"name": "", "type": null, "defaultValue": null, "kind": "NAMED_ONLY_MARKER", "required": false, "repr": "*"}, {"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "result: AgentRunResult"}, {"name": "rubric", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}, {"name": "JudgeRubric", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "NAMED_ONLY", "required": true, "repr": "rubric: str | Path | JudgeRubric"}, {"name": "judge_adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "NAMED_ONLY", "required": false, "repr": "judge_adapter: str = generic"}, {"name": "judge_model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "NAMED_ONLY", "required": false, "repr": "judge_model: str | None = None"}, {"name": "adapter_kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**adapter_kwargs: Any"}], "returnType": {"name": "JudgeScore", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Evaluates an <span class=\"name\">AgentRunResult</span> against a Markdown rubric using an LLM judge (PRD FR48).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 single-shot LLM call against the configured <span class=\"name\">judge_adapter</span> (default <span class=\"name\">\"generic\"</span> LiteLLM-backed). LLM-deterministic per the determinism-contract.md <span class=\"name\">@tier(2)</span> contract when invoked with <span class=\"name\">seed + temperature=0</span>. Wraps <span class=\"name\">@guarded_fanout</span> cost+runtime guardrails per ADR-015.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td>The <span class=\"name\">AgentRunResult</span> to evaluate. Reads <code>result.response_text</code> for the agent's output.</td>\n</tr>\n<tr>\n<td><code>rubric</code></td>\n<td>Path to a Markdown rubric file (<span class=\"name\">.md</span>) OR a pre-loaded <span class=\"name\">JudgeRubric</span> instance.</td>\n</tr>\n<tr>\n<td><code>judge_adapter</code></td>\n<td>Adapter slug to resolve via <span class=\"name\">agenteval.coding_agents</span> entry-points. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>judge_model</code></td>\n<td>Model identifier for the judge adapter (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>). Forwarded to the adapter's <span class=\"name\">run(model=...)</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**adapter_kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs (e.g., <code>temperature=0.0</code>, <code>seed=42</code>).</td>\n</tr>\n</table>\n<p>Returns <code>JudgeScore</code> with: <code>numeric_score</code> (0-10), <code>pass_threshold_met</code> (vs rubric threshold), <code>reasoning</code> (LLM's narrative explanation), <code>criteria_breakdown</code> (per-criterion sub-scores), <code>cost_usd</code>.</p>\n<p>Raises <code>InvalidJudgeRubricError</code> on rubric parse failure. Raises <code>JudgeOutputParseError</code> when the LLM response is not valid JSON OR is missing required fields OR <code>numeric_score</code> is outside <code>[0.0, 10.0]</code>.</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find the largest file    adapter=generic    model=anthropic/claude-sonnet-4-6\n${score} =    <a href=\"#Judge.Get%20Score\" class=\"name\">Judge.Get Score</a>    result=${result}    rubric=${CURDIR}/rubrics/skill-quality.md    judge_adapter=generic    judge_model=anthropic/claude-sonnet-4-6\nShould Be True    ${score.pass_threshold_met}\nShould Be True    ${score.numeric_score} &gt;= 7.0\nLog    Reasoning: ${score.reasoning}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR48 ratifies the keyword + rubric calibration discipline.</li>\n<li>Tier-2 LLM-deterministic per <span class=\"name\">determinism-contract.md</span>; cost guardrails per ADR-015.</li>\n<li><span class=\"name\">JudgeScore</span> shape ratified Story 12.1 AC-12.1.2 per architecture L1316.</li>\n<li>Phase-1 single-shot LLM call; multi-turn chain-of-thought is DF-12.1-S2 carry-over.</li>\n</ul>", "shortdoc": "Evaluates an `AgentRunResult` against a Markdown rubric using an LLM judge (PRD FR48).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/judge/library.py", "lineno": 117}, {"name": "Load Scenario", "args": [{"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "scenario: str"}], "returnType": {"name": "Scenario", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Loads + validates a scenario YAML without executing it.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file read + YAML parse + schema validation. Returns the parsed <code>Scenario</code> dataclass without dispatching to any adapter \u2014 useful for <code>.robot</code> tests that assert on scenario metadata or pre-flight-check scenarios before a <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidScenarioYAMLError</code> on parse failure or schema violation. The error's <code>field_name</code> attribute pinpoints the offending field per FR59.</p>\n<p>Example:</p>\n<pre>\n${scenario} =    <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a>    ${CURDIR}/scenarios/web-search.yaml\nShould Be Equal    ${scenario.agent}    web-search-agent\nShould Be Equal    ${scenario.model}    anthropic/claude-sonnet-4-6\nLength Should Be    ${scenario.evals}    5\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the scenario YAML schema; see <span class=\"name\">Scenario</span> dataclass in <span class=\"name\">scenarios/schema.py</span>.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> (Tier-3) for dispatch + execution.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n</ul>", "shortdoc": "Loads + validates a scenario YAML without executing it.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 330}, {"name": "Run Scenario", "args": [{"name": "adapter", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "_Unset", "typedoc": null, "nested": [], "union": false}], "union": true}, "defaultValue": "_UNSET", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str | _Unset = _UNSET"}, {"name": "scenario", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "scenario: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Executes a scenario YAML file's <code>evals[]</code> against an adapter (PRD FR15).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 loads the scenario YAML via <code>load_scenario()</code>, validates against the <code>Scenario</code> schema, then dispatches each eval's prompt to <code>adapter.run()</code> <code>repeat</code> times. Returns a flat <code>list[AgentRunResult]</code> of length <code>sum(eval.repeat for eval in scenario.evals)</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Per-scenario <code>agent:</code> field in the YAML overrides this kwarg per FR15 (\"scenario YAML specifies agent\" \u2014 YAML beats default but not explicit kwarg).</td>\n</tr>\n<tr>\n<td><code>scenario</code></td>\n<td>Filesystem path to the scenario YAML file.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code>. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are split between adapter constructor + <code>run()</code> per the same signature-introspection rule as <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>. Scenario-YAML <code>model:</code> / <code>provider:</code> fields inject into the merged kwargs unless the caller already passed them.</p>\n<p>Raises <code>InvalidScenarioYAMLError</code> on YAML parse / schema failure, <code>AdapterDiscoveryError</code> on unknown adapter name, and <code>NotImplementedError</code> on non-empty comma-separated <code>mcp_servers</code> (Phase-1 DF-4.3-S2 carve-out).</p>\n<p>Example:</p>\n<pre>\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    scenario=${CURDIR}/scenarios/web-search.yaml\nLength Should Be    ${results}    5\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${results}[0]    ${{['web_search', 'fetch', 'summarize']}}\n@{results} =    <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a>    adapter=claude-code-cli    scenario=${CURDIR}/scenarios/build.yaml\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR15 ratifies the multi-eval orchestration contract.</li>\n<li>FR41 precedence resolution: explicit kwarg &gt; scenario YAML &gt; library default.</li>\n<li>Sibling keyword: <a href=\"#Load%20Scenario\" class=\"name\">Load Scenario</a> (Tier-1) to validate the YAML without executing.</li>\n<li>Carry-overs: DF-4.3-S2 (mcp_servers name resolution), DF-4.3-S4 (multi-turn threading).</li>\n</ul>", "shortdoc": "Executes a scenario YAML file's ``evals[]`` against an adapter (PRD FR15).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 215}, {"name": "Send Prompt", "args": [{"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "prompt", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "prompt: str = "}, {"name": "mcp_servers", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_servers: dict[str, Any] | str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Executes a single-shot prompt against a coding-agent adapter (PRD FR14).</p>\n<p>[Tier 2 \u2014 Stochastic Single-Shot] \u2014 invokes the named adapter's <code>run()</code> method per the <span class=\"name\">CodingAgentAdapter</span> Protocol. Returns an <code>AgentRunResult</code> carrying <code>response_text</code>, <code>tool_calls</code>, <code>usage</code>, <code>metadata</code> (with <code>completeness</code> + <code>mcp_coverage</code>), <code>cost_usd</code>, <code>latency_seconds</code>, and <code>trace_id</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name registered via the <code>agenteval.coding_agents</code> entry-points group. Defaults to <code>\"generic\"</code> (LiteLLM-backed).</td>\n</tr>\n<tr>\n<td><code>prompt</code></td>\n<td>Prompt text to send to the agent.</td>\n</tr>\n<tr>\n<td><code>mcp_servers</code></td>\n<td>Optional <code>dict[str, ServerHandle]</code> of attached MCP servers. Phase-1: comma-separated name strings raise <code>NotImplementedError</code> (DF-4.3-S2 \u2014 name resolution to handles deferred).</td>\n</tr>\n</table>\n<p>Additional keyword arguments are forwarded to the adapter \u2014 caller kwargs that match the adapter's <code>__init__</code> signature flow to construction; the rest flow to <code>run()</code>. Useful for <code>model=\"anthropic/claude-sonnet-4-6\"</code>, <code>temperature=0.5</code>, etc.</p>\n<p>Raises <code>AdapterDiscoveryError</code> when the <code>adapter</code> name is not registered. Raises <code>NotImplementedError</code> on comma-separated <code>mcp_servers</code> name strings until DF-4.3-S2 lands the name \u2192 handle resolver (pass <code>mcp_servers={'name': handle}</code> directly to forward Phase-1).</p>\n<p>Example:</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Hello, world.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=claude-code-cli    prompt=Run the build.\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    adapter=generic    prompt=Search    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR14 ratifies the single-prompt orchestration contract.</li>\n<li>Adapter discovery per Story 1b.3 + ADR-013 entry-points.</li>\n<li><code>cost_usd</code> is 0.0 on the Mock provider; non-zero on real adapters per Story 8a.1.</li>\n<li>Sibling keyword: <a href=\"#Run%20Scenario\" class=\"name\">Run Scenario</a> for multi-eval YAML-driven dispatch (Tier-3).</li>\n</ul>", "shortdoc": "Executes a single-shot prompt against a coding-agent adapter (PRD FR14).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/orchestration/library.py", "lineno": 127}, {"name": "Stat.Assert Run Determinism", "args": [{"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "expect", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "byte_identical", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "expect: str = byte_identical"}], "returnType": null, "doc": "<p>Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 invokes the wrapped keyword twice with identical inputs and compares via deep-equality. The bit-identical guarantee is scoped to Tier-1 keywords only (FR31a contract); the keyword raises <code>TierViolationError</code> if a Tier-2/3 keyword is passed.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR callable. Same dispatch rules as <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> (string form requires active RF context).</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings.</td>\n</tr>\n<tr>\n<td><code>expect</code></td>\n<td>Comparison mode. Phase-1 supports <code>\"byte_identical\"</code> only; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> deferred to Phase-2.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>expect != \"byte_identical\"</code> (Phase-1 scope). Raises <code>TierViolationError</code> when the wrapped keyword is not Tier-1 \u2014 FR31a is scoped to Tier-1 only. Raises <code>AssertionError</code> on output mismatch with a <span class=\"name\">`redact()</span>`-scrubbed diff per FR38a credential-safety contract.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}\n<a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Get Effective Config\nRun Keyword And Expect Error    TierViolationError*    <a href=\"#Stat.Assert%20Run%20Determinism\" class=\"name\">Stat.Assert Run Determinism</a>    keyword=Send Prompt\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> + <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for statistical assertions instead.</li>\n<li>Diff redaction per FR38a + Story 5.3 \u2014 credentials in args / output don't leak into RF logs.</li>\n<li>Story 6.3 ratifies <code>\"byte_identical\"</code> as the Phase-1 contract; <code>\"approximate\"</code> + <code>\"schema_identical\"</code> are Phase-2 work-items.</li>\n</ul>", "shortdoc": "Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 297}, {"name": "Stat.Bootstrap Confidence Interval", "args": [{"name": "samples", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "samples: list[KeywordRun] | list[float]"}, {"name": "seed", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "seed: int"}, {"name": "statistic", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[list[float]]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "statistic: Callable[[list[float]], float] | None = None"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}, {"name": "alpha", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.05", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "alpha: float = 0.05"}, {"name": "n_resamples", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "10000", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "n_resamples: int = 10000"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 given fixed <code>samples</code> + <code>seed</code>, the result is bit-identical across calls (FR31a guarantee). Returns <code>(ci_lower, ci_upper)</code> tuple at the <code>(1 - alpha) * 100%</code> percentile level (default 95% CI).</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>samples</code></td>\n<td>Either <code>list[KeywordRun]</code> (then <code>predicate</code> extracts floats) OR <code>list[float]</code> (predicate ignored). Mixed-type lists raise <code>TypeError</code> \u2014 homogeneous types required.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>REQUIRED <code>int</code> seed for the numpy <code>Generator</code>. No default \u2014 the <code>@tier(1)</code> bit-identical guarantee (FR31a) requires a fixed seed. Operators wanting OS-entropy randomness must pass an explicit seed (e.g., <code>seed=random.randrange(2**32)</code>).</td>\n</tr>\n<tr>\n<td><code>statistic</code></td>\n<td><code>Callable[[list[float]], float]</code> whose CI is computed. Default <code>None</code> \u2192 <code>statistics.mean</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], float]</code> value-extractor (required when <code>samples</code> is <code>list[KeywordRun]</code>).</td>\n</tr>\n<tr>\n<td><code>alpha</code></td>\n<td>Significance level; CI is at <code>(1-alpha)*100%</code> confidence. Must satisfy <code>0.0 &lt; alpha &lt; 1.0</code>. Default <code>0.05</code>.</td>\n</tr>\n<tr>\n<td><code>n_resamples</code></td>\n<td>Number of bootstrap resamples (with replacement). Must be <code>&gt;= 100</code>. Default <code>10_000</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy unavailable; <code>ValueError</code> when <code>samples</code> is empty / <code>alpha</code> is out of range / <code>n_resamples &lt; 100</code> / <code>predicate</code> is missing for a <code>list[KeywordRun]</code> input. Raises <code>TypeError</code> when <code>samples</code> mixes <code>KeywordRun</code> and raw floats (homogeneous types required).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${cost_pred} =    Evaluate    lambda r: r.result.cost_usd\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Bootstrap%20Confidence%20Interval\" class=\"name\">Stat.Bootstrap Confidence Interval</a>    ${runs}    seed=42    predicate=${cost_pred}\nShould Be True    ${ci_lo} &lt;= ${ci_hi}                                    # CI bounds well-ordered.\n${median_stat} =    Evaluate    statistics.median    modules=statistics\n${med_lo}    ${med_hi} =    <a href=\"#Stat.Bootstrap%20Confidence%20Interval\" class=\"name\">Stat.Bootstrap Confidence Interval</a>    ${runs}    seed=42    statistic=${median_stat}    predicate=${cost_pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29c ratifies the <code>(lo, hi)</code> tuple return type \u2014 preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.</li>\n<li>Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).</li>\n<li>Math reference: <code>scipy.stats.bootstrap(samples, statistic, rng=numpy.random.default_rng(seed), method=\"percentile\")</code>. The local implementation uses the same <code>numpy.random.default_rng(seed)</code> source so reference equivalence is verifiable.</li>\n<li>Mandatory <code>seed</code> preserves the <code>@tier(1)</code> FR31a bit-identical guarantee (Story 13.1 code-review HIGH-C catch, Opus tier review).</li>\n<li>Resampling result determinism is pinned to a single <code>numpy.random.Generator</code> algorithm (PCG64). Major numpy ABI changes that retire PCG64 would shift CI bounds; track via <span class=\"name\">`_TESTED_UP_TO</span>`-style pinning in Phase-2 if numpy 3.x ships a different default generator.</li>\n</ul>", "shortdoc": "Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 509}, {"name": "Stat.Cliff Delta", "args": [{"name": "runs_a", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_a: list[KeywordRun]"}, {"name": "runs_b", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_b: list[KeywordRun]"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form Cliff (1993) brute-force formula. Returns <code>float \u2208 [-1.0, 1.0]</code>. Positive values indicate <code>runs_a</code> tends to produce larger values; negative values indicate <code>runs_b</code> tends to produce larger values.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs_a</code></td>\n<td><code>list[KeywordRun]</code> \u2014 first sample.</td>\n</tr>\n<tr>\n<td><code>runs_b</code></td>\n<td><code>list[KeywordRun]</code> \u2014 second sample.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>REQUIRED <code>Callable[[KeywordRun], float]</code> value-extractor. <code>None</code> raises <code>ValueError</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy unavailable; <code>ValueError</code> when <code>predicate</code> is <code>None</code> OR either sample is empty.</p>\n<p>Example:</p>\n<pre>\n${latency_pred} =    Evaluate    lambda r: r.latency_seconds\n${delta} =    <a href=\"#Stat.Cliff%20Delta\" class=\"name\">Stat.Cliff Delta</a>    ${runs_a}    ${runs_b}    predicate=${latency_pred}\nShould Be True    abs(${delta}) &gt; 0.474                                  # Large effect per Romano-Coraggio-Smith conventions.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29b ratifies the scalar <code>float</code> return type (NOT a dataclass) \u2014 preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.</li>\n<li>Math: <code>\u03b4 = (#{a&gt;b} - #{a&lt;b}) / (n_a * n_b)</code>; ties contribute 0.</li>\n<li>Complexity: <code>O(n_a * n_b)</code>. Fine for typical n \u2264 100 trials; Phase-2 perf carve-out for n_a + n_b &gt; 1000.</li>\n</ul>", "shortdoc": "Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 463}, {"name": "Stat.Get Pass At K", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}], "returnType": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "doc": "<p>Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form computation of the HumanEval estimator <code>1 - C(n-c, k) / C(n, k)</code>. Returns <code>float \u2208 [0, 1]</code>. Scalar return preserves AssertionEngine compatibility (<code>&gt;=</code> / <code>&lt;=</code> matchers); CI is a separate paired getter \u2014 see <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Must satisfy <code>1 &lt;= k &lt;= len(runs)</code>.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Default checks <code>r.completeness == \"complete\"</code> per epic AC-2 + Story 6.4 fix-NOW.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k &lt; 1</code>, <code>k &gt; len(runs)</code>, or <code>len(runs) == 0</code>.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${pass_at_1} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=1\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.\n${pred} =    Evaluate    lambda r: r.error is None\n${pass_strict} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5    predicate=${pred}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR27 ratifies the scalar <code>float</code> return type \u2014 no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).</li>\n<li>Default predicate updated by Story 6.4 fix-NOW: <code>completeness == \"complete\"</code> (pre-edit <code>\"full\"</code> was fake-green; <span class=\"name\">AgentRunMetadata._VALID_COMPLETENESS</span> is <code>{\"complete\", \"truncated\", \"partial\"}</code>).</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a> for the Wilson score CI.</li>\n</ul>", "shortdoc": "Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 199}, {"name": "Stat.Get Pass At K Confidence Interval", "args": [{"name": "runs", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs: list[KeywordRun]"}, {"name": "k", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "k: int"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "bool", "typedoc": "boolean", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], bool] | None = None"}, {"name": "confidence", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "0.95", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "confidence: float = 0.95"}], "returnType": {"name": "tuple", "typedoc": "tuple", "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, "doc": "<p>Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Wilson score interval at the given <code>confidence</code> level for the latent per-trial success probability. Returns <code>(ci_lower, ci_upper)</code> tuple of <code>float</code> in <code>[0, 1]</code>. Paired with <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> \u2014 the scalar point estimate plus this CI together satisfy epic AC-2's \"Pass@k with confidence interval\" promise.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs</code></td>\n<td><code>list[KeywordRun]</code> \u2014 typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>.</td>\n</tr>\n<tr>\n<td><code>k</code></td>\n<td>Top-k parameter. Validated for <code>1 &lt;= k &lt;= len(runs)</code> but only used for sanity check \u2014 the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself.</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>Optional <code>Callable[[KeywordRun], bool]</code> for pass/fail classification. Same default as <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>.</td>\n</tr>\n<tr>\n<td><code>confidence</code></td>\n<td>Confidence level in <code>(0, 1)</code>. Defaults to <code>0.95</code>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>k</code> is non-positive or <code>k &gt; n</code> (with <code>n &gt; 0</code> \u2014 empty <code>runs</code> is permitted per the Wilson formula).</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}\n${ci_lo}    ${ci_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5\nShould Be True    0.0 &lt;= ${ci_lo} &lt;= ${ci_hi} &lt;= 1.0                      # CI bounds are well-formed probabilities.\n${ci99_lo}    ${ci99_hi} =    <a href=\"#Stat.Get%20Pass%20At%20K%20Confidence%20Interval\" class=\"name\">Stat.Get Pass At K Confidence Interval</a>    ${runs}    k=5    confidence=0.99\nShould Be True    (${ci99_hi} - ${ci99_lo}) &gt;= (${ci_hi} - ${ci_lo})      # Higher confidence \u2192 wider interval.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.</li>\n<li>PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> for the scalar point estimate.</li>\n</ul>", "shortdoc": "Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 241}, {"name": "Stat.Mann Whitney U", "args": [{"name": "runs_a", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_a: list[KeywordRun]"}, {"name": "runs_b", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "runs_b: list[KeywordRun]"}, {"name": "predicate", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[KeywordRun]", "typedoc": null, "nested": [], "union": false}, {"name": "float", "typedoc": "float", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "predicate: Callable[[KeywordRun], float] | None = None"}], "returnType": {"name": "MannWhitneyResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 closed-form non-parametric test for whether two independent samples were drawn from the same distribution. Returns <code>MannWhitneyResult</code> with U statistic, two-sided p-value, rank-biserial effect size, and sample sizes.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra (scipy + numpy); raises <code>ImportError</code> when invoked without it. The <code>StatsLibrary</code> class itself remains importable without the extra; only this Phase-2 keyword method raises on invocation.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>runs_a</code></td>\n<td><code>list[KeywordRun]</code> \u2014 first sample (typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> against flow A).</td>\n</tr>\n<tr>\n<td><code>runs_b</code></td>\n<td><code>list[KeywordRun]</code> \u2014 second sample (typically the result of <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a> against flow B).</td>\n</tr>\n<tr>\n<td><code>predicate</code></td>\n<td>REQUIRED <code>Callable[[KeywordRun], float]</code> value-extractor producing the numeric quantity to compare (e.g., <code>lambda r: r.latency_seconds</code>). Default <code>None</code> raises <code>ValueError</code> \u2014 no sensible default numeric metric across all <code>KeywordRun</code> shapes. NOTE: distinct from <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>'s boolean predicate.</td>\n</tr>\n</table>\n<p>Raises <code>ImportError</code> when scipy/numpy are unavailable (missing <code>[agenteval-advanced]</code> extra). Raises <code>ValueError</code> when <code>predicate</code> is <code>None</code> OR when either <code>runs_a</code> / <code>runs_b</code> is empty.</p>\n<p>Example:</p>\n<pre>\n@{runs_a} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=claude_code_cli']}}\n@{runs_b} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=codex_cli']}}\n${cost_pred} =    Evaluate    lambda r: r.result.cost_usd\n${mwu} =    <a href=\"#Stat.Mann%20Whitney%20U\" class=\"name\">Stat.Mann Whitney U</a>    ${runs_a}    ${runs_b}    predicate=${cost_pred}\nShould Be True    ${mwu.p_value} &lt; 0.05                                  # Reject the null at \u03b1=0.05.\nShould Be True    abs(${mwu.effect_size_r}) &gt; 0.3                        # Medium-or-larger effect.\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.1 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra.</li>\n<li>PRD FR29a ratifies the <code>MannWhitneyResult</code> dataclass with <code>u_statistic</code> / <code>p_value</code> / <code>effect_size_r</code> + <code>n_a</code> / <code>n_b</code>.</li>\n<li>Math reference: <code>scipy.stats.mannwhitneyu(alternative=\"two-sided\", use_continuity=False)</code>. The returned <code>p_value</code> matches scipy exactly; the returned <code>u_statistic</code> is normalized to <code>min(U1, U2)</code> (smaller-U canonical form) and does NOT match scipy's <code>.statistic</code> directly \u2014 scipy returns <code>U1</code>. Consumers needing scipy's U1 can recover it via <code>U1 = (1 + effect_size_r) * n_a * n_b / 2</code>.</li>\n<li>Effect size: signed rank-biserial <code>r = 2*U1/(n_a*n_b) - 1</code> (where U1 is the M-W U for samples_a); positive r \u2192 samples_a tends to be larger; matches <code>Stat.Cliff Delta</code> sign convention.</li>\n<li>One-sided variants (<code>alternative=\"greater\"<span class=\"name\">`/</span>`\"less\"</code>) deferred to Phase-2 (DF-13.1-S1).</li>\n</ul>", "shortdoc": "Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 407}, {"name": "Stat.Run N Times", "args": [{"name": "n", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "n: int"}, {"name": "keyword", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Callable", "typedoc": null, "nested": [{"name": "...", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "keyword: str | Callable[..., Any]"}, {"name": "keyword_args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "list", "typedoc": "list", "nested": [{"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "keyword_args: dict[str, Any] | list[Any] | None = None"}, {"name": "seed", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "int", "typedoc": "integer", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "seed: int | None = None"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "KeywordRun", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Runs a keyword <code>n</code> times independently and returns the per-trial results (PRD FR26).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 wraps the target keyword in independent trials. Returns <code>list[KeywordRun]</code> of length <code>n</code>. Trial-level errors are re-raised from this keyword \u2014 wrap in <code>Run Keyword And Ignore Error</code> for \"ignore failures\" semantics.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>n</code></td>\n<td>Number of independent trials. Must be <code>&gt;= 1</code>.</td>\n</tr>\n<tr>\n<td><code>keyword</code></td>\n<td>RF keyword name (<code>str</code>) OR a Python callable. String form requires an active RF execution context (resolved via <code>BuiltIn</code>); callable form is useful for pytest unit tests.</td>\n</tr>\n<tr>\n<td><code>keyword_args</code></td>\n<td>Optional <code>dict</code> of kwargs OR <code>list</code> of RF named-arg strings (e.g. <code>{\"adapter\": \"generic\", \"prompt\": \"Hi\"}</code> or <code>[\"adapter=generic\", \"prompt=Hi\"]</code>). <code>None</code> = no args.</td>\n</tr>\n<tr>\n<td><code>seed</code></td>\n<td>Optional <code>int</code> seed; each trial receives <code>seed + trial_index</code> via a <code>seed=</code> kwarg injection so trials are deterministic but distinct. <code>None</code> = OS-entropy seeding per trial.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>n &lt; 1</code>. Raises <code>CostExceededError</code> / <code>RuntimeBudgetExceededError</code> per the <code>@guarded_fanout</code> 3-layer enforcement.</p>\n<p>Example:</p>\n<pre>\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}\n${pass_at_5} =    <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a>    ${runs}    k=5\nShould Be True    ${pass_at_5} &gt;= 0.6\n@{runs} =    <a href=\"#Stat.Run%20N%20Times\" class=\"name\">Stat.Run N Times</a>    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the <code>list[KeywordRun]</code> return type.</li>\n<li>Cost / runtime guardrails per ADR-015 + <span class=\"name\">_kernel/guardrails.py::@guarded_fanout</span>.</li>\n<li>Sibling keyword: <a href=\"#Stat.Get%20Pass%20At%20K\" class=\"name\">Stat.Get Pass At K</a> (Tier-1) consumes the returned list.</li>\n</ul>", "shortdoc": "Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/stats/library.py", "lineno": 113}, {"name": "Tool Call Should Have Occurred", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "tool", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool: str"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: dict[str, Any] | None = None"}, {"name": "match_mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "subset", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "match_mode: str = subset"}], "returnType": null, "doc": "<p>Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 searches all observed <code>tool_calls</code> for one matching <code>tool</code> + (optionally) <code>args</code>. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>tool</code></td>\n<td>Expected tool name (exact-match required).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>Optional dict of expected args. <code>None</code> (default) = name-only match.</td>\n</tr>\n<tr>\n<td><code>match_mode</code></td>\n<td><code>\"subset\"</code> (default \u2014 <code>args</code> is a dict-subset of <code>tc.args</code>; recursive for nested dicts) OR <code>\"exact\"</code> (<code>tc.args == args</code>).</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when <code>match_mode</code> is invalid (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> when no tool call matches.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected <code>web_search</code> call):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"agenteval\"} }}\n<a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a>    ${result}    web_search    args=${{ {\"query\": \"x\"} }}    match_mode=exact\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR24 ratifies the name + args + match-mode contract.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a> for ordered-sequence assertions over multiple calls.</li>\n</ul>", "shortdoc": "Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 162}, {"name": "Trajectory Should Match", "args": [{"name": "result", "type": {"name": "AgentRunResult", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "result: AgentRunResult"}, {"name": "expected", "type": {"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "expected: list[str]"}, {"name": "mode", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "exact", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mode: str = exact"}], "returnType": null, "doc": "<p>Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 four match modes available. Failure messages are <span class=\"name\">`redact()</span>`-scrubbed per FR38a so credentials in tool args don't leak into RF logs.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>result</code></td>\n<td><code>AgentRunResult</code> carrying the observed <code>tool_calls</code>.</td>\n</tr>\n<tr>\n<td><code>expected</code></td>\n<td>List of expected tool names (or regex patterns when <code>mode=\"regex\"</code>).</td>\n</tr>\n<tr>\n<td><code>mode</code></td>\n<td>Match mode: <code>\"exact\"</code> (ordered equality) / <code>\"subsequence\"</code> (ordered, extras allowed between) / <code>\"set\"</code> (unordered set-equality of distinct names) / <code>\"regex\"</code> (each <code>expected[i]</code> is a <code>re.fullmatch</code> pattern against <code>&lt;tool&gt;:&lt;json.dumps(args, sort_keys=True)&gt;</code>). Default <code>\"exact\"</code>.</td>\n</tr>\n</table>\n<p>Set-mode caveat: duplicate names collapse \u2014 <code>[\"a\", \"a\"]</code> set- equals <code>[\"a\"]</code>. Operators wanting multiset semantics (\"exactly N calls of tool X\") should use <code>mode=\"exact\"</code>.</p>\n<p>Raises <code>ValueError</code> when <code>mode</code> is not one of the 4 documented values (caller-typo gate fires BEFORE the FR37 coverage gate). Raises <code>IncompleteTraceError</code> per FR37 on <code>mcp_coverage=\"external_mixed\"</code> + <code>allow_external_mcp_blind=False</code>. Raises <code>AssertionError</code> on trajectory mismatch.</p>\n<p>Example (illustrative \u2014 assumes a real adapter with the expected 3-call trajectory):</p>\n<pre>\n${result} =    <a href=\"#Send%20Prompt\" class=\"name\">Send Prompt</a>    prompt=Find news    adapter=generic    model=anthropic/claude-sonnet-4-6\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'fetch', 'summarize']}}\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['fetch', 'web_search']}}    mode=set\n<a href=\"#Trajectory%20Should%20Match\" class=\"name\">Trajectory Should Match</a>    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR23a + FR23b ratify the 4 match modes.</li>\n<li>mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.</li>\n<li>Sibling keyword: <a href=\"#Tool%20Call%20Should%20Have%20Occurred\" class=\"name\">Tool Call Should Have Occurred</a> for single-call name+args assertions.</li>\n</ul>", "shortdoc": "Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/_assertions/library.py", "lineno": 86}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config", "Get Last Warnings", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["Any"]}, {"type": "Standard", "name": "boolean", "doc": "<p>Strings <code>TRUE</code>, <code>YES</code>, <code>ON</code>, <code>1</code> and possible localization specific \"true strings\" are converted to Boolean <code>True</code>, the empty string, strings <code>FALSE</code>, <code>NO</code>, <code>OFF</code> and <code>0</code> and possibly localization specific \"false strings\" are converted to Boolean <code>False</code>, and the string <code>NONE</code> is converted to the Python <code>None</code> object. Other strings and all other values are passed as-is, allowing keywords to handle them specially if needed. All string comparisons are case-insensitive.</p>\n<p>Examples: <code>TRUE</code> (converted to <code>True</code>), <code>off</code> (converted to <code>False</code>), <code>example</code> (used as-is)</p>", "usages": ["__init__", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "integer", "float", "None"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Get Effective Config With Provenance", "Get Last Warnings", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["__init__", "Get Cost Total", "Get Latency", "Get Latency P95", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Keyword Tier", "Get Tool Call Count", "Stat.Bootstrap Confidence Interval", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Run N Times"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["Get Config", "Get Cost Total", "Get Last Warnings", "Get Latency", "Get Latency P95", "Get Spans", "Get Token Usage", "Get Tool Call Count", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Tool Success Rate", "Get Unnecessary Call Rate", "Run Scenario", "Stat.Assert Run Determinism", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U", "Stat.Run N Times", "Trajectory Should Match"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["__init__"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["__init__", "Get Effective Config", "Get Run Manifest", "Judge.Calibrate Rubric", "Judge.Get Score", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Bootstrap Confidence Interval", "Stat.Cliff Delta", "Stat.Get Pass At K", "Stat.Get Pass At K Confidence Interval", "Stat.Mann Whitney U", "Stat.Run N Times", "Tool Call Should Have Occurred"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Agent Response Should Match Schema", "Get Config", "Judge.Calibrate Rubric", "Judge.Get Score"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["__init__", "Agent Response Should Contain", "Agent Response Should Match Regex", "Agent Response Should Match Schema", "Get Cohort Heatmap", "Get Config", "Get Effective Config", "Get Effective Config With Provenance", "Get Keyword Tier", "Get Last Warnings", "Get Run Manifest", "Get Spans", "Get Tool Call Names", "Get Tool Calls", "Get Tool Hit Rate", "Get Unnecessary Call Rate", "Judge.Calibrate Rubric", "Judge.Get Score", "Load Scenario", "Run Scenario", "Send Prompt", "Stat.Assert Run Determinism", "Stat.Run N Times", "Tool Call Should Have Occurred", "Trajectory Should Match"], "accepts": ["Any"]}, {"type": "Standard", "name": "tuple", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> or <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible lists converted further to tuples. They can contain any values <code>ast.literal_eval</code> supports, including tuples and other collections.</p>\n<p>If the argument is a tuple, it is used without conversion. Lists and other sequences are converted to tuples.</p>\n<p>If the type has nested types like <code>tuple[str, int, int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>('one', 'two')</code>, <code>(('one', 1), ('two', 2))</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for list literals is new in Robot Framework 7.4.</p>", "usages": ["Stat.Bootstrap Confidence Interval", "Stat.Get Pass At K Confidence Interval"], "accepts": ["string", "Sequence"]}]}
 </script>
 <link rel=icon type=image/x-icon href="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKcAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAAqAAAAAAAAAAAAAAAAAAAALIAAAD/AAAA4AAAANwAAADcAAAA3AAAANwAAADcAAAA3AAAANwAAADcAAAA4AAAAP8AAACxAAAAAAAAAKYAAAD/AAAAuwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC/AAAA/wAAAKkAAAD6AAAAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN8AAAD/AAAA+gAAAMMAAAAAAAAAAgAAAGsAAABrAAAAawAAAGsAAABrAAAAawAAAGsAAABrAAAADAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAIsAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAANEAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAAAAAAAAMgAAADIAAAAyAAAAMgAAADIAAAAyAAAAMgAAADIAAAAFAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAADwAAAB8AAAAAAAAAGAAAABcAAAAAAAAAH8AAABKAAAAAAAAAAAAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAADCAAAA/wAAACkAAADqAAAA4QAAAAAAAAD7AAAA/wAAALAAAAAGAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAIwAAAP4AAAD/AAAA/wAAAGAAAAAAAAAAAAAAAMkAAAD/AAAAigAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAAAAAAAIAAAAcAAAABkAAAAAAAAAAAAAAAAAAAAAAAAAEgAAAAAAAAAAAAAA2gAAAP8AAAD7AAAAywAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN4AAAD/AAAAqwAAAP8AAACvAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALIAAAD/AAAAsgAAAAAAAAC5AAAA/wAAAMoAAADAAAAAwAAAAMAAAADAAAAAwAAAAMAAAADAAAAAwAAAAMkAAAD/AAAAvAAAAAAAAAAAAAAAAAAAAKwAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAArQAAAAAAAAAAwAMAAIABAAAf+AAAP/wAAD/8AAAgBAAAP/wAAD/8AAA//AAAJIwAADHEAAA//AAAP/wAAB/4AACAAQAAwAMAAA==">
 </head>
diff --git a/docs/keywords/MCPLibrary.html b/docs/keywords/MCPLibrary.html
index d7319f2..7e7206c 100644
--- a/docs/keywords/MCPLibrary.html
+++ b/docs/keywords/MCPLibrary.html
@@ -6,7 +6,7 @@
 <meta http-equiv=X-UA-Compatible content="IE=edge">
 <meta content="Robot Framework 7.4.2 (Python 3.12.3 on linux)" name="Generator">
 <script type="text/javascript">
-libdoc = {"specversion": 3, "name": "AgentEval.mcp.library.MCPLibrary", "doc": "<p>Static-inspection keywords for <span class=\"name\">.mcp.json</span> files [Tier 1 \u2014 Deterministic].</p>", "version": "", "generated": "2026-05-27T19:45:48+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 109, "tags": [], "inits": [], "keywords": [{"name": "Call Tool", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "arguments", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "arguments: dict[str, Any] | None = None"}], "returnType": {"name": "MCPToolResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Invokes a tool by name on the MCP server at <code>handle</code> (PRD FR9b).</p>\n<p>[Tier 1 \u2014 Deterministic] (given a deterministic tool) \u2014 opens a fresh per-call MCP session, runs <code>initialize()</code>, invokes the named tool, computes wall-clock latency, then tears down. Tool-LEVEL error responses surface as <code>MCPToolResult(is_error=True, ...)</code> \u2014 first-class data, NOT exceptions. Infrastructure failures raise <code>MCPConnectionLostError</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>The tool name as advertised by the server.</td>\n</tr>\n<tr>\n<td><code>arguments</code></td>\n<td>Optional dict of tool-specific arguments. Defaults to <code>{}</code>.</td>\n</tr>\n</table>\n<p>Returns <code>MCPToolResult</code> with <code>content</code> (list of content blocks), <code>is_error</code>, <code>error_message</code>, <code>latency_ms</code>, and <code>correlation_id</code> (Phase-1 uuid4 placeholder).</p>\n<p>Raises <code>ValueError</code> on <code>streamable_http</code> transport (Phase-1 passthrough). Raises <code>UnsupportedMCPVersionError</code> on version gate failure. Raises <code>MCPConnectionLostError</code> on transport- layer failure mid-call (subprocess crash, etc.).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${result} =    <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>    ${handle}    echo_back    arguments=${{ {\"text\": \"hi\"} }}\nShould Be Equal    ${result.is_error}    ${FALSE}\nShould Contain    ${result.content}[0][text]    hi\n<a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR9b ratifies the tool-call contract; tool-error-as-data per AC-MCP-CALL-01.</li>\n<li><code>correlation_id</code> Phase-1 placeholder; Epic 5 wires real trace-id lookup.</li>\n<li>Sibling keywords: <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Start%20Server\" class=\"name\">Start Server</a>, <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>.</li>\n</ul>", "shortdoc": "Invokes a tool by name on the MCP server at ``handle`` (PRD FR9b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 379}, {"name": "Connect To Server", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": {"name": "MCPSession", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Opens + initializes an MCP <code>ClientSession</code> and gate-checks the version (PRD FR8 + FR46).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 per Story 3.1 per-call-session design: opens session, runs <code>initialize()</code>, captures the negotiated protocol version + server info, gates on the agenteval-supported range (<code>mcp&gt;=1.0,&lt;2.0</code>), then closes the underlying SDK session. Returns <code>MCPSession</code> metadata \u2014 <b>*NOT a live SDK session*</b>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Raises <code>UnsupportedMCPVersionError</code> when the negotiated protocol version is outside the supported range. Raises <code>ValueError</code> when <code>handle.transport == \"streamable_http\"</code> (Phase-1 passthrough; not yet implemented).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${session} =    <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>    ${handle}\nShould Not Be Empty    ${session.protocol_version}\nShould Contain    ${session.server_info}[name]    echo\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR8 + FR46 ratify the version-gate + per-call-session contract.</li>\n<li>Story 3.1 ratifies per-call-session design (no live session returned).</li>\n<li>NFR-COMPAT-04 pins the MCP SDK at <code>mcp&gt;=1.0,&lt;2.0</code>.</li>\n<li>Sibling keywords: <a href=\"#Start%20Server\" class=\"name\">Start Server</a> (handle construction); <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a> (Phase-1 no-op cleanup); <a href=\"#List%20Tools\" class=\"name\">List Tools</a> / <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a> (per-call session-internal).</li>\n</ul>", "shortdoc": "Opens + initializes an MCP ``ClientSession`` and gate-checks the version (PRD FR8 + FR46).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 274}, {"name": "Get Server Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a <code>.mcp.json</code> file's <code>mcpServers</code> declarations (PRD FR5).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per- entry validation. Does NOT spawn any MCP subprocesses. Returns a dict mapping <code>&lt;server_name&gt;</code> \u2192 server-entry dict. Each entry has at minimum <code>command</code> (str); may carry <code>args</code>, <code>env</code>, <code>transport</code> (one of <code>stdio</code> / <code>streamable_http</code> / <code>in_memory</code> per FR7), <code>tools</code> (Phase-1 declarative extension). Median \u2264 50 ms per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on any structural failure. The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer into the offending location.</p>\n<p>Example:</p>\n<pre>\n${servers} =    <a href=\"#Get%20Server%20Config\" class=\"name\">Get Server Config</a>    ${CURDIR}/.mcp.json\nShould Be Equal    ${servers}[echo][transport]    stdio\nShould Contain    ${servers}[echo][args]    -m\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR5 ratifies the <code>.mcp.json</code> parse contract; FR7 ratifies the transport enum.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> + <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a> for tool-schema introspection.</li>\n</ul>", "shortdoc": "Parses a ``.mcp.json`` file's ``mcpServers`` declarations (PRD FR5).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 114}, {"name": "Get Tool Discoverability", "args": [{"name": "mcp_server", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_server: str = "}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "tasks", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "tasks: str = "}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "5.0", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_cost_usd: float = 5.0"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_runtime_seconds: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Drives N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 for each task in the YAML, dispatches <code>trials_per_task</code> adapter.run() calls and inspects <code>tool_calls</code> to compute Pass@k with Wilson CI bounds.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>mcp_server</code></td>\n<td>Name of the MCP server (per <a href=\"#Start%20Server\" class=\"name\">Start Server</a>). Must be a non-empty string. Phase-1: accepted but NOT forwarded to <code>adapter.run()</code> (DF-4.1-S2 + DF-4.2-S1).</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Model identifier (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>).</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Path to the discoverability tasks YAML.</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Number of trials per task (Pass@k semantics). Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>max_cost_usd</code></td>\n<td>Budget cap. Phase-1: tracked, NOT enforced (DF-4.4-S1 carry-over). Defaults to <code>5.00</code>.</td>\n</tr>\n<tr>\n<td><code>max_runtime_seconds</code></td>\n<td>Runtime cap. Phase-1: tracked, NOT enforced. Defaults to <code>None</code>.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Phase-1 carve-out (DF-4.4-S1): <code>@guarded_fanout</code> enforcement of <code>max_cost_usd</code> + <code>max_runtime_seconds</code> is DEFERRED \u2014 same architectural gap as Story 4.3 DF-4.3-S6 (MCPLibrary is excluded from <code>_SUB_LIBRARIES</code> per Story 2.2 norm; no clean path to inject library-level budgets without architectural change). The kwargs are accepted + tracked on the result but NOT enforced. Operators must bound cost manually until Phase-1.5 plumbs the cross-library config.</p>\n<p>Phase-1 carve-out (DF-4.1-S2 + DF-4.2-S1): <code>mcp_server=</code> is NOT forwarded to <code>adapter.run(mcp_servers=...)</code> because both Phase-1 adapters (Generic + Claude Code CLI) raise <code>NotImplementedError</code> on non-empty <code>mcp_servers</code>. The kwarg is accepted for forward-compatibility + validated as non-empty; tool-call success is gated on what the model returns from prompt alone (useful for stub-adapter tests; meaningful for real LLMs only when DF-4.1-S2 + DF-4.2-S1 land).</p>\n<p>Empty-<span class=\"name\">`expected_tools</span>` semantics (Story 4.4 code-review 3-way MED-A 2026-05-20): when a task's <code>expected_tools</code> is <code>[]</code>, the keyword treats ANY tool call as success (wildcard mode \u2014 useful for \"did the agent invoke ANY tool?\" probes). <code>competing_tools_picked</code> in this case collects ALL called tool names.</p>\n<p>Returns <code>DiscoverabilityResult</code> with <code>per_task_results</code> + <code>summary</code> (aggregate pass rate + cost + runtime) + <code>mcp_coverage</code> per PRD FR10a L1499 ratified shape.</p>\n<p>Raises <code>InvalidDiscoverabilityTasksError</code> on tasks YAML parse/schema failure. Raises <code>AdapterDiscoveryError</code> on unknown adapter name. Raises <code>ValueError</code> when required kwargs are missing/empty.</p>\n<p>Example (illustrative \u2014 assumes a real adapter or fixture stub):</p>\n<pre>\n${result} =    <a href=\"#Get%20Tool%20Discoverability\" class=\"name\">Get Tool Discoverability</a>\n...    mcp_server=echo\n...    adapter=generic\n...    provider=mock\n...    model=stub\n...    tasks=${CURDIR}/discoverability_tasks.yaml\n...    trials_per_task=3\nShould Be True    0.0 &lt;= ${result.summary.overall_pass_rate} &lt;= 1.0\nShould Not Be Empty    ${result.per_task_results}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR10a ratifies the keyword + <code>DiscoverabilityResult</code> shape.</li>\n<li>Tier-3 stochastic; budgets tracked but NOT enforced in Phase-1 (DF-4.4-S1).</li>\n<li>Story 4.3 + Story 4.4 ratify the carve-out (architectural budget-injection gap shared with <span class=\"name\">MetricsLibrary</span> family).</li>\n<li>Story 2.2 ratifies the <code>_SUB_LIBRARIES</code> composition norm (which excludes <code>MCPLibrary</code> \u2014 driver of the carve-out).</li>\n<li>Sibling keywords (same library): <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>, <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</li>\n<li>Downstream keyword (separately composed sub-library): <span class=\"name\">HeatmapLibrary.Get Cohort Heatmap</span> consumes <code>DiscoverabilityResult</code> to render the FR55 cohort heatmap.</li>\n</ul>", "shortdoc": "Drives N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 429}, {"name": "Get Tool Schema", "args": [{"name": "config_path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "config_path: str | Path"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "server_name", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_name: str | None = None"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns a tool's input JSON Schema from the <code>.mcp.json:tools</code> extension (PRD FR6).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 reads from the declarative <code>tools</code> extension on each server entry (Story 2.3 D-D). Returns the schema as a <code>dict</code>. PRD FR6's runtime \"against a running MCP server\" path is Phase-2 + Epic 3 scope.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>config_path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>Name of the tool whose input schema to retrieve.</td>\n</tr>\n<tr>\n<td><code>server_name</code></td>\n<td>When <code>None</code> (default), search every server in declaration order + return the first match. When set, only consult the named server.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on <code>.mcp.json</code> structural failure. Raises <code>InvalidMCPToolSchemaError</code> when the tool is not declared on any candidate server.</p>\n<p>Example:</p>\n<pre>\n${schema} =    <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=echo\nShould Be Equal    ${schema}[type]    object\nShould Contain    ${schema}[required]    message\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR6 ratifies the tool-schema retrieval contract; Phase-1 scope per Story 2.3 D-D drift-check.</li>\n<li>Sibling keywords: <a href=\"#Get%20Server%20Config\" class=\"name\">Get Server Config</a> (full <code>.mcp.json</code> parse); <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a> (Draft 2020-12 well-formedness check).</li>\n</ul>", "shortdoc": "Returns a tool's input JSON Schema from the ``.mcp.json:tools`` extension (PRD FR6).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 146}, {"name": "List Tools", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "MCPTool", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Lists the tools advertised by the MCP server at <code>handle</code> (PRD FR9a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 opens a fresh per-call MCP session per Story 3.1, runs <code>initialize()</code>, calls the MCP spec's <code>list_tools</code> operation, then tears down. Each call pays the full handshake cost; Phase-1.5 may introduce pooled sessions for hot loops. Returns a <code>list[MCPTool]</code> with <code>name</code>, <code>description</code>, <code>input_schema</code>, and optional <code>output_schema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when transport is <code>streamable_http</code> (Phase-1 passthrough). Raises <code>UnsupportedMCPVersionError</code> when <code>initialize()</code> rejects the negotiated protocol version. Raises <code>MCPConnectionLostError</code> when the transport layer fails mid-call.</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n@{tools} =    <a href=\"#List%20Tools\" class=\"name\">List Tools</a>    ${handle}\nShould Not Be Empty    ${tools}\nShould Contain    ${{ [t.name for t in $tools] }}    echo_back\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR9a ratifies the list-tools contract.</li>\n<li>Story 3.1 ratifies per-call-session design.</li>\n<li>Pooled-session optimization is Phase-1.5; Phase-1 pays per-call handshake.</li>\n<li>Sibling keyword: <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a> (invoke a tool by name); <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> (declarative \u2014 reads from <code>.mcp.json</code>).</li>\n</ul>", "shortdoc": "Lists the tools advertised by the MCP server at ``handle`` (PRD FR9a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 344}, {"name": "Start Server", "args": [{"name": "name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "name: str"}, {"name": "transport", "type": {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'stdio'", "typedoc": null, "nested": [], "union": false}, {"name": "'streamable_http'", "typedoc": null, "nested": [], "union": false}, {"name": "'in_memory'", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "transport: Literal['stdio', 'streamable_http', 'in_memory']"}, {"name": "command", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "command: str | None = None"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: list[str] | None = None"}, {"name": "env", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "env: dict[str, str] | None = None"}, {"name": "server_factory", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[]", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_factory: Callable[[], Any] | None = None"}], "returnType": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds an MCP server handle per the 3-transport enum (PRD FR7).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure handle construction. For <code>stdio</code> + <code>in_memory</code> transports, does NOT spawn the server yet (per Story 3.1 per-call-session design); the actual server start happens during <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>. The <code>streamable_http</code> transport is accepted as a Phase-1 passthrough; full HTTP round-trip lands Phase-1.5 or Story 3.2.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>name</code></td>\n<td>Caller-chosen server identifier (echoed in errors).</td>\n</tr>\n<tr>\n<td><code>transport</code></td>\n<td>One of <code>\"stdio\"</code> / <code>\"streamable_http\"</code> / <code>\"in_memory\"</code> per FR7 transport enum.</td>\n</tr>\n<tr>\n<td><code>command</code></td>\n<td>stdio only \u2014 executable path/name (e.g. <code>\"python\"</code>).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>stdio only \u2014 list of command-line arguments.</td>\n</tr>\n<tr>\n<td><code>env</code></td>\n<td>stdio only \u2014 environment overlay.</td>\n</tr>\n<tr>\n<td><code>server_factory</code></td>\n<td>in_memory only \u2014 no-arg callable returning a <code>FastMCP</code> server instance.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when transport-required parameters are missing (e.g. <code>transport=\"stdio\"</code> without <code>command</code>).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${session} =    <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>    ${handle}\n@{tools} =    <a href=\"#List%20Tools\" class=\"name\">List Tools</a>    ${handle}\n<a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR7 ratifies the 3-transport enum; Story 3.1 ratifies the per-call-session design.</li>\n<li>Story 3.2 lands the full <code>streamable_http</code> round-trip (Phase-1 currently passthrough).</li>\n<li>Sibling keywords: <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> (handshake + version check); <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>, <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>.</li>\n</ul>", "shortdoc": "Builds an MCP server handle per the 3-transport enum (PRD FR7).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 223}, {"name": "Stop Server", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": null, "doc": "<p>Tears down any per-handle MCP resources.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Phase-1 no-op (each <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> self-cleans the SDK session). The keyword ships now so <code>.robot</code> tests can adopt the canonical 3-step lifecycle without breaking when Phase-1.5 introduces pooled sessions that need explicit teardown.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>The <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Returns <code>None</code>. Never raises in Phase-1 (no-op).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\nTRY\n    ${result} =    <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>    ${handle}    echo    arguments=${{ {\"message\": \"hi\"} }}\n    Should Be True    ${result.is_error} == False\nFINALLY\n    <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Phase-1 no-op per Story 3.1 design (per-call sessions self-clean).</li>\n<li>The canonical 3-step lifecycle (<a href=\"#Start%20Server\" class=\"name\">Start Server</a> \u2192 <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> \u2192 <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>) is ratified now to avoid breakage when Phase-1.5 introduces pooled sessions.</li>\n<li>Sibling keywords: <a href=\"#Start%20Server\" class=\"name\">Start Server</a> + <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> (companion lifecycle steps).</li>\n</ul>", "shortdoc": "Tears down any per-handle MCP resources.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 308}, {"name": "Validate Tool Schema", "args": [{"name": "config_path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "config_path: str | Path"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "server_name", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_name: str | None = None"}], "returnType": null, "doc": "<p>Validates a tool's schema against the jsonschema Draft 2020-12 meta-schema.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 verifies the schema-VALIDITY of an MCP tool's input schema. Does NOT validate any tool-call's ARGUMENTS against the schema \u2014 that's a runtime concern Epic 3 owns. Median \u2264 50 ms per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>config_path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>Tool whose schema to validate.</td>\n</tr>\n<tr>\n<td><code>server_name</code></td>\n<td>Optional server scoping (see <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a>).</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on <code>.mcp.json</code> structural failure. Raises <code>InvalidMCPToolSchemaError</code> when the tool is not declared OR its schema fails Draft 2020-12 meta-schema validation. The error's <code>field_name</code> carries an RFC 6901 JSON Pointer; the wrapped jsonschema exception is available via <code>__cause__</code>.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=echo\nRun Keyword And Expect Error    InvalidMCPToolSchemaError*    <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=nonexistent\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Validates schema well-formedness, NOT argument conformance \u2014 that's runtime/Epic 3.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> for retrieving the schema dict.</li>\n</ul>", "shortdoc": "Validates a tool's schema against the jsonschema Draft 2020-12 meta-schema.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 181}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Discoverability", "Get Tool Schema", "Start Server"], "accepts": ["Any"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Schema", "Start Server"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["Get Tool Discoverability"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Tool Discoverability"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["List Tools", "Start Server"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["Start Server"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["Call Tool", "Get Tool Discoverability", "Get Tool Schema", "Start Server", "Validate Tool Schema"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Get Server Config", "Get Tool Schema", "Validate Tool Schema"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Discoverability", "Get Tool Schema", "Start Server", "Validate Tool Schema"], "accepts": ["Any"]}]}
+libdoc = {"specversion": 3, "name": "MCPLibrary", "doc": "<p>Static-inspection keywords for <span class=\"name\">.mcp.json</span> files [Tier 1 \u2014 Deterministic].</p>", "version": "", "generated": "2026-06-01T11:44:07+00:00", "type": "LIBRARY", "scope": "TEST", "docFormat": "HTML", "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 106, "tags": [], "inits": [], "keywords": [{"name": "Call Tool", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "arguments", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "arguments: dict[str, Any] | None = None"}], "returnType": {"name": "MCPToolResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Invokes a tool by name on the MCP server at <code>handle</code> (PRD FR9b).</p>\n<p>[Tier 1 \u2014 Deterministic] (given a deterministic tool) \u2014 opens a fresh per-call MCP session, runs <code>initialize()</code>, invokes the named tool, computes wall-clock latency, then tears down. Tool-LEVEL error responses surface as <code>MCPToolResult(is_error=True, ...)</code> \u2014 first-class data, NOT exceptions. Infrastructure failures raise <code>MCPConnectionLostError</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>The tool name as advertised by the server.</td>\n</tr>\n<tr>\n<td><code>arguments</code></td>\n<td>Optional dict of tool-specific arguments. Defaults to <code>{}</code>.</td>\n</tr>\n</table>\n<p>Returns <code>MCPToolResult</code> with <code>content</code> (list of content blocks), <code>is_error</code>, <code>error_message</code>, <code>latency_ms</code>, and <code>correlation_id</code> (Phase-1 uuid4 placeholder).</p>\n<p>Raises <code>ValueError</code> on <code>streamable_http</code> transport (Phase-1 passthrough). Raises <code>UnsupportedMCPVersionError</code> on version gate failure. Raises <code>MCPConnectionLostError</code> on transport- layer failure mid-call (subprocess crash, etc.).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${result} =    <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>    ${handle}    echo_back    arguments=${{ {\"text\": \"hi\"} }}\nShould Be Equal    ${result.is_error}    ${FALSE}\nShould Contain    ${result.content}[0][text]    hi\n<a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR9b ratifies the tool-call contract; tool-error-as-data per AC-MCP-CALL-01.</li>\n<li><code>correlation_id</code> Phase-1 placeholder; Epic 5 wires real trace-id lookup.</li>\n<li>Sibling keywords: <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Start%20Server\" class=\"name\">Start Server</a>, <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>.</li>\n</ul>", "shortdoc": "Invokes a tool by name on the MCP server at ``handle`` (PRD FR9b).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 376}, {"name": "Connect To Server", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": {"name": "MCPSession", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Opens + initializes an MCP <code>ClientSession</code> and gate-checks the version (PRD FR8 + FR46).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 per Story 3.1 per-call-session design: opens session, runs <code>initialize()</code>, captures the negotiated protocol version + server info, gates on the agenteval-supported range (<code>mcp&gt;=1.0,&lt;2.0</code>), then closes the underlying SDK session. Returns <code>MCPSession</code> metadata \u2014 <b>*NOT a live SDK session*</b>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Raises <code>UnsupportedMCPVersionError</code> when the negotiated protocol version is outside the supported range. Raises <code>ValueError</code> when <code>handle.transport == \"streamable_http\"</code> (Phase-1 passthrough; not yet implemented).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${session} =    <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>    ${handle}\nShould Not Be Empty    ${session.protocol_version}\nShould Contain    ${session.server_info}[name]    echo\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR8 + FR46 ratify the version-gate + per-call-session contract.</li>\n<li>Story 3.1 ratifies per-call-session design (no live session returned).</li>\n<li>NFR-COMPAT-04 pins the MCP SDK at <code>mcp&gt;=1.0,&lt;2.0</code>.</li>\n<li>Sibling keywords: <a href=\"#Start%20Server\" class=\"name\">Start Server</a> (handle construction); <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a> (Phase-1 no-op cleanup); <a href=\"#List%20Tools\" class=\"name\">List Tools</a> / <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a> (per-call session-internal).</li>\n</ul>", "shortdoc": "Opens + initializes an MCP ``ClientSession`` and gate-checks the version (PRD FR8 + FR46).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 271}, {"name": "Get Server Config", "args": [{"name": "path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "path: str | Path"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}], "union": false}, "doc": "<p>Parses a <code>.mcp.json</code> file's <code>mcpServers</code> declarations (PRD FR5).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure file-read + JSON parse + per- entry validation. Does NOT spawn any MCP subprocesses. Returns a dict mapping <code>&lt;server_name&gt;</code> \u2192 server-entry dict. Each entry has at minimum <code>command</code> (str); may carry <code>args</code>, <code>env</code>, <code>transport</code> (one of <code>stdio</code> / <code>streamable_http</code> / <code>in_memory</code> per FR7), <code>tools</code> (Phase-1 declarative extension). Median \u2264 50 ms per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file. Accepts <code>str</code> OR <code>pathlib.Path</code>.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on any structural failure. The error's <code>field_name</code> attribute carries an RFC 6901 JSON Pointer into the offending location.</p>\n<p>Example:</p>\n<pre>\n${servers} =    <a href=\"#Get%20Server%20Config\" class=\"name\">Get Server Config</a>    ${CURDIR}/.mcp.json\nShould Be Equal    ${servers}[echo][transport]    stdio\nShould Contain    ${servers}[echo][args]    -m\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR5 ratifies the <code>.mcp.json</code> parse contract; FR7 ratifies the transport enum.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keywords: <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> + <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a> for tool-schema introspection.</li>\n</ul>", "shortdoc": "Parses a ``.mcp.json`` file's ``mcpServers`` declarations (PRD FR5).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 111}, {"name": "Get Tool Discoverability", "args": [{"name": "mcp_server", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_server: str = "}, {"name": "adapter", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "generic", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapter: str = generic"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "tasks", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "tasks: str = "}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "5.0", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_cost_usd: float = 5.0"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_runtime_seconds: float | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "DiscoverabilityResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Drives N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 for each task in the YAML, dispatches <code>trials_per_task</code> adapter.run() calls and inspects <code>tool_calls</code> to compute Pass@k with Wilson CI bounds.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>mcp_server</code></td>\n<td>Name of the MCP server (per <a href=\"#Start%20Server\" class=\"name\">Start Server</a>). Must be a non-empty string. Phase-1: accepted but NOT forwarded to <code>adapter.run()</code> (DF-4.1-S2 + DF-4.2-S1).</td>\n</tr>\n<tr>\n<td><code>adapter</code></td>\n<td>Adapter name. Defaults to <code>\"generic\"</code>.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Model identifier (e.g., <code>\"anthropic/claude-sonnet-4-6\"</code>).</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Path to the discoverability tasks YAML.</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Number of trials per task (Pass@k semantics). Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>max_cost_usd</code></td>\n<td>Budget cap. Phase-1: tracked, NOT enforced (DF-4.4-S1 carry-over). Defaults to <code>5.00</code>.</td>\n</tr>\n<tr>\n<td><code>max_runtime_seconds</code></td>\n<td>Runtime cap. Phase-1: tracked, NOT enforced. Defaults to <code>None</code>.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Provider/adapter forward-compat kwargs.</td>\n</tr>\n</table>\n<p>Phase-1 carve-out (DF-4.4-S1): <code>@guarded_fanout</code> enforcement of <code>max_cost_usd</code> + <code>max_runtime_seconds</code> is DEFERRED \u2014 same architectural gap as Story 4.3 DF-4.3-S6 (MCPLibrary is excluded from <code>_SUB_LIBRARIES</code> per Story 2.2 norm; no clean path to inject library-level budgets without architectural change). The kwargs are accepted + tracked on the result but NOT enforced. Operators must bound cost manually until Phase-1.5 plumbs the cross-library config.</p>\n<p>Phase-1 carve-out (DF-4.1-S2 + DF-4.2-S1): <code>mcp_server=</code> is NOT forwarded to <code>adapter.run(mcp_servers=...)</code> because both Phase-1 adapters (Generic + Claude Code CLI) raise <code>NotImplementedError</code> on non-empty <code>mcp_servers</code>. The kwarg is accepted for forward-compatibility + validated as non-empty; tool-call success is gated on what the model returns from prompt alone (useful for stub-adapter tests; meaningful for real LLMs only when DF-4.1-S2 + DF-4.2-S1 land).</p>\n<p>Empty-<span class=\"name\">`expected_tools</span>` semantics (Story 4.4 code-review 3-way MED-A 2026-05-20): when a task's <code>expected_tools</code> is <code>[]</code>, the keyword treats ANY tool call as success (wildcard mode \u2014 useful for \"did the agent invoke ANY tool?\" probes). <code>competing_tools_picked</code> in this case collects ALL called tool names.</p>\n<p>Returns <code>DiscoverabilityResult</code> with <code>per_task_results</code> + <code>summary</code> (aggregate pass rate + cost + runtime) + <code>mcp_coverage</code> per PRD FR10a L1499 ratified shape.</p>\n<p>Raises <code>InvalidDiscoverabilityTasksError</code> on tasks YAML parse/schema failure. Raises <code>AdapterDiscoveryError</code> on unknown adapter name. Raises <code>ValueError</code> when required kwargs are missing/empty.</p>\n<p>Example (illustrative \u2014 assumes a real adapter or fixture stub):</p>\n<pre>\n${result} =    <a href=\"#Get%20Tool%20Discoverability\" class=\"name\">Get Tool Discoverability</a>\n...    mcp_server=echo\n...    adapter=generic\n...    provider=mock\n...    model=stub\n...    tasks=${CURDIR}/discoverability_tasks.yaml\n...    trials_per_task=3\nShould Be True    0.0 &lt;= ${result.summary.overall_pass_rate} &lt;= 1.0\nShould Not Be Empty    ${result.per_task_results}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR10a ratifies the keyword + <code>DiscoverabilityResult</code> shape.</li>\n<li>Tier-3 stochastic; budgets tracked but NOT enforced in Phase-1 (DF-4.4-S1).</li>\n<li>Story 4.3 + Story 4.4 ratify the carve-out (architectural budget-injection gap shared with <span class=\"name\">MetricsLibrary</span> family).</li>\n<li>Story 2.2 ratifies the <code>_SUB_LIBRARIES</code> composition norm (which excludes <code>MCPLibrary</code> \u2014 driver of the carve-out).</li>\n<li>Sibling keywords (same library): <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>, <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</li>\n<li>Downstream keyword (separately composed sub-library): <span class=\"name\">HeatmapLibrary.Get Cohort Heatmap</span> consumes <code>DiscoverabilityResult</code> to render the FR55 cohort heatmap.</li>\n</ul>", "shortdoc": "Drives N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 426}, {"name": "Get Tool Schema", "args": [{"name": "config_path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "config_path: str | Path"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "server_name", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_name: str | None = None"}], "returnType": {"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, "doc": "<p>Returns a tool's input JSON Schema from the <code>.mcp.json:tools</code> extension (PRD FR6).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 reads from the declarative <code>tools</code> extension on each server entry (Story 2.3 D-D). Returns the schema as a <code>dict</code>. PRD FR6's runtime \"against a running MCP server\" path is Phase-2 + Epic 3 scope.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>config_path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>Name of the tool whose input schema to retrieve.</td>\n</tr>\n<tr>\n<td><code>server_name</code></td>\n<td>When <code>None</code> (default), search every server in declaration order + return the first match. When set, only consult the named server.</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on <code>.mcp.json</code> structural failure. Raises <code>InvalidMCPToolSchemaError</code> when the tool is not declared on any candidate server.</p>\n<p>Example:</p>\n<pre>\n${schema} =    <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=echo\nShould Be Equal    ${schema}[type]    object\nShould Contain    ${schema}[required]    message\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR6 ratifies the tool-schema retrieval contract; Phase-1 scope per Story 2.3 D-D drift-check.</li>\n<li>Sibling keywords: <a href=\"#Get%20Server%20Config\" class=\"name\">Get Server Config</a> (full <code>.mcp.json</code> parse); <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a> (Draft 2020-12 well-formedness check).</li>\n</ul>", "shortdoc": "Returns a tool's input JSON Schema from the ``.mcp.json:tools`` extension (PRD FR6).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 143}, {"name": "List Tools", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": {"name": "list", "typedoc": "list", "nested": [{"name": "MCPTool", "typedoc": null, "nested": [], "union": false}], "union": false}, "doc": "<p>Lists the tools advertised by the MCP server at <code>handle</code> (PRD FR9a).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 opens a fresh per-call MCP session per Story 3.1, runs <code>initialize()</code>, calls the MCP spec's <code>list_tools</code> operation, then tears down. Each call pays the full handshake cost; Phase-1.5 may introduce pooled sessions for hot loops. Returns a <code>list[MCPTool]</code> with <code>name</code>, <code>description</code>, <code>input_schema</code>, and optional <code>output_schema</code>.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>An <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when transport is <code>streamable_http</code> (Phase-1 passthrough). Raises <code>UnsupportedMCPVersionError</code> when <code>initialize()</code> rejects the negotiated protocol version. Raises <code>MCPConnectionLostError</code> when the transport layer fails mid-call.</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n@{tools} =    <a href=\"#List%20Tools\" class=\"name\">List Tools</a>    ${handle}\nShould Not Be Empty    ${tools}\nShould Contain    ${{ [t.name for t in $tools] }}    echo_back\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR9a ratifies the list-tools contract.</li>\n<li>Story 3.1 ratifies per-call-session design.</li>\n<li>Pooled-session optimization is Phase-1.5; Phase-1 pays per-call handshake.</li>\n<li>Sibling keyword: <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a> (invoke a tool by name); <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> (declarative \u2014 reads from <code>.mcp.json</code>).</li>\n</ul>", "shortdoc": "Lists the tools advertised by the MCP server at ``handle`` (PRD FR9a).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 341}, {"name": "MCP.Compare Tool Discoverability", "args": [{"name": "mcp_server", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "mcp_server: str = "}, {"name": "adapters", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "adapters: list[str] | None = None"}, {"name": "tasks", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": "", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "tasks: str = "}, {"name": "trials_per_task", "type": {"name": "int", "typedoc": "integer", "nested": [], "union": false}, "defaultValue": "3", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "trials_per_task: int = 3"}, {"name": "max_cost_usd", "type": {"name": "float", "typedoc": "float", "nested": [], "union": false}, "defaultValue": "20.0", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_cost_usd: float = 20.0"}, {"name": "max_runtime_seconds", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "float", "typedoc": "float", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "max_runtime_seconds: float | None = None"}, {"name": "model", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "model: str | None = None"}, {"name": "kwargs", "type": {"name": "Any", "typedoc": "Any", "nested": [], "union": false}, "defaultValue": null, "kind": "VAR_NAMED", "required": false, "repr": "**kwargs: Any"}], "returnType": {"name": "DiscoverabilityComparisonResult", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Compares Tool Discoverability across \u22652 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).</p>\n<p>[Tier 3 \u2014 Stochastic Fan-Out] \u2014 runs <a href=\"#Get%20Tool%20Discoverability\" class=\"name\">Get Tool Discoverability</a> once per adapter against the SAME task set, then computes pairwise Mann-Whitney U deltas across the per-task pass-rate distributions. Returns a <span class=\"name\">DiscoverabilityComparisonResult</span> with per-adapter results + cross-adapter deltas + multi-column cohort heatmap + aggregate summary.</p>\n<p>Requires the <code>[agenteval-advanced]</code> optional extra (scipy + numpy) for the Mann-Whitney U cross-adapter delta computation; raises <code>ImportError</code> on invocation WITHOUT the extra (fail-fast BEFORE running any per-adapter fan-out \u2014 operators discovering the missing extra should not pay 3-adapter trial cost first).</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>mcp_server</code></td>\n<td>Name of the MCP server (per <a href=\"#Start%20Server\" class=\"name\">Start Server</a>). Same Phase-1 carve-out as <a href=\"#Get%20Tool%20Discoverability\" class=\"name\">Get Tool Discoverability</a> (DF-4.1-S2 + DF-4.2-S1).</td>\n</tr>\n<tr>\n<td><code>adapters</code></td>\n<td>REQUIRED <code>list[str]</code> of adapter names; \u22652 entries required. N=3+ enables ranking across Claude/GPT/Copilot/....</td>\n</tr>\n<tr>\n<td><code>tasks</code></td>\n<td>Path to the discoverability tasks YAML (loaded ONCE; shared across adapters).</td>\n</tr>\n<tr>\n<td><code>trials_per_task</code></td>\n<td>Pass@k trials per task. Defaults to <code>3</code>.</td>\n</tr>\n<tr>\n<td><code>max_cost_usd</code></td>\n<td>Budget cap. Defaults to <code>20.00</code> per epics.md L2186 (4\u00d7 the single-adapter default reflecting N=3-adapter typical cost). Phase-1 carve-out DF-13.3-S1: tracked NOT enforced (same MCPLibrary architectural gap as DF-4.4-S1 / C20).</td>\n</tr>\n<tr>\n<td><code>max_runtime_seconds</code></td>\n<td>Runtime cap. Phase-1: tracked, NOT enforced.</td>\n</tr>\n<tr>\n<td><code>model</code></td>\n<td>Optional <code>str</code> forwarded to ALL adapters' ctor. Phase-2.5 (DF-13.3-S4): per-adapter model overrides via <span class=\"name\">adapter_models: dict[str, str]</span> kwarg.</td>\n</tr>\n<tr>\n<td><code>**kwargs</code></td>\n<td>Forward-compat kwargs routed to each adapter's ctor.</td>\n</tr>\n</table>\n<p>Returns <code>DiscoverabilityComparisonResult</code> with <code>adapters</code> + <code>per_adapter_results</code> (one <code>DiscoverabilityResult</code> per adapter) + <code>cross_adapter_deltas</code> (C(N, 2) <code>PairwiseAdapterDelta</code> entries keyed <code>f\"{a1}_vs_{a2}\"</code>) + <code>heatmap</code> (multi-column <code>CohortHeatmap</code> via <code>from_comparison</code>) + <code>summary</code> (<code>DiscoverabilityComparisonSummary</code>).</p>\n<p>Raises <code>ImportError</code> when <code>[agenteval-advanced]</code> extra is missing (Mann-Whitney U requires scipy/numpy). Raises <code>ValueError</code> on missing/empty <code>mcp_server</code> / <code>tasks</code> / <code>adapters</code> (\u22652 required) / invalid <code>trials_per_task</code>. Raises <code>InvalidDiscoverabilityTasksError</code> on tasks YAML parse/schema failure. Raises <code>AdapterDiscoveryError</code> on unknown adapter name.</p>\n<p>Example:</p>\n<pre>\n${comparison}=    <a href=\"#MCP.Compare%20Tool%20Discoverability\" class=\"name\">MCP.Compare Tool Discoverability</a>\n...    mcp_server=rf-mcp\n...    adapters=${{['generic', 'claude_code_cli', 'codex_cli']}}\n...    tasks=${CURDIR}/tasks.yaml\n...    trials_per_task=5\n...    max_cost_usd=20.00\nShould Be Equal As Strings    ${comparison.summary.best_adapter}    claude_code_cli\nShould Be True    ${comparison.cross_adapter_deltas['generic_vs_codex_cli'].significant_at_alpha_05}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Story 13.3 (Epic 13) ships this Phase-2 keyword behind the <code>[agenteval-advanced]</code> optional extra (the Mann-Whitney U dependency from Story 13.1).</li>\n<li>PRD FR10b ratifies the <code>DiscoverabilityComparisonResult</code> shape; epics.md L2186-2189 ratifies the keyword signature + behavior.</li>\n<li>Math reference: <code>AgentEval.stats.mannwhitney.compute_mann_whitney_u</code> (Story 13.1 pure helper at <code>src/AgentEval/stats/mannwhitney.py</code>). The keyword surface <code>Stat.Mann Whitney U</code> is NOT called here because the input is <code>list[float]</code> per-task pass rates (NOT <code>list[KeywordRun]</code>).</li>\n<li><code>@tier(3)</code> per fan-out semantics \u2014 stochastic by tier definition; no bit-identical FR31a guarantee (Story 13.1 HIGH-C concern doesn't apply at @tier(3)).</li>\n<li>Phase-1 carve-out DF-13.3-S1: <code>@guarded_fanout</code> enforcement DEFERRED (same MCPLibrary architectural gap as DF-4.4-S1 / C20).</li>\n<li>Phase-2.5 carry-overs: DF-13.3-S2 (per-adapter MCP attachment gated on C72 + C68/C69/C73/C75); DF-13.3-S3 (Bonferroni / Holm multi-pairwise correction).</li>\n<li>Sibling keyword: <span class=\"name\">MCP.Get Tool Discoverability</span> (Phase-1 single-adapter; this keyword's N=1 case is intentionally rejected via the \u22652 validation \u2014 single-adapter callers should use the simpler <span class=\"name\">Get</span> keyword).</li>\n</ul>", "shortdoc": "Compares Tool Discoverability across \u22652 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 558}, {"name": "Start Server", "args": [{"name": "name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "name: str"}, {"name": "transport", "type": {"name": "Literal", "typedoc": "Literal", "nested": [{"name": "'stdio'", "typedoc": null, "nested": [], "union": false}, {"name": "'streamable_http'", "typedoc": null, "nested": [], "union": false}, {"name": "'in_memory'", "typedoc": null, "nested": [], "union": false}], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "transport: Literal['stdio', 'streamable_http', 'in_memory']"}, {"name": "command", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "command: str | None = None"}, {"name": "args", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "list", "typedoc": "list", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "args: list[str] | None = None"}, {"name": "env", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "dict", "typedoc": "dictionary", "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "str", "typedoc": "string", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "env: dict[str, str] | None = None"}, {"name": "server_factory", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "Callable", "typedoc": null, "nested": [{"name": "[]", "typedoc": null, "nested": [], "union": false}, {"name": "Any", "typedoc": "Any", "nested": [], "union": false}], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_factory: Callable[[], Any] | None = None"}], "returnType": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "doc": "<p>Builds an MCP server handle per the 3-transport enum (PRD FR7).</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 pure handle construction. For <code>stdio</code> + <code>in_memory</code> transports, does NOT spawn the server yet (per Story 3.1 per-call-session design); the actual server start happens during <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>. The <code>streamable_http</code> transport is accepted as a Phase-1 passthrough; full HTTP round-trip lands Phase-1.5 or Story 3.2.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>name</code></td>\n<td>Caller-chosen server identifier (echoed in errors).</td>\n</tr>\n<tr>\n<td><code>transport</code></td>\n<td>One of <code>\"stdio\"</code> / <code>\"streamable_http\"</code> / <code>\"in_memory\"</code> per FR7 transport enum.</td>\n</tr>\n<tr>\n<td><code>command</code></td>\n<td>stdio only \u2014 executable path/name (e.g. <code>\"python\"</code>).</td>\n</tr>\n<tr>\n<td><code>args</code></td>\n<td>stdio only \u2014 list of command-line arguments.</td>\n</tr>\n<tr>\n<td><code>env</code></td>\n<td>stdio only \u2014 environment overlay.</td>\n</tr>\n<tr>\n<td><code>server_factory</code></td>\n<td>in_memory only \u2014 no-arg callable returning a <code>FastMCP</code> server instance.</td>\n</tr>\n</table>\n<p>Raises <code>ValueError</code> when transport-required parameters are missing (e.g. <code>transport=\"stdio\"</code> without <code>command</code>).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\n${session} =    <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a>    ${handle}\n@{tools} =    <a href=\"#List%20Tools\" class=\"name\">List Tools</a>    ${handle}\n<a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\n</pre>\n<p>Notes:</p>\n<ul>\n<li>PRD FR7 ratifies the 3-transport enum; Story 3.1 ratifies the per-call-session design.</li>\n<li>Story 3.2 lands the full <code>streamable_http</code> round-trip (Phase-1 currently passthrough).</li>\n<li>Sibling keywords: <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> (handshake + version check); <a href=\"#List%20Tools\" class=\"name\">List Tools</a>, <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>, <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>.</li>\n</ul>", "shortdoc": "Builds an MCP server handle per the 3-transport enum (PRD FR7).", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 220}, {"name": "Stop Server", "args": [{"name": "handle", "type": {"name": "MCPServerHandle", "typedoc": null, "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "handle: MCPServerHandle"}], "returnType": null, "doc": "<p>Tears down any per-handle MCP resources.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 Phase-1 no-op (each <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> self-cleans the SDK session). The keyword ships now so <code>.robot</code> tests can adopt the canonical 3-step lifecycle without breaking when Phase-1.5 introduces pooled sessions that need explicit teardown.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>handle</code></td>\n<td>The <code>MCPServerHandle</code> from <a href=\"#Start%20Server\" class=\"name\">Start Server</a>.</td>\n</tr>\n</table>\n<p>Returns <code>None</code>. Never raises in Phase-1 (no-op).</p>\n<p>Example:</p>\n<pre>\n${handle} =    <a href=\"#Start%20Server\" class=\"name\">Start Server</a>    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}\nTRY\n    ${result} =    <a href=\"#Call%20Tool\" class=\"name\">Call Tool</a>    ${handle}    echo    arguments=${{ {\"message\": \"hi\"} }}\n    Should Be True    ${result.is_error} == False\nFINALLY\n    <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>    ${handle}\nEND\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Phase-1 no-op per Story 3.1 design (per-call sessions self-clean).</li>\n<li>The canonical 3-step lifecycle (<a href=\"#Start%20Server\" class=\"name\">Start Server</a> \u2192 <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> \u2192 <a href=\"#Stop%20Server\" class=\"name\">Stop Server</a>) is ratified now to avoid breakage when Phase-1.5 introduces pooled sessions.</li>\n<li>Sibling keywords: <a href=\"#Start%20Server\" class=\"name\">Start Server</a> + <a href=\"#Connect%20To%20Server\" class=\"name\">Connect To Server</a> (companion lifecycle steps).</li>\n</ul>", "shortdoc": "Tears down any per-handle MCP resources.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 305}, {"name": "Validate Tool Schema", "args": [{"name": "config_path", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "Path", "typedoc": "Path", "nested": [], "union": false}], "union": true}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "config_path: str | Path"}, {"name": "tool_name", "type": {"name": "str", "typedoc": "string", "nested": [], "union": false}, "defaultValue": null, "kind": "POSITIONAL_OR_NAMED", "required": true, "repr": "tool_name: str"}, {"name": "server_name", "type": {"name": "Union", "typedoc": null, "nested": [{"name": "str", "typedoc": "string", "nested": [], "union": false}, {"name": "None", "typedoc": "None", "nested": [], "union": false}], "union": true}, "defaultValue": "None", "kind": "POSITIONAL_OR_NAMED", "required": false, "repr": "server_name: str | None = None"}], "returnType": null, "doc": "<p>Validates a tool's schema against the jsonschema Draft 2020-12 meta-schema.</p>\n<p>[Tier 1 \u2014 Deterministic] \u2014 verifies the schema-VALIDITY of an MCP tool's input schema. Does NOT validate any tool-call's ARGUMENTS against the schema \u2014 that's a runtime concern Epic 3 owns. Median \u2264 50 ms per NFR-PERF-02.</p>\n<table border=\"1\">\n<tr>\n<th>Arguments</th>\n<th>Description</th>\n</tr>\n<tr>\n<td><code>config_path</code></td>\n<td>Filesystem path to the <code>.mcp.json</code> file.</td>\n</tr>\n<tr>\n<td><code>tool_name</code></td>\n<td>Tool whose schema to validate.</td>\n</tr>\n<tr>\n<td><code>server_name</code></td>\n<td>Optional server scoping (see <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a>).</td>\n</tr>\n</table>\n<p>Raises <code>InvalidMCPServerConfigError</code> on <code>.mcp.json</code> structural failure. Raises <code>InvalidMCPToolSchemaError</code> when the tool is not declared OR its schema fails Draft 2020-12 meta-schema validation. The error's <code>field_name</code> carries an RFC 6901 JSON Pointer; the wrapped jsonschema exception is available via <code>__cause__</code>.</p>\n<p>Example:</p>\n<pre>\n<a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=echo\nRun Keyword And Expect Error    InvalidMCPToolSchemaError*    <a href=\"#Validate%20Tool%20Schema\" class=\"name\">Validate Tool Schema</a>    ${CURDIR}/.mcp.json    tool_name=nonexistent\n</pre>\n<p>Notes:</p>\n<ul>\n<li>Validates schema well-formedness, NOT argument conformance \u2014 that's runtime/Epic 3.</li>\n<li>Error format per FR59 + <span class=\"name\">docs/contracts/error-class-hierarchy.md</span> L96-104.</li>\n<li>Sibling keyword: <a href=\"#Get%20Tool%20Schema\" class=\"name\">Get Tool Schema</a> for retrieving the schema dict.</li>\n</ul>", "shortdoc": "Validates a tool's schema against the jsonschema Draft 2020-12 meta-schema.", "tags": [], "source": "/home/many/workspace/robotframework-agenteval/src/AgentEval/mcp/library.py", "lineno": 178}], "typedocs": [{"type": "Standard", "name": "Any", "doc": "<p>Any value is accepted. No conversion is done.</p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Discoverability", "Get Tool Schema", "MCP.Compare Tool Discoverability", "Start Server"], "accepts": ["Any"]}, {"type": "Standard", "name": "dictionary", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#dict\">dictionary</a> literals. They are converted to actual dictionaries using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function. They can contain any values <code>ast.literal_eval</code> supports, including dictionaries and other collections.</p>\n<p>Any mapping is accepted and converted to a <code>dict</code>.</p>\n<p>If the type has nested types like <code>dict[str, int]</code>, items are converted to those types automatically. This in new in Robot Framework 6.0.</p>\n<p>Examples: <code>{'a': 1, 'b': 2}</code>, <code>{'key': 1, 'nested': {'key': 2}}</code></p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Schema", "Start Server"], "accepts": ["string", "Mapping"]}, {"type": "Standard", "name": "float", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#float\">float</a> built-in function.</p>\n<p>Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>3.14</code>, <code>2.9979e8</code>, <code>10 000.000 01</code></p>", "usages": ["Get Tool Discoverability", "MCP.Compare Tool Discoverability"], "accepts": ["string", "Real"]}, {"type": "Standard", "name": "integer", "doc": "<p>Conversion is done using Python's <a href=\"https://docs.python.org/library/functions.html#int\">int</a> built-in function. Floating point numbers are accepted only if they can be represented as integers exactly. For example, <code>1.0</code> is accepted and <code>1.1</code> is not.</p>\n<p>It is possible to use hexadecimal, octal and binary numbers by prefixing values with <code>0x</code>, <code>0o</code> and <code>0b</code>, respectively. Spaces and underscores can be used as visual separators for digit grouping purposes.</p>\n<p>Examples: <code>42</code>, <code>-1</code>, <code>0b1010</code>, <code>10 000 000</code>, <code>0xBAD_C0FFEE</code></p>", "usages": ["Get Tool Discoverability", "MCP.Compare Tool Discoverability"], "accepts": ["string", "float"]}, {"type": "Standard", "name": "list", "doc": "<p>Strings must be Python <a href=\"https://docs.python.org/library/stdtypes.html#list\">list</a> or <a href=\"https://docs.python.org/library/stdtypes.html#tuple\">tuple</a> literals. They are converted using the <a href=\"https://docs.python.org/library/ast.html#ast.literal_eval\">ast.literal_eval</a> function and possible tuples converted further to lists. They can contain any values <code>ast.literal_eval</code> supports, including lists and other collections.</p>\n<p>If the argument is a list, it is used without conversion. Tuples and other sequences are converted to lists.</p>\n<p>If the type has nested types like <code>list[int]</code>, items are converted to those types automatically.</p>\n<p>Examples: <code>['one', 'two']</code>, <code>[('one', 1), ('two', 2)]</code></p>\n<p>Support to convert nested types is new in Robot Framework 6.0. Support for tuple literals is new in Robot Framework 7.4.</p>", "usages": ["List Tools", "MCP.Compare Tool Discoverability", "Start Server"], "accepts": ["string", "Sequence"]}, {"type": "Standard", "name": "Literal", "doc": "<p>Only specified values are accepted. Values can be strings, integers, bytes, Booleans, enums and None, and used arguments are converted using the value type specific conversion logic.</p>\n<p>Strings are case, space, underscore and hyphen insensitive, but exact matches have precedence over normalized matches.</p>", "usages": ["Start Server"], "accepts": ["Any"]}, {"type": "Standard", "name": "None", "doc": "<p>String <code>NONE</code> (case-insensitive) and the empty string are converted to the Python <code>None</code> object. Other values cause an error.</p>\n<p>Converting the empty string is new in Robot Framework 7.4.</p>", "usages": ["Call Tool", "Get Tool Discoverability", "Get Tool Schema", "MCP.Compare Tool Discoverability", "Start Server", "Validate Tool Schema"], "accepts": ["string"]}, {"type": "Standard", "name": "Path", "doc": "<p>Strings are converted <a href=\"https://docs.python.org/library/pathlib.html\">Path</a> objects. On Windows <code>/</code> is converted to <code>\\</code> automatically.</p>\n<p>Examples: <code>/tmp/absolute/path</code>, <code>relative/path/to/file.ext</code>, <code>name.txt</code></p>", "usages": ["Get Server Config", "Get Tool Schema", "Validate Tool Schema"], "accepts": ["string", "PurePath"]}, {"type": "Standard", "name": "string", "doc": "<p>All arguments are converted to Unicode strings.</p>\n<p>Most values are converted simply by using <code>str(value)</code>. An exception is that bytes are mapped directly to Unicode code points with same ordinals. This means that, for example, <code>b\"hyv\\xe4\"</code> becomes <code>\"hyv\u00e4\"</code>.</p>\n<p>Converting bytes specially is new Robot Framework 7.4.</p>", "usages": ["Call Tool", "Get Server Config", "Get Tool Discoverability", "Get Tool Schema", "MCP.Compare Tool Discoverability", "Start Server", "Validate Tool Schema"], "accepts": ["Any"]}]}
 </script>
 <link rel=icon type=image/x-icon href="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKcAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAAqAAAAAAAAAAAAAAAAAAAALIAAAD/AAAA4AAAANwAAADcAAAA3AAAANwAAADcAAAA3AAAANwAAADcAAAA4AAAAP8AAACxAAAAAAAAAKYAAAD/AAAAuwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC/AAAA/wAAAKkAAAD6AAAAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN8AAAD/AAAA+gAAAMMAAAAAAAAAAgAAAGsAAABrAAAAawAAAGsAAABrAAAAawAAAGsAAABrAAAADAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAIsAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAANEAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAAAAAAAAMgAAADIAAAAyAAAAMgAAADIAAAAyAAAAMgAAADIAAAAFAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAADwAAAB8AAAAAAAAAGAAAABcAAAAAAAAAH8AAABKAAAAAAAAAAAAAAAAAAAA2gAAAP8AAAD6AAAAwwAAAAAAAADCAAAA/wAAACkAAADqAAAA4QAAAAAAAAD7AAAA/wAAALAAAAAGAAAAAAAAANoAAAD/AAAA+gAAAMMAAAAAAAAAIwAAAP4AAAD/AAAA/wAAAGAAAAAAAAAAAAAAAMkAAAD/AAAAigAAAAAAAADaAAAA/wAAAPoAAADDAAAAAAAAAAAAAAAIAAAAcAAAABkAAAAAAAAAAAAAAAAAAAAAAAAAEgAAAAAAAAAAAAAA2gAAAP8AAAD7AAAAywAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAN4AAAD/AAAAqwAAAP8AAACvAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALIAAAD/AAAAsgAAAAAAAAC5AAAA/wAAAMoAAADAAAAAwAAAAMAAAADAAAAAwAAAAMAAAADAAAAAwAAAAMkAAAD/AAAAvAAAAAAAAAAAAAAAAAAAAKwAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAArQAAAAAAAAAAwAMAAIABAAAf+AAAP/wAAD/8AAAgBAAAP/wAAD/8AAA//AAAJIwAADHEAAA//AAAP/wAAB/4AACAAQAAwAMAAA==">
 </head>
diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md
index 1622d81..05247b2 100644
--- a/docs/phase-1-5-carry-overs.md
+++ b/docs/phase-1-5-carry-overs.md
@@ -112,8 +112,11 @@ The Phase-1.5 carry-over chain has been deferred via Epic 0 Action #6 → Epic 1
 | **C86** | **Phase-2.5: OTLP exporter resource-attribute customization (`DF-13.2-S1`).** Story 13.2 ships OTLPBackend with `service.name="robotframework-agenteval"` (per `docs/contracts/otel-trace-visual.md` L78 + L104 convention) baked into the Listener's resource. Phase-2.5: expose `service.namespace` (per-suite isolation) + `service.instance.id` (per-run UUID) as optional `AgentEval.__init__` kwargs that flow to the OpenTelemetry Resource at TracerProvider config time. Useful for multi-suite operators wanting per-suite span filtering in their observability backend. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 fixed-resource ceiling | maintainability | S | TBD | `service_namespace` + `service_instance_id` kwargs added + resource-attribute mapping verified via OTLP collector round-trip + stability-surface row updated. |
 | **C87** | **Phase-2.5: OTLP header-based auth + TLS cert customization (`DF-13.2-S2`).** Story 13.2 ships OTLPBackend supporting endpoint-only configuration; the `opentelemetry.exporter.otlp.proto.{http,grpc}.OTLPSpanExporter` classes accept `headers=` (bearer tokens) and `credentials=` (mTLS) kwargs. Phase-2.5: expose `otlp_headers` (string-keyed dict) + `otlp_credentials` (TLS cert file path / SSL context) as `AgentEval.__init__` kwargs + env vars (`AGENTEVAL_OTLP_HEADERS`, `AGENTEVAL_OTLP_CREDENTIALS`). Phase-1 operators using Honeycomb / Datadog / etc. authenticate via headers; the current ceiling forces them to pre-configure via the OpenTelemetry SDK env vars (`OTEL_EXPORTER_OTLP_HEADERS`) — operational but inconsistent with the FR41 4-level precedence chain. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 endpoint-only ceiling | maintainability | M | TBD | `otlp_headers` + `otlp_credentials` kwargs + env vars added + integration test verifies header propagation against a collector requiring `x-honeycomb-team:` header. |
 | **C88** | **Phase-2.5: OTLP exporter circuit-breaker + JSONL fallback on sustained collector outage (`DF-13.2-S3`).** Story 13.2 ships `BatchSpanProcessor(OTLPSpanExporter)` with the OpenTelemetry SDK's built-in retry but NO circuit-breaker for sustained outages. If the collector is unreachable for N consecutive batches, the BatchSpanProcessor's queue fills + drops spans silently. Phase-2.5: ship an `OTLPCircuitBreakerProcessor` wrapping `BatchSpanProcessor` that falls back to JSONL-on-disk persistence after `failure_threshold` consecutive batch failures + auto-resumes when the collector becomes reachable. *Surfaced via Story 13.2 spec D-10 + pre-emptive review-time catalog enforcement per Epic 11 retro lesson UPSTREAM 2026-06-01.* | Story 13.2 D-10 decision — Phase-1 SDK-default retry ceiling | correctness | M | TBD | Circuit-breaker processor + JSONL fallback + auto-resume + integration test simulates a 30s collector outage + verifies JSONL artifacts captured the dropped batches + auto-resume re-attaches to the recovering collector. |
+| **C89** | **Phase-2.5: `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` (`DF-13.3-S1`).** Story 13.3 ships the cross-adapter compare keyword WITHOUT `@guarded_fanout` decorator — same MCPLibrary architectural gap as `MCP.Get Tool Discoverability` (DF-4.4-S1 / C20: MCPLibrary excluded from `_SUB_LIBRARIES` per Story 2.2 collision norm, no clean path to inject library-level budgets). Cross-adapter fan-out compounds cost N× (N adapters × M tasks × trials), making this carve-out MORE expensive than the single-adapter case. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-1.5 architectural gap (compounds DF-4.4-S1 cost N×) | correctness | M | TBD | `MCP.Compare Tool Discoverability` enforces `max_cost_usd` (mid-run hard-stop at 1.1× cap raises `CostExceededError`) + `max_runtime_seconds` across all N adapters' combined trial cost. Shared resolution with C20 — both load-bear on the same MCPLibrary host-instance plumbing. |
+| **C90** | **Phase-2.5: Real per-adapter MCP-server attachment in `MCP.Compare Tool Discoverability` (`DF-13.3-S2`).** Story 13.3 ships the keyword with the SAME mcp_server-accepted-but-not-forwarded carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). For Phase-2 adapters (Stories 10.1+10.2+11.1+11.2 SDK + CLI adapters) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge + DF-10.1-S1 / C68, DF-10.2-S1 / C69, DF-11.1-S1 / C73, DF-11.2-S1 / C75 wire HostedMcpObserver per-adapter attachment. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — gated on cross-cutting MCP-bridge backlog | correctness | M | TBD | Per-adapter `adapter.run(mcp_servers=[handle])` forwarding wired AFTER C68 + C69 + C72 + C73 + C75 land; integration test verifies per-adapter `mcp_coverage` reflects real attachment per ADR-016. |
+| **C91** | **Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance (`DF-13.3-S3`).** Story 13.3 ships pairwise comparisons WITHOUT multiple-testing correction. For N=3 adapters there are C(3,2)=3 pairs; uncorrected α=0.05 inflates the family-wise error rate. Bonferroni-adjusted α = 0.05/3 ≈ 0.0167; Holm step-down is less conservative. Phase-2.5: add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` + optional `correction_method: Literal["none", "bonferroni", "holm"]` kwarg. *Surfaced via Story 13.3 spec D-10 + pre-emptive review-time catalog enforcement UPSTREAM 2026-06-01.* | Story 13.3 D-10 decision — Phase-2 uncorrected α=0.05 ceiling | maintainability | S | TBD | `correction_method` kwarg ships + summary + delta carry the adjusted-alpha + significant-at-corrected-alpha fields + unit tests verify Bonferroni-adjustment math vs known reference. |
 
-**Total: 88 catalog items** (was 85 after Story 13.1 close; Story 13.2 adds C86 + C87 + C88 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 33rd consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 52nd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 25 S, 31 M, 8 L, 1 XL (Story 13.2 adds 1 S + 2 M).
+**Total: 91 catalog items** (was 88 after Story 13.2 close; Story 13.3 adds C89 + C90 + C91 UPSTREAM at story-create time per Epic 11 retro pre-emptive catalog enforcement lesson — 34th consecutive `feedback_carry_over_catalog_gate` UPSTREAM use). 53rd consecutive use of `feedback_spec_vs_ratified_doc_precheck` 100% real-drift catch rate intact. Effort breakdown: 15 XS, 26 S, 33 M, 8 L, 1 XL (Story 13.3 adds 1 S + 2 M).
 
 ## Execution policy
 
diff --git a/src/AgentEval/_heatmap/models.py b/src/AgentEval/_heatmap/models.py
index e69ec7f..9be3020 100644
--- a/src/AgentEval/_heatmap/models.py
+++ b/src/AgentEval/_heatmap/models.py
@@ -20,7 +20,10 @@ from dataclasses import dataclass
 from typing import TYPE_CHECKING
 
 if TYPE_CHECKING:
-    from AgentEval.discoverability.schema import DiscoverabilityResult
+    from AgentEval.discoverability.schema import (
+        DiscoverabilityComparisonResult,
+        DiscoverabilityResult,
+    )
 
 __all__ = ["CohortHeatmap"]
 
@@ -63,6 +66,42 @@ class CohortHeatmap:
         cells = tuple((t.task_id, model_name, t.pass_rate) for t in result.per_task_results)
         return cls(tasks=tasks, models=(model_name,), cells=cells)
 
+    @classmethod
+    def from_comparison(
+        cls,
+        result: DiscoverabilityComparisonResult,
+    ) -> CohortHeatmap:
+        """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).
+
+        Columns = adapter names (preserving input order from ``result.adapters``).
+        Rows = task IDs (union across all per-adapter results, preserving
+        first-encounter order — defensively handles the edge case where a
+        stub adapter dropped a task; in production all adapters run the
+        SAME task set so the union equals each adapter's task list).
+
+        Args:
+            result: Story 13.3 ``DiscoverabilityComparisonResult``.
+
+        Returns:
+            ``CohortHeatmap`` with one column per adapter + one row per task.
+        """
+        # Build the row list as the union preserving first-encounter order.
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
+            (task_result.task_id, adapter, task_result.pass_rate)
+            for adapter in result.adapters
+            for task_result in result.per_adapter_results[adapter].per_task_results
+        )
+        return cls(tasks=tasks, models=models, cells=cells)
+
     def as_dict(self) -> dict[str, dict[str, float]]:
         """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
         out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
diff --git a/src/AgentEval/discoverability/_internal.py b/src/AgentEval/discoverability/_internal.py
new file mode 100644
index 0000000..a55a605
--- /dev/null
+++ b/src/AgentEval/discoverability/_internal.py
@@ -0,0 +1,171 @@
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
+"""Shared per-adapter discoverability helper (Story 13.3 refactor of Story 4.4).
+
+Extracted from `MCPLibrary.get_tool_discoverability` so the new
+`MCP.Compare Tool Discoverability` keyword (Story 13.3) can reuse the
+per-adapter logic without duplicating ~80 LoC. Behavior MUST be
+identical to the pre-refactor `get_tool_discoverability` body —
+verified by Story 4.4's 50+ existing tests passing unchanged.
+
+Architecture note: this is the canonical `_internal.py` helper module
+per `feedback_full_surface_retro_review` discipline (mirrors
+`stats/_internal.py` from Story 6.3 + `_assertions/_internal.py`-style
+sibling). Pure functions; no side effects beyond the adapter calls
+themselves.
+"""
+
+from __future__ import annotations
+
+import time
+from typing import TYPE_CHECKING, Any
+
+from AgentEval._kernel.discovery import get_adapter
+from AgentEval.discoverability.schema import (
+    DiscoverabilityResult,
+    DiscoverabilitySummary,
+    TaskResult,
+)
+from AgentEval.discoverability.wilson_ci import wilson_score_interval
+
+if TYPE_CHECKING:
+    from AgentEval.discoverability.schema import DiscoverabilityTask
+
+__all__ = ["run_single_adapter_discoverability"]
+
+
+def run_single_adapter_discoverability(
+    *,
+    mcp_server: str,
+    adapter: str,
+    model: str | None,
+    task_list: list[DiscoverabilityTask],
+    trials_per_task: int,
+    max_cost_usd: float,
+    max_runtime_seconds: float | None,
+    extra_adapter_kwargs: dict[str, Any],
+    t_start: float,
+) -> DiscoverabilityResult:
+    """Run discoverability evaluation against ONE adapter; produce a `DiscoverabilityResult`.
+
+    Internal helper extracted from `MCPLibrary.get_tool_discoverability`
+    (Story 4.4) so the cross-adapter `Compare Tool Discoverability`
+    keyword (Story 13.3) reuses the per-adapter logic without ~80 LoC
+    duplication. Behavior MUST equal pre-refactor; verified by Story
+    4.4's existing tests passing unchanged.
+
+    Args:
+        mcp_server: Already-validated non-empty MCP server name. NOT
+            forwarded to `adapter.run(mcp_servers=...)` in Phase-1
+            (DF-4.1-S2 + DF-4.2-S1 carve-out); accepted for
+            forward-compat.
+        adapter: Adapter name. Resolved via `_kernel.discovery.get_adapter`.
+        model: Optional model identifier; forwarded to adapter ctor when
+            non-None.
+        task_list: Already-loaded + schema-validated list of tasks.
+            Caller (single-adapter or compare-multi-adapter) loads the
+            YAML ONCE and passes the parsed list here.
+        trials_per_task: Pass@k trials per task; already validated >= 1.
+        max_cost_usd: Budget cap. Phase-1: tracked, NOT enforced
+            (DF-4.4-S1 carry-over).
+        max_runtime_seconds: Runtime cap. Phase-1: tracked, NOT enforced.
+        extra_adapter_kwargs: Forward-compat kwargs routed to adapter ctor.
+        t_start: Wall-clock start time (from the caller's `time.monotonic()`
+            BEFORE arg validation / YAML load). Lets compare-multi-adapter
+            measure end-to-end across all adapters from a single anchor.
+
+    Returns:
+        ``DiscoverabilityResult`` with per-task results + summary +
+        Phase-1 hardcoded ``mcp_coverage="hosted_in_process"`` (DF-4.4-S3
+        carry-over).
+
+    Raises:
+        TypeError: When the adapter doesn't accept the forwarded kwargs
+            (DF-4.4-S2 carry-over re ctor/run split parity).
+    """
+    adapter_cls = get_adapter(adapter)
+    adapter_ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
+    if model is not None:
+        adapter_ctor_kwargs["model"] = model
+    try:
+        adapter_instance = adapter_cls(**adapter_ctor_kwargs)
+    except TypeError as exc:
+        raise TypeError(
+            f"Adapter {adapter!r} doesn't accept kwargs {sorted(adapter_ctor_kwargs)}; "
+            "DF-4.4-S2 carry-over (ctor/run split parity for MCPLibrary "
+            "lands in Phase-1.5 — mirroring Story 4.3's "
+            "`_split_adapter_kwargs` introspection on OrchestrationLibrary). "
+            "For now, pass kwargs the adapter accepts."
+        ) from exc
+
+    # Per-call mcp_servers integration is DF-4.1-S2 / DF-4.2-S1.
+    _ = mcp_server
+
+    per_task: list[TaskResult] = []
+    total_cost = 0.0
+    for task in task_list:
+        tool_calls_per_trial: list[list[Any]] = []
+        cost_per_trial: list[float] = []
+        success_count = 0
+        competing_set: set[str] = set()
+        for _ in range(trials_per_task):
+            run_result = adapter_instance.run(task.prompt)
+            tool_calls_per_trial.append(list(run_result.tool_calls))
+            cost_per_trial.append(run_result.cost_usd)
+            total_cost += run_result.cost_usd
+            called_names = {tc.name for tc in run_result.tool_calls}
+            # Story 4.4 3-way MED-A: wildcard-success mode when expected_tools empty.
+            if task.expected_tools:
+                expected_set = set(task.expected_tools)
+                if called_names & expected_set:
+                    success_count += 1
+                competing_set.update(called_names - expected_set)
+            else:
+                if called_names:
+                    success_count += 1
+                competing_set.update(called_names)
+        lower, upper = wilson_score_interval(success_count, trials_per_task)
+        per_task.append(
+            TaskResult(
+                task_id=task.id,
+                task_prompt=task.prompt,
+                trials_run=trials_per_task,
+                success_count=success_count,
+                tool_calls_per_trial=tool_calls_per_trial,
+                competing_tools_picked=sorted(competing_set),
+                cost_per_trial_usd=cost_per_trial,
+                wilson_ci_lower=lower,
+                wilson_ci_upper=upper,
+            )
+        )
+    total_runtime = time.monotonic() - t_start
+
+    # Overall pass rate weighted by trials.
+    total_trials = sum(t.trials_run for t in per_task)
+    total_successes = sum(t.success_count for t in per_task)
+    overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0
+
+    # Phase-1: mcp_coverage hardcoded (DF-4.4-S3 carry-over).
+    _ = max_cost_usd
+    _ = max_runtime_seconds
+    return DiscoverabilityResult(
+        per_task_results=per_task,
+        summary=DiscoverabilitySummary(
+            overall_pass_rate=overall_pass_rate,
+            total_cost_usd=total_cost,
+            total_runtime_seconds=total_runtime,
+        ),
+        mcp_coverage="hosted_in_process",
+    )
diff --git a/src/AgentEval/discoverability/schema.py b/src/AgentEval/discoverability/schema.py
index 2d76479..75aff03 100644
--- a/src/AgentEval/discoverability/schema.py
+++ b/src/AgentEval/discoverability/schema.py
@@ -38,16 +38,25 @@ PRD a second time.
 
 from __future__ import annotations
 
+from collections.abc import Mapping
 from dataclasses import dataclass, field
-from typing import Literal
+from typing import TYPE_CHECKING, Literal
 
 from AgentEval.types import ToolCallTrace
 
+if TYPE_CHECKING:
+    from AgentEval._heatmap.models import CohortHeatmap
+    from AgentEval.stats.types import MannWhitneyResult
+
 __all__ = [
     "DiscoverabilityTask",
     "TaskResult",
     "DiscoverabilitySummary",
     "DiscoverabilityResult",
+    # Story 13.3 (Epic 13) — cross-adapter comparison surface (FR10b).
+    "DiscoverabilityComparisonResult",
+    "PairwiseAdapterDelta",
+    "DiscoverabilityComparisonSummary",
 ]
 
 
@@ -144,3 +153,143 @@ class DiscoverabilityResult:
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "per_task_results", list(self.per_task_results))
+
+
+# --------------------------------------------------------------------------- #
+# Story 13.3 (Epic 13) — cross-adapter comparison surface (FR10b)             #
+# --------------------------------------------------------------------------- #
+
+
+@dataclass(frozen=True)
+class PairwiseAdapterDelta:
+    """One pairwise cross-adapter delta within `DiscoverabilityComparisonResult` (Story 13.3).
+
+    Carries the Mann-Whitney U result + the per-task pass-rate
+    differential between two adapters. The cohort comparison ships
+    C(N, 2) pairwise deltas across N adapters; each delta is indexed by
+    the ordered key `f"{adapter_a}_vs_{adapter_b}"` in
+    `DiscoverabilityComparisonResult.cross_adapter_deltas`.
+
+    Fields:
+        adapter_a: First adapter name.
+        adapter_b: Second adapter name (must differ from `adapter_a`).
+        pass_rate_delta: ``mean(adapter_a per-task pass rates) - mean(adapter_b)``;
+            in ``[-1.0, 1.0]``. Positive → adapter_a outperforms adapter_b.
+        mann_whitney_result: Story 13.1 ``MannWhitneyResult`` (Mann-Whitney
+            U on the per-task pass rates with `predicate=lambda r: r.pass_rate`).
+        significant_at_alpha_05: ``mann_whitney_result.p_value < 0.05``;
+            redundant with the Mann-Whitney p-value but stored explicitly so
+            consumers can ``Should Be True ${delta.significant_at_alpha_05}``
+            without re-deriving.
+    """
+
+    adapter_a: str
+    adapter_b: str
+    pass_rate_delta: float
+    mann_whitney_result: MannWhitneyResult
+    significant_at_alpha_05: bool
+
+    def __post_init__(self) -> None:
+        if self.adapter_a == self.adapter_b:
+            raise ValueError(
+                f"PairwiseAdapterDelta requires distinct adapters; got "
+                f"adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
+            )
+        if not (-1.0 <= self.pass_rate_delta <= 1.0):
+            raise ValueError(f"pass_rate_delta must be in [-1.0, 1.0]; got {self.pass_rate_delta!r}")
+        # `nan < 0.05` evaluates to False, so significant_at_alpha_05 is
+        # False for nan p_values (identical-samples scipy convention) —
+        # consistent with "cannot reject the null."
+        import math
+
+        p = self.mann_whitney_result.p_value
+        expected = (not math.isnan(p)) and p < 0.05
+        if self.significant_at_alpha_05 != expected:
+            raise ValueError(
+                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as not significant); "
+                f"got significant_at_alpha_05={self.significant_at_alpha_05!r} but "
+                f"p_value={self.mann_whitney_result.p_value!r}"
+            )
+
+
+@dataclass(frozen=True)
+class DiscoverabilityComparisonSummary:
+    """Aggregate roll-up of `DiscoverabilityComparisonResult` (Story 13.3).
+
+    Fields:
+        total_cost_usd: Sum of per-adapter `summary.total_cost_usd` across all adapters.
+        total_runtime_seconds: MAX of per-adapter `summary.total_runtime_seconds`
+            (parallel cross-adapter fan-out wall-clock — adapters run sequentially
+            in Phase-2 but the runtime metric models the eventual parallel target).
+        pass_rate_per_adapter: Mapping of adapter name → overall pass rate
+            (i.e., `per_adapter_results[adapter].summary.overall_pass_rate`).
+        best_adapter: Adapter name with the highest pass rate.
+        worst_adapter: Adapter name with the lowest pass rate. Equals
+            `best_adapter` only when all adapters tie.
+    """
+
+    total_cost_usd: float
+    total_runtime_seconds: float
+    pass_rate_per_adapter: Mapping[str, float]
+    best_adapter: str
+    worst_adapter: str
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "pass_rate_per_adapter", dict(self.pass_rate_per_adapter))
+        if self.best_adapter not in self.pass_rate_per_adapter:
+            raise ValueError(
+                f"best_adapter={self.best_adapter!r} not in "
+                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
+            )
+        if self.worst_adapter not in self.pass_rate_per_adapter:
+            raise ValueError(
+                f"worst_adapter={self.worst_adapter!r} not in "
+                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
+            )
+
+
+@dataclass(frozen=True)
+class DiscoverabilityComparisonResult:
+    """Top-level result of `MCP.Compare Tool Discoverability` (Story 13.3 / PRD FR10b).
+
+    Shape per epics.md L2186-2187 + Story 13.3 D-2 ratified shape:
+        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
+        - `per_adapter_results: Mapping[str, DiscoverabilityResult]` —
+          one full `DiscoverabilityResult` per adapter (mirrors what
+          `MCP.Get Tool Discoverability` returns for the single-adapter case).
+        - `cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]` —
+          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
+          For N=2 there is 1 delta; for N=3 there are 3 deltas.
+        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
+          adapter; rows = task IDs). Built via
+          `CohortHeatmap.from_comparison(self)`.
+        - `summary: DiscoverabilityComparisonSummary` — aggregate roll-up.
+
+    Cross-consistency invariants checked in `__post_init__`:
+        - `len(adapters) >= 2`.
+        - `set(adapters) == set(per_adapter_results.keys())`.
+        - `set(adapters) == set(heatmap.models)`.
+    """
+
+    adapters: tuple[str, ...]
+    per_adapter_results: Mapping[str, DiscoverabilityResult]
+    cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]
+    heatmap: CohortHeatmap
+    summary: DiscoverabilityComparisonSummary
+
+    def __post_init__(self) -> None:
+        # Tuple coercion + defensive Mapping → dict casts (Story 1b.2 M_R6).
+        object.__setattr__(self, "adapters", tuple(self.adapters))
+        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
+        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
+        if len(self.adapters) < 2:
+            raise ValueError(f"DiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
+        if set(self.adapters) != set(self.per_adapter_results.keys()):
+            raise ValueError(
+                f"adapters {sorted(self.adapters)!r} must equal "
+                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
+            )
+        if set(self.adapters) != set(self.heatmap.models):
+            raise ValueError(
+                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
+            )
diff --git a/src/AgentEval/mcp/library.py b/src/AgentEval/mcp/library.py
index 026319d..8cd0c70 100644
--- a/src/AgentEval/mcp/library.py
+++ b/src/AgentEval/mcp/library.py
@@ -73,15 +73,12 @@ from typing import Any
 
 from robot.api.deco import keyword
 
-from AgentEval._kernel.discovery import get_adapter
 from AgentEval._kernel.tier import tier
 from AgentEval.discoverability.loader import load_discoverability_tasks
 from AgentEval.discoverability.schema import (
+    DiscoverabilityComparisonResult,
     DiscoverabilityResult,
-    DiscoverabilitySummary,
-    TaskResult,
 )
-from AgentEval.discoverability.wilson_ci import wilson_score_interval
 from AgentEval.mcp._parser import (
     get_tool_schema,
     parse_mcp_servers,
@@ -533,106 +530,242 @@ class MCPLibrary:
         # Load + validate the tasks YAML.
         task_list = load_discoverability_tasks(tasks)
 
-        # Resolve the adapter (Phase-1 simplified: route ALL kwargs to ctor
-        # like Story 4.3 pre-split-introspection — orchestration's split
-        # logic lives on OrchestrationLibrary, not MCPLibrary; MCPLibrary
-        # is a Phase-1 sub-library that doesn't yet inherit the split.
-        # DF-4.4-S2 carry-over for ctor/run split parity.).
-        adapter_cls = get_adapter(adapter)
-        adapter_ctor_kwargs: dict[str, Any] = dict(kwargs)
-        if model is not None:
-            adapter_ctor_kwargs["model"] = model
-        try:
-            adapter_instance = adapter_cls(**adapter_ctor_kwargs)
-        except TypeError as exc:
-            # Story 4.4 code-review MED-D fix 2026-05-20 (Blind): pre-edit
-            # comment claimed "fall back to no-kwarg construction + log the
-            # dropped kwargs" but the handler actually re-raises with no
-            # fallback. Fixed the comment-vs-code drift — re-raise is
-            # intentional + DF-4.4-S2 carry-over plumbs the real split.
-            raise TypeError(
-                f"Adapter {adapter!r} doesn't accept kwargs {sorted(adapter_ctor_kwargs)}; "
-                "DF-4.4-S2 carry-over (ctor/run split parity for MCPLibrary "
-                "lands in Phase-1.5 — mirroring Story 4.3's "
-                "`_split_adapter_kwargs` introspection on OrchestrationLibrary). "
-                "For now, pass kwargs the adapter accepts."
-            ) from exc
-
-        # Per-call mcp_servers integration is DF-4.1-S2 / DF-4.2-S1; for now
-        # we DON'T forward the mcp_server name since the adapter would just
-        # raise NotImplementedError. Phase-1 dispatches WITHOUT MCP context;
-        # tool-call success is gated on what the model returns from prompt
-        # alone.
-        _ = mcp_server
-
-        per_task: list[TaskResult] = []
-        total_cost = 0.0
-        for task in task_list:
-            tool_calls_per_trial: list[list[Any]] = []
-            cost_per_trial: list[float] = []
-            success_count = 0
-            competing_set: set[str] = set()
-            for _ in range(trials_per_task):
-                run_result = adapter_instance.run(task.prompt)
-                tool_calls_per_trial.append(list(run_result.tool_calls))
-                cost_per_trial.append(run_result.cost_usd)
-                total_cost += run_result.cost_usd
-                called_names = {tc.name for tc in run_result.tool_calls}
-                # Story 4.4 code-review 3-way MED-A fix 2026-05-20 (Edge-cases
-                # M1 + Codex MED + Blind LOW-1): when expected_tools is empty,
-                # wildcard-success mode is active — ANY tool call counts AND
-                # ALL called names go into competing_tools_picked so the
-                # verdict matrix retains visibility into what the model
-                # picked. Pre-edit the `competing_set.update(...)` line was
-                # only reachable in the `if task.expected_tools` branch,
-                # leaving wildcard-mode tasks with permanently-empty
-                # competing_tools_picked.
-                if task.expected_tools:
-                    expected_set = set(task.expected_tools)
-                    if called_names & expected_set:
-                        success_count += 1
-                    competing_set.update(called_names - expected_set)
-                else:
-                    if called_names:
-                        success_count += 1
-                    competing_set.update(called_names)
-            lower, upper = wilson_score_interval(success_count, trials_per_task)
-            per_task.append(
-                TaskResult(
-                    task_id=task.id,
-                    task_prompt=task.prompt,
-                    trials_run=trials_per_task,
-                    success_count=success_count,
-                    tool_calls_per_trial=tool_calls_per_trial,
-                    competing_tools_picked=sorted(competing_set),
-                    cost_per_trial_usd=cost_per_trial,
-                    wilson_ci_lower=lower,
-                    wilson_ci_upper=upper,
-                )
+        # Story 13.3 refactor: per-adapter logic extracted to
+        # `discoverability/_internal.run_single_adapter_discoverability` so
+        # the new `MCP.Compare Tool Discoverability` keyword reuses it
+        # without ~80 LoC duplication. Behavior MUST equal pre-refactor —
+        # verified by Story 4.4's 50+ existing tests passing unchanged.
+        from AgentEval.discoverability._internal import run_single_adapter_discoverability
+
+        return run_single_adapter_discoverability(
+            mcp_server=mcp_server,
+            adapter=adapter,
+            model=model,
+            task_list=task_list,
+            trials_per_task=trials_per_task,
+            max_cost_usd=max_cost_usd,
+            max_runtime_seconds=max_runtime_seconds,
+            extra_adapter_kwargs=dict(kwargs),
+            t_start=t_start,
+        )
+
+    # --------------------------------------------------------------- #
+    # Story 13.3: Cross-adapter comparison (PRD FR10b)
+    # --------------------------------------------------------------- #
+
+    @keyword(name="MCP.Compare Tool Discoverability")
+    @tier(3)
+    def get_tool_discoverability_comparison(
+        self,
+        mcp_server: str = "",
+        adapters: list[str] | None = None,
+        tasks: str = "",
+        trials_per_task: int = 3,
+        max_cost_usd: float = 20.00,
+        max_runtime_seconds: float | None = None,
+        model: str | None = None,
+        **kwargs: Any,
+    ) -> DiscoverabilityComparisonResult:
+        """Compares Tool Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).
+
+        [Tier 3 — Stochastic Fan-Out] — runs `Get Tool Discoverability`
+        once per adapter against the SAME task set, then computes
+        pairwise Mann-Whitney U deltas across the per-task pass-rate
+        distributions. Returns a `DiscoverabilityComparisonResult` with
+        per-adapter results + cross-adapter deltas + multi-column
+        cohort heatmap + aggregate summary.
+
+        Requires the ``[agenteval-advanced]`` optional extra (scipy +
+        numpy) for the Mann-Whitney U cross-adapter delta computation;
+        raises ``ImportError`` on invocation WITHOUT the extra (fail-fast
+        BEFORE running any per-adapter fan-out — operators discovering
+        the missing extra should not pay 3-adapter trial cost first).
+
+        | =Arguments= | =Description= |
+        | ``mcp_server`` | Name of the MCP server (per `Start Server`). Same Phase-1 carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). |
+        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. N=3+ enables ranking across Claude/GPT/Copilot/.... |
+        | ``tasks`` | Path to the discoverability tasks YAML (loaded ONCE; shared across adapters). |
+        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
+        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2186 (4× the single-adapter default reflecting N=3-adapter typical cost). Phase-1 carve-out DF-13.3-S1: tracked NOT enforced (same MCPLibrary architectural gap as DF-4.4-S1 / C20). |
+        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. |
+        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. Phase-2.5 (DF-13.3-S4): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg. |
+        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |
+
+        Returns ``DiscoverabilityComparisonResult`` with ``adapters`` +
+        ``per_adapter_results`` (one ``DiscoverabilityResult`` per
+        adapter) + ``cross_adapter_deltas`` (C(N, 2) ``PairwiseAdapterDelta``
+        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
+        ``CohortHeatmap`` via ``from_comparison``) + ``summary``
+        (``DiscoverabilityComparisonSummary``).
+
+        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
+        missing (Mann-Whitney U requires scipy/numpy). Raises
+        ``ValueError`` on missing/empty ``mcp_server`` / ``tasks`` /
+        ``adapters`` (≥2 required) / invalid ``trials_per_task``.
+        Raises ``InvalidDiscoverabilityTasksError`` on tasks YAML
+        parse/schema failure. Raises ``AdapterDiscoveryError`` on
+        unknown adapter name.
+
+        Example:
+        | ${comparison}=    `MCP.Compare Tool Discoverability`
+        | ...    mcp_server=rf-mcp
+        | ...    adapters=${{['generic', 'claude_code_cli', 'codex_cli']}}
+        | ...    tasks=${CURDIR}/tasks.yaml
+        | ...    trials_per_task=5
+        | ...    max_cost_usd=20.00
+        | Should Be Equal As Strings    ${comparison.summary.best_adapter}    claude_code_cli
+        | Should Be True    ${comparison.cross_adapter_deltas['generic_vs_codex_cli'].significant_at_alpha_05}
+
+        Notes:
+        - Story 13.3 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra (the Mann-Whitney U dependency from Story 13.1).
+        - PRD FR10b ratifies the ``DiscoverabilityComparisonResult`` shape; epics.md L2186-2189 ratifies the keyword signature + behavior.
+        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper at ``src/AgentEval/stats/mannwhitney.py``). The keyword surface ``Stat.Mann Whitney U`` is NOT called here because the input is ``list[float]`` per-task pass rates (NOT ``list[KeywordRun]``).
+        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition; no bit-identical FR31a guarantee (Story 13.1 HIGH-C concern doesn't apply at @tier(3)).
+        - Phase-1 carve-out DF-13.3-S1: ``@guarded_fanout`` enforcement DEFERRED (same MCPLibrary architectural gap as DF-4.4-S1 / C20).
+        - Phase-2.5 carry-overs: DF-13.3-S2 (per-adapter MCP attachment gated on C72 + C68/C69/C73/C75); DF-13.3-S3 (Bonferroni / Holm multi-pairwise correction).
+        - Sibling keyword: `MCP.Get Tool Discoverability` (Phase-1 single-adapter; this keyword's N=1 case is intentionally rejected via the ≥2 validation — single-adapter callers should use the simpler `Get` keyword).
+        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
+        t_start = time.monotonic()
+
+        # Validate args (mirrors single-adapter Get + adds N≥2 constraint).
+        if not mcp_server:
+            raise ValueError(
+                "MCP.Compare Tool Discoverability requires `mcp_server=<name>` kwarg "
+                "(name of an MCP server started via `MCP.Start Server`); empty "
+                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
+                "adapter-side integration."
+            )
+        if not tasks:
+            raise ValueError("MCP.Compare Tool Discoverability requires `tasks=<yaml-path>` kwarg")
+        if trials_per_task < 1:
+            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
+        if adapters is None or len(adapters) < 2:
+            raise ValueError(
+                f"MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, "
+                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
+            )
+        if len(set(adapters)) != len(adapters):
+            raise ValueError(
+                f"MCP.Compare Tool Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
             )
-        total_runtime = time.monotonic() - t_start
-
-        # Overall pass rate: weighted by trials.
-        total_trials = sum(t.trials_run for t in per_task)
-        total_successes = sum(t.success_count for t in per_task)
-        overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0
-
-        # Phase-1: mcp_coverage hardcoded to "hosted_in_process" since
-        # Phase-1 doesn't yet attach real MCP via the adapter (DF-4.4-S3
-        # carry-over: Epic 5 hosted-MCP observer wires real coverage detection).
-        _ = max_cost_usd
-        _ = max_runtime_seconds
-        # Story 4.4 code-review HIGH-B fix 2026-05-20 (Auditor citation-drift
-        # catch): PRD FR10a L1499 ratifies `summary` nesting for the aggregate
-        # roll-up; pre-edit shape flattened the 3 summary fields into
-        # top-level result attributes. "Fix-the-losing-source-NOW" pattern
-        # per feedback_citation_drift_first_class — implementation realigned.
-        return DiscoverabilityResult(
-            per_task_results=per_task,
-            summary=DiscoverabilitySummary(
-                overall_pass_rate=overall_pass_rate,
-                total_cost_usd=total_cost,
-                total_runtime_seconds=total_runtime,
-            ),
-            mcp_coverage="hosted_in_process",
+
+        # `[agenteval-advanced]` extras gate (D-6 + L-2). Fail-fast BEFORE
+        # the per-adapter fan-out so operators discovering the missing
+        # extra don't pay N-adapter trial cost first. Direct raise per
+        # AC-13.3.4 in-flight decision (b) — the `Stat.`-prefixed helper
+        # `_raise_advanced_extra_missing` would mis-frame the message
+        # for an `MCP.`-prefixed keyword.
+        #
+        # Read the attribute via module-level access (NOT
+        # `from X import Y` which binds a local) so test
+        # `monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)`
+        # is observed correctly even when this code path runs AFTER
+        # Story 13.1's `test_advanced_extras_gate.py` has run + cleaned
+        # up its own monkeypatch in the same pytest session.
+        from AgentEval.stats import library as _stats_lib
+
+        if not _stats_lib._ADVANCED_AVAILABLE:
+            raise ImportError(
+                "MCP.Compare Tool Discoverability: scipy + numpy required. "
+                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
+            )
+
+        # Load tasks YAML ONCE (shared across adapters).
+        task_list = load_discoverability_tasks(tasks)
+
+        # Run per-adapter discoverability serially. Phase-2.5 may parallelize
+        # via thread pool / asyncio; Phase-2 ships serial for simplicity +
+        # safer cost accounting.
+        from AgentEval._heatmap.models import CohortHeatmap
+        from AgentEval.discoverability._internal import run_single_adapter_discoverability
+        from AgentEval.discoverability.schema import (
+            DiscoverabilityComparisonResult,
+            DiscoverabilityComparisonSummary,
+            PairwiseAdapterDelta,
+        )
+        from AgentEval.stats.mannwhitney import compute_mann_whitney_u
+
+        per_adapter_results: dict[str, DiscoverabilityResult] = {}
+        for adapter_name in adapters:
+            per_adapter_results[adapter_name] = run_single_adapter_discoverability(
+                mcp_server=mcp_server,
+                adapter=adapter_name,
+                model=model,
+                task_list=task_list,
+                trials_per_task=trials_per_task,
+                max_cost_usd=max_cost_usd,
+                max_runtime_seconds=max_runtime_seconds,
+                extra_adapter_kwargs=dict(kwargs),
+                t_start=time.monotonic(),  # per-adapter timer; aggregate uses MAX.
+            )
+
+        # Build C(N, 2) pairwise deltas. Ordering: itertools.combinations
+        # preserves input order so `adapter_a` always comes before
+        # `adapter_b` in the input list.
+        import itertools
+
+        cross_adapter_deltas: dict[str, PairwiseAdapterDelta] = {}
+        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
+            rates_a = [t.pass_rate for t in per_adapter_results[adapter_a].per_task_results]
+            rates_b = [t.pass_rate for t in per_adapter_results[adapter_b].per_task_results]
+            # Empty per-task lists guard: skip the comparison if either is
+            # empty (would otherwise raise from `compute_mann_whitney_u`).
+            if not rates_a or not rates_b:
+                continue
+            mwu = compute_mann_whitney_u(rates_a, rates_b)
+            delta_key = f"{adapter_a}_vs_{adapter_b}"
+            mean_a = sum(rates_a) / len(rates_a)
+            mean_b = sum(rates_b) / len(rates_b)
+            import math as _math
+
+            cross_adapter_deltas[delta_key] = PairwiseAdapterDelta(
+                adapter_a=adapter_a,
+                adapter_b=adapter_b,
+                pass_rate_delta=mean_a - mean_b,
+                mann_whitney_result=mwu,
+                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
+            )
+
+        # Build summary aggregate.
+        pass_rate_per_adapter = {name: per_adapter_results[name].summary.overall_pass_rate for name in adapters}
+        best_adapter = max(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
+        worst_adapter = min(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
+        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
+        # Wall-clock: MAX models eventual parallel fan-out target (per dataclass docs).
+        total_runtime = max(r.summary.total_runtime_seconds for r in per_adapter_results.values())
+        summary = DiscoverabilityComparisonSummary(
+            total_cost_usd=total_cost,
+            total_runtime_seconds=total_runtime,
+            pass_rate_per_adapter=pass_rate_per_adapter,
+            best_adapter=best_adapter,
+            worst_adapter=worst_adapter,
+        )
+
+        # Build a provisional comparison result so CohortHeatmap.from_comparison
+        # can read the per-adapter results. The CohortHeatmap construction
+        # happens AFTER per_adapter_results is populated; we pass a
+        # "placeholder" comparison via direct construction (the
+        # CohortHeatmap.from_comparison reads result.adapters + result.per_adapter_results
+        # only, NOT the heatmap field — no chicken-and-egg).
+        #
+        # Build the heatmap via a lightweight namespace stand-in: the
+        # classmethod accesses .adapters + .per_adapter_results.
+        class _ComparisonShim:
+            pass
+
+        shim = _ComparisonShim()
+        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
+        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
+        heatmap = CohortHeatmap.from_comparison(shim)  # type: ignore[arg-type]
+
+        # Track end-to-end runtime (caller-side; not stored separately
+        # but contributes to the per-adapter timers we MAX'd above).
+        _ = t_start
+
+        return DiscoverabilityComparisonResult(
+            adapters=tuple(adapters),
+            per_adapter_results=per_adapter_results,
+            cross_adapter_deltas=cross_adapter_deltas,
+            heatmap=heatmap,
+            summary=summary,
         )
diff --git a/src/AgentEval/stats/types.py b/src/AgentEval/stats/types.py
index 9c2d974..d65f60a 100644
--- a/src/AgentEval/stats/types.py
+++ b/src/AgentEval/stats/types.py
@@ -64,14 +64,22 @@ class MannWhitneyResult:
     n_b: int
 
     def __post_init__(self) -> None:
+        import math
+
         if self.n_a < 1:
             raise ValueError(f"n_a must be >= 1; got {self.n_a!r}")
         if self.n_b < 1:
             raise ValueError(f"n_b must be >= 1; got {self.n_b!r}")
         if not (-1.0 <= self.effect_size_r <= 1.0):
             raise ValueError(f"effect_size_r must be in [-1.0, 1.0]; got {self.effect_size_r!r}")
-        if not (0.0 <= self.p_value <= 1.0):
-            raise ValueError(f"p_value must be in [0.0, 1.0]; got {self.p_value!r}")
+        # `p_value=nan` is the scipy convention when both samples have
+        # identical rank distributions (no variance → no test possible).
+        # Permit nan + the [0, 1] range; reject anything else.
+        if not (math.isnan(self.p_value) or 0.0 <= self.p_value <= 1.0):
+            raise ValueError(
+                f"p_value must be in [0.0, 1.0] or nan (scipy identical-samples convention); "
+                f"got {self.p_value!r}"
+            )
 
 
 @dataclass(frozen=True, slots=True)
diff --git a/tests/integration/discoverability/__init__.py b/tests/integration/discoverability/__init__.py
new file mode 100644
index 0000000..9ae05e2
--- /dev/null
+++ b/tests/integration/discoverability/__init__.py
@@ -0,0 +1,7 @@
+# Copyright 2026 Many Kasiriha
+#
+# Licensed under the Apache License, Version 2.0 (the "License");
+# you may not use this file except in compliance with the License.
+# You may obtain a copy of the License at
+#
+#     http://www.apache.org/licenses/LICENSE-2.0
diff --git a/tests/integration/discoverability/test_compare_e2e.py b/tests/integration/discoverability/test_compare_e2e.py
new file mode 100644
index 0000000..2ab8c0e
--- /dev/null
+++ b/tests/integration/discoverability/test_compare_e2e.py
@@ -0,0 +1,187 @@
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
+"""End-to-end integration test for `MCP.Compare Tool Discoverability` (Story 13.3 AC-13.3.8).
+
+Per Story 13.1 L-4 lesson (empirical correctness verification): asserts
+CONCRETE numerical outcomes of the cross-adapter comparison — known
+stub pass-rate distributions produce the EXPECTED ranking + p-value
+signs, NOT just "the keyword ran without error."
+
+3 stubs via `register_adapter()` (mirrors Story 12.3 + Story 7.3
+canonical pattern):
+- `compare_stub_a` → 100% success on all tasks/trials.
+- `compare_stub_b` → 50% success (alternating per call).
+- `compare_stub_c` → 0% success.
+
+Expected outcomes:
+- per-adapter pass rates: a=1.0, b=0.5, c=0.0.
+- summary.best_adapter == "compare_stub_a"; worst_adapter == "compare_stub_c".
+- 3 pairwise deltas keyed by f"{a}_vs_{b}".
+- a-vs-c delta: p_value < 0.05 (significant).
+- heatmap.models has 3 columns + heatmap.tasks matches the YAML task count.
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
+# Phase-2 deps required.
+pytest.importorskip("scipy")
+pytest.importorskip("numpy")
+pytest.importorskip("opentelemetry")
+
+from AgentEval._kernel import discovery  # noqa: E402
+from AgentEval._kernel.discovery import register_adapter  # noqa: E402
+from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
+from AgentEval.discoverability.schema import DiscoverabilityComparisonResult  # noqa: E402
+from AgentEval.mcp.library import MCPLibrary  # noqa: E402
+from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402
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
+def _make_stub_adapter(success_pattern: list[bool], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
+    """Build a stub adapter that emits `echo_back` on success, no tools on fail."""
+
+    class _Stub(InProcessAdapter):
+        _call_idx = 0
+
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__()
+
+        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
+            idx = type(self)._call_idx
+            type(self)._call_idx += 1
+            success = success_pattern[idx % len(success_pattern)] if success_pattern else False
+            names = ["echo_back"] if success else []
+            tool_calls = [
+                ToolCallTrace(
+                    name=n,
+                    args={},
+                    result=None,
+                    error=None,
+                    latency_ms=1.0,
+                    source="adapter",
+                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
+                    sequence_index=i,
+                )
+                for i, n in enumerate(names)
+            ]
+            return AgentRunResult(
+                response_text=f"stub-{idx}",
+                tool_calls=tool_calls,
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=cost_per_call,
+                latency_seconds=0.001,
+                trace_id=f"stub-id-{idx:032d}"[:32],
+            )
+
+    return _Stub
+
+
+def test_compare_3_stub_adapters_end_to_end(tmp_path: Path) -> None:
+    """3-stub cross-adapter comparison produces expected ranking + significant a-vs-c delta."""
+    # Register 3 stubs with deterministic + KNOWN-different pass rates.
+    # Pass pattern length-1 → constant across all calls.
+    register_adapter("compare_stub_a", _make_stub_adapter([True]))  # 100%
+    register_adapter("compare_stub_b", _make_stub_adapter([True, False]))  # 50%
+    register_adapter("compare_stub_c", _make_stub_adapter([False]))  # 0%
+
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+
+    lib = MCPLibrary()
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["compare_stub_a", "compare_stub_b", "compare_stub_c"],
+        tasks=str(fixture_path),
+        trials_per_task=10,  # enough for Mann-Whitney to have power.
+        model=None,
+    )
+
+    assert isinstance(result, DiscoverabilityComparisonResult)
+
+    # Per-adapter overall pass rates.
+    a_rate = result.per_adapter_results["compare_stub_a"].summary.overall_pass_rate
+    b_rate = result.per_adapter_results["compare_stub_b"].summary.overall_pass_rate
+    c_rate = result.per_adapter_results["compare_stub_c"].summary.overall_pass_rate
+    assert a_rate == pytest.approx(1.0)
+    assert b_rate == pytest.approx(0.5)
+    assert c_rate == pytest.approx(0.0)
+
+    # Summary ranking.
+    assert result.summary.best_adapter == "compare_stub_a"
+    assert result.summary.worst_adapter == "compare_stub_c"
+
+    # All 3 pairwise deltas present + correctly keyed.
+    assert set(result.cross_adapter_deltas.keys()) == {
+        "compare_stub_a_vs_compare_stub_b",
+        "compare_stub_a_vs_compare_stub_c",
+        "compare_stub_b_vs_compare_stub_c",
+    }
+
+    # a-vs-c delta: max-effect (a always-pass vs c always-fail) → p < 0.05.
+    ac_delta = result.cross_adapter_deltas["compare_stub_a_vs_compare_stub_c"]
+    assert ac_delta.pass_rate_delta == pytest.approx(1.0)
+    assert ac_delta.significant_at_alpha_05
+
+    # Heatmap: 3 columns, M rows (M = task count from YAML).
+    assert result.heatmap.models == ("compare_stub_a", "compare_stub_b", "compare_stub_c")
+    assert len(result.heatmap.tasks) >= 1  # at least 1 task from the YAML.
+
+    # Cost: 3 adapters × M tasks × 10 trials × 0.001 each.
+    expected_cost = 3 * len(result.heatmap.tasks) * 10 * 0.001
+    assert result.summary.total_cost_usd == pytest.approx(expected_cost)
+
+
+def test_compare_rejects_single_adapter_list_at_arg_validation(tmp_path: Path) -> None:
+    """≥2 adapter requirement enforced at arg validation."""
+    register_adapter("only_one", _make_stub_adapter([True]))
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+    lib = MCPLibrary()
+    with pytest.raises(ValueError, match=">= 2 entries"):
+        lib.get_tool_discoverability_comparison(
+            mcp_server="echo",
+            adapters=["only_one"],
+            tasks=str(fixture_path),
+            trials_per_task=1,
+        )
+
+
+def test_compare_rejects_duplicate_adapter_names(tmp_path: Path) -> None:
+    """Duplicate adapter names in `adapters` list raise ValueError."""
+    register_adapter("dup_a", _make_stub_adapter([True]))
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+    lib = MCPLibrary()
+    with pytest.raises(ValueError, match="distinct adapter names"):
+        lib.get_tool_discoverability_comparison(
+            mcp_server="echo",
+            adapters=["dup_a", "dup_a"],
+            tasks=str(fixture_path),
+            trials_per_task=1,
+        )
diff --git a/tests/unit/discoverability/test_comparison.py b/tests/unit/discoverability/test_comparison.py
new file mode 100644
index 0000000..3eb9dc0
--- /dev/null
+++ b/tests/unit/discoverability/test_comparison.py
@@ -0,0 +1,440 @@
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
+"""Unit tests for `MCP.Compare Tool Discoverability` cross-adapter surface (Story 13.3).
+
+Coverage:
+- `DiscoverabilityComparisonResult` / `PairwiseAdapterDelta` /
+  `DiscoverabilityComparisonSummary` dataclass validators.
+- `CohortHeatmap.from_comparison` multi-column heatmap.
+- Pairwise delta computation (C(N, 2) coverage for N=2 + N=3).
+- Mann-Whitney U dispatch via the Story 13.1 pure helper.
+
+ImportError-gate tests for the `[agenteval-advanced]` extra requirement
+live in the companion `test_comparison_extras_gate.py` file per Story
+13.1 L-2 lesson (NO top-level `importorskip` so they run in both base
++ WITH-extras CI envs).
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+from typing import Any
+
+import pytest
+
+# Phase-2 deps required.
+pytest.importorskip("scipy")
+pytest.importorskip("numpy")
+pytest.importorskip("opentelemetry")
+
+from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
+from AgentEval._kernel.discovery import register_adapter  # noqa: E402
+from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
+from AgentEval.discoverability.schema import (  # noqa: E402
+    DiscoverabilityComparisonResult,
+    DiscoverabilityComparisonSummary,
+    DiscoverabilityResult,
+    DiscoverabilitySummary,
+    PairwiseAdapterDelta,
+    TaskResult,
+)
+from AgentEval.mcp.library import MCPLibrary  # noqa: E402
+from AgentEval.stats.types import MannWhitneyResult  # noqa: E402
+from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402
+
+# --------------------------------------------------------------------------- #
+# Stub adapter factory (reused from test_keyword.py pattern)                  #
+# --------------------------------------------------------------------------- #
+
+
+def _make_stub_adapter(tool_names_per_call: list[list[str]], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
+    class _StubAdapter(InProcessAdapter):
+        _call_idx = 0
+
+        def __init__(self, **kwargs: Any) -> None:
+            super().__init__()
+            self._kwargs = kwargs
+
+        def run(
+            self,
+            prompt: str,
+            tools: Any = None,
+            mcp_servers: Any = None,
+            **kwargs: Any,
+        ) -> AgentRunResult:
+            idx = type(self)._call_idx
+            type(self)._call_idx += 1
+            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
+            tool_calls = [
+                ToolCallTrace(
+                    name=name,
+                    args={},
+                    result=None,
+                    error=None,
+                    latency_ms=1.0,
+                    source="adapter",
+                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
+                    sequence_index=i,
+                )
+                for i, name in enumerate(names)
+            ]
+            return AgentRunResult(
+                response_text=f"stub-{idx}",
+                tool_calls=tool_calls,
+                usage=Usage(input_tokens=1, output_tokens=1),
+                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
+                cost_usd=cost_per_call,
+                latency_seconds=0.001,
+                trace_id=f"stub-id-{idx:032d}"[:32],
+            )
+
+    return _StubAdapter
+
+
+@pytest.fixture
+def lib() -> MCPLibrary:
+    return MCPLibrary()
+
+
+@pytest.fixture
+def fixture_path() -> Path:
+    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+
+
+# --------------------------------------------------------------------------- #
+# Helper builders for dataclass validator tests                               #
+# --------------------------------------------------------------------------- #
+
+
+def _make_mwu(p_value: float = 0.5) -> MannWhitneyResult:
+    return MannWhitneyResult(u_statistic=10.0, p_value=p_value, effect_size_r=0.0, n_a=5, n_b=5)
+
+
+def _make_discoverability_result(pass_rate: float, n_tasks: int = 3) -> DiscoverabilityResult:
+    per_task = [
+        TaskResult(
+            task_id=f"t{i}",
+            task_prompt=f"prompt {i}",
+            trials_run=10,
+            success_count=int(pass_rate * 10),
+            tool_calls_per_trial=[],
+            competing_tools_picked=[],
+            cost_per_trial_usd=[],
+            wilson_ci_lower=0.0,
+            wilson_ci_upper=1.0,
+        )
+        for i in range(n_tasks)
+    ]
+    return DiscoverabilityResult(
+        per_task_results=per_task,
+        summary=DiscoverabilitySummary(overall_pass_rate=pass_rate, total_cost_usd=0.0, total_runtime_seconds=0.1),
+        mcp_coverage="hosted_in_process",
+    )
+
+
+# --------------------------------------------------------------------------- #
+# Dataclass validators (6 tests)                                              #
+# --------------------------------------------------------------------------- #
+
+
+def test_comparison_result_rejects_single_adapter() -> None:
+    """len(adapters) < 2 raises ValueError."""
+    per = {"a": _make_discoverability_result(1.0)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a",), cells=(("t0", "a", 1.0),))
+    summary = DiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        pass_rate_per_adapter={"a": 1.0},
+        best_adapter="a",
+        worst_adapter="a",
+    )
+    with pytest.raises(ValueError, match="len\\(adapters\\) >= 2"):
+        DiscoverabilityComparisonResult(
+            adapters=("a",),
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_comparison_result_rejects_adapters_keys_mismatch() -> None:
+    """adapters ↔ per_adapter_results key mismatch raises ValueError."""
+    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
+    summary = DiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
+        best_adapter="a",
+        worst_adapter="b",
+    )
+    with pytest.raises(ValueError, match="per_adapter_results keys"):
+        DiscoverabilityComparisonResult(
+            adapters=("a", "c"),  # 'c' not in per
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_comparison_result_rejects_heatmap_models_mismatch() -> None:
+    """adapters ↔ heatmap.models mismatch raises ValueError."""
+    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
+    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "wrong"), cells=())
+    summary = DiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
+        best_adapter="a",
+        worst_adapter="b",
+    )
+    with pytest.raises(ValueError, match="heatmap.models"):
+        DiscoverabilityComparisonResult(
+            adapters=("a", "b"),
+            per_adapter_results=per,
+            cross_adapter_deltas={},
+            heatmap=heatmap,
+            summary=summary,
+        )
+
+
+def test_pairwise_delta_rejects_identical_adapters() -> None:
+    """adapter_a == adapter_b raises ValueError."""
+    with pytest.raises(ValueError, match="distinct adapters"):
+        PairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="a",
+            pass_rate_delta=0.0,
+            mann_whitney_result=_make_mwu(),
+            significant_at_alpha_05=False,
+        )
+
+
+def test_pairwise_delta_rejects_out_of_range_delta() -> None:
+    """pass_rate_delta outside [-1, 1] raises ValueError."""
+    with pytest.raises(ValueError, match="pass_rate_delta"):
+        PairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="b",
+            pass_rate_delta=1.5,
+            mann_whitney_result=_make_mwu(),
+            significant_at_alpha_05=False,
+        )
+
+
+def test_pairwise_delta_rejects_significance_inconsistency() -> None:
+    """significant_at_alpha_05 vs p_value inconsistency raises ValueError."""
+    with pytest.raises(ValueError, match="significant_at_alpha_05"):
+        PairwiseAdapterDelta(
+            adapter_a="a",
+            adapter_b="b",
+            pass_rate_delta=0.0,
+            mann_whitney_result=_make_mwu(p_value=0.5),  # > 0.05
+            significant_at_alpha_05=True,  # but claims significant
+        )
+
+
+def test_comparison_summary_rejects_unknown_best_adapter() -> None:
+    """best_adapter not in pass_rate_per_adapter raises ValueError."""
+    with pytest.raises(ValueError, match="best_adapter"):
+        DiscoverabilityComparisonSummary(
+            total_cost_usd=0.0,
+            total_runtime_seconds=0.0,
+            pass_rate_per_adapter={"a": 0.5},
+            best_adapter="unknown",
+            worst_adapter="a",
+        )
+
+
+# --------------------------------------------------------------------------- #
+# CohortHeatmap.from_comparison (4 tests)                                     #
+# --------------------------------------------------------------------------- #
+
+
+def _make_minimal_comparison(adapters: list[str]) -> DiscoverabilityComparisonResult:
+    """Build a minimal valid comparison for testing the heatmap classmethod."""
+    per = {a: _make_discoverability_result(0.5, n_tasks=2) for a in adapters}
+    cells = tuple((t.task_id, a, t.pass_rate) for a in adapters for t in per[a].per_task_results)
+    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=tuple(adapters), cells=cells)
+    summary = DiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        pass_rate_per_adapter=dict.fromkeys(adapters, 0.5),
+        best_adapter=adapters[0],
+        worst_adapter=adapters[0],
+    )
+    return DiscoverabilityComparisonResult(
+        adapters=tuple(adapters),
+        per_adapter_results=per,
+        cross_adapter_deltas={},
+        heatmap=heatmap,
+        summary=summary,
+    )
+
+
+def test_heatmap_from_comparison_2_adapters() -> None:
+    """2-adapter comparison → 2-column heatmap."""
+    result = _make_minimal_comparison(["a", "b"])
+    h = CohortHeatmap.from_comparison(result)
+    assert h.models == ("a", "b")
+    assert h.tasks == ("t0", "t1")
+
+
+def test_heatmap_from_comparison_3_adapters() -> None:
+    """3-adapter comparison → 3-column heatmap."""
+    result = _make_minimal_comparison(["a", "b", "c"])
+    h = CohortHeatmap.from_comparison(result)
+    assert h.models == ("a", "b", "c")
+    assert len(h.tasks) == 2
+
+
+def test_heatmap_from_comparison_per_task_pass_rate_in_cells() -> None:
+    """Per-task pass rate dispatched to correct cell."""
+    per = {
+        "fast": _make_discoverability_result(1.0, n_tasks=2),
+        "slow": _make_discoverability_result(0.0, n_tasks=2),
+    }
+    cells = tuple((t.task_id, a, t.pass_rate) for a in ("fast", "slow") for t in per[a].per_task_results)
+    heatmap = CohortHeatmap(tasks=("t0", "t1"), models=("fast", "slow"), cells=cells)
+    summary = DiscoverabilityComparisonSummary(
+        total_cost_usd=0.0,
+        total_runtime_seconds=0.0,
+        pass_rate_per_adapter={"fast": 1.0, "slow": 0.0},
+        best_adapter="fast",
+        worst_adapter="slow",
+    )
+    result = DiscoverabilityComparisonResult(
+        adapters=("fast", "slow"),
+        per_adapter_results=per,
+        cross_adapter_deltas={},
+        heatmap=heatmap,
+        summary=summary,
+    )
+    h = CohortHeatmap.from_comparison(result)
+    data = h.as_dict()
+    assert data["t0"]["fast"] == 1.0
+    assert data["t0"]["slow"] == 0.0
+
+
+def test_heatmap_from_comparison_as_ascii_3_columns() -> None:
+    """as_ascii() produces ≥3 columns when 3 adapters provided."""
+    result = _make_minimal_comparison(["a", "b", "c"])
+    h = CohortHeatmap.from_comparison(result)
+    ascii_table = h.as_ascii()
+    # Header row has 4 segments: Task + 3 adapter names.
+    assert "a" in ascii_table
+    assert "b" in ascii_table
+    assert "c" in ascii_table
+    assert "Task" in ascii_table
+
+
+# --------------------------------------------------------------------------- #
+# Pairwise delta computation via end-to-end keyword (3 tests)                 #
+# --------------------------------------------------------------------------- #
+
+
+def test_compare_2_adapters_produces_1_pairwise_delta(lib: MCPLibrary, fixture_path: Path) -> None:
+    """2 adapters → 1 pairwise delta keyed `a_vs_b`."""
+    register_adapter("c2_pass", _make_stub_adapter([["echo_back"]] * 30))
+    register_adapter("c2_fail", _make_stub_adapter([[]] * 30))
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["c2_pass", "c2_fail"],
+        tasks=str(fixture_path),
+        trials_per_task=5,
+    )
+    assert len(result.cross_adapter_deltas) == 1
+    assert "c2_pass_vs_c2_fail" in result.cross_adapter_deltas
+
+
+def test_compare_3_adapters_produces_3_pairwise_deltas(lib: MCPLibrary, fixture_path: Path) -> None:
+    """3 adapters → 3 pairwise deltas (C(3,2))."""
+    register_adapter("c3_a", _make_stub_adapter([["echo_back"]] * 30))
+    # Alternating pass/fail per call so per-task variance ≠ 0.
+    register_adapter(
+        "c3_b",
+        _make_stub_adapter([(["echo_back"] if i % 2 == 0 else []) for i in range(30)]),
+    )
+    register_adapter("c3_c", _make_stub_adapter([[]] * 30))
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["c3_a", "c3_b", "c3_c"],
+        tasks=str(fixture_path),
+        trials_per_task=5,
+    )
+    assert len(result.cross_adapter_deltas) == 3
+    assert set(result.cross_adapter_deltas.keys()) == {
+        "c3_a_vs_c3_b",
+        "c3_a_vs_c3_c",
+        "c3_b_vs_c3_c",
+    }
+
+
+def test_compare_pairwise_keys_preserve_input_order(lib: MCPLibrary, fixture_path: Path) -> None:
+    """Pairwise delta keys preserve input adapter order (a comes before b)."""
+    register_adapter("zzz_first", _make_stub_adapter([[]] * 30))
+    register_adapter("aaa_second", _make_stub_adapter([[]] * 30))
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["zzz_first", "aaa_second"],
+        tasks=str(fixture_path),
+        trials_per_task=5,
+    )
+    # 'zzz_first' was passed first → it's adapter_a; 'aaa_second' is adapter_b.
+    assert "zzz_first_vs_aaa_second" in result.cross_adapter_deltas
+
+
+# --------------------------------------------------------------------------- #
+# Mann-Whitney U dispatch + significance ranking (2 tests)                    #
+# --------------------------------------------------------------------------- #
+
+
+def test_compare_clearly_different_distributions_significant(lib: MCPLibrary, fixture_path: Path) -> None:
+    """2 adapters with KNOWN-different pass rates → Mann-Whitney p < 0.05.
+
+    Stub 'always-pass' (100%) vs 'always-fail' (0%) across 5 tasks × 5 trials
+    yields max-effect Mann-Whitney U. p_value should be small enough to
+    reject the null at α=0.05.
+    """
+    register_adapter("mwu_pass", _make_stub_adapter([["echo_back"]] * 30))
+    register_adapter("mwu_fail", _make_stub_adapter([[]] * 30))
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["mwu_pass", "mwu_fail"],
+        tasks=str(fixture_path),
+        trials_per_task=5,
+    )
+    delta = result.cross_adapter_deltas["mwu_pass_vs_mwu_fail"]
+    # mwu_pass mean pass_rate = 1.0; mwu_fail = 0.0; delta = 1.0.
+    assert delta.pass_rate_delta == pytest.approx(1.0)
+    # Mann-Whitney U on identical-ranks-per-group should reject the null.
+    assert delta.significant_at_alpha_05
+
+
+def test_compare_identical_distributions_not_significant(lib: MCPLibrary, fixture_path: Path) -> None:
+    """2 adapters with IDENTICAL pass-rate distributions → Mann-Whitney p > 0.05."""
+    register_adapter("mwu_id_a", _make_stub_adapter([["echo_back"]] * 30))
+    register_adapter("mwu_id_b", _make_stub_adapter([["echo_back"]] * 30))
+    result = lib.get_tool_discoverability_comparison(
+        mcp_server="echo",
+        adapters=["mwu_id_a", "mwu_id_b"],
+        tasks=str(fixture_path),
+        trials_per_task=5,
+    )
+    delta = result.cross_adapter_deltas["mwu_id_a_vs_mwu_id_b"]
+    assert delta.pass_rate_delta == pytest.approx(0.0)
+    assert not delta.significant_at_alpha_05
diff --git a/tests/unit/discoverability/test_comparison_extras_gate.py b/tests/unit/discoverability/test_comparison_extras_gate.py
new file mode 100644
index 0000000..12155c0
--- /dev/null
+++ b/tests/unit/discoverability/test_comparison_extras_gate.py
@@ -0,0 +1,130 @@
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
+"""ImportError-gate tests for `MCP.Compare Tool Discoverability` (Story 13.3 L-2 lesson).
+
+Mirrors `tests/unit/stats/test_advanced_extras_gate.py` (Story 13.1) +
+`tests/unit/telemetry/test_backends_otlp_extras_gate.py` (Story 13.2)
+discipline: NO module-top `pytest.importorskip` so these tests run in
+BOTH the WITH-extras and WITHOUT-extras CI environments.
+
+Per AC-13.3.4 + Story 13.1 L-2 lesson: the WITHOUT-extras CI matrix
+MUST verify (a) the comparison schema module imports without scipy;
+(b) the keyword raises the spec-mandated ImportError when invoked
+without scipy/numpy; (c) the ImportError message contains the verbatim
+`uv pip install robotframework-agenteval[agenteval-advanced]` install
+hint.
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+
+def test_comparison_schema_importable_without_extra() -> None:
+    """`from AgentEval.discoverability.schema import DiscoverabilityComparisonResult` succeeds without `[agenteval-advanced]`.
+
+    The dataclasses reference `MannWhitneyResult` via `TYPE_CHECKING`
+    only — no runtime scipy import at module load time.
+    """
+    from AgentEval.discoverability.schema import (  # noqa: F401
+        DiscoverabilityComparisonResult,
+        DiscoverabilityComparisonSummary,
+        PairwiseAdapterDelta,
+    )
+
+
+def test_compare_keyword_raises_import_error_when_advanced_extra_missing(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """`MCP.Compare Tool Discoverability` raises ImportError when `_ADVANCED_AVAILABLE=False`.
+
+    Monkeypatches the Story 13.1 module-level gate directly (vs reloading
+    the module with scipy stubbed out) per Story 13.1 review HIGH-B lesson.
+    The gate check sits BEFORE the per-adapter fan-out (D-6 fail-fast)
+    so operators discovering the missing extra do not pay any trial cost.
+    """
+    pytest.importorskip("opentelemetry")  # MCPLibrary infrastructure dep.
+
+    from AgentEval.mcp.library import MCPLibrary
+    from AgentEval.stats import library as stats_lib
+
+    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
+
+    lib = MCPLibrary()
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+    with pytest.raises(ImportError, match="agenteval-advanced"):
+        lib.get_tool_discoverability_comparison(
+            mcp_server="echo",
+            adapters=["any_a", "any_b"],
+            tasks=str(fixture_path),
+            trials_per_task=1,
+        )
+
+
+def test_compare_keyword_import_error_message_contract() -> None:
+    """The ImportError message contains the verbatim install hint.
+
+    Per Story 13.2 D-3 + AC-13.3.4 in-flight decision (b): the MCP
+    keyword raises directly (not via the Stats helper) so the message
+    is `MCP.Compare Tool Discoverability:`-prefixed (NOT `Stat.`).
+    """
+    pytest.importorskip("opentelemetry")
+
+    from unittest.mock import patch
+
+    from AgentEval.mcp.library import MCPLibrary
+    from AgentEval.stats import library as stats_lib
+
+    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
+    lib = MCPLibrary()
+
+    with patch.object(stats_lib, "_ADVANCED_AVAILABLE", False), pytest.raises(ImportError) as exc_info:
+        lib.get_tool_discoverability_comparison(
+            mcp_server="echo",
+            adapters=["a", "b"],
+            tasks=str(fixture_path),
+            trials_per_task=1,
+        )
+    msg = str(exc_info.value)
+    assert "MCP.Compare Tool Discoverability" in msg
+    assert "scipy + numpy required" in msg
+    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
+
+
+def test_compare_keyword_arg_validation_runs_before_extras_gate(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """Arg validation (mcp_server / adapters / tasks) runs BEFORE the extras gate.
+
+    Rationale: a user with a missing extra AND missing args should see
+    the arg error first (more actionable). Empty `mcp_server` → ValueError
+    even when `_ADVANCED_AVAILABLE=False`.
+    """
+    pytest.importorskip("opentelemetry")
+
+    from AgentEval.mcp.library import MCPLibrary
+    from AgentEval.stats import library as stats_lib
+
+    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
+    lib = MCPLibrary()
+    with pytest.raises(ValueError, match="mcp_server"):
+        lib.get_tool_discoverability_comparison(
+            mcp_server="",  # empty — arg validation should fire first.
+            adapters=["a", "b"],
+            tasks="some.yaml",
+            trials_per_task=1,
+        )
```

codex
Reviewing Story 13.3 as code review, not implementation. I’m starting from the actual repo state and the supplied diff, then I’ll run the existing discoverability tests and probe the new cross-adapter behavior against the spec sources.
  → Read ratified sources: PRD, architecture, epics, prior story code, and Story 13.3 implementation files
  • Run targeted tests and behavioral probes for refactor equivalence, pairwise counts/order, extras gate, and nan handling
  • Cross-check claims like test counts, libdoc/spec amendments, and synthesize concrete findings with file/line evidence
exec
/bin/bash -lc "rg -n \"FR10b|MCP.Compare Tool Discoverability|13\\.3|compare-tool-discoverability\" _bmad-output/planning-artifacts/prd.md _bmad-output/planning-artifacts/architecture.md _bmad-output/planning-artifacts/epics.md src/AgentEval/mcp/library.py src/AgentEval/discoverability/schema.py src/AgentEval/_heatmap/models.py src/AgentEval/stats/types.py tests/unit/discoverability/test_keyword.py tests/unit/discoverability/test_comparison.py tests/unit/discoverability/test_comparison_extras_gate.py tests/integration/discoverability/test_compare_e2e.py" in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: rg: command not found

exec
/bin/bash -lc "wc -l /tmp/story-13-3-review.diff && sed -n '1,80p' /tmp/story-13-3-review.diff" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
2130 /tmp/story-13-3-review.diff
diff --git a/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md b/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md
new file mode 100644
index 0000000..7a2f584
--- /dev/null
+++ b/_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md
@@ -0,0 +1,421 @@
+# Story 13.3: Compare Tool Discoverability Cross-Adapter (FR10b)
+
+Status: review
+
+## Story
+
+As **Mei (Agent Surface Author)** doing cross-runtime MCP analysis,
+I want `MCP.Compare Tool Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per PRD FR10b,
+So that I can claim "tool X is discoverable by Claude AND GPT AND Copilot" with empirical evidence — the killer Mei feature deferred from Phase 1, building on Story 13.1's Mann-Whitney U + Story 8b.2's `CohortHeatmap` + Story 4.4's per-adapter `MCP.Get Tool Discoverability`.
+
+## Pre-create-story drift check (53rd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)
+
+11 drifts caught — 6 fresh decisions from spec analysis + 5 UPSTREAM lessons from Stories 13.1 + 13.2 reviews. **100% real-drift catch rate maintained through 52 prior uses.**
+
+- **D-1 (HIGH — runtime-shape drift PRD vs epic, 1-vs-1 NOT resolved by majority — needs Mei intent reading):** **PRD vs epic disagree on the keyword signature.**
+  - **PRD L1500:** `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>` — explicit 2-runtime A/B comparison.
+  - **Epic L2186:** `MCP.Compare Tool Discoverability mcp_server=rf-mcp tasks=... adapters=[generic, claude-agent-sdk, openai-agents-sdk] trials_per_task=5 max_cost_usd=20.00` — N-runtime list (3 adapters in the example).
+  - **Decision (epic wins, generalize-then-PRD-amend):** ship the N-runtime `adapters: list[str]` shape per epic — covers the PRD's 2-runtime A/B case by passing a 2-element list (`adapters=["claude_code_cli", "codex_cli"]`). The N-shape is strictly more general, more aligned with Mei's "claim X across Claude AND GPT AND Copilot" goal (which requires ≥3 adapters), and matches Story 13.5's symmetric Skill version (which also uses `adapters=[...]`). **Same-commit fix:** amend PRD L1500 to read: `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...] (≥2 required)` with note "Backwards-compat: a 2-element list satisfies the original A/B semantic". Per `feedback_in_flight_spec_amendment` + Story 13.1 D-1 fix-the-losing-source-NOW precedent.
+
+- **D-2 (HIGH — return-type shape, no canonical source):** PRD doesn't fully spec `DiscoverabilityComparisonResult`'s field set; epic L2187 enumerates "per-adapter task-level results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data." **Decision:** ship `DiscoverabilityComparisonResult` frozen dataclass at `src/AgentEval/discoverability/schema.py` (alongside existing `DiscoverabilityResult` / `TaskResult` / `DiscoverabilitySummary`) with fields:
+  ```python
+  @dataclass(frozen=True)
+  class DiscoverabilityComparisonResult:
+      adapters: tuple[str, ...]                                                       # adapter names in input order
+      per_adapter_results: Mapping[str, DiscoverabilityResult]                        # {adapter_name: per-adapter result}
+      cross_adapter_deltas: Mapping[str, "PairwiseAdapterDelta"]                      # {f"{a1}_vs_{a2}": delta} for all ordered pairs
+      heatmap: CohortHeatmap                                                          # multi-column heatmap (one column per adapter)
+      summary: "DiscoverabilityComparisonSummary"                                     # aggregate roll-up
+  ```
+  with:
+  ```python
+  @dataclass(frozen=True)
+  class PairwiseAdapterDelta:
+      adapter_a: str
+      adapter_b: str
+      pass_rate_delta: float                                                          # avg(adapter_a per-task pass rate) - avg(adapter_b)
+      mann_whitney_result: MannWhitneyResult                                          # Story 13.1 dataclass; predicate=lambda r: r.pass_rate
+      significant_at_alpha_05: bool                                                   # p_value < 0.05
+
+  @dataclass(frozen=True)
+  class DiscoverabilityComparisonSummary:
+      total_cost_usd: float                                                           # sum across all adapters
+      total_runtime_seconds: float                                                    # max across adapters (parallel; not summed)
+      pass_rate_per_adapter: Mapping[str, float]                                      # adapter_name → overall_pass_rate
+      best_adapter: str                                                               # max(pass_rate_per_adapter)
+      worst_adapter: str                                                              # min(pass_rate_per_adapter)
+  ```
+  Frozen dataclasses with `__post_init__` defensive copy + Mapping → dict cast per Story 1b.2 M_R6 pattern + Story 4.4 frozen-invariant precedent.
+
+- **D-3 (HIGH — file home + sub-library composition, `MCPLibrary` carve-out):** `MCPLibrary` is excluded from `_SUB_LIBRARIES` per Story 2.2 collision norm + Story 4.4 architectural gap (DF-4.4-S1 / C20: `@guarded_fanout` enforcement deferred because `MCPLibrary` constructed via `WITH NAME MCP` not `_SUB_LIBRARIES`). **Decision:** ship `MCP.Compare Tool Discoverability` as a NEW `@keyword`-decorated method on `MCPLibrary` at `src/AgentEval/mcp/library.py` — same parent as `MCP.Get Tool Discoverability`. Same `@guarded_fanout` carve-out applies (kwargs tracked, NOT enforced; DF-4.4-S1 carry-over EXTENDED to cover Compare). NO new sub-library. Per Story 13.1 D-5 + Story 13.2 D-3: honor architecture's pre-allocated file home; don't create new modules.
+
+- **D-4 (HIGH — `mcp_server` arg semantics under N-adapters):** Epic AC L2186 shows ONE `mcp_server=rf-mcp` arg shared across all adapters. The Phase-1 `Get Tool Discoverability` carve-out (DF-4.1-S2 + DF-4.2-S1) means `mcp_server=` is accepted-but-not-forwarded to `adapter.run(mcp_servers=...)` — both Phase-1 adapters raise `NotImplementedError` on non-empty `mcp_servers`. For Phase-2 adapters from Stories 10.1+10.2 (Claude Agent SDK + OpenAI Agents SDK) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge. **Decision:** Cross-adapter `Compare Tool Discoverability` inherits the same carve-out behavior — the `mcp_server` arg is forwarded VERBATIM to each per-adapter `Get Tool Discoverability` call; downstream behavior is identical to single-adapter Phase-1 (accepted, validated non-empty, not forwarded to adapter.run; tests use stub adapters via `register_adapter` per Story 7.3 pattern). Catalog a DF-13.3-S2 carry-over for "Phase-2.5: real per-adapter MCP attachment" gated on C72 + C68 + C69 + C73 + C75 (the existing per-adapter MCP-bridge backlog).
+
+- **D-5 (HIGH — Mann-Whitney U predicate selection):** Story 13.1's `Stat.Mann Whitney U` requires `predicate: Callable[[KeywordRun], float]` value-extractor. But the comparison input is `list[TaskResult]` per adapter, NOT `list[KeywordRun]`. **Decision:** the Mann-Whitney U input is the PER-TASK pass-rate list per adapter:
+  ```python
+  rates_a = [t.pass_rate for t in per_adapter_results["adapter_a"].per_task_results]
+  rates_b = [t.pass_rate for t in per_adapter_results["adapter_b"].per_task_results]
+  ```
+  These are `list[float]` directly. `MannWhitneyResult` consumes these via the lower-level `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` helper at `src/AgentEval/stats/mannwhitney.py` (Story 13.1 module-level pure helper). The keyword surface `Stat.Mann Whitney U` (which takes `list[KeywordRun]` + predicate) does NOT apply at this layer; we call the pure helper directly. Document this dispatch in the dev notes. (`_ADVANCED_AVAILABLE` gate at `stats/library.py` controls availability — same ImportError gate as the keyword surface; OTLPBackend D-5 precedent applies.)
+
+- **D-6 (HIGH — `[agenteval-advanced]` extras dependency + ImportError gate):** Mann-Whitney U requires scipy + numpy via Story 13.1's `[agenteval-advanced]` extra. Story 13.3's `Compare Tool Discoverability` IS-A consumer of that dependency. **Decision:** `MCP.Compare Tool Discoverability` raises the SAME canonical ImportError (`"Stat.Mann Whitney U: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`) when invoked without `[agenteval-advanced]`. Implementation: at the call site, probe `from AgentEval.stats.library import _ADVANCED_AVAILABLE`; if False, raise ImportError BEFORE running any per-adapter fan-out (fail-fast, save cost — operators discovering the missing extra should not pay 3-adapter trial cost first). Per Story 13.2 L-2 lesson: tests split into happy-path + extras-gate files.
+
+- **D-7 (MED — `@tier(3)` + `@guarded_fanout` for the Compare-keyword, UPSTREAM Story 13.1 HIGH-C lesson):** `Compare Tool Discoverability` runs N×M trials (N adapters × M tasks × `trials_per_task` trials). This is Tier-3 fan-out by definition (parallel to `Stat.Run N Times` + `MCP.Get Tool Discoverability`). **Decision:** `@tier(3) + @guarded_fanout()` on the method, mirroring `MCP.Get Tool Discoverability` per Story 4.4 pattern. The `@guarded_fanout` Phase-1 carve-out applies identically (DF-4.4-S1 / C20: kwargs tracked, NOT enforced). Story 13.1 HIGH-C lesson re seed-required-for-FR31a DOESN'T apply here — `@tier(3)` keywords are explicitly stochastic by tier definition; no bit-identical guarantee.
+
+- **D-8 (MED — `CohortHeatmap` multi-adapter extension):** Story 8b.2's `CohortHeatmap` already supports multi-column heatmaps via `tasks: tuple[str, ...]` + `models: tuple[str, ...]` + `cells`. `CohortHeatmap.from_discoverability` is single-model-only (Phase-1 carve-out per `_heatmap/models.py:46`). **Decision:** ADD a NEW classmethod `CohortHeatmap.from_comparison(result: DiscoverabilityComparisonResult) -> CohortHeatmap` at `src/AgentEval/_heatmap/models.py` that builds a multi-column heatmap (columns = adapter names; rows = task IDs; cells = per-adapter per-task pass-rate). The existing single-model classmethod stays unchanged for backward compat. This is the "cohort heatmap data" half of epic AC L2187 ("+ cohort heatmap data").
+
+- **D-9 (MED — integration test stub-adapter pattern per epic L2189):** Epic L2189 mandates "integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero)." Story 12.3 + Story 7.3 established the canonical `register_adapter()` stub pattern (NOT MockProvider at the provider layer — adapter-level stub). **Decision:** use the `register_adapter` 3-stub pattern from Story 12.3 — register 3 stub adapters (`compare_stub_a`, `compare_stub_b`, `compare_stub_c`) returning different per-task pass-rate distributions so Mann-Whitney U produces meaningfully different p-values. The 3rd stub validates ≥2 adapters → N-adapter generalization (per D-1 PRD-amend coverage).
+
+- **D-10 (LOW — carry-over catalog gate UPSTREAM Story 13.1+13.2, 34th consecutive):** Anticipated Phase-1.5 / Phase-2 carry-overs for Story 13.3:
+  - **DF-13.3-S1 (Phase-2.5):** `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` — same architectural gap as DF-4.4-S1 / C20. Cross-adapter fan-out compounds cost N× (N adapters × M tasks × trials). Once Phase-1.5 lands `MCPLibrary` cross-library budget plumbing, this keyword benefits identically.
+  - **DF-13.3-S2 (Phase-2.5):** Real per-adapter MCP-server attachment (gated on C72 LiteLLM MCP-bridge + C68/C69/C73/C75 per-adapter HostedMcpObserver wiring). Phase-2 ships the keyword shape + stub-adapter testing; real cross-adapter MCP coverage flows from upstream MCP-bridge work.
+  - **DF-13.3-S3 (Phase-2.5):** Multi-pairwise correction (Bonferroni / Holm) for the cross-adapter delta significance. Phase-2 ships pairwise comparisons WITHOUT multiple-testing correction — for N=3 adapters there are C(3,2)=3 pairs; Bonferroni-adjusted α=0.0167. Add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` in Phase-2.5.
+  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C89 + C90 + C91 BEFORE invoking `/bmad-code-review`.
+

exec
/bin/bash -lc 'git status --short' in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
 A _bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md
 M _bmad-output/implementation-artifacts/deferred-work.md
 M _bmad-output/implementation-artifacts/sprint-status.yaml
 M _bmad-output/planning-artifacts/prd.md
 M docs/contracts/stability-surface.md
 M docs/keywords/AgentEval.html
 M docs/keywords/MCPLibrary.html
 M docs/phase-1-5-carry-overs.md
 M src/AgentEval/_heatmap/models.py
 A src/AgentEval/discoverability/_internal.py
 M src/AgentEval/discoverability/schema.py
 M src/AgentEval/mcp/library.py
 M src/AgentEval/stats/types.py
 A tests/integration/discoverability/__init__.py
 A tests/integration/discoverability/test_compare_e2e.py
 A tests/unit/discoverability/test_comparison.py
 A tests/unit/discoverability/test_comparison_extras_gate.py
?? _bmad-output/cross-llm-reviews/13-3-claude-opus-findings.md
?? _bmad-output/cross-llm-reviews/13-3-claude-sonnet-findings.md
?? _bmad-output/cross-llm-reviews/13-3-codex-findings.md

codex
The repo state matches the supplied diff. Next I’m reading the ratified spec lines and the concrete implementations around the new helper, comparison keyword, schema, heatmap, and stats types so I can anchor findings to source instead of the story notes.
exec
/bin/bash -lc "sed -n '1248,1268p' _bmad-output/planning-artifacts/architecture.md; printf '\\n---\\n'; sed -n '2177,2189p' _bmad-output/planning-artifacts/epics.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
│       │   ├── claude_agent_sdk.py         # Phase 2 (FR13c, under [claude-sdk] extra; Story 10.1 D-1 fix-the-losing-source-NOW 2026-05-25)
│       │   ├── openai_agents.py            # Phase 2 (FR13d, under [openai-agents] extra)
│       │   ├── codex_cli.py                # Phase 2 (FR13e, under [codex] extra)
│       │   ├── copilot_cli.py              # Phase 2 (FR13f, under [copilot] extra)
│       │   └── factory.py                  # Adapter discovery via entry-points
│       │
│       ├── telemetry/                      # Per agentguard ADR-012 pattern (borrowed, evaluated on merit) + Decision-2
│       │   ├── __init__.py
│       │   ├── listener.py                 # RF Listener v3 entry point (registered via [project.entry-points."robot.listener"]) per FR33a. (Story 5.1 pre-create-story drift fix 2026-05-20: was `otel_listener.py` borrowing agentguard's name; ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 say `listener.py`.)
│       │   ├── spans.py                    # OTel span emission helpers (invoke_agent → chat → execute_tool) per FR32 + Step-5 semconv convention
│       │   ├── backends.py                 # memory / jsonl backends Phase 1; otlp dispatch Phase 2 per FR33b
│       │   └── semconv.py                  # Internal facade for gen_ai.* attribute names per NFR-COMPAT-06
│       │
│       ├── mcp/                            # MCP sub-library
│       │   ├── __init__.py
│       │   ├── library.py                  # MCP keywords: Get Server Config, Start/Connect/Stop Server, Get Tools, Call Tool, Get Tool Discoverability per FR5-11 + FR11b
│       │   ├── _internal.py                # _negotiate_version, _parse_server_config, _spawn_server, etc.
│       │   ├── observer.py                 # Hosted-MCP universal trace observer per FR35 + ADR-004 (Story 5.2; ratified spike Decision-3 = request_handlers dict-wrap pattern)
      │   ├── _observer_subprocess_wrapper.py  # Subprocess-bootstrap wrapper injecting observer at stdio subprocess startup per ADR-004 Consequences (Story 5.2 pre-create-story drift D-3 fix 2026-05-20: spike findings + ADR-004 mandated this file; pre-edit project tree didn't list it)
│       │   ├── transport.py                # stdio / streamable_http / in-memory transport adapters per NFR-COMPAT-04
│       │   ├── version_gate.py             # UnsupportedMCPVersionError per FR8/FR46 + ADR-011 from PRD sidecar

---
#### Story 13.3: Compare Tool Discoverability Cross-Adapter

As **Mei (Agent Surface Author)** doing cross-runtime MCP analysis,
I want `MCP.Compare Tool Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per FR10b,
So that I can claim "tool X is discoverable by Claude AND GPT AND Copilot" with empirical evidence — the killer Mei feature deferred from Phase 1.

**Acceptance Criteria:**

**Given** the MVP Discoverability from Story 4.4 + the SDK adapters from Epic 10 + CLI adapters from Epic 11 (≥2 Tier-1 adapters fully shipped per ADR-A4 prerequisite),
**When** I call `${comparison}=    MCP.Compare Tool Discoverability    mcp_server=rf-mcp    tasks=...    adapters=[generic, claude-agent-sdk, openai-agents-sdk]    trials_per_task=5    max_cost_usd=20.00`,
**Then** the variable receives a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data.

**And** integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero).

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/mannwhitney.py | sed -n '1,220p'; printf '\\n---\\n'; nl -ba tests/unit/discoverability/test_keyword.py | sed -n '1,260p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Mann-Whitney U statistical primitive (PRD FR29a; Story 13.1).
    16	
    17	Phase-2 module — requires the `[agenteval-advanced]` optional extra (scipy +
    18	numpy). Imported lazily by
    19	`AgentEval.stats.library.StatsLibrary.compute_mann_whitney_u` behind an
    20	`_ADVANCED_AVAILABLE` gate; importing this module without scipy installed
    21	raises `ImportError` at the `import scipy.stats` line.
    22	
    23	Math reference: ``scipy.stats.mannwhitneyu`` (alternative="two-sided",
    24	use_continuity=False). Effect size: rank-biserial correlation
    25	``r = 2 * U1 / (n_a * n_b) - 1`` (signed convention where U1 is the
    26	Mann-Whitney U for samples_a; positive r → samples_a tends to be larger
    27	than samples_b). This matches the Cliff's delta sign convention shipped
    28	by `Stat.Cliff Delta` (Story 13.1 FR29b).
    29	
    30	Phase-1.5/2 carry-overs:
    31	- DF-13.1-S1: one-sided alternatives ("greater"/"less"). Phase-1 ships
    32	  two-sided only.
    33	- DF-13.1-S3: ``MannWhitneyResult.effect_size_interpretation`` Cohen-band
    34	  Literal field. Phase-1 returns the raw ``effect_size_r``.
    35	"""
    36	
    37	from __future__ import annotations
    38	
    39	import scipy.stats as _scipy_stats
    40	
    41	from AgentEval.stats.types import MannWhitneyResult
    42	
    43	__all__ = ["compute_mann_whitney_u"]
    44	
    45	
    46	def compute_mann_whitney_u(
    47	    samples_a: list[float],
    48	    samples_b: list[float],
    49	) -> MannWhitneyResult:
    50	    """Compute the Mann-Whitney U statistic + p-value + effect size (FR29a).
    51	
    52	    Args:
    53	        samples_a: First-group numeric samples; must be non-empty.
    54	        samples_b: Second-group numeric samples; must be non-empty.
    55	
    56	    Returns:
    57	        ``MannWhitneyResult`` with ``u_statistic`` (the smaller of U1, U2 —
    58	        the canonical smaller-U form), two-sided ``p_value`` (matches
    59	        ``scipy.stats.mannwhitneyu`` default), rank-biserial ``effect_size_r``,
    60	        and the sample sizes ``n_a`` and ``n_b``.
    61	
    62	    Raises:
    63	        ValueError: When either samples list is empty.
    64	
    65	    Notes:
    66	        - ``scipy.stats.mannwhitneyu(..., alternative="two-sided",
    67	          use_continuity=False).statistic`` returns ``U1`` (the U-statistic
    68	          for ``samples_a``). This implementation NORMALIZES the return to
    69	          ``min(U1, U2)`` — the smaller-U canonical form widely cited in
    70	          literature — and DOES NOT match scipy's ``.statistic`` value
    71	          directly. The ``effect_size_r`` computation still uses ``U1``
    72	          (so the sign carries the directionality of the effect); consumers
    73	          needing scipy's U1 can recover it via
    74	          ``U1 = (1 + effect_size_r) * n_a * n_b / 2``.
    75	        - The two-sided ``p_value`` IS symmetric in U1/U2 and matches scipy
    76	          exactly.
    77	    """
    78	    n_a = len(samples_a)
    79	    n_b = len(samples_b)
    80	    if n_a < 1:
    81	        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    82	    if n_b < 1:
    83	        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    84	    result = _scipy_stats.mannwhitneyu(
    85	        samples_a,
    86	        samples_b,
    87	        alternative="two-sided",
    88	        use_continuity=False,
    89	    )
    90	    u1 = float(result.statistic)
    91	    u2 = float(n_a * n_b - u1)
    92	    u_smaller = min(u1, u2)
    93	    # Signed rank-biserial correlation r = 2 * U1 / (n_a * n_b) - 1. U1 is
    94	    # the count of pairs where samples_a > samples_b (with 0.5 for ties), so:
    95	    #   - U1 = 0 (samples_a strictly < samples_b) → r = -1.0
    96	    #   - U1 = n_a * n_b / 2 (no separation) → r = 0.0
    97	    #   - U1 = n_a * n_b (samples_a strictly > samples_b) → r = +1.0
    98	    # Matches Cliff's delta sign convention shipped by `Stat.Cliff Delta`.
    99	    effect_size_r = 2.0 * u1 / (n_a * n_b) - 1.0
   100	    return MannWhitneyResult(
   101	        u_statistic=u_smaller,
   102	        p_value=float(result.pvalue),
   103	        effect_size_r=effect_size_r,
   104	        n_a=n_a,
   105	        n_b=n_b,
   106	    )

---
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""End-to-end tests for `MCP.Get Tool Discoverability` (Story 4.4)."""
    16	
    17	from __future__ import annotations
    18	
    19	from pathlib import Path
    20	from typing import Any
    21	
    22	import pytest
    23	
    24	from AgentEval._kernel.discovery import register_adapter
    25	from AgentEval._kernel.tier import get_keyword_tier
    26	from AgentEval.coding_agent.base import InProcessAdapter
    27	from AgentEval.discoverability.schema import (
    28	    DiscoverabilityResult,
    29	    DiscoverabilitySummary,
    30	    TaskResult,
    31	)
    32	from AgentEval.errors import InvalidDiscoverabilityTasksError
    33	from AgentEval.mcp.library import MCPLibrary
    34	from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage
    35	
    36	
    37	def _make_stub_adapter(tool_names_per_call: list[list[str]], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
    38	    """Build a stub adapter class returning scripted tool_calls per run().
    39	
    40	    Each element of `tool_names_per_call` is the list of tool names that
    41	    `run()` should report on the i-th invocation. The class is fresh per
    42	    test so the call counter resets cleanly.
    43	    """
    44	
    45	    class _StubAdapter(InProcessAdapter):
    46	        _call_idx = 0
    47	
    48	        def __init__(self, **kwargs: Any) -> None:
    49	            super().__init__()
    50	            self._kwargs = kwargs
    51	
    52	        def run(
    53	            self,
    54	            prompt: str,
    55	            tools: Any = None,
    56	            mcp_servers: Any = None,
    57	            **kwargs: Any,
    58	        ) -> AgentRunResult:
    59	            idx = type(self)._call_idx
    60	            type(self)._call_idx += 1
    61	            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
    62	            tool_calls = [
    63	                ToolCallTrace(
    64	                    name=name,
    65	                    args={},
    66	                    result=None,
    67	                    error=None,
    68	                    latency_ms=1.0,
    69	                    source="adapter",
    70	                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
    71	                    sequence_index=i,
    72	                )
    73	                for i, name in enumerate(names)
    74	            ]
    75	            return AgentRunResult(
    76	                response_text=f"stub-{idx}",
    77	                tool_calls=tool_calls,
    78	                usage=Usage(input_tokens=1, output_tokens=1),
    79	                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
    80	                cost_usd=cost_per_call,
    81	                latency_seconds=0.001,
    82	                trace_id=f"stub-id-{idx:032d}"[:32],
    83	            )
    84	
    85	    return _StubAdapter
    86	
    87	
    88	def _make_stub_adapter_per_trial_costs(
    89	    tool_names_per_call: list[list[str]], costs_per_call: list[float]
    90	) -> type[InProcessAdapter]:
    91	    """Stub adapter variant with distinct per-trial costs.
    92	
    93	    Story 4.4 code-review LOW-B fix 2026-05-20 (Codex 244): the original
    94	    fixture used `all(c == 0.002 ...)` which would pass under any list
    95	    reordering. This variant scripts a distinct cost per call so the
    96	    ordering invariant is testable.
    97	    """
    98	
    99	    class _StubAdapter(InProcessAdapter):
   100	        _call_idx = 0
   101	
   102	        def __init__(self, **kwargs: Any) -> None:
   103	            super().__init__()
   104	            self._kwargs = kwargs
   105	
   106	        def run(
   107	            self,
   108	            prompt: str,
   109	            tools: Any = None,
   110	            mcp_servers: Any = None,
   111	            **kwargs: Any,
   112	        ) -> AgentRunResult:
   113	            idx = type(self)._call_idx
   114	            type(self)._call_idx += 1
   115	            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
   116	            cost = costs_per_call[idx] if idx < len(costs_per_call) else 0.0
   117	            tool_calls = [
   118	                ToolCallTrace(
   119	                    name=name,
   120	                    args={},
   121	                    result=None,
   122	                    error=None,
   123	                    latency_ms=1.0,
   124	                    source="adapter",
   125	                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
   126	                    sequence_index=i,
   127	                )
   128	                for i, name in enumerate(names)
   129	            ]
   130	            return AgentRunResult(
   131	                response_text=f"stub-{idx}",
   132	                tool_calls=tool_calls,
   133	                usage=Usage(input_tokens=1, output_tokens=1),
   134	                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
   135	                cost_usd=cost,
   136	                latency_seconds=0.001,
   137	                trace_id=f"stub-id-{idx:032d}"[:32],
   138	            )
   139	
   140	    return _StubAdapter
   141	
   142	
   143	@pytest.fixture
   144	def lib() -> MCPLibrary:
   145	    return MCPLibrary()
   146	
   147	
   148	@pytest.fixture
   149	def fixture_path() -> Path:
   150	    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
   151	
   152	
   153	def test_get_tool_discoverability_returns_discoverability_result(lib: MCPLibrary, fixture_path: Path) -> None:
   154	    """End-to-end happy path: all 9 trials report `echo_back` -> 100% pass.
   155	
   156	    Verifies PRD FR10a L1499 ratified shape: `per_task_results` + `summary`
   157	    nesting + `mcp_coverage` (Story 4.4 code-review HIGH-B fix 2026-05-20).
   158	    """
   159	    stub = _make_stub_adapter([["echo_back"]] * 9)
   160	    register_adapter("stub_disco_all_pass", stub)
   161	    result = lib.get_tool_discoverability(
   162	        mcp_server="echo",
   163	        adapter="stub_disco_all_pass",
   164	        tasks=str(fixture_path),
   165	        trials_per_task=3,
   166	    )
   167	    assert isinstance(result, DiscoverabilityResult)
   168	    assert isinstance(result.summary, DiscoverabilitySummary)
   169	    assert len(result.per_task_results) == 3
   170	    assert result.summary.overall_pass_rate == 1.0
   171	    for tr in result.per_task_results:
   172	        assert tr.success_count == 3
   173	        assert tr.trials_run == 3
   174	        assert tr.wilson_ci_upper == 1.0
   175	        assert 0.4 < tr.wilson_ci_lower < 0.5
   176	    assert abs(result.summary.total_cost_usd - 0.009) < 1e-9
   177	    assert result.summary.total_runtime_seconds >= 0.0
   178	    assert result.mcp_coverage == "hosted_in_process"
   179	
   180	
   181	def test_get_tool_discoverability_no_tool_calls_zero_pass_rate(lib: MCPLibrary, fixture_path: Path) -> None:
   182	    """Adapter returns NO tool calls -> 0/9 successes -> overall_pass_rate = 0."""
   183	    stub = _make_stub_adapter([[]] * 9)
   184	    register_adapter("stub_disco_no_calls", stub)
   185	    result = lib.get_tool_discoverability(
   186	        mcp_server="echo",
   187	        adapter="stub_disco_no_calls",
   188	        tasks=str(fixture_path),
   189	        trials_per_task=3,
   190	    )
   191	    assert result.summary.overall_pass_rate == 0.0
   192	    for tr in result.per_task_results:
   193	        assert tr.success_count == 0
   194	        assert tr.wilson_ci_lower == 0.0
   195	
   196	
   197	def test_get_tool_discoverability_competing_tools_tracked(lib: MCPLibrary, fixture_path: Path) -> None:
   198	    """When the model picks a tool NOT in expected_tools, it's tracked."""
   199	    stub = _make_stub_adapter([["wrong_tool"]] * 9)
   200	    register_adapter("stub_disco_competing", stub)
   201	    result = lib.get_tool_discoverability(
   202	        mcp_server="echo",
   203	        adapter="stub_disco_competing",
   204	        tasks=str(fixture_path),
   205	        trials_per_task=3,
   206	    )
   207	    assert result.summary.overall_pass_rate == 0.0
   208	    for tr in result.per_task_results:
   209	        assert "wrong_tool" in tr.competing_tools_picked
   210	
   211	
   212	def test_get_tool_discoverability_partial_pass_rate_with_wilson_ci(lib: MCPLibrary, fixture_path: Path) -> None:
   213	    """Mixed success/failure per task — Wilson CI brackets pass rate.
   214	
   215	    Story 4.4 code-review 2-way LOW-A fix 2026-05-20 (Blind LOW-2 + Codex 157):
   216	    pre-edit asserted only edge bounds; the test name claimed "brackets pass
   217	    rate" but the 2/3 mid-case wasn't bracket-checked. Per
   218	    `feedback_test_name_assertion_match` (Epic 3 retro), test body must
   219	    deliver on the name's promise — now asserts the full bracketing
   220	    invariant for all 3 tasks AND the canonical Wilson reference value
   221	    for 2/3 at 95% confidence ≈ (0.208, 0.939).
   222	    """
   223	    pattern = [
   224	        ["echo_back"],
   225	        ["echo_back"],
   226	        [],  # task 1: 2/3
   227	        [],
   228	        [],
   229	        [],  # task 2: 0/3
   230	        ["echo_back"],
   231	        ["echo_back"],
   232	        ["echo_back"],  # task 3: 3/3
   233	    ]
   234	    stub = _make_stub_adapter(pattern)
   235	    register_adapter("stub_disco_partial", stub)
   236	    result = lib.get_tool_discoverability(
   237	        mcp_server="echo",
   238	        adapter="stub_disco_partial",
   239	        tasks=str(fixture_path),
   240	        trials_per_task=3,
   241	    )
   242	    assert abs(result.summary.overall_pass_rate - 5 / 9) < 1e-9
   243	    t1, t2, t3 = result.per_task_results
   244	    assert t1.success_count == 2
   245	    assert t2.success_count == 0
   246	    assert t3.success_count == 3
   247	    # Bracketing invariant for every task — Wilson CI MUST contain the
   248	    # point estimate (Wilson is a "score" interval, not Wald; bracket is
   249	    # guaranteed by construction).
   250	    for tr in result.per_task_results:
   251	        assert tr.wilson_ci_lower <= tr.pass_rate <= tr.wilson_ci_upper, (
   252	            f"Wilson CI [{tr.wilson_ci_lower}, {tr.wilson_ci_upper}] does not "
   253	            f"bracket pass_rate={tr.pass_rate} for task {tr.task_id}"
   254	        )
   255	    # Canonical Wilson reference for 2/3 at 95% ≈ (0.208, 0.939).
   256	    assert 0.20 < t1.wilson_ci_lower < 0.22
   257	    assert 0.93 < t1.wilson_ci_upper < 0.95
   258	    # Edge cases still verified.
   259	    assert t2.wilson_ci_lower == 0.0
   260	    assert t3.wilson_ci_upper == 1.0

exec
/bin/bash -lc "nl -ba src/AgentEval/mcp/library.py | sed -n '500,760p'; printf '\\n---\\n'; nl -ba src/AgentEval/discoverability/_internal.py | sed -n '1,220p'; printf '\\n---\\n'; nl -ba src/AgentEval/discoverability/schema.py | sed -n '130,320p'; printf '\\n---\\n'; nl -ba src/AgentEval/_heatmap/models.py | sed -n '1,140p'; printf '\\n---\\n'; nl -ba src/AgentEval/stats/types.py | sed -n '50,95p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   500	        - Tier-3 stochastic; budgets tracked but NOT enforced in Phase-1 (DF-4.4-S1).
   501	        - Story 4.3 + Story 4.4 ratify the carve-out (architectural budget-injection gap shared with `MetricsLibrary` family).
   502	        - Story 2.2 ratifies the ``_SUB_LIBRARIES`` composition norm (which excludes ``MCPLibrary`` — driver of the carve-out).
   503	        - Sibling keywords (same library): `Call Tool`, `List Tools`, `Start Server`.
   504	        - Downstream keyword (separately composed sub-library): `HeatmapLibrary.Get Cohort Heatmap` consumes ``DiscoverabilityResult`` to render the FR55 cohort heatmap.
   505	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   506	        # Story 4.4 code-review MED-B fix 2026-05-20 (Codex empirical probe):
   507	        # `total_runtime_seconds` must capture the full end-to-end wall time
   508	        # operators care about for AC-DISCOVER-02 budget audit — including
   509	        # tasks YAML load + adapter resolution + adapter construction, NOT
   510	        # just the trial dispatch loop. Pre-edit `t_start` fired after ctor
   511	        # and underreported by the ctor cost (probe: 0.0202 vs 0.3712 actual).
   512	        t_start = time.monotonic()
   513	
   514	        # Story 4.4 code-review MED-E fix 2026-05-20 (Edge-cases M2): pre-edit
   515	        # accepted `mcp_server=""` silently — Phase-1 the field is unused
   516	        # (DF-4.1-S2) but future-proofing means rejecting the empty-string
   517	        # input now so existing callers don't lock in a no-op default.
   518	        if not mcp_server:
   519	            raise ValueError(
   520	                "Get Tool Discoverability requires `mcp_server=<name>` kwarg "
   521	                "(name of an MCP server started via `MCP.Start Server`); empty "
   522	                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
   523	                "adapter-side integration."
   524	            )
   525	        if not tasks:
   526	            raise ValueError("Get Tool Discoverability requires `tasks=<yaml-path>` kwarg")
   527	        if trials_per_task < 1:
   528	            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
   529	
   530	        # Load + validate the tasks YAML.
   531	        task_list = load_discoverability_tasks(tasks)
   532	
   533	        # Story 13.3 refactor: per-adapter logic extracted to
   534	        # `discoverability/_internal.run_single_adapter_discoverability` so
   535	        # the new `MCP.Compare Tool Discoverability` keyword reuses it
   536	        # without ~80 LoC duplication. Behavior MUST equal pre-refactor —
   537	        # verified by Story 4.4's 50+ existing tests passing unchanged.
   538	        from AgentEval.discoverability._internal import run_single_adapter_discoverability
   539	
   540	        return run_single_adapter_discoverability(
   541	            mcp_server=mcp_server,
   542	            adapter=adapter,
   543	            model=model,
   544	            task_list=task_list,
   545	            trials_per_task=trials_per_task,
   546	            max_cost_usd=max_cost_usd,
   547	            max_runtime_seconds=max_runtime_seconds,
   548	            extra_adapter_kwargs=dict(kwargs),
   549	            t_start=t_start,
   550	        )
   551	
   552	    # --------------------------------------------------------------- #
   553	    # Story 13.3: Cross-adapter comparison (PRD FR10b)
   554	    # --------------------------------------------------------------- #
   555	
   556	    @keyword(name="MCP.Compare Tool Discoverability")
   557	    @tier(3)
   558	    def get_tool_discoverability_comparison(
   559	        self,
   560	        mcp_server: str = "",
   561	        adapters: list[str] | None = None,
   562	        tasks: str = "",
   563	        trials_per_task: int = 3,
   564	        max_cost_usd: float = 20.00,
   565	        max_runtime_seconds: float | None = None,
   566	        model: str | None = None,
   567	        **kwargs: Any,
   568	    ) -> DiscoverabilityComparisonResult:
   569	        """Compares Tool Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).
   570	
   571	        [Tier 3 — Stochastic Fan-Out] — runs `Get Tool Discoverability`
   572	        once per adapter against the SAME task set, then computes
   573	        pairwise Mann-Whitney U deltas across the per-task pass-rate
   574	        distributions. Returns a `DiscoverabilityComparisonResult` with
   575	        per-adapter results + cross-adapter deltas + multi-column
   576	        cohort heatmap + aggregate summary.
   577	
   578	        Requires the ``[agenteval-advanced]`` optional extra (scipy +
   579	        numpy) for the Mann-Whitney U cross-adapter delta computation;
   580	        raises ``ImportError`` on invocation WITHOUT the extra (fail-fast
   581	        BEFORE running any per-adapter fan-out — operators discovering
   582	        the missing extra should not pay 3-adapter trial cost first).
   583	
   584	        | =Arguments= | =Description= |
   585	        | ``mcp_server`` | Name of the MCP server (per `Start Server`). Same Phase-1 carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). |
   586	        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. N=3+ enables ranking across Claude/GPT/Copilot/.... |
   587	        | ``tasks`` | Path to the discoverability tasks YAML (loaded ONCE; shared across adapters). |
   588	        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
   589	        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2186 (4× the single-adapter default reflecting N=3-adapter typical cost). Phase-1 carve-out DF-13.3-S1: tracked NOT enforced (same MCPLibrary architectural gap as DF-4.4-S1 / C20). |
   590	        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. |
   591	        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. Phase-2.5 (DF-13.3-S4): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg. |
   592	        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |
   593	
   594	        Returns ``DiscoverabilityComparisonResult`` with ``adapters`` +
   595	        ``per_adapter_results`` (one ``DiscoverabilityResult`` per
   596	        adapter) + ``cross_adapter_deltas`` (C(N, 2) ``PairwiseAdapterDelta``
   597	        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
   598	        ``CohortHeatmap`` via ``from_comparison``) + ``summary``
   599	        (``DiscoverabilityComparisonSummary``).
   600	
   601	        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
   602	        missing (Mann-Whitney U requires scipy/numpy). Raises
   603	        ``ValueError`` on missing/empty ``mcp_server`` / ``tasks`` /
   604	        ``adapters`` (≥2 required) / invalid ``trials_per_task``.
   605	        Raises ``InvalidDiscoverabilityTasksError`` on tasks YAML
   606	        parse/schema failure. Raises ``AdapterDiscoveryError`` on
   607	        unknown adapter name.
   608	
   609	        Example:
   610	        | ${comparison}=    `MCP.Compare Tool Discoverability`
   611	        | ...    mcp_server=rf-mcp
   612	        | ...    adapters=${{['generic', 'claude_code_cli', 'codex_cli']}}
   613	        | ...    tasks=${CURDIR}/tasks.yaml
   614	        | ...    trials_per_task=5
   615	        | ...    max_cost_usd=20.00
   616	        | Should Be Equal As Strings    ${comparison.summary.best_adapter}    claude_code_cli
   617	        | Should Be True    ${comparison.cross_adapter_deltas['generic_vs_codex_cli'].significant_at_alpha_05}
   618	
   619	        Notes:
   620	        - Story 13.3 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra (the Mann-Whitney U dependency from Story 13.1).
   621	        - PRD FR10b ratifies the ``DiscoverabilityComparisonResult`` shape; epics.md L2186-2189 ratifies the keyword signature + behavior.
   622	        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper at ``src/AgentEval/stats/mannwhitney.py``). The keyword surface ``Stat.Mann Whitney U`` is NOT called here because the input is ``list[float]`` per-task pass rates (NOT ``list[KeywordRun]``).
   623	        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition; no bit-identical FR31a guarantee (Story 13.1 HIGH-C concern doesn't apply at @tier(3)).
   624	        - Phase-1 carve-out DF-13.3-S1: ``@guarded_fanout`` enforcement DEFERRED (same MCPLibrary architectural gap as DF-4.4-S1 / C20).
   625	        - Phase-2.5 carry-overs: DF-13.3-S2 (per-adapter MCP attachment gated on C72 + C68/C69/C73/C75); DF-13.3-S3 (Bonferroni / Holm multi-pairwise correction).
   626	        - Sibling keyword: `MCP.Get Tool Discoverability` (Phase-1 single-adapter; this keyword's N=1 case is intentionally rejected via the ≥2 validation — single-adapter callers should use the simpler `Get` keyword).
   627	        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
   628	        t_start = time.monotonic()
   629	
   630	        # Validate args (mirrors single-adapter Get + adds N≥2 constraint).
   631	        if not mcp_server:
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
   690	            per_adapter_results[adapter_name] = run_single_adapter_discoverability(
   691	                mcp_server=mcp_server,
   692	                adapter=adapter_name,
   693	                model=model,
   694	                task_list=task_list,
   695	                trials_per_task=trials_per_task,
   696	                max_cost_usd=max_cost_usd,
   697	                max_runtime_seconds=max_runtime_seconds,
   698	                extra_adapter_kwargs=dict(kwargs),
   699	                t_start=time.monotonic(),  # per-adapter timer; aggregate uses MAX.
   700	            )
   701	
   702	        # Build C(N, 2) pairwise deltas. Ordering: itertools.combinations
   703	        # preserves input order so `adapter_a` always comes before
   704	        # `adapter_b` in the input list.
   705	        import itertools
   706	
   707	        cross_adapter_deltas: dict[str, PairwiseAdapterDelta] = {}
   708	        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
   709	            rates_a = [t.pass_rate for t in per_adapter_results[adapter_a].per_task_results]
   710	            rates_b = [t.pass_rate for t in per_adapter_results[adapter_b].per_task_results]
   711	            # Empty per-task lists guard: skip the comparison if either is
   712	            # empty (would otherwise raise from `compute_mann_whitney_u`).
   713	            if not rates_a or not rates_b:
   714	                continue
   715	            mwu = compute_mann_whitney_u(rates_a, rates_b)
   716	            delta_key = f"{adapter_a}_vs_{adapter_b}"
   717	            mean_a = sum(rates_a) / len(rates_a)
   718	            mean_b = sum(rates_b) / len(rates_b)
   719	            import math as _math
   720	
   721	            cross_adapter_deltas[delta_key] = PairwiseAdapterDelta(
   722	                adapter_a=adapter_a,
   723	                adapter_b=adapter_b,
   724	                pass_rate_delta=mean_a - mean_b,
   725	                mann_whitney_result=mwu,
   726	                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
   727	            )
   728	
   729	        # Build summary aggregate.
   730	        pass_rate_per_adapter = {name: per_adapter_results[name].summary.overall_pass_rate for name in adapters}
   731	        best_adapter = max(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
   732	        worst_adapter = min(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
   733	        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
   734	        # Wall-clock: MAX models eventual parallel fan-out target (per dataclass docs).
   735	        total_runtime = max(r.summary.total_runtime_seconds for r in per_adapter_results.values())
   736	        summary = DiscoverabilityComparisonSummary(
   737	            total_cost_usd=total_cost,
   738	            total_runtime_seconds=total_runtime,
   739	            pass_rate_per_adapter=pass_rate_per_adapter,
   740	            best_adapter=best_adapter,
   741	            worst_adapter=worst_adapter,
   742	        )
   743	
   744	        # Build a provisional comparison result so CohortHeatmap.from_comparison
   745	        # can read the per-adapter results. The CohortHeatmap construction
   746	        # happens AFTER per_adapter_results is populated; we pass a
   747	        # "placeholder" comparison via direct construction (the
   748	        # CohortHeatmap.from_comparison reads result.adapters + result.per_adapter_results
   749	        # only, NOT the heatmap field — no chicken-and-egg).
   750	        #
   751	        # Build the heatmap via a lightweight namespace stand-in: the
   752	        # classmethod accesses .adapters + .per_adapter_results.
   753	        class _ComparisonShim:
   754	            pass
   755	
   756	        shim = _ComparisonShim()
   757	        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
   758	        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
   759	        heatmap = CohortHeatmap.from_comparison(shim)  # type: ignore[arg-type]
   760	

---
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Shared per-adapter discoverability helper (Story 13.3 refactor of Story 4.4).
    16	
    17	Extracted from `MCPLibrary.get_tool_discoverability` so the new
    18	`MCP.Compare Tool Discoverability` keyword (Story 13.3) can reuse the
    19	per-adapter logic without duplicating ~80 LoC. Behavior MUST be
    20	identical to the pre-refactor `get_tool_discoverability` body —
    21	verified by Story 4.4's 50+ existing tests passing unchanged.
    22	
    23	Architecture note: this is the canonical `_internal.py` helper module
    24	per `feedback_full_surface_retro_review` discipline (mirrors
    25	`stats/_internal.py` from Story 6.3 + `_assertions/_internal.py`-style
    26	sibling). Pure functions; no side effects beyond the adapter calls
    27	themselves.
    28	"""
    29	
    30	from __future__ import annotations
    31	
    32	import time
    33	from typing import TYPE_CHECKING, Any
    34	
    35	from AgentEval._kernel.discovery import get_adapter
    36	from AgentEval.discoverability.schema import (
    37	    DiscoverabilityResult,
    38	    DiscoverabilitySummary,
    39	    TaskResult,
    40	)
    41	from AgentEval.discoverability.wilson_ci import wilson_score_interval
    42	
    43	if TYPE_CHECKING:
    44	    from AgentEval.discoverability.schema import DiscoverabilityTask
    45	
    46	__all__ = ["run_single_adapter_discoverability"]
    47	
    48	
    49	def run_single_adapter_discoverability(
    50	    *,
    51	    mcp_server: str,
    52	    adapter: str,
    53	    model: str | None,
    54	    task_list: list[DiscoverabilityTask],
    55	    trials_per_task: int,
    56	    max_cost_usd: float,
    57	    max_runtime_seconds: float | None,
    58	    extra_adapter_kwargs: dict[str, Any],
    59	    t_start: float,
    60	) -> DiscoverabilityResult:
    61	    """Run discoverability evaluation against ONE adapter; produce a `DiscoverabilityResult`.
    62	
    63	    Internal helper extracted from `MCPLibrary.get_tool_discoverability`
    64	    (Story 4.4) so the cross-adapter `Compare Tool Discoverability`
    65	    keyword (Story 13.3) reuses the per-adapter logic without ~80 LoC
    66	    duplication. Behavior MUST equal pre-refactor; verified by Story
    67	    4.4's existing tests passing unchanged.
    68	
    69	    Args:
    70	        mcp_server: Already-validated non-empty MCP server name. NOT
    71	            forwarded to `adapter.run(mcp_servers=...)` in Phase-1
    72	            (DF-4.1-S2 + DF-4.2-S1 carve-out); accepted for
    73	            forward-compat.
    74	        adapter: Adapter name. Resolved via `_kernel.discovery.get_adapter`.
    75	        model: Optional model identifier; forwarded to adapter ctor when
    76	            non-None.
    77	        task_list: Already-loaded + schema-validated list of tasks.
    78	            Caller (single-adapter or compare-multi-adapter) loads the
    79	            YAML ONCE and passes the parsed list here.
    80	        trials_per_task: Pass@k trials per task; already validated >= 1.
    81	        max_cost_usd: Budget cap. Phase-1: tracked, NOT enforced
    82	            (DF-4.4-S1 carry-over).
    83	        max_runtime_seconds: Runtime cap. Phase-1: tracked, NOT enforced.
    84	        extra_adapter_kwargs: Forward-compat kwargs routed to adapter ctor.
    85	        t_start: Wall-clock start time (from the caller's `time.monotonic()`
    86	            BEFORE arg validation / YAML load). Lets compare-multi-adapter
    87	            measure end-to-end across all adapters from a single anchor.
    88	
    89	    Returns:
    90	        ``DiscoverabilityResult`` with per-task results + summary +
    91	        Phase-1 hardcoded ``mcp_coverage="hosted_in_process"`` (DF-4.4-S3
    92	        carry-over).
    93	
    94	    Raises:
    95	        TypeError: When the adapter doesn't accept the forwarded kwargs
    96	            (DF-4.4-S2 carry-over re ctor/run split parity).
    97	    """
    98	    adapter_cls = get_adapter(adapter)
    99	    adapter_ctor_kwargs: dict[str, Any] = dict(extra_adapter_kwargs)
   100	    if model is not None:
   101	        adapter_ctor_kwargs["model"] = model
   102	    try:
   103	        adapter_instance = adapter_cls(**adapter_ctor_kwargs)
   104	    except TypeError as exc:
   105	        raise TypeError(
   106	            f"Adapter {adapter!r} doesn't accept kwargs {sorted(adapter_ctor_kwargs)}; "
   107	            "DF-4.4-S2 carry-over (ctor/run split parity for MCPLibrary "
   108	            "lands in Phase-1.5 — mirroring Story 4.3's "
   109	            "`_split_adapter_kwargs` introspection on OrchestrationLibrary). "
   110	            "For now, pass kwargs the adapter accepts."
   111	        ) from exc
   112	
   113	    # Per-call mcp_servers integration is DF-4.1-S2 / DF-4.2-S1.
   114	    _ = mcp_server
   115	
   116	    per_task: list[TaskResult] = []
   117	    total_cost = 0.0
   118	    for task in task_list:
   119	        tool_calls_per_trial: list[list[Any]] = []
   120	        cost_per_trial: list[float] = []
   121	        success_count = 0
   122	        competing_set: set[str] = set()
   123	        for _ in range(trials_per_task):
   124	            run_result = adapter_instance.run(task.prompt)
   125	            tool_calls_per_trial.append(list(run_result.tool_calls))
   126	            cost_per_trial.append(run_result.cost_usd)
   127	            total_cost += run_result.cost_usd
   128	            called_names = {tc.name for tc in run_result.tool_calls}
   129	            # Story 4.4 3-way MED-A: wildcard-success mode when expected_tools empty.
   130	            if task.expected_tools:
   131	                expected_set = set(task.expected_tools)
   132	                if called_names & expected_set:
   133	                    success_count += 1
   134	                competing_set.update(called_names - expected_set)
   135	            else:
   136	                if called_names:
   137	                    success_count += 1
   138	                competing_set.update(called_names)
   139	        lower, upper = wilson_score_interval(success_count, trials_per_task)
   140	        per_task.append(
   141	            TaskResult(
   142	                task_id=task.id,
   143	                task_prompt=task.prompt,
   144	                trials_run=trials_per_task,
   145	                success_count=success_count,
   146	                tool_calls_per_trial=tool_calls_per_trial,
   147	                competing_tools_picked=sorted(competing_set),
   148	                cost_per_trial_usd=cost_per_trial,
   149	                wilson_ci_lower=lower,
   150	                wilson_ci_upper=upper,
   151	            )
   152	        )
   153	    total_runtime = time.monotonic() - t_start
   154	
   155	    # Overall pass rate weighted by trials.
   156	    total_trials = sum(t.trials_run for t in per_task)
   157	    total_successes = sum(t.success_count for t in per_task)
   158	    overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0
   159	
   160	    # Phase-1: mcp_coverage hardcoded (DF-4.4-S3 carry-over).
   161	    _ = max_cost_usd
   162	    _ = max_runtime_seconds
   163	    return DiscoverabilityResult(
   164	        per_task_results=per_task,
   165	        summary=DiscoverabilitySummary(
   166	            overall_pass_rate=overall_pass_rate,
   167	            total_cost_usd=total_cost,
   168	            total_runtime_seconds=total_runtime,
   169	        ),
   170	        mcp_coverage="hosted_in_process",
   171	    )

---
   130	    PRD wording (Auditor citation-drift catch).
   131	    """
   132	
   133	    overall_pass_rate: float
   134	    total_cost_usd: float
   135	    total_runtime_seconds: float
   136	
   137	
   138	@dataclass(frozen=True)
   139	class DiscoverabilityResult:
   140	    """Top-level result of `MCP.Get Tool Discoverability` (Story 4.4 / PRD FR10a).
   141	
   142	    Shape per PRD FR10a L1499:
   143	        - `per_task_results: list[TaskResult]`
   144	        - `summary: DiscoverabilitySummary` (overall pass rate, total cost,
   145	          total runtime)
   146	        - `mcp_coverage: Literal[...]` per Story 1b.2 `compute_mcp_coverage`
   147	          + ADR-016 3-value enum.
   148	    """
   149	
   150	    per_task_results: list[TaskResult]
   151	    summary: DiscoverabilitySummary
   152	    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]
   153	
   154	    def __post_init__(self) -> None:
   155	        object.__setattr__(self, "per_task_results", list(self.per_task_results))
   156	
   157	
   158	# --------------------------------------------------------------------------- #
   159	# Story 13.3 (Epic 13) — cross-adapter comparison surface (FR10b)             #
   160	# --------------------------------------------------------------------------- #
   161	
   162	
   163	@dataclass(frozen=True)
   164	class PairwiseAdapterDelta:
   165	    """One pairwise cross-adapter delta within `DiscoverabilityComparisonResult` (Story 13.3).
   166	
   167	    Carries the Mann-Whitney U result + the per-task pass-rate
   168	    differential between two adapters. The cohort comparison ships
   169	    C(N, 2) pairwise deltas across N adapters; each delta is indexed by
   170	    the ordered key `f"{adapter_a}_vs_{adapter_b}"` in
   171	    `DiscoverabilityComparisonResult.cross_adapter_deltas`.
   172	
   173	    Fields:
   174	        adapter_a: First adapter name.
   175	        adapter_b: Second adapter name (must differ from `adapter_a`).
   176	        pass_rate_delta: ``mean(adapter_a per-task pass rates) - mean(adapter_b)``;
   177	            in ``[-1.0, 1.0]``. Positive → adapter_a outperforms adapter_b.
   178	        mann_whitney_result: Story 13.1 ``MannWhitneyResult`` (Mann-Whitney
   179	            U on the per-task pass rates with `predicate=lambda r: r.pass_rate`).
   180	        significant_at_alpha_05: ``mann_whitney_result.p_value < 0.05``;
   181	            redundant with the Mann-Whitney p-value but stored explicitly so
   182	            consumers can ``Should Be True ${delta.significant_at_alpha_05}``
   183	            without re-deriving.
   184	    """
   185	
   186	    adapter_a: str
   187	    adapter_b: str
   188	    pass_rate_delta: float
   189	    mann_whitney_result: MannWhitneyResult
   190	    significant_at_alpha_05: bool
   191	
   192	    def __post_init__(self) -> None:
   193	        if self.adapter_a == self.adapter_b:
   194	            raise ValueError(
   195	                f"PairwiseAdapterDelta requires distinct adapters; got "
   196	                f"adapter_a={self.adapter_a!r} == adapter_b={self.adapter_b!r}"
   197	            )
   198	        if not (-1.0 <= self.pass_rate_delta <= 1.0):
   199	            raise ValueError(f"pass_rate_delta must be in [-1.0, 1.0]; got {self.pass_rate_delta!r}")
   200	        # `nan < 0.05` evaluates to False, so significant_at_alpha_05 is
   201	        # False for nan p_values (identical-samples scipy convention) —
   202	        # consistent with "cannot reject the null."
   203	        import math
   204	
   205	        p = self.mann_whitney_result.p_value
   206	        expected = (not math.isnan(p)) and p < 0.05
   207	        if self.significant_at_alpha_05 != expected:
   208	            raise ValueError(
   209	                f"significant_at_alpha_05 must equal (p_value < 0.05; nan treated as not significant); "
   210	                f"got significant_at_alpha_05={self.significant_at_alpha_05!r} but "
   211	                f"p_value={self.mann_whitney_result.p_value!r}"
   212	            )
   213	
   214	
   215	@dataclass(frozen=True)
   216	class DiscoverabilityComparisonSummary:
   217	    """Aggregate roll-up of `DiscoverabilityComparisonResult` (Story 13.3).
   218	
   219	    Fields:
   220	        total_cost_usd: Sum of per-adapter `summary.total_cost_usd` across all adapters.
   221	        total_runtime_seconds: MAX of per-adapter `summary.total_runtime_seconds`
   222	            (parallel cross-adapter fan-out wall-clock — adapters run sequentially
   223	            in Phase-2 but the runtime metric models the eventual parallel target).
   224	        pass_rate_per_adapter: Mapping of adapter name → overall pass rate
   225	            (i.e., `per_adapter_results[adapter].summary.overall_pass_rate`).
   226	        best_adapter: Adapter name with the highest pass rate.
   227	        worst_adapter: Adapter name with the lowest pass rate. Equals
   228	            `best_adapter` only when all adapters tie.
   229	    """
   230	
   231	    total_cost_usd: float
   232	    total_runtime_seconds: float
   233	    pass_rate_per_adapter: Mapping[str, float]
   234	    best_adapter: str
   235	    worst_adapter: str
   236	
   237	    def __post_init__(self) -> None:
   238	        object.__setattr__(self, "pass_rate_per_adapter", dict(self.pass_rate_per_adapter))
   239	        if self.best_adapter not in self.pass_rate_per_adapter:
   240	            raise ValueError(
   241	                f"best_adapter={self.best_adapter!r} not in "
   242	                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
   243	            )
   244	        if self.worst_adapter not in self.pass_rate_per_adapter:
   245	            raise ValueError(
   246	                f"worst_adapter={self.worst_adapter!r} not in "
   247	                f"pass_rate_per_adapter keys {sorted(self.pass_rate_per_adapter.keys())!r}"
   248	            )
   249	
   250	
   251	@dataclass(frozen=True)
   252	class DiscoverabilityComparisonResult:
   253	    """Top-level result of `MCP.Compare Tool Discoverability` (Story 13.3 / PRD FR10b).
   254	
   255	    Shape per epics.md L2186-2187 + Story 13.3 D-2 ratified shape:
   256	        - `adapters: tuple[str, ...]` — adapter names in input order (≥2).
   257	        - `per_adapter_results: Mapping[str, DiscoverabilityResult]` —
   258	          one full `DiscoverabilityResult` per adapter (mirrors what
   259	          `MCP.Get Tool Discoverability` returns for the single-adapter case).
   260	        - `cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]` —
   261	          C(N, 2) pairwise deltas keyed by `f"{adapter_a}_vs_{adapter_b}"`.
   262	          For N=2 there is 1 delta; for N=3 there are 3 deltas.
   263	        - `heatmap: CohortHeatmap` — multi-column heatmap (one column per
   264	          adapter; rows = task IDs). Built via
   265	          `CohortHeatmap.from_comparison(self)`.
   266	        - `summary: DiscoverabilityComparisonSummary` — aggregate roll-up.
   267	
   268	    Cross-consistency invariants checked in `__post_init__`:
   269	        - `len(adapters) >= 2`.
   270	        - `set(adapters) == set(per_adapter_results.keys())`.
   271	        - `set(adapters) == set(heatmap.models)`.
   272	    """
   273	
   274	    adapters: tuple[str, ...]
   275	    per_adapter_results: Mapping[str, DiscoverabilityResult]
   276	    cross_adapter_deltas: Mapping[str, PairwiseAdapterDelta]
   277	    heatmap: CohortHeatmap
   278	    summary: DiscoverabilityComparisonSummary
   279	
   280	    def __post_init__(self) -> None:
   281	        # Tuple coercion + defensive Mapping → dict casts (Story 1b.2 M_R6).
   282	        object.__setattr__(self, "adapters", tuple(self.adapters))
   283	        object.__setattr__(self, "per_adapter_results", dict(self.per_adapter_results))
   284	        object.__setattr__(self, "cross_adapter_deltas", dict(self.cross_adapter_deltas))
   285	        if len(self.adapters) < 2:
   286	            raise ValueError(f"DiscoverabilityComparisonResult requires len(adapters) >= 2; got {self.adapters!r}")
   287	        if set(self.adapters) != set(self.per_adapter_results.keys()):
   288	            raise ValueError(
   289	                f"adapters {sorted(self.adapters)!r} must equal "
   290	                f"per_adapter_results keys {sorted(self.per_adapter_results.keys())!r}"
   291	            )
   292	        if set(self.adapters) != set(self.heatmap.models):
   293	            raise ValueError(
   294	                f"adapters {sorted(self.adapters)!r} must equal heatmap.models {sorted(self.heatmap.models)!r}"
   295	            )

---
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""``CohortHeatmap`` dataclass + ASCII + dict renderers (Story 8b.2)."""
    16	
    17	from __future__ import annotations
    18	
    19	from dataclasses import dataclass
    20	from typing import TYPE_CHECKING
    21	
    22	if TYPE_CHECKING:
    23	    from AgentEval.discoverability.schema import (
    24	        DiscoverabilityComparisonResult,
    25	        DiscoverabilityResult,
    26	    )
    27	
    28	__all__ = ["CohortHeatmap"]
    29	
    30	
    31	@dataclass(frozen=True)
    32	class CohortHeatmap:
    33	    """Pass@k cohort heatmap (Story 8b.2 / FR55-ASCII + dict).
    34	
    35	    Phase-1: single-model heatmap (rows = tasks, single column = model).
    36	    Multi-model comparison (rows = tasks, columns = models) is Phase-2.
    37	
    38	    The model name in Phase-1 defaults to ``"default"`` unless the caller
    39	    provides one via ``from_discoverability(result, model_name=...)``.
    40	    """
    41	
    42	    tasks: tuple[str, ...]
    43	    models: tuple[str, ...]
    44	    # Mapping: cell[(task_id, model_name)] = pass_at_k.
    45	    # Stored as a frozen-friendly tuple of (task, model, value) triples so the
    46	    # dataclass remains hashable.
    47	    cells: tuple[tuple[str, str, float], ...]
    48	
    49	    @classmethod
    50	    def from_discoverability(
    51	        cls,
    52	        result: DiscoverabilityResult,
    53	        *,
    54	        model_name: str = "default",
    55	    ) -> CohortHeatmap:
    56	        """Build a single-model heatmap from a ``DiscoverabilityResult``.
    57	
    58	        Args:
    59	            result: Story 4.4 ``DiscoverabilityResult``.
    60	            model_name: Column label for the single-model column.
    61	
    62	        Returns:
    63	            ``CohortHeatmap`` instance with one column.
    64	        """
    65	        tasks = tuple(t.task_id for t in result.per_task_results)
    66	        cells = tuple((t.task_id, model_name, t.pass_rate) for t in result.per_task_results)
    67	        return cls(tasks=tasks, models=(model_name,), cells=cells)
    68	
    69	    @classmethod
    70	    def from_comparison(
    71	        cls,
    72	        result: DiscoverabilityComparisonResult,
    73	    ) -> CohortHeatmap:
    74	        """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).
    75	
    76	        Columns = adapter names (preserving input order from ``result.adapters``).
    77	        Rows = task IDs (union across all per-adapter results, preserving
    78	        first-encounter order — defensively handles the edge case where a
    79	        stub adapter dropped a task; in production all adapters run the
    80	        SAME task set so the union equals each adapter's task list).
    81	
    82	        Args:
    83	            result: Story 13.3 ``DiscoverabilityComparisonResult``.
    84	
    85	        Returns:
    86	            ``CohortHeatmap`` with one column per adapter + one row per task.
    87	        """
    88	        # Build the row list as the union preserving first-encounter order.
    89	        seen: set[str] = set()
    90	        tasks_list: list[str] = []
    91	        for adapter in result.adapters:
    92	            for task_result in result.per_adapter_results[adapter].per_task_results:
    93	                if task_result.task_id not in seen:
    94	                    seen.add(task_result.task_id)
    95	                    tasks_list.append(task_result.task_id)
    96	        tasks = tuple(tasks_list)
    97	        models = result.adapters
    98	        cells = tuple(
    99	            (task_result.task_id, adapter, task_result.pass_rate)
   100	            for adapter in result.adapters
   101	            for task_result in result.per_adapter_results[adapter].per_task_results
   102	        )
   103	        return cls(tasks=tasks, models=models, cells=cells)
   104	
   105	    def as_dict(self) -> dict[str, dict[str, float]]:
   106	        """Nested dict: ``{task_id: {model_name: pass_at_k}}``."""
   107	        out: dict[str, dict[str, float]] = {task: {} for task in self.tasks}
   108	        for task, model, value in self.cells:
   109	            out.setdefault(task, {})[model] = value
   110	        return out
   111	
   112	    def as_ascii(self) -> str:
   113	        """ASCII heatmap with box-drawing characters.
   114	
   115	        Rows = tasks, columns = models, cells = Pass@k as 2-decimal float.
   116	        Empty input → ``"(empty heatmap)"`` placeholder.
   117	        """
   118	        if not self.tasks or not self.models:
   119	            return "(empty heatmap)"
   120	
   121	        data = self.as_dict()
   122	        # Story 8b.2 v0.2.0 kilo/minimax cross-LLM review HIGH-1 patch
   123	        # (2026-05-26): missing cells render as " — " sentinel (em-dash with
   124	        # spaces) instead of silently substituting 0.0, which was
   125	        # indistinguishable from a genuine 0% pass-rate. Operators can now
   126	        # tell missing-from-data apart from real-zero.
   127	        _missing = " — "
   128	
   129	        def _fmt(task: str, model: str) -> str:
   130	            value = data.get(task, {}).get(model)
   131	            return _missing if value is None else f"{value:.2f}"
   132	
   133	        # Compute column widths.
   134	        task_col_width = max(len("Task"), *(len(t) for t in self.tasks))
   135	        model_widths: dict[str, int] = {}
   136	        for model in self.models:
   137	            cells = [_fmt(task, model) for task in self.tasks]
   138	            model_widths[model] = max(len(model), *(len(c) for c in cells))
   139	
   140	        # Render header row.

---
    50	            tends to be larger; r ≈ 0 → substantial overlap. Matches Cliff's
    51	            delta sign convention shipped by ``Stat.Cliff Delta`` (FR29b).
    52	        n_a: Number of samples in the first group (after predicate extraction).
    53	        n_b: Number of samples in the second group (after predicate extraction).
    54	
    55	    Validation (``__post_init__``): ``n_a >= 1``, ``n_b >= 1``,
    56	    ``-1.0 <= effect_size_r <= 1.0``, ``0.0 <= p_value <= 1.0`` —
    57	    all raise ``ValueError`` on violation.
    58	    """
    59	
    60	    u_statistic: float
    61	    p_value: float
    62	    effect_size_r: float
    63	    n_a: int
    64	    n_b: int
    65	
    66	    def __post_init__(self) -> None:
    67	        import math
    68	
    69	        if self.n_a < 1:
    70	            raise ValueError(f"n_a must be >= 1; got {self.n_a!r}")
    71	        if self.n_b < 1:
    72	            raise ValueError(f"n_b must be >= 1; got {self.n_b!r}")
    73	        if not (-1.0 <= self.effect_size_r <= 1.0):
    74	            raise ValueError(f"effect_size_r must be in [-1.0, 1.0]; got {self.effect_size_r!r}")
    75	        # `p_value=nan` is the scipy convention when both samples have
    76	        # identical rank distributions (no variance → no test possible).
    77	        # Permit nan + the [0, 1] range; reject anything else.
    78	        if not (math.isnan(self.p_value) or 0.0 <= self.p_value <= 1.0):
    79	            raise ValueError(
    80	                f"p_value must be in [0.0, 1.0] or nan (scipy identical-samples convention); "
    81	                f"got {self.p_value!r}"
    82	            )
    83	
    84	
    85	@dataclass(frozen=True, slots=True)
    86	class KeywordRun:
    87	    """Single-trial result from `Stat.Run N Times` (PRD FR26).
    88	
    89	    Fields:
    90	        trial_index: 0-indexed trial number within the parent `Stat.Run N Times` call.
    91	        test_id: ContextVar-bound sub-scope id, formatted as
    92	            `{parent_test_id}::trial-{trial_index}` (per Story 4.3 ContextVar precedent).
    93	        keyword_name: RF name of the wrapped keyword (e.g., `Send Prompt`).
    94	        result: Raw return value from the wrapped keyword (commonly an
    95	            `AgentRunResult`, but any return type is preserved).

exec
/bin/bash -lc "grep -n \"FR10b:\" -A2 -B2 _bmad-output/planning-artifacts/prd.md; printf '\\n---\\n'; sed -n '1497,1503p' _bmad-output/planning-artifacts/prd.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
1498-- **FR9b:** Agent Surface Author can call `MCP.Call Tool <handle> <tool_name> <args_dict>` and receive an `MCPToolResult` (`content` list of MCP content blocks per spec, `is_error` mirroring the SDK's `CallToolResult.isError`, `error_message` extracted from the first text-content block when `is_error=True`, `latency_ms` wall-clock for the SDK round-trip, `correlation_id` per-call uuid4 hex Phase-1 placeholder for Epic 5 trace-id wiring); same call supports AssertionEngine matchers (`Should Contain`, `matches`, `Should Match Schema`) against `content`. (Story 3.2 code-review Auditor HIGH 2026-05-19: amended from pre-edit `(result, error, latency_ms)` shape to match the 5-field implementation that ships in `src/AgentEval/mcp/lifecycle.py:MCPToolResult` — same pattern as Story 3.1's FR8 prefix amendment. Pre-edit shape was too narrow: `content` is a LIST of typed blocks per MCP spec, not a scalar `result`; tool-level error responses surface as `is_error=True` first-class data per FR9b semantic intent, distinct from infrastructure failure which raises `MCPConnectionLostError`; per-call `correlation_id` ships now so Epic 5 trace wiring doesn't require a breaking API change.)
1499-- **FR10a:** Agent Surface Author can call `MCP.Get Tool Discoverability mcp_server=<name> adapter=<name> model=<id> tasks=<yaml-path> trials_per_task=<n> max_cost_usd=<usd>` (single-runtime + single-model Phase-1 surface; FR10b lifts the per-model cohort restriction in Phase-2) and receive a `DiscoverabilityResult` containing `per_task_results: list[TaskResult]` (each with `task_id`, `task_prompt`, `trials_run`, `success_count` per Pass@k semantics, `tool_calls_per_trial`, `competing_tools_picked`, `cost_per_trial_usd`, `wilson_ci_lower`, `wilson_ci_upper`), `summary` (overall pass-rate, total-cost, total-runtime), `mcp_coverage` per Story 1b.2 `compute_mcp_coverage`. (Story 4.4 pre-create-story drift D-C 2026-05-20: pre-edit FR10a wording named `tool=<name>` `by_models=<list>` `with_tasks=<list>` `k=<n>` — amended to match the ratified operational shape per epics.md L1403 + Story 4.4 implementation. Phase-1 single-runtime is preserved; the `tool=<name>` focus filter becomes an optional task-level field within the YAML per AC-DISCOVER-01 evidence-block design. Wilson-CI cohort table per AC-DISCOVER-01 is computed per-task across `trials_per_task` trials — single-model variant per Phase-1 carve-out.) [Tier 3, Phase 1; single-runtime version. FR10b lifts the single-runtime restriction in Phase 2.]
1500:- **FR10b:** Agent Surface Author can compare `DiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...]` (≥2 required; N=3+ enables ranking across Claude/GPT/Copilot/...) and receive a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-runtime delta with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data — **Phase 2** (Story 13.3; depends on ≥2 fully-shipped Tier-1 runtimes; Phase 1 has only Generic + CC CLI where Generic is a thin LiteLLM stub; backwards-compat with the original A/B semantic via a 2-element list). Story 13.3 D-1 fix-the-losing-source-NOW 2026-06-01: amended from earlier `runtime_a=<adapter> runtime_b=<adapter>` 2-runtime A/B wording to the N-runtime `adapters=[...]` shape per epics.md L2186 ratified spec + the symmetric Story 13.5 Skill version; also corrected stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
1501-- **FR11:** Library raises `CostExceededError("projected $X.XX > max_cost_usd=$5.00; raise limit or reduce task_list")` pre-flight if the projected cost for a fanned-out keyword exceeds `max_cost_usd` (default 5.00 USD); during execution, the cumulative cost meter hard-stops with `CostExceededError("$X.XX exceeded $Y.YY=1.1× max_cost_usd")` at 1.1× the limit. Verifiable via `Stat.Run N Times 10 max_cost_usd=0.01 ...` against a deterministic mock provider.
1502-- **FR11b (time guardrail — sibling to FR11):** Library exposes `max_runtime_seconds` keyword argument (default `None` — no time cap; opt-in) on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). When set, library performs a pre-flight wall-clock estimate (`mcp_startup_estimate × n_servers × n_trials + agent_runtime_estimate × n_trials`) and raises `RuntimeBudgetExceededError("projected XXs > max_runtime_seconds=YY; reduce trials, use mcp_per_test=suite, or raise limit")` pre-flight; mid-run wall-clock meter hard-stops at 1.1× declared limit. Orthogonal to FR11: cost guard catches token spend; time guard catches latency under heavy MCP servers (e.g., `rf-mcp` / `robotmcp` take several seconds to start; multiplied across trials this can silently blow runtime budgets). Verifiable via `Stat.Run N Times 20 max_runtime_seconds=5 ...` against a deterministic slow-mock provider.

---
- **FR9a:** Agent Surface Author can call `MCP.List Tools <handle>` and receive an ordered list of `MCPTool` records (`name`, `description`, `input_schema`, `output_schema`). The field-projection convenience keywords `Get Tool Names` / `Get Tool Descriptions` are deferred to Phase-1.5 (Story 3.2 code-review Auditor HIGH 2026-05-19: PRD originally named both projection keywords inline with FR9a; Story 3.2 implements only `MCP.List Tools` because AssertionEngine + native Python list-comprehension + `${tools[*].name}` index access cover the documented use case without a dedicated keyword. Phase-1.5 may re-introduce as convenience keywords if .robot-test ergonomics warrant — tracked in `deferred-work.md`).
- **FR9b:** Agent Surface Author can call `MCP.Call Tool <handle> <tool_name> <args_dict>` and receive an `MCPToolResult` (`content` list of MCP content blocks per spec, `is_error` mirroring the SDK's `CallToolResult.isError`, `error_message` extracted from the first text-content block when `is_error=True`, `latency_ms` wall-clock for the SDK round-trip, `correlation_id` per-call uuid4 hex Phase-1 placeholder for Epic 5 trace-id wiring); same call supports AssertionEngine matchers (`Should Contain`, `matches`, `Should Match Schema`) against `content`. (Story 3.2 code-review Auditor HIGH 2026-05-19: amended from pre-edit `(result, error, latency_ms)` shape to match the 5-field implementation that ships in `src/AgentEval/mcp/lifecycle.py:MCPToolResult` — same pattern as Story 3.1's FR8 prefix amendment. Pre-edit shape was too narrow: `content` is a LIST of typed blocks per MCP spec, not a scalar `result`; tool-level error responses surface as `is_error=True` first-class data per FR9b semantic intent, distinct from infrastructure failure which raises `MCPConnectionLostError`; per-call `correlation_id` ships now so Epic 5 trace wiring doesn't require a breaking API change.)
- **FR10a:** Agent Surface Author can call `MCP.Get Tool Discoverability mcp_server=<name> adapter=<name> model=<id> tasks=<yaml-path> trials_per_task=<n> max_cost_usd=<usd>` (single-runtime + single-model Phase-1 surface; FR10b lifts the per-model cohort restriction in Phase-2) and receive a `DiscoverabilityResult` containing `per_task_results: list[TaskResult]` (each with `task_id`, `task_prompt`, `trials_run`, `success_count` per Pass@k semantics, `tool_calls_per_trial`, `competing_tools_picked`, `cost_per_trial_usd`, `wilson_ci_lower`, `wilson_ci_upper`), `summary` (overall pass-rate, total-cost, total-runtime), `mcp_coverage` per Story 1b.2 `compute_mcp_coverage`. (Story 4.4 pre-create-story drift D-C 2026-05-20: pre-edit FR10a wording named `tool=<name>` `by_models=<list>` `with_tasks=<list>` `k=<n>` — amended to match the ratified operational shape per epics.md L1403 + Story 4.4 implementation. Phase-1 single-runtime is preserved; the `tool=<name>` focus filter becomes an optional task-level field within the YAML per AC-DISCOVER-01 evidence-block design. Wilson-CI cohort table per AC-DISCOVER-01 is computed per-task across `trials_per_task` trials — single-model variant per Phase-1 carve-out.) [Tier 3, Phase 1; single-runtime version. FR10b lifts the single-runtime restriction in Phase 2.]
- **FR10b:** Agent Surface Author can compare `DiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...]` (≥2 required; N=3+ enables ranking across Claude/GPT/Copilot/...) and receive a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-runtime delta with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data — **Phase 2** (Story 13.3; depends on ≥2 fully-shipped Tier-1 runtimes; Phase 1 has only Generic + CC CLI where Generic is a thin LiteLLM stub; backwards-compat with the original A/B semantic via a 2-element list). Story 13.3 D-1 fix-the-losing-source-NOW 2026-06-01: amended from earlier `runtime_a=<adapter> runtime_b=<adapter>` 2-runtime A/B wording to the N-runtime `adapters=[...]` shape per epics.md L2186 ratified spec + the symmetric Story 13.5 Skill version; also corrected stale `ToolDiscoverabilityResult` type name → `DiscoverabilityResult` (the FR10a-shipped type).
- **FR11:** Library raises `CostExceededError("projected $X.XX > max_cost_usd=$5.00; raise limit or reduce task_list")` pre-flight if the projected cost for a fanned-out keyword exceeds `max_cost_usd` (default 5.00 USD); during execution, the cumulative cost meter hard-stops with `CostExceededError("$X.XX exceeded $Y.YY=1.1× max_cost_usd")` at 1.1× the limit. Verifiable via `Stat.Run N Times 10 max_cost_usd=0.01 ...` against a deterministic mock provider.
- **FR11b (time guardrail — sibling to FR11):** Library exposes `max_runtime_seconds` keyword argument (default `None` — no time cap; opt-in) on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). When set, library performs a pre-flight wall-clock estimate (`mcp_startup_estimate × n_servers × n_trials + agent_runtime_estimate × n_trials`) and raises `RuntimeBudgetExceededError("projected XXs > max_runtime_seconds=YY; reduce trials, use mcp_per_test=suite, or raise limit")` pre-flight; mid-run wall-clock meter hard-stops at 1.1× declared limit. Orthogonal to FR11: cost guard catches token spend; time guard catches latency under heavy MCP servers (e.g., `rf-mcp` / `robotmcp` take several seconds to start; multiplied across trials this can silently blow runtime budgets). Verifiable via `Stat.Run N Times 20 max_runtime_seconds=5 ...` against a deterministic slow-mock provider.


codex
I have the key ratified lines now. The next step is empirical: run the existing Story 4.4 suite unchanged, then run the new comparison tests and a few direct probes for adapter-count math, ordering, and the identical-samples `nan` path.
exec
/bin/bash -lc 'pytest -q tests/unit/discoverability/test_keyword.py' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: pytest: command not found

exec
/bin/bash -lc 'pytest --collect-only -q tests/unit/discoverability/test_comparison.py tests/unit/discoverability/test_comparison_extras_gate.py tests/integration/discoverability/test_compare_e2e.py' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: pytest: command not found

exec
/bin/bash -lc 'pytest -q tests/unit/discoverability/test_comparison.py tests/unit/discoverability/test_comparison_extras_gate.py tests/integration/discoverability/test_compare_e2e.py' in /home/many/workspace/robotframework-agenteval
 exited 127 in 0ms:
/bin/bash: line 1: pytest: command not found

codex
`pytest` isn’t on PATH here; the project uses `uv`. I’m rerunning the same probes through `uv run pytest`, which will also tell me whether the claimed new tests actually collect and whether the refactor preserved Story 4.4 behavior.
exec
/bin/bash -lc 'uv run pytest --collect-only -q tests/unit/discoverability/test_comparison.py tests/unit/discoverability/test_comparison_extras_gate.py tests/integration/discoverability/test_compare_e2e.py' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'uv run pytest -q tests/unit/discoverability/test_keyword.py' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'uv run pytest -q tests/unit/discoverability/test_comparison.py tests/unit/discoverability/test_comparison_extras_gate.py tests/integration/discoverability/test_compare_e2e.py' in /home/many/workspace/robotframework-agenteval
 succeeded in 2486ms:
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_single_adapter
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_adapters_keys_mismatch
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_heatmap_models_mismatch
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_identical_adapters
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_out_of_range_delta
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_significance_inconsistency
tests/unit/discoverability/test_comparison.py::test_comparison_summary_rejects_unknown_best_adapter
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_2_adapters
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_3_adapters
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_per_task_pass_rate_in_cells
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_as_ascii_3_columns
tests/unit/discoverability/test_comparison.py::test_compare_2_adapters_produces_1_pairwise_delta
tests/unit/discoverability/test_comparison.py::test_compare_3_adapters_produces_3_pairwise_deltas
tests/unit/discoverability/test_comparison.py::test_compare_pairwise_keys_preserve_input_order
tests/unit/discoverability/test_comparison.py::test_compare_clearly_different_distributions_significant
tests/unit/discoverability/test_comparison.py::test_compare_identical_distributions_not_significant
tests/unit/discoverability/test_comparison_extras_gate.py::test_comparison_schema_importable_without_extra
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_raises_import_error_when_advanced_extra_missing
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_import_error_message_contract
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_arg_validation_runs_before_extras_gate
tests/integration/discoverability/test_compare_e2e.py::test_compare_3_stub_adapters_end_to_end
tests/integration/discoverability/test_compare_e2e.py::test_compare_rejects_single_adapter_list_at_arg_validation
tests/integration/discoverability/test_compare_e2e.py::test_compare_rejects_duplicate_adapter_names

23 tests collected in 1.15s

 succeeded in 4254ms:
.......................                                                  [100%]
23 passed in 2.58s

 succeeded in 7001ms:
....................                                                     [100%]
20 passed in 4.88s

codex
The broad test pass is real: the refactor didn’t break the current Story 4.4 unit file, and the new files collect 23 tests, not the claimed 22. I’m now probing the places where tests can still miss correctness issues: runtime accounting, reversed adapter-order keys, `N=4`, and the identical-distribution Mann-Whitney path.
exec
/bin/bash -lc "uv run python - <<'PY'
from AgentEval.stats.mannwhitney import compute_mann_whitney_u
for a,b in [([1.0,1.0,1.0],[1.0,1.0,1.0]), ([0.0,0.0,0.0],[0.0,0.0,0.0]), ([1.0,1.0,1.0,1.0],[1.0,1.0,1.0,1.0]), ([1,1,1,1,1],[1,1,1,1,1])]:
    r=compute_mann_whitney_u(a,b)
    print(a,b,'->',r)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run python - <<'PY'
import time
from pathlib import Path
from AgentEval.mcp.library import MCPLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunResult, AgentRunMetadata, ToolCallTrace, Usage

fixture = Path('tests/fixtures/discoverability/tasks-basic.yaml')

class SlowAdapter(InProcessAdapter):
    def run(self, prompt, **kwargs):
        time.sleep(0.05)
        tc = ToolCallTrace(name='echo_back',args={},result=None,error=None,latency_ms=1.0,source='adapter',gen_ai_tool_call_id='x',sequence_index=0)
        return AgentRunResult(response_text='x', tool_calls=[tc], usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='0'*32)

register_adapter('slow_a', SlowAdapter)
register_adapter('slow_b', SlowAdapter)
lib = MCPLibrary()
start = time.monotonic()
r = lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['slow_a','slow_b'], tasks=str(fixture), trials_per_task=2)
elapsed = time.monotonic() - start
print('measured_elapsed', elapsed)
print('reported_summary_runtime', r.summary.total_runtime_seconds)
print('per_adapter_runtimes', {k:v.summary.total_runtime_seconds for k,v in r.per_adapter_results.items()})
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run python - <<'PY'
from pathlib import Path
from AgentEval.mcp.library import MCPLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunResult, AgentRunMetadata, ToolCallTrace, Usage

fixture = Path('tests/fixtures/discoverability/tasks-basic.yaml')

def make_adapter(tool_names_per_call):
    class A(InProcessAdapter):
        _i = 0
        def run(self, prompt, **kwargs):
            i=type(self)._i; type(self)._i += 1
            names = tool_names_per_call[i] if i < len(tool_names_per_call) else []
            tool_calls=[ToolCallTrace(name=n,args={},result=None,error=None,latency_ms=1.0,source='adapter',gen_ai_tool_call_id=f'id-{i}-{j}',sequence_index=j) for j,n in enumerate(names)]
            return AgentRunResult(response_text='x', tool_calls=tool_calls, usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id=f'{i:032d}')
    return A

# N=4 count probe
for name, pattern in {
    'n4_a': [['echo_back']]*100,
    'n4_b': [['echo_back'],[]]*50,
    'n4_c': [[]]*100,
    'n4_d': [['other']]*100,
}.items():
    register_adapter(name, make_adapter(pattern))
lib=MCPLibrary()
r = lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['n4_a','n4_b','n4_c','n4_d'], tasks=str(fixture), trials_per_task=5)
print('N4 keys', list(r.cross_adapter_deltas.keys()), 'len=', len(r.cross_adapter_deltas))

# order probe
for name, pattern in {
    'ord_a': [['echo_back']]*100,
    'ord_b': [[]]*100,
    'ord_c': [['other']]*100,
}.items():
    register_adapter(name, make_adapter(pattern))
r1 = lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['ord_a','ord_b','ord_c'], tasks=str(fixture), trials_per_task=2)
r2 = lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['ord_c','ord_b','ord_a'], tasks=str(fixture), trials_per_task=2)
print('order1', list(r1.cross_adapter_deltas.keys()))
print('order2', list(r2.cross_adapter_deltas.keys()))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 2100ms:
[1.0, 1.0, 1.0] [1.0, 1.0, 1.0] -> MannWhitneyResult(u_statistic=4.5, p_value=nan, effect_size_r=0.0, n_a=3, n_b=3)
[0.0, 0.0, 0.0] [0.0, 0.0, 0.0] -> MannWhitneyResult(u_statistic=4.5, p_value=nan, effect_size_r=0.0, n_a=3, n_b=3)
[1.0, 1.0, 1.0, 1.0] [1.0, 1.0, 1.0, 1.0] -> MannWhitneyResult(u_statistic=8.0, p_value=nan, effect_size_r=0.0, n_a=4, n_b=4)
[1, 1, 1, 1, 1] [1, 1, 1, 1, 1] -> MannWhitneyResult(u_statistic=12.5, p_value=nan, effect_size_r=0.0, n_a=5, n_b=5)

 succeeded in 3257ms:
N4 keys ['n4_a_vs_n4_b', 'n4_a_vs_n4_c', 'n4_a_vs_n4_d', 'n4_b_vs_n4_c', 'n4_b_vs_n4_d', 'n4_c_vs_n4_d'] len= 6
order1 ['ord_a_vs_ord_b', 'ord_a_vs_ord_c', 'ord_b_vs_ord_c']
order2 ['ord_c_vs_ord_b', 'ord_c_vs_ord_a', 'ord_b_vs_ord_a']

 succeeded in 3859ms:
measured_elapsed 2.1785764321684837
reported_summary_runtime 0.3013240317814052
per_adapter_runtimes {'slow_a': 0.3013240317814052, 'slow_b': 0.30095729092136025}

codex
The `nan` behavior is real in this environment: identical constant samples do produce `p_value=nan`, and the runtime accounting is already showing a major mismatch. I’m pulling one more probe through the keyword result path for the `nan` propagation and checking a couple of edge invariants in the schema and tests.
exec
/bin/bash -lc "nl -ba tests/unit/discoverability/test_comparison.py | sed -n '1,260p'; printf '\\n---\\n'; nl -ba tests/unit/discoverability/test_comparison_extras_gate.py | sed -n '1,220p'; printf '\\n---\\n'; nl -ba tests/integration/discoverability/test_compare_e2e.py | sed -n '1,260p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Unit tests for `MCP.Compare Tool Discoverability` cross-adapter surface (Story 13.3).
    16	
    17	Coverage:
    18	- `DiscoverabilityComparisonResult` / `PairwiseAdapterDelta` /
    19	  `DiscoverabilityComparisonSummary` dataclass validators.
    20	- `CohortHeatmap.from_comparison` multi-column heatmap.
    21	- Pairwise delta computation (C(N, 2) coverage for N=2 + N=3).
    22	- Mann-Whitney U dispatch via the Story 13.1 pure helper.
    23	
    24	ImportError-gate tests for the `[agenteval-advanced]` extra requirement
    25	live in the companion `test_comparison_extras_gate.py` file per Story
    26	13.1 L-2 lesson (NO top-level `importorskip` so they run in both base
    27	+ WITH-extras CI envs).
    28	"""
    29	
    30	from __future__ import annotations
    31	
    32	from pathlib import Path
    33	from typing import Any
    34	
    35	import pytest
    36	
    37	# Phase-2 deps required.
    38	pytest.importorskip("scipy")
    39	pytest.importorskip("numpy")
    40	pytest.importorskip("opentelemetry")
    41	
    42	from AgentEval._heatmap.models import CohortHeatmap  # noqa: E402
    43	from AgentEval._kernel.discovery import register_adapter  # noqa: E402
    44	from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
    45	from AgentEval.discoverability.schema import (  # noqa: E402
    46	    DiscoverabilityComparisonResult,
    47	    DiscoverabilityComparisonSummary,
    48	    DiscoverabilityResult,
    49	    DiscoverabilitySummary,
    50	    PairwiseAdapterDelta,
    51	    TaskResult,
    52	)
    53	from AgentEval.mcp.library import MCPLibrary  # noqa: E402
    54	from AgentEval.stats.types import MannWhitneyResult  # noqa: E402
    55	from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402
    56	
    57	# --------------------------------------------------------------------------- #
    58	# Stub adapter factory (reused from test_keyword.py pattern)                  #
    59	# --------------------------------------------------------------------------- #
    60	
    61	
    62	def _make_stub_adapter(tool_names_per_call: list[list[str]], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
    63	    class _StubAdapter(InProcessAdapter):
    64	        _call_idx = 0
    65	
    66	        def __init__(self, **kwargs: Any) -> None:
    67	            super().__init__()
    68	            self._kwargs = kwargs
    69	
    70	        def run(
    71	            self,
    72	            prompt: str,
    73	            tools: Any = None,
    74	            mcp_servers: Any = None,
    75	            **kwargs: Any,
    76	        ) -> AgentRunResult:
    77	            idx = type(self)._call_idx
    78	            type(self)._call_idx += 1
    79	            names = tool_names_per_call[idx] if idx < len(tool_names_per_call) else []
    80	            tool_calls = [
    81	                ToolCallTrace(
    82	                    name=name,
    83	                    args={},
    84	                    result=None,
    85	                    error=None,
    86	                    latency_ms=1.0,
    87	                    source="adapter",
    88	                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
    89	                    sequence_index=i,
    90	                )
    91	                for i, name in enumerate(names)
    92	            ]
    93	            return AgentRunResult(
    94	                response_text=f"stub-{idx}",
    95	                tool_calls=tool_calls,
    96	                usage=Usage(input_tokens=1, output_tokens=1),
    97	                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
    98	                cost_usd=cost_per_call,
    99	                latency_seconds=0.001,
   100	                trace_id=f"stub-id-{idx:032d}"[:32],
   101	            )
   102	
   103	    return _StubAdapter
   104	
   105	
   106	@pytest.fixture
   107	def lib() -> MCPLibrary:
   108	    return MCPLibrary()
   109	
   110	
   111	@pytest.fixture
   112	def fixture_path() -> Path:
   113	    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
   114	
   115	
   116	# --------------------------------------------------------------------------- #
   117	# Helper builders for dataclass validator tests                               #
   118	# --------------------------------------------------------------------------- #
   119	
   120	
   121	def _make_mwu(p_value: float = 0.5) -> MannWhitneyResult:
   122	    return MannWhitneyResult(u_statistic=10.0, p_value=p_value, effect_size_r=0.0, n_a=5, n_b=5)
   123	
   124	
   125	def _make_discoverability_result(pass_rate: float, n_tasks: int = 3) -> DiscoverabilityResult:
   126	    per_task = [
   127	        TaskResult(
   128	            task_id=f"t{i}",
   129	            task_prompt=f"prompt {i}",
   130	            trials_run=10,
   131	            success_count=int(pass_rate * 10),
   132	            tool_calls_per_trial=[],
   133	            competing_tools_picked=[],
   134	            cost_per_trial_usd=[],
   135	            wilson_ci_lower=0.0,
   136	            wilson_ci_upper=1.0,
   137	        )
   138	        for i in range(n_tasks)
   139	    ]
   140	    return DiscoverabilityResult(
   141	        per_task_results=per_task,
   142	        summary=DiscoverabilitySummary(overall_pass_rate=pass_rate, total_cost_usd=0.0, total_runtime_seconds=0.1),
   143	        mcp_coverage="hosted_in_process",
   144	    )
   145	
   146	
   147	# --------------------------------------------------------------------------- #
   148	# Dataclass validators (6 tests)                                              #
   149	# --------------------------------------------------------------------------- #
   150	
   151	
   152	def test_comparison_result_rejects_single_adapter() -> None:
   153	    """len(adapters) < 2 raises ValueError."""
   154	    per = {"a": _make_discoverability_result(1.0)}
   155	    heatmap = CohortHeatmap(tasks=("t0",), models=("a",), cells=(("t0", "a", 1.0),))
   156	    summary = DiscoverabilityComparisonSummary(
   157	        total_cost_usd=0.0,
   158	        total_runtime_seconds=0.0,
   159	        pass_rate_per_adapter={"a": 1.0},
   160	        best_adapter="a",
   161	        worst_adapter="a",
   162	    )
   163	    with pytest.raises(ValueError, match="len\\(adapters\\) >= 2"):
   164	        DiscoverabilityComparisonResult(
   165	            adapters=("a",),
   166	            per_adapter_results=per,
   167	            cross_adapter_deltas={},
   168	            heatmap=heatmap,
   169	            summary=summary,
   170	        )
   171	
   172	
   173	def test_comparison_result_rejects_adapters_keys_mismatch() -> None:
   174	    """adapters ↔ per_adapter_results key mismatch raises ValueError."""
   175	    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
   176	    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "b"), cells=())
   177	    summary = DiscoverabilityComparisonSummary(
   178	        total_cost_usd=0.0,
   179	        total_runtime_seconds=0.0,
   180	        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
   181	        best_adapter="a",
   182	        worst_adapter="b",
   183	    )
   184	    with pytest.raises(ValueError, match="per_adapter_results keys"):
   185	        DiscoverabilityComparisonResult(
   186	            adapters=("a", "c"),  # 'c' not in per
   187	            per_adapter_results=per,
   188	            cross_adapter_deltas={},
   189	            heatmap=heatmap,
   190	            summary=summary,
   191	        )
   192	
   193	
   194	def test_comparison_result_rejects_heatmap_models_mismatch() -> None:
   195	    """adapters ↔ heatmap.models mismatch raises ValueError."""
   196	    per = {"a": _make_discoverability_result(1.0), "b": _make_discoverability_result(0.5)}
   197	    heatmap = CohortHeatmap(tasks=("t0",), models=("a", "wrong"), cells=())
   198	    summary = DiscoverabilityComparisonSummary(
   199	        total_cost_usd=0.0,
   200	        total_runtime_seconds=0.0,
   201	        pass_rate_per_adapter={"a": 1.0, "b": 0.5},
   202	        best_adapter="a",
   203	        worst_adapter="b",
   204	    )
   205	    with pytest.raises(ValueError, match="heatmap.models"):
   206	        DiscoverabilityComparisonResult(
   207	            adapters=("a", "b"),
   208	            per_adapter_results=per,
   209	            cross_adapter_deltas={},
   210	            heatmap=heatmap,
   211	            summary=summary,
   212	        )
   213	
   214	
   215	def test_pairwise_delta_rejects_identical_adapters() -> None:
   216	    """adapter_a == adapter_b raises ValueError."""
   217	    with pytest.raises(ValueError, match="distinct adapters"):
   218	        PairwiseAdapterDelta(
   219	            adapter_a="a",
   220	            adapter_b="a",
   221	            pass_rate_delta=0.0,
   222	            mann_whitney_result=_make_mwu(),
   223	            significant_at_alpha_05=False,
   224	        )
   225	
   226	
   227	def test_pairwise_delta_rejects_out_of_range_delta() -> None:
   228	    """pass_rate_delta outside [-1, 1] raises ValueError."""
   229	    with pytest.raises(ValueError, match="pass_rate_delta"):
   230	        PairwiseAdapterDelta(
   231	            adapter_a="a",
   232	            adapter_b="b",
   233	            pass_rate_delta=1.5,
   234	            mann_whitney_result=_make_mwu(),
   235	            significant_at_alpha_05=False,
   236	        )
   237	
   238	
   239	def test_pairwise_delta_rejects_significance_inconsistency() -> None:
   240	    """significant_at_alpha_05 vs p_value inconsistency raises ValueError."""
   241	    with pytest.raises(ValueError, match="significant_at_alpha_05"):
   242	        PairwiseAdapterDelta(
   243	            adapter_a="a",
   244	            adapter_b="b",
   245	            pass_rate_delta=0.0,
   246	            mann_whitney_result=_make_mwu(p_value=0.5),  # > 0.05
   247	            significant_at_alpha_05=True,  # but claims significant
   248	        )
   249	
   250	
   251	def test_comparison_summary_rejects_unknown_best_adapter() -> None:
   252	    """best_adapter not in pass_rate_per_adapter raises ValueError."""
   253	    with pytest.raises(ValueError, match="best_adapter"):
   254	        DiscoverabilityComparisonSummary(
   255	            total_cost_usd=0.0,
   256	            total_runtime_seconds=0.0,
   257	            pass_rate_per_adapter={"a": 0.5},
   258	            best_adapter="unknown",
   259	            worst_adapter="a",
   260	        )

---
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""ImportError-gate tests for `MCP.Compare Tool Discoverability` (Story 13.3 L-2 lesson).
    16	
    17	Mirrors `tests/unit/stats/test_advanced_extras_gate.py` (Story 13.1) +
    18	`tests/unit/telemetry/test_backends_otlp_extras_gate.py` (Story 13.2)
    19	discipline: NO module-top `pytest.importorskip` so these tests run in
    20	BOTH the WITH-extras and WITHOUT-extras CI environments.
    21	
    22	Per AC-13.3.4 + Story 13.1 L-2 lesson: the WITHOUT-extras CI matrix
    23	MUST verify (a) the comparison schema module imports without scipy;
    24	(b) the keyword raises the spec-mandated ImportError when invoked
    25	without scipy/numpy; (c) the ImportError message contains the verbatim
    26	`uv pip install robotframework-agenteval[agenteval-advanced]` install
    27	hint.
    28	"""
    29	
    30	from __future__ import annotations
    31	
    32	from pathlib import Path
    33	
    34	import pytest
    35	
    36	
    37	def test_comparison_schema_importable_without_extra() -> None:
    38	    """`from AgentEval.discoverability.schema import DiscoverabilityComparisonResult` succeeds without `[agenteval-advanced]`.
    39	
    40	    The dataclasses reference `MannWhitneyResult` via `TYPE_CHECKING`
    41	    only — no runtime scipy import at module load time.
    42	    """
    43	    from AgentEval.discoverability.schema import (  # noqa: F401
    44	        DiscoverabilityComparisonResult,
    45	        DiscoverabilityComparisonSummary,
    46	        PairwiseAdapterDelta,
    47	    )
    48	
    49	
    50	def test_compare_keyword_raises_import_error_when_advanced_extra_missing(
    51	    monkeypatch: pytest.MonkeyPatch,
    52	) -> None:
    53	    """`MCP.Compare Tool Discoverability` raises ImportError when `_ADVANCED_AVAILABLE=False`.
    54	
    55	    Monkeypatches the Story 13.1 module-level gate directly (vs reloading
    56	    the module with scipy stubbed out) per Story 13.1 review HIGH-B lesson.
    57	    The gate check sits BEFORE the per-adapter fan-out (D-6 fail-fast)
    58	    so operators discovering the missing extra do not pay any trial cost.
    59	    """
    60	    pytest.importorskip("opentelemetry")  # MCPLibrary infrastructure dep.
    61	
    62	    from AgentEval.mcp.library import MCPLibrary
    63	    from AgentEval.stats import library as stats_lib
    64	
    65	    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    66	
    67	    lib = MCPLibrary()
    68	    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    69	    with pytest.raises(ImportError, match="agenteval-advanced"):
    70	        lib.get_tool_discoverability_comparison(
    71	            mcp_server="echo",
    72	            adapters=["any_a", "any_b"],
    73	            tasks=str(fixture_path),
    74	            trials_per_task=1,
    75	        )
    76	
    77	
    78	def test_compare_keyword_import_error_message_contract() -> None:
    79	    """The ImportError message contains the verbatim install hint.
    80	
    81	    Per Story 13.2 D-3 + AC-13.3.4 in-flight decision (b): the MCP
    82	    keyword raises directly (not via the Stats helper) so the message
    83	    is `MCP.Compare Tool Discoverability:`-prefixed (NOT `Stat.`).
    84	    """
    85	    pytest.importorskip("opentelemetry")
    86	
    87	    from unittest.mock import patch
    88	
    89	    from AgentEval.mcp.library import MCPLibrary
    90	    from AgentEval.stats import library as stats_lib
    91	
    92	    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    93	    lib = MCPLibrary()
    94	
    95	    with patch.object(stats_lib, "_ADVANCED_AVAILABLE", False), pytest.raises(ImportError) as exc_info:
    96	        lib.get_tool_discoverability_comparison(
    97	            mcp_server="echo",
    98	            adapters=["a", "b"],
    99	            tasks=str(fixture_path),
   100	            trials_per_task=1,
   101	        )
   102	    msg = str(exc_info.value)
   103	    assert "MCP.Compare Tool Discoverability" in msg
   104	    assert "scipy + numpy required" in msg
   105	    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg
   106	
   107	
   108	def test_compare_keyword_arg_validation_runs_before_extras_gate(
   109	    monkeypatch: pytest.MonkeyPatch,
   110	) -> None:
   111	    """Arg validation (mcp_server / adapters / tasks) runs BEFORE the extras gate.
   112	
   113	    Rationale: a user with a missing extra AND missing args should see
   114	    the arg error first (more actionable). Empty `mcp_server` → ValueError
   115	    even when `_ADVANCED_AVAILABLE=False`.
   116	    """
   117	    pytest.importorskip("opentelemetry")
   118	
   119	    from AgentEval.mcp.library import MCPLibrary
   120	    from AgentEval.stats import library as stats_lib
   121	
   122	    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
   123	    lib = MCPLibrary()
   124	    with pytest.raises(ValueError, match="mcp_server"):
   125	        lib.get_tool_discoverability_comparison(
   126	            mcp_server="",  # empty — arg validation should fire first.
   127	            adapters=["a", "b"],
   128	            tasks="some.yaml",
   129	            trials_per_task=1,
   130	        )

---
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""End-to-end integration test for `MCP.Compare Tool Discoverability` (Story 13.3 AC-13.3.8).
    16	
    17	Per Story 13.1 L-4 lesson (empirical correctness verification): asserts
    18	CONCRETE numerical outcomes of the cross-adapter comparison — known
    19	stub pass-rate distributions produce the EXPECTED ranking + p-value
    20	signs, NOT just "the keyword ran without error."
    21	
    22	3 stubs via `register_adapter()` (mirrors Story 12.3 + Story 7.3
    23	canonical pattern):
    24	- `compare_stub_a` → 100% success on all tasks/trials.
    25	- `compare_stub_b` → 50% success (alternating per call).
    26	- `compare_stub_c` → 0% success.
    27	
    28	Expected outcomes:
    29	- per-adapter pass rates: a=1.0, b=0.5, c=0.0.
    30	- summary.best_adapter == "compare_stub_a"; worst_adapter == "compare_stub_c".
    31	- 3 pairwise deltas keyed by f"{a}_vs_{b}".
    32	- a-vs-c delta: p_value < 0.05 (significant).
    33	- heatmap.models has 3 columns + heatmap.tasks matches the YAML task count.
    34	"""
    35	
    36	from __future__ import annotations
    37	
    38	from collections.abc import Iterator
    39	from pathlib import Path
    40	from typing import Any
    41	
    42	import pytest
    43	
    44	# Phase-2 deps required.
    45	pytest.importorskip("scipy")
    46	pytest.importorskip("numpy")
    47	pytest.importorskip("opentelemetry")
    48	
    49	from AgentEval._kernel import discovery  # noqa: E402
    50	from AgentEval._kernel.discovery import register_adapter  # noqa: E402
    51	from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
    52	from AgentEval.discoverability.schema import DiscoverabilityComparisonResult  # noqa: E402
    53	from AgentEval.mcp.library import MCPLibrary  # noqa: E402
    54	from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402
    55	
    56	
    57	@pytest.fixture(autouse=True)
    58	def _restore_adapter_registry() -> Iterator[None]:
    59	    """Snapshot + restore the programmatic adapter registry per test."""
    60	    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    61	    try:
    62	        yield
    63	    finally:
    64	        discovery._registered_adapters.clear()  # noqa: SLF001
    65	        discovery._registered_adapters.update(snapshot)  # noqa: SLF001
    66	
    67	
    68	def _make_stub_adapter(success_pattern: list[bool], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
    69	    """Build a stub adapter that emits `echo_back` on success, no tools on fail."""
    70	
    71	    class _Stub(InProcessAdapter):
    72	        _call_idx = 0
    73	
    74	        def __init__(self, **kwargs: Any) -> None:
    75	            super().__init__()
    76	
    77	        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
    78	            idx = type(self)._call_idx
    79	            type(self)._call_idx += 1
    80	            success = success_pattern[idx % len(success_pattern)] if success_pattern else False
    81	            names = ["echo_back"] if success else []
    82	            tool_calls = [
    83	                ToolCallTrace(
    84	                    name=n,
    85	                    args={},
    86	                    result=None,
    87	                    error=None,
    88	                    latency_ms=1.0,
    89	                    source="adapter",
    90	                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
    91	                    sequence_index=i,
    92	                )
    93	                for i, n in enumerate(names)
    94	            ]
    95	            return AgentRunResult(
    96	                response_text=f"stub-{idx}",
    97	                tool_calls=tool_calls,
    98	                usage=Usage(input_tokens=1, output_tokens=1),
    99	                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
   100	                cost_usd=cost_per_call,
   101	                latency_seconds=0.001,
   102	                trace_id=f"stub-id-{idx:032d}"[:32],
   103	            )
   104	
   105	    return _Stub
   106	
   107	
   108	def test_compare_3_stub_adapters_end_to_end(tmp_path: Path) -> None:
   109	    """3-stub cross-adapter comparison produces expected ranking + significant a-vs-c delta."""
   110	    # Register 3 stubs with deterministic + KNOWN-different pass rates.
   111	    # Pass pattern length-1 → constant across all calls.
   112	    register_adapter("compare_stub_a", _make_stub_adapter([True]))  # 100%
   113	    register_adapter("compare_stub_b", _make_stub_adapter([True, False]))  # 50%
   114	    register_adapter("compare_stub_c", _make_stub_adapter([False]))  # 0%
   115	
   116	    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
   117	
   118	    lib = MCPLibrary()
   119	    result = lib.get_tool_discoverability_comparison(
   120	        mcp_server="echo",
   121	        adapters=["compare_stub_a", "compare_stub_b", "compare_stub_c"],
   122	        tasks=str(fixture_path),
   123	        trials_per_task=10,  # enough for Mann-Whitney to have power.
   124	        model=None,
   125	    )
   126	
   127	    assert isinstance(result, DiscoverabilityComparisonResult)
   128	
   129	    # Per-adapter overall pass rates.
   130	    a_rate = result.per_adapter_results["compare_stub_a"].summary.overall_pass_rate
   131	    b_rate = result.per_adapter_results["compare_stub_b"].summary.overall_pass_rate
   132	    c_rate = result.per_adapter_results["compare_stub_c"].summary.overall_pass_rate
   133	    assert a_rate == pytest.approx(1.0)
   134	    assert b_rate == pytest.approx(0.5)
   135	    assert c_rate == pytest.approx(0.0)
   136	
   137	    # Summary ranking.
   138	    assert result.summary.best_adapter == "compare_stub_a"
   139	    assert result.summary.worst_adapter == "compare_stub_c"
   140	
   141	    # All 3 pairwise deltas present + correctly keyed.
   142	    assert set(result.cross_adapter_deltas.keys()) == {
   143	        "compare_stub_a_vs_compare_stub_b",
   144	        "compare_stub_a_vs_compare_stub_c",
   145	        "compare_stub_b_vs_compare_stub_c",
   146	    }
   147	
   148	    # a-vs-c delta: max-effect (a always-pass vs c always-fail) → p < 0.05.
   149	    ac_delta = result.cross_adapter_deltas["compare_stub_a_vs_compare_stub_c"]
   150	    assert ac_delta.pass_rate_delta == pytest.approx(1.0)
   151	    assert ac_delta.significant_at_alpha_05
   152	
   153	    # Heatmap: 3 columns, M rows (M = task count from YAML).
   154	    assert result.heatmap.models == ("compare_stub_a", "compare_stub_b", "compare_stub_c")
   155	    assert len(result.heatmap.tasks) >= 1  # at least 1 task from the YAML.
   156	
   157	    # Cost: 3 adapters × M tasks × 10 trials × 0.001 each.
   158	    expected_cost = 3 * len(result.heatmap.tasks) * 10 * 0.001
   159	    assert result.summary.total_cost_usd == pytest.approx(expected_cost)
   160	
   161	
   162	def test_compare_rejects_single_adapter_list_at_arg_validation(tmp_path: Path) -> None:
   163	    """≥2 adapter requirement enforced at arg validation."""
   164	    register_adapter("only_one", _make_stub_adapter([True]))
   165	    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
   166	    lib = MCPLibrary()
   167	    with pytest.raises(ValueError, match=">= 2 entries"):
   168	        lib.get_tool_discoverability_comparison(
   169	            mcp_server="echo",
   170	            adapters=["only_one"],
   171	            tasks=str(fixture_path),
   172	            trials_per_task=1,
   173	        )
   174	
   175	
   176	def test_compare_rejects_duplicate_adapter_names(tmp_path: Path) -> None:
   177	    """Duplicate adapter names in `adapters` list raise ValueError."""
   178	    register_adapter("dup_a", _make_stub_adapter([True]))
   179	    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
   180	    lib = MCPLibrary()
   181	    with pytest.raises(ValueError, match="distinct adapter names"):
   182	        lib.get_tool_discoverability_comparison(
   183	            mcp_server="echo",
   184	            adapters=["dup_a", "dup_a"],
   185	            tasks=str(fixture_path),
   186	            trials_per_task=1,
   187	        )

exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
import ast
p = Path('tests/unit/discoverability/test_comparison.py')
text = p.read_text()
print('unit file test defs', sum(1 for line in text.splitlines() if line.startswith('def test_')))
p2 = Path('tests/unit/discoverability/test_comparison_extras_gate.py')
print('gate file test defs', sum(1 for line in p2.read_text().splitlines() if line.startswith('def test_')))
p3 = Path('tests/integration/discoverability/test_compare_e2e.py')
print('integration file test defs', sum(1 for line in p3.read_text().splitlines() if line.startswith('def test_')))
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
unit file test defs 16
gate file test defs 4
integration file test defs 3

exec
/bin/bash -lc "uv run python - <<'PY'
from pathlib import Path
from AgentEval.mcp.library import MCPLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunResult, AgentRunMetadata, ToolCallTrace, Usage

fixture = Path('tests/fixtures/discoverability/tasks-basic.yaml')

def mk(pattern):
    class A(InProcessAdapter):
        _i=0
        def run(self, prompt, **kwargs):
            i=type(self)._i; type(self)._i += 1
            names = pattern[i] if i < len(pattern) else []
            tc=[ToolCallTrace(name=n,args={},result=None,error=None,latency_ms=1.0,source='adapter',gen_ai_tool_call_id=f'{i}',sequence_index=j) for j,n in enumerate(names)]
            return AgentRunResult(response_text='x', tool_calls=tc, usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='0'*32)
    return A

register_adapter('nan_a', mk([['echo_back']]*30))
register_adapter('nan_b', mk([['echo_back']]*30))
lib = MCPLibrary()
r = lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['nan_a','nan_b'], tasks=str(fixture), trials_per_task=5)
d = r.cross_adapter_deltas['nan_a_vs_nan_b']
print('p_value', d.mann_whitney_result.p_value)
print('significant', d.significant_at_alpha_05)
print('delta', d.pass_rate_delta)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 2954ms:
p_value nan
significant False
delta 0.0

exec
/bin/bash -lc "nl -ba src/AgentEval/mcp/library.py | sed -n '760,790p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   760	
   761	        # Track end-to-end runtime (caller-side; not stored separately
   762	        # but contributes to the per-adapter timers we MAX'd above).
   763	        _ = t_start
   764	
   765	        return DiscoverabilityComparisonResult(
   766	            adapters=tuple(adapters),
   767	            per_adapter_results=per_adapter_results,
   768	            cross_adapter_deltas=cross_adapter_deltas,
   769	            heatmap=heatmap,
   770	            summary=summary,
   771	        )

exec
/bin/bash -lc "find tests -path '*discoverability*' -maxdepth 3 -type f | sort" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
tests/dogfood/agentskills/parity-checklist-agentskills-discoverability.md
tests/dogfood/agentskills/test_skill_discoverability.robot
tests/fixtures/discoverability/skill-tasks-basic.yaml
tests/fixtures/discoverability/tasks-basic.yaml
tests/integration/discoverability/__init__.py
tests/integration/discoverability/test_compare_e2e.py
tests/unit/discoverability/__init__.py
tests/unit/discoverability/conftest.py
tests/unit/discoverability/test_comparison.py
tests/unit/discoverability/test_comparison_extras_gate.py
tests/unit/discoverability/test_keyword.py
tests/unit/discoverability/test_loader.py
tests/unit/discoverability/test_wilson_ci.py
tests/unit/skills/test_discoverability.py

codex
I’ve got one concrete product defect already: the comparison runtime is underreported by roughly 7x because the helper timer is restarted per adapter, then summarized with `max()`. I’m checking the public dataclass invariants next, because the story explicitly promised validation there and the current code looks only partially enforced.
exec
/bin/bash -lc "grep -n \"50+\\|1874 passed\\|22 new tests\\|16 unit \\+ 4 gate \\+ 3 integration\\|50\\+ existing\" -n _bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
205:Mirrors the existing `MCPLibrary.get_tool_discoverability` body but factored for shared use. Existing `get_tool_discoverability` is refactored to call the helper after its own arg validation + YAML load. **No behavior change** for single-adapter callers (verify via the existing 50+ Story 4.4 tests passing unchanged).
259:Per AC-13.3.6 the existing `get_tool_discoverability` is refactored to call `_run_single_adapter_discoverability`. ALL Story 4.4's existing tests (50+ unit + 8 integration per `tests/unit/discoverability/` + `tests/integration/discoverability/`) MUST pass unchanged — proves the refactor is behavior-preserving. Test count delta = +18 new (per AC-13.3.7 + AC-13.3.8), no test renames or removals.
302:- [x] **Task 4: `src/AgentEval/discoverability/_internal.py` (AC-13.3.6, NEW)** — `run_single_adapter_discoverability` helper extracted from existing Story 4.4 body; behavior identity verified by Story 4.4's 50+ existing tests passing unchanged.
309:- [x] **Task 11: All-gates pass** (AC-13.3.13) — `uv run pytest tests/` reports **1874 passed + 16 skipped + 0 failed** (+28 net vs 1846 + 16 Story 13.2 baseline). 22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration; the +28 includes a couple of side-fix tests). ruff/format/mypy/license clean. libdoc `docs/keywords/MCPLibrary.html` regenerated with `MCP.Compare Tool Discoverability` keyword.
315:- **Story 4.4** shipped `MCP.Get Tool Discoverability` + `DiscoverabilityResult` + `TaskResult` + `DiscoverabilitySummary` + 50+ unit tests + 8 integration tests + the loader/schema infrastructure. Story 13.3 builds the N-adapter wrapper.
325:- Preserves the existing 50+ Story 4.4 tests unchanged (they call the keyword surface, which delegates to the helper).
373:- **AC-13.3.6**: `run_single_adapter_discoverability` helper extracted to `_internal.py`; existing `get_tool_discoverability` delegates to it. Story 4.4's 50+ existing tests pass unchanged.

exec
/bin/bash -lc "grep -n \"class DiscoverabilityComparisonSummary\\|class DiscoverabilityComparisonResult\\|summary:\" -n src/AgentEval/discoverability/schema.py" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
144:        - `summary: DiscoverabilitySummary` (overall pass rate, total cost,
151:    summary: DiscoverabilitySummary
216:class DiscoverabilityComparisonSummary:
252:class DiscoverabilityComparisonResult:
266:        - `summary: DiscoverabilityComparisonSummary` — aggregate roll-up.
278:    summary: DiscoverabilityComparisonSummary

exec
/bin/bash -lc "uv run python - <<'PY'
from AgentEval.discoverability.schema import DiscoverabilityComparisonSummary, DiscoverabilityComparisonResult, DiscoverabilityResult, DiscoverabilitySummary, TaskResult
from AgentEval._heatmap.models import CohortHeatmap

per = {
  'a': DiscoverabilityResult(per_task_results=[TaskResult(task_id='t1', task_prompt='p', trials_run=1, success_count=1, tool_calls_per_trial=[], competing_tools_picked=[], cost_per_trial_usd=[], wilson_ci_lower=0, wilson_ci_upper=1)], summary=DiscoverabilitySummary(overall_pass_rate=1.0, total_cost_usd=0.0, total_runtime_seconds=0.1), mcp_coverage='hosted_in_process'),
  'b': DiscoverabilityResult(per_task_results=[TaskResult(task_id='t1', task_prompt='p', trials_run=1, success_count=0, tool_calls_per_trial=[], competing_tools_picked=[], cost_per_trial_usd=[], wilson_ci_lower=0, wilson_ci_upper=1)], summary=DiscoverabilitySummary(overall_pass_rate=0.0, total_cost_usd=0.0, total_runtime_seconds=0.1), mcp_coverage='hosted_in_process'),
}
heatmap=CohortHeatmap(tasks=('t1',), models=('a','b'), cells=(('t1','a',1.0),('t1','b',0.0)))
# Inverted best/worst still accepted?
summary = DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'a':1.0,'b':0.0}, best_adapter='b', worst_adapter='a')
print('summary accepted', summary)
# Summary keys mismatching adapters still accepted inside top-level result?
summary2 = DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'x':1.0}, best_adapter='x', worst_adapter='x')
result = DiscoverabilityComparisonResult(adapters=('a','b'), per_adapter_results=per, cross_adapter_deltas={}, heatmap=heatmap, summary=summary2)
print('result accepted summary keys mismatch', result.summary)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 431ms:
summary accepted DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'a': 1.0, 'b': 0.0}, best_adapter='b', worst_adapter='a')
result accepted summary keys mismatch DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'x': 1.0}, best_adapter='x', worst_adapter='x')

codex
The dataclass contract is weaker than the story says: malformed summaries are accepted right now, including inverted `best_adapter`/`worst_adapter` and summary key sets that don’t match `adapters`. I’m checking whether there’s another product-level gap around empty task sets or comparison construction before I write up the findings.
exec
/bin/bash -lc "nl -ba src/AgentEval/discoverability/loader.py | sed -n '1,220p'; printf '\\n---\\n'; grep -RIn \"tasks-basic.yaml\\|InvalidDiscoverabilityTasksError\\|expected_tools\" tests/fixtures/discoverability src/AgentEval/discoverability tests/unit/discoverability" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Discoverability tasks YAML loader (Story 4.4 / PRD FR10a).
    16	
    17	Reads + validates a tasks YAML file; returns `list[DiscoverabilityTask]`
    18	or raises `InvalidDiscoverabilityTasksError` with an RFC 6901 JSON
    19	Pointer `field_name` per the Tier-1 setup-failure convention (parallel
    20	to Story 4.3's `scenarios/loader.py`).
    21	"""
    22	
    23	from __future__ import annotations
    24	
    25	from pathlib import Path
    26	from typing import Any
    27	
    28	import yaml
    29	
    30	from AgentEval.discoverability.schema import DiscoverabilityTask
    31	from AgentEval.errors import InvalidDiscoverabilityTasksError
    32	
    33	__all__ = ["load_discoverability_tasks"]
    34	
    35	
    36	def load_discoverability_tasks(path: str | Path) -> list[DiscoverabilityTask]:
    37	    """Load + validate a discoverability tasks YAML file.
    38	
    39	    Raises:
    40	        InvalidDiscoverabilityTasksError: on any structural failure
    41	            (file missing, wrong extension, malformed YAML, schema
    42	            violation). `field_name` carries an RFC 6901 JSON Pointer.
    43	    """
    44	    p = Path(path)
    45	    if not p.exists():
    46	        raise InvalidDiscoverabilityTasksError(
    47	            f"discoverability tasks YAML file not found: {p}",
    48	            file_path=str(p),
    49	            field_name="",
    50	            fix_suggestion="Verify the path exists and is readable.",
    51	        )
    52	    if p.suffix.lower() not in (".yaml", ".yml"):
    53	        raise InvalidDiscoverabilityTasksError(
    54	            f"discoverability tasks file must have .yaml or .yml extension; got {p.suffix!r}",
    55	            file_path=str(p),
    56	            field_name="",
    57	            fix_suggestion="Rename the file to use .yaml or .yml extension.",
    58	        )
    59	
    60	    try:
    61	        raw_text = p.read_text(encoding="utf-8")
    62	    except OSError as exc:
    63	        raise InvalidDiscoverabilityTasksError(
    64	            f"failed to read discoverability tasks YAML: {exc}",
    65	            file_path=str(p),
    66	            field_name="",
    67	            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
    68	        ) from exc
    69	    except UnicodeDecodeError as exc:
    70	        raise InvalidDiscoverabilityTasksError(
    71	            f"discoverability tasks YAML is not valid UTF-8: {exc}",
    72	            file_path=str(p),
    73	            field_name="",
    74	            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
    75	        ) from exc
    76	
    77	    try:
    78	        parsed: Any = yaml.safe_load(raw_text)
    79	    except yaml.YAMLError as exc:
    80	        line = getattr(getattr(exc, "problem_mark", None), "line", None)
    81	        raise InvalidDiscoverabilityTasksError(
    82	            f"malformed YAML: {exc}",
    83	            file_path=str(p),
    84	            line_number=line + 1 if line is not None else None,
    85	            field_name="",
    86	            fix_suggestion="Validate the YAML with `python -c 'import yaml; yaml.safe_load(open(...))'`.",
    87	        ) from exc
    88	
    89	    if not isinstance(parsed, dict):
    90	        raise InvalidDiscoverabilityTasksError(
    91	            f"discoverability tasks YAML top-level must be a mapping; got {type(parsed).__name__}",
    92	            file_path=str(p),
    93	            field_name="",
    94	            fix_suggestion="Wrap the content in a top-level YAML mapping with a `tasks:` key.",
    95	        )
    96	
    97	    if "tasks" not in parsed:
    98	        raise InvalidDiscoverabilityTasksError(
    99	            "discoverability tasks YAML missing required `tasks` field",
   100	            file_path=str(p),
   101	            field_name="/tasks",
   102	            fix_suggestion="Add a top-level `tasks:` list of task entries.",
   103	        )
   104	    tasks_raw = parsed["tasks"]
   105	    if not isinstance(tasks_raw, list):
   106	        raise InvalidDiscoverabilityTasksError(
   107	            f"`tasks` must be a list; got {type(tasks_raw).__name__}",
   108	            file_path=str(p),
   109	            field_name="/tasks",
   110	            fix_suggestion="Format as a YAML list of task entries.",
   111	        )
   112	    if not tasks_raw:
   113	        raise InvalidDiscoverabilityTasksError(
   114	            "discoverability tasks YAML `tasks` list is empty; at least one task is required",
   115	            file_path=str(p),
   116	            field_name="/tasks",
   117	            fix_suggestion="Add at least one task entry with `id:` + `prompt:` fields.",
   118	        )
   119	
   120	    out: list[DiscoverabilityTask] = []
   121	    seen_ids: dict[str, int] = {}
   122	    for idx, entry in enumerate(tasks_raw):
   123	        task = _parse_task(entry, idx=idx, file_path=str(p))
   124	        # Story 4.4 code-review 3-way HIGH-A fix 2026-05-20 (Edge-cases H1 +
   125	        # Codex HIGH + Blind MED-1): pre-edit loader accepted duplicate task
   126	        # ids silently — two `TaskResult.task_id` rows with the same id would
   127	        # collide downstream in the AC-DISCOVER-01 verdict matrix / CSV export.
   128	        # Reject the second occurrence with the first occurrence's index in
   129	        # the fix suggestion so users can locate both copies.
   130	        if task.id in seen_ids:
   131	            prior_idx = seen_ids[task.id]
   132	            raise InvalidDiscoverabilityTasksError(
   133	                f"`tasks[{idx}].id` duplicates `tasks[{prior_idx}].id` "
   134	                f"(both = {task.id!r}); task ids must be unique per the "
   135	                f"AC-DISCOVER-01 verdict-matrix key contract",
   136	                file_path=str(p),
   137	                field_name=f"/tasks/{idx}/id",
   138	                fix_suggestion=(f"Rename `tasks[{idx}].id` to a value distinct from `tasks[{prior_idx}].id`."),
   139	            )
   140	        seen_ids[task.id] = idx
   141	        out.append(task)
   142	    return out
   143	
   144	
   145	def _parse_task(entry: Any, *, idx: int, file_path: str) -> DiscoverabilityTask:
   146	    """Validate one `tasks[<idx>]` entry."""
   147	    if not isinstance(entry, dict):
   148	        raise InvalidDiscoverabilityTasksError(
   149	            f"`tasks[{idx}]` must be a mapping; got {type(entry).__name__}",
   150	            file_path=file_path,
   151	            field_name=f"/tasks/{idx}",
   152	            fix_suggestion="Format each task as a YAML mapping with `id:` + `prompt:` fields.",
   153	        )
   154	    if "id" not in entry:
   155	        raise InvalidDiscoverabilityTasksError(
   156	            f"`tasks[{idx}]` missing required `id` field",
   157	            file_path=file_path,
   158	            field_name=f"/tasks/{idx}/id",
   159	            fix_suggestion="Add an `id:` key with a unique task identifier.",
   160	        )
   161	    task_id = entry["id"]
   162	    if not isinstance(task_id, str) or not task_id.strip():
   163	        raise InvalidDiscoverabilityTasksError(
   164	            f"`tasks[{idx}].id` must be a non-empty string; got {task_id!r}",
   165	            file_path=file_path,
   166	            field_name=f"/tasks/{idx}/id",
   167	            fix_suggestion="Use a non-empty string task identifier.",
   168	        )
   169	    if "prompt" not in entry:
   170	        raise InvalidDiscoverabilityTasksError(
   171	            f"`tasks[{idx}]` missing required `prompt` field",
   172	            file_path=file_path,
   173	            field_name=f"/tasks/{idx}/prompt",
   174	            fix_suggestion="Add a `prompt:` key with the natural-language task text.",
   175	        )
   176	    prompt = entry["prompt"]
   177	    if not isinstance(prompt, str):
   178	        raise InvalidDiscoverabilityTasksError(
   179	            f"`tasks[{idx}].prompt` must be a string; got {type(prompt).__name__}",
   180	            file_path=file_path,
   181	            field_name=f"/tasks/{idx}/prompt",
   182	            fix_suggestion="Use a string prompt.",
   183	        )
   184	    if not prompt.strip():
   185	        raise InvalidDiscoverabilityTasksError(
   186	            f"`tasks[{idx}].prompt` must be non-empty; got {prompt!r}",
   187	            file_path=file_path,
   188	            field_name=f"/tasks/{idx}/prompt",
   189	            fix_suggestion="Provide the prompt text; empty prompts are rejected.",
   190	        )
   191	    expected_tools_raw = entry.get("expected_tools")
   192	    if expected_tools_raw is None:
   193	        expected_tools: list[str] = []
   194	    else:
   195	        if not isinstance(expected_tools_raw, list):
   196	            raise InvalidDiscoverabilityTasksError(
   197	                f"`tasks[{idx}].expected_tools` must be a list of strings; got {type(expected_tools_raw).__name__}",
   198	                file_path=file_path,
   199	                field_name=f"/tasks/{idx}/expected_tools",
   200	                fix_suggestion="Format `expected_tools` as a YAML list of tool names.",
   201	            )
   202	        for jdx, name in enumerate(expected_tools_raw):
   203	            if not isinstance(name, str):
   204	                raise InvalidDiscoverabilityTasksError(
   205	                    f"`tasks[{idx}].expected_tools[{jdx}]` must be a string; got {type(name).__name__}",
   206	                    file_path=file_path,
   207	                    field_name=f"/tasks/{idx}/expected_tools/{jdx}",
   208	                    fix_suggestion="Use string tool names.",
   209	                )
   210	        expected_tools = list(expected_tools_raw)
   211	    required_raw = entry.get("required", True)
   212	    if not isinstance(required_raw, bool):
   213	        raise InvalidDiscoverabilityTasksError(
   214	            f"`tasks[{idx}].required` must be a bool; got {type(required_raw).__name__}",
   215	            file_path=file_path,
   216	            field_name=f"/tasks/{idx}/required",
   217	            fix_suggestion="Use true or false.",
   218	        )
   219	    return DiscoverabilityTask(
   220	        id=task_id,

---
tests/fixtures/discoverability/tasks-basic.yaml:14:#     expected_tools: optional list[str]; successful trial = any of
tests/fixtures/discoverability/tasks-basic.yaml:22:    expected_tools:
tests/fixtures/discoverability/tasks-basic.yaml:27:    expected_tools:
tests/fixtures/discoverability/tasks-basic.yaml:32:    expected_tools:
src/AgentEval/discoverability/loader.py:18:or raises `InvalidDiscoverabilityTasksError` with an RFC 6901 JSON
src/AgentEval/discoverability/loader.py:31:from AgentEval.errors import InvalidDiscoverabilityTasksError
src/AgentEval/discoverability/loader.py:40:        InvalidDiscoverabilityTasksError: on any structural failure
src/AgentEval/discoverability/loader.py:46:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:53:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:63:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:70:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:81:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:90:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:98:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:106:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:113:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:132:            raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:148:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:155:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:163:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:170:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:178:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:185:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:191:    expected_tools_raw = entry.get("expected_tools")
src/AgentEval/discoverability/loader.py:192:    if expected_tools_raw is None:
src/AgentEval/discoverability/loader.py:193:        expected_tools: list[str] = []
src/AgentEval/discoverability/loader.py:195:        if not isinstance(expected_tools_raw, list):
src/AgentEval/discoverability/loader.py:196:            raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:197:                f"`tasks[{idx}].expected_tools` must be a list of strings; got {type(expected_tools_raw).__name__}",
src/AgentEval/discoverability/loader.py:199:                field_name=f"/tasks/{idx}/expected_tools",
src/AgentEval/discoverability/loader.py:200:                fix_suggestion="Format `expected_tools` as a YAML list of tool names.",
src/AgentEval/discoverability/loader.py:202:        for jdx, name in enumerate(expected_tools_raw):
src/AgentEval/discoverability/loader.py:204:                raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:205:                    f"`tasks[{idx}].expected_tools[{jdx}]` must be a string; got {type(name).__name__}",
src/AgentEval/discoverability/loader.py:207:                    field_name=f"/tasks/{idx}/expected_tools/{jdx}",
src/AgentEval/discoverability/loader.py:210:        expected_tools = list(expected_tools_raw)
src/AgentEval/discoverability/loader.py:213:        raise InvalidDiscoverabilityTasksError(
src/AgentEval/discoverability/loader.py:222:        expected_tools=expected_tools,
src/AgentEval/discoverability/_internal.py:129:            # Story 4.4 3-way MED-A: wildcard-success mode when expected_tools empty.
src/AgentEval/discoverability/_internal.py:130:            if task.expected_tools:
src/AgentEval/discoverability/_internal.py:131:                expected_set = set(task.expected_tools)
src/AgentEval/discoverability/schema.py:20:  `prompt`, optional `expected_tools`, optional `required` flag.
src/AgentEval/discoverability/schema.py:69:    expected_tools: list[str] = field(default_factory=list)
src/AgentEval/discoverability/schema.py:74:        object.__setattr__(self, "expected_tools", list(self.expected_tools))
src/AgentEval/discoverability/schema.py:86:          `expected_tools` (debugging discoverability = debugging vocabulary).
tests/unit/discoverability/test_loader.py:25:from AgentEval.errors import InvalidDiscoverabilityTasksError
tests/unit/discoverability/test_loader.py:40:    assert tasks[0].expected_tools == []
tests/unit/discoverability/test_loader.py:51:    expected_tools:
tests/unit/discoverability/test_loader.py:58:    assert tasks[0].expected_tools == ["search", "find"]
tests/unit/discoverability/test_loader.py:63:    with pytest.raises(InvalidDiscoverabilityTasksError, match="not found"):
tests/unit/discoverability/test_loader.py:70:    with pytest.raises(InvalidDiscoverabilityTasksError, match="extension"):
tests/unit/discoverability/test_loader.py:76:    with pytest.raises(InvalidDiscoverabilityTasksError, match="malformed YAML"):
tests/unit/discoverability/test_loader.py:83:    with pytest.raises(InvalidDiscoverabilityTasksError, match="UTF-8"):
tests/unit/discoverability/test_loader.py:89:    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a mapping"):
tests/unit/discoverability/test_loader.py:95:    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
tests/unit/discoverability/test_loader.py:102:    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a list"):
tests/unit/discoverability/test_loader.py:108:    with pytest.raises(InvalidDiscoverabilityTasksError, match="empty"):
tests/unit/discoverability/test_loader.py:114:    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
tests/unit/discoverability/test_loader.py:121:    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty"):
tests/unit/discoverability/test_loader.py:127:    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
tests/unit/discoverability/test_loader.py:134:    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty"):
tests/unit/discoverability/test_loader.py:140:    with pytest.raises(InvalidDiscoverabilityTasksError, match="non-empty string"):
tests/unit/discoverability/test_loader.py:144:def test_load_task_expected_tools_not_list(tmp_path: Path) -> None:
tests/unit/discoverability/test_loader.py:145:    p = _write(tmp_path, "tasks:\n  - id: t\n    prompt: hi\n    expected_tools: search\n")
tests/unit/discoverability/test_loader.py:146:    with pytest.raises(InvalidDiscoverabilityTasksError, match="list of strings"):
tests/unit/discoverability/test_loader.py:150:def test_load_task_expected_tools_non_string_element(tmp_path: Path) -> None:
tests/unit/discoverability/test_loader.py:151:    p = _write(tmp_path, "tasks:\n  - id: t\n    prompt: hi\n    expected_tools:\n      - 42\n")
tests/unit/discoverability/test_loader.py:152:    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a string"):
tests/unit/discoverability/test_loader.py:158:    with pytest.raises(InvalidDiscoverabilityTasksError, match="must be a bool"):
tests/unit/discoverability/test_loader.py:173:    with pytest.raises(InvalidDiscoverabilityTasksError) as exc_info:
tests/unit/discoverability/test_loader.py:184:    p = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
tests/unit/discoverability/test_keyword.py:32:from AgentEval.errors import InvalidDiscoverabilityTasksError
tests/unit/discoverability/test_keyword.py:150:    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
tests/unit/discoverability/test_keyword.py:198:    """When the model picks a tool NOT in expected_tools, it's tracked."""
tests/unit/discoverability/test_keyword.py:280:    with pytest.raises(InvalidDiscoverabilityTasksError):
tests/unit/discoverability/test_keyword.py:365:def test_get_tool_discoverability_empty_expected_tools_wildcard_mode(lib: MCPLibrary, tmp_path: Path) -> None:
tests/unit/discoverability/test_keyword.py:366:    """Empty `expected_tools` -> ANY tool call counts as success AND all
tests/unit/discoverability/test_keyword.py:371:    the populated-expected_tools branch, leaving wildcard-mode tasks with
tests/unit/discoverability/test_keyword.py:379:        # expected_tools omitted -> defaults to []
tests/unit/discoverability/test_comparison_extras_gate.py:68:    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
tests/unit/discoverability/test_comparison_extras_gate.py:92:    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
tests/unit/discoverability/test_comparison.py:113:    return Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"

exec
/bin/bash -lc "uv run python - <<'PY'
from AgentEval.mcp.library import MCPLibrary
from pathlib import Path
import tempfile
from textwrap import dedent
p = Path(tempfile.gettempdir())/'empty_discoverability_tasks.yaml'
p.write_text('tasks: []\\n')
lib = MCPLibrary()
try:
    lib.get_tool_discoverability(mcp_server='echo', adapter='generic', tasks=str(p), trials_per_task=1)
except Exception as e:
    print(type(e).__name__, e)
PY" in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc "uv run python - <<'PY'
from pathlib import Path
from AgentEval.mcp.library import MCPLibrary
from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunResult, AgentRunMetadata, Usage

fixture = Path('tests/fixtures/discoverability/tasks-basic.yaml')
class NoTools(InProcessAdapter):
    def run(self, prompt, **kwargs):
        return AgentRunResult(response_text='x', tool_calls=[], usage=Usage(input_tokens=1, output_tokens=1), metadata=AgentRunMetadata(completeness='complete', mcp_coverage='hosted_in_process'), cost_usd=0.0, latency_seconds=0.0, trace_id='0'*32)
register_adapter('same_a', NoTools)
register_adapter('same_b', NoTools)
lib=MCPLibrary()
r=lib.get_tool_discoverability_comparison(mcp_server='echo', adapters=['same_a','same_b'], tasks=str(fixture), trials_per_task=1)
print(r.cross_adapter_deltas)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 1290ms:
InvalidDiscoverabilityTasksError INVALID_DISCOVERABILITY_TASKS: discoverability tasks YAML `tasks` list is empty; at least one task is required
  File: /tmp/empty_discoverability_tasks.yaml
  Line: N/A
  Field: /tasks
  Fix: Add at least one task entry with `id:` + `prompt:` fields.

 succeeded in 2670ms:
{'same_a_vs_same_b': PairwiseAdapterDelta(adapter_a='same_a', adapter_b='same_b', pass_rate_delta=0.0, mann_whitney_result=MannWhitneyResult(u_statistic=4.5, p_value=nan, effect_size_r=0.0, n_a=3, n_b=3), significant_at_alpha_05=False)}

exec
/bin/bash -lc "nl -ba tests/unit/discoverability/conftest.py | sed -n '1,200p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	"""Test fixtures for `tests/unit/discoverability/`.
    16	
    17	Story 4.4 code-review LOW-C fix 2026-05-20 (Blind LOW-4): the keyword
    18	tests register stub adapters via `register_adapter("stub_disco_*", ...)`
    19	which mutates the module-global `_registered_adapters` dict in
    20	`AgentEval._kernel.discovery`. Without cleanup, those names persist
    21	across the test session and a future test re-registering the same name
    22	would hit `UserWarning("entry-point override detected")` or shadow the
    23	fresh class. Snapshot + restore the registry post-test for isolation.
    24	"""
    25	
    26	from __future__ import annotations
    27	
    28	from collections.abc import Iterator
    29	
    30	import pytest
    31	
    32	from AgentEval._kernel import discovery
    33	
    34	
    35	@pytest.fixture(autouse=True)
    36	def _restore_adapter_registry() -> Iterator[None]:
    37	    """Snapshot + restore the programmatic adapter registry per test."""
    38	    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    39	    try:
    40	        yield
    41	    finally:
    42	        discovery._registered_adapters.clear()  # noqa: SLF001
    43	        discovery._registered_adapters.update(snapshot)  # noqa: SLF001

codex
I’m not seeing another product bug in the pairwise math or the `nan` propagation; those are behaving correctly. I’m doing one last sweep on the surrounding discoverability suite and the story’s evidence claims so I can separate real code defects from inaccurate audit notes.
exec
/bin/bash -lc "python - <<'PY'
from pathlib import Path
for path in ['tests/unit/discoverability/test_keyword.py','tests/unit/discoverability/test_loader.py','tests/unit/discoverability/test_wilson_ci.py']:
    p=Path(path)
    n=sum(1 for line in p.read_text().splitlines() if line.startswith('def test_'))
    print(path, n)
PY" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
tests/unit/discoverability/test_keyword.py 20
tests/unit/discoverability/test_loader.py 21
tests/unit/discoverability/test_wilson_ci.py 10

exec
/bin/bash -lc 'uv run pytest --collect-only -q tests/unit/discoverability' in /home/many/workspace/robotframework-agenteval
exec
/bin/bash -lc 'uv run pytest -q tests/unit/discoverability' in /home/many/workspace/robotframework-agenteval
 succeeded in 2414ms:
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_single_adapter
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_adapters_keys_mismatch
tests/unit/discoverability/test_comparison.py::test_comparison_result_rejects_heatmap_models_mismatch
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_identical_adapters
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_out_of_range_delta
tests/unit/discoverability/test_comparison.py::test_pairwise_delta_rejects_significance_inconsistency
tests/unit/discoverability/test_comparison.py::test_comparison_summary_rejects_unknown_best_adapter
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_2_adapters
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_3_adapters
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_per_task_pass_rate_in_cells
tests/unit/discoverability/test_comparison.py::test_heatmap_from_comparison_as_ascii_3_columns
tests/unit/discoverability/test_comparison.py::test_compare_2_adapters_produces_1_pairwise_delta
tests/unit/discoverability/test_comparison.py::test_compare_3_adapters_produces_3_pairwise_deltas
tests/unit/discoverability/test_comparison.py::test_compare_pairwise_keys_preserve_input_order
tests/unit/discoverability/test_comparison.py::test_compare_clearly_different_distributions_significant
tests/unit/discoverability/test_comparison.py::test_compare_identical_distributions_not_significant
tests/unit/discoverability/test_comparison_extras_gate.py::test_comparison_schema_importable_without_extra
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_raises_import_error_when_advanced_extra_missing
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_import_error_message_contract
tests/unit/discoverability/test_comparison_extras_gate.py::test_compare_keyword_arg_validation_runs_before_extras_gate
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_returns_discoverability_result
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_no_tool_calls_zero_pass_rate
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_competing_tools_tracked
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_partial_pass_rate_with_wilson_ci
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_missing_tasks_kwarg_raises
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_missing_mcp_server_kwarg_raises
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_invalid_yaml_raises
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_zero_trials_raises
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_unknown_adapter_raises
tests/unit/discoverability/test_keyword.py::test_keyword_has_tier_3_annotation
tests/unit/discoverability/test_keyword.py::test_keyword_has_robot_marker
tests/unit/discoverability/test_keyword.py::test_task_result_pass_rate_property
tests/unit/discoverability/test_keyword.py::test_task_result_pass_rate_zero_trials
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_tracks_per_trial_data
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_empty_expected_tools_wildcard_mode
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_runtime_includes_setup
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_budget_carve_out_not_enforced
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_strict_signature_adapter_raises_with_df_4_4_s2_reference
tests/unit/discoverability/test_keyword.py::test_task_result_inner_list_mutation_blocked
tests/unit/discoverability/test_keyword.py::test_get_tool_discoverability_summary_shape_per_prd_fr10a
tests/unit/discoverability/test_loader.py::test_load_minimal_task
tests/unit/discoverability/test_loader.py::test_load_full_task
tests/unit/discoverability/test_loader.py::test_load_file_not_found
tests/unit/discoverability/test_loader.py::test_load_wrong_extension
tests/unit/discoverability/test_loader.py::test_load_malformed_yaml
tests/unit/discoverability/test_loader.py::test_load_non_utf8
tests/unit/discoverability/test_loader.py::test_load_top_level_not_mapping
tests/unit/discoverability/test_loader.py::test_load_missing_tasks_field
tests/unit/discoverability/test_loader.py::test_load_tasks_not_list
tests/unit/discoverability/test_loader.py::test_load_empty_tasks
tests/unit/discoverability/test_loader.py::test_load_task_missing_id
tests/unit/discoverability/test_loader.py::test_load_task_empty_id
tests/unit/discoverability/test_loader.py::test_load_task_missing_prompt
tests/unit/discoverability/test_loader.py::test_load_task_empty_prompt_rejected
tests/unit/discoverability/test_loader.py::test_load_task_non_string_id_rejected
tests/unit/discoverability/test_loader.py::test_load_task_expected_tools_not_list
tests/unit/discoverability/test_loader.py::test_load_task_expected_tools_non_string_element
tests/unit/discoverability/test_loader.py::test_load_task_required_not_bool
tests/unit/discoverability/test_loader.py::test_load_duplicate_task_ids_rejected
tests/unit/discoverability/test_loader.py::test_load_bundled_fixture
tests/unit/discoverability/test_loader.py::test_discoverability_task_dataclass_frozen
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_zero_trials_returns_full_range
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_all_success_with_small_n
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_zero_success_with_small_n
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_half_success_centered
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_bounds_in_unit_interval
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_negative_trials_raises
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_successes_out_of_range_raises
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_unsupported_confidence_raises
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_90_percent_narrower_than_95
tests/unit/discoverability/test_wilson_ci.py::test_wilson_ci_99_percent_wider_than_95

71 tests collected in 1.13s

 succeeded in 8592ms:
.......................................................................  [100%]
71 passed in 6.19s

exec
/bin/bash -lc "nl -ba _bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md | sed -n '296,312p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
   296	
   297	## Tasks / Subtasks
   298	
   299	- [x] **Task 1: PRD amendment (D-1 + AC-13.3.12)** — `_bmad-output/planning-artifacts/prd.md` L1500 amended per the N-runtime `adapters=[...]` wording + `DiscoverabilityResult` typo fix.
   300	- [x] **Task 2: `src/AgentEval/discoverability/schema.py` extension (AC-13.3.2)** — `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` appended with `__post_init__` validators; nan-tolerant `significant_at_alpha_05` consistency check (per scipy identical-samples convention).
   301	- [x] **Task 3: `src/AgentEval/_heatmap/models.py` extension (AC-13.3.3)** — `CohortHeatmap.from_comparison` classmethod added with `TYPE_CHECKING` import.
   302	- [x] **Task 4: `src/AgentEval/discoverability/_internal.py` (AC-13.3.6, NEW)** — `run_single_adapter_discoverability` helper extracted from existing Story 4.4 body; behavior identity verified by Story 4.4's 50+ existing tests passing unchanged.
   303	- [x] **Task 5: `src/AgentEval/mcp/library.py` extension (AC-13.3.1 + AC-13.3.4 + AC-13.3.5)** — `get_tool_discoverability_comparison` method (Python name `get_*` per verb-allowlist; RF name `MCP.Compare Tool Discoverability` per epic); `_ADVANCED_AVAILABLE` gate via `_stats_lib._ADVANCED_AVAILABLE` module-attr read (NOT `from X import Y` which captures stale value across session-wide monkeypatch); existing `get_tool_discoverability` refactored to delegate to the helper.
   304	- [x] **Task 6: `tests/unit/discoverability/test_comparison.py` (AC-13.3.7)** — 16 unit tests covering dataclass validators (7) + heatmap multi-column (4) + pairwise counting (3) + Mann-Whitney significance dispatch (2).
   305	- [x] **Task 7: `tests/unit/discoverability/test_comparison_extras_gate.py` (AC-13.3.7 + L-2)** — 4 ImportError-gate tests, NO module-top `importorskip`; covers schema importability + helper message + keyword raise + arg-validation-precedence.
   306	- [x] **Task 8: `tests/integration/discoverability/test_compare_e2e.py` (AC-13.3.8)** — 3 stub adapters (100% / 50% / 0% pass rates) + CONCRETE numerical assertions per L-4 (ranking + p < 0.05 for a-vs-c + heatmap shape + cost math); + 2 arg-validation tests.
   307	- [x] **Task 9: `docs/contracts/stability-surface.md` (AC-13.3.10)** — `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)` subsection with 5 entries.
   308	- [x] **Task 10: Phase-1.5 carry-over catalog UPSTREAM (34th consecutive)** (AC-13.3.11) — C89 (DF-13.3-S1 @guarded_fanout) + C90 (DF-13.3-S2 per-adapter MCP) + C91 (DF-13.3-S3 Bonferroni correction) added to both `phase-1-5-carry-overs.md` (88 → 91) + `deferred-work.md`.
   309	- [x] **Task 11: All-gates pass** (AC-13.3.13) — `uv run pytest tests/` reports **1874 passed + 16 skipped + 0 failed** (+28 net vs 1846 + 16 Story 13.2 baseline). 22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration; the +28 includes a couple of side-fix tests). ruff/format/mypy/license clean. libdoc `docs/keywords/MCPLibrary.html` regenerated with `MCP.Compare Tool Discoverability` keyword.
   310	- [x] **Task 12: Sprint-status flip** (AC-13.3.14) — `13-3-compare-tool-discoverability-cross-adapter: review`; `last_updated: 2026-06-01`.
   311	
   312	## Dev Notes

exec
/bin/bash -lc "nl -ba src/AgentEval/stats/library.py | sed -n '1,120p'" in /home/many/workspace/robotframework-agenteval
 succeeded in 0ms:
     1	# Copyright 2026 Many Kasiriha
     2	#
     3	# Licensed under the Apache License, Version 2.0 (the "License");
     4	# you may not use this file except in compliance with the License.
     5	# You may obtain a copy of the License at
     6	#
     7	#     http://www.apache.org/licenses/LICENSE-2.0
     8	#
     9	# Unless required by applicable law or agreed to in writing, software
    10	# distributed under the License is distributed on an "AS IS" BASIS,
    11	# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    12	# See the License for the specific language governing permissions and
    13	# limitations under the License.
    14	
    15	# ruff: noqa: E501
    16	# Browser-Library-style docstring tables (`| =Arguments= | =Description= |`)
    17	# can carry long descriptions on a single physical line. The per-line
    18	# 120-char limit is waived for this file per Phase 2 docstring-refresh
    19	# proposal (2026-05-26).
    20	
    21	"""Statistical primitives RF-keyword surface (Story 6.3 / PRD FR26 + FR27 + FR31a).
    22	
    23	Ships 4 `@keyword`-decorated methods on `StatsLibrary`:
    24	
    25	- FR26: `Stat.Run N Times` (Tier-3 fan-out via `@guarded_fanout`) — independent-
    26	  sample N-trial runner; returns `list[KeywordRun]` per Story 1b.6 ratified
    27	  return type.
    28	- FR27: `Stat.Get Pass At K` (Tier-1) — HumanEval unbiased estimator; returns
    29	  `float ∈ [0, 1]`.
    30	- D-1 resolution paired getter: `Stat.Get Pass At K Confidence Interval` (Tier-1)
    31	  — Wilson score interval at `confidence` level.
    32	- FR31a: `Stat.Assert Run Determinism` (Tier-1) — runs a Tier-1 keyword twice,
    33	  asserts bit-identical output.
    34	
    35	Sub-library registration via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.
    36	Tier-3 `Stat.Run N Times` reads `_max_cost_usd` + `_max_runtime_seconds`
    37	from `self` (forwarded from top-level `AgentEval(...)` per Story 1a.6 +
    38	Story 4.3 propagation pattern).
    39	"""
    40	
    41	from __future__ import annotations
    42	
    43	from collections.abc import Callable
    44	from typing import Any
    45	
    46	from robot.api.deco import keyword
    47	
    48	from AgentEval._kernel.context import current_context
    49	from AgentEval._kernel.guardrails import guarded_fanout
    50	from AgentEval._kernel.redaction import redact
    51	from AgentEval._kernel.tier import tier
    52	from AgentEval.errors import TierViolationError
    53	from AgentEval.stats import _internal
    54	from AgentEval.stats.types import KeywordRun, MannWhitneyResult
    55	
    56	__all__ = ["StatsLibrary"]
    57	
    58	# Browser-Library-style docstring migration marker (Phase 2, 2026-05-26).
    59	_BROWSER_STYLE_MIGRATED = True
    60	
    61	# Story 13.1 — Phase-2 `[agenteval-advanced]` extra gate. scipy + numpy power
    62	# the 3 advanced keyword methods (Mann-Whitney U, Cliff Delta, Bootstrap CI).
    63	# The `StatsLibrary` class itself MUST remain importable WITHOUT the extra so
    64	# Phase-1 surface keywords stay functional; only the 3 Phase-2 methods raise
    65	# ImportError on invocation.
    66	try:
    67	    import numpy as _numpy_advanced  # noqa: F401
    68	    import scipy as _scipy_advanced  # noqa: F401
    69	
    70	    _ADVANCED_AVAILABLE = True
    71	    _ADVANCED_IMPORT_ERROR: ImportError | None = None
    72	except ImportError as _advanced_err:  # pragma: no cover  -- exercised via monkeypatch
    73	    _ADVANCED_AVAILABLE = False
    74	    _ADVANCED_IMPORT_ERROR = _advanced_err
    75	
    76	
    77	def _raise_advanced_extra_missing(keyword_name: str) -> None:
    78	    """Raise the canonical `[agenteval-advanced]` extra-missing ImportError.
    79	
    80	    Per Story 13.1 D-3 + epics.md L2153: the ImportError MUST recommend
    81	    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
    82	    """
    83	    raise ImportError(
    84	        f"Stat.{keyword_name}: scipy + numpy required. "
    85	        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
    86	    ) from _ADVANCED_IMPORT_ERROR
    87	
    88	
    89	class StatsLibrary:
    90	    """4 `@keyword`-decorated statistical primitives (Story 6.3 / PRD FR26-FR31a)."""
    91	
    92	    def __init__(
    93	        self,
    94	        max_cost_usd: float | None = None,
    95	        max_runtime_seconds: float | None = None,
    96	    ) -> None:
    97	        """Library-level cost/runtime budgets per Story 1a.6 + ADR-015.
    98	
    99	        Forwarded from top-level `AgentEval(max_cost_usd=..., max_runtime_seconds=...)`
   100	        via `_build_components` per Story 4.3 pattern. Consumed by `@guarded_fanout`
   101	        on `Stat.Run N Times` (Tier-3 fan-out keyword).
   102	        """
   103	        self._max_cost_usd = max_cost_usd
   104	        self._max_runtime_seconds = max_runtime_seconds
   105	
   106	    # ----------------------------------------------------------------- #
   107	    # FR26 — Stat.Run N Times (Tier-3 fan-out)                          #
   108	    # ----------------------------------------------------------------- #
   109	
   110	    @keyword(name="Stat.Run N Times")
   111	    @tier(3)
   112	    @guarded_fanout()
   113	    def run_n_times(
   114	        self,
   115	        n: int,
   116	        keyword: str | Callable[..., Any],
   117	        keyword_args: dict[str, Any] | list[Any] | None = None,
   118	        seed: int | None = None,
   119	    ) -> list[KeywordRun]:
   120	        """Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).

codex
### HIGH-1: Comparison runtime is underreported by restarting the timer for each adapter

**File:** `src/AgentEval/mcp/library.py:689`
**Issue:** The comparison loop passes a fresh `time.monotonic()` into `run_single_adapter_discoverability()` for every adapter, then summarizes with `max(...)`. Because the compare keyword currently runs adapters serially, `summary.total_runtime_seconds` becomes “slowest single adapter” instead of “time the caller actually waited for `MCP.Compare Tool Discoverability`”. That contradicts the helper contract in Story 13.3 and materially underreports runtime.
**Evidence:** 
```python
for adapter_name in adapters:
    per_adapter_results[adapter_name] = run_single_adapter_discoverability(
        ...
        t_start=time.monotonic(),  # per-adapter timer; aggregate uses MAX.
    )
...
total_runtime = max(r.summary.total_runtime_seconds for r in per_adapter_results.values())
```
Probe output:
```text
measured_elapsed 2.1785764321684837
reported_summary_runtime 0.3013240317814052
per_adapter_runtimes {'slow_a': 0.3013240317814052, 'slow_b': 0.30095729092136025}
```
**Fix:** Pass the outer `t_start` into every helper call and compute the comparison summary runtime from the shared start, or add a separate end-to-end comparison runtime field and document the per-adapter runtime semantics explicitly.

### HIGH-2: `DiscoverabilityComparisonSummary` accepts impossible best/worst adapters

**File:** `src/AgentEval/discoverability/schema.py:237`
**Issue:** The new public summary dataclass only checks that `best_adapter` and `worst_adapter` are present in the mapping. It never checks that `best_adapter` actually has the maximum pass rate or that `worst_adapter` has the minimum. That violates the Story 13.3 schema contract and allows internally false summaries to be constructed without error.
**Evidence:**
```python
if self.best_adapter not in self.pass_rate_per_adapter:
    raise ValueError(...)
if self.worst_adapter not in self.pass_rate_per_adapter:
    raise ValueError(...)
```
Probe output:
```text
summary accepted DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'a': 1.0, 'b': 0.0}, best_adapter='b', worst_adapter='a')
```
**Fix:** In `__post_init__`, recompute `max(...)` and `min(...)` from `pass_rate_per_adapter` and reject summaries whose `best_adapter`/`worst_adapter` do not match.

### HIGH-3: Top-level comparison results do not validate `summary.pass_rate_per_adapter` against `adapters`

**File:** `src/AgentEval/discoverability/schema.py:280`
**Issue:** `DiscoverabilityComparisonResult.__post_init__` validates `per_adapter_results` and `heatmap.models`, but it never cross-checks the embedded summary against the adapter set. A result can therefore claim adapters `("a", "b")` while its summary only contains `{"x": ...}`. That breaks the public dataclass invariant Story 13.3 said it would enforce.
**Evidence:**
```python
if set(self.adapters) != set(self.per_adapter_results.keys()):
    raise ValueError(...)
if set(self.adapters) != set(self.heatmap.models):
    raise ValueError(...)
```
Probe output:
```text
result accepted summary keys mismatch DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'x': 1.0}, best_adapter='x', worst_adapter='x')
```
**Fix:** Add a `summary.pass_rate_per_adapter` key-set check in `DiscoverabilityComparisonResult.__post_init__`, and reject summaries whose adapters do not exactly match `self.adapters`.

### MED-1: The integration acceptance test drifts from the epic’s “zero-cost” requirement

**File:** `tests/integration/discoverability/test_compare_e2e.py:68`
**Issue:** The epic acceptance text says the integration comparison should run “using Mock provider for all adapters to keep costs zero.” The new integration test instead hardcodes `cost_per_call=0.001` and asserts a non-zero aggregate cost. That means the acceptance evidence no longer matches the ratified epic behavior it is supposed to prove.
**Evidence:**
```python
def _make_stub_adapter(success_pattern: list[bool], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
```
and
```python
expected_cost = 3 * len(result.heatmap.tasks) * 10 * 0.001
assert result.summary.total_cost_usd == pytest.approx(expected_cost)
```
**Fix:** Either change the stubs to `cost_per_call=0.0` and drop the non-zero cost assertion, or amend the epic/story source so the acceptance criterion no longer claims zero-cost comparison runs.

### LOW-1: The Story 13.3 test-count evidence is numerically wrong

**File:** `_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md:309`
**Issue:** The artifact claims “22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration)”, but that arithmetic is 23, and `pytest --collect-only` confirms 23 collected tests. The same artifact also says the refactor was verified by “50+ existing tests” in `tests/unit/discoverability/test_keyword.py`, but that file currently contains 20 tests; the broader `tests/unit/discoverability/` suite is 71.
**Evidence:**
```text
22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration)
```
Collection output:
```text
unit file test defs 16
gate file test defs 4
integration file test defs 3
23 tests collected in 1.15s
```
and
```text
uv run pytest -q tests/unit/discoverability/test_keyword.py
....................                                                     [100%]
20 passed in 4.88s
```
**Fix:** Correct the story artifact to 23 new tests, and if the intent is to cite the full Story 4.4 discoverability unit surface, reference `tests/unit/discoverability/` rather than `test_keyword.py` alone.

**Total: 3 HIGH + 1 MED + 1 LOW**
tokens used
458,649
### HIGH-1: Comparison runtime is underreported by restarting the timer for each adapter

**File:** `src/AgentEval/mcp/library.py:689`
**Issue:** The comparison loop passes a fresh `time.monotonic()` into `run_single_adapter_discoverability()` for every adapter, then summarizes with `max(...)`. Because the compare keyword currently runs adapters serially, `summary.total_runtime_seconds` becomes “slowest single adapter” instead of “time the caller actually waited for `MCP.Compare Tool Discoverability`”. That contradicts the helper contract in Story 13.3 and materially underreports runtime.
**Evidence:** 
```python
for adapter_name in adapters:
    per_adapter_results[adapter_name] = run_single_adapter_discoverability(
        ...
        t_start=time.monotonic(),  # per-adapter timer; aggregate uses MAX.
    )
...
total_runtime = max(r.summary.total_runtime_seconds for r in per_adapter_results.values())
```
Probe output:
```text
measured_elapsed 2.1785764321684837
reported_summary_runtime 0.3013240317814052
per_adapter_runtimes {'slow_a': 0.3013240317814052, 'slow_b': 0.30095729092136025}
```
**Fix:** Pass the outer `t_start` into every helper call and compute the comparison summary runtime from the shared start, or add a separate end-to-end comparison runtime field and document the per-adapter runtime semantics explicitly.

### HIGH-2: `DiscoverabilityComparisonSummary` accepts impossible best/worst adapters

**File:** `src/AgentEval/discoverability/schema.py:237`
**Issue:** The new public summary dataclass only checks that `best_adapter` and `worst_adapter` are present in the mapping. It never checks that `best_adapter` actually has the maximum pass rate or that `worst_adapter` has the minimum. That violates the Story 13.3 schema contract and allows internally false summaries to be constructed without error.
**Evidence:**
```python
if self.best_adapter not in self.pass_rate_per_adapter:
    raise ValueError(...)
if self.worst_adapter not in self.pass_rate_per_adapter:
    raise ValueError(...)
```
Probe output:
```text
summary accepted DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'a': 1.0, 'b': 0.0}, best_adapter='b', worst_adapter='a')
```
**Fix:** In `__post_init__`, recompute `max(...)` and `min(...)` from `pass_rate_per_adapter` and reject summaries whose `best_adapter`/`worst_adapter` do not match.

### HIGH-3: Top-level comparison results do not validate `summary.pass_rate_per_adapter` against `adapters`

**File:** `src/AgentEval/discoverability/schema.py:280`
**Issue:** `DiscoverabilityComparisonResult.__post_init__` validates `per_adapter_results` and `heatmap.models`, but it never cross-checks the embedded summary against the adapter set. A result can therefore claim adapters `("a", "b")` while its summary only contains `{"x": ...}`. That breaks the public dataclass invariant Story 13.3 said it would enforce.
**Evidence:**
```python
if set(self.adapters) != set(self.per_adapter_results.keys()):
    raise ValueError(...)
if set(self.adapters) != set(self.heatmap.models):
    raise ValueError(...)
```
Probe output:
```text
result accepted summary keys mismatch DiscoverabilityComparisonSummary(total_cost_usd=0.0, total_runtime_seconds=0.0, pass_rate_per_adapter={'x': 1.0}, best_adapter='x', worst_adapter='x')
```
**Fix:** Add a `summary.pass_rate_per_adapter` key-set check in `DiscoverabilityComparisonResult.__post_init__`, and reject summaries whose adapters do not exactly match `self.adapters`.

### MED-1: The integration acceptance test drifts from the epic’s “zero-cost” requirement

**File:** `tests/integration/discoverability/test_compare_e2e.py:68`
**Issue:** The epic acceptance text says the integration comparison should run “using Mock provider for all adapters to keep costs zero.” The new integration test instead hardcodes `cost_per_call=0.001` and asserts a non-zero aggregate cost. That means the acceptance evidence no longer matches the ratified epic behavior it is supposed to prove.
**Evidence:**
```python
def _make_stub_adapter(success_pattern: list[bool], cost_per_call: float = 0.001) -> type[InProcessAdapter]:
```
and
```python
expected_cost = 3 * len(result.heatmap.tasks) * 10 * 0.001
assert result.summary.total_cost_usd == pytest.approx(expected_cost)
```
**Fix:** Either change the stubs to `cost_per_call=0.0` and drop the non-zero cost assertion, or amend the epic/story source so the acceptance criterion no longer claims zero-cost comparison runs.

### LOW-1: The Story 13.3 test-count evidence is numerically wrong

**File:** `_bmad-output/implementation-artifacts/13-3-compare-tool-discoverability-cross-adapter.md:309`
**Issue:** The artifact claims “22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration)”, but that arithmetic is 23, and `pytest --collect-only` confirms 23 collected tests. The same artifact also says the refactor was verified by “50+ existing tests” in `tests/unit/discoverability/test_keyword.py`, but that file currently contains 20 tests; the broader `tests/unit/discoverability/` suite is 71.
**Evidence:**
```text
22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration)
```
Collection output:
```text
unit file test defs 16
gate file test defs 4
integration file test defs 3
23 tests collected in 1.15s
```
and
```text
uv run pytest -q tests/unit/discoverability/test_keyword.py
....................                                                     [100%]
20 passed in 4.88s
```
**Fix:** Correct the story artifact to 23 new tests, and if the intent is to cite the full Story 4.4 discoverability unit surface, reference `tests/unit/discoverability/` rather than `test_keyword.py` alone.

**Total: 3 HIGH + 1 MED + 1 LOW**
