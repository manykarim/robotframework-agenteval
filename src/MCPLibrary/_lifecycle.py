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

``Connect To Server`` opens a *warm* session: it spawns the server subprocess
(or in-process server) once, runs the MCP handshake, and holds the SDK
``ClientSession`` open on a dedicated background event-loop thread. Subsequent
``List Tools`` / ``Call Tool`` operations dispatch onto that one warm session,
so a connect + N ops reuse a single subprocess instead of cold-starting each
time. ``Stop Server`` tears the session down (closes the session, terminates
the subprocess, joins the thread).

For backward compatibility, ``List Tools`` / ``Call Tool`` still work without a
prior ``Connect To Server``: they fall back to a one-shot cold session that
opens, runs the op, and tears down.

Only ``stdio`` and ``in_memory`` transports are wired; ``streamable_http`` is
rejected. Transport and handshake failures surface as ``MCPError``.

The anyio SDK requires the task that *opens* a session's cancel scopes to be
the same task that *closes* them. The warm session honors this by keeping open,
serve, and teardown all inside one long-lived actor coroutine on the background
loop - ops are marshalled in over a queue, never opened/closed across tasks.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import contextlib
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
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

# Cross-thread wait budgets. Bounded so an un-stopped or wedged session can
# never hang the RF run or the pytest suite indefinitely.
_CONNECT_TIMEOUT_S = 30.0
_OP_TIMEOUT_S = 120.0
_STOP_TIMEOUT_S = 15.0


@dataclass(frozen=True)
class MCPServerHandle:
    """Describes how to open a session to an MCP server.

    Holds connection parameters, not a live session. ``Connect To Server`` pairs
    a handle with a live warm session (tracked separately, keyed by handle
    identity) that later operations reuse.
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

    Pure metadata (negotiated protocol version + server info). The live SDK
    session it describes is held warm and reused until ``Stop Server``; this
    object does not own it.
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


def _build_session_meta(handle: MCPServerHandle, init_result: Any) -> MCPSession:
    """Project an SDK ``InitializeResult`` into the ``MCPSession`` metadata."""
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


async def _list_tools_op(ts: TransportSession, server_name: str) -> list[MCPTool]:
    """List an already-initialized session's tools (paginated cursor loop)."""
    try:
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
                f"MCP session for server {server_name!r} lost connection during list_tools"
            ) from _representative_cause(exc)
        raise


async def _call_tool_op(ts: TransportSession, server_name: str, tool_name: str, args: dict[str, Any]) -> MCPToolResult:
    """Invoke a tool on an already-initialized session; map the result."""
    try:
        t0 = time.monotonic()
        result = await ts.session.call_tool(tool_name, args)
    except BaseException as exc:
        if _is_connection_lost(exc):
            raise MCPError(
                f"MCP session for server {server_name!r} lost connection during call_tool({tool_name!r})"
            ) from _representative_cause(exc)
        raise
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    return _map_call_result(result, latency_ms=elapsed_ms)


# --------------------------------------------------------------------------- #
# Warm session: one persistent server subprocess + client session.            #
# --------------------------------------------------------------------------- #

_STOP = object()

# Keyed by ``id(handle)``. The ``WarmSession`` keeps a strong reference to its
# handle, so the id cannot be recycled onto a different object while registered.
_WARM_SESSIONS: dict[int, WarmSession] = {}
_REGISTRY_LOCK = threading.Lock()

# A queued op: (result future, coroutine factory taking the live session).
_Request = tuple["concurrent.futures.Future[Any]", Callable[[TransportSession], Awaitable[Any]]]


class WarmSession:
    """A persistent MCP session held open on a dedicated event-loop thread.

    The session is opened, served, and torn down entirely inside one actor
    coroutine so the SDK's same-task cancel-scope invariant holds. Synchronous
    keyword code submits ops over a queue and blocks (with a timeout) on a
    ``concurrent.futures.Future`` for each result.
    """

    def __init__(self, handle: MCPServerHandle) -> None:
        self._handle = handle
        self._loop = asyncio.new_event_loop()
        self._requests: asyncio.Queue[Any] = asyncio.Queue()
        self._ready: concurrent.futures.Future[MCPSession] = concurrent.futures.Future()
        self._state_lock = threading.Lock()
        self._closed = False
        # daemon=True is a defensive backstop: even if teardown wedges, the
        # process can still exit. atexit teardown runs first and terminates the
        # subprocess cleanly for the normal path.
        self._thread = threading.Thread(
            target=self._thread_main,
            name=f"mcp-warm-{handle.name}",
            daemon=True,
        )
        self.meta: MCPSession | None = None

    # -- lifecycle ------------------------------------------------------- #

    def start(self) -> MCPSession:
        """Spawn the loop thread, open the session, and return handshake meta.

        Blocks until the handshake completes or fails. On any failure the loop
        thread is torn down before the exception propagates - no leaked thread
        or subprocess.
        """
        self._thread.start()
        try:
            self.meta = self._ready.result(timeout=_CONNECT_TIMEOUT_S)
        except concurrent.futures.TimeoutError as exc:
            self.close()
            raise MCPError(
                f"MCP.Connect To Server for {self._handle.name!r} timed out after {_CONNECT_TIMEOUT_S}s"
            ) from exc
        except BaseException:
            self.close()
            raise
        return self.meta

    def _thread_main(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._actor())
        except BaseException:  # noqa: BLE001 - loop-thread guard; never propagate off-thread
            # Actor already reports open/handshake failures via `_ready`; this
            # only guards a truly unexpected escape so the thread exits cleanly.
            if not self._ready.done():
                self._ready.set_exception(
                    MCPError(f"MCP warm session for {self._handle.name!r} crashed during startup")
                )
        finally:
            with contextlib.suppress(Exception):  # best-effort loop close
                self._loop.close()

    async def _actor(self) -> None:
        """Open the session, serve queued ops, and tear down - all one task."""
        try:
            ts = await _open_session(self._handle)
        except BaseException as exc:  # noqa: BLE001 - reported to the waiting caller
            if not self._ready.done():
                self._ready.set_exception(exc)
            return
        try:
            try:
                init_result = await _initialize(ts)
                meta = _build_session_meta(self._handle, init_result)
            except BaseException as exc:  # noqa: BLE001 - reported to the caller
                if not self._ready.done():
                    self._ready.set_exception(exc)
                return
            self._ready.set_result(meta)
            await self._serve(ts)
        finally:
            with contextlib.suppress(BaseException):  # teardown is best-effort
                await ts.stack.aclose()

    async def _serve(self, ts: TransportSession) -> None:
        while True:
            req = await self._requests.get()
            if req is _STOP:
                return
            fut, op = req
            try:
                res = await op(ts)
            except BaseException as exc:  # noqa: BLE001 - marshalled back to caller
                if not fut.done():
                    fut.set_exception(exc)
            else:
                if not fut.done():
                    fut.set_result(res)

    def close(self, timeout: float = _STOP_TIMEOUT_S) -> None:
        """Tear the session down: stop the actor, join the thread. Idempotent."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        # Ask the actor to stop; it closes the stack (terminating the
        # subprocess) in its own task before the loop unwinds.
        with contextlib.suppress(RuntimeError):  # loop already stopped/closed
            self._loop.call_soon_threadsafe(self._requests.put_nowait, _STOP)
        self._thread.join(timeout=timeout)

    # -- op dispatch ----------------------------------------------------- #

    def _submit(self, op: Callable[[TransportSession], Awaitable[Any]], timeout: float) -> Any:
        with self._state_lock:
            if self._closed:
                raise MCPError(
                    f"MCP session for server {self._handle.name!r} is stopped; "
                    "call MCP.Connect To Server again before using it"
                )
        fut: concurrent.futures.Future[Any] = concurrent.futures.Future()
        try:
            self._loop.call_soon_threadsafe(self._requests.put_nowait, (fut, op))
        except RuntimeError as exc:
            raise MCPError(f"MCP session for server {self._handle.name!r} is no longer running") from exc
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise MCPError(f"MCP operation on server {self._handle.name!r} timed out after {timeout}s") from exc

    def list_tools(self) -> list[MCPTool]:
        name = self._handle.name

        async def op(ts: TransportSession) -> list[MCPTool]:
            return await _list_tools_op(ts, name)

        return list(self._submit(op, _OP_TIMEOUT_S))

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> MCPToolResult:
        name = self._handle.name

        async def op(ts: TransportSession) -> MCPToolResult:
            return await _call_tool_op(ts, name, tool_name, args)

        result: MCPToolResult = self._submit(op, _OP_TIMEOUT_S)
        return result


def _get_warm(handle: MCPServerHandle) -> WarmSession | None:
    with _REGISTRY_LOCK:
        return _WARM_SESSIONS.get(id(handle))


@atexit.register
def _close_all_warm_sessions() -> None:
    """Best-effort teardown of any session left open at interpreter exit.

    Runs before daemon loop threads are killed, so subprocesses are terminated
    cleanly rather than orphaned.
    """
    with _REGISTRY_LOCK:
        sessions = list(_WARM_SESSIONS.values())
        _WARM_SESSIONS.clear()
    for warm in sessions:
        with contextlib.suppress(Exception):  # shutdown is best-effort
            warm.close()


def connect_to_server(handle: MCPServerHandle) -> MCPSession:
    """Open and hold a warm session; run the handshake and version-gate.

    Spawns the server once and keeps the SDK session open on a background
    thread so later ``list_tools`` / ``call_tool`` reuse it. Returns handshake
    metadata. Re-connecting an already-connected handle tears the old session
    down first.
    """
    _validate_for_connect(handle)

    with _REGISTRY_LOCK:
        existing = _WARM_SESSIONS.pop(id(handle), None)
    if existing is not None:
        existing.close()

    warm = WarmSession(handle)
    meta = warm.start()  # tears itself down on failure before raising
    with _REGISTRY_LOCK:
        _WARM_SESSIONS[id(handle)] = warm
    return meta


def list_tools(handle: MCPServerHandle) -> list[MCPTool]:
    """List the tools an MCP server advertises (paginated cursor loop).

    Reuses the warm session when the handle is connected; otherwise opens a
    one-shot cold session for backward compatibility.
    """
    _validate_for_connect(handle)
    warm = _get_warm(handle)
    if warm is not None:
        return warm.list_tools()

    async def _drive() -> list[MCPTool]:
        ts = await _open_session(handle)
        try:
            await _initialize(ts)
            return await _list_tools_op(ts, handle.name)
        finally:
            await ts.stack.aclose()

    return run_async(_drive())


def call_tool(
    handle: MCPServerHandle,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> MCPToolResult:
    """Invoke a tool by name; return an ``MCPToolResult``.

    Reuses the warm session when the handle is connected; otherwise opens a
    one-shot cold session for backward compatibility. Tool-level errors come
    back as ``is_error=True`` data; transport failures raise ``MCPError``.
    """
    _validate_for_connect(handle)
    args = dict(arguments) if arguments is not None else {}
    warm = _get_warm(handle)
    if warm is not None:
        return warm.call_tool(tool_name, args)

    async def _drive() -> MCPToolResult:
        ts = await _open_session(handle)
        try:
            await _initialize(ts)
            return await _call_tool_op(ts, handle.name, tool_name, args)
        finally:
            await ts.stack.aclose()

    return run_async(_drive())


def stop_server(handle: MCPServerHandle) -> None:
    """Tear down the handle's warm session (if any): close it, terminate the
    subprocess, join the loop thread. A no-op when no session is held.
    """
    with _REGISTRY_LOCK:
        warm = _WARM_SESSIONS.pop(id(handle), None)
    if warm is not None:
        warm.close()


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
