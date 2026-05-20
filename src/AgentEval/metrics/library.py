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

"""Tool-call metrics RF-keyword surface (Story 6.1 / PRD FR19-22).

Ships 9 `Metric.*` keywords reading from `AgentRunResult` instances:

- FR19: `Get Tool Call Count` + `Get Tool Call Names`
- FR20: `Get Tool Hit Rate` + `Get Tool Success Rate`
- FR21: `Get Unnecessary Call Rate`
- FR22: `Get Token Usage` + `Get Latency` + `Get Latency P95` + `Get Cost Total`

Each keyword:
- Accepts single `AgentRunResult` OR `list[AgentRunResult]` (multi-trial
  aggregation) via input-type dispatch.
- Carries `@tier(1)` Tier-1 badge per Story 1b.1 + `[Tier 1 — Deterministic]`
  docstring per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- Tool-call-bearing keywords (count, names, hit_rate, success_rate,
  unnecessary_rate) gate on `mcp_coverage` via
  `_kernel/coverage._check_mcp_coverage` per FR37 (default-deny on
  `external_mixed`; opt-out via `allow_external_mcp_blind=True` Library
  kwarg). Token usage / latency / cost keywords do NOT gate — they're
  observer-independent provider-reported scalars.

**Phase-1 data source carve-out (Story 6.1 D-7 / DF-6.1-S1 / C46):**
keywords read from `AgentRunResult` fields directly, NOT from
`_kernel/trace_store` spans (architecture L677's idealized path).
Rationale: adapter span instrumentation is deferred per DF-5.5-DOGFOOD-2
/ C44. `AgentRunResult` IS the Phase-1 projection layer above the trace.

Sub-library registration via `_SUB_LIBRARIES` in
`src/AgentEval/__init__.py`. Filename matches the existing convention
(`hooks/library.py`, `orchestration/library.py`, `telemetry/library.py`).
"""

from __future__ import annotations

from robot.api.deco import keyword

from AgentEval._kernel.coverage import _check_mcp_coverage
from AgentEval._kernel.tier import tier
from AgentEval.metrics import _internal
from AgentEval.types import AgentRunResult, Usage

__all__ = ["MetricsLibrary", "Usage"]


# Coverage-gated keywords (per AC-6.1.1): tool-call-bearing metrics
# raise IncompleteTraceError on `external_mixed` unless opted out.
# Non-tool-call metrics (token usage / latency / cost) do NOT gate —
# provider-reported scalars are observer-independent.


class MetricsLibrary:
    """`Metric.*` keyword surface (Story 6.1 / PRD FR19-22).

    Library-level `allow_external_mcp_blind` kwarg (forwarded from the
    top-level `AgentEval(allow_external_mcp_blind=...)` via
    `_build_components` per Story 4.3 precedent) controls the
    `IncompleteTraceError` gate's default-deny posture for tool-call-
    bearing keywords. Default `False` matches PRD FR42.
    """

    def __init__(self, allow_external_mcp_blind: bool = False) -> None:
        self._allow_external_mcp_blind = allow_external_mcp_blind

    # ----------------------------------------------------------------- #
    # FR19 — Tool-call count + names                                    #
    # ----------------------------------------------------------------- #

    @keyword(name="Get Tool Call Count")
    @tier(1)
    def get_tool_call_count(self, result: AgentRunResult | list[AgentRunResult]) -> int:
        """[Tier 1 — Deterministic] Return the number of tool calls (PRD FR19).

        Args:
            result: Single `AgentRunResult` OR `list[AgentRunResult]` for
                multi-trial sum aggregation per AC-6.1.1.

        Returns:
            `int` — `len(result.tool_calls)` for a single run; sum across
            trials for a list.

        Raises:
            `IncompleteTraceError`: per FR37 when any input run carries
                `mcp_coverage="external_mixed"` AND the Library was
                constructed with `allow_external_mcp_blind=False`
                (default-deny per PRD FR42).
        """
        if isinstance(result, list):
            for r in result:
                _check_mcp_coverage(
                    r,
                    allow_external_mcp_blind=self._allow_external_mcp_blind,
                    metric_keyword="Get Tool Call Count",
                )
            return _internal._aggregate_tool_call_count(result)
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Get Tool Call Count",
        )
        return _internal._compute_tool_call_count(result)

    @keyword(name="Get Tool Call Names")
    @tier(1)
    def get_tool_call_names(self, result: AgentRunResult | list[AgentRunResult]) -> list[str]:
        """[Tier 1 — Deterministic] Return tool-call names in chronological order (PRD FR19).

        Duplicates preserved per PRD FR19 verbatim ("list[str] (preserving order)").
        Multi-trial: union preserving order-of-first-appearance.
        """
        if isinstance(result, list):
            for r in result:
                _check_mcp_coverage(
                    r,
                    allow_external_mcp_blind=self._allow_external_mcp_blind,
                    metric_keyword="Get Tool Call Names",
                )
            return _internal._aggregate_tool_call_names(result)
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Get Tool Call Names",
        )
        return _internal._compute_tool_call_names(result)

    # ----------------------------------------------------------------- #
    # FR20 — Tool-hit rate + success rate                               #
    # ----------------------------------------------------------------- #

    @keyword(name="Get Tool Hit Rate")
    @tier(1)
    def get_tool_hit_rate(
        self,
        result: AgentRunResult | list[AgentRunResult],
        expected_tools: list[str],
    ) -> float:
        """[Tier 1 — Deterministic] Return `|expected ∩ observed| / |expected|` (PRD FR20).

        Empty `expected_tools` returns 0.0 per AC-6.1.8 vacuous-truth
        convention.
        """
        if isinstance(result, list):
            for r in result:
                _check_mcp_coverage(
                    r,
                    allow_external_mcp_blind=self._allow_external_mcp_blind,
                    metric_keyword="Get Tool Hit Rate",
                )
            return _internal._aggregate_tool_hit_rate(result, expected_tools)
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Get Tool Hit Rate",
        )
        return _internal._compute_tool_hit_rate(result, expected_tools)

    @keyword(name="Get Tool Success Rate")
    @tier(1)
    def get_tool_success_rate(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """[Tier 1 — Deterministic] Return `non-error / total` (PRD FR20).

        Zero tool_calls → 0.0 per AC-6.1.8.
        """
        if isinstance(result, list):
            for r in result:
                _check_mcp_coverage(
                    r,
                    allow_external_mcp_blind=self._allow_external_mcp_blind,
                    metric_keyword="Get Tool Success Rate",
                )
            return _internal._aggregate_tool_success_rate(result)
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Get Tool Success Rate",
        )
        return _internal._compute_tool_success_rate(result)

    # ----------------------------------------------------------------- #
    # FR21 — Unnecessary call rate                                      #
    # ----------------------------------------------------------------- #

    @keyword(name="Get Unnecessary Call Rate")
    @tier(1)
    def get_unnecessary_call_rate(
        self,
        result: AgentRunResult | list[AgentRunResult],
        expected_tools: list[str],
    ) -> float:
        """[Tier 1 — Deterministic] Return `not_in_expected / total` (PRD FR21).

        Zero tool_calls → 0.0 per AC-6.1.8.
        """
        if isinstance(result, list):
            for r in result:
                _check_mcp_coverage(
                    r,
                    allow_external_mcp_blind=self._allow_external_mcp_blind,
                    metric_keyword="Get Unnecessary Call Rate",
                )
            return _internal._aggregate_unnecessary_call_rate(result, expected_tools)
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Get Unnecessary Call Rate",
        )
        return _internal._compute_unnecessary_call_rate(result, expected_tools)

    # ----------------------------------------------------------------- #
    # FR22 — Token usage + latency + latency P95 + cost total           #
    # (No mcp_coverage gate — provider-reported scalars                  #
    # are observer-independent per AC-6.1.1.)                            #
    # ----------------------------------------------------------------- #

    @keyword(name="Get Token Usage")
    @tier(1)
    def get_token_usage(self, result: AgentRunResult | list[AgentRunResult]) -> Usage:
        """[Tier 1 — Deterministic] Return token usage (PRD FR22).

        Multi-trial: sum per field. Empty list → `Usage(0, 0, 0)`.
        """
        if isinstance(result, list):
            return _internal._aggregate_token_usage(result)
        return _internal._compute_token_usage(result)

    @keyword(name="Get Latency")
    @tier(1)
    def get_latency(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """[Tier 1 — Deterministic] Return mean turn-level latency in ms (PRD FR22).

        Per AC-6.1.1: when `tool_calls` is empty, falls back to
        `result.latency_seconds * 1000.0`. Multi-trial: union-of-tool-calls
        mean — all per-tool-call latencies from all trials are flattened
        into one list + `statistics.mean()` taken. Zero-tc trials
        contribute their `latency_seconds * 1000` fallback as a SINGLE
        sample to the union. Mean-of-per-run-means is a known statistical
        anti-pattern (under-weights runs with more tool calls); union-then-
        mean is the operator-intuitive default (Story 6.1 code-review
        3-way HIGH-γ docstring fix 2026-05-20).
        """
        if isinstance(result, list):
            return _internal._aggregate_latency_mean(result)
        return _internal._compute_latency_mean(result)

    @keyword(name="Get Latency P95")
    @tier(1)
    def get_latency_p95(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """[Tier 1 — Deterministic] Return P95 latency in ms (PRD FR22).

        Per AC-6.1.8 boundary:
        - 0 tool_calls → 0.0
        - 1 tool_call → that single latency value
        - ≥2 → `statistics.quantiles(n=100)[94]`.

        Multi-trial: P95 across the union of all tool_calls' latencies.
        """
        if isinstance(result, list):
            return _internal._aggregate_latency_p95(result)
        return _internal._compute_latency_p95(result)

    @keyword(name="Get Cost Total")
    @tier(1)
    def get_cost_total(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """[Tier 1 — Deterministic] Return total USD cost (PRD FR22).

        Multi-trial: sum across trials. Empty list → 0.0.
        """
        if isinstance(result, list):
            return _internal._aggregate_cost_total(result)
        return _internal._compute_cost_total(result)
