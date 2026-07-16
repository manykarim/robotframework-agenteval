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

"""Test doubles for the subagent surface - no real LLM is ever called."""

from __future__ import annotations

from typing import Any

from AgentEval._core import AgentRunResult, ToolCallTrace


class FakeRoutingAdapter:
    """An adapter that delegates to a subagent looked up from a prompt table.

    Satisfies the spine ``Adapter`` protocol (``name`` + ``run``). A prompt with
    no table entry produces a run with zero delegations.
    """

    name = "fake"

    def __init__(self, table: dict[str, str] | None = None, *, cost_usd: float = 0.0, **kwargs: Any) -> None:
        self._table = dict(table or {})
        self._cost_usd = cost_usd

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        target = self._table.get(prompt)
        tool_calls: list[ToolCallTrace] = []
        if target:
            tool_calls.append(ToolCallTrace(name="Task", args={"subagent_type": target}, sequence_index=0))
        return AgentRunResult(
            response_text=f"handled: {prompt}",
            tool_calls=tool_calls,
            cost_usd=self._cost_usd,
        )


def delegating_result(*subagents: str) -> AgentRunResult:
    """Build an ``AgentRunResult`` whose tool calls delegate to each subagent."""
    tool_calls = [
        ToolCallTrace(name="Task", args={"subagent_type": name}, sequence_index=index)
        for index, name in enumerate(subagents)
    ]
    return AgentRunResult(response_text="ok", tool_calls=tool_calls)
