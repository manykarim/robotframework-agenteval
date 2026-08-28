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

from ._helpers import build_echo_server, build_error_server, build_server_with_instructions


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


def test_connect_captures_server_instructions() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("guide", "in_memory", server_factory=build_server_with_instructions)
    session = lib.connect_to_server(handle)
    # Captured on the handshake and readable both ways.
    assert session.instructions == "Build a suite before deleting."
    assert lib.get_server_instructions(session) == "Build a suite before deleting."
    lib.stop_server(handle)


def test_connect_without_instructions_reports_none() -> None:
    lib = MCPLibrary()
    handle = lib.start_server("echo", "in_memory", server_factory=build_echo_server)
    session = lib.connect_to_server(handle)
    # A server that advertises no instructions yields None, not an error/placeholder.
    assert session.instructions is None
    assert lib.get_server_instructions(session) is None
    lib.stop_server(handle)


def test_build_session_meta_instructions_type_guard() -> None:
    from types import SimpleNamespace

    from MCPLibrary._lifecycle import _build_session_meta

    handle = SimpleNamespace(name="s", transport="stdio")

    def init_result(instructions: object) -> SimpleNamespace:
        return SimpleNamespace(protocolVersion="2025-06-18", serverInfo={"name": "x"}, instructions=instructions)

    assert _build_session_meta(handle, init_result("GUIDE")).instructions == "GUIDE"
    assert _build_session_meta(handle, init_result("")).instructions == ""  # empty string is a set value, not None
    assert _build_session_meta(handle, init_result(123)).instructions is None  # non-str -> None (isinstance guard)
    assert _build_session_meta(handle, init_result(None)).instructions is None


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


def test_remote_transport_requires_url() -> None:
    lib = MCPLibrary()
    for transport in ("streamable_http", "sse"):
        with pytest.raises(ValueError, match="url"):
            lib.start_server("x", transport)


def test_remote_handle_builds_and_redacts_headers() -> None:
    lib = MCPLibrary()
    handle = lib.start_server(
        "api",
        "streamable_http",
        url="https://host/mcp",
        headers={"Authorization": "Bearer ${API_KEY}"},
    )
    assert handle.transport == "streamable_http"
    assert handle.url == "https://host/mcp"
    # The handle repr redacts header VALUES (never a bearer token / ${VAR}).
    assert "Bearer" not in repr(handle)
    assert "API_KEY" not in repr(handle)
    assert "***" in repr(handle)


def test_resolve_headers_expands_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from MCPLibrary._lifecycle import _resolve_headers

    monkeypatch.setenv("API_KEY", "sekret-123")
    assert _resolve_headers({"Authorization": "Bearer ${API_KEY}"}) == {"Authorization": "Bearer sekret-123"}


def test_resolve_headers_missing_var_fails_without_leaking(monkeypatch: pytest.MonkeyPatch) -> None:
    from MCPLibrary._lifecycle import _resolve_headers

    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(MCPError) as exc:
        _resolve_headers({"Authorization": "Bearer ${MISSING_KEY}"})
    assert "MISSING_KEY" in str(exc.value)


def test_open_session_dispatches_http_with_resolved_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    import MCPLibrary._lifecycle as lifecycle

    monkeypatch.setenv("API_KEY", "sekret-xyz")
    captured: dict[str, object] = {}

    async def fake_open_http_session(*, url: str, headers: dict[str, str] | None = None) -> str:
        captured["url"] = url
        captured["headers"] = headers
        return "SESSION"

    monkeypatch.setattr(lifecycle, "open_http_session", fake_open_http_session)
    handle = lifecycle.start_server(
        name="api",
        transport="streamable_http",
        url="https://host/mcp",
        headers={"Authorization": "Bearer ${API_KEY}"},
    )
    result = asyncio.run(lifecycle._open_session(handle))
    assert result == "SESSION"
    assert captured["url"] == "https://host/mcp"
    # Headers are resolved from env at connect time and passed to the transport only.
    assert captured["headers"] == {"Authorization": "Bearer sekret-xyz"}
