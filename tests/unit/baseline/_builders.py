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

"""Shared result builders for baseline unit tests."""

from __future__ import annotations

from AgentEval.stats.types import KeywordRun
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def keyword_runs(
    successes: int,
    trials: int,
    *,
    latency_seconds: float = 0.1,
    with_agent_result: bool = False,
    cost_usd: float = 0.01,
) -> list[KeywordRun]:
    """Build ``trials`` KeywordRun items; the first ``successes`` are complete."""
    runs: list[KeywordRun] = []
    for i in range(trials):
        result = agent_result(cost_usd=cost_usd) if with_agent_result else None
        runs.append(
            KeywordRun(
                trial_index=i,
                test_id=f"t::trial-{i}",
                keyword_name="Send Prompt",
                result=result,
                error=None,
                completeness="complete" if i < successes else "partial",
                latency_seconds=latency_seconds + 0.001 * i,
                seed=None,
            )
        )
    return runs


def agent_result(
    *,
    completeness: str = "complete",
    cost_usd: float = 0.01,
    latency_seconds: float = 0.1,
    tool_names: list[str] | None = None,
) -> AgentRunResult:
    tool_calls = [
        ToolCallTrace(
            name=name,
            args={},
            result="ok",
            error=None,
            latency_ms=10.0,
            source="hosted_mcp",
            gen_ai_tool_call_id=f"t-{i}",
            sequence_index=i,
        )
        for i, name in enumerate(tool_names or [])
    ]
    return AgentRunResult(
        response_text="ok",
        tool_calls=tool_calls,
        usage=Usage(input_tokens=10, output_tokens=20),
        metadata=AgentRunMetadata(completeness=completeness, mcp_coverage="hosted_in_process"),  # type: ignore[arg-type]
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        trace_id="t-" + "0" * 30,
    )


def agent_results(
    successes: int,
    trials: int,
    *,
    cost_usd: float = 0.01,
    latency_seconds: float = 0.1,
    tool_names: list[str] | None = None,
) -> list[AgentRunResult]:
    return [
        agent_result(
            completeness="complete" if i < successes else "partial",
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
            tool_names=tool_names,
        )
        for i in range(trials)
    ]
