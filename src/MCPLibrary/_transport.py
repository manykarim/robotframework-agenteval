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

"""MCP transport factories over the MCP SDK - needs the ``[mcp]`` extra.

Opens un-initialized ``ClientSession`` objects for the ``stdio`` and
``in_memory`` transports. Initialization is left to the caller so lifecycle
code can map SDK version-rejection into a typed ``MCPError``.
"""

from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Literal

import anyio
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_client_server_memory_streams

__all__ = [
    "Transport",
    "TransportSession",
    "open_stdio_session",
    "open_http_session",
    "open_sse_session",
    "open_in_memory_session",
]

Transport = Literal["stdio", "streamable_http", "sse", "in_memory"]


@dataclass
class TransportSession:
    """A live-but-uninitialized MCP client session with its async cleanup stack.

    Callers must ``await session.stack.aclose()`` when done. The factories own
    cleanup for the failure path (they close the stack before re-raising).
    """

    session: ClientSession
    stack: AsyncExitStack
    transport: Transport


async def open_stdio_session(
    *,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> TransportSession:
    """Spawn a stdio MCP server subprocess and open an uninitialized session.

    Passes ``errlog=sys.__stderr__`` (falling back to ``os.devnull``) because
    Robot Framework's listener replaces ``sys.stderr`` with a non-fd capture
    buffer that crashes the SDK's ``.fileno()`` call.
    """
    params = StdioServerParameters(command=command, args=args or [], env=env)
    stack = AsyncExitStack()
    try:
        errlog = (
            sys.__stderr__ if sys.__stderr__ is not None else stack.enter_context(open(os.devnull, "w"))  # noqa: SIM115 -- closed via the stack
        )
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params, errlog=errlog))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return TransportSession(session=session, stack=stack, transport="stdio")
    except BaseException:
        await stack.aclose()
        raise


async def open_http_session(
    *,
    url: str,
    headers: dict[str, str] | None = None,
) -> TransportSession:
    """Open an uninitialized session to a remote MCP server over Streamable HTTP.

    Uses the SDK's non-deprecated ``streamable_http_client`` with a caller-owned
    ``httpx.AsyncClient`` carrying any auth ``headers`` (the client is closed via the
    stack; the SDK does not close a client it did not create). Initialization is left
    to the caller, matching ``open_stdio_session``.
    """
    stack = AsyncExitStack()
    try:
        client = await stack.enter_async_context(httpx.AsyncClient(headers=headers or None))
        read_stream, write_stream, _get_session_id = await stack.enter_async_context(
            streamable_http_client(url, http_client=client)
        )
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return TransportSession(session=session, stack=stack, transport="streamable_http")
    except BaseException:
        await stack.aclose()
        raise


async def open_sse_session(
    *,
    url: str,
    headers: dict[str, str] | None = None,
) -> TransportSession:
    """Open an uninitialized session to a remote MCP server over the legacy SSE transport."""
    stack = AsyncExitStack()
    try:
        read_stream, write_stream = await stack.enter_async_context(sse_client(url, headers=headers))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return TransportSession(session=session, stack=stack, transport="sse")
    except BaseException:
        await stack.aclose()
        raise


async def open_in_memory_session(server_factory: Any) -> TransportSession:
    """Wire an in-process ``FastMCP`` server to a client over memory streams.

    Uses the SDK's low-level ``create_client_server_memory_streams`` (not the
    auto-initializing convenience helper) so the caller owns initialization.
    """
    stack = AsyncExitStack()
    try:
        server_instance = server_factory()
        low_level_server = server_instance._mcp_server if isinstance(server_instance, FastMCP) else server_instance

        client_streams, server_streams = await stack.enter_async_context(create_client_server_memory_streams())
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        task_group = await stack.enter_async_context(anyio.create_task_group())

        async def _server_runner() -> None:
            await low_level_server.run(
                server_read,
                server_write,
                low_level_server.create_initialization_options(),
                raise_exceptions=False,
            )

        task_group.start_soon(_server_runner)
        stack.push_async_callback(_cancel_task_group, task_group)

        session = await stack.enter_async_context(ClientSession(read_stream=client_read, write_stream=client_write))
        return TransportSession(session=session, stack=stack, transport="in_memory")
    except BaseException:
        await stack.aclose()
        raise


async def _cancel_task_group(task_group: Any) -> None:
    """Cancel an in_memory server's task group when the stack closes."""
    task_group.cancel_scope.cancel()
