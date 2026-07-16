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

"""Live lifecycle keywords: in-memory round-trips, the [mcp] gate, arg-form rules."""

from __future__ import annotations

import pytest

import MCPLibrary.library as library_module
from AgentEval._core.errors import MCPError, MissingExtraError
from MCPLibrary import MCPLibrary

from ._helpers import build_echo_server, build_error_server


def test_start_server_needs_mcp_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate the MCP SDK being absent: the probe module cannot be found.
    monkeypatch.setattr(library_module, "_LIVE_BACKEND_PROBE", "definitely_not_installed_xyz")
    lib = MCPLibrary()
    with pytest.raises(MissingExtraError) as exc:
        lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    assert exc.value.extra == "mcp"
    assert "[mcp]" in str(exc.value)


def test_connect_needs_mcp_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(library_module, "_LIVE_BACKEND_PROBE", "definitely_not_installed_xyz")
    lib = MCPLibrary()
    with pytest.raises(MissingExtraError) as exc:
        lib.connect_to_server(object())
    assert exc.value.extra == "mcp"


def test_call_tool_conflicting_arg_forms_is_structured_error() -> None:
    lib = MCPLibrary()
    # Both a dict and inline kwargs -> rejected before any server work.
    with pytest.raises(MCPError) as exc:
        lib.call_tool(object(), "search", arguments={"query": "x"}, query="y")
    assert exc.value.error_code == "MCP_ERROR"
    assert "only one form" in str(exc.value) or "one form" in str(exc.value)


def test_in_memory_connect_lists_and_calls_tools() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)

    session = lib.connect_to_server(handle)
    assert session.protocol_version
    assert session.transport == "in_memory"

    tools = lib.list_tools(handle)
    names = {t.name for t in tools}
    assert "echo_back" in names
    assert "search" in names

    lib.stop_server(handle)


def test_call_tool_with_rf_kwargs_routes_arguments() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    # `MCP.Call Tool    search    query=robots` -> {"query": "robots"}.
    result = lib.call_tool(handle, "search", query="robots")
    assert result.is_error is False
    assert any("robots" in (block.get("text") or "") for block in result.content)


def test_call_tool_with_dict_form() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    result = lib.call_tool(handle, "echo_back", arguments={"text": "hello"})
    assert result.is_error is False
    assert any("hello" in (block.get("text") or "") for block in result.content)


def test_call_tool_tool_level_error_is_data_not_exception() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("boom", "in_memory", server_factory=build_error_server)
    result = lib.call_tool(handle, "boom")
    assert result.is_error is True
    assert result.error_message


def test_start_server_stdio_requires_command() -> None:
    lib = MCPLibrary()
    with pytest.raises(ValueError):
        lib.start_server("x", "stdio")


def test_streamable_http_is_rejected_on_connect() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("x", "streamable_http")
    with pytest.raises(ValueError):
        lib.connect_to_server(handle)
