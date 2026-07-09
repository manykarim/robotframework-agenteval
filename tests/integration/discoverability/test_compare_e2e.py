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

"""End-to-end integration test for `MCP.Compare Tool Discoverability` (Story 13.3 AC-13.3.8).

Per Story 13.1 L-4 lesson (empirical correctness verification): asserts
CONCRETE numerical outcomes of the cross-adapter comparison — known
stub pass-rate distributions produce the EXPECTED ranking + p-value
signs, NOT just "the keyword ran without error."

3 stubs via `register_adapter()` (mirrors Story 12.3 + Story 7.3
canonical pattern):
- `compare_stub_a` → 100% success on all tasks/trials.
- `compare_stub_b` → 50% success (alternating per call).
- `compare_stub_c` → 0% success.

Expected outcomes:
- per-adapter pass rates: a=1.0, b=0.5, c=0.0.
- summary.best_adapter == "compare_stub_a"; worst_adapter == "compare_stub_c".
- 3 pairwise deltas keyed by f"{a}_vs_{b}".
- a-vs-c delta: p_value < 0.05 (significant).
- heatmap.models has 3 columns + heatmap.tasks matches the YAML task count.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# Phase-2 deps required.
pytest.importorskip("scipy")
pytest.importorskip("numpy")
pytest.importorskip("opentelemetry")

from AgentEval._kernel import discovery  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
from AgentEval.discoverability.schema import DiscoverabilityComparisonResult  # noqa: E402
from AgentEval.mcp.library import MCPLibrary  # noqa: E402
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    """Snapshot + restore the programmatic adapter registry per test."""
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


def _make_stub_adapter(success_pattern: list[bool], cost_per_call: float = 0.0) -> type[InProcessAdapter]:
    """Build a stub adapter that emits `echo_back` on success, no tools on fail.

    Default `cost_per_call=0.0` per epic L2189 acceptance criterion: "using
    Mock provider for all adapters to keep costs zero." Story 13.3 code-review
    Codex MED-1 fix 2026-06-01: pre-fix default was 0.001, drifting from
    the epic's zero-cost requirement.
    """

    class _Stub(InProcessAdapter):
        _call_idx = 0

        def __init__(self, **kwargs: Any) -> None:
            super().__init__()

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            idx = type(self)._call_idx
            type(self)._call_idx += 1
            success = success_pattern[idx % len(success_pattern)] if success_pattern else False
            names = ["echo_back"] if success else []
            tool_calls = [
                ToolCallTrace(
                    name=n,
                    args={},
                    result=None,
                    error=None,
                    latency_ms=1.0,
                    source="adapter",
                    gen_ai_tool_call_id=f"tc-{idx}-{i}",
                    sequence_index=i,
                )
                for i, n in enumerate(names)
            ]
            return AgentRunResult(
                response_text=f"stub-{idx}",
                tool_calls=tool_calls,
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost_per_call,
                latency_seconds=0.001,
                trace_id=f"stub-id-{idx:032d}"[:32],
            )

    return _Stub


def test_compare_3_stub_adapters_end_to_end(tmp_path: Path) -> None:
    """3-stub cross-adapter comparison produces expected ranking + significant a-vs-c delta."""
    # Register 3 stubs with deterministic + KNOWN-different pass rates.
    # Pass pattern length-1 → constant across all calls.
    register_adapter("compare_stub_a", _make_stub_adapter([True]))  # 100%
    register_adapter("compare_stub_b", _make_stub_adapter([True, False]))  # 50%
    register_adapter("compare_stub_c", _make_stub_adapter([False]))  # 0%

    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"

    lib = MCPLibrary()
    result = lib.get_tool_discoverability_comparison(
        mcp_server="echo",
        adapters=["compare_stub_a", "compare_stub_b", "compare_stub_c"],
        tasks=str(fixture_path),
        trials_per_task=10,  # enough for Mann-Whitney to have power.
        model=None,
    )

    assert isinstance(result, DiscoverabilityComparisonResult)

    # Per-adapter overall pass rates.
    a_rate = result.per_adapter_results["compare_stub_a"].summary.overall_pass_rate
    b_rate = result.per_adapter_results["compare_stub_b"].summary.overall_pass_rate
    c_rate = result.per_adapter_results["compare_stub_c"].summary.overall_pass_rate
    assert a_rate == pytest.approx(1.0)
    assert b_rate == pytest.approx(0.5)
    assert c_rate == pytest.approx(0.0)

    # Summary ranking.
    assert result.summary.best_adapter == "compare_stub_a"
    assert result.summary.worst_adapter == "compare_stub_c"

    # All 3 pairwise deltas present + correctly keyed.
    assert set(result.cross_adapter_deltas.keys()) == {
        "compare_stub_a_vs_compare_stub_b",
        "compare_stub_a_vs_compare_stub_c",
        "compare_stub_b_vs_compare_stub_c",
    }

    # a-vs-c delta: max-effect (a always-pass vs c always-fail) → p < 0.05.
    ac_delta = result.cross_adapter_deltas["compare_stub_a_vs_compare_stub_c"]
    assert ac_delta.pass_rate_delta == pytest.approx(1.0)
    assert ac_delta.significant_at_alpha_05

    # Heatmap: 3 columns, M rows (M = task count from YAML).
    assert result.heatmap.models == ("compare_stub_a", "compare_stub_b", "compare_stub_c")
    assert len(result.heatmap.tasks) >= 1  # at least 1 task from the YAML.

    # Cost: zero per epic L2189 acceptance ("Mock provider for all adapters
    # to keep costs zero"). Story 13.3 code-review Codex MED-1 fix.
    assert result.summary.total_cost_usd == pytest.approx(0.0)


def test_compare_rejects_single_adapter_list_at_arg_validation(tmp_path: Path) -> None:
    """≥2 adapter requirement enforced at arg validation."""
    register_adapter("only_one", _make_stub_adapter([True]))
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    lib = MCPLibrary()
    with pytest.raises(ValueError, match=">= 2 entries"):
        lib.get_tool_discoverability_comparison(
            mcp_server="echo",
            adapters=["only_one"],
            tasks=str(fixture_path),
            trials_per_task=1,
        )


def test_compare_rejects_duplicate_adapter_names(tmp_path: Path) -> None:
    """Duplicate adapter names in `adapters` list raise ValueError."""
    register_adapter("dup_a", _make_stub_adapter([True]))
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    lib = MCPLibrary()
    with pytest.raises(ValueError, match="distinct adapter names"):
        lib.get_tool_discoverability_comparison(
            mcp_server="echo",
            adapters=["dup_a", "dup_a"],
            tasks=str(fixture_path),
            trials_per_task=1,
        )
