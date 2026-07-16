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

"""Test doubles for the MCPLibrary surface tests: an in-memory server + adapters."""

from __future__ import annotations

from typing import Any

from AgentEval._core.types import AgentRunResult, ToolCallTrace


def build_echo_server() -> Any:
    """Build a FastMCP server exposing ``echo_back`` and ``search`` tools."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("mcplibrary-test-echo")

    @server.tool(description="Echo the input text verbatim.")
    def echo_back(text: str) -> str:
        return text

    @server.tool(description="Search for the given query.")
    def search(query: str) -> str:
        return f"results for {query}"

    return server


def build_error_server() -> Any:
    """Build a FastMCP server whose one tool always reports a tool-level error."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("mcplibrary-test-error")

    @server.tool(description="Always fails.")
    def boom() -> str:
        raise ValueError("kaboom")

    return server


def trace(name: str, args: dict[str, Any] | None = None, *, error: str | None = None) -> ToolCallTrace:
    """Build a ``ToolCallTrace`` for coverage-metric tests."""
    return ToolCallTrace(name=name, args=args or {}, error=error)


def run_with_calls(*calls: ToolCallTrace, cost_usd: float = 0.0) -> AgentRunResult:
    """Build an ``AgentRunResult`` carrying the given tool calls."""
    return AgentRunResult(response_text="ok", tool_calls=list(calls), cost_usd=cost_usd)


class StubAdapter:
    """An adapter that returns a fixed set of tool calls for every prompt.

    ``calls_for`` maps a prompt substring to the tool names the stub "calls";
    an empty match yields a run with no tool calls.
    """

    name = "stub"

    def __init__(self, *, calls_for: dict[str, list[str]] | None = None, cost_usd: float = 0.01) -> None:
        self._calls_for = calls_for or {}
        self._cost_usd = cost_usd

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        tool_names: list[str] = []
        for needle, names in self._calls_for.items():
            if needle in prompt:
                tool_names = names
                break
        calls = [ToolCallTrace(name=n, args={}) for n in tool_names]
        return AgentRunResult(response_text="ok", tool_calls=calls, cost_usd=self._cost_usd)
