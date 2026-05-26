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
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line. Per-line 120-char limit waived for this file
# per Phase 3 docstring-refresh proposal (2026-05-26).

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

# Browser-Library-style docstring migration marker (Phase 3, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


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
        """Returns the number of tool calls made by the agent (PRD FR19).

        [Tier 1 — Deterministic] — returns ``int``. Single run:
        ``len(result.tool_calls)``. Multi-trial: sum across trials.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]`` for multi-trial sum aggregation. |

        Raises ``IncompleteTraceError`` per FR37 when any input run carries
        ``mcp_coverage="external_mixed"`` AND the Library was constructed
        with ``allow_external_mcp_blind=False`` (default-deny per FR42).

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${count} =    `Get Tool Call Count`    ${result}
        | Should Be Equal As Integers    ${count}    3

        Notes:
        - PRD FR19 ratifies the count metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.
        - mcp_coverage gating per FR37 + FR42 — opt out via ``AgentEval(allow_external_mcp_blind=True)``.
        - Sibling keyword: `Get Tool Call Names` for the ordered names list.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Returns tool-call names in chronological order (PRD FR19).

        [Tier 1 — Deterministic] — duplicates preserved per FR19 verbatim
        ("list[str] (preserving order)"). Single run: chronological list.
        Multi-trial: union preserving order-of-first-appearance.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]`` for multi-trial union aggregation. |

        Raises ``IncompleteTraceError`` per FR37 when any input run carries
        ``mcp_coverage="external_mixed"`` AND the Library was constructed
        with ``allow_external_mcp_blind=False``.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | @{names} =    `Get Tool Call Names`    ${result}
        | Should Contain    ${names}    web_search
        | Should Be Equal    ${names}[0]    web_search                              # First tool called.

        Notes:
        - PRD FR19 ratifies the names metric; AC-6.1.1 ratifies single-vs-multi-trial dispatch.
        - mcp_coverage gating per FR37 + FR42.
        - Sibling keyword: `Get Tool Call Count` for the count; `Get Tool Hit Rate` for expected-set comparison.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Returns the tool-hit rate ``|expected ∩ observed| / |expected|`` (PRD FR20).

        [Tier 1 — Deterministic] — returns ``float`` in ``[0, 1]``. Empty
        ``expected_tools`` returns ``0.0`` per AC-6.1.8 vacuous-truth
        convention. Multi-trial: union-of-observed against expected_tools.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |
        | ``expected_tools`` | List of tool names the agent SHOULD have called. |

        Raises ``IncompleteTraceError`` per FR37 when any input run carries
        ``mcp_coverage="external_mixed"`` AND the Library was constructed
        with ``allow_external_mcp_blind=False``.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${hit_rate} =    `Get Tool Hit Rate`    ${result}    ${{['web_search', 'fetch']}}
        | Should Be True    ${hit_rate} >= 0.5                                      # At least half of expected tools were called.

        Notes:
        - PRD FR20 ratifies the hit-rate formula; AC-6.1.8 ratifies the vacuous-truth convention for empty expected_tools.
        - mcp_coverage gating per FR37 + FR42.
        - Sibling keywords: `Get Unnecessary Call Rate` (calls NOT in expected set); `Get Tool Success Rate` (errors / total).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Returns the tool-success rate ``non-error / total`` (PRD FR20).

        [Tier 1 — Deterministic] — returns ``float`` in ``[0, 1]``. Zero
        ``tool_calls`` returns ``0.0`` per AC-6.1.8 vacuous-truth
        convention. Multi-trial: aggregate across all per-trial tool
        calls.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |

        Raises ``IncompleteTraceError`` per FR37 when any input run carries
        ``mcp_coverage="external_mixed"`` AND the Library was constructed
        with ``allow_external_mcp_blind=False``.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${success_rate} =    `Get Tool Success Rate`    ${result}
        | Should Be True    ${success_rate} >= 0.8                                  # At least 80% of tool calls succeeded.

        Notes:
        - PRD FR20 ratifies the success-rate formula; AC-6.1.8 ratifies the zero-division convention.
        - mcp_coverage gating per FR37 + FR42.
        - Each ``ToolCallTrace`` has an ``error`` field — non-None counts as a failure.
        - Sibling keywords: `Get Tool Hit Rate` (vs expected set); `Get Unnecessary Call Rate`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Returns the unnecessary-call rate ``not_in_expected / total`` (PRD FR21).

        [Tier 1 — Deterministic] — returns ``float`` in ``[0, 1]``. Zero
        ``tool_calls`` returns ``0.0`` per AC-6.1.8 vacuous-truth
        convention.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |
        | ``expected_tools`` | List of tool names the agent SHOULD have called. Any observed call NOT in this list counts as unnecessary. |

        Raises ``IncompleteTraceError`` per FR37 when any input run carries
        ``mcp_coverage="external_mixed"`` AND the Library was constructed
        with ``allow_external_mcp_blind=False``.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${noise} =    `Get Unnecessary Call Rate`    ${result}    ${{['web_search']}}
        | Should Be True    ${noise} <= 0.2                                         # At most 20% of calls were off-task.

        Notes:
        - PRD FR21 ratifies the unnecessary-rate formula — quantifies "noise" tool calls beyond the expected set.
        - AC-6.1.8 ratifies the vacuous-truth convention (zero tool_calls → 0.0).
        - Sibling keyword: `Get Tool Hit Rate` (calls that ARE in expected set).
        - mcp_coverage gating per FR37 + FR42.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Returns the agent's token usage as a ``Usage`` dataclass (PRD FR22).

        [Tier 1 — Deterministic] — returns ``Usage(input_tokens,
        output_tokens, cached_input_tokens)``. Single run: the run's own
        usage. Multi-trial: sum per field. Empty list → ``Usage(0, 0, 0)``.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |

        Provider-reported scalar — observer-independent. NOT
        ``mcp_coverage``-gated (PRD FR22 + AC-6.1.1).

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${usage} =    `Get Token Usage`    ${result}
        | Should Be True    ${usage.input_tokens} > 0
        | Should Be True    ${usage.output_tokens} > 0
        | Log    Total: ${{${usage.input_tokens} + ${usage.output_tokens}}} tokens

        Notes:
        - PRD FR22 ratifies the four usage metrics — `Get Token Usage`, `Get Latency`, `Get Latency P95`, `Get Cost Total` — all observer-independent per AC-6.1.1.
        - ``Usage`` is a frozen dataclass; field validation ensures non-negative counts.
        - Sibling keywords: `Get Cost Total`, `Get Latency`, `Get Latency P95`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if isinstance(result, list):
            return _internal._aggregate_token_usage(result)
        return _internal._compute_token_usage(result)

    @keyword(name="Get Latency")
    @tier(1)
    def get_latency(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """Returns mean turn-level latency in milliseconds (PRD FR22).

        [Tier 1 — Deterministic] — returns ``float`` (ms). When the run
        has no ``tool_calls``, falls back to
        ``result.latency_seconds * 1000.0``. Multi-trial: union-of-
        tool-calls mean — all per-tool-call latencies from all trials
        are flattened into one list before ``statistics.mean()`` is
        taken. Mean-of-per-run-means is a statistical anti-pattern
        (under-weights runs with more tool calls); union-then-mean is
        the operator-intuitive default per Story 6.1 code-review.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |

        Provider-reported scalar — NOT ``mcp_coverage``-gated.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${latency_ms} =    `Get Latency`    ${result}
        | Should Be True    ${latency_ms} < 2000                                    # Mean turn latency under 2 seconds.

        Notes:
        - PRD FR22 ratifies the latency metric — per-tool-call resolution preferred over per-run.
        - Union-then-mean aggregation rule ratified by Story 6.1 code-review (anti-pattern: mean-of-per-run-means).
        - Sibling keyword: `Get Latency P95` for tail-latency tracking.
        - Provider-reported scalar — observer-independent per AC-6.1.1.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if isinstance(result, list):
            return _internal._aggregate_latency_mean(result)
        return _internal._compute_latency_mean(result)

    @keyword(name="Get Latency P95")
    @tier(1)
    def get_latency_p95(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """Returns the P95 latency across tool calls in milliseconds (PRD FR22).

        [Tier 1 — Deterministic] — returns ``float`` (ms). AC-6.1.8
        boundary conditions: 0 tool_calls → ``0.0``; 1 tool_call → that
        single latency; ≥2 → ``statistics.quantiles(n=100)[94]``.
        Multi-trial: P95 across the union of all tool_calls' latencies.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |

        Provider-reported scalar — NOT ``mcp_coverage``-gated.

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | @{results} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}
        | ${p95_ms} =    `Get Latency P95`    ${results}
        | ${mean_ms} =    `Get Latency`    ${results}
        | Should Be True    ${p95_ms} >= ${mean_ms}                                 # P95 ≥ mean by definition.

        Notes:
        - PRD FR22 ratifies the P95 metric — tail-latency tracking complements `Get Latency` mean.
        - AC-6.1.8 boundary conditions cover empty / single-call edge cases.
        - Sibling keywords: `Get Latency` for mean; `Stat.Run N Times` to generate multi-trial input.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if isinstance(result, list):
            return _internal._aggregate_latency_p95(result)
        return _internal._compute_latency_p95(result)

    @keyword(name="Get Cost Total")
    @tier(1)
    def get_cost_total(self, result: AgentRunResult | list[AgentRunResult]) -> float:
        """Returns total provider-reported USD cost (PRD FR22).

        [Tier 1 — Deterministic] — returns ``float`` (USD). Single run:
        the run's ``cost_usd``. Multi-trial: sum across trials. Empty
        list → ``0.0``.

        | =Arguments= | =Description= |
        | ``result`` | Single ``AgentRunResult`` OR ``list[AgentRunResult]``. |

        Provider-reported scalar — NOT ``mcp_coverage``-gated. Returns
        ``0.0`` on the Mock provider; non-zero on real adapters per
        Story 8a.1 (real adapters use ``total_cost_usd`` not
        ``cost_usd``).

        Example (illustrative — assumes a real adapter with the expected tool-call surface):
        | ${result} =    `Send Prompt`    prompt=Find the latest news    adapter=generic    model=anthropic/claude-sonnet-4-6
        | ${cost_usd} =    `Get Cost Total`    ${result}
        | Should Be True    ${cost_usd} < 0.10                                      # Single-shot cost cap $0.10.
        | @{results} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=generic', 'provider=mock']}}
        | ${total_cost} =    `Get Cost Total`    ${results}                         # Cohort cost rollup.

        Notes:
        - PRD FR22 ratifies the cost metric.
        - Mock-provider runs return ``0.0`` cost; real adapters surface the provider's reported cost.
        - Story 8a.1 v1 HIGH-1 ratified ``total_cost_usd`` as the canonical real-adapter key.
        - Sibling keywords: `Get Token Usage`, `Get Latency`, `Get Latency P95`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if isinstance(result, list):
            return _internal._aggregate_cost_total(result)
        return _internal._compute_cost_total(result)
