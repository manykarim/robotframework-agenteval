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

"""Unit tests for Story 3.2: MCP tool inspection keywords (List Tools + Call Tool)."""

from __future__ import annotations

import dataclasses
import re
import sys
from typing import Any

import pytest

from AgentEval._kernel.tier import get_keyword_tier, tier_badge
from AgentEval.errors import (
    AgentEvalCompatError,
    AgentEvalError,
    MCPConnectionLostError,
)
from AgentEval.mcp.bundled.echo import build_server
from AgentEval.mcp.library import MCPLibrary
from AgentEval.mcp.lifecycle import (
    MCPServerHandle,
    MCPTool,
    MCPToolResult,
    call_tool,
    list_tools,
    start_server,
)


@pytest.fixture
def lib() -> MCPLibrary:
    return MCPLibrary()


@pytest.fixture
def in_memory_handle() -> MCPServerHandle:
    return start_server(name="echo", transport="in_memory", server_factory=build_server)


@pytest.fixture
def stdio_handle() -> MCPServerHandle:
    return start_server(
        name="echo",
        transport="stdio",
        command=sys.executable,
        args=["-m", "AgentEval.mcp.bundled.echo"],
    )


# --------------------------------------------------------------------------- #
# MCPTool dataclass shape (AC-3.2.1)
# --------------------------------------------------------------------------- #


def test_mcptool_is_frozen_dataclass() -> None:
    tool = MCPTool(name="x", description="d", input_schema={"type": "object"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        tool.name = "renamed"  # type: ignore[misc]


def test_mcptool_default_input_schema_is_empty_dict() -> None:
    tool = MCPTool(name="x", description="d")
    assert tool.input_schema == {}
    assert tool.output_schema is None


# --------------------------------------------------------------------------- #
# MCPToolResult dataclass shape (AC-3.2.2)
# --------------------------------------------------------------------------- #


def test_mcptoolresult_is_frozen_dataclass() -> None:
    result = MCPToolResult()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.is_error = True  # type: ignore[misc]


def test_mcptoolresult_defaults_are_empty_and_zero() -> None:
    result = MCPToolResult()
    assert result.content == []
    assert result.is_error is False
    assert result.error_message is None
    assert result.latency_ms == 0.0
    assert result.correlation_id == ""


# --------------------------------------------------------------------------- #
# list_tools — happy path (AC-3.2.3)
# --------------------------------------------------------------------------- #


def test_list_tools_in_memory_returns_echo_back_tool(in_memory_handle: MCPServerHandle) -> None:
    tools = list_tools(in_memory_handle)
    assert len(tools) == 1
    assert tools[0].name == "echo_back"
    assert "echo" in tools[0].description.lower()
    # The bundled echo server's input_schema is generated from the
    # `def echo_back(text: str) -> str` signature.
    assert tools[0].input_schema.get("type") == "object"
    assert "text" in tools[0].input_schema.get("properties", {})


def test_list_tools_stdio_returns_echo_back_tool(stdio_handle: MCPServerHandle) -> None:
    tools = list_tools(stdio_handle)
    assert len(tools) == 1
    assert tools[0].name == "echo_back"


def test_list_tools_returns_list_of_mcptool(in_memory_handle: MCPServerHandle) -> None:
    tools = list_tools(in_memory_handle)
    assert all(isinstance(t, MCPTool) for t in tools)


# --------------------------------------------------------------------------- #
# call_tool — happy path (AC-3.2.4)
# --------------------------------------------------------------------------- #


def test_call_tool_in_memory_happy_path(in_memory_handle: MCPServerHandle) -> None:
    result = call_tool(in_memory_handle, "echo_back", {"text": "hello"})
    assert isinstance(result, MCPToolResult)
    assert result.is_error is False
    assert result.error_message is None
    # The echo content should appear in at least one text-block.
    text_blocks = [b for b in result.content if b.get("type") == "text"]
    assert any("hello" in (b.get("text") or "") for b in text_blocks)


def test_call_tool_stdio_happy_path(stdio_handle: MCPServerHandle) -> None:
    result = call_tool(stdio_handle, "echo_back", {"text": "world"})
    assert result.is_error is False
    text_blocks = [b for b in result.content if b.get("type") == "text"]
    assert any("world" in (b.get("text") or "") for b in text_blocks)


def test_call_tool_arguments_default_to_empty_dict(in_memory_handle: MCPServerHandle) -> None:
    # echo_back has a required `text` arg, so omitting it should yield is_error=True
    # — this verifies arguments default to {} (NOT None which would crash the SDK).
    result = call_tool(in_memory_handle, "echo_back")
    assert result.is_error is True
    assert result.error_message is not None


def test_call_tool_arguments_are_copied_not_referenced(in_memory_handle: MCPServerHandle) -> None:
    """Mutating the source args dict after call must not affect a future call."""
    args = {"text": "first"}
    call_tool(in_memory_handle, "echo_back", args)
    args["text"] = "MUTATED"
    # The internal copy preserved the first value; a follow-up call sees fresh args.
    result2 = call_tool(in_memory_handle, "echo_back", {"text": "second"})
    text_blocks = [b for b in result2.content if b.get("type") == "text"]
    assert any("second" in (b.get("text") or "") for b in text_blocks)


# --------------------------------------------------------------------------- #
# call_tool — latency + correlation_id invariants (AC-3.2.4 + 3.2.9)
# --------------------------------------------------------------------------- #


def test_call_tool_latency_ms_is_positive(in_memory_handle: MCPServerHandle) -> None:
    result = call_tool(in_memory_handle, "echo_back", {"text": "lat"})
    assert result.latency_ms > 0.0


def test_call_tool_correlation_id_is_uuid4_hex(in_memory_handle: MCPServerHandle) -> None:
    result = call_tool(in_memory_handle, "echo_back", {"text": "cid"})
    assert isinstance(result.correlation_id, str)
    assert re.fullmatch(r"[0-9a-f]{32}", result.correlation_id) is not None


def test_call_tool_correlation_id_is_unique_per_call(in_memory_handle: MCPServerHandle) -> None:
    r1 = call_tool(in_memory_handle, "echo_back", {"text": "a"})
    r2 = call_tool(in_memory_handle, "echo_back", {"text": "b"})
    assert r1.correlation_id != r2.correlation_id


# --------------------------------------------------------------------------- #
# call_tool — error responses are first-class data (AC-3.2.5)
# --------------------------------------------------------------------------- #


def test_call_tool_missing_required_arg_returns_is_error_no_exception(
    in_memory_handle: MCPServerHandle,
) -> None:
    """echo_back requires `text` — omitting it must NOT raise; must return is_error=True."""
    result = call_tool(in_memory_handle, "echo_back", {})
    assert result.is_error is True
    assert result.error_message is not None
    assert isinstance(result.error_message, str)


def test_call_tool_unknown_tool_returns_is_error(in_memory_handle: MCPServerHandle) -> None:
    """Calling a tool the server doesn't advertise should yield a server-side error response."""
    result = call_tool(in_memory_handle, "nonexistent_tool", {})
    assert result.is_error is True
    assert result.error_message is not None


# --------------------------------------------------------------------------- #
# Error class hierarchy (AC-3.2.6)
# --------------------------------------------------------------------------- #


def test_mcp_connection_lost_inherits_compat_error() -> None:
    assert issubclass(MCPConnectionLostError, AgentEvalCompatError)
    assert issubclass(MCPConnectionLostError, AgentEvalError)


def test_mcp_connection_lost_error_code() -> None:
    err = MCPConnectionLostError("boom")
    assert err.error_code == "MCP_CONNECTION_LOST"


def test_mcp_connection_lost_str_includes_error_code() -> None:
    err = MCPConnectionLostError("transport went away")
    # Inherits the base AgentEvalError `__str__` (H_R7) which prepends `<error_code>: `.
    assert str(err) == "MCP_CONNECTION_LOST: transport went away"


def test_mcp_connection_lost_carries_structured_attrs() -> None:
    err = MCPConnectionLostError(
        "boom",
        server_name="echo",
        last_operation="call_tool",
        fix_suggestion="restart the server",
    )
    assert err.server_name == "echo"
    assert err.last_operation == "call_tool"
    assert err.fix_suggestion == "restart the server"


def test_mcp_connection_lost_attrs_default_to_none() -> None:
    err = MCPConnectionLostError("boom")
    assert err.server_name is None
    assert err.last_operation is None
    assert err.fix_suggestion is None


# --------------------------------------------------------------------------- #
# MCPConnectionLostError raise site (AC-3.2.6 behavioral)
# --------------------------------------------------------------------------- #


def test_list_tools_maps_anyio_closed_resource_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch,
    in_memory_handle: MCPServerHandle,
) -> None:
    """Inject `anyio.ClosedResourceError` at the SDK's `list_tools` call site;
    verify it maps to `MCPConnectionLostError` with the documented attrs +
    no traceback leakage of the raw anyio type.
    """
    import anyio
    from mcp import ClientSession

    async def _boom(self: Any) -> Any:
        raise anyio.ClosedResourceError("simulated stream close")

    monkeypatch.setattr(ClientSession, "list_tools", _boom)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        list_tools(in_memory_handle)
    assert exc_info.value.error_code == "MCP_CONNECTION_LOST"
    assert exc_info.value.server_name == "echo"
    assert exc_info.value.last_operation == "list_tools"
    assert exc_info.value.fix_suggestion is not None
    # __cause__ preserves the original anyio exception for forensics.
    assert isinstance(exc_info.value.__cause__, anyio.ClosedResourceError)


def test_call_tool_maps_anyio_broken_resource_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch,
    in_memory_handle: MCPServerHandle,
) -> None:
    import anyio
    from mcp import ClientSession

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise anyio.BrokenResourceError("simulated peer reset")

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        call_tool(in_memory_handle, "echo_back", {"text": "x"})
    assert exc_info.value.last_operation == "call_tool"
    assert isinstance(exc_info.value.__cause__, anyio.BrokenResourceError)


def test_call_tool_does_not_map_unrelated_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    in_memory_handle: MCPServerHandle,
) -> None:
    """A `ValueError` from inside the SDK must propagate as-is — only
    transport-layer exceptions get mapped to MCPConnectionLostError.
    """
    from mcp import ClientSession

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise ValueError("nothing to do with transport")

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(ValueError, match="nothing to do with transport"):
        call_tool(in_memory_handle, "echo_back", {"text": "x"})


# --------------------------------------------------------------------------- #
# Library keyword surface (AC-3.2.7)
# --------------------------------------------------------------------------- #


def test_library_list_tools_keyword(lib: MCPLibrary, in_memory_handle: MCPServerHandle) -> None:
    tools = lib.list_tools(in_memory_handle)
    assert isinstance(tools, list)
    assert all(isinstance(t, MCPTool) for t in tools)


def test_library_call_tool_keyword(lib: MCPLibrary, in_memory_handle: MCPServerHandle) -> None:
    result = lib.call_tool(in_memory_handle, "echo_back", {"text": "lib"})
    assert isinstance(result, MCPToolResult)
    assert result.is_error is False


def test_library_call_tool_arguments_default(lib: MCPLibrary, in_memory_handle: MCPServerHandle) -> None:
    """The keyword's `arguments` parameter defaults to `None`, mapped to `{}` internally."""
    result = lib.call_tool(in_memory_handle, "echo_back")
    assert result.is_error is True  # missing required arg → server error response


# --------------------------------------------------------------------------- #
# Streamable HTTP passthrough still rejected on Story 3.2 keywords (AC-3.2.3 + 3.2.4)
# --------------------------------------------------------------------------- #


def test_list_tools_streamable_http_raises() -> None:
    handle = start_server(name="remote", transport="streamable_http")
    with pytest.raises(ValueError, match="Phase-1 passthrough"):
        list_tools(handle)


def test_call_tool_streamable_http_raises() -> None:
    handle = start_server(name="remote", transport="streamable_http")
    with pytest.raises(ValueError, match="Phase-1 passthrough"):
        call_tool(handle, "echo_back", {"text": "x"})


# --------------------------------------------------------------------------- #
# Direct-construction handle validation (AC-3.2.3 + 3.2.4 — production-path)
# --------------------------------------------------------------------------- #


def test_list_tools_handle_missing_command_raises_value_error() -> None:
    """Bypass `start_server`'s validation by constructing handle directly;
    `list_tools` must still surface a clean ValueError (no bare assert stripped under -O).
    """
    handle = MCPServerHandle(name="echo", transport="stdio", command=None)
    with pytest.raises(ValueError, match="stdio transport requires"):
        list_tools(handle)


def test_call_tool_handle_missing_factory_raises_value_error() -> None:
    handle = MCPServerHandle(name="echo", transport="in_memory", server_factory=None)
    with pytest.raises(ValueError, match="in_memory transport requires"):
        call_tool(handle, "echo_back", {"text": "x"})


# --------------------------------------------------------------------------- #
# Story 1b.6 conventions invariants (AC-3.2.8)
# --------------------------------------------------------------------------- #


STORY_3_2_KEYWORDS = ["list_tools", "call_tool"]


@pytest.mark.parametrize("method_name", STORY_3_2_KEYWORDS)
def test_story_3_2_keyword_has_tier_1_annotation(method_name: str) -> None:
    func = getattr(MCPLibrary, method_name)
    assert get_keyword_tier(func) == 1


@pytest.mark.parametrize("method_name", STORY_3_2_KEYWORDS)
def test_story_3_2_keyword_docstring_has_tier_1_badge(method_name: str) -> None:
    doc = getattr(MCPLibrary, method_name).__doc__ or ""
    assert tier_badge(1) in doc


@pytest.mark.parametrize("method_name", STORY_3_2_KEYWORDS)
def test_story_3_2_keyword_has_robot_marker(method_name: str) -> None:
    assert hasattr(getattr(MCPLibrary, method_name), "robot_name")


@pytest.mark.parametrize("method_name", STORY_3_2_KEYWORDS)
def test_story_3_2_keyword_is_not_async(method_name: str) -> None:
    import inspect

    assert not inspect.iscoroutinefunction(getattr(MCPLibrary, method_name))
