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

"""MCP transport abstraction (Story 3.1).

Wraps the MCP SDK's 3 transport constructors (`stdio_client`,
`streamablehttp_client`, in-memory `create_client_server_memory_streams`)
per PRD FR7's `<stdio|streamable_http|in_memory>` enum. Phase-1 scope:

- `stdio` — full support; bundled echo + arbitrary subprocess servers.
- `in_memory` — full support; in-process FastMCP host via the SDK's
  memory streams directly (NOT via
  `create_connected_server_and_client_session` because that helper
  auto-initializes; agenteval owns initialization to map
  `RuntimeError("Unsupported protocol version...")` → typed
  `UnsupportedMCPVersionError`).
- `streamable_http` — Phase-1 PASSTHROUGH: routes to the SDK's
  `streamablehttp_client` but full integration testing is deferred to
  Phase-1.5 OR Epic 3 Story 3.2.

Story 3.1 code-review (Edge-cases + Codex 2-way HIGH 2026-05-19)
load-bearing refactor: the transport factories return UN-INITIALIZED
sessions. `lifecycle.connect_to_server()` runs exactly ONE
`initialize()` under agenteval control + maps the SDK's bare
`RuntimeError("Unsupported protocol version...")` to typed
`UnsupportedMCPVersionError`. The pre-edit shape had two HIGH bugs:
(a) the SDK's `RuntimeError` fired BEFORE agenteval's version gate
on stdio + monkeypatched in_memory; (b) `open_stdio_session` didn't
close the AsyncExitStack if `initialize()` raised mid-handshake,
leaking subprocesses. Both fixed: agenteval-owned init + universal
try/except/cleanup pattern.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Literal

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_client_server_memory_streams

__all__ = [
    "Transport",
    "TransportSession",
    "open_stdio_session",
    "open_in_memory_session",
]


Transport = Literal["stdio", "streamable_http", "in_memory"]


@dataclass
class TransportSession:
    """A LIVE MCP client session paired with its async cleanup stack.

    Returned by `open_*_session()` factories. The session has NOT been
    initialized — the caller (typically `lifecycle.connect_to_server`)
    runs `await session.initialize()` itself so agenteval can map
    SDK-level version-rejection errors to typed
    `UnsupportedMCPVersionError`.

    Callers MUST `await session.stack.aclose()` when done. Code paths
    that open the session BUT raise before returning to the caller
    MUST close the stack themselves; the transport factories
    implement that try/except/cleanup pattern.
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
    """Open an UN-INITIALIZED MCP `ClientSession` over the `stdio` transport.

    Uses the MCP SDK's `stdio_client(StdioServerParameters(...))` to
    spawn the server subprocess + wire stdin/stdout/stderr. The
    subprocess is reaped when `stack.aclose()` is called.

    Per Story 0.1 review carry-over (`deferred-work.md` L34): `errlog`
    is NOT passed `sys.stderr` because RF listener can replace stderr
    with a non-fd capture buffer; the SDK default is used.

    Story 3.1 code-review (2026-05-19) load-bearing fix: the function
    body is wrapped in `try/except BaseException` so that if the
    session-context-manager fails to enter, the stack is closed +
    re-raise propagates cleanly. Without this guard, the subprocess
    spawned by `stdio_client` was orphaned on init failure.

    Args:
        command: Executable name or path (e.g., `"python"`).
        args: Optional command-line arguments.
        env: Optional environment overlay.

    Returns:
        `TransportSession` with a LIVE but UN-INITIALIZED `ClientSession`.
    """
    params = StdioServerParameters(command=command, args=args or [], env=env)
    stack = AsyncExitStack()
    try:
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return TransportSession(session=session, stack=stack, transport="stdio")
    except BaseException:
        await stack.aclose()
        raise


async def open_in_memory_session(server_factory: Any) -> TransportSession:
    """Open an UN-INITIALIZED MCP `ClientSession` over the `in_memory` transport.

    Wires the MCP SDK's memory streams to a FastMCP server in the
    SAME Python process. Returns the session ready for an
    agenteval-owned `initialize()` call.

    Phase-1 implementation uses the SDK's low-level
    `create_client_server_memory_streams` directly — NOT the
    `create_connected_server_and_client_session` convenience helper —
    because the helper auto-initializes BEFORE yielding, which
    bypasses agenteval's typed-error mapping for
    `UnsupportedMCPVersionError`. The low-level streams + manual
    server-task-group setup mirror the helper's pattern but leave
    initialization to the caller.

    Args:
        server_factory: A no-arg callable returning a `FastMCP` server.

    Returns:
        `TransportSession` with a LIVE but UN-INITIALIZED `ClientSession`.
    """
    stack = AsyncExitStack()
    try:
        server_instance = server_factory()
        # Extract the low-level Server from FastMCP. The SDK's own
        # `create_connected_server_and_client_session` does the same
        # private-attribute access (with a TODO upstream to expose a
        # public API). Tracked as Phase-1.5 hygiene if SDK adds it.
        low_level_server = server_instance._mcp_server if isinstance(server_instance, FastMCP) else server_instance

        client_streams, server_streams = await stack.enter_async_context(create_client_server_memory_streams())
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        # Spawn the server's run-loop as a task in a managed task-group.
        # The task is cancelled when the stack closes via the callback.
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
    """Cancel a task group on stack-close. Defensive helper for in_memory teardown."""
    task_group.cancel_scope.cancel()
