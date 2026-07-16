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

"""Live MCP server lifecycle over the MCP SDK - needs the ``[mcp]`` extra.

A handle captures how to open a session; each operation re-opens a fresh
session, runs the MCP handshake, does its work, and tears down. This keeps
the sync keyword world free of a long-lived background event loop. Only
``stdio`` and ``in_memory`` transports are wired; ``streamable_http`` is
rejected. Transport and handshake failures surface as ``MCPError``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp.shared.exceptions import McpError

from AgentEval._core import run_async
from AgentEval._core.errors import MCPError
from MCPLibrary._transport import (
    Transport,
    TransportSession,
    open_in_memory_session,
    open_stdio_session,
)

__all__ = [
    "MCPServerHandle",
    "MCPSession",
    "MCPTool",
    "MCPToolResult",
    "start_server",
    "connect_to_server",
    "stop_server",
    "list_tools",
    "call_tool",
]

# The MCP package version range this library is built and tested against.
SUPPORTED_RANGE = "mcp>=1.0,<2.0"


@dataclass(frozen=True)
class MCPServerHandle:
    """Describes how to (re-)open a session to an MCP server.

    Holds connection parameters, not a live session - each operation re-opens.
    """

    name: str
    transport: Transport
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    server_factory: Callable[[], Any] | None = None


@dataclass(frozen=True)
class MCPSession:
    """Handshake metadata captured after a successful ``Connect To Server``.

    Not a live session - the underlying SDK session was already torn down.
    """

    name: str
    transport: Transport
    protocol_version: str
    server_info: dict[str, Any]


@dataclass(frozen=True)
class MCPTool:
    """One tool advertised by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class MCPToolResult:
    """The result of one ``Call Tool`` invocation.

    Tool-level errors are data (``is_error=True`` with ``error_message``);
    infrastructure failures raise ``MCPError`` instead.
    """

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    error_message: str | None = None
    latency_ms: float = 0.0
    correlation_id: str = ""


def start_server(
    *,
    name: str,
    transport: Transport,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    server_factory: Callable[[], Any] | None = None,
) -> MCPServerHandle:
    """Build an ``MCPServerHandle``. Pure - no subprocess is spawned yet."""
    if transport == "stdio":
        if not command:
            raise ValueError("stdio transport requires `command`")
    elif transport == "in_memory":
        if server_factory is None:
            raise ValueError("in_memory transport requires `server_factory`")
    elif transport == "streamable_http":
        pass
    else:
        raise ValueError(
            f"unsupported transport {transport!r}; must be one of 'stdio' | 'streamable_http' | 'in_memory'"
        )
    return MCPServerHandle(
        name=name,
        transport=transport,
        command=command,
        args=tuple(args or ()),
        env=dict(env) if env is not None else None,
        server_factory=server_factory,
    )


def _validate_for_connect(handle: MCPServerHandle) -> None:
    """Reject ``streamable_http`` and verify transport-required handle params."""
    if handle.transport == "streamable_http":
        raise ValueError("streamable_http transport is not supported; use 'stdio' or 'in_memory'")
    if handle.transport == "stdio" and not handle.command:
        raise ValueError("stdio transport requires `command` on the handle")
    if handle.transport == "in_memory" and handle.server_factory is None:
        raise ValueError("in_memory transport requires `server_factory` on the handle")


async def _open_session(handle: MCPServerHandle) -> TransportSession:
    """Open an uninitialized session over the handle's transport."""
    if handle.transport == "stdio":
        assert handle.command is not None
        return await open_stdio_session(command=handle.command, args=list(handle.args), env=handle.env)
    if handle.transport == "in_memory":
        assert handle.server_factory is not None
        return await open_in_memory_session(handle.server_factory)
    raise ValueError(f"unsupported transport on handle: {handle.transport!r}")


def _check_protocol_version(server_version: str | None) -> None:
    """Reject a negotiated protocol version the pinned MCP SDK does not accept."""
    if not server_version:
        raise MCPError(f"MCP server version <None> is outside the tested range {SUPPORTED_RANGE}")
    try:
        from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
    except ImportError as exc:
        raise MCPError(f"MCP SDK does not expose SUPPORTED_PROTOCOL_VERSIONS: {exc}") from exc
    if server_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise MCPError(f"MCP server version {server_version} is outside the tested range {SUPPORTED_RANGE}")


async def _initialize(ts: TransportSession) -> Any:
    """Run ``initialize()`` and version-gate; map SDK errors into ``MCPError``."""
    try:
        init_result = await ts.session.initialize()
    except RuntimeError as exc:
        if "Unsupported protocol version" in str(exc):
            raw = str(exc)
            server_version = raw.split(":", 1)[-1].strip() if ":" in raw else None
            raise MCPError(
                f"MCP server version {server_version} is outside the tested range {SUPPORTED_RANGE}"
            ) from exc
        raise
    negotiated = getattr(init_result, "protocolVersion", None)
    _check_protocol_version(negotiated)
    return init_result


_CONNECTION_LOST_MARKERS: tuple[str, ...] = ("Connection closed", "Connection lost", "Stream closed")


def _is_connection_lost(exc: BaseException) -> bool:
    """Classify ``exc`` as an MCP transport-layer connection loss."""
    if isinstance(exc, (anyio.ClosedResourceError, anyio.BrokenResourceError, anyio.EndOfStream)):
        return True
    if isinstance(exc, (ConnectionError, BrokenPipeError)):
        return True
    if isinstance(exc, McpError):
        error_data = getattr(exc, "error", None)
        msg = getattr(error_data, "message", None) if error_data is not None else None
        text = msg if msg is not None else str(exc)
        return any(marker in text for marker in _CONNECTION_LOST_MARKERS)
    if isinstance(exc, BaseExceptionGroup):
        return any(_is_connection_lost(child) for child in exc.exceptions)
    return False


def _representative_cause(exc: BaseException) -> BaseException:
    """Pick the transport-layer child of an ExceptionGroup for ``__cause__``."""
    if isinstance(exc, BaseExceptionGroup):
        for child in exc.exceptions:
            if _is_connection_lost(child):
                return _representative_cause(child)
    return exc


def connect_to_server(handle: MCPServerHandle) -> MCPSession:
    """Open a session, run the MCP handshake, version-gate, then tear down.

    Returns handshake metadata (negotiated protocol version + server info).
    """
    _validate_for_connect(handle)

    async def _drive() -> MCPSession:
        ts = await _open_session(handle)
        try:
            init_result = await _initialize(ts)
            negotiated = getattr(init_result, "protocolVersion", None)
            server_info_raw = getattr(init_result, "serverInfo", None)
            if server_info_raw is None:
                server_info: dict[str, Any] = {}
            elif hasattr(server_info_raw, "model_dump"):
                server_info = server_info_raw.model_dump()
            elif isinstance(server_info_raw, dict):
                server_info = dict(server_info_raw)
            else:
                server_info = {}
            return MCPSession(
                name=handle.name,
                transport=handle.transport,
                protocol_version=negotiated or "",
                server_info=server_info,
            )
        finally:
            await ts.stack.aclose()

    return run_async(_drive())


def list_tools(handle: MCPServerHandle) -> list[MCPTool]:
    """List the tools an MCP server advertises (paginated cursor loop)."""
    _validate_for_connect(handle)

    async def _drive() -> list[MCPTool]:
        ts = await _open_session(handle)
        try:
            try:
                await _initialize(ts)
                collected: list[Any] = []
                cursor: str | None = None
                while True:
                    page = await ts.session.list_tools(cursor=cursor)
                    collected.extend(getattr(page, "tools", None) or [])
                    cursor = getattr(page, "nextCursor", None)
                    if not cursor:
                        break
                return [_map_tool(t) for t in collected]
            except BaseException as exc:
                if _is_connection_lost(exc):
                    raise MCPError(
                        f"MCP session for server {handle.name!r} lost connection during list_tools"
                    ) from _representative_cause(exc)
                raise
        finally:
            await ts.stack.aclose()

    return run_async(_drive())


def call_tool(
    handle: MCPServerHandle,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> MCPToolResult:
    """Invoke a tool by name; return an ``MCPToolResult``.

    Tool-level errors come back as ``is_error=True`` data; transport failures
    raise ``MCPError``.
    """
    _validate_for_connect(handle)
    args = dict(arguments) if arguments is not None else {}

    async def _drive() -> MCPToolResult:
        ts = await _open_session(handle)
        try:
            try:
                await _initialize(ts)
                t0 = time.monotonic()
                result = await ts.session.call_tool(tool_name, args)
            except BaseException as exc:
                if _is_connection_lost(exc):
                    raise MCPError(
                        f"MCP session for server {handle.name!r} lost connection during call_tool({tool_name!r})"
                    ) from _representative_cause(exc)
                raise
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            return _map_call_result(result, latency_ms=elapsed_ms)
        finally:
            await ts.stack.aclose()

    return run_async(_drive())


def stop_server(handle: MCPServerHandle) -> None:
    """Release per-handle resources. Sessions self-clean, so this is a no-op."""
    _ = handle


def _map_tool(tool: Any) -> MCPTool:
    """Map an SDK ``mcp.types.Tool`` into an ``MCPTool``."""
    input_schema_raw = getattr(tool, "inputSchema", None)
    output_schema_raw = getattr(tool, "outputSchema", None)
    return MCPTool(
        name=str(getattr(tool, "name", "") or ""),
        description=str(getattr(tool, "description", "") or ""),
        input_schema=dict(input_schema_raw) if isinstance(input_schema_raw, dict) else {},
        output_schema=dict(output_schema_raw) if isinstance(output_schema_raw, dict) else None,
    )


def _map_call_result(result: Any, *, latency_ms: float) -> MCPToolResult:
    """Map an SDK ``CallToolResult`` into an ``MCPToolResult``."""
    content_blocks_raw = getattr(result, "content", None) or []
    content: list[dict[str, Any]] = []
    for block in content_blocks_raw:
        if isinstance(block, dict):
            content.append(dict(block))
        elif hasattr(block, "model_dump"):
            content.append(block.model_dump())
        else:
            content.append({"type": "unknown", "raw": repr(block)})

    is_error = bool(getattr(result, "isError", False))
    error_message: str | None = None
    if is_error:
        for blk in content:
            if blk.get("type") == "text" and isinstance(blk.get("text"), str):
                error_message = blk["text"]
                break
        if error_message is None:
            if content:
                first_type = content[0].get("type") if isinstance(content[0], dict) else None
                error_message = f"tool returned an error with a non-text content block of type {first_type!r}"
            else:
                error_message = "tool returned an error with no content"
    return MCPToolResult(
        content=content,
        is_error=is_error,
        error_message=error_message,
        latency_ms=latency_ms,
        correlation_id=uuid.uuid4().hex,
    )
