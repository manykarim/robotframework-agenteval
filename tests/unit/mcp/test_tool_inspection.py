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


def test_call_tool_arguments_are_copied_not_referenced(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Mutating the source args dict after `call_tool` returns must NOT mutate the dict the SDK saw.

    Story 3.2 code-review Blind HIGH-2 fix 2026-05-19: the pre-edit
    test was fake-green — it called `call_tool` twice with two
    different literal dicts and verified the second one's content
    arrived. That assertion passes regardless of whether `call_tool`
    does `args = dict(arguments)` or `args = arguments`. Removing
    the defensive copy at `lifecycle.py:497` would leave the
    pre-edit test green. Now we monkeypatch the SDK to capture the
    dict object reference + verify it's a different object than the
    caller's source dict.
    """
    from types import SimpleNamespace

    from mcp import ClientSession

    captured: dict[str, Any] = {}

    async def _capture(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        captured["seen"] = arguments
        return SimpleNamespace(content=[], isError=False)

    monkeypatch.setattr(ClientSession, "call_tool", _capture)
    src = {"text": "orig"}
    call_tool(in_memory_handle, "echo_back", src)
    src["text"] = "MUTATED"
    # Defensive copy: SDK saw a DIFFERENT object than `src` AND that
    # object's `text` value is the pre-mutation `"orig"`.
    assert captured["seen"] is not src
    assert captured["seen"]["text"] == "orig"


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

    async def _boom(self: Any, cursor: str | None = None) -> Any:
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


# --------------------------------------------------------------------------- #
# Story 3.2 code-review patches 2026-05-19 — additional behavioral tests
# --------------------------------------------------------------------------- #


def test_list_tools_follows_next_cursor_pagination(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Story 3.2 code-review Blind HIGH-1 fix 2026-05-19: `list_tools`
    must follow `nextCursor` to retrieve the full tool list. SDK
    signature: `list_tools(self, cursor: str | None = None, ...)`
    returns `ListToolsResult` with `nextCursor: Cursor | None`. The
    pre-edit code ignored the cursor + dropped pages.
    """
    from types import SimpleNamespace

    from mcp import ClientSession

    call_count = {"n": 0}
    pages = [
        SimpleNamespace(
            tools=[SimpleNamespace(name="t1", description="d1", inputSchema={}, outputSchema=None)],
            nextCursor="cursor-2",
        ),
        SimpleNamespace(
            tools=[SimpleNamespace(name="t2", description="d2", inputSchema={}, outputSchema=None)],
            nextCursor="cursor-3",
        ),
        SimpleNamespace(
            tools=[SimpleNamespace(name="t3", description="d3", inputSchema={}, outputSchema=None)],
            nextCursor=None,
        ),
    ]
    received_cursors: list[str | None] = []

    async def _paged(self: Any, cursor: str | None = None) -> Any:
        received_cursors.append(cursor)
        page = pages[call_count["n"]]
        call_count["n"] += 1
        return page

    monkeypatch.setattr(ClientSession, "list_tools", _paged)
    tools = list_tools(in_memory_handle)
    assert [t.name for t in tools] == ["t1", "t2", "t3"]
    assert received_cursors == [None, "cursor-2", "cursor-3"]


def test_list_tools_stops_when_next_cursor_is_empty(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Single-page case still works (no infinite loop on empty cursor)."""
    from types import SimpleNamespace

    from mcp import ClientSession

    async def _single(self: Any, cursor: str | None = None) -> Any:
        return SimpleNamespace(
            tools=[SimpleNamespace(name="solo", description="", inputSchema={}, outputSchema=None)],
            nextCursor=None,
        )

    monkeypatch.setattr(ClientSession, "list_tools", _single)
    tools = list_tools(in_memory_handle)
    assert len(tools) == 1
    assert tools[0].name == "solo"


def test_list_tools_handles_result_with_missing_tools_attr(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Story 3.2 code-review Codex LOW-2 fix 2026-05-19: defensive
    `getattr(page, 'tools', None) or []` on missing-attr case.
    """
    from types import SimpleNamespace

    from mcp import ClientSession

    async def _no_tools_attr(self: Any, cursor: str | None = None) -> Any:
        return SimpleNamespace(nextCursor=None)  # NO `tools` attr at all

    monkeypatch.setattr(ClientSession, "list_tools", _no_tools_attr)
    tools = list_tools(in_memory_handle)
    assert tools == []


@pytest.mark.parametrize(
    "exc_factory",
    [
        pytest.param(
            lambda: __import__("anyio").EndOfStream(),
            id="anyio.EndOfStream",
        ),
        pytest.param(
            lambda: ConnectionError("network gone"),
            id="ConnectionError",
        ),
        pytest.param(
            lambda: BrokenPipeError("pipe died"),
            id="BrokenPipeError",
        ),
    ],
)
def test_call_tool_maps_extra_transport_signatures_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch,
    in_memory_handle: MCPServerHandle,
    exc_factory: Any,
) -> None:
    """Story 3.2 code-review Codex LOW-1 fix 2026-05-19: extend
    coverage to the 3 documented signatures the pre-edit suite missed
    (`anyio.EndOfStream`, `ConnectionError`, `BrokenPipeError`).
    """
    from mcp import ClientSession

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise exc_factory()

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        call_tool(in_memory_handle, "echo_back", {"text": "x"})
    # __cause__ chain preserves the original exception for forensics.
    assert isinstance(exc_info.value.__cause__, type(exc_factory()))


def test_call_tool_maps_mcp_error_connection_closed_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Story 3.2 code-review Codex HIGH-2 fix 2026-05-19 (REAL
    PRODUCTION SCENARIO): stdio subprocess crashes mid-call surface
    as `mcp.shared.exceptions.McpError("Connection closed")` from the
    SDK's JSON-RPC layer — NOT as anyio/stdlib transport exceptions.
    The pre-edit classifier missed this canonical failure mode.
    """
    from mcp import ClientSession
    from mcp.shared.exceptions import McpError
    from mcp.types import ErrorData

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise McpError(ErrorData(code=-32000, message="Connection closed"))

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        call_tool(in_memory_handle, "echo_back", {"text": "x"})
    assert exc_info.value.last_operation == "call_tool"
    assert isinstance(exc_info.value.__cause__, McpError)


def test_call_tool_does_not_map_generic_mcp_error_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Generic protocol-level McpError (e.g., -32601 Method not found)
    is NOT a transport failure — must propagate raw, NOT be wrapped.
    """
    from mcp import ClientSession
    from mcp.shared.exceptions import McpError
    from mcp.types import ErrorData

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise McpError(ErrorData(code=-32601, message="Method not found"))

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(McpError, match="Method not found"):
        call_tool(in_memory_handle, "echo_back", {"text": "x"})


def test_call_tool_unwraps_exception_group_with_connection_lost_child(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Story 3.2 code-review 2-way HIGH 2026-05-19 (Blind MED + Codex
    HIGH Probe 6b): anyio task-group unwinds in Python 3.11+ wrap
    transport-layer failures in `BaseExceptionGroup` when multiple
    tasks fail simultaneously. The classifier must recurse so the
    typed-error contract holds.
    """
    import anyio
    from mcp import ClientSession

    async def _boom(self: Any, name: str, arguments: dict[str, Any]) -> Any:
        raise BaseExceptionGroup(
            "transport failure",
            [anyio.ClosedResourceError("inner stream closed")],
        )

    monkeypatch.setattr(ClientSession, "call_tool", _boom)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        call_tool(in_memory_handle, "echo_back", {"text": "x"})
    # `_representative_cause` preserves the inner anyio exception in
    # `__cause__` rather than the synthetic group wrapper — operators
    # tracing the failure see the real transport-layer cause.
    assert isinstance(exc_info.value.__cause__, anyio.ClosedResourceError)


def test_call_tool_initialize_handshake_transport_failure_maps_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Story 3.2 code-review Edge-cases HIGH-2 fix 2026-05-19:
    transport-layer failures DURING `initialize()` (subprocess died
    mid-handshake) must also map to `MCPConnectionLostError`, not
    leak raw anyio exceptions. The pre-edit `try/except` wrapper only
    covered the `session.call_tool()` window, not the
    `_initialize_with_typed_error_mapping` step.
    """
    import anyio
    from mcp import ClientSession

    async def _boom_init(self: Any) -> Any:
        raise anyio.BrokenResourceError("init died mid-handshake")

    monkeypatch.setattr(ClientSession, "initialize", _boom_init)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        call_tool(in_memory_handle, "echo_back", {"text": "x"})
    assert exc_info.value.last_operation == "call_tool"


def test_list_tools_initialize_handshake_transport_failure_maps_to_connection_lost(
    monkeypatch: pytest.MonkeyPatch, in_memory_handle: MCPServerHandle
) -> None:
    """Sibling test for `list_tools` — same pre-edit gap."""
    import anyio
    from mcp import ClientSession

    async def _boom_init(self: Any) -> Any:
        raise anyio.ClosedResourceError("init stream closed")

    monkeypatch.setattr(ClientSession, "initialize", _boom_init)
    with pytest.raises(MCPConnectionLostError) as exc_info:
        list_tools(in_memory_handle)
    assert exc_info.value.last_operation == "list_tools"


def test_map_call_result_empty_content_with_is_error_yields_fallback_message() -> None:
    """Story 3.2 code-review 2-way HIGH 2026-05-19 (Edge-cases HIGH-1 +
    Codex MED-1 Probe 8b): `is_error=True` with `content=[]` must NOT
    leave `error_message=None` — that violates the dataclass docstring
    contract ("populated when is_error=True; None otherwise").
    """
    from types import SimpleNamespace

    from AgentEval.mcp.lifecycle import _map_call_result

    result = _map_call_result(
        SimpleNamespace(isError=True, content=[]),
        latency_ms=1.0,
    )
    assert result.is_error is True
    assert result.error_message is not None
    assert "no content" in result.error_message


def test_map_call_result_non_text_content_block_with_is_error_yields_typed_fallback() -> None:
    """Same fix, non-empty-but-non-text case: fallback message names the actual block type."""
    from types import SimpleNamespace

    from AgentEval.mcp.lifecycle import _map_call_result

    result = _map_call_result(
        SimpleNamespace(isError=True, content=[{"type": "image", "data": "..."}]),
        latency_ms=1.0,
    )
    assert result.is_error is True
    assert result.error_message is not None
    assert "image" in result.error_message
