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

"""Unit tests: metric extraction from the results union (task 6.2)."""

from __future__ import annotations

import pytest

from AgentEval.baseline.extraction import extract_metrics
from AgentEval.baseline.models import ContinuousEvidence, ProportionEvidence

from ._builders import agent_results, keyword_runs


def test_keyword_run_default_predicate_counts_complete() -> None:
    result = extract_metrics(keyword_runs(9, 10))
    pr = result.metrics["pass_rate"]
    assert isinstance(pr, ProportionEvidence)
    assert (pr.successes, pr.trials) == (9, 10)
    assert pr.value == pytest.approx(0.9)


def test_predicate_override() -> None:
    # Custom predicate: always False → 0 successes.
    result = extract_metrics(keyword_runs(9, 10), predicate=lambda _r: False)
    assert result.metrics["pass_rate"].successes == 0


def test_pass_at_k_multiple_k() -> None:
    result = extract_metrics(keyword_runs(8, 10), k_list=[1, 5])
    assert "pass_at_1" in result.metrics
    assert "pass_at_5" in result.metrics
    assert result.metrics["pass_at_1"].k == 1  # type: ignore[union-attr]
    assert result.metrics["pass_at_5"].k == 5  # type: ignore[union-attr]


def test_pass_at_k_omitted_when_k_exceeds_trials() -> None:
    result = extract_metrics(keyword_runs(3, 5), k_list=[10])
    assert "pass_at_10" not in result.metrics
    assert any("pass_at_10" in note for note in result.omitted)


def test_cost_omitted_when_no_agent_result_payloads() -> None:
    # Plain KeywordRuns carry no AgentRunResult payloads → cost omitted, not zero-filled.
    result = extract_metrics(keyword_runs(9, 10, with_agent_result=False))
    assert "cost_usd" not in result.metrics
    assert any("cost_usd" in note for note in result.omitted)


def test_cost_present_when_agent_result_payloads() -> None:
    result = extract_metrics(keyword_runs(9, 10, with_agent_result=True, cost_usd=0.05))
    assert isinstance(result.metrics["cost_usd"], ContinuousEvidence)
    assert result.metrics["cost_usd"].mean == pytest.approx(0.05)


def test_latency_always_present_for_keyword_runs() -> None:
    result = extract_metrics(keyword_runs(9, 10))
    assert isinstance(result.metrics["latency_p95_ms"], ContinuousEvidence)
    assert len(result.metrics["latency_p95_ms"].samples) == 10


def test_agent_result_list_path() -> None:
    result = extract_metrics(agent_results(8, 10, cost_usd=0.02))
    assert result.metrics["pass_rate"].successes == 8
    assert isinstance(result.metrics["cost_usd"], ContinuousEvidence)
    assert result.metrics["cost_usd"].mean == pytest.approx(0.02)


def test_tool_hit_rate_only_with_expected_tools() -> None:
    runs = agent_results(10, 10, tool_names=["search", "fetch"])
    without = extract_metrics(runs)
    assert "tool_hit_rate" not in without.metrics
    with_tools = extract_metrics(runs, expected_tools=["search", "fetch"])
    assert isinstance(with_tools.metrics["tool_hit_rate"], ProportionEvidence)
    # All runs hit both expected tools → hit rate 1.0.
    assert with_tools.metrics["tool_hit_rate"].value == pytest.approx(1.0)


def test_tool_hit_rate_partial() -> None:
    # Runs call only "search"; expected {search, fetch} → half the Bernoulli trials hit.
    runs = agent_results(10, 4, tool_names=["search"])
    result = extract_metrics(runs, expected_tools=["search", "fetch"])
    thr = result.metrics["tool_hit_rate"]
    assert isinstance(thr, ProportionEvidence)
    assert thr.successes == 4  # 4 runs × search hit
    assert thr.trials == 8  # 4 runs × 2 expected tools
    assert thr.value == pytest.approx(0.5)


def test_empty_results_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        extract_metrics([])
