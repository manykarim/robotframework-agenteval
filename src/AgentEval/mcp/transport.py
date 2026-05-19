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
`streamablehttp_client`, in-memory `ClientSession`) per PRD FR7's
`<stdio|streamable_http|in_memory>` enum. Phase-1 scope:

- `stdio` — full support; bundled echo + arbitrary subprocess servers.
- `in_memory` — full support; in-process FastMCP host via the SDK's
  memory streams.
- `streamable_http` — Phase-1 PASSTHROUGH: the transport-selector
  routes to the SDK's `streamablehttp_client` but full integration
  testing (real HTTP round-trip with httpx-backed echo) is deferred
  to Phase-1.5 OR Epic 3 Story 3.2 per story 3.1 spec carve-out.

The transport layer does NOT spawn the subprocess for `stdio`. That's
`MCPLifecycleManager.acquire()` from Story 1b.1 `_kernel/context.py`.
Separation of concerns: lifecycle owns the process; transport owns the
stream + MCP session.

Story 3.1 design notes:
- `open_*_session()` functions are async (they return `ClientSession`
  context managers). Robot keywords wrap them via
  `_kernel.run_async._run_async` to avoid bare `async def @keyword`
  (Story 1b.6 conventions test prohibition).
- The spec-version gate (`mcp/version_gate.py`) fires AFTER
  `session.initialize()` returns; this module surfaces the
  `InitializeResult` for the caller to gate-check.

Architecture-layout note: this module's name `transport.py` matches
the architecture L1196 `transport.py` shape (no `_internal.py`
deviation here — `transport.py` is a first-class public-surface module
since it's accessed via `MCPLibrary.start_server`'s transport
parameter).
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Literal

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

__all__ = [
    "Transport",
    "TransportSession",
    "open_stdio_session",
    "open_in_memory_session",
]


Transport = Literal["stdio", "streamable_http", "in_memory"]


@dataclass
class TransportSession:
    """A live MCP client session paired with its async cleanup stack.

    Returned by `open_*_session()` factories. The `stack` field owns
    every async context the session depends on (transport streams +
    `ClientSession`). Callers MUST `await session.stack.aclose()` when
    done — the lifecycle module handles this in `stop_server`.

    `init_result` is the `InitializeResult` from `session.initialize()`;
    callers use it to drive the spec-version gate
    (`version_gate.check_protocol_version`).
    """

    session: ClientSession
    stack: AsyncExitStack
    init_result: Any  # mcp.types.InitializeResult; typed loosely to avoid mypy stub churn
    transport: Transport


async def open_stdio_session(
    *,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> TransportSession:
    """Open an MCP `ClientSession` over the `stdio` transport.

    Uses the MCP SDK's `stdio_client(StdioServerParameters(...))` to
    spawn the server subprocess + wire stdin/stdout/stderr. The
    subprocess is reaped when `stack.aclose()` is called.

    Per Story 0.1 review carry-over (`deferred-work.md` L34): the
    `errlog` parameter is NOT passed `sys.stderr` here because RF
    listener can replace stderr with a non-fd capture buffer; the SDK
    default (a real file or `subprocess.PIPE`) is used instead.

    Args:
        command: Executable name or path (e.g., `"python"`).
        args: Optional command-line arguments (e.g., `["-m", "AgentEval.mcp.bundled.echo"]`).
        env: Optional environment overlay (merged with parent env per
            MCP SDK semantics).

    Returns:
        `TransportSession` with `init_result` populated. The caller is
        responsible for spec-version-gating + eventually closing the
        `stack`.
    """
    params = StdioServerParameters(command=command, args=args or [], env=env)
    stack = AsyncExitStack()
    read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
    session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
    init_result = await session.initialize()
    return TransportSession(session=session, stack=stack, init_result=init_result, transport="stdio")


async def open_in_memory_session(server_factory: Any) -> TransportSession:
    """Open an MCP `ClientSession` over the `in_memory` transport.

    Uses the MCP SDK's in-process memory streams to wire a `FastMCP`
    server + a `ClientSession` in the SAME Python process. Returns the
    session ready for `initialize()`-gated calls.

    Phase-1 implementation uses `mcp.shared.memory.create_connected_server_and_client_session`
    helper which encapsulates the memory-stream wiring.

    Args:
        server_factory: A no-arg callable returning a `FastMCP` server
            instance (e.g., `AgentEval.mcp.bundled.echo.build_server`).

    Returns:
        `TransportSession` with `init_result` populated.
    """
    from mcp.shared.memory import create_connected_server_and_client_session

    stack = AsyncExitStack()
    server = server_factory()
    # `create_connected_server_and_client_session` is an async-context
    # manager yielding the connected `ClientSession`. The SDK runs the
    # server's lifecycle inside the same context so `aclose()` reaps
    # both ends cleanly.
    session = await stack.enter_async_context(create_connected_server_and_client_session(server._mcp_server))
    init_result = session._init_result if hasattr(session, "_init_result") else None
    # The SDK auto-initializes inside `create_connected_server_and_client_session`;
    # if `init_result` isn't surfaced as an attr (SDK version drift),
    # call `initialize()` manually + cache the result. The SDK is
    # idempotent on initialize.
    if init_result is None:
        init_result = await session.initialize()
    return TransportSession(session=session, stack=stack, init_result=init_result, transport="in_memory")
