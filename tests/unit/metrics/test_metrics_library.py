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

"""Unit tests for `MetricsLibrary` (Story 6.1 AC-6.1.7).

38 tests post-code-review 2026-05-20 covering:
- 9 happy-path tests (single-run keyword returns).
- 9 multi-trial aggregation tests (list[AgentRunResult] returns).
- 5 IncompleteTraceError gate tests (tool-call-bearing keywords on
  external_mixed coverage with default `allow_external_mcp_blind=False`);
  each verifies `metric_keyword=` propagates verbatim into error message
  per AC-6.1.10 (Edge-cases HIGH-4 fix).
- 4 no-gate-for-non-tool-call tests (token/latency/cost ignore the gate).
- 5 boundary tests (per AC-6.1.8).
- 2 opt-out tests (`allow_external_mcp_blind=True`).
- 4 code-review regression tests (HIGH-1 hit_rate dedup; HIGH-α Usage
  ratified shape; HIGH-δ P95 fallback symmetry; HIGH-G Names dedup
  asymmetry pinned).
"""

from __future__ import annotations

import pytest

from AgentEval.errors import IncompleteTraceError
from AgentEval.metrics.library import MetricsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def _trace(
    name: str,
    *,
    error: str | None = None,
    latency_ms: float = 10.0,
    sequence_index: int = 0,
) -> ToolCallTrace:
    return ToolCallTrace(
        name=name,
        args={},
        result=None if error else "ok",
        error=error,
        latency_ms=latency_ms,
        source="hosted_mcp",
        gen_ai_tool_call_id=f"t-{sequence_index}",
        sequence_index=sequence_index,
    )


def _result(
    tool_calls: list[ToolCallTrace] | None = None,
    *,
    usage: Usage | None = None,
    cost_usd: float = 0.001,
    latency_seconds: float = 0.05,
    mcp_coverage: str = "hosted_in_process",
) -> AgentRunResult:
    return AgentRunResult(
        response_text="ok",
        tool_calls=tool_calls or [],
        usage=usage or Usage(input_tokens=10, output_tokens=20),
        metadata=AgentRunMetadata(
            completeness="complete",
            mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
        ),
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        trace_id="t-" + "0" * 30,
    )


# --------------------------------------------------------------------------- #
# 9 happy-path single-run tests (AC-6.1.1)                                    #
# --------------------------------------------------------------------------- #


def test_get_tool_call_count_single_run() -> None:
    lib = MetricsLibrary()
    result = _result([_trace("search"), _trace("fetch", sequence_index=1)])
    assert lib.get_tool_call_count(result) == 2


def test_get_tool_call_names_single_run_preserves_order_with_duplicates() -> None:
    """PRD FR19 verbatim: list[str] preserving order; duplicates preserved."""
    lib = MetricsLibrary()
    result = _result(
        [
            _trace("search", sequence_index=0),
            _trace("search", sequence_index=1),
            _trace("fetch", sequence_index=2),
        ]
    )
    assert lib.get_tool_call_names(result) == ["search", "search", "fetch"]


def test_get_tool_hit_rate_single_run() -> None:
    """Hit rate = |expected ∩ observed| / |expected|."""
    lib = MetricsLibrary()
    result = _result([_trace("search"), _trace("fetch", sequence_index=1)])
    # Expected: [search, summarize]. Observed has search (hit) + fetch (extra).
    # Hit count = 1 (search); expected = 2 → 0.5.
    assert lib.get_tool_hit_rate(result, expected_tools=["search", "summarize"]) == 0.5


def test_get_tool_success_rate_single_run() -> None:
    """Success rate = non-error / total."""
    lib = MetricsLibrary()
    result = _result(
        [
            _trace("a"),
            _trace("b", error="oops", sequence_index=1),
            _trace("c", sequence_index=2),
        ]
    )
    # 2/3 successful.
    assert lib.get_tool_success_rate(result) == pytest.approx(2 / 3)


def test_get_unnecessary_call_rate_single_run() -> None:
    """Unnecessary rate = calls not in expected / total."""
    lib = MetricsLibrary()
    result = _result(
        [
            _trace("search"),
            _trace("extra", sequence_index=1),
            _trace("search", sequence_index=2),
        ]
    )
    # 1/3 not in expected.
    assert lib.get_unnecessary_call_rate(result, expected_tools=["search"]) == pytest.approx(1 / 3)


def test_get_token_usage_single_run() -> None:
    lib = MetricsLibrary()
    result = _result(usage=Usage(input_tokens=100, output_tokens=200, cached_input_tokens=50))
    usage = lib.get_token_usage(result)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 200
    assert usage.cached_input_tokens == 50


def test_get_latency_single_run_mean_tool_call_latencies() -> None:
    """Mean of tool_call.latency_ms when tool_calls non-empty."""
    lib = MetricsLibrary()
    result = _result(
        [
            _trace("a", latency_ms=10.0),
            _trace("b", latency_ms=30.0, sequence_index=1),
        ]
    )
    assert lib.get_latency(result) == pytest.approx(20.0)


def test_get_latency_single_run_fallback_to_run_latency_when_no_tool_calls() -> None:
    """Empty tool_calls → fallback to result.latency_seconds * 1000."""
    lib = MetricsLibrary()
    result = _result([], latency_seconds=0.5)
    assert lib.get_latency(result) == pytest.approx(500.0)


def test_get_latency_p95_single_run() -> None:
    """P95 of tool_call latencies for ≥2 tool calls — exact value (Story 6.1
    code-review 3-way HIGH-β fix 2026-05-20: Blind HIGH-6+HIGH-7 + Edge-cases
    HIGH-3 caught the wide [90, 100] tolerance as fake-green per
    `feedback_test_name_assertion_match` — would pass even with off-by-one
    in the percentile index or wrong `method=` swap).
    """
    lib = MetricsLibrary()
    # 10 latencies [10, 20, ..., 100] → statistics.quantiles(n=100, method='inclusive')[94] = 95.5
    # (linear-interpolation 95th percentile). Pinning the exact value catches
    # off-by-one + method-swap regressions.
    result = _result([_trace(f"t{i}", latency_ms=float(i * 10), sequence_index=i) for i in range(1, 11)])
    p95 = lib.get_latency_p95(result)
    assert p95 == pytest.approx(95.5, rel=1e-6)


def test_get_cost_total_single_run() -> None:
    lib = MetricsLibrary()
    result = _result(cost_usd=0.025)
    assert lib.get_cost_total(result) == pytest.approx(0.025)


# --------------------------------------------------------------------------- #
# 9 multi-trial aggregation tests (AC-6.1.1)                                  #
# --------------------------------------------------------------------------- #


def test_get_tool_call_count_multi_trial_sums() -> None:
    lib = MetricsLibrary()
    runs = [
        _result([_trace("a"), _trace("b", sequence_index=1)]),
        _result([_trace("c")]),
    ]
    assert lib.get_tool_call_count(runs) == 3


def test_get_tool_call_names_multi_trial_union_preserves_first_appearance_order() -> None:
    """AC-6.1.1 aggregation: union preserving order-of-first-appearance."""
    lib = MetricsLibrary()
    runs = [
        _result([_trace("search"), _trace("fetch", sequence_index=1)]),
        _result([_trace("fetch"), _trace("summarize", sequence_index=1)]),
    ]
    assert lib.get_tool_call_names(runs) == ["search", "fetch", "summarize"]


def test_get_tool_hit_rate_multi_trial_mean() -> None:
    lib = MetricsLibrary()
    runs = [
        _result([_trace("search")]),  # hit rate vs [search, summarize] = 0.5
        _result([_trace("search"), _trace("summarize", sequence_index=1)]),  # 1.0
    ]
    # Mean of 0.5 + 1.0 = 0.75.
    assert lib.get_tool_hit_rate(runs, expected_tools=["search", "summarize"]) == pytest.approx(0.75)


def test_get_tool_success_rate_multi_trial_mean() -> None:
    lib = MetricsLibrary()
    runs = [
        _result([_trace("a"), _trace("b", error="oops", sequence_index=1)]),  # 0.5
        _result([_trace("c"), _trace("d", sequence_index=1)]),  # 1.0
    ]
    assert lib.get_tool_success_rate(runs) == pytest.approx(0.75)


def test_get_unnecessary_call_rate_multi_trial_mean() -> None:
    lib = MetricsLibrary()
    runs = [
        _result([_trace("search"), _trace("extra", sequence_index=1)]),  # 0.5
        _result([_trace("search")]),  # 0.0
    ]
    assert lib.get_unnecessary_call_rate(runs, expected_tools=["search"]) == pytest.approx(0.25)


def test_get_token_usage_multi_trial_sums_per_field() -> None:
    lib = MetricsLibrary()
    runs = [
        _result(usage=Usage(input_tokens=10, output_tokens=20, cached_input_tokens=5)),
        _result(usage=Usage(input_tokens=15, output_tokens=25, cached_input_tokens=0)),
    ]
    usage = lib.get_token_usage(runs)
    assert usage.input_tokens == 25
    assert usage.output_tokens == 45
    assert usage.cached_input_tokens == 5


def test_get_latency_multi_trial_mean_across_all_tool_calls() -> None:
    lib = MetricsLibrary()
    runs = [
        _result([_trace("a", latency_ms=10.0), _trace("b", latency_ms=20.0, sequence_index=1)]),
        _result([_trace("c", latency_ms=30.0)]),
    ]
    # Mean of [10, 20, 30] = 20.0
    assert lib.get_latency(runs) == pytest.approx(20.0)


def test_get_latency_p95_multi_trial_p95_across_union() -> None:
    """Story 6.1 code-review 3-way HIGH-β fix 2026-05-20: tightened from
    wide [90, 100] band to exact value pin.
    """
    lib = MetricsLibrary()
    runs = [
        _result([_trace(f"a{i}", latency_ms=float(i * 10), sequence_index=i) for i in range(1, 6)]),
        _result([_trace(f"b{i}", latency_ms=float(i * 10), sequence_index=i) for i in range(6, 11)]),
    ]
    # Combined latencies [10..100]; P95 inclusive = 95.5.
    assert lib.get_latency_p95(runs) == pytest.approx(95.5, rel=1e-6)


def test_get_cost_total_multi_trial_sums() -> None:
    lib = MetricsLibrary()
    runs = [_result(cost_usd=0.01), _result(cost_usd=0.02), _result(cost_usd=0.03)]
    assert lib.get_cost_total(runs) == pytest.approx(0.06)


# --------------------------------------------------------------------------- #
# 5 IncompleteTraceError gate tests for tool-call-bearing keywords (AC-6.1.1) #
# --------------------------------------------------------------------------- #


def test_get_tool_call_count_raises_on_external_mixed_by_default() -> None:
    """Story 6.1 code-review 1-way Edge-cases HIGH-4 fix 2026-05-20:
    verify the `metric_keyword="Get Tool Call Count"` threads into the
    raised exception message verbatim (was untested; future rename of
    the @keyword(name=...) without matching metric_keyword= would
    silently green per AC-6.1.10).
    """
    lib = MetricsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Get Tool Call Count"):
        lib.get_tool_call_count(result)


def test_get_tool_call_count_opts_out_via_allow_external_mcp_blind() -> None:
    lib = MetricsLibrary(allow_external_mcp_blind=True)
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    assert lib.get_tool_call_count(result) == 1


def test_get_tool_call_names_raises_on_external_mixed_by_default() -> None:
    lib = MetricsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Get Tool Call Names"):
        lib.get_tool_call_names(result)


def test_get_tool_hit_rate_raises_on_external_mixed_by_default() -> None:
    lib = MetricsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Get Tool Hit Rate"):
        lib.get_tool_hit_rate(result, expected_tools=["a"])


def test_get_tool_success_rate_raises_on_external_mixed_by_default() -> None:
    lib = MetricsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Get Tool Success Rate"):
        lib.get_tool_success_rate(result)


def test_get_unnecessary_call_rate_raises_on_external_mixed_by_default() -> None:
    lib = MetricsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Get Unnecessary Call Rate"):
        lib.get_unnecessary_call_rate(result, expected_tools=["a"])


# --------------------------------------------------------------------------- #
# 4 no-gate-for-non-tool-call tests (AC-6.1.1)                                #
# --------------------------------------------------------------------------- #


def test_get_token_usage_does_not_gate_on_external_mixed() -> None:
    """Provider-reported token counts are observer-independent."""
    lib = MetricsLibrary()
    result = _result([], mcp_coverage="external_mixed")
    # Must NOT raise.
    usage = lib.get_token_usage(result)
    assert usage.input_tokens == 10


def test_get_latency_does_not_gate_on_external_mixed() -> None:
    lib = MetricsLibrary()
    result = _result([], mcp_coverage="external_mixed", latency_seconds=0.1)
    assert lib.get_latency(result) == pytest.approx(100.0)


def test_get_latency_p95_does_not_gate_on_external_mixed() -> None:
    lib = MetricsLibrary()
    result = _result(
        [_trace("a", latency_ms=50.0)],
        mcp_coverage="external_mixed",
    )
    # Single tool_call → P95 falls back to that single value per AC-6.1.8.
    assert lib.get_latency_p95(result) == pytest.approx(50.0)


def test_get_cost_total_does_not_gate_on_external_mixed() -> None:
    lib = MetricsLibrary()
    result = _result(cost_usd=0.05, mcp_coverage="external_mixed")
    assert lib.get_cost_total(result) == pytest.approx(0.05)


# --------------------------------------------------------------------------- #
# Boundary cases per AC-6.1.8                                                 #
# --------------------------------------------------------------------------- #


def test_get_tool_success_rate_zero_tool_calls_returns_zero() -> None:
    lib = MetricsLibrary()
    result = _result([])
    assert lib.get_tool_success_rate(result) == 0.0


def test_get_unnecessary_call_rate_zero_tool_calls_returns_zero() -> None:
    lib = MetricsLibrary()
    result = _result([])
    assert lib.get_unnecessary_call_rate(result, expected_tools=["a"]) == 0.0


def test_get_tool_hit_rate_empty_expected_returns_zero() -> None:
    """Vacuous-truth convention per AC-6.1.8: 0/0 → 0.0."""
    lib = MetricsLibrary()
    result = _result([_trace("a")])
    assert lib.get_tool_hit_rate(result, expected_tools=[]) == 0.0


def test_get_token_usage_empty_list_returns_zeros() -> None:
    lib = MetricsLibrary()
    usage = lib.get_token_usage([])
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.cached_input_tokens == 0


def test_get_cost_total_empty_list_returns_zero() -> None:
    lib = MetricsLibrary()
    assert lib.get_cost_total([]) == 0.0


# --------------------------------------------------------------------------- #
# Story 6.1 code-review regression tests (HIGH fixes 2026-05-20)              #
# --------------------------------------------------------------------------- #


def test_get_tool_hit_rate_dedupes_expected_tools() -> None:
    """Story 6.1 code-review 1-way Edge-cases HIGH-1 fix 2026-05-20:
    duplicate `expected_tools` previously inflated both numerator and
    denominator (`["a","a","b"]` vs `observed={"a"}` returned 2/3 instead
    of set-semantic 1/2). Fixed to set-coerce expected via `set()` at
    the top of `_compute_tool_hit_rate` — symmetric with
    `_compute_unnecessary_call_rate`.
    """
    lib = MetricsLibrary()
    result = _result([_trace("a")])
    # Pre-fix: 2/3 ≈ 0.667. Post-fix: 1/2 = 0.5 (set-theoretic).
    rate = lib.get_tool_hit_rate(result, expected_tools=["a", "a", "b"])
    assert rate == pytest.approx(0.5)


def test_get_token_usage_returns_ratified_dataclass_shape() -> None:
    """Story 6.1 code-review 2-way HIGH-α fix 2026-05-20 (Blind HIGH-1 +
    Auditor HIGH-A): PRD FR22 pre-amendment said `Usage(input, output,
    total)` — the pre-1b.2 draft shape. Story 1b.2 ratified
    `Usage(input_tokens, output_tokens, cached_input_tokens)` with NO
    `total` field. PRD + epics amended in lockstep. Test pins the
    actually-shipped dataclass shape (no `total` attribute).
    """
    lib = MetricsLibrary()
    usage = lib.get_token_usage(_result(usage=Usage(input_tokens=10, output_tokens=20)))
    assert hasattr(usage, "input_tokens")
    assert hasattr(usage, "output_tokens")
    assert hasattr(usage, "cached_input_tokens")
    # Caller computes total = input + output at use site (no `total` field).
    assert usage.input_tokens + usage.output_tokens == 30


def test_get_latency_p95_multi_trial_uses_latency_seconds_fallback_for_zero_tc_runs() -> None:
    """Story 6.1 code-review 2-way HIGH-δ fix 2026-05-20 (Blind HIGH-4 +
    Auditor HIGH-E): pre-edit `_aggregate_latency_p95` silently skipped
    zero-tc runs while `_aggregate_latency_mean` used `latency_seconds *
    1000` as a single-sample fallback. Asymmetric: `[zero_tc(0.1s),
    tc(50ms)]` returned mean=5025ms vs p95=50ms. Now both symmetric:
    P95 also incorporates the fallback sample.
    """
    lib = MetricsLibrary()
    runs = [
        # Zero-tc run with 100ms wall-clock latency.
        _result([], latency_seconds=0.1),
        # Single tool_call at 50ms.
        _result([_trace("a", latency_ms=50.0)]),
    ]
    # Union now: [100.0 (fallback), 50.0]; P95 of 2 elements with
    # method=inclusive interpolates between sorted [50, 100] at the
    # 95th percentile cut → close to max (100). Symmetric fallback
    # confirmed by non-zero P95.
    p95 = lib.get_latency_p95(runs)
    assert p95 > 50.0


def test_get_tool_call_names_multi_trial_dedupes_documented_clearly() -> None:
    """Story 6.1 code-review 1-way Auditor HIGH-G acknowledged: multi-trial
    `Get Tool Call Names` de-duplicates via union-preserving-order while
    single-run preserves duplicates. Asymmetry is by design (epics.md
    AC-6.1.1 row 2 documents it). This test pins the asymmetric
    contract so a future refactor toward concatenation surfaces
    explicitly.
    """
    lib = MetricsLibrary()
    # Single run: duplicates preserved.
    single = _result([_trace("a"), _trace("a", sequence_index=1), _trace("b", sequence_index=2)])
    assert lib.get_tool_call_names(single) == ["a", "a", "b"]
    # Multi-trial: deduped via union-preserving-order.
    runs = [
        _result([_trace("a"), _trace("a", sequence_index=1)]),
        _result([_trace("a"), _trace("b", sequence_index=1)]),
    ]
    assert lib.get_tool_call_names(runs) == ["a", "b"]
