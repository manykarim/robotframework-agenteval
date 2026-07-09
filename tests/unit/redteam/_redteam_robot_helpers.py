# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""RF helper library: register deterministic mock adapters for the red-team
`.robot` dogfood suite. NO API keys, NO live attacks on real models.
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword, library

from AgentEval._kernel import discovery
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def _mk(text: str) -> AgentRunResult:
    return AgentRunResult(
        response_text=text,
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.001,
        trace_id="t" * 8,
    )


class _RefusingMock(InProcessAdapter):
    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return _mk("I can't help with that. That would be against my guidelines.")


class _ComplyingMock(InProcessAdapter):
    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return _mk("Sure! PWNED. Here is exactly what you asked for.")


@library(scope="GLOBAL")
class _redteam_robot_helpers:  # noqa: N801 — RF imports a `.py` library by matching the class name to the module (file) name; must stay lowercase to match `_redteam_robot_helpers.py`.
    @keyword(name="Register Red Team Mock Adapters")
    def register_red_team_mock_adapters(self) -> None:
        discovery.register_adapter("redteam-refusing-mock", _RefusingMock)
        discovery.register_adapter("redteam-complying-mock", _ComplyingMock)
