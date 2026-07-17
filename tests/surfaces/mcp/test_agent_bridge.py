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

"""The MCP->pydantic-ai bridge: a stub model drives real MCP tools through the handle.

These tests need pydantic-ai (the ``[agent]`` extra); skip cleanly if absent.
No live model is called - a deterministic ``FunctionModel`` scripts the tool
calls, and the tools run against the in-memory echo server through the same
MCPLibrary handle the recorder/metrics keywords use.
"""

from __future__ import annotations

import os

import pytest

from MCPLibrary import MCPLibrary

from ._helpers import build_echo_server

pytest.importorskip("pydantic_ai", reason="the MCP agent-toolset bridge needs the [agent] extra")

_LIVE = pytest.mark.skipif(
    not (os.environ.get("AGENTEVAL_API_KEY") and os.environ.get("AGENTEVAL_MODEL")),
    reason="set AGENTEVAL_MODEL/AGENTEVAL_BASE_URL/AGENTEVAL_API_KEY for the live MCP-agent smoke",
)


def test_as_agent_toolset_builds_a_tool_per_advertised_tool() -> None:
    from pydantic_ai.toolsets import FunctionToolset

    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    lib.connect_to_server(handle)
    try:
        toolset = lib.as_agent_toolset(handle)
        assert isinstance(toolset, FunctionToolset)
        # Every tool the echo server advertises has a built pydantic-ai tool.
        assert set(toolset.tools) == {"echo_back", "search"}
    finally:
        lib.stop_server(handle)


def test_stub_model_executes_mcp_tool_through_the_handle_and_records_it() -> None:
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from AgentEval._core.adapter import get_adapter
    from AgentEval._core.agent_adapter import _map_agent_result

    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    lib.connect_to_server(handle)

    # A deterministic model: first turn calls echo_back, second turn replies DONE.
    turns = {"n": 0}

    def model_fn(messages: list, info: AgentInfo) -> ModelResponse:  # type: ignore[type-arg]
        turns["n"] += 1
        if turns["n"] == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="echo_back", args={"text": "mcp-works"})])
        return ModelResponse(parts=[TextPart("DONE")])

    try:
        toolset = lib.as_agent_toolset(handle)
        # get_adapter("in-process", toolsets=[...]) stores the bridged toolset.
        adapter = get_adapter("in-process", toolsets=[toolset])
        assert adapter._toolsets == [toolset]

        # Drive the toolset with the stub model directly (no live provider).
        agent = Agent(FunctionModel(model_fn), toolsets=[toolset])
        result = agent.run_sync("Use echo_back on 'mcp-works', then say DONE")

        # The tool ran through the REAL echo server, so its result is the echoed text.
        assert result.output == "DONE"

        # pydantic-ai's history + the adapter projection see the executed call WITH result.
        run = _map_agent_result(result)
        echo_calls = [t for t in run.tool_calls if t.name == "echo_back"]
        assert len(echo_calls) == 1
        assert echo_calls[0].args == {"text": "mcp-works"}
        assert echo_calls[0].result == "mcp-works"  # executed through the handle

        # ... and MCPLibrary's own recorder captured the very same call.
        recorded = lib.get_recorded_tool_calls()
        assert lib.get_tool_call_names(recorded) == ["echo_back"]
        assert recorded[0].source == "hosted_mcp"
        assert recorded[0].args == {"text": "mcp-works"}
        assert recorded[0].error is None
    finally:
        lib.stop_server(handle)


def test_toolset_closure_reports_tool_level_errors_as_text() -> None:
    from AgentEval._core.errors import MCPError

    from ._helpers import build_error_server

    lib = MCPLibrary()
    handle = lib.start_server("boom", "in_memory", server_factory=build_error_server)
    lib.connect_to_server(handle)
    try:
        toolset = lib.as_agent_toolset(handle)
        # Invoke the built closure the way pydantic-ai would; a tool-level error
        # comes back as its message text (the model sees the failure), and the
        # call is still recorded.
        fn = toolset.tools["boom"].function
        out = fn()
        assert isinstance(out, str) and out  # non-empty error text, not a raise
        recorded = lib.get_recorded_tool_calls()
        assert recorded[0].name == "boom"
        assert recorded[0].error  # recorder saw the tool-level error
    except MCPError:  # pragma: no cover - defensive; error tools are data, not raises
        pytest.fail("tool-level error should be data, not an MCPError")
    finally:
        lib.stop_server(handle)


@_LIVE
def test_live_in_process_agent_drives_mcp_tool_through_the_handle() -> None:
    """Live smoke: a real model calls a real MCP tool through the shared handle.

    Gated on AGENTEVAL_MODEL/BASE_URL/API_KEY. Asserts the in-process adapter's
    result carries the executed ``echo_back`` call WITH its result, and that
    MCPLibrary's recorder + MetricsLibrary see the very same call.
    """
    from AgentEval._core.adapter import get_adapter
    from MetricsLibrary import MetricsLibrary

    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    lib.connect_to_server(handle)
    try:
        toolset = lib.as_agent_toolset(handle)
        result = get_adapter("in-process", toolsets=[toolset]).run(
            "Use the echo_back tool to echo the text 'mcp-works', then reply DONE"
        )

        echo_calls = [t for t in result.tool_calls if t.name == "echo_back"]
        assert echo_calls, f"model never called echo_back; calls={[t.name for t in result.tool_calls]}"
        assert any("mcp-works" in str(t.result) for t in echo_calls), "executed echo_back result not captured"

        recorded = lib.get_recorded_tool_calls()
        assert lib.was_tool_called(recorded, "echo_back"), "MCPLibrary recorder missed the executed call"

        metrics = MetricsLibrary().get_tool_call_metrics(result)
        assert metrics["per_tool"].get("echo_back", {}).get("count", 0) >= 1
    finally:
        lib.stop_server(handle)
