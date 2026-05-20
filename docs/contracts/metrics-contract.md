# `Metric.*` Keyword Contract — Tool-Call Metrics Library

**Story:** 6.1 — Tool-Call Metrics Library
**Phase-1 stability label:** provisional
**Source-of-truth FRs:** PRD FR19, FR20, FR21, FR22
**Library:** `AgentEval.metrics.library.MetricsLibrary`

## Surface (9 keywords)

| # | Keyword | Input | Return | PRD source |
| --- | --- | --- | --- | --- |
| 1 | `Get Tool Call Count` | `AgentRunResult \| list[AgentRunResult]` | `int` | FR19 |
| 2 | `Get Tool Call Names` | `AgentRunResult \| list[AgentRunResult]` | `list[str]` | FR19 |
| 3 | `Get Tool Hit Rate    expected_tools=<list>` | `AgentRunResult \| list[AgentRunResult]` + `list[str]` | `float` | FR20 |
| 4 | `Get Tool Success Rate` | `AgentRunResult \| list[AgentRunResult]` | `float` | FR20 |
| 5 | `Get Unnecessary Call Rate    expected_tools=<list>` | `AgentRunResult \| list[AgentRunResult]` + `list[str]` | `float` | FR21 |
| 6 | `Get Token Usage` | `AgentRunResult \| list[AgentRunResult]` | `Usage` | FR22 |
| 7 | `Get Latency` | `AgentRunResult \| list[AgentRunResult]` | `float` (ms) | FR22 |
| 8 | `Get Latency P95` | `AgentRunResult \| list[AgentRunResult]` | `float` (ms) | FR22 |
| 9 | `Get Cost Total` | `AgentRunResult \| list[AgentRunResult]` | `float` (USD) | FR22 |

All keywords:
- `@tier(1)` Tier-1 deterministic (no LLM invocation; reads from already-captured data).
- `[Tier 1 — Deterministic]` docstring badge per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- Single-run / multi-trial dispatch via `isinstance(result, list)`.

## Boundary contract per AC-6.1.8

| Input | Keyword | Return |
| --- | --- | --- |
| Empty `list[]` | `Get Tool Call Count` | `0` |
| Empty `list[]` | `Get Tool Call Names` | `[]` |
| Single run with zero tool_calls | `Get Tool Success Rate` | `0.0` (vacuous-truth) |
| Single run with zero tool_calls | `Get Unnecessary Call Rate` | `0.0` (vacuous-truth) |
| `expected_tools=[]` | `Get Tool Hit Rate` | `0.0` (vacuous-truth convention; 0/0 → 0.0 not NaN) |
| Empty `list[]` | `Get Token Usage` | `Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)` |
| Single run with zero tool_calls | `Get Latency` | `result.latency_seconds * 1000` (fallback) |
| Single run with zero tool_calls | `Get Latency P95` | `0.0` |
| Single run with 1 tool_call | `Get Latency P95` | that single `tc.latency_ms` |
| Empty `list[]` | `Get Cost Total` | `0.0` |

## Multi-trial aggregation rules per AC-6.1.1

| Metric | Aggregation rule |
| --- | --- |
| Count | sum per trial |
| Names | union preserving order-of-first-appearance |
| Hit Rate | mean of per-trial hit rates |
| Success Rate | mean of per-trial success rates |
| Unnecessary Call Rate | mean of per-trial unnecessary-call rates |
| Token Usage | sum per field (input, output, cached_input) |
| Latency | **mean of all `tc.latency_ms` across the union of trials** (zero-tc trials contribute `latency_seconds * 1000` as a single sample). Mean-of-means is a known anti-pattern; union-mean is the operator-intuitive default per Story 6.1 implementation choice. |
| Latency P95 | P95 of all `tc.latency_ms` across the union of trials. Uses `statistics.quantiles(method="inclusive")` so the result is clamped to `[min, max]` of observed latencies. |
| Cost Total | sum per trial |

## `IncompleteTraceError` gate per AC-6.1.1 + FR37

**Tool-call-bearing keywords (1-5)** — gate on `mcp_coverage`:

| `mcp_coverage` | `allow_external_mcp_blind` | Outcome |
| --- | --- | --- |
| `hosted_in_process` | any | proceed |
| `subprocess_with_observer` | any | proceed |
| `external_mixed` | `False` (default per FR42) | **raise `IncompleteTraceError`** per FR37 |
| `external_mixed` | `True` (Library kwarg opt-in) | proceed (blind run; result trust degraded) |

**Non-tool-call keywords (6-9)** — `Get Token Usage` / `Get Latency` / `Get Latency P95` / `Get Cost Total` — do NOT gate. Rationale: token counts + latency + cost are provider-reported scalars at adapter `run()` completion; they're observer-independent.

For multi-trial input, the gate fires on the FIRST trial that violates the coverage contract (fail-fast).

## Phase-1 data-source carve-out (DF-6.1-S1 / C46)

Per architecture L677, the idealized design has `Metric.*` keywords read from `_kernel/trace_store` via projection accessors. Phase-1 ships with adapters NOT emitting `chat_span` / `execute_tool_span` per DF-5.5-DOGFOOD-2 / C44 — so trace-store reads would return `[]` for every metric.

**Phase-1 resolution:** keywords read from `AgentRunResult` fields directly, which IS the projection layer above the trace:
- `result.tool_calls` — populated by the `HostedMcpObserver` (Story 5.2) or adapter capture.
- `result.usage` — populated by the adapter at `run()` completion (provider-reported).
- `result.cost_usd` — populated by the adapter (provider-reported).
- `result.latency_seconds` — populated by the adapter (wall-clock).
- `result.metadata.mcp_coverage` — populated by the adapter per ADR-016 D1 trust-floor.

**Phase-1.5 closure:** when DF-5.5-DOGFOOD-2 / C44 lands (adapter span instrumentation), helpers can be re-pointed at `_kernel/trace_store.get_run_spans` / `get_tool_calls` projection accessors without changing the keyword surface contract. The carve-out is documented in `src/AgentEval/metrics/_internal.py` module docstring + tracked as DF-6.1-S1 / C46.

## Stability + change log

- **v1.0 (2026-05-20)**: initial publication. Story 6.1 ships the 9-keyword surface + boundary contract + aggregation rules + Phase-1 data-source carve-out. Provisional stability — surface may evolve as Stories 6.2 (assertions) + 6.3 (Stat.*) consume the same projection helpers from `_internal.py`.
