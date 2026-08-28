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

"""Tier-1 metric readers, budget assertions, and the normalized run-metrics record.

Every case builds a hand-made ``AgentRunResult`` - no live model - so the
keywords are exercised against a known ground-truth trace.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from AgentEval._core.errors import BudgetExceededError
from AgentEval._core.types import AgentRunResult, ToolCallTrace, Usage
from MetricsLibrary import ExpectedToolCall, MetricsLibrary, RunMetrics
from MetricsLibrary._record import compute_run_metrics


def _run() -> AgentRunResult:
    """A recorded run: two ``search`` calls (one failed) + one ``fetch`` call."""
    return AgentRunResult(
        response_text="done",
        tool_calls=[
            ToolCallTrace(
                name="search",
                args={"query": "robots"},
                error=None,
                latency_ms=10.0,
                input_tokens=5,
                output_tokens=7,
                cost_usd=0.001,
            ),
            ToolCallTrace(
                name="search",
                args={"query": "androids"},
                error="rate limited",
                latency_ms=20.0,
                input_tokens=3,
                output_tokens=0,
                cost_usd=0.0005,
            ),
            ToolCallTrace(
                name="fetch",
                args={"url": "http://x"},
                error=None,
                latency_ms=5.0,
                input_tokens=2,
                output_tokens=4,
                cost_usd=0.002,
            ),
        ],
        usage=Usage(input_tokens=120, output_tokens=80, cached_input_tokens=30),
        cost_usd=0.0035,
        latency_seconds=1.5,
        trace_id="trace-1",
    )


# --------------------------------------------------------------------------- #
# Readers.                                                                     #
# --------------------------------------------------------------------------- #


def test_get_token_usage_returns_ground_truth() -> None:
    usage = MetricsLibrary().get_token_usage(_run())
    assert usage == {
        "input": 120,
        "output": 80,
        "cached": 30,
        "cache_creation": 0,
        "cache_creation_1h": 0,
        "cache_creation_5m": 0,
    }


def test_get_cost_usd_reads_recorded_value() -> None:
    assert MetricsLibrary().get_cost_usd(_run()) == pytest.approx(0.0035)


def test_get_latency_seconds_reads_recorded_value() -> None:
    assert MetricsLibrary().get_latency_seconds(_run()) == pytest.approx(1.5)


def test_get_tool_call_metrics_per_task_rollup() -> None:
    metrics = MetricsLibrary().get_tool_call_metrics(_run())
    task = metrics["per_task"]
    assert task["count"] == 3
    assert task["passed"] == 2  # error is None
    assert task["failed"] == 1
    assert task["input_tokens"] == 10
    assert task["output_tokens"] == 11
    assert task["cost_usd"] == pytest.approx(0.0035)
    assert task["latency_ms"] == pytest.approx(35.0)


def test_get_tool_call_metrics_per_tool_groups_by_name() -> None:
    metrics = MetricsLibrary().get_tool_call_metrics(_run())
    per_tool = metrics["per_tool"]
    assert set(per_tool) == {"search", "fetch"}

    search = per_tool["search"]
    assert search["count"] == 2
    assert search["passed"] == 1
    assert search["failed"] == 1
    assert search["input_tokens"] == 8
    assert search["output_tokens"] == 7
    assert search["cost_usd"] == pytest.approx(0.0015)
    assert search["latency_ms"] == pytest.approx(30.0)

    fetch = per_tool["fetch"]
    assert fetch["count"] == 1
    assert fetch["passed"] == 1
    assert fetch["failed"] == 0


def test_get_tool_call_metrics_empty_run() -> None:
    empty = AgentRunResult(response_text="nothing")
    metrics = MetricsLibrary().get_tool_call_metrics(empty)
    assert metrics["per_task"]["count"] == 0
    assert metrics["per_tool"] == {}


# --------------------------------------------------------------------------- #
# Budget assertions.                                                           #
# --------------------------------------------------------------------------- #


def test_tokens_used_should_be_below_passes_under_threshold() -> None:
    MetricsLibrary().tokens_used_should_be_below(_run(), 1000)  # 200 < 1000


def test_tokens_used_should_be_below_fails_at_or_over_threshold() -> None:
    lib = MetricsLibrary()
    with pytest.raises(BudgetExceededError) as exc:
        lib.tokens_used_should_be_below(_run(), 200)  # 200 total, strict below
    assert "200" in str(exc.value)


def test_cost_should_be_below_passes_under_threshold() -> None:
    MetricsLibrary().cost_should_be_below(_run(), 0.10)


def test_cost_should_be_below_fails_over_threshold_naming_values() -> None:
    lib = MetricsLibrary()
    with pytest.raises(BudgetExceededError) as exc:
        lib.cost_should_be_below(_run(), 0.001)
    message = str(exc.value)
    assert "0.003500" in message  # actual cost
    assert "0.001000" in message  # threshold


# --------------------------------------------------------------------------- #
# ExpectedToolCall contract + tool_hit_rate.                                   #
# --------------------------------------------------------------------------- #


def test_expected_tool_met_within_bounds_and_required_args() -> None:
    run = _run()
    expected = [
        ExpectedToolCall(tool="search", min_calls=1, max_calls=2, required_args={"query": "robots"}),
        ExpectedToolCall(tool="fetch"),
    ]
    metrics = compute_run_metrics(run, expected)
    assert metrics.expected_total == 2
    assert metrics.expected_met == 2
    assert metrics.tool_hit_rate == pytest.approx(1.0)


def test_expected_tool_unmet_when_never_called() -> None:
    metrics = compute_run_metrics(_run(), [ExpectedToolCall(tool="delete")])
    assert metrics.expected_met == 0
    assert metrics.tool_hit_rate == pytest.approx(0.0)


def test_expected_tool_unmet_outside_max_calls() -> None:
    # search is called twice; max_calls=1 makes the entry unmet.
    metrics = compute_run_metrics(_run(), [ExpectedToolCall(tool="search", max_calls=1)])
    assert metrics.expected_met == 0
    assert metrics.tool_hit_rate == pytest.approx(0.0)


def test_expected_tool_unmet_when_required_arg_key_missing() -> None:
    metrics = compute_run_metrics(_run(), [ExpectedToolCall(tool="fetch", required_args={"missing_key": "x"})])
    assert metrics.expected_met == 0


def test_expected_tool_required_arg_value_none_matches_key_presence() -> None:
    # {"url": None} asserts only that the url arg was passed at all.
    metrics = compute_run_metrics(_run(), [ExpectedToolCall(tool="fetch", required_args={"url": None})])
    assert metrics.expected_met == 1


def test_partial_hit_rate() -> None:
    expected = [ExpectedToolCall(tool="search"), ExpectedToolCall(tool="delete")]
    metrics = compute_run_metrics(_run(), expected)
    assert metrics.expected_met == 1
    assert metrics.expected_total == 2
    assert metrics.tool_hit_rate == pytest.approx(0.5)


def test_get_run_metrics_accepts_dict_contract() -> None:
    metrics = MetricsLibrary().get_run_metrics(_run(), [{"tool": "search", "min_calls": 2}])
    assert metrics.expected_met == 1
    assert metrics.tool_hit_rate == pytest.approx(1.0)


def test_get_run_metrics_rejects_unknown_dict_key() -> None:
    with pytest.raises(ValueError, match="unknown expected-tool keys"):
        MetricsLibrary().get_run_metrics(_run(), [{"tool": "search", "bogus": 1}])


# --------------------------------------------------------------------------- #
# RunMetrics record shape + errors + no-contract hit rate.                     #
# --------------------------------------------------------------------------- #


def test_get_run_metrics_record_fields() -> None:
    metrics = MetricsLibrary().get_run_metrics(_run())
    assert isinstance(metrics, RunMetrics)
    assert metrics.total_tool_calls == 3
    assert metrics.errors == ["rate limited"]
    assert metrics.execution_time_seconds == pytest.approx(1.5)
    assert metrics.usage.input_tokens == 120
    assert metrics.cost_usd == pytest.approx(0.0035)
    # No expected contract => hit rate is 0.0 by convention.
    assert metrics.expected_total == 0
    assert metrics.tool_hit_rate == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# JSON export.                                                                 #
# --------------------------------------------------------------------------- #


def test_export_run_metrics_writes_ground_truth_json(tmp_path: Path) -> None:
    lib = MetricsLibrary()
    record = lib.get_run_metrics(_run(), [ExpectedToolCall(tool="search")])
    dest = tmp_path / "nested" / "metrics.json"

    written = lib.export_run_metrics(record, str(dest))
    assert Path(written) == dest
    assert dest.exists()

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["total_tool_calls"] == 3
    assert data["expected_met"] == 1
    assert data["expected_total"] == 1
    assert data["tool_hit_rate"] == pytest.approx(1.0)
    assert data["errors"] == ["rate limited"]
    assert data["execution_time_seconds"] == pytest.approx(1.5)
    assert data["cost_usd"] == pytest.approx(0.0035)
    assert data["usage"] == {
        "input_tokens": 120,
        "output_tokens": 80,
        "cached_input_tokens": 30,
        "cache_creation_input_tokens": 0,
        "cache_creation_1h_input_tokens": 0,
        "cache_creation_5m_input_tokens": 0,
    }
    assert len(data["tool_calls"]) == 3
    first = data["tool_calls"][0]
    assert first["name"] == "search"
    assert first["args"] == {"query": "robots"}
    assert first["input_tokens"] == 5


def test_export_run_metrics_accepts_agent_run_result(tmp_path: Path) -> None:
    lib = MetricsLibrary()
    dest = tmp_path / "from_run.json"
    lib.export_run_metrics(_run(), str(dest))
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["total_tool_calls"] == 3
    assert data["expected_total"] == 0
