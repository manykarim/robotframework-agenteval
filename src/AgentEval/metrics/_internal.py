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

"""Internal projection + aggregation helpers for `MetricsLibrary` (Story 6.1).

Per architecture L1291: `_internal.py` houses projection accessors that
read from the trace layer. **Phase-1 data-source carve-out per Story 6.1
D-7 drift fix (DF-6.1-S1 / C46)**: helpers read from `AgentRunResult`
fields directly, NOT from `_kernel/trace_store` spans. Rationale: adapter
span instrumentation is deferred per DF-5.5-DOGFOOD-2 / C44 (Phase-2
work). `AgentRunResult` IS the Phase-1 projection layer above the trace —
`.tool_calls` is populated by the HostedMcpObserver (Story 5.2);
`.usage` / `.cost_usd` / `.latency_seconds` are populated by the
adapter at run completion. When DF-5.5-DOGFOOD-2 lands, helpers can be
re-pointed at `_kernel/trace_store` projection accessors without changing
the keyword surface contract.

Two helper families per metric (9 metrics × 2 = 18 functions):

- `_compute_<metric>(result: AgentRunResult) -> <return>` — single-run.
- `_aggregate_<metric>(results: list[AgentRunResult]) -> <return>` —
  multi-trial aggregation per AC-6.1.1's documented rules.

Pure functions (no class state) so Story 6.3 `Stat.*` can re-use them
without going through the keyword surface.
"""

from __future__ import annotations

import statistics

from AgentEval.metrics.types import LatencyStats
from AgentEval.types import AgentRunResult, Usage


def _latency_stats(latencies: list[float]) -> LatencyStats:
    """Compute `LatencyStats(mean, p95, max)` for the given latency list.

    Story 6.1 code-review 1-way Auditor HIGH-F + Edge-cases MED-7 fix
    2026-05-20: AC-6.1.5 claimed `LatencyStats` is "Used INTERNALLY by
    `_compute_latency_p95` to memoize the percentile computation" but
    pre-edit no caller existed (0-caller violation of
    `feedback_caller_count_check` Epic 5 retro NEW norm). Now both
    `_compute_latency_p95` + `_compute_latency_mean` route through this
    helper when given non-trivial input, so `LatencyStats` is the
    shared computation point. The dataclass IS the typed return for
    any future `Metric.Get Latency Stats` composite keyword surface
    (Phase-2).

    Boundary handling: empty list returns `LatencyStats(0, 0, 0)`;
    single-element returns mean=p95=max=that-value.
    """
    if not latencies:
        return LatencyStats(mean=0.0, p95=0.0, max=0.0)
    if len(latencies) == 1:
        return LatencyStats(mean=latencies[0], p95=latencies[0], max=latencies[0])
    mean = statistics.mean(latencies)
    p95 = statistics.quantiles(latencies, n=100, method="inclusive")[94]
    return LatencyStats(mean=mean, p95=p95, max=max(latencies))


# --------------------------------------------------------------------------- #
# Single-run projection helpers (9)                                           #
# --------------------------------------------------------------------------- #


def _compute_tool_call_count(result: AgentRunResult) -> int:
    """Number of tool calls in the run (per FR19)."""
    return len(result.tool_calls)


def _compute_tool_call_names(result: AgentRunResult) -> list[str]:
    """Chronological list of tool-call names; duplicates preserved (PRD FR19)."""
    return [tc.name for tc in result.tool_calls]


def _compute_tool_hit_rate(result: AgentRunResult, expected: list[str]) -> float:
    """|expected ∩ observed| / |expected| (PRD FR20).

    Per AC-6.1.8 boundary contract: `expected=[]` → 0.0 (vacuous-truth
    convention; avoids ZeroDivisionError + matches "no hits to claim"
    semantic).

    Story 6.1 code-review 1-way Edge-cases HIGH-1 fix 2026-05-20:
    pre-edit iterated `expected` as a list — duplicates in `expected`
    inflated both numerator and denominator (e.g., `expected=["a","a","b"]`
    vs `observed={"a"}` returned 2/3 instead of the set-semantic 1/2).
    Worse: asymmetric with `_compute_unnecessary_call_rate` which DOES
    coerce via `set(expected)`. Now both helpers dedup expected via
    `set()` first — set-theoretic interpretation per PRD FR20's
    `|expected ∩ observed|` notation.
    """
    if not expected:
        return 0.0
    expected_set = set(expected)
    observed = {tc.name for tc in result.tool_calls}
    hits = len(expected_set & observed)
    return hits / len(expected_set)


def _compute_tool_success_rate(result: AgentRunResult) -> float:
    """count(tc.error is None) / len(result.tool_calls); zero-tc → 0.0 (PRD FR20).

    Per AC-6.1.8 boundary contract: zero-tc → 0.0 (vacuous-truth).
    """
    if not result.tool_calls:
        return 0.0
    successes = sum(1 for tc in result.tool_calls if tc.error is None)
    return successes / len(result.tool_calls)


def _compute_unnecessary_call_rate(result: AgentRunResult, expected: list[str]) -> float:
    """count(tc.name ∉ expected) / len(result.tool_calls); zero-tc → 0.0 (PRD FR21).

    Per AC-6.1.8 boundary contract: zero-tc → 0.0.
    """
    if not result.tool_calls:
        return 0.0
    expected_set = set(expected)
    unnecessary = sum(1 for tc in result.tool_calls if tc.name not in expected_set)
    return unnecessary / len(result.tool_calls)


def _compute_token_usage(result: AgentRunResult) -> Usage:
    """Pass-through projection of `result.usage` (PRD FR22).

    Returns the existing `Usage` dataclass; metrics layer doesn't reshape.
    """
    return result.usage


def _compute_latency_mean(result: AgentRunResult) -> float:
    """Mean `tc.latency_ms` (PRD FR22).

    Per AC-6.1.1 + AC-6.1.8 boundary contract: when tool_calls is empty,
    fallback to `result.latency_seconds * 1000` (the run-level wall-clock
    duration). This makes `Get Latency` always-defined while preserving
    the per-turn semantic when tool calls exist.

    Story 6.1 code-review HIGH-F: routes through `_latency_stats` so the
    `LatencyStats` dataclass has a real caller (closes 0-caller gap).
    """
    if not result.tool_calls:
        return result.latency_seconds * 1000.0
    return _latency_stats([tc.latency_ms for tc in result.tool_calls]).mean


def _compute_latency_p95(result: AgentRunResult) -> float:
    """P95 of `tc.latency_ms` (PRD FR22).

    Per AC-6.1.8 boundary contract:
    - 0 tool_calls → 0.0
    - 1 tool_call → that single latency (P95 of a single value is itself)
    - ≥2 tool_calls → `statistics.quantiles(n=100)[94]` (95th percentile
      via linear-interpolation method, which is `statistics`'s default).

    `statistics.quantiles(data, n=100)` requires ≥2 data points so we
    handle the 0-and-1 boundaries explicitly. `method="inclusive"`
    clamps the result to `[min, max]` of the input — matches the
    operator intuition that P95 should not exceed the observed maximum.
    """
    # Story 6.1 code-review HIGH-F: routes through `_latency_stats` so
    # the `LatencyStats` dataclass has a real caller (closes 0-caller gap
    # per `feedback_caller_count_check`). The .p95 field handles all 3
    # boundaries (0 → 0.0, 1 → that value, ≥2 → quantiles).
    return _latency_stats([tc.latency_ms for tc in result.tool_calls]).p95


def _compute_cost_total(result: AgentRunResult) -> float:
    """`result.cost_usd` pass-through (PRD FR22)."""
    return result.cost_usd


# --------------------------------------------------------------------------- #
# Multi-trial aggregation helpers (9)                                         #
# --------------------------------------------------------------------------- #


def _aggregate_tool_call_count(results: list[AgentRunResult]) -> int:
    """Sum tool-call counts across trials (AC-6.1.1)."""
    return sum(_compute_tool_call_count(r) for r in results)


def _aggregate_tool_call_names(results: list[AgentRunResult]) -> list[str]:
    """Union across trials preserving order-of-first-appearance (AC-6.1.1)."""
    seen: dict[str, None] = {}  # dict preserves insertion order
    for r in results:
        for name in _compute_tool_call_names(r):
            if name not in seen:
                seen[name] = None
    return list(seen.keys())


def _aggregate_tool_hit_rate(results: list[AgentRunResult], expected: list[str]) -> float:
    """Mean hit rate across trials (AC-6.1.1)."""
    if not results:
        return 0.0
    return statistics.mean(_compute_tool_hit_rate(r, expected) for r in results)


def _aggregate_tool_success_rate(results: list[AgentRunResult]) -> float:
    """Mean success rate across trials (AC-6.1.1)."""
    if not results:
        return 0.0
    return statistics.mean(_compute_tool_success_rate(r) for r in results)


def _aggregate_unnecessary_call_rate(results: list[AgentRunResult], expected: list[str]) -> float:
    """Mean unnecessary-call rate across trials (AC-6.1.1)."""
    if not results:
        return 0.0
    return statistics.mean(_compute_unnecessary_call_rate(r, expected) for r in results)


def _aggregate_token_usage(results: list[AgentRunResult]) -> Usage:
    """Sum per field across trials (AC-6.1.1).

    Per AC-6.1.8 boundary contract: empty list → `Usage(0, 0, 0)`.
    """
    if not results:
        return Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)
    return Usage(
        input_tokens=sum(r.usage.input_tokens for r in results),
        output_tokens=sum(r.usage.output_tokens for r in results),
        cached_input_tokens=sum(r.usage.cached_input_tokens for r in results),
    )


def _aggregate_latency_mean(results: list[AgentRunResult]) -> float:
    """Mean latency across the union of tool_calls (AC-6.1.1).

    Story 6.1 implementation choice: union-of-tool-calls mean (NOT
    mean-of-per-run-means). Rationale: a run with many tool calls
    contributes more samples to the multi-trial aggregate; per-run-mean
    averaging would over-weight runs with fewer tool calls. Mean-of-
    means is a known statistical anti-pattern; union-then-mean is the
    operator-intuitive default. Runs with zero tool_calls contribute
    their `result.latency_seconds * 1000` fallback as a SINGLE sample
    to the union (preserves the per-run fallback semantic).
    """
    if not results:
        return 0.0
    all_latencies: list[float] = []
    for r in results:
        if r.tool_calls:
            all_latencies.extend(tc.latency_ms for tc in r.tool_calls)
        else:
            all_latencies.append(r.latency_seconds * 1000.0)
    return statistics.mean(all_latencies) if all_latencies else 0.0


def _aggregate_latency_p95(results: list[AgentRunResult]) -> float:
    """P95 across the union of `tc.latency_ms` from all trials (AC-6.1.1).

    Story 6.1 code-review 2-way HIGH-δ fix 2026-05-20 (Blind HIGH-4 +
    Auditor HIGH-E): symmetric with `_aggregate_latency_mean` — zero-tc
    runs contribute `latency_seconds * 1000.0` as a single sample to the
    union (operator-surprising asymmetry pre-fix where mean used the
    fallback but P95 silently skipped it; `[zero_tc, tc=50]` returned
    mean=5025 vs p95=50 which violated the unstated `mean ≤ max(union)`
    invariant). Uses `method="inclusive"` to clamp interpolation within
    `[min, max]` of the union (matches `_compute_latency_p95`).
    """
    all_latencies: list[float] = []
    for r in results:
        if r.tool_calls:
            all_latencies.extend(tc.latency_ms for tc in r.tool_calls)
        else:
            all_latencies.append(r.latency_seconds * 1000.0)
    if not all_latencies:
        return 0.0
    if len(all_latencies) == 1:
        return all_latencies[0]
    return statistics.quantiles(all_latencies, n=100, method="inclusive")[94]


def _aggregate_cost_total(results: list[AgentRunResult]) -> float:
    """Sum costs across trials (AC-6.1.1)."""
    return sum(_compute_cost_total(r) for r in results)
