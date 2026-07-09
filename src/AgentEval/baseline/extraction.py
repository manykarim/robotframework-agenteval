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

"""Metric extraction from a results union (design Decision 5).

Accepts ``list[KeywordRun]`` (from ``Stat.Run N Times``) or
``list[AgentRunResult]`` (from repeated ``Send Prompt`` / ``Run Scenario``) and
computes evidence-bearing metric entries:

- **Proportions**: ``pass_rate`` (successes/trials), ``pass_at_k`` for each
  requested ``k`` (HumanEval estimator, reusing ``stats._internal``),
  ``tool_hit_rate`` only when ``expected_tools=`` is provided.
- **Continuous**: per-trial ``cost_usd`` sample list (point = mean) and
  ``latency_p95_ms`` (samples = per-trial latency in ms; point = p95, with
  mean/p50 stored).

Metric families whose evidence is unavailable are OMITTED and logged — never
zero-filled (design D5 + ``_heatmap`` em-dash honesty precedent).
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Callable
from typing import Any

from AgentEval.baseline.models import ContinuousEvidence, ProportionEvidence
from AgentEval.stats._internal import _compute_pass_at_k
from AgentEval.stats.types import KeywordRun
from AgentEval.types import AgentRunResult

__all__ = ["ExtractionResult", "extract_metrics"]

_logger = logging.getLogger("AgentEval.baseline")

# Predicate over a single result item (KeywordRun or AgentRunResult).
Predicate = Callable[[Any], bool]


class ExtractionResult:
    """Container for extracted metric evidence + omission notes."""

    def __init__(
        self,
        metrics: dict[str, ProportionEvidence | ContinuousEvidence],
        extra_metrics: dict[str, float],
        omitted: list[str],
    ) -> None:
        self.metrics = metrics
        self.extra_metrics = extra_metrics
        self.omitted = omitted


def _default_predicate(item: Any) -> bool:
    """Success iff ``completeness == "complete"`` (ratified `Stat.Get Pass At K` default)."""
    if isinstance(item, KeywordRun):
        return item.completeness == "complete"
    metadata = getattr(item, "metadata", None)
    completeness = getattr(metadata, "completeness", None)
    return completeness == "complete"


def _unwrap_agent_result(item: Any) -> AgentRunResult | None:
    """Return the ``AgentRunResult`` payload for a result item, or ``None``."""
    if isinstance(item, AgentRunResult):
        return item
    if isinstance(item, KeywordRun):
        inner = item.result
        if isinstance(inner, AgentRunResult):
            return inner
    return None


def _latency_ms_sample(item: Any) -> float | None:
    """Per-trial latency in ms.

    ``KeywordRun`` carries its own wall-clock ``latency_seconds``;
    ``AgentRunResult`` carries ``latency_seconds`` too. Multiply by 1000.
    """
    latency_seconds = getattr(item, "latency_seconds", None)
    if latency_seconds is None:
        return None
    return float(latency_seconds) * 1000.0


def _percentile(samples: list[float], q: float) -> float:
    """Inclusive-method percentile, guarding the 0-and-1-sample boundaries."""
    if not samples:
        return 0.0
    if len(samples) == 1:
        return samples[0]
    # q in [0, 100]. statistics.quantiles(n=100) → 99 cut points at 1..99.
    idx = int(round(q)) - 1
    idx = max(0, min(98, idx))
    return statistics.quantiles(samples, n=100, method="inclusive")[idx]


def extract_metrics(
    results: list[Any],
    *,
    predicate: Predicate | None = None,
    k_list: list[int] | None = None,
    expected_tools: list[str] | None = None,
    extra_metrics: dict[str, float] | None = None,
) -> ExtractionResult:
    """Extract evidence-bearing metrics from a results union (design D5)."""
    if not results:
        raise ValueError("results must be a non-empty list of KeywordRun or AgentRunResult")

    pred = predicate or _default_predicate
    k_values = k_list if k_list is not None else [1]
    metrics: dict[str, ProportionEvidence | ContinuousEvidence] = {}
    omitted: list[str] = []

    trials = len(results)
    successes = sum(1 for r in results if pred(r))

    # --- Proportion: pass_rate ------------------------------------------- #
    metrics["pass_rate"] = ProportionEvidence(
        successes=successes, trials=trials, value=successes / trials, k=None
    )

    # --- Proportion: pass_at_k ------------------------------------------- #
    for k in k_values:
        if k > trials:
            omitted.append(f"pass_at_{k} (k={k} > trials={trials})")
            continue
        value = _compute_pass_at_k(successes, trials, k)
        metrics[f"pass_at_{k}"] = ProportionEvidence(
            successes=successes, trials=trials, value=value, k=k
        )

    # --- Continuous: cost + latency, from AgentRunResult payloads -------- #
    agent_results = [ar for r in results if (ar := _unwrap_agent_result(r)) is not None]

    cost_samples = [ar.cost_usd for ar in agent_results]
    if cost_samples:
        metrics["cost_usd"] = _continuous(cost_samples, point="mean")
    else:
        omitted.append("cost_usd (no AgentRunResult payloads carrying cost)")

    latency_samples = [ms for r in results if (ms := _latency_ms_sample(r)) is not None]
    if latency_samples:
        metrics["latency_p95_ms"] = _continuous(latency_samples, point="p95")
    else:
        omitted.append("latency_p95_ms (no per-trial latency available)")

    # --- Proportion: tool_hit_rate (only with expected_tools) ------------ #
    if expected_tools:
        expected_set = set(expected_tools)
        if agent_results and expected_set:
            # Each (run, expected_tool) is a Bernoulli trial "was it called?".
            hit_successes = 0
            hit_trials = 0
            for ar in agent_results:
                observed = {tc.name for tc in ar.tool_calls}
                for tool in expected_set:
                    hit_trials += 1
                    if tool in observed:
                        hit_successes += 1
            if hit_trials:
                metrics["tool_hit_rate"] = ProportionEvidence(
                    successes=hit_successes,
                    trials=hit_trials,
                    value=hit_successes / hit_trials,
                    k=None,
                )
        else:
            omitted.append("tool_hit_rate (no AgentRunResult tool-call payloads)")

    for note in omitted:
        _logger.info("Save Metrics Baseline: omitted metric — %s", note)

    return ExtractionResult(
        metrics=metrics,
        extra_metrics={str(k): float(v) for k, v in (extra_metrics or {}).items()},
        omitted=omitted,
    )


def _continuous(samples: list[float], *, point: str) -> ContinuousEvidence:
    total = float(sum(samples))
    mean = statistics.mean(samples)
    p50 = _percentile(samples, 50.0)
    p95 = _percentile(samples, 95.0)
    value = {"mean": mean, "total": total, "p50": p50, "p95": p95}[point]
    return ContinuousEvidence(
        samples=tuple(float(s) for s in samples),
        value=float(value),
        total=total,
        mean=float(mean),
        p50=float(p50),
        p95=float(p95),
        samples_truncated=False,
    )
