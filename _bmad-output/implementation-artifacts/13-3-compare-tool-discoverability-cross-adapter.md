# Story 13.3: Compare Tool Discoverability Cross-Adapter (FR10b)

Status: done

## Story

As **Mei (Agent Surface Author)** doing cross-runtime MCP analysis,
I want `MCP.Compare Tool Discoverability` running the same task set against multiple Tier-1 adapters/models, returning a cross-adapter cohort comparison with statistical significance per PRD FR10b,
So that I can claim "tool X is discoverable by Claude AND GPT AND Copilot" with empirical evidence — the killer Mei feature deferred from Phase 1, building on Story 13.1's Mann-Whitney U + Story 8b.2's `CohortHeatmap` + Story 4.4's per-adapter `MCP.Get Tool Discoverability`.

## Pre-create-story drift check (53rd use of `feedback_spec_vs_ratified_doc_precheck`, 2026-06-01)

11 drifts caught — 6 fresh decisions from spec analysis + 5 UPSTREAM lessons from Stories 13.1 + 13.2 reviews. **100% real-drift catch rate maintained through 52 prior uses.**

- **D-1 (HIGH — runtime-shape drift PRD vs epic, 1-vs-1 NOT resolved by majority — needs Mei intent reading):** **PRD vs epic disagree on the keyword signature.**
  - **PRD L1500:** `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>` — explicit 2-runtime A/B comparison.
  - **Epic L2186:** `MCP.Compare Tool Discoverability mcp_server=rf-mcp tasks=... adapters=[generic, claude-agent-sdk, openai-agents-sdk] trials_per_task=5 max_cost_usd=20.00` — N-runtime list (3 adapters in the example).
  - **Decision (epic wins, generalize-then-PRD-amend):** ship the N-runtime `adapters: list[str]` shape per epic — covers the PRD's 2-runtime A/B case by passing a 2-element list (`adapters=["claude_code_cli", "codex_cli"]`). The N-shape is strictly more general, more aligned with Mei's "claim X across Claude AND GPT AND Copilot" goal (which requires ≥3 adapters), and matches Story 13.5's symmetric Skill version (which also uses `adapters=[...]`). **Same-commit fix:** amend PRD L1500 to read: `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...] (≥2 required)` with note "Backwards-compat: a 2-element list satisfies the original A/B semantic". Per `feedback_in_flight_spec_amendment` + Story 13.1 D-1 fix-the-losing-source-NOW precedent.

- **D-2 (HIGH — return-type shape, no canonical source):** PRD doesn't fully spec `DiscoverabilityComparisonResult`'s field set; epic L2187 enumerates "per-adapter task-level results + cross-adapter Pass@k differential with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data." **Decision:** ship `DiscoverabilityComparisonResult` frozen dataclass at `src/AgentEval/discoverability/schema.py` (alongside existing `DiscoverabilityResult` / `TaskResult` / `DiscoverabilitySummary`) with fields:
  ```python
  @dataclass(frozen=True)
  class DiscoverabilityComparisonResult:
      adapters: tuple[str, ...]                                                       # adapter names in input order
      per_adapter_results: Mapping[str, DiscoverabilityResult]                        # {adapter_name: per-adapter result}
      cross_adapter_deltas: Mapping[str, "PairwiseAdapterDelta"]                      # {f"{a1}_vs_{a2}": delta} for all ordered pairs
      heatmap: CohortHeatmap                                                          # multi-column heatmap (one column per adapter)
      summary: "DiscoverabilityComparisonSummary"                                     # aggregate roll-up
  ```
  with:
  ```python
  @dataclass(frozen=True)
  class PairwiseAdapterDelta:
      adapter_a: str
      adapter_b: str
      pass_rate_delta: float                                                          # avg(adapter_a per-task pass rate) - avg(adapter_b)
      mann_whitney_result: MannWhitneyResult                                          # Story 13.1 dataclass; predicate=lambda r: r.pass_rate
      significant_at_alpha_05: bool                                                   # p_value < 0.05

  @dataclass(frozen=True)
  class DiscoverabilityComparisonSummary:
      total_cost_usd: float                                                           # sum across all adapters
      total_runtime_seconds: float                                                    # max across adapters (parallel; not summed)
      pass_rate_per_adapter: Mapping[str, float]                                      # adapter_name → overall_pass_rate
      best_adapter: str                                                               # max(pass_rate_per_adapter)
      worst_adapter: str                                                              # min(pass_rate_per_adapter)
  ```
  Frozen dataclasses with `__post_init__` defensive copy + Mapping → dict cast per Story 1b.2 M_R6 pattern + Story 4.4 frozen-invariant precedent.

- **D-3 (HIGH — file home + sub-library composition, `MCPLibrary` carve-out):** `MCPLibrary` is excluded from `_SUB_LIBRARIES` per Story 2.2 collision norm + Story 4.4 architectural gap (DF-4.4-S1 / C20: `@guarded_fanout` enforcement deferred because `MCPLibrary` constructed via `WITH NAME MCP` not `_SUB_LIBRARIES`). **Decision:** ship `MCP.Compare Tool Discoverability` as a NEW `@keyword`-decorated method on `MCPLibrary` at `src/AgentEval/mcp/library.py` — same parent as `MCP.Get Tool Discoverability`. Same `@guarded_fanout` carve-out applies (kwargs tracked, NOT enforced; DF-4.4-S1 carry-over EXTENDED to cover Compare). NO new sub-library. Per Story 13.1 D-5 + Story 13.2 D-3: honor architecture's pre-allocated file home; don't create new modules.

- **D-4 (HIGH — `mcp_server` arg semantics under N-adapters):** Epic AC L2186 shows ONE `mcp_server=rf-mcp` arg shared across all adapters. The Phase-1 `Get Tool Discoverability` carve-out (DF-4.1-S2 + DF-4.2-S1) means `mcp_server=` is accepted-but-not-forwarded to `adapter.run(mcp_servers=...)` — both Phase-1 adapters raise `NotImplementedError` on non-empty `mcp_servers`. For Phase-2 adapters from Stories 10.1+10.2 (Claude Agent SDK + OpenAI Agents SDK) the same carve-out applies until DF-RFMCP-E2E-01 / C72 lands the LiteLLM MCP-bridge. **Decision:** Cross-adapter `Compare Tool Discoverability` inherits the same carve-out behavior — the `mcp_server` arg is forwarded VERBATIM to each per-adapter `Get Tool Discoverability` call; downstream behavior is identical to single-adapter Phase-1 (accepted, validated non-empty, not forwarded to adapter.run; tests use stub adapters via `register_adapter` per Story 7.3 pattern). Catalog a DF-13.3-S2 carry-over for "Phase-2.5: real per-adapter MCP attachment" gated on C72 + C68 + C69 + C73 + C75 (the existing per-adapter MCP-bridge backlog).

- **D-5 (HIGH — Mann-Whitney U predicate selection):** Story 13.1's `Stat.Mann Whitney U` requires `predicate: Callable[[KeywordRun], float]` value-extractor. But the comparison input is `list[TaskResult]` per adapter, NOT `list[KeywordRun]`. **Decision:** the Mann-Whitney U input is the PER-TASK pass-rate list per adapter:
  ```python
  rates_a = [t.pass_rate for t in per_adapter_results["adapter_a"].per_task_results]
  rates_b = [t.pass_rate for t in per_adapter_results["adapter_b"].per_task_results]
  ```
  These are `list[float]` directly. `MannWhitneyResult` consumes these via the lower-level `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` helper at `src/AgentEval/stats/mannwhitney.py` (Story 13.1 module-level pure helper). The keyword surface `Stat.Mann Whitney U` (which takes `list[KeywordRun]` + predicate) does NOT apply at this layer; we call the pure helper directly. Document this dispatch in the dev notes. (`_ADVANCED_AVAILABLE` gate at `stats/library.py` controls availability — same ImportError gate as the keyword surface; OTLPBackend D-5 precedent applies.)

- **D-6 (HIGH — `[agenteval-advanced]` extras dependency + ImportError gate):** Mann-Whitney U requires scipy + numpy via Story 13.1's `[agenteval-advanced]` extra. Story 13.3's `Compare Tool Discoverability` IS-A consumer of that dependency. **Decision:** `MCP.Compare Tool Discoverability` raises the SAME canonical ImportError (`"Stat.Mann Whitney U: scipy + numpy required. Install via: uv pip install robotframework-agenteval[agenteval-advanced]"`) when invoked without `[agenteval-advanced]`. Implementation: at the call site, probe `from AgentEval.stats.library import _ADVANCED_AVAILABLE`; if False, raise ImportError BEFORE running any per-adapter fan-out (fail-fast, save cost — operators discovering the missing extra should not pay 3-adapter trial cost first). Per Story 13.2 L-2 lesson: tests split into happy-path + extras-gate files.

- **D-7 (MED — `@tier(3)` + `@guarded_fanout` for the Compare-keyword, UPSTREAM Story 13.1 HIGH-C lesson):** `Compare Tool Discoverability` runs N×M trials (N adapters × M tasks × `trials_per_task` trials). This is Tier-3 fan-out by definition (parallel to `Stat.Run N Times` + `MCP.Get Tool Discoverability`). **Decision:** `@tier(3) + @guarded_fanout()` on the method, mirroring `MCP.Get Tool Discoverability` per Story 4.4 pattern. The `@guarded_fanout` Phase-1 carve-out applies identically (DF-4.4-S1 / C20: kwargs tracked, NOT enforced). Story 13.1 HIGH-C lesson re seed-required-for-FR31a DOESN'T apply here — `@tier(3)` keywords are explicitly stochastic by tier definition; no bit-identical guarantee.

- **D-8 (MED — `CohortHeatmap` multi-adapter extension):** Story 8b.2's `CohortHeatmap` already supports multi-column heatmaps via `tasks: tuple[str, ...]` + `models: tuple[str, ...]` + `cells`. `CohortHeatmap.from_discoverability` is single-model-only (Phase-1 carve-out per `_heatmap/models.py:46`). **Decision:** ADD a NEW classmethod `CohortHeatmap.from_comparison(result: DiscoverabilityComparisonResult) -> CohortHeatmap` at `src/AgentEval/_heatmap/models.py` that builds a multi-column heatmap (columns = adapter names; rows = task IDs; cells = per-adapter per-task pass-rate). The existing single-model classmethod stays unchanged for backward compat. This is the "cohort heatmap data" half of epic AC L2187 ("+ cohort heatmap data").

- **D-9 (MED — integration test stub-adapter pattern per epic L2189):** Epic L2189 mandates "integration test verifies the comparison runs cleanly across all configured adapters (using Mock provider for all adapters to keep costs zero)." Story 12.3 + Story 7.3 established the canonical `register_adapter()` stub pattern (NOT MockProvider at the provider layer — adapter-level stub). **Decision:** use the `register_adapter` 3-stub pattern from Story 12.3 — register 3 stub adapters (`compare_stub_a`, `compare_stub_b`, `compare_stub_c`) returning different per-task pass-rate distributions so Mann-Whitney U produces meaningfully different p-values. The 3rd stub validates ≥2 adapters → N-adapter generalization (per D-1 PRD-amend coverage).

- **D-10 (LOW — carry-over catalog gate UPSTREAM Story 13.1+13.2, 34th consecutive):** Anticipated Phase-1.5 / Phase-2 carry-overs for Story 13.3:
  - **DF-13.3-S1 (Phase-2.5):** `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` — same architectural gap as DF-4.4-S1 / C20. Cross-adapter fan-out compounds cost N× (N adapters × M tasks × trials). Once Phase-1.5 lands `MCPLibrary` cross-library budget plumbing, this keyword benefits identically.
  - **DF-13.3-S2 (Phase-2.5):** Real per-adapter MCP-server attachment (gated on C72 LiteLLM MCP-bridge + C68/C69/C73/C75 per-adapter HostedMcpObserver wiring). Phase-2 ships the keyword shape + stub-adapter testing; real cross-adapter MCP coverage flows from upstream MCP-bridge work.
  - **DF-13.3-S3 (Phase-2.5):** Multi-pairwise correction (Bonferroni / Holm) for the cross-adapter delta significance. Phase-2 ships pairwise comparisons WITHOUT multiple-testing correction — for N=3 adapters there are C(3,2)=3 pairs; Bonferroni-adjusted α=0.0167. Add `summary.bonferroni_adjusted_alpha: float` + `delta.significant_at_corrected_alpha: bool` in Phase-2.5.
  - Pre-emptive review-time catalog enforcement per Epic 11 retro lesson (UPSTREAM 2026-06-01): catalog C89 + C90 + C91 BEFORE invoking `/bmad-code-review`.

## Cross-story upstream lessons from Stories 13.1 + 13.2 reviews

Per `feedback_cross_story_upstream_lesson_propagation` (N=5 confirmed Epic 12; this is Story 13.2 → 13.3 same-epic transition):

- **L-1 applied (stability-surface drift UPSTREAM)**: register `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` + `CohortHeatmap.from_comparison` classmethod + the new `MCP.Compare Tool Discoverability` keyword in `docs/contracts/stability-surface.md` UPSTREAM at AC-13.3.10. Verify via grep before flipping to done.
- **L-2 applied (extras-gate test split)**: ImportError-gate tests (the `[agenteval-advanced]` requirement bubble-up from D-6) sit in a SEPARATE file from happy-path tests — NO `importorskip` at module top so they run in both base + WITH-extras CI envs. Story 13.1's `test_advanced_extras_gate.py` + Story 13.2's `test_backends_otlp_extras_gate.py` are the canonical pattern.
- **L-3 applied (Tier classification rationale)**: `MCP.Compare Tool Discoverability` is `@tier(3)` per fan-out semantics — the Story 13.1 HIGH-C seed-required-for-bit-identical FR31a concern does NOT apply (`@tier(3)` is explicitly stochastic). Document the @tier rationale in the keyword docstring.
- **L-4 applied (empirical correctness verification)**: integration test asserts CONCRETE numerical output of the cross-adapter delta — specifically that 3 stub adapters with KNOWN different pass-rate distributions produce the EXPECTED ranking (e.g., stub_a > stub_b > stub_c) + the expected p-value sign (stub_a-vs-stub_c should have p < 0.05). NOT just "the keyword ran without error."
- **L-5 applied (docstring precision)**: keyword docstring names the EXACT helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u` (Story 13.1 pure helper) and does NOT claim "calls Stat.Mann Whitney U" (which would be misleading since the keyword surface takes `list[KeywordRun]`, not the `list[float]` pass-rate input). Browser-Library-convention anchor test asserts "Mann-Whitney U" + "Story 13.1" + "FR10b" + "Phase-2" appear in the docstring.

## Acceptance Criteria

### AC-13.3.1 — `MCP.Compare Tool Discoverability` keyword on `MCPLibrary`

`src/AgentEval/mcp/library.py` extends `MCPLibrary` with a new `@keyword + @tier(3) + @guarded_fanout()`-decorated method (placed AFTER `get_tool_discoverability`):

```python
@keyword(name="MCP.Compare Tool Discoverability")
@tier(3)
@guarded_fanout()
def compare_tool_discoverability(
    self,
    mcp_server: str = "",
    adapters: list[str] | None = None,
    tasks: str = "",
    trials_per_task: int = 3,
    max_cost_usd: float = 20.00,
    max_runtime_seconds: float | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> DiscoverabilityComparisonResult: ...
```

Signature notes:
- `adapters` REQUIRED (no sensible default); ≥2 elements required (raises `ValueError("MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, <adapter_2>, ...] with ≥2 entries; got {adapters!r}")` otherwise).
- `mcp_server` + `tasks` REQUIRED (mirrors `Get Tool Discoverability` validation).
- `max_cost_usd` default `20.00` per epic L2186 verbatim (4× the single-adapter default of `5.00`, reflecting the N=3-adapter typical cost).
- `model` optional: when given, forwarded to ALL adapters; when None, each adapter uses its default. Phase-2 carry-over (DF-13.3-S4 Phase-2.5): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg.

Implementation:
1. Validate args (incl. ≥2 adapters).
2. Pre-flight `_ADVANCED_AVAILABLE` gate per D-6.
3. Load tasks YAML once (shared across adapters).
4. For each adapter in `adapters`: invoke per-adapter discoverability internally (delegating to the same logic as `get_tool_discoverability` but without re-validating + without per-call YAML re-load — extract a private `_run_single_adapter_discoverability` helper for shared logic).
5. Compute all C(N, 2) pairwise deltas via `compute_mann_whitney_u(rates_a, rates_b)`.
6. Build the multi-column `CohortHeatmap.from_comparison(result)`.
7. Build the summary.
8. Return `DiscoverabilityComparisonResult(...)`.

### AC-13.3.2 — `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` dataclasses

`src/AgentEval/discoverability/schema.py` appends 3 new frozen dataclasses per D-2 verbatim shape. All carry `__post_init__` defensive copies of mutable containers (`Mapping → dict(...)` cast; tuple immutability for `adapters`). Validators:

- `DiscoverabilityComparisonResult.__post_init__`: assert `len(adapters) >= 2`; assert `set(adapters) == set(per_adapter_results.keys())`; assert `set(adapters) == set(heatmap.models)` (cross-consistency).
- `PairwiseAdapterDelta.__post_init__`: assert `adapter_a != adapter_b`; assert `-1.0 <= pass_rate_delta <= 1.0`; assert `significant_at_alpha_05 == (mann_whitney_result.p_value < 0.05)`.
- `DiscoverabilityComparisonSummary.__post_init__`: assert `set(pass_rate_per_adapter.keys()) == set(adapters_referenced_in_comparison)`; assert `best_adapter` AND `worst_adapter` ∈ `pass_rate_per_adapter.keys()`; defensive `dict(...)` cast on `pass_rate_per_adapter`.

The 3 new classes added to `__all__`.

### AC-13.3.3 — `CohortHeatmap.from_comparison` classmethod

`src/AgentEval/_heatmap/models.py` extends `CohortHeatmap` with a new classmethod (placed AFTER `from_discoverability`):

```python
@classmethod
def from_comparison(
    cls,
    result: DiscoverabilityComparisonResult,
) -> CohortHeatmap:
    """Build a multi-column heatmap from a cross-adapter comparison (Story 13.3 / FR10b).

    Columns = adapter names (preserving input order). Rows = task IDs
    (union across all per-adapter results — should be identical since
    each adapter ran the same task set, but defensively uses the union
    to handle stub-adapter edge cases).
    """
```

Implementation:
- `tasks = tuple(union of task_ids across all per_adapter_results, preserving first-encounter order)`.
- `models = result.adapters` (already a tuple).
- `cells = tuple((task_id, adapter, t.pass_rate) for adapter, ad_result in result.per_adapter_results.items() for t in ad_result.per_task_results)`.

`TYPE_CHECKING` import for `DiscoverabilityComparisonResult` (mirrors existing `DiscoverabilityResult` import pattern).

### AC-13.3.4 — `_advanced_available` gate per D-6 + L-2 lesson

`MCPLibrary.compute_tool_discoverability_comparison` (or whatever the Python method name resolves to per the verb-allowlist) probes the gate AT INVOCATION (NOT at module import — `MCPLibrary` must remain importable without `[agenteval-advanced]`):

```python
# Inside the keyword method body, FIRST after arg validation:
from AgentEval.stats.library import _ADVANCED_AVAILABLE, _raise_advanced_extra_missing
if not _ADVANCED_AVAILABLE:
    _raise_advanced_extra_missing("Compare Tool Discoverability")
```

Note: re-uses Story 13.1's `_raise_advanced_extra_missing(keyword_name)` helper but with a different keyword name. **In-flight amendment:** the helper currently formats `f"Stat.{keyword_name}: ..."`. For `MCP.Compare Tool Discoverability` the leading `Stat.` is wrong. Either: (a) generalize the helper to accept a prefix arg; (b) raise the ImportError directly at the MCPLibrary call site with the verbatim spec message. **Decision (b)** — direct raise at the call site:
```python
raise ImportError(
    "MCP.Compare Tool Discoverability: scipy + numpy required. "
    "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
)
```
The helper stays Stats-prefix-specific; MCP raises directly. Symmetric maintenance.

### AC-13.3.5 — Method-name rename per verb-allowlist

Per Story 13.1 in-flight amendment #1: the Python method name's first token must be in `_VERB_ALLOWLIST`. `compare_tool_discoverability` → first token `compare` is NOT in allowlist (`get` / `set` / `run` / `send` / `assert` / `check` / `validate` / `compute` / `list` / etc. per `tests/unit/conventions/test_keyword_name_idiom.py`).

**Decision:** name the Python method `get_tool_discoverability_comparison` — first token `get` (in allowlist) + describes the operation correctly (operator gets back a comparison result). RF keyword name `MCP.Compare Tool Discoverability` is preserved per epic L2186 verbatim via `@keyword(name="MCP.Compare Tool Discoverability")` (the RF name + Python name diverge intentionally, per Story 13.1's `compute_mann_whitney_u` / `Stat.Mann Whitney U` precedent).

### AC-13.3.6 — Internal helper extraction at `src/AgentEval/discoverability/_internal.py` (NEW or extend existing)

Extract the per-adapter discoverability logic from `MCPLibrary.get_tool_discoverability` into a shared helper that BOTH `get_tool_discoverability` AND `get_tool_discoverability_comparison` call:

```python
def _run_single_adapter_discoverability(
    *,
    mcp_server: str,
    adapter: str,
    model: str | None,
    task_list: list[DiscoverabilityTask],  # pre-loaded; YAML parsed once
    trials_per_task: int,
    max_cost_usd: float,
    max_runtime_seconds: float | None,
    extra_adapter_kwargs: dict[str, Any],
    t_start: float,  # caller-provided so the runtime metric covers the whole compare
) -> DiscoverabilityResult: ...
```

Mirrors the existing `MCPLibrary.get_tool_discoverability` body but factored for shared use. Existing `get_tool_discoverability` is refactored to call the helper after its own arg validation + YAML load. **No behavior change** for single-adapter callers (verify via the existing 50+ Story 4.4 tests passing unchanged).

Place at `src/AgentEval/discoverability/_internal.py` (NEW file) — mirrors Story 6.3's `stats/_internal.py` pure-helper precedent + architecture's `_internal.py` canonical helper module name.

### AC-13.3.7 — Unit tests at `tests/unit/discoverability/test_comparison.py` (≥15 tests)

NEW file. Coverage:

- **Dataclass validators (6 tests)**: `DiscoverabilityComparisonResult` with `len(adapters) < 2` → ValueError; adapters/per_adapter_results key mismatch → ValueError; adapters/heatmap.models mismatch → ValueError; `PairwiseAdapterDelta` with `adapter_a == adapter_b` → ValueError; `pass_rate_delta` out of [-1, 1] → ValueError; `significant_at_alpha_05` vs p_value consistency mismatch → ValueError.
- **`CohortHeatmap.from_comparison` (4 tests)**: 2-adapter happy path; 3-adapter (≥3 columns) happy path; per-task-pass-rate dispatched to correct cell; `as_ascii()` produces ≥3 columns when 3 adapters provided.
- **Pairwise delta computation (3 tests)**: 2 adapters → 1 pairwise delta (key `"<a1>_vs_<a2>"`); 3 adapters → 3 pairwise deltas; pairwise key ordering deterministic.
- **`compute_mann_whitney_u` dispatch (2 tests)**: 2 adapters with known-different pass-rate distributions → `p_value < 0.05`; 2 adapters with identical distributions → `p_value > 0.5`.

Gated by `pytest.importorskip("opentelemetry")` for the MCPLibrary infrastructure dependency (Story 4.4 precedent) + `pytest.importorskip("scipy")` for the Mann-Whitney U math (Story 13.1 precedent).

Plus 3 ImportError-gate tests at NEW `tests/unit/discoverability/test_comparison_extras_gate.py` (per L-2 lesson; NO `importorskip` at module top):
- `test_compare_keyword_raises_import_error_when_advanced_extra_missing` — monkeypatch `_ADVANCED_AVAILABLE = False`, assert the spec-mandated ImportError with `"MCP.Compare Tool Discoverability"` + `"agenteval-advanced"` substring.
- `test_compare_module_importable_without_extra` — `from AgentEval.discoverability.schema import DiscoverabilityComparisonResult` works without scipy/numpy.
- `test_compare_message_contract` — message contains the verbatim install hint.

### AC-13.3.8 — Integration test with 3 stub adapters at `tests/integration/discoverability/test_compare_e2e.py` (NEW)

Per epic L2189 + L-4 lesson: ship 3 stub adapters via `register_adapter()` (mirrors Story 12.3 + Story 7.3 pattern) returning KNOWN-different per-task pass-rate distributions. Assert CONCRETE numerical outcomes:

```python
# Stub returns: stub_a → 1.0 success on all tasks; stub_b → 0.5 success; stub_c → 0.0 success.
result = lib.get_tool_discoverability_comparison(
    mcp_server="echo",
    adapters=["compare_stub_a", "compare_stub_b", "compare_stub_c"],
    tasks=str(TASKS_YAML),
    trials_per_task=10,  # enough for Mann-Whitney to have power
    model="stub",
)

# Per-adapter pass rates.
assert result.per_adapter_results["compare_stub_a"].summary.overall_pass_rate == pytest.approx(1.0)
assert result.per_adapter_results["compare_stub_b"].summary.overall_pass_rate == pytest.approx(0.5)
assert result.per_adapter_results["compare_stub_c"].summary.overall_pass_rate == pytest.approx(0.0)

# Ranking (summary.best_adapter / worst_adapter).
assert result.summary.best_adapter == "compare_stub_a"
assert result.summary.worst_adapter == "compare_stub_c"

# Pairwise significance.
ac_delta = result.cross_adapter_deltas["compare_stub_a_vs_compare_stub_c"]
assert ac_delta.significant_at_alpha_05  # stub_a (all-pass) vs stub_c (all-fail) is significant.

# Heatmap shape: 3 columns, M rows (M = task count).
assert result.heatmap.models == ("compare_stub_a", "compare_stub_b", "compare_stub_c")
assert len(result.heatmap.tasks) == len(YAML_TASKS)
```

### AC-13.3.9 — `MCP.Get Tool Discoverability` refactor (extract helper)

Per AC-13.3.6 the existing `get_tool_discoverability` is refactored to call `_run_single_adapter_discoverability`. ALL Story 4.4's existing tests (50+ unit + 8 integration per `tests/unit/discoverability/` + `tests/integration/discoverability/`) MUST pass unchanged — proves the refactor is behavior-preserving. Test count delta = +18 new (per AC-13.3.7 + AC-13.3.8), no test renames or removals.

### AC-13.3.10 — `docs/contracts/stability-surface.md` registry per L-1 lesson

NEW subsection `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)`:

- `MCP.Compare Tool Discoverability` RF keyword + Python method `MCPLibrary.get_tool_discoverability_comparison` — `provisional` label. Signature stable (mirrors `Get Tool Discoverability` with `adapters: list[str]` replacing `adapter: str`); the `@guarded_fanout` carve-out (DF-13.3-S1) applies identically to DF-4.4-S1.
- `AgentEval.discoverability.schema.DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` frozen dataclasses — `provisional` label. Field set may extend in Phase-2.5 (multi-pairwise correction per DF-13.3-S3).
- `CohortHeatmap.from_comparison` classmethod — `provisional` label. Mirrors `from_discoverability` discipline.
- `[agenteval-advanced]` extra requirement bubble-up — the `MCP.Compare Tool Discoverability` keyword inherits the same ImportError contract as the Story 13.1 `Stat.Mann Whitney U` keyword. ImportError message format is `stable`.

### AC-13.3.11 — Phase-1.5 carry-over catalog UPSTREAM (34th consecutive)

`docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` gain 3 new rows BEFORE invoking `/bmad-code-review`:
- **C89** `DF-13.3-S1` — Phase-2.5: `@guarded_fanout` enforcement on `MCP.Compare Tool Discoverability` (same MCPLibrary architectural gap as C20).
- **C90** `DF-13.3-S2` — Phase-2.5: Real per-adapter MCP-server attachment (gated on C72 + C68/C69/C73/C75).
- **C91** `DF-13.3-S3` — Phase-2.5: Multi-pairwise correction (Bonferroni / Holm) for cross-adapter delta significance.

### AC-13.3.12 — PRD amendment per D-1 (same-commit, fix-the-losing-source-NOW)

`_bmad-output/planning-artifacts/prd.md` L1500 amended:
- **Old:** "Agent Surface Author can compare `ToolDiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>`..."
- **New:** "Agent Surface Author can compare `DiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability adapters=[<adapter_1>, <adapter_2>, ...]` (≥2 required; N=3+ enables ranking across Claude/GPT/Copilot/...) and receive a `DiscoverabilityComparisonResult` with per-adapter task-level results + cross-runtime delta with statistical significance (Mann-Whitney U from Story 13.1) + cohort heatmap data — Phase 2 (Story 13.3; depends on ≥2 fully-shipped Tier-1 runtimes; backwards-compat with the original A/B semantic via a 2-element list)."

Also amend "`ToolDiscoverabilityResult`" typo → "`DiscoverabilityResult`" (the existing FR10a-shipped type; not "Tool" prefix).

### AC-13.3.13 — All-gates pass

- `uv run pytest tests/`: ≥18 new tests + all existing 1846 + 16 pre-existing tests still pass. Net ≥18 added.
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/AgentEval/mcp/ src/AgentEval/discoverability/ src/AgentEval/_heatmap/ tests/unit/discoverability/ tests/integration/discoverability/` clean for Story-13.3 files.
- `uv run mypy src/` clean (≥106 src files).
- libdoc regeneration (per Story 13.2 Codex LOW-1 lesson): `uv run python -m robot.libdoc src/AgentEval docs/keywords/AgentEval.html` produces an updated artifact with the new `MCP.Compare Tool Discoverability` keyword.

### AC-13.3.14 — Sprint-status

`13-3-compare-tool-discoverability-cross-adapter: done` (after review); `last_updated: 2026-06-01`.

## Tasks / Subtasks

- [x] **Task 1: PRD amendment (D-1 + AC-13.3.12)** — `_bmad-output/planning-artifacts/prd.md` L1500 amended per the N-runtime `adapters=[...]` wording + `DiscoverabilityResult` typo fix.
- [x] **Task 2: `src/AgentEval/discoverability/schema.py` extension (AC-13.3.2)** — `DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary` appended with `__post_init__` validators; nan-tolerant `significant_at_alpha_05` consistency check (per scipy identical-samples convention).
- [x] **Task 3: `src/AgentEval/_heatmap/models.py` extension (AC-13.3.3)** — `CohortHeatmap.from_comparison` classmethod added with `TYPE_CHECKING` import.
- [x] **Task 4: `src/AgentEval/discoverability/_internal.py` (AC-13.3.6, NEW)** — `run_single_adapter_discoverability` helper extracted from existing Story 4.4 body; behavior identity verified by Story 4.4's 50+ existing tests passing unchanged.
- [x] **Task 5: `src/AgentEval/mcp/library.py` extension (AC-13.3.1 + AC-13.3.4 + AC-13.3.5)** — `get_tool_discoverability_comparison` method (Python name `get_*` per verb-allowlist; RF name `MCP.Compare Tool Discoverability` per epic); `_ADVANCED_AVAILABLE` gate via `_stats_lib._ADVANCED_AVAILABLE` module-attr read (NOT `from X import Y` which captures stale value across session-wide monkeypatch); existing `get_tool_discoverability` refactored to delegate to the helper.
- [x] **Task 6: `tests/unit/discoverability/test_comparison.py` (AC-13.3.7)** — 16 unit tests covering dataclass validators (7) + heatmap multi-column (4) + pairwise counting (3) + Mann-Whitney significance dispatch (2).
- [x] **Task 7: `tests/unit/discoverability/test_comparison_extras_gate.py` (AC-13.3.7 + L-2)** — 4 ImportError-gate tests, NO module-top `importorskip`; covers schema importability + helper message + keyword raise + arg-validation-precedence.
- [x] **Task 8: `tests/integration/discoverability/test_compare_e2e.py` (AC-13.3.8)** — 3 stub adapters (100% / 50% / 0% pass rates) + CONCRETE numerical assertions per L-4 (ranking + p < 0.05 for a-vs-c + heatmap shape + cost math); + 2 arg-validation tests.
- [x] **Task 9: `docs/contracts/stability-surface.md` (AC-13.3.10)** — `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)` subsection with 5 entries.
- [x] **Task 10: Phase-1.5 carry-over catalog UPSTREAM (34th consecutive)** (AC-13.3.11) — C89 (DF-13.3-S1 @guarded_fanout) + C90 (DF-13.3-S2 per-adapter MCP) + C91 (DF-13.3-S3 Bonferroni correction) added to both `phase-1-5-carry-overs.md` (88 → 91) + `deferred-work.md`.
- [x] **Task 11: All-gates pass** (AC-13.3.13) — `uv run pytest tests/` reports **1874 passed + 16 skipped + 0 failed** (+28 net vs 1846 + 16 Story 13.2 baseline). 22 new tests directly attributable to Story 13.3 (16 unit + 4 gate + 3 integration; the +28 includes a couple of side-fix tests). ruff/format/mypy/license clean. libdoc `docs/keywords/MCPLibrary.html` regenerated with `MCP.Compare Tool Discoverability` keyword.
- [x] **Task 12: Sprint-status flip** (AC-13.3.14) — `13-3-compare-tool-discoverability-cross-adapter: review`; `last_updated: 2026-06-01`.

## Dev Notes

Building on multiple Phase-1 + Phase-2 foundations:
- **Story 4.4** shipped `MCP.Get Tool Discoverability` + `DiscoverabilityResult` + `TaskResult` + `DiscoverabilitySummary` + 50+ unit tests + 8 integration tests + the loader/schema infrastructure. Story 13.3 builds the N-adapter wrapper.
- **Story 13.1** shipped `Stat.Mann Whitney U` keyword + `MannWhitneyResult` dataclass + the `compute_mann_whitney_u` pure helper at `stats/mannwhitney.py` + the `[agenteval-advanced]` extra. Story 13.3 consumes the pure helper directly (NOT the keyword surface — different input shape per D-5).
- **Story 8b.2** shipped `CohortHeatmap` dataclass + `from_discoverability` single-model classmethod + `as_ascii()` / `as_dict()` renderers. Story 13.3 adds the multi-column `from_comparison` classmethod.
- **Story 7.3** + **Story 12.3** established the `register_adapter` stub pattern for integration tests with multiple per-test adapters. Story 13.3 ships 3 stubs (1 more than Story 12.3's coherent-pass/coherent-fail design) to validate ranking across N≥3.

**Key implementation detail — pure helper dispatch (D-5).** `Stat.Mann Whitney U` is the user-facing keyword; it takes `list[KeywordRun]` + a predicate to extract floats. Story 13.3's per-adapter pass-rate input is ALREADY `list[float]` (one per task per adapter). The pure helper `compute_mann_whitney_u(samples_a: list[float], samples_b: list[float]) -> MannWhitneyResult` at `stats/mannwhitney.py` is the correct dispatch target — bypasses the predicate machinery. Document this in the keyword docstring so future maintainers don't try to refactor to "consistently call the keyword surface."

**Key implementation detail — helper extraction (AC-13.3.6).** The existing `MCPLibrary.get_tool_discoverability` body is ~150 LoC with significant complexity (adapter resolution + per-trial dispatch + cost/runtime tracking + DiscoverabilityResult assembly). Extracting `_run_single_adapter_discoverability` to a shared helper:
- Avoids ~150 LoC duplication.
- Provides a clean per-adapter unit-test surface.
- Preserves the existing 50+ Story 4.4 tests unchanged (they call the keyword surface, which delegates to the helper).
- Failure mode: subtle behavior change. **Mitigation:** the existing Story 4.4 tests MUST pass unchanged (verified at AC-13.3.13). If they don't, the refactor introduced a regression and must be fixed BEFORE adding the Compare surface.

**Cross-story lesson application:**
- L-1: stability-surface MUST register the new surface UPSTREAM (verified at AC-13.3.10).
- L-2: extras-gate tests split per Story 13.1 / 13.2 pattern.
- L-3: `@tier(3)` rationale documented (stochastic by tier definition).
- L-4: integration test asserts CONCRETE numerical correctness — known stub pass-rate distributions produce expected ranking + p-value sign.
- L-5: docstring names exact helper path; Browser-Library anchor test.

### Project Structure Notes

- **NO new sub-library directory.** `MCP.Compare Tool Discoverability` ships on the existing `MCPLibrary` per architecture's MCP carve-out.
- **NEW file:** `src/AgentEval/discoverability/_internal.py` (shared helper).
- **NEW test files:** `tests/unit/discoverability/test_comparison.py` + `tests/unit/discoverability/test_comparison_extras_gate.py` + `tests/integration/discoverability/test_compare_e2e.py`.
- **EXTENDED files:** `src/AgentEval/mcp/library.py` (new keyword + helper-call refactor); `src/AgentEval/discoverability/schema.py` (3 new dataclasses); `src/AgentEval/_heatmap/models.py` (new classmethod); `docs/contracts/stability-surface.md` (new subsection); `docs/phase-1-5-carry-overs.md` + `_bmad-output/implementation-artifacts/deferred-work.md` (carry-overs); `_bmad-output/planning-artifacts/prd.md` (FR10b amendment per D-1); `docs/keywords/AgentEval.html` (libdoc regen).

### References

- PRD: `_bmad-output/planning-artifacts/prd.md` L1499 (FR10a — base discoverability shape); L1500 (FR10b — to be amended per D-1 + AC-13.3.12).
- Architecture: `_bmad-output/planning-artifacts/architecture.md` L737 (FR10b → "Phase 2 cross-adapter comparison"); L1300 (`CohortHeatmap` file home at `metrics/types.py` — but actual shipping location is `_heatmap/models.py` per Story 8b.2 — `feedback_full_surface_retro_review` precedent for "architecture-pre-allocated paths get amended when implementation lands").
- Epic: `_bmad-output/planning-artifacts/epics.md` L582-590 (Epic 13 charter); L2177-2189 (Story 13.3 detailed).
- Prior stories: `_bmad-output/implementation-artifacts/4-4-mvp-tool-discoverability-fr10a-single-runtime-discoverability-check.md` (single-adapter foundation); `13-1-advanced-statistical-primitives-behind-agenteval-advanced-extra.md` (`Stat.Mann Whitney U` + pure helper + `[agenteval-advanced]` extra); `13-2-otlp-trace-backend.md` (immediately-prior cross-story upstream lessons).
- Contracts: `docs/contracts/stability-surface.md` (label-scheme + registry); `src/AgentEval/discoverability/schema.py` (existing `DiscoverabilityResult` + `TaskResult`); `src/AgentEval/_heatmap/models.py` (existing `CohortHeatmap` shape).
- Norms: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_spec_vs_ratified_doc_precheck.md` (53rd use); `feedback_carry_over_catalog_gate.md` UPSTREAM (34th); `feedback_cross_story_upstream_lesson_propagation.md` (Story 13.2 → 13.3 same-epic transition); `feedback_listener_hook_api_surface_empirical_check.md` (L-4 empirical numerical verification); `feedback_in_flight_spec_amendment.md` (D-1 PRD amendment in same commit + AC-13.3.5 method-name divergence).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

3 mid-dev catches:
1. **`MannWhitneyResult` nan-p-value**: scipy returns `p_value=nan` when both samples have identical rank distributions (no variance → no test possible). Story 13.1's `MannWhitneyResult.__post_init__` rejected nan; relaxed to accept `nan` or `[0, 1]`. Documented as the scipy convention.
2. **`PairwiseAdapterDelta.significant_at_alpha_05` validator**: `nan < 0.05` evaluates `False` in Python, so the bool field naturally becomes False — but the validator required explicit consistency check. Updated to `(not isnan(p)) and p < 0.05`.
3. **`_ADVANCED_AVAILABLE` read pattern**: function-local `from AgentEval.stats.library import _ADVANCED_AVAILABLE` captured stale value across pytest session-wide module reload. Fixed by reading via `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` (always reads current module attribute).

### Completion Notes List

Story 13.3 dev complete. Phase-2 cross-adapter Tool Discoverability comparison (FR10b) shipped.

- **AC-13.3.1**: `MCP.Compare Tool Discoverability` ships on `MCPLibrary` (file home preserved per architecture L1258; NO new sub-library). Validates ≥2 distinct adapters; ImportError gate at first body line (fail-fast).
- **AC-13.3.2**: 3 new frozen dataclasses with `__post_init__` validators. Cross-consistency invariants checked: `adapters ↔ per_adapter_results.keys()` and `adapters ↔ heatmap.models`.
- **AC-13.3.3**: `CohortHeatmap.from_comparison` builds multi-column heatmap from comparison; supports the multi-column ASCII rendering.
- **AC-13.3.4**: `_ADVANCED_AVAILABLE` gate at module-attr read (not `from X import Y` to handle session-wide reload). Direct ImportError raise with `MCP.Compare Tool Discoverability:` prefix (per spec decision (b)).
- **AC-13.3.5**: Python method `get_tool_discoverability_comparison` (verb-allowlist conformant) + RF name `MCP.Compare Tool Discoverability` preserved.
- **AC-13.3.6**: `run_single_adapter_discoverability` helper extracted to `_internal.py`; existing `get_tool_discoverability` delegates to it. Story 4.4's 50+ existing tests pass unchanged.
- **AC-13.3.7**: 16 unit tests (test_comparison.py) + 4 ImportError-gate tests (test_comparison_extras_gate.py, NO module-top importorskip per L-2 lesson).
- **AC-13.3.8**: 3 integration tests at `test_compare_e2e.py`: end-to-end happy path + 2 arg-validation tests. Concrete numerical assertions per L-4 (pass-rate ranking, p_value sign, heatmap shape, cost math).
- **AC-13.3.9**: refactor verified — Story 4.4's existing tests pass unchanged.
- **AC-13.3.10**: stability-surface registry NEW `### Cross-Adapter Discoverability Surface` subsection with 5 entries.
- **AC-13.3.11**: C89 + C90 + C91 catalogued UPSTREAM (34th consecutive).
- **AC-13.3.12**: PRD L1500 amended per D-1 (N-runtime `adapters=[...]` shape + `DiscoverabilityResult` typo fix).
- **AC-13.3.13**: All gates pass — 1874+16 final, ruff/format/mypy/license clean, libdoc regen.
- **AC-13.3.14**: sprint-status flipped to `review`.

### Cross-story upstream lesson application (Stories 13.1 + 13.2 reviews → Story 13.3)

- **L-1 applied (stability-surface UPSTREAM)**: registered all 5 Story 13.3 surface entries before flipping to review; verified via grep.
- **L-2 applied (extras-gate test split)**: `test_comparison.py` (importorskip) + `test_comparison_extras_gate.py` (NO importorskip) split per canonical pattern.
- **L-3 applied (@tier classification rationale)**: `@tier(3)` documented in keyword docstring as stochastic-by-tier (no FR31a bit-identical guarantee); Story 13.1 HIGH-C seed-required concern moot.
- **L-4 applied (empirical numerical verification)**: integration test asserts CONCRETE outcomes (best=stub_a, worst=stub_c, p<0.05 for max-effect pair, heatmap.models exactly the 3 names).
- **L-5 applied (docstring precision)**: keyword docstring names exact helper path `AgentEval.stats.mannwhitney.compute_mann_whitney_u` + explains the predicate-bypass rationale (input is `list[float]` not `list[KeywordRun]`).

### In-flight spec amendments

1. **AC-13.3.1 `@guarded_fanout` removed**: spec D-7 said `@tier(3) + @guarded_fanout()`. Existing `MCP.Get Tool Discoverability` only has `@tier(3)` because MCPLibrary's host-instance plumbing doesn't carry `_max_cost_usd` (DF-4.4-S1 / C20 carve-out). Adding `@guarded_fanout()` would crash on `self._max_cost_usd` access. Amended in-flight: only `@tier(3)`, document the carve-out in docstring (C89 / DF-13.3-S1 tracks the cross-library fix shared with C20).

2. **AC-13.3.4 module-attr gate read**: spec said `from AgentEval.stats.library import _ADVANCED_AVAILABLE`. Empirically the function-local import captured a stale value across pytest session-wide reload (Story 13.1's `test_advanced_extras_gate.py` reloaded `stats.library` earlier in the session). Amended to `from AgentEval.stats import library as _stats_lib; _stats_lib._ADVANCED_AVAILABLE` for always-fresh attribute read.

3. **AC-13.3.2 `PairwiseAdapterDelta.significant_at_alpha_05` nan-tolerance**: spec required `significant_at_alpha_05 == (p_value < 0.05)` strict equality. scipy returns `p_value=nan` for identical-rank samples. Amended to `(not isnan(p)) and p < 0.05` — equivalent semantics (nan is not-significant).

4. **`MannWhitneyResult.p_value` nan-tolerance** (Story 13.1 side-fix): Story 13.1's validator rejected nan. Relaxed to `isnan(p) or 0.0 <= p <= 1.0` per scipy identical-samples convention. Backwards-compat: real p_values still validated.

### File List

**New files:**
- `src/AgentEval/discoverability/_internal.py` — `run_single_adapter_discoverability` helper.
- `tests/unit/discoverability/test_comparison.py` — 16 unit tests.
- `tests/unit/discoverability/test_comparison_extras_gate.py` — 4 ImportError-gate tests (run in both base + WITH-extras).
- `tests/integration/discoverability/__init__.py` — package marker.
- `tests/integration/discoverability/test_compare_e2e.py` — 3 integration tests.

### 3-Tier Cross-LLM Code Review (2026-06-01) — All HIGH + key MED + addressable LOW applied as v2 patches

Per CLAUDE.md ratified 3-tier review chain. Tier-1 Claude CLI (sonnet + opus) + Tier-2 Codex CLI in parallel. Findings at `_bmad-output/cross-llm-reviews/13-3-{claude-sonnet,claude-opus,codex}-findings.md`.

**Aggregate:** 3 HIGH + 6 MED + 7 LOW raw across 3 reviewers; deduplicated to **3 unique HIGH + 5 unique MED + 5 LOW**. 2-way HIGH agreement on `total_runtime_seconds` MAX bug (Codex HIGH-1 + Opus MED-2 + Sonnet MED-1 — 3-way actually).

**HIGH-A (3-way: Codex HIGH-1 + Opus MED-2 + Sonnet MED-1):** `summary.total_runtime_seconds` = MAX(per-adapter runtimes) under serial execution underreports actual wait time by ~N-1× (Codex empirical probe showed 0.30s reported vs 2.18s actual for N=3). The pre-fix docs+code modeled a parallel-fan-out target but the keyword runs serially. → FIXED: `total_runtime = time.monotonic() - t_start` (measured from keyword entry); docstring updated to clarify per-adapter runtimes remain in `per_adapter_results[adapter].summary.total_runtime_seconds` for cost-attribution. Sonnet MED-1's "dead `_ = t_start`" complaint resolved by the same fix.

**HIGH-B (Codex HIGH-2, empirical probe):** `DiscoverabilityComparisonSummary` accepted impossible best/worst adapters — only verified membership, NOT max/min consistency. Codex probe accepted `best_adapter='b'` when `pass_rate_per_adapter={'a':1.0, 'b':0.0}`. → FIXED: `__post_init__` re-derives `max(pass_rate_per_adapter.values())` + `min(...)` + validates `best_adapter`/`worst_adapter` match. New unit tests `test_comparison_summary_rejects_inconsistent_best_adapter_rate` + `test_comparison_summary_rejects_inconsistent_worst_adapter_rate` cover the fix.

**HIGH-C (Codex HIGH-3 + Opus MED-1, 2-way):** `DiscoverabilityComparisonResult` cross-checked `adapters` vs `per_adapter_results.keys()` + `heatmap.models` but NOT `summary.pass_rate_per_adapter.keys()`. Could ship a result with summary about completely different adapters. → FIXED: 4th cross-consistency check added. New unit test `test_comparison_result_rejects_summary_adapter_mismatch` covers the fix.

**MED-A (Codex MED-1):** Epic L2189 acceptance: "using Mock provider for all adapters to keep costs zero." Integration test stub used `cost_per_call=0.001` + asserted non-zero aggregate cost — epic-acceptance drift. → FIXED: stub default `cost_per_call=0.0`; assertion `total_cost_usd == 0.0`. Docstring on `_make_stub_adapter` cites epic L2189 verbatim.

**MED-B (Sonnet MED-2):** `_internal.py` `t_start` docstring claimed "single anchor across all adapters" semantic that the compare loop does NOT implement (each iteration passes a fresh timer). → FIXED: docstring rewritten to accurately describe per-adapter anchor semantics + the comparison-level wall-clock measurement separately.

**LOW-A (Sonnet LOW-1):** Missing symmetric `worst_adapter` unknown-key validator test. → FIXED: `test_comparison_summary_rejects_unknown_worst_adapter` added.

**LOW-B (Sonnet LOW-2):** L-5 lesson docstring anchor test was spec'd but not implemented. → FIXED: `test_compare_keyword_docstring_anchors` added asserting "Mann-Whitney U" + "Story 13.1" + "FR10b" + "Phase-2" in docstring.

**LOW-C (Opus LOW-1):** PRD FR55 L1583 still had stale `ToolDiscoverabilityResult` type name. → FIXED in same commit.

**Findings deferred:** Opus MED-3 (nan-relaxation in `MannWhitneyResult` has no direct regression test) — partial fix: new `test_comparison_summary_rejects_inconsistent_*` tests exercise nan-tolerance indirectly via `PairwiseAdapterDelta.significant_at_alpha_05` validator. Codex LOW-1 (test-count arithmetic 16+4+3=23, not 22; "50+ tests" actually 20-71 depending on scope) — story-record arithmetic corrected below. Sonnet LOW-3 (registry-cleanup missing) — INCORRECT: `conftest.py:35` already provides autouse `_restore_adapter_registry` covering test_comparison.py. Opus LOW-2 (empty per-task list silently skipped) — acceptable degenerate-case behavior; documented. Opus LOW-3 (redundant local re-import) — cosmetic; ignored.

### Final test count (post-review, accurate per Codex LOW-1)

`uv run pytest tests/`: **1879 passed + 16 skipped + 0 failed** in ~112s. Net new tests directly from Story 13.3:
- `tests/unit/discoverability/test_comparison.py`: **22 tests** (16 initial + 3 post-review for best/worst/cross + 3 post-review for symmetry+docstring+empty).
- `tests/unit/discoverability/test_comparison_extras_gate.py`: **4 tests** (no change).
- `tests/integration/discoverability/test_compare_e2e.py`: **3 tests** (no change).
- Total: **29 net new tests** (pre-review 23 → post-review 29 with 6 added by review fixes).

Story 4.4's existing tests at `tests/unit/discoverability/test_keyword.py` (20 tests) + `tests/unit/discoverability/` total (71 tests including the new comparison ones) pass unchanged — refactor behavior identity preserved.

**Modified files:**
- `src/AgentEval/discoverability/schema.py` — 3 new frozen dataclasses (`DiscoverabilityComparisonResult` + `PairwiseAdapterDelta` + `DiscoverabilityComparisonSummary`) + `TYPE_CHECKING` imports + `__all__` updates + 3 v2 HIGH-fix validator extensions (best/worst rate consistency + summary cross-check).
- `src/AgentEval/_heatmap/models.py` — `CohortHeatmap.from_comparison` classmethod + extended `TYPE_CHECKING` imports.
- `src/AgentEval/mcp/library.py` — `get_tool_discoverability_comparison` method + extras gate + existing `get_tool_discoverability` refactored to delegate.
- `src/AgentEval/stats/types.py` — `MannWhitneyResult.__post_init__` p_value validator relaxed for nan (Story 13.1 side-fix; doc'd as scipy convention).
- `_bmad-output/planning-artifacts/prd.md` — L1500 FR10b amended per D-1 (N-runtime shape + `DiscoverabilityResult` typo fix).
- `docs/contracts/stability-surface.md` — `### Cross-Adapter Discoverability Surface (Phase-2 — FR10b)` subsection.
- `docs/phase-1-5-carry-overs.md` — C89 + C90 + C91 entries + total 88 → 91.
- `_bmad-output/implementation-artifacts/deferred-work.md` — new "Deferred from: story-13.3 dev" section with 3 entries.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `13-3-compare-tool-discoverability-cross-adapter: review`; `last_updated: 2026-06-01`.
- `docs/keywords/MCPLibrary.html` — libdoc regenerated with `MCP.Compare Tool Discoverability` keyword.
- `docs/keywords/AgentEval.html` — libdoc regenerated (no top-level kwarg change but timestamp updated for consistency).
