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

"""Robot Framework library exposing ground-truth metrics over an agent run.

All keywords sit under the ``Metric.`` prefix and are Tier-1 (deterministic, no
model). They are thin readers over a recorded ``AgentRunResult`` and its
``ToolCallTrace`` records - every number comes from the recorded trace, never
from model self-report:

- *Readers* - ``Get Token Usage``, ``Get Cost USD``, ``Get Latency Seconds``,
  ``Get Tool Call Metrics`` (per-task rollup + per-tool breakdown).
- *Budget assertions* - ``Tokens Used Should Be Below``, ``Cost Should Be
  Below`` (raise ``BudgetExceededError``).
- *Normalized record* - ``Get Run Metrics`` computes the rf-mcp-shaped
  ``RunMetrics`` record (with a declarative expected-tool contract and
  ``tool_hit_rate``); ``Export Run Metrics`` writes it to JSON.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._core.errors import BudgetExceededError
from AgentEval._core.tier import tier
from AgentEval._core.types import AgentRunResult, Usage
from MetricsLibrary._record import ExpectedToolCall, RunMetrics, compute_run_metrics

__all__ = ["MetricsLibrary", "ExpectedToolCall", "RunMetrics"]


def _empty_rollup() -> dict[str, Any]:
    """A zeroed per-task / per-tool rollup bucket."""
    return {
        "count": 0,
        "passed": 0,
        "failed": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0.0,
    }


class MetricsLibrary:
    """Read ground-truth token/cost/latency/tool metrics off a recorded agent run."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    # ------------------------------------------------------------------ #
    # Tier-1 readers over AgentRunResult fields.                         #
    # ------------------------------------------------------------------ #

    @keyword(name="Metric.Get Token Usage")
    @tier(1)
    def get_token_usage(self, run: AgentRunResult) -> dict[str, int]:
        """Token counts from the recorded run's ``usage``.

        Keys: ``input``, ``output``, ``cached`` (prompt-cache read), and the
        prompt-cache *write* counts ``cache_creation`` (total) plus its
        ``cache_creation_1h`` / ``cache_creation_5m`` TTL split. A ``0`` cache-creation
        value on an adapter that does not report one means "not reported."

        Example:
        | ${usage}=    Metric.Get Token Usage    ${result}
        | Should Be Equal As Integers    ${usage}[input]    120
        """
        usage: Usage = run.usage
        return {
            "input": usage.input_tokens,
            "output": usage.output_tokens,
            "cached": usage.cached_input_tokens,
            "cache_creation": usage.cache_creation_input_tokens,
            "cache_creation_1h": usage.cache_creation_1h_input_tokens,
            "cache_creation_5m": usage.cache_creation_5m_input_tokens,
        }

    @keyword(name="Metric.Get Cost USD")
    @tier(1)
    def get_cost_usd(self, run: AgentRunResult) -> float:
        """The recorded run's ``cost_usd``, unchanged.

        Example:
        | ${cost}=    Metric.Get Cost USD    ${result}
        | Should Be True    ${cost} < 0.05
        """
        return run.cost_usd

    @keyword(name="Metric.Get Latency Seconds")
    @tier(1)
    def get_latency_seconds(self, run: AgentRunResult) -> float:
        """The recorded run's ``latency_seconds``, unchanged.

        Example:
        | ${latency}=    Metric.Get Latency Seconds    ${result}
        | Should Be True    ${latency} < 30
        """
        return run.latency_seconds

    @keyword(name="Metric.Get Tool Call Metrics")
    @tier(1)
    def get_tool_call_metrics(self, run: AgentRunResult) -> dict[str, Any]:
        """Per-task rollup plus a per-tool breakdown over the run's tool calls.

        Returns ``{"per_task": {...}, "per_tool": {name: {...}, ...}}``. Each
        rollup carries ``count``, ``passed`` (``error is None``), ``failed``,
        ``input_tokens``, ``output_tokens``, ``cost_usd``, and ``latency_ms``,
        all summed from the recorded ``ToolCallTrace`` records.

        Example:
        | ${m}=    Metric.Get Tool Call Metrics    ${result}
        | Should Be Equal As Integers    ${m}[per_task][count]    3
        | Should Be Equal As Integers    ${m}[per_tool][search][passed]    2
        """
        per_task = _empty_rollup()
        per_tool: dict[str, dict[str, Any]] = {}
        for call in run.tool_calls:
            bucket = per_tool.setdefault(call.name, _empty_rollup())
            for target in (per_task, bucket):
                target["count"] += 1
                if call.error is None:
                    target["passed"] += 1
                else:
                    target["failed"] += 1
                target["input_tokens"] += call.input_tokens
                target["output_tokens"] += call.output_tokens
                target["cost_usd"] += call.cost_usd
                target["latency_ms"] += call.latency_ms
        return {"per_task": per_task, "per_tool": per_tool}

    # ------------------------------------------------------------------ #
    # Budget assertions.                                                 #
    # ------------------------------------------------------------------ #

    @keyword(name="Metric.Tokens Used Should Be Below")
    @tier(1)
    def tokens_used_should_be_below(self, run: AgentRunResult, threshold: int) -> None:
        """Pass when total tokens used (input + output) is strictly below ``threshold``.

        Raises ``BudgetExceededError`` naming the actual total and the threshold.

        Example:
        | Metric.Tokens Used Should Be Below    ${result}    10000
        """
        total = run.usage.input_tokens + run.usage.output_tokens
        if total >= threshold:
            raise BudgetExceededError(
                f"token budget exceeded: run used {total} tokens (input + output); threshold is {threshold}"
            )

    @keyword(name="Metric.Cost Should Be Below")
    @tier(1)
    def cost_should_be_below(self, run: AgentRunResult, threshold: float) -> None:
        """Pass when the run's ``cost_usd`` is strictly below ``threshold``.

        Raises ``BudgetExceededError`` naming the actual cost and the threshold.

        Example:
        | Metric.Cost Should Be Below    ${result}    0.10
        """
        if run.cost_usd >= threshold:
            raise BudgetExceededError(
                f"cost budget exceeded: run cost ${run.cost_usd:.6f}; threshold is ${threshold:.6f}"
            )

    # ------------------------------------------------------------------ #
    # Normalized run-metrics record + JSON export.                       #
    # ------------------------------------------------------------------ #

    @keyword(name="Metric.Get Run Metrics")
    @tier(1)
    def get_run_metrics(
        self,
        run: AgentRunResult,
        expected: ExpectedToolCall | Mapping[str, Any] | Iterable[ExpectedToolCall | Mapping[str, Any]] | None = None,
    ) -> RunMetrics:
        """Compute the normalized ``RunMetrics`` record from a run + optional contract.

        ``expected`` is an ``ExpectedToolCall`` (or dict), or a list of them; the
        record's ``tool_hit_rate`` reports how many entries the recorded trace
        satisfied.

        Example:
        | ${expected}=    Evaluate    [{'tool': 'search', 'min_calls': 1}]
        | ${m}=    Metric.Get Run Metrics    ${result}    ${expected}
        | Should Be Equal As Numbers    ${m.tool_hit_rate}    1.0
        """
        return compute_run_metrics(run, expected)

    @keyword(name="Metric.Export Run Metrics")
    @tier(1)
    def export_run_metrics(self, record: RunMetrics | AgentRunResult, path: str) -> str:
        """Write a ``RunMetrics`` record to ``path`` as JSON; return the path written.

        An ``AgentRunResult`` is accepted and computed into a record first (with
        no expected contract). Every value written is ground-truth from the
        recorded run - no model self-report is exported.

        Example:
        | ${m}=    Metric.Get Run Metrics    ${result}
        | Metric.Export Run Metrics    ${m}    ${OUTPUT_DIR}/metrics.json
        """
        metrics = record if isinstance(record, RunMetrics) else compute_run_metrics(record)
        destination = Path(path)
        if destination.parent and not destination.parent.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(metrics.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return str(destination)
