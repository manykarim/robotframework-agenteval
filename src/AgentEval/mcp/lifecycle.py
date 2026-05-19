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

"""MCP server lifecycle keyword implementation (Story 3.1).

Per Story 3.1 Phase-1 design (mirrors agentguard's per-call-session
pattern; see `feedback_agentguard_inspiration_not_dependency`): the
keywords return lightweight handles that capture the connection
parameters; each subsequent operation (initialize, list tools, call
tool) re-opens the MCP session via the SDK + tears down at the end of
the keyword call. This avoids the "keep async session alive across
sync keyword calls" complexity that would otherwise require a
background-thread event loop.

Phase-1 trade-off documented honestly: stdio transport pays the
subprocess-startup latency on every `connect_to_server` call. The
overhead is captured separately via NFR-PERF metrics (NOT via tier
badge — these are still Tier-1 keywords, deterministic given same env
+ server binary). Phase-1.5 OR Epic 5 may add a pooled
`MCPLifecycleManager`-backed session-reuse path; Story 3.1 deliberately
ships the simpler shape first.

Architecture compliance:
- Stories 2.1-2.4 lessons inherited: no eager re-export; behavioral
  probes for tests; structured attrs on errors; deviation-tracker
  docstrings.
- `_kernel.run_async._run_async` bridges async SDK ↔ sync RF keyword
  per ADR-012 (no bare `async def @keyword`).
- `UnsupportedMCPVersionError` raised post-initialize per FR8 + FR46
  + AC-MCP-OBSERVE-02; structured attrs (`server_version`,
  `supported_range`) populated for programmatic consumers.
- `MCPLibrary` remains EXCLUDED from `_SUB_LIBRARIES` per Story 2.2
  collision-prevention norm.

Phase-1 scope (Story 3.1 carve-out):
- `stdio` + `in_memory` transports fully supported.
- `streamable_http` accepted as a transport name + passes through to
  the SDK's `streamablehttp_client`, but Phase-1 doesn't ship an HTTP
  echo fixture; full round-trip is deferred to Phase-1.5 OR Epic 3
  Story 3.2.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from AgentEval._kernel.run_async import _run_async
from AgentEval.errors import MCPConnectionLostError, UnsupportedMCPVersionError
from AgentEval.mcp.transport import (
    Transport,
    TransportSession,
    open_in_memory_session,
    open_stdio_session,
)
from AgentEval.mcp.version_gate import check_protocol_version

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


@dataclass(frozen=True)
class MCPServerHandle:
    """A handle describing how to (re-)open an MCP session to a server.

    The handle does NOT hold a live MCP client session (Story 3.1
    Phase-1 design: each operation re-opens). Subsequent keywords
    consume the handle to re-establish the session for THAT operation
    only.

    Story 3.1 design notes:
    - Stories using a long-lived session pattern (Phase-1.5 or Epic 5)
      will introduce a sibling `MCPSession` handle backed by a
      background event loop. The two coexist.
    - `frozen=True` for immutability; the `kwargs` dict is shallow-
      copied at construction per Story 1b.2 M_R6 pattern.
    """

    name: str
    transport: Transport
    # stdio-specific:
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    # in_memory-specific: a no-arg callable returning a FastMCP server.
    server_factory: Callable[[], Any] | None = None
    # Story 3.1 code-review Codex LOW (2026-05-19): removed the
    # `extra: dict[str, Any]` field — `frozen=True` doesn't seal dict
    # mutation, so the field gave a false sense of immutability AND
    # was unused. Sub-libraries that need per-handle metadata can
    # introduce a typed extension dataclass when needed.


@dataclass(frozen=True)
class MCPSession:
    """Post-`Connect To Server` session metadata.

    Carries the negotiated MCP protocol version + server info AFTER a
    successful `initialize()` + version-gate pass. NOT a live session —
    the SDK session was torn down at the end of `connect_to_server`
    per Phase-1 per-call-session design.
    """

    name: str
    transport: Transport
    protocol_version: str
    server_info: dict[str, Any]


@dataclass(frozen=True)
class MCPTool:
    """Description of a single tool advertised by an MCP server (PRD FR9a).

    Story 3.2: structured record returned by `list_tools`. Maps from
    the MCP SDK's `mcp.types.Tool` per the MCP spec's `Tool` shape
    (`name`, `description`, `inputSchema`, optional `outputSchema`).

    `frozen=True` for immutability; dict fields are shallow-copied at
    construction per Story 1b.2 M_R6 pattern.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class MCPToolResult:
    """Result of a single `call_tool` invocation (PRD FR9b).

    Story 3.2: structured record returned by `call_tool`. Distinguishes
    PROTOCOL-LEVEL error responses (`is_error=True`, `error_message`
    populated; tool ran but returned an error — first-class DATA, not
    an exception) from INFRASTRUCTURE failures (connection lost,
    transport crash — those raise `MCPConnectionLostError` instead).

    Fields:
        - `content`: list of content blocks per the MCP spec. Each
          block has a `type` key + type-specific keys (`text`, `data`,
          `mimeType`, ...). Phase-1 stores blocks as plain dicts; a
          typed-ContentBlock variant is deferred to Phase-1.5.
        - `is_error`: mirrors the SDK's `CallToolResult.isError` field.
        - `error_message`: populated when `is_error=True` (extracted
          from the first text-content block); `None` otherwise.
        - `latency_ms`: wall-clock elapsed (monotonic) from
          `call_tool` request-send to response-receive, in
          milliseconds.
        - `correlation_id`: per-call uuid4 hex string. Phase-1
          PLACEHOLDER for the Epic 5 trace-id wiring; ships now so the
          API contract is stable + downstream code can already pass
          the field. Epic 5 binds this to the active trace context.
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
    """Build an `MCPServerHandle` describing a server target.

    Per Story 3.1 Phase-1 design, this does NOT spawn a subprocess for
    `stdio` (the spawn happens during `connect_to_server`). The
    function is a pure constructor that validates the transport-
    appropriate parameters.

    Args:
        name: Caller-chosen identifier for the server (echoed back in
            error messages and handle representation).
        transport: One of `"stdio"`, `"streamable_http"`, `"in_memory"`
            per PRD FR7.
        command: stdio only — the executable name (e.g., `"python"`).
        args: stdio only — command-line arguments.
        env: stdio only — environment overlay.
        server_factory: in_memory only — no-arg callable returning a
            `FastMCP` server instance.

    Returns:
        `MCPServerHandle` describing the server target. Pass to
        `connect_to_server` to open + initialize a session.

    Raises:
        ValueError: If transport-required parameters are missing.
    """
    if transport == "stdio":
        if not command:
            raise ValueError("stdio transport requires `command`")
    elif transport == "in_memory":
        if server_factory is None:
            raise ValueError("in_memory transport requires `server_factory`")
    elif transport == "streamable_http":
        # Phase-1 passthrough: the keyword accepts the transport name
        # so future stories don't need a breaking change. Real HTTP
        # round-trip support lands in Phase-1.5 OR Epic 3 Story 3.2.
        # No required-parameter check today; future work will add
        # URL validation.
        pass
    else:
        raise ValueError(
            f"unsupported transport {transport!r}; must be one of 'stdio' | 'streamable_http' | 'in_memory' per PRD FR7"
        )
    # Story 3.1 code-review HIGH (Blind + Edge-cases 2-way 2026-05-19):
    # `env=dict(env) if env else None` collapses an empty dict `{}` to
    # `None`. SDK semantics differ: `env=None` → inherit parent; `env={}`
    # → strip all parent env. Use `is not None` so both shapes are
    # round-trip-preserved.
    return MCPServerHandle(
        name=name,
        transport=transport,
        command=command,
        args=tuple(args or ()),
        env=dict(env) if env is not None else None,
        server_factory=server_factory,
    )


def _validate_handle_for_connect(handle: MCPServerHandle) -> None:
    """Reject `streamable_http` + verify per-transport required params.

    Phase-1 passthrough: `streamable_http` is rejected at the entry to
    every keyword that requires a live session. The transport name is
    still accepted in `start_server` so future stories can flip it on
    without a breaking API change.

    Story 3.1 code-review HIGH (Blind 2026-05-19): replace bare
    `assert` (stripped under `python -O` / PYTHONOPTIMIZE) with typed
    `ValueError` so direct `MCPServerHandle` construction (bypassing
    `start_server`) still surfaces a clean failure on the production
    path.
    """
    if handle.transport == "streamable_http":
        raise ValueError(
            "streamable_http transport is Phase-1 passthrough; full HTTP "
            "round-trip support is deferred to Phase-1.5 OR Epic 3 Story 3.2"
        )
    if handle.transport == "stdio" and not handle.command:
        raise ValueError("stdio transport requires `command` on the handle")
    if handle.transport == "in_memory" and handle.server_factory is None:
        raise ValueError("in_memory transport requires `server_factory` on the handle")


async def _open_session(handle: MCPServerHandle) -> TransportSession:
    """Open an un-initialized session over `handle`'s transport.

    Pre: `_validate_handle_for_connect(handle)` already ran. Transport
    factories own their own `try/except BaseException` cleanup, so on
    failure the AsyncExitStack is closed before this returns.
    """
    if handle.transport == "stdio":
        assert handle.command is not None  # validated by caller
        return await open_stdio_session(
            command=handle.command,
            args=list(handle.args),
            env=handle.env,
        )
    if handle.transport == "in_memory":
        assert handle.server_factory is not None  # validated by caller
        return await open_in_memory_session(handle.server_factory)
    # Defense-in-depth: streamable_http already rejected, but if a new
    # transport name slipped in via direct MCPServerHandle construction
    # the caller still gets a clean ValueError instead of a confusing
    # AttributeError downstream.
    raise ValueError(f"unsupported transport on handle: {handle.transport!r}")


async def _initialize_with_typed_error_mapping(ts: TransportSession) -> Any:
    """Run `session.initialize()` + version-gate; map SDK errors to typed.

    Per Story 3.1 code-review HIGH (Edge-cases + Codex 2-way 2026-05-19):
    the SDK's bare `RuntimeError("Unsupported protocol version...")`
    is mapped to typed `UnsupportedMCPVersionError`. The pre-edit
    shape let the SDK error escape (AC-MCP-OBSERVE-02 was fake-green
    on stdio).

    Also runs the agenteval-side late gate via
    `check_protocol_version` for defense-in-depth — catches cases
    where the SDK's allowlist drifts ahead of ours.

    Returns the SDK's `InitializeResult` on success.
    """
    try:
        init_result = await ts.session.initialize()
    except RuntimeError as exc:
        if "Unsupported protocol version" in str(exc):
            raw = str(exc)
            # SDK message format: `Unsupported protocol version from the server: <version>`
            server_version = raw.split(":", 1)[-1].strip() if ":" in raw else None
            raise UnsupportedMCPVersionError(
                f"MCP server version {server_version} outside library tested range mcp>=1.0,<2.0",
                server_version=server_version,
                supported_range="mcp>=1.0,<2.0",
            ) from exc
        raise
    negotiated = getattr(init_result, "protocolVersion", None)
    check_protocol_version(negotiated)
    return init_result


def connect_to_server(handle: MCPServerHandle) -> MCPSession:
    """Open a fresh MCP `ClientSession`, run `initialize()`, gate-check the version.

    Per Story 3.1 Phase-1 design (per-call session): this function
    opens the session, runs the handshake, captures the negotiated
    protocol version + server info, then closes the session. The
    returned `MCPSession` carries the metadata for the caller's
    assertions; the underlying SDK session is no longer live.

    Args:
        handle: An `MCPServerHandle` from `start_server`.

    Returns:
        `MCPSession` with negotiated `protocol_version` + `server_info`.

    Raises:
        ValueError: If transport is `streamable_http` (Phase-1
            passthrough; no implementation yet).
        UnsupportedMCPVersionError: If the negotiated protocol version
            is outside the `mcp>=1.0,<2.0` range per
            `version_gate.check_protocol_version`.
    """
    _validate_handle_for_connect(handle)

    async def _drive() -> MCPSession:
        ts = await _open_session(handle)
        try:
            init_result = await _initialize_with_typed_error_mapping(ts)
            negotiated = getattr(init_result, "protocolVersion", None)
            server_info_raw = getattr(init_result, "serverInfo", None)
            if server_info_raw is None:
                server_info_dict: dict[str, Any] = {}
            elif hasattr(server_info_raw, "model_dump"):
                server_info_dict = server_info_raw.model_dump()
            elif isinstance(server_info_raw, dict):
                server_info_dict = dict(server_info_raw)
            else:
                server_info_dict = {}
            return MCPSession(
                name=handle.name,
                transport=handle.transport,
                protocol_version=negotiated or "",
                server_info=server_info_dict,
            )
        finally:
            await ts.stack.aclose()

    return _run_async(_drive())


def _is_connection_lost_exception(exc: BaseException) -> bool:
    """Heuristically classify `exc` as an MCP transport-layer connection loss.

    Story 3.2 design: we map a narrow set of anyio + connection-loss
    exception types to `MCPConnectionLostError`. We deliberately do
    NOT swallow protocol-level `mcp.shared.exceptions.McpError`
    (server-returned JSON-RPC errors) — those are legitimate protocol
    failures, not transport loss. Tool-level errors arrive via
    `CallToolResult.isError=True` and are surfaced as
    `MCPToolResult(is_error=True, ...)` — also NOT this code path.

    Recognized signatures (Phase-1 best-effort; expand as real-world
    failure modes surface):
        - `anyio.ClosedResourceError` — stream closed under us.
        - `anyio.BrokenResourceError` — peer reset / pipe broken.
        - `anyio.EndOfStream` — orderly close mid-call (unexpected).
        - `ConnectionError` (stdlib) — generic connection failure.
        - `BrokenPipeError` (stdlib) — child stdin/stdout pipe died.
    """
    import anyio

    if isinstance(exc, (anyio.ClosedResourceError, anyio.BrokenResourceError, anyio.EndOfStream)):
        return True
    return isinstance(exc, (ConnectionError, BrokenPipeError))


def list_tools(handle: MCPServerHandle) -> list[MCPTool]:
    """List the tools advertised by the MCP server at `handle` (PRD FR9a).

    Per Story 3.2 Phase-1 design (per-call-session inherited from
    Story 3.1): opens a fresh session, runs `initialize()`, calls
    `session.list_tools()`, maps the SDK `Tool` shapes to `MCPTool`
    dataclasses, then tears down. Each call pays the full handshake
    cost — Phase-1.5 may introduce pooled sessions.

    Args:
        handle: An `MCPServerHandle` from `start_server`.

    Returns:
        A list of `MCPTool` records, one per server-advertised tool.

    Raises:
        ValueError: If transport is `streamable_http` (Phase-1
            passthrough) or required handle params are missing.
        UnsupportedMCPVersionError: If `initialize()` rejects the
            negotiated protocol version.
        MCPConnectionLostError: If the transport layer fails mid-call
            (subprocess crash, anyio stream closed, etc.).
    """
    _validate_handle_for_connect(handle)

    async def _drive() -> list[MCPTool]:
        ts = await _open_session(handle)
        try:
            await _initialize_with_typed_error_mapping(ts)
            try:
                result = await ts.session.list_tools()
            except BaseException as exc:
                if _is_connection_lost_exception(exc):
                    raise MCPConnectionLostError(
                        f"MCP session for server {handle.name!r} lost connection during list_tools",
                        server_name=handle.name,
                        last_operation="list_tools",
                        fix_suggestion=(
                            "Inspect the server's stderr / logs for the underlying failure; "
                            "re-run `MCP.Start Server` + `MCP.Connect To Server` to recover."
                        ),
                    ) from exc
                raise
            return [_map_tool(t) for t in (result.tools or [])]
        finally:
            await ts.stack.aclose()

    return _run_async(_drive())


def call_tool(
    handle: MCPServerHandle,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> MCPToolResult:
    """Invoke a tool by name on the MCP server at `handle` (PRD FR9b).

    Per Story 3.2 Phase-1 design (per-call-session inherited from
    Story 3.1): opens a fresh session, runs `initialize()`, calls
    `session.call_tool(tool_name, arguments)`, computes wall-clock
    latency, generates a per-call uuid4 `correlation_id`, then maps
    the SDK's `CallToolResult` to a typed `MCPToolResult`.

    Tool-LEVEL error responses (`isError=True` per MCP spec) are
    surfaced as `MCPToolResult(is_error=True, error_message=...)` —
    NOT as exceptions. Infrastructure failures (transport disconnect,
    subprocess crash) raise `MCPConnectionLostError` instead.

    Args:
        handle: An `MCPServerHandle` from `start_server`.
        tool_name: The tool name as advertised by the server (use
            `list_tools` to discover available names).
        arguments: Tool-specific argument dict; defaults to `{}`.

    Returns:
        `MCPToolResult` with `content`, `is_error`, `error_message`,
        `latency_ms`, and a per-call uuid4-hex `correlation_id`
        (Phase-1 placeholder; Epic 5 wires real trace-id lookup).

    Raises:
        ValueError: If transport is `streamable_http` (Phase-1
            passthrough) or required handle params are missing.
        UnsupportedMCPVersionError: If `initialize()` rejects the
            negotiated protocol version.
        MCPConnectionLostError: If the transport layer fails mid-call.
    """
    _validate_handle_for_connect(handle)
    args = dict(arguments) if arguments is not None else {}

    async def _drive() -> MCPToolResult:
        ts = await _open_session(handle)
        try:
            await _initialize_with_typed_error_mapping(ts)
            t0 = time.monotonic()
            try:
                result = await ts.session.call_tool(tool_name, args)
            except BaseException as exc:
                if _is_connection_lost_exception(exc):
                    raise MCPConnectionLostError(
                        f"MCP session for server {handle.name!r} lost connection during call_tool({tool_name!r})",
                        server_name=handle.name,
                        last_operation="call_tool",
                        fix_suggestion=(
                            "Inspect the server's stderr / logs for the underlying failure; "
                            "re-run `MCP.Start Server` + `MCP.Connect To Server` to recover."
                        ),
                    ) from exc
                raise
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            return _map_call_result(result, latency_ms=elapsed_ms)
        finally:
            await ts.stack.aclose()

    return _run_async(_drive())


def _map_tool(tool: Any) -> MCPTool:
    """Map an SDK `mcp.types.Tool` (pydantic model) to a typed `MCPTool`.

    Defensive against minor SDK shape drift: uses `getattr` rather
    than positional unpacking + falls back to empty defaults when an
    optional field is absent (per MCP spec, `outputSchema` is optional).
    """
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    input_schema_raw = getattr(tool, "inputSchema", None)
    output_schema_raw = getattr(tool, "outputSchema", None)
    return MCPTool(
        name=name,
        description=description,
        input_schema=dict(input_schema_raw) if isinstance(input_schema_raw, dict) else {},
        output_schema=dict(output_schema_raw) if isinstance(output_schema_raw, dict) else None,
    )


def _map_call_result(result: Any, *, latency_ms: float) -> MCPToolResult:
    """Map an SDK `CallToolResult` to a typed `MCPToolResult`.

    Handles the MCP-spec contract where `isError=True` carries the
    error message inside the first text-content block. Phase-1 stores
    content blocks as plain dicts; typed-ContentBlock variant deferred
    to Phase-1.5.
    """
    content_blocks_raw = getattr(result, "content", None) or []
    content: list[dict[str, Any]] = []
    error_message: str | None = None
    for block in content_blocks_raw:
        if isinstance(block, dict):
            content.append(dict(block))
        elif hasattr(block, "model_dump"):
            content.append(block.model_dump())
        else:
            # Defensive: best-effort dict-ish projection. Mirrors the
            # Story 1b.2 M_R6 shallow-copy pattern for foreign shapes.
            content.append({"type": "unknown", "raw": repr(block)})
    is_error = bool(getattr(result, "isError", False))
    if is_error:
        # Extract the first text-block's message for the `error_message`
        # convenience field. Callers wanting structured content still
        # have `result.content` available.
        for blk in content:
            if blk.get("type") == "text" and isinstance(blk.get("text"), str):
                error_message = blk["text"]
                break
        if error_message is None and content:
            # Fallback to a generic representation when no text block
            # is present (e.g., image-only error response).
            error_message = "tool returned an error response without a text content block"
    return MCPToolResult(
        content=content,
        is_error=is_error,
        error_message=error_message,
        latency_ms=latency_ms,
        correlation_id=uuid.uuid4().hex,
    )


def stop_server(handle: MCPServerHandle) -> None:
    """Tear down any per-handle resources.

    Per Story 3.1 Phase-1 design: each operation self-cleans (the SDK
    session is torn down at the end of `connect_to_server`). So
    `stop_server` is a no-op today — but the keyword surface ships
    now so .robot tests can use the canonical 3-step lifecycle without
    breaking when Phase-1.5 introduces pooled sessions that need
    explicit teardown.

    Args:
        handle: The `MCPServerHandle` to release.
    """
    # Phase-1: no-op. Phase-1.5 may close a pooled session keyed by
    # `handle.name`.
    _ = handle
