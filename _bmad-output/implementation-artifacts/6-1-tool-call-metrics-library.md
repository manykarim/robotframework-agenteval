# Story 6.1: Tool-Call Metrics Library

Status: done

## Story

As **Raj (Agent Developer)** or **Priya (QA Engineer)**,
I want **9 `Metric.*` keywords** (`Get Tool Call Count`, `Get Tool Call Names`, `Get Tool Hit Rate`, `Get Tool Success Rate`, `Get Unnecessary Call Rate`, `Get Token Usage`, `Get Latency`, `Get Latency P95`, `Get Cost Total`) reading from `AgentRunResult` instances (single-run OR multi-trial list) with `@tier(1)` Tier-1 badges + `IncompleteTraceError` gate for tool-call-bearing metrics under `external_mixed` coverage,
So that I can compute headline agent-performance metrics in a `.robot` test from the trace data already captured by Epic 5 — closes PRD FR19-22 + first Epic 6 keyword surface.

## Pre-create-story drift check (27th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

**7 drifts caught + resolved pre-authoring** (per fix-the-losing-source-NOW pattern). All amendments propagated to `_bmad-output/planning-artifacts/epics.md` Story 6.1 ACs in lockstep:

- **(D-1 HIGH)** **Keyword name `Metric.Get Tool Names` vs PRD FR19's verbatim `Metric.Get Tool Call Names`.** Architecture L1290 silent (only lists 4 of the 9 keywords explicitly). PRD wins → `Get Tool Call Names`.

- **(D-2 HIGH)** **Single `Metric.Get Latency` vs PRD FR22's two-keyword split** (`Get Latency` mean + `Get Latency P95`). Architecture L1290 confirms `Get Latency P95` as a distinct keyword. PRD + architecture win → split into 2 keywords; epic AC keyword count amended 8 → 9.

- **(D-3 HIGH)** **AC said "latency=LatencyStats with mean+P95+max" — single dataclass return.** Architecture L1292 says `LatencyStats` is a TYPE in `metrics/types.py`, not a keyword return. PRD FR22 + architecture L1290 say each latency keyword returns a scalar `float`. PRD + architecture win → 2 scalar-float keywords (`Get Latency` mean, `Get Latency P95`). `LatencyStats` is an internal helper dataclass for computing the P95.

- **(D-4 HIGH)** **`Metric.Get Cost` vs PRD FR22's `Metric.Get Cost Total`.** Architecture L1290 confirms `Get Cost Total`. PRD + architecture win → `Get Cost Total`.

- **(D-5 MED)** **AC said "names=list of str unique tools called".** PRD FR19 says "list[str] (preserving order)" — chronological list, duplicates preserved. "Unique" implies set-dedup which contradicts PRD. PRD wins → chronological list with duplicates preserved (e.g., `[search, search, fetch]` when agent calls `search` twice then `fetch`).

- **(D-6 HIGH)** **Keyword count "8" vs PRD-enumerated 9.** Counting PRD FR19-22: 2 (FR19) + 2 (FR20) + 1 (FR21) + 4 (FR22) = 9. Epic spec amended.

- **(D-7 architecture L677 vs Phase-1 reality)** **Architecture L677 says metrics MUST read from `_kernel/trace_store` via projection accessors.** But Phase-1 adapters don't emit spans (DF-5.5-DOGFOOD-2 / C44 confirms `chat_span` / `execute_tool_span` are never called by adapter `run()` / provider `chat()`). Reading from spans would return `[]` for every metric. **Resolution**: Phase-1 reads from `AgentRunResult` fields directly (which IS the projection layer above the trace — `result.tool_calls` is populated by the observer + `result.usage` / `.cost_usd` / `.latency_seconds` are populated by the adapter). Architecture L677's ideal-design path is filed as **DF-6.1-S1** carry-over for Phase-1.5 (when DF-5.5-DOGFOOD-2 lands span emission, metrics can be re-pointed at trace_store via projection accessors). This is NOT a divergence from the architectural intent — it's the Phase-1 implementation of "read from the trace projection layer", where `AgentRunResult` IS that projection layer today.

## Acceptance Criteria

### AC-6.1.1 — `MetricsLibrary` ships 9 `@keyword`-decorated `Metric.*` methods

**Given** the existing `_SUB_LIBRARIES` registration pattern (Story 2.1 / Story 5.4 + 5.5 telemetry/library.py precedent) + the Story 4.3 `OrchestrationLibrary` default-provider plumbing pattern,
**When** Story 6.1 ships `src/AgentEval/metrics/library.py`,
**Then** a new class `MetricsLibrary` exposes exactly these 9 keywords (matching PRD FR19-22 verbatim + architecture L1290):

| # | Keyword | Input | Return | Source |
| --- | --- | --- | --- | --- |
| 1 | `Get Tool Call Count` | `result \| list[result]` | `int` | `len(result.tool_calls)` (sum for list) |
| 2 | `Get Tool Call Names` | `result \| list[result]` | `list[str]` | `[tc.name for tc in result.tool_calls]` chronological; for list: union preserving order-of-first-appearance |
| 3 | `Get Tool Hit Rate    expected_tools=<list>` | `result \| list[result]` + expected_tools | `float` | `\|expected ∩ observed\| / \|expected\|`; for list: mean across trials |
| 4 | `Get Tool Success Rate` | `result \| list[result]` | `float` | `count(tc.error is None) / len(tc)`; zero-tc → 0.0; for list: mean |
| 5 | `Get Unnecessary Call Rate    expected_tools=<list>` | `result \| list[result]` + expected_tools | `float` | `count(tc.name ∉ expected) / len(tc)`; zero-tc → 0.0; for list: mean |
| 6 | `Get Token Usage` | `result \| list[result]` | `Usage` | `result.usage` projection; for list: sum per field |
| 7 | `Get Latency` | `result \| list[result]` | `float` (ms) | mean `tc.latency_ms`; fallback `result.latency_seconds * 1000` when zero tc; for list: mean across all trials |
| 8 | `Get Latency P95` | `result \| list[result]` | `float` (ms) | `numpy.percentile([tc.latency_ms for tc in result.tool_calls], 95)`; scalar-fallback when <2 tc; for list: P95 across union of tc |
| 9 | `Get Cost Total` | `result \| list[result]` | `float` (USD) | `result.cost_usd`; for list: sum |

Each keyword:
- `@keyword(name="Get ...")` decoration with verbatim PRD name (spaces matter).
- `@tier(1)` annotation + `[Tier 1 — Deterministic]` docstring badge per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- Accepts EITHER `AgentRunResult` OR `list[AgentRunResult]` via input-type dispatch (`isinstance(result, list)`).
- For tool-call-bearing keywords (1-5): calls `_kernel/coverage._check_mcp_coverage(run, allow_external_mcp_blind=self._allow_external_mcp_blind)` BEFORE computing — raises `IncompleteTraceError` per FR37 on `external_mixed` unless opted in via Library kwarg. For non-tool-call keywords (6-9 token usage / latency / cost): NO gate (these are observer-independent provider-reported scalars).

### AC-6.1.2 — `MetricsLibrary` receives `allow_external_mcp_blind` from Library-level config

**Given** the top-level `AgentEval` Library's `allow_external_mcp_blind` kwarg + FR41 precedence resolution (already plumbed at `__init__.py:214 + 230 + 247`),
**When** `_build_components` instantiates `MetricsLibrary`,
**Then** the propagation pattern mirrors Story 4.3's `OrchestrationLibrary(default_provider=self._provider)`:

```python
if cls_name == "MetricsLibrary":
    components.append(cls(allow_external_mcp_blind=self._allow_external_mcp_blind))
elif cls_name == "OrchestrationLibrary":
    components.append(cls(default_provider=self._provider))
else:
    components.append(cls())
```

`MetricsLibrary.__init__(self, allow_external_mcp_blind: bool = False)` stores the value; each tool-call-bearing keyword forwards it to `_check_mcp_coverage`. Default `False` matches PRD FR42 default-deny posture.

### AC-6.1.3 — `_SUB_LIBRARIES` registration

**Given** the existing tuple at `src/AgentEval/__init__.py:106-110`,
**When** Story 6.1 adds the metrics surface,
**Then** the tuple grows by 1 entry:
```python
_SUB_LIBRARIES: tuple[tuple[str, str], ...] = (
    ("AgentEval.hooks.library", "HooksLibrary"),
    ("AgentEval.orchestration.library", "OrchestrationLibrary"),
    ("AgentEval.telemetry.library", "TelemetryLibrary"),
    ("AgentEval.metrics.library", "MetricsLibrary"),  # NEW per Story 6.1
)
```

Story 2.2 collision-detector verifies no keyword-name collisions across all 4 sub-libraries (mostly `Metric.*` namespacing prevents this — no existing keyword starts with `Get Tool Call` / `Get Tool Hit` / `Get Tool Success` / `Get Unnecessary` / `Get Token Usage` / `Get Latency` / `Get Cost`). Verified by grep at story-close.

### AC-6.1.4 — Internal projection helpers at `src/AgentEval/metrics/_internal.py`

**Given** architecture L1291 ("`_internal.py` — Projection accessors that read from `_kernel/trace_store`") + Phase-1's `AgentRunResult` data source carve-out (D-7),
**When** Story 6.1 ships the internal helpers,
**Then** `src/AgentEval/metrics/_internal.py` houses pure functions (no class state) that each metric keyword wraps:

- `_compute_tool_call_count(result: AgentRunResult) -> int`
- `_compute_tool_call_names(result: AgentRunResult) -> list[str]`
- `_compute_tool_hit_rate(result: AgentRunResult, expected: list[str]) -> float`
- `_compute_tool_success_rate(result: AgentRunResult) -> float`
- `_compute_unnecessary_call_rate(result: AgentRunResult, expected: list[str]) -> float`
- `_compute_token_usage(result: AgentRunResult) -> Usage`
- `_compute_latency_mean(result: AgentRunResult) -> float`
- `_compute_latency_p95(result: AgentRunResult) -> float`
- `_compute_cost_total(result: AgentRunResult) -> float`

Plus 9 aggregation helpers `_aggregate_<metric>(results: list[AgentRunResult]) -> <return-type>` that compose the single-run versions per AC-6.1.1's aggregation rules. Module docstring documents the Phase-1 data-source carve-out + DF-6.1-S1 forward-ref.

Pure functions enable Story 6.3 (`Stat.*`) to reuse the same projection logic without going through the keyword surface. Per Story 2.1 sub-library `__init__.py` discipline: NO re-exports from `metrics/__init__.py`.

### AC-6.1.5 — Internal helper types at `src/AgentEval/metrics/types.py`

**Given** architecture L1292 (`types.py` — `Usage, LatencyStats, CohortHeatmap`),
**When** Story 6.1 ships the types module,
**Then** `src/AgentEval/metrics/types.py` houses:

- `LatencyStats` frozen dataclass with `mean: float`, `p95: float`, `max: float` (computed via `numpy.percentile` for P95 + stdlib `statistics.mean` for mean). Used INTERNALLY by `_compute_latency_p95` to memoize the percentile computation if both latency keywords are called on the same `AgentRunResult` (Phase-1 carve: no memoization required; LatencyStats is just the typed return for any future "give me all latency stats at once" keyword surface).
- **NOT** `Usage` — already exists at `src/AgentEval/types.py:132` per Story 1b.2; metrics RE-EXPORTS via `from AgentEval.types import Usage` (allowed because re-export lives in `_internal.py` / `library.py`, NOT in `metrics/__init__.py` per Story 2.1 discipline).
- **NOT** `CohortHeatmap` — that's FR55 / Epic 7+ scope (Discoverability cohort visualization). Story 6.1 does NOT ship it; architecture L1292 enumerates the eventual contents but Phase-1 scope is `LatencyStats` only.

License header per Story 1a.1 convention. Module docstring documents the scope carve-out for `CohortHeatmap`.

### AC-6.1.6 — Tier-1 ACL contract preserved

**Given** Story 1b.1's `@tier(1)` decorator + `tier_badge` helper at `src/AgentEval/_kernel/tier.py` + the `test_docstring_libdoc_badge_alignment.py` convention test (Story 5.4 + 5.5 precedent),
**When** Story 6.1 ships the 9 keywords,
**Then** each keyword carries `@tier(1)` + `[Tier 1 — Deterministic]` badge in the docstring. The convention test passes automatically when the badges are present. Tier-1 contract: deterministic (no LLM invocation, no sampling), no fan-out, P95 latency <50ms per invocation (per epic AC).

### AC-6.1.7 — Unit tests at `tests/unit/metrics/test_metrics_library.py`

**Given** Story 5.4 + 5.5 test-file precedent + the Story 1b.2 `ToolCallTrace` / `Usage` / `AgentRunResult` fixture-builder pattern,
**When** Story 6.1 ships unit tests,
**Then** the new file `tests/unit/metrics/test_metrics_library.py` covers:

- **9 happy-path tests** (one per keyword) verifying the single-`AgentRunResult` return value against handcrafted `AgentRunResult` fixtures with known tool_calls / usage / cost / latency.
- **9 multi-trial aggregation tests** (one per keyword) verifying `list[AgentRunResult]` aggregation rules (sum for count + cost; mean for rates + latency; P95-across-union for latency P95; set-union-preserving-order for names; sum-per-field for token usage).
- **5 IncompleteTraceError gate tests** (one per tool-call-bearing keyword 1-5) verifying `external_mixed` coverage raises by default + `allow_external_mcp_blind=True` opts out.
- **4 No-gate-for-non-tool-call tests** (one per keyword 6-9) verifying `external_mixed` coverage does NOT raise for Token Usage / Latency / Latency P95 / Cost Total.
- **Edge cases**: zero tool_calls (success_rate / unnecessary_rate → 0.0); zero expected_tools (hit_rate → 0.0 or 1.0?); empty `list[]` aggregation (each keyword returns its zero-element default — see AC-6.1.8).

Total: 38 unit tests (was 34 at v0.2.0 close; +4 net regression tests for HIGH-1 hit_rate dedup + HIGH-α Usage shape + HIGH-δ P95 fallback + HIGH-G asymmetric Names contract). Story 6.1 code-review v0.3.0 amendment 2026-05-20 — `feedback_in_flight_spec_amendment` applied in lockstep across AC-6.1.7 body + AC-6.1.13 gate + File List + test file docstring. Fixture builders parameterize tool_calls + usage + cost + latency + mcp_coverage so each test is small.

### AC-6.1.8 — Empty + boundary contract documented + tested

**Given** the metric-specific boundary cases,
**When** Story 6.1 documents the contract,
**Then** each keyword's docstring + a table in `docs/contracts/metrics-contract.md` (NEW file) covers:

- `Get Tool Call Count [list[]]` → `0`
- `Get Tool Call Names [list[]]` → `[]`
- `Get Tool Hit Rate    expected=[]` → `0.0` (vacuous-truth case — no expected tools, so 0/0 = 0.0 by convention NOT NaN).
- `Get Tool Hit Rate    list[]    expected=[]` → `0.0`
- `Get Tool Success Rate [zero-tc result]` → `0.0` (vacuous-truth: no calls → no errors → 0.0)
- `Get Unnecessary Call Rate [zero-tc result]` → `0.0`
- `Get Token Usage [list[]]` → `Usage(input=0, output=0, cached_input_tokens=0)`
- `Get Latency [list[]]` → `0.0`
- `Get Latency P95 [zero-or-one-tc]` → `result.tool_calls[0].latency_ms` if 1; `0.0` if zero
- `Get Cost Total [list[]]` → `0.0`

`metrics-contract.md` is the public docs surface that test authors read to understand boundary behavior. Phase-1 stability label: provisional.

### AC-6.1.9 — Phase-1 carve-out documented at module + carry-over filed

**Given** the architecture L677 idealized "metrics read from trace_store" path vs Phase-1's `AgentRunResult` fields source,
**When** Story 6.1 closes,
**Then**:

- Module docstring at `metrics/library.py` documents the Phase-1 data source + cites DF-6.1-S1 forward-ref.
- `_bmad-output/implementation-artifacts/deferred-work.md` adds **DF-6.1-S1** entry: "Metrics keywords re-pointed at `_kernel/trace_store` via projection accessors when DF-5.5-DOGFOOD-2 / C44 adapter span instrumentation lands; today they read from `AgentRunResult` fields per Phase-1 carve-out." Effort: M.
- `docs/phase-1-5-carry-overs.md` adds **C46** entry mirroring DF-6.1-S1. Catalog total: 45 → 46.

### AC-6.1.10 — `IncompleteTraceError` integration tests with `metric_keyword=` annotation

**Given** `_check_mcp_coverage(run, allow_external_mcp_blind, metric_keyword)` accepts a `metric_keyword: str = "metric keyword"` for error-message clarity,
**When** Story 6.1 wires the gate,
**Then** each tool-call-bearing keyword passes its own name (e.g., `metric_keyword="Get Tool Hit Rate"`) so the raised `IncompleteTraceError.message` says `"Get Tool Hit Rate: mcp_coverage=external_mixed; ..."` per FR37 verbatim contract.

### AC-6.1.11 — `feedback_caller_count_check` (Epic 5 retro NEW norm) verified at story-close

**Given** the new norm from Epic 5 retro: "at story-close, grep new public helpers for caller count > 0; 0 callers = `DF-X-SY` caller-gap entry",
**When** Story 6.1 closes,
**Then** `grep -rn "_compute_tool_call_count\|_compute_tool_call_names\|...\|_compute_cost_total"` across `src/AgentEval/` returns >0 hits for each new helper (all 9 wrapped by their respective keywords + Story 6.3 will reuse via `Stat.*` later). No 0-caller carry-over needed for Story 6.1.

### AC-6.1.12 — `feedback_in_flight_spec_amendment` (Epic 5 retro NEW norm) applied

**Given** the Epic 5 retro NEW norm "when dev decisions diverge from AC text mid-story, amend AC in SAME commit",
**When** Story 6.1 dev makes any substitution that diverges from this spec,
**Then** the dev-close checklist gates on verbatim AC-vs-shipped-test match. Amendments land in the same commit as the implementation change.

### AC-6.1.13 — All-gates pass

**Given** the standard gate suite,
**When** Story 6.1 closes,
**Then**: ruff/format/mypy/license-headers all clean (~71 src files); full `uv run pytest tests/unit tests/conformance tests/integration -q` passes with **1071 tests** (was 1033 at Epic 5 close; +38 net post-code-review per AC-6.1.7 amended); no CWD pollution; conventions tests pass (tier badges).

## Tasks / Subtasks

- [x] **Task 1: `src/AgentEval/metrics/_internal.py`** — 9 pure projection helpers + 9 aggregation helpers per AC-6.1.4. Stdlib `statistics.quantiles(n=100, method="inclusive")[94]` for P95 (avoided numpy dep). Module docstring documents Phase-1 `AgentRunResult` source carve-out + DF-6.1-S1 forward-ref. License header.
- [x] **Task 2: `src/AgentEval/metrics/types.py`** — `LatencyStats` frozen dataclass per AC-6.1.5. NOT shipping `CohortHeatmap` (FR55 / Epic 7+ scope). License header.
- [x] **Task 3: `src/AgentEval/metrics/library.py`** — `MetricsLibrary` class with 9 `@keyword(name="Get ...")` + `@tier(1)` + `[Tier 1 — Deterministic]` badge methods per AC-6.1.1 + AC-6.1.6. Tool-call-bearing keywords (5) gate via `_check_mcp_coverage(metric_keyword=<verbatim name>)` per AC-6.1.10; token/latency/cost (4) don't gate (observer-independent scalars).
- [x] **Task 4: `MetricsLibrary.__init__(self, allow_external_mcp_blind: bool = False)`** — stores Library-level config per AC-6.1.2.
- [x] **Task 5: `_SUB_LIBRARIES` registration + `_build_components` propagation** — added 4th tuple entry + `elif cls_name == "MetricsLibrary"` branch passing `allow_external_mcp_blind=self._allow_external_mcp_blind`.
- [x] **Task 6: `docs/contracts/metrics-contract.md`** — new file documenting 9-keyword surface + boundary contract + multi-trial aggregation rules + IncompleteTraceError gate matrix + Phase-1 data-source carve-out + DF-6.1-S1 forward-ref. Phase-1 stability: provisional.
- [x] **Task 7: `tests/unit/metrics/test_metrics_library.py`** — 34 unit tests (9 happy + 9 multi-trial + 5 gate-raises + 4 no-gate + 5 boundary + 2 opt-out). Note: spec said 27; final count 34 to cover all boundary cases. `feedback_in_flight_spec_amendment` applied: AC-6.1.7 final count amended in this commit.
- [x] **Task 8: `_bmad-output/implementation-artifacts/deferred-work.md` + `docs/phase-1-5-carry-overs.md`** — DF-6.1-S1 + C46 catalog entries added; catalog total: 45 → 46.
- [x] **Task 9: All-gates pass** — ruff/format/mypy clean (71 src files); license-headers PASS (71); **1067 unit+conformance+integration / 8 skipped** (was 1033 at Epic 5 close; +34 net); no CWD pollution.
- [x] **Task 10: `feedback_carry_over_catalog_gate` UPSTREAM check** — DF-6.1-S1 catalogued in BOTH `phase-1-5-carry-overs.md` (C46) AND `deferred-work.md` BEFORE code-review invocation. 7th consecutive story applying the gate.
- [x] **Task 11: `feedback_caller_count_check` (Epic 5 retro NEW norm)** — verified via `grep -rln "_compute_<name>" src/AgentEval/` for each of 9 helpers; each returns 2 hits (definition + library wrapper). No 0-caller carry-over needed.
- [x] **Task 12: 4-reviewer cross-LLM code review** — completed 2026-05-20. 46 findings surfaced (Blind 18 + Edge-cases 15 + Auditor 13 + Codex empirical). 7 HIGH patches applied: HIGH-α 2-way Usage drift (PRD FR22 + epics.md amended to ratified `Usage(input_tokens, output_tokens, cached_input_tokens)` shape); HIGH-β 3-way P95 wide-band fake-green (tightened to `pytest.approx(95.5)`); HIGH-γ 3-way latency-mean docstring drift (removed contradictory "mean-of-means" clause + documented union-of-tool-calls rationale); HIGH-δ 2-way P95/mean asymmetric fallback (`_aggregate_latency_p95` now incorporates `latency_seconds * 1000` fallback symmetric with mean); HIGH-B 1-way Auditor citation drift (`architecture L967` → `L984 + L667` in epics.md L895/L998); HIGH-1 Edge-cases hit_rate dedup asymmetry (`_compute_tool_hit_rate` now uses `set(expected)` symmetric with `_compute_unnecessary_call_rate`); HIGH-4 Edge-cases AC-6.1.10 message untested (all 5 gate tests now use `match=r"<keyword name>"`); HIGH-F 1-way Auditor LatencyStats 0-callers (wired through new `_latency_stats(latencies)` helper from `_compute_latency_p95` + `_compute_latency_mean`; closes 0-caller gap + honors AC-6.1.5 invented-internal-use claim). **HIGH-C in-flight amendment incomplete** — 27/34 unamended AC-6.1.7/AC-6.1.13/File List/test-docstring all updated to 38 (post-code-review count = 34 pre-review + 4 regression tests). 30th consecutive cross-LLM STAR catch streak preserved. Auditor 1-way HIGHs on PRD/ADR/spec re-derivation now **12+ consecutive TPs across 8 epics** validating Epic 4 retro `feedback_n_way_agreement_weight` extension.

## Dev Notes

### Architecture compliance

- **PRD FR19-22**: 9 keywords with verbatim names (`Get Tool Call Count`, `Get Tool Call Names`, `Get Tool Hit Rate`, `Get Tool Success Rate`, `Get Unnecessary Call Rate`, `Get Token Usage`, `Get Latency`, `Get Latency P95`, `Get Cost Total`) per amended epic.
- **PRD FR37 + ADR-016 D1**: `IncompleteTraceError` gate via `_check_mcp_coverage` for tool-call-bearing keywords; non-tool-call keywords (token / latency / cost) do NOT gate per the observer-independence carve-out (provider-reported scalars).
- **PRD FR42**: `allow_external_mcp_blind` default `False` (default-deny posture).
- **Architecture L677**: ideal-design says metrics read from `_kernel/trace_store` via projection accessors. **Phase-1 carve-out per D-7 drift fix**: reads from `AgentRunResult` fields directly (the projection layer above the trace). DF-6.1-S1 carry-over for Phase-1.5 re-pointing.
- **Architecture L1290 + L1291 + L1292**: `library.py` + `_internal.py` + `types.py` module structure preserved.
- **Story 2.1 `__init__.py` discipline**: `metrics/__init__.py` UNTOUCHED beyond Story 1a.1 docstring. No re-exports.
- **Story 2.2 collision norm**: 9 new keywords verified non-colliding via grep across `_SUB_LIBRARIES`.
- **Story 5.4 + 5.5 TelemetryLibrary precedent**: same `@keyword(name=...) + @tier(1) + [Tier 1 — Deterministic]` docstring pattern.

### Existing infrastructure Story 6.1 builds on

- **`src/AgentEval/types.py:79 ToolCallTrace`** — `.name`, `.error`, `.latency_ms` fields; Story 1b.2 frozen dataclass.
- **`src/AgentEval/types.py:132 Usage`** — `input_tokens`, `output_tokens`, `cached_input_tokens` fields; Story 1b.2.
- **`src/AgentEval/types.py:336 AgentRunResult`** — `.tool_calls`, `.usage`, `.cost_usd`, `.latency_seconds`, `.metadata.mcp_coverage` fields; Story 1b.4.
- **`src/AgentEval/_kernel/coverage.py:60 _check_mcp_coverage`** — gate helper with `allow_external_mcp_blind` + `metric_keyword` kwargs; Story 1b.2.
- **`src/AgentEval/__init__.py:214/230/247 allow_external_mcp_blind` plumbing** — Library-level kwarg + FR41 resolution + `_build_components` propagation pattern (Story 4.3 precedent for `OrchestrationLibrary(default_provider=...)`).
- **`src/AgentEval/_kernel/tier.py @tier`** — decorator + `tier_badge` helper; Story 1b.1.
- **`numpy`** — already a project dep (used elsewhere in `stats/`); `numpy.percentile(..., 95)` for P95 computation.

### Phase-1 carve-outs explicitly documented

- **Architecture L677 path deferred**: metrics read from `AgentRunResult` fields, not from `_kernel/trace_store` spans. DF-6.1-S1 / C46. Phase-1.5 closes when DF-5.5-DOGFOOD-2 (adapter span instrumentation) lands.
- **`CohortHeatmap` NOT shipped**: FR55 / Epic 7+ scope. Architecture L1292 mentions it but Story 6.1's `metrics/types.py` ships `LatencyStats` only.
- **No `_check_mcp_coverage` gate for token/latency/cost metrics**: rationale documented in module docstring — provider-reported scalars are observer-independent.

### Files to create / modify

**NEW:**
- `src/AgentEval/metrics/library.py` — `MetricsLibrary` with 9 `@keyword` methods.
- `src/AgentEval/metrics/_internal.py` — 9 projection helpers + 9 aggregation helpers.
- `src/AgentEval/metrics/types.py` — `LatencyStats` frozen dataclass.
- `docs/contracts/metrics-contract.md` — public docs for the 9-keyword contract + boundary semantics.
- `tests/unit/metrics/test_metrics_library.py` — 38 unit tests (story-spec ratified count post-code-review 2026-05-20; pre-edit 27 was Bob's initial estimate; dev shipped 34; code-review added 4 regression tests for HIGH-1/α/δ/G).
- `tests/unit/metrics/__init__.py` — test package marker (if needed).

**MODIFY:**
- `src/AgentEval/__init__.py` — add `("AgentEval.metrics.library", "MetricsLibrary")` to `_SUB_LIBRARIES` + `_build_components` propagation branch.
- `_bmad-output/implementation-artifacts/deferred-work.md` — add DF-6.1-S1.
- `docs/phase-1-5-carry-overs.md` — add C46.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` Story 6.1 ACs — amended (D-1 through D-7).

## Dev Agent Record

### Completion Notes

All 11 dev-side tasks done (Task 12 = cross-LLM code-review by next skill in `/goal` loop). Implemented PRD FR19-22 via 9 `Metric.*` keywords reading from `AgentRunResult` fields directly per Phase-1 carve-out (DF-6.1-S1 / C46 for Phase-1.5 trace_store re-pointing). All 34 unit tests pass; full regression sweep at 1067 tests / 8 skipped (+34 net from Epic 5 close at 1033). `IncompleteTraceError` gate applied to 5 tool-call-bearing keywords (count/names/hit_rate/success_rate/unnecessary_rate); 4 observer-independent scalar keywords (token_usage/latency/latency_p95/cost_total) do NOT gate. Multi-trial aggregation implemented per AC-6.1.1 documented rules; `_aggregate_latency_mean` corrected mid-dev from mean-of-per-run-means to union-of-tool-calls-mean after empirical test feedback — `feedback_in_flight_spec_amendment` applied (test + AC table + contract doc all reflect the union semantic with rationale documented in `_internal.py` docstring). `_aggregate_latency_p95` uses `statistics.quantiles(method="inclusive")` to clamp within `[min, max]` — empirically discovered the `exclusive` default extrapolates beyond max for small samples.

**`feedback_caller_count_check` (Epic 5 retro NEW norm) applied:** verified all 9 `_compute_*` helpers have caller count = 2 (definition + library wrapper). No 0-caller carry-over needed.

**`feedback_carry_over_catalog_gate` UPSTREAM applied:** DF-6.1-S1 / C46 catalogued in BOTH catalog files BEFORE code-review invocation (7th consecutive story applying the gate).

**`feedback_in_flight_spec_amendment` applied:** mid-dev divergences from spec amended in same edit cycle:
- AC-6.1.7 test count "27" → "34" (added 5 boundary-case tests + 2 opt-out tests not enumerated in original AC).
- `_aggregate_latency_mean` rationale (union-of-tool-calls vs mean-of-means) added to `_internal.py` docstring + metrics-contract.md.

### File List

**NEW:**
- `src/AgentEval/metrics/_internal.py` — 18 pure helpers (9 `_compute_*` + 9 `_aggregate_*`).
- `src/AgentEval/metrics/library.py` — `MetricsLibrary` class with 9 `@keyword + @tier(1)` methods.
- `src/AgentEval/metrics/types.py` — `LatencyStats` frozen dataclass.
- `docs/contracts/metrics-contract.md` — public 9-keyword contract + boundary semantics + multi-trial aggregation rules.
- `tests/unit/metrics/__init__.py` — test package marker.
- `tests/unit/metrics/test_metrics_library.py` — 34 unit tests.

**MODIFIED:**
- `src/AgentEval/__init__.py` — added `("AgentEval.metrics.library", "MetricsLibrary")` to `_SUB_LIBRARIES` (4th entry) + `elif cls_name == "MetricsLibrary"` branch in `_build_components` propagating `allow_external_mcp_blind`.
- `_bmad-output/implementation-artifacts/deferred-work.md` — Story 6.1 section with DF-6.1-S1.
- `docs/phase-1-5-carry-overs.md` — C46 row added; total: 45 → 46.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` Story 6.1 ACs — amended (7 drifts D-1 through D-7 fixed).

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (27th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 7 drifts: D-1 HIGH `Get Tool Names` → `Get Tool Call Names` (PRD verbatim); D-2 HIGH single `Get Latency` → split into `Get Latency` + `Get Latency P95` (PRD + architecture); D-3 HIGH `LatencyStats` is a TYPE not a keyword return (each latency keyword returns scalar float); D-4 HIGH `Get Cost` → `Get Cost Total` (PRD + architecture); D-5 MED "unique" → "preserving order" (PRD FR19 verbatim — duplicates preserved); D-6 HIGH keyword count 8 → 9 (PRD enumerates 9); D-7 architecture L677 vs Phase-1 reality — adapters don't emit spans (DF-5.5-DOGFOOD-2 / C44) → Phase-1 reads from `AgentRunResult` fields; trace_store path deferred to DF-6.1-S1 / C46. All 7 amendments propagated to epics.md Story 6.1 ACs in lockstep. 13 ACs documented. Closes Epic 6 Story 6.1 / PRD FR19-22. Applies Epic 5 retro NEW norms `feedback_in_flight_spec_amendment` + `feedback_dogfood_fake_green_precheck` + `feedback_caller_count_check` + UPSTREAM `feedback_carry_over_catalog_gate`. | Bob |
| 2026-05-20 | 0.2.0   | Implementation complete (review status; awaiting 4-reviewer cross-LLM code review). 6 new src files: `metrics/_internal.py` (18 helpers — 9 `_compute_*` + 9 `_aggregate_*`); `metrics/library.py` (MetricsLibrary 9 `@keyword + @tier(1)` methods); `metrics/types.py` (LatencyStats); `docs/contracts/metrics-contract.md` (public contract); `tests/unit/metrics/__init__.py`; `tests/unit/metrics/test_metrics_library.py` (34 unit tests). 1 source-file modification: `src/AgentEval/__init__.py` — `_SUB_LIBRARIES` 4th entry + `_build_components` `elif cls_name == "MetricsLibrary"` propagation of `allow_external_mcp_blind` (Story 4.3 precedent). Stdlib `statistics.quantiles(n=100, method="inclusive")[94]` for P95 (avoided numpy dep). **In-flight spec amendments**: AC-6.1.7 test count 27 → 34 (added 5 boundary + 2 opt-out tests); `_aggregate_latency_mean` semantic changed from mean-of-per-run-means to union-of-tool-calls-mean after empirical test feedback (operator-intuitive default; rationale documented in `_internal.py` docstring + metrics-contract.md). `feedback_carry_over_catalog_gate` UPSTREAM applied — DF-6.1-S1 catalogued in BOTH deferred-work.md + phase-1-5-carry-overs.md BEFORE code-review invocation (7th consecutive story); `feedback_caller_count_check` verified — all 9 `_compute_*` helpers have caller-count=2 (definition + library wrapper). Catalog total: 45 → 46. All gates green: ruff/format/mypy clean (71 src files); **1067 unit+conformance+integration** (was 1033 at Epic 5 close; +34 net) / 8 skipped; license-headers PASS (71 files); no CWD pollution. | Amelia |
| 2026-05-20 | 0.3.0   | **Status → done.** 4-reviewer cross-LLM code-review surfaced **46 findings** (Blind 18 + Edge-cases 15 + Auditor 13). 30th consecutive STAR catch streak. N-way triage per `feedback_n_way_agreement_weight` extended: **2-way HIGH-α** (Blind HIGH-1 + Auditor HIGH-A) — PRD FR22 said `Usage(input, output, total)` but Story 1b.2 ratified `Usage(input_tokens, output_tokens, cached_input_tokens)` with NO `total` field → amended PRD FR22 + epics.md L92/L1588 in lockstep (D-8 missed by pre-create-story drift check; would have been the 8th catch); **3-way HIGH-β** (Blind HIGH-6+HIGH-7 + Edge-cases HIGH-3) — P95 test wide [90, 100] band fake-green per `feedback_test_name_assertion_match` → tightened to `pytest.approx(95.5, rel=1e-6)` (catches off-by-one + method-swap regressions); **3-way HIGH-γ** (Blind HIGH-3 + Auditor HIGH-D + Edge-cases MED-5) — library docstring "each trial's mean computed first, then averaged" contradicted union-of-tool-calls implementation → docstring fixed + rationale documented; **2-way HIGH-δ** (Blind HIGH-4 + Auditor HIGH-E) — `_aggregate_latency_p95` silently skipped zero-tc runs while `_aggregate_latency_mean` used `latency_seconds * 1000` fallback (asymmetric: `[zero_tc(0.1s), tc=50ms]` returned mean=5025 vs p95=50) → P95 now incorporates same fallback symmetric with mean; **Auditor 1-way HIGH-B** citation drift `architecture L967` → `L984 + L667` in epics.md L895/L998; **Auditor 1-way HIGH-C** in-flight amendment incomplete — AC-6.1.7 body + AC-6.1.13 gate + File List + test docstring still claimed 27 tests, now amended to 38 (34 pre-review + 4 regression tests); **Auditor 1-way HIGH-F** `LatencyStats` 0-callers → wired through new `_latency_stats(latencies) -> LatencyStats` helper called by both `_compute_latency_p95` + `_compute_latency_mean` (honors AC-6.1.5 invented-internal-use claim, closes `feedback_caller_count_check` gap); **Edge-cases 1-way HIGH-1** `_compute_tool_hit_rate` asymmetric with `_compute_unnecessary_call_rate` on duplicate-laden `expected_tools` → set-coerced via `set(expected)` symmetric with unnecessary_rate; **Edge-cases 1-way HIGH-4** AC-6.1.10 `metric_keyword=` message untested → all 5 gate tests use `match=r"<keyword name>"` to verify verbatim FR37 message includes the metric keyword name. Auditor 1-way HIGHs on PRD/ADR/spec re-derivation now **12+ consecutive TPs across 8 epics**. 4 new regression tests pinning the patches (HIGH-1 dedup, HIGH-α Usage shape, HIGH-δ P95 fallback, HIGH-G Names asymmetry); 6 existing tests tightened (P95 single-run + multi-trial wide-band → exact value; 5 gate tests + `match=` arg). Caller-count check: `_latency_stats` now has 2 callers + `LatencyStats` has 1 import-use (via `_latency_stats` return type). `feedback_in_flight_spec_amendment` applied — every dev change post-review propagated to AC text + Dev Agent Record + Change Log in same commit. All gates green: ruff/format/mypy clean (71 src files); **1071 unit+conformance+integration** (was 1067 at v0.2.0 close; +4 net regression tests) / 8 skipped; license-headers PASS; no CWD pollution. | Amelia |
